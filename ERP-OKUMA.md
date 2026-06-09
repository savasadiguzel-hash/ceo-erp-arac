# CEO ERP Araçları

**GitHub:** https://github.com/savasadiguzel-hash/ceo-erp-arac  
**Dağıtım:** `dist/CEO-ERP-Araclar.exe` (~54 MB)  
**Son güncelleme:** 2026-06-09

---

## Sekmeler

| Sekme | Ne yapar |
|---|---|
| 🔗 Mamül Ağacı | Reçetesiz + faturalı stokları tespit eder, mamüle bağlar |
| 💰 Maliyet | LIFO / FIFO / Ağırlıklı Ortalama — Excel maliyet raporu |
| ⚙ SW Kodlama | SolidWorks montaj → AI sınıflandırma → GEM/YMB kodu |
| 📦 Stok Kartı Aktar | SW sonrası CEO ERP'ye otomatik stok kartı açar |
| 🧾 Satış Faturaları | Tarih aralığına göre satış fatura/irsaliye listesi + Excel çıktısı |

---

## Mamül Ağacı Sekmesi

### Tarama Sayfası — Kesişim Kümesi

Reçetesiz + faturalı stokları bulur (faturada var ama hiçbir reçetede bileşen değil).

**Fiyat yöntemi seçimi:** FIFO (ilk alış) / LIFO (son alış) / Ağırlıklı Ortalama — tarama başlamadan seçilir.

**Excel çıktısı — 2 sayfa:**
- `Kesişim Kümesi` — stok bazında özet (7 sütun: Stok Kodu / Stok Adı / Fatura Sayısı / Birim Fiyat / İlk–Son Fatura / Tedarikçi)
- `Fatura Detayları` — her fatura satırı ayrı (9 sütun: + İşlem Türü / Belge No / Tarih / Miktar / Tutar)

**Kritik filtreler (değiştirme):**
- `sk.Id NOT IN (UretimReceteHatPlaniGirdi.KartId)` — bileşen/operasyon alt kodları kesişimden çıkar
- `shd.Turu = 1` — yalnızca ürün satırları; Turu=3 kur farkı/muhasebe satırlarında `IslemKartId` gerçek stoğu göstermez
- `StokHareketDetay JOIN sk.Id` üzerinden yapılır — aksi takdirde 2 milyon+ Kartezyen çarpım

**Bilinen veri kalitesi sorunu:** ERP'deki bazı `sk.Adi` değerleri sonda `\n\n` içerir. `kesisim_excel_kaydet` tüm string değerlere `.strip()` uygular; uygulanmazsa `wrap_text=True` + `vertical=center` + sabit satır yüksekliği metni görünmez kılar.

### Eşleştirme Sayfası

Tespit edilen stokları mamüle bağlar. Stok detay etiketleri fare ile seçilebilir (kopyalama/arama kolaylığı).

---

## Maliyet Sekmesi

- **Bağlan ve Mamülleri Yükle** → DB bağlantısı arka thread'de kurulur, pencere donmaz
- Yükleme tamamlanınca buton "✅ N mamül yüklendi" olur; arama kutusu anlık filtreler
- **Fiyat kaynağı:** `IslemKodu IN (1, 5)` — alış faturası + alış irsaliyesi; üretimden giriş, sayım, devir hariç
- **Performans:** `stok_fiyatlari_toplu()` ile N bileşen için tek SQL sorgusu; BOM listesi özyinelemeli hesaplamada önbelleğe alınır

---

## Satış Faturaları Sekmesi

- **Bağlan** → DB bağlantısı arka thread'de kurulur
- Tarih aralığı girip **Faturaları Getir** → `satis_faturalari()` çalışır
- `IslemKodu IN (2, 6)` — satış faturası + irsaliye; `shd.Turu = 1` ürün satırlarını filtreler
- 9 kolonlu tablo: Tarih / Belge Türü / Belge No / Müşteri / Stok Kodu / Stok Adı / Miktar / Birim Fiyat / Tutar
- Arama kutusu anlık filtreler (müşteri, stok kodu, belge no)
- **Excel'e Aktar** → openpyxl ile biçimlendirilmiş xlsx, son satırda toplam tutar
- `shd.Turu = 1` kayıt dönmüyorsa ERP versiyonuna göre değer farklı olabilir; `sorgular.py:satis_faturalari()` içinde ayarla

---

## Veritabanı

| Parametre | Değer |
|---|---|
| Sunucu | `WIN-3FATBI9RQAA\CEO1` |
| Firma | 504 |
| Auth | SQL Server (`sa`), şifre `config.json`'da base64 |
| Kural | **SADECE OKUMA** — yazma yalnızca Stok Kartı Aktar akışında, kullanıcı onayıyla |

---

## Kurulum & Çalıştırma

```
git clone https://github.com/savasadiguzel-hash/ceo-erp-arac
cd ceo-erp-arac
pip install -r requirements.txt
python main.py
```

Gerekli `.env` (SW Kodlama + Stok Kartı için):
```
GEMINI_API_KEY=...
CEO_SQL_CONN=DRIVER={SQL Server};SERVER=WIN-3FATBI9RQAA\CEO1;UID=sa;PWD=...
```

Derleme: `build.bat` → `dist/CEO-ERP-Araclar.exe` + `dist/config.json`

---

## Klasör Yapısı

```
main.py / config.py / config.json / build.bat
db/      → baglanti.py, sorgular.py
logic/   → maliyet.py, excel.py
ui/      → ana_pencere.py, maliyet.py, mamul_agaci_tab.py, tarama.py, eslestirme.py, rapor.py
          tab_satis_faturalari.py, tab_erp_aktar.py, tab_sw.py, baglanti.py, stil.py
sw/      → SW Kodlama modülleri (classifier, pipeline, renamer, erp_handler, vision_handler)
dist/    → CEO-ERP-Araclar.exe, config.json
```

---

## Sıradaki Geliştirmeler

1. **BOM otomasyonu** — SW çalışması sonrası `UrunAgaci + UrunAgaciDetay` otomatik oluşturma
2. **PDF gömme** — teknik resim PDF'lerini `StokKarti.DokumanPath`'e bağlama
3. **Canlı SW testi** — SW Kodlama sekmesini iş makinesinde SolidWorks 2019 ile doğrulama
