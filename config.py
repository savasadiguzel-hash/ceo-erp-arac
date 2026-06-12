"""
Uygulama konfigürasyonu — config.json'dan okunur, yoksa şablon oluşturulur.
Şifre base64 ile gizlenir (şifreleme değil, düz metin saklamayı engeller).
"""
import json
import base64
import logging
import sys
from pathlib import Path

# PyInstaller ile paketlendiğinde exe'nin yanı sıra çalışması için
if getattr(sys, "frozen", False):
    _BASE = Path(sys.executable).parent
else:
    _BASE = Path(__file__).parent

CONFIG_PATH = _BASE / "config.json"

_SABLON: dict = {
    "sunucu":     "localhost\\SQLEXPRESS",
    "veritabani": "CEO_ERP",
    "kullanici":  "sa",
    "sifre_enc":  "",
}


def _cfg_oku() -> dict:
    if not CONFIG_PATH.exists():
        _cfg_yaz(_SABLON)
        logging.info("config.json bulunamadi; varsayilan sablon olusturuldu: %s", CONFIG_PATH)
        return _SABLON.copy()
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return {**_SABLON, **json.load(f)}
    except Exception as e:
        logging.error("config.json okunamadi, varsayilanlar kullaniliyor: %s", e)
        return _SABLON.copy()


def _cfg_yaz(data: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error("config.json yazilamadi: %s", e)


def _decode(enc: str) -> str:
    try:
        return base64.b64decode(enc.encode()).decode() if enc else ""
    except Exception:
        return ""


def config_kaydet(sunucu: str, veritabani: str, kullanici: str, sifre: str) -> None:
    """Bağlantı bilgilerini config.json'a yazar; şifre base64 ile gizlenir."""
    data = _cfg_oku()
    data.update({
        "sunucu":     sunucu,
        "veritabani": veritabani,
        "kullanici":  kullanici,
        "sifre_enc":  base64.b64encode(sifre.encode()).decode(),
    })
    _cfg_yaz(data)
    logging.info("Baglanti bilgileri config.json'a kaydedildi.")


def gemini_api_key_kaydet(key: str) -> None:
    """Gemini API anahtarını config.json'a yazar; base64 ile gizlenir."""
    data = _cfg_oku()
    data["gemini_api_key_enc"] = base64.b64encode(key.strip().encode()).decode() if key.strip() else ""
    _cfg_yaz(data)
    logging.info("Gemini API anahtari config.json'a kaydedildi.")


def gemini_api_key_oku() -> str:
    """Gemini API anahtarını config.json'dan okur; yoksa GEMINI_API_KEY env var'ına bakar."""
    import os
    data = _cfg_oku()
    enc = data.get("gemini_api_key_enc", "")
    if enc:
        return _decode(enc)
    return os.environ.get("GEMINI_API_KEY", "")


_cfg = _cfg_oku()

DB_DEFAULTS: dict = {
    "sunucu":     _cfg.get("sunucu", ""),
    "veritabani": _cfg.get("veritabani", ""),
    "kullanici":  _cfg.get("kullanici", ""),
    "sifre":      _decode(_cfg.get("sifre_enc", "")),
}
