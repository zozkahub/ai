import requests
from flask import Flask, request, jsonify

TELEGRAM_BOT_TOKEN = "8439529866:AAFDeUsR7nokJHiiZcwT2hApUOyPZjLAFBg"
AI_API_KEY = "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"
AI_API_URL = "https://openrouter.ai/api/v1/chat/completions"

MODEL_NAME = "openrouter/free"

SYSTEM_PROMPT = """You are an AI assistant acting on behalf of @p_r_o_m.
Mandatory rules for your responses:
1. Reply entirely in English. Keep it very brief, casual, and superficial.
2. Do not repeat the user's words. Answer directly and simply without committing to any decisions.
3. If the user asks for complex details, dates, or prices, briefly state that @p_r_o_m will check the chat and reply later.
4. Mandatory rule: You must end EVERY single message with this exact text on a new line at the very bottom:
[🤖 Automated AI Reply]"""

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
        # هنا البوت مش هيرد بأي رسالة احتياطية لو حصل خطأ
        return None

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
            
            sender_id = msg.get("from", {}).get("id")
            chat_id = msg.get("chat", {}).get("id")
            
            # --- سطر الحماية: يتجاهل رسائلك الشخصية نهائياً ---
            # لو الـ ID بتاع المرسل مختلف عن الـ ID بتاع المحادثة، ده معناه إن صاحب الحساب هو اللي بيكتب
            if sender_id and chat_id and sender_id != chat_id:
                return jsonify({"status": "ignored outgoing"}), 200
                
            incoming_text = msg.get("text", "")
            business_conn_id = msg.get("business_connection_id")
            
            if incoming_text and business_conn_id and chat_id:
                send_typing_action(chat_id, business_conn_id)
                reply = get_ai_reply(chat_id, incoming_text)
                
                # لن يرسل الرسالة إلا إذا كان هناك رد ناجح من الذكاء الاصطناعي
                if reply:
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
