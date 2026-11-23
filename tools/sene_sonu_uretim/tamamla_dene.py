"""Bir emrin tüm hatlarını CEO'nun yerel tamamlama düzeniyle (16 Üretimden Giriş + 17 Üretime Çıkış + UretimEmriHatPlaniStokHareketleri)
TRANSACTION içinde yazar, aynı transaction'da stok bakiyelerinin önce/sonra halini ölçer ve HER ZAMAN GERİ ALIR (rollback).
Amaç: emir kapatılınca hangi kalemlerin eksiye düşeceğini görmek. Maliyet alanları (BirimFiyat/Tutar/MaliyetTutari) 0 yazılır —
gerçek kapanış CEO'da yapılmalı, maliyeti CEO hesaplar.
Kullanım: python tamamla_dene.py ŞİRKET.11112026-1"""
import sys, io
from datetime import datetime
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import stok_guncel_bakiyeleri
USER = 'BDE76801-C1DD-499E-A51B-C23901B28197'
kodu = sys.argv[1]
c = get_connection(**DB_DEFAULTS); c.autocommit = False; cur = c.cursor()
cur.execute("SELECT Id, Aciklama, UretimEmriTarihi FROM UretimEmri WHERE Kodu=?", kodu); eid, acik, etarih = cur.fetchone()
cur.execute("""SELECT h.Id, h.HatTipi, h.KartId, sk.Kodu, h.TalepMiktari, h.Birim, h.StokDepoId,
  (SELECT COUNT(*) FROM UretimEmriHatPlaniStokHareketleri x WHERE x.UretimEmriHatPlaniId=h.Id)
  FROM UretimEmriHatPlani h JOIN StokKarti sk ON sk.Id=h.KartId WHERE h.UretimEmriId=? ORDER BY h.HatTipi DESC, h.sira""", eid)
hatlar = [h for h in cur.fetchall() if not h[7]]   # yarı mamul hatları önce, sonra ana hat
etk = set()
for h in hatlar:
    etk.add(h[3])
    cur.execute("SELECT sk.Kodu FROM UretimEmriHatPlaniGirdi g JOIN StokKarti sk ON sk.Id=g.KartId WHERE g.UretimEmriHatPlaniId=? AND g.Tipi<>2", h[0])
    etk |= {r[0] for r in cur.fetchall()}
etk = sorted(etk)
once = stok_guncel_bakiyeleri(c, etk)
tarih = etarih.replace(hour=0, minute=0, second=0, microsecond=0)
notlar = f'{kodu} / {acik}'[:250]
def fis(islem):
    now = datetime.now().replace(microsecond=0)
    cur.execute("""INSERT INTO StokHareket (Aktif, IslemKodu, BelgeTarihi, BelgeSiraNo, DepoKartId, ToplamTutar, NetTutar, CreatedBy, CreationTime,
        ModifiedBy, ModificationTime, Notlar, MusteriBolgeId, HareketBolgeId) OUTPUT INSERTED.Id VALUES (1, ?, ?, ?, 2, 0, 0, ?, ?, ?, ?, ?, 2, 2)""",
        islem, tarih, f'{tarih.year}{tarih.month}{tarih.day}{now:%H%M%S}', USER, now, USER, now, notlar)
    return int(cur.fetchone()[0]), now
def detay(hid_fis, kart, birim, mik, depo, islem, now):
    cur.execute("""INSERT INTO StokHareketDetay (Aktif, Turu, HareketId, IslemKartId, StokBirimId, Miktar, BirimFiyat, Tutar, DepoKartId, BirimKatsayisi,
        MaliyetTarihi, MaliyetTutari, IslemKodu, KalanMiktar, CreatedBy, CreationTime, ModifiedBy, ModificationTime)
        VALUES (1, 1, ?, ?, ?, ?, 0, 0, ?, 1, ?, 0, ?, ?, ?, ?, ?, ?)""", hid_fis, kart, birim, mik, depo or 2, tarih, islem, mik, USER, now, USER, now)
try:
    for h_id, htip, kart, hkod, talep, birim, depo, _ in hatlar:
        cikis, now = fis(17)
        cur.execute("SELECT KartId, StokBirim, TalepMiktar, StokDepoId FROM UretimEmriHatPlaniGirdi WHERE UretimEmriHatPlaniId=? AND Tipi<>2", h_id)
        for gk, gb, gt, gd in cur.fetchall(): detay(cikis, gk, gb, float(gt), gd, 17, now)
        giris, now = fis(16)
        detay(giris, kart, birim, float(talep), depo, 16, now)
        cur.execute("INSERT INTO UretimEmriHatPlaniStokHareketleri (UretimEmriHatPlaniId, StokHareketId, UretimHatPlaniTuru) VALUES (?, ?, 0), (?, ?, 1)",
                    h_id, giris, h_id, cikis)
        print(f'  hat {hkod} x{float(talep):g}: 16 fiş {giris}, 17 fiş {cikis}')
    sonra = stok_guncel_bakiyeleri(c, etk)
finally:
    c.rollback(); print('GERİ ALINDI — kalıcı kayıt yok')
cur.execute("SELECT COUNT(*) FROM UretimEmriHatPlaniStokHareketleri x JOIN UretimEmriHatPlani h ON h.Id=x.UretimEmriHatPlaniId WHERE h.UretimEmriId=?", eid)
print('rollback kontrolü — emre bağlı hareket:', cur.fetchone()[0])
cur.execute(f"SELECT Kodu, Adi FROM StokKarti WHERE Kodu IN ({','.join('?'*len(etk))})", *etk); ad = dict(cur.fetchall())
print(f"\n{'Kod':24s} {'Önce':>9s} {'Sonra':>9s}  Durum")
for k in sorted(etk, key=lambda k: (sonra[k] >= -1e-9, sonra[k])):
    d = 'EKSİ' + (' (zaten eksiydi)' if once[k] < -1e-9 else ' (YENİ)') if sonra[k] < -1e-9 else ''
    print(f'{k:24s} {once[k]:>9.2f} {sonra[k]:>9.2f}  {d:18s} {(ad.get(k) or "").strip()[:40]}')
