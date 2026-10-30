# Oturum Devri — LRF 6001 Maliyet Çalışması

**Tarih:** 30.10.2026
**Proje:** `C:\yeni-erp`
**Durum:** Maliyet hesaplandı, iki Excel çıktısı üretildi. Scriptler `tools/lrf6001_maliyet/` altında. CEO ERP'ye hiçbir şey yazılmadı.

## Talep

`LRF 6001 ÜRÜN BOM.xlsx` dosyasındaki ürünün maliyetini çıkarmak; alış günündeki kur ile bugünkü kur farkını maliyete yansıtmak.

## Çıktılar (proje kökünde, `.gitignore` gereği commit edilmez)

- `LRF6001_maliyet_20261030.xlsx` — Özet / Fiyatı Olmayanlar / Detay / Kontrol Edilecekler
- `LRF 6001 ÜRÜN BOM - MALİYETLİ.xlsx` — orijinal BOM'un kopyası, fiyatlar kodların karşısında (orijinal dosya değişmedi)

Yeniden üretmek için: `tools/lrf6001_maliyet/maliyet_hesapla.py` docstring'indeki 3 komut.

## Sonuç

| Grup | Alış günü (₺) | Güncel kur (₺) |
|---|---|---|
| Elektronik kartlar (PCB dahil) | 5.861,72 | 18.903,25 |
| Aksesuar & OEM modül | 13.061,37 | 15.494,84 |
| Kablaj | 4.016,83 | 5.756,32 |
| Mekanik (operasyonlar) | 22.545,33 | 36.321,67 |
| Optik | 3.662,01 | 12.974,16 |
| Çevre birimleri (BC300 çanta) | 3.559,84 | 3.578,38 |
| **Toplam** | **52.707,09** | **93.028,62 (1.871,81 $)** |

Kur (GunlukKur, 30.10.2026): USD 49,6997 · EUR 55,4243.

## Kullanıcı kararları

- OEM modül: `OEM-LRF-NP` kullanılacak (Excel'de `NOPTEL LRF 221`).
- Kur farkı maliyete yansıtılacak.
- Çanta: BC300 (`GMP-110-230004`, son alış 14.10.2026, 72 USD = 3.559,84 ₺).
- Fiyatı olmayan kalemler raporda ayrı sayfada belirtilecek.

## Kullanıcıya sorulmadan yapılan varsayımlar (değiştirilebilir)

- OLED ekran: `MDP05APRMRO` (Excel "MDP05A"); alternatif `MDP05BPRMHO` (415,91 EUR, 2026).
- Optik adetleri boş → hepsi 1.
- Penta prizma: Excel'deki `HMCOMPRS010`; alternatif `GMP-401-230014`.
- Elektronik: Excel kart sayfaları + ERP reçetesinden çıplak PCB.

## Açık konular

1. **OEM modül fiyatı:** son alış NPT12167 (24.10.2025, LRF 6002 projesi, 6 adet) 263,92 EUR/adet; 2021'de 2.311 EUR/adet (410 adet). Teknik resimde modül **QS42753BE**; ERP kartı adında QS42526AE. Kullanıcı faturayı kontrol edecek. 2021 fiyatıyla toplam ≈ 203.000 ₺.
2. **20 fiyatsız kalem:** MTi-3-0I-T IMU, pil kartı PCB, 15 mekanik parçanın stok kartı yok, 230029/230031 kartlı ama alışsız, `GMP-200-230043:80` operasyonu faturasız.
3. Tripod, omuz taşıma çantası, boyun askısı — ürün seçimi bekleniyor.
4. İşçilik / SMT dizgi / montaj dahil değil.
