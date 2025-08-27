import os
import json
import logging
from flask import Flask, request, Response
import requests
from datetime import datetime, time

app = Flask(__name__)

# ---------------------
# Logging
# ---------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FBBot")

# ---------------------
# Tokens
# ---------------------
PAGE_ACCESS_TOKEN = os.getenv(
    "PAGE_ACCESS_TOKEN",
    "EAHJTYAULctYBPU2QsZCocyqjZBHakvyMR95h0ZCAZACW076ARf8QZAUAgwJ6crkVivna5teNDUlLEVWvxzGKlBlocpvr21iotTels4nZBS6loaMx0eZBCA79R36oXy1uVnIRSJgyhdPZBSSaNeewk59ne2bv9eBZCHpqLRnZBLMsF14ofaZAaSIyje2yXBSTTbOxoZBOVisF3T2zBQZDZD"
)
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "123darcscar")
FB_GRAPH = "https://graph.facebook.com/v19.0"

# ---------------------
# Config
# ---------------------
FOODPANDA_URL = "https://www.foodpanda.ph/restaurant/locg/pedros-old-manila-rd"
MENU_URL = "https://imgur.com/a/byqpSBq"
PHONE_NUMBER = "0424215968"
GOOGLE_MAP_URL = "https://maps.app.goo.gl/GQUDgxLqgW6no26X8"  # Replace with your Google Maps link
OPEN_TIME = time(10, 0)  # 10:00 AM
CLOSE_TIME = time(22, 0)  # 10:00 PM

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
        logger.info("✅ Message sent to PSID %s", psid)
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.error("❌ Send API error: %s", e)
        return None

# ---------------------
# Check store hours
# ---------------------
def is_store_open():
    now = datetime.now().time()
    if OPEN_TIME <= now <= CLOSE_TIME:
        return True
    return False

def store_closed_message():
    now = datetime.now().time()
    if now < OPEN_TIME:
        return f"🌅 Good morning! The store will open at {OPEN_TIME.strftime('%I:%M %p')}."
    else:
        return f"🌙 Sorry, the store is closed now. We’ll open tomorrow at {OPEN_TIME.strftime('%I:%M %p')}."

# ---------------------
# Quick Replies Menu
# ---------------------
def send_quick_replies(psid):
    if not is_store_open():
        return call_send_api(psid, {"text": store_closed_message()})
    
    msg = {
        "text": "Welcome! Please choose an option:",
        "quick_replies": [
            {"content_type": "text", "title": "📋 View Menu", "payload": "Q_VIEW_MENU"},
            {"content_type": "text", "title": "🛵 Order on Foodpanda", "payload": "Q_FOODPANDA"},
            {"content_type": "text", "title": "🍴 Advance Order", "payload": "Q_ADVANCE_ORDER"},
            {"content_type": "text", "title": "📞 Contact Us", "payload": "Q_CONTACT"},
            {"content_type": "text", "title": "📍 Location", "payload": "Q_LOCATION"},
        ]
    }
    return call_send_api(psid, msg)

# ---------------------
# Other Messages
# ---------------------
def send_menu(psid):
    msg = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": "📋 Here’s our full menu:",
                "buttons": [{"type": "web_url", "url": MENU_URL, "title": "Open Menu", "webview_height_ratio": "full"}],
            }
        }
    }
    return call_send_api(psid, msg)

def send_advance_order_info(psid):
    text = (
        "✅ We accept advance orders!\n\n"
        "• For Foodpanda: schedule inside the app.\n"
        "• For dine-in/pickup: reply here with your order and time.\n"
        "We’ll have it ready fresh. 🕑✨"
    )
    call_send_api(psid, {"text": text})
    return send_quick_replies(psid)

def send_contact_info(psid):
    text = f"📞 Contact us at {PHONE_NUMBER} or reply here and a staff member will assist you."
    call_send_api(psid, {"text": text})
    return send_quick_replies(psid)

# ---------------------
# Handle payloads
# ---------------------
def handle_payload(psid, payload):
    if not payload or payload == "GET_STARTED":
        # Send welcome message first
        welcome_text = (
            "Hi! Thanks for messaging Pedro’s Classic and Asian Cuisine 🍗🍳🥩\n"
            "For quick orders, call us at 0917 150 5518 or (042)421 5968. 🥰"
        )
        call_send_api(psid, {"text": welcome_text})
        return send_quick_replies(psid)
    
    if not is_store_open():
        return call_send_api(psid, {"text": store_closed_message()})
    
    if payload == "Q_VIEW_MENU":
        return send_menu(psid)
    if payload == "Q_ADVANCE_ORDER":
        return send_advance_order_info(psid)
    if payload == "Q_CONTACT":
        return send_contact_info(psid)
    if payload == "Q_FOODPANDA":
        call_send_api(psid, {"text": f"Order online here: {FOODPANDA_URL}"})
        return send_quick_replies(psid)
    if payload == "Q_LOCATION":
        call_send_api(psid, {"text": f"📍 Find us here: {GOOGLE_MAP_URL}"})
        return send_quick_replies(psid)
    
    return send_quick_replies(psid)

# ---------------------
# Webhook
# ---------------------
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        logger.info(f"Webhook verification attempt: mode={mode}, token={token}")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("✅ Verification successful")
            return Response(challenge, status=200, mimetype="text/plain")
        return Response("Forbidden", status=403)

    if request.method == "POST":
        data = request.get_json()
        logger.info(f"Incoming webhook event: {json.dumps(data, indent=2)}")

        if data.get("object") == "page":
            for entry in data.get("entry", []):
                for event in entry.get("messaging", []):
                    psid = event.get("sender", {}).get("id")
                    if not psid:
                        continue
                    logger.info(f"New PSID: {psid}")

                    # Message
                    if "message" in event:
                        msg = event["message"]
                        if msg.get("quick_reply"):
                            handle_payload(psid, msg["quick_reply"].get("payload"))
                        elif "text" in msg:
                            send_quick_replies(psid)

                    # Postback (GET_STARTED)
                    elif "postback" in event:
                        payload = event["postback"].get("payload")
                        handle_payload(psid, payload)

        return Response("EVENT_RECEIVED", status=200)

# ---------------------
# Run app
# ---------------------
if __name__ == "__main__":
    PORT = int(os.getenv("PORT", 10000))
    logger.info(f"Starting Flask app on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=True)
