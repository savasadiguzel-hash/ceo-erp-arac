"""Reçetesi olmayan mamul için, EN SON üretim emrinin ana hat girdilerinden aktif reçete yazar.
Kullanım: python recete_yaz.py KOD [KOD ...]            -> deneme (ROLLBACK)
          python recete_yaz.py KOD [KOD ...] --commit   -> kalıcı
Yapı yerel tek hatlı mamul reçetesiyle aynı (ör. GMP-101-230063, UretimRecete Id 1):
  UretimRecete(UretimYontemi=1, KullanimDisi=0, Acik=0) → UretimReceteHatPlani(Tipi=1, KartId=ürünün kendisi, Miktar=1, BirimId=ürün birimi, DepoId=2)
  → UretimReceteHatPlaniGirdi(Tipi, KartId, Miktar=birim başı, BirimId, DepoId=2, SabitMiktar=0, GarantiKapsaminda=0, Yazdirma=0)
Pasif kartlar kullanıcı kararıyla (2026-11-11) güncel karşılıklarıyla değiştirilir (DEGISIM)."""
import sys, io
from datetime import datetime
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection
USER = 'BDE76801-C1DD-499E-A51B-C23901B28197'; ADET = '4ACC21E3-3140-4863-922D-A0B3D35DE8C1'; DEPO = 2
DEGISIM = {'HMGMDDAL009': ['YMGMÇBK0001'], 'HMGMDDAL086': ['YMGMDPK0001'], 'HMGMDDAL002': ['YMGMÇBK0001', 'YMGMDPK0001']}
COMMIT = '--commit' in sys.argv
kodlar = [a for a in sys.argv[1:] if not a.startswith('--')]
c = get_connection(**DB_DEFAULTS); c.autocommit = False; cur = c.cursor()

def kart(kod):
    cur.execute("SELECT Id, StokBirim, Aktif, Adi FROM StokKarti WHERE Kodu=?", kod); return cur.fetchone()

try:
    for kod in kodlar:
        cur.execute("SELECT COUNT(*) FROM UretimRecete WHERE Kodu=?", kod)
        if cur.fetchone()[0]: raise RuntimeError(f'{kod}: reçete kaydı zaten var')
        urun = kart(kod)
        cur.execute("""SELECT TOP 1 ue.Kodu, h.Id FROM UretimEmri ue JOIN UretimEmriHatPlani h ON h.UretimEmriId=ue.Id
          WHERE h.KartId=? AND h.HatTipi=1 ORDER BY ue.UretimEmriTarihi DESC, ue.Id DESC""", urun[0])
        kaynak, hid = cur.fetchone()
        cur.execute("""SELECT g.Tipi, g.KartId, g.Miktar, g.StokBirim, COALESCE(sk.Kodu, smk.Kodu), sk.Aktif
          FROM UretimEmriHatPlaniGirdi g LEFT JOIN StokKarti sk ON sk.Id=g.KartId AND g.Tipi<>2
          LEFT JOIN StokMasrafKarti smk ON smk.Id=g.KartId AND g.Tipi=2 WHERE g.UretimEmriHatPlaniId=? ORDER BY g.Id""", hid)
        satir = []; notlar = []
        for tipi, kid, mik, birim, gkod, aktif in cur.fetchall():
            if tipi != 2 and not aktif:
                if gkod not in DEGISIM: raise RuntimeError(f'{kod}: pasif kart {gkod} için karşılık tanımlı değil')
                for yeni in DEGISIM[gkod]:
                    yk = kart(yeni)
                    satir.append((1, yk[0], float(mik), yk[1] or ADET, yeni)); notlar.append(f'{gkod} → {yeni}')
                continue
            satir.append((tipi, kid, float(mik), birim or ADET, gkod))
        # aynı kart iki kez gelirse (değişim sonrası) tek satır, büyük miktar
        tekil = {}
        for s in satir:
            k = (s[0], s[1])
            if k in tekil: notlar.append(f'{s[4]} zaten listede — tek satır'); tekil[k] = max(tekil[k], s, key=lambda x: x[2])
            else: tekil[k] = s
        now = datetime.now().replace(microsecond=0)
        cur.execute("""INSERT INTO UretimRecete (Kodu, Tanim, UretimYontemi, KullanimDisi, Acik, Dipnot, CreatedBy, CreationTime, ModifiedBy, ModificationTime)
            OUTPUT INSERTED.Id VALUES (?, ?, 1, 0, 0, ?, ?, ?, ?, ?)""",
            kod, (urun[3] or kod).strip()[:200], f'Son üretim emri {kaynak} girdilerinden oluşturuldu (2026-11-11)', USER, now, USER, now)
        rid = int(cur.fetchone()[0])
        cur.execute("""INSERT INTO UretimReceteHatPlani (UretimReceteId, Tipi, KartId, Miktar, BirimId, DepoId)
            OUTPUT INSERTED.Id VALUES (?, 1, ?, 1, ?, ?)""", rid, urun[0], urun[1] or ADET, DEPO)
        rhid = int(cur.fetchone()[0])
        for tipi, kid, mik, birim, gkod in tekil.values():
            cur.execute("""INSERT INTO UretimReceteHatPlaniGirdi (UretimReceteHatPlaniId, Tipi, KartId, Miktar, BirimId, DepoId,
                SabitMiktar, GarantiKapsaminda, Yazdirma) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0)""", rhid, tipi, kid, mik, birim, DEPO)
        print(f'{kod}: reçete Id {rid}, hat {rhid}, {len(tekil)} girdi (kaynak {kaynak}) {"; ".join(notlar)}')
    if COMMIT: c.commit(); print('KAYDEDİLDİ')
    else: c.rollback(); print('DENEME — geri alındı')
except Exception as e:
    c.rollback(); print('HATA, geri alındı:', e); raise
