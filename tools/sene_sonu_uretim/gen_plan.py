"""Fatura miktarıyla birebir iş emri planı → plan.json
Kural: eksi bakiyeli mamulü eksiye düşüren her fatura için 1 emir; miktar = faturadaki miktar (birebir).
Yarı mamul: kronolojik (eski fatura önce) mevcut stoktan karşılanamayan kısım HatTipi=2 satırı olur.
Emir tarihi = fatura tarihi − 1 gün (hafta sonuna denk gelirse önceki Cuma)."""
import sys, io, pickle, json
from datetime import timedelta
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from collections import defaultdict
from config import DB_DEFAULTS
from db.baglanti import get_connection
d = pickle.load(open(sys.argv[1], 'rb')); OUT = sys.argv[2]
bak, ad, bom, comp_tip = d['bak'], d['ad'], d['bom'], d['comp_tip']
def is_op(k): return comp_tip.get(k) == 'masraf' or k.count(':') == 1
recete = {k for k in bom if k in ad}
child = {p: {c: q for c, q in v.items() if not is_op(c)} for p, v in bom.items()}
c = get_connection(**DB_DEFAULTS); cur = c.cursor()
GIR = {1,4,5,8,15,16,20,22,26,29}; CIK = {2,3,6,7,17,18,19,21,24,28}

# Girdisi olan hat sayısı (Tipi=0 boş alt kayıtlar sayılmaz)
cur.execute("""SELECT ur.Kodu, COUNT(DISTINCT h.Id) FROM UretimRecete ur JOIN UretimReceteHatPlani h ON h.UretimReceteId=ur.Id
 JOIN UretimReceteHatPlaniGirdi g ON g.UretimReceteHatPlaniId=h.Id
 WHERE (ur.KullanimDisi IS NULL OR ur.KullanimDisi=0) GROUP BY ur.Kodu""")
hat_sayisi = dict(cur.fetchall())
# Reçetesi olmayan ama operasyon kartı (KOD:XX) olan parçalar → yalnız operasyonlu yarı mamul hattı
cur.execute("""SELECT LEFT(Kodu, CHARINDEX(':', Kodu)-1) FROM StokKarti WHERE Aktif=1 AND Kodu LIKE '%:%' AND Kodu NOT LIKE '%:%:%'
 UNION SELECT LEFT(Kodu, CHARINDEX(':', Kodu)-1) FROM StokMasrafKarti WHERE Kodu LIKE '%:%' AND Kodu NOT LIKE '%:%:%'""")
op_parca = {r[0] for r in cur.fetchall()}
# Karar bekleyen faturalar (yazılmaz)
# Kullanıcı kararları (2026-11-11): TUSAŞ → yeni emir yok, açık emir 1092026-3 düzeltilir; Caracal → yeni emir.
ENGEL = {'GEF2026000000032': 'TUSAŞ: yeni emir açılmaz — açık emir ŞİRKET.1092026-3 düzeltilir (230013 → 230027)'}

def hareketler(kod):
    cur.execute("""
    SELECT sh.IslemKodu, sh.BelgeTarihi, ISNULL(sh.BelgeSeriNo,'')+ISNULL(CAST(sh.BelgeSiraNo AS VARCHAR(20)),''),
           ISNULL(cmk.Unvani,''), shd.Miktar-ISNULL(shd_f.Miktar,0), sh.Id
    FROM StokHareketDetay shd JOIN StokHareket sh ON sh.Id=shd.HareketId
    LEFT JOIN StokHareketDetay shd_f ON shd_f.Id=shd.FaturaDetayId
    JOIN StokKarti sk ON sk.Id=shd.IslemKartId LEFT JOIN CariMusteriKarti cmk ON cmk.Id=sh.MusteriKartId
    WHERE sk.Kodu=? AND shd.Turu=1 AND shd.Aktif=1 AND sh.Aktif=1 AND sh.FaturaId IS NULL
      AND sh.IslemKodu NOT IN (9,10,11,12,13,14,25,27,23)
    ORDER BY sh.BelgeTarihi, CASE WHEN sh.IslemKodu IN (1,4,5,8,15,16,20,22,26,29) THEN 0 ELSE 1 END, sh.Id""", kod)
    return [dict(ik=r[0], t=r[1], belge=r[2], cari=r[3], m=float(r[4] or 0), hid=r[5]) for r in cur.fetchall()]

