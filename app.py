import requests
import time
import re
from flask import Flask, request, jsonify

TELEGRAM_BOT_TOKEN = "8439529866:AAFDeUsR7nokJHiiZcwT2hApUOyPZjLAFBg"
AI_API_KEY = "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"
AI_API_URL = "https://openrouter.ai/api/v1/chat/completions"

MODEL_NAME = "openrouter/free"

# تعليمات مقفولة بالضبة والمفتاح
SYSTEM_PROMPT = """أنت مساعد آلي ذكي تعمل نيابة عن صاحب الحساب (@p_r_o_m).
قواعد صارمة جداً إياك مخالفتها:
1. **ممنوع التفكير بصوت عالٍ**: أرسل الرد النهائي للعميل مباشرة. ممنوع كتابة أي خطوات تحليل، أو تفكير (Thinking process)، أو ملاحظات داخلية في رسالتك.
2. **التطابق اللغوي**: رد بنفس لغة العميل وأسلوبه (عامية مصرية خفيفة إذا تحدث بها، أو إنجليزية، إلخ).
3. **هويتك**: وضح بلطافة في سياق الكلام أنك "مساعد آلي".
4. **الحدود**: إذا طلب المستخدم أسعار، شغل، أو ملفات، اعتذر بلطف وأخبره أن ينتظر عودة @p_r_o_m لأنه الوحيد المختص بذلك.
5. **التوقيع**: ضع هذا التوقيع في سطر مستقل أسفل الرد (انسخه كما هو بالضبط):
_🤖 مساعد آلي_"""

app = Flask(__name__)

chat_histories = {}
owner_active_sessions = {}
OWNER_PAUSE_DURATION = 300  # 5 دقائق صمت لو أنت اتكلمت

def send_typing_action(chat_id, business_conn_id):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendChatAction"
        requests.post(url, json={
            "business_connection_id": business_conn_id,
            "chat_id": chat_id,
            "action": "typing"
        }, timeout=5)
    except:
        pass

def send_telegram_message(chat_id, business_conn_id, text):
    send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "business_connection_id": business_conn_id,
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(send_url, json=payload, timeout=10)
        if response.status_code != 200:
            payload.pop("parse_mode")
            requests.post(send_url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending message: {e}")

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
        "temperature": 0.7,
        "max_tokens": 400
    }
    
    try:
        response = requests.post(AI_API_URL, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        res_data = response.json()
        
        if "choices" in res_data and len(res_data["choices"]) > 0:
            bot_reply = res_data["choices"][0]["message"]["content"]
            
            # --- فلتر تنظيف قوي يمسح أي تفكير داخلي للنموذج ---
            bot_reply = re.sub(r'<think>.*?</think>', '', bot_reply, flags=re.DOTALL).strip()
            
            chat_histories[chat_id].append({"role": "assistant", "content": bot_reply})
            return bot_reply
        return None
    except Exception as e:
        print(f"AI API Error: {e}")
        return None

@app.route("/", methods=["GET"])
def home():
    return "Bot Server is Robust & Running!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"status": "no data"}), 400

        if "business_message" in data:
            msg = data["business_message"]
            current_time = time.time()
            chat_id = msg.get("chat", {}).get("id")
            business_conn_id = msg.get("business_connection_id")
            
            # الحل القاطع لمشكلة "بيرد وأنا موجود":
            # تليجرام بيبعت is_outgoing = True لو الرسالة مبعوتة من تليفونك أنت
            is_outgoing = msg.get("is_outgoing", False)
            
            if is_outgoing:
                # أنت اللي بعت رسالة -> نسجل وقتك ونقفل البوت
                owner_active_sessions[chat_id] = current_time
                return jsonify({"status": "ignored outgoing, paused bot"}), 200
                
            # لو الرسالة من العميل، نتأكد إنك ما اتكلمتش آخر 5 دقايق
            last_active = owner_active_sessions.get(chat_id, 0)
            if current_time - last_active < OWNER_PAUSE_DURATION:
                return jsonify({"status": "bot paused due to owner activity"}), 200
                
            incoming_text = msg.get("text", "")
            
            if incoming_text and business_conn_id and chat_id:
                send_typing_action(chat_id, business_conn_id)
                reply = get_ai_reply(chat_id, incoming_text)
                
                if reply:
                    send_telegram_message(chat_id, business_conn_id, reply)
                
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Webhook Error: {e}")
        return jsonify({"status": "error"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
