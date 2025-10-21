"""
CATEGORY-BASED ORDERING SYSTEM - Facebook Bot for Pedro's Restaurant
NEW VERSION - Customers browse categories and select items instead of typing orders
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
CATEGORY_MENU_FILE = "category_menu.json"
config = {}
category_menu = {}
config_last_modified = None
category_menu_last_modified = None

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

def load_category_menu():
    global category_menu, category_menu_last_modified
    try:
        if os.path.exists(CATEGORY_MENU_FILE):
            current_modified = os.path.getmtime(CATEGORY_MENU_FILE)
            if category_menu_last_modified != current_modified:
                with open(CATEGORY_MENU_FILE, 'r') as f:
                    category_menu = json.load(f)
                category_menu_last_modified = current_modified
                logger.info(f"Category menu loaded from {CATEGORY_MENU_FILE}")
        else:
            logger.warning(f"{CATEGORY_MENU_FILE} not found, using empty menu")
            category_menu = {"menu_categories": {}}
    except Exception as e:
        logger.error(f"Error loading category menu: {e}")
        category_menu = {"menu_categories": {}}

load_config()
load_category_menu()

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

# User states and cart management
user_states = {}
user_carts = {}  # Store user's cart: {psid: [{"item": "name", "variation": "size", "price": 123, "quantity": 1}]}
last_greeted = {}
menu_shown_time = {}
user_menu_muted_until = {}

def get_user_cart(psid):
    """Get user's current cart"""
    return user_carts.get(psid, [])

def add_to_cart(psid, item_name, variation_name, price, quantity=1):
    """Add item to user's cart"""
    if psid not in user_carts:
        user_carts[psid] = []
    
    # Check if item already exists in cart
    for cart_item in user_carts[psid]:
        if cart_item["item"] == item_name and cart_item["variation"] == variation_name:
            cart_item["quantity"] += quantity
            return
    
    # Add new item to cart
    user_carts[psid].append({
        "item": item_name,
        "variation": variation_name,
        "price": price,
        "quantity": quantity
    })

def remove_from_cart(psid, item_name, variation_name):
    """Remove item from user's cart"""
    if psid not in user_carts:
        return
    
    user_carts[psid] = [item for item in user_carts[psid] 
                       if not (item["item"] == item_name and item["variation"] == variation_name)]

def clear_cart(psid):
    """Clear user's cart"""
    user_carts[psid] = []

def get_cart_total(psid):
    """Calculate total price of cart"""
    cart = get_user_cart(psid)
    return sum(item["price"] * item["quantity"] for item in cart)

def format_cart_summary(psid):
    """Format cart for display"""
    cart = get_user_cart(psid)
    if not cart:
        return "Your cart is empty"
    
    summary = "🛒 Your Order:\n\n"
    for i, item in enumerate(cart, 1):
        summary += f"{i}. {item['quantity']}× {item['item']} ({item['variation']}) - ₱{item['price'] * item['quantity']}\n"
    
    total = get_cart_total(psid)
    summary += f"\n💰 Total: ₱{total}"
    return summary

# Category and item selection functions
def show_categories(psid):
    """Show main menu categories"""
    load_category_menu()
    
    if not category_menu.get("menu_categories"):
        return call_send_api(psid, {"text": "Menu is currently unavailable. Please try again later."})
    
    # Create quick reply buttons for categories
    quick_replies = []
    categories = category_menu["menu_categories"]
    
    for category_id, category_data in categories.items():
        quick_replies.append({
            "content_type": "text",
            "title": category_data["name"],
            "payload": f"CATEGORY_{category_id}"
        })
    
    # Add cart and checkout options
    cart = get_user_cart(psid)
    if cart:
        quick_replies.append({
            "content_type": "text",
            "title": "🛒 View Cart",
            "payload": "VIEW_CART"
        })
        quick_replies.append({
            "content_type": "text",
            "title": "✅ Checkout",
            "payload": "CHECKOUT"
        })
    
    # Add main menu option
    quick_replies.append({
        "content_type": "text",
        "title": "🏠 Main Menu",
        "payload": "MAIN_MENU"
    })
    
    message_text = "🍽️ Choose a category to browse our menu:\n\n"
    for category_id, category_data in categories.items():
        message_text += f"• {category_data['name']} - {category_data['description']}\n"
    
    call_send_api(psid, {
        "text": message_text,
        "quick_replies": quick_replies
    })

