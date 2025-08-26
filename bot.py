import os
import json
import yaml
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from data import fetch_history
from strategies import breakout_daily, ema_rsi_pullback
from chart import draw_signal_chart

load_dotenv()

# Token fallbacks
TOKEN = (
    os.getenv("TOKEN_FTMO")
    or os.getenv("TOKEN_STOCKS")
    or os.getenv("BOT_TOKEN")
)
CHAT_ID = (
    os.getenv("CHAT_ID_FTMO")
    or os.getenv("CHAT_ID_STOCKS")
    or os.getenv("CHAT_ID")
)

ACCOUNT_SIZE = float(os.getenv("ACCOUNT_SIZE", "100000") or "100000")
RISK_PER_TRADE_PERCENT = float(os.getenv("RISK_PER_TRADE_PERCENT", "0.5") or "0.5")

if not TOKEN or not CHAT_ID:
    raise SystemExit("Missing TOKEN_FTMO/CHAT_ID_FTMO (or TOKEN_STOCKS/CHAT_ID_STOCKS).")

def tg_send_message(text: str, parse_mode: str = "Markdown"):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": parse_mode, "disable_web_page_preview": True}
    r = requests.post(url, data=data, timeout=30)
    r.raise_for_status()
    return r.json()

def tg_send_photo(photo_path: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(photo_path, "rb") as f:
        files = {"photo": f}
        data = {"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
        r = requests.post(url, files=files, data=data, timeout=60)
    r.raise_for_status()
    return r.json()

def format_signal_message(idea: dict) -> str:
    entry, stop, tps = idea["entry"], idea["stop"], idea["targets"]
    msg = (
        f"📊 *FTMO Signal*\n\n"
        f"🪙 *Symbol*: {idea['symbol']}\n"
        f"⏱ *Timeframe*: {idea['timeframe']}\n"
        f"📈 *Direction*: {idea['direction']}\n\n"
        f"🎯 *Entry*: `{entry:.2f}`\n"
        f"🛑 *Stop*: `{stop:.2f}`\n\n"
        f"🎯 *Targets*:\n"
        f" • TP1 = {tps[0]:.2f} (R:R 1:1)\n"
        f" • TP2 = {tps[1]:.2f} (R:R 1:2)\n"
        f" • TP3 = {tps[2]:.2f} (R:R 1:3)\n\n"
        f"ℹ️ *Reason*: {idea['reason']}\n"
        f"⚠️ *Note*: אות לימודי/חינוכי בלבד; לא פקודת מסחר"
    )
    return msg

def main():
    with open("config.yaml", "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    symbols = cfg["symbols"]
    tfs = cfg["timeframes"]
    breakout_cfg = cfg.get("breakout", {})
    emarsi_cfg = cfg.get("ema_rsi", {})

    tg_send_message(
        f"🚀 *FTMO Signals Bot Started*\n"
        f"Account: {ACCOUNT_SIZE:.0f}$ | Risk/trade: {RISK_PER_TRADE_PERCENT:.2f}%"
    )

    all_ideas = []
    data_cache = {}

    for symbol in symbols:
        # Daily breakout
        if breakout_cfg.get("enabled", True) and "1d" in tfs:
            dfd = fetch_history(symbol, "1d")
            data_cache[(symbol, "1d")] = dfd
            if not dfd.empty:
                all_ideas.extend(breakout_daily(symbol, dfd, breakout_cfg))

        # EMA/RSI 1h
        if emarsi_cfg.get("enabled", True) and "1h" in tfs:
            dfh = fetch_history(symbol, "1h")
            data_cache[(symbol, "1h")] = dfh
            if not dfh.empty:
                all_ideas.extend(ema_rsi_pullback(symbol, dfh, emarsi_cfg))

    if not all_ideas:
        tg_send_message("ℹ️ לא נמצאו סט־אפים מתאימים כרגע.")
        return

    # שליחת אותות
    for idea in all_ideas[:5]:  # מקסימום 5
        msg = format_signal_message(idea)
        try:
            df = data_cache[(idea["symbol"], idea["timeframe"])]
            img = draw_signal_chart(
                idea["symbol"], idea["timeframe"], df,
                idea["entry"], idea["stop"], idea["targets"],
                save_dir=cfg["chart"].get("save_dir", "charts"),
                candles=cfg["chart"].get("candles", 150)
            )
            tg_send_photo(img, caption=msg)
        except Exception as e:
            tg_send_message(msg + f"\n(⚠️ בעיה ביצירת גרף: {e})")

if __name__ == "__main__":
    main()
