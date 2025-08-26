import numpy as np
import pandas as pd
from typing import Dict, List
from utils import get_symbol_meta, rr_ratio

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0.0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    hl = high - low
    hc = (high - close.shift()).abs()
    lc = (low - close.shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def breakout_daily(symbol: str, df_daily: pd.DataFrame, cfg: Dict) -> List[Dict]:
    """
    Propose pending orders for next day around yesterday's High/Low.
    Entry = prev_high + buffer ; Stop = ATR * mult ; TP = 1R/2R/3R
    """
    out = []
    if df_daily.shape[0] < 20:
        return out
    meta = get_symbol_meta(symbol)
    atr_series = atr(df_daily, cfg["atr_period"]).dropna()
    if atr_series.empty:
        return out

    prev = df_daily.iloc[-2]
    atr_val = float(atr_series.iloc[-1])
    buffer_price = float(cfg["breakout_buffer_pips"] * meta.pip_size)

    # LONG breakout
    entry_long = float(prev["High"] + buffer_price)
    stop_long = float(entry_long - cfg["atr_mult_stop"] * atr_val)
    r = entry_long - stop_long
    if r > 0:
        tp1 = entry_long + r
        tp2 = entry_long + 2 * r
        tp3 = entry_long + 3 * r
        out.append({
            "symbol": symbol, "timeframe": "1d", "direction": "LONG",
            "entry": entry_long, "stop": stop_long,
            "targets": [tp1, tp2, tp3],
            "rrs": [1.0, 2.0, 3.0],
            "reason": "Daily Breakout מעל שיא אתמול + ATR Stop",
        })

    # SHORT breakout
    entry_short = float(prev["Low"] - buffer_price)
    stop_short = float(entry_short + cfg["atr_mult_stop"] * atr_val)
    r = stop_short - entry_short
    if r > 0:
        tp1 = entry_short - r
        tp2 = entry_short - 2 * r
        tp3 = entry_short - 3 * r
        out.append({
            "symbol": symbol, "timeframe": "1d", "direction": "SHORT",
            "entry": entry_short, "stop": stop_short,
            "targets": [tp1, tp2, tp3],
            "rrs": [1.0, 2.0, 3.0],
            "reason": "Daily Breakout מתחת לשפל אתמול + ATR Stop",
        })

    return out

def ema_rsi_pullback(symbol: str, df_1h: pd.DataFrame, cfg: Dict) -> List[Dict]:
    """
    Trend-following entries (EMA50 vs EMA200) after RSI pullback.
    Stop = ATR*mult ; TP = 1R/2R/3R from last price.
    """
    out = []
    if df_1h.shape[0] < max(cfg["ema_fast"], cfg["ema_slow"]) + 30:
        return out

    close = df_1h["Close"].copy()
    e50 = ema(close, cfg["ema_fast"])
    e200 = ema(close, cfg["ema_slow"])
    r = rsi(close, cfg["rsi_period"])
    atr_series = atr(df_1h, cfg["atr_period"]).dropna()
    if atr_series.empty:
        return out

    last_close = float(close.iloc[-1])
    last_e50 = float(e50.iloc[-1])
    last_e200 = float(e200.iloc[-1])
    last_rsi = float(r.iloc[-1])
    last_atr = float(atr_series.iloc[-1])

    # LONG condition
    if last_e50 > last_e200 and last_rsi <= cfg["rsi_pullback_long"]:
        entry = last_close
        stop = entry - cfg["atr_mult_stop"] * last_atr
        risk = entry - stop
        if risk > 0:
            tps = [entry + risk, entry + 2*risk, entry + 3*risk]
            out.append({
                "symbol": symbol, "timeframe": "1h", "direction": "LONG",
                "entry": entry, "stop": stop, "targets": tps,
                "rrs": [1.0, 2.0, 3.0],
                "reason": "EMA50>EMA200 + RSI Pullback + ATR Stop",
            })

    # SHORT condition
    if last_e50 < last_e200 and last_rsi >= cfg["rsi_pullback_short"]:
        entry = last_close
        stop = entry + cfg["atr_mult_stop"] * last_atr
        risk = stop - entry
        if risk > 0:
            tps = [entry - risk, entry - 2*risk, entry - 3*risk]
            out.append({
                "symbol": symbol, "timeframe": "1h", "direction": "SHORT",
                "entry": entry, "stop": stop, "targets": tps,
                "rrs": [1.0, 2.0, 3.0],
                "reason": "EMA50<EMA200 + RSI Pullback + ATR Stop",
            })

    return out        return out

    prev = df_daily.iloc[-2]
    atr_val = atr_series.iloc[-1]
    buffer_price = cfg["breakout_buffer_pips"] * meta.pip_size

    # LONG breakout מעל High של אתמול
    entry_long = prev["High"] + buffer_price
    stop_long = entry_long - cfg["atr_mult_stop"] * atr_val
    r = (entry_long - stop_long)
    tp1 = entry_long + r
    tp2 = entry_long + 2 * r
    tp3 = entry_long + 3 * r

    if r > 0:
        out.append({
            "symbol": symbol, "timeframe": "1d", "direction": "LONG",
            "entry": float(entry_long), "stop": float(stop_long),
            "targets": [float(tp1), float(tp2), float(tp3)],
            "rrs": [1.0, 2.0, 3.0],
            "reason": "Daily Breakout מעל שיא אתמול + ATR Stop",
        })

    # SHORT breakout מתחת Low של אתמול
    entry_short = prev["Low"] - buffer_price
    stop_short = entry_short + cfg["atr_mult_stop"] * atr_val
    r = (stop_short - entry_short)
    tp1 = entry_short - r
    tp2 = entry_short - 2 * r
    tp3 = entry_short - 3 * r

    if r > 0:
        out.append({
            "symbol": symbol, "timeframe": "1d", "direction": "SHORT",
            "entry": float(entry_short), "stop": float(stop_short),
            "targets": [float(tp1), float(tp2), float(tp3)],
            "rrs": [1.0, 2.0, 3.0],
            "reason": "Daily Breakout מתחת לשפל אתמול + ATR Stop",
        })

    return out

def ema_rsi_pullback(symbol: str, df_1h: pd.DataFrame, cfg: Dict) -> List[Dict]:
    '''Trend-following entries (EMA50 vs EMA200) after RSI pullback.
    Stop = ATR*mult ; TP = 1R/2R/3R from last price.
    '''
    out = []
    if df_1h.shape[0] < max(cfg["ema_fast"], cfg["ema_slow"]) + 30:
        return out

    close = df_1h["Close"].copy()
    e50 = ema(close, cfg["ema_fast"])
    e200 = ema(close, cfg["ema_slow"])
    r = rsi(close, cfg["rsi_period"])
    atr_series = atr(df_1h, cfg["atr_period"]).dropna()
    if atr_series.empty:
        return out

    last_close = close.iloc[-1]
    last_e50 = e50.iloc[-1]
    last_e200 = e200.iloc[-1]
    last_rsi = r.iloc[-1]
    last_atr = atr_series.iloc[-1]

    # מגמת עליה: EMA50 > EMA200 ; Pullback: RSI נמוך לסף הלונג
    if last_e50 > last_e200 and last_rsi <= cfg["rsi_pullback_long"]:
        entry = float(last_close)
        stop = float(entry - cfg["atr_mult_stop"] * last_atr)
        risk = entry - stop
        if risk > 0:
            tps = [entry + risk, entry + 2*risk, entry + 3*risk]
            out.append({
                "symbol": symbol, "timeframe": "1h", "direction": "LONG",
                "entry": entry, "stop": stop, "targets": [float(tps[0]), float(tps[1]), float(tps[2])],
                "rrs": [1.0, 2.0, 3.0],
                "reason": "EMA50>EMA200 + RSI Pullback + ATR Stop",
            })

    # מגמת ירידה: EMA50 < EMA200 ; Pullback: RSI גבוה לסף השורט
    if last_e50 < last_e200 and last_rsi >= cfg["rsi_pullback_short"]:
        entry = float(last_close)
        stop = float(entry + cfg["atr_mult_stop"] * last_atr)
        risk = stop - entry
        if risk > 0:
            tps = [entry - risk, entry - 2*risk, entry - 3*risk]
            out.append({
                "symbol": symbol, "timeframe": "1h", "direction": "SHORT",
                "entry": entry, "stop": stop, "targets": [float(tps[0]), float(tps[1]), float(tps[2])],
                "rrs": [1.0, 2.0, 3.0],
                "reason": "EMA50<EMA200 + RSI Pullback + ATR Stop",
            })

    return out
