def handle_payload(psid, payload=None, text_message=None):
    today = date.today()

    # Greet user once per day
    if psid not in last_greeted or last_greeted[psid] != today:
        call_send_api(psid, {"text": hours_message()})
        last_greeted[psid] = today

    # GET_STARTED greeting
    if payload == "GET_STARTED":
        welcome_text = (
            "Hi! Thanks for messaging Pedro’s Classic and Asian Cuisine 🥰🍗🍳🥩\n\n"
            "For quick orders, call us at 0917 150 5518 or (042)421 5968."
        )
        call_send_api(psid, {"text": welcome_text})
        return send_main_menu(psid)

    # Start Advance Order flow
    if payload == "Q_ADVANCE_ORDER":
        call_send_api(psid, {"text": "📝 Please type your order now:"})
        user_states[psid] = "awaiting_order"
        return

    # If waiting for advance order text
    if user_states.get(psid) == "awaiting_order" and text_message:
        try:
            # Replace with your public Render URL for the n8n webhook
            n8n_webhook_url = "https://n8n-kbew.onrender.com/webhook/advance-order"

            requests.post(
                n8n_webhook_url,
                json={"psid": psid, "order": text_message},
                timeout=10
            )
        except Exception as e:
            logger.error(f"n8n forwarding error: {e}")

        call_send_api(psid, {"text": "✅ Your advance order has been received. Thank you!"})
        user_states.pop(psid, None)
        return send_main_menu(psid)

    # Button actions
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
        return send_main_menu(psid)

    # Free-text → show menu (if not advance order)
    if text_message:
        return send_main_menu(psid)

    return send_main_menu(psid)

