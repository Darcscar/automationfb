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
