"""Daha önce yazılmış bir emri plan.json'daki haliyle eşitler (eksik hat ekler, miktarı değişen hattın TalepMiktari
ve girdilerinin TalepMiktar'ını günceller). Stok hareketi bağlı hatta dokunmaz. Hat silmez.
Kullanım: python emir_esitle.py plan.json PLAN-12 [--commit]"""
import sys, io, json
from datetime import datetime
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection
USER = 'BDE76801-C1DD-499E-A51B-C23901B28197'; ADET = '4ACC21E3-3140-4863-922D-A0B3D35DE8C1'; DEPO = 2
plan = {p['plan_no']: p for p in json.load(open(sys.argv[1], encoding='utf-8'))}
p = plan[sys.argv[2]]; COMMIT = '--commit' in sys.argv
if p['uyari']: sys.exit(f"Uyarılı plan: {p['uyari']}")
c = get_connection(**DB_DEFAULTS); c.autocommit = False; cur = c.cursor()

def recete_girdileri(kod):
    cur.execute("""SELECT h.Id, h.KartId, g.Tipi, g.KartId, g.Miktar, g.BirimId, g.DepoId, g.SabitMiktar, g.FireOrani, g.GarantiKapsaminda, g.Aciklama
      FROM UretimRecete ur JOIN UretimReceteHatPlani h ON h.UretimReceteId=ur.Id JOIN UretimReceteHatPlaniGirdi g ON g.UretimReceteHatPlaniId=h.Id
      WHERE ur.Kodu=? AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi=0) ORDER BY h.Id, g.Id""", kod)
    rs = cur.fetchall()
    if not rs: raise ValueError(f'Reçete girdisi yok: {kod}')
    tuketilen = {r[3] for r in rs if r[2] != 2}
    alt = {r[0] for r in rs if r[1] in tuketilen and len({x[0] for x in rs}) > 1}
    return [r[2:] for r in rs if r[0] not in alt]

cur.execute("SELECT Id, Kodu FROM UretimEmri WHERE SurecDipnot LIKE ?", f"%{p['fatura']}%")
eid, ekodu = cur.fetchone()
cur.execute("""SELECT h.Id, h.HatTipi, sk.Kodu, h.TalepMiktari, h.sira,
   (SELECT COUNT(*) FROM UretimEmriHatPlaniStokHareketleri x WHERE x.UretimEmriHatPlaniId=h.Id)
   FROM UretimEmriHatPlani h JOIN StokKarti sk ON sk.Id=h.KartId WHERE h.UretimEmriId=?""", eid)
mevcut = {(r[1], r[2]): r for r in cur.fetchall()}
hedef = [(1, a['kod'], a['miktar']) for a in p['ana']] + [(2, y['kod'], y['miktar']) for y in p['yari_mamul']]
sira = max([r[4] or 0 for r in mevcut.values()], default=0)
try:
    for tip, kod, mik in hedef:
        m = mevcut.get((tip, kod))
        if m:
            if abs(float(m[3]) - mik) < 1e-9: continue
            if m[5]: raise RuntimeError(f'{kod}: hatta stok hareketi var, güncellenmez')
            cur.execute("UPDATE UretimEmriHatPlani SET TalepMiktari=? WHERE Id=?", mik, m[0])
            cur.execute("UPDATE UretimEmriHatPlaniGirdi SET TalepMiktar = CASE WHEN SabitMiktar=1 THEN Miktar ELSE Miktar*? END WHERE UretimEmriHatPlaniId=?", mik, m[0])
            print(f'  güncellendi: HatTipi {tip} {kod} {float(m[3]):g} → {mik:g} ({cur.rowcount} girdi)')
        else:
            cur.execute("SELECT Id, StokBirim, SeriNoTakibi FROM StokKarti WHERE Kodu=? AND Aktif=1", kod); kid, birim, seri = cur.fetchone()
            if seri: raise RuntimeError(f'{kod}: SeriNoTakibi açık')
            sira += 1; birim = birim or ADET
            cur.execute("""INSERT INTO UretimEmriHatPlani (UretimEmriId, HatTipi, KartId, Miktar, Birim, TalepMiktari, StokDepoId, sira, TalepBirim)
                OUTPUT INSERTED.Id VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)""", eid, tip, kid, birim, mik, DEPO, sira, birim)
            hid = int(cur.fetchone()[0]); n = 0
            for (tipi, gk, gm, gb, gd, sabit, fire, gar, gac) in recete_girdileri(kod):
                cur.execute("""INSERT INTO UretimEmriHatPlaniGirdi (UretimEmriHatPlaniId, Tipi, KartId, Miktar, TalepMiktar, StokBirim, StokDepoId,
                    FireOrani, SabitMiktar, Aciklama, GarantiKapsami, Yazilmasin) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                    hid, tipi, gk, gm, float(gm) if sabit else float(gm) * mik, gb, gd if gd is not None else DEPO, fire, bool(sabit), gac, bool(gar))
                n += 1
            print(f'  eklendi: sira {sira} HatTipi {tip} {kod} x{mik:g} ({n} girdi)')
    now = datetime.now().replace(microsecond=0)
    cur.execute("UPDATE UretimEmri SET ModifiedBy=?, ModificationTime=? WHERE Id=?", USER, now, eid)
    print(f"{'COMMIT' if COMMIT else 'DENEME'} {ekodu} (Id {eid})")
    if COMMIT: c.commit(); print('KAYDEDİLDİ')
    else: c.rollback(); print('Geri alındı (deneme).')
except Exception as e:
    c.rollback(); print('HATA, geri alındı:', e); raise
