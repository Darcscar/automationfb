import os
import json
import logging
from flask import Flask, request, Response
import requests

app = Flask(__name__)

# ---------------------
# Logging
# ---------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------
# Tokens
# ---------------------
PAGE_ACCESS_TOKEN = "EAHJTYAULctYBPU2QsZCocyqjZBHakvyMR95h0ZCAZACW076ARf8QZAUAgwJ6crkVivna5teNDUlLEVWvxzGKlBlocpvr21iotTels4nZBS6loaMx0eZBCA79R36oXy1uVnIRSJgyhdPZBSSaNeewk59ne2bv9eBZCHpqLRnZBLMsF14ofaZAaSIyje2yXBSTTbOxoZBOVisF3T2zBQZDZD"
VERIFY_TOKEN = "123darcscar"
FB_GRAPH = "https://graph.facebook.com/v19.0"

# ---------------------
# Helper: Send message
# ---------------------
def send_message(psid, text):
    payload = {
        "recipient": {"id": psid},
        "message": {"text": text},
        "messaging_type": "RESPONSE"
    }
    url = f"{FB_GRAPH}/me/messages"
    r = requests.post(url, params={"access_token": PAGE_ACCESS_TOKEN}, json=payload)
    if r.status_code != 200:
        logger.error("Send API error %s: %s", r.status_code, r.text)
    else:
        logger.info("Message sent to PSID %s", psid)

# ---------------------
# Webhook verification
# ---------------------
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        logger.info(f"Webhook verification attempt: mode={mode}, token={token}")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("✅ Verification successful")
            return Response(challenge, status=200, mimetype="text/plain")
        return Response("Forbidden", status=403)

    if request.method == "POST":
        data = request.get_json()
        logger.info(f"Incoming webhook event: {json.dumps(data, indent=2)}")

        if data.get("object") == "page":
            for entry in data.get("entry", []):
                for event in entry.get("messaging", []):
                    psid = event.get("sender", {}).get("id")
                    if not psid:
                        continue
                    logger.info(f"New PSID: {psid}")

                    # Respond to messages
                    if "message" in event:
                        text = event["message"].get("text", "")
                        send_message(psid, f"Echo: {text}")

                    # Respond to postbacks (GET_STARTED)
                    elif "postback" in event:
                        payload = event["postback"].get("payload")
                        send_message(psid, f"Postback received: {payload}")

        return Response("EVENT_RECEIVED", status=200)

if __name__ == "__main__":
    PORT = int(os.getenv("PORT", 10000))
    logger.info(f"Starting Flask app on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=True)
