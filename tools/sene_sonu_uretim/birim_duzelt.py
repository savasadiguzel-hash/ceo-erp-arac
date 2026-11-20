"""Girdi birimi kart birimiyle uyuşmayan bir kartı (vars. HMGMDDAL001 TAKIM→ADET) düzeltir.
Kapsam: (1) sene sonu açık emirlerimizin girdileri (SurecDipnot 'Fatura:%', DurumId=3), (2) kartı kullanan tüm reçete girdileri.
Kullanım: python birim_duzelt.py [KART_KODU] [--commit]   (--commit yoksa rollback = deneme)
Eski değerler birim_duzelt_yedek_<tarih>.json'a yazılır."""
import sys, io, json
from datetime import datetime
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import birimleri_getir

KULLANICI = 'BDE76801-C1DD-499E-A51B-C23901B28197'
args = [a for a in sys.argv[1:] if not a.startswith('--')]
KOD = args[0] if args else 'HMGMDDAL001'
COMMIT = '--commit' in sys.argv
c = get_connection(**DB_DEFAULTS); c.autocommit = False; cur = c.cursor()
bir = {str(g).casefold().strip('{}'): n for n, g in birimleri_getir(c).items()}
B = lambda g: bir.get(str(g or '').casefold().strip('{}'), str(g))

cur.execute("SELECT Id, StokBirim FROM StokKarti WHERE Kodu=?", KOD)
kid, kb = cur.fetchone()
print(f'{KOD} kart birimi: {B(kb)}')
cur.execute("""SELECT g.Id, ue.Kodu, hk.Kodu, g.StokBirim FROM UretimEmriHatPlaniGirdi g JOIN UretimEmriHatPlani h ON h.Id=g.UretimEmriHatPlaniId
  JOIN UretimEmri ue ON ue.Id=h.UretimEmriId JOIN StokKarti hk ON hk.Id=h.KartId
  WHERE g.KartId=? AND g.StokBirim<>? AND ue.DurumId=3 AND ue.SurecDipnot LIKE 'Fatura:%'""", kid, kb)
emir = cur.fetchall()
cur.execute("""SELECT g.Id, r.Id, r.Kodu, g.BirimId FROM UretimReceteHatPlaniGirdi g JOIN UretimReceteHatPlani h ON h.Id=g.UretimReceteHatPlaniId
  JOIN UretimRecete r ON r.Id=h.UretimReceteId WHERE g.KartId=? AND g.BirimId<>?""", kid, kb)
recete = cur.fetchall()
for r in emir: print(f'  emir   girdi {r[0]}  {r[1]:22s} {r[2]:16s} {B(r[3])} → {B(kb)}')
for r in recete: print(f'  reçete girdi {r[0]}  {r[2]:22s} (Id {r[1]}) {B(r[3])} → {B(kb)}')

yedek = {'kart': KOD, 'yeni_birim': str(kb), 'zaman': datetime.now().isoformat(),
         'emir_girdi': [{'id': r[0], 'emir': r[1], 'eski': str(r[3])} for r in emir],
         'recete_girdi': [{'id': r[0], 'recete_id': r[1], 'recete': r[2], 'eski': str(r[3])} for r in recete]}
n1 = n2 = 0
for r in emir:
    cur.execute("UPDATE UretimEmriHatPlaniGirdi SET StokBirim=? WHERE Id=?", kb, r[0]); n1 += cur.rowcount
for r in recete:
    cur.execute("UPDATE UretimReceteHatPlaniGirdi SET BirimId=? WHERE Id=?", kb, r[0]); n2 += cur.rowcount
for rid in sorted({r[1] for r in recete}):
    cur.execute("UPDATE UretimRecete SET ModifiedBy=?, ModificationTime=GETDATE() WHERE Id=?", KULLANICI, rid)
# doğrulama
cur.execute("""SELECT COUNT(*) FROM UretimEmriHatPlaniGirdi g JOIN UretimEmriHatPlani h ON h.Id=g.UretimEmriHatPlaniId JOIN UretimEmri ue ON ue.Id=h.UretimEmriId
  WHERE g.KartId=? AND g.StokBirim<>? AND ue.DurumId=3 AND ue.SurecDipnot LIKE 'Fatura:%'""", kid, kb); k1 = cur.fetchone()[0]
cur.execute("""SELECT COUNT(*) FROM UretimReceteHatPlaniGirdi WHERE KartId=? AND BirimId<>?""", kid, kb); k2 = cur.fetchone()[0]
print(f'güncellenen: emir girdisi {n1}, reçete girdisi {n2} | kalan uyumsuz: emir {k1}, reçete {k2}')
if COMMIT and k1 == 0 and k2 == 0:
    c.commit()
    fn = rf'C:\yeni-erp\birim_duzelt_yedek_{datetime.now():%Y%m%d_%H%M%S}.json'
    json.dump(yedek, open(fn, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('COMMIT edildi. Yedek:', fn)
else:
    c.rollback(); print('ROLLBACK (deneme)' if not COMMIT else 'ROLLBACK — doğrulama başarısız')
