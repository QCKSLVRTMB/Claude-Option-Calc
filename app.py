"""
Калькулятор опционов MOEX с поддержкой кеша между сессиями
"""
import streamlit as st
import logging
import os
import requests
from datetime import datetime, date, timedelta
from pathlib import Path

from config import IS_CLOUD, CACHE_VERSION
from cache_manager import get_cache_manager
from utils import setup_logging, fmt_price, fmt_date

# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)

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
    
    # Показываем статус загрузки кеша
    if st.session_state.get("cache_load_success"):
        logger.info("Cache successfully loaded from disk")
    elif st.session_state.get("cache_load_error"):
        logger.warning(f"Cache load error: {st.session_state['cache_load_error']}")

cache_mgr = st.session_state["cache_manager"]

# ================= СТИЛИ =================
st.markdown("""
<style>
* {
    box-sizing: border-box;
}

html, body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background-color: #f5f7fa;
    color: #1a3b4f;
}

.block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
    padding-left: 1rem;
    padding-right: 1rem;
}

/* ========== ФОРМЫ ========== */
[data-testid="stForm"] {
    border: 1px solid #e2edf4 !important;
    border-radius: 12px !important;
    padding: 16px !important;
    background: white !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
}

/* ========== КНОПКИ ========== */
button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}

button[kind="primary"] {
    background-color: #1e88e5 !important;
}

button[kind="secondary"] {
    background-color: #eef2f7 !important;
    color: #1a3b4f !important;
    border: 1px solid #cfdfe9 !important;
}

/* ========== ТАБЛИЦЫ ========== */
[data-testid="stDataFrame"] {
    border: 1px solid #e2edf4 !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}

/* ========== ВКЛАДКИ ========== */
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] {
    position: sticky !important;
    top: 0 !important;
    z-index: 999 !important;
    background-color: #ffffff !important;
    border-bottom: 1px solid #e2edf4 !important;
    padding-top: 8px !important;
    padding-bottom: 6px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

div[data-testid="stTabs"] > div[data-baseweb="tab-list"] button {
    background-color: transparent !important;
    font-weight: 600 !important;
}

/* ========== МОБИЛЬНЫЕ ========== */
@media (max-width: 768px) {
    .block-container {
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }
    
    [data-testid="stForm"] {
        padding: 10px 12px !important;
    }
    
    button {
        font-size: 0.9rem !important;
        padding: 8px 12px !important;
    }
}

</style>
""", unsafe_allow_html=True)

# ================= HEADER =================
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.markdown("# 📊 Калькулятор опционов MOEX")
    st.markdown("Black-Scholes • Волатильность • Журнал сделок")

with col2:
    if st.button("💾 Сохранить кеш", use_container_width=True):
        if cache_mgr.flush_to_disk():
            st.success("✅ Кеш сохранён на диск")
        else:
            st.error("❌ Ошибка при сохранении")

with col3:
    if st.button("🔄 Загрузить кеш", use_container_width=True):
        st.session_state["show_import_dialog"] = True

