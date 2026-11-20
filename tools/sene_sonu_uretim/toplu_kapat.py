"""Sene sonu emirlerini kapanış tarihi sırasıyla toplu kapatır (hat_kapat.py ile aynı CEO kalıbı + depo bazlı FIFO).
Kullanım: python toplu_kapat.py [--commit] [--sadece ŞİRKET.x]
  --commit yoksa: TÜM plan tek transaction'da sırayla yazılır, sonunda ROLLBACK (deneme).
  --commit varsa: her emir kendi transaction'ında yazılır; sorun çıkan emir geri alınır ve iş DURUR.
Her emir için:
  1) Emir tarihi plandaki kapanış tarihinden farklıysa UretimEmriTarihi = kapanış tarihi 09:00 (+ tarihçe yok, CEO da yazmıyor).
  2) Açık hatlar sırayla (başka hattın girdisi olan YM önce, sonra YM, en son ana hat). Her stok girdisi için girdinin deposunda
     min(kapanış tarihindeki, bugünkü) depo bakiyesi yeterli değilse: yeterli başka depoya çevrilir; tek depo yetmiyorsa satır depolara
     bölünür (aynı kolonlarla yeni girdi satırı); toplam da yetmiyorsa emir DURDURULUR.
  3) 17 + 16 fişleri, bağlantılar, MaliyetlendirilenMiktar; tüm hatlar kapanınca DurumId=5 + tarihçe.
  4) Kontrol: dokunulan kartlarda kapanış tarihinde ve bugün YENİ eksi (şirket geneli) yoksa ve StokKumulatif tutarlıysa kabul.
Çıktı: toplu_kapat_<tarih>.json (emir bazında fişler, maliyetler, depo değişiklikleri)."""
import sys, io, json
from collections import defaultdict
from datetime import datetime, date
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import stok_guncel_bakiyeleri

PLAN = [('ŞİRKET.11112026-10', '07.04.2026'), ('ŞİRKET.11112026-3', '31.07.2026'), ('ŞİRKET.11112026-4', '30.09.2026'),
        ('ŞİRKET.11112026-16', '01.10.2026'), ('ŞİRKET.11112026-12', '06.10.2026'), ('ŞİRKET.11112026-5', '07.10.2026'),
        ('ŞİRKET.11112026-13', '15.10.2026'), ('ŞİRKET.11112026-2', '16.10.2026'), ('ŞİRKET.11112026-9', '21.10.2026'),
        ('ŞİRKET.11112026-11', '21.10.2026'), ('ŞİRKET.11112026-14', '30.10.2026'), ('ŞİRKET.11112026-6', '02.11.2026'),
        ('ŞİRKET.11112026-7', '02.11.2026'), ('ŞİRKET.11112026-8', '04.11.2026')]
USER = 'BDE76801-C1DD-499E-A51B-C23901B28197'
GIR = (1, 4, 5, 8, 15, 16, 20, 22, 26, 29); CIK = (2, 3, 6, 7, 17, 18, 19, 21, 24, 28)
COMMIT = '--commit' in sys.argv
if '--sadece' in sys.argv: s_ = sys.argv[sys.argv.index('--sadece') + 1]; PLAN = [p for p in PLAN if p[0] == s_]
c = get_connection(**DB_DEFAULTS); c.autocommit = False; cur = c.cursor()
cur.execute("SELECT Id, Adi FROM StokDepoKarti"); DEPO = {r[0]: r[1].strip() for r in cur.fetchall()}
BUGUN = datetime.combine(date.today(), datetime.min.time())

def depo_hareket(kid, t):
    t = t.replace(hour=23, minute=59, second=59)
    cur.execute(f"""SELECT sh.Id, sh.BelgeTarihi, sh.IslemKodu, d.Miktar, d.BirimFiyat, COALESCE(d.DepoKartId, sh.DepoKartId), COALESCE(d.KarsiDepoKartId, sh.KarsiDepoKartId)
      FROM StokHareketDetay d JOIN StokHareket sh ON sh.Id=d.HareketId
      WHERE d.IslemKartId=? AND d.Turu=1 AND d.Aktif=1 AND sh.Aktif=1 AND sh.FaturaId IS NULL AND sh.BelgeTarihi<=? AND sh.IslemKodu IN {GIR + CIK + (23,)}""", kid, t)
    return cur.fetchall()
