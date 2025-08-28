import os
import json
import logging
from flask import Flask, request, Response
import requests
from datetime import datetime, time, date
from zoneinfo import ZoneInfo

app = Flask(__name__)

# ---------------------
# Logging
# ---------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FBBot")

# ---------------------
# Tokens
# ---------------------
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "<YOUR_PAGE_ACCESS_TOKEN>")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "123darcscar")
FB_GRAPH = "https://graph.facebook.com/v19.0"

# ---------------------
# Store configuration
# ---------------------
FOODPANDA_URL = "https://www.foodpanda.ph/restaurant/locg/pedros-old-manila-rd"
MENU_URL = "https://i.imgur.com/josQM5k.jpeg"
GOOGLE_MAP_URL = "https://maps.app.goo.gl/GQUDgxLqgW6no26X8"
PHONE_NUMBER = "09171505518 / (042)4215968"

MANILA_TZ = ZoneInfo("Asia/Manila")
OPEN_TIME = time(10, 0)
CLOSE_TIME = time(22, 0)

# ---------------------
# Track user states
# ---------------------
user_states = {}
last_greeted = {}

# ---------------------
# Helper: Send message
# ---------------------
def call_send_api(psid, message_data):
    url = f"{FB_GRAPH}/me/messages"
    payload = {
        "recipient": {"id": psid},
        "messaging_type": "RESPONSE",
        "message": message_data,
    }
    try:
        r = requests.post(url, params={"access_token": PAGE_ACCESS_TOKEN}, json=payload, timeout=20)
        r.raise_for_status()
        logger.info(f"✅ Message sent to PSID {psid}")
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Send API error: {e}")
        return None

# ---------------------
# Time and store hours
# ---------------------
def get_manila_time():
    return datetime.now(MANILA_TZ)

def is_store_open():
    now = get_manila_time().time()
    logger.info(f"⏱ Current Manila time: {now}")
    return OPEN_TIME <= now <= CLOSE_TIME

def hours_message():
    now = get_manila_time().time()
    if is_store_open():
        return "⏰ We are OPEN today from 10:00 AM to 10:00 PM."
    if now < OPEN_TIME:
        return f"🌅 Good morning! We’ll open at {OPEN_TIME.strftime('%I:%M %p')}."
    return f"🌙 We’re closed now. We’ll open tomorrow at {OPEN_TIME.strftime('%I:%M %p')}."

def send_daily_greeting(psid):
    today = get_manila_time().date()
    if psid not in last_greeted or last_greeted[psid] != today:
        call_send_api(psid, {"text": hours_message()})
        last_greeted[psid] = today

# ---------------------
# Quick replies menu
# ---------------------
def send_main_menu(psid):
    msg = {
        "text": "👇 Please choose an option:",
        "quick_replies": [
            {"content_type": "text", "title": "📋 Menu", "payload": "Q_VIEW_MENU"},
            {"content_type": "text", "title": "🛵 Foodpanda", "payload": "Q_FOODPANDA"},
            {"content_type": "text", "title": "📝 Advance Order", "payload": "Q_ADVANCE_ORDER"},
            {"content_type": "text", "title": "📍 Location", "payload": "Q_LOCATION"},
            {"content_type": "text", "title": "📞 Contact Us", "payload": "Q_CONTACT"},
            {"content_type": "text", "title": "⏰ Store Hours", "payload": "Q_HOURS"},
        ]
    }
    return call_send_api(psid, msg)

# ---------------------
# Buttons / templates
# ---------------------
def send_menu(psid):
    call_send_api(psid, {
        "attachment": {"type": "image", "payload": {"url": MENU_URL, "is_reusable": True}}
    })
    return send_main_menu(psid)

def send_foodpanda(psid):
    call_send_api(psid, {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": "🍴 Tap below to order via Foodpanda:",
                "buttons": [{"type": "web_url", "url": FOODPANDA_URL, "title": "Order Now"}]
            }
        }
    })
    return send_main_menu(psid)

def send_location(psid):
    call_send_api(psid, {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": "📍 Tap below to view our location on Google Maps:",
                "buttons": [{"type": "web_url", "url": GOOGLE_MAP_URL, "title": "Open Location"}]
            }
        }
    })
    return send_main_menu(psid)

def send_contact_info(psid):
    call_send_api(psid, {"text": f"☎️ Contact us: {PHONE_NUMBER}"})
    return send_main_menu(psid)

# ---------------------
# Handle payloads / messages
# ---------------------
def handle_payload(psid, payload=None, text_message=None):
    send_daily_greeting(psid)

    if payload == "GET_STARTED":
        welcome_text = (
            "Hi! Thanks for messaging Pedro’s Classic and Asian Cuisine 🥰🍗🍳🥩\n\n"
            "For quick orders, call us at 0917 150 5518 or (042)421 5968."
        )
        call_send_api(psid, {"text": welcome_text})
        return send_main_menu(psid)

    if payload == "Q_ADVANCE_ORDER":
        call_send_api(psid, {"text": "📝 Please type your order now:"})
        user_states[psid] = "awaiting_order"
        return

    if user_states.get(psid) == "awaiting_order" and text_message:
        logger.info(f"🔹 Forwarding advance order from PSID {psid} to n8n...")
        try:
            n8n_webhook_url = "https://n8n-kbew.onrender.com/webhook/advance-order"
            resp = requests.post(
                n8n_webhook_url,
                json={"psid": psid, "order": text_message},
                timeout=15
            )
            logger.info(f"📤 n8n response status: {resp.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ n8n forwarding error: {e}")

        call_send_api(psid, {"text": "✅ Your advance order has been received. Thank you!"})
        user_states.pop(psid, None)
        return send_main_menu(psid)

    # Quick reply actions
    if payload == "Q_VIEW_MENU":
        return send_menu(psid)
    if payload == "Q_FOODPANDA":
        return send_foodpanda(psid)
    if payload == "Q_LOCATION":
        return send_location(psid)
    if payload == "Q_CONTACT":
        return send_contact_info(psid)
    if payload == "Q_HOURS":
        call_send_api(psid, {"text": hours_message()})
        return send_main_menu(psid)

    # Default fallback for text
    if text_message:
        return send_main_menu(psid)

    return send_main_menu(psid)

# ---------------------
# Webhook
# ---------------------
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        logger.info(f"🔑 Webhook verification attempt: mode={mode}, token={token}")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("✅ Verification successful")
            return Response(challenge, status=200, mimetype="text/plain")
        return Response("Forbidden", status=403)

    # POST
    data = request.get_json()
    logger.info(f"📩 Incoming webhook event: {json.dumps(data, indent=2)}")

    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                psid = event.get("sender", {}).get("id")
                if not psid:
                    logger.warning("⚠️ No PSID found in event")
                    continue

                if "message" in event:
                    msg = event["message"]
                    if msg.get("quick_reply"):
                        handle_payload(psid, payload=msg["quick_reply"].get("payload"))
                    elif "text" in msg:
                        handle_payload(psid, text_message=msg.get("text", "").strip())
                elif "postback" in event:
                    handle_payload(psid, payload=event["postback"].get("payload"))

    return Response("EVENT_RECEIVED", status=200)

# ---------------------
# Run app
# ---------------------
if __name__ == "__main__":
    PORT = int(os.getenv("PORT", 10000))
    logger.info(f"🚀 Starting Flask app on port {PORT}...")
    try:
        app.run(host="0.0.0.0", port=PORT, debug=True)
    except Exception as e:
        logger.error(f"❌ Flask app failed to start: {e}")
