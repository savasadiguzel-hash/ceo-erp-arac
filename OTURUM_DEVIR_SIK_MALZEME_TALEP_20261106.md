# Oturum Devri — Sabit Işık Kaynağı (SIK) Bağlantı Elemanları Malzeme Talebi

**Tarih:** 06.11.2026
**Proje:** `C:\yeni-erp`
**Durum:** Tamamlandı. CEO ERP'ye **A-29** (MalzemeTalep Id **1230**) malzeme talebi yazıldı; kullanıcı ERP'de açıp not alanını düzenledi ve kaydetti. Kod değişikliği yok, commit yapılmadı.

> ⚠ "CEO ERP'de SADECE OKUMA" kuralına **kullanıcının açık isteğiyle** yapılmış bir istisnadır.

## Talep

1. `SIK\SIK_BAGLANTI_ELEMANLARI_15_ADET.xlsx` dosyasını incelemek.
2. 40 bağlantı elemanını CEO ERP stok kodlarıyla eşleştirmek.
3. ERP stoklarına güvenmeden, **16 ürün** için ihtiyacı sıfırdan hesaplamak.
4. Son 2 ayın taleplerinde zaten olan kalemleri düşüp kalanları ERP'de malzeme talep formuna girmek.

## Çıktılar (`SIK\` klasörü, git'e eklenmedi)

| Dosya | İçerik |
|---|---|
| `SIK_BAGLANTI_ELEMANLARI_15_ADET.xlsx` | Kullanıcının orijinal dosyası (değiştirilmedi) |
| `SIK_BAGLANTI_ELEMANLARI_15_ADET_STOKKODLU.xlsx` | J–N sütunları: Stok Kodu, ERP Adı, Güven, Alternatif, Not; Detay sayfasında K = stok kodu |
| `SIK_BAGLANTI_ELEMANLARI_16_ADET_SATINALMA.xlsx` | C3 = 16; ilk sayfa "Satınalma (16 Adet)" — perçin somunlar çıkarılmış, 38 kalem / 2.880 adet |

## Stok kodu eşleştirme kuralı

1. Kalem SIK reçetesinde (`GMP-100-230002`, alt gruplar `YMB-V00R01-220012…220020`) kullanılıyorsa o kart.
2. Değilse standardı ve ölçüsü tutan, en son alışı olan aktif kart.
3. Eşdeğer kabul edilenler: DIN 7985 ≡ ISO 7045, DIN 965 ≡ ISO 7046, DIN 912 ≡ ISO 4762, DIN 7380 ≡ ISO 7380.

Sonuç: Kesin 10, Yüksek 19, Orta 8, Yok 3 (M4x35 yıldız bombe, ISO 10642 M3x8, YK-03).
Not: Arka Panel, Batarya, Lamba ve Aksesuarlar alt reçeteleri ERP'de boş.

## Talepten düşülenler

