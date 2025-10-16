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
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "<EAHJTYAULctYBPozkAuQsRvMfnqGRaz1kprNm3wxmF9gZA4hx9LtWaSZClpnk9fiDGQ4uSe0Fwv7GCGyJN8G4yVvs7UZAASRL4mhBOy6nqwhe2OZA9ovZC7ACU3JdOF4hag9JTmhLVKuK7nVcZAcj6QZAwpnG437jtXLeL6K6xREI04ZB8L2f06rrbaCSiKXmalbTUCuEZCN4ArgZDZD>")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "123darcscar")
FB_GRAPH = "https://graph.facebook.com/v19.0"

# ---------------------
# Configuration management
# ---------------------
CONFIG_FILE = "config.json"
config = {}
config_last_modified = None

def load_config():
    """Load configuration from config.json and cache it"""
    global config, config_last_modified
    try:
        if os.path.exists(CONFIG_FILE):
            current_modified = os.path.getmtime(CONFIG_FILE)
            if config_last_modified != current_modified:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                config_last_modified = current_modified
                logger.info(f"✅ Configuration loaded/reloaded from {CONFIG_FILE}")
        else:
            # Fallback default config
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
            logger.warning(f"⚠️ {CONFIG_FILE} not found, using defaults")
    except Exception as e:
        logger.error(f"❌ Error loading config: {e}")

# Load config on startup
load_config()

# ---------------------
# Store configuration helpers
# ---------------------
def get_config_value(key_path, default=None):
    """Get config value by dot notation path (e.g., 'store_hours.open_time')"""
    load_config()  # Auto-reload if file changed
    keys = key_path.split('.')
    value = config
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default
    return value if value is not None else default

# ---------------------
# Track user states and greetings
# ---------------------
user_states = {}
last_greeted = {}
menu_shown_time = {}  # Track when menu was last shown to prevent spam

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
    tz_name = get_config_value('store_hours.timezone', 'Asia/Manila')
    return datetime.now(ZoneInfo(tz_name))

def get_store_hours():
    """Parse store hours from config"""
    open_str = get_config_value('store_hours.open_time', '10:00')
    close_str = get_config_value('store_hours.close_time', '22:00')
    
    open_parts = open_str.split(':')
    close_parts = close_str.split(':')
    
    open_time = time(int(open_parts[0]), int(open_parts[1]))
    close_time = time(int(close_parts[0]), int(close_parts[1]))
    
    return open_time, close_time

def is_date_closed():
    """Check if today is a special closure date"""
    closed_dates = get_config_value('special_closures.closed_dates', [])
    today = get_manila_time().date().isoformat()
    return today in closed_dates

def is_store_open():
    if is_date_closed():
        logger.info(f"⏱ Store is closed today (special closure)")
        return False
    
    now = get_manila_time().time()
    open_time, close_time = get_store_hours()
    logger.info(f"⏱ Current Manila time: {now}, Store hours: {open_time}-{close_time}")
    return open_time <= now <= close_time

def hours_message():
    if is_date_closed():
        return "🚫 We are closed today. Sorry for the inconvenience!"
    
    now = get_manila_time().time()
    open_time, close_time = get_store_hours()
    
    if is_store_open():
        return f"⏰ We are OPEN today from {open_time.strftime('%I:%M %p')} to {close_time.strftime('%I:%M %p')}."
    if now < open_time:
        return f"🌅 Good morning! We'll open at {open_time.strftime('%I:%M %p')}."
    return f"🌙 We're closed now. We'll open tomorrow at {open_time.strftime('%I:%M %p')}."

def send_daily_greeting(psid):
    today = get_manila_time().date()
    if psid not in last_greeted or last_greeted[psid] != today:
        call_send_api(psid, {"text": hours_message()})
        last_greeted[psid] = today

# ---------------------
# Quick replies menu
# ---------------------
def should_show_menu(psid):
    """Determine if we should show the menu to avoid spam"""
    now = datetime.now()
    last_shown = menu_shown_time.get(psid)
    
    # Show menu if never shown, or if it's been more than 2 minutes
    if not last_shown or (now - last_shown).total_seconds() > 120:
        menu_shown_time[psid] = now
        return True
    return False