# ================= IMPORT/EXPORT DIALOG =================
if st.session_state.get("show_import_dialog"):
    st.markdown("---")
    
    import_tab, export_tab, stats_tab = st.tabs(["📥 Импорт", "📤 Экспорт", "📈 Статистика"])
    
    with import_tab:
        st.markdown("### Загрузить кеш из JSON файла")
        uploaded_file = st.file_uploader(
            "Выберите JSON файл",
            type=["json"],
            key="cache_file_uploader",
            help="Выберите ранее экспортированный файл кеша"
        )
        
        if uploaded_file is not None:
            json_str = uploaded_file.read().decode("utf-8")
            success, message = cache_mgr.import_from_json(json_str)
            
            if success:
                st.success(f"✅ {message}")
                st.balloons()
            else:
                st.error(f"❌ {message}")
        
        # Текстовая область для вставки JSON
        st.markdown("**Или вставьте JSON напрямую:**")
        json_text = st.text_area(
            "JSON кеш",
            height=200,
            key="json_paste_area",
            help="Вставьте содержимое экспортированного JSON"
        )
        
        if json_text and st.button("Импортировать из текста", key="import_json_btn"):
            success, message = cache_mgr.import_from_json(json_text)
            if success:
                st.success(f"✅ {message}")
            else:
                st.error(f"❌ {message}")
    
    with export_tab:
        st.markdown("### Экспортировать кеш в JSON")
        
        json_export = cache_mgr.export_to_json()
        
        st.download_button(
            label="⬇️ Скачать JSON",
            data=json_export,
            file_name=f"options_calc_cache_{CACHE_VERSION}_{date.today().isoformat()}.json",
            mime="application/json",
            use_container_width=True,
        )
        
        st.markdown("**Или скопируйте:**")
        st.text_area(
            "JSON кеш",
            value=json_export,
            height=200,
            disabled=True,
            key="json_copy_area"
        )
    
    with stats_tab:
        st.markdown("### Статистика кеша")
        
        stats = cache_mgr.get_cache_stats()
        
        # Отображаем статистику в 2 колонки
        sc1, sc2 = st.columns(2)
        
        with sc1:
            st.metric("📦 Версия", stats["version"])
            st.metric("🏢 Активов", stats["assets_count"])
            st.metric("📋 Сделок", stats["journal_rows"])
        
        with sc2:
            st.metric("📊 Серий IV", stats["iv_series"])
            st.metric("✅ Чекбоксов", stats["alert_checks"])
            st.metric("💾 Хранилище", "На диске" if "memory" not in stats["cache_path"] else "В памяти")
        
        st.markdown("**Информация кеша:**")
        col_info1, col_info2, col_info3 = st.columns(3)
        
        with col_info1:
            st.caption(f"Создан: {fmt_datetime_short(stats['created_at'])}")
        with col_info2:
            st.caption(f"Обновлён: {fmt_datetime_short(stats['updated_at'])}")
        with col_info3:
            if st.button("🗑️ Очистить кеш", use_container_width=True, help="ВНИМАНИЕ: Все данные будут удалены!"):
                if cache_mgr.clear_cache():
                    st.success("✅ Кеш очищен")
                    st.rerun()

def fmt_datetime_short(dt_str):
    """Форматирует дату/время из ISO строки"""
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return dt_str

# ================= ОСНОВНОЙ ИНТЕРФЕЙС =================
st.markdown("---")

# TAB NAVIGATION
tab_names = [
    "📊 Калькулятор",
    "📈 Доска опционов",
    "💼 Позиции",
    "⚖️ What-if",
    "🔥 Heatmap IV",
    "📉 IV Rank",
    "🎯 Skew",
    "📓 Журнал",
    "🎲 Келли",
    "🔔 Оповещения",
]

active_tab = st.radio(
    "Раздел",
    tab_names,
    horizontal=True,
    label_visibility="collapsed",
    key="main_tab"
)

