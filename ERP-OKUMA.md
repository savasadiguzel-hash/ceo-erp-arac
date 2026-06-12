# CEO ERP Araçları

**GitHub:** https://github.com/savasadiguzel-hash/ceo-erp-arac  
**Dağıtım:** `dist/CEO-ERP-Araclar.exe`  
**Son güncelleme:** 2026-06-12

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
| Fatura Eşleştir | Gelen e-fatura kalemlerini stok kartlarıyla bulanık eşleştirme; satınalma notu üretir |

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

### Bakiye Formülü (CEO `fnStokBakiyeGetir` inline — tarih filtreli)

CEO ERP'nin kendi `fnStokBakiyeGetir` scalar fonksiyonunun mantığı, tarih filtresi eklenerek Python'dan çağrılabilir hâle getirildi.

**GirenMiktar:** `IslemKodu IN (1, 4, 5, 8, 15, 16, 20, 22, 26, 29)`

| Kod | Açıklama |
|---|---|
| 1 | Alış Faturası |
| 4 | Satış İade Faturası |
| 5 | Alış İrsaliyesi (FaturaDetayId bağlıysa net = 0 → çift sayım önlenir) |
| 8 | Üretim Faturası |
| 15 | Devir Girişi |
| 16 | Üretimden Giriş |
| 20 | Sayım Fazlası |
| 22 | Devir Girişi |
| 26 | Konsinye Giriş |
| 29 | Diğer Giriş |

**CikanMiktar:** `IslemKodu IN (2, 3, 6, 7, 17, 18, 19, 21, 23, 24, 28)`

| Kod | Açıklama |
|---|---|
| 2 | Satış Faturası |
| 3 | Alış İade Faturası |
| 6 | Satış İrsaliyesi |
| 7 | Üretim İade Faturası |
| 17 | Üretime Çıkış |
| 18 | Depolar Arası Çıkış |
| 19 | Sayım Eksiği |
| 21 | Fire |
| **23** | **Depolar Arası Giriş — CEO `StokHareketIsGiris(23)=0` (ÇIKIŞ sayar)** |
| 24 | Konsinye Çıkış |
| 28 | Diğer Çıkış |

**CEO `fnStokBakiyeGetir` SQL (tarih filtreli inline):**
```sql
SUM(CASE
    WHEN sh.IslemKodu IN (1,4,5,8,15,16,20,22,26,29)
        THEN (shd.Miktar - ISNULL(shd_f.Miktar, 0))
    WHEN sh.IslemKodu IN (2,3,6,7,17,18,19,21,24,28)
        THEN -(shd.Miktar - ISNULL(shd_f.Miktar, 0))
    ELSE 0
END)
FROM StokHareketDetay shd
JOIN StokHareket sh ON sh.Id = shd.HareketId
LEFT JOIN StokHareketDetay shd_f ON shd_f.Id = shd.FaturaDetayId
WHERE shd.Turu = 1 AND shd.Aktif = 1
  AND sh.Aktif = 1
  AND sh.FaturaId IS NULL
  AND sh.IslemKodu NOT IN (9,10,11,12,13,14,25,27,23)
  AND CAST(sh.BelgeTarihi AS DATE) <= CAST(? AS DATE)
```

