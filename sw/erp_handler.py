"""
erp_handler.py — CEO (Gempa CEO) ERP SQL Server entegrasyonu — STOK KARTI ACMA.

Oncelik 2: Ajan kod atadigi yeni parcalar icin CEO firma veritabaninda stok karti acar.
- Baglanti bilgisi .env -> CEO_SQL_CONN (sifre KODA YAZILMAZ; repoya girmez).
- VARSAYILAN KURU-CALISMA: live=False iken DB'ye HICBIR yazma yapilmaz; sadece ne
  olacagini doner/loglar. Yazma yalnizca live=True ile yapilir.
- Bir kartin CEO'da gorunmesi icin gereken 3 kayit TEK TRANSACTION'da olusturulur:
    1) StokKarti        (asil kart)
    2) StokKumulatif    (StokKartiView INNER JOIN sarti — yoksa kart listede gorunmez)
    3) StokKartiBolge   (BolgeId=2 Merkez — bolge bazli erisim sarti)
- Kod zaten varsa ATLANIR (mevcut kayda dokunulmaz).

CEO_SQL_CONN ornek (.env, tek satir; DATABASE YAZMAYIN — firma kod icinde secilir):
    CEO_SQL_CONN=DRIVER={SQL Server};SERVER=WIN-3FATBI9RQAA\\CEO1;UID=sa;PWD=********
"""

import os
import uuid as _uuid
from datetime import datetime

try:
    import pyodbc
except ImportError:  # pragma: no cover
    pyodbc = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# --- Sabitler (CeoCommon'da tanimli; tum firmalar arasi ortak) ---
ADET_BIRIM_GUID = "4acc21e3-3140-4863-922d-a0b3d35de8c1"   # StokBirim = ADET
SAVAS_USER_GUID = "bde76801-c1dd-499e-a51b-c23901b28197"   # CreatedBy/ModifiedBy
MERKEZ_BOLGE_ID = 2                                         # firma 500 ve 504'te "Merkez"

# DIKKAT: GERCEK calisma firmasi 504'tur (kullanicinin gordugu/kullandigi firma).
# 500'u MUHASEBECILER kullaniyor — bizim islerimiz icin DEGIL, oraya YAZMA.
FIRMA_GERCEK = "504"   # gercek calisma firmasi (kart buraya acilir)
DEFAULT_FIRMA_DB = FIRMA_GERCEK


def _tr_upper(s: str) -> str:
    """Turkce uyumlu buyuk harf (strip dahil): i→İ, diger karakterler Python upper ile."""
    return (s or "").strip().replace("i", "İ").upper()


class ErpError(Exception):
    """ERP baglanti/islem hatalari icin."""


# ---------------------------------------------------------------------------
# Baglanti
# ---------------------------------------------------------------------------
def _pick_driver():
    """Sistemde kurulu en uygun SQL Server ODBC surucusunu sec."""
    if pyodbc is None:
        raise ErpError("pyodbc kurulu degil. 'python -m pip install pyodbc' calistirin.")
    tercih = ["ODBC Driver 18 for SQL Server",
              "ODBC Driver 17 for SQL Server",
              "SQL Server Native Client 11.0",
              "SQL Server"]
    mevcut = [d for d in pyodbc.drivers()]
    for d in tercih:
        if d in mevcut:
            return d
    # SQL Server iceren ilk surucu
    for d in mevcut:
        if "SQL Server" in d:
            return d
    raise ErpError("SQL Server ODBC surucusu bulunamadi. Mevcut: %r" % mevcut)


def _conn_str_for(firma_db):
    """CEO_SQL_CONN tabanini alip DRIVER (gerekirse) ve DATABASE=<firma_db> ekler."""
    base = os.environ.get("CEO_SQL_CONN", "").strip()
    if not base:
        raise ErpError("CEO_SQL_CONN tanimli degil. .env dosyasina ekleyin "
                       "(DRIVER={SQL Server};SERVER=...;UID=...;PWD=...).")
    # mevcut DATABASE/Initial Catalog parcalarini ayikla (firmayi biz sececegiz)
    parcalar = [p for p in base.split(";")
                if p.strip() and not p.strip().lower().startswith(("database=", "initial catalog="))]
    if not any(p.strip().lower().startswith("driver=") for p in parcalar):
        parcalar.insert(0, "DRIVER={%s}" % _pick_driver())
    parcalar.append("DATABASE=%s" % firma_db)
    return ";".join(parcalar) + ";"


