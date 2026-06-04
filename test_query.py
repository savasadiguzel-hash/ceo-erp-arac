#!/usr/bin/env python3
"""Stok fiyat geçmişi sorgusunu test et"""

from config import DB_DEFAULTS
from db.baglanti import get_connection, cursor_ctx

conn = get_connection(
    DB_DEFAULTS['sunucu'],
    DB_DEFAULTS['veritabani'],
    DB_DEFAULTS['kullanici'],
    DB_DEFAULTS['sifre']
)

# Test stok kodu
stok_kodu = "CHZ-V00R00-220001"
bas_sql = "2024-01-01"
bit_sql = "2024-12-31"

print(f"Stok: {stok_kodu}")
print(f"Tarih: {bas_sql} - {bit_sql}\n")

# Sorgu 1: Direkt BirimFiyat sorgula
print("=" * 80)
print("SORGU 1: StokHareketDetay - BirimFiyat ve Miktar")
print("=" * 80)
with cursor_ctx(conn) as cur:
    cur.execute(f"""
        SELECT TOP 10
            CONVERT(VARCHAR(10), sh.BelgeTarihi, 120) as Tarih,
            shd.BirimFiyat,
            shd.Miktar,
            sk.Kodu,
            sk.Adi
        FROM StokHareketDetay shd
        JOIN StokHareket sh ON sh.Id = shd.HareketId
        LEFT JOIN StokKarti sk ON sk.Id = shd.IslemKartId
        WHERE sk.Kodu = ?
          AND CAST(sh.BelgeTarihi AS DATE) >= CAST('{bas_sql}' AS DATE)
          AND CAST(sh.BelgeTarihi AS DATE) <= CAST('{bit_sql}' AS DATE)
        ORDER BY sh.BelgeTarihi ASC
    """, stok_kodu)

    rows = cur.fetchall()
    print(f"Sonuç: {len(rows)} kayıt")
    for row in rows[:5]:
        print(f"  {row}")

# Sorgu 2: ISNULL kullan
print("\n" + "=" * 80)
print("SORGU 2: ISNULL ile boş değerleri kontrol et")
print("=" * 80)
with cursor_ctx(conn) as cur:
    cur.execute(f"""
        SELECT TOP 10
            CONVERT(VARCHAR(10), sh.BelgeTarihi, 120) as Tarih,
            ISNULL(shd.BirimFiyat, 0) as BirimFiyat,
            ISNULL(shd.Miktar, 0) as Miktar,
            sk.Kodu
        FROM StokHareketDetay shd
        JOIN StokHareket sh ON sh.Id = shd.HareketId
        LEFT JOIN StokKarti sk ON sk.Id = shd.IslemKartId
        WHERE sk.Kodu = ?
          AND CAST(sh.BelgeTarihi AS DATE) >= CAST('{bas_sql}' AS DATE)
          AND CAST(sh.BelgeTarihi AS DATE) <= CAST('{bit_sql}' AS DATE)
        ORDER BY sh.BelgeTarihi ASC
    """, stok_kodu)

    rows = cur.fetchall()
    print(f"Sonuç: {len(rows)} kayıt")
    for row in rows[:5]:
        print(f"  {row}")

# Sorgu 3: StokKarti.Id ile IslemKartId eşleşme kontrolü
print("\n" + "=" * 80)
print("SORGU 3: StokKarti.Id ve IslemKartId eşleşmesi")
print("=" * 80)
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT TOP 5
            sk.Id,
            sk.Kodu,
            COUNT(*) as HareketSayisi,
            AVG(CAST(shd.BirimFiyat AS FLOAT)) as OrtBirimFiyat
        FROM StokKarti sk
        LEFT JOIN StokHareketDetay shd ON sk.Id = shd.IslemKartId
        WHERE sk.Kodu IN (?, ?)
        GROUP BY sk.Id, sk.Kodu
    """, stok_kodu, "GMP-101-230015")

    for row in cur.fetchall():
        print(f"  {row}")
