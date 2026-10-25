"""
Конфигурация приложения
"""
import os
from enum import Enum

# Проверка на облако
IS_CLOUD = os.path.exists("/mount/src") or "STREAMLIT_SERVER_PORT" in os.environ
CACHE_VERSION = "v8"

class CacheTTL(Enum):
    OPTIONBOARD = 120
    SERIES_INFO = 300
    VOLATILITY_GRAPH = 300
    LAST_PRICE = 10
    FUTURES_CONTRACTS = 3600
    RVI_CURRENT = 60
    RVI_HISTORY = 300
    G_CURVE = 600
    DIVIDENDS = 21600

MAX_IV_HISTORY_PER_SERIES = 365
MAX_IV_HISTORY_SERIES = 100
MAX_JOURNAL_ROWS = 10000
MAX_ALERT_CHECKS = 500

class Commission:
    OPTIONS_PCT = 3.0
    OPTIONS_MIN = 0.02
    FUTURES_PCT = 0.1
    STOCKS_PCT = 0.3
    METALS_PCT = 1.9
    CURRENCY_PCT = 0.9
    MIN_OTHER = 0.01

class ChecklistRules:
    MIN_BUSINESS_DAYS_TO_EXPIRY = 20
    MIN_QTY = 2
    VOLUME_SPIKE_MULTIPLIER = 2.0
    LEVEL_PROXIMITY_PCT = 2.0
    SKEW_THRESHOLD_PCT = 15.0
    CLOSE_WEEKLY_DAYS_THRESHOLD = 10
    CLOSE_WEEKLY_DAYS_BEFORE = 1
    CLOSE_MONTHLY_DAYS_BEFORE = 2

API_BASE_URL = "https://iss.moex.com/iss/apps/option-calc/v1"
ISS_BASE_URL = "https://iss.moex.com/iss"

class UIConfig:
    MAX_COLUMNS_DESKTOP = 20
    MAX_COLUMNS_MOBILE = 3
    MOBILE_BREAKPOINT = 768
    HEADER_HEIGHT = 60
    SIDEBAR_WIDTH = 280

class Colors:
    SUCCESS = "#00a651"
    ERROR = "#d32f2f"
    WARNING = "#e6a500"
    INFO = "#1e88e5"
    NEUTRAL = "#7a7a7a"
    CALL = "#00a651"
    PUT = "#d32f2f"
    ATM = "#1e88e5"
    ITM = "#2e7d32"
    OTM = "#d32f2f"

ASSET_TYPE_MAP = {
    'Фьючерс': 'futures',
    'Акция': 'share',
    'Валюта': 'currency',
    'Товар': 'commodity',
    'Индекс': 'index',
}