def get_connection(firma_db=DEFAULT_FIRMA_DB):
    """Belirtilen firma veritabanina pyodbc baglantisi (autocommit kapali)."""
    if pyodbc is None:
        raise ErpError("pyodbc kurulu degil.")
    try:
        return pyodbc.connect(_conn_str_for(firma_db), autocommit=False, timeout=10)
    except Exception as e:
        raise ErpError("CEO veritabanina baglanilamadi (%s): %s" % (firma_db, e))


# ---------------------------------------------------------------------------
# Sorgular
# ---------------------------------------------------------------------------
def kod_var_mi(cursor, kod):
    """Stok kodu zaten var mi? Varsa StokKarti.Id, yoksa None doner (SALT-OKUNUR)."""
    cursor.execute("SELECT TOP 1 Id FROM StokKarti WHERE Kodu = ?", kod)
    row = cursor.fetchone()
    return int(row[0]) if row else None


# ---------------------------------------------------------------------------
# Stok karti acma
# ---------------------------------------------------------------------------
def stok_karti_ac(kod, adi, firma_db=DEFAULT_FIRMA_DB, live=False,
                  adi2="",
                  birim_guid=ADET_BIRIM_GUID, user_guid=SAVAS_USER_GUID,
                  bolge_id=MERKEZ_BOLGE_ID, conn=None):
    """
    Tek stok karti acar (StokKarti + StokKumulatif + StokKartiBolge, tek transaction).

    Donen dict: {kod, durum, id, mesaj}
      durum: 'atlandi'        -> kod zaten var (dokunulmadi)
             'olusturulacak'  -> kuru-calisma (live=False), yazilmadi
             'olusturuldu'    -> live=True, gercekten yazildi
             'hata'           -> istisna olustu (mesaj'da)
    """
    kod  = (kod or "").strip()
    adi  = _tr_upper(adi)
    adi2 = _tr_upper(adi2)
    if not kod:
        return {"kod": kod, "durum": "hata", "id": None, "mesaj": "Bos kod"}

    dis_baglanti = conn is not None
    try:
        if conn is None:
            conn = get_connection(firma_db)
        cur = conn.cursor()

        mevcut = kod_var_mi(cur, kod)
        if mevcut is not None:
            return {"kod": kod, "durum": "atlandi", "id": mevcut,
                    "mesaj": "Kod zaten var (Id=%d), dokunulmadi" % mevcut}

        if not live:
            return {"kod": kod, "durum": "olusturulacak", "id": None,
                    "mesaj": "KURU-CALISMA: '%s' acilacakti (yazilmadi)" % adi}

        # --- GERCEK YAZMA (tek transaction) ---
        # NOT: yeni Id'yi OUTPUT INSERTED.Id ile ALIYORUZ. (pyodbc'de INSERT ve
        # SELECT SCOPE_IDENTITY() ayri batch oldugundan SCOPE_IDENTITY NULL doner;
        # StokKarti'da trigger olmadigi icin OUTPUT guvenli.)
        now = datetime.now()
        # NOT: AltStokBirim1/2/3Miktar = 1 ZORUNLU. NULL birakilirsa CEO stok karti
        # DETAY formu acilirken NULL->decimal donusumunde patlar (bos uyari penceresi).
        # (11362 kartin hepsinde bu alanlar dolu; sadece bos birakilan kart formu acmiyor.)
        cur.execute("""
            INSERT INTO StokKarti
                (Aktif, Kodu, Adi, Adi2, StokBirim, UretimFireDahil, WebSipariseDahilEt,
                 AltStokBirim1Aktif, AltStokBirim1Miktar, AltStokBirim2Aktif, AltStokBirim2Miktar,
                 AltStokBirim3Aktif, AltStokBirim3Miktar,
                 FabrikadaUretimde, FabrikadaUretilmis, CreatedBy, CreationTime,
                 ModifiedBy, ModificationTime, Acik, LotTakibi, SeriNoTakibi, Bakir, Bolgeler)
            OUTPUT INSERTED.Id
            VALUES (1, ?, ?, ?, ?, 0, 0, 0, 1, 0, 1, 0, 1, 0, 0, ?, ?, ?, ?, 0, 0, 0, 0, ?)
        """, kod, adi, adi2 or "", birim_guid, user_guid, now, user_guid, now, str(bolge_id))
        yeni_id = int(cur.fetchone()[0])

        cur.execute("INSERT INTO StokKumulatif (StokKartId, GirenMiktar, CikanMiktar) "
                    "VALUES (?, 0, 0)", yeni_id)
        cur.execute("INSERT INTO StokKartiBolge (KartId, BolgeId) VALUES (?, ?)",
                    yeni_id, bolge_id)

        conn.commit()
        return {"kod": kod, "durum": "olusturuldu", "id": yeni_id,
                "mesaj": "Kart acildi (Id=%d) + kumulatif + bolge=%d" % (yeni_id, bolge_id)}

    except Exception as e:
        try:
            if conn is not None:
                conn.rollback()
        except Exception:
            pass
        return {"kod": kod, "durum": "hata", "id": None, "mesaj": str(e)}
    finally:
        if conn is not None and not dis_baglanti:
            try:
                conn.close()
            except Exception:
                pass


