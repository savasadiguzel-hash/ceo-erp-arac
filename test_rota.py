#!/usr/bin/env python3
from config import DB_DEFAULTS
from db.baglanti import get_connection, cursor_ctx

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])

# UretimReceteHatPlaniRota tablosunun yapisi
print("=== UretimReceteHatPlaniRota kolonlari ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME='UretimReceteHatPlaniRota' ORDER BY ORDINAL_POSITION
    """)
    for r in cur.fetchall():
        print(f"  {r[0]:<35} {r[1]}")

# GMP-200-230602 için rota satirlari
print("\n=== GMP-200-230602 rota satirlari ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT urhpr.*, sk.Kodu, sk.Adi
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        JOIN UretimReceteHatPlaniRota urhpr ON urhpr.UretimReceteHatPlaniId = urhp.Id
        LEFT JOIN StokKarti sk ON sk.Id = urhpr.StokKartId
        WHERE ur.Kodu = 'GMP-200-230602'
    """)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    print(f"  Kolonlar: {cols}")
    print(f"  {len(rows)} satir:")
    for r in rows:
        print(f"  {dict(zip(cols, r))}")

# Genel: rota tablosunda StokKartId ve :XX kodlari var mi?
print("\n=== UretimReceteHatPlaniRota - StokKarti linkleri ornegi ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT TOP 10 sk.Kodu, sk.Adi, urhpr.Miktar
        FROM UretimReceteHatPlaniRota urhpr
        JOIN StokKarti sk ON sk.Id = urhpr.StokKartId
        WHERE sk.Kodu LIKE '%:%'
        ORDER BY sk.Kodu
    """)
    rows = cur.fetchall()
    print(f"  {len(rows)} ornek:")
    for r in rows:
        print(f"  Kodu={r[0]}  Adi={r[1][:40]}  Miktar={r[2]}")
