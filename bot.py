import os
import yfinance as yf
import mplfinance as mpf
import requests
import pandas as pd
from telegram import Bot
from datetime import datetime, timedelta

# === קריאת משתנים מהסביבה ===
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
bot = Bot(token=TOKEN)

# צור תיקייה לגרפים אם לא קיימת
CHARTS_DIR = "charts"
os.makedirs(CHARTS_DIR, exist_ok=True)

# ===== מחיקה אוטומטית של גרפים ישנים =====
def clean_old_charts(days=7):
    now = datetime.now()
    for file in os.listdir(CHARTS_DIR):
        path = os.path.join(CHARTS_DIR, file)
        if os.path.isfile(path):
            modified_time = datetime.fromtimestamp(os.path.getmtime(path))
            if now - modified_time > timedelta(days=days):
                os.remove(path)

# ===== כתיבה ללוג =====
def write_log(text):
    log_file = "log.txt"
    # אם הקובץ לא קיים – ניצור אותו עם כותרת
    if not os.path.exists(log_file):
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("===== Stock Bot Logs =====\n")
    # הוספת שורה חדשה ללוג
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")

# ===== חדשות על מניה =====
def get_news(ticker):
    url = f"https://query1.finance.yahoo.com/v1/finance/search?q={ticker}"
    try:
        r = requests.get(url).json()
        if "news" in r and len(r["news"]) > 0:
            return r["news"][0]["title"]
    except:
        return "אין חדשות זמינות"
    return "אין חדשות זמינות"

# ===== חוות דעת אנליסטים =====
def get_analyst_opinion(ticker):
    try:
        stock = yf.Ticker(ticker)
        recs = stock.recommendations_summary
        if recs is None or recs.empty:
            return "אין נתוני אנליסטים", "Low"
        last = recs.iloc[-1].to_dict()
        buy = last.get("buy", 0)
        hold = last.get("hold", 0)
        sell = last.get("sell", 0)
        total = buy + hold + sell
        if total == 0:
            return "אין נתוני אנליסטים", "Low"

        buy_pct = round(buy/total*100)
        hold_pct = round(hold/total*100)
        sell_pct = round(sell/total*100)

        # ציון משוקלל
        if buy_pct >= 60:
            score = "High"
        elif buy_pct >= 40:
            score = "Medium"
        else:
            score = "Low"

        return f"קנייה: {buy_pct}% | החזקה: {hold_pct}% | מכירה: {sell_pct}%", score
    except:
        return "אין נתוני אנליסטים", "Low"

# ===== גרף נרות עם קווי יעד =====
def generate_chart(ticker, entry, stop, tp1, tp2, tp3):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="3mo", interval="1d")
    if hist.empty:
        return None

    hlines = dict(hlines=[entry, stop, tp1, tp2, tp3],
                  colors=["g","r","b","b","b"],
                  linewidths=[1.5,1.5,1,1,1],
                  linestyle="--")

    filepath = os.path.join(CHARTS_DIR, f"{ticker}.png")
    mpf.plot(hist, type="candle", style="yahoo",
             title=f"{ticker} - גרף נרות",
             hlines=hlines,
             savefig=filepath)
    return filepath

# ===== סורק מניות עם fallback =====
def scan_stocks(limit=5, strict=True):
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    table = pd.read_html(url)[0]
    tickers = table['Symbol'].tolist()

    selected = []

    for t in tickers:
        try:
            # תיקון סימבולים שלא עובדים ב-Yahoo
            if "." in t:
                t = t.replace(".", "-")

            stock = yf.Ticker(t)
            info = stock.info
            sector = info.get("sector", "לא ידוע")

            hist = stock.history(period="10d", interval="1d")
            if len(hist) < 2:
                continue

            today = hist.iloc[-1]
            yesterday = hist.iloc[-2]

            # שינוי יומי באחוזים
            change = (today['Close'] - yesterday['Close']) / yesterday['Close'] * 100
            # ממוצע ווליום
            avg_vol = hist['Volume'].tail(5).mean()
            unusual_vol = today['Volume'] > (2 * avg_vol if strict else 1.2 * avg_vol)

            if abs(change) >= (3 if strict else 2) and unusual_vol:
                entry = today['Close']
                stop = entry * 0.97   # סטופ ~3%
                tp1 = entry * 1.06    # יעד 1:2
                tp2 = entry * 1.09    # יעד 1:3
                tp3 = entry * 1.15    # יעד 1:5

                selected.append({
                    "ticker": t,
                    "sector": sector,
                    "entry": round(entry,2),
                    "stop": round(stop,2),
                    "tp1": round(tp1,2),
                    "tp2": round(tp2,2),
                    "tp3": round(tp3,2),
                    "change": round(change,2)
                })
        except:
            continue

    return selected[:limit]

# ===== שליחת דוח =====
def send_report():
    clean_old_charts(days=7)  # 🧹 מנקה גרפים ישנים לפני הרצה

    stocks = scan_stocks()

    if not stocks:
        msg = "⚠️ לא נמצאו מניות לפי הקריטריונים הקשוחים. מחפש קריטריונים חלופיים..."
        bot.send_message(chat_id=CHAT_ID, text=msg)
        write_log(msg)
        stocks = scan_stocks(strict=False)

    if not stocks:
        msg = "❌ גם בקריטריונים חלופיים לא נמצאו מניות להיום."
        bot.send_message(chat_id=CHAT_ID, text=msg)
        write_log(msg)
        return

    for s in stocks:
        news = get_news(s["ticker"])
        analyst, score = get_analyst_opinion(s["ticker"])
        chart = generate_chart(s["ticker"], s["entry"], s["stop"], s["tp1"], s["tp2"], s["tp3"])

        msg = (
            f"📊 מניה חמה: {s['ticker']}\n"
            f"🏷️ סקטור: {s['sector']}\n\n"
            f"💵 כניסה: {s['entry']}\n"
            f"🔻 סטופ: {s['stop']}\n"
            f"🎯 יעד 1 (1:2): {s['tp1']}\n"
            f"🎯 יעד 2 (1:3): {s['tp2']}\n"
            f"🎯 יעד 3 (1:5): {s['tp3']}\n\n"
            f"📈 שינוי יומי: {s['change']}%\n"
            f"📰 חדשות: {news}\n"
            f"📊 חוות דעת אנליסטים: {analyst}\n"
            f"⭐ ציון משוקלל: {score}\n"
        )

        bot.send_message(chat_id=CHAT_ID, text=msg)
        write_log(msg)
        if chart:
            bot.send_photo(chat_id=CHAT_ID, photo=open(chart, "rb"))

if __name__ == "__main__":
    send_report()