# ================= TAB 1: КАЛЬКУЛЯТОР =================
if active_tab == "📊 Калькулятор":
    st.header("📊 Калькулятор опционов (Black-Scholes)")
    
    with st.form("calculator_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🟢 Уровень покупок")
            
            opt_type_buy = st.selectbox(
                "Тип опциона",
                ["Call", "Put"],
                key="opt_type_buy_calc"
            )
            
            price_buy = st.number_input(
                "Цена БА",
                min_value=0.01,
                value=100.0,
                step=1.0,
                key="price_buy_calc",
                format="%.2f"
            )
            
            strike_buy = st.number_input(
                "Страйк",
                min_value=0.01,
                value=100.0,
                step=1.0,
                key="strike_buy_calc",
                format="%.2f"
            )
            
            expiry_buy = st.date_input(
                "Экспирация",
                value=date.today() + timedelta(days=30),
                key="expiry_buy_calc"
            )
            
            current_date_buy = st.date_input(
                "Текущая дата",
                value=date.today(),
                key="current_date_buy_calc"
            )
            
            vol_buy = st.number_input(
                "Волатильность %",
                min_value=0.1,
                max_value=500.0,
                value=30.0,
                step=0.5,
                key="vol_buy_calc"
            )
            
            rf_buy = st.number_input(
                "Безрисковая ставка %",
                min_value=-10.0,
                max_value=100.0,
                value=5.0,
                step=0.1,
                key="rf_buy_calc"
            )
            
            div_buy = st.number_input(
                "Дивиденды %",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.1,
                key="div_buy_calc"
            )
        
        with col2:
            st.markdown("### 🔴 Уровень продаж")
            
            opt_type_sell = st.selectbox(
                "Тип опциона",
                ["Call", "Put"],
                key="opt_type_sell_calc"
            )
            
            price_sell = st.number_input(
                "Цена БА",
                min_value=0.01,
                value=100.0,
                step=1.0,
                key="price_sell_calc",
                format="%.2f"
            )
            
            strike_sell = st.number_input(
                "Страйк",
                min_value=0.01,
                value=105.0,
                step=1.0,
                key="strike_sell_calc",
                format="%.2f"
            )
            
            expiry_sell = st.date_input(
                "Экспирация",
                value=date.today() + timedelta(days=30),
                key="expiry_sell_calc"
            )
            
            current_date_sell = st.date_input(
                "Текущая дата",
                value=date.today(),
                key="current_date_sell_calc"
            )
            
            vol_sell = st.number_input(
                "Волатильность %",
                min_value=0.1,
                max_value=500.0,
                value=30.0,
                step=0.5,
                key="vol_sell_calc"
            )
            
            rf_sell = st.number_input(
                "Безрисковая ставка %",
                min_value=-10.0,
                max_value=100.0,
                value=5.0,
                step=0.1,
                key="rf_sell_calc"
            )
            
            div_sell = st.number_input(
                "Дивиденды %",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.1,
                key="div_sell_calc"
            )
        
        submitted = st.form_submit_button(
            "🔢 Рассчитать",
            use_container_width=True,
            type="primary"
        )
    
    if submitted:
        from utils import black_scholes, calc_greeks
        
        # Расчёт для покупки
        T_buy = max((expiry_buy - current_date_buy).days, 0) / 365.0
        price_buy_calc = black_scholes(price_buy, strike_buy, T_buy, rf_buy, vol_buy, div_buy, opt_type_buy.lower())
        greeks_buy = calc_greeks(price_buy, strike_buy, T_buy, rf_buy, vol_buy, div_buy, opt_type_buy.lower())
        
        # Расчёт для продажи
        T_sell = max((expiry_sell - current_date_sell).days, 0) / 365.0
        price_sell_calc = black_scholes(price_sell, strike_sell, T_sell, rf_sell, vol_sell, div_sell, opt_type_sell.lower())
        greeks_sell = calc_greeks(price_sell, strike_sell, T_sell, rf_sell, vol_sell, div_sell, opt_type_sell.lower())
        
        # Спред
        spread = price_sell_calc - price_buy_calc
        
        # Результаты
        res_col1, res_col2, res_col3 = st.columns(3)
        
        with res_col1:
            st.metric("💚 Покупка", fmt_price(price_buy_calc))
            st.markdown(f"**Греки:** Δ {greeks_buy['delta']:.3f} Γ {greeks_buy['gamma']:.3f}")
        
        with res_col2:
            st.metric("❤️ Продажа", fmt_price(price_sell_calc))
            st.markdown(f"**Греки:** Δ {greeks_sell['delta']:.3f} Γ {greeks_sell['gamma']:.3f}")
        
        with res_col3:
            spread_color = "green" if spread > 0 else "red"
            st.metric("💰 Спред", fmt_price(spread))

# ================= TAB 2: ДОСКА ОПЦИОНОВ =================
elif active_tab == "📈 Доска опционов":
    st.header("📈 Доска опционов")
    st.info("Функционал загрузки доски опционов (в разработке)")

# ================= TAB 3: ПОЗИЦИИ =================
elif active_tab == "💼 Позиции":
    st.header("💼 Управление позициями")
    st.info("Функционал управления позициями (в разработке)")

