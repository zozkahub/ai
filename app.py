import requests
from flask import Flask, request, jsonify

TELEGRAM_BOT_TOKEN = "8439529866:AAFDeUsR7nokJHiiZcwT2hApUOyPZjLAFBg"
AI_API_KEY = "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"
AI_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "google/gemma-4-31b-it:free"

SYSTEM_PROMPT = """أنت مساعد ذكاء اصطناعي تعمل نيابة عن (prom).
القواعد والتعليمات الإجبارية للرد:
1. رد بالعامية المصرية الخفيفة والودية وبأسلوب مختصر وسريع جداً او بنفس لهجة المستخدم.
2. لا تقم بتكرار كلام المستخدم أو تحويله لفصحى، بل أجب على سؤاله مباشرة بإجابة سطحية وبسيطة.
3. إذا طلب تفاصيل معقدة أو مواعيد، أبلغه بوجازة أن زياد سيشاهد الرسالة ويزوده بالتفاصيل فور تفرغه.
4. شرط إجباري: يجب أن تنهي كل رسالة بهذا النص في سطر مستقل أسفل الرد:
[🤖 رد آلي بواسطة الذكاء الاصطناعي]"""

app = Flask(__name__)

chat_histories = {}

def send_typing_action(chat_id, business_conn_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendChatAction"
    requests.post(url, json={
        "business_connection_id": business_conn_id,
        "chat_id": chat_id,
        "action": "typing"
    })

def get_ai_reply(chat_id, user_text):
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
    
    chat_histories[chat_id].append({"role": "user", "content": user_text})
    chat_histories[chat_id] = chat_histories[chat_id][-8:]
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + chat_histories[chat_id]
    
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(AI_API_URL, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        res_data = response.json()
        bot_reply = res_data["choices"][0]["message"]["content"]
        
        chat_histories[chat_id].append({"role": "assistant", "content": bot_reply})
        return bot_reply
    except Exception as e:
        print(f"AI Error: {e}")
        return "أهلاً بك! رسالتك وصلت، وزياد هيشوفها ويرد عليك في أقرب وقت.\n\n[🤖 رد آلي بواسطة الذكاء الاصطناعي]"

@app.route("/", methods=["GET"])
def home():
    return "Bot Server is Online & Running!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "no data"}), 400

        if "business_message" in data:
            msg = data["business_message"]
            chat_id = msg.get("chat", {}).get("id")
            incoming_text = msg.get("text", "")
            business_conn_id = msg.get("business_connection_id")
            
            if incoming_text and business_conn_id and chat_id:
                send_typing_action(chat_id, business_conn_id)
                reply = get_ai_reply(chat_id, incoming_text)
                
                send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                requests.post(send_url, json={
                    "business_connection_id": business_conn_id,
                    "chat_id": chat_id,
                    "text": reply
                })
                
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Webhook Error: {e}")
        return jsonify({"status": "error"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
