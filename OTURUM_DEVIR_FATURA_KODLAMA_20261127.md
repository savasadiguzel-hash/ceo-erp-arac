# Oturum Devri — Satınalma Fatura Mail Cevapları

**Tarih:** 27.11.2026
**Proje:** `C:\yeni-erp`
**Önceki Oturum:** `OTURUM_DEVIR_FATURA_KODLAMA_20261126.md`
**Durum:** 4 satınalma fatura maili canlı CEO ERP (`504`, salt-okuma) doğrulamasıyla cevaplandı; mail formatı kuralı proje hafızasına (`AGENTS.md` ve `CLAUDE.md`) işlendi.

---

## Cevaplanan Mailler (4 Fatura)

| # | Fatura No | Tedarikçi | Proje Kodu | Stok Kodu / Ayrım | ERP Referans |
|---|---|---|---|---|---|
| 1 | `TKL2026000003595` | Tek-El Metal | `SABİT IŞIK 18 ADET` (`Id=80117`) | `HMPOMLVH005` (`30x40x40MM POM LEVHA SİYAH`) — 4 Adet × 62,50 TL | `Sip=593677` (proje kodu eklenecek) |
| 2 | `TKL2026000003607` | Tek-El Metal | `SABİT IŞIK 18 ADET` | `HMALMLAM098` (1,75 kg) + `HMALMLAM073` (1,05 kg) × 395,00 TL | `Sip=593676` (proje kodu eklenecek) |
| 3 | `TKL2026000003618` | Tek-El Metal | `SABİT IŞIK 18 ADET` | `HMPOMÇBK020` (`Ø25MM-POM ÇUBUK SİYAH`) — 1,51 kg × 275,00 TL | `Sip=593678` (proje kodu eklenecek) |
| 4 | `BDS2026000002884` | Baskı Devre | `0601` (`ANONS`) | Tek panelde 3 kart × 10 adet × **202,00 TL** = 6.060,00 TL KDV hariç:<br>• `HMGMKRT0094` (Tuş Kartı V.03)<br>• `HMGMKRT0066` (Verici Kodlayıcı Kartı)<br>• `HMGMKRT0090` (Verici USB Giriş Kartı V2.4) | • Talep `184` (`Id=1216`) / `Sip=593576` (`0601`)<br>• Talep `185` (`Id=1217`, sipariş henüz bağlı değil)<br>• Talep `186` (`Id=1219`) / `Sip=593625` (`0601` eklenecek) |

---

## Proje Kurallarına İşlenenler

- `AGENTS.md` ve `CLAUDE.md` dosyalarına **Mail Cevapları** kuralı eklendi: mail cevap taslakları alıntı çizgisi (`>`), ayırıcı çizgi (`---`) ve markdown biçimlendirmesi (`**`, `` ` ``) olmadan, doğrudan kopyalayıp maile yapıştırılabilecek düz metin olarak verilir.

---

## Kalan Açık Faturalar (26.11 listesinden)

1. **Tek-El (`TKL2026000003566`):** `Sip=593675` (`HMPROJE0048` → KG birimli `HMPOMLVH016`, 5,3 kg × 300 TL) + proje `SABİT IŞIK 18 ADET`.
2. **Aymak (`GID2026000000030` — `ÖC-053`):** Parça/proje teyidi ve gerekirse yeni kart açma.
3. **Sonersan (`SNR2026000000099`):** Cari açma (`VKN 7740663986`) ve `:40` büküm kartı dağıtımı.
4. **Stannic (`ST02026000001089`):** 14 satır `:60` kaplama eşleştirmesi.
5. **Özgenç Cıvata (`OGF2026000003190`):** Açıklamalı PDF / `OGI2026000003229` irsaliyesi bekleniyor.