# ================= TAB 4: WHAT-IF =================
elif active_tab == "⚖️ What-if":
    st.header("⚖️ Симулятор What-if")
    st.info("Функционал симуляции What-if (в разработке)")

# ================= TAB 5: HEATMAP =================
elif active_tab == "🔥 Heatmap IV":
    st.header("🔥 Heatmap волатильности")
    st.info("Функционал Heatmap (в разработке)")

# ================= TAB 6: IV RANK =================
elif active_tab == "📉 IV Rank":
    st.header("📉 IV Rank / Децили")
    st.info("Функционал IV Rank (в разработке)")

# ================= TAB 7: SKEW =================
elif active_tab == "🎯 Skew":
    st.header("🎯 Детектор Skew")
    st.info("Функционал Skew (в разработке)")

# ================= TAB 8: ЖУРНАЛ =================
elif active_tab == "📓 Журнал":
    st.header("📓 Журнал сделок")
    
    # Добавление сделки
    with st.form("add_trade_form"):
        st.markdown("### Добавить сделку")
        
        col1, col2 = st.columns(2)
        
        with col1:
            trade_date = st.date_input("Дата сделки", value=date.today())
            ticker = st.text_input("Тикер", value="SBER", max_chars=10)
            category = st.selectbox("Категория", ["Акция", "Фьючерс", "Опцион"])
        
        with col2:
            side = st.selectbox("Направление", ["Покупка", "Продажа"])
            qty = st.number_input("Кол-во", min_value=1, value=1)
            price = st.number_input("Цена входа", min_value=0.01, value=100.0, format="%.2f")
        
        submitted = st.form_submit_button("➕ Добавить", use_container_width=True, type="primary")
        
        if submitted:
            trade_id = f"trade_{date.today().isoformat()}_{datetime.now().strftime('%H%M%S')}"
            trade = {
                "_id": trade_id,
                "date": trade_date.isoformat(),
                "ticker": ticker.upper(),
                "category": category,
                "side": side,
                "qty": qty,
                "price": price,
            }
            
            if cache_mgr.add_journal_row(trade):
                st.success(f"✅ Добавлена сделка: {side} {ticker} × {qty} по {price}")
            else:
                st.error("❌ Не удалось добавить сделку")
    
    # Отображение сделок
    journal_rows = st.session_state.get("_persistent_cache", {}).get("journal_rows", [])
    
    if journal_rows:
        st.markdown("### Открытые сделки")
        
        df_display = []
        for row in journal_rows:
            df_display.append({
                "Дата": row.get("date"),
                "Тикер": row.get("ticker"),
                "Категория": row.get("category"),
                "Направление": row.get("side"),
                "Кол-во": row.get("qty"),
                "Цена": row.get("price"),
            })
        
        if df_display:
            st.dataframe(df_display, use_container_width=True)
    else:
        st.info("📝 Сделок нет. Добавьте первую сделку выше.")

# ================= TAB 9: КЕЛЛИ =================
elif active_tab == "🎲 Келли":
    st.header("🎲 Калькулятор Келли")
    st.info("Функционал Келли (в разработке)")

# ================= TAB 10: ОПОВЕЩЕНИЯ =================
elif active_tab == "🔔 Оповещения":
    st.header("🔔 Оповещения по уровням")
    st.info("Функционал оповещений (в разработке)")

# ================= FOOTER =================
st.markdown("---")

footer_col1, footer_col2, footer_col3 = st.columns([1, 1, 1])

with footer_col1:
    st.caption(f"🔗 Версия: {CACHE_VERSION}")

with footer_col2:
    env_label = "☁️ Cloud" if IS_CLOUD else "💻 Local"
    st.caption(f"{env_label}")

with footer_col3:
    st.caption(f"⏰ {datetime.now().strftime('%H:%M:%S')}")

# ================= АВТО-СОХРАНЕНИЕ =================
# Сохраняем кеш при каждом обновлении (если не на Cloud)
if not IS_CLOUD:
    cache_mgr.flush_to_disk()
