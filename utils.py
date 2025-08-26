
from dataclasses import dataclass

@dataclass
class SymbolMeta:
    pip_size: float
    pip_value_per_lot: float  # קירוב בלבד לצורכי תיוג

SYMBOL_MAP = {
    "EURUSD=X": SymbolMeta(pip_size=0.0001, pip_value_per_lot=10.0),
    "GBPUSD=X": SymbolMeta(pip_size=0.0001, pip_value_per_lot=10.0),
    "USDJPY=X": SymbolMeta(pip_size=0.01,   pip_value_per_lot=9.0),
    "XAUUSD=X": SymbolMeta(pip_size=0.1,    pip_value_per_lot=10.0),  # תלוי ברוקר
}

def get_symbol_meta(symbol: str) -> SymbolMeta:
    return SYMBOL_MAP.get(symbol, SymbolMeta(pip_size=0.0001, pip_value_per_lot=10.0))

def rr_ratio(entry: float, stop: float, target: float, is_long: bool) -> float:
    risk = (entry - stop) if is_long else (stop - entry)
    reward = (target - entry) if is_long else (entry - target)
    if risk <= 0:
        return 0.0
    return reward / risk