def depo_bakiye(kid, t):
    b = defaultdict(float)
    for i, bt, ik, m, f, d, kd in depo_hareket(kid, t):
        m = float(m)
        if ik == 23: b[d] -= m; b[kd] += m if kd else 0
        elif ik in GIR: b[d] += m
        elif ik in CIK: b[d] -= m
    return b
def fifo(kid, miktar, depo, t):
    gir, cik = [], 0.0
    for i, bt, ik, m, f, d, kd in depo_hareket(kid, t):
        m = float(m); f = float(f or 0)
        if ik == 23:
            if kd == depo: gir.append((bt, i, m, f))
            if d == depo: cik += m
        elif ik in GIR and d == depo: gir.append((bt, i, m, f))
        elif ik in CIK and d == depo: cik += m
    gir.sort(); kal, top, al = cik, 0.0, 0.0
    for bt, i, m, f in gir:
        if kal >= m - 1e-9: kal -= m; continue
        u = min(m - kal, miktar - al); top += u * f; al += u; kal = 0
        if al >= miktar - 1e-9: break
    if al < miktar - 1e-9: top += (miktar - al) * (gir[-1][3] if gir else 0.0)
    return round(top / miktar, 6) if miktar else 0.0
def baslik(islem, sira, toplam, t, notlar):
    now = datetime.now()
    cur.execute("""SET NOCOUNT ON; INSERT INTO StokHareket (Aktif, IhracKayitliMi, IslemKodu, BelgeTarihi, BelgeSiraNo, DepoKartId, ToplamTutar, SatirlarinIskontoToplamTutari,
        KdvMatrahiToplamTutari, KdvToplamTutari, KdvTevfikatTutari, OtvTutari, OzelIletisimVerigisiToplamTutari, NetTutar, IrsaliyedenMi, KonsinyedenMi, Acik,
        CreatedBy, CreationTime, ModifiedBy, ModificationTime, Notlar, EntegreDurumu, MusteriBolgeId, HareketBolgeId, ITS, PTS, EPDKdanmi,
        HatirlatmayaGelmesin, OdemePlaniIslendi, Odendi, InternetSatisi, KdvDahil)
      VALUES (1,0,?,?,?,2,?,0,0,0,0,0,0,?,0,0,0,?,?,?,?,?,0,2,2,0,0,0,0,0,0,0,0); SELECT CAST(SCOPE_IDENTITY() AS bigint)""",
        islem, t, sira, toplam, toplam, USER, now, USER, now, notlar)
    while cur.description is None:
        if not cur.nextset(): raise RuntimeError('Id okunamadı')
    return int(cur.fetchone()[0])
def detay(hid, turu, kid, birim, mik, bf, depo, islem, t):
    now = datetime.now(); tutar = round(bf * mik, 6)
    cur.execute("""INSERT INTO StokHareketDetay (Aktif, Yazdirma, Turu, HareketId, IslemKartId, KdvOrani, StokBirimId, Miktar, BirimFiyat, Tutar,
        OzelIslemVergisiOrani, DepoKartId, BirimKatsayisi, MaliyetTarihi, MaliyetTutari, IslemKodu, IrsaliyedenMi, KalanMiktar, KonsinyedenMi,
        CreatedBy, CreationTime, ModifiedBy, ModificationTime) VALUES (1,0,?,?,?,0,?,?,?,?,0,?,?,?,?,?,0,?,0,?,?,?,?)""",
        turu, hid, kid, birim, mik, bf, tutar, depo, mik, t, tutar, islem, mik, USER, now, USER, now)

cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='UretimEmriHatPlaniGirdi' AND COLUMN_NAME<>'Id' ORDER BY ORDINAL_POSITION")
GCOL = [r[0] for r in cur.fetchall()]

