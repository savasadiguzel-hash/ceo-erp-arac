# CEO ERP Proje Kuralları

## ERP-OKUMA.md Güncelleme Zorunluluğu

Her kod değişikliğinden, hata düzeltmesinden veya yeni özellik eklenmesinden sonra
**ERP-OKUMA.md dosyası mutlaka güncellenmeli ve GitHub'a push edilmelidir.**

Bu adımlar her değişiklik döngüsünün son adımıdır:
1. Kodu değiştir
2. Test et
3. exe derle (gerekiyorsa)
4. **ERP-OKUMA.md güncelle** ← UNUTMA
5. `git add -A && git commit && git push`

## Dağıtım Kuralları

- Her exe derlemesinden sonra `config.json` → `dist/config.json` kopyalanmalı
- Her push'ta `dist/CEO-ERP.exe` ve `dist/config.json` birlikte gönderilmeli

## Proje Bilgileri

- Veritabanı: SQL Server, WIN-3FATBI9RQAA\CEO1, Firma 504
- Demo mod: Kaldırıldı — sadece canlı DB
- GitHub: https://github.com/savasadiguzel-hash/ceo-erp-arac
