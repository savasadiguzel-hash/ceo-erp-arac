import sys, json, pickle
sys.path.insert(0, r'C:\yeni-erp')
from collections import defaultdict
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import mamul_agaci_listesi, birimleri_getir
c = get_connection(**DB_DEFAULTS); cur = c.cursor()
OUT = sys.argv[1]

# 1) Reçete ham verisi (aktif reçeteler)
cur.execute("""
SELECT ur.Id, ur.Kodu, ur.Tanim, urhp.Id, urhp.Tipi, urhp.KartId, urhp.Miktar,
       urhpg.Tipi, urhpg.KartId, urhpg.Miktar,
       CASE WHEN urhpg.Tipi=2 THEN smk.Kodu ELSE sk.Kodu END,
       CASE WHEN urhpg.Tipi=2 THEN smk.Adi ELSE sk.Adi END,
       hk.Kodu
FROM UretimRecete ur
JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId=ur.Id
LEFT JOIN StokKarti hk ON hk.Id=urhp.KartId
JOIN UretimReceteHatPlaniGirdi urhpg ON urhpg.UretimReceteHatPlaniId=urhp.Id
LEFT JOIN StokKarti sk ON sk.Id=urhpg.KartId AND urhpg.Tipi<>2
LEFT JOIN StokMasrafKarti smk ON smk.Id=urhpg.KartId AND urhpg.Tipi=2
WHERE (ur.KullanimDisi IS NULL OR ur.KullanimDisi=0)
""")
rows = cur.fetchall()
mamul = dict(mamul_agaci_listesi(c))
# recete sayısı / kod başına birden fazla aktif reçete?
cur.execute("""SELECT Kodu, COUNT(*) FROM UretimRecete WHERE (KullanimDisi IS NULL OR KullanimDisi=0)
GROUP BY Kodu HAVING COUNT(*)>1""")
coklu = cur.fetchall()
hatmiktar = defaultdict(set)
bom = defaultdict(lambda: defaultdict(float))  # parent -> comp -> qty (summed across hats)
comp_ad = {}; comp_tip = {}
hat_kartlari = defaultdict(set)
for (rid, rk, rt, hid, htip, hkart, hmik, gtip, gkart, gmik, ckod, cad, hkod) in rows:
    if ckod is None: continue
    hatmiktar[rk].add(float(hmik or 1))
    if hkod: hat_kartlari[rk].add(hkod)
    bom[rk][ckod] += float(gmik or 0)
    comp_ad[ckod] = cad
    comp_tip[ckod] = 'masraf' if (gtip == 2 or ckod.count(':') == 1) else 'stok'

# 2) Tüm stok kartlarının bakiyesi (bugün) — tek sorgu, aynı formül
cur.execute("""
SELECT sk.Kodu, sk.Adi, sk.StokBirim,
  SUM(CASE WHEN sh.IslemKodu IN (1,4,5,8,15,16,20,22,26,29) THEN (shd.Miktar-ISNULL(shd_f.Miktar,0))
           WHEN sh.IslemKodu IN (2,3,6,7,17,18,19,21,24,28) THEN -(shd.Miktar-ISNULL(shd_f.Miktar,0))
           ELSE 0 END)
FROM StokHareketDetay shd
JOIN StokHareket sh ON sh.Id=shd.HareketId
LEFT JOIN StokHareketDetay shd_f ON shd_f.Id=shd.FaturaDetayId
JOIN StokKarti sk ON sk.Id=shd.IslemKartId
WHERE shd.Turu=1 AND shd.Aktif=1 AND sh.Aktif=1 AND sh.FaturaId IS NULL
  AND sh.IslemKodu NOT IN (9,10,11,12,13,14,25,27,23)
  AND CAST(sh.BelgeTarihi AS DATE) <= CAST(GETDATE() AS DATE)
GROUP BY sk.Kodu, sk.Adi, sk.StokBirim
""")
bak = {}; ad = {}; birimg = {}
for k, a, b, v in cur.fetchall():
    bak[k] = float(v or 0); ad[k] = a; birimg[k] = b
