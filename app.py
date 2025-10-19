"""
FINAL WORKING VERSION - Facebook Bot for Pedro's Restaurant
FIXED VERSION - Now includes complete_menu_name for proper sales reporting
"""

import os
import json
import logging
from flask import Flask, request, Response
try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False
    print("Warning: flask-cors not available, CORS disabled")
import requests
from datetime import datetime, time, date, timedelta
from zoneinfo import ZoneInfo

app = Flask(__name__)
if CORS_AVAILABLE:
    CORS(app)  # Enable CORS for all routes

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
MENU_CONFIG_FILE = "menu_config.json"
PRICING_CONFIG_FILE = "pricing_config.json"
config = {}
menu_config = {}
pricing_config = {}
config_last_modified = None
menu_config_last_modified = None
pricing_config_last_modified = None

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
                "store_hours": {"open_time": "10:00", "close_time": "21:00", "timezone": "Asia/Manila"},
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

def load_menu_config():
    global menu_config, menu_config_last_modified
    try:
        if os.path.exists(MENU_CONFIG_FILE):
            current_modified = os.path.getmtime(MENU_CONFIG_FILE)
            if menu_config_last_modified != current_modified:
                with open(MENU_CONFIG_FILE, 'r') as f:
                    menu_config = json.load(f)
                menu_config_last_modified = current_modified
                logger.info(f"Menu configuration loaded from {MENU_CONFIG_FILE}")
        else:
            logger.warning(f"{MENU_CONFIG_FILE} not found, using empty menu")
            menu_config = {"menu_items": {}, "quantities": [], "order_keywords": []}
    except Exception as e:
        logger.error(f"Error loading menu config: {e}")
        menu_config = {"menu_items": {}, "quantities": [], "order_keywords": []}

def load_pricing_config():
    global pricing_config, pricing_config_last_modified
    try:
        if os.path.exists(PRICING_CONFIG_FILE):
            current_modified = os.path.getmtime(PRICING_CONFIG_FILE)
            if pricing_config_last_modified != current_modified:
                with open(PRICING_CONFIG_FILE, 'r') as f:
                    pricing_config = json.load(f)
                pricing_config_last_modified = current_modified
                logger.info(f"Pricing configuration loaded from {PRICING_CONFIG_FILE}")
        else:
            logger.warning(f"{PRICING_CONFIG_FILE} not found, using default pricing")
            pricing_config = {"pricing": {}}
    except Exception as e:
        logger.error(f"Error loading pricing config: {e}")
        pricing_config = {"pricing": {}}

load_config()
load_menu_config()
load_pricing_config()

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

def get_complete_menu_name(order_text):
    """Get the complete menu name for the order"""
    load_menu_config()
    
    if not menu_config or not menu_config.get("menu_items"):
        return order_text  # Fallback to original text
    
    text_lower = order_text.lower().strip()
    all_menu_items = []
    
    # Get all menu items from all categories
    for category, items in menu_config.get("menu_items", {}).items():
        all_menu_items.extend(items)
    
    # Find the best match
    best_match = None
    best_score = 0
    
    for item in all_menu_items:
        item_lower = item.lower()
        
        # Direct match (highest priority)
        if item_lower in text_lower:
            return item
            
        # Flexible matching
        item_clean = item_lower.replace(' w/', ' ').replace(' with ', ' ').replace(' & ', ' and ')
        text_clean = text_lower.replace(' w/', ' ').replace(' with ', ' ').replace(' & ', ' and ')
        
        if item_clean in text_clean:
            return item
            
        # Word-based matching
        item_words = [word for word in item_clean.split() if len(word) > 2]
        text_words = [word for word in text_clean.split() if len(word) > 2]
        matching_words = [word for word in item_words if word in text_words]
        
        if len(matching_words) >= 2 and len(matching_words) > best_score:
            best_match = item
            best_score = len(matching_words)
    
    return best_match if best_match else order_text

