# Autonomous Trading Dashboard - User Guide

## Access

Open the dashboard in your browser:
```
http://localhost:8001/static/autonomous-dashboard.html
```

## Dashboard Overview

The Autonomous Trading Dashboard provides real-time monitoring and control of the autonomous crypto trading bot.

### Header
- **Status Indicator**: Green dot = Trading active, Red dot = Trading stopped
- **Current Mode**: Shows whether the bot is actively trading or in standby

## Tabs

### 1. 📊 Overview
Main dashboard with trading metrics and quick stats.

**Trading Status Card**
- Current status (Running/Stopped)
- Uptime duration
- Number of active positions
- Total trades executed

**Account Overview Card**
- Total equity
- Available cash
- Current positions value
- Daily profit/loss

**Performance Metrics Card**
- Win rate percentage
- Average trade duration
- Largest winning trade
- Largest losing trade

**Quick Stats Card**
- Entry threshold (signal strength required to enter)
- Maximum concurrent positions
- Stop loss percentage
- Take profit percentage

**Recent Activity**
- Latest trades and status changes

**Controls**
- **Start Trading**: Activate autonomous trading
- **Stop Trading**: Pause autonomous trading (no new trades, but positions held)

### 2. ⚡ Signals
Real-time signal analysis for all monitored symbols.

**Signal Table**
- Symbol
- Current signal type (BUY/SELL/NEUTRAL)
- Signal strength (0-100 scale)
  - Green bar: Strong signal (≥60)
  - Yellow bar: Neutral signal (40-59)
  - Red bar: Weak signal (<40)
- Recommendation

**Interpretation**
- Signal ≥ Entry Threshold: Bot may enter position
- Signal strengthens as multiple indicators align
- Higher volatility = higher threshold required for entry

### 3. 💼 Positions
Currently held positions with real-time P&L tracking.

**Position Table**
- Symbol: Trading pair
- Quantity: Amount held
- Entry Price: Purchase price
- Current Price: Live market price
- P&L: Profit/loss in dollars and percentage
- Actions:
  - **Close**: Exit position immediately at market price

**Interpretation**
- Green P&L: Profitable position
- Red P&L: Losing position
- % shows return on that position

### 4. 📈 Trade History
Complete history of executed trades.

**Trade Table**
- Symbol
- Side: BUY or SELL
- Price: Execution price
- Size: Quantity traded
- Time: Execution timestamp
- P&L: Profit/loss for that trade

**Sorting**
- Most recent trades listed first
- Full history available (default: last 20)

### 5. 🌍 Market Regime
Market condition analysis for adaptive trading.

**Regime Table**
- Symbol
- Regime Type:
  - **BULL** (green): Uptrend, favorable for long positions
  - **BEAR** (red): Downtrend, trade cautiously
  - **SIDEWAYS** (yellow): Ranging, grid trading preferred
  - **VOLATILE** (purple): High volatility, reduce position size
- Confidence: 0-100% likelihood of regime
- Volatility: Current annualized volatility percentage
- Trend: Trend strength (-1 to +1, negative=down, positive=up)

**How it Affects Trading**
- Bull: Entry threshold lowered, position size increased
- Bear: Entry threshold raised, position size decreased
- Volatile: Entry threshold raised, risk management tightened
- Sideways: Suitable for range-bound strategies

### 6. ⚙️ Configuration
Manage autonomous trading parameters.

**Trading Configuration**
- **Entry Threshold**: Signal strength required to enter (0-100)
  - Lower = more aggressive
  - Higher = more conservative
  - Adjusted by market regime
- **Max Positions**: Maximum concurrent positions
  - Spread risk across multiple trades
  - Default: 5
- **Position Size %**: Percentage of equity per trade
  - 10% = 10% of account per position
  - Adjusted down in volatile markets
- **Stop Loss %**: Maximum loss allowed per trade
  - 2% = sell if position drops 2%
  - Market regime may adjust this
- **Take Profit %**: Target profit per trade
  - 3% = sell if position rises 3%
  - Can be exceeded if signal remains strong

**Symbol Management**
- Comma-separated list of trading pairs
- Only these symbols will be traded
- Changes take effect immediately
- Format: BTCUSDT, ETHUSDT, BNBUSDT

**Saving Changes**
- Click **Save Configuration** to apply changes
- Changes persist across bot restarts
- Confirmation message displayed on success

## Trading Logic

### Entry Decision
1. Signal strength calculated for symbol
2. Signal compared to entry threshold (adjusted for market regime)
3. If signal ≥ threshold:
   - Calculate position size based on regime
   - Check max positions not exceeded
   - Place buy order
4. Entry logged and displayed in recent activity

### Exit Decision
**Stop Loss Exit**
- Triggered when position drops by configured %
- Automatic, no additional confirmation
- Protects against large losses

**Take Profit Exit**
- Triggered when position rises by configured %
- Locks in gains
- Can sell into strength or hold for more

