# CEO ERP Araçları

**GitHub:** https://github.com/savasadiguzel-hash/ceo-erp-arac  
**Dağıtım:** `dist/CEO-ERP-Araclar.exe` · `dist/CEO-ERP-Kurulum.exe` (Inno Setup)  
**Son güncelleme:** 2026-06-17 (UretimRecete INSERT düzeltmeleri + ADLASMKE Excel formatı)

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
| Reçete Sorgula | Stok kodunu hangi mamül ağaçlarında bileşen olarak kullandığını bulur (BFS) |
| Stok Hazırlık | BOM ağacı oluşturma / yükleme / düzenleme + CEO ERP'ye yazma |
| İş Emri Formu | Tüm durumlardaki üretim emirlerini listeler; checkbox seçim + toplu PDF çıktısı; boş doldurulabilir Excel formu (A4) |

---

## Mamül Ağacı Sekmesi

**Tarama — Kesişim Kümesi:** Reçetesiz + faturalı stokları bulur.

**Fiyat yöntemi:** FIFO / LIFO / Ağırlıklı Ortalama — tarama başlamadan seçilir.

**Excel çıktısı — 2 sayfa:**
- `Kesişim Kümesi` — stok bazında özet (8 sütun: Stok Kodu / Stok Adı / **Stok Adı-2** / Fatura Sayısı / Birim Fiyat / İlk Fatura / Son Fatura / Tedarikçi)
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

```sql
SUM(CASE
    WHEN sh.IslemKodu IN (1,4,5,8,15,16,20,22,26,29)
        THEN (shd.Miktar - ISNULL(shd_f.Miktar, 0))   -- GirenMiktar
    WHEN sh.IslemKodu IN (2,3,6,7,17,18,19,21,24,28)
        THEN -(shd.Miktar - ISNULL(shd_f.Miktar, 0))  -- CikanMiktar
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

**Üç kilit kural:**
1. `sh.FaturaId IS NULL` — faturalaşmış irsaliyeler (k5/k6) otomatik hariç, çift sayım engellenir
2. `NOT IN (9..27,23)` — konsinye hareketler + k23 (Depolar Arası Giriş) hariç; k23 toplam stoğu değiştirmez
3. `FaturaDetayId` deduction — kısmi ödenen irsaliyeler için

**Not:** k23 (Depolar Arası Giriş) ÇIKIŞ sayılır — CEO `StokHareketIsGiris(23)=0` mantığıyla örtüşür.

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

**Fonksiyon:** `db/sorgular.py:muhasebe_eksik_raporu_olustur()`

### Bakiye Formülü Doğrulaması

CEO `fnStokBakiyeGetir` inline formülü 932 kartlık ekstrede ~%92 eşleşme sağlar (eski v1 formülü %60-70'di).

Kalan uyumsuzluğun kök nedeni: CEO stok kartı ekstresi **depo+period spesifik** gösterir; bizim formülümüz **toplam şirket all-time** bakiyesi hesaplar.

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

### Geliştirici Ortamı

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

Exe derleme: `build.bat` → `dist/CEO-ERP-Araclar.exe` + `copy config.json dist\config.json`

### Şirket İçi Dağıtım (Yeni PC)

**Gereksinim:** Inno Setup 6 ([jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php)) — yalnızca paketi derleyen makinede.

```
build.bat              ← önce exe derle
create_installer.bat   ← ardından kurulum paketi oluştur
```

Çıktı: `dist\CEO-ERP-Kurulum.exe` (~72 MB, her şey dahil)

**Hedef PC'de kurulum:**
1. `CEO-ERP-Kurulum.exe` çalıştır → sihirbaz `Program Files\CEO ERP Araclar\` altına kurar
2. Başlat Menüsü + isteğe bağlı masaüstü kısayolu otomatik oluşur
3. İlk çalıştırmada bağlantı bilgileri girilir → `config.json` otomatik kaydedilir
4. Güncelleme kurulumlarında mevcut `config.json` korunur

**Ekstra bağımlılık yok** — Windows yerleşik `DRIVER={SQL Server}` sürücüsü yeterli.

---

## Klasör Yapısı

```
main.py / config.py / config.json / build.bat / setup.iss / create_installer.bat
db/      baglanti.py, sorgular.py
logic/   maliyet.py, excel.py, excel_is_emri.py, pdf_is_emri.py
tools/   fatura_eslestir.py, mutabakat.py
ui/      ana_pencere.py, maliyet.py, mamul_agaci_tab.py, tarama.py, eslestirme.py, rapor.py
         tab_satis_faturalari.py, tab_erp_aktar.py, tab_sw.py, tab_uretim_raporu.py
         tab_fatura_eslestir.py, tab_recete_sorgula.py, tab_stok_hazirla.py
         tab_is_emri_formu.py, baglanti.py, stil.py
