"""classifier.py — ASAMA 2: Katmanli Puanlama Matrisi ile parcalari siniflandirir.

Her parca icin uc bagımsız katmandan puan toplanir:
  Katman 1 — Malzeme    : SW'den okunan malzeme adi (optik malzemeler +100)
  Katman 2 — Geometri   : GetBox() ile alinan bb_x/bb_y/bb_z zarflari
  Katman 3 — Kelime/Yol : Dosya adi ve klasor yolundaki anahtar kelimeler

Karar: en yuksek puanli kategori secilir.
Belirsizlik (puan < 40 veya beraberlik) -> STATUS_UNKNOWN, guvenli varsayilan "Mekanik".

4 ana kategori: Mekanik, Elektronik, Montaj, Optik
  - Mil kategorisi kaldirildi; mil keywordleri Mekanik'e tasindi.
  - Mekanik Montaj + Elektronik Montaj -> Montaj olarak birlestirildi.
"""
from __future__ import annotations

from sw.models import Part, STATUS_NEW, STATUS_UNKNOWN, STATUS_EXISTING

# 4 ana kategori — konfig.xlsx sekme adlariyla birebir eslesir
CAT_MEKANIK   = "Mekanik"
CAT_ELEKTRONIK = "Elektronik"
CAT_MONTAJ    = "Montaj"
CAT_OPTIK     = "Optik"

# --- Anahtar kelime listeleri -----------------------------------------------

_OPTIK_MALZEME = (
    "cam", "glass", "quartz", "bk7", "fused silica",
    "safir", "sapphire", "ayna", "mirror",
)

_ELEK_MALZEME  = ("fr4", "fr-4", "cem-1", "copper", "bakir")

_POLIMER_MALZEME = (
    "delrin", "pom", "kestamid", "pa6", "pa6g",
    "abs", "tpu", "carbon", "teflon", "ptfe",
)

_MONTAJ_KELIME = ("pcb", "kart", "elektronik", "sensor", "power")

_OPTIK_KELIME  = (
    "lens", "prizma", "prism", "ayna", "window",
    "filtre", "filter", "pencere",
    "lazer", "laser", "lrf", "mercek", "prts",
)
_ELEK_KELIME   = (
    "pcb", "kart", "sensor", "direnc", "led", "button", "switch",
    "kablo", "cable", "connector", "konnektor",
    "board", "baski", "devre", "motherboard", "altium", "eagle",
    "mcu", "cpu", "vcc", "gnd", "ic", "module", "modul",
    "receiver", "emitter", "pil", "batarya", "battery", "a000057",
)
_MEK_KELIME    = (
    "sac", "plaka", "bracket", "govde", "flans", "flange", "destek",
    "mandren", "mandrel", "disli", "gear", "yuva", "kilif",
    "housing", "kapak", "tabla", "gövde",
    # eski Mil keywordleri Mekanik'e tasindi
    "mil", "shaft", "aks", "axis", "rod", "pim", "pin",
)

_STANDART_PARCA_KELIME = (
    "iso", "din", "sae", "screw", "bolt", "washer", "nut",
    "civata", "somun", "rulman", "bearing", "oring", "o-ring",
    "mhmf", "panasonic", "servo", "connector", "konnektor", "fan",
    "segman", "circlip", "yay", "spring", "helicoil",
    "insert", "percin", "rivet", "rondela", "kelepce", "ray",
)


# --- Yardimci ---------------------------------------------------------------

def _empty_scores() -> dict[str, int]:
    return {
        CAT_MEKANIK:    0,
        CAT_ELEKTRONIK: 0,
        CAT_MONTAJ:     0,
        CAT_OPTIK:      0,
    }


# --- Ana siniflandirma fonksiyonu -------------------------------------------

