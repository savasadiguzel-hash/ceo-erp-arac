# Oturum Devri — SIK Vida Listesi → Malzeme Talebi A-31

**Tarih:** 12.11.2026
**Durum:** Tamamlandı. CEO ERP'ye **A-31** (MalzemeTalep Id **1233**) yazıldı. Kod değişikliği yok, commit yapılmadı.

> ⚠ "CEO ERP'de SADECE OKUMA" kuralına **kullanıcının açık isteğiyle** yapılmış istisna (A-29/A-30 ile aynı yöntem).

## Akış

1. Kullanıcı iki sayfalık el yazısı vida listesinin fotoğrafını gönderdi → `vida_listesi_20261112.xlsx` (35 ham satır → 27 birleşik kalem; sayfalar: "Birleşik Liste", "Ham Liste (resimden)").
2. Belirsiz okumalar kullanıcıya soruldu:
   - Listedeki "Karda" ifadeleri "Kaide" olarak düzeltildi.
   - M4x48 Alyan, aslında M4x18 Alyan Başlı Topbaş, 80 adet.
   - Kullanıcı şu okumaları onayladı: M4x10 Alyan 150; M3x3 topbaş; M4x8 setskur 200; M6x15 setskur 100; PFC + Balast arası ikisi de M3x10, toplam 100.
3. Resimde tikli kalemler siparişten düşüldü. Yatık "L" işaretleri de kullanıcı onayıyla tik sayıldı. Düşülenler: M2 somun (50+100), M2x5 topbaş 100, M4x18 Alyan 80, M4x22 pullu 60, M3x22 60, M3x5 havşa 30, M2,5x20 havşa 100.
4. Kullanıcı önce "satın alma siparişi" dedi. `StokSiparis`'e daha önce hiç yazılmamıştı; tedarikçi (`MusteriKartId`) zorunlu, her sipariş için 8 `StokSiparisDurum` satırı ve bir `StokSiparisTarihce` kaydı gerekiyor. Bu yüzden kullanıcı malzeme talebini seçti; siparişe CEO'da talepten kendisi dönüştürecek.
5. Kartlar SIK reçetesinden (`GMP-100-230002` → `YMB-V00R01-2200xx`) ve ölçü/baş tipi eşleşmesiyle seçildi. Son 2 ayın taleplerinde çakışan kalem çıkmadı.

## A-31 (Id 1233) — Proje 80117 SABİT IŞIK, Personel 18, Depo 2, Durum 1

| # | Stok Kodu | Malzeme | Adet |
|---|---|---|---|
| 1 | HMVİDA0026 | M2,5x5 DIN965 yıldız havşa inox | 100 |
| 2 | HMVİDA0049 | M3x10 ISO7046 yıldız havşa psl | 50 |
| 3 | HMVİDA0067 | M3x10 ISO7045 yıldız silindir psl | 150 |
| 4 | HMVİDA0069 | M3x12 yıldız silindir | 50 |
| 5 | HMVİDA0068 | M3x5 ISO7045 yıldız silindir psl | 400 |
| 6 | HMVİDA0066 | M3x8 ISO7045 yıldız silindir psl | 200 |
| 7 | HM.İNX.VİD.012 | M4x10 DIN7380 bombe imbus inox | 150 |
| 8 | HMVİDA0009 | M4x10 ISO7045 yıldız silindir psl | 80 |
| 9 | HMVİDA0064 | M4x12 ISO7045 yıldız havşa inox | 50 |
| 10 | YMSTKPSL015 | M3x4 setskur siyah | 200 |
| 11 | YMSTKPSL012 | M4x8 setskur | 200 |
| 12 | YMSTKPSL011 | M6 bilyalı setskur (listede M6x15; kart adında boy yok) | 100 |
| 13 | HMPUL00005 | M3 DIN125 geniş pul | 250 |
| 14 | HMSOMUN003 | M3 somun inox | 300 |
| 15 | HMSOMUN004 | M4 somun inox | 150 |
| 16 | serbest (Turu=5) | M2x16 yıldız havşa paslanmaz vida | 50 |
| 17 | serbest | M2,5x7 yıldız havşa paslanmaz vida | 100 |
| 18 | serbest | M3x3 yıldız silindir (topbaş) vida | 100 |
| 19 | serbest | M4x18 yıldız silindir (topbaş) vida | 100 |
| 20 | serbest | M3x8 erkek-dişi spacer | 100 |

Detay Id 2401–2420, toplam 2.880 adet. ModifiedBy/ModificationTime baştan dolduruldu.
Id 1232, ilk denemenin rollback'inde boş kaldı (yanlış kontrol toplamı yüzünden; kayıt oluşmadı).

## Açık kalanlar

- 5 serbest satırın stok kartı yok. Kart açılırsa satırlar kartlı satırla değiştirilebilir.
- YMSTKPSL011'in M6x15 olup olmadığı doğrulanmalı.
- Kullanıcı CEO'yu kapatıp açınca talep görünür; siparişe dönüştürme kullanıcıda.
- Yazma scripti: `%TEMP%\mt_a31.py` (repo'ya eklenmedi).