def toplu_kart_ac(kartlar, firma_db=DEFAULT_FIRMA_DB, live=False, log=print):
    """
    kartlar: [(kod, adi), ...]  veya  .erp_code/.original_name tasiyan nesneler.
    Tek baglanti acar, hepsini sirayla isler. Ozet dict doner.
    """
    # Nesne -> (kod, adi) normalizasyonu
    ciftler = []
    for k in kartlar:
        if isinstance(k, (tuple, list)):
            ciftler.append((k[0], k[1] if len(k) > 1 else ""))
        else:
            ciftler.append((getattr(k, "erp_code", None), getattr(k, "original_name", "")))

    sonuc = {"olusturuldu": 0, "atlandi": 0, "olusturulacak": 0, "hata": 0, "detay": []}
    conn = None
    try:
        conn = get_connection(firma_db)
        mod = "CANLI YAZMA" if live else "KURU-CALISMA (yazma yok)"
        log("[ERP] Firma DB=%s | Mod=%s | %d kart" % (firma_db, mod, len(ciftler)))
        for kod, adi in ciftler:
            r = stok_karti_ac(kod, adi, firma_db=firma_db, live=live, conn=conn)
            sonuc[r["durum"]] = sonuc.get(r["durum"], 0) + 1
            sonuc["detay"].append(r)
            log("  [%s] %s — %s" % (r["durum"].upper(), r["kod"], r["mesaj"]))
    except ErpError as e:
        log("[ERP] HATA: %s" % e)
        sonuc["hata"] += 1
        sonuc["detay"].append({"kod": None, "durum": "hata", "id": None, "mesaj": str(e)})
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    log("[ERP] Ozet: olusturuldu=%(olusturuldu)d atlandi=%(atlandi)d "
        "kuru=%(olusturulacak)d hata=%(hata)d" % sonuc)
    return sonuc


# ---------------------------------------------------------------------------
# Masraf karti acma
# ---------------------------------------------------------------------------
def masraf_karti_var_mi(cursor, kod):
    """StokMasrafKarti'de kod var mi? Varsa Id, yoksa None."""
    cursor.execute("SELECT TOP 1 Id FROM StokMasrafKarti WHERE Kodu = ?", kod)
    row = cursor.fetchone()
    return int(row[0]) if row else None


