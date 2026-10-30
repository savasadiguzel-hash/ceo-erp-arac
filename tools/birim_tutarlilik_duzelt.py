#!/usr/bin/env python3
"""Reçete ve açık üretim emri birimlerini stok kartlarıyla eşitler.

Bu araç yalnızca daha önce incelenmiş, kesin kapsamı tanımlı iki grubu düzeltir:

* Aktif reçetelerde ``Tipi=1`` olan ve ADET görünen, ancak stok kartı KG/METRE
  olan satırlar.
* ``DurumId=3`` (Devam Ediyor) üretim emirlerinde aynı uyumsuzluğu taşıyan
  girdi satırları.

Miktar, fiyat, fatura, irsaliye ve stok hareketleri değiştirilmez. Varsayılan
    çalışma yalnızca ön izleme yapar; gerçek DB yazımı için ``--uygula``
    açıkça verilmelidir.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

ADET_GUID = "4ACC21E3-3140-4863-922D-A0B3D35DE8C1"

RECETE_ADAY_SQL = """
    SELECT
        urhpg.Id,
        ur.Kodu,
        sk.Kodu,
        sk.Adi,
        urhpg.Miktar,
        CONVERT(varchar(50), urhpg.BirimId),
        CONVERT(varchar(50), sk.StokBirim),
        sb.StokBirimAciklama
    FROM UretimReceteHatPlaniGirdi urhpg
    JOIN UretimReceteHatPlani urhp
        ON urhp.Id = urhpg.UretimReceteHatPlaniId
    JOIN UretimRecete ur
        ON ur.Id = urhp.UretimReceteId
    JOIN StokKarti sk
        ON sk.Id = urhpg.KartId
    LEFT JOIN [CeoCommon].dbo.StokBirim sb
        ON sb.StokBirimID = sk.StokBirim
    WHERE urhpg.Tipi = 1
      AND urhpg.BirimId = ?
      AND sk.StokBirim <> ?
      AND sk.Aktif = 1
      AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
      AND (? IS NULL OR ur.Kodu = ?)
    ORDER BY sk.Kodu, ur.Kodu, urhpg.Id
"""

EMIR_ADAY_SQL = """
    SELECT
        ueg.Id,
        ue.Kodu,
        sk.Kodu,
        sk.Adi,
        ueg.Miktar,
        ueg.TalepMiktar,
        CONVERT(varchar(50), ueg.StokBirim),
        CONVERT(varchar(50), sk.StokBirim),
        sb.StokBirimAciklama
    FROM UretimEmriHatPlaniGirdi ueg
    JOIN UretimEmriHatPlani uep
        ON uep.Id = ueg.UretimEmriHatPlaniId
    JOIN UretimEmri ue
        ON ue.Id = uep.UretimEmriId
    JOIN StokKarti sk
        ON sk.Id = ueg.KartId
    LEFT JOIN [CeoCommon].dbo.StokBirim sb
        ON sb.StokBirimID = sk.StokBirim
    WHERE ue.DurumId = 3
      AND ueg.Tipi = 1
      AND ueg.StokBirim = ?
      AND sk.StokBirim <> ?
      AND sk.Aktif = 1
    ORDER BY ue.Kodu, sk.Kodu, ueg.Id
