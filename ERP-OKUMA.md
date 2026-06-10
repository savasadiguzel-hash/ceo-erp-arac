# CEO ERP Araçları

**GitHub:** https://github.com/savasadiguzel-hash/ceo-erp-arac  
**Dağıtım:** `dist/CEO-ERP-Araclar.exe` (~54 MB)  
**Son güncelleme:** 2026-06-10 (tüm emirler toplu Excel export)

---

## Sekmeler

| Sekme | Ne yapar |
|---|---|
| 🔗 Mamül Ağacı | Reçetesiz + faturalı stokları tespit eder, mamüle bağlar |
| 💰 Maliyet | LIFO / FIFO / Ağırlıklı Ortalama — Excel maliyet raporu |
| ⚙ SW Kodlama | SolidWorks montaj → AI sınıflandırma → GEM/YMB kodu |
| 📦 Stok Kartı Aktar | SW sonrası CEO ERP'ye otomatik stok kartı açar |
| 🧾 Satış Faturaları | Tarih aralığına göre satış fatura/irsaliye listesi + Excel çıktısı |
| 🏭 Üretim Eksik Stok | "Devam Ediyor" üretim emirlerinde hat planı malzemeleri için eksik stok raporu |

---

## Mamül Ağacı Sekmesi

### Tarama Sayfası — Kesişim Kümesi

Reçetesiz + faturalı stokları bulur (faturada var ama hiçbir reçetede bileşen değil).

**Fiyat yöntemi seçimi:** FIFO (ilk alış) / LIFO (son alış) / Ağırlıklı Ortalama — tarama başlamadan seçilir.

**Excel çıktısı — 2 sayfa:**
- `Kesişim Kümesi` — stok bazında özet (7 sütun: Stok Kodu / Stok Adı / Fatura Sayısı / Birim Fiyat / İlk–Son Fatura / Tedarikçi)
- `Fatura Detayları` — her fatura satırı ayrı (9 sütun: + İşlem Türü / Belge No / Tarih / Miktar / Tutar)

**Kritik filtreler (değiştirme):**
- `sk.Id NOT IN (UretimReceteHatPlaniGirdi.KartId)` — bileşen/operasyon alt kodları kesişimden çıkar
- `shd.Turu = 1` — yalnızca ürün satırları; Turu=3 kur farkı/muhasebe satırlarında `IslemKartId` gerçek stoğu göstermez
- `StokHareketDetay JOIN sk.Id` üzerinden yapılır — aksi takdirde 2 milyon+ Kartezyen çarpım

**Bilinen veri kalitesi sorunu:** ERP'deki bazı `sk.Adi` değerleri sonda `\n\n` içerir. `kesisim_excel_kaydet` tüm string değerlere `.strip()` uygular; uygulanmazsa `wrap_text=True` + `vertical=center` + sabit satır yüksekliği metni görünmez kılar.

### Eşleştirme Sayfası

Tespit edilen stokları mamüle bağlar. Stok detay etiketleri fare ile seçilebilir (kopyalama/arama kolaylığı).

---

## Maliyet Sekmesi

- **Bağlan ve Mamülleri Yükle** → DB bağlantısı arka thread'de kurulur, pencere donmaz
- Yükleme tamamlanınca buton "✅ N mamül yüklendi" olur; arama kutusu anlık filtreler
- **Fiyat kaynağı:** `IslemKodu IN (1, 5)` — alış faturası + alış irsaliyesi; üretimden giriş, sayım, devir hariç
- **Performans:** `stok_fiyatlari_toplu()` ile N bileşen için tek SQL sorgusu; BOM listesi özyinelemeli hesaplamada önbelleğe alınır

---

## Satış Faturaları Sekmesi

- **Bağlan** → DB bağlantısı arka thread'de kurulur
- Tarih aralığı girip **Faturaları Getir** → `satis_faturalari()` çalışır
- `IslemKodu IN (2, 6)` — satış faturası + irsaliye; `shd.Turu = 1` ürün satırlarını filtreler
- 9 kolonlu tablo: Tarih / Belge Türü / Belge No / Müşteri / Stok Kodu / Stok Adı / Miktar / Birim Fiyat / Tutar
- Arama kutusu anlık filtreler (müşteri, stok kodu, belge no)
- **Excel'e Aktar** → openpyxl ile biçimlendirilmiş xlsx, son satırda toplam tutar
- `shd.Turu = 1` kayıt dönmüyorsa ERP versiyonuna göre değer farklı olabilir; `sorgular.py:satis_faturalari()` içinde ayarla

---

## Üretim Eksik Stok Sekmesi