sw/      classifier, pipeline, renamer, erp_handler, vision_handler
referans/faturalar/  test_kalemleri.json
dist/    CEO-ERP-Araclar.exe, config.json
```

---

## Fatura Eşleştir Sekmesi

Gelen e-fatura kalemlerini CEO ERP stok kartlarıyla **bulanık eşleştirme** yapar; satınalma sorumlusuna iletilecek metin bloğunu üretir.

**Giriş:** JSON dosyası (QFileDialog) veya "Örnek Yükle" (`referans/faturalar/test_kalemleri.json`)

**Akış:**
1. **Bağlan ve Stok Yükle** → `StokKarti WHERE Aktif=1` (arka plan, UI donmaz)
2. **JSON Yükle** → kalem listesi renk badge'li: GÜÇLÜ / GÖZDEN GEÇİR / KART YOK / İŞÇİLİK / MUHTELİF
3. **Eşleştir** → `adaylar_bul()` (`token_set_ratio`, üst 5 aday) + `operasyon_mu()` + `kova_ayir()`
4. Kalem seçince sağ üstte aday listesi; muhtelif seçilince dağıtım tablosu aktif
5. **Dağıtım** — Eşit / Ağırlık / Miktar / Elle
6. **Satınalma Metni Üret** → QTextEdit; Kopyala / Dosyaya Kaydet

**Eşleştirme mantığı (`tools/fatura_eslestir.py`):**
- Türkçe normalize: `İŞĞÜÇÖ` → büyük harf
- Ölçü token çıkarımı: CAP_ / KESIT_ / KAL_ / FORM_
- Eleme tavanı: çakışan token → 59.9; eksik token → 84.9
- Eşik: GÜÇLÜ ≥ 85, GÖZDEN GEÇİR ≥ 60

**UI:** `ui/tab_fatura_eslestir.py:FaturaEslestirTab`

---

## Reçete Sorgula Sekmesi

Girilen stok / masraf kodlarının hangi mamül ağaçlarında **bileşen** olarak kullanıldığını bulur.

**Akış:** Kodları yaz (veya Excel'den yükle) → **Sorgula** → BFS ile tüm üst seviyeleri tarar → renkli tablo (Direkt / Dolaylı / Bağlantısız) → Excel çıktısı (5 sütun)

**Masraf desteği:** `StokMasrafKarti` (Tipi=2) de sorgulanır.

**Fonksiyon:** `db/sorgular.py:bilesen_mamul_bul()`  
**UI:** `ui/tab_recete_sorgula.py:ReceteSorgulaTab`

---

## Stok Hazırlık Sekmesi

BOM ağacı oluşturma, yükleme, düzenleme ve CEO ERP'ye yazma.

### Ağaç Yapısı

QTreeWidget — 7 sütun: **Tip | Stok Kodu | Stok Adı | Stok Adı-2 | Miktar | Birim | Durum**

Tip seçenekleri: `Hammadde / Yarımamül / Mamül / Reçete / Masraf`

### BOM Görsel Diyagram

**BOM Diyagramı** butonu (mor) — reçete veya Excel yüklendikten sonra aktif olur. Her açılışta QTreeWidget'taki **güncel** ağaç verisi kullanılır (eski Excel verisi değil).

| Eylem | Davranış |
|---|---|
| Fare tekerleği | Zoom in / out |
| Sol tık + sürükle | Kaydırma (pan) |
| CTRL + sol tık | Çoklu seçim (turuncu çerçeve) |
| Sağ tık → seçim YOK | "Ebeveynini Değiştir" context menu |
| Sağ tık → seçim VAR | "Seçilileri Buraya Bağla (N düğüm)" |
| **Kaydet** | Diyagram değişiklikleri QTreeWidget'a yansır |
| **Sıfırla** | Orijinal yüklü hâle döner |

**Düğüm renkleri:** Mamül (indigo) / Reçete (açık mavi) / Hammadde (yeşil) / Yarımamül (mor) / Masraf (turuncu)

**Teknik:** `_ReceteHaritaWidget(QGraphicsView)` + `_DugumItem(QGraphicsPathItem)`. Context menu VIEW seviyesinde yakalanır; sahne yeniden çizimi `QTimer.singleShot(0, ...)` ile ertelenir.

### Reçete Yükleme

**Reçete Yükle** → `recete_yukle()` recursive ağacı çeker:
- `Tipi=1` → `StokKarti` (hammadde / yarı mamül)
- `Tipi=2` → `StokMasrafKarti` (masraf / işlem — `GMP-xxx:NN` formatı)
- Max 8 seviye, döngü korumalı; birim GUID → isim çözümü thread'de yapılır

### Excel Aktar / Yükle

**Excel'e Aktar** → 7 sütun (Seviye / Tip / Stok Kodu / Stok Adı / Stok Adı-2 / Miktar / Birim), derinlik bazlı renkler, native +/- satır grupları.

**Excel'den Yükle** — 4 format tanır:

| Format | Tespit | Davranış |
|---|---|---|
| Yeni (Seviye-Tip) | A sütunu integer | Seviye+girinti korunarak yüklenir |
| Eski 6-kolon | A sütunu tip metni | Girintili stok kodu ile hiyerarşi |
| Çok eski | Diğer durum | Flat yükleme |
| **ADLASMKE** | A1 = "Stok Kodu" | CEO ERP dışa aktarımı — özel işleme ↓ |

**ADLASMKE formatı** (`_excel_yukle_adlasmke`):
- Header: `Stok Kodu | Stok Adı | Stok Adı-2 | Gerçek Bakiye | Ölçü Birimi | Depo Raf Adedi`
- `:XX` sonek taşıyan her kod (ör. `GMP-200-240839:20`) → baz kodunun **çocuk düğümü** olarak eklenir
- Baz kodu listede varsa → `Reçete` tipine dönüştürülür + çocuk altına alınır
- Baz kodu listede **yoksa** → sanal `Reçete` ebeveyni oluşturulur (ad boş; kullanıcı doldurur)

### Kontrol Et / CANLI Aktar

**CANLI Aktar — 3 faz:**

| Faz | İşlem |
|-----|-------|
| 1 | Stok/masraf kartlarını aç |
| 2a | Miktar değişikliği → `UPDATE UretimReceteHatPlaniGirdi.Miktar` |
| 2b | Yeni bileşenler → `recete_bagla()` (Tipi=1) / `recete_masraf_bagla()` (Tipi=2) |
| 3 | Ağaçtan silinen yüklü bileşenler → `DELETE UretimReceteHatPlaniGirdi` |

### CEO ERP Tablo Yapısı

```
UretimRecete
  └─ UretimReceteHatPlani  (KartId → StokKarti)
       └─ UretimReceteHatPlaniGirdi
            ├─ Tipi=1  KartId → StokKarti       (hammadde / yarı mamül)
            └─ Tipi=2  KartId → StokMasrafKarti  (masraf / işlem)
