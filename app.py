import os
import requests
from flask import Flask, request, jsonify

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
AI_API_KEY = os.environ.get("AI_API_KEY")
AI_API_URL = "https://openrouter.ai/api/v1/chat/completions" # أو رابط OpenAI

SYSTEM_PROMPT = """أنت مساعد ذكاء اصطناعي تفاعلي تعمل نيابة عن صاحب الحساب.
القواعد والتعليمات الإجبارية للرد:
1. الإجابة بأسلوب مختصر وشديد السطحية، دون الخوض في تفاصيل معقدة أو اتخاذ أي قرارات.
2. إذا طلب المستخدم تفاصيل دقيقة أو اتخاذ قرار، أبلغه بوجازة أن صاحب الحساب سيراجع المحادثة لاحقاً.
3. التزم بسياق المحادثة والرسائل السابقة المرفقة معك.
4. شرط إجباري لا يتغير: يجب أن تنهي كل رسالة ترسلها بهذا النص تماماً في السطر الأخير:
[🤖 رد آلي بواسطة الذكاء الاصطناعي]"""

app = Flask(__name__)

# ذاكرة مؤقتة لحفظ آخر 6 رسائل لكل محادثة (للحفاظ على السياق)
chat_histories = {}

def get_ai_reply(chat_id, user_text):
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
    
    # إضافة رسالة المستخدم للذاكرة
    chat_histories[chat_id].append({"role": "user", "content": user_text})
    
    # الاحتفاظ بآخر 6 رسائل فقط لعدم استهلاك التوكينز
    chat_histories[chat_id] = chat_histories[chat_id][-6:]
    
    # تجهيز الطلب للذكاء الاصطناعي
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + chat_histories[chat_id]
    
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": messages
    }
    
    try:
        response = requests.post(AI_API_URL, json=payload, headers=headers, timeout=10)
        res_data = response.json()
        bot_reply = res_data["choices"][0]["message"]["content"]
        
        # حفظ رد الذكاء الاصطناعي في الذاكرة
        chat_histories[chat_id].append({"role": "assistant", "content": bot_reply})
        return bot_reply
    except Exception:
        return "تم استلام رسالتك وسيتواصل معك صاحب الحساب فور تفرغه.\n\n[🤖 رد آلي بواسطة الذكاء الاصطناعي]"

@app.route("/", methods=["GET"])
def home():
    return "Server is running!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if "business_message" in data:
        msg = data["business_message"]
        chat_id = msg["chat"]["id"]
        incoming_text = msg.get("text", "")
        business_conn_id = msg.get("business_connection_id")
        
        if incoming_text and business_conn_id:
            reply = get_ai_reply(chat_id, incoming_text)
            
            send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(send_url, json={
                "business_connection_id": business_conn_id,
                "chat_id": chat_id,
                "text": reply
            })
            
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