def classify_part(part: Part) -> Part:
    """Tek bir Part'i siniflandirir: category, status, reason alanlarini doldurur."""

    # ════════════════════════════════════════════════════════════════════════
    # KATMAN 0: Standart / Hazir Ticari Urun Kontrolu
    # ════════════════════════════════════════════════════════════════════════
    name_lower = (part.original_name + " " + part.file_path).lower()
    is_toolbox = "toolbox" in part.file_path.lower()
    is_standart = any(k in name_lower for k in _STANDART_PARCA_KELIME)
    if is_toolbox or is_standart:
        part.status   = STATUS_EXISTING
        part.category = None
        part.reason   = "Standart / hazir ticari urun tespiti"
        return part

    scores = _empty_scores()
    log: list[str] = []

    # ════════════════════════════════════════════════════════════════════════
    # ALT MONTAJ
    # ════════════════════════════════════════════════════════════════════════
    if part.is_assembly:
        scores[CAT_MONTAJ] += 80
        log.append(f"{CAT_MONTAJ}+80 (alt montaj)")

    # ════════════════════════════════════════════════════════════════════════
    # NORMAL PARCA
    # ════════════════════════════════════════════════════════════════════════
    else:
        mat = (part.material or "").lower()

        # --- Katman 1: Malzeme ---
        if any(k in mat for k in _OPTIK_MALZEME):
            scores[CAT_OPTIK] += 100
            log.append(f"{CAT_OPTIK}+100 (optik malzeme: '{part.material}')")
        if any(k in mat for k in _ELEK_MALZEME):
            scores[CAT_ELEKTRONIK] += 100
            log.append(f"{CAT_ELEKTRONIK}+100 (PCB malzeme: '{part.material}')")
        if any(k in mat for k in _POLIMER_MALZEME):
            scores[CAT_MEKANIK] += 100
            log.append(f"{CAT_MEKANIK}+100 (polimer malzeme: '{part.material}')")

        # --- Katman 2: Geometri (Atalet Momenti) ---
        # bb_x/bb_y/bb_z = Ixx/Iyy/Izz (kg*m²) — sw_reader GetMassProperties ile doldurur.
        # SW 2019 late-binding'de GetBoundingBox vtable-only oldugu icin BB okunamiyor;
        # atalet momentlerinin oranlari sekil tespiti icin kullanilir.
        i_sorted = sorted([part.bb_x, part.bb_y, part.bb_z])
        I_min, I_mid, I_max = i_sorted
        if I_max > 0:
            # Kural A: Silindirik/mil/pim — iki esit buyuk moment + bir kucuk
            # Silindir: I_perp1 ≈ I_perp2 (buyuk, esit), I_axial (kucuk)
            is_cylindrical = (I_mid / I_max > 0.7 and I_min / I_max < 0.25)
            if is_cylindrical:
                scores[CAT_MEKANIK] += 60
                log.append(
                    f"{CAT_MEKANIK}+60 (geometri silindirik: Imin/Imax={I_min/I_max:.2f} "
                    f"Imid/Imax={I_mid/I_max:.2f})"
                )

            # Kural B: Sac/plaka — Dik Eksen Teoremi: I_max ≈ I_min + I_mid
            # Silindirik ile ortusmeyi onlemek icin is_cylindrical kontrolu yapilir.
            perp_ratio = I_max / (I_min + I_mid) if (I_min + I_mid) > 0 else 0
            if not is_cylindrical and abs(perp_ratio - 1.0) < 0.15:
                scores[CAT_MEKANIK] += 50
                log.append(
                    f"{CAT_MEKANIK}+50 (geometri sac/plaka: Imax/(Imin+Imid)={perp_ratio:.2f})"
                )
                # Belirsiz ince plaka: isimde mekanik/elektronik ipucu yoksa AI'a devret
                has_mek_name  = any(k in name_lower for k in _MEK_KELIME)
                has_elek_name = any(k in name_lower for k in _ELEK_KELIME)
                if not has_mek_name and not has_elek_name:
                    part.category = CAT_MEKANIK
                    part.status   = STATUS_UNKNOWN
                    part.reason   = "Belirsiz ince plaka geometrisi (Mekanik/PCB shuphesi)"
                    if log:
                        part.reason += f" | Puanlar: {'; '.join(log)}"
                    return part

        # --- Katman 3: Kelime ve Yol Analizi ---
        if any(k in name_lower for k in _OPTIK_KELIME):
            scores[CAT_OPTIK] += 40
            log.append(f"{CAT_OPTIK}+40 (optik anahtar kelime)")
        if any(k in name_lower for k in _ELEK_KELIME):
            scores[CAT_ELEKTRONIK] += 100
            log.append(f"{CAT_ELEKTRONIK}+100 (elektronik anahtar kelime)")
        if any(k in name_lower for k in _MEK_KELIME):
            scores[CAT_MEKANIK] += 40
            log.append(f"{CAT_MEKANIK}+40 (mekanik anahtar kelime)")

    # ════════════════════════════════════════════════════════════════════════
    # KARAR
    # ════════════════════════════════════════════════════════════════════════
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_cat, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    # Belirsizlik: puan cok dusuk veya iki kategori esit
    uncertain = best_score < 40 or (best_score == second_score and best_score > 0)

    if uncertain:
        part.category = CAT_MEKANIK   # guvenli varsayilan
        part.status   = STATUS_UNKNOWN
        part.reason   = "Sistem kararsiz kaldi, el ile kontrol gerekli"
        if log:
            part.reason += f" | Puanlar: {'; '.join(log)}"
    else:
        part.category = best_cat
        part.status   = STATUS_NEW
        part.reason   = "; ".join(log) if log else "Varsayilan siniflandirma"

    # ════════════════════════════════════════════════════════════════════════
    # HARD CHECK: .SLDPRT dosyasi kesinlikle Montaj kategorisine atanamaz
    # ════════════════════════════════════════════════════════════════════════
    if not part.is_assembly and part.category == CAT_MONTAJ:
        part.category  = CAT_MEKANIK
        part.reason   += " | [HARD CHECK] .SLDPRT Montaj olamaz -> Mekanik"

    return part