cur.execute("SELECT Kodu, Adi, StokBirim FROM StokKarti WHERE Aktif=1")
for k, a, b in cur.fetchall():
    ad.setdefault(k, a); birimg.setdefault(k, b); bak.setdefault(k, 0.0)
bir = {str(g).casefold().strip('{}'): n for n, g in birimleri_getir(c).items()}
birim = {k: bir.get(str(g or '').casefold().strip('{}'), '?') for k, g in birimg.items()}

# 3) Son hareket tarihleri + negatife sebep olan hareket türleri (negatifler için)
neg = [k for k, v in bak.items() if v < -1e-9]
son_hareket = {}; islem_ozet = defaultdict(dict)
for i in range(0, len(neg), 500):
    p = neg[i:i+500]; yer = ','.join('?'*len(p))
    cur.execute(f"""
    SELECT sk.Kodu, sh.IslemKodu, SUM(shd.Miktar-ISNULL(shd_f.Miktar,0)), MAX(sh.BelgeTarihi)
    FROM StokHareketDetay shd JOIN StokHareket sh ON sh.Id=shd.HareketId
    LEFT JOIN StokHareketDetay shd_f ON shd_f.Id=shd.FaturaDetayId
    JOIN StokKarti sk ON sk.Id=shd.IslemKartId
    WHERE sk.Kodu IN ({yer}) AND shd.Turu=1 AND shd.Aktif=1 AND sh.Aktif=1 AND sh.FaturaId IS NULL
      AND sh.IslemKodu NOT IN (9,10,11,12,13,14,25,27,23)
    GROUP BY sk.Kodu, sh.IslemKodu""", *p)
    for k, ik, m, t in cur.fetchall():
        islem_ozet[k][ik] = float(m or 0)
        if t and (k not in son_hareket or t > son_hareket[k]): son_hareket[k] = t

# 4) Açık üretim emirleri (DurumId=3) — üretilen kart (HatTipi=1)
cur.execute("""
SELECT ue.Kodu, ue.Aciklama, ue.UretimEmriTarihi, uehp.HatTipi, sk.Kodu, uehp.Miktar
FROM UretimEmri ue JOIN UretimEmriHatPlani uehp ON uehp.UretimEmriId=ue.Id
LEFT JOIN StokKarti sk ON sk.Id=uehp.KartId
WHERE ue.DurumId=3 ORDER BY ue.UretimEmriTarihi""")
acik = [tuple(str(x) if x is not None else None for x in r) for r in cur.fetchall()]

# son üretim tarihi (IslemKodu 16) reçeteli kalemler için
cur.execute("""SELECT sk.Kodu, MAX(sh.BelgeTarihi), COUNT(DISTINCT sh.Id) FROM StokHareketDetay shd
JOIN StokHareket sh ON sh.Id=shd.HareketId JOIN StokKarti sk ON sk.Id=shd.IslemKartId
WHERE sh.IslemKodu=16 AND sh.Aktif=1 AND shd.Aktif=1 GROUP BY sk.Kodu""")
son_uretim = {k: (str(t)[:10], n) for k, t, n in cur.fetchall()}

data = dict(mamul=mamul, bom={k: dict(v) for k, v in bom.items()}, comp_ad=comp_ad, comp_tip=comp_tip,
            hatmiktar={k: sorted(v) for k, v in hatmiktar.items()}, hat_kartlari={k: sorted(v) for k, v in hat_kartlari.items()},
            coklu=[tuple(x) for x in coklu], bak=bak, ad=ad, birim=birim,
            son_hareket={k: str(v)[:10] for k, v in son_hareket.items()}, islem_ozet=dict(islem_ozet),
            acik=acik, son_uretim=son_uretim)
pickle.dump(data, open(OUT, 'wb'))
print('recete', len(mamul), 'bom', len(bom), 'kart', len(bak), 'negatif', len(neg), 'acik satir', len(acik), 'coklu', coklu[:5])