**Üç kilit kural (CEO'dan alınmış):**
1. `sh.FaturaId IS NULL` — faturalaşmış irsaliyeler (k5/k6 where FaturaId IS NOT NULL) otomatik hariç, çift sayım engellenir
2. `NOT IN (9,10,11,12,13,14,25,27,23)` — konsinye hareketler + k23 (Depolar Arası Giriş) hariç; k23 toplam şirket stoğunu değiştirmez
3. `FaturaDetayId` deduction — henüz faturalaşmamış ama kısmi ödenen irsaliyeler için

**Tarih filtresi:** `BelgeTarihi <= UretimEmriTarihi`

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

### Bakiye Doğrulaması — CEO Stok Kartı Ekstresi (2026-06-12)

Referans: `dist/Stok Kartı Ekstresi_12062026190248.xlsx` (932 kart). **Metot E** (`tani_multi_seed.py`, 5 seed × 20 kart).

| Seed | Eşleşme | Oran | Uyumsuz kartlar |
|---|---|---|---|
| 42  | 16/20 | %80  | BC81725TP(+1244), GMP-200-230065(-2), HMGMTRM0009(+54), RMCF0805FT10K0(+189) |
| 99  | 18/20 | %90  | GMP-200-230538(-1), GMP-200-230555(-1) |
| 777 | 19/20 | **%95** | MAL215097011E3(+6) |
| 1234| 17/20 | %85  | 09-3782-91-08(-5), GMP-110-230025(+1), MAX98357A(+6) |
| 5678| 19/20 | **%95** | GMP-101-230035(+5) |

**Ortalama eşleşme:** ~%92 (Metot E %89, eski formül %60-70'di)

| Seed | Metot E | CEO formülü |
|---|---|---|
| 42 | 16/20 (%80) | **17/20 (%85)** |
| 99 | 18/20 (%90) | **20/20 (%100)** |
| 777 | 19/20 (%95) | 18/20 (%90) |
| 1234 | 17/20 (%85) | **18/20 (%90)** |
| 5678 | 19/20 (%95) | 19/20 (%95) |

**Kalan uyumsuzlukların kök nedeni:**
- CEO stok kartı ekstresi **depo+period spesifik** bakiye gösterir; `fnStokBakiyeGetir` (ve bizim formülümüz) **toplam şirket all-time** bakiyesi hesaplar
- Fark pozitif (+): bizim formülümüz CEO extract'tan fazla stok gösteriyor → DB'de olmayan June 2026 hareketleri veya depo senkron sorunu
- MAL215097011E3: CEO extract'te Haz 2026'da k23 hareketleri var, DB'de yok (veri senkron sorunu)

**Formül evrimi:**
- v1 (eski): `IslemKodu IN (1,16,20,22)` — k5/k4/k20 eksikti
- v2 (Metot E): CEO `StokHareketIsGiris` sign map + k23 çıkış
- **v3 (güncel)**: CEO `fnStokBakiyeGetir` EXACT inline — `FaturaId IS NULL` + `NOT IN (9..23)` + `shd.Turu=1`

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
tools/   fatura_eslestir.py, mutabakat.py
ui/      ana_pencere.py, maliyet.py, mamul_agaci_tab.py, tarama.py, eslestirme.py, rapor.py
         tab_satis_faturalari.py, tab_erp_aktar.py, tab_sw.py, tab_uretim_raporu.py, tab_fatura_eslestir.py, baglanti.py, stil.py
sw/      classifier, pipeline, renamer, erp_handler, vision_handler
referans/faturalar/  test_kalemleri.json
dist/    CEO-ERP-Araclar.exe, config.json
```

---

## Fatura Eşleştir Sekmesi

Gelen e-fatura kalemlerini CEO ERP stok kartlarıyla **bulanık eşleştirme** yapar; satınalma sorumlusuna iletilecek metin bloğunu üretir.

**Giriş:** JSON dosyası (QFileDialog) veya "Örnek Yükle" (`referans/faturalar/test_kalemleri.json`)

**Akış:**
1. **Bağlan ve Stok Yükle** — `BaglantiThread` → `StokYuklemeThread` → `StokKarti WHERE Aktif=1` (arka plan, UI donmaz)
2. **JSON Yükle** — kalem listesi renk badge'li: GÜÇLÜ (yeşil) / GÖZDEN GEÇİR (turuncu) / KART YOK (kırmızı) / İŞÇİLİK (mavi) / MUHTELİF (gri)
3. **Eşleştir** — `EslestirmeThread` → her kalem için `adaylar_bul()` (`token_set_ratio`, üst 5 aday) + `operasyon_mu()` + `kova_ayir()`
4. Kalem seçince sağ üstte aday listesi (skor + etiket); muhtelif seçilince sağ altta dağıtım tablosu aktif
5. **Dağıtım** — yöntem: Eşit / Ağırlık / Miktar / Elle; `dagitim_hesapla()` + `elle_dogrula()` ile tutar sütunu doldurulur
6. **Satınalma Metni Üret** → `metin_blogu_olustur()` → QTextEdit; Kopyala / Dosyaya Kaydet

**Eşleştirme mantığı (`tools/fatura_eslestir.py`):**
- Türkçe normalize: `İŞĞÜÇÖ` → büyük harf
- Ölçü token çıkarımı: CAP_ (Ø çap) / KESIT_ (AxB kesit) / KAL_ (304/316) / FORM_ (DOLU/LAMA/SAC/BORU)
- Eleme tavanı: çakışan token → 59.9; eksik token → 84.9
- Eşik: GÜÇLÜ ≥ 85, GÖZDEN GEÇİR ≥ 60

**Kritik kural:** CEO ERP'ye YAZMA YOK — yalnızca `StokKarti` okuma.

**Fonksiyonlar:** `tools/fatura_eslestir.py` → `stok_kartlari_db`, `adaylar_bul`, `kova_ayir`, `kirli_neden`, `operasyon_mu`, `dagitim_hesapla`, `elle_dogrula`, `metin_blogu_olustur`  
**UI:** `ui/tab_fatura_eslestir.py:FaturaEslestirTab`

---

## Sıradaki Geliştirmeler

1. **PDF gömme** — teknik resim PDF'lerini `StokKarti.DokumanPath`'e bağlama
2. **Canlı SW testi** — SW Kodlama sekmesini iş makinesinde SolidWorks 2019 ile doğrulama
