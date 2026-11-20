# Oturum Devri — Sene Sonu Üretim Emirleri: KAPANIŞ TAMAMLANDI

**Tarih:** 2026-11-20 · **Önceki devir:** `OTURUM_DEVIR_SENE_SONU_URETIM_20261111.md` (emirlerin açılışı, kararlar)
**Son commit:** `a6bcab6`. Bu oturumda yazılan scriptler ve `ERP-OKUMA.md` **commit edilmedi, push yapılmadı.**
**Durum:** ✅ 16 sene sonu emrinin hepsi **Tamamlandı**. Sene sonu emirlerinin girdi kartlarında eksi bakiye yok. Açık kalan küçük işler §7'de.

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
