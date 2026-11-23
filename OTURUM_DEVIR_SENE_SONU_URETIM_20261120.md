# Oturum Devri — Sene Sonu Üretim Emirleri: KAPANIŞ TAMAMLANDI

**Tarih:** 2026-11-20 · **Önceki devir:** `OTURUM_DEVIR_SENE_SONU_URETIM_20261111.md` (emirlerin açılışı, kararlar)
**Son commit:** `9be920c` (push edildi). §9 ve §10 sonradan eklendi, henüz commit edilmedi.
**Durum:** ✅ 16 sene sonu emrinin hepsi **Tamamlandı**. Sene sonu emirlerinin girdi kartlarında eksi bakiye yok. Açık kalan küçük işler §7'de.
**▶ DEVAM NOKTASI: §10 (güncel), ayrıntı §9.** Son tarih 27.11.2026 (eksik üretimler), sayım 30.11.2026. Bekleyen kararlar: 3 eski emir (muhasebe mi, hemen kapanış mı), 230093 ve HAV-HPB0001 için yeni emir.

---

## 1. Özet: bu oturumda ne oldu

1. **Muhasebe cevabı:** "Ekleme yapıldı." Gönderilen liste `eksi liste.xlsx` (dokunma). Muhasebe 137 kalemin tamamını tek fişle girdi: `SYM202600003` (StokHareket Id 744507, IslemKodu 20, **belge tarihi 19.01.2026**, kayıt 19.11.2026, Depo 2, ≈1,18 M ₺). Miktarlar listeyle birebir. Tahmini 717 bin ₺'yi aşan kısım, alışı olmayan iki parçadan geliyor: 240570 ×111 @1.615 ve 240602 ×111 @2.500 (≈456 bin ₺; fiyatlar muhasebeyle teyit edilmedi).
2. **Deneme emri `-1`** kullanıcı tarafından CEO'da kapatıldı. İki sorun çıktı ve çözüldü:
   - **Birim:** HMGMDDAL001 reçetede TAKIM, kartta ADET → 7 emir girdisi ve 11 reçete girdisi ADET yapıldı.
   - **Depo:** perçin (SARF0000010) Merkez'de −232, 3.000 adet ANONS deposunda (02.06.2026 tarihli k23 transferi). CEO girdi deposuna bakıyor.
3. **Depo sorunu çözümü:** Önce Depo Transfer Talebi **Id 115** açıldı (7 satır). Sonra kullanıcının önerisiyle **girdi deposunu değiştirme** yöntemi denendi, işe yaradı ve tüm emirlerde bu kullanıldı. → **Talep 115 gereksiz, CEO'da iptal edilebilir** (kullanıcı Not2'yi kendisi "Savaş Adıgüzel" yapmış, durumu 1 = Devam Ediyor).
4. **Fatura ↔ emir uyum kontrolü (2026):** AES `962026-25` ve Bilişim `1092026-1` faturalarla uyumlu çıktı. İkisinin yarı mamul hatları kapalıydı ve ürettikleri başka emirlerde tüketilmişti → kullanıcı **iki emrin de yalnızca ana hattını sildi**; CEO iki emri otomatik Tamamlandı yaptı. `2082026-1` (230107 ×45) faturası henüz kesilmedi → **silinmeyecek**.
5. **Van `-15`** (2025): kullanıcı tarafından **silindi** (2025 kapsam dışı).
6. **Masraf tutarları:** CEO masraf (Tipi=2) maliyetini `UretimEmriHatPlaniGirdi.Tutar` alanından alır; alan boşsa 0 yazar. 218 satır dolduruldu (≈1,86 M ₺), 110 mükerrer masraf satırı silindi. Caracal 230032:65 Polisaj'a kullanıcının verdiği 250 ₺ elle yazıldı.
7. **İki kat reçete:** 230016 reçetesinde her girdi iki kez yazılıydı. 2026'da bu reçeteyle kapanmış iki emir (`962026-3` ×1 ve `962026-9` ×5) 33.433 ₺/adet maliyet çıkarıyor, stoktan da iki kat tüketim yapıyordu → reçete 96 → 48 satır; emirlerde girdi ve 17 fişi 90 → 45 satır; maliyet **16.716 ₺/adet** yapıldı.
8. **TUSAŞ `1092026-3`** kullanıcı tarafından CEO'da kapatıldı (01.06 ve 25.06). Karşılaştırma temiz çıktı.
9. **CEO'nun maliyet yöntemi çözüldü:** depo bazlı FIFO (§4).
10. **Kalan 14 emir SQL ile toplu kapatıldı** (`toplu_kapat.py`). Hepsi temiz.

