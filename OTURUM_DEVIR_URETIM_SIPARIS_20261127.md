# Oturum Devri — Satış Siparişleri, Fason İncelemesi ve HAV-HPB0001 Kapanışı

**Tarih:** 27.11.2026
**Proje:** `C:\yeni-erp`
**Önceki Oturumlar:** `OTURUM_DEVIR_SENE_SONU_URETIM_20261120.md`, `OTURUM_DEVIR_FATURA_KODLAMA_20261127.md`
**Durum:** `HAV-HPB0001 ×43` üretim emri açılıp kapatıldı (Ford faturası eksiği kapandı); 2026 açık satış siparişleri ve malzeme yeterliliği analiz edildi; 23.11 muhasebe listesi henüz girilmediği için 4 emir muhasebe girişi bekliyor.

---

## 1. Bu Oturumda Yapılanlar

### A. Satınalma Sipariş No Karşılıkları
- Önceki maillerde geçen `593675..593678`, `593576`, `593625`, `593670`, `593674` sayıları CEO ERP veritabanı iç kimliği (`StokSiparis.Id`) olup ekranda görünmüyor.
- Gerçek ekran `SiparisNo` karşılıkları (`1511..1514`, `1434`, `1473`, `1507`, `1510`) çıkarılıp `Fatura/Siparis_No_Karsiliklari_20261127.xlsx` (yerel) dosyasına aktarıldı.
- **Not:** Bundan sonraki maillerde DB `Id` yerine mutlaka CEO ERP ekranındaki `SiparisNo` yazılacak.

### B. CEO ERP Satış Siparişi & Fason Modülü İncelemesi (Salt-Okuma)
- **Satış Siparişi (`StokSiparis`, `Turu='1'`):** Aktif kullanılıyor (toplam 2.010 sipariş; 2026'da 184 sipariş, 24'ü `DEVAM EDİYOR`, 158'i `TAMAMLANDI`). Ancak 2018–2025 arası **332 eski sipariş** hâlâ `DEVAM EDİYOR` durumunda açık bırakılmış.
- **Üretim Emri ↔ Satış Siparişi:** `UretimEmri` tablosunda `SiparisId` ve `ProjeId` alanları mevcut ancak `0 / 862` emirde doldurulmuş.
- **Fason Sipariş (`FasonSiparis`, `FasonSiparisUretilen`, `FasonSiparisGonderilen`, `MalzemeTalep.IsFasonSiparis`):** Tablolar mevcut ancak bugüne kadar **0 kayıt** var (hiç kullanılmamış).

### C. `HAV-HPB0001 ×43` (Ford `GEF2026000000070`) Kapanışı — ✅ TAMAMLANDI
- **Emir:** `ŞİRKET.27112026-1` (`UretimEmri.Id = 210943`), tarih `09.11.2026`, `DurumId = 5` (Tamamlandı).
- **Fişler:** `17` Sarf Fişi `Id = 745062`, `16` Üretimden Giriş Fişi `Id = 745063`.
- **Maliyet:** Toplam `56.856,75 TL` · Birim `1.322,25 TL` (`AKGMDDHOP01` ×43 @ `613,26 TL` + `AKGMDDUNT03` ×43 @ `708,99 TL`).
- **Kapanış Sonrası Bakiyeler (`StokKumulatif = formül` doğrulandı):**
  - `HAV-HPB0001`: `−27` → **`+16`** (`#2063` Resul Kurdoğlu ×3 siparişini de stoktan karşılıyor)
  - `AKGMDDHOP01`: `143`
  - `AKGMDDUNT03`: `157`
- **Yerel yedek:** `hav_hpb0001_commit_20261127_171612.json` (commit edilmez).

### D. Muhasebe Eksik Giriş Kontrolü (27.11.2026)
- 23.11.2026'da gönderilen `muhasebe_eklenecek_kalemler_FIYATLI_20261123.xlsx` (56 kalem) **henüz CEO ERP'ye girilmemiş**.
- En son sayım fazlası/giriş fişi hâlâ 19.11.2026 tarihli `SYM202600003` (`Id=744507`, 137 satır); listedeki 56 kalemden **55'i hâlâ eksik**.

---

## 2. ▶ Bir Sonraki Oturumda Devam Noktası

### 1. Muhasebe Girişi Gelince Kapatılacak 4 Emir (En Acil)
Fatma Hanım 23.11 listesini (`tarih ≤ 06.06.2026`) girince `muhasebe_kontrol.py` ile doğrula, ardından kapat:
1. `ŞİRKET.1862026-10` (RSTEK 12X ×1) — önce 3 mükerrer girdiyi çıkar (`YMB-V00-R00-23001`, `YMB-V00-R00-23002`, `SPORTAKS004`)
2. `ŞİRKET.1862026-7` (RSTEK 120–122 mm ×1) — açık soru: `YMB-V00-R00-23008` ×3 mükerrer mi teyit
3. `ŞİRKET.1862026-8` (Unirobotics 12,7 mm ×5) — `masraf_doldur.py --emir` sonrası kapat
4. `GMP-101-230093` (FAEM ×50, bakiye `−50`) — yeni emir aç (`12.11.2026`, YM hatları `YMGMKRT0004` & `YMGMÇBK0001` dahil) ve kapat

*(Bu 4 emir kapanınca 2026 faturalı tüm eksi ürünler sıfırlanmış olacak.)*

### 2. Kasım 2026 Açık Satış Siparişleri (2026 Bitmeden Sevk Edilecekler)
- **Hemen üretime hazır (0 eksik):**
  - `GMP-101-230036 ×9` (`#2054` MKE ×9 + `#2061` Unirobotics ×2 − bakiye 2)
  - `YMGMÇBK0001 ×10` (`#2062` Kemalpaşa Bel. ×10)
  - `YMGMKRT0004 ×1` (`#2050` Gerede Bel. ×1)
- **Sadece 1–2 kalem eksik:**
  - `GMP-101-230032 ×2`, `230040 ×2` *(⚠ iki kat reçete kontrolü)*, `230038 ×1` *(⚠ iki kat reçete kontrolü)* → tek eksik `HM.İNX.VİD.017`
  - `GMP-101-230035 ×2` → `HM.İNX.VİD.017` + `HMÇLKISH007` (1,50 kg)
- **Çoklu eksik:**
  - `GMP-101-230063 ×5` (`#2060` Oğuz Yılmaz — 6 eksik: `ETHYDX00004` + 5 sarf/klemens)
  - `GMP-101-230013 ×1` (`#2061` Unirobotics — 8 eksik)
  - Reçetesiz 0 bakiyeli: `GMP-101-230034 ×2` (`#2061` Unirobotics)

### 3. Fatura Bekleyen Açık Emir
- `ŞİRKET.2082026-1` (`GMP-101-230107 ×45`, `#2053` TEZ İLERİ ×36): Faturası kesildiğinde kapatılacak *(kapatmadan önce `230107` iki kat reçete düzeltmesi yapılmalı)*.

### 4. Satıştan Teyit Bekleyen Eski 2026 Siparişleri
- `#1964` Extra Otomasyon (10.06 — `HAV-HPB0001 ×115`, `230085 ×60`, `230111 ×3`), `#1974` Emergen (25.06 — `230063 ×58`), `#2040` Fatih Emirdağ (20.10 — `230093 ×50`, FAEM faturasıyla aynıysa kapatılmamış olabilir) hâlâ geçerli mi teyit edilecek.
