
import os
import mplfinance as mpf
import pandas as pd
from datetime import datetime

def draw_signal_chart(symbol: str, timeframe: str, df: pd.DataFrame, entry: float, stop: float, tps, save_dir: str, candles: int = 150) -> str:
    os.makedirs(save_dir, exist_ok=True)
    tail = df.iloc[-candles:]
    lines = [
        mpf.make_addplot([entry]*len(tail)),
        mpf.make_addplot([stop]*len(tail)),
    ]
    for tp in tps:
        lines.append(mpf.make_addplot([tp]*len(tail)))

    title = f"{symbol} | {timeframe} | Entry/SL/TP"
    fname = f"{symbol.replace('=','')}_{timeframe}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
    out_path = os.path.join(save_dir, fname)

    mpf.plot(
        tail,
        type='candle',
        style='charles',
        addplot=lines,
        title=title,
        volume=True,
        savefig=out_path
    )
    return out_path
