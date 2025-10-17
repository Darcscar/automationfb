# 📱 Facebook Messenger Bot - Supabase Integration

## 🔧 **Modified Code for Your Flask Bot**

Replace your `handle_payload` function with this version that saves to Supabase:

```python
import requests

# Add this at the top with your other config
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://tgawpkpcfrxobgrsysic.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "your-anon-key-here")

def save_order_to_supabase(psid, order_text):
    """Save Facebook order directly to Supabase"""
    try:
        # Generate order number
        order_number = f"FB-{datetime.now().strftime('%Y%m%d')}-{psid[-6:]}"
        
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
            "order_date": datetime.now(ZoneInfo('Asia/Manila')).isoformat()
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        
        logger.info(f"✅ Order saved to Supabase: {order_number}")
        return True, order_number
        
    except Exception as e:
        logger.error(f"❌ Supabase save error: {e}")
        return False, None

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
            return

        call_send_api(psid, {"text": "📝 Please type your order now:"})
        user_states[psid] = "awaiting_order"
        return

    # Handle order submission
    if user_states.get(psid) == "awaiting_order" and text_message:
        # Save to Supabase instead of n8n
        success, order_number = save_order_to_supabase(psid, text_message)
        
        if success:
            return send_message_with_quick_replies(
                psid, 
                f"✅ Your advance order has been received!\n\n"
                f"📝 Order Number: {order_number}\n\n"
                f"We'll prepare your order and contact you when it's ready. Thank you! 🙏"
            )
        else:
            call_send_api(psid, {"text": "❌ Sorry, we couldn't process your order. Please try again later."})

        user_states.pop(psid, None)
        return

    # Rest of your existing code...
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

    # Default fallback
    if text_message:
        lower_text = text_message.lower()
        agent_names = get_config_value('menu_suppression.agent_names', []) or []
        if any(name in lower_text for name in agent_names):
            user_menu_muted_until[psid] = datetime.now().replace(microsecond=0) + timedelta(hours=24)
            logger.info(f"🔇 Menu muted for PSID {psid} due to agent mention")
            return

        if should_show_menu(psid):
            return send_message_with_quick_replies(psid, "I can help you with the following options:")
```

---

## 🔑 **Environment Variables**

Add these to your Flask bot environment (Render/Heroku/etc):

```bash
SUPABASE_URL=https://tgawpkpcfrxobgrsysic.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here
```

**To get your Supabase Anon Key:**
1. Go to [Supabase Dashboard](https://app.supabase.com)
2. Select your project
3. Go to **Settings** → **API**
4. Copy **anon/public** key

---

## 📊 **How It Works:**

### **Customer Flow:**
1. Customer clicks **"📝 Advance Order"** on Facebook
2. Bot asks: "📝 Please type your order now:"
3. Customer types: "2 Adobo, 1 Sinigang, 3 Rice"
4. Bot saves to **Supabase** `online_orders` table
5. Bot replies: "✅ Order received! Order #FB-20250117-ABC123"
6. **POS automatically shows the order!** 📱

### **Staff Flow (in POS):**
1. New notification: "🔔 New Facebook Order!"
2. Staff sees order details
3. Staff clicks "Confirm" → Status changes to "confirmed"
4. Staff clicks "Preparing" → Status changes to "preparing"
5. Staff clicks "Ready" → Status changes to "ready"
6. (Optional) Bot notifies customer: "Your order is ready for pickup!"

---

## 🎯 **Next Steps:**

1. ✅ Run the SQL migration (`06_create_online_orders_table.sql`)
2. ✅ Update your Flask bot code (above)
3. ✅ Add Supabase env variables to your bot
4. ✅ I'll create the POS component to display orders
5. ✅ Test: Send "Advance Order" from Facebook

---

## 📱 **Optional: Send Reply When Order is Ready**

Add this function to your bot:

```python
def notify_customer_order_ready(psid, order_number):
    """Send notification when order is ready"""
    message = f"🎉 Great news! Your order #{order_number} is ready for pickup!\n\nSee you soon! 😊"
    call_send_api(psid, {"text": message})
```

Then your POS can call a webhook to trigger this when staff marks order as "ready".

---

## 🔔 **Testing:**

1. Message your Facebook Page
2. Click "📝 Advance Order"
3. Type: "1 Chicken Adobo, 2 Rice"
4. Check Supabase Table Editor → `online_orders` table
5. Should see the order!
6. Check your POS → Online Orders tab (I'll create this next)

---

Ready to proceed? Should I create the POS component to display these Facebook orders? 🚀

