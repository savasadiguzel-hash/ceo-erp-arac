# Oturum Devri — Üretim Emri Masraf Maliyetleri

**Tarih:** 15.09.2026  
**Proje:** `C:\yeni-erp`  
**Durum:** Çalışmalar proje dosyalarına kaydedildi. Commit, push, test ve exe derlemesi yapılmadı.

## Son kullanıcı talebi

CEO ERP'de üretim emri hareketlerinde **İşlemler → Maliyetlendir** çalıştırıldığında `Masraf` türündeki kalemlerin maliyetinin 0 görünmesi incelendi. Kullanıcının kontrol edebilmesi için `ŞİRKET.1862026-8` üretim emrinin masraf maliyetleri girildi. Sorun doğrulanırsa bu işlem için programda Maliyet sekmesi altında bir buton kullanılacak şekilde kaynak koduna özellik eklendi.

## Araştırma sonucu

- CEO ERP'nin üretim emri maliyetlendirme mantığında stok kalemlerinin fiyatı stok hareketlerinden gelir.
- Masraf kalemlerinde satınalma hareketindeki fiyat otomatik olarak üretim emri satırına taşınmıyor.
- Üretim emri masraf satırlarının maliyeti `UretimEmriHatPlaniGirdi.Tutar` alanından okunuyor.
- `StokBirimFiyatGetir` ve `StokBirimFiyatGetirDeposuz` sorguları yalnızca `StokHareketDetay.Turu=1` stok hareketlerini fiyat kaynağı olarak kullanıyor; masraf kartlarının `Turu=3` hareketleri bu native fiyat akışına dahil değil.
- Önceki maliyetlendirilmiş üretim emirlerinde masraf satırlarının `Tutar` alanı dolu olduğunda CEO ERP maliyeti gösteriyor. Bu nedenle sorun, masraf kartı alış fiyatlarının yokluğundan çok üretim emri girdi satırındaki `Tutar` alanının boş/0 bırakılmasıdır.

## `ŞİRKET.1862026-8` için yapılan DB işlemi

Üretim emri:

- Kod: `ŞİRKET.1862026-8`
- Id: `210899`
- Ürün: `GMP-101-230035`
- Üretim miktarı: `5`
- Masraf satırı sayısı: `7`

Sipariş tarihinden önceki son aktif masraf alış fiyatı bulunan 5 satırda şu formülle `Tutar` güncellendi:

`TalepMiktari × son alış BirimFiyatı`

Güncellenen tutarlar:

- `GMP-101-230035:10` → `7.499,999935`
- `GMP-101-230035:110` → `1.075,000030`
- `GMP-101-230035:80` → `157,500000`
- `GMP-101-230035:100` → `5.999,999900`
- `GMP-101-230035:60` → `2.500,000010`

Toplam güncellenen masraf maliyeti: **17.232,499875**

Son alış fiyatı sipariş tarihinden önce bulunamayan şu iki satır 0 bırakıldı:

- `GMP-101-230035:90`
- `GMP-101-230035:120`

Fatura, irsaliye ve stok hareketlerine dokunulmadı; yalnızca üretim emri masraf girdi satırlarının `Tutar` alanı değiştirildi.

### Yedek

İşlem öncesi yedek:

`C:\yeni-erp\masraf_maliyet_yedek_20260915_171711.json`

## Programa eklenen özellik

### DB katmanı — `db/sorgular.py`

- `uretim_emri_masraf_maliyet_onizle(conn, emir_kodu)`
  - Üretim emrinin `Tipi=2` masraf satırlarını listeler.
  - Üretim emri tarihinden önceki son aktif masraf alış fiyatını bulur.
  - Kaynağı `StokHareketDetay.IslemKartId` veya `StokMasrafKartId` üzerinden arar.
  - `IslemKodu=1` alış ve faturasız `IslemKodu=5` giriş hareketlerini dikkate alır.
  - Mevcut tutarı dolu olanları korur; fiyatı bulunmayanları işaretler.

- `uretim_emri_masraf_maliyet_uygula(conn, emir_kodu)`
  - Yalnızca `Tipi=2` ve mevcut `Tutar=0` olan, alış fiyatı bulunan satırları günceller.
  - İşlemi transaction içinde yapar.

### UI — `ui/maliyet.py`

Maliyet sekmesine **Üretim Emri Masraf Maliyetleri** grubu eklendi:

- Üretim emri kodu girişi
- Masraf maliyetlerini önizleme
- Son alış tarihi, birim fiyatı ve yeni tutarı gösteren tablo
- **Fiyatı bulunanları uygula** butonu
- Uygulama öncesinde yerel JSON yedekleme
- Uygulama sırasında fatura/irsaliye/stok hareketlerinin değişmediğini belirten onay metni

Program özelliği kaynak koda eklendi. Kullanıcının açık talimatı gereği mevcut exe yeniden derlenmedi; sonraki oturumda derleme ayrıca istenirse yapılacak.

### Dokümantasyon — `ERP-OKUMA.md`

Üretim emri masraf maliyetlerinin kaynak fiyat kuralları, hesaplama yöntemi, güncellenen alan, yedekleme ve native CEO ERP'de yeniden **Maliyetlendir** çalıştırma adımları eklendi.

## Önceki oturumda tamamlanan ilgili çalışmalar

- Aktif reçetelerdeki 50 birim tutarsızlığı giderildi: `GMP-101-230134`, `GMP-101-230136`, `MMSBIŞIK002`.
- Fatura/irsaliye hareketleri değiştirilmedi.
- Üretim emri masraf maliyetleri için eklenen özellik kaynak dosyalarına kaydedildi.
- Birim düzeltme yedekleri proje klasöründe tutuluyor.

## Sonraki oturum için devam planı

1. Kaynak uygulama çalıştırılarak Maliyet sekmesindeki yeni buton görsel olarak kontrol edilecek.
2. `ŞİRKET.1862026-8` kodu ile önizleme ve uygulama akışı test edilecek.
3. Native CEO ERP kapatılıp açıldıktan sonra ilgili emirde **İşlemler → Maliyetlendir** çalıştırılarak 5 masraf satırının fiyatı kontrol edilecek.
4. Kullanıcı sonucu doğrularsa genel kullanım için fiyat kaynağı kuralları ve olası `AlisFiyat1` standardizasyonu gözden geçirilecek.
5. Exe derlemesi yalnızca kullanıcı ayrıca istediğinde yapılacak.

## Çalışma kuralları

- Kullanıcı commit yapılmamasını ve kendisi söylemeden derleme/test yapılmamasını belirtti.
- Bu nedenle bu oturumda commit, push, `python main.py` ve `build.bat` çalıştırılmadı.
