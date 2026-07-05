# Telegram Bot Token Rotation Guide

**Purpose:** Securely rotate the Telegram bot token to prevent unauthorized access

**Current Risk:** Token visible in `.env` file and git history

**Timeline:** 5-10 minutes

---

## Step 1: Generate New Token from BotFather

1. **Open Telegram** on any device
2. **Search for:** `@BotFather` (official Telegram bot manager)
3. **Send command:** `/start`
4. **List your bots:** `/mybots`
5. **Select your bot:** Click on the bot name (should be your crypto-trading bot)
6. **Generate new token:** `/regeneratetoken`
7. **Confirm:** BotFather will show you the new token

**Example new token:**
```
6189234567:AAFG5X9pK3mL8nQ2rS4tU6vW7xY9zAbCdEfGhI
```

**Keep this token safe!** Don't share it anywhere.

---

## Step 2: Update .env File

Open `.env` and replace the old token:

**BEFORE:**
```bash
ALERT_TELEGRAM_BOT_TOKEN=8876131965:AAGL4rfF8kfyvF44AGjowuOI6PkMtjnWZbY
```

**AFTER:**
```bash
ALERT_TELEGRAM_BOT_TOKEN=6189234567:AAFG5X9pK3mL8nQ2rS4tU6vW7xY9zAbCdEfGhI
```

---

## Step 3: Test New Token

Run this command to verify the new token works:

```bash
# Test new Telegram token
python3 << 'EOF'
import os
import asyncio
from backend.core.alerting import get_alert_manager

async def test_token():
    alert_mgr = get_alert_manager()
    if alert_mgr.is_telegram_configured():
        result = await alert_mgr.test_telegram()
        print(f"✅ Telegram test: {result}")
    else:
        print("❌ Telegram not configured")

asyncio.run(test_token())
EOF
```

**Expected output:**
```
✅ Telegram test: {'success': True}
```

---

## Step 4: Restart Services

Deploy the new token to both machines:

```bash
# Reload environment on PRIMARY
systemctl restart crypto-trading

# Reload environment on BACKUP
ssh openhabian@192.168.3.25 "sudo systemctl restart crypto-backup"
```

---

## Step 5: Verify New Token in Production

Send a test message to verify the new token is working in the live system:

1. **Check logs** for successful Telegram connections:
   ```bash
   tail -20 logs/api.log | grep -i "telegram"
   ```

2. **Expected log output:**
   ```
   Telegram alerts enabled
   ✅ Telegram alert sent: 🧪 Test message
   ```

---

## Step 6: Commit the Change

Create a commit with the new token:

```bash
git add .env
git commit -m "security: Rotate Telegram bot token

Updated bot token for security (previous token exposed in git history).
Generated new token via BotFather /regeneratetoken.

Old token is now invalid and cannot be used.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
"

git push origin master
```

---

## Step 7: Revoke Old Token (Recommended)

Go back to BotFather and revoke the old token so it can't be used:

1. **Open Telegram**
2. **Message @BotFather:** `/mybots`
3. **Select your bot**
4. **Send:** `/revoke`
5. **Confirm:** "I understand that I'm revoking access to this token"

**Note:** BotFather doesn't have explicit revoke, but the old token becomes invalid once you generate a new one. You can also delete/recreate the bot if needed.

---

## Why This Is Important

| Issue | Before Rotation | After Rotation |
|-------|--|--|
| **Token in .env** | Visible | Still visible but invalid |
| **Token in git history** | Can be found by anyone | Old token now useless |
| **Risk if leaked** | Complete bot compromise | No risk (token is dead) |
| **Recovery time** | N/A | Immediate (new token active) |

**Key point:** Rotating the token doesn't remove old occurrences from git history, but it makes those old tokens completely useless, so git visibility becomes harmless.

---

## Verification Checklist

- [ ] New token generated from BotFather
- [ ] `.env` file updated with new token
- [ ] Test message sent successfully
- [ ] Services restarted on both machines
- [ ] Log confirms Telegram connection working
- [ ] Commit pushed to master
- [ ] Old token revoked (optional but recommended)

---

## Rollback (If Needed)

If the new token doesn't work:

1. **Revert to old token** in `.env`
2. **Restart services:** `systemctl restart crypto-trading`
3. **Check logs:** `tail -f logs/api.log | grep -i telegram`
4. **Investigate** why new token didn't work (wrong token, typo, etc.)

---

## What NOT to Do

❌ **Don't:** Share the new token anywhere  
❌ **Don't:** Commit the token to a public repository  
❌ **Don't:** Use the same token on multiple systems  
❌ **Don't:** Keep old token in backups (rotate immediately)

---

## Timeline

**Total time:** 5-10 minutes  
**Downtime:** ~30 seconds (service restart)  
**Risk:** Minimal (old token becomes useless, new token is secure)

