import requests
import time
from flask import Flask, request, jsonify

TELEGRAM_BOT_TOKEN = "8439529866:AAFDeUsR7nokJHiiZcwT2hApUOyPZjLAFBg"
AI_API_KEY = "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"
AI_API_URL = "https://openrouter.ai/api/v1/chat/completions"

MODEL_NAME = "openrouter/free"

# تعليمات مكثفة وصارمة جداً
SYSTEM_PROMPT = """أنت مساعد ذكاء اصطناعي آلي (AI Assistant) تعمل نيابة عن صاحب الحساب (@p_r_o_m).
يجب عليك الالتزام الحرفي والصارم بالقواعد التالية، ولا تقم بكسرها تحت أي ظرف:
1. **التطابق اللغوي المطلق**: أجب بنفس اللغة والأسلوب الذي يستخدمه المستخدم بدقة متناهية (إذا كان إنجليزي رد بالإنجليزي، إذا كان عربي عامي رد بالعامية).
2. **الإفصاح عن الهوية**: في سياق حديثك، وضح دائماً وبشكل ودي ولبق أنك "مساعد آلي ذكي" تتحدث بالنيابة عن @p_r_o_m.
3. **الحدود الصارمة (تأجيل الطلبات)**: إذا طلب المستخدم أي شيء يخرج عن نطاق الدردشة السطحية (مثل: طلبات عمل، استفسار عن أسعار، مشاريع، ملفات، أو مساعدة فنية)، اعتذر بلطف شديد وأخبره أنك كذكاء اصطناعي لا تملك هذه الصلاحيات، وأن عليه الانتظار حتى يعود @p_r_o_m ليتولى الأمر بنفسه. إياك أن تخترع أي معلومات أو أرقام من عندك.
4. **التنسيق (Markdown)**: استخدم التنسيقات لجعل النص مريحاً للعين (مثل وضع الكلمات المهمة بين نجمتين **هكذا**).
5. **التوقيع الإجباري**: لا تنهي رسالتك أبداً بدون هذا التوقيع في سطر مستقل أسفل الرد. قم بترجمته للغة المحادثة واكتبه هكذا بدون أي أقواس:
_🤖 AI Assistant_"""

app = Flask(__name__)

chat_histories = {}
# قاموس لتسجيل آخر ظهور لصاحب الحساب في كل محادثة
owner_active_sessions = {}
# مدة إسكات البوت لو صاحب الحساب بيكتب (300 ثانية = 5 دقائق)
OWNER_PAUSE_DURATION = 300 

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
        # إذا رفض تليجرام الرسالة بسبب خطأ في تنسيق الـ Markdown، أرسلها كنص عادي
        if response.status_code != 200:
            payload.pop("parse_mode")
            requests.post(send_url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending message: {e}")

def get_ai_reply(chat_id, user_text):
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
    
    chat_histories[chat_id].append({"role": "user", "content": user_text})
    chat_histories[chat_id] = chat_histories[chat_id][-10:]
    
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
            
            sender_id = msg.get("from", {}).get("id")
            chat_id = msg.get("chat", {}).get("id")
            
            # 1. هل الرسالة دي طالعة منك أنت (صاحب الحساب)؟
            if sender_id and chat_id and sender_id != chat_id:
                # نسجل إنك اكتيف في المحادثة دي دلوقتي
                owner_active_sessions[chat_id] = current_time
                return jsonify({"status": "ignored outgoing, paused bot"}), 200
                
            # 2. لو العميل هو اللي باعت، نتأكد إنك مش موجود في المحادثة
            last_active = owner_active_sessions.get(chat_id, 0)
            if current_time - last_active < OWNER_PAUSE_DURATION:
                # البوت هيسكت ومش هيرد لأنك لسه باعت رسالة من أقل من 5 دقايق
                return jsonify({"status": "bot paused due to owner activity"}), 200
                
            incoming_text = msg.get("text", "")
            business_conn_id = msg.get("business_connection_id")
            
            # 3. لو أنت مش موجود والرسالة من العميل، البوت يبدأ شغله
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