- Uygulama açıldığında DB'ye otomatik bağlanır; "Devam Ediyor" emirler sol panelde listelenir
- Kullanıcı emir seçip **Analiz Et** tıklar; sağ panelde eksik malzemeler **BOM patlatmalı ağaç görünümünde** listelenir
- **Hat filtresi:** `HatTipi = 1` (ana üretim hattı) — HatTipi=2 (ek süreçler) dahil edilmez
- **Bakiye formülü — üretim emri tarihi bazlı:**
  - `GirenMiktar`: `IslemKodu IN (1, 16, 20, 22)` — Alış Faturası, Üretimden Giriş, Sayım Fazlası, Devir Girişi
  - `CikanMiktar`: `IslemKodu IN (2, 6, 17, 18, 19, 21)` — Satış, Satış İrsaliyesi, Üretime Çıkış, Depo Çıkış, Sayım Eksiği, Fire
  - Tarih filtresi: `BelgeTarihi <= UretimEmriTarihi`
- **IslemKodu=16 eklenmesi kritik:** Üretilmiş yarı mamüller bu formül olmadan yanlış negatif çıkar
- **Depo bazlı bakiye (2026-06-10 düzeltmesi):** CEO ERP, her malzeme için `StokDepoId` (hat planındaki hedef depo) bazında bakiye hesaplar. Depo bakiyesi negatifse (`sh.DepoKartId = StokDepoId`), o değer esas alınır; depo bakiyesi ≥ 0 ise toplam bakiye kullanılır. Bu düzeltme sayesinde CEO ERP ile eşleşme 11 `Yetersiz miktar!` öğesinden 8'inde sağlanmaktadır. Kalan 3 sapma ATP (tüm açık emirlerin kümülatif talep) ve CEO'nun iç rezervasyon mantığını gerektirdiğinden uygulanmadı.

### BOM Patlatma (Alt Montaj Açma)

