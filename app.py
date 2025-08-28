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
    "YOUR_PAGE_ACCESS_TOKEN"
)
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
# User state
# ---------------------
user_state = {}  # psid: {"step": "order"/"time", "order_text": str}

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
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.error("❌ Send API error: %s", e)
        return None

# ---------------------
# Store hours
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
# Main menu
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
# Other messages
# ---------------------
def send_menu(psid):
    msg = {"attachment": {"type": "image", "payload": {"url": MENU_URL}}}
    return call_send_api(psid, msg)

def send_foodpanda(psid):
    return call_send_api(psid, {"text": FOODPANDA_URL})

def send_location(psid):
    return call_send_api(psid, {"text": GOOGLE_MAP_URL})

def send_contact_info(psid):
    call_send_api(psid, {"text": f"📞 Contact us at {PHONE_NUMBER}"})
    return send_main_menu(psid)

# ---------------------
# Advance Order Flow
# ---------------------
def prompt_advance_order(psid):
    if not is_store_open():
        call_send_api(psid, {"text": store_closed_message()})
        return send_main_menu(psid)
    user_state[psid] = {"step": "order"}
    return call_send_api(psid, {"text": "📝 Please type your advance order."})

def handle_advance_order(psid, text):
    state = user_state.get(psid)
    if not state:
        return send_main_menu(psid)

    if state["step"] == "order":
        state["order_text"] = text
        state["step"] = "time"
        return call_send_api(psid, {"text": f"⏰ What time would you like to pick up your order? (e.g., 02:30 PM)"})
    
    if state["step"] == "time":
        # validate time
        try:
            order_time = datetime.strptime(text, "%I:%M %p").time()
            if not (OPEN_TIME <= order_time <= CLOSE_TIME):
                return call_send_api(psid, {"text": f"⛔ The time must be during store hours ({OPEN_TIME.strftime('%I:%M %p')} - {CLOSE_TIME.strftime('%I:%M %p')})."})
        except ValueError:
            return call_send_api(psid, {"text": "❌ Invalid time format. Please enter time as HH:MM AM/PM."})

        order_text = state.get("order_text")
        call_send_api(psid, {"text": f"✅ Your order has been received:\n{order_text}\nPickup/Dine-in time: {text}"})
        user_state.pop(psid, None)
        return send_main_menu(psid)

# ---------------------
# Handle payloads
# ---------------------
def handle_payload(psid, payload):
    if not payload or payload == "GET_STARTED":
        call_send_api(psid, {"text": "Hi! Thanks for messaging Pedro’s Classic and Asian Cuisine 🍗🍳🥩\nFor quick orders, call us at 0917 150 5518 or (042)421 5968. 🥰"})
        return send_main_menu(psid)

    if payload == "Q_VIEW_MENU":
        return send_menu(psid)
    if payload == "Q_FOODPANDA":
        return send_foodpanda(psid)
    if payload == "Q_LOCATION":
        return send_location(psid)
    if payload == "Q_ADVANCE_ORDER":
        return prompt_advance_order(psid)
    if payload == "Q_CONTACT":
        return send_contact_info(psid)

    return send_main_menu(psid)

# ---------------------
# Webhook
# ---------------------
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.cha
