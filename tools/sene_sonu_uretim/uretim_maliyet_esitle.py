"""Kapalı bir üretim hattının giriş (16) maliyetini çıkış (17) fişindeki satır maliyetlerinin toplamına eşitler.
CEO'nun kendi kuralı: 16 maliyeti = 17 satırlarının MaliyetTutari toplamı (+ masraf). Doğrulandı (962026-3/-9, 2026-11-20).
Kullanım: python uretim_maliyet_esitle.py "ŞİRKET.962026-3" "ŞİRKET.962026-9" [--kart GMP-101-230016] [--commit]
Güncellenen alanlar: 16 detay BirimFiyat/Tutar/MaliyetTutari, 16 ve 17 başlık ToplamTutar/NetTutar. Satırlar tek tek güncellenir (tetikleyici).
StokKumulatif önce/sonra karşılaştırılır; değişirse ROLLBACK. Eski değerler uretim_maliyet_yedek_<tarih>.json'a yazılır."""
import sys, io, json
from datetime import datetime
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection

a = sys.argv[1:]; COMMIT = '--commit' in a
KART = a[a.index('--kart') + 1] if '--kart' in a else 'GMP-101-230016'
EMIRLER = [x for x in a if x.startswith('ŞİRKET.')]
c = get_connection(**DB_DEFAULTS); c.autocommit = False; cur = c.cursor()
yedek = []; kart_ids = set(); tamam = True

def kumulatif(ids):
    cur.execute(f"SELECT StokKartId, GirenMiktar, CikanMiktar FROM StokKumulatif WHERE StokKartId IN ({','.join(map(str, ids))})")
    return {r[0]: (r[1], r[2]) for r in cur.fetchall()}

plan = []
for ek in EMIRLER:
    cur.execute("""SELECT h.Id, h.TalepMiktari FROM UretimEmriHatPlani h JOIN UretimEmri ue ON ue.Id=h.UretimEmriId JOIN StokKarti hk ON hk.Id=h.KartId
      WHERE ue.Kodu=? AND hk.Kodu=?""", ek, KART); hid, adet = cur.fetchone(); adet = float(adet)
    cur.execute("""SELECT sh.Id, sh.IslemKodu, sh.ToplamTutar, sh.NetTutar FROM UretimEmriHatPlaniStokHareketleri x JOIN StokHareket sh ON sh.Id=x.StokHareketId
      WHERE x.UretimEmriHatPlaniId=?""", hid); fis = {r[1]: r for r in cur.fetchall()}
    cur.execute("SELECT SUM(MaliyetTutari), COUNT(*) FROM StokHareketDetay WHERE HareketId=? AND Aktif=1", fis[17][0]); top, n = cur.fetchone()
    cur.execute("SELECT Id, IslemKartId, Miktar, BirimFiyat, Tutar, MaliyetTutari FROM StokHareketDetay WHERE HareketId=?", fis[16][0]); gd = cur.fetchall()
    top = round(float(top), 6); bf = round(top / adet, 6)
    plan.append((ek, fis, gd, top, bf, adet, n))
    for g in gd: kart_ids.add(g[1])
    cur.execute("SELECT IslemKartId FROM StokHareketDetay WHERE HareketId=?", fis[17][0]); kart_ids |= {r[0] for r in cur.fetchall()}
once = kumulatif(kart_ids)
for ek, fis, gd, top, bf, adet, n in plan:
    eski = float(gd[0][5] or 0)
    print(f'{ek}: çıkış {n} satır toplam {top:,.2f} | giriş eski {eski:,.2f} → yeni {top:,.2f} | birim {eski/adet:,.2f} → {bf:,.2f}')
    for g in gd:
        yedek.append({'tablo': 'StokHareketDetay', 'Id': g[0], 'BirimFiyat': str(g[3]), 'Tutar': str(g[4]), 'MaliyetTutari': str(g[5])})
        cur.execute("UPDATE StokHareketDetay SET BirimFiyat=?, Tutar=?, MaliyetTutari=? WHERE Id=?", bf, round(bf * float(g[2]), 6), round(bf * float(g[2]), 6), g[0])
    for ik in (16, 17):
        f = fis[ik]; yedek.append({'tablo': 'StokHareket', 'Id': f[0], 'ToplamTutar': str(f[2]), 'NetTutar': str(f[3])})
        cur.execute("UPDATE StokHareket SET ToplamTutar=?, NetTutar=? WHERE Id=?", round(top, 2), round(top, 2), f[0])
sonra = kumulatif(kart_ids)
fark = {k: (once.get(k), sonra.get(k)) for k in kart_ids if once.get(k) != sonra.get(k)}
print('StokKumulatif değişen kart:', len(fark), list(fark.items())[:5])
if COMMIT and not fark:
    c.commit(); fn = rf'C:\yeni-erp\uretim_maliyet_yedek_{datetime.now():%Y%m%d_%H%M%S}.json'
    json.dump(yedek, open(fn, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); print('COMMIT edildi. Yedek:', fn)
else: c.rollback(); print('ROLLBACK' + (' — StokKumulatif değişti, yazılmadı' if fark else ' (deneme)'))
