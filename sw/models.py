"""models.py — Ortak veri yapilari.

Tum asamalar (sw_reader, classifier, excel_handler, renamer) veriyi
dosyaya yazip okumak yerine bu nesneler uzerinden birbirine aktarir.
Veri hep ayni Part nesnesinde "buyur": her asama kendi alanini doldurur.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


# --- Sabitler --------------------------------------------------------------
# Part.status alaninin alabilecegi degerler. Su an sadece NEW kullaniliyor;
# COImateClassifier akillanip ERP aramasi eklendiginde digerleri devreye girer.
STATUS_NEW             = "new"              # yeni parca, kod atanacak
STATUS_EXISTING        = "existing"         # standart ticari parca (civata vs.) - ERP'de hazir
STATUS_UNKNOWN         = "unknown"          # siniflandirilamadi, kullanici onayi gerekiyor
STATUS_PREVIOUSLY_CODED = "previously_coded" # daha once kodlanmis; geo imzayla eslesti


@dataclass
class Part:
    """Montajdaki benzersiz bir dosyayi (parca veya alt montaj) temsil eder.

    Alanlarin hangi asamada dolduruldugu:
      - Asama 1 / sw_reader  : file_path, original_name, is_assembly,
                               material, config_name, instance_count, suppressed,
                               bb_x, bb_y, bb_z
      - Asama 2 / classifier : category, status, reason
      - Excel adimi          : erp_code
    """
    file_path: str                # diskteki tam yol (.sldprt / .sldasm)
    original_name: str            # uzantisiz dosya adi (eski parca ismi)
    is_assembly: bool             # True ise alt montaj, False ise parca

    material: str | None = None       # parca malzemesi (varsa)
    config_name: str | None = None    # aktif konfigurasyon adi
    instance_count: int = 1           # montajda kac kez gectigi
    suppressed: bool = False          # bastirilmis (suppressed) bilesen mi
    is_imported: bool = False         # ozellik agacinda "Imported/Alinmis" var mi?
                                      # (STEP gibi ice aktarilmis parca -> kod verilmez)

    # Geometri — sw_reader GetMassProperties'ten doldurur (sadece parcalar, kg*m²)
    # SW 2019 late-binding'de GetBoundingBox/GetBox vtable-only; erisilemedigi icin
    # bu alanlara props[6/7/8] = Ixx/Iyy/Izz atalet momentleri kaydedilir.
    # classifier.py bu degerleri moment orani kurallariyla sekil tespitinde kullanir.
    bb_x: float = 0.0                 # I_xx atalet momenti (kg*m²) veya 0.0
    bb_y: float = 0.0                 # I_yy atalet momenti (kg*m²) veya 0.0
    bb_z: float = 0.0                 # I_zz atalet momenti (kg*m²) veya 0.0

    # Asama 2 / classifier doldurur
    category: str | None = None       # konfig.xlsx sekme adi: "Mekanik", "Mekanik Montaj" ...
    status: str = STATUS_NEW          # new / existing / unknown (yukaridaki sabitler)
    reason: str = ""                  # siniflandirma gerekcesi (onay ekraninda gosterilir)

    # Excel adimi doldurur
    erp_code: str | None = None       # atanan konfigurasyon kodu

    # Gorsel Zeka — export_part_image() tarafindan doldurulur
    image_path: str | None = None     # otonom cekilen fotografin disk yolu

    # Geometrik Parmak Izi — sw_reader tarafindan doldurulur
    # Format: "volume_surfacearea"         (basarili okuma)
    #         "HATA_OKUNAMADI_<isim>"      (Lightweight/API hatasi)
    #         None                         (alt montaj)
    geometric_signature: str | None = None

    @property
    def extension(self) -> str:
        return os.path.splitext(self.file_path)[1].lower()

    def __str__(self) -> str:
        tip = "ALT MONTAJ" if self.is_assembly else "PARCA"
        kod = self.erp_code or "(kod yok)"
        kat = self.category or "(siniflandirilmadi)"
        return f"[{tip}] {self.original_name} -> {kod} | {kat}"
