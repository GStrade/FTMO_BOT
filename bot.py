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
    return msg    r.raise_for_status()
    return r.json()

def tg_send_photo(photo_path: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(photo_path, "rb") as f:
        files = {"photo": f}
        data = {"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
        r = requests.post(url, files=files, data=data, timeout=60)
    r.raise_for_status()
    return r.json()

def fmt_price(x: float) -> str:
    if x >= 100:
        return f"{x:.2f}"
    return f"{x:.5f}"

def idea_score(idea: dict) -> float:
    '''Heuristic scoring to cap signals to top quality.'''
    entry = idea["entry"]
    stop = idea["stop"]
    tf = idea.get("timeframe", "1h")
    # lower relative risk is better
    rel_risk = abs(entry - stop) / max(1e-9, abs(entry))
    score = 1.0 / (rel_risk + 1e-6)
    # timeframe weight: prefer 1d a bit
    if tf == "1d":
        score *= 1.2
    # small bonus to EMA/RSI setups (they include 'EMA' in reason)
    if "EMA" in idea.get("reason", ""):
        score *= 1.1
    return float(score)

def next_runs_local(tz: ZoneInfo) -> str:
    '''Return human-friendly next run times based on cron 06:00 & 14:00 local.'''
    now = datetime.now(tz)
    today_6 = now.replace(hour=6, minute=0, second=0, microsecond=0)
    today_14 = now.replace(hour=14, minute=0, second=0, microsecond=0)
    upcoming = []
    for t in [today_6, today_14]:
        if t > now:
            upcoming.append(t.strftime("%H:%M"))
    if not upcoming:
        # tomorrow 06:00
        tomorrow_6 = (now + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
        upcoming.append(tomorrow_6.strftime("%H:%M"))
    return ", ".join(upcoming)

def load_state(path="state.json"):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"first_run": None, "days_with_signals": []}

def save_state(state, path="state.json"):
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass  # GitHub Actions קבצים אינם נשמרים בין ריצות

def main():
    with open("config.yaml", "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    symbols = cfg["symbols"]
    tfs = cfg["timeframes"]
    chart_cfg = cfg.get("chart", {})
    breakout_cfg = cfg.get("breakout", {})
    emarsi_cfg = cfg.get("ema_rsi", {})
    limits_cfg = cfg.get("limits", {"min_signals": 2, "max_signals": 5, "max_per_symbol": 2})
    status_cfg = cfg.get("status", {"send_status": True, "timezone": "Asia/Jerusalem"})
    ftmo = cfg.get("ftmo_rules", {"daily_loss_limit_percent": 5, "overall_loss_limit_percent": 10, "profit_target_percent": 10, "min_trading_days": 10})

    tz = ZoneInfo(status_cfg.get("timezone", "Asia/Jerusalem"))

    header = (
        f"**FTMO Signals Bot (Educational)**\n"
        f"Account (label): {ACCOUNT_SIZE:.0f}$ | Risk/trade: {RISK_PER_TRADE_PERCENT:.2f}%\n"
        f"FTMO rules (info): Daily {ftmo['daily_loss_limit_percent']}% | Overall {ftmo['overall_loss_limit_percent']}% | Target {ftmo['profit_target_percent']}% | Min days {ftmo['min_trading_days']}"
    )
    tg_send_message(header)

    # 1) Gather all ideas first
    all_ideas = []
    data_cache = {}

    for symbol in symbols:
        # Daily
        if breakout_cfg.get("enabled", True) and "1d" in tfs:
            dfd = data_cache.get((symbol, "1d"))
            if dfd is None:
                from data import fetch_history
                dfd = fetch_history(symbol, "1d")
                data_cache[(symbol, "1d")] = dfd
            if not dfd.empty:
                all_ideas.extend(breakout_daily(symbol, dfd, breakout_cfg))

        # 1h EMA/RSI
        if emarsi_cfg.get("enabled", True) and "1h" in tfs:
            dfh = data_cache.get((symbol, "1h"))
            if dfh is None:
                from data import fetch_history
                dfh = fetch_history(symbol, "1h")
                data_cache[(symbol, "1h")] = dfh
            if not dfh.empty:
                all_ideas.extend(ema_rsi_pullback(symbol, dfh, emarsi_cfg))

    # 2) Rank & cap ideas per symbol and globally
    if all_ideas:
        # score
        for idea in all_ideas:
            idea["_score"] = idea_score(idea)

        # sort by score desc
        all_ideas.sort(key=lambda x: x["_score"], reverse=True)

        # cap per symbol
        capped = []
        per_symbol = {}
        max_per_symbol = int(limits_cfg.get("max_per_symbol", 2))
        for idea in all_ideas:
            sym = idea["symbol"]
            per_symbol.setdefault(sym, 0)
            if per_symbol[sym] < max_per_symbol:
                capped.append(idea)
                per_symbol[sym] += 1

        # cap globally
        max_signals = int(limits_cfg.get("max_signals", 5))
        selected = capped[:max_signals]
    else:
        selected = []

    # 3) Send selected signals with charts
    sent = 0
    for idea in selected:
        symbol = idea["symbol"]
        tf = idea["timeframe"]
        entry, stop, tps = idea["entry"], idea["stop"], idea["targets"]
        msg = (
            f"*{symbol}* (TF: {tf}) – *{idea['direction']}*\n"
            f"Entry: `{fmt_price(entry)}` | SL: `{fmt_price(stop)}`\n"
            f"TP1: `{fmt_price(tps[0])}` | TP2: `{fmt_price(tps[1])}` | TP3: `{fmt_price(tps[2])}`\n"
            f"R:R: `1:1`, `1:2`, `1:3`\n"
            f"סיבה: {idea['reason']}\n"
            f"_הערה_: אות לימודי/חינוכי בלבד; לא פקודת מסחר.\n"
        )
        try:
            from chart import draw_signal_chart
            df = data_cache[(symbol, "1d")] if tf == "1d" else data_cache[(symbol, "1h")]
            img = draw_signal_chart(symbol, tf, df, entry, stop, tps,
                                    save_dir=cfg["chart"].get("save_dir", "charts"),
                                    candles=cfg["chart"].get("candles", 150))
            tg_send_photo(img, caption=msg)
        except Exception as e:
            msg += f"\n(בעיה ביצירת גרף: {e})"
            tg_send_message(msg)
        sent += 1

    # 4) If none selected
    if sent == 0:
        tg_send_message("לא נמצאו סט־אפים שעומדים בקריטריונים כרגע. נשוב בבדיקה הבאה.")

    # 5) Status & trading days progress
    if status_cfg.get("send_status", True):
        state = load_state()
        today_str = datetime.now(tz).strftime("%Y-%m-%d")
        if state["first_run"] is None:
            state["first_run"] = today_str
        if sent > 0 and today_str not in state["days_with_signals"]:
            state["days_with_signals"].append(today_str)
        save_state(state)

        days_done = len(state["days_with_signals"])
        min_days = int(ftmo.get("min_trading_days", 10))
        upcoming = next_runs_local(tz)
        status_msg = (
            f"*FTMO Status*\n"
            f"יום: {today_str} ({status_cfg.get('timezone','Asia/Jerusalem')})\n"
            f"אותות שנשלחו כעת: {sent}\n"
            f"ימי מסחר עם אותות עד כה: {days_done}/{min_days}\n"
            f"הרצות הבאות היום: {upcoming}\n"
            f"כללי FTMO (לידע): הפסד יומי {ftmo['daily_loss_limit_percent']}% | הפסד כולל {ftmo['overall_loss_limit_percent']}% | יעד רווח {ftmo['profit_target_percent']}%"
        )
        tg_send_message(status_msg)

if __name__ == "__main__":
    main()
