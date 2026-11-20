"""Bir emrin kapanışa hazırlığı: kapanış sırası + verilen tarihte (vars. emir tarihi) hat hat depo yeterliliği + en erken uygun tarih. Salt okuma.
Kullanım: python emir_hazirlik.py "ŞİRKET.1092026-3" [GG.AA.YYYY]
- Sıra: başka bir hattın girdisi olan YM hattı önce (topolojik), sonra kalan YM'ler, en son ana hatlar.
- Depo bakiyesi CEO formülü + k23 (kaynaktan düş, hedefe ekle), girdinin kendi deposunda, kapanış tarihi itibarıyla.
- Daha eski tarihli diğer açık sene sonu emirlerinin tüketimi düşülür (ATP); bu emrin önceki hatlarının üretimi eklenir.
- En erken tarih: emir tarihinden bugüne kadar, ilgili kartların hareket tarihleri denenerek tüm hatların sorunsuz kapandığı ilk gün."""
import sys, io
from collections import defaultdict
from datetime import datetime, date
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection

GIRIS = (1, 4, 5, 8, 15, 16, 20, 22, 26, 29)
CIKIS = (2, 3, 6, 7, 17, 18, 19, 21, 24, 28)
HEDEF = sys.argv[1]
c = get_connection(**DB_DEFAULTS); cur = c.cursor()
cur.execute("SELECT Id, Adi FROM StokDepoKarti"); depo_ad = {r[0]: r[1].strip() for r in cur.fetchall()}
cur.execute("SELECT Id, UretimEmriTarihi FROM UretimEmri WHERE Kodu=?", HEDEF); eid, etarih = cur.fetchone()
TARIH = datetime.strptime(sys.argv[2], '%d.%m.%Y').date() if len(sys.argv) > 2 else etarih.date()

def hatlar_getir(emir_id):
    cur.execute("""SELECT h.Id, h.sira, h.HatTipi, hk.Id, hk.Kodu, LEFT(hk.Adi,32), h.TalepMiktari, ISNULL(h.StokDepoId,2),
        (SELECT COUNT(*) FROM UretimEmriHatPlaniStokHareketleri x WHERE x.UretimEmriHatPlaniId=h.Id)
      FROM UretimEmriHatPlani h JOIN StokKarti hk ON hk.Id=h.KartId WHERE h.UretimEmriId=? ORDER BY h.sira""", emir_id)
    out = []
    for hid, sira, tip, hkid, hkod, had, talep, hdepo, har in cur.fetchall():
        cur.execute("""SELECT sk.Id, sk.Kodu, LEFT(sk.Adi,38), g.TalepMiktar, ISNULL(g.StokDepoId,2) FROM UretimEmriHatPlaniGirdi g JOIN StokKarti sk ON sk.Id=g.KartId
          WHERE g.UretimEmriHatPlaniId=? AND g.Tipi<>2 AND (g.Yazilmasin IS NULL OR g.Yazilmasin=0)""", hid)
        out.append(dict(id=hid, sira=sira, tip=tip, kid=hkid, kod=hkod, ad=had, talep=float(talep or 0), depo=hdepo, kapali=har > 0,
                        girdi=[dict(kid=r[0], kod=r[1], ad=r[2], talep=float(r[3] or 0), depo=r[4]) for r in cur.fetchall()]))
    return out

H = hatlar_getir(eid)
# önceki açık emirler (ATP)
cur.execute("""SELECT Id, Kodu FROM UretimEmri WHERE DurumId=3 AND (SurecDipnot LIKE 'Fatura:%' OR Kodu='ŞİRKET.1092026-3') AND Id<>? AND UretimEmriTarihi<?""", eid, etarih)
onceki = [(k, hatlar_getir(i)) for i, k in cur.fetchall()]