def calculate_order_total(order_text):
    """Calculate estimated total for Facebook orders based on menu items"""
    load_pricing_config()
    
    if not pricing_config or not pricing_config.get("pricing"):
        logger.warning("No pricing configuration found, returning 0")
        return 0
    
    text_lower = order_text.lower().strip()
    total = 0
    found_items = []
    
    logger.info(f"Calculating total for order: '{order_text}'")
    
    # Get all pricing from the external file (excluding free requests)
    all_pricing = {}
    for category, items in pricing_config.get("pricing", {}).items():
        if category != "free_requests":  # Skip free requests from pricing
            all_pricing.update(items)
    
    logger.info(f"Loaded {len(all_pricing)} pricing items from config")
    
    # Count quantities and calculate total
    for item, price in all_pricing.items():
        item_lower = item.lower()
        if item_lower in text_lower:
            # Try to extract quantity
            quantity = 1
            for qty_word in ["1", "2", "3", "4", "5", "one", "two", "three", "four", "five"]:
                if qty_word in text_lower:
                    if qty_word.isdigit():
                        quantity = int(qty_word)
                    elif qty_word == "two":
                        quantity = 2
                    elif qty_word == "three":
                        quantity = 3
                    elif qty_word == "four":
                        quantity = 4
                    elif qty_word == "five":
                        quantity = 5
                    break
            
            item_total = quantity * price
            total += item_total
            found_items.append(f"{quantity}×{item}@{price}")
            logger.info(f"Found item '{item}' with quantity {quantity} at ₱{price} each = ₱{item_total}")
    
    if found_items:
        logger.info(f"Order breakdown: {', '.join(found_items)}")
        logger.info(f"Total calculated: ₱{total}")
    else:
        logger.warning(f"No matching items found for order: '{order_text}'")
        logger.warning("Available items in pricing config:")
        for item in all_pricing.keys():
            logger.warning(f"  - {item}")
    
    return total

def validate_order_text(text):
    """Check if the text contains valid menu items"""
    load_menu_config()
    
    if not menu_config or not menu_config.get("menu_items"):
        # If no menu config, allow all orders (fallback)
        return True, "Order accepted (no menu validation)"
    
    text_lower = text.lower().strip()
    
    # Get all menu items from all categories (excluding free requests)
    all_menu_items = []
    for category, items in menu_config.get("menu_items", {}).items():
        if category not in ['free_requests']:  # Exclude free requests from main validation
            all_menu_items.extend(items)
    
    # Also include chargeable extras
    chargeable_extras = menu_config.get("menu_items", {}).get("chargeable_extras", [])
    all_menu_items.extend(chargeable_extras)
    
    # Check if any menu item is mentioned in the text
    found_items = []
    match_scores = {}  # Track match quality for prioritization
    
    for item in all_menu_items:
        item_lower = item.lower()
        text_lower = text.lower().strip()
        
        # Direct match (highest priority)
        if item_lower in text_lower:
            found_items.append(item)
            match_scores[item] = 100  # Perfect match
            continue
            
        # Flexible matching for common variations
        # Remove common separators and check for partial matches
        item_clean = item_lower.replace(' w/', ' ').replace(' with ', ' ').replace(' & ', ' and ')
        text_clean = text_lower.replace(' w/', ' ').replace(' with ', ' ').replace(' & ', ' and ')
        
        if item_clean in text_clean:
            found_items.append(item)
            match_scores[item] = 90  # Very good match
            continue
            
        # Check if all key words from item are in text
        item_words = [word for word in item_clean.split() if len(word) > 2]  # Skip short words
        if len(item_words) >= 2 and all(word in text_clean for word in item_words):
            found_items.append(item)
            match_scores[item] = 80  # Good match
            continue
            
        # Check for partial matches (at least 2 significant words match)
        text_words = [word for word in text_clean.split() if len(word) > 2]
        matching_words = [word for word in item_words if word in text_words]
        if len(matching_words) >= 2:
            found_items.append(item)
            match_scores[item] = 70  # Partial match
    
    if found_items:
        # Sort by match score (highest first) to prioritize better matches
        sorted_items = sorted(found_items, key=lambda x: match_scores.get(x, 0), reverse=True)
        
        # For ambiguous cases (like "lechon kawali"), prefer more specific matches
        best_matches = []
        for item in sorted_items:
            # If we have multiple matches, prefer the most specific one
            if len(best_matches) == 0 or match_scores[item] >= match_scores[best_matches[0]]:
                best_matches.append(item)
            elif match_scores[item] < match_scores[best_matches[0]] - 10:  # Significant difference
                break
        
        return True, f"Valid order containing: {', '.join(best_matches)}"
    
    # Check if it looks like a question or non-order
    question_words = ['what', 'how', 'when', 'where', 'why', 'can', 'could', 'would', 'should', 'is', 'are', 'do', 'does']
    if any(word in text_lower for word in question_words) and len(text) < 50:
        return False, "This appears to be a question, not an order"
    
    # If no menu items found and doesn't look like a question, ask for clarification
    return False, "I don't recognize any menu items in your message. Please check our menu and try again."