neg_mamul = sorted([k for k, v in bak.items() if v < -1e-9 and (k in recete or k.startswith('GMP-101'))])
satirlar = []
for k in neg_mamul:
    avail = 0.0; kuyruk = []
    for h in hareketler(k):
        if h['ik'] in GIR:
            q = h['m']
            while q > 1e-9 and kuyruk:
                take = min(q, kuyruk[0][1]); kuyruk[0][1] -= take; q -= take
                if kuyruk[0][1] <= 1e-9: kuyruk.pop(0)
            avail += q
        elif h['ik'] in CIK:
            use = min(avail, h['m']); avail -= use
            if h['m'] - use > 1e-9: kuyruk.append([h, h['m'] - use])
    for h, q in kuyruk:
        satirlar.append(dict(kod=k, h=h, eksik=q, fatura_miktar=h['m']))

emirler = defaultdict(list)
for s in satirlar: emirler[(s['h']['t'], s['h']['belge'], s['h']['cari'])].append(s)

stok = {k: max(0.0, v) for k, v in bak.items()}
def patlat(kod, q, ym, lvl=1):
    for cc, per in child.get(kod, {}).items():
        need = per * q; use = min(stok.get(cc, 0.0), need); stok[cc] = stok.get(cc, 0.0) - use
        rest = need - use
        if cc in recete and rest > 1e-9:
            ym[cc] = ym.get(cc, 0.0) + rest
            patlat(cc, rest, ym, lvl + 1)
        elif cc not in recete and cc in op_parca and rest > 1e-9:
            ym[cc] = ym.get(cc, 0.0) + rest          # operasyonlu iç imalat parçası

def emir_tarihi(t):
    e = t - timedelta(days=1)
    while e.weekday() >= 5: e -= timedelta(days=1)
    return e.replace(hour=9, minute=0, second=0, microsecond=0)

plan = []
for no, ((t, belge, cari), ss) in enumerate(sorted(emirler.items(), key=lambda kv: (kv[0][0], kv[0][1])), 1):
    ym = {}; uyari = []; bilgi = []
    ana = []; ertelenen = []
    if belge in ENGEL: uyari.append(ENGEL[belge])
    receteli_var = any(s['kod'] in recete for s in ss)
    for s in ss:
        k = s['kod']; q = s['fatura_miktar']
        if k not in recete and receteli_var:
            # Faturadaki reçetesiz ürün ertelenir; emir reçeteli ürünlerle açılır, bu ürün sonra aynı emre eklenir.
            ertelenen.append(dict(kod=k, miktar=q, eksik=round(s['eksik'], 4)))
            bilgi.append(f'{k}: reçete yok — ertelendi, sonra aynı emre ana hat olarak eklenecek'); continue
        ana.append(dict(kod=k, miktar=q, eksik=round(s['eksik'], 4)))
        if k not in recete: uyari.append(f'{k}: aktif reçete yok'); continue
        if hat_sayisi.get(k, 1) > 1: bilgi.append(f'{k}: çok hatlı reçete ({hat_sayisi[k]} hat) — girdiler tek hatta')
        patlat(k, q, ym)
    for y in ym:
        if y not in recete: bilgi.append(f'{y}: reçetesiz, operasyon kartlarıyla YM hattı')
        elif hat_sayisi.get(y, 1) > 1: bilgi.append(f'{y}: çok hatlı yarı mamul reçetesi')
    ad_ana = (ad.get(ana[0]['kod'] if ana else ss[0]['kod']) or '').strip()
    kisa = ' '.join(cari.split()[:3]).upper()
    plan.append(dict(plan_no=f'PLAN-{no:02d}', fatura=belge, fatura_tarihi=t.strftime('%Y-%m-%d'), cari=cari,
                     emir_tarihi=emir_tarihi(t).strftime('%Y-%m-%d %H:%M:%S'),
                     aciklama=f'{ad_ana} {kisa}'.upper()[:200],
                     surec_dipnot=f'Fatura: {belge} ({t.strftime("%d.%m.%Y")}) - {cari}',
                     ana=ana, ertelenen=ertelenen, yari_mamul=[dict(kod=k, miktar=round(v, 6)) for k, v in ym.items()], uyari=uyari, bilgi=bilgi))
json.dump(plan, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for p in plan:
    print(p['plan_no'], p['emir_tarihi'][:10], p['fatura'], p['cari'][:28], '|', ', '.join(f"{a['kod']}x{a['miktar']:g}" for a in p['ana']),
          '| YM:', ', '.join(f"{y['kod']}x{y['miktar']:g}" for y in p['yari_mamul']), '| ENGEL:' if p['uyari'] else '', '; '.join(p['uyari']))
    for b in p['bilgi']: print('      ·', b)
