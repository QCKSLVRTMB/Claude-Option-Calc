"""
Вспомогательные функции и утилиты
"""
import math
import logging
from typing import Optional, Any, Union
import streamlit as st
from datetime import date, datetime
import numpy as np

logger = logging.getLogger(__name__)

# ================= БЕЗОПАСНЫЕ ПРЕОБРАЗОВАНИЯ =================

def safe_float(value: Any, default: float = 0.0) -> float:
    """Безопасно преобразует значение в float"""
    if value is None or value == "":
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)

def safe_int(value: Any, default: int = 0) -> int:
    """Безопасно преобразует значение в int"""
    if value is None or value == "":
        return int(default)
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)

def safe_str(value: Any, default: str = "") -> str:
    """Безопасно преобразует значение в str"""
    if value is None:
        return default
    return str(value).strip() if value else default

def safe_bool(value: Any, default: bool = False) -> bool:
    """Безопасно преобразует значение в bool"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).lower().strip()
    return s in ("true", "1", "yes", "on")

# ================= ВАЛИДАЦИЯ =================

def validate_date_range(start_date: date, end_date: date) -> tuple[bool, str]:
    """Валидирует диапазон дат"""
    if start_date > end_date:
        return False, "Дата начала не может быть позже даты окончания"
    
    days_diff = (end_date - start_date).days
    if days_diff > 365 * 10:
        return False, "Диапазон не может быть более 10 лет"
    
    return True, ""

def validate_price(price: float, min_price: float = 0.01) -> tuple[bool, str]:
    """Валидирует цену"""
    if not isinstance(price, (int, float)):
        return False, "Цена должна быть числом"
    
    if price < min_price:
        return False, f"Цена должна быть не менее {min_price}"
    
    if price > 1e10:
        return False, "Цена слишком большая"
    
    if not math.isfinite(price):
        return False, "Цена должна быть конечным числом"
    
    return True, ""

def validate_qty(qty: int, min_qty: int = 1) -> tuple[bool, str]:
    """Валидирует количество"""
    if not isinstance(qty, int):
        return False, "Кол-во должно быть целым числом"
    
    if qty < min_qty:
        return False, f"Кол-во должно быть не менее {min_qty}"
    
    if qty > 1000000:
        return False, "Кол-во слишком большое"
    
    return True, ""

# ================= ФОРМАТИРОВАНИЕ =================

def fmt_price(price: Optional[float], decimals: int = 2) -> str:
    """Форматирует цену"""
    if price is None or not math.isfinite(price):
        return "—"
    return f"{price:,.{decimals}f} ₽"

def fmt_pct(value: Optional[float], decimals: int = 2) -> str:
    """Форматирует процент"""
    if value is None or not math.isfinite(value):
        return "—"
    return f"{value:+.{decimals}f}%"

def fmt_date(d: Optional[Union[date, datetime]]) -> str:
    """Форматирует дату"""
    if d is None:
        return "—"
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%d.%m.%Y")

def fmt_datetime(dt: Optional[datetime]) -> str:
    """Форматирует дату и время"""
    if dt is None:
        return "—"
    return dt.strftime("%d.%m.%Y %H:%M:%S")

def fmt_strike(strike: Optional[float], decimals: int = 0) -> str:
    """Форматирует страйк"""
    if strike is None or not math.isfinite(strike):
        return "—"
    if decimals == 0 and strike == int(strike):
        return f"{int(strike)}"
    return f"{strike:.{decimals}f}"

# ================= РАСЧЁТЫ =================

def norm_cdf(x: float) -> float:
    """Нормальное распределение (CDF)"""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def black_scholes(
    S: float, K: float, T: float, r: float, sigma: float,
    q: float = 0.0, option_type: str = "call"
) -> float:
    """Black-Scholes для европейских опционов"""
    if T <= 0 or S <= 0 or K <= 0 or sigma <= 0:
        return max(0.0, S - K) if option_type == "call" else max(0.0, K - S)
    
    try:
        r_pct = r / 100.0
        q_pct = q / 100.0
        sigma_pct = sigma / 100.0
        
        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r_pct - q_pct + sigma_pct * sigma_pct / 2) * T) / (sigma_pct * sqrt_T)
        d2 = d1 - sigma_pct * sqrt_T
        
        if option_type == "call":
            return S * math.exp(-q_pct * T) * norm_cdf(d1) - K * math.exp(-r_pct * T) * norm_cdf(d2)
        else:
            return K * math.exp(-r_pct * T) * norm_cdf(-d2) - S * math.exp(-q_pct * T) * norm_cdf(-d1)
    except Exception as e:
        logger.error(f"Black-Scholes error: {e}")
        return max(0.0, S - K) if option_type == "call" else max(0.0, K - S)

def calc_greeks(
    S: float, K: float, T: float, r: float, sigma: float,
    q: float = 0.0, option_type: str = "call"
) -> dict:
    """Расчёт греков"""
    if T <= 1e-6 or S <= 0 or K <= 0 or sigma <= 0:
        return {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0}
    
    try:
        r_pct = r / 100.0
        q_pct = q / 100.0
        sigma_pct = sigma / 100.0
        
        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r_pct - q_pct + sigma_pct * sigma_pct / 2) * T) / (sigma_pct * sqrt_T)
        d2 = d1 - sigma_pct * sqrt_T
        
        nd1 = norm_cdf(d1)
        pdf = math.exp(-d1 * d1 / 2) / math.sqrt(2 * math.pi)
        
        # Delta
        delta = math.exp(-q_pct * T) * nd1 if option_type == "call" else math.exp(-q_pct * T) * (nd1 - 1)
        
        # Gamma
        gamma = pdf * math.exp(-q_pct * T) / (S * sigma_pct * sqrt_T)
        
        # Vega
        vega = S * pdf * math.exp(-q_pct * T) * sqrt_T / 100.0
        
        # Theta
        if option_type == "call":
            theta = (-S * pdf * sigma_pct * math.exp(-q_pct * T) / (2 * sqrt_T)
                     - r_pct * K * math.exp(-r_pct * T) * nd1
                     + q_pct * S * math.exp(-q_pct * T) * nd1) / 365.0
        else:
            nd2_neg = norm_cdf(-d2)
            theta = (-S * pdf * sigma_pct * math.exp(-q_pct * T) / (2 * sqrt_T)
                     + r_pct * K * math.exp(-r_pct * T) * nd2_neg
                     - q_pct * S * math.exp(-q_pct * T) * (nd1 - 1)) / 365.0
        
        # Rho
        rho = K * T * math.exp(-r_pct * T) * (nd1 if option_type == "call" else -nd2_neg) / 100.0
        
        return {
            "delta": float(delta),
            "gamma": float(gamma),
            "vega": float(vega),
            "theta": float(theta),
            "rho": float(rho),
        }
    except Exception as e:
        logger.error(f"Greeks calculation error: {e}")
        return {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0}

def calc_iv_rank(
    current_iv: float, min_iv: float, max_iv: float
) -> Optional[float]:
    """Расчёт IV Rank"""
    if min_iv is None or max_iv is None or max_iv <= min_iv:
        return None
    
    try:
        rank = (current_iv - min_iv) / (max_iv - min_iv) * 100.0
        return max(0.0, min(100.0, rank))
    except Exception as e:
        logger.error(f"IV Rank error: {e}")
        return None

# ================= ЛОГИРОВАНИЕ =================

def setup_logging():
    """Настраивает логирование"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

# ================= CSV =================

def csv_escape(value: Any) -> str:
    """Экранирует значение для CSV (RFC 4180)"""
    s = str(value if value is not None else "")
    s = s.replace('"', '""')
    if any(c in s for c in ',"}\n\r'):
        return f'"{s}"'
    return s

def csv_row(values: list) -> str:
    """Создаёт CSV-строку"""
    return ",".join(csv_escape(v) for v in values)