# User states
user_states = {}
last_greeted = {}
menu_shown_time = {}
user_menu_muted_until = {}

# Variation detection and prompting
def detect_item_variations(order_text):
    """Detect if an item needs variation selection"""
    load_menu_config()
    
    if not menu_config or not menu_config.get("menu_items"):
        return None, None
    
    text_lower = order_text.lower().strip()
    
    # Define base items and their variations based on menu categories
    base_items = {}
    
    # Stir fry items (solo/double)
    stir_fry_items = menu_config.get("menu_items", {}).get("stir_fry", [])
    for item in stir_fry_items:
        # Extract base item name (remove common variations)
        base_name = item
        for variation in [" solo", " double", " large", " medium"]:
            base_name = base_name.replace(variation, "")
        base_items[base_name] = ["solo", "double"]
    
    # Short order items (solo/medium/large)
    short_order_items = menu_config.get("menu_items", {}).get("short_order", [])
    for item in short_order_items:
        # Extract base item name
        base_name = item
        for variation in [" solo", " medium", " large"]:
            base_name = base_name.replace(variation, "")
        base_items[base_name] = ["solo", "medium", "large"]
    
    # Yangchow special items
    yangchow_items = menu_config.get("menu_items", {}).get("yangchow", [])
    for item in yangchow_items:
        if "yangchow" in item.lower() and not any(specific in item.lower() for specific in ["pork tonkatsu", "sweet", "chicken fillet", "general tso", "lechon"]):
            base_items["yangchow"] = ["w/ pork tonkatsu", "w/ sweet & sour pork", "w/ chicken fillet", "w/ general tso chicken", "w/ lechon kawali"]
            break
    
    # Check for base items in the order text
    for base_item, variations in base_items.items():
        if base_item in text_lower:
            # Check if variation is already specified
            for variation in variations:
                if variation in text_lower:
                    return None, None  # Variation already specified
            
            # Return base item and available variations
            return base_item, variations
    
    return None, None

def ask_for_variation(psid, base_item, variations):
    """Ask user to select a variation"""
    if not variations:
        return False
    
    # Create quick reply buttons for variations
    quick_replies = []
    for variation in variations:
        quick_replies.append({
            "content_type": "text",
            "title": variation.title(),
            "payload": f"VARIATION_{base_item}_{variation}"
        })
    
    # Add cancel option
    quick_replies.append({
        "content_type": "text",
        "title": "Cancel",
        "payload": "VARIATION_CANCEL"
    })
    
    # Determine size type for better messaging
    if variations == ["solo", "double"]:
        size_type = "size"
        message_text = f"I found '{base_item}' in your order. Please choose a size:\n\n"
    elif variations == ["solo", "medium", "large"]:
        size_type = "size"
        message_text = f"I found '{base_item}' in your order. Please choose a size:\n\n"
    elif "w/" in variations[0]:
        size_type = "variation"
        message_text = f"I found '{base_item}' in your order. Please choose a variation:\n\n"
    else:
        size_type = "option"
        message_text = f"I found '{base_item}' in your order. Please choose an option:\n\n"
    
    for i, variation in enumerate(variations, 1):
        message_text += f"{i}. {variation.title()}\n"
    
    call_send_api(psid, {
        "text": message_text,
        "quick_replies": quick_replies
    })
    
    return True

