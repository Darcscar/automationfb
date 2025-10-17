"""
FINAL WORKING VERSION - Facebook Bot for Pedro's Restaurant
Copy this ENTIRE file to your app.py
"""

import os
import json
import logging
from flask import Flask, request, Response
import requests
from datetime import datetime, time, date, timedelta
from zoneinfo import ZoneInfo

app = Flask(__name__)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FBBot")

# Tokens
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "EAHJTYAULctYBPozkAuQsRvMfnqGRaz1kprNm3wxmF9gZA4hx9LtWaSZClpnk9fiDGQ4uSe0Fwv7GCGyJN8G4yVvs7UZAASRL4mhBOy6nqwhe2OZA9ovZC7ACU3JdOF4hag9JTmhLVKuK7nVcZAcj6QZAwpnG437jtXLeL6K6xREI04ZB8L2f06rrbaCSiKXmalbTUCuEZCN4ArgZDZD")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "123darcscar")
FB_GRAPH = "https://graph.facebook.com/v19.0"

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://tgawpkpcfrxobgrsysic.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRnYXdwa3BjZnJ4b2JncnN5c2ljIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTM1ODI5NjQsImV4cCI6MjA2OTE1ODk2NH0.AsNuusVkPzozfCB6QTyLy5cnQUgwmXsjNhNH3hb75Ew")

# Configuration
CONFIG_FILE = "config.json"
config = {}
config_last_modified = None

def load_config():
    global config, config_last_modified
    try:
        if os.path.exists(CONFIG_FILE):
            current_modified = os.path.getmtime(CONFIG_FILE)
            if config_last_modified != current_modified:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                config_last_modified = current_modified
                logger.info(f"Configuration loaded from {CONFIG_FILE}")
        else:
            config = {
                "store_hours": {"open_time": "10:00", "close_time": "22:00", "timezone": "Asia/Manila"},
                "contact": {"phone_number": "09171505518 / (042)4215968"},
                "urls": {
                    "foodpanda": "https://www.foodpanda.ph/restaurant/locg/pedros-old-manila-rd",
                    "menu": "https://i.imgur.com/c2ir2Qy.jpeg",
                    "google_map": "https://maps.app.goo.gl/GQUDgxLqgW6no26X8"
                },
                "special_closures": {"closed_dates": []}
            }
            logger.warning(f"{CONFIG_FILE} not found, using defaults")
    except Exception as e:
        logger.error(f"Error loading config: {e}")

load_config()

def get_config_value(key_path, default=None):
    load_config()
    keys = key_path.split('.')
    value = config
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default
    return value if value is not None else default

# User states
user_states = {}
last_greeted = {}
menu_shown_time = {}
user_menu_muted_until = {}