def emir_kapat(ek, tstr):
    T = datetime.strptime(tstr, '%d.%m.%Y'); rap = {'emir': ek, 'kapanis': tstr, 'depo': [], 'hatlar': []}
    cur.execute("SELECT Id, Aciklama, DurumId, UretimEmriTarihi FROM UretimEmri WHERE Kodu=?", ek); eid, acik, durum, et = cur.fetchone()
    if durum != 3: raise RuntimeError(f'{ek} durumu {durum}')
    if et.date() != T.date():
        cur.execute("UPDATE UretimEmri SET UretimEmriTarihi=?, ModifiedBy=?, ModificationTime=GETDATE() WHERE Id=?", T.replace(hour=9), USER, eid)
        rap['emir_tarihi'] = f'{et:%d.%m.%Y} → {tstr}'
    notlar = f'{ek} / {(acik or "").strip()}'[:250]
    cur.execute("""SELECT h.Id, h.HatTipi, h.sira, h.KartId, hk.Kodu, h.TalepMiktari, h.Birim, ISNULL(h.StokDepoId,2) FROM UretimEmriHatPlani h JOIN StokKarti hk ON hk.Id=h.KartId
      WHERE h.UretimEmriId=? AND NOT EXISTS (SELECT 1 FROM UretimEmriHatPlaniStokHareketleri x WHERE x.UretimEmriHatPlaniId=h.Id)""", eid)
    acik_h = cur.fetchall()
    girdi_kart = {}
    for h in acik_h:
        cur.execute("SELECT KartId FROM UretimEmriHatPlaniGirdi WHERE UretimEmriHatPlaniId=? AND Tipi<>2", h[0]); girdi_kart[h[0]] = {r[0] for r in cur.fetchall()}
    sira, kalan = [], list(acik_h)
    while kalan:
        hazir = [h for h in kalan if not any(x[3] in girdi_kart[h[0]] for x in kalan if x is not h and x[1] == 2)] or kalan[:1]
        hazir.sort(key=lambda h: (h[1] == 1, h[2])); sira.append(hazir[0]); kalan.remove(hazir[0])
    dokunulan = set()
    tum = {h[3] for h in acik_h} | {k for v in girdi_kart.values() for k in v}
    cur.execute(f"SELECT Id, Kodu FROM StokKarti WHERE Id IN ({','.join(map(str, tum))})"); kod_once = dict(cur.fetchall()); kl0 = sorted(kod_once.values())
    once_b = {t: stok_guncel_bakiyeleri(c, kl0, t.strftime('%Y-%m-%d')) for t in (T, BUGUN)}
    b0 = stok_guncel_bakiyeleri(c, kl0, '2099-12-31')
    cur.execute(f"SELECT sk.Kodu, k.GirenMiktar-k.CikanMiktar FROM StokKumulatif k JOIN StokKarti sk ON sk.Id=k.StokKartId WHERE sk.Kodu IN ({','.join('?'*len(kl0))})", *kl0)
    once_kf = {k: round(b0[k] - float(v or 0), 4) for k, v in cur.fetchall()}
    for h in sira:
        hid, htip, hs, hkid, hkod, talep, hbirim, hdepo = h; talep = float(talep)
        # depo yeterliliği
        cur.execute("SELECT Id, KartId, TalepMiktar, ISNULL(StokDepoId,2) FROM UretimEmriHatPlaniGirdi WHERE UretimEmriHatPlaniId=? AND Tipi<>2 AND (Yazilmasin IS NULL OR Yazilmasin=0)", hid)
        for gid, kid, mik, gd in cur.fetchall():
            mik = float(mik); dokunulan.add(kid)
            bT, bB = depo_bakiye(kid, T), depo_bakiye(kid, BUGUN)
            uygun = {d: min(bT[d], bB[d]) for d in set(bT) | set(bB)}
            if uygun.get(gd, 0) >= mik - 1e-6: continue
            tek = [d for d, v in sorted(uygun.items(), key=lambda x: -x[1]) if v >= mik - 1e-6]
            if tek:
                cur.execute("UPDATE UretimEmriHatPlaniGirdi SET StokDepoId=? WHERE Id=?", tek[0], gid)
                rap['depo'].append(f'{hkod}: kart {kid} {mik:g} {DEPO.get(gd)} → {DEPO.get(tek[0])}'); continue
            parcalar, ihtiyac = [], mik
            for d, v in sorted(uygun.items(), key=lambda x: (x[0] != gd, -x[1])):
                if v <= 1e-6: continue
                al = min(v, ihtiyac); parcalar.append((d, round(al, 6))); ihtiyac -= al
                if ihtiyac <= 1e-6: break
            if ihtiyac > 1e-6:
                cur.execute("SELECT Kodu FROM StokKarti WHERE Id=?", kid)
                raise RuntimeError(f'{ek} {hkod}: {cur.fetchone()[0]} ihtiyaç {mik:g}, depolarda toplam {mik - ihtiyac:g} ({ {DEPO.get(d): round(v, 2) for d, v in uygun.items() if v} })')
            ilk_d, ilk_m = parcalar[0]
            cur.execute("UPDATE UretimEmriHatPlaniGirdi SET StokDepoId=?, TalepMiktar=? WHERE Id=?", ilk_d, ilk_m, gid)
            for d, m in parcalar[1:]:
                cols = ','.join(GCOL); sel = ','.join('?' if k in ('StokDepoId', 'TalepMiktar') else k for k in GCOL)
                cur.execute(f"INSERT INTO UretimEmriHatPlaniGirdi ({cols}) SELECT {sel} FROM UretimEmriHatPlaniGirdi WHERE Id=?",
                            *[d if k == 'StokDepoId' else m for k in GCOL if k in ('StokDepoId', 'TalepMiktar')], gid)
            rap['depo'].append(f'{hkod}: kart {kid} {mik:g} bölündü {[(DEPO.get(d), m) for d, m in parcalar]}')
        # fişler
        cur.execute("""SELECT g.Tipi, g.KartId, g.StokBirim, g.TalepMiktar, ISNULL(g.StokDepoId,2), ISNULL(g.Tutar,0) FROM UretimEmriHatPlaniGirdi g
          WHERE g.UretimEmriHatPlaniId=? AND (g.Yazilmasin IS NULL OR g.Yazilmasin=0) ORDER BY g.Id""", hid)
        st = []
        for tip, kid, birim, mik, depo, tut in cur.fetchall():
            mik = float(mik)
            if tip == 2: st.append((3, kid, birim, mik, round(float(tut) / mik, 6) if mik else 0.0, depo))
            else: st.append((1, kid, birim, mik, fifo(kid, mik, depo, T), depo))
        toplam = round(sum(s[3] * s[4] for s in st), 2)
        bsn = int(f'{T.year}{T.month}{T.day}{datetime.now():%H%M%S}')
        f17 = baslik(17, bsn, toplam, T, notlar)
        for s in st: detay(f17, s[0], s[1], s[2], s[3], s[4], s[5], 17, T)
        f16 = baslik(16, bsn, toplam, T, notlar)
        detay(f16, 1, hkid, hbirim, talep, round(toplam / talep, 6), hdepo, 16, T); dokunulan.add(hkid)
        cur.execute("INSERT INTO UretimEmriHatPlaniStokHareketleri (UretimEmriHatPlaniId, StokHareketId, UretimHatPlaniTuru) VALUES (?,?,0)", hid, f16)
        cur.execute("INSERT INTO UretimEmriHatPlaniStokHareketleri (UretimEmriHatPlaniId, StokHareketId, UretimHatPlaniTuru) VALUES (?,?,1)", hid, f17)
        cur.execute("UPDATE UretimEmriHatPlani SET MaliyetlendirilenMiktar=TalepMiktari WHERE Id=?", hid)
        rap['hatlar'].append({'hat': hkod, 'adet': talep, 'satir': len(st), 'maliyet': toplam, 'birim': round(toplam / talep, 2), 'f17': f17, 'f16': f16})
    cur.execute("UPDATE UretimEmri SET DurumId=5, ModifiedBy=?, ModificationTime=GETDATE() WHERE Id=?", USER, eid)
    cur.execute("""INSERT INTO UretimEmriTarihce (UretimEmriId, KullaniciId, Tarih, Aciklama, IsOnay, EskiUretimDurumId, YeniUretimDurumId)
      VALUES (?, ?, GETDATE(), 'Üretim emri hareketi durumu değişti.Eski durum : Devam Ediyor Yeni durum : Tamamlandı', 0, 3, 5)""", eid, USER)
    # kontroller
    cur.execute(f"SELECT Id, Kodu FROM StokKarti WHERE Id IN ({','.join(map(str, dokunulan))})"); kod = dict(cur.fetchall())
    kl = sorted(kod.values())
    sorun = []
    for t in (T, BUGUN):
        for k, v in stok_guncel_bakiyeleri(c, kl, t.strftime('%Y-%m-%d')).items():
            o = once_b[t].get(k, 0.0)
            if v < -1e-6 and v < o - 1e-6: sorun.append(f'{t:%d.%m.%Y} {k} {o:g} → {v:g}')
    rap['eksi'] = sorun
    bak = stok_guncel_bakiyeleri(c, kl, '2099-12-31')
    cur.execute(f"SELECT sk.Kodu, k.GirenMiktar-k.CikanMiktar FROM StokKumulatif k JOIN StokKarti sk ON sk.Id=k.StokKartId WHERE sk.Kodu IN ({','.join('?'*len(kl))})", *kl)
    rap['kumulatif_fark'] = [(k, once_kf.get(k), round(bak[k] - float(v or 0), 4)) for k, v in cur.fetchall() if abs((bak[k] - float(v or 0)) - once_kf.get(k, 0)) > 0.011]
    return rap

