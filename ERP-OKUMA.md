# CEO ERP Araçları

**GitHub:** https://github.com/savasadiguzel-hash/ceo-erp-arac  
**Dağıtım:** `dist/CEO-ERP-Araclar.exe` (~54 MB)  
**Son güncelleme:** 2026-06-10 (bakiye formülü düzeltildi — 11/11 CEO eşleşmesi)

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
  - `GirenMiktar`: `IslemKodu IN (1, 16, 20, 22)` + `IslemKodu=23 AND StokHareket.Id IN (paired_ids)` — Alış Faturası, Üretimden Giriş, Sayım Fazlası, Devir Girişi, Depolar Arası Giriş (yalnızca İrsaliye kökenli)
  - `CikanMiktar`: `IslemKodu IN (2, 3, 6, 17, 18, 19, 21)` — Satış, Alış İade Faturası, Satış İrsaliyesi, Üretime Çıkış, Depolar Arası Çıkış, Sayım Eksiği, Fire
  - Tarih filtresi: `BelgeTarihi <= UretimEmriTarihi`
  - **Not:** `IslemKodu=5` (Alış İrsaliyesi) dahil edilmez — IslemKodu=1 veya IslemKodu=23 ile eşli gelir, ayrıca sayılırsa çift sayım olur
- **IslemKodu=16 eklenmesi kritik:** Üretilmiş yarı mamüller bu formül olmadan yanlış negatif çıkar
- **IslemKodu=23 (Depolar Arası Giriş) — koşullu sayım:**
  - `_kod23_paired_ids_str(conn)` fonksiyonu, tüm DB'deki IslemKodu=23 kayıtları içinde aynı `BelgeSiraNo` + `IslemKartId` için bir `IslemKodu=5` (Alış İrsaliyesi) eşi olan kayıtların `StokHareket.Id` listesini döner.
  - Bu eşleşme, IslemKodu=23'ün irsaliye kökenli depo kredisini (GİR) temsil ettiğini kanıtlar.
  - Eşi olmayan IslemKodu=23 (saf depo-depo transferi), IslemKodu=18 ile netleşir — toplam bakiyeye etkisi sıfır.
  - Bu DB'de 8 adet eşleşen hareket ID'si bulunmaktadır: `740137,741399,741897,743385-743389`.
- **IslemKodu=3 (Alış İade Faturası):** Tedarikçiye iade; CIK'a eklenmesi HMGMDDAL004 gibi geçmişte iade yapılmış kalemlerin tarihsel bakiyesini CEO ile eşleştirir
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

### CEO ile Karşılaştırma Analizi (2026-06-10) — Sonuç: 11/11 ✅

CEO ERP "Stok Kartı Ekstresi_10062026183813.xlsx" (804 kart) ile DB bakiye formülü karşılaştırıldı.
Referans kart HMGMDDAL004 + rastgele 10 kart (seed=42) test edildi.

**Son formül sonuçları:**

| Stok Kodu | CEO | DB | Fark | Durum |
|---|---|---|---|---|
| HMGMDDAL004 | 591 | 591 | 0 | ✅ |
| RT0603BRD07665KL | 6 | 6 | 0 | ✅ |
| C0805C103J3GACTU | 238 | 238 | 0 | ✅ |
| 40VK6 | 6 | 6 | 0 | ✅ |
| YMGMKRT0056 | 550 | 550 | 0 | ✅ |
| GMP-200-240294 | -21 | -21 | 0 | ✅ |
| GMP-200-230540 | 0 | 0 | 0 | ✅ |
| GMP-101-230044 | 1 | 1 | 0 | ✅ |
| CL10A475KO8NNNC | 12 | 12 | 0 | ✅ |
| XP10NA1R5TL | 76 | 76 | 0 | ✅ |
| BLM31PG121SN1L | 206 | 206 | 0 | ✅ |

**Hedef doğrulaması:**
- HMGMDDAL004 05.01.2026 bakiyesi: **0** ✓ (talimat: 0)
- HMGMDDAL004 güncel bakiye: **591** ✓ (talimat: 591)

**Düzeltilen sorunlar:**
1. **IslemKodu=3 eksikti:** Alış İade Faturası CIK'a eklenmedi, HMGMDDAL004'ün 2021 iade hareketi (-200) sayılmıyordu → 05.01.2026'da 200 yerine doğru: 0.
2. **IslemKodu=23 koşulsuz sayılıyordu:** Tüm Depolar Arası Girişler GIR'a eklenince bazı kartlarda (+96, +1, +2) sapma oluştu. Düzeltme: yalnızca aynı `BelgeSiraNo`+`IslemKartId` için `IslemKodu=5` eşi olan kayıtlar sayılır (`_kod23_paired_ids_str()` ile).
3. **Excel parser hatası:** Eski parser "Stok Kodu:" satırı aradı; gerçek format kodu doğrudan col A'da, Ana Miktar col L'de (idx 11), Devir Toplamı col H'de. Düzeltilmiş parser: col E datetime ise hareket satırı; col X (idx 23) = devir.

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