def masraf_karti_ac(kod, adi, firma_db=DEFAULT_FIRMA_DB, live=False,
                    birim_guid=ADET_BIRIM_GUID, user_guid=SAVAS_USER_GUID,
                    conn=None):
    """
    Tek masraf karti acar (StokMasrafKarti).
    Donen dict: {kod, durum, id, mesaj}
      durum: 'atlandi' | 'olusturulacak' | 'olusturuldu' | 'hata'
    """
    kod = (kod or "").strip()
    adi = _tr_upper(adi)
    if not kod:
        return {"kod": kod, "durum": "hata", "id": None, "mesaj": "Bos kod"}

    dis_baglanti = conn is not None
    try:
        if conn is None:
            conn = get_connection(firma_db)
        cur = conn.cursor()

        mevcut = masraf_karti_var_mi(cur, kod)
        if mevcut is not None:
            return {"kod": kod, "durum": "atlandi", "id": mevcut,
                    "mesaj": "Masraf karti zaten var (Id=%d)" % mevcut}

        if not live:
            return {"kod": kod, "durum": "olusturulacak", "id": None,
                    "mesaj": "KURU: '%s' masraf karti acilacakti" % adi}

        now = datetime.now()
        cur.execute("""
            INSERT INTO StokMasrafKarti
                (Aktif, Kodu, Adi, StokBirimId,
                 CreatedBy, CreationTime, ModifiedBy, ModificationTime, Acik)
            OUTPUT INSERTED.Id
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, 0)
        """, kod, adi, birim_guid, user_guid, now, user_guid, now)
        yeni_id = int(cur.fetchone()[0])
        conn.commit()
        return {"kod": kod, "durum": "olusturuldu", "id": yeni_id,
                "mesaj": "Masraf karti acildi (Id=%d)" % yeni_id}

    except Exception as e:
        try:
            if conn is not None:
                conn.rollback()
        except Exception:
            pass
        return {"kod": kod, "durum": "hata", "id": None, "mesaj": str(e)}
    finally:
        if conn is not None and not dis_baglanti:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# BOM / Recete baglantisi
# ---------------------------------------------------------------------------
def recete_bagla(parent_kod, parent_adi, parent_stok_id, child_stok_id, miktar,
                 firma_db=DEFAULT_FIRMA_DB, live=False, conn=None):
    """
    parent_kod stok kodu icin UretimRecete + UretimReceteHatPlani olusturur (yoksa).
    Sonra UretimReceteHatPlaniGirdi'ye child_stok_id + miktar ekler (yoksa).

    Donen dict: {durum: 'olusturuldu'|'olusturulacak'|'atlandi'|'hata', mesaj}
    """
    dis_baglanti = conn is not None
    try:
        if conn is None:
            conn = get_connection(firma_db)
        cur = conn.cursor()

        # 1. Mevcut UretimRecete + HatPlani kontrol
        cur.execute(
            "SELECT TOP 1 Id FROM UretimRecete WHERE Kodu = ? "
            "AND (KullanimDisi IS NULL OR KullanimDisi = 0)",
            parent_kod,
        )
        row = cur.fetchone()
        recete_id    = row[0] if row else None
        hat_plani_id = None

        if recete_id is not None:
            cur.execute(
                "SELECT TOP 1 Id FROM UretimReceteHatPlani WHERE UretimReceteId = ?",
                recete_id,
            )
            h = cur.fetchone()
            hat_plani_id = h[0] if h else None

        # 2. Girdi zaten var mi?
        if hat_plani_id is not None:
            cur.execute(
                "SELECT TOP 1 Id FROM UretimReceteHatPlaniGirdi "
                "WHERE UretimReceteHatPlaniId = ? AND KartId = ?",
                hat_plani_id, child_stok_id,
            )
            if cur.fetchone():
                return {"durum": "atlandi", "mesaj": "Girdi zaten mevcut"}

        if not live:
            parcalar = []
            if recete_id is None:    parcalar.append("Recete")
            if hat_plani_id is None: parcalar.append("HatPlani")
            parcalar.append("Girdi")
            return {"durum": "olusturulacak",
                    "mesaj": "KURU: %s olusturulacakti" % "+".join(parcalar)}

        # 3. UretimRecete olustur (yoksa) — Id IDENTITY, belirtme
        if recete_id is None:
            _now = datetime.now()
            cur.execute(
                "INSERT INTO UretimRecete "
                "(Kodu, Tanim, KullanimDisi, UretimYontemi, Acik, "
                "CreatedBy, CreationTime, ModifiedBy, ModificationTime) "
                "OUTPUT INSERTED.Id VALUES (?, ?, 0, 1, 0, ?, ?, ?, ?)",
                parent_kod, parent_adi or parent_kod,
                SAVAS_USER_GUID, _now, SAVAS_USER_GUID, _now,
            )
            recete_id = cur.fetchone()[0]

        # 4. UretimReceteHatPlani olustur (yoksa) — Id IDENTITY, belirtme
        if hat_plani_id is None:
            cur.execute(
                "INSERT INTO UretimReceteHatPlani (UretimReceteId, KartId, Tipi) "
                "OUTPUT INSERTED.Id VALUES (?, ?, 2)",
                recete_id, parent_stok_id,
            )
            hat_plani_id = cur.fetchone()[0]

        # 5. Girdi ekle — BirimId/DepoId zorunlu (NULL bırakılırsa CEO iş emri NullReferenceException fırlatır)
        cur.execute(
            "INSERT INTO UretimReceteHatPlaniGirdi "
            "(UretimReceteHatPlaniId, Tipi, KartId, Miktar, SabitMiktar, GarantiKapsaminda, BirimId, DepoId) "
            "VALUES (?, 1, ?, ?, 0, 0, ?, ?)",
            hat_plani_id, child_stok_id, float(miktar), ADET_BIRIM_GUID, MERKEZ_BOLGE_ID,
        )

        conn.commit()
        return {"durum": "olusturuldu", "mesaj": "BOM baglantisi olusturuldu"}

    except Exception as e:
        try:
            if conn is not None:
                conn.rollback()
        except Exception:
            pass
        return {"durum": "hata", "mesaj": str(e)}
    finally:
        if conn is not None and not dis_baglanti:
            try:
                conn.close()
            except Exception:
                pass


