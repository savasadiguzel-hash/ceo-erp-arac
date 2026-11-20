"""CEO'da kapatılan hatların fişlerini hat_kapat.py --beklenen çıktısıyla satır satır karşılaştırır. Salt okuma.
Kullanım: python kapanis_karsilastir.py "ŞİRKET.1092026-3" tusas_beklenen_maliyet_20261120.json
Kontroller: belge tarihi, satır sayısı/miktar, birim fiyat (FIFO tahmini vs CEO), 16 = 17 toplamı, emir durumu, StokKumulatif = formül, eksiye düşen."""
import sys, io, json
from collections import defaultdict
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import stok_guncel_bakiyeleri

EMIR, DOSYA = sys.argv[1], sys.argv[2]
bek = json.load(open(DOSYA, encoding='utf-8'))
c = get_connection(**DB_DEFAULTS); cur = c.cursor()
cur.execute("SELECT Id, DurumId FROM UretimEmri WHERE Kodu=?", EMIR); eid, durum = cur.fetchone()
print(f'{EMIR}: durum {durum} ({"Tamamlandı" if durum == 5 else "AÇIK"})')
hatlar = defaultdict(list)
for b in bek: hatlar[b['hat']].append(b)
kartlar = set(); genel_fark = 0.0
for hat, satir in hatlar.items():
    cur.execute("""SELECT sh.Id, sh.IslemKodu, sh.BelgeTarihi, sh.ToplamTutar FROM UretimEmriHatPlani h JOIN StokKarti hk ON hk.Id=h.KartId
      JOIN UretimEmriHatPlaniStokHareketleri x ON x.UretimEmriHatPlaniId=h.Id JOIN StokHareket sh ON sh.Id=x.StokHareketId
      WHERE h.UretimEmriId=? AND hk.Kodu=?""", eid, hat)
    fis = {r[1]: r for r in cur.fetchall()}
    if 17 not in fis: print(f'\n## {hat}: HENÜZ KAPANMAMIŞ'); continue
    cur.execute("""SELECT COALESCE(sk.Kodu, m.Kodu), d.Turu, d.Miktar, d.BirimFiyat, d.MaliyetTutari, d.BirimKatsayisi FROM StokHareketDetay d
      LEFT JOIN StokKarti sk ON sk.Id=d.IslemKartId AND d.Turu=1 LEFT JOIN StokMasrafKarti m ON m.Id=d.IslemKartId AND d.Turu=3 WHERE d.HareketId=? ORDER BY d.Id""", fis[17][0])
    gercek = defaultdict(list)
    for k, t, m, bf, mt, bk in cur.fetchall(): gercek[(k, t)].append((float(m), float(bf or 0), float(mt or 0), float(bk or 0))); kartlar.add(k)
    cur.execute("SELECT d.Miktar, d.MaliyetTutari FROM StokHareketDetay d WHERE d.HareketId=?", fis[16][0]); g16 = cur.fetchone()
    bt = fis[17][2].strftime('%d.%m.%Y'); beklenen_t = satir[0]['tarih']
    top17 = sum(x[2] for v in gercek.values() for x in v)
    b16 = next(b for b in satir if b['turu'] == 16)
    print(f"\n## {hat}: belge {bt} {'✓' if bt == beklenen_t else '✗ beklenen ' + beklenen_t} | 17 satır {sum(len(v) for v in gercek.values())} "
          f"(beklenen {len([b for b in satir if b['turu'] != 16])}) | CEO maliyet {float(g16[1]):,.2f} / benim {b16['birim_fiyat'] * b16['miktar']:,.2f} "
          f"| 16=17 toplamı {'✓' if abs(float(g16[1]) - top17) < 0.05 else '✗ ' + f'{top17:,.2f}'}")
    kartlar.add(hat); fark_say = 0
    kalan = {k: list(v) for k, v in gercek.items()}
    for b in satir:
        if b['turu'] == 16: continue
        lst = kalan.get((b['kod'], b['turu']))
        if not lst: print(f"   ✗ {b['kod']} CEO fişinde yok"); fark_say += 1; continue
        m, bf, mt, bk = lst.pop(0)
        sorun = []
        if abs(m - b['miktar']) > 1e-6: sorun.append(f'miktar {m:g}≠{b["miktar"]:g}')
        if abs(bk - m) > 1e-6: sorun.append(f'BirimKatsayisi {bk:g}')
        if abs(bf - b['birim_fiyat']) > max(0.01, abs(bf) * 0.001):
            sorun.append(f'fiyat CEO {bf:,.4f} / benim {b["birim_fiyat"]:,.4f} (fark {(bf - b["birim_fiyat"]) * m:+,.2f})'); genel_fark += (bf - b['birim_fiyat']) * m
        if sorun: fark_say += 1; print(f"   ~ {b['kod']:22s} " + '; '.join(sorun))
    for k, v in kalan.items():
        for x in v: print(f'   ✗ fazla satır CEO fişinde: {k[0]} x{x[0]:g}'); fark_say += 1
    print(f'   farklı satır: {fark_say}')
kl = sorted(kartlar)
if not kl: sys.exit()
bak =stok_guncel_bakiyeleri(c, kl, '2099-12-31')
cur.execute(f"SELECT sk.Kodu, k.GirenMiktar-k.CikanMiktar FROM StokKumulatif k JOIN StokKarti sk ON sk.Id=k.StokKartId WHERE sk.Kodu IN ({','.join('?'*len(kl))})", *kl)
kum = {r[0]: float(r[1] or 0) for r in cur.fetchall()}
print('\nStokKumulatif ≠ formül:', [(k, bak[k], kum.get(k)) for k in kl if kum.get(k) is not None and abs(bak[k] - kum[k]) > 0.01])
for T in sorted({b['tarih'] for b in bek}):
    d, m_, y = T.split('.')
    print(f'{T} itibarıyla eksi:', {k: v for k, v in stok_guncel_bakiyeleri(c, kl, f'{y}-{m_}-{d}').items() if v < -1e-6})
print(f'toplam maliyet farkı (CEO − benim): {genel_fark:+,.2f}')
