import os
import json
import logging
from flask import Flask, request, Response
import requests
from datetime import datetime, time
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
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "<EAHJTYAULctYBPozkAuQsRvMfnqGRaz1kprNm3wxmF9gZA4hx9LtWaSZClpnk9fiDGQ4uSe0Fwv7GCGyJN8G4yVvs7UZAASRL4mhBOy6nqwhe2OZA9ovZC7ACU3JdOF4hag9JTmhLVKuK7nVcZAcj6QZAwpnG437jtXLeL6K6xREI04ZB8L2f06rrbaCSiKXmalbTUCuEZCN4ArgZDZD>")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "123darcscar")
FB_GRAPH = "https://graph.facebook.com/v19.0"

# ---------------------
# Store configuration
# ---------------------
FOODPANDA_URL = "https://www.foodpanda.ph/restaurant/locg/pedros-old-manila-rd"
MENU_URL = "https://i.imgur.com/c2ir2Qy.jpeg"
GOOGLE_MAP_URL = "https://maps.app.goo.gl/GQUDgxLqgW6no26X8"
PHONE_NUMBER = "09171505518 / (042)4215968"

MANILA_TZ = ZoneInfo("Asia/Manila")
OPEN_TIME = time(10, 0)
CLOSE_TIME = time(22, 0)

# ---------------------
# Track user states and menu
# ---------------------
user_states = {}       # Tracks states like "awaiting_order"
menu_shown = {}        # Tracks if the main menu has already been sent
last_greeted = {}      # Tracks daily greetings

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
MAIN_MENU = [
    {"content_type": "text", "title": "📋 Menu", "payload": "Q_VIEW_MENU"},
    {"content_type": "text", "title": "🛵 Foodpanda", "payload": "Q_FOODPANDA"},
    {"content_type": "text", "title": "📝 Advance Order", "payload": "Q_ADVANCE_ORDER"},
    {"content_type": "text", "title": "📍 Location", "payload": "Q_LOCATION"},
    {"content_type": "text", "title": "📞 Contact Us", "payload": "Q_CONTACT"},
    {"content_type": "text", "title": "⏰ Store Hours", "payload": "Q_HOURS"},
]

def send_main_menu(psid, message_text="👇 Please choose an option:"):
    msg = {
        "text": message_text,
        "quick_replies": MAIN_MENU
    }
    return call_send_api(psid, msg)

# ---------------------
# Buttons / templates
# ---------------------
def send_menu(psid):
    call_send_api(psid, {
        "attachment": {"type": "image", "payload": {"url": MENU_URL, "is_reusable": True}}
    })
    menu_shown[psid] = True
    return send_main_menu(psid, message_text="Here's our menu, select an option:")

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
    menu_shown[psid] = True
    return send_main_menu(psid, message_text="Back to menu:")

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
    menu_shown[psid] = True
    return send_main_menu(psid, message_text="Back to menu:")

def send_contact_info(psid):
    call_send_api(psid, {"text": f"☎️ Contact us: {PHONE_NUMBER}"})
    menu_shown[psid] = True
    return send_main_menu(psid, message_text="Back to menu:")

# ---------------------
# Handle payloads / messages
# ---------------------
def handle_payload(psid, payload=None, text_message=None):
    send_daily_greeting(psid)

    # Helper to send menu only if not shown
    def maybe_show_menu(msg_text="👇 Please choose an option:"):
        if not menu_shown.get(psid, False):
            send_main_menu(psid, msg_text)
            menu_shown[psid] = True

    if payload == "GET_STARTED":
        welcome_text = (
            "Hi! Thanks for messaging Pedro’s Classic and Asian Cuisine 🥰🍗🍳🥩\n\n"
            "For quick orders, call us at 0917 150 5518 or (042)421 5968."
        )
        call_send_api(psid, {"text": welcome_text})
        maybe_show_menu()
        return

    if payload == "Q_ADVANCE_ORDER":
        if not is_store_open():
            call_send_api(psid, {"text": f"🌙 Sorry, we’re closed now. We’ll open tomorrow at {OPEN_TIME.strftime('%I:%M %p')}."})
            maybe_show_menu("Back to menu:")
            return

        call_send_api(psid, {"text": "📝 Please type your order now:"})
        user_states[psid] = "awaiting_order"
        return

    if user_states.get(psid) == "awaiting_order" and text_message:
        try:
            n8n_webhook_url = "https://n8n-kbew.onrender.com/webhook/advance-order"
            resp = requests.post(
                n8n_webhook_url,
                json={"psid": psid, "order": text_message},
                timeout=15
            )
            if resp.status_code == 200:
                call_send_api(psid, {"text": "✅ Your advance order has been received. Thank you!"})
            else:
                call_send_api(psid, {"text": "❌ Sorry, we couldn't process your order. Please try again later."})
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ n8n forwarding error: {e}")
            call_send_api(psid, {"text": "❌ Sorry, we couldn't process your order. Please try again later."})

        user_states.pop(psid, None)
        menu_shown[psid] = False  # allow menu to appear again
        maybe_show_menu("Back to menu:")
        return

    # Quick reply actions
    if payload == "Q_VIEW_MENU":
        menu_shown[psid] = False
        send_menu(psid)
        return
    if payload == "Q_FOODPANDA":
        menu_shown[psid] = False
        send_foodpanda(psid)
        return
    if payload == "Q_LOCATION":
        menu_shown[psid] = False
        send_location(psid)
        return
    if payload == "Q_CONTACT":
        menu_shown[psid] = False
        send_contact_info(psid)
        return
    if payload == "Q_HOURS":
        call_send_api(psid, {"text": hours_message()})
        maybe_show_menu("Back to menu:")
        return

    # Fallback: for any text that isn’t an order or quick reply
    if text_message:
        maybe_show_menu("Select an option from the menu below:")
        return

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

    data = request.get_json()
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                psid = event.get("sender", {}).get("id")
                if not psid:
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
    app.run(host="0.0.0.0", port=PORT, debug=True)