def recete_masraf_bagla(parent_kod, parent_adi, parent_stok_id, masraf_id, miktar,
                        firma_db=DEFAULT_FIRMA_DB, live=False, conn=None):
    """
    parent_kod reçetesine masraf bileşeni (Tipi=2) ekler.
    UretimRecete + HatPlani yoksa olusturur, sonra UretimReceteHatPlaniGirdi'ye
    Tipi=2 ile ekler.
    Donen dict: {durum, mesaj}
    """
    dis_baglanti = conn is not None
    try:
        if conn is None:
            conn = get_connection(firma_db)
        cur = conn.cursor()

        cur.execute(
            "SELECT TOP 1 Id FROM UretimRecete WHERE Kodu = ? "
            "AND (KullanimDisi IS NULL OR KullanimDisi = 0)",
            parent_kod,
        )
        row = cur.fetchone()
        recete_id    = row[0] if row else None
        hat_plani_id = None

        if recete_id is not None:
            cur.execute(
                "SELECT TOP 1 Id FROM UretimReceteHatPlani WHERE UretimReceteId = ?",
                recete_id,
            )
            h = cur.fetchone()
            hat_plani_id = h[0] if h else None

        if hat_plani_id is not None:
            cur.execute(
                "SELECT TOP 1 Id FROM UretimReceteHatPlaniGirdi "
                "WHERE UretimReceteHatPlaniId = ? AND KartId = ? AND Tipi = 2",
                hat_plani_id, masraf_id,
            )
            if cur.fetchone():
                return {"durum": "atlandi", "mesaj": "Masraf girdisi zaten mevcut"}

        if not live:
            parcalar = []
            if recete_id is None:    parcalar.append("Recete")
            if hat_plani_id is None: parcalar.append("HatPlani")
            parcalar.append("MasrafGirdi")
            return {"durum": "olusturulacak",
                    "mesaj": "KURU: %s olusturulacakti" % "+".join(parcalar)}

        if recete_id is None:
            _now = datetime.now()
            cur.execute(
                "INSERT INTO UretimRecete "
                "(Kodu, Tanim, KullanimDisi, UretimYontemi, Acik, "
                "CreatedBy, CreationTime, ModifiedBy, ModificationTime) "
                "OUTPUT INSERTED.Id VALUES (?, ?, 0, 1, 0, ?, ?, ?, ?)",
                parent_kod, parent_adi or parent_kod,
                SAVAS_USER_GUID, _now, SAVAS_USER_GUID, _now,
            )
            recete_id = cur.fetchone()[0]

        if hat_plani_id is None:
            cur.execute(
                "INSERT INTO UretimReceteHatPlani (UretimReceteId, KartId, Tipi) "
                "OUTPUT INSERTED.Id VALUES (?, ?, 2)",
                recete_id, parent_stok_id,
            )
            hat_plani_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO UretimReceteHatPlaniGirdi "
            "(UretimReceteHatPlaniId, Tipi, KartId, Miktar, SabitMiktar, GarantiKapsaminda, BirimId, DepoId) "
            "VALUES (?, 2, ?, ?, 0, 0, ?, ?)",
            hat_plani_id, masraf_id, float(miktar), ADET_BIRIM_GUID, MERKEZ_BOLGE_ID,
        )
        conn.commit()
        return {"durum": "olusturuldu", "mesaj": "Masraf BOM baglantisi olusturuldu"}

    except Exception as e:
        try:
            if conn is not None:
                conn.rollback()
        except Exception:
            pass
        return {"durum": "hata", "mesaj": str(e)}
    finally:
        if conn is not None and not dis_baglanti:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# BOM satiri guncelleme / silme