def show_category_items(psid, category_id):
    """Show items in a specific category"""
    load_category_menu()
    
    categories = category_menu.get("menu_categories", {})
    if category_id not in categories:
        # Support nested stir_fry subcategories like 'stir_fry_chicken'
        if category_id.startswith("stir_fry_") and "stir_fry" in categories:
            subcats = categories["stir_fry"].get("subcategories", {})
            if category_id in subcats:
                subcat_data = subcats[category_id]
                items = subcat_data.get("items", [])
                if not items:
                    return call_send_api(psid, {"text": "No items found for this category. Please choose another."})
                quick_replies = []
                for item in items[:10]:
                    safe_name = item["name"].replace(" ", "_").replace("/", "_").replace("&", "and")
                    quick_replies.append({
                        "content_type": "text",
                        "title": item["name"],
                        "payload": f"ITEM|{category_id}|{safe_name}"
                    })
                quick_replies.append({"content_type": "text", "title": "🔙 Back to Categories", "payload": "CATEGORIES"})
                cart = get_user_cart(psid)
                if cart:
                    quick_replies.append({"content_type": "text", "title": "🛒 View Cart", "payload": "VIEW_CART"})
                message_text = f"🍽️ {subcat_data.get('name', category_id).title()}\n\n"
                for item in items:
                    message_text += f"• {item['name']}\n"
                    for variation in item["variations"]:
                        message_text += f"  - {variation['name']}: ₱{variation['price']}\n"
                    message_text += "\n"
                return call_send_api(psid, {"text": message_text, "quick_replies": quick_replies})
        
        # If selecting 'stir_fry' top-level, show its subcategories
        if category_id == "stir_fry" and "stir_fry" in categories:
            subcats = categories["stir_fry"].get("subcategories", {})
            if not subcats:
                return call_send_api(psid, {"text": "No items found for this category. Please choose another."})
            quick_replies = []
            message_text = "🍽️ Stir Fry\n\nChoose a subcategory:\n\n"
            for subcat_id, subcat in subcats.items():
                quick_replies.append({
                    "content_type": "text",
                    "title": subcat["name"],
                    "payload": f"CATEGORY_{subcat_id}"
                })
                message_text += f"• {subcat['name']} - {subcat.get('description', '')}\n"
            quick_replies.append({"content_type": "text", "title": "🔙 Back to Categories", "payload": "CATEGORIES"})
            cart = get_user_cart(psid)
            if cart:
                quick_replies.append({"content_type": "text", "title": "🛒 View Cart", "payload": "VIEW_CART"})
            return call_send_api(psid, {"text": message_text, "quick_replies": quick_replies})
        
        # Fallback legacy split keywords (kept for compatibility but not used with new structure)
        return call_send_api(psid, {"text": "Category not found. Please try again."})
    
    category_data = categories[category_id]
    
    # Handle old category structure that might not have 'items' key
    if "items" not in category_data:
        # If this is a container category with subcategories, prompt user to choose one
        if category_id == "stir_fry" and "subcategories" in category_data:
            quick_replies = []
            message_text = "🍽️ Stir Fry\n\nChoose a subcategory:\n\n"
            for subcat_id, subcat in category_data.get("subcategories", {}).items():
                quick_replies.append({
                    "content_type": "text",
                    "title": subcat["name"],
                    "payload": f"CATEGORY_{subcat_id}"
                })
                message_text += f"• {subcat['name']} - {subcat.get('description', '')}\n"
            quick_replies.append({"content_type": "text", "title": "🔙 Back to Categories", "payload": "CATEGORIES"})
            cart = get_user_cart(psid)
            if cart:
                quick_replies.append({"content_type": "text", "title": "🛒 View Cart", "payload": "VIEW_CART"})
            return call_send_api(psid, {"text": message_text, "quick_replies": quick_replies})
        return call_send_api(psid, {"text": "This category is no longer available. Please browse our updated menu categories."})
    
    items = category_data["items"]
    
    # Create quick reply buttons for items (max 13 buttons)
    quick_replies = []
    
    for item in items[:10]:  # Limit to 10 items to avoid button limit
        # Create a safe payload by replacing spaces and special characters
        safe_name = item["name"].replace(" ", "_").replace("/", "_").replace("&", "and")
        quick_replies.append({
            "content_type": "text",
            "title": item["name"],
            "payload": f"ITEM|{category_id}|{safe_name}"
        })
    
    # Add navigation buttons
    quick_replies.append({
        "content_type": "text",
        "title": "🔙 Back to Categories",
        "payload": "CATEGORIES"
    })
    
    cart = get_user_cart(psid)
    if cart:
        quick_replies.append({
            "content_type": "text",
            "title": "🛒 View Cart",
            "payload": "VIEW_CART"
        })
    
    message_text = f"🍽️ {category_data['name']}\n\n"
    for item in items:
        message_text += f"• {item['name']}\n"
        for variation in item["variations"]:
            message_text += f"  - {variation['name']}: ₱{variation['price']}\n"
        message_text += "\n"
    
    call_send_api(psid, {
        "text": message_text,
        "quick_replies": quick_replies
    })

