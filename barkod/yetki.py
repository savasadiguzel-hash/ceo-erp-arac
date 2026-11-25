"""Barkod programı kullanıcı yetkileri.

Yetki dosyası config.json ile aynı klasörde (barkod_yetki.json) durur; şifreler
düz yazı değil tuzlu PBKDF2 özeti olarak saklanır. Dosya okunamazsa ya da
kullanıcı kayıtlı değilse EN KISITLI mod (yalnız VARSAYILAN sekmeler) uygulanır.

Bu bir arayüz kilididir; veritabanı düzeyinde güvenlik değildir.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

# sekme anahtarı → mod düğmesi indeksi (BarkodPencere.MODLAR sırası)
MOD_ANAHTAR = {0: 'sorgula', 1: 'sayim', 2: 'giris', 3: 'cikis', 4: 'transfer', 5: 'etiket', 6: 'recete'}
VARSAYILAN = frozenset({'sorgula', 'sayim', 'etiket'})
EK_YETKILER = [('giris', 'Giriş'), ('cikis', 'Çıkış'), ('transfer', 'Transfer'), ('recete', 'Reçeteye ekle')]
_ITER = 200_000
VARSAYILAN_YETKI_YOLU = r'\\WIN-3FATBI9RQAA\ceo'


def dosya_yolu() -> Path:
    """Yetki dosyası. config.json'da "barkod_yetki_yolu" (klasör ya da dosya yolu,
    örn. ağ paylaşımı) varsa orası; yoksa ortak CEO paylaşımı. (ERP Araçları'nın
    config.json'ı zaten kurulu PC'lerde bu anahtar olmayabilir.)"""
    from config import _cfg_oku
    ozel = str(_cfg_oku().get('barkod_yetki_yolu') or '').strip()
    if ozel:
        p = Path(ozel)
        return p if p.suffix.lower() == '.json' else p / 'barkod_yetki.json'
    return Path(VARSAYILAN_YETKI_YOLU) / 'barkod_yetki.json'


def sifre_ozeti(sifre: str) -> str:
    tuz = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', sifre.encode('utf-8'), bytes.fromhex(tuz), _ITER).hex()
    return f'pbkdf2${_ITER}${tuz}${h}'


def sifre_dogru(sifre: str, ozet: str) -> bool:
    try:
        _, it, tuz, h = ozet.split('$')
        calc = hashlib.pbkdf2_hmac('sha256', sifre.encode('utf-8'), bytes.fromhex(tuz), int(it)).hex()
        return hmac.compare_digest(calc, h)
    except Exception:
        return False


def oku() -> tuple[dict, str]:
    """(veri, hata). Hata doluysa veri boş: herkes en kısıtlı modda kalır."""
    p = dosya_yolu()
    try:
        with open(p, encoding='utf-8') as f:
            veri = json.load(f)
        if not isinstance(veri.get('kullanicilar'), dict):
            raise ValueError('kullanicilar bölümü yok')
        return veri, ''
    except FileNotFoundError:
        return {'kullanicilar': {}}, f'Yetki dosyası bulunamadı ({p.name}) — kısıtlı mod'
    except Exception as e:
        return {'kullanicilar': {}}, f'Yetki dosyası okunamadı ({type(e).__name__}) — kısıtlı mod'


def yaz(veri: dict) -> None:
    p = dosya_yolu()
    tmp = str(p) + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(veri, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def kayit(veri: dict, guid: str | None) -> dict | None:
    if not guid:
        return None
    return (veri.get('kullanicilar') or {}).get(str(guid).strip().upper()) or \
           (veri.get('kullanicilar') or {}).get(str(guid).strip())


def yukseltilmis_mi(k: dict | None) -> bool:
    """Varsayılandan fazla yetkisi (ya da yöneticiliği) olan kayıt mı?"""
    return bool(k and (k.get('yonetici') or k.get('yetki')))


def sifre_gerekli(k: dict | None) -> bool:
    return yukseltilmis_mi(k)


def yetkiler(k: dict | None, dogrulandi: bool) -> set[str]:
    """Doğrulanmış kullanıcının yetki kümesi; aksi halde en kısıtlı."""
    y = set(VARSAYILAN)
    if k and dogrulandi:
        if k.get('yonetici'):
            y.update(a for a, _ in EK_YETKILER)
        else:
            y.update(a for a in (k.get('yetki') or []) if a in dict(EK_YETKILER))
    return y


def yonetici_mi(k: dict | None, dogrulandi: bool) -> bool:
    return bool(k and dogrulandi and k.get('yonetici'))
