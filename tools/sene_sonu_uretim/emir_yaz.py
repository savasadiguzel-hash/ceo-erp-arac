"""plan.json'dan TEK bir iş emrini CEO ERP'ye yazar (Devam Ediyor).
Kullanım: python emir_yaz.py plan.json PLAN-15            -> deneme (ROLLBACK)
          python emir_yaz.py plan.json PLAN-15 --commit   -> kalıcı yaz
Yazılanlar: UretimEmri + UretimEmriHatPlani (HatTipi 1 ana, 2 yarı mamul) + UretimEmriHatPlaniGirdi + UretimEmriTarihce.
Stok hareketi (16/17) YAZILMAZ — CEO'da hat tamamlanınca oluşur."""
import sys, io, json
from datetime import datetime
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection
plan = {p['plan_no']: p for p in json.load(open(sys.argv[1], encoding='utf-8'))}
p = plan[sys.argv[2]]; COMMIT = '--commit' in sys.argv
USER = 'BDE76801-C1DD-499E-A51B-C23901B28197'   # Savaş Adıgüzel (CEO kullanıcısı)
DEPO = 2

if p['uyari']:
    sys.exit(f"Uyarılı plan yazılmaz: {p['uyari']}")
c = get_connection(**DB_DEFAULTS); c.autocommit = False; cur = c.cursor()

def kart(kod):
    cur.execute("SELECT Id, StokBirim, SeriNoTakibi FROM StokKarti WHERE Kodu=? AND Aktif=1", kod)
    r = cur.fetchone()
    if not r: raise ValueError(f'Stok kartı yok: {kod}')
    return r

def recete_girdileri(kod):
    """Aktif reçetenin tüm hatlarındaki girdiler tek listede (çok hatlı reçete düzleştirilir).
    Kartı aynı reçetenin başka bir hattında GİRDİ olarak tüketilen hat (ör. 230027'de 240502 gövde)
    alt üretimdir: girdileri buraya alınmaz, gerekirse ayrı HatTipi=2 satırı olur."""
    cur.execute("""SELECT h.Id, h.KartId, g.Tipi, g.KartId, g.Miktar, g.BirimId, g.DepoId, g.SabitMiktar, g.FireOrani, g.GarantiKapsaminda, g.Aciklama
      FROM UretimRecete ur JOIN UretimReceteHatPlani h ON h.UretimReceteId=ur.Id
      JOIN UretimReceteHatPlaniGirdi g ON g.UretimReceteHatPlaniId=h.Id
      WHERE ur.Kodu=? AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi=0) ORDER BY h.Id, g.Id""", kod)
    rs = cur.fetchall()
    if not rs: raise ValueError(f'Reçete girdisi yok: {kod}')
    tuketilen = {r[3] for r in rs if r[2] != 2}
    alt_hatlar = {r[0] for r in rs if r[1] in tuketilen and len({x[0] for x in rs}) > 1}
    out = [r[2:] for r in rs if r[0] not in alt_hatlar]
    for r in out:
        if r[3] is None: raise ValueError(f'{kod}: reçete girdisinde BirimId NULL (KartId {r[1]})')
    return out

def operasyon_girdileri(kod):
    """Reçetesi olmayan iç imalat parçası: KOD:XX operasyon kartları (önce StokKarti Tipi=1, yoksa StokMasrafKarti Tipi=2),
    birim başı 1 — yerel Lüp emri ŞİRKET.2442025-14 ile aynı düzen."""
    cur.execute("SELECT 1, Id, 1.0, StokBirim, ?, 0, NULL, 0, NULL FROM StokKarti WHERE Aktif=1 AND Kodu LIKE ? AND Kodu NOT LIKE ? ORDER BY Kodu",
                DEPO, kod + ':%', kod + ':%:%')
    rs = cur.fetchall()
    if not rs:
        cur.execute("SELECT 2, Id, 1.0, StokBirimId, ?, 0, NULL, 0, NULL FROM StokMasrafKarti WHERE Kodu LIKE ? AND Kodu NOT LIKE ? ORDER BY Kodu",
                    DEPO, kod + ':%', kod + ':%:%')
        rs = cur.fetchall()
    if not rs: raise ValueError(f'{kod}: reçete de operasyon kartı da yok')
    return [tuple(r[:3]) + ((r[3] or '4ACC21E3-3140-4863-922D-A0B3D35DE8C1'),) + tuple(r[4:]) for r in rs]

def girdiler(kod):
    cur.execute("SELECT COUNT(*) FROM UretimRecete WHERE Kodu=? AND (KullanimDisi IS NULL OR KullanimDisi=0)", kod)
    return recete_girdileri(kod) if cur.fetchone()[0] else operasyon_girdileri(kod)

