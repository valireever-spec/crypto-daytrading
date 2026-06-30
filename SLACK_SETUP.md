# Slack Alert Setup Guide

## Quick Setup (5 minutes)

### Step 1: Create Slack Webhook

1. Go to https://api.slack.com/messaging/webhooks
2. Click "Create New App"
3. Select "From scratch"
4. App name: "Crypto Trading Alerts"
5. Workspace: Select your workspace
6. Click "Create App"
7. In the left menu, click "Incoming Webhooks"
8. Toggle "Activate Incoming Webhooks" to ON
9. Click "Add New Webhook to Workspace"
10. Select channel: #trading-alerts (or create one)
11. Click "Allow"
12. Copy the webhook URL (format: `https://hooks.slack.com/services/[TEAM_ID]/[BOT_ID]/[TOKEN]`)

### Step 2: Set Environment Variable

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/[YOUR_TEAM_ID]/[YOUR_BOT_ID]/[YOUR_TOKEN]"
```

### Step 3: Restart Trading System

```bash
systemctl restart crypto-trading
```

### Step 4: Test Alerts

To manually trigger a test alert, you can run:

```bash
python -c "
import asyncio
from backend.core.alerting import get_alert_manager

async def test():
    mgr = get_alert_manager()
    await mgr.alert_circuit_breaker_open('TEST: Manual alert test')
    print('✅ Test alert sent to Slack')

asyncio.run(test())
"
```

## Alert Types

The system sends alerts for:

| Event | Severity | Alert Channel |
|-------|----------|----------------|
| Circuit breaker opened | 🔴 DANGER | Slack + Logs |
| PRIMARY machine unhealthy | 🔴 DANGER | Slack + Logs |
| Daily loss limit exceeded | 🔴 DANGER | Slack + Logs |
| Stop loss triggered | 🟠 WARNING | Slack + Logs |
| Profit target hit | 🟢 INFO | Logs only (too chatty) |

## Verification

After setting up, check:

```bash
# Verify environment variable is set
echo $SLACK_WEBHOOK_URL

# Check logs for alert initialization
tail -f logs/system.log | grep -i slack
```

If you see "Slack alerts enabled" in the logs, you're good!

## Troubleshooting

**"Slack alerts disabled"?**
- Check that `SLACK_WEBHOOK_URL` is set: `echo $SLACK_WEBHOOK_URL`
- Verify it's a valid Slack webhook URL
- Restart the system: `systemctl restart crypto-trading`

**Alerts not appearing in Slack?**
- Check webhook URL is correct
- Verify app has permission to post to the channel
- Check Slack notification settings in channel

**Test alert not working?**
- Make sure the environment variable is exported (not just in shell)
- Check Python can import alerting: `python -c "from backend.core.alerting import get_alert_manager"`
- Restart and try again

## Disabling Slack Alerts

If you want to turn off Slack alerts:

```bash
unset SLACK_WEBHOOK_URL
systemctl restart crypto-trading
```

Logs will continue to capture all events.
