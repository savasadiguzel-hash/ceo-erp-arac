DEMO_MAMUL_AGACLARI = [
    ("MA-001", "Ahşap Masa Ünitesi"), ("MA-002", "Metal Raf Sistemi"),
    ("MA-003", "Sandalye Grubu"),     ("MA-004", "Dolap Modülü"),
    ("MA-005", "Montaj Aparatı"),     ("MA-006", "Çelik Kapı Kasası"),
    ("MA-007", "Alüminyum Profil Çerçeve"), ("MA-008", "Hidrolik Piston Ünitesi"),
]

DEMO_STOKLAR = [
    {"stok_kodu": "STK-001", "stok_adi": "Çelik Profil 40x40",
     "fatura_sayisi": 3, "toplam_tutar": "37.500,00 ₺",
     "ilk_fatura": "10.01.2024", "son_fatura": "15.03.2024",
     "tedarikci": "ABC Çelik San. Tic. A.Ş.", "fatura_turleri": "Alış, İthalat"},
    {"stok_kodu": "STK-014", "stok_adi": "Endüstriyel Boya (Epoksi)",
     "fatura_sayisi": 5, "toplam_tutar": "21.800,00 ₺",
     "ilk_fatura": "05.02.2024", "son_fatura": "18.03.2024",
     "tedarikci": "Renkli Kimya Ltd. Şti.", "fatura_turleri": "Alış, Masraf"},
    {"stok_kodu": "STK-022", "stok_adi": "Vida-Somun Seti M8",
     "fatura_sayisi": 2, "toplam_tutar": "6.400,00 ₺",
     "ilk_fatura": "20.01.2024", "son_fatura": "22.03.2024",
     "tedarikci": "Teknik Donanım A.Ş.", "fatura_turleri": "Alış"},
    {"stok_kodu": "STK-037", "stok_adi": "MDF Levha 18mm",
     "fatura_sayisi": 4, "toplam_tutar": "96.000,00 ₺",
     "ilk_fatura": "03.01.2024", "son_fatura": "25.03.2024",
     "tedarikci": "Orman Ürünleri San. ve Tic.", "fatura_turleri": "Alış, İthalat"},
    {"stok_kodu": "STK-045", "stok_adi": "Köpük Conta (15mm)",
     "fatura_sayisi": 3, "toplam_tutar": "6.300,00 ₺",
     "ilk_fatura": "14.02.2024", "son_fatura": "02.04.2024",
     "tedarikci": "Kauçuk San. ve Tic.", "fatura_turleri": "Alış, Masraf"},
    {"stok_kodu": "STK-053", "stok_adi": "Rulman 6205-ZZ",
     "fatura_sayisi": 2, "toplam_tutar": "36.800,00 ₺",
     "ilk_fatura": "01.03.2024", "son_fatura": "05.04.2024",
     "tedarikci": "SKF Türkiye A.Ş.", "fatura_turleri": "İthalat"},
]

DEMO_TARAMA_ADIMLARI = [
    ("Tüm stok kodları listeleniyor",            1842),
    ("Reçeteler kontrol ediliyor",               1842),
    ("Mamül ağaçları kontrol ediliyor",          1842),
    ("Reçete/ağaç dışı stoklar filtreleniyor",    318),
    ("Alış faturaları kontrol ediliyor",          318),
    ("Kesişim kümesi hesaplanıyor",               87),
]

