# Oturum Devri — Satınalma Fatura Kodlama İncelemesi (Üretim)

**Tarih:** 26.11.2026
**Proje:** `C:\yeni-erp`
**Durum:** Tamamlandı. CEO ERP (`504`) üzerinde yalnızca salt-okuma sorguları yapıldı; veritabanına yazma ve git commit yapılmadı.

---

## Girdi ve Çıktı

- **Girdi (`C:\yeni-erp\Fatura\`):** 6 PDF dosyası, toplam **16 tekil fatura** (`TEK-EL 16.11 3566.pdf` 14 sayfalık toplu PDF; 3 Tek-El faturasının ürün açıklamalı tekil PDF'leri de klasörde mevcut).
- **Çıktı:** `C:\yeni-erp\Fatura\Uretim_Fatura_Kodlama_20261126.xlsx`
  - 4 sayfa: `Özet`, `Üretim Faturaları`, `Sonersan-Stannic Referans`, `Satınalma Notu`
  - Kapsam: **11 üretim faturası**, **33 veri satırı**, KDV hariç toplam **164.139,75 TL**
  - Üretim betiği (scratch): `uretim_fatura_excel.py`

---

## Kullanıcı Kararları

1. **Üretim dışı bırakılanlar (5 fatura):**
   - Market: Fixgross (`EF12026000124709` · 9.073,15 TL KDV dahil), BİM (`AF02026007568058` · 322,00 TL KDV dahil)
   - Araç: Otokoç (`OSA2026000021579` · 18.505,30 TL)
   - IT / Sunucu: Netinternet (`NE52026000001366` · 4.202,50 TL — ERP'de `NE620261366`, `StokHareket.Id=745022`, masraf `219` olarak zaten işli)
   - Kırtasiye: İrem Kırtasiye (`IG12026000007338` · 3.062,50 TL — `Sip=593679`, masraf `169` hazır, NATO tesis güvenlik çıktısı)
2. **Tek-El Metal (4 fatura):** Tamamı **`SABİT IŞIK 18 ADET`** projesine ait. `TKL2026000003566` (5,3 kg × 300 TL) KG birimli **`HMPOMLVH016`** kartına geçirilecek (`Sip=593675`'teki ADET kartı `HMPROJE0048` yerine).
3. **Baskı Devre (`BDS2026000002884` — `D.1586-47`):** Birim fiyat ayrımı `10 Adet × 606,00 TL = 6.060,00 TL` (`12 USD @ 50,5 TL`) olarak işlendi; kart ve proje elektronikten teyit edilmek üzere **"KONTROL / TEYİT"** bırakıldı (aday: `HMGMKRT0090`, `Sip=593625`).
4. **Aymak (`GID2026000000030` — `ÖC-053`):** ERP'de kayıt yok; **"KONTROL / TEYİT"** (yeni stok/masraf kartı veya teyit gerekli) olarak işaretlendi.
5. **Sonersan (`SNR2026000000099`) ve Stannic (`ST02026000001089`):** Ham satırlar Excel'e **"EŞLEŞTİRME BEKLİYOR"** olarak alındı; ERP'deki aday `:40` büküm ve `:60` kaplama kartları `Sonersan-Stannic Referans` sayfasında öneri/referans olarak listelendi.
6. **Özgenç Cıvata (`OGF2026000003190`, İrs. `OGI2026000003229`):** PDF'te ürün adları görünmediği için **"BELGE EKSİK"** durumuyla Excel'e dahil edildi.

---

## 11 Üretim Faturası Özeti

| # | Fatura No | Tedarikçi | Durum | KDV Hariç (TL) | ERP Sipariş / Proje / Not |
|---|---|---|---|---:|---|
| 1 | `GID2026000000031` | Aymak Teknoloji | HAZIR | 33.000,00 | `Sip=593674` · `0102` (`230035:10`, `230036:10`) & `0704` (`260126:10`, `260127:10`) birebir hazır |
| 2 | `TRN2026000000067` | Tufan Torna | HAZIR | 73.500,00 | `Sip=593670` · `OTOKAR ROMANYA 2026` (`GMP-101-230033:90`, 42×1.750 TL) |
| 3 | `TKL2026000003566` | Tek-El Metal | HAZIR | 1.590,00 | `Sip=593675` · `SABİT IŞIK 18 ADET` · `HMPROJE0048` → `HMPOMLVH016` (5,3 kg × 300 TL) güncellenecek |
| 4 | `TKL2026000003595` | Tek-El Metal | HAZIR | 250,00 | `Sip=593677` · `HMPOMLVH005` (4 Ad) · Proje `SABİT IŞIK 18 ADET` eklenecek |
| 5 | `TKL2026000003607` | Tek-El Metal | HAZIR | 1.106,00 | `Sip=593676` · `HMALMLAM098` (1,75 kg) + `HMALMLAM073` (1,05 kg) · Proje eklenecek |
| 6 | `TKL2026000003618` | Tek-El Metal | HAZIR | 415,25 | `Sip=593678` · `HMPOMÇBK020` (1,51 kg) · Proje `SABİT IŞIK 18 ADET` eklenecek |
| 7 | `BDS2026000002884` | Baskı Devre | KONTROL / TEYİT | 6.060,00 | `D.1586-47` → 10 × 606 TL; aday `HMGMKRT0090` (`Sip=593625`), elektronik teyidi bekliyor |
| 8 | `GID2026000000030` | Aymak Teknoloji | KONTROL / TEYİT | 30.000,00 | `ÖC-053` (2 × 15.000 TL) ERP'de yok; parça/proje teyidi & yeni kart gerekli |
| 9 | `SNR2026000000099` | Sonersan Metal | EŞLEŞTİRME BEKLİYOR | 2.350,00 | Cari (`VKN 7740663986`) yok; 15 ad büküm + 1.000 TL perçin somun → aday Sabit Işık `:40` kartları |
| 10 | `ST02026000001089` | Stannic Grup | EŞLEŞTİRME BEKLİYOR | 14.356,00 | 14 satır ebat/kaplama → aday Sabit Işık `:60` (17 kart) & `0704` `:60` (2 kart) + sert krom |
| 11 | `OGF2026000003190` | Özgenç Cıvata | BELGE EKSİK | 1.512,50 | 5 satırda ad yok (`...0699/2523/1549/2658/0895`) · İrs. `OGI2026000003229` / açıklamalı PDF gerekli |
| | **TOPLAM** | | **33 satır** | **164.139,75** | |

---

## Açık Kalanlar

1. **Tek-El (`Sip=593675..593678`):** `Sip=593675` kartını `HMPOMLVH016` (5,3 kg × 300 TL) olarak güncelleme ve 4 siparişe `SABİT IŞIK 18 ADET` proje kodunu ekleme.
2. **Baskı Devre (`BDS2026000002884`):** Elektronikten `D.1586-47` kart kodu (`HMGMKRT0090`?) ve proje (`0601`/`0602`) teyidi.
3. **Aymak (`GID2026000000030`):** `ÖC-053` parça/proje teyidi ve gerekirse yeni stok/masraf kartı açma.
4. **Sonersan (`SNR2026000000099`):** Cari kartı açma (`VKN 7740663986`), 15 ad büküm + 1.000 TL perçin somun bedelinin hangi `:40` kartlara dağıtılacağını belirleme (`GMP-200-230308:4O` kodunda `0` yerine `O` harfi var).
5. **Stannic (`ST02026000001089`):** 14 satırın `:60` kaplama kartlarıyla eşleştirilmesi (`2CMQ` 150 ad → güçlü aday `GMP-200-230378:60`; `12CM Q` / `10CM Q` 1'er ad → `0704 LABİT` `GMP-200-260127:60` / `260126:60`; 18 ad ince + 9 ad kalın sert krom parça teyidi).
6. **Özgenç (`OGF2026000003190`):** Satınalmadan açıklamalı orijinal e-fatura PDF'i veya `OGI2026000003229` irsaliyesinin istenmesi.