kartlar = {g['kid'] for h in H for g in h['girdi']} | {h['kid'] for h in H}
hareket = defaultdict(list)
kl = list(kartlar)
for i in range(0, len(kl), 500):
    p = kl[i:i+500]
    cur.execute(f"""SELECT shd.IslemKartId, sh.IslemKodu, COALESCE(shd.DepoKartId, sh.DepoKartId), COALESCE(shd.KarsiDepoKartId, sh.KarsiDepoKartId), sh.BelgeTarihi,
         shd.Miktar - ISNULL(f.Miktar,0)
      FROM StokHareketDetay shd JOIN StokHareket sh ON sh.Id=shd.HareketId LEFT JOIN StokHareketDetay f ON f.Id=shd.FaturaDetayId
      WHERE shd.IslemKartId IN ({','.join('?'*len(p))}) AND shd.Turu=1 AND shd.Aktif=1 AND sh.Aktif=1 AND sh.FaturaId IS NULL
        AND sh.IslemKodu NOT IN (9,10,11,12,13,14,25,27)""", *p)
    for kid, ik, d, kd, t, m in cur.fetchall():
        m = float(m or 0); t = t.date()
        if ik == 23:
            hareket[(kid, d)].append((t, -m))
            if kd: hareket[(kid, kd)].append((t, m))
        elif ik in GIRIS: hareket[(kid, d)].append((t, m))
        elif ik in CIKIS: hareket[(kid, d)].append((t, -m))
bak = lambda k, d, t: sum(m for x, m in hareket.get((k, d), []) if x <= t)

# Kapanış sırası: açık hatlar; YM'nin ürünü başka açık hattın girdisiyse önce
acik = [h for h in H if not h['kapali']]
tuketen = defaultdict(set)
for h in acik:
    for g in h['girdi']: tuketen[g['kid']].add(h['id'])
sira = []; kalan = list(acik)
while kalan:
    hazir = [h for h in kalan if not any(x['kid'] in {g['kid'] for g in h['girdi']} for x in kalan if x is not h and x['tip'] == 2)]
    if not hazir: hazir = kalan[:1]
    hazir.sort(key=lambda h: (h['tip'] == 1, h['sira']))
    sira.append(hazir[0]); kalan.remove(hazir[0])

def simule(t, yaz=False):
    on = defaultdict(float)
    for _, hs in onceki:
        for h in hs:
            if h['kapali']: continue
            for g in h['girdi']: on[(g['kid'], g['depo'])] -= g['talep']
            on[(h['kid'], h['depo'])] += h['talep']
    sorun = 0
    for n, h in enumerate(sira, 1):
        eks = []
        for g in h['girdi']:
            b = bak(g['kid'], g['depo'], t) + on[(g['kid'], g['depo'])]
            if b - g['talep'] < -1e-6: eks.append((g, b))
        for g in h['girdi']: on[(g['kid'], g['depo'])] -= g['talep']
        on[(h['kid'], h['depo'])] += h['talep']
        sorun += len(eks)
        if yaz:
            print(f"{n:>2}. sıra {h['sira']:>2} {'ANA' if h['tip']==1 else 'YM '} {h['kod']:18s} {h['ad']:32s} ×{h['talep']:g}  "
                  + ('OK' if not eks else f'{len(eks)} EKSİK'))
            for g, b in eks:
                diger = {depo_ad.get(d, d): round(bak(g['kid'], d, t), 3) for (k, d) in hareket if k == g['kid'] and d != g['depo'] and bak(g['kid'], d, t) > 0}
                print(f"        - {g['kod']:20s} {g['ad']:38s} ihtiyaç {g['talep']:g}, {depo_ad.get(g['depo'])} bakiye {b:g}"
                      + (f' | diğer depolar: {diger}' if diger else ''))
    return sorun

print(f"{HEDEF} — emir tarihi {etarih:%d.%m.%Y}, kontrol tarihi {TARIH:%d.%m.%Y}")
kapalilar = [h for h in H if h['kapali']]
if kapalilar: print('zaten kapalı hatlar:', ', '.join(f"sıra {h['sira']} {h['kod']}" for h in kapalilar))
if onceki: print('ATP ile düşülen önceki açık emirler:', ', '.join(k for k, _ in onceki))
print()
s = simule(TARIH, yaz=True)
print(f'\n{TARIH:%d.%m.%Y} itibarıyla eksik girdi sayısı: {s}')
if s:
    adaylar = sorted({x for (k, d), hs in hareket.items() for x, _ in hs if etarih.date() <= x <= date.today()} | {date.today()})
    for t in adaylar:
        if simule(t) == 0: print(f'En erken sorunsuz kapanış tarihi: {t:%d.%m.%Y}'); break
    else: print('Bugün itibarıyla bile tüm hatlar kapanamıyor.')