# eksi kontrolü için: emirden ÖNCE zaten eksi olan kartlar yeni sorun sayılmaz
sonuclar = []
for ek, t in PLAN:
    try:
        cur.execute("SELECT DurumId FROM UretimEmri WHERE Kodu=?", ek)
        if cur.fetchone()[0] == 5: print(f'{ek}: zaten Tamamlandı, atlandı'); continue
        r = emir_kapat(ek, t)
        once = set()
        if r['eksi']:   # aynı kartlar emirden önce de eksi miydi?
            pass
        sonuclar.append(r)
        top = sum(h['maliyet'] for h in r['hatlar'])
        print(f"\n{ek} kapanış {t}{' (emir tarihi ' + r['emir_tarihi'] + ')' if r.get('emir_tarihi') else ''}: {len(r['hatlar'])} hat, toplam {top:,.2f}")
        for h in r['hatlar']: print(f"   {h['hat']:18s} ×{h['adet']:g} birim {h['birim']:>12,.2f}  ({h['satir']} satır)")
        for d in r['depo']: print('   depo:', d)
        if r['eksi']: print('   ⚠ EKSİ:', r['eksi'])
        if r['kumulatif_fark']: print('   ⚠ StokKumulatif farkı:', r['kumulatif_fark'])
        if COMMIT:
            if r['eksi'] or r['kumulatif_fark']: c.rollback(); print('   → GERİ ALINDI, durduruluyor'); break
            c.commit(); print('   → COMMIT')
    except Exception as e:
        print(f'\n{ek}: HATA {e}'); c.rollback(); print('   → GERİ ALINDI, durduruluyor'); break
if not COMMIT: c.rollback(); print('\nROLLBACK (deneme) — hiçbir şey yazılmadı')
fn = rf'C:\yeni-erp\toplu_kapat_{"commit" if COMMIT else "deneme"}_{datetime.now():%Y%m%d_%H%M%S}.json'
json.dump(sonuclar, open(fn, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str); print('rapor:', fn)
