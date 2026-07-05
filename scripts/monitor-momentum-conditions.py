#!/usr/bin/env python3
"""
Monitor momentum strategy entry conditions.
Check RSI, Volume, and Signal Strength every 5 minutes.
Alert when conditions improve (RSI > 50, Volume > 1.2x).
"""

import asyncio
import ccxt.async_support as ccxt
from datetime import datetime
import json
from statistics import mean
import sys

async def check_conditions():
    """Check momentum strategy entry conditions for all symbols."""
    try:
        exchange = ccxt.binance()
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

        timestamp = datetime.utcnow().isoformat()
        results = {
            "timestamp": timestamp,
            "symbols": {}
        }

        for symbol in symbols:
            try:
                ohlcv = await exchange.fetch_ohlcv(symbol, '5m', limit=100)

                closes = [c[4] for c in ohlcv]
                volumes = [c[5] for c in ohlcv]

                current_price = closes[-1]
                current_volume = volumes[-1]

                # Calculate SMA3 and SMA10
                sma_3 = mean(closes[-3:])
                sma_10 = mean(closes[-10:])

                # Calculate RSI
                deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
                gains = [d for d in deltas if d > 0]
                losses = [-d for d in deltas if d < 0]

                avg_gain = mean(gains[-14:]) if gains else 0
                avg_loss = mean(losses[-14:]) if losses else 0

                if avg_loss == 0:
                    rsi = 100.0 if avg_gain > 0 else 50.0
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))

                # Volume analysis
                avg_volume = mean(volumes[-20:])
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

                # SMA gap
                sma_gap = ((sma_3 - sma_10) / sma_10) * 100

                # Signal strength
                signal_strength = 50 + (sma_gap * 15)
                signal_strength += (rsi - 50) * 1.5
                signal_strength += (volume_ratio - 1.0) * 20
                signal_strength = min(signal_strength, 100.0)

                # Check entry conditions
                entry_possible = (sma_3 > sma_10 and
                                 current_price > sma_10 and
                                 50 <= rsi < 65 and
                                 volume_ratio >= 1.2 and
                                 signal_strength >= 40)

                results["symbols"][symbol] = {
                    "price": round(current_price, 2),
                    "rsi": round(rsi, 1),
                    "rsi_ok": 50 <= rsi < 65,
                    "volume_ratio": round(volume_ratio, 2),
                    "volume_ok": volume_ratio >= 1.2,
                    "signal_strength": round(signal_strength, 1),
                    "entry_possible": entry_possible
                }

            except Exception as e:
                results["symbols"][symbol] = {"error": str(e)}

        await exchange.close()
        return results

    except Exception as e:
        return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

async def main():
    """Run continuous monitoring."""
    print(f"[{datetime.utcnow().isoformat()}] Starting momentum conditions monitor...")

    check_count = 0
    entry_found = False

    while True:
        try:
            check_count += 1
            results = await check_conditions()

            # Format output
            ts = results.get("timestamp", "?")
            print(f"\n[{ts}] Check #{check_count}", end="")

            if "error" in results:
                print(f" ❌ ERROR: {results['error']}")
                await asyncio.sleep(300)  # 5 minutes
                continue

            # Check each symbol
            any_entry_ready = False
            for symbol, data in results.get("symbols", {}).items():
                if "error" in data:
                    print(f"\n  {symbol}: ERROR")
                else:
                    rsi = data.get("rsi", 0)
                    vol = data.get("volume_ratio", 0)
                    sig = data.get("signal_strength", 0)
                    entry_ok = data.get("entry_possible", False)

                    status = "✅ READY" if entry_ok else "⏳ Waiting"
                    print(f"\n  {symbol}: RSI {rsi} Vol {vol}x Sig {sig} → {status}", end="")

                    if entry_ok and not entry_found:
                        print(f"\n\n🔔 ALERT: {symbol} READY FOR ENTRY!", end="")
                        print(f"\n   RSI {rsi} (need 50-65) ✅")
                        print(f"   Volume {vol}x (need 1.2x) ✅")
                        print(f"   Signal {sig} (need 40+) ✅")
                        print(f"\n   Momentum strategy should generate entry signal now!")
                        entry_found = True
                        any_entry_ready = True

            if check_count % 12 == 0:  # Every hour (12 x 5min)
                print(f"\n[{ts}] Monitoring ongoing... waiting for RSI > 50 and volume > 1.2x")

            # Wait 5 minutes before next check
            await asyncio.sleep(300)

        except KeyboardInterrupt:
            print("\n\nMonitor stopped by user")
            break
        except Exception as e:
            print(f"\n❌ Monitor error: {e}")
            await asyncio.sleep(300)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