```

**UretimRecete INSERT — zorunlu NOT NULL alanlar:**

| Alan | Değer | Açıklama |
|---|---|---|
| `UretimYontemi` | `1` | Montaj Üretim Metodu |
| `Acik` | `0` | **0 = kapalı/bağımsız**; 1 = "kullanıcı ekranında açık" kilidi (1 koyarsan CEO "Başkası tarafından kullanılıyor" der) |
| `KullanimDisi` | `0` | Aktif reçete |
| `CreatedBy` | `SAVAS_USER_GUID` | `uniqueidentifier NOT NULL` |
| `CreationTime` | `datetime.now()` | `datetime NOT NULL` |
| `ModifiedBy` | `SAVAS_USER_GUID` | `uniqueidentifier NOT NULL` |
| `ModificationTime` | `datetime.now()` | `datetime NOT NULL` |

**UretimReceteHatPlani.Tipi:**
- `Tipi=2` → CEO ERP üst kutucukta **Yarı Mamül** gösterir (GMP-200-24xxx gibi ara reçeteler)
- `Tipi=1` → CEO ERP üst kutucukta **Mamul** gösterir (GMP-101-xxx gibi nihai ürünler)

**Kritik:** `UretimReceteHatPlaniGirdi.Tipi` NOT NULL — INSERT'te `Tipi=1/2` zorunlu; `SabitMiktar=0`, `GarantiKapsaminda=0` da gerekli.

**Kritik:** `UretimReceteHatPlaniGirdi.BirimId` ve `DepoId` NULL bırakılamaz — CEO ERP iş emri oluştururken bu alanları okur; NULL olursa `.NET NullReferenceException` fırlatır. Değerler: `BirimId=ADET_BIRIM_GUID`, `DepoId=2` (Merkez).

**UI:** `ui/tab_stok_hazirla.py:StokHazirlaTab`

---

## İş Emri Formu Sekmesi

- Tüm durumlardaki üretim emirleri listelenir (aktif + tamamlanmış)
- Checkbox ile tekli/çoklu seçim → **Toplu PDF** çıktısı (A4, şirket logolu)
- **Boş Excel Formu** — doldurulabilir xlsx (PDF ile aynı stil, A4 baskıya hazır)

**Fonksiyonlar:** `db/sorgular.py:tum_is_emirleri_listesi()`, `is_emri_malzeme_listesi()`  
**UI:** `ui/tab_is_emri_formu.py`  
**PDF:** `logic/pdf_is_emri.py` · **Excel:** `logic/excel_is_emri.py`

---

## Sıradaki Geliştirmeler

1. **PDF gömme** — teknik resim PDF'lerini `StokKarti.DokumanPath`'e bağlama
2. **Canlı SW testi** — SW Kodlama sekmesini iş makinesinde SolidWorks 2019 ile doğrulama
