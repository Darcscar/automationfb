import os
import json
import logging
from flask import Flask, request, Response
import requests

app = Flask(__name__)

# ---------------------
# Logging
# ---------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------
# Tokens
# ---------------------
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "EAHJTYAULctYBPU2QsZCocyqjZBHakvyMR95h0ZCAZACW076ARf8QZAUAgwJ6crkVivna5teNDUlLEVWvxzGKlBlocpvr21iotTels4nZBS6loaMx0eZBCA79R36oXy1uVnIRSJgyhdPZBSSaNeewk59ne2bv9eBZCHpqLRnZBLMsF14ofaZAaSIyje2yXBSTTbOxoZBOVisF3T2zBQZDZD")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "123darcscar")
FB_GRAPH = "https://graph.facebook.com/v19.0"

# ---------------------
# Config
# ---------------------
FOODPANDA_URL = "https://www.foodpanda.ph/restaurant/locg/pedros-old-manila-rd"
MENU_URL = "https://imgur.com/a/byqpSBq"
PHONE_NUMBER = "0424215968"

# ---------------------
# Helpers
# ---------------------
def call_send_api(psid, message_data):
    url = f"{FB_GRAPH}/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    payload = {
        "recipient": {"id": psid},
        "messaging_type": "RESPONSE",
        "message": message_data
    }
    try:
        r = requests.post(url, params=params, json=payload, timeout=20)
        r.raise_for_status()
        logger.info("✅ Message sent to PSID %s", psid)
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.error("❌ Send API error: %s", e)
        return None

# ---------------------
# Message Templates
# ---------------------
def send_vertical_menu(psid):
    msg = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "generic",
                "elements": [
                    {
                        "title": "📋 View Menu",
                        "subtitle": "See all dishes",
                        "buttons": [{"type": "postback", "title": "Open Menu", "payload": "Q_VIEW_MENU"}]
                    },
                    {
                        "title": "🛵 Order on Foodpanda",
                        "subtitle": "Order online",
                        "buttons": [{"type": "web_url", "title": "Open Foodpanda", "url": FOODPANDA_URL}]
                    },
                    {
                        "title": "🍴 Advance Order",
                        "subtitle": "Schedule in advance",
                        "buttons": [{"type": "postback", "title": "Order Ahead", "payload": "Q_ADVANCE_ORDER"}]
                    },
                    {
                        "title": "📞 Contact Us",
                        "subtitle": f"Reach us at {PHONE_NUMBER}",
                        "buttons": [{"type": "postback", "title": "Call Us", "payload": "Q_CONTACT"}]
                    }
                ]
            }
        }
    }
    return call_send_api(psid, msg)

def send_menu(psid):
    msg = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": "📋 Here’s our full menu:",
                "buttons": [
                    {"type": "web_url", "url": MENU_URL, "title": "Open Menu", "webview_height_ratio": "full"}
                ]
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
    return send_vertical_menu(psid)

def send_contact_info(psid):
    text = f"📞 Contact us at {PHONE_NUMBER} or reply here and a staff member will assist you."
    call_send_api(psid, {"text": text})
    return send_vertical_menu(psid)

# ---------------------
# Handle payloads
# ---------------------
def handle_payload(psid, payload):
    if not payload:
        return send_vertical_menu(psid)
    if payload == "GET_STARTED":
        return send_vertical_menu(psid)
    if payload == "Q_VIEW_MENU":
        return send_menu(psid)
    if payload == "Q_ADVANCE_ORDER":
        return send_advance_order_info(psid)
    if payload == "Q_CONTACT":
        return send_contact_info(psid)
    return send_vertical_menu(psid)

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
                            handle_payload(psid, msg["quick_reply"].get("payload"))
                        elif "text" in msg:
                            send_vertical_menu(psid)

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
