import os
import mplfinance as mpf
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

def draw_signal_chart(symbol: str, timeframe: str, df: pd.DataFrame,
                      entry: float, stop: float, tps, save_dir: str, candles: int = 150) -> str:
    os.makedirs(save_dir, exist_ok=True)

    # ודא שכל הערכים מספריים
    df = df.copy()
    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Open", "High", "Low", "Close"])

    # חתך של מספר נרות אחרונים
    tail = df.iloc[-candles:].copy()

    # יצירת הגרף
    fig, ax = mpf.plot(
        tail,
        type="candle",
        style="charles",
        volume=True,
        title=f"{symbol} ({timeframe})",
        returnfig=True
    )

    # קו כניסה (כחול)
    ax[0].axhline(entry, color="blue", linestyle="--", linewidth=1)
    ax[0].text(tail.index[-1], entry, " Entry", color="blue", va="bottom")

    # קו סטופ (אדום)
    ax[0].axhline(stop, color="red", linestyle="--", linewidth=1)
    ax[0].text(tail.index[-1], stop, " Stop", color="red", va="top")

    # קווי טייק פרופיט (ירוק)
    colors = ["green", "darkgreen", "lime"]
    for i, tp in enumerate(tps, start=1):
        ax[0].axhline(tp, color=colors[i-1], linestyle="--", linewidth=1)
        ax[0].text(tail.index[-1], tp, f" TP{i}", color=colors[i-1], va="bottom")

    # שמירת הקובץ
    fname = f"{symbol.replace('=','')}_{timeframe}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
    out_path = os.path.join(save_dir, fname)
    plt.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path
