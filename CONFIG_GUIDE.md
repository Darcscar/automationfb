# Configuration Guide

## Quick Store Settings - No Code Deployment Needed! 🎉

You can now change store hours, contact info, and URLs **without deploying new code**. Just edit the `config.json` file and the changes will take effect automatically within 1-2 minutes.

## How to Edit `config.json`

### 1. Change Store Hours

To change opening/closing times, edit the `store_hours` section:

```json
{
  "store_hours": {
    "open_time": "10:00",
    "close_time": "22:00",
    "timezone": "Asia/Manila"
  }
}
```

**Example:** To open at 9 AM and close at 10 PM:
```json
"open_time": "09:00",
"close_time": "22:00"
```

### 2. Mark Special Closure Days

When your store will be closed on specific dates (holidays, events, etc.), add dates to the `closed_dates` array:

```json
{
  "special_closures": {
    "note": "Add dates here when store will be closed (format: YYYY-MM-DD)",
    "closed_dates": ["2025-10-17", "2025-12-25", "2026-01-01"]
  }
}
```

**Example:** Closed tomorrow (Oct 17, 2025) and Christmas:
```json
"closed_dates": ["2025-10-17", "2025-12-25"]
```

Customers will see: "🚫 We are closed today. Sorry for the inconvenience!"

### 3. Update Contact Info

```json
{
  "contact": {
    "phone_number": "09171505518 / (042)4215968"
  }
}
```

### 4. Update URLs

```json
{
  "urls": {
    "foodpanda": "https://www.foodpanda.ph/restaurant/locg/pedros-old-manila-rd",
    "menu": "https://i.imgur.com/c2ir2Qy.jpeg",
    "google_map": "https://maps.app.goo.gl/GQUDgxLqgW6no26X8"
  }
}
```

## How to Apply Changes

### Option 1: Edit on Your Server (Recommended)
1. SSH into your server or access your deployment platform's file editor
2. Navigate to the `automationfb` folder
3. Edit `config.json`
4. Save the file
5. **That's it!** Changes apply automatically within 1-2 minutes

### Option 2: Edit Locally and Push
1. Edit `config.json` in your local project
2. Commit and push to GitHub:
   ```bash
   git add config.json
   git commit -m "Update store hours for tomorrow"
   git push
   ```
3. Your deployment platform will redeploy automatically

## Quick Replies Fix 🎯

The bot no longer spams "Please choose an option" after every response! 

**What changed:**
- Quick replies now appear when customers first start chatting
- After clicking a menu option, customers won't see the menu again for 2 minutes
- Quick replies are **persistent** in Messenger - customers can still tap them anytime
- Cleaner, less annoying conversation flow

**When quick replies appear:**
- ✅ When customer sends "Get Started"
- ✅ After completing an advance order
- ✅ When customer sends unrecognized text (but only if it's been >2 minutes since last shown)
- ❌ NOT after viewing menu, foodpanda, location, contact, or store hours

## Example Scenarios

### Scenario 1: Store Closed Tomorrow
Edit `config.json`:
```json
"special_closures": {
  "closed_dates": ["2025-10-17"]
}
```
Save. Done! No code deployment needed.

### Scenario 2: Change Store Hours for the Weekend
Friday afternoon:
```json
"open_time": "10:00",
"close_time": "23:00"
```
Monday morning:
```json
"open_time": "10:00",
"close_time": "22:00"
```

### Scenario 3: Update Menu Image
Upload new menu image to Imgur, copy the link:
```json
"urls": {
  "menu": "https://i.imgur.com/NEW_IMAGE_LINK.jpeg"
}
```

## Auto-Reload Feature

The bot automatically checks if `config.json` has been modified and reloads it. This means:
- **No need to restart the server**
- **No need to redeploy code**
- Changes take effect within 1-2 minutes (on the next customer interaction)

## Backup

Before making changes, consider keeping a backup of your current `config.json`:
```bash
cp config.json config.backup.json
```

## Need Help?

If you make a mistake in the JSON format, the bot will use default values and log an error. Just fix the JSON syntax and save again.

---

**Note:** Always ensure your JSON is properly formatted. Use a JSON validator if needed: https://jsonlint.com/