## 2. Emirlerin son durumu (hepsi DurumId=5)

| Emir | Kapanış | Ana ürün | Birim maliyet | Not |
|---|---|---|---|---|
| `-10` Caracal | 07.04.2026 | 230032 ×1 | 2.584 | |
| `1092026-3` TUSAŞ | 01.06 / 25.06 | 230016, 230035, 230027 | 16.731 / 3.310 / 6.403 | CEO'da kapatıldı (kullanıcı) |
| `-3` İznik | 31.07.2026 | 230064 ×10 | 5.069 | perçin ANONS |
| `-4` ADLAS MKE | 30.09.2026 | 230136 ×1 | 3.359.242 | güç kaynağı ADLAS-MKE, servo ADLAS |
| `-16` FAEM | 01.10.2026 | 230094 ×1 | 14.728 | perçin ANONS |
| `-12` Lüp | **06.10.2026** (emir 15.09'dan taşındı) | 230010 ×45 | 4.052 | |
| `-5` Bilişim | 07.10.2026 | 230063 ×5 | 4.188 | perçin ANONS |
| `-13` FAEM | 15.10.2026 | 260002 ×40 / 230093 ×20 | 2.436 / 3.377 | perçin ANONS |
| `-2` 5. Ana Bakım | **16.10.2026** (01.07'den) | 230129 ×1 | 7.856 | 240698/240699 masrafları fiyatsız (0) |
| `-9` Otokar | **21.10.2026** (02.07'den) | 230022 ×37 | 27.828 | |
| `-11` Otokar | **21.10.2026** (01.09'dan) | 230022 ×32 | 29.868 | mendil PORTATİF |
| `-14` Otokar | 30.10.2026 | 230022 ×42 | 30.746 | mendil 24 Merkez + 18 PORTATİF (satır bölündü) |
| `-1` Oğuz Yılmaz (deneme) | 02.11.2026 | 230063 ×1 | 5.110 | CEO'da kapatıldı (kullanıcı) |
| `-6` Nazar / `-7` Melekli | 02.11.2026 | 230063 ×1 / ×4 | 4.061 | perçin ANONS |
| `-8` Genç Teknoloji | 04.11.2026 | 230063 ×40 / 230064 ×10 | 4.060 / 3.970 | perçin ANONS |

Fatura miktarıyla birebir açıldığı için bakiyede küçük fazlalar oluştu (beklenen): 230022 +1, 230063 +1, 230064 +2, 230010 +5.
Toplu kapanışın satır satır dökümü: `toplu_kapat_commit_20261120_132355.json`.

## 3. Kalan eksiler (reçeteli kartlar, 20.11.2026)

| Kart | Bakiye | Kaynak | Öneri |
|---|---|---|---|
| GMP-101-230093 B Anons Alıcı | −50 | FAEM GEF2026000000073, 13.11.2026, ×50 | Aynı yöntemle emir aç + kapat (kullanıcıya soruldu, cevap bekliyor) |
| HAV-HPB0001 Havalı Hoparlör | −27 | Ford GEF2026000000070, 10.11.2026, ×43 | Aynı |
| GMP-101-230111 | −1 | 2025 Van satışı | Kapsam dışı (Van emri silindi) |

## 4. Kritik teknik bulgular (yeniden keşfetme)

- **CEO maliyet yöntemi = depo bazlı FIFO.** Girdinin deposundaki girişler tarih/Id sırasıyla katman oluşturur; bu depoya gelen k23 transferi transfer fiyatıyla katman sayılır. Depodaki önceki çıkışlar ve bu depodan giden k23'ler katmanları tüketir. 20.11 CEO fişlerinde 134 satırın 130'u birebir tuttu (şirket geneli FIFO 49'da 43). `KalanMiktar` katman takibi için **kullanılmıyor**, hep Miktar'a eşit. 16 maliyeti = 17 satırlarının MaliyetTutari toplamı (kuruşu kuruşuna doğrulandı). Masraf satırı maliyeti = girdi `Tutar`.
- **CEO kapanış kalıbı (alan alan):** 16 ve 17 başlıkları aynı `BelgeSiraNo`'yu taşır (yıl + ay + gün + SSDDss, ay ve gün sıfırsız, ör. `202661122840`). Notlar = `"<emir> / <açıklama>"`, DepoKartId=2, bölge 2/2, vergi alanları 0. Detay: Turu 1 stok / 3 masraf (IslemKartId = masraf kart Id), **`BirimKatsayisi = Miktar`** (tetikleyici StokKumulatif'i bu alanla günceller, DECIMAL(18,2) yuvarlar), KalanMiktar = Miktar, MaliyetTarihi = belge tarihi, `UretimHatPlaniId` boş. `UretimEmriHatPlaniStokHareketleri`: 16 → 0, 17 → 1. `UretimEmriHatPlani.MaliyetlendirilenMiktar = TalepMiktari`. Son hat kapanınca DurumId=5 + `UretimEmriTarihce` satırı ("Eski durum : Devam Ediyor Yeni durum : Tamamlandı", 3 → 5). Girdi ↔ detay bağlantısı (`UretimEmriGirdiStokHareketi`) yazılmıyor.
- **Tetikleyiciler:** StokHareketDetay insert/update/delete tetikleyicileri `inserted`/`deleted`'dan TEK satır okur → satırları tek tek yaz/sil. INSERT'te `SET NOCOUNT ON; ... SELECT SCOPE_IDENTITY()` kullan ve sonuç kümelerinde `nextset` ile ilerle. `AfterUpdateStokHareketDetay` irsaliye/konsinye alanı NULL ise StokKumulatif'i NULL yapabilir → güncellemede önce/sonra kontrol et. `trg_AfterDelete_StokHareketDetay` hat + kart eşleşen TÜM girdi satırlarının KullanilanMiktar'ını düşer.
- **Tarih saati:** BelgeTarihi saat içerebilir → depo bakiyesi ve FIFO'da kapanış gününü 23:59:59'a kadar say.
- **CEO kapanışta stoğu belge tarihine ve girdi deposuna göre kontrol eder.** Toplam şirket bakiyesi yeterli olsa bile girdi deposunda yoksa "eksik stok" der.
- **Masraf/operasyon:** operasyon alımlarının çoğu aynı `P:XX` kodlu **StokKarti**'ne işleniyor; masraf kartının kendi fiyatı yok. Düzleştirilmiş ana hatlarda aynı operasyon hem YM hattında hem ana hatta durabilir → mükerrer maliyet (Otokar'da 3,56 M → 1,86 M ₺).
- **Satış faturası detayındaki `MaliyetTutari` satış tutarıdır**, satılan malın maliyeti değil.
- **İki kat reçeteler (11.11'de bulundu):** 230016 düzeltildi. Kalan 10 reçete (230033, 230037, 230038, 230040, 230107, GMP-300-230001, MMPBIŞIK01, MMSBIŞIK002, YMPKIŞIK003, YMTKANCA01) hâlâ iki kat; 2026'da bunlarla kapanmış emir yok. **230107 → açık emir `2082026-1` etkilenir**, kapatmadan önce düzelt.
- **Boresighter SP maliyeti:** kullanıcının elle hesabı ≈33 bin ₺; eski CNC teklifi 14.500 ₺ (7,62 mil dahil), yeni teklif mil hariç 20.000 ₺/takım. ERP'deki 1 adetlik CNC + yüzey işlem ≈13,1 bin ₺ (2025 sonu faturaları). Fark fiyat artışından geliyor, reçeteden değil. Defter maliyeti faturalardan gelir; yeni fiyatlar fatura girdikçe yansır.

## 5. Bu oturumda ERP'ye yazılanlar (yedekleriyle)

| İşlem | Script | Yedek |
|---|---|---|
| HMGMDDAL001 birim TAKIM→ADET (7 emir girdisi + 11 reçete girdisi) | `birim_duzelt.py` | `birim_duzelt_yedek_20261120_105655.json` |
| Depo Transfer Talebi 115 (7 satır) | `transfer_talep.py` | — (talep; stok etkisi yok) |
| `-5` perçin girdisi Merkez→ANONS (deneme) | `girdi_depo_duzelt.py` | `girdi_depo_yedek_20261120_110904.json` |
| TUSAŞ 230016 kapak girdileri → BORESIGHT deposu | (tek seferlik) | `girdi_depo_yedek_20261120_115707.json` |
| 218 masraf satırına Tutar | `masraf_doldur.py` | `masraf_doldur_yedek_20261120_121126.json` |
| Caracal 230032:65 = 250 ₺ | elle | `masraf_doldur_yedek_*_elle.json` |
| 110 mükerrer masraf satırı silindi | `mukerrer_masraf_sil.py` | `mukerrer_masraf_yedek_20261120_123437.json` |
| 230016 reçetesi 96→48; `962026-3`/`-9` girdi + 17 detay 90→45 | `recete_ikikat_duzelt.py` | `recete_ikikat_yedek_20261120_125524.json` |
| `962026-3`/`-9` 16 maliyeti = 17 toplamı (16.716 ₺/adet) | `uretim_maliyet_esitle.py` | `uretim_maliyet_yedek_20261120_125745.json` |
| 14 emrin kapanışı (fişler, depo düzeltmeleri, 4 emrin tarih taşıma) | `toplu_kapat.py --commit` | rapor `toplu_kapat_commit_20261120_132355.json` (geri alma için fiş Id'leri burada) |

Kullanıcının CEO'dan yaptıkları: `-1` kapanışı; AES `962026-25` ve Bilişim `1092026-1` ana hatlarının silinmesi; Van `-15`'in silinmesi; TUSAŞ'ın tüm hatlarının kapanışı; talep 115 Not2/durum düzeltmesi.

## 6. Yeni scriptler (`tools/sene_sonu_uretim/`, commit edilmedi)

| Script | Ne | Yazma? |
|---|---|---|
| `muhasebe_kontrol.py` | Gönderilen eksi listesi ↔ bugünkü bakiye ve gönderim sonrası hareketler | okuma |
| `depo_kontrol.py` | Açık emir girdilerinin depo bazlı yeterliliği (ATP) | okuma |
| `fatura_emir_uyum.py` | 2026 faturaları ↔ emirler eşleştirme (yalnız 2026) | okuma |
| `emir_hazirlik.py` | Bir emrin kapanış sırası + verilen tarihte eksikler + en erken tarih (⚠ masraf kontrolü yok) | okuma |
| `kapanis_karsilastir.py` | CEO kapanışı ↔ `hat_kapat.py --beklenen` satır satır | okuma |
| `birim_duzelt.py` | Girdi birimi ≠ kart birimi düzeltmesi | YAZMA |
| `transfer_talep.py` | Depo Transfer Talebi oluşturma | YAZMA |
| `girdi_depo_duzelt.py` | Emir girdi deposunu yeterli depoya çevirme | YAZMA |
| `masraf_doldur.py` | Masraf girdilerine Tutar (masraf alışı → stok kartı alışı, mükerrer kuralları) | YAZMA |
| `mukerrer_masraf_sil.py` | Aynı kodu stok girdisi olarak da bulunan masraf satırlarını silme | YAZMA |
| `recete_ikikat_duzelt.py` | İki kat reçete + o reçeteyle kapanmış emirlerin düzeltmesi | YAZMA |
| `uretim_maliyet_esitle.py` | Kapalı hatta 16 maliyeti = 17 toplamı | YAZMA |
| `hat_kapat.py` | Tek emrin hatlarını CEO kalıbıyla kapatma (çok tarihli; `--beklenen`) | YAZMA |
| `toplu_kapat.py` | Plan listesiyle toplu kapatma (önce/sonra kontrollü, sorun çıkınca durur) | YAZMA |

Hepsi `--commit` verilmezse rollback (deneme) çalışır. `tamamla_dene.py` eski ve hatalı (BirimKatsayisi=1, OUTPUT INSERTED) → kullanma; `hat_kapat.py` onun yerini aldı.

## 7. Açık işler / sıradaki adımlar

1. **230093 (FAEM ×50) ve HAV-HPB0001 (Ford ×43):** yeni emir açılıp kapatılsın mı? **Kullanıcıya soruldu, cevap bekleniyor.** Evet derse: `gen_plan.py` / `emir_yaz.py` düzeniyle fatura−1 gün emir → `masraf_doldur.py --emir` → `toplu_kapat.py` (PLAN'a ekle).
2. **Kullanıcı CEO'da birkaç emri kontrol edecek** (öneri: `-14`, `-8`). İsterse CEO Toplu Maliyetlendirme ile yeniden hesaplatır; fark küçük olmalı.
3. **Talep 115'i CEO'da iptal et** (kullanıcı).
4. **Commit/push:** yeni scriptler + `ERP-OKUMA.md` (kullanıcı komutu bekleniyor). JSON yedekleri, xlsx'ler ve `eksi liste.xlsx` commit edilmez.
5. **Muhasebeye bildirilecekler:**
   - 230016 iki kat düzeltmesiyle stoğa geri dönen 14 kalem SYM202600003'te de var. Bu kalemlerde bakiye 6–12 adet yüksek: 230606:20/60, 230607:20/60, 230608:20, 230609:20, 230611:20/60, 230615:60, 230616:20/60, 230617:60, 240004, 240012.
   - 240570/240602 fiyatları (1.615 / 2.500 ₺) teyit edilmeli.
   - 4 emrin kapanışı fatura tarihinden sonraya taşındı (`-2`, `-9`, `-11`, `-12`).
6. **Kalan 10 iki kat reçete** (§4) düzeltilmeli; özellikle 230107, çünkü `2082026-1` faturası kesilince kapatılacak.
7. **`-2` 5. Ana Bakım:** 240698/240699 torna ve freze masrafları fiyatsız (kullanıcı bilmiyor) → 0 kaldı; fiyat öğrenilirse girdi Tutar'ı yazılır ve emir yeniden maliyetlendirilir.
8. **Kalite notları:** HMPROJE0065 reçetede KG, kartta METRE (dokunulmadı). StokKumulatif ↔ formül farkı 4 kartta önceden vardı: HMGMKRS0002, HMGMSWC0001, HMPUL00016, ERJ-3EKF4703V. TUSAŞ'ta V4 Kasa (240677, 25.800 ₺) Boresighter L aksesuar grubunun (BRSLAKS001) içinde; doğru yerde mi, kullanıcıya soruldu, cevap yok.
9. **`emir_hazirlik.py`'ye masraf Tutar=0 kontrolü eklenmeli.**

## 8. Kurallar (bu oturumda konan)

- ERP'ye yazılan hiçbir not/açıklama alanında "Claude" geçmez; gerekirse yalnızca **"Savaş Adıgüzel"**.
- 2025 kapsam dışı (fatura ve emir analizlerinde yalnız 2026).
- Faturayla uyumsuz emir silinir. Faturası henüz kesilmemiş ama kesilecek emir (`2082026-1`) silinmez.
- Yazma işlemlerinde önce deneme (rollback), sonuç gösterilir, sonra `--commit`; her yazmada JSON yedek.

## 9. ▶ Devam noktası: kalan 4 açık emir (2026-11-20, son durum)

Sene sonu emirleri bittikten sonra ERP'de **4 emir Devam Ediyor (DurumId=3)** durumunda kaldı. Bunlar sene sonu kapsamına girmemişti, çünkü ürünlerinin bakiyesi eksi değildi.

| Emir | Ürün | Fatura | Bakiye (bugün) | Kapanırsa | Karar |
|---|---|---|---|---|---|
| `ŞİRKET.1862026-10` RSTEK (emir tarihi 07.06.2026) | GMP-101-230030 Boresighter SP 12X ×1 (1 hat) | GEF2026000000029, 08.06.2026, RSTEK ×1 | 0 | +1 | **Kapatılacak** (kullanıcı: "doğru, artıya geçmeli") |
| `ŞİRKET.1862026-7` RSTEK (08.06.2026) | GMP-101-230044 120-122 mm adaptör ×1 (1 ana + 7 YM hattı) | GEF2026000000029, 08.06.2026, RSTEK ×1 | 0 | +1 | **Kapatılacak** |
| `ŞİRKET.1862026-8` Unirobotics (18.06.2026) | GMP-101-230035 12,7 mm mil ×5 (1 hat) | GEF2026000000028, 04.06.2026, Unirobotics ×5 | +5 | +10 | **Kapatılacak** |
| `ŞİRKET.2082026-1` Portatif Işık Kaynağı-30 (20.08.2026) | GMP-101-230107 ×45 (13 hat) | henüz kesilmedi | 0 | +45 | **Açık kalacak**: fatura kesilince kapatılacak; 230107 reçetesi iki kat, kapatmadan önce girdileri düzelt |

**Engel:** İlk üç emrin girdileri hiçbir depoda yok, bugün itibarıyla bile. Ürünler fiziksel olarak üretilmiş, ama parça girişleri ERP'de yapılmamış.
- `1862026-10`: 23 kalem eksik, ~10.127 ₺ (12X gövde/prizma/paralaks parçaları, lens grupları YMB-V00-R00-23001/23002, aksesuar SPORTAKS004, kılavuz 240660, o-ring, vida…)
- `1862026-7`: 28 kalem eksik, ~4.733 ₺ (rulmanlar SKF6195 ×3 ve 240606, pimler, imbus vidalar, çene montajı YMB-V00-R00-23008 ×3, YM operasyon kartları :50/:90/:115…)
- `1862026-8`: 2 kalem eksik, ~7 ₺ (HM.İNX.VİD.017 ×5, HMÇLKISH007 3,75)
- Liste: `C:\yeni-erp\uc_emir_eksik_kalemler_20261120.xlsx` (gitignore'da, commit edilmez)
- Masraf ön izlemesi: `-10` ve `-7`'de doldurulacak masraf yok. `-8`'de 2 satır yazılabilir (4.250 ₺; 5 satır zaten dolu). Henüz yazılmadı.

**Kullanıcıya sunulan seçenekler (cevap bekleniyor):**
1. **(Önerilen) Muhasebe yolu:** Liste muhasebeye gönderilir; girişler **07.06.2026'dan önce** tarihli yapılır. Sonra `masraf_doldur.py --emir` (`-8`) ve `toplu_kapat.py` ile üç emir emir tarihleriyle kapatılır. İstenirse muhasebe mail metni hazırlanacak.
2. **Hemen kapanış:** Şimdi kapatılır, 53 kalem eksiye düşer (son alış fiyatıyla maliyetlenir), muhasebe sonradan düzeltir. Bunun için `toplu_kapat.py`'deki "yeni eksi oluşursa dur" kontrolünü bilerek gevşetmek gerekir.

**Kapanış için teknik notlar:**
- `toplu_kapat.py`'nin `PLAN` listesi sabit. Bu üç emir için PLAN'a eklenmeli: `('ŞİRKET.1862026-10','07.06.2026')`, `('ŞİRKET.1862026-7','08.06.2026')`, `('ŞİRKET.1862026-8','18.06.2026')`. Ya da `--plan` parametresi eklenmeli.
- `masraf_doldur.py` ve `mukerrer_masraf_sil.py` varsayılan olarak yalnız `SurecDipnot LIKE 'Fatura:%'` emirlerini tarar. Bu üç emir için `masraf_doldur.py --emir X` kullan; `mukerrer_masraf_sil.py` için sorgu kapsamını genişlet.
- Unirobotics emri faturadan (04.06) sonra tarihli (18.06). Kullanıcı bu haliyle kabul etti.

**Bundan sonra sırayla:**
1. Kullanıcının seçimine göre üç emri kapat → `kapanis_karsilastir.py` benzeri doğrulama + bakiye kontrolü (beklenen: 230030 +1, 230044 +1, 230035 +10).
2. §7'deki açık işler: 230093 (FAEM ×50) ve HAV-HPB0001 (Ford ×43) için yeni emir kararı; talep 115 iptali; muhasebeye bildirimler; kalan 10 iki kat reçete (önce 230107).

## 10. ▶ GÜNCEL DEVAM NOKTASI: Kalite maili ve sayım takvimi (2026-11-20, oturum sonu)

Kalite bölümünden gelen mail (özet):
- **27.11.2026 Cuma'ya kadar** eksik üretimler CEO'da tamamlanmış olmalı, birim fiyatlar kontrol edilerek. Muhasebe muhatabı **Fatma Hanım**; gerekirse Muhammet dahil edilir.
- **Stok sayımı 30.11.2026 Pazartesi** başlıyor (mailde "30.11.2027" yazıyor; 2027'de 30.11 Salı → yazım hatası). Sayımı **İsmail** yönetecek, **İbrahim Bey** dahil; kalite sorumlusu sayımda depoda olacak.
- Sayımdan önce sayım gününden dönem sonuna kadarki **sipariş durumları** çıkarılıp üretim için gereken malzemeler ayrılacak.
- Depo sayımından sonra **Ar-Ge malzemeleri** sayımı planlanacak.

**27.11'e kadar yapılacak üretimler:**

| İş | Durum |
|---|---|
| 16 sene sonu emri | ✅ Tamamlandı (birim fiyatlar depo bazlı FIFO ile CEO yöntemine uygun) |
| RSTEK `1862026-10`, RSTEK `1862026-7`, Unirobotics `1862026-8` | ⏳ 53 kalem girdi eksik (~14,9 bin ₺) → §9; muhasebe mi, hemen kapanış mı, kullanıcı kararı bekleniyor |
| GMP-101-230093 FAEM ×50 (GEF2026000000073, 13.11) | ⏳ Yeni emir açılması onay bekliyor |
| HAV-HPB0001 Ford ×43 (GEF2026000000070, 10.11) | ⏳ Yeni emir açılması onay bekliyor |
| `2082026-1` Portatif Işık ×45 | Fatura kesilmeden açık; 27.11 öncesi kesilirse listeye girer (önce 230107 iki kat reçete düzeltmesi) |

**Kullanıcıya önerilen sıra (onaylanmadı; "sonra devam edeceğiz" dendi):**
1. Üç eski emir için karar + **Fatma Hanım'a tek muhasebe maili**. İçeriği:
   - 53 eksik kalem (`uc_emir_eksik_kalemler_20261120.xlsx`), giriş tarihi 07.06.2026'dan önce olmalı.
   - 240570 / 240602 fiyat teyidi (1.615 / 2.500 ₺).
   - 230016 iki kat düzeltmesiyle stoğa geri dönen 14 kalem (§7.5).
   - Kapanış tarihi ileri alınan 4 emir (`-2` 16.10, `-9` / `-11` 21.10, `-12` 06.10).
   - Talep 115'in gereksiz olduğu.
2. 230093 ve HAV-HPB0001 için fatura birebir emir aç (fatura−1 gün) → `masraf_doldur.py --emir` → `toplu_kapat.py` (PLAN'a ekle).
3. Sayım hazırlığı (hafta içi):
   - (a) açık satış siparişleri + 30.11'den dönem sonuna kadarki üretim ihtiyacı → malzeme ayırma raporu;
   - (b) depo bazlı yazdırılabilir sayım listeleri (kod, ad, birim, ERP bakiyesi; depo bakiyesi k23 dahil hesaplanmalı); Ar-Ge için de;
   - (c) sayım sonrası fark raporu (tutar bazlı).

Bellek: `project_stok_sayimi_2026.md` (takvim), `project_sene_sonu_eksi_recete.md` (iş geçmişi).

## 11. Kural + hazırlık (2026-11-20, §10'dan sonra)

- **KURAL (kullanıcı):** Yarı mamul ve hammadde stokları eksiye düşürülmez → üç eski emir için yalnız **muhasebe yolu**. "Hemen kapatma" seçeneği iptal.
- **HAV-HPB0001 (Ford ×43, emir tarihi 09.11.2026):** reçete tek hat, 2 girdi; hepsi yeterli, mükerrer yok, masraf yok → **hemen açılıp kapatılabilir** (kullanıcı onayı bekleniyor). Fatura birebir → bakiye −27 → +16.
- **GMP-101-230093 (FAEM ×50, emir tarihi 12.11.2026):** reçete tek hat, 24 girdi. YMGMKRT0004 ×50 ve YMGMÇBK0001 ×50 eksik → aynı emirde YM hattı olarak üretilecek (girdileri yeterli). 7 hammadde/sarf eksik (HMGMDDAL120 50, HMGMKBL0095 0,25, HMGMKLM0004 100, SARF0000006 50, SARF0000001 578, SARF0000003 300, SARF0000021 50) → muhasebe girişi gerekiyor. Perçin ANONS'ta (depo düzeltmesi otomatik).
- **Muhasebe listesi:** `C:\yeni-erp\muhasebe_eksik_giris_20261120.xlsx`. 60 satır: üç eski emir (53) + 230093 (7). Tahmini ≈18,1 bin ₺; 29 satırda alış fiyatı yok, fiyatı muhasebe belirleyecek. Mail taslağı kullanıcıya verildi (Fatma Hanım'a).
- **Muhasebe girişi gelince:** `muhasebe_kontrol.py "muhasebe_eksik_giris_20261120.xlsx"` ile kontrol (sayfa adı farklı; gerekirse uyarla) → 3 eski emir + 230093 emrini aç/kapat (`toplu_kapat.py` PLAN'a ekle).

## 12. Sayım öncesi liste (2026-11-20)

`tools/sene_sonu_uretim/sayim_oncesi_liste.py` (salt okuma) → `sayim_oncesi_liste_20261120.xlsx`:
- **1-Sayım Fazlası Girişi:** tek fiş, Merkez, tarih ≤ 06.06.2026; 60 kalem (3 eski emir + 230093), ≈18,1 bin ₺ + 29 fiyatsız kalem.
- **2-Sayım Eksiği Çıkışı:** tek fiş, sayımdan önce; 230016 iki kat düzeltmesi × SYM202600003 çakışan 14 kalem; düşülecek = min(iade, SYM) → ≈24,1 bin ₺.
- **3-Yapılacak Üretimler:** A (faturalı, kayıt eksik: 3 eski emir, HAV ×43 hazır, 230093 ×50) + B (açık satış siparişlerinden: 230107 ×45 = 2082026-1, HAV ×100, 230063 ×15, KRT0004 ×11, 230085 ×40, 230111 ×3, 230093 ×50, 230036 ×7, 230129 ×1). Haziran öncesi siparişler "hâlâ geçerli mi" teyit bekliyor. Reçetesiz: 230115, 230136-1.
- **3a:** B grubunun eksik malzemeleri (sıralı düşümle).
- **Karar (kullanıcı):** Muhasebe yalnız sayım fazlası girişini yapacak (`muhasebe_eklenecek_kalemler_20261120.xlsx`, 60 kalem, tarih ≤ 06.06.2026). Fazla görünen 14 kalem için çıkış yapılmayacak, yıl sonu sayımında düzelecek. Dosya 20.11.2026'da muhasebeye gönderildi.
- `fatura_uretim_fark.py` → `fatura_uretim_fark_20261120.xlsx`: 31 reçeteli ürün; bekleyen 5 iş kapanınca eksi kalan ürün yok.
- **Sıradaki:** muhasebe girişi gelince `muhasebe_kontrol.py` ile doğrula → 1862026-10 / -7 / -8 kapat, 230093 ×50 emrini aç-kapat. HAV ×43 onay bekliyor.

## 13. Fiyatsız kalemler tamamlandı (2026-11-23)

- `tools/sene_sonu_uretim/fiyatsiz_tamamla.py` → `muhasebe_eklenecek_kalemler_FIYATLI_20261123.xlsx`: 26 fiyatsız kaleme önerilen fiyat yazıldı. Kur farkı: TL ÷ alış günü USD × bugünkü USD (USD 50,4028 / EUR 55,2974). Genel toplam ≈35.203 ₺.
- **Karar (kullanıcı):** Mükerrer girdiler üretim emrinden çıkarılacak, muhasebe listesine girmez. Listeden çıkan 3 kalem (1862026-10): YMB-V00-R00-23001, YMB-V00-R00-23002, SPORTAKS004. Ana liste 57 kalem.
- Kullanıcı dosyada kendi düzenlemelerini yapıp 23.11.2026'da muhasebeye gönderdi (gönderilen son hali bizde değil).
- **Sıradaki:** muhasebe girişi gelince `muhasebe_kontrol.py` ile doğrula → 1862026-10'dan 3 mükerrer girdiyi çıkar (YAZMA, onay gerekli) → -7 / -8 / -10 ve 230093 ×50 emirlerini kapat. Açık konu: YMB-V00-R00-23008 ×3 (1862026-7) mükerrer mi, ürün sorumlusuna sorulacak.
