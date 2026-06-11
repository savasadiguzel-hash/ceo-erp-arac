# CEO ERP Araçları

**GitHub:** https://github.com/savasadiguzel-hash/ceo-erp-arac  
**Dağıtım:** `dist/CEO-ERP-Araclar.exe`  
**Son güncelleme:** 2026-06-11

---

## Sekmeler

| Sekme | Ne yapar |
|---|---|
| Mamül Ağacı | Reçetesiz + faturalı stokları tespit eder, mamüle bağlar |
| Maliyet | LIFO / FIFO / Ağırlıklı Ortalama maliyet raporu (Excel) |
| SW Kodlama | SolidWorks montaj → AI sınıflandırma → GEM/YMB kodu |
| Stok Kartı Aktar | SW sonrası CEO ERP'ye otomatik stok kartı açar |
| Satış Faturaları | Tarih aralığına göre satış fatura/irsaliye listesi + Excel |
| Üretim Eksik Stok | "Devam Ediyor" emirlerinde hat planı malzemeleri için eksik stok raporu |

---

## Mamül Ağacı Sekmesi

**Tarama — Kesişim Kümesi:** Reçetesiz + faturalı stokları bulur.

**Fiyat yöntemi:** FIFO / LIFO / Ağırlıklı Ortalama — tarama başlamadan seçilir.

**Excel çıktısı — 2 sayfa:**
- `Kesişim Kümesi` — stok bazında özet (7 sütun)
- `Fatura Detayları` — her fatura satırı ayrı (9 sütun)

**Kritik filtreler:**
- `sk.Id NOT IN (UretimReceteHatPlaniGirdi.KartId)` — bileşenler kesişimden çıkar
- `shd.Turu = 1` — yalnızca ürün satırları (Turu=3 kur farkı/muhasebe satırları hariç)
- `StokHareketDetay JOIN sk.Id` üzerinden — aksi hâlde 2M+ Kartezyen çarpım

**Bilinen sorun:** Bazı `sk.Adi` değerleri sonda `\n\n` içerir; `kesisim_excel_kaydet` `.strip()` uygular.

**Eşleştirme sayfası:** Tespit edilen stokları mamüle bağlar; etiketler fare ile seçilebilir.

---

## Maliyet Sekmesi

- Bağlan → DB bağlantısı arka thread'de kurulur, pencere donmaz
- **Fiyat kaynağı:** `IslemKodu IN (1, 5)` — alış faturası + alış irsaliyesi
- **Performans:** `stok_fiyatlari_toplu()` ile N bileşen için tek SQL sorgusu

---

## Satış Faturaları Sekmesi

- `IslemKodu IN (2, 6)` — satış faturası + irsaliye; `shd.Turu = 1`
- 9 kolonlu tablo + anlık arama (müşteri, stok kodu, belge no)
- Excel çıktısı: biçimlendirilmiş xlsx, son satırda toplam tutar

---

## Üretim Eksik Stok Sekmesi

- Aç → DB'ye otomatik bağlanır; "Devam Ediyor" emirler sol panelde listelenir
- Emir seç → **Analiz Et** → sağ panelde eksik malzemeler BOM patlatmalı ağaç görünümünde
- **Hat filtresi:** `HatTipi IN (1, 2)` (ana üretim hattı + aksesuar grubu)

### Bakiye Formülü

**GirenMiktar:**
- `IslemKodu IN (1, 16, 22)` — Alış Faturası, Üretimden Giriş, Devir Girişi
  - ⚠️ `IslemKodu=20` (Sayım Fazlası) **sayılmaz** — CEO ERP saymıyor; sayılırsa bakiye şişer → false negative
- `IslemKodu = 23 AND StokHareket.Id IN (paired_ids)` — Depolar Arası Giriş, **yalnızca irsaliye kökenli**

**CikanMiktar:** `IslemKodu IN (2, 3, 6, 17, 18, 19, 21)` — Satış, Alış İade Faturası, Satış İrsaliyesi, Üretime Çıkış, Depolar Arası Çıkış, Sayım Eksiği, Fire

**Tarih filtresi:** `BelgeTarihi <= UretimEmriTarihi`

**IslemKodu notları:**
- `5` (Alış İrsaliyesi) sayılmaz — IslemKodu=1 veya eşli IslemKodu=23 ile gelir, sayılırsa çift sayım
- `3` (Alış İade Faturası) CIK'ta — geçmişte iade yapılmış kartların tarihsel bakiyesini düzeltir
- `23` (Depolar Arası Giriş) koşullu: `_kod23_paired_ids_str(conn)` ile hesaplanan eşleşen ID'ler sayılır; eşi olmayan saf depo transferleri IslemKodu=18 ile netleşir (toplam bakiyeye etkisi sıfır). Bu DB'de 8 eşleşen ID: `740137, 741399, 741897, 743385–743389`

### BOM Patlatma

