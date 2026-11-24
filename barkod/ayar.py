"""Barkod programının yerel ayarları ve fiş günlüğü (config klasöründe)."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


def _dizin() -> Path:
    from config import CONFIG_PATH
    return Path(CONFIG_PATH).parent


def ayar_oku() -> dict:
    p = _dizin() / 'barkod_ayar.json'
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def ayar_yaz(**degerler) -> None:
    d = ayar_oku(); d.update(degerler)
    p = _dizin() / 'barkod_ayar.json'
    tmp = str(p) + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def kullanicilar(conn) -> list[tuple[str, str]]:
    """[(UserId GUID, 'UserKod')] — CEO'daki aktif kullanıcılar."""
    from db.baglanti import cursor_ctx
    with cursor_ctx(conn) as cur:
        cur.execute("SELECT CAST(UserId AS nvarchar(40)), UserKod FROM CeoCommon.dbo.Kullanici "
                    "WHERE Active = 1 ORDER BY UserKod")
        return [(r[0], (r[1] or '').strip()) for r in cur.fetchall()]


def fis_gunluge_yaz(kayit: dict) -> None:
    """Kaydedilen her fişin yerel denetim kaydı (satır satır JSON)."""
    p = _dizin() / 'barkod_fis_gunlugu.jsonl'
    kayit = {'zaman': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), **kayit}
    with open(p, 'a', encoding='utf-8') as f:
        f.write(json.dumps(kayit, ensure_ascii=False, default=str) + '\n')