def process_variation_selection(psid, payload, original_order_text):
    """Process user's variation selection"""
    if payload == "VARIATION_CANCEL":
        user_states.pop(psid, None)
        user_states.pop(f"{psid}_original_order", None)
        return send_message_with_quick_replies(psid, "Order cancelled. How can I help you today?")
    
    if payload.startswith("VARIATION_"):
        # Extract base item and variation
        parts = payload.split("_", 2)
        if len(parts) >= 3:
            base_item = parts[1]
            variation = parts[2]
            
            # Update the order text with the selected variation
            updated_order_text = original_order_text.replace(base_item, f"{base_item} {variation}")
            
            # Clear the variation state
            user_states.pop(psid, None)
            user_states.pop(f"{psid}_original_order", None)
            
            # Process the updated order
            return process_order_with_variation(psid, updated_order_text)
    
    return False

def process_order_with_variation(psid, order_text):
    """Process order after variation selection"""
    # Validate the updated order
    is_valid, validation_message = validate_order_text(order_text)
    
    if not is_valid:
        call_send_api(psid, {"text": f"{validation_message}\n\nPlease try again or type 'cancel' to stop."})
        return
    
    # Process the order
    success, order_number = save_order_to_supabase(psid, order_text)
    
    if success:
        estimated_total = calculate_order_total(order_text)
        
        # Add pickup time information based on store status
        if is_store_open():
            pickup_info = "We'll prepare your order and contact you when it's ready."
        else:
            now = get_manila_time().time()
            open_time, close_time = get_store_hours()
            if now < open_time:
                pickup_info = f"We'll prepare your order when we open at {open_time.strftime('%I:%M %p')} and contact you when it's ready."
            else:
                pickup_info = f"We'll prepare your order when we open tomorrow at {open_time.strftime('%I:%M %p')} and contact you when it's ready."
        
        total_info = f"Estimated Total: ₱{estimated_total}\n\n" if estimated_total > 0 else ""
        
        send_message_with_quick_replies(psid, f"Your order has been received!\n\nOrder Number: {order_number}\n\n{total_info}{pickup_info} Thank you!")
    else:
        send_message_with_quick_replies(psid, "Sorry, we couldn't process your order. Please try again later.")