def show_item_variations(psid, category_id, item_name):
    """Show variations for a specific item"""
    load_category_menu()
    
    categories = category_menu.get("menu_categories", {})
    if category_id not in categories:
        # Support nested stir_fry subcategories
        if category_id.startswith("stir_fry_") and "stir_fry" in categories:
            subcats = categories["stir_fry"].get("subcategories", {})
            subcat = subcats.get(category_id)
            if not subcat:
                return call_send_api(psid, {"text": "Category not found. Please try again."})
            items = subcat.get("items", [])
            selected_item = next((it for it in items if it["name"] == item_name), None)
            if not selected_item:
                return call_send_api(psid, {"text": "Item not found. Please try again."})
            variations = selected_item["variations"]
            quick_replies = []
            for variation in variations:
                safe_item_name = item_name.replace(" ", "_").replace("/", "_").replace("&", "and")
                safe_variation_name = variation['name'].replace(" ", "_").replace("/", "_").replace("&", "and")
                quick_replies.append({
                    "content_type": "text",
                    "title": f"{variation['name']} - ₱{variation['price']}",
                    "payload": f"ADD_ITEM|{category_id}|{safe_item_name}|{safe_variation_name}|{variation['price']}"
                })
            quick_replies.append({"content_type": "text", "title": "🔙 Back to Items", "payload": f"CATEGORY_{category_id}"})
            quick_replies.append({"content_type": "text", "title": "🏠 Main Menu", "payload": "MAIN_MENU"})
            message_text = f"🍽️ {item_name}\n\nChoose a variation:\n\n"
            for variation in variations:
                message_text += f"• {variation['name']}: ₱{variation['price']}\n"
            return call_send_api(psid, {"text": message_text, "quick_replies": quick_replies})
        return call_send_api(psid, {"text": "Category not found. Please try again."})
    
    category_data = categories[category_id]
    
    # Handle old category structure that might not have 'items' key
    if "items" not in category_data:
        return call_send_api(psid, {"text": "This category is no longer available. Please browse our updated menu categories."})
    
    items = category_data["items"]
    
    # Find the specific item
    selected_item = None
    for item in items:
        if item["name"] == item_name:
            selected_item = item
            break
            
    if not selected_item:
        return call_send_api(psid, {"text": "Item not found. Please try again."})
    
    variations = selected_item["variations"]
    
    # Create quick reply buttons for variations
    quick_replies = []
    
    for variation in variations:
        # Create safe names for payload
        safe_item_name = item_name.replace(" ", "_").replace("/", "_").replace("&", "and")
        safe_variation_name = variation['name'].replace(" ", "_").replace("/", "_").replace("&", "and")
        quick_replies.append({
            "content_type": "text",
            "title": f"{variation['name']} - ₱{variation['price']}",
            "payload": f"ADD_ITEM|{category_id}|{safe_item_name}|{safe_variation_name}|{variation['price']}"
        })
    
    # Add navigation buttons
    quick_replies.append({
        "content_type": "text",
        "title": "🔙 Back to Items",
        "payload": f"CATEGORY_{category_id}"
    })
    
    quick_replies.append({
        "content_type": "text",
        "title": "🏠 Main Menu",
        "payload": "MAIN_MENU"
    })
    
    message_text = f"🍽️ {item_name}\n\nChoose a variation:\n\n"
    for variation in variations:
        message_text += f"• {variation['name']}: ₱{variation['price']}\n"
    
    call_send_api(psid, {
        "text": message_text,
        "quick_replies": quick_replies
    })
    
