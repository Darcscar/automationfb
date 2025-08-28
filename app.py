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
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "<YOUR_PAGE_ACCESS_TOKEN>")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "123darcscar")
FB_GRAPH = "https://graph.facebook.com/v19.0"

# ---------------------
# Config
# ---------------------
FOODPANDA_URL = "https://www.foodpanda.ph/restaurant/locg/pedros-old-manila-rd"
MENU_URL = "https://i.imgur.com/josQM5k.jpeg"
GOOGLE_MAP_URL = "https://maps.app.goo.gl/GQUDgxLqgW6no26X8"
PHONE_NUMBER = "0424215968"
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
# Store hours check
# ---------------------
def is_store_open():
    now = datetime.now().time()
    return OPEN_TIME <= now <= CLOSE_TIME

def store_closed_message():
    now = datetime.now().time()
    if now < OPEN_TIME:
        return f"🌅 Good morning! The store will open at {OPEN_TIME.strftime('%I:%M %p')}."
    else:
        return f"🌙 Sorry, the store is closed now. We’ll open tomorrow at {OPEN_TIME.strftime('%I:%M %p')}."

# ---------------------
# Quick Replies Menu
# ---------------------
def send_main_menu(psid):
    msg = {
        "text": "Please choose an option:",
        "quick_replies": [
            {"content_type": "text", "title": "📋 Menu", "payload": "Q_VIEW_MENU"},
            {"content_type": "text", "title": "🛵 Order on Foodpanda", "payload": "Q_FOODPANDA"},
            {"content_type": "text", "title": "🍴 Advance Order", "payload": "Q_ADVANCE_ORDER"},
            {"content_type": "text", "title": "📞 Contact Us", "payload": "Q_CONTACT"},
            {"content_type": "text", "title": "📍 Location", "payload": "Q_LOCATION"},
        ]
    }
    return call_send_api(psid, msg)

# ---------------------
# Send button templates
# ---------------------
def send_menu(psid):
    msg = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": "📋 Full Menu",
                "buttons": [{"type": "web_url", "url": MENU_URL, "title": "Open Menu", "webview_height_ratio": "full"}],
            }
        }
    }
    return call_send_api(psid, msg)

def send_foodpanda(psid):
    msg = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": "🛵 Order on Foodpanda",
                "buttons": [{"type": "web_url", "url": FOODPANDA_URL, "title": "Open Foodpanda"}],
            }
        }
    }
    return call_send_api(psid, msg)

def send_location(psid):
    msg = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": "📍 Our Location",
                "buttons": [{"type": "web_url", "url": GOOGLE_MAP_URL, "title": "View Map"}],
            }
        }
    }
    return call_send_api(psid, msg)

def send_contact_info(psid):
    text = f"📞 Contact us at {PHONE_NUMBER} or reply here and a staff member will assist you."
    call_send_api(psid, {"text": text})
    return send_main_menu(psid)

# ---------------------
# Handle payloads
# ---------------------
def handle_payload(psid, payload=None, text_message=None):
    now = datetime.now().time()

    # GET_STARTED greeting
    if payload == "GET_STARTED":
        welcome_text = (
            "Hi! Thanks for messaging Pedro’s Classic and Asian Cuisine 🍗🍳🥩\n"
            "For quick orders, call us at 0917 150 5518 or (042)421 5968. 🥰"
        )
        call_send_api(psid, {"text": welcome_text})
        return send_main_menu(psid)

    # Advance Order: capture any text typed by user
    if payload == "Q_ADVANCE_ORDER" or text_message:
        # Forward to n8n webhook (uncomment and set your webhook)
        # requests.post("https://n8n-webhook-url", json={"psid": psid, "message": text_message})
        logger.info(f"Advance order from {psid}: {text_message}")
        call_send_api(psid, {"text": "✅ Your advance order has been received and will be prepared once the store opens."})
        return send_main_menu(psid)

    # Normal inquiries outside store hours
    if not is_store_open():
        return call_send_api(psid, {"text": store_closed_message()})

    # Buttons actions
    if payload == "Q_VIEW_MENU":
        return send_menu(psid)
    if payload == "Q_FOODPANDA":
        return send_foodpanda(psid)
    if payload == "Q_LOCATION":
        return send_location(psid)
    if payload == "Q_CONTACT":
        return send_contact_info(psid)

    # Fallback
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

                    if "message" in event:
                        msg = event["message"]
                        if msg.get("quick_reply"):
                            handle_payload(psid, payload=msg["quick_reply"].get("payload"))
                        elif "text" in msg:
                            handle_payload(psid, text_message=msg.get("text").strip())
                    elif "postback" in event:
                        handle_payload(psid, payload=event["postback"].get("payload"))

        return Response("EVENT_RECEIVED", status=200)

# ---------------------
# Run app
# ---------------------
if __name__ == "__main__":
    PORT = int(os.getenv("PORT", 10000))
    logger.info(f"Starting Flask app on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=True)
