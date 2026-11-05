# CEO ERP Araçları

**GitHub:** https://github.com/savasadiguzel-hash/ceo-erp-arac  
**Dağıtım:** `dist/CEO-ERP-Araclar.exe` · `dist/CEO-ERP-Kurulum.exe` (Inno Setup)  
**Son güncelleme:** 2026-09-17 (Mamül Ağacı — toplu reçete bağlama)

---

## Sekmeler

| Sekme | Ne yapar |
|---|---|
| Mamül Ağacı | Alış belgeli, reçeteye bağlı olmayan stok ve masraf kartlarını tespit eder; mevcut mamül reçetesine bağlar |
| Maliyet | LIFO / FIFO / Ağırlıklı Ortalama maliyet raporu (Excel); ayrıca ERP'ye işlenmemiş taslak mamül ağaçlarını Excel'den okuyup maliyetlendirme |
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

**Tarama — Kesişim Kümesi:** Seçilen dönemde alış faturası veya henüz faturalaşmamış alış irsaliyesi bulunan, reçeteye bağlı olmayan **stok ve masraf kartlarını** bulur. Stok ve masraf aynı kodu taşısa bile ayrı aday olarak tutulur. Masrafın fiziksel stok bakiyesi olmadığından Güncel Miktar alanı boş kalır.

**Fiyat yöntemi:** FIFO / LIFO / Ağırlıklı Ortalama — tarama başlamadan seçilir.

**Excel çıktısı — 2 sayfa:**
- `Kesişim Kümesi` — kart bazında özet (11 sütun: Kart Türü / Kart Kodu / Kart Adı / Kart Adı-2 / Birim / Güncel Miktar / Fatura Sayısı / Birim Fiyat / İlk Fatura / Son Fatura / Tedarikçi)
- `Fatura Detayları` — her alış belgesi satırı ayrı (10 sütun, ilk sütun Kart Türü)

**Kritik filtreler:**
- Stok: `StokKarti` ve `shd.Turu = 1`; mevcut `UretimReceteHatPlani`, `UretimReceteHatPlaniGirdi` ve `UrunAgaciDetay` bağlantıları elenir.
- Masraf: `StokMasrafKarti` ve `shd.Turu = 3`; `UretimReceteHatPlaniGirdi.Tipi = 2` bağlantıları elenir. Bu sayede stok ve masraf kartlarının aynı sayısal Id değerleri karışmaz.
- Alış belgesi: `IslemKodu = 1` veya `IslemKodu = 5 AND FaturaId IS NULL`; pozitif miktar ve birim fiyat aranır.

**Bilinen sorun:** Bazı `sk.Adi` değerleri sonda `\n\n` içerir; `kesisim_excel_kaydet` `.strip()` uygular.

**Eşleştirme sayfası:** Tüm tarama sonuçları tek tabloda gösterilir. "Güncel Stok" sütunu tarama sırasında CEO ERP'den hesaplanan stok bakiyesini gösterir; masraf kartında fiziksel stok bulunmadığından boş gösterilir. Başlıklara tıklayarak artan/azalan sıralama yapılır; güncel stok, fatura sayısı, birim fiyat ve reçete miktarı sayısal sıralanır. Kod, ad ve tedarikçiye göre arama; stok/masraf ve bekleyen/bağlanan filtreleri; görünen bekleyenleri topluca seçme vardır. Kartlar fareyle tek tek veya birlikte işaretlenir; klavyede ok tuşlarıyla satıra gelip Boşluk tuşuyla işaret açılıp kapatılır. Reçete miktarı her satırda ayrı düzenlenir (varsayılan 1). Sağ tarafta mamül ve mevcut reçete grubu seçilir. Varsayılan görünüm yalnızca bekleyenleri gösterir: başarılı kayıttan hemen sonra bağlanan stok/masraf satırları işlem listesinden düşer ve tekrar seçilemez. "Bağlananlar" veya "Tüm durumlar" filtresiyle kayıtlar kontrol edilebilir. Rapor istendiği anda tüm tarama sonuçlarını, bağlanan ve bekleyen durumlarıyla birlikte gösterir. Mamul listesi `db/sorgular.py::mamul_agaci_listesi()`'nden gelir — bu fonksiyon 2026-09-14'te düzeltildi (çok-hatlı montaj reçeteli ürünler eskiden listeden düşüyordu, bkz. "Satılıp Üretilmemiş Ürünler Raporu" bölümü).

**Eşleştirme listesi Excel çıktısı:** "Listeyi Excel'e Aktar" düğmesi iki sayfalı `.xlsx` oluşturur. `Görünen Liste` etkin arama, tür/durum filtresi ve başlık sıralamasındaki satırları ekrandaki sırayla içerir; `Tüm Tarama` aynı oturumdaki tüm kartları içerir. Her iki sayfada seçim işareti, kart türü/kodu/adı, birim, güncel stok, fatura sayısı, birim fiyat, düzenlenmiş reçete miktarı, bağlama durumu, fatura tarihleri, tedarikçi ve varsa mamül/grup bilgileri bulunur. Yalnızca yerel dosya yazılır; CEO ERP verileri değiştirilmez.

**Bağlama düzeltmesi (2026-09-17):** `kartlari_receteye_toplu_bagla()` yeni `UretimReceteHatPlani` veya üretim emri satırı oluşturmaz; seçilen aktif reçetenin **mevcut grubuna** `UretimReceteHatPlaniGirdi` bileşenleri ekler (`Tipi=1` stok, `Tipi=2` masraf). Tek gruplu reçetede grup otomatik seçilir, çok gruplu reçetede kullanıcı seçer. Birim ilgili karttan, depo mevcut gruptan alınır. Aktif reçete ve grup ilişkisi doğrulanır; aynı kart mamül reçetesinde zaten varsa tekrar eklenmez. Toplu işlem tek transaction'dır: bir satırda hata olursa bütün seçilen satırlar geri alınır. Kayıt arka thread'de yürür; yalnızca başarılı commit sonrasında ekrandaki durumlar bağlandı olarak güncellenir. `karti_receteye_bagla()` tek kart çağrıları için aynı işlevi kullanır. 16 sütunlu Excel raporu grup, miktar ve bekleyen/bağlanan durumlarını gösterir. Tarama sonucuna dönmek kaydedilmiş bağlantıları geri almaz.

**Canlı doğrulama:** 01.01.2026–17.09.2026 taramasında 534 stok alış satırı / 463 aday stok, 1.354 masraf alış satırı / 313 aday masraf bulundu. Eski kod `GMP-200-240921` → `GMP-101-230008` denemesinde yalnızca hat planına satır ekliyor, gerçek reçete girdisi oluşturmuyordu. Yeni kod `0010541600500011` stokunu aynı mamül reçetesine 2,5 METRE olarak gerçek girdi tablosuna ekledi. Çok gruplu `GMP-101-230022` reçetesinde stok girdisi seçilen grupta ve reçete okuyucusunda göründü. `079` masraf kartı aynı reçeteye `Tipi=2` olarak eklendi ve reçete okuyucusunda Masraf düğümü olarak göründü. Bütün denemeler transaction içinde geri alındı; kalıcı deneme kaydı bırakılmadı.