def show_cart(psid):
    """Show user's cart"""
    cart = get_user_cart(psid)
    
    if not cart:
        quick_replies = [
            {"content_type": "text", "title": "🍽️ Browse Menu", "payload": "CATEGORIES"},
            {"content_type": "text", "title": "🏠 Main Menu", "payload": "MAIN_MENU"}
        ]
        call_send_api(psid, {
            "text": "Your cart is empty. Browse our menu to add items!",
            "quick_replies": quick_replies
        })
        return
    
    # Create quick reply buttons
    quick_replies = [
        {"content_type": "text", "title": "✅ Checkout", "payload": "CHECKOUT"},
        {"content_type": "text", "title": "🍽️ Add More Items", "payload": "CATEGORIES"},
        {"content_type": "text", "title": "🗑️ Clear Cart", "payload": "CLEAR_CART"},
        {"content_type": "text", "title": "🏠 Main Menu", "payload": "MAIN_MENU"}
    ]
    
    # Add remove item buttons (limit to first 5 items)
    for i, item in enumerate(cart[:5]):
        quick_replies.append({
            "content_type": "text",
            "title": f"❌ Remove {item['item']}",
            "payload": f"REMOVE_ITEM_{item['item']}_{item['variation']}"
        })
    
    call_send_api(psid, {
        "text": format_cart_summary(psid),
        "quick_replies": quick_replies
    })

def process_checkout(psid):
    """Process checkout and create order"""
    cart = get_user_cart(psid)
    
    if not cart:
        return call_send_api(psid, {"text": "Your cart is empty. Please add items before checkout."})
    
    # Create order text from cart
    order_items = []
    for item in cart:
        order_items.append(f"{item['quantity']}× {item['item']} ({item['variation']})")
    
    order_text = ", ".join(order_items)
    
    # Calculate total before clearing cart
    total = get_cart_total(psid)
    
    # Save order to Supabase
    success, order_number = save_order_to_supabase(psid, order_text, cart)
    
    if success:
        # Clear cart
        clear_cart(psid)
        user_states.pop(psid, None)
        
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
        
        send_message_with_quick_replies(psid, f"✅ Order Confirmed!\n\nOrder Number: {order_number}\n\nTotal: ₱{total}\n\n{pickup_info}\n\nThank you for ordering with us!")
    else:
        send_message_with_quick_replies(psid, "Sorry, we couldn't process your order. Please try again later.")

# Save order to Supabase
def save_order_to_supabase(psid, order_text, cart_items):
    try:
        now = datetime.now(ZoneInfo('Asia/Manila'))
        order_number = f"FB-{now.strftime('%Y%m%d%H%M%S')}-{psid[-6:]}"
        
        # Calculate total from cart
        total = sum(item["price"] * item["quantity"] for item in cart_items)
        
        # Create parsed items for sales reporting
        parsed_items = []
        for item in cart_items:
            parsed_items.append({
                "name": f"{item['item']} ({item['variation']})",
                "quantity": item["quantity"],
                "price": item["price"],
                "total": item["price"] * item["quantity"]
            })
        
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
            "complete_menu_name": order_text,  # Use order text as complete menu name
            "items": parsed_items,
            "order_type": "pickup",
            "status": "pending",
            "order_date": now.isoformat(),
            "estimated_total": total,
            "customer_name": f"Facebook Customer {psid[-4:]}"
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        
        logger.info(f"Order saved to Supabase: {order_number} (Total: ₱{total})")
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
        {"content_type": "text", "title": "🍽️ Order Now", "payload": "CATEGORIES"},
        {"content_type": "text", "title": "📋 View Menu", "payload": "Q_VIEW_MENU"},
        {"content_type": "text", "title": "🛒 My Cart", "payload": "VIEW_CART"},
        {"content_type": "text", "title": "📍 Location", "payload": "Q_LOCATION"},
        {"content_type": "text", "title": "📞 Contact Us", "payload": "Q_CONTACT"},
        {"content_type": "text", "title": "🕒 Store Hours", "payload": "Q_HOURS"},
    ]

def send_message_with_quick_replies(psid, text):
    msg = {"text": text, "quick_replies": get_quick_replies()}
    return call_send_api(psid, msg)

def send_menu(psid):
    menu_url = get_config_value('urls.menu', 'https://i.imgur.com/Y6F3gFh.jpeg')
    call_send_api(psid, {"attachment": {"type": "image", "payload": {"url": menu_url, "is_reusable": True}}})
    
    # Add return button after showing menu
    quick_replies = [
        {"content_type": "text", "title": "🍽️ Order Now", "payload": "CATEGORIES"},
        {"content_type": "text", "title": "🏠 Main Menu", "payload": "MAIN_MENU"}
    ]
    call_send_api(psid, {"text": "Here's our menu! 📋", "quick_replies": quick_replies})

