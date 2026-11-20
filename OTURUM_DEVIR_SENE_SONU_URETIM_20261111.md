# Oturum Devri — Sene Sonu Eksi Bakiyeli Reçeteler / Fatura Bazlı Üretim Emirleri

**Tarih:** 2026-11-11 · **Son commit:** `a6bcab6` (push edildi)
**Durum:** ⏸ **MUHASEBE BEKLENİYOR.** Muhasebe, gönderilen eksi listesini CEO'ya işleyecek. Cevap gelmeden emir kapatılmayacak.

---

## 1. Amaç

Yıl sonundan önce, satılıp üretim girişi yapılmamış (bakiyesi eksi) reçeteli mamulleri **eksiye düşüren satış faturasının içeriğiyle birebir uyumlu** üretim emirleriyle kapatmak. Emirler tamamlandığında alt malzemede eksiye düşecek kalemler muhasebeye toplu olarak bildirilip düzeltilecek; sonra emirler tek tek kapatılacak.

## 2. Kullanıcı kararları (hepsi 2026-11-11)

| Konu | Karar |
|---|---|
| Emir miktarı | **Fatura miktarıyla birebir** (eksik kadar değil) |
| Emir tarihi | Faturadan önce: **fatura tarihi − 1 gün** (hafta sonuysa önceki Cuma), saat 09:00 |
| Emir durumu | **Devam Ediyor (DurumId=3)**, stok hareketi yazılmaz |
| Çalışma yöntemi | Önce 1 deneme emri → kullanıcı CEO'da kontrol etti, onayladı → kalanlar |
| Çok hatlı reçeteler | Ana hat = satılan mamul, tüm hat girdileri tek hatta; eksik parçalar HatTipi=2 (onaylandı) |
| TUSAŞ | Yeni emir yok; açık emir `ŞİRKET.1092026-3` düzeltildi |
| Caracal | Yeni emir açıldı (eski kapalı `2842026-1`'e dokunulmadı) |
| FAEM GEF…063 | Önce 260002 ile açıldı; 230093 reçetesi yazılınca aynı emre eklendi |
| Reçetesiz mamuller | Son üretim emrinden reçete önerisi → kullanıcı onayladı → yazıldı |
| Pasif kartlar | Güncel karşılıklarıyla değiştirildi |
| Van (2025 faturası) | Emir tarihi 24.12.2025 |
| Bilişim / AES eski açık emirleri | **Dokunulmadı**, muhasebe notunda bilgi olarak |
| Otokar GEF…065 | 42 (fatura miktarı); notta seri aralığı 43 — teyit gerekli |
| Mükerrer TUSAŞ girdileri | Düzeltildi |
| Operasyon kartları | Muhasebe listesinde aynı tabloda |
| Emirleri kapatma | **Muhasebe girişlerinden sonra, CEO ekranından, tek tek** |

## 3. ERP'ye yazılanlar

### 3a. Üretim emirleri — 16 yeni + 1 düzeltilen (hepsi Devam Ediyor, hiçbiri kapatılmadı)

Fatura tarihi sırasıyla (kapatma da bu sırayla önerilir):

| # | Emir | Id | Emir tarihi | Fatura | Cari | Ana ürün(ler) | YM hattı |
|---|---|---|---|---|---|---|---|
| 1 | ŞİRKET.11112026-15 | 210940 | 24.12.2025 | GEA2025000000119 | Van Bld. | 230111 ×1 | 2 |
| 2 | ŞİRKET.11112026-10 | 210933 | 07.04.2026 | GEA2026000000037 | Caracal | 230032 ×1 | 0 |
| 3 | ŞİRKET.1092026-3 *(yerel, düzeltildi)* | 210905 | 01.06.2026 | GEF2026000000032 | TUSAŞ | 230016, 230035, 230027 ×1 | 15 |
| 4 | ŞİRKET.11112026-2 | 210916 | 01.07.2026 | GEF2026000000040 | 5. Ana Bakım | 230129 ×1 | 8 |
| 5 | ŞİRKET.11112026-9 | 210927 | 02.07.2026 | GEF2026000000042 | Otokar | 230022 ×37 | 14 |
| 6 | ŞİRKET.11112026-3 | 210917 | 31.07.2026 | GEA2026000000077 | İznik Bld. | 230064 ×10 | 0 |
| 7 | ŞİRKET.11112026-11 | 210934 | 01.09.2026 | GEF2026000000051 | Otokar | 230022 ×32 | 17 |
| 8 | ŞİRKET.11112026-12 | 210935 | 15.09.2026 | GEF2026000000053 | TEZ İleri Tek. | 230010 Lüp ×45 | 6 |
| 9 | ŞİRKET.11112026-4 | 210918 | 30.09.2026 | GEF2026000000057 | MKE | 230136 ADLAS ×1 (506 girdi) | 0 |
| 10 | ŞİRKET.11112026-16 | 210941 | 01.10.2026 | GEF2026000000059 | FAEM | 230094 ×1 | 3 |
| 11 | ŞİRKET.11112026-5 | 210919 | 07.10.2026 | GEF2026000000062 | Bilişim | 230063 ×5 | 0 |
| 12 | ŞİRKET.11112026-13 | 210936 | 15.10.2026 | GEF2026000000063 | FAEM | 260002 ×40 + 230093 ×20 | 2 |
| 13 | ŞİRKET.11112026-14 | 210937 | 30.10.2026 | GEF2026000000065 | Otokar | 230022 ×42 | 17 |
| 14 | ŞİRKET.11112026-6 | 210920 | 02.11.2026 | GEA2026000000105 | Nazar | 230063 ×1 | 2 |
| 15 | ŞİRKET.11112026-7 | 210921 | 02.11.2026 | GEA2026000000107 | Melekli Bld. | 230063 ×4 | 2 |
| 16 | **ŞİRKET.11112026-1 (DENEME)** | 210908 | 02.11.2026 | GEA2026000000106 | Oğuz Yılmaz | 230063 ×1 | 2 |
| 17 | ŞİRKET.11112026-8 | 210922 | 04.11.2026 | GEF2026000000067 | Genç Teknoloji | 230063 ×40 + 230064 ×10 | 2 |

- Her yeni emrin `SurecDipnot` alanı: `Fatura: <no> (<tarih>) - <cari>` → izlenebilirlik + mükerrer emir koruması.
- Açıklama düzeni yerel emirlerle aynı: `"ÜRÜN ADI + CARİ"`.
- TUSAŞ emrinde `GMP-200-240502` hattı 25.06.2026'da zaten tamamlanmış (2 stok hareketi var) — diğer hatlarda hareket yok.

### 3b. TUSAŞ `ŞİRKET.1092026-3` düzeltmeleri
1. Sıra 5 ana hat `KartId` 230013 (L v04) → **230027 (L v01)** — fatura ile birebir.
2. 230016 hattında 96 girdi vardı; kaynak **230016 reçetesinin kendisi iki kat** (96 satır / 47 tekil) → 48 mükerrer girdi silindi.
3. 13 yarı mamul hattı eklendi: 2405xx (503/504/505/507/508) + operasyonlu 240506/240509/240677 (230027 için) ve 230605 ×2, 230610/612/613/614 ×1 (230016 için).

### 3c. Yazılan reçeteler (daha önce aktif reçetesi yoktu)
| Ürün | UretimRecete Id | Kaynak (son üretim emri) | Girdi |
|---|---|---|---|
| GMP-101-230111 TX UHF CC Verici | 110346 | ŞİRKET.912026-2 (01.12.2025) | 40 |
| GMP-101-230094 B VHF Akü Beslemeli Alıcı | 110347 | ŞİRKET.25102021-10 (2021) | 31 |
| GMP-101-230093 B Anons Alıcı | 110348 | ŞİRKET.2172020-4 (2020) | 24 |

Pasif kart değişimleri: HMGMDDAL009 → YMGMÇBK0001 · HMGMDDAL086 → YMGMDPK0001 · HMGMDDAL002 (diplik takım) → YMGMÇBK0001 + YMGMDPK0001.

## 4. Muhasebe listesi

- Üretilen dosya: `muhasebe_eksi_malzeme_20261111.xlsx` (script: `tools/sene_sonu_uretim/muhasebe_eksi_liste.py`).
- ⚠ **Kullanıcı dosyayı yeniden adlandırıp düzenledi ve muhasebeye o haliyle gönderdi — O DOSYAYA DOKUNMA, üzerine yazma.** Yeni dosya adını kullanıcıdan öğren. Liste tekrar gerekirse scripti **farklı bir dosya adıyla** çalıştır ve farkı raporla.
- Hesap: emirler tamamlandığında bakiye = bugünkü bakiye + hat üretimleri − girdi tüketimleri (Tipi≠2). 11.11.2026 itibarıyla:
  - 91 satın alma kalemi ≈ 509 bin ₺ (335 bin ₺'si ADLAS LRX-20A modülü `HMMDLLSR016`)
  - 46 operasyon kartı (KOD:XX, fason/işçilik) ≈ 208 bin ₺
  - Yarı mamul eksisi: **0**
  - Emirlerle ilgisiz 4 eksi kart: HMPUL00001, GMP-200-240293, HMGMDDAL003, AKTRMİK0011
- Muhasebeye önerilen: girişleri mümkünse **ilgili emir tarihinden önceye** atsınlar (en eski 24.12.2025), yoksa kapanışta maliyet bulunamayabilir.

## 5. Muhasebeden cevap gelince — yapılacaklar (sırayla)

1. **Kullanıcının düzenlediği listenin dosya adını sor.** `muhasebe_eksi_liste.py`'yi yeni bir adla çalıştır (ör. `..._kontrol_<tarih>.xlsx`); kullanıcının listesindeki her kalemin bugünkü bakiyesini ve "emirler sonrası" bakiyesini karşılaştır → hangi kalemler düzeldi / hâlâ eksi kalacak raporla. (Bakiye: `db.sorgular.stok_guncel_bakiyeleri`.)
2. **Deneme emri `ŞİRKET.11112026-1`'i kullanıcı CEO'da kapatsın** — önce 2 yarı mamul hattı (YMGMKRT0004, YMGMÇBK0001), sonra ana hat (230063). Mümkünse maliyetlendirme de denensin.
3. Kapanış sonrası DB kontrolü: `python tools/sene_sonu_uretim/emir_detay.py "ŞİRKET.11112026-1"` → her hatta 16+17 hareketi oluşmuş mu, tarihleri, bakiyeler eksiye düştü mü.
4. Sorun yoksa kalan emirler **§3a tablosundaki sırayla** (fatura tarihi), her birinde **önce YM hatları sonra ana hat**. Her kapanıştan sonra `emir_detay.py` ile kontrol.
5. Hepsi kapanınca: eksi bakiye analizini yeniden çalıştır (`analiz.py` → `rapor.py`/`satis.py`) — hedef: 9 reçeteli mamulün eksisi kapanmış olmalı.
6. ERP-OKUMA.md + bellek güncelle, kullanıcı isterse commit/push.

## 6. Önemli teknik bulgular

- **Üretim emri yapısı** (ayrıntı ERP-OKUMA.md "Sene Sonu" bölümünde): `UretimEmri` → `UretimEmriHatPlani` (HatTipi 1 ana / 2 YM, `TalepMiktari`=adet) → `UretimEmriHatPlaniGirdi` (reçete girdisinin kopyası, `TalepMiktar=Miktar×adet`) + `UretimEmriTarihce`. Kod: `'ŞİRKET.' + gün + ay + yıl (sıfırsız, oluşturma tarihi) + '-' + sıra`.
- **Tamamlama:** CEO her hat için 1 adet 17 (Üretime Çıkış, girdi başına detay) + 1 adet 16 (Üretimden Giriş) fişi yazar, `UretimEmriHatPlaniStokHareketleri` ile bağlar (Tür 0=giriş, 1=çıkış). Maliyet alanlarını (BirimFiyat, MaliyetTutari, KalanMiktar) CEO hesaplar.
- **`StokHareket` / `StokHareketDetay` tetikleyicileri incelendi (2026-11-11, salt okuma):**
  - `StokHareket` After Insert/Update/Delete → yalnız `CariMusteriKarti.BorcToplam/AlacakToplam` günceller, o da sadece IslemKodu 1,2,3,4,15,25–29 ve MusteriKartId dolu ise → **16/17 üretim fişlerini etkilemez.**
  - `StokHareketDetay` After Insert/Update/Delete → `StokKumulatif.GirenMiktar/CikanMiktar` önbelleğini günceller. ⚠ Tetikleyici `inserted`'tan TEK satır okur → detaylar **tek tek INSERT** edilmeli (çok satırlı INSERT önbelleği bozar).
  - `trg_AfterDelete_StokHareketDetay` → silinen detay için `UretimEmriHatPlaniGirdi.KullanilanMiktar` düşer (`StokHareketDetay.UretimHatPlaniId` dolu ise).
  - Tetikleyici olan tabloda `OUTPUT INSERTED.Id` çalışmaz → `OUTPUT ... INTO @t` veya `SCOPE_IDENTITY()` kullanılmalı (`tamamla_dene.py` bu yüzden ilk INSERT'te durdu; rollback, kalıcı kayıt yok — doğrulandı; dosya commit edilmedi).
  - **Sonuç:** SQL ile kapanış teknik olarak mümkün; asıl açık nokta **maliyet alanları** (17/16 detay BirimFiyat, Tutar, MaliyetTutari, KalanMiktar) — CEO bunları kendi hesaplıyor. SQL kapanıştan sonra CEO maliyetlendirmesinin bu fişleri yeniden hesaplayıp hesaplamadığı deneme emriyle test edilmeli.
- **CEO eksi stokla üretime çıkışa izin veriyor** (SARF0000003 eksideyken 20.04.2026'da 17 hareketi almış) → muhasebe girişleri bitmeden de kapanış stok yüzünden engellenmez; girişler bakiyeyi düzeltir.
- `KayitDonemi` tablosu boş → CEO'da dönem kilidi görünmüyor (2025 tarihli Van emri için muhasebenin kendi defter kapanışı ayrıca sorulmalı).
- Çok hatlı reçete tuzağı: CEO reçeteden emir açınca **her hattın kartını** üretir (230022 reçetesi → 230016 + 230033; 230027 reçetesi → 230013). Bu yüzden ana hat elle satılan mamul yapıldı.
- Yarı mamullerin maliyetlendirmesi ana üründen önce yapılmalı (yoksa CEO NullReferenceException — ERP-OKUMA.md "Kritik — Çok katmanlı reçete maliyetlendirme").

## 7. Açık konular / riskler

1. **Mükerrer girdili 11 aktif reçete** (düzeltilmedi): 230016, 230033, 230037, 230038, 230040, 230107, GMP-300-230001, MMPBIŞIK01, MMSBIŞIK002, YMPKIŞIK003, YMTKANCA01. Açık emir **`ŞİRKET.2082026-1` (Portatif Işık Kaynağı-30, 230107 ×45)** bundan etkilenir — malzemeyi fazla düşer. Kullanıcıya bildirildi; ayrı iş olarak ele alınabilir.
2. **Bilişim `ŞİRKET.1092026-1` (230063 ×10) ve AES `ŞİRKET.962026-25` (230063 ×5)** eski açık emirler — tamamlanırlarsa 230063'e +15 girer ve listede olmayan malzeme tüketirler. Karar kullanıcıda.
3. **Otokar GEF2026000000065:** fatura 42, notta seri 2026-0094…0136 = 43. Teyit bekliyor.
4. Fatura miktarıyla birebir açıldığı için emirler kapanınca **Lüp 230010 +5, 230022 +1, 230063 +1** bakiyeye geçer.
5. Muhasebe girişleri emir tarihlerinden sonraya atılırsa kapanışta maliyet 0/yanlış çıkabilir.
6. Liste 11.11 bakiyelerine göre; aradaki başka hareketler (ör. 230107 emrinin kapanması) tutarları değiştirir.

## 8. Dosyalar

| Dosya | Ne |
|---|---|
| `tools/sene_sonu_uretim/analiz.py` | Reçeteler + bakiyeler + açık emirler → pickle (`python analiz.py <out.pkl>`) |
| `rapor.py`, `satis.py`, `plan.py` | İlk analiz Excel'i (eksi reçeteler, ürün bazında satış-stok, fatura planı) |
| `gen_plan.py` | Fatura-birebir emir planı → `plan_20261111.json` (güncel = v3; v1 ilk sürüm) |
| `emir_yaz.py` | Plandan tek emir yazar (`--commit` yoksa rollback) |
| `emir_esitle.py` | Yazılmış emri planla eşitler (FAEM'e 230093 ekleme) |
| `recete_onerisi.py` / `recete_yaz.py` | Son üretim emrinden reçete önerisi / yazımı |
| `tusas_duzelt.py`, `tusas_ek_ym.json` | TUSAŞ emri düzeltmesi |
| `muhasebe_eksi_liste.py` | Emirler sonrası eksi malzeme listesi |
| `emir_detay.py` | Bir emrin hat/girdi/hareket dökümü (kontrol için) |
| `cok_hat_incele.py` | Çok hatlı reçete ↔ yerel emir karşılaştırması |
| `tamamla_dene.py` | ⚠ Commit edilmedi, çalışmıyor (tetikleyici) — kullanma |
| `eksi_recete_uretim_analizi_20261111.xlsx` | İlk analiz raporu (12 sayfa, gitignore) |
| `recete_onerisi_20261111.xlsx` | Reçete önerileri (gitignore) |
| `muhasebe_eksi_malzeme_20261111.xlsx` | Üretilen ilk muhasebe listesi — kullanıcının düzenlediği kopya ayrı (adı sorulacak) |

Yazma işlemlerinde kullanılan kullanıcı: `BDE76801-C1DD-499E-A51B-C23901B28197` (Savaş Adıgüzel). SQL ile yazılan kayıtlar CEO'da önbellek nedeniyle hemen görünmeyebilir — CEO kapat/aç.

## 9. CEO maliyet motoru araştırması (2026-11-11, salt okuma — kod çalıştırılmadı)

- CEO programı: `\Win-3fatbi9rqaa\ceo\Ceo.exe` (v8.17.0.4, .NET Framework 4, 57 MB, 4.818 tip, son güncelleme 10.03.2026). DB erişimi Entity Framework.
- **Veritabanında maliyet prosedürü yok** (55 SP / 98 fonksiyon tarandı) → maliyet motoru Ceo.exe içinde.
- Ayrı bir iş katmanı / servis DLL'i yok; mantık WinForms ekran sınıflarının içinde: `Ceo.Uretim.FrmTopluMaliyetlendirme` (**Toplu Maliyetlendirme ekranı** — sonuç modeli: UretimEmriKodAciklama, HatGirdiKodAd, StokKartiKodAd, uyariYadaHata), `Ceo.Uretim.FrmUretimEmriHareketi` (emir ekranı), `Ceo.Uretim.TopluUretim`. İç sınıf adları obfuscate edilmiş (ör. `FrmTopluMaliyetlendirme+duWxcqVHHGM72fLUXXs`).
- **MCP değerlendirmesi:** maliyet motorunu doğrudan çağıran MCP önerilmez — Ceo.exe'yi süreç içinde yüklemek, oturum/lisans/DB bağlamını taklit etmek ve obfuscate edilmiş özel metotları çağırmak gerekir; kırılgan, güncellemede bozulur, lisans ve veri riski var. Uygulanabilir alternatif: CEO ekranlarını Windows UI Automation ile süren bir MCP (pywinauto) — prototip gerektirir.
- **Pratik yol:** CEO'nun kendi "Toplu Maliyetlendirme" ekranı var. Deneme emri SQL ile kapatılıp (maliyet 0) bu ekranla maliyetlendirilirse ve maliyetler dolarsa, kalan emirler SQL ile kapatılıp tek seferde toplu maliyetlendirilebilir. Muhasebe girişlerinden sonra test edilecek.
