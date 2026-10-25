"""
Менеджер кеша с поддержкой сохранения состояния между сессиями
"""
import json
import hashlib
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional, List
import streamlit as st

from config import (
    IS_CLOUD, CACHE_VERSION, MAX_IV_HISTORY_PER_SERIES,
    MAX_IV_HISTORY_SERIES, MAX_JOURNAL_ROWS, MAX_ALERT_CHECKS
)

logger = logging.getLogger(__name__)

class CacheManager:
    """Управление кешем приложения с сохранением между сессиями"""
    
    CACHE_FILENAME = f"options_calc_cache_{CACHE_VERSION}.json"
    
    def __init__(self):
        self.cache_path = self._get_cache_path()
        self._initialize_session_state()
        self._load_persistent_cache()
    
    def _get_cache_path(self) -> Optional[Path]:
        """Определяет путь для сохранения кеша"""
        if IS_CLOUD:
            # На Cloud используем только session_state
            return None
        
        candidates = [
            Path.home() / ".options_calc" / self.CACHE_FILENAME,
            Path("/tmp") / self.CACHE_FILENAME,
            Path.cwd() / self.CACHE_FILENAME,
        ]
        
        for path in candidates:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                # Проверяем возможность записи
                test_file = path.parent / ".write_test"
                test_file.write_text("ok", encoding="utf-8")
                test_file.unlink()
                logger.info(f"Cache path selected: {path}")
                return path
            except Exception as e:
                logger.debug(f"Cache path {path} unavailable: {e}")
                continue
        
        logger.warning("No suitable cache path found - using memory only")
        return None
    
    def _initialize_session_state(self):
        """Инициализирует session_state если требуется"""
        if "cache_manager_initialized" in st.session_state:
            return
        
        # Основной кеш
        if "_persistent_cache" not in st.session_state:
            st.session_state["_persistent_cache"] = {
                "version": CACHE_VERSION,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "positions_by_asset": {},      # {asset|category: [{...}, ...]}
                "journal_rows": [],             # Таблица сделок
                "iv_history": {},               # {asset|atype|series: [(date, iv), ...]}
                "alert_checks": {},             # {ticker|category: {buy: ..., sell: ...}}
                "settings": {},                 # Пользовательские настройки
            }
        
        st.session_state["cache_manager_initialized"] = True
    
    def _load_persistent_cache(self):
        """Загружает кеш из файла (если существует)"""
        if self.cache_path is None or not self.cache_path.exists():
            return
        
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                file_cache = json.load(f)
            
            # Валидация версии
            if file_cache.get("version") != CACHE_VERSION:
                logger.info(f"Cache version mismatch: {file_cache.get('version')} vs {CACHE_VERSION}")
                # Миграция или создание нового кеша
                return
            
            # Дополняем session_state загруженными данными
            persistent = st.session_state["_persistent_cache"]
            
            # Объединяем positions_by_asset
            persistent["positions_by_asset"].update(file_cache.get("positions_by_asset", {}))
            
            # Объединяем journal_rows (избегаем дубликатов)
            existing_ids = {r.get("_id") for r in persistent["journal_rows"]}
            for row in file_cache.get("journal_rows", []):
                if row.get("_id") not in existing_ids:
                    persistent["journal_rows"].append(row)
            
            # Объединяем IV history
            for key, history in file_cache.get("iv_history", {}).items():
                if key not in persistent["iv_history"]:
                    persistent["iv_history"][key] = []
                
                # Добавляем новые записи
                existing_dates = {d for d, _ in persistent["iv_history"][key]}
                for date_str, iv_value in history:
                    if date_str not in existing_dates:
                        persistent["iv_history"][key].append((date_str, iv_value))
                
                # Ограничиваем размер
                self._trim_iv_history(key)
            
            # Объединяем alert_checks (перезаписываем)
            persistent["alert_checks"].update(file_cache.get("alert_checks", {}))
            
            # Объединяем settings (перезаписываем)
            persistent["settings"].update(file_cache.get("settings", {}))
            
            logger.info(f"Cache loaded from {self.cache_path}")
            st.session_state["cache_load_success"] = True
            
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            st.session_state["cache_load_error"] = str(e)
    
    def _trim_iv_history(self, key: str):
        """Ограничивает размер истории IV"""
        persistent = st.session_state.get("_persistent_cache", {})
        history = persistent.get("iv_history", {}).get(key, [])
        
        if len(history) > MAX_IV_HISTORY_PER_SERIES:
            # Сортируем по дате и оставляем самые новые
            history.sort(key=lambda x: x[0])
            history = history[-MAX_IV_HISTORY_PER_SERIES:]
            persistent["iv_history"][key] = history
    
    def save_position(self, asset: str, category: str, position: Dict[str, Any]):
        """Сохраняет позицию в кеш"""
        key = f"{asset}|{category}"
        persistent = st.session_state.get("_persistent_cache", {})
        
        if key not in persistent["positions_by_asset"]:
            persistent["positions_by_asset"][key] = []
        
        # Обновляем или добавляем позицию
        pos_id = position.get("_id")
        existing_idx = next(
            (i for i, p in enumerate(persistent["positions_by_asset"][key])
             if p.get("_id") == pos_id),
            -1
        )
        
        if existing_idx >= 0:
            persistent["positions_by_asset"][key][existing_idx] = position
        else:
            persistent["positions_by_asset"][key].append(position)
    
    def get_positions(self, asset: str, category: str) -> List[Dict[str, Any]]:
        """Получает позиции для актива"""
        key = f"{asset}|{category}"
        persistent = st.session_state.get("_persistent_cache", {})
        return persistent.get("positions_by_asset", {}).get(key, [])
    
    def add_journal_row(self, row: Dict[str, Any]):
        """Добавляет запись в журнал"""
        persistent = st.session_state.get("_persistent_cache", {})
        
        if len(persistent["journal_rows"]) >= MAX_JOURNAL_ROWS:
            logger.warning(f"Journal limit reached ({MAX_JOURNAL_ROWS})")
            return False
        
        persistent["journal_rows"].append(row)
        return True
    
    def store_iv_snapshot(self, asset: str, atype: str, series: str, iv_value: float):
        """Сохраняет снимок IV"""
        if iv_value is None or iv_value <= 0:
            return
        
        key = f"{asset}|{atype}|{series}"
        today_str = date.today().isoformat()
        persistent = st.session_state.get("_persistent_cache", {})
        iv_hist = persistent.get("iv_history", {})
        
        if len(iv_hist) >= MAX_IV_HISTORY_SERIES:
            logger.warning(f"IV history limit reached ({MAX_IV_HISTORY_SERIES})")
            return
        
        if key not in iv_hist:
            iv_hist[key] = []
        
        # Избегаем дубликатов в один день
        if any(d == today_str for d, _ in iv_hist[key]):
            return
        
        iv_hist[key].append((today_str, float(iv_value)))
        
        # Ограничиваем размер
        self._trim_iv_history(key)
    
    def save_alert_checks(self, checks: Dict[str, Any]):
        """Сохраняет состояние чекбоксов оповещений"""
        persistent = st.session_state.get("_persistent_cache", {})
        
        # Ограничиваем размер
        if len(checks) > MAX_ALERT_CHECKS:
            logger.warning(f"Alert checks limit reached ({MAX_ALERT_CHECKS})")
            return
        
        persistent["alert_checks"] = checks
    
    def get_alert_checks(self) -> Dict[str, Any]:
        """Получает сохранённые чекбоксы"""
        persistent = st.session_state.get("_persistent_cache", {})
        return persistent.get("alert_checks", {})
    
    def save_setting(self, key: str, value: Any):
        """Сохраняет пользовательскую настройку"""
        persistent = st.session_state.get("_persistent_cache", {})
        persistent["settings"][key] = value
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Получает пользовательскую настройку"""
        persistent = st.session_state.get("_persistent_cache", {})
        return persistent.get("settings", {}).get(key, default)
    
    def export_to_json(self) -> str:
        """Экспортирует весь кеш в JSON"""
        persistent = st.session_state.get("_persistent_cache", {})
        
        # Чистим данные перед экспортом
        export_data = {
            "version": persistent.get("version"),
            "created_at": persistent.get("created_at"),
            "updated_at": datetime.now().isoformat(),
            "exported_at": datetime.now().isoformat(),
            "positions_by_asset": persistent.get("positions_by_asset", {}),
            "journal_rows": persistent.get("journal_rows", []),
            "iv_history": persistent.get("iv_history", {}),
            "alert_checks": persistent.get("alert_checks", {}),
            "settings": persistent.get("settings", {}),
        }
        
        return json.dumps(export_data, ensure_ascii=False, indent=2, default=str)
    
    def import_from_json(self, json_str: str) -> tuple[bool, str]:
        """Импортирует кеш из JSON"""
        try:
            import_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"
        
        # Валидация версии
        if import_data.get("version") != CACHE_VERSION:
            return False, f"Cache version mismatch: {import_data.get('version')} vs {CACHE_VERSION}"
        
        persistent = st.session_state.get("_persistent_cache", {})
        
        try:
            # Объединяем данные
            persistent["positions_by_asset"].update(import_data.get("positions_by_asset", {}))
            
            existing_ids = {r.get("_id") for r in persistent["journal_rows"]}
            for row in import_data.get("journal_rows", []):
                if row.get("_id") not in existing_ids:
                    persistent["journal_rows"].append(row)
            
            for key, history in import_data.get("iv_history", {}).items():
                if key not in persistent["iv_history"]:
                    persistent["iv_history"][key] = []
                
                existing_dates = {d for d, _ in persistent["iv_history"][key]}
                for date_str, iv_value in history:
                    if date_str not in existing_dates:
                        persistent["iv_history"][key].append((date_str, iv_value))
                
                self._trim_iv_history(key)
            
            persistent["alert_checks"].update(import_data.get("alert_checks", {}))
            persistent["settings"].update(import_data.get("settings", {}))
            
            return True, f"Successfully imported {len(import_data.get('positions_by_asset', {}))} assets"
            
        except Exception as e:
            return False, f"Import error: {e}"
    
    def flush_to_disk(self) -> bool:
        """Сохраняет кеш на диск"""
        if self.cache_path is None:
            logger.info("Cache flushing skipped (cloud environment)")
            return True
        
        try:
            persistent = st.session_state.get("_persistent_cache", {})
            persistent["updated_at"] = datetime.now().isoformat()
            
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(persistent, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"Cache saved to {self.cache_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
            return False
    
    def clear_cache(self) -> bool:
        """Очищает весь кеш"""
        try:
            st.session_state["_persistent_cache"] = {
                "version": CACHE_VERSION,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "positions_by_asset": {},
                "journal_rows": [],
                "iv_history": {},
                "alert_checks": {},
                "settings": {},
            }
            
            if self.cache_path and self.cache_path.exists():
                self.cache_path.unlink()
                logger.info("Cache cleared and file deleted")
            
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Возвращает статистику кеша"""
        persistent = st.session_state.get("_persistent_cache", {})
        
        return {
            "version": persistent.get("version"),
            "created_at": persistent.get("created_at"),
            "updated_at": persistent.get("updated_at"),
            "assets_count": len(persistent.get("positions_by_asset", {})),
            "journal_rows": len(persistent.get("journal_rows", [])),
            "iv_series": len(persistent.get("iv_history", {})),
            "alert_checks": len(persistent.get("alert_checks", {})),
            "cache_path": str(self.cache_path) if self.cache_path else "memory only",
        }


# Глобальный экземпляр менеджера
_cache_manager = None

def get_cache_manager() -> CacheManager:
    """Получает или создаёт глобальный менеджер кеша"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
