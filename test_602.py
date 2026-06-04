#!/usr/bin/env python3
from config import DB_DEFAULTS
from db.baglanti import get_connection, cursor_ctx
from db.sorgular import bom_listesi

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])

# 1) GMP-200-230602 UretimRecete'de var mi?
print("=== 1) UretimRecete'de var mi? ===")
with cursor_ctx(conn) as cur:
    cur.execute("SELECT Id, Kodu, Tanim FROM UretimRecete WHERE Kodu LIKE 'GMP-200-230602%'")
    rows = cur.fetchall()
    for r in rows:
        print(f"  Id={r[0]}  Kodu={r[1]}  Tanim={r[2]}")
    if not rows:
        print("  HAYIR - UretimRecete'de yok")

# 2) UretimReceteHatPlaniGirdi'de var mi?
print("\n=== 2) UretimReceteHatPlaniGirdi girdileri ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT urhpg.Miktar, sk.Kodu, sk.Adi
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        JOIN UretimReceteHatPlaniGirdi urhpg ON urhpg.UretimReceteHatPlaniId = urhp.Id
        JOIN StokKarti sk ON sk.Id = urhpg.KartId
        WHERE ur.Kodu = 'GMP-200-230602'
    """)
    rows = cur.fetchall()
    print(f"  {len(rows)} girdi")
    for r in rows:
        print(f"  Miktar={r[0]}  Kodu={r[1]}  Adi={r[2][:50]}")

# 3) UretimReceteHatPlani - eski yol
print("\n=== 3) UretimReceteHatPlani satirlari ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT urhp.Tipi, urhp.Miktar, sk.Kodu, sk.Adi
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        LEFT JOIN StokKarti sk ON sk.Id = urhp.KartId
        WHERE ur.Kodu = 'GMP-200-230602'
    """)
    rows = cur.fetchall()
    print(f"  {len(rows)} satir")
    for r in rows:
        print(f"  Tipi={r[0]}  Miktar={r[1]}  Kodu={r[2]}  Adi={r[3][:50] if r[3] else None}")

# 4) GMP-200-230602:XX StokKarti'de var mi?
print("\n=== 4) StokKarti'de :XX alt kodlar ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT Kodu, Adi FROM StokKarti
        WHERE Kodu LIKE 'GMP-200-230602%'
        ORDER BY Kodu
    """)
    for r in cur.fetchall():
        print(f"  {r[0]}  {r[1][:50]}")

# 5) GMP-101-230014'un bom_listesi() ile gelen bilesenleri
print("\n=== 5) GMP-101-230014 bom_listesi() sonucu ===")
bom = bom_listesi(conn)
mamul = bom.get('GMP-101-230014')
if mamul:
    print(f"  {len(mamul['bilesenleri'])} bilesen:")
    for b in mamul['bilesenleri']:
        in_bom = 'BOM var' if b['kod'] in bom else 'yaprak'
        print(f"  {b['kod']:<30} {b['ad'][:35]}  [{in_bom}]")
else:
    print("  BOM'da yok!")
