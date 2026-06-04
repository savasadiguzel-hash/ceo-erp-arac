#!/usr/bin/env python3
"""UretimReceteHatPlaniGirdi - gercek alt bilesenleri goster"""

from config import DB_DEFAULTS
from db.baglanti import get_connection, cursor_ctx

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])

# GMP-101-230016'nin gercek girdi bilesenleri
print("=== GMP-101-230016 gercek girdileri (UretimReceteHatPlaniGirdi) ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT urhpg.Miktar, sk.Kodu, sk.Adi
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        JOIN UretimReceteHatPlaniGirdi urhpg ON urhpg.UretimReceteHatPlaniId = urhp.Id
        JOIN StokKarti sk ON sk.Id = urhpg.KartId
        WHERE ur.Kodu = 'GMP-101-230016'
        ORDER BY sk.Kodu
    """)
    rows = cur.fetchall()
    print(f"  {len(rows)} girdi bulundu")
    for row in rows:
        print(f"  Miktar={row[0]}  Kodu={row[1]}  Adi={row[2]}")

# GMP-101-230107 (bildigimiz 12 bilesenli mamul) de kontrol et
print("\n=== GMP-101-230107 girdileri (karsilastirma) ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT urhpg.Miktar, sk.Kodu, sk.Adi
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        JOIN UretimReceteHatPlaniGirdi urhpg ON urhpg.UretimReceteHatPlaniId = urhp.Id
        JOIN StokKarti sk ON sk.Id = urhpg.KartId
        WHERE ur.Kodu = 'GMP-101-230107'
        ORDER BY sk.Kodu
    """)
    rows = cur.fetchall()
    print(f"  {len(rows)} girdi")
    for row in rows:
        print(f"  Miktar={row[0]}  Kodu={row[1]}  Adi={row[2]}")

# Toplam kayit sayisi
print("\n=== UretimReceteHatPlaniGirdi toplam kayit ===")
with cursor_ctx(conn) as cur:
    cur.execute("SELECT COUNT(*) FROM UretimReceteHatPlaniGirdi")
    print(f"  Toplam: {cur.fetchone()[0]} kayit")

with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT COUNT(DISTINCT ur.Id)
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        JOIN UretimReceteHatPlaniGirdi urhpg ON urhpg.UretimReceteHatPlaniId = urhp.Id
        JOIN StokKarti sk ON sk.Id = urhpg.KartId
        WHERE sk.Aktif = 1
    """)
    print(f"  Girdisi olan mamul sayisi: {cur.fetchone()[0]}")
