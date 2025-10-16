# Staff Guide - Bot Control

## 🤖 Automatic Bot Pause Feature

When **any staff member** (Pedro, Danez, Ariane Marie, etc.) replies to a customer through Facebook Messenger, the bot will **automatically stop responding** to that conversation.

This prevents the bot from interfering when you're handling a customer personally!

## How It Works

### ✅ Automatic Detection
1. **Customer messages** → Bot responds automatically
2. **You reply to customer** → Bot detects your message and goes silent
3. **Customer replies again** → Bot stays silent (you're in control)
4. **Bot won't send any more messages** until you resume it

### 🔄 Manual Control (Optional)

If you need to manually control the bot, you can type these commands in the customer conversation:

#### Pause the Bot (Take Over Manually)
Type any of these in the conversation:
- `/pause`
- `/human`
- `/takeover`

The bot will immediately stop responding to that customer.

#### Resume the Bot (Hand Back to Automation)
When you're done and want the bot to take over again, type:
- `/resume`
- `/bot`

The bot will send a message and start responding again.

## 📋 Example Scenarios

### Scenario 1: Customer Has Special Request
```
Customer: "Hi, I want to order"
Bot: "How can I help you today?" [quick replies]

Customer: "I need a custom order for 50 people"
You (Pedro): "Hi! Let me help you with that custom order..."
[🤖 Bot automatically pauses]

Customer: "Can you do lechon for Saturday?"
You: "Yes, we can! Let me check availability..."
[🤖 Bot stays quiet]

You: "/resume"
[🤖 Bot sends: "Bot is now active again. How can I help you?"]
```

### Scenario 2: Customer Complaint
```
Customer: "My order was wrong!"
Bot: [Shows menu options]

You (Ariane): "I'm so sorry about that! Let me fix this for you right away..."
[🤖 Bot automatically pauses and stays quiet]

Customer: "Thank you!"
You: "You're welcome! Have a great day!"
```

### Scenario 3: You Want to Take Over Immediately
```
Customer: "Is the restaurant open?"
Bot: "We are OPEN today from 10:00 AM to 10:00 PM"

[You see the customer needs special attention]
You (Danez): "/takeover"
[🤖 Bot pauses]

You: "Hi! Yes we're open. Did you need something specific?"
Customer: "Yes, can I reserve a table for 10 people?"
You: "Of course! Let me help you with that..."
```

## 🎯 Key Points

✅ **Just reply normally** - Bot pauses automatically when you message customers
✅ **No special commands needed** - Automatic detection works in the background
✅ **Manual commands available** - Use `/pause` and `/resume` if needed
✅ **Per-conversation control** - Each customer chat is tracked separately
✅ **Bot remembers** - Once paused, bot stays quiet until resumed

## 🔍 How to Tell if Bot is Paused

Check your server logs for messages like:
- `👤 Human agent replied to PSID xxxxx, bot paused automatically`
- `👤 Human agent is handling PSID xxxxx, bot staying silent`
- `🤖 Bot resumed for PSID xxxxx`

## ⚠️ Important Notes

1. **Commands are case-insensitive**: `/PAUSE`, `/pause`, `/Pause` all work
2. **Commands work in the customer chat**: Type them in the conversation thread
3. **Bot stays paused**: Even if you close the chat, bot won't resume until you type `/resume`
4. **Each customer is separate**: Pausing for one customer doesn't affect others

## 💡 Tips

- **Let bot handle simple questions** (menu, hours, location)
- **Take over for complex requests** (custom orders, complaints, reservations)
- **Use `/resume` when done** so bot can handle follow-up questions
- **No need to pause manually** - just reply and bot will pause automatically!

---

**Questions?** Check the logs or test it with a friend's account to see how it works!