DEMO_BOM = {
    "MA-001": {"ad": "Ahşap Masa Ünitesi", "birim": "ADET", "bilesenleri": [
        {"kod": "STK-037", "ad": "MDF Levha 18mm",     "miktar": 2,   "birim": "ADET"},
        {"kod": "STK-022", "ad": "Vida-Somun Seti M8", "miktar": 20,  "birim": "ADET"},
        {"kod": "STK-014", "ad": "Endüstriyel Boya",   "miktar": 0.5, "birim": "LT"},
    ]},
    "MA-002": {"ad": "Metal Raf Sistemi", "birim": "ADET", "bilesenleri": [
        {"kod": "STK-001", "ad": "Çelik Profil 40x40", "miktar": 6,  "birim": "KG"},
        {"kod": "STK-022", "ad": "Vida-Somun Seti M8", "miktar": 12, "birim": "ADET"},
        {"kod": "STK-045", "ad": "Köpük Conta 15mm",   "miktar": 2,  "birim": "ADET"},
    ]},
    "MA-003": {"ad": "Sandalye Grubu", "birim": "ADET", "bilesenleri": [
        {"kod": "STK-037", "ad": "MDF Levha 18mm",     "miktar": 1,   "birim": "ADET"},
        {"kod": "STK-001", "ad": "Çelik Profil 40x40", "miktar": 3,   "birim": "KG"},
        {"kod": "STK-014", "ad": "Endüstriyel Boya",   "miktar": 0.3, "birim": "LT"},
        {"kod": "STK-022", "ad": "Vida-Somun Seti M8", "miktar": 8,   "birim": "ADET"},
    ]},
    "MA-004": {"ad": "Dolap Modülü", "birim": "ADET", "bilesenleri": [
        {"kod": "STK-037", "ad": "MDF Levha 18mm",     "miktar": 4,  "birim": "ADET"},
        {"kod": "STK-022", "ad": "Vida-Somun Seti M8", "miktar": 32, "birim": "ADET"},
        {"kod": "STK-053", "ad": "Rulman 6205-ZZ",     "miktar": 2,  "birim": "ADET"},
        {"kod": "STK-045", "ad": "Köpük Conta 15mm",   "miktar": 4,  "birim": "ADET"},
    ]},
    "MA-005": {"ad": "Montaj Aparatı", "birim": "ADET", "bilesenleri": [
        {"kod": "STK-001", "ad": "Çelik Profil 40x40", "miktar": 2, "birim": "KG"},
        {"kod": "STK-008", "ad": "NYY Kablo 3x2.5mm",  "miktar": 5, "birim": "MT"},
        {"kod": "STK-053", "ad": "Rulman 6205-ZZ",     "miktar": 1, "birim": "ADET"},
    ]},
}

# tarih: YYYY-MM-DD, birim_fiyat: float, miktar: float
DEMO_FIYATLAR = {
    "STK-001": [{"tarih": "2024-01-10", "birim_fiyat": 23.50, "miktar": 500},
                {"tarih": "2024-02-08", "birim_fiyat": 24.80, "miktar": 300},
                {"tarih": "2024-03-15", "birim_fiyat": 26.20, "miktar": 800}],
    "STK-008": [{"tarih": "2024-01-28", "birim_fiyat": 22.50, "miktar": 300}],
    "STK-014": [{"tarih": "2024-02-05", "birim_fiyat": 165.00, "miktar": 60},
                {"tarih": "2024-03-18", "birim_fiyat": 178.00, "miktar": 60}],
    "STK-022": [{"tarih": "2024-01-20", "birim_fiyat": 3.10, "miktar": 1000},
                {"tarih": "2024-03-22", "birim_fiyat": 3.40, "miktar": 1000}],
    "STK-037": [{"tarih": "2024-01-05", "birim_fiyat": 280.00, "miktar": 40},
                {"tarih": "2024-02-20", "birim_fiyat": 295.00, "miktar": 40},
                {"tarih": "2024-03-25", "birim_fiyat": 310.00, "miktar": 80}],
    "STK-045": [{"tarih": "2024-01-15", "birim_fiyat": 2.05, "miktar": 500},
                {"tarih": "2024-03-02", "birim_fiyat": 2.15, "miktar": 500}],
    "STK-053": [{"tarih": "2024-03-01", "birim_fiyat": 92.00, "miktar": 100},
                {"tarih": "2024-04-05", "birim_fiyat": 98.00, "miktar": 100}],
}
