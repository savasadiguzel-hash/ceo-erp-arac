#!/usr/bin/env python3
"""StokHareketDetay tablosunun şemasını kontrol et"""

from config import DB_DEFAULTS
from db.baglanti import get_connection, cursor_ctx

conn = get_connection(
    DB_DEFAULTS['sunucu'],
    DB_DEFAULTS['veritabani'],
    DB_DEFAULTS['kullanici'],
    DB_DEFAULTS['sifre']
)

print("StokHareketDetay Tablosu - Kolonlar:")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'StokHareketDetay'
        ORDER BY ORDINAL_POSITION
    """)
    for col_name, data_type, is_nullable in cur.fetchall():
        print(f"  {col_name:<25} {data_type:<15} {'NULL' if is_nullable == 'YES' else 'NOT NULL'}")

print("\n" + "=" * 60)
print("Örnek StokHareketDetay verisi:")
with cursor_ctx(conn) as cur:
    cur.execute("SELECT TOP 5 * FROM StokHareketDetay")
    columns = [desc[0] for desc in cur.description]
    print("Kolonlar:", ", ".join(columns[:10]))
    for row in cur.fetchall():
        print(f"  {row[:10]}")

print("\n" + "=" * 60)
print("StokHareket Tablosu - Kolonlar:")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'StokHareket'
        ORDER BY ORDINAL_POSITION
    """)
    for col_name, data_type in cur.fetchall():
        print(f"  {col_name:<25} {data_type}")