# ---------------------------------------------------------------------------
def recete_satiri_guncelle(girdi_id: int, yeni_miktar: float,
                            live: bool = False, conn=None):
    """
    UretimReceteHatPlaniGirdi.Miktar'i gunceller.
    Donen dict: {durum, mesaj}
    """
    dis_baglanti = conn is not None
    try:
        if conn is None:
            conn = get_connection()
        cur = conn.cursor()
        if not live:
            return {"durum": "olusturulacak",
                    "mesaj": "KURU: Id=%d Miktar=%g güncellenecekti" % (girdi_id, yeni_miktar)}
        cur.execute(
            "UPDATE UretimReceteHatPlaniGirdi SET Miktar = ? WHERE Id = ?",
            float(yeni_miktar), int(girdi_id),
        )
        conn.commit()
        return {"durum": "guncellendi", "mesaj": "Miktar güncellendi"}
    except Exception as e:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        return {"durum": "hata", "mesaj": str(e)}
    finally:
        if conn and not dis_baglanti:
            try:
                conn.close()
            except Exception:
                pass


def recete_satiri_sil(girdi_id: int, live: bool = False, conn=None):
    """
    UretimReceteHatPlaniGirdi satirini siler.
    Donen dict: {durum, mesaj}
    """
    dis_baglanti = conn is not None
    try:
        if conn is None:
            conn = get_connection()
        cur = conn.cursor()
        if not live:
            return {"durum": "olusturulacak",
                    "mesaj": "KURU: Id=%d silinecekti" % girdi_id}
        cur.execute(
            "DELETE FROM UretimReceteHatPlaniGirdi WHERE Id = ?", int(girdi_id)
        )
        conn.commit()
        return {"durum": "silindi", "mesaj": "Bileşen silindi"}
    except Exception as e:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        return {"durum": "hata", "mesaj": str(e)}
    finally:
        if conn and not dis_baglanti:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Komut satiri (hizli test)
# ---------------------------------------------------------------------------
def _main():
    import argparse
    ap = argparse.ArgumentParser(description="CEO ERP stok karti acma (varsayilan kuru-calisma).")
    ap.add_argument("--firma", default=DEFAULT_FIRMA_DB, help="Firma DB (varsayilan 504 test)")
    ap.add_argument("--kod", help="Tek kart: stok kodu")
    ap.add_argument("--adi", default="", help="Tek kart: stok adi")
    ap.add_argument("--canli", action="store_true", help="GERCEK YAZMA (verilmezse kuru-calisma)")
    ap.add_argument("--kontrol", metavar="KOD", help="Sadece kod var mi diye bak (salt-okunur)")
    args = ap.parse_args()

    if args.kontrol:
        conn = get_connection(args.firma)
        try:
            cur = conn.cursor()
            mevcut = kod_var_mi(cur, args.kontrol)
            print("VAR (Id=%d)" % mevcut if mevcut else "YOK")
        finally:
            conn.close()
        return

    if not args.kod:
        ap.error("--kod veya --kontrol verin.")
    r = stok_karti_ac(args.kod, args.adi, firma_db=args.firma, live=args.canli)
    print("%s | %s | %s" % (r["durum"].upper(), r["kod"], r["mesaj"]))


if __name__ == "__main__":
    _main()