now = datetime.now().replace(microsecond=0)
gun = datetime.strptime(p['emir_tarihi'], '%Y-%m-%d %H:%M:%S')
kodu = f"ŞİRKET.{now.day}{now.month}{now.year}-"
cur.execute("SELECT Kodu FROM UretimEmri WHERE Kodu LIKE ?", kodu + '%')
mevcut = [int(r[0].rsplit('-', 1)[1]) for r in cur.fetchall() if r[0].rsplit('-', 1)[1].isdigit()]
kodu += str(max(mevcut, default=0) + 1)

# Aynı fatura için daha önce yazılmış emir var mı? (SurecDipnot'ta fatura no)
cur.execute("SELECT Kodu FROM UretimEmri WHERE SurecDipnot LIKE ?", f"%{p['fatura']}%")
onceki = cur.fetchall()
if onceki: sys.exit(f"Bu fatura için zaten emir var: {onceki}")

try:
    cur.execute("""INSERT INTO UretimEmri (Kodu, Aciklama, UretimYontemi, UretimTeknigi, UretimEmriTarihi, PlanlananBasTarih, PlanlananBitisTarih,
        DurumId, SurecDipnot, Acik, CreatedBy, CreationTime, ModifiedBy, ModificationTime)
        OUTPUT INSERTED.Id
        VALUES (?, ?, 1, 1, ?, ?, ?, 3, ?, 0, ?, ?, ?, ?)""",
        kodu, p['aciklama'], gun, gun.replace(hour=0, minute=1), gun.replace(hour=23, minute=59),
        p['surec_dipnot'], USER, now, USER, now)
    eid = int(cur.fetchone()[0])
    satirlar = [(1, a['kod'], a['miktar']) for a in p['ana']] + [(2, y['kod'], y['miktar']) for y in p['yari_mamul']]
    ozet = []
    for sira, (hat_tipi, kod, miktar) in enumerate(satirlar, 1):
        kid, birim, seri = kart(kod)
        if seri: raise ValueError(f'{kod}: SeriNoTakibi açık — Seri alanı gerekir, yazılmadı')
        birim = birim or '4ACC21E3-3140-4863-922D-A0B3D35DE8C1'
        cur.execute("""INSERT INTO UretimEmriHatPlani (UretimEmriId, HatTipi, KartId, Miktar, Birim, TalepMiktari, StokDepoId, sira, TalepBirim)
            OUTPUT INSERTED.Id VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)""", eid, hat_tipi, kid, birim, miktar, DEPO, sira, birim)
        hid = int(cur.fetchone()[0])
        n = 0
        for (tipi, gkart, gmik, gbirim, gdepo, sabit, fire, garanti, gacik) in girdiler(kod):
            talep = float(gmik) if sabit else float(gmik) * miktar
            cur.execute("""INSERT INTO UretimEmriHatPlaniGirdi (UretimEmriHatPlaniId, Tipi, KartId, Miktar, TalepMiktar, StokBirim, StokDepoId,
                FireOrani, SabitMiktar, Aciklama, GarantiKapsami, Yazilmasin) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                hid, tipi, gkart, gmik, talep, gbirim, gdepo if gdepo is not None else DEPO, fire, bool(sabit), gacik, bool(garanti))
            n += 1
        ozet.append((sira, hat_tipi, kod, miktar, hid, n))
    cur.execute("""INSERT INTO UretimEmriTarihce (UretimEmriId, KullaniciId, Tarih, Aciklama, IsOnay, YeniUretimDurumId)
        VALUES (?, ?, ?, ?, 0, 3)""", eid, USER, now, 'Üretim emri hareketi durumu değişti.Eski durum : BOŞ Yeni durum : Devam Ediyor')
    # doğrulama
    cur.execute("""SELECT COUNT(*) FROM UretimEmriHatPlaniGirdi g JOIN UretimEmriHatPlani h ON h.Id=g.UretimEmriHatPlaniId WHERE h.UretimEmriId=?""", eid)
    toplam_girdi = cur.fetchone()[0]
    print(f"{'COMMIT' if COMMIT else 'DENEME (rollback)'} | Emir Id {eid} | {kodu} | tarih {gun:%d.%m.%Y} | {p['aciklama']}")
    print('  SurecDipnot:', p['surec_dipnot'])
    for s in ozet: print(f'  sira {s[0]} HatTipi {s[1]} {s[2]} x{s[3]:g}  (HatPlani Id {s[4]}, {s[5]} girdi)')
    print('  toplam girdi:', toplam_girdi)
    if COMMIT: c.commit(); print('KAYDEDİLDİ')
    else: c.rollback(); print('Geri alındı (deneme).')
except Exception as e:
    c.rollback(); print('HATA, geri alındı:', e); raise
