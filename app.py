# ---------------------
# Notification: Order Ready
# ---------------------
@app.route("/webhook/order-ready", methods=["POST"])
def notify_order_ready():
    """Send notification to customer when order is ready for pickup"""
    try:
        data = request.get_json()
        psid = data.get("psid")
        order_number = data.get("order_number")
        customer_name = data.get("customer_name", "Customer")
        
        if not psid or not order_number:
            logger.error("Missing PSID or order_number in notification request")
            return Response(json.dumps({"error": "Missing required fields"}), status=400, mimetype="application/json")
        
        logger.info(f"Sending order ready notification to PSID {psid} for order {order_number}")
        
        # Send notification message to customer
        message_text = (
            f"Good news! Your order #{order_number} is ready for pickup!\n\n"
            f"Please come to {get_config_value('contact.restaurant_name', 'Pedro\\'s Restaurant')} to pick up your order.\n\n"
            f"See you soon! Thank you for ordering with us!"
        )
        
        result = call_send_api(psid, {"text": message_text})
        
        if result:
            logger.info(f"Order ready notification sent successfully to {customer_name}")
            return Response(json.dumps({"success": True, "message": "Customer notified"}), status=200, mimetype="application/json")
        else:
            logger.error("Failed to send notification via Facebook API")
            return Response(json.dumps({"error": "Failed to send message"}), status=500, mimetype="application/json")
            
    except Exception as e:
        logger.error(f"Error in order ready notification: {e}")
        return Response(json.dumps({"error": str(e)}), status=500, mimetype="application/json")

# ---------------------
# Webhook
# ---------------------
@app.route("/webhook", methods=["GET", "POST"])
                    "menu": "https://i.imgur.com/c2ir2Qy.jpeg",
                    "google_map": "https://maps.app.goo.gl/GQUDgxLqgW6no26X8"
                },
                "special_closures": {"closed_dates": []}
            }
            logger.warning(f"{CONFIG_FILE} not found, using defaults")
    except Exception as e:
        logger.error(f"Error loading config: {e}")

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
menu_shown_time = {}
user_menu_muted_until = {}

# ---------------------
# SUPABASE: Save order to database
# ---------------------
def save_order_to_supabase(psid, order_text):
    """Save Facebook order directly to Supabase"""
    try:
        # Generate order number: FB-YYYYMMDD-XXXXXX
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
            "order_type": "pickup",  # Default, can be changed by staff
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
        logger.info(f"Message sent to PSID {psid}")
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Send API error: {e}")
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
        logger.info(f"Store is closed today (special closure)")
        return False
    
    now = get_manila_time().time()
    open_time, close_time = get_store_hours()
    logger.info(f"Current Manila time: {now}, Store hours: {open_time}-{close_time}")
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

# ---------------------
# Quick replies menu
# ---------------------
def should_show_menu(psid):
    """Determine if we should show the menu to avoid spam"""
    # Global suppression via config
    if get_config_value('menu_suppression.suppress_menu_globally', False):
        return False

    # Per-user mute window
    muted_until = user_menu_muted_until.get(psid)
    if muted_until and datetime.now() < muted_until:
        return False

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
        {"content_type": "text", "title": "Menu", "payload": "Q_VIEW_MENU"},
        {"content_type": "text", "title": "Foodpanda", "payload": "Q_FOODPANDA"},
        {"content_type": "text", "title": "Advance Order", "payload": "Q_ADVANCE_ORDER"},
        {"content_type": "text", "title": "Location", "payload": "Q_LOCATION"},
        {"content_type": "text", "title": "Contact Us", "payload": "Q_CONTACT"},
        {"content_type": "text", "title": "Store Hours", "payload": "Q_HOURS"},
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

def send_foodpanda(psid):
    foodpanda_url = get_config_value('urls.foodpanda', 'https://www.foodpanda.ph/restaurant/locg/pedros-old-manila-rd')
    call_send_api(psid, {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": "Tap below to order via Foodpanda:",
                "buttons": [{"type": "web_url", "url": foodpanda_url, "title": "Order Now"}]
            }
        }
    })

def send_location(psid):
    google_map_url = get_config_value('urls.google_map', 'https://maps.app.goo.gl/GQUDgxLqgW6no26X8')
    call_send_api(psid, {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": "Tap below to view our location on Google Maps:",
                "buttons": [{"type": "web_url", "url": google_map_url, "title": "Open Location"}]
            }
        }
    })

