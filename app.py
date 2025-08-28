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
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "YOUR_PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "123darcscar")
FB_GRAPH = "https://graph.facebook.com/v19.0"

# ---------------------
# Config
# ---------------------
FOODPANDA_URL = "https://www.foodpanda.ph/restaurant/locg/pedros-old-manila-rd"
MENU_URL = "https://i.imgur.com/josQM5k.jpeg"
GOOGLE_MAP_URL = "https://maps.app.goo.gl/GQUDgxLqgW6no26X8"
PHONE_NUMBER = "0424215968"
OPEN_TIME = time(10, 0)
CLOSE_TIME = time(22, 0)

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
# Messages
# ---------------------
def send_button_template(psid, text, buttons):
    msg = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": text,
                "buttons": buttons
            }
        }
    }
    return call_send_api(psid, msg)

def send_menu(psid):
    buttons = [{"type": "web_url", "url": MENU_URL, "title": "Open Menu", "webview_height_ratio": "full"}]
    return send_button_template(psid, "📋 Here’s our menu:", buttons)

def send_foodpanda(psid):
    buttons = [{"type": "web_url", "url": FOODPANDA_URL, "title": "Order on Foodpanda"}]
    return send_button_template(psid, "🛵 Order online:", buttons)

def send_location(psid):
    buttons = [{"type": "web_url", "url": GOOGLE_MAP_URL, "title": "View Location"}]
    return send_button_template(psid, "📍 Our location:", buttons)

def send_contact_info(psid):
    return call_send_api(psid, {"text": f"📞 Contact us at {PHONE_NUMBER}"})

def prompt_advance_order(psid):
    now = datetime.now().time()
    if now < OPEN_TIME:
        return call_send_api(psid, {"text": f"📝 You can place your advance order now. It will be prepared once the store opens at {OPEN_TIME.strftime('%I:%M %p')}."})
    return call_send_api(psid, {"text": "📝 Please type your advance order now."})

# ---------------------
# Quick Replies
# ---------------------
def send_main_menu(psid):
    msg = {
        "text": "Please choose an option:",
        "quick_replies": [
            {"content_type": "text", "title": "📋 Menu", "payload": "Q_VIEW_MENU"},
            {"content_type": "text", "title": "🛵 Foodpanda", "payload": "Q_FOODPANDA"},
            {"content_type": "text", "title": "🍴 Advance Order", "payload": "Q_ADVANCE_ORDER"},
            {"content_type": "text", "title": "📞 Contact", "payload": "Q_CONTACT"},
            {"content_type": "text", "title": "📍 Location", "payload": "Q_LOCATION"},
        ]
    }
    return call_send_api(psid, msg)

# ---------------------
# Handle payloads
# ---------------------
def handle_payload(psid, payload):
    if not payload or payload == "GET_STARTED":
        greeting = (
            "Hi! Thanks for messaging Pedro’s Classic and Asian Cuisine 🍗🍳🥩\n"
            "For quick orders, call us at 0917 150 5518 or (042)421 5968. 🥰"
        )
        call_send_api(psid, {"text": greeting})
        return send_main_menu(psid)

    if payload == "Q_VIEW_MENU":
        return send_menu(psid)
    if payload == "Q_FOODPANDA":
        return send_foodpanda(psid)
    if payload == "Q_LOCATION":
        return send_location(psid)
    if payload == "Q_CONTACT":
        return send_contact_info(psid)
    if payload == "Q_ADVANCE_ORDER":
        return prompt_advance_order(psid)

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
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return Response(challenge, status=200, mimetype="text/plain")
        return Response("Forbidden", status=403)

    if request.method == "POST":
        data = request.get_json()
        if data.get("object") == "page":
            for entry in data.get("entry", []):
                for event in entry.get("messaging", []):
                    psid = event.get("sender", {}).get("id")
                    if not psid:
                        continue
                    # Quick replies
                    if "message" in event:
                        msg = event["message"]
                        if msg.get("quick_reply"):
                            handle_payload(psid, msg["quick_reply"].get("payload"))
                    # Postback GET_STARTED
                    elif "postback" in event:
                        payload = event["postback"].get("payload")
                        handle_payload(psid, payload)
        return Response("EVENT_RECEIVED", status=200)

# ---------------------
# Run app
# ---------------------
if __name__ == "__main__":
    PORT = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=PORT, debug=True)