**Toplu bağlama doğrulaması (2026-09-17):** `GMP-101-230022` reçetesinin `110238` grubuna `0010541600500011` stok ve `079` masraf kartları tek transaction içinde farklı miktarlarla eklendi; tür ve miktarlar sorguyla doğrulandı. Commit kapatılarak deneme sonunda rollback yapıldı. İkinci kart geçersiz olduğunda ilk kartın eklemesi de geri alındı. 776 satırlık tablo ve çoklu seçim arayüz testi ile `main.py` açılış testi başarılı oldu. Deneme kayıtları kalıcı bırakılmadı.

---

## Maliyet Sekmesi

- Bağlan → DB bağlantısı arka thread'de kurulur, pencere donmaz
- **Fiyat kaynağı:** `IslemKodu IN (1, 5)` — alış faturası + alış irsaliyesi
- **Performans:** `stok_fiyatlari_toplu()` ile N bileşen için tek SQL sorgusu
- **Çok seviyeli BOM:** alt bileşen de mamülse maliyet özyinelemeli hesaplanır; döngü korumalı (`_visiting` frozenset)
- **Stok Miktarı sütunu (en sağ):** Excel çıktısında son sütun. `stok_guncel_bakiyeleri()` ile **rapor bitiş tarihi** itibarıyla hesaplanır (Üretim Eksik Stok'taki bakiye formülünün aynısı — tarih parametreli). MAMÜL satırında mamülün kendi stoğu, BİLEŞEN satırında bileşenin stoğu gelir; MASRAF / İşçilik / Toplam satırları boş bırakılır (masrafın fiziksel stoğu yoktur).

### Masraf / Operasyon Kartları (StokMasrafKarti — reçetede Tipi=2)

Reçetedeki masraf bileşenleri (FREZE, KAPLAMA, TORNA vb. `:XX` kodları) `bom_listesi()` içinde ayrı sorguyla `tip="masraf"` olarak eklenir; maliyetleri **`masraf_birim_maliyet()`** ile hesaplanır. İki kritik kural:

1. **Turu filtresi YOK.** Masraf faturaları stoktan farklı olarak `Turu=3` kullanır (stok `Turu=1`). Bu yüzden `masraf_fiyat_gecmisi()` sorgusunda `Turu` filtrelenmez — aksi hâlde masraf faturalarının %99'u elenir, maliyet sıfır çıkar.
2. **StokKarti fallback.** Operasyon maliyeti çoğunlukla aynı `:XX` kodun **StokKarti** tarafına işlenir. `masraf_birim_maliyet()` önce masrafa bakar, fatura yoksa aynı kodu StokKarti'de arar (seçilen FIFO/LIFO/WA korunur). Bileşen mükerrer sayılmaz — yalnızca *fiyat kaynağı* değişir.

Metod (FIFO/LIFO/WA) hesabı tek yerde: `logic/maliyet.py::_metod_uygula()`.

**Sıfır maliyetli bileşen = veri boşluğu:** Hiç fatura/reçete/operasyon kodu olmayan parça 0 gösterir (kod hatası değil, ERP veri girişi eksiği). Örn. reçeteye kolonsuz girilen `GMP-200-24044060` (doğrusu `GMP-200-240440:60`) fatura eşleşmez.

### Excel'den Maliyet Hesapla (taslak mamül ağaçları)

CEO ERP'ye henüz işlenmemiş (reçetesi yüklenmemiş) taslak mamül ağaçlarını Excel'den okuyup aynı 13 sütunlu rapor formatıyla maliyetlendiren buton. "Bağlan ve Mamülleri Yükle" ile DB bağlantısı kurulduktan sonra kullanılabilir (fiyat sorguları için gerekli); mevcut tarih aralığı/yöntem alanları paylaşılır, ayrıca tek bir işçilik tutarı sorulur.

- **Okuyucu:** `logic/mamul_agaci_excel_oku.py::excel_dosyasindan_bom_oku()` — Excel'i `db.sorgular.bom_listesi()` ile **aynı şekildeki** bir `bom` dict'ine çevirir, böylece `mamul_maliyet_hesapla()` değişmeden çalışır.
- **Format tespiti başlık adına göre** (pozisyona göre değil): "Miktar" sütunu bulunursa gerçek adetlerle düz/hiyerarşik liste; "Tip" + "Seviye" sütunları da varsa çok seviyeli ağaç (Mamül/Yarımamül/Reçete düğümleri özyinelemeli). Sadece "Stok Kodu" varsa (gerçek ADLASMKE şekli, miktar bilgisi yok) tüm adetler 1 varsayılır. Hiçbir başlık tanınmazsa Stok Hazırlık'ın pozisyonel tespiti (Seviye-Tip / girintili Tip / düz kod-ad) tekrarlanır.
- **Kategori başlığı satırları** (kod dolu, miktar boş — ör. "ELEKTRONİK") otomatik atlanır.
- **Aynı kod birden fazla kez geçerse** (düzleştirilmiş listede farklı alt-montajlardan gelen aynı parça) miktarlar **toplanır** — ilk değeri kullanıp atlamak yanlış (düşük) maliyete yol açar.
- **Miktar "20M"/"100M" gibi birim ekli metinse** baştaki sayısal kısım alınır (uyarı olarak raporun sonuna eklenir).
- **Stok/masraf ayrımı bilinmiyorsa** (Tip sütunu yoksa ya da satır düz listede): `birim_maliyet_oto()` önce StokKarti fatura fiyatına bakar, bulamazsa StokMasrafKarti'ye düşer — mevcut `masraf_birim_maliyet()`'in tersi sıralı fallback'i (`logic/maliyet.py`, `tip="stok_oto"`).
- **`:XX` operasyon kodu otomatik tarama** (`db/sorgular.py::bom_operasyon_kodlarini_tamamla()`): Excel'deki her ana parça kodu için CEO ERP'de (StokKarti **veya** StokMasrafKarti) `ana_kod:XX` formatında kayıtlı bir alt kod varsa — Excel'de hiç yazılmamış olsa bile — otomatik bulunup **ana parçanın hemen altına**, miktar olarak ana parçanın miktarı kullanılarak eklenir. Rapor tipinde `"MASRAF (OTO)"` etiketiyle elle eklenmiş masraf satırlarından (`"MASRAF"`) ayırt edilir. Bulunan kodlar ayrıca rapor sonunda bilgi listesi olarak da özetlenir.
- **UI:** `ui/maliyet.py::ExcelBomMaliyetThread` — mevcut `MaliyetHesaplamaThread` ile aynı sinyal deseni (`ilerleme`/`bitti`/`hata`), aynı `_ui_kilitle`/`_ui_serbest_birak` kilidini paylaşır (iki hesaplama aynı anda çalışamaz).

### Üretim Emri Masraf Maliyetleri

Maliyet sekmesindeki **"🔧 Üretim Emri Masraflarını Doldur"** butonu, girilen
üretim emrinin `Tipi=2` masraf satırlarını önce satır bazında ön izler. Fiyat
kaynağı, üretim emri tarihine kadar olan son aktif masraf alış hareketidir
(`Turu=3`, `IslemKodu=1` veya faturalaşmamış `IslemKodu=5`). Alış irsaliyesi
faturaya dönüştüyse `FaturaId` dolu irsaliye tekrar sayılmaz.

- Önerilen toplam: `TalepMiktar × kaynak BirimFiyat`.
- Mevcut `Tutar` değeri sıfır olmayan satırlar korunur.
- Üretim emri tarihinden önce fiyatı bulunmayan satırlar değiştirilmez ve
  ön izlemede açıkça gösterilir.
- Uygulama yalnızca `UretimEmriHatPlaniGirdi.Tutar` alanına yapılır; fatura,
  irsaliye ve stok hareketleri değişmez.
- Uygulama öncesi satır değerleri `%LOCALAPPDATA%\CEO ERP Araclar\yedekler`
  altında `masraf_maliyet_yedek_*.json` dosyasına yazılır.

Veri erişimi `db/sorgular.py::uretim_emri_masraf_maliyet_onizle()` ve
`uretim_emri_masraf_maliyet_uygula()` fonksiyonlarındadır; uygulama transaction
ile çalışır. CEO ERP'de güncel üretim maliyet hareketlerinin oluşması için
aktarımı yaptıktan sonra native **İşlemler → Maliyetlendir** işlemi ayrıca
çalıştırılmalıdır.

### Proje Fiili Satınalma Karşılaştırması (Teorik BOM vs Fiili Alım)

Maliyet sekmesinde, seçilen mamül(ler)in BOM'dan hesaplanan **teorik** maliyetini, belirli bir CEO ERP proje koduna fiilen kesilmiş alış faturalarıyla (**fiili** satınalma) kalem bazında karşılaştıran ayrı bir buton: "📊 Proje Fark Raporu (Excel)".

- **Proje kodu şeması:** CEO ERP'de proje kodu **belge başlığında değil, satır bazında** tutulur — `StokHareketDetay.ProjeId` → `Proje.Id` (`Proje.ProjeKodu` / `Proje.ProjeAdi`). Aynı faturanın bazı satırları bir projeye, bazıları başka bir projeye/hiçbir projeye ait olmayabilir. Sorgu: `db/sorgular.py::proje_satinalma_hareketleri()`.
- **Kapsam:** Hem stok (`StokKarti`, `shd.Turu = 1`) hem masraf/operasyon (`StokMasrafKarti`) tarafı `UNION ALL` ile tek listede birleştirilir — CEO'nun kendi "Stok Hareketleri Raporu"ndaki "Detay İşlem Türü" (Stok/Masraf) ayrımıyla aynı.
- **Alış iadeleri:** `IslemKodu=3` CEO ERP'de alış iadesidir. Miktar ve tutar ERP'de pozitif saklansa da `proje_satinalma_hareketleri()` bunları `-ABS(...)` olarak döndürür. Böylece `proje_fiili_maliyet()` net satınalma hesabında iadeleri düşer; `Satınalma Detayı` sayfasında işlem türü `Alış İadesi` ve miktar/tutar negatif görünür.
- **Sabit Kıymet HARİÇ:** `StokHareketDetay.SabitKiymetId` ile işaretli demirbaş/ekipman alımları bu rapora dahil edilmez (BOM'a girmeyen kalemler, kasıtlı dışlama).
- **⚠ Faturalaşan irsaliye — mükerrer sayım düzeltmesi:** Bir irsaliye (`IslemKodu=5`) sonradan faturaya dönüştüğünde CEO ERP `StokHareket.FaturaId` alanını doldurur; hem irsaliye hem faturası ayrı satır olarak durur. Sadece `IslemKodu=1` (Alış Faturası) VE `FaturaId`'si BOŞ olan `IslemKodu=5` (henüz faturalaşmamış irsaliye) satırları toplanır — aksi hâlde aynı alım iki kez sayılır. Aynı desen (2026-09-14) `stok_fiyat_gecmisi()`, `masraf_fiyat_gecmisi()`, `stok_fiyatlari_toplu()`, `recetesiz_stok_hareketleri()`, `recetesiz_masraf_hareketleri()`, `son_alis_fiyati_toplu()` ve satış tarafında `satis_faturalari()` (`IslemKodu = 2 OR (IslemKodu = 6 AND FaturaId IS NULL)`) fonksiyonlarına da uygulandı.
- **Doğrulama:** ADLAS-MKE projesi için CEO ERP'nin kendi "Stok Hareketleri Raporu" Excel çıktısıyla satır satır karşılaştırıldı — düzeltme sonrası **Stok: 542 satır / 4.475.809,98 ₺** ve **Masraf: 128 satır / 588.592,95 ₺** birebir eşleşti (toplam 5.064.402,93 ₺).
- **Fark hesaplama:** `logic/maliyet.py::proje_fiili_maliyet()` satırları `bil_kod` bazında gruplar; `proje_fark_raporu()` bunu teorik BOM satırlarıyla (`bil_kod` birleşimi/union) eşleştirip miktar/tutar farkını ve durumu (`"Sadece Satınalmada"` / `"Sadece BOM'da"` / `"Miktar Farkı"` / `"Eşleşiyor"`) üretir.
- **1 birim üretim varsayımı:** Uygulamanın geri kalanındaki BOM hesaplama mantığıyla tutarlı — her seçili mamül için 1 adet üretim varsayılır, adet çarpanı yoktur.
- **Excel çıktısı** (`logic/excel.py::_proje_fark_workbook_yaz()`, ortak) 3 sayfa (+ uyarı varsa 4.): **Özet** (proje kodu, dönem, teorik/fiili toplam, fark ₺ ve %), **Fark Detayı** (kod bazında karşılaştırma, durum renk kodlu), **Satınalma Detayı** (ham fatura satırları — belge no, tarih, tedarikçi), **Uyarılar** (opsiyonel).
- **UI:** `ui/maliyet.py::ProjeFarkThread` — mevcut thread deseniyle aynı (`ilerleme`/`bitti`/`hata`), `_ui_kilitle`/`_ui_serbest_birak` kilidini paylaşır.
- **İkinci varyant — Excel taslak BOM ile:** "📄 Excel BOM ile Fark Raporu" butonu, "Excel'den Maliyet Hesapla" ile aynı mantıkla (`excel_dosyasindan_bom_oku()` + `bom_operasyon_kodlarini_tamamla()`) CEO ERP'ye **henüz işlenmemiş** bir taslak mamül ağacını okuyup aynı proje koduyla karşılaştırır. Fonksiyon: `logic/excel.py::proje_fark_excel_bom_kaydet()` (`ui/maliyet.py::ProjeFarkExcelBomThread`). İşçilik **sorulmaz** (satınalma tarafının işçilik kalemi yok). Uçtan uca doğrulandı: sentetik tek satırlık taslak + "ADLAS-MKE" ile fiili taraf, ERP-BOM varyantıyla birebir aynı toplamı (5.064.402,93 ₺) verdi — iki fonksiyon aynı `_proje_fark_workbook_yaz()` yardımcısını paylaştığı için beklenen davranış.
- **⚠ Proje kodu serbest metin — yazım hatası riski ve otomatik tamamlama:** Proje kodu kutusu serbest metindir; gerçek `Proje.ProjeKodu` değeriyle birebir uyuşmazsa (ör. kullanıcı "ADLAS MKE" yazdı, gerçek kod tire ile "ADLAS-MKE") sorgu **sessizce 0 satır** döner ve rapor yanıltıcı biçimde "%100 fark, hiç satınalma yok" gösterir — bu canlı kullanımda bizzat yaşandı. İki katmanlı önlem: (1) "Bağlan ve Mamülleri Yükle" sonrası `proje_kodlari_listele()` ile CEO ERP'deki tüm gerçek proje kodları çekilip proje kodu kutusuna `QCompleter` (case-insensitive, `MatchContains`) olarak bağlanır; (2) `fiili` toplam tam 0 çıkarsa sonuç mesajına açık bir uyarı eklenir.

### LRF 6001 Maliyet Çalışması (`tools/lrf6001_maliyet/`, 2026-10-30)

CEO ERP'de reçetesi olmayan **LRF 6001 (Lazer Mesafe Ölçer)** ürününün malzeme maliyeti, kullanıcının `LRF 6001 ÜRÜN BOM.xlsx` dosyasından **son alış fiyatı + kur farkı** ile hesaplandı. Standalone script seti (UI'da buton yok); yalnızca okuma yapar.

- **`bom_oku.py`** — Excel'i okur: "Urun BOM" sayfası (bölüm başlıkları ELEKTRONİK / AKSESUAR / KABLAJ / MEKANİK / OPTİK, kod önceliği KONFİGÜRASYON NO → ESKİ KOD, `(revizyon olacak)` eki atılır) + 6 elektronik kart sayfası (`Comment`=MPN, `Quantity`).
- **`maliyet_hesapla.py`** — her kalem için ERP'deki **en son** alış (`IslemKodu=1` veya faturalaşmamış `5`, tarih sınırı yok; stok `Turu=1` + masraf kartı). Kur farkı:
  - USD/EUR faturalı satır: `StokHareketDetay.DovizBirimFiyati × bugünkü kur` (EUR faturada EUR kuru — USD'ye çevirmek yanlış olurdu)
  - TL faturalı satır: `TL ÷ alış günü USD × bugünkü USD`
  - Kur kaynağı: `GunlukKur.Kur1` (döviz alış), `DovizBirimId` USD `93F5D195-…`, EUR `6F454FBD-…`; tarihte kayıt yoksa öncesindeki son kayıt. ⚠ Tarih parametresi **datetime nesnesi** olarak geçilmeli — `'2021-02-12'` string'i Türkçe locale'de YYYY-DD-MM okunuyor. ⚠ Tabloda ileri tarihli (2026-12-31) hatalı bir USD satırı var; sorgu `Tarih <= bugün` ile süzer.
  - Mekanik parçalar: maliyet = parçanın `:XX` operasyon kodlarının (StokKarti veya StokMasrafKarti) son alışlarının toplamı (+ varsa parçanın kendi alışı).
  - Elektronik kartlar: Excel kart sayfaları esas; ERP'deki LRF 6001 kart reçetelerinden (`GMP-300-230015…019`) yalnızca çıplak PCB (`GMP-301-23002x`) eklenir. Excel'deki kart kodları (`GMP-300-230007…012`) ERP'de YOK.
  - `ESLESME` sözlüğü: Excel kodu → ERP kodu (ör. `NOPTEL LRF 221` → `OEM-LRF-NP`, `MICROOLED MDP05A` → `MDP05APRMRO`, kısaltılmış MPN'ler).
  - Çıktı: 4 sayfalı rapor (Özet / Fiyatı Olmayanlar / Detay / Kontrol Edilecekler) + `<çıktı>.json` (satır bazında hesap).
- **`bom_fiyat_isle.py`** — orijinal BOM'un **kopyasına** fiyatları kodların karşısına yazar (ana sayfa J–S, kart sayfaları E–N; kart toplamı formülle ana sayfaya bağlı; toplamlar formül). Orijinal dosyaya dokunmaz.
- **`fiyatsiz.py`** — fiyatı bulunamayan (0 ₺) kalemler sayfası, neden + yapılacak iş.

**Sonuç (30.10.2026, USD 49,6997 / EUR 55,4243):** alış günü 52.707,09 ₺ → güncel kur **93.028,62 ₺ (1.871,81 $)**, BC300 çanta (`GMP-110-230004`, kullanıcı bilgisi) dahil. 20 kalem fiyatsız (MTi-3 IMU, pil kartı PCB, 18 mekanik). Dahil değil: işçilik, SMT dizgi, montaj, test, tripod/omuz çantası/boyun askısı.

**Açık konu:** OEM modül `OEM-LRF-NP` son alışı 24.10.2025 NPT12167 (LRF 6002 projesi) 263,92 EUR/adet — 2021'de 2.311 EUR idi. Teknik resimdeki modül **QS42753BE**, ERP kartı adında QS42526AE yazıyor; QS42753BE ERP'de hiç geçmiyor. Fatura doğrulanmadan sonuç kesin değil (2021 fiyatıyla toplam ≈ 203.000 ₺).

---

## Satış Faturaları Sekmesi

- `IslemKodu = 2 OR (IslemKodu = 6 AND FaturaId IS NULL)` — satış faturası + henüz faturalaşmamış irsaliye; `shd.Turu = 1`
- 9 kolonlu tablo + anlık arama (müşteri, stok kodu, belge no)
- Excel çıktısı: biçimlendirilmiş xlsx, son satırda toplam tutar
- **Filtre:** `shd.Miktar > 0` — miktarsız satırlar hariç; `BirimFiyat = 0` olan (ücretsiz) kalemler dahil edilir
- **⚠ Faturalaşan irsaliye — mükerrer sayım düzeltmesi (2026-09-14):** Bir satış irsaliyesi (`IslemKodu=6`) sonradan faturaya dönüştüğünde CEO ERP `StokHareket.FaturaId` alanını doldurur; hem irsaliye hem faturası ayrı satır olarak durur. Eskiden sorgu `IslemKodu IN (2, 6)` deseniyle ikisini birden sayıyordu — aynı satış iki kez raporlanıyordu. `proje_satinalma_hareketleri()`'ndeki alış tarafı düzeltmesinin satış aynası uygulandı (bkz. `db/sorgular.py::satis_faturalari()`).

### Birim ana verisi ve geçmiş birim hataları

CEO ERP'nin birim sözlüğü şirket veritabanında değil, ortak `CeoCommon.dbo.StokBirim` tablosunda tutulur. `StokKarti.StokBirim`, `StokHareketDetay.StokBirimId`, `UretimReceteHatPlaniGirdi.BirimId` ve `UretimEmriHatPlaniGirdi.StokBirim` alanları bu sözlükteki GUID'lere bağlanır. Raporlar ortak tabloyu kullanmalı; şirket DB'sinde bulunmayan `StokBirim` tablosu nedeniyle bilinmeyen GUID'leri `ADET` göstermek hatalıdır.

2026-09-15 incelemesinde kullanıcı tarafından verilen Kardağ ve Tek-El belgelerinin canlı kayıtları doğrulandı: `HMGMKBL0040` hareketi `METRE`, `HMALMÇBK114` ve `HMALMDRT003` hareketleri `KG` birim GUID'leriyle kayıtlıdır. Bu üç satır için mevcut hareket miktarı fiziksel birimle uyumludur; önceki rapordaki `ADET` etiketi veri tabanından değil, uygulamanın yanlış fallback'inden kaynaklanmıştır.

Geçmişte ADET GUID'iyle kesirli miktar girilmiş 21 alış/alış irsaliyesi satırı tespit edilmiştir. Bu kayıtlar otomatik olarak başka birime çevrilmemelidir: hedef birim fatura/irsaliye, stok kartı, reçete ve üretim hareketleri birlikte incelenerek belirlenmeli; miktarın fiziksel birim mi yoksa dönüşüm sonrası değer mi olduğu doğrulanmalıdır. Vergi belgesi ve muhasebe kayıtları için düzeltme CEO ERP'nin resmi iade/düzeltme akışıyla yapılmalı, doğrudan SQL güncellemesi son seçenek olarak transaction ve ön izleme ile ele alınmalıdır.

**Bu olay için önerilen düzeltme sırası:**

1. Önce `CeoCommon.dbo.StokBirim` üzerinden denetim raporu alınır; her satırda kart birimi, reçete birimi, üretim emri birimi, belge birimi ve miktar birlikte gösterilir. ADET ile KG/METRE farkı otomatik aday olarak işaretlenir, ancak hedef birim insan onayı olmadan yazılmaz.
2. Bu incelemede aktif reçetelerde kart birimi ile reçete satırı birimi arasında **50 uyumsuzluk** bulundu: **29 KG**, **21 METRE** satırı reçetede ADET kayıtlı. `GMP-101-230134` ve `GMP-101-230136` altındaki alüminyum ve kablo satırları bu kümededir. Reçete satırlarının `BirimId` değeri, miktarlar fiziksel temel birimde tutuluyorsa kartın doğru birim GUID'iyle eşleştirilmelidir.
3. Üretim emri oluşturulurken reçete birimi emre kopyalandığı için mevcut emirler ayrıca kontrol edilir. Canlı kontrolde `ŞİRKET.1092026-2` emrinde 5 KG ve 2 METRE satırının `StokBirim` alanı ADET, `TalepMiktari` ise sırasıyla 15,49 KG ve 2 METRE karşılığıdır. Bu emir için resmi CEO ERP ekranından birimlerin yenilenmesi veya emrin doğru reçeteden yeniden oluşturulması gerekir; yalnız reçeteyi düzeltmek mevcut emir satırını geriye dönük değiştirmeyebilir.
4. Fatura/irsaliye hareketi ile kart birimi de yanlışsa ilgili belge CEO ERP'nin resmi iade/düzeltme akışıyla düzeltilir. İncelenen Kardağ ve Tek-El belgelerinde hareket birimleri zaten doğru olduğundan bu iki belge için hareket miktarı değiştirilmemelidir.
5. Düzeltme sonrasında aynı denetim tekrar çalıştırılır; açık üretim emri ihtiyaçları, stok bakiyeleri, malzeme düşümleri ve maliyet raporları karşılaştırılır. Doğrudan SQL yazımı uygulanmaz; zorunlu kalırsa önce yalnızca ön izleme çıktısı ve geri alınabilir transaction hazırlanır.

**Uygulama aracı:** `tools/birim_tutarlilik_duzelt.py` varsayılan olarak yalnızca ön izleme yapar. `--recete-kodu KOD --sadece-recete --uygula` ile tek reçete, `--uygula` ile tanımlı tüm reçete ve devam eden emir adayları transaction içinde düzeltilebilir. Her gerçek çalıştırmada işlem öncesi değerler `birim_duzeltme_yedek_*.json` dosyasına alınır; miktar/fiyat ve fatura/irsaliye hareketleri değiştirilmez. Kullanıcı onayıyla 2026-09-15 tarihinde üç reçetedeki toplam **50 satır** düzeltildi (`GMP-101-230134`: 7, `GMP-101-230136`: 41, `MMSBIŞIK002`: 2). İşlem sonrası aktif reçete birim uyumsuzluğu **0** kaldı; devam eden üretim emirlerindeki **7** uyumsuz satır sonraki aşamaya bırakıldı.

### Satılıp Üretilmemiş Ürünler Raporu (`tools/satilip_uretilmemis.py`, 2026-09-14)

Bağımsız script — UI'da buton yok, `python tools/satilip_uretilmemis.py [--bas GG.AA.YYYY] [--bit GG.AA.YYYY] [--dosya DOSYA.xlsx]` ile çalıştırılır (varsayılan aralık `01.01.2026` → bugün). Kullanım amacı: kullanıcı bu raporla eksik kalan mamulleri CEO ERP'nin "Üretim Emri Hareketi" ekranından üretime alarak kapatıyor.

- **"Ürün" tanımı:** `mamul_agaci_listesi()`'nin döndürdüğü küme — aktif reçetesi (`UretimRecete`) olan StokKarti'ler. StokKarti'de Mamul/Yarımamül/Hammadde ayrımı için ayrı bir DB alanı **yok**; bu, reçete ilişkisinden türetilen tek DB-tabanlı tanım.
- **⚠ `mamul_agaci_listesi()` düzeltmesi (2026-09-14):** Fonksiyon eskiden `UretimReceteHatPlani.KartId = StokKarti.Id` eşleşmesine bakıyordu — bu YANLIŞ'tı. `UretimReceteHatPlani.KartId`, ürünün kendisini değil, o reçetenin bir **alt-montaj/bileşen GRUBUNU** temsil eder (bkz. `UretimRecete → UretimReceteHatPlani → UretimReceteHatPlaniGirdi` hiyerarşisi altında, "Stok Hazırlık Sekmesi" bölümü). Tek-hatlı "basit" reçetelerde bu hat tesadüfen ürünün kendi kartına eşitti (self-reference), ama çok-hatlı montaj reçetelerinde (ör. `GMP-101-230022` — 5 ayrı hat grubu, "OKÜLER LENS GRUBU" / "BORESİGHTER SP AKSESUAR" vb., hiçbiri kendi kartına referans vermiyor) ürün tamamen listeden düşüyordu — canlı kullanımda 12,4M ₺'lik bir satışın kaçırılmasına yol açtı. Doğrusu (artık uygulanan): `UretimRecete.Kodu = StokKarti.Kodu` eşleşmesi — `uretim_emir_bom_patlat()`'ın zaten kullandığı doğru desenle aynı. Düzeltme sonrası mamul sayısı 261 → **217** (eskiden bazı "bileşen grubu" kartları yanlışlıkla ürün sayılıyordu). Bu fonksiyon aynı zamanda `ui/eslestirme.py`'nin (Mamül Ağacı → Eşleştirme sayfası) mamul dropdown'ını besliyor — düzeltme orayı da iyileştirdi.
- **"Üretilmedi" tespiti:** CEO ERP'de `UretimEmri` ile üretilen ürün/miktar arasında sorgulanabilir bir bağlantı (JOIN/FK) kod tabanında yok. Bunun yerine mevcut bakiye formülü (`stok_guncel_bakiyeleri()`) kullanılır — IslemKodu=16 (Üretimden Giriş) bu formülün giriş tarafında zaten hesaba katılı; bir ürünün bugünkü ERP bakiyesi negatifse, satışın üretim + mevcut stokla karşılanamadığı anlamına gelir (Üretim Eksik Stok sekmesindeki "eksik" mantığıyla birebir aynı).
- **Kapsam:** yalnızca bakiyesi negatif (gerçekten eksik) ürünler rapora girer; stoktan karşılanmış satışlar listelenmez.
- Mevcut hiçbir bakiye/depo sorgu fonksiyonu değiştirilmedi (`satis_faturalari`, `stok_guncel_bakiyeleri` olduğu gibi kullanıldı) — bu rapor bakiye/depo mantığına dokunmuyor, `tools/mutabakat.py` gerektirmiyor. (`mamul_agaci_listesi()` düzeltildi ama bu bir bakiye/depo formülü değil, "hangi StokKarti mamul sayılır" tanımıdır.)
- **Sayfa 1 — "Üretilmesi Gereken":** Stok Kodu / Stok Adı / Satılan Miktar / Satış Tutarı / Güncel ERP Bakiyesi / Üretilmesi Gereken Miktar / İlk-Son Satış Tarihi / Belge Sayısı, eksik miktara göre azalan sıralı, toplam satırlı.
- **Sayfa 2 — "Alt Parça İhtiyacı" (`db/sorgular.py::ihtiyac_bom_patlat()`):** Sayfa 1'deki her ürünün eksik miktarını `bom_listesi()` reçetesiyle en alt kademeye kadar (max 8 seviye) recursive patlatır — Üretim Eksik Stok sekmesindeki `_patlat()` ile aynı net/mahsuplu mantık (bir alt montajın kendi bakiyesi ihtiyacı karşılıyorsa onun altına inilmez). Stok kodları (yalnızca eksik > 0 olanlar, azalan sıralı) + masraf/operasyon kalemleri (`:XX` kodlar dahil, bilgi amaçlı — stok bakiyesi kavramı yok) tek sayfada, "Hangi Ürün(ler) İçin" sütunuyla kaynağı gösterilir.
- **Son Alım Fiyatı sütunu (`db/sorgular.py::son_alis_fiyati_toplu()`):** Hem stok hem masraf kodları için, **tarih sınırı olmadan** (kaydın bulunduğu en eski tarihe kadar) geriye giderek en son alım fiyatını bulur — `stok_fiyat_gecmisi()`/`masraf_fiyat_gecmisi()`'nin aksine `bas` parametresi almaz. Aynı faturalaşan-irsaliye mükerrer sayım düzeltmesini kullanır (`IslemKodu=1 OR (IslemKodu=5 AND FaturaId IS NULL)`). Hiç alım bulunamayan kodlar sonuç sözlüğünde yer almaz → Excel'de hücre boş bırakılır (canlı DB'de doğrulandı: `GMP-200-240570` örneğinde gerçekten sıfır hareket satırı var, "veri boşluğu" iddiası tahmini değil).
- **Açık Üretim Emri İhtiyacı sütunu (`db/sorgular.py::acik_uretim_emri_ihtiyaclari()`):** `DurumId=3` (Devam Ediyor) durumundaki üretim emirlerinde, `UretimEmriHatPlaniGirdi.TalepMiktar` değerleri stok kodu bazında toplanır. `HatTipi IN (1,2)` kapsamı kullanılır. Bu değer reçetedeki birimlik `Miktar` alanından farklıdır; açık üretim emirlerinin ilgili stoktan talep ettiği toplam miktarı gösterir. Masraf/operasyon satırlarında boş bırakılır.
- **Reçeteli (yarı mamül) alt parçalar için hesaplanan maliyet (2026-09-14):** Bir alt parça (ör. `GMP-200-240506`) CEO ERP'de hiç satın alınmamışsa (sadece üretiliyorsa) "Son Alım Fiyatı" doğal olarak boştu. Artık böyle kodlar için (`kod in bom`) kendi bileşenlerinin (miktar × bileşen fiyatı, gerektiğinde özyinelemeli) toplamı hesaplanıp aynı sütuna yazılıyor — `logic/maliyet.py::mamul_maliyet_hesapla()` ile aynı mantık, farkı tarih aralığı sınırı olmaması (`son_alis_fiyati_toplu()`'nun tarihsiz arama mantığını kullanır). Excel'de "Son Alım Tarihi" sütununda **"Hesaplanan (alt bileşenlerden)"** notuyla ve mavi italik yazı tipiyle gerçek alım fiyatlarından ayrıştırılır. Fiyatı hiç bulunamayan alt bileşenler 0 katkı yapar (Maliyet sekmesinde zaten dokümante edilmiş "veri boşluğu" davranışıyla tutarlı); hiçbir bileşeninde veri yoksa hücre yine boş kalır. Fonksiyon: `tools/satilip_uretilmemis.py::_hesapla_maliyet()` (rapora özel, `db/sorgular.py`'ye taşınmadı — sadece bu script tarafından kullanılıyor).
- **⚠ Operasyon kodu StokKarti tarafında girilmişse `:XX` sonekiyle yakalanır (2026-09-14 düzeltmesi):** `ihtiyac_bom_patlat()` bir bileşeni `tip='masraf'` olarak `UretimReceteHatPlaniGirdi.Tipi` alanından belirliyordu — ama Maliyet sekmesinde zaten belgelenen alışkanlık burada da geçerli: bazı operasyonlar (ör. `GMP-200-230609:110` ÇAPAK ALMA, `:20` FREZE, `:60` KAPLAMA) `StokMasrafKarti` yerine `StokKarti` tarafına `Tipi=1` ile girilmiş. Düzeltme öncesi bunlar "gerçek stok" sayılıp eksik-filtresine giriyor, bakiyeleri yeterli göründüğü için raporda **sessizce kayboluyordu** — reçeteli bir alt parçanın (`GMP-200-230609`) kendi bileşenleri hiç görünmüyordu. Artık `kod.count(':') == 1` kontrolüyle (Tipi alanından bağımsız) StokKarti tarafındaki operasyon kodları da masraf/operasyon olarak sınıflandırılıp eksik-filtresi dışında, kaynak ürünüyle birlikte gösteriliyor.

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

**Gereksinim:** Inno Setup 6 ([jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php) veya `winget install --id JRSoftware.InnoSetup -e`) — yalnızca paketi derleyen makinede.
`create_installer.bat`, ISCC.exe'yi hem Program Files hem de winget'in kurduğu `%LOCALAPPDATA%\Programs\Inno Setup 6\` altında arar.

```
build.bat              ← önce exe derle (kaynak exe'den yeniyse)
create_installer.bat   ← ardından kurulum paketi oluştur
```

Çıktı: `dist\CEO-ERP-Kurulum.exe` (~72 MB, her şey dahil)

**Önemli:** `setup.iss` artık `dist\config.sablon.json` (boş şablon) yerine gerçek `dist\config.json`'ı paketliyor —
şirket içi tüm PC'ler aynı CEO ERP veritabanına (`WIN-3FATBI9RQAA\CEO1`) bağlandığı için kurulumda bağlantı
bilgileri/şifre sorulmaz, otomatik gelir. `dist\config.json`'ın güncel/doğru olduğundan emin olmadan
`create_installer.bat` çalıştırma — şifre base64 ile gizlenmiş, şifreleme değil; bu exe'yi şirket dışına
veya güvenilmeyen bir yere paylaşma.

**Program Files yazma izni hatası (2026-07-30 düzeltildi):** Kurulum `{autopf}\CEO ERP Araclar\` altına
yapıldığından (varsayılan Inno Setup davranışı), normal kullanıcı bu klasöre yazamaz →
`PermissionError: ceo_erp.log` ile açılış anında çöküyordu. Düzeltme:
- `main.py`: log dosyası artık `%LOCALAPPDATA%\CEO ERP Araclar\ceo_erp.log`'a yazılıyor.
- `config.py`: yazılabilir `config.json` artık `%LOCALAPPDATA%\CEO ERP Araclar\config.json`'da tutuluyor;
  kurulumun `{app}\config.json`'a koyduğu gerçek bağlantı bilgileri yalnızca **ilk çalıştırmada tohum
  (seed) olarak** oraya kopyalanır. Ayarlar sekmesinden yapılan değişiklikler de artık bu yazılabilir
  kopyaya kaydedilir — Program Files'a yazma denenmez.

**Hedef PC'de kurulum:**
1. `CEO-ERP-Kurulum.exe` çalıştır → sihirbaz `Program Files\CEO ERP Araclar\` altına kurar
2. Başlat Menüsü + isteğe bağlı masaüstü kısayolu otomatik oluşur
3. `config.json` (gerçek bağlantı bilgileriyle) otomatik gelir — ilk çalıştırmada şifre sorulmaz
4. Güncelleme kurulumlarında mevcut `config.json` korunur (üzerine yazılmaz)

**Ekstra bağımlılık yok** — Windows yerleşik `DRIVER={SQL Server}` sürücüsü yeterli.

---

## Klasör Yapısı

```
main.py / config.py / config.json / build.bat / setup.iss / create_installer.bat
db/      baglanti.py, sorgular.py
logic/   maliyet.py, excel.py, excel_is_emri.py, pdf_is_emri.py, mamul_agaci_excel_oku.py
tools/   fatura_eslestir.py, mutabakat.py, satilip_uretilmemis.py
ui/      ana_pencere.py, maliyet.py, mamul_agaci_tab.py, tarama.py, eslestirme.py, rapor.py
         tab_satis_faturalari.py, tab_erp_aktar.py, tab_sw.py, tab_uretim_raporu.py
         tab_fatura_eslestir.py, tab_recete_sorgula.py, tab_stok_hazirla.py
         tab_is_emri_formu.py, baglanti.py, stil.py
sw/      classifier, pipeline, renamer, erp_handler, vision_handler
referans/faturalar/  test_kalemleri.json
dist/    CEO-ERP-Araclar.exe, config.json
kanban/  Siparis_Takip_Kartlari.pdf (ANONS · VHF ALICI stok takip kartları), yedek/
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

**Excel'den Yükle** — 5 format tanır:

| Format | Tespit | Davranış |
|---|---|---|
| Yeni (Seviye-Tip) | A sütunu integer | Seviye+girinti korunarak yüklenir |
| Eski 6-kolon | A sütunu tip metni | Girintili stok kodu ile hiyerarşi |
| Çok eski | Diğer durum | Flat yükleme |
| **ADLASMKE** | A1 = "Stok Kodu" | CEO ERP dışa aktarımı — özel işleme ↓ |
| **Başlıklı rapor** | `Kod` / `Stok Kodu` başlığı | Sütunlar başlık adına göre okunur; `Kod/Ad/Adet` yapılı proje fark Excel'i de desteklenir |

Başlıklı veya pozisyonel Excel yüklemesinden sonra kodlar toplu ve salt-okunur
olarak CEO ERP'de `StokKarti`, `StokMasrafKarti` ve aktif `UretimRecete`
başlıklarıyla eşleştirilir. ERP'deki `Adi`, `Adi2` ve birim bilgileri doluysa
Excel değerlerine önceliklidir; ERP'de kayıt veya ilgili alan yoksa Excel değeri
korunur. ERP'de doğrudan Mamül/Yarımamül/Hammadde alanı bulunmadığı için stok
tipi aktif reçete ve ağaç konumundan türetilir; masraf kartı `Masraf` olarak
işaretlenir. Aynı kod iki kart tablosunda bulunursa Excel tip ipucu kullanılır
ve belirsizlik loga yazılır. Bu tarama canlı aktarım yapmaz.

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

`recete_bagla()` ve `recete_masraf_bagla()` fonksiyonları `hat_tipi` parametresi alır (varsayılan `2`).  
`tab_stok_hazirla.py`'deki BOM döngüsü, parent node'un `tip`'i `"Mamül"` ise `hat_tipi=1`, aksi hâlde `hat_tipi=2` geçer.

**Kritik:** `UretimReceteHatPlaniGirdi.Tipi` NOT NULL — INSERT'te `Tipi=1/2` zorunlu; `SabitMiktar=0`, `GarantiKapsaminda=0` da gerekli.

**Kritik:** `UretimReceteHatPlaniGirdi.BirimId` ve `DepoId` NULL bırakılamaz — CEO ERP iş emri oluştururken bu alanları okur; NULL olursa `.NET NullReferenceException` fırlatır. Değerler: `BirimId` = **bileşen kartının kendi birimi** (`StokKarti.StokBirim` / `StokMasrafKarti.StokBirimId`; kart birimi boşsa `ADET_BIRIM_GUID`), `DepoId=2` (Merkez). Native CEO kayıtlarında Girdi birimi kart birimiyle aynıdır (KG→KG, METRE→METRE); 2026-10-07 öncesi `recete_bagla()` / `recete_masraf_bagla()` her satıra sabit ADET yazıyordu.

**Kritik:** `UretimReceteHatPlani.Miktar`, `BirimId`, `DepoId` de NULL bırakılamaz — CEO ERP `Nullable<T>.Value` ile okur; NULL olursa `InvalidOperationException` fırlatır. Değerler: `Miktar=1`, `BirimId=ADET_BIRIM_GUID`, `DepoId=2` (Merkez).

**Kritik — SeriNoTakibi:** Üretilen ürünün `StokKarti.SeriNoTakibi=True` ise CEO ERP maliyetlendirmede seri no bekler; `UretimEmriHatPlani.Seri=NULL` olursa `.NET NullReferenceException` fırlatır. Çözüm: stok kartında `SeriNoTakibi=False` yap ve CEO'yu yeniden başlat (değişiklik önbelleğe alınır, restart gerekir).

**Kritik — Çok katmanlı reçete maliyetlendirme:** CANLI Aktar, Yarımamül (Tipi=2) düğümler için `UretimRecete`+`UretimReceteHatPlani` kaydı oluşturur. CEO ERP maliyetlendirme bu yarımamüllerin kendi üretim maliyetlerini arar; daha önce maliyetlendirilmiş iş emri yoksa `NullReferenceException` verir. Üst ürünü maliyetlendirmeden önce tüm Yarımamül bileşenlerin (Tipi=2) kendi iş emirleri maliyetlendirilmiş olmalıdır.

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

## Kanban Stok Takip Kartları (`kanban/`, 2026-11-05)

`kanban/Siparis_Takip_Kartlari.pdf`: ANONS · VHF ALICI için 36 adet stok takip kartı (form UR-FR-11_R00, Excel 2010'dan üretilmiş PDF; repoda üreten kod yok). Her kartta stok kodu/adı, MİN (sipariş noktası), sipariş miktarı, ürün başı kullanım, firma, termin ve elle doldurulan stok geçmişi tablosu bulunur. Satınalmaya gönderilen güncel dosya budur.

**MİN formülü (kart altında yazılı):** `MİN = ürün başı kullanım × 200 ürün/ay × (termin + 2 hf emniyet)`, haftalık talep 200×12/52 ≈ 46,15; sonuç yukarı 10'a yuvarlanır. Termin sınıfları: KISA (STOK/OSTİM/1 hf → 1 hf, yeşil), ORTA (1–3 hf, turuncu), UZUN (3–8 hf, kırmızı). Sipariş miktarı kontrol kuralı: ≥ 1 aylık tüketim ve ≥ termin süresince tüketim (aksi halde mal kabulden hemen sonra kart yeniden tetiklenir).

**Referans mamuller (ERP reçetesi):** GMP-101-230063 IR-610 VHF ALICI, GMP-101-230086 IR-610 B VHF ALICI, GMP-101-230101 OPAK KUTULU, GMP-101-260002 OPAK KUTULU (TELSİZSİZ).

### 2026-11-05 güncellemeleri (yalnızca okuma ile ERP'den doğrulandı)

1. **KODSUZ 10 kart kodlandı** (kullanıcı onayıyla):

   | Kart | Stok adı | Kod |
   |---|---|---|
   | 27 | M4 SOMUN | HMSOMUN004 |
   | 28 | 4X10 YSB VİDA | HMVİDA0009 |
   | 29 | M2,5X20 YHB INOX | SARF0000026 |
   | 30 | M3X12 YSB VİDA | HMVİDA0069 |
   | 31 | M3X10 YSB VİDA | HMVİDA0067 |
   | 32 | M3X6 YSB VİDA | HMVİDA0053 |
   | 33 | M3 SOMUN | HMSOMUN003 |
   | 34 | M12 PUL TIRTILLI-RONDELA | HMPUL00016 |
   | 35 | M12 SOMUN | HMPUL00018 |
   | 36 | KABLO PAPUCU (ANTEN KABLOSU İÇİN) | HMGMDDRL002 |

   Kararlar: vidalarda reçetedeki grup kartları (SARF0000001 M3 VİDA GRUBU, SARF0000003 M4 VİDA GRUBU) yerine **tekil kodlar**; somunlarda inox tekil kodlar; M2,5X20 için reçetede kullanılan SARF0000026 (ERP adında "BEYAZ" yazıyor, kartta "INOX" — ad uyumsuzluğu açık).

2. **MİN düzeltmeleri** (200/ay varsayımı korunarak, formüle uymayan kartlar):

   | Kart | Malzeme | Eski → Yeni |
   |---|---|---|
   | 3 | 0,75 mm montaj kablo | 110 → 140 |
   | 19 | Alıcı kutusu (4–5 hf) | 150 → 330 |
   | 23 | Alıcı trafosu (4–5 hf) | 200 → 330 |
   | 24 | HYDX VHF telsiz (6–8 hf) | 300 → 470 |

3. **Termin belirsiz kartlar netleşti:**
   - Kart 21 ANTEN DİPLİĞİ (YMGMDPK0001): termin **3 HAFTA** → ORTA TERMİN (turuncu), MİN 240 (değişmedi). Firma boş.
   - Kart 36 KABLO PAPUCU (HMGMDDRL002): termin **STOK** → KISA TERMİN (yeşil), ürün başı kullanım "—" → **2**, MİN → **280**. Firma boş.

4. Sipariş miktarlarında değişiklik gerekmedi (kart kullanım değerleriyle hepsi kuralı sağlıyor).

**Yedekler (`kanban/yedek/`):** `_ORIJINAL_` (dokunulmamış) → `_KODLU_` (kodlar) → `_MINDUZELTME_` (MİN düzeltmeleri) → `_KART21_` (kart 21 sonrası); güncel dosya kart 36 dahil son haldir.

**Açık konular:**
- **Talep varsayımı:** Formül 200 ürün/ay; ERP üretimden giriş (IslemKodu=16) kayıtlarına göre VHF alıcı ailesi son 12 ayda ≈ 900 adet (≈ 75/ay; 2026'da ≈ 37/ay). Kararla 200/ay korundu; düşürülürse tüm MİN'ler yeniden hesaplanmalı.
- **Kart kullanımı ≠ ERP reçetesi** (kartlar değiştirilmedi): kart 3 (kart 1 / reçete 0,25 m), 4 (1/2), 6 (3/5), 7 (5/6), 8 (1/3), 29 (4/2), 34 (4/1), 35 (4/1). Üretim çıkışı reçeteden yapıldığından bu kalemlerde fiziksel stok ile ERP bakiyesi ayrışır; hangisi doğruysa diğeri düzeltilmeli.
- Kart 27–33 vida/somunları alıcı reçetelerinde tekil olarak yok (grup kartıyla geçiyor); kart 36 kablo papucu IR-610 VHF reçetelerinde hiç yok (yalnızca diğer alıcı modellerinde, 2 adet).
- Kart 21 ve 36'da firma boş — satınalma dolduracak.

**PDF düzenleme yöntemi (tekrar gerekirse):** PyMuPDF (`pymupdf`) ile; metin redaksiyonla (zemin rengiyle) silinip `C:\Windows\Fonts\arialbd.ttf` ile aynı punto/konuma yazıldı (base-14 Helvetica "İ" desteklemez). Kart renkleri içerik akışındaki dolgu operatörleri değiştirilerek çevrildi (gri `.459 g`/`.941 g` → yeşil `0.18 0.49 0.196 rg`/`0.91 0.961 0.914 rg` veya turuncu `0.949 0.663 0 rg`/`1 0.965 0.859 rg`). Dikkat: `clean_contents()` ve önceki redaksiyonlar akışı yeniden yazar (ör. `0.459` → `.459`), regex'ler buna göre yazılmalı; tüm `get_contents()` akışları taranmalı.

---

## Sıradaki Geliştirmeler

1. **PDF gömme** — teknik resim PDF'lerini `StokKarti.DokumanPath`'e bağlama
2. **Canlı SW testi** — SW Kodlama sekmesini iş makinesinde SolidWorks 2019 ile doğrulama
3. ~~**Faturalaşan irsaliye mükerrer sayım riski (fiyat geçmişi genelinde)**~~ — **Düzeltildi (2026-09-14).** Proje Fark Raporu doğrulaması sırasında bulundu: `IslemKodu IN (1, 5)` / `IN (2, 6)` deseni, `FaturaId` dolu (faturaya dönüşmüş) irsaliye satırlarını faturasıyla birlikte iki kez sayıyordu. Düzeltme (`sh.IslemKodu = 1 OR (sh.IslemKodu = 5 AND sh.FaturaId IS NULL)` deseni, alış tarafı; satışta 2/6) artık şu 6 fonksiyonun hepsinde uygulanıyor: `proje_satinalma_hareketleri()`, `satis_faturalari()`, `stok_fiyat_gecmisi()`, `masraf_fiyat_gecmisi()`, `recetesiz_stok_hareketleri()`, `stok_fiyatlari_toplu()` (bu sonuncusu Maliyet sekmesinin asıl FIFO/LIFO/WA fiyat kaynağı). **Not:** Bu, Maliyet sekmesinin FIFO/LIFO/WA sonuçlarını değiştirebilir (artık daha az/doğru satır fiyat hesabına giriyor) — canlı kullanımda maliyet raporlarını gözle kontrol edin; `python tools\mutabakat.py` bu fonksiyonları kapsamıyor (yalnızca Üretim Eksik Stok bakiye/depo mutabakatını kontrol ediyor), o yüzden ayrı bir otomatik doğrulama aracı yok.
