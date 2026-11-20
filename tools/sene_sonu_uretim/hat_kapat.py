"""Üretim emri hatlarını CEO'nun kapanış düzeniyle kapatır (16 Üretimden Giriş + 17 Üretime Çıkış). Verilen sırayla, verilen belge tarihiyle.
Kullanım: python hat_kapat.py "ŞİRKET.1092026-3" GG.AA.YYYY HAT [HAT ...] [GG.AA.YYYY HAT ...] [--commit] [--beklenen dosya.json]
  (birden çok tarih grubu verilebilir; --commit yoksa rollback = deneme; --beklenen satır bazında hesaplanan maliyetleri kaydeder)
CEO kalıbı (CEO'nun 20.11.2026'da kapattığı hatlardan alan alan çıkarıldı):
  - 16 ve 17 başlıkları aynı BelgeSiraNo (yıl+ay+gün+SSDDss, sıfırsız ay/gün), Notlar = "<emir> / <açıklama>", DepoKartId=2, bölge 2/2, vergi alanları 0.
  - Detay: Turu 1 stok / 3 masraf (IslemKartId = masraf kart Id), BirimKatsayisi = Miktar (tetikleyici StokKumulatif'i bununla günceller),
    KalanMiktar = Miktar, MaliyetTarihi = belge tarihi, MaliyetTutari = Tutar. Satırlar TEK TEK eklenir (tetikleyici tek satır okur).
  - UretimEmriHatPlaniStokHareketleri: 16 → Turu 0, 17 → Turu 1. Hat.MaliyetlendirilenMiktar = TalepMiktari.
  - Tüm hatlar kapanınca UretimEmri.DurumId = 5 + UretimEmriTarihce satırı.
Maliyet: stok satırı DEPO BAZLI FIFO (girdinin deposunda; k23 transferleri katman sayılır). CEO 20.11 fişleriyle 134 satırın 130'unda birebir. Masraf satırı = girdi Tutar. 16 maliyeti = 17 toplamı.
Kapanış sonrası CEO Toplu Maliyetlendirme ile yeniden hesaplatılabilir."""
import sys, io, json
from datetime import datetime
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import stok_guncel_bakiyeleri

USER = 'BDE76801-C1DD-499E-A51B-C23901B28197'
GIR = (1, 4, 5, 8, 15, 16, 20, 22, 26, 29); CIK = (2, 3, 6, 7, 17, 18, 19, 21, 24, 28)
a = [x for x in sys.argv[1:] if x != '--commit']; COMMIT = '--commit' in sys.argv
BEKLENEN = None
if '--beklenen' in a: i = a.index('--beklenen'); BEKLENEN = a[i + 1]; del a[i:i + 2]
EMIR = a[0]; HATLAR = []; TARIH = None
for x in a[1:]:
    try: TARIH = datetime.strptime(x, '%d.%m.%Y'); continue
    except ValueError: HATLAR.append((TARIH, x))
c = get_connection(**DB_DEFAULTS); c.autocommit = False; cur = c.cursor()
cur.execute("SELECT Id, Aciklama, DurumId FROM UretimEmri WHERE Kodu=?", EMIR); eid, acik, durum = cur.fetchone()
assert durum == 3, f'emir durumu {durum}, Devam Ediyor değil'
NOT = f'{EMIR} / {(acik or "").strip()}'[:250]

def fifo(kid, miktar, depo):
    """Depo bazlı FIFO (CEO ile 20.11.2026 fişlerinde 134 satırın 130'u birebir). Girişler: depodaki giriş kodları + bu depoya gelen k23;
    önceki çıkışlar: depodaki çıkış kodları + bu depodan giden k23. Katman bölünürse ağırlıklı ortalama; yetmezse son giriş fiyatı."""
    cur.execute(f"""SELECT sh.Id, sh.BelgeTarihi, sh.IslemKodu, d.Miktar, d.BirimFiyat, COALESCE(d.DepoKartId, sh.DepoKartId), COALESCE(d.KarsiDepoKartId, sh.KarsiDepoKartId)
      FROM StokHareketDetay d JOIN StokHareket sh ON sh.Id=d.HareketId
      WHERE d.IslemKartId=? AND d.Turu=1 AND d.Aktif=1 AND sh.Aktif=1 AND sh.FaturaId IS NULL AND sh.BelgeTarihi<=?
        AND sh.IslemKodu IN {GIR + CIK + (23,)}""", kid, TARIH)
    gir, cik = [], 0.0
    for i, t, ik, m, f, d, kd in cur.fetchall():
        m = float(m); f = float(f or 0)
        if ik == 23:
            if kd == depo: gir.append((t, i, m, f))
            if d == depo: cik += m
        elif ik in GIR and d == depo: gir.append((t, i, m, f))
        elif ik in CIK and d == depo: cik += m
    gir.sort()
    kal, top, al = cik, 0.0, 0.0
    for t, i, m, f in gir:
        if kal >= m - 1e-9: kal -= m; continue
        kullan = min(m - kal, miktar - al); top += kullan * f; al += kullan; kal = 0
        if al >= miktar - 1e-9: break
    if al < miktar - 1e-9:
        son = gir[-1][3] if gir else 0.0; top += (miktar - al) * son
    return round(top / miktar, 6) if miktar else 0.0