def send_contact_info(psid):
    phone_number = get_config_value('contact.phone_number', '09171505518 / (042)4215968')
    call_send_api(psid, {"text": f"Contact us: {phone_number}"})

# ---------------------
# Handle payloads / messages
# ---------------------
def handle_payload(psid, payload=None, text_message=None):
    send_daily_greeting(psid)

    if payload == "GET_STARTED":
        phone_number = get_config_value('contact.phone_number', '09171505518 / (042)4215968')
        welcome_text = (
            f"Hi! Thanks for messaging Pedro's Classic and Asian Cuisine\n\n"
            f"For quick orders, call us at {phone_number}.\n\n"
            f"How can I help you today?"
        )
        return send_message_with_quick_replies(psid, welcome_text)

    if payload == "Q_ADVANCE_ORDER":
        if not is_store_open():
            open_time, close_time = get_store_hours()
            call_send_api(psid, {"text": f"Sorry, we're closed now. We'll open tomorrow at {open_time.strftime('%I:%M %p')}."})
            return

        call_send_api(psid, {"text": "Please type your order now:"})
        user_states[psid] = "awaiting_order"
        return

    # Handle order submission - SAVE TO SUPABASE
    if user_states.get(psid) == "awaiting_order" and text_message:
        success, order_number = save_order_to_supabase(psid, text_message)
        
        if success:
            return send_message_with_quick_replies(
                psid, 
                f"Your advance order has been received!\n\n"
                f"Order Number: {order_number}\n\n"
                f"We'll prepare your order and contact you when it's ready. Thank you!"
            )
        else:
            call_send_api(psid, {"text": "Sorry, we couldn't process your order. Please try again later."})

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
        return

    # Default fallback for unrecognized text
    if text_message:
        # Auto-mute if message mentions an agent name
        lower_text = text_message.lower()
        agent_names = get_config_value('menu_suppression.agent_names', []) or []
        if any(name in lower_text for name in agent_names):
            # Mute menu for this user for 24 hours
            user_menu_muted_until[psid] = datetime.now().replace(microsecond=0) + timedelta(hours=24)
            logger.info(f"Menu muted for PSID {psid} due to agent mention")
            return

        # Only show quick replies if it hasn't been shown recently
        if should_show_menu(psid):
            return send_message_with_quick_replies(psid, "I can help you with the following options:")

# ---------------------
# Notification: Order Ready
# ---------------------
@app.route("/webhook/order-ready", methods=["POST"])
def notify_order_ready():
    """Send notification to customer when order is ready for pickup"""
    try:
        data = request.get_json()
        psid = data.get("psid")
        order_number = data.get("order_number")
        customer_name = data.get("customer_name", "Customer")
        
        if not psid or not order_number:
            logger.error("Missing PSID or order_number in notification request")
            return Response(json.dumps({"error": "Missing required fields"}), status=400, mimetype="application/json")
        
        logger.info(f"Sending order ready notification to PSID {psid} for order {order_number}")
        
        # Send notification message to customer
        message_text = (
            f"Good news! Your order #{order_number} is ready for pickup!\n\n"
            f"Please come to {get_config_value('contact.restaurant_name', 'Pedro\\'s Restaurant')} to pick up your order.\n\n"
            f"See you soon! Thank you for ordering with us!"
        )
        
        result = call_send_api(psid, {"text": message_text})
        
        if result:
            logger.info(f"Order ready notification sent successfully to {customer_name}")
            return Response(json.dumps({"success": True, "message": "Customer notified"}), status=200, mimetype="application/json")
        else:
            logger.error("Failed to send notification via Facebook API")
            return Response(json.dumps({"error": "Failed to send message"}), status=500, mimetype="application/json")
            
    except Exception as e:
        logger.error(f"Error in order ready notification: {e}")
        return Response(json.dumps({"error": str(e)}), status=500, mimetype="application/json")

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
            logger.info("Verification successful")
            return Response(challenge, status=200, mimetype="text/plain")
        return Response("Forbidden", status=403)

    # POST
    data = request.get_json()
    logger.info(f"Incoming webhook event: {json.dumps(data, indent=2)}")

    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                psid = event.get("sender", {}).get("id")
                if not psid:
                    logger.warning("No PSID found in event")
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
    logger.info(f"Starting Flask app on port {PORT}...")
    try:
        app.run(host="0.0.0.0", port=PORT, debug=True)
    except Exception as e:
        logger.error(f"Flask app failed to start: {e}")