# Save order to Supabase
def save_order_to_supabase(psid, order_text):
    try:
        now = datetime.now(ZoneInfo('Asia/Manila'))
        order_number = f"FB-{now.strftime('%Y%m%d')}-{psid[-6:]}"
        
        url = f"{SUPABASE_URL}/rest/v1/online_orders"
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        payload = {
            "order_number": order_number,
            "facebook_psid": psid,
            "order_text": order_text,
            "order_type": "pickup",
            "status": "pending",
            "order_date": now.isoformat()
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        
        logger.info(f"Order saved to Supabase: {order_number}")
        return True, order_number
        
    except Exception as e:
        logger.error(f"Supabase save error: {e}")
        return False, None

# Send message
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
        logger.info(f"Message sent to PSID {psid}")
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Send API error: {e}")
        return None

# Time functions
def get_manila_time():
    tz_name = get_config_value('store_hours.timezone', 'Asia/Manila')
    return datetime.now(ZoneInfo(tz_name))

def get_store_hours():
    open_str = get_config_value('store_hours.open_time', '10:00')
    close_str = get_config_value('store_hours.close_time', '22:00')
    open_parts = open_str.split(':')
    close_parts = close_str.split(':')
    open_time = time(int(open_parts[0]), int(open_parts[1]))
    close_time = time(int(close_parts[0]), int(close_parts[1]))
    return open_time, close_time

def is_date_closed():
    closed_dates = get_config_value('special_closures.closed_dates', [])
    today = get_manila_time().date().isoformat()
    return today in closed_dates

def is_store_open():
    if is_date_closed():
        return False
    now = get_manila_time().time()
    open_time, close_time = get_store_hours()
    return open_time <= now <= close_time

def hours_message():
    if is_date_closed():
        return "We are closed today. Sorry for the inconvenience!"
    now = get_manila_time().time()
    open_time, close_time = get_store_hours()
    if is_store_open():
        return f"We are OPEN today from {open_time.strftime('%I:%M %p')} to {close_time.strftime('%I:%M %p')}."
    if now < open_time:
        return f"Good morning! We'll open at {open_time.strftime('%I:%M %p')}."
    return f"We're closed now. We'll open tomorrow at {open_time.strftime('%I:%M %p')}."

def send_daily_greeting(psid):
    today = get_manila_time().date()
    if psid not in last_greeted or last_greeted[psid] != today:
        call_send_api(psid, {"text": hours_message()})
        last_greeted[psid] = today

# Quick replies
def should_show_menu(psid):
    if get_config_value('menu_suppression.suppress_menu_globally', False):
        return False
    muted_until = user_menu_muted_until.get(psid)
    if muted_until and datetime.now() < muted_until:
        return False
    now = datetime.now()
    last_shown = menu_shown_time.get(psid)
    if not last_shown or (now - last_shown).total_seconds() > 120:
        menu_shown_time[psid] = now
        return True
    return False

def get_quick_replies():
    return [
        {"content_type": "text", "title": "Menu", "payload": "Q_VIEW_MENU"},
        {"content_type": "text", "title": "Foodpanda", "payload": "Q_FOODPANDA"},
        {"content_type": "text", "title": "Advance Order", "payload": "Q_ADVANCE_ORDER"},
        {"content_type": "text", "title": "Location", "payload": "Q_LOCATION"},
        {"content_type": "text", "title": "Contact Us", "payload": "Q_CONTACT"},
        {"content_type": "text", "title": "Store Hours", "payload": "Q_HOURS"},
    ]

def send_message_with_quick_replies(psid, text):
    msg = {"text": text, "quick_replies": get_quick_replies()}
    return call_send_api(psid, msg)

def send_menu(psid):
    menu_url = get_config_value('urls.menu', 'https://i.imgur.com/c2ir2Qy.jpeg')
    call_send_api(psid, {"attachment": {"type": "image", "payload": {"url": menu_url, "is_reusable": True}}})

def send_foodpanda(psid):
    foodpanda_url = get_config_value('urls.foodpanda', 'https://www.foodpanda.ph/restaurant/locg/pedros-old-manila-rd')
    call_send_api(psid, {"attachment": {"type": "template", "payload": {"template_type": "button", "text": "Tap below to order via Foodpanda:", "buttons": [{"type": "web_url", "url": foodpanda_url, "title": "Order Now"}]}}})

def send_location(psid):
    google_map_url = get_config_value('urls.google_map', 'https://maps.app.goo.gl/GQUDgxLqgW6no26X8')
    call_send_api(psid, {"attachment": {"type": "template", "payload": {"template_type": "button", "text": "Tap below to view our location:", "buttons": [{"type": "web_url", "url": google_map_url, "title": "Open Location"}]}}})

def send_contact_info(psid):
    phone_number = get_config_value('contact.phone_number', '09171505518 / (042)4215968')
    call_send_api(psid, {"text": f"Contact us: {phone_number}"})

# Handle messages
def handle_payload(psid, payload=None, text_message=None):
    send_daily_greeting(psid)

    if payload == "GET_STARTED":
        phone_number = get_config_value('contact.phone_number', '09171505518 / (042)4215968')
        welcome_text = f"Hi! Thanks for messaging Pedro's Classic and Asian Cuisine\n\nFor quick orders, call us at {phone_number}.\n\nHow can I help you today?"
        return send_message_with_quick_replies(psid, welcome_text)

    if payload == "Q_ADVANCE_ORDER":
        if not is_store_open():
            open_time, close_time = get_store_hours()
            call_send_api(psid, {"text": f"Sorry, we're closed now. We'll open tomorrow at {open_time.strftime('%I:%M %p')}."})
            return
        call_send_api(psid, {"text": "Please type your order now:"})
        user_states[psid] = "awaiting_order"
        return

    if user_states.get(psid) == "awaiting_order" and text_message:
        success, order_number = save_order_to_supabase(psid, text_message)
        
        if success:
            return send_message_with_quick_replies(psid, f"Your advance order has been received!\n\nOrder Number: {order_number}\n\nWe'll prepare your order and contact you when it's ready. Thank you!")
        else:
            call_send_api(psid, {"text": "Sorry, we couldn't process your order. Please try again later."})
        
        user_states.pop(psid, None)
        return

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
        return

    if text_message:
        lower_text = text_message.lower()
        agent_names = get_config_value('menu_suppression.agent_names', []) or []
        if any(name in lower_text for name in agent_names):
            user_menu_muted_until[psid] = datetime.now().replace(microsecond=0) + timedelta(hours=24)
            return
        if should_show_menu(psid):
            return send_message_with_quick_replies(psid, "I can help you with the following options:")

# Webhook: Notify customer order is ready
@app.route("/webhook/order-ready", methods=["POST"])
def notify_order_ready():
    try:
        data = request.get_json()
        psid = data.get("psid")
        order_number = data.get("order_number")
        customer_name = data.get("customer_name", "Customer")
        
        if not psid or not order_number:
            logger.error("Missing PSID or order_number")
            return Response(json.dumps({"error": "Missing required fields"}), status=400, mimetype="application/json")
        
        logger.info(f"Notifying PSID {psid} for order {order_number}")
        
        # Build message
        restaurant_name = get_config_value('contact.restaurant_name', "Pedro's Restaurant")
        message_text = f"Good news! Your order #{order_number} is ready for pickup!\n\nPlease come to {restaurant_name} to pick up your order.\n\nSee you soon! Thank you for ordering with us!"
        
        result = call_send_api(psid, {"text": message_text})
        
        if result:
            logger.info(f"Notification sent to {customer_name}")
            return Response(json.dumps({"success": True}), status=200, mimetype="application/json")
        else:
            return Response(json.dumps({"error": "Failed to send"}), status=500, mimetype="application/json")
            
    except Exception as e:
        logger.error(f"Notification error: {e}")
        return Response(json.dumps({"error": str(e)}), status=500, mimetype="application/json")

# Main webhook
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("Verification successful")
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

# Run
if __name__ == "__main__":
    PORT = int(os.getenv("PORT", 10000))
    logger.info(f"Starting Flask app on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT, debug=True)