def send_foodpanda(psid):
    foodpanda_url = get_config_value('urls.foodpanda', 'https://www.foodpanda.ph/restaurant/locg/pedros-brgy-ibabang-dupay')
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
    
    # Add return button after showing Foodpanda
    quick_replies = [
        {"content_type": "text", "title": "🍽️ Order Now", "payload": "CATEGORIES"},
        {"content_type": "text", "title": "🏠 Main Menu", "payload": "MAIN_MENU"}
    ]
    call_send_api(psid, {"text": "Or browse our menu categories to order directly! 🍽️", "quick_replies": quick_replies})

def send_location(psid):
    google_map_url = get_config_value('urls.google_map', 'https://maps.app.goo.gl/GQUDgxLqgW6no26X8')
    call_send_api(psid, {
        "attachment": {
            "type": "template", 
            "payload": {
                "template_type": "button", 
                "text": "Tap below to view our location:", 
                "buttons": [{"type": "web_url", "url": google_map_url, "title": "Open Location"}]
            }
        }
    })
    
    # Add return button after showing location
    quick_replies = [
        {"content_type": "text", "title": "🍽️ Order Now", "payload": "CATEGORIES"},
        {"content_type": "text", "title": "🏠 Main Menu", "payload": "MAIN_MENU"}
    ]
    call_send_api(psid, {"text": "Visit us soon! We'd love to serve you! 🍽️", "quick_replies": quick_replies})

def send_contact_info(psid):
    phone_number = get_config_value('contact.phone_number', '09171505518 / (042)4215968')
    
    # Add return button after showing contact info
    quick_replies = [
        {"content_type": "text", "title": "🍽️ Order Now", "payload": "CATEGORIES"},
        {"content_type": "text", "title": "🏠 Main Menu", "payload": "MAIN_MENU"}
    ]
    call_send_api(psid, {"text": f"Contact us: {phone_number}\n\nCall us for quick orders or browse our menu! 🍽️", "quick_replies": quick_replies})

