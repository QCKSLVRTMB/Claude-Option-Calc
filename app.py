"""
Калькулятор опционов MOEX с поддержкой кеша между сессиями
"""
import streamlit as st
import logging
from datetime import datetime, date, timedelta

# Прямые импорты из корневой папки
from config import IS_CLOUD, CACHE_VERSION, Colors, UIConfig
from cache_manager import get_cache_manager
from utils import setup_logging, fmt_price, fmt_date, safe_float, safe_int

setup_logging()
logger = logging.getLogger(__name__)

# Вспомогательная функция для корректной работы статистики
def fmt_datetime_short(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return str(dt_str)

# ================= PAGE CONFIG =================
st.set_page_config(
    page_title="MOEX Options & Black-Scholes",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items=None,
)

# ================= ИНИЦИАЛИЗАЦИЯ =================
if "app_initialized" not in st.session_state:
    st.session_state["app_initialized"] = True
    st.session_state["cache_manager"] = get_cache_manager()
    
    if st.session_state.get("cache_load_success"):
        logger.info("✅ Cache successfully loaded from disk")
    elif st.session_state.get("cache_load_error"):
        logger.warning(f"⚠️ Cache load error: {st.session_state['cache_load_error']}")

cache_mgr = st.session_state["cache_manager"]

# ================= СТИЛИ =================
st.markdown("""
<style>
html, body { background-color: #f5f7fa; color: #1a3b4f; font-family: -apple-system, sans-serif; }
.block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1400px; }
[data-testid="stForm"] { border: 1px solid #e2edf4 !important; border-radius: 12px !important; padding: 16px !important; background: white !important; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important; }
button { border-radius: 8px !important; font-weight: 600 !important; }
button[kind="primary"] { background-color: #1e88e5 !important; color: white !important; }
button[kind="secondary"] { background-color: #eef2f7 !important; color: #1a3b4f !important; border: 1px solid #cfdfe9 !important; }
[data-testid="stDataFrame"] { border: 1px solid #e2edf4 !important; border-radius: 8px !important; }
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] { position: sticky !important; top: 0 !important; z-index: 999 !important; background-color: #ffffff !important; border-bottom: 1px solid #e2edf4 !important; padding-top: 8px !important; padding-bottom: 6px !important; }
[data-testid="stMetricContainer"] { background-color: #f8fbfd !important; border: 1px solid #e2edf4 !important; border-radius: 8px !important; padding: 12px !important; }
@media (max-width: 768px) {
    .block-container { padding-left: 0.75rem; padding-right: 0.75rem; padding-top: 0.5rem; }
    [data-testid="stForm"] { padding: 12px !important; }
    button { font-size: 0.85rem !important; padding: 8px 12px !important; }
    h1 { font-size: 1.5rem !important; } h2 { font-size: 1.2rem !important; } h3 { font-size: 1rem !important; }
    [data-testid="stMetricContainer"] { padding: 10px !important; }
}
</style>
""", unsafe_allow_html=True)

# ================= HEADER =================
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.markdown("# 📊 Калькулятор опционов MOEX")
    st.markdown("*Black-Scholes • Волатильность • Журнал сделок*")
with col2:
    if st.button("💾 Сохранить", use_container_width=True):
        if cache_mgr.flush_to_disk(): st.success("✅ Кеш сохранён")
        else: st.warning("⚠️ На Cloud кеш в памяти")
with col3:
    if st.button("📥 Загрузить", use_container_width=True):
        st.session_state["show_import"] = not st.session_state.get("show_import", False)

# ================= IMPORT/EXPORT =================
if st.session_state.get("show_import"):
    st.markdown("---")
    tabs = st.tabs(["📥 Импорт", "📤 Экспорт", "📈 Статистика"])
    with tabs[0]:
        st.markdown("### Загрузить кеш")
        col1, col2 = st.columns(2)
        with col1:
            uploaded_file = st.file_uploader("JSON файл", type=["json"], key="cache_uploader")
            if uploaded_file:
                success, message = cache_mgr.import_from_json(uploaded_file.read().decode("utf-8"))
                if success: st.success(f"✅ {message}"); st.balloons()
                else: st.error(f"❌ {message}")
        with col2:
            json_text = st.text_area("Или вставьте JSON", height=150, key="json_paste")
            if json_text and st.button("Импортировать", key="import_btn"):
                success, message = cache_mgr.import_from_json(json_text)
                if success: st.success(f"✅ {message}")
                else: st.error(f"❌ {message}")
    with tabs[1]:
        st.markdown("### Экспортировать кеш")
        json_export = cache_mgr.export_to_json()
        st.download_button(label="⬇️ Скачать JSON", data=json_export, file_name=f"cache_{CACHE_VERSION}_{date.today().isoformat()}.json", mime="application/json", use_container_width=True)
        with st.expander("📋 Просмотреть JSON"): st.text_area("JSON", value=json_export, height=300, disabled=True, key="json_view")
    with tabs[2]:
        st.markdown("### Статистика кеша")
        stats = cache_mgr.get_cache_stats()
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.metric("📦 Версия", stats["version"])
            st.metric("🏢 Активов", stats["assets_count"])
            st.metric("📋 Сделок", stats["journal_rows"])
        with col_s2:
            st.metric("📊 Серий IV", stats["iv_series"])
            st.metric("✅ Чекбоксов", stats["alert_checks"])
        with col_s3:
            storage_type = "На диске" if "memory" not in stats["cache_path"] else "В памяти"
            st.metric("💾 Хранилище", storage_type)
            if st.button("🗑️ Очистить кеш", use_container_width=True):
                if cache_mgr.clear_cache(): st.success("✅ Кеш очищен"); st.rerun()

# ================= ОСНОВНОЙ ИНТЕРФЕЙС =================
st.markdown("---")
tabs_names = ["📊 Калькулятор", "📈 Доска", "💼 Позиции", "⚖️ What-if", "🔥 Heatmap", "📉 IV Rank", "🎯 Skew", "📓 Журнал", "🎲 Келли", "🔔 Оповещения"]
active_tab = st.radio("Навигация", tabs_names, horizontal=True, label_visibility="collapsed", key="main_nav")

if "📊 Калькулятор" in active_tab:
    st.header("📊 Калькулятор опционов (Black-Scholes)")
    with st.form("calc_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 🟢 Покупка")
            opt_type_buy = st.selectbox("Тип опциона", ["Call", "Put"], key="opt_buy_type")
            price_buy = st.number_input("Цена БА, ₽", min_value=0.01, value=100.0, step=1.0, key="price_buy", format="%.2f")
            strike_buy = st.number_input("Страйк, ₽", min_value=0.01, value=100.0, step=1.0, key="strike_buy", format="%.2f")
            vol_buy = st.number_input("Волатильность, %", min_value=0.1, max_value=500.0, value=30.0, step=0.5, key="vol_buy")
            rf_buy = st.number_input("Безрисковая ставка, %", min_value=-10.0, max_value=100.0, value=5.0, step=0.1, key="rf_buy")
            div_buy = st.number_input("Дивиденды, %", min_value=0.0, max_value=100.0, value=0.0, step=0.1, key="div_buy")
            current_date_buy = st.date_input("Текущая дата", value=date.today(), key="current_date_buy")
            expiry_buy = st.date_input("Экспирация", value=date.today() + timedelta(days=30), key="expiry_buy")
        with col2:
            st.markdown("### 🔴 Продажа")
            opt_type_sell = st.selectbox("Тип опциона", ["Call", "Put"], key="opt_sell_type")
            price_sell = st.number_input("Цена БА, ₽", min_value=0.01, value=100.0, step=1.0, key="price_sell", format="%.2f")
            strike_sell = st.number_input("Страйк, ₽", min_value=0.01, value=105.0, step=1.0, key="strike_sell", format="%.2f")
            vol_sell = st.number_input("Волатильность, %", min_value=0.1, max_value=500.0, value=30.0, step=0.5, key="vol_sell")
            rf_sell = st.number_input("Безрисковая ставка, %", min_value=-10.0, max_value=100.0, value=5.0, step=0.1, key="rf_sell")
            div_sell = st.number_input("Дивиденды, %", min_value=0.0, max_value=100.0, value=0.0, step=0.1, key="div_sell")
            current_date_sell = st.date_input("Текущая дата", value=date.today(), key="current_date_sell")
            expiry_sell = st.date_input("Экспирация", value=date.today() + timedelta(days=30), key="expiry_sell")
        
        submitted = st.form_submit_button("🔢 Рассчитать", use_container_width=True, type="primary")
    
    if submitted:
        from utils import black_scholes, calc_greeks
        if expiry_buy <= current_date_buy: st.error("❌ Дата экспирации должна быть позже текущей даты (покупка)"); st.stop()
        if expiry_sell <= current_date_sell: st.error("❌ Дата экспирации должна быть позже текущей даты (продажа)"); st.stop()
        
        T_buy = max((expiry_buy - current_date_buy).days, 1) / 365.0
        price_buy_calc = black_scholes(price_buy, strike_buy, T_buy, rf_buy, vol_buy, div_buy, opt_type_buy.lower())
        greeks_buy = calc_greeks(price_buy, strike_buy, T_buy, rf_buy, vol_buy, div_buy, opt_type_buy.lower())
        T_sell = max((expiry_sell - current_date_sell).days, 1) / 365.0
        price_sell_calc = black_scholes(price_sell, strike_sell, T_sell, rf_sell, vol_sell, div_sell, opt_type_sell.lower())
        greeks_sell = calc_greeks(price_sell, strike_sell, T_sell, rf_sell, vol_sell, div_sell, opt_type_sell.lower())
        spread = price_sell_calc - price_buy_calc
        
        st.markdown("---")
        res_col1, res_col2, res_col3 = st.columns(3)
        with res_col1:
            st.metric("💚 Покупка", fmt_price(price_buy_calc))
            st.caption(f"Δ {greeks_buy['delta']:+.3f} Γ {greeks_buy['gamma']:+.4f}")
        with res_col2:
            st.metric("❤️ Продажа", fmt_price(price_sell_calc))
            st.caption(f"Δ {greeks_sell['delta']:+.3f} Γ {greeks_sell['gamma']:+.4f}")
        with res_col3:
            st.metric("💰 Спред", fmt_price(spread))
            st.caption(f"Θ {greeks_buy['theta']:+.4f}")

elif "📈 Доска" in active_tab:
    st.header("📈 Доска опционов"); st.info("⚙️ Функционал в разработке")
elif "💼 Позиции" in active_tab:
    st.header("💼 Управление позициями"); st.info("⚙️ Функционал в разработке")
elif "⚖️ What-if" in active_tab:
    st.header("⚖️ Симулятор What-if"); st.info("⚙️ Функционал в разработке")
elif "🔥 Heatmap" in active_tab:
    st.header("🔥 Heatmap волатильности"); st.info("⚙️ Функционал в разработке")
elif "📉 IV Rank" in active_tab:
    st.header("📉 IV Rank / Децили"); st.info("⚙️ Функционал в разработке")
elif "🎯 Skew" in active_tab:
    st.header("🎯 Детектор Skew"); st.info("⚙️ Функционал в разработке")
elif "📓 Журнал" in active_tab:
    st.header("📓 Журнал сделок")
    with st.form("trade_form"):
        st.markdown("### Добавить сделку")
        col1, col2 = st.columns(2)
        with col1:
            trade_date = st.date_input("Дата", value=date.today())
            ticker = st.text_input("Тикер", value="SBER", max_chars=10)
            category = st.selectbox("Категория", ["Акция", "Фьючерс", "Опцион"])
        with col2:
            side = st.selectbox("Направление", ["Покупка", "Продажа"])
            qty = st.number_input("Кол-во", min_value=1, value=1)
            price = st.number_input("Цена", min_value=0.01, value=100.0, format="%.2f")
        if st.form_submit_button("➕ Добавить", use_container_width=True, type="primary"):
            trade = {"_id": f"trade_{datetime.now().strftime('%Y%m%d%H%M%S%f')}", "date": trade_date.isoformat(), "ticker": ticker.upper(), "category": category, "side": side, "qty": qty, "price": price}
            if cache_mgr.add_journal_row(trade): st.success(f"✅ {side} {ticker} × {qty} по {price}")
            else: st.error("❌ Лимит сделок")
    journal = st.session_state.get("_persistent_cache", {}).get("journal_rows", [])
    if journal:
        st.markdown("### Сделки")
        st.dataframe([{"Дата": r.get("date"), "Тикер": r.get("ticker"), "Категория": r.get("category"), "Сторона": r.get("side"), "Кол-во": r.get("qty"), "Цена": f"{r.get('price'):.2f} ₽"} for r in reversed(journal[-50:])], use_container_width=True)
    else: st.info("📝 Сделок нет")
elif "🎲 Келли" in active_tab:
    st.header("🎲 Калькулятор Келли"); st.info("⚙️ Функционал в разработке")
elif "🔔 Оповещения" in active_tab:
    st.header("🔔 Оповещения"); st.info("⚙️ Функционал в разработке")

# ================= FOOTER =================
st.markdown("---")
f1, f2, f3, f4 = st.columns(4)
f1.caption(f"📦 v{CACHE_VERSION}")
f2.caption("☁️ Cloud" if IS_CLOUD else "💻 Local")
f3.caption(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
f4.caption("[GitHub](https://github.com/yourusername/options_calc)")

# ================= AUTO-SAVE =================
if not IS_CLOUD: cache_mgr.flush_to_disk()