- **Perçin somunlar** (M3 `SARF0000096`, M4 `HMSOMUN014`): kullanıcı aldığını söyledi.
- **Son 2 ay (06.09.2026 sonrası) SIK taleplerinde olanlar:** A-15 (Id 1205, 21.09.2026, Tamamlandı) ve A-28 (Id 1229, 03.11.2026, Yeni Talep). Alternatif kodlar da tarandı, 24 kalem düşüldü.
- **GMP-200 imalat parçaları** (`GMP-200-230579`, `GMP-200-230580`, `GMP-200-230405`): kullanıcı kararıyla çıkarıldı.
- Başka projelerin taleplerinde olan 3 kalem (#6, #20, #26) kullanıcı kararıyla **eklendi**.

## ERP'ye yazılan kayıt — A-29 (Id 1230)

Başlık: Tarih 06.11.2026, Durum 1 (Yeni Talep), Personel 18 (Savaş Adıgüzel), Depo 2 (Merkez), Proje 80117 "SABİT IŞIK 18 ADET", CreatedBy `BDE76801-…` (Savaş).

| # | Stok Kodu | Malzeme | Adet |
|---|---|---|---|
| 1 | HMVİDA0029 | M2,5x5 yıldız silindir başlı vida | 144 |
| 2 | HMVİDA0024 | M2,5x10 yıldız silindir başlı vida | 32 |
| 3 | HMVİDA0034 | M3x6 yıldız silindir başlı vida | 112 |
| 4 | *(Turu=5 serbest)* | ISO 10642 M3x8 havşa başlı imbus — kart yok | 160 |
| 5 | HM.CVT.İMB.028 | M4x8 ISO 10642 havşa başlı imbus | 32 |
| 6 | HMCIVATA06 | M2x5 DIN 912 imbus | 32 |
| 7 | HM.İNX.VİD.008 | M3x6 DIN 912 imbus | 16 |
| 8 | YMSTKPSL002 | M2,5x3 setskur | 32 |
| 9 | HMSOMUN002 | M2,5 somun inox | 32 |
| 10 | HMSOMUN006 | M5 somun inox | 16 |
| 11 | HMAYSGM001 | 4 mm ay segman | 16 |
| 12 | *(Turu=5 serbest)* | YK-03 yaylı kilit — kart yok | 16 |

Detay Id'leri: 2341–2352.

## Karşılaşılan sorunlar ve çözümleri

1. **Talep ERP listesinde görünmedi** → CEO kapatılıp açılınca göründü (önbellek).
2. **Not değiştirilirken "SqlDateTime taşması" hatası** → `ModificationTime` ve `ModifiedBy` NULL bırakılmıştı. ERP UPDATE'te iyimser eşzamanlılık kontrolü için `@Original_ModificationTime` gönderiyor; NULL değer MinValue'ya dönüşüp taşıyor. `ModificationTime = CreationTime`, `ModifiedBy = CreatedBy` yapılarak düzeltildi. 213 talep içinde bu alanları NULL olan tek kayıt buydu.

## MalzemeTalep'e SQL ile yazma şablonu (ileride gerekirse)

- **Başlık:** `BolgeId=2`, `DepoKartId=2`, `YaziciSablonu='MalzemeTalep.repx'`, `BelgeSeriNo='A'`, `BelgeSiraNo = MAX+1` (sayaç tablosu yok, UPDLOCK ile), toplamlar 0, `Acik=0`, **`ModificationTime=CreationTime`, `ModifiedBy=CreatedBy`**.
- **Detay Turu=1:** `KartId`, `KdvYuzdesi = kart KdvOrani`, `StokBirimId = kart StokBirim`, `Miktar = BirimKatsayi = KalanMiktar`, `Tutar=0`, `SatirKdvMatrahi=0`, `Yazdirma=0`, `SiraNo`.
- **Detay Turu=5 (serbest satır):** `Aciklama` + `Miktar` (diğerleri Turu=1 gibi, kart alanları NULL).
- **Durumlar:** 1 Yeni Talep, 2 İncelemede, 3 Onaylandı, 4 Tamamlandı, 5 Reddedildi.
- Trigger yok. Liste ekranı `MalzemeTalepView`'dan okuyor.
- Yazdıktan sonra kullanıcıya **CEO'yu kapatıp açmasını** söyle.

## Açık kalanlar

- 4 ve 12 numaralı serbest satırların stok kartı yok. Kart açılırsa satırlar kartlı satırla değiştirilmeli.
- Excel ile ERP reçetesi arasındaki farklar ayrıca incelenmeli: M2.5x5 vida 23 ↔ 14 adet, M2.5x20 ↔ M2.5x10 havşa, kulpta ISO 10642 ↔ yıldız havşa, Dişli'de M3 somun ↔ M3 insert.
- Geçici scriptler oturum geçici klasöründe kaldı (`%TEMP%\sik_*.py`, `mt_*.py`); repo'ya eklenmedi.

---

# Ek — Akülü Kart Malzeme Talebi (A-30)

**Tarih:** 06.11.2026 · **Durum:** Tamamlandı. Kullanıcı ERP'de kontrol etti, sorun yok.

- **Kaynak:** `Akülü\Kopya akülü_sipariş.xlsx` (6 kart, %10 yedek; adetler Excel'in `I` sütunundan).
- **Kayıt:** MalzemeTalep **Id 1231, A-30**, Durum 1 (Yeni Talep), Personel 18, Depo 2, **Proje 80087 ANONS** (ERP'de Akülü projesi yok). ModifiedBy/ModificationTime baştan dolduruldu.
- **Detay:** Id 2353–2380, 28 satır. 18 kartlı (Excel A sütunundaki kodlar, 19'u da ERP'de aktif) + 10 serbest satır.
- **Kullanıcı kararları:** Kodsuz kalemler kart eşleştirmeden serbest satır; 18 pin soket (HMGMSKT0004) dahil; LP2950 → HMGMENT0084 (3,3 V); soğutucu çıkarıldı.
- **Serbest satırlar için ERP'deki aday kartlar:** TDA7396 → `TDA7396`, 0 Ω 1206 → `ERJ-8GEY0R00V`, 1/10/47/100 µF → `HMGMKDS0032/0034/0037/0038`, röle → `HMGMKLM0014`. 78M08 DPAK, 100 kΩ ve 470 kΩ 1206 için kart yok.
- Geçici scriptler: oturum scratchpad'i (`ak_kontrol.py`, `ak_ara*.py`, `ak_talep.py`, `ak_yaz.py`), repo'ya eklenmedi.