def baslik(islem, sira, toplam):
    now = datetime.now()
    cur.execute("""SET NOCOUNT ON; INSERT INTO StokHareket (Aktif, IhracKayitliMi, IslemKodu, BelgeTarihi, BelgeSiraNo, DepoKartId, ToplamTutar, SatirlarinIskontoToplamTutari,
        KdvMatrahiToplamTutari, KdvToplamTutari, KdvTevfikatTutari, OtvTutari, OzelIletisimVerigisiToplamTutari, NetTutar, IrsaliyedenMi, KonsinyedenMi, Acik,
        CreatedBy, CreationTime, ModifiedBy, ModificationTime, Notlar, EntegreDurumu, MusteriBolgeId, HareketBolgeId, ITS, PTS, EPDKdanmi,
        HatirlatmayaGelmesin, OdemePlaniIslendi, Odendi, InternetSatisi, KdvDahil)
      VALUES (1,0,?,?,?,2,?,0,0,0,0,0,0,?,0,0,0,?,?,?,?,?,0,2,2,0,0,0,0,0,0,0,0); SELECT CAST(SCOPE_IDENTITY() AS bigint)""",
        islem, TARIH, sira, toplam, toplam, USER, now, USER, now, NOT)
    while cur.description is None:
        if not cur.nextset(): raise RuntimeError('Id okunamadı')
    return int(cur.fetchone()[0])

def detay(hid, turu, kid, birim, mik, bf, depo, islem):
    now = datetime.now(); tutar = round(bf * mik, 6)
    cur.execute("""INSERT INTO StokHareketDetay (Aktif, Yazdirma, Turu, HareketId, IslemKartId, KdvOrani, StokBirimId, Miktar, BirimFiyat, Tutar,
        OzelIslemVergisiOrani, DepoKartId, BirimKatsayisi, MaliyetTarihi, MaliyetTutari, IslemKodu, IrsaliyedenMi, KalanMiktar, KonsinyedenMi,
        CreatedBy, CreationTime, ModifiedBy, ModificationTime)
      VALUES (1,0,?,?,?,0,?,?,?,?,0,?,?,?,?,?,0,?,0,?,?,?,?)""",
        turu, hid, kid, birim, mik, bf, tutar, depo, mik, TARIH, tutar, islem, mik, USER, now, USER, now)
    return tutar