**Manual Exit**
- Click "Close" in Positions tab
- Executes at market price immediately
- Useful for quick adjustments

## Key Metrics Explained

### Signal Strength (0-100)
- Composite score of multiple indicators
- Components:
  - Technical analysis (RSI, MACD, Bollinger)
  - Trend strength
  - Volatility conditions
  - Market regime
- Higher = more confident direction

### Win Rate
- Percentage of profitable trades
- Formula: Winning Trades / Total Trades × 100%
- Target: >50% (better if coupled with good risk/reward)

### Average Trade Duration
- Time positions stay open
- Shorter = faster capital cycling
- Longer = patience waiting for target

### P&L
- Profit/Loss in dollars
- Positive = bot is making money
- Includes trading costs (fees, slippage)

## Best Practices

### 1. Monitor Daily
- Check dashboard at least once per day
- Review overnight trades in history
- Verify positions are as expected

### 2. Adjust Settings Gradually
- Don't change multiple parameters at once
- Change one, run for a few days, observe results
- Roll back if performance degrades

### 3. Regime-Aware Configuration
- Bull market: Lower entry threshold (60-70), higher position size (15%)
- Bear market: Higher entry threshold (75-85), lower position size (5%)
- Volatile: High threshold (80+), smallest position size (3-5%)

### 4. Risk Management
- Never exceed 5 concurrent positions (unless testing)
- Set stop loss to max loss you can tolerate
- Take profits at reasonable targets

### 5. During Market Hours
- Watch for unusual regime changes
- Be ready to pause trading if markets turn volatile
- Close large losing positions quickly

## Troubleshooting

### Dashboard Shows "Loading..."
- Wait 5 seconds for API responses
- Check browser console for errors (F12)
- Verify server is running on port 8001

### Status Shows "Offline"
- Server may not be responding
- Check that uvicorn is running: `ps aux | grep uvicorn`
- Restart server if needed

### Positions Not Updating
- Refresh page (F5) to force update
- Check that paper trading is enabled
- Verify symbol data is available

### Can't Update Configuration
- Ensure "Save Configuration" button is visible
- Check that trader is initialized
- Review browser console for errors

### No Recent Trades
- Bot may not have generated signals yet
- Check entry threshold isn't too high
- Review signal strength for your symbols

## Performance Optimization

### Auto-refresh Rate
- Dashboard refreshes every 5 seconds
- Adjust if network is slow: Change `refreshInterval` in dashboard HTML
- Minimum recommended: 2 seconds
- Maximum: 30 seconds

### Symbol Monitoring Limit
- Dashboard shows first 10 symbols
- Edit HTML to show more (performance cost)
- Line: `for (const symbol of config.symbols.slice(0, 10))`

## API Endpoints Used

The dashboard calls these APIs:
- `/api/autonomous/status` - Trading status
- `/api/autonomous/config` - Current configuration
- `/api/autonomous/start` - Start trading
- `/api/autonomous/stop` - Stop trading
- `/api/autonomous/config/update` - Update settings
- `/api/autonomous/trades` - Trade history
- `/api/paper/account` - Account metrics
- `/api/regime/detect` - Market regime
- `/api/signals/calculate` - Signal strength

All endpoints return JSON and support CORS for browser access.

## Advanced Features

### Custom Thresholds by Regime
The bot automatically adjusts entry thresholds:
- Bull market: -10 to base threshold
- Bear market: +10 to base threshold
- Volatile: +15 to base threshold

### Position Sizing Multipliers
Position sizes are adjusted by regime:
- Bull: 1.5x multiplier
- Sideways: 1.0x multiplier
- Bear: 0.5x multiplier
- Volatile: 0.3x multiplier

### Profit Target Scaling
Take profit % may be adjusted based on:
- Current volatility
- Position risk
- Portfolio concentration

## Emergency Controls

### Pause Trading
- Click "Stop Trading" button
- Existing positions remain open
- No new trades will execute
- Can be resumed with "Start Trading"

### Close All Positions
- Use "Close" button for each position individually
- Or manually execute market orders
- Dashboard will update immediately

### Reset Configuration
- Stop trading first
- Update symbols to empty list (if needed)
- Set entry threshold to high value (95+)
- Restart trading once values adjusted

## Support & Debugging

### Enable Debug Logging
Add to browser console (F12):
```javascript
localStorage.setItem('DEBUG', 'true');
```

### Test API Endpoints
```bash
curl http://localhost:8001/api/autonomous/status
curl http://localhost:8001/api/autonomous/config
curl http://localhost:8001/api/paper/account
```

### Check Server Logs
```bash
journalctl -u investing-platform -f
# or
tail -f logs/app.log
```

---

**Last Updated**: 2026-06-24  
**Version**: Phase 333 (Production Ready)  
**Status**: ✅ Fully Operational