- Hat planında alt montaj varsa bileşenleri ağaç görünümünde gösterilir (max 8 seviye)
- Aynı kart_id birden fazla yoldan geliyorsa talep toplanır
- Net gereksinim: alt montaj için `üretilecek = max(0, talep − emri_tarihi_bakiyesi)`
- **Excel'e Aktar** — tek emir, hiyerarşik xlsx (`└─` öneki)
- **Tüm Emirleri Excel'e Aktar** (turuncu) — tüm açık emirler tek sayfada, progress bar ile

**Fonksiyonlar:** `db/sorgular.py` → `uretim_emir_bom_patlat()`, `tum_emirler_eksik_stok()`  
**UI:** `ui/tab_uretim_raporu.py:UretimRaporuTab`

### Muhasebe Eksik Raporu (ATP destekli)

**Muhasebe Eksik Raporu (Excel)** butonu (mor, üst sağ):

- Emirler `UretimEmriTarihi ASC` — eski → yeni
- Düz (flat) BOM: yarı mamüller + tüm recursive bileşenler ayrı satırlar, brüt talep
- **Depo bazlı hibrit bakiye:** hedef depo bakiyesi < 0 ise depo bakiyesi esas alınır; aksi hâlde toplam şirket bakiyesi
- **ATP kümülatif rezervasyon:** eski emirlerin talebi yeni emirlerin net bakiyesinden düşülür
- Net Eksik = ERP Bakiyesi − İhtiyaç − Önceki Rezervasyon (yalnızca > 0 satırlar yazılır)
- 9 sütun: İş Emri Tarihi / No / Açıklama / Stok Kodu / Adı / İhtiyaç / ERP Bakiyesi / Önceki Rezervasyon / Net Eksik
- Emir grupları mor header ile; Net Eksik kırmızı/kalın; `auto_filter` tüm sütunlara

**Fonksiyon:** `db/sorgular.py:muhasebe_eksik_raporu_olustur()`

### Bakiye Doğrulaması — CEO Stok Kartı Ekstresi (2026-06-10)

Referans: `Stok Kartı Ekstresi_10062026183813.xlsx` (804 kart). 11 kart test edildi.

| Stok Kodu | CEO | DB | Durum |
|---|---|---|---|
| HMGMDDAL004 | 591 | 591 | ✅ |
| RT0603BRD07665KL | 6 | 6 | ✅ |
| C0805C103J3GACTU | 238 | 238 | ✅ |
| 40VK6 | 6 | 6 | ✅ |
| YMGMKRT0056 | 550 | 550 | ✅ |
| GMP-200-240294 | -21 | -21 | ✅ |
| GMP-200-230540 | 0 | 0 | ✅ |
| GMP-101-230044 | 1 | 1 | ✅ |
| CL10A475KO8NNNC | 12 | 12 | ✅ |
| XP10NA1R5TL | 76 | 76 | ✅ |
| BLM31PG121SN1L | 206 | 206 | ✅ |

**Hedef:** HMGMDDAL004 → 05.01.2026 = **0** ✓, güncel = **591** ✓  
**Sonuç: 11/11 eşleşme**

---

## Veritabanı

| Parametre | Değer |
|---|---|
| Sunucu | `WIN-3FATBI9RQAA\CEO1` |
| Firma | 504 (`DATABASE=504`) |
| Auth | SQL Server (`sa`), şifre `dist/config.json`'da base64 |
| Kural | **SADECE OKUMA** — yazma yalnızca Stok Kartı Aktar akışında |

---

## Kurulum

```
git clone https://github.com/savasadiguzel-hash/ceo-erp-arac
pip install -r requirements.txt
python main.py
```

`.env` (SW Kodlama + Stok Kartı için):
```
GEMINI_API_KEY=...
CEO_SQL_CONN=DRIVER={SQL Server};SERVER=WIN-3FATBI9RQAA\CEO1;UID=sa;PWD=...
```

Derleme: `build.bat` → `dist/CEO-ERP-Araclar.exe` + `copy config.json dist\config.json`

---

## Klasör Yapısı

```
main.py / config.py / config.json / build.bat
db/      baglanti.py, sorgular.py
logic/   maliyet.py, excel.py
ui/      ana_pencere.py, maliyet.py, mamul_agaci_tab.py, tarama.py, eslestirme.py, rapor.py
         tab_satis_faturalari.py, tab_erp_aktar.py, tab_sw.py, tab_uretim_raporu.py, baglanti.py, stil.py
sw/      classifier, pipeline, renamer, erp_handler, vision_handler
dist/    CEO-ERP-Araclar.exe, config.json
```

---

## Sıradaki Geliştirmeler

1. **PDF gömme** — teknik resim PDF'lerini `StokKarti.DokumanPath`'e bağlama
2. **Canlı SW testi** — SW Kodlama sekmesini iş makinesinde SolidWorks 2019 ile doğrulama
