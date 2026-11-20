"""Sene sonu emirleri için Merkez depoya transfer talebi (DepoTransferTalep + Detay) oluşturur.
Talep CEO'da 'Onay Bekliyor' (DurumId=2) açılır; kullanıcı kontrol edip CEO'dan Depolar Arası Transfer'e çevirir (stok hareketi CEO'da oluşur).
Kullanım: python transfer_talep.py [--commit]   (--commit yoksa rollback = deneme)
Miktar = kalan açık emirlerin Merkez depodaki toplam ihtiyacı − bugünkü Merkez bakiyesi (k23: kaynak depodan düşer, hedefe girer)."""
import sys, io
from collections import defaultdict
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection

KULLANICI = 'BDE76801-C1DD-499E-A51B-C23901B28197'
MERKEZ = 2
TRANSFER_TARIHI = '30.07.2026'   # kaynak depolarda stok 27.07.2026'dan beri var; ilk ihtiyaç 31.07.2026 (ŞİRKET.11112026-3)
KAYNAK = {  # kart -> çıkış deposu
    'SARF0000010': 3, 'HMGMKLM0005': 3, 'HMGMKNK0015': 3,       # ANONS
    'HMGZLKMND02': 4,                                            # PORTATİF
    'GMP-110-230004': 10012,                                     # BORESIGHT SP / KAMERALI / L
    'MW-LRS-1200-24': 10017,                                     # ADLAS-MKE
    'DS5160': 10010,                                             # ADLAS
}
GIRIS = (1, 4, 5, 8, 15, 16, 20, 22, 26, 29)
CIKIS = (2, 3, 6, 7, 17, 18, 19, 21, 24, 28)
COMMIT = '--commit' in sys.argv
c = get_connection(**DB_DEFAULTS); c.autocommit = False; cur = c.cursor()
cur.execute("SELECT Id, Adi FROM StokDepoKarti"); depo_ad = {r[0]: r[1].strip() for r in cur.fetchall()}

def depo_bakiye(kid):
    cur.execute("""SELECT sh.IslemKodu, COALESCE(shd.DepoKartId, sh.DepoKartId), COALESCE(shd.KarsiDepoKartId, sh.KarsiDepoKartId), shd.Miktar - ISNULL(f.Miktar,0)
      FROM StokHareketDetay shd JOIN StokHareket sh ON sh.Id=shd.HareketId LEFT JOIN StokHareketDetay f ON f.Id=shd.FaturaDetayId
      WHERE shd.IslemKartId=? AND shd.Turu=1 AND shd.Aktif=1 AND sh.Aktif=1 AND sh.FaturaId IS NULL AND sh.IslemKodu NOT IN (9,10,11,12,13,14,25,27)""", kid)
    b = defaultdict(float)
    for ik, d, kd, m in cur.fetchall():
        m = float(m or 0)
        if ik == 23:
            b[d] -= m
            if kd: b[kd] += m
        elif ik in GIRIS: b[d] += m
        elif ik in CIKIS: b[d] -= m
    return b

satirlar = []
for kod, kaynak in KAYNAK.items():
    cur.execute("SELECT Id, StokBirim, LEFT(Adi,45) FROM StokKarti WHERE Kodu=?", kod); kid, birim, ad = cur.fetchone()
    cur.execute("""SELECT g.TalepMiktar, ue.Kodu FROM UretimEmriHatPlaniGirdi g JOIN UretimEmriHatPlani h ON h.Id=g.UretimEmriHatPlaniId
      JOIN UretimEmri ue ON ue.Id=h.UretimEmriId
      WHERE g.KartId=? AND ISNULL(g.StokDepoId,2)=? AND g.Tipi<>2 AND ue.DurumId=3 AND (ue.SurecDipnot LIKE 'Fatura:%' OR ue.Kodu='ŞİRKET.1092026-3')
        AND NOT EXISTS (SELECT 1 FROM UretimEmriHatPlaniStokHareketleri x WHERE x.UretimEmriHatPlaniId=h.Id)""", kid, MERKEZ)
    rr = cur.fetchall(); ihtiyac = sum(float(r[0] or 0) for r in rr); emirler = ','.join(r[1] for r in rr)
    b = depo_bakiye(kid)
    eksik = round(ihtiyac - b[MERKEZ], 6)
    if eksik <= 0: print(f'  {kod}: eksik yok, atlandı'); continue
    if b[kaynak] < eksik: print(f'  ⚠ {kod}: kaynak depoda yetersiz ({b[kaynak]:g} < {eksik:g})')
    emir_kisa = ', '.join(sorted({e.replace('ŞİRKET.', '') for e in emirler.split(',')}))
    satirlar.append((kid, kod, ad, birim, kaynak, eksik, ihtiyac, b[MERKEZ], b[kaynak], emir_kisa))

print(f"{'Kod':16s} {'Ad':40s} {'Çıkış deposu':28s} {'Miktar':>7s} | ihtiyaç  Merkez  kaynak | emirler")
for kid, kod, ad, birim, kaynak, eksik, iht, bm, bk, em in satirlar:
    print(f'{kod:16s} {ad:40s} {depo_ad[kaynak][:28]:28s} {eksik:>7g} | {iht:>7g} {bm:>7g} {bk:>7g} | {em}')

not1 = f'SENE SONU ÜRETİM EMİRLERİ - Merkez depoda eksik girdiler. TRANSFER FİŞİ BELGE TARİHİ: {TRANSFER_TARIHI}'
cur.execute("""INSERT INTO DepoTransferTalep (Not1, Not2, CreatedBy, CreationTime, ModifiedBy, ModificationTime, DurumId, Acik)
  VALUES (?, ?, ?, GETDATE(), ?, GETDATE(), 2, 0); SELECT CAST(SCOPE_IDENTITY() AS bigint)""", not1, 'Savaş Adıgüzel', KULLANICI, KULLANICI)
cur.nextset(); tid = cur.fetchone()[0]
for i, (kid, kod, ad, birim, kaynak, eksik, iht, bm, bk, em) in enumerate(satirlar, 1):
    cur.execute("""INSERT INTO DepoTransferTalepDetay (TalepId, StokKartId, GirisDepoId, CikisDepoId, Not1, CreatedBy, CreationTime, ModifiedBy, ModificationTime,
        Not2, StokBirimId, Miktar, KalanMiktar, BirimKatsayi, SiraNo, Yazdirma) VALUES (?,?,?,?,?,?,GETDATE(),?,GETDATE(),?,?,?,?,1,?,0)""",
        tid, kid, MERKEZ, kaynak, f'Emirler: {em}'[:250], KULLANICI, KULLANICI, f'Belge tarihi {TRANSFER_TARIHI}', birim, eksik, eksik, i)
cur.execute("SELECT COUNT(*), SUM(Miktar) FROM DepoTransferTalepDetay WHERE TalepId=?", tid); n, top = cur.fetchone()
print(f'\nTalep Id {tid}: {n} satır, toplam {float(top):g} (DurumId=2 Onay Bekliyor)')
if COMMIT: c.commit(); print('COMMIT edildi.')
else: c.rollback(); print('ROLLBACK (deneme)')