# Handle messages
def handle_payload(psid, payload=None, text_message=None):
    send_daily_greeting(psid)

    if payload == "GET_STARTED":
        phone_number = get_config_value('contact.phone_number', '09171505518 / (042)4215968')
        welcome_text = f"Hi! Welcome to Pedro's Classic and Asian Cuisine! 🍽️\n\nBrowse our menu categories to place your order.\n\nFor quick orders, call us at {phone_number}.\n\nHow can I help you today?"
        return send_message_with_quick_replies(psid, welcome_text)

    # Handle category-based ordering
    if payload == "CATEGORIES":
        return show_categories(psid)
    
    if payload == "MAIN_MENU":
        user_states.pop(psid, None)
        return send_message_with_quick_replies(psid, "🏠 Main Menu\n\nHow can I help you today?")
    
    if payload == "VIEW_CART":
        return show_cart(psid)
    
    if payload == "CHECKOUT":
        return process_checkout(psid)
    
    if payload == "CLEAR_CART":
        clear_cart(psid)
        return send_message_with_quick_replies(psid, "🗑️ Cart cleared! Browse our menu to add items.")
    
    # Handle category selection
    if payload and payload.startswith("CATEGORY_"):
        category_id = payload.replace("CATEGORY_", "")
        # If 'stir_fry' selected, show its real subcategories from category_menu.json
        if category_id == "stir_fry":
            load_category_menu()
            subcats = (category_menu.get("menu_categories", {})
                                  .get("stir_fry", {})
                                  .get("subcategories", {}))
            if subcats:
                quick_replies = []
                message_text = "🍽️ Stir Fry\n\nChoose a subcategory:\n\n"
                for subcat_id, subcat in subcats.items():
                    quick_replies.append({
                        "content_type": "text",
                        "title": subcat.get("name", subcat_id),
                        "payload": f"CATEGORY_{subcat_id}"
                    })
                    message_text += f"• {subcat.get('name', subcat_id)} - {subcat.get('description', '')}\n"
                quick_replies.append({"content_type": "text", "title": "🏠 Main Menu", "payload": "MAIN_MENU"})
                return call_send_api(psid, {"text": message_text, "quick_replies": quick_replies})
        return show_category_items(psid, category_id)
    
    # Handle item selection
    if payload and payload.startswith("ITEM|"):
        # Remove "ITEM|" prefix and split by pipe to get category_id and safe_name
        remaining = payload[5:]  # Remove "ITEM|"
        parts = remaining.split("|", 1)  # Split on pipe
        if len(parts) >= 2:
            category_id = parts[0]
            safe_name = parts[1]
            
            # Convert safe name back to original name
            load_category_menu()
            categories = category_menu.get("menu_categories", {})
            if category_id in categories:
                items = categories[category_id]["items"]
                for item in items:
                    item_safe_name = item["name"].replace(" ", "_").replace("/", "_").replace("&", "and")
                    if item_safe_name == safe_name:
                        return show_item_variations(psid, category_id, item["name"])
            # Support stir_fry subcategories
            if category_id.startswith("stir_fry_") and "stir_fry" in categories:
                subcats = categories["stir_fry"].get("subcategories", {})
                subcat = subcats.get(category_id)
                if subcat:
                    items = subcat.get("items", [])
                    for item in items:
                        item_safe_name = item["name"].replace(" ", "_").replace("/", "_").replace("&", "and")
                        if item_safe_name == safe_name:
                            return show_item_variations(psid, category_id, item["name"])
            
            return call_send_api(psid, {"text": "Item not found. Please try again."})
    
    # Handle adding item to cart
    if payload and payload.startswith("ADD_ITEM|"):
        parts = payload.split("|")
        if len(parts) >= 5:
            category_id = parts[1]
            safe_item_name = parts[2]
            safe_variation_name = parts[3]
            price = int(parts[4])
            
            # Convert safe names back to original names
            load_category_menu()
            categories = category_menu.get("menu_categories", {})
            if category_id in categories:
                items = categories[category_id]["items"]
                for item in items:
                    item_safe_name = item["name"].replace(" ", "_").replace("/", "_").replace("&", "and")
                    if item_safe_name == safe_item_name:
                        # Find the variation
                        for variation in item["variations"]:
                            var_safe_name = variation['name'].replace(" ", "_").replace("/", "_").replace("&", "and")
                            if var_safe_name == safe_variation_name:
                                add_to_cart(psid, item["name"], variation['name'], price)
                                
                                # Show confirmation and cart
                                call_send_api(psid, {"text": f"✅ Added to cart: {item['name']} ({variation['name']}) - ₱{price}"})
                                return show_cart(psid)
            # Support stir_fry subcategories
            if category_id.startswith("stir_fry_") and "stir_fry" in categories:
                subcats = categories["stir_fry"].get("subcategories", {})
                subcat = subcats.get(category_id)
                if subcat:
                    items = subcat.get("items", [])
                    for item in items:
                        item_safe_name = item["name"].replace(" ", "_").replace("/", "_").replace("&", "and")
                        if item_safe_name == safe_item_name:
                            for variation in item["variations"]:
                                var_safe_name = variation['name'].replace(" ", "_").replace("/", "_").replace("&", "and")
                                if var_safe_name == safe_variation_name:
                                    add_to_cart(psid, item["name"], variation['name'], price)
                                    call_send_api(psid, {"text": f"✅ Added to cart: {item['name']} ({variation['name']}) - ₱{price}"})
                                    return show_cart(psid)
            
            return call_send_api(psid, {"text": "Item not found. Please try again."})
    
    # Handle removing item from cart
    if payload and payload.startswith("REMOVE_ITEM_"):
        parts = payload.split("_", 3)
        if len(parts) >= 4:
            item_name = parts[2]
            variation_name = parts[3]
            
            remove_from_cart(psid, item_name, variation_name)
            call_send_api(psid, {"text": f"❌ Removed from cart: {item_name} ({variation_name})"})
            return show_cart(psid)

    # Handle other quick replies
    if payload == "Q_VIEW_MENU":
        return send_menu(psid)
    if payload == "Q_FOODPANDA":
        return send_foodpanda(psid)
    if payload == "Q_LOCATION":
        return send_location(psid)
    if payload == "Q_CONTACT":
        return send_contact_info(psid)
    if payload == "Q_HOURS":
        # Add return button after showing hours
        quick_replies = [
            {"content_type": "text", "title": "🍽️ Order Now", "payload": "CATEGORIES"},
            {"content_type": "text", "title": "🏠 Main Menu", "payload": "MAIN_MENU"}
        ]
        call_send_api(psid, {"text": hours_message() + "\n\nBrowse our menu to place your order! 🍽️", "quick_replies": quick_replies})
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