def classify_parts(parts: list[Part]) -> list[Part]:
    """Part listesinin tamamini siniflandirir. main.py bu fonksiyonu cagirir."""
    return [classify_part(p) for p in parts]


# --- Tek basina test bloku --------------------------------------------------
# NOT: bb_x/bb_y/bb_z artik Ixx/Iyy/Izz (kg*m^2) tasimaktadir.
# Gercek degerler ancak SW'den GetMassProperties ile okunabilir.
# Geometrik katmanin test edilmesi icin test_bb_katman.py kullanin.
# Bu blok yalnizca Katman 0/1/3 (standart/malzeme/kelime) kurallari icin gecerlidir.
if __name__ == "__main__":
    ornekler = [
        # Katman 0: standart parca
        Part(r"C:\proj\iso_screw.SLDPRT",  "iso_screw",  False),
        # Katman 1: optik malzeme
        Part(r"C:\proj\lens_on.SLDPRT",    "lens_on",    False, material="BK7 glass"),
        # Katman 1: PCB malzeme
        Part(r"C:\proj\pcb_ana.SLDPRT",    "pcb_ana",    False, material="FR4"),
        # Katman 1: polimer
        Part(r"C:\proj\kapak.SLDPRT",      "kapak",      False, material="Delrin"),
        # Katman 3: mekanik keyword
        Part(r"C:\proj\shaft_main.SLDPRT", "shaft_main", False),
        # Katman 3: elektronik keyword
        Part(r"C:\proj\pcb_kontrol.SLDPRT","pcb_kontrol",False),
        # Belirsiz (moment yok)
        Part(r"C:\proj\parca.SLDPRT",      "parca",      False),
        # Alt montaj
        Part(r"C:\proj\alt_montaj.SLDASM", "alt_montaj", True),
    ]
    print(f"  {'PARCA':24} {'KATEGORI':14} {'STATUS':9} GEREKCE")
    print("  " + "-" * 95)
    for p in classify_parts(ornekler):
        print(f"  {p.original_name:24} {str(p.category):14} {p.status:9} {p.reason[:60]}")
