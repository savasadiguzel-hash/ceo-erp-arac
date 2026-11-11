"""TUSAŞ açık emri ŞİRKET.1092026-3 düzeltmesi (kullanıcı kararı 2026-11-11):
 1) 230016 satırındaki girdiler 230016 reçetesinden İKİ KAT kopyalanmış (reçetenin kendisi 96 satır / 47 tekil, her grup çift) →
    her (Tipi, KartId, Miktar) grubu yarıya indirilir (en küçük Id'ler kalır).
 2) 230027 satırının tükettiği yarı mamuller için plan PLAN-03'teki HatTipi=2 satırları eklenir.
Stok hareketi bağlı satıra dokunulmaz. Kullanım: python tusas_duzelt.py plan.json [--commit]"""
import sys, io, json
from collections import defaultdict
from datetime import datetime
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection
USER = 'BDE76801-C1DD-499E-A51B-C23901B28197'; ADET = '4ACC21E3-3140-4863-922D-A0B3D35DE8C1'; DEPO = 2
plan = {p['plan_no']: p for p in json.load(open(sys.argv[1], encoding='utf-8'))}[sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else 'PLAN-03']
COMMIT = '--commit' in sys.argv
c = get_connection(**DB_DEFAULTS); c.autocommit = False; cur = c.cursor()

def recete_girdileri(kod):
    cur.execute("""SELECT h.Id, h.KartId, g.Tipi, g.KartId, g.Miktar, g.BirimId, g.DepoId, g.SabitMiktar, g.FireOrani, g.GarantiKapsaminda, g.Aciklama
      FROM UretimRecete ur JOIN UretimReceteHatPlani h ON h.UretimReceteId=ur.Id JOIN UretimReceteHatPlaniGirdi g ON g.UretimReceteHatPlaniId=h.Id
      WHERE ur.Kodu=? AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi=0) ORDER BY h.Id, g.Id""", kod)
    rs = cur.fetchall()
    tuketilen = {r[3] for r in rs if r[2] != 2}
    alt = {r[0] for r in rs if r[1] in tuketilen and len({x[0] for x in rs}) > 1}
    return [r[2:] for r in rs if r[0] not in alt]

def operasyon_girdileri(kod):
    cur.execute("SELECT 1, Id, 1.0, StokBirim, ?, 0, NULL, 0, NULL FROM StokKarti WHERE Aktif=1 AND Kodu LIKE ? AND Kodu NOT LIKE ? ORDER BY Kodu", DEPO, kod + ':%', kod + ':%:%')
    rs = cur.fetchall()
    if not rs:
        cur.execute("SELECT 2, Id, 1.0, StokBirimId, ?, 0, NULL, 0, NULL FROM StokMasrafKarti WHERE Kodu LIKE ? AND Kodu NOT LIKE ? ORDER BY Kodu", DEPO, kod + ':%', kod + ':%:%')
        rs = cur.fetchall()
    if not rs: raise ValueError(f'{kod}: reçete de operasyon kartı da yok')
    return [tuple(r[:3]) + ((r[3] or ADET),) + tuple(r[4:]) for r in rs]

def girdiler(kod):
    cur.execute("SELECT COUNT(*) FROM UretimRecete WHERE Kodu=? AND (KullanimDisi IS NULL OR KullanimDisi=0)", kod)
    return recete_girdileri(kod) if cur.fetchone()[0] else operasyon_girdileri(kod)

try:
    cur.execute("SELECT Id FROM UretimEmri WHERE Kodu='ŞİRKET.1092026-3'"); eid = cur.fetchone()[0]
    cur.execute("""SELECT h.Id, sk.Kodu, h.HatTipi, h.sira, (SELECT COUNT(*) FROM UretimEmriHatPlaniStokHareketleri x WHERE x.UretimEmriHatPlaniId=h.Id)
      FROM UretimEmriHatPlani h JOIN StokKarti sk ON sk.Id=h.KartId WHERE h.UretimEmriId=?""", eid)
    hatlar = {r[1]: r for r in cur.fetchall()}
    # 1) 230016 mükerrer girdiler
    h16 = hatlar['GMP-101-230016']
    if h16[4]: raise RuntimeError('230016 hattında stok hareketi var')
    cur.execute("SELECT Id, Tipi, KartId, Miktar FROM UretimEmriHatPlaniGirdi WHERE UretimEmriHatPlaniId=? ORDER BY Id", h16[0])
    grup = defaultdict(list)
    for gid, t, k, m in cur.fetchall(): grup[(t, k, float(m))].append(gid)
    if '--mukerrer-yok' in sys.argv: grup = {}   # mükerrer temizliği daha önce yapıldı (2026-11-11)
    if any(len(v) % 2 for v in grup.values()): raise RuntimeError('tek sayılı grup var — iki kat kopya varsayımı tutmuyor')
    sil = [gid for v in grup.values() for gid in v[len(v) // 2:]]
    for i in range(0, len(sil), 100):
        p = sil[i:i + 100]; cur.execute(f"DELETE FROM UretimEmriHatPlaniGirdi WHERE Id IN ({','.join('?'*len(p))})", *p)
    print(f'230016 hattı: {sum(len(v) for v in grup.values())} girdi → {sum(len(v) for v in grup.values()) - len(sil)} ({len(sil)} mükerrer silindi)')
    # 2) Yarı mamul hatları
    sira = max(r[3] or 0 for r in hatlar.values())
    for y in plan['yari_mamul']:
        kod, mik = y['kod'], y['miktar']
        if kod in hatlar: print(f'  {kod} zaten var, atlandı'); continue
        cur.execute("SELECT Id, StokBirim, SeriNoTakibi FROM StokKarti WHERE Kodu=? AND Aktif=1", kod); kid, birim, seri = cur.fetchone()
        if seri: raise RuntimeError(f'{kod}: SeriNoTakibi açık')
        sira += 1; birim = birim or ADET
        cur.execute("""INSERT INTO UretimEmriHatPlani (UretimEmriId, HatTipi, KartId, Miktar, Birim, TalepMiktari, StokDepoId, sira, TalepBirim)
            OUTPUT INSERTED.Id VALUES (?, 2, ?, 1, ?, ?, ?, ?, ?)""", eid, kid, birim, mik, DEPO, sira, birim)
        hid = int(cur.fetchone()[0]); n = 0
        for (tipi, gk, gm, gb, gd, sabit, fire, gar, gac) in girdiler(kod):
            cur.execute("""INSERT INTO UretimEmriHatPlaniGirdi (UretimEmriHatPlaniId, Tipi, KartId, Miktar, TalepMiktar, StokBirim, StokDepoId,
                FireOrani, SabitMiktar, Aciklama, GarantiKapsami, Yazilmasin) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                hid, tipi, gk, gm, float(gm) if sabit else float(gm) * mik, gb, gd if gd is not None else DEPO, fire, bool(sabit), gac, bool(gar))
            n += 1
        print(f'  eklendi: sira {sira} HatTipi 2 {kod} x{mik:g} ({n} girdi)')
    cur.execute("UPDATE UretimEmri SET ModifiedBy=?, ModificationTime=? WHERE Id=?", USER, datetime.now().replace(microsecond=0), eid)
    if COMMIT: c.commit(); print('KAYDEDİLDİ')
    else: c.rollback(); print('DENEME — geri alındı')
except Exception as e:
    c.rollback(); print('HATA, geri alındı:', e); raise