# Save order to Supabase
def save_order_to_supabase(psid, order_text):
    try:
        now = datetime.now(ZoneInfo('Asia/Manila'))
        # Include time to make order number unique (even if same customer orders multiple times per day)
        order_number = f"FB-{now.strftime('%Y%m%d%H%M%S')}-{psid[-6:]}"
        
        # Get complete menu name and calculate estimated total
        complete_menu_name = get_complete_menu_name(order_text)
        estimated_total = calculate_order_total(order_text)
        
        url = f"{SUPABASE_URL}/rest/v1/online_orders"
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        # FIXED: Now includes complete_menu_name for proper sales reporting
        payload = {
            "order_number": order_number,
            "facebook_psid": psid,
            "order_text": order_text,  # Original customer text
            "complete_menu_name": complete_menu_name,  # Complete menu name for POS
            "order_type": "pickup",
            "status": "pending",
            "order_date": now.isoformat(),
            "estimated_total": estimated_total,
            "customer_name": f"Facebook Customer {psid[-4:]}"
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        
        logger.info(f"Order saved to Supabase: {order_number} (Complete menu: {complete_menu_name}, Estimated total: ₱{estimated_total})")
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
    # Send confirmation without quick replies to close buttons
    call_send_api(psid, {"text": "Here's our menu! 📋"})

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
        # Always allow advance orders, but show different messages based on store status
        if not is_store_open():
            now = get_manila_time().time()
            open_time, close_time = get_store_hours()
            if now < open_time:
                call_send_api(psid, {"text": f"Great! You can place an advance order now. We'll open at {open_time.strftime('%I:%M %p')} and prepare your order.\n\nPlease type your order (or type 'cancel' to stop):"})
            else:
                call_send_api(psid, {"text": f"Perfect! You can place an advance order now. We'll prepare it when we open tomorrow at {open_time.strftime('%I:%M %p')}.\n\nPlease type your order (or type 'cancel' to stop):"})
        else:
            call_send_api(psid, {"text": "Please type your advance order now (or type 'cancel' to stop):"})
        
        user_states[psid] = "awaiting_order"
        return

    if user_states.get(psid) == "awaiting_order" and text_message:
        # Check for cancellation commands first
        lower_text = text_message.lower().strip()
        cancel_commands = ['cancel', 'stop', 'quit', 'exit', 'no', 'nevermind', 'never mind']
        
        if any(cmd in lower_text for cmd in cancel_commands):
            user_states.pop(psid, None)
            return send_message_with_quick_replies(psid, "Order cancelled. How can I help you today?")
        
        # Check if this is a variation selection
        if user_states.get(psid) == "awaiting_variation":
            return process_variation_selection(psid, text_message, user_states.get(f"{psid}_original_order", ""))
        
        # Validate the order text
        is_valid, validation_message = validate_order_text(text_message)
        
        if not is_valid:
            # Send validation error and keep user in order mode
            call_send_api(psid, {"text": f"{validation_message}\n\nPlease type your order again (or 'cancel' to stop):"})
            return
        
        # Check if order needs variation selection
        base_item, variations = detect_item_variations(text_message)
        if base_item and variations:
            # Store original order text and ask for variation
            user_states[psid] = "awaiting_variation"
            user_states[f"{psid}_original_order"] = text_message
            return ask_for_variation(psid, base_item, variations)
        
        # If valid and no variation needed, process the order
        success, order_number = save_order_to_supabase(psid, text_message)
        
        # Always clear the user state after processing (success or failure)
        user_states.pop(psid, None)
        user_states.pop(f"{psid}_original_order", None)
        
        if success:
            # Calculate estimated total for display
            estimated_total = calculate_order_total(text_message)
            
            # Add pickup time information based on store status
            if is_store_open():
                pickup_info = "We'll prepare your order and contact you when it's ready."
            else:
                now = get_manila_time().time()
                open_time, close_time = get_store_hours()
                if now < open_time:
                    pickup_info = f"We'll prepare your order when we open at {open_time.strftime('%I:%M %p')} and contact you when it's ready."
                else:
                    pickup_info = f"We'll prepare your order when we open tomorrow at {open_time.strftime('%I:%M %p')} and contact you when it's ready."
            
            # Include estimated total in confirmation
            total_info = f"Estimated Total: ₱{estimated_total}\n\n" if estimated_total > 0 else ""
            
            return send_message_with_quick_replies(psid, f"Your advance order has been received!\n\nOrder Number: {order_number}\n\n{total_info}{pickup_info} Thank you!")
        else:
            return send_message_with_quick_replies(psid, "Sorry, we couldn't process your order. Please try again later.")

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
                        payload = msg["quick_reply"].get("payload")
                        # Handle variation selections
                        if payload and payload.startswith("VARIATION_"):
                            original_order = user_states.get(f"{psid}_original_order", "")
                            process_variation_selection(psid, payload, original_order)
                        else:
                            handle_payload(psid, payload=payload)
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