"""


def _rows(conn, recete_kodu: str | None = None) -> tuple[list[tuple], list[tuple]]:
    cur = conn.cursor()
    try:
        cur.execute(
            RECETE_ADAY_SQL, ADET_GUID, ADET_GUID, recete_kodu, recete_kodu
        )
        recete = cur.fetchall()
        cur.execute(EMIR_ADAY_SQL, ADET_GUID, ADET_GUID)
        emir = cur.fetchall()
        return recete, emir
    finally:
        cur.close()


def _json_rows(recete: list[tuple], emir: list[tuple]) -> dict:
    return {
        "olusturma": datetime.now().isoformat(timespec="seconds"),
        "adet_guid": ADET_GUID,
        "recete_satirlari": [
            {
                "id": int(r[0]), "recete": str(r[1]), "stok_kodu": str(r[2]),
                "stok_adi": str(r[3] or "").strip(),
                "miktar": str(r[4]), "eski_birim_guid": str(r[5]),
                "yeni_birim_guid": str(r[6]), "yeni_birim": str(r[7] or ""),
            }
            for r in recete
        ],
        "acik_emir_satirlari": [
            {
                "id": int(r[0]), "emir": str(r[1]), "stok_kodu": str(r[2]),
                "stok_adi": str(r[3] or "").strip(),
                "miktar": str(r[4]), "talep_miktari": str(r[5]),
                "eski_birim_guid": str(r[6]), "yeni_birim_guid": str(r[7]),
                "yeni_birim": str(r[8] or ""),
            }
            for r in emir
        ],
    }


def _say(conn, sql: str) -> int:
    cur = conn.cursor()
    try:
        cur.execute(sql, ADET_GUID, ADET_GUID)
        return int(cur.fetchone()[0])
    finally:
        cur.close()


def duzelt(
    conn,
    uygula: bool,
    recete_kodu: str | None = None,
    sadece_recete: bool = False,
) -> tuple[int, int, Path | None]:
    recete, emir = _rows(conn, recete_kodu)
    if sadece_recete:
        emir = []
    print(f"Reçete aday satırı: {len(recete)}")
    print(f"Açık üretim emri aday satırı: {len(emir)}")

    if not uygula:
        print("Ön izleme tamamlandı; DB'ye yazılmadı. Gerçek işlem için --uygula kullanın.")
        return len(recete), len(emir), None

    yedek = BASE / f"birim_duzeltme_yedek_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    yedek.write_text(
        json.dumps(_json_rows(recete, emir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE urhpg
               SET BirimId = sk.StokBirim
            FROM UretimReceteHatPlaniGirdi urhpg
            JOIN UretimReceteHatPlani urhp
                ON urhp.Id = urhpg.UretimReceteHatPlaniId
            JOIN UretimRecete ur
                ON ur.Id = urhp.UretimReceteId
            JOIN StokKarti sk
                ON sk.Id = urhpg.KartId
            WHERE urhpg.Tipi = 1
              AND urhpg.BirimId = ?
              AND sk.StokBirim <> ?
              AND sk.Aktif = 1
              AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
              AND (? IS NULL OR ur.Kodu = ?)
        """, ADET_GUID, ADET_GUID, recete_kodu, recete_kodu)
        recete_guncel = cur.rowcount

        emir_guncel = 0
        if not sadece_recete:
            cur.execute("""
                UPDATE ueg
                   SET StokBirim = sk.StokBirim
                FROM UretimEmriHatPlaniGirdi ueg
                JOIN UretimEmriHatPlani uep
                    ON uep.Id = ueg.UretimEmriHatPlaniId
                JOIN UretimEmri ue
                    ON ue.Id = uep.UretimEmriId
                JOIN StokKarti sk
                    ON sk.Id = ueg.KartId
                WHERE ue.DurumId = 3
                  AND ueg.Tipi = 1
                  AND ueg.StokBirim = ?
                  AND sk.StokBirim <> ?
                  AND sk.Aktif = 1
            """, ADET_GUID, ADET_GUID)
            emir_guncel = cur.rowcount

        kalan_recete, kalan_emir = _rows(conn, recete_kodu)
        if sadece_recete:
            kalan_emir = []
        if (recete_guncel != len(recete) or emir_guncel != len(emir)
                or kalan_recete or kalan_emir):
            raise RuntimeError(
                "Ön izleme ve güncelleme kapsamı eşleşmedi; transaction geri alınacak. "
                f"beklenen=({len(recete)},{len(emir)}), "
                f"güncellenen=({recete_guncel},{emir_guncel}), "
                f"kalan=({kalan_recete},{kalan_emir})"
            )
        conn.commit()
        print(f"Reçete satırı güncellendi: {recete_guncel}")
        print(f"Açık üretim emri satırı güncellendi: {emir_guncel}")
        print(f"Yedek: {yedek}")
        return recete_guncel, emir_guncel, yedek
    except Exception:
        conn.rollback()
        try:
            yedek.unlink()
        except OSError:
            pass
        raise
    finally:
        cur.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Reçete ve açık emir birim tutarlılığı düzeltmesi")
    parser.add_argument(
        "--uygula", action="store_true",
        help="ön izlemeyi geçip tanımlı satırlara DB güncellemesi yap",
    )
    parser.add_argument(
        "--recete-kodu",
        help="yalnızca belirtilen reçete kodunu düzelt",
    )
    parser.add_argument(
        "--sadece-recete", action="store_true",
        help="açık üretim emri satırlarına geçmeden yalnızca reçeteyi düzelt",
    )
    args = parser.parse_args()

    if args.sadece_recete and not args.recete_kodu:
        parser.error("--sadece-recete için --recete-kodu da verilmelidir")

    from config import DB_DEFAULTS
    from db.baglanti import baglanti_ctx

    print(f"Bağlanılıyor: {DB_DEFAULTS.get('sunucu')} / {DB_DEFAULTS.get('veritabani')}")
    with baglanti_ctx(**DB_DEFAULTS) as conn:
        duzelt(conn, args.uygula, args.recete_kodu, args.sadece_recete)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
