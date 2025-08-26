
import yfinance as yf
import pandas as pd

def fetch_history(symbol: str, interval: str) -> pd.DataFrame:
    '''Fetch history via yfinance.
    interval: '1h' (maps to 60m) or '1d'.
    '''
    if interval == "1h":
        df = yf.download(symbol, period="30d", interval="60m", auto_adjust=True, progress=False)
    elif interval == "1d":
        df = yf.download(symbol, period="60d", interval="1d", auto_adjust=True, progress=False)
    else:
        raise ValueError("Unsupported interval: " + interval)
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    df = df.rename(columns=str.title)  # ensure 'Open','High','Low','Close','Adj Close','Volume'
    df.dropna(inplace=True)
    return df