rapor = []; kartlar = set(); beklenen = []
for TARIH, hkod in HATLAR:
    cur.execute("""SELECT h.Id, h.KartId, h.TalepMiktari, h.Birim, ISNULL(h.StokDepoId,2),
        (SELECT COUNT(*) FROM UretimEmriHatPlaniStokHareketleri x WHERE x.UretimEmriHatPlaniId=h.Id)
      FROM UretimEmriHatPlani h JOIN StokKarti hk ON hk.Id=h.KartId WHERE h.UretimEmriId=? AND hk.Kodu=?""", eid, hkod)
    hid, hkid, talep, hbirim, hdepo, kapali = cur.fetchone(); talep = float(talep)
    assert not kapali, f'{hkod} zaten kapalı'
    cur.execute("""SELECT g.Tipi, g.KartId, g.StokBirim, g.TalepMiktar, ISNULL(g.StokDepoId,2), ISNULL(g.Tutar,0), COALESCE(sk.Kodu, m.Kodu)
      FROM UretimEmriHatPlaniGirdi g LEFT JOIN StokKarti sk ON sk.Id=g.KartId AND g.Tipi<>2 LEFT JOIN StokMasrafKarti m ON m.Id=g.KartId AND g.Tipi=2
      WHERE g.UretimEmriHatPlaniId=? AND (g.Yazilmasin IS NULL OR g.Yazilmasin=0) ORDER BY g.Id""", hid)
    gs = cur.fetchall()
    sira = int(f'{TARIH.year}{TARIH.month}{TARIH.day}{datetime.now():%H%M%S}')
    satirlar = []
    for tip, kid, birim, mik, depo, tut, kod in gs:
        mik = float(mik)
        if tip == 2: bf = round(float(tut) / mik, 6) if mik else 0.0; turu = 3
        else: bf = fifo(kid, mik, depo); turu = 1; kartlar.add(kod)
        satirlar.append((turu, kid, birim, mik, bf, depo, kod)); beklenen.append({'hat': hkod, 'tarih': TARIH.strftime('%d.%m.%Y'), 'kod': kod, 'turu': turu, 'miktar': mik, 'birim_fiyat': bf})
    toplam = round(sum(s[4] * s[3] for s in satirlar), 2)
    f17 = baslik(17, sira, toplam)
    for s in satirlar: detay(f17, s[0], s[1], s[2], s[3], s[4], s[5], 17)
    f16 = baslik(16, sira, toplam)
    detay(f16, 1, hkid, hbirim, talep, round(toplam / talep, 6), hdepo, 16); kartlar.add(hkod)
    cur.execute("INSERT INTO UretimEmriHatPlaniStokHareketleri (UretimEmriHatPlaniId, StokHareketId, UretimHatPlaniTuru) VALUES (?,?,0)", hid, f16)
    cur.execute("INSERT INTO UretimEmriHatPlaniStokHareketleri (UretimEmriHatPlaniId, StokHareketId, UretimHatPlaniTuru) VALUES (?,?,1)", hid, f17)
    cur.execute("UPDATE UretimEmriHatPlani SET MaliyetlendirilenMiktar=TalepMiktari WHERE Id=?", hid)
    beklenen.append({'hat': hkod, 'tarih': TARIH.strftime('%d.%m.%Y'), 'kod': hkod, 'turu': 16, 'miktar': talep, 'birim_fiyat': round(toplam / talep, 6)})
    rapor.append((hkod, talep, len(satirlar), toplam, f17, f16, [s for s in satirlar if s[0] == 1 and s[4] == 0]))

cur.execute("SELECT COUNT(*) FROM UretimEmriHatPlani h WHERE h.UretimEmriId=? AND NOT EXISTS (SELECT 1 FROM UretimEmriHatPlaniStokHareketleri x WHERE x.UretimEmriHatPlaniId=h.Id)", eid)
acik_hat = cur.fetchone()[0]
if acik_hat == 0:
    cur.execute("UPDATE UretimEmri SET DurumId=5, ModifiedBy=?, ModificationTime=GETDATE() WHERE Id=?", USER, eid)
    cur.execute("""INSERT INTO UretimEmriTarihce (UretimEmriId, KullaniciId, Tarih, Aciklama, IsOnay, EskiUretimDurumId, YeniUretimDurumId)
      VALUES (?, ?, GETDATE(), 'Üretim emri hareketi durumu değişti.Eski durum : Devam Ediyor Yeni durum : Tamamlandı', 0, 3, 5)""", eid, USER)

for hkod, talep, n, top, f17, f16, sifir in rapor:
    print(f'{hkod:18s} ×{talep:g}: 17 fiş {f17} ({n} satır), 16 fiş {f16} | maliyet {top:,.2f} (birim {top/talep:,.2f})' + (f' | 0 fiyatlı: {[s[6] for s in sifir]}' if sifir else ''))
print('emirde açık hat kalan:', acik_hat, '→ emir Tamamlandı' if acik_hat == 0 else '')
# tutarlılık: StokKumulatif = formül (tüm tarihler)
kl = sorted(kartlar); bak = stok_guncel_bakiyeleri(c, kl, '2099-12-31')
cur.execute(f"SELECT sk.Kodu, k.GirenMiktar-k.CikanMiktar FROM StokKumulatif k JOIN StokKarti sk ON sk.Id=k.StokKartId WHERE sk.Kodu IN ({','.join('?'*len(kl))})", *kl)
kum = {r[0]: float(r[1] or 0) for r in cur.fetchall()}
uyumsuz = [(k, bak[k], kum.get(k)) for k in kl if kum.get(k) is not None and abs(bak[k] - kum[k]) > 1e-6]
print('StokKumulatif ≠ formül:', uyumsuz[:8], f'({len(uyumsuz)} kart)')
for T in sorted({t for t, _ in HATLAR}):
    eksi = {k: v for k, v in stok_guncel_bakiyeleri(c, kl, T.strftime('%Y-%m-%d')).items() if v < -1e-6}
    print(f'{T:%d.%m.%Y} itibarıyla eksiye düşen:', eksi)
if BEKLENEN: json.dump(beklenen, open(BEKLENEN, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); print('beklenen maliyetler:', BEKLENEN)
if COMMIT: c.commit(); print('COMMIT edildi.')
else: c.rollback(); print('ROLLBACK (deneme)')
