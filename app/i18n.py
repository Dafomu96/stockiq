"""
Internationalisation (i18n) helper for the Streamlit app.

Usage:
    from app.i18n import t

    st.title(t("app_name"))
    st.button(t("analyze_btn"))

The active language is stored in st.session_state["lang"] and defaults
to "en". Switch it with set_language("es") or the sidebar toggle.

Translation files live in i18n/{lang}.json. Keys missing in the active
language fall back to English, then to the key itself — the UI never
shows a raw exception for a missing translation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import streamlit as st

logger = logging.getLogger(__name__)

_I18N_DIR = Path(__file__).parent.parent / "i18n"
_SUPPORTED_LANGS: tuple[str, ...] = ("en", "es")
_DEFAULT_LANG = "en"

# Cache loaded translation dicts — loaded once per process
_translations: dict[str, dict[str, str]] = {}


def _load(lang: str) -> dict[str, str]:
    """Load translation dict for lang, with caching."""
    if lang not in _translations:
        path = _I18N_DIR / f"{lang}.json"
        try:
            _translations[lang] = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.warning("i18n_load_failed lang=%s error=%s", lang, exc)
            _translations[lang] = {}
    return _translations[lang]


def t(key: str) -> str:
    """Return the translated string for key in the active language.

    Falls back to English, then to the key itself. Never raises.

    Args:
        key: Translation key (must exist in i18n/en.json).

    Returns:
        Translated string, or English fallback, or the key itself.
    """
    lang = st.session_state.get("lang", _DEFAULT_LANG)
    texts = _load(lang)
    if key in texts:
        return texts[key]
    # Fallback to English
    en = _load("en")
    if key in en:
        logger.debug("i18n_fallback key=%s lang=%s", key, lang)
        return en[key]
    # Last resort — return key so the UI is never broken
    logger.warning("i18n_missing_key key=%s", key)
    return key


def set_language(lang: str) -> None:
    """Set the active language in session state.

    Args:
        lang: Language code. Must be in _SUPPORTED_LANGS.
    """
    if lang not in _SUPPORTED_LANGS:
        logger.warning("i18n_unsupported_lang lang=%s", lang)
        return
    st.session_state["lang"] = lang


def current_lang() -> str:
    """Return the currently active language code."""
    return st.session_state.get("lang", _DEFAULT_LANG)


def supported_languages() -> tuple[str, ...]:
    """Return the tuple of supported language codes."""
    return _SUPPORTED_LANGS