- Hat planında alt montaj varsa (UretimRecete'de reçetesi bulunan) ve stok yetersizse, bileşenleri ağaç görünümünde gösterilir
- **Recursive:** Alt montajın bileşeni de alt montajsa, o da açılır (max 8 seviye)
- **Aggregasyon:** Bir malzeme hem ana hatta hem alt montajda bileşen olarak geçiyorsa, **toplam talep** kök satırda gösterilir (örn. HMGMSGR0008 = ana hat 80 + alt montaj 40 = toplam 120)
- **Net gereksinim:** Alt montaj için `üretilecek = max(0, talep - emri_tarihi_bakiyesi)`, bileşen talebi bu üretim miktarı üzerinden hesaplanır
- Kök satırda alt montaj: açık indigo arka plan; bileşenler altında girintili gösterilir
- Negatif eksik sütunu: kırmızı ve kalın
- Sıfır/negatif bakiye: kırmızı renk
- **Excel'e Aktar** butonu ağacı hiyerarşik olarak xlsx olarak kaydeder (bileşenler `└─` ön ekiyle)
- **Tüm Emirleri Excel'e Aktar** butonu (turuncu, üst sağ): tüm açık emirleri tek Excel'e döker
  - Her emir kendi tarihi esas alınarak hesaplanır; tek sayfada hiyerarşik satırlar
  - Sütunlar: Emir Kodu | Emir Tarihi | Açıklama | Malzeme Kodu | Malzeme Adı | İhtiyaç | Bakiye | Eksik
  - Emir header satırı yeşil; alt montaj satırları indigo; eksik değerler kırmızı/kalın
  - İşlem süresince progress bar her emir için güncellenir
- BOM sorgu fonksiyonu: `db/sorgular.py:uretim_emir_bom_patlat(conn, emir_id)`
- Toplu sorgu fonksiyonu: `db/sorgular.py:tum_emirler_eksik_stok(conn)`
- UI: `ui/tab_uretim_raporu.py:UretimRaporuTab`

### Muhasebe Eksik Raporu (ATP destekli)

- **Muhasebe Eksik Raporu (Excel)** butonu (mor, üst sağ): kronolojik ATP analizi
- Fonksiyon: `db/sorgular.py:muhasebe_eksik_raporu_olustur(conn)`
- **Farkları (Tüm Emirleri Excel'e Aktar'dan):**
  - Emirler `UretimEmriTarihi ASC` sıralanır (eski → yeni)
  - BOM düz (flat) liste: yarı mamüller + tüm recursive bileşenler ayrı satırlar
  - **Brüt talep**: bileşen ihtiyacı, üst montajın bakiye eksiğine göre ölçeklenmez; tüm talep listelenir
  - **Depo bazlı hibrit bakiye** kullanılır: hedef depo bakiyesi < 0 ise depo bakiyesi esas alınır; aksi halde toplam şirket bakiyesi kullanılır. Bu, "başka depoda stok var ama hedef depo boş" durumunu doğru yakalar.
  - **ATP kümülatif rezervasyon**: eski emirlerin talebi yeni emirlerin net bakiyesinden düşülür
  - Net Eksik = ERP Bakiyesi − İhtiyaç − Önceki Emirlerin Rezervasyonu (pozitif = eksiklik)
  - Sadece Net Eksik > 0 olan satırlar Excel'e yazılır
- **Excel sütunları (9 adet):** İş Emri Tarihi | İş Emri No | Açıklama | Stok Kodu | Stok Adı | İhtiyaç Miktarı | O Tarihteki ERP Bakiyesi | Önceki Emirlerin Rezervasyonu | Net Eksik Miktar
- Emir grupları mor ayırıcı header satırıyla ayrılır; Net Eksik ve negatif bakiye kırmızı/kalın
- `auto_filter` tüm sütunlara uygulanır (muhasebeci filtreleyebilir)

### CEO ile Karşılaştırma Analizi (2026-06-10) — Neden %100 tutmuyor?

ŞİRKET.962026-10 (05.01.2026) iş emrinin 11 `Yetersiz miktar!` kalemi, CEO ERP
"Stok Kartı Ekstresi" raporuyla satır satır karşılaştırıldı. Üç farklı bakiye
yöntemi denendi:

| Yöntem | Tanım | CEO ile eşleşme |
|---|---|---|
| **Depo-bazlı hibrit (mevcut)** | depo bakiyesi<0 ise depo, değilse total | **23/27** ✅ |
| Ekstre kodları ekli | +Alış İrsaliyesi(5) +Depo Transfer(23) | 19-20/27 ⬇ |
| ATP (kümülatif talep) | depo bakiyesi − tüm açık emir talebi | 15-16/27 ⬇ |

**Çıkan kesin sonuçlar:**

1. **Tarih karışıklığı (en sık yanılgı):** CEO ekstresinin *son* `Kalan Miktar`
   rakamı raporun alındığı *bugünkü* tarihe aittir, iş emri tarihine değil.
   Örn. HMGMDDAL004: ekstre sonu 591 (Haziran), ama iş emri günü (05.01.2026)
   Depo-2 bakiyesi ~0/−50 idi — ilk alış 06.01.2026'da, emirden bir gün sonra
   geldi. Script doğru tarihe bakıyor; ekstrenin son satırı 5 ay sonrasını gösterir.

2. **Alış İrsaliyesi (IslemKodu=5) bilerek sayılmıyor:** Faturası kesilmemiş,
   resmî stoğa girmemiş malı saymak gerçek eksikleri gizler. Eklendiğinde eşleşme
   düştü. CEO ekstresi geçmiş dökümünde gösterir ama eksik analizinde saymak yanlış.

3. **ATP/rezervasyon genellenemiyor:** CEO bazı kalemleri (HMGMKBL0002: 150 stok,
   318 toplam talep → Yetersiz) çapraz-emir talebine göre işaretliyor, ama
   tutarsız: SARF0000001 (469 stok, 3564 toplam talep) yine de "Yeterli". Bu
   nedenle basit hiçbir kural CEO'yu birebir veremiyor.

**Karar:** Mevcut depo-bazlı hibrit formül korunuyor (23/27, ulaşılabilir en iyi).
Üretimi gerçekten durduran boş/eksi bakiyeli kalemler eksiksiz yakalanıyor; kaçan
2-3 kalem CEO'nun görünmeyen iç rezervasyon motorundan kaynaklanan sınır durumlar.
İlgili `IslemKodu` evreni (bu DB'de tanım tablosu yok): 1,2,3,5,16,17,18,19,20,21,22,23.

---

## Veritabanı

| Parametre | Değer |
|---|---|
| Sunucu | `WIN-3FATBI9RQAA\CEO1` |
| Firma | 504 |
| Auth | SQL Server (`sa`), şifre `config.json`'da base64 |
| Kural | **SADECE OKUMA** — yazma yalnızca Stok Kartı Aktar akışında, kullanıcı onayıyla |

---

## Kurulum & Çalıştırma

```
git clone https://github.com/savasadiguzel-hash/ceo-erp-arac
cd ceo-erp-arac
pip install -r requirements.txt
python main.py
```

Gerekli `.env` (SW Kodlama + Stok Kartı için):
```
GEMINI_API_KEY=...
CEO_SQL_CONN=DRIVER={SQL Server};SERVER=WIN-3FATBI9RQAA\CEO1;UID=sa;PWD=...
```

Derleme: `build.bat` → `dist/CEO-ERP-Araclar.exe` + `dist/config.json`

---

## Klasör Yapısı

```
main.py / config.py / config.json / build.bat
db/      → baglanti.py, sorgular.py
logic/   → maliyet.py, excel.py
ui/      → ana_pencere.py, maliyet.py, mamul_agaci_tab.py, tarama.py, eslestirme.py, rapor.py
          tab_satis_faturalari.py, tab_erp_aktar.py, tab_sw.py, tab_uretim_raporu.py, baglanti.py, stil.py
sw/      → SW Kodlama modülleri (classifier, pipeline, renamer, erp_handler, vision_handler)
dist/    → CEO-ERP-Araclar.exe, config.json
```

---

## Sıradaki Geliştirmeler

1. **PDF gömme** — teknik resim PDF'lerini `StokKarti.DokumanPath`'e bağlama
2. **Canlı SW testi** — SW Kodlama sekmesini iş makinesinde SolidWorks 2019 ile doğrulama