def get_quick_replies():
    """Return the quick reply buttons array"""
    return [
        {"content_type": "text", "title": "📋 Menu", "payload": "Q_VIEW_MENU"},
        {"content_type": "text", "title": "🛵 Foodpanda", "payload": "Q_FOODPANDA"},
        {"content_type": "text", "title": "📝 Advance Order", "payload": "Q_ADVANCE_ORDER"},
        {"content_type": "text", "title": "📍 Location", "payload": "Q_LOCATION"},
        {"content_type": "text", "title": "📞 Contact Us", "payload": "Q_CONTACT"},
        {"content_type": "text", "title": "⏰ Store Hours", "payload": "Q_HOURS"},
    ]

def send_message_with_quick_replies(psid, text):
    """Send a message with quick replies embedded"""
    msg = {
        "text": text,
        "quick_replies": get_quick_replies()
    }
    return call_send_api(psid, msg)

# ---------------------
# Buttons / templates
# ---------------------
def send_menu(psid):
    menu_url = get_config_value('urls.menu', 'https://i.imgur.com/c2ir2Qy.jpeg')
    call_send_api(psid, {
        "attachment": {"type": "image", "payload": {"url": menu_url, "is_reusable": True}}
    })
    # Don't show menu again - quick replies are persistent in Messenger

def send_foodpanda(psid):
    foodpanda_url = get_config_value('urls.foodpanda', 'https://www.foodpanda.ph/restaurant/locg/pedros-old-manila-rd')
    call_send_api(psid, {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": "🍴 Tap below to order via Foodpanda:",
                "buttons": [{"type": "web_url", "url": foodpanda_url, "title": "Order Now"}]
            }
        }
    })
    # Don't show menu again - quick replies are persistent in Messenger

def send_location(psid):
    google_map_url = get_config_value('urls.google_map', 'https://maps.app.goo.gl/GQUDgxLqgW6no26X8')
    call_send_api(psid, {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": "📍 Tap below to view our location on Google Maps:",
                "buttons": [{"type": "web_url", "url": google_map_url, "title": "Open Location"}]
            }
        }
    })
    # Don't show menu again - quick replies are persistent in Messenger

def send_contact_info(psid):
    phone_number = get_config_value('contact.phone_number', '09171505518 / (042)4215968')
    call_send_api(psid, {"text": f"☎️ Contact us: {phone_number}"})
    # Don't show menu again - quick replies are persistent in Messenger

# ---------------------
# Handle payloads / messages
# ---------------------
def handle_payload(psid, payload=None, text_message=None):
    send_daily_greeting(psid)

    if payload == "GET_STARTED":
        phone_number = get_config_value('contact.phone_number', '09171505518 / (042)4215968')
        welcome_text = (
            f"Hi! Thanks for messaging Pedro's Classic and Asian Cuisine 🥰🍗🍳🥩\n\n"
            f"For quick orders, call us at {phone_number}.\n\n"
            f"How can I help you today?"
        )
        return send_message_with_quick_replies(psid, welcome_text)

    if payload == "Q_ADVANCE_ORDER":
        if not is_store_open():
            open_time, close_time = get_store_hours()
            call_send_api(psid, {"text": f"🌙 Sorry, we're closed now. We'll open tomorrow at {open_time.strftime('%I:%M %p')}."})
            return  # Don't spam menu

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
                return send_message_with_quick_replies(psid, "✅ Your advance order has been received. Thank you! Anything else?")
            else:
                call_send_api(psid, {"text": "❌ Sorry, we couldn't process your order. Please try again later."})
            logger.info(f"📤 n8n response: {resp.status_code} {resp.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ n8n forwarding error: {e}")
            call_send_api(psid, {"text": "❌ Sorry, we couldn't process your order. Please try again later."})

        user_states.pop(psid, None)
        return

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
        return  # Don't spam menu

    # Default fallback for unrecognized text
    if text_message:
        # Only show quick replies if it hasn't been shown recently (2 min cooldown)
        if should_show_menu(psid):
            return send_message_with_quick_replies(psid, "I can help you with the following options:")
        # Otherwise, don't respond to avoid spam

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
