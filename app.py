import requests
import time
import re
from flask import Flask, request, jsonify

TELEGRAM_BOT_TOKEN = "8439529866:AAFDeUsR7nokJHiiZcwT2hApUOyPZjLAFBg"
AI_API_KEY = "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"
AI_API_URL = "https://openrouter.ai/api/v1/chat/completions"

MODEL_NAME = "openrouter/free"

# 1. تعليمات "الكاتب" (المسودة الأولى)
DRAFTER_PROMPT = """أنت مساعد آلي ذكي لـ @p_r_o_m.
مهمتك كتابة رد أولي على العميل بالقواعد التالية:
1. تحدث بنفس لغة العميل تماماً.
2. اذكر في سياق الكلام بأسلوب لطيف أنك "مساعد ذكاء اصطناعي".
3. إذا سألك العميل عن تطبيقات، أسعار، تفاصيل تقنية، أو من أنت، قل صراحة أنك مساعد آلي وأن عليه انتظار @p_r_o_m ليجيبه.
4. لا تفكر بصوت عالٍ، أعطني الرد مباشرة."""

# 2. تعليمات "المراجع" (الفلتر الصارم)
REVIEWER_PROMPT = """أنت نظام مراجعة وفلترة صارم. لديك رسالة من عميل، ومسودة رد من ذكاء اصطناعي.
مهمتك هي تعديل المسودة وإخراج الرد النهائي المثالي وفقاً للشروط التالية:
1. الفلسفة وحرية الرد: إذا كان كلام العميل عبارة عن (حرف واحد، شتيمة، أو سبام عشوائي)، أخرج فقط الكلمة التالية: IGNORE_MESSAGE
2. الطول: الرد النهائي يجب ألا يتجاوز سطرين بأي حال من الأحوال. لخصه فوراً إذا كان طويلاً.
3. الهوية: تأكد أن الرد يوضح بوضوح أن المتحدث هو "مساعد ذكاء اصطناعي"، وأنه يؤجل أي تفاصيل معقدة (مثل تصميم التطبيقات) لـ @p_r_o_m.
4. التطابق اللغوي: يجب أن يكون الرد بنفس لغة العميل.
5. التوقيع الديناميكي: أضف التوقيع في النهاية بسطر جديد، مترجماً للغة العميل (مثلاً _🤖 مساعد آلي_ أو _🤖 AI Assistant_).
6. أخرج النص النهائي فقط بدون أي ملاحظات أو <think>."""

app = Flask(__name__)

chat_histories = {}
owner_active_sessions = {}
OWNER_PAUSE_DURATION = 300 

def send_telegram_request(method, payload):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Telegram API Error: {e}")
        return None

def get_ai_response(messages, temp=0.7, max_tokens=200):
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": temp,
        "max_tokens": max_tokens
    }
    try:
        response = requests.post(AI_API_URL, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        # مسح أي تفكير داخلي
        return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    except Exception as e:
        print(f"AI Call Error: {e}")
        return None

def process_ai_logic(chat_id, user_text):
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
    
    # 1. جلب المسودة
    drafter_msgs = [{"role": "system", "content": DRAFTER_PROMPT}] + chat_histories[chat_id][-6:] + [{"role": "user", "content": user_text}]
    draft = get_ai_response(drafter_msgs, temp=0.7)
    
    if not draft: return None
    
    # 2. المراجعة الصارمة
    reviewer_msgs = [
        {"role": "system", "content": REVIEWER_PROMPT},
        {"role": "user", "content": f"رسالة العميل: {user_text}\n\nمسودة الرد: {draft}\n\nقم بالتعديل وإخراج النص النهائي فقط."}
    ]
    final_reply = get_ai_response(reviewer_msgs, temp=0.2, max_tokens=150)
    
    if not final_reply: return None
    
    # فلترة بايثون النهائية كضمان إضافي
    if "IGNORE_MESSAGE" in final_reply:
        return "IGNORE"
        
    lines = [line.strip() for line in final_reply.split('\n') if line.strip()]
    if len(lines) > 3: # السماح بـ 3 أسطر فقط (سطرين للرد وسطر للتوقيع)
        final_reply = '\n'.join(lines[:3])
        
    chat_histories[chat_id].append({"role": "user", "content": user_text})
    chat_histories[chat_id].append({"role": "assistant", "content": final_reply})
    
    return final_reply

@app.route("/", methods=["GET"])
def home():
    return "Dual-Agent AI Bot is Running!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True)
        if not data or "business_message" not in data:
            return jsonify({"status": "ignored"}), 200

        msg = data["business_message"]
        current_time = time.time()
        chat_id = msg.get("chat", {}).get("id")
        business_conn_id = msg.get("business_connection_id")
        is_outgoing = msg.get("is_outgoing", False)
        
        # إسكات البوت إذا كنت أنت من يتحدث
        if is_outgoing:
            owner_active_sessions[chat_id] = current_time
            return jsonify({"status": "bot paused"}), 200
            
        if current_time - owner_active_sessions.get(chat_id, 0) < OWNER_PAUSE_DURATION:
            return jsonify({"status": "bot sleeping"}), 200
            
        incoming_text = msg.get("text", "")
        if incoming_text and business_conn_id and chat_id:
            
            # إرسال رسالة "يُفكر..." كواجهة مستخدم احترافية
            thinking_res = send_telegram_request("sendMessage", {
                "business_connection_id": business_conn_id,
                "chat_id": chat_id,
                "text": "⏳ _يُفكر... / Thinking..._",
                "parse_mode": "Markdown"
            })
            
            msg_id_to_edit = None
            if thinking_res and thinking_res.get("ok"):
                msg_id_to_edit = thinking_res["result"]["message_id"]

            # معالجة الذكاء الاصطناعي المزدوج
            final_reply = process_ai_logic(chat_id, incoming_text)
            
            if final_reply == "IGNORE":
                # مسح رسالة التفكير لأننا سنتجاهل العميل
                if msg_id_to_edit:
                    send_telegram_request("deleteMessage", {"chat_id": chat_id, "message_id": msg_id_to_edit})
            elif final_reply:
                # تعديل رسالة التفكير بالرد النهائي
                if msg_id_to_edit:
                    edit_res = send_telegram_request("editMessageText", {
                        "business_connection_id": business_conn_id, # مهم لتعديل رسائل البيزنس
                        "chat_id": chat_id,
                        "message_id": msg_id_to_edit,
                        "text": final_reply,
                        "parse_mode": "Markdown"
                    })
                    # حماية لو التنسيق غلط
                    if not edit_res.get("ok"):
                        send_telegram_request("editMessageText", {
                            "business_connection_id": business_conn_id,
                            "chat_id": chat_id,
                            "message_id": msg_id_to_edit,
                            "text": final_reply
                        })
                else:
                    # لو فشل يبعت رسالة التفكير، يبعت الرد مباشرة
                    send_telegram_request("sendMessage", {
                        "business_connection_id": business_conn_id,
                        "chat_id": chat_id,
                        "text": final_reply,
                        "parse_mode": "Markdown"
                    })
                
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Fatal Error: {e}")
        return jsonify({"status": "error"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
