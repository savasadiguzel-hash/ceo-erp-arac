"""renamer.py — ASAMA 3: Kodlanmis kopya uretir (Python kopyalama + SW referans guncelleme).

NE YAPAR:
  Montaj agacindaki tum dosyalari ERP koduyla yeniden adlandirarak
  hedef bir klasore KOPYALAR. Orijinal dosyalara DOKUNMAZ.
  Kopyadaki montaj referanslari SolidWorks API ile guncellenir.

YONTEM (2 asamali):
  1. KOPYALA: Python shutil ile tum dosyalari (Part listesindeki her Part)
     hedef klasore kopyalar, ERP kodu olan dosyalari yeni adla kaydeder.
  2. REFERANS GUNCELLE: swApp.ReplaceReferencedDocument ile dosyalari
     acmadan/kapatmadan dogrudan SW uygulama nesnesi uzerinden gunceller.

EN ONEMLI OZELLIK — dry_run:
  dry_run=True (varsayilan) iken HICBIR DOSYA olusturulmaz/kopyalanmaz.
  SolidWorks COM'a BAGLANMAZ — sadece Part listesinden plan basilir.
  Gercekten calistirmak icin acikca dry_run=False vermen gerekir.

  ILK DENEMENI MUTLAKA dry_run=True ILE YAP.

NOT: Referans guncelleme (Asama 2) SolidWorks COM gerektirir.
Dosya kopyalama (Asama 1) ise SolidWorks olmadan calisir.
"""
from __future__ import annotations

import os
import shutil

try:
    import win32com.client
    import pythoncom
except ImportError:
    win32com = None
    pythoncom = None

from sw.models import Part, STATUS_EXISTING

SW_DOC_ASSEMBLY = 2
SW_DOC_PART = 1
SW_OPEN_SILENT = 1
SW_OPEN_READONLY = 2


# ═══════════════════════════════════════════════════════════════════════════
#  YARDIMCI FONKSIYONLAR
# ═══════════════════════════════════════════════════════════════════════════

def _call(attr):
    """win32com bazen property bazen method dondurur; ikisini de calistirir."""
    return attr() if callable(attr) else attr


def _connect_to_solidworks():
    """Acik SolidWorks oturumuna baglanir; yoksa yeni baslatir.

    Once sw_reader modülünün cache'ini kontrol eder; Dispatch ile açılmış
    oturumlar COM ROT'a kayıt olmayabileceğinden bu cache olmadan ikinci
    bir SW penceresi açılır.
    """
    if win32com is None:
        raise RuntimeError("pywin32 kutuphanesi eksik. Kurulum: pip install pywin32")

    try:
        pythoncom.CoInitialize()
    except Exception:
        pass

    # 1. COM ROT uzerinden bul
    try:
        swApp = win32com.client.GetActiveObject("SldWorks.Application")
        print("Acik SolidWorks oturumu bulundu.")
        return swApp
    except Exception:
        pass

    # 2. sw_reader cache'inden al (Dispatch ile acilmis oturumlar ROT'a kayit olmaz)
    try:
        import sw_reader as _swr
        if _swr._sw_app_cache is not None:
            _ = _swr._sw_app_cache.Visible   # oturumun hala acik oldugunu dogrula
            print("Acik SolidWorks oturumu bulundu (cache).")
            return _swr._sw_app_cache
    except Exception:
        pass

    print("Acik SolidWorks yok, yeni oturum baslatiliyor...")
    swApp = win32com.client.Dispatch("SldWorks.Application")
    swApp.Visible = True
    # Cache'e kaydet ki bir sonraki cagri da faydalanabilsin
    try:
        import sw_reader as _swr
        _swr._sw_app_cache = swApp
    except Exception:
        pass
    return swApp


def _build_rename_map(parts: list[Part]) -> dict[str, str]:
    """Part listesinden 'normallestirilmis-kucuk-yol -> yeni dosya adi' haritasi kurar.

    Yalnizca erp_code'u dolu olan parcalar haritaya girer.
    Yeni ad = ERP kodu + orijinal uzanti  (orn. GEM-200-261304.SLDPRT)
    """
    rename_map: dict[str, str] = {}
    for part in parts:
        if not part.erp_code:
            continue
        ext = os.path.splitext(part.file_path)[1]   # .SLDPRT / .SLDASM
        new_name = f"{part.erp_code}{ext}"
        rename_map[os.path.normpath(part.file_path).lower()] = new_name
    return rename_map


def _default_target(assembly_path: str) -> str:
    """Hedef verilmezse: montajin bulundugu klasorde 'kodlanmis' alt klasoru."""
    return os.path.join(os.path.dirname(os.path.abspath(assembly_path)), "kodlanmis")


# ═══════════════════════════════════════════════════════════════════════════
#  DRY-RUN — SolidWorks COM gerektirmez
# ═══════════════════════════════════════════════════════════════════════════

def _dry_run_plan(
    abs_assembly: str,
    parts: list[Part],
    rename_map: dict[str, str],
    target_folder: str,
) -> dict:
    """COM kullanmadan, sadece Part listesinden dry-run plani olusturur."""
    planned = []

    # Ana montaj dosyasi (genelde yeniden adlandirilmaz)
    asm_key = os.path.normpath(abs_assembly).lower()
    asm_basename = os.path.basename(abs_assembly)
    if asm_key in rename_map:
        planned.append({"eski": asm_basename, "yeni": rename_map[asm_key], "degisti": True})
    else:
        planned.append({"eski": asm_basename, "yeni": asm_basename, "degisti": False})

    # Her parcayi goster
    seen = set()
    for part in parts:
        key = os.path.normpath(part.file_path).lower()
        if key in seen:
            continue
        seen.add(key)

        old_name = os.path.basename(part.file_path)
        if key in rename_map:
            planned.append({"eski": old_name, "yeni": rename_map[key], "degisti": True})
        else:
            planned.append({"eski": old_name, "yeni": old_name, "degisti": False})

    _print_plan(planned, target_folder, "dry_run=True")
    print("DRY-RUN: hicbir dosya olusturulmadi. Gercek calistirma icin "
          "dry_run=False ver.")

    return {"planned": planned, "executed": False, "target": target_folder}


def _print_plan(planned: list[dict], target_folder: str, mod: str) -> None:
    """Plani ekrana basar."""
    print("\n" + "=" * 70)
    print(f"KOPYALAMA VE YENIDEN ADLANDIRMA PLANI  ({mod})")
    print(f"Hedef klasor: {target_folder}")
    print("-" * 70)
    for item in planned:
        ok = "->" if item["degisti"] else "  (degismez)"
        print(f"  {item['eski']:32} {ok} {item['yeni']}")
    print("=" * 70)


# ═══════════════════════════════════════════════════════════════════════════
#  CANLI MOD — Python kopyalama + SolidWorks referans guncelleme
# ═══════════════════════════════════════════════════════════════════════════

def _copy_files(
    abs_assembly: str,
    parts: list[Part],
    rename_map: dict[str, str],
    target_folder: str,
) -> tuple[list[dict], dict[str, str], list[tuple[str, str, str]]]:
    """Asama 1: Dosyalari hedef klasore kopyalar, yeni adlarla kaydeder.

    Donus:
      planned   : her dosya icin {eski, yeni, degisti} listesi
      ref_updates: {eski_tam_yol -> yeni_tam_yol} (montaj referans guncelleme icin)
      drw_pairs : [(yeni_drw_yolu, eski_parca_yolu, yeni_parca_yolu)] (teknik resim ref.)
    """
    os.makedirs(target_folder, exist_ok=True)

    planned = []
    ref_updates: dict[str, str] = {}
    drw_pairs: list[tuple[str, str, str]] = []

    # Ana montaj dosyasi
    asm_key = os.path.normpath(abs_assembly).lower()
    asm_basename = os.path.basename(abs_assembly)
    asm_new_name = rename_map.get(asm_key, asm_basename)
    asm_new_path = os.path.join(target_folder, asm_new_name)

    shutil.copy2(abs_assembly, asm_new_path)
    planned.append({"eski": asm_basename, "yeni": asm_new_name,
                     "degisti": asm_key in rename_map})
    if asm_key in rename_map:
        ref_updates[abs_assembly] = asm_new_path

    # Parcalar ve alt montajlar
    seen = set()
    for part in parts:
        # Standart/ticari urunler (vida, rulman, servo...) SolidWorks tarafindan
        # kilitli olabilir; Errno 13 (Permission denied) hatasini onlemek icin
        # bunlari kopyalamiyoruz. Montaj orijinal konumdan okumaya devam eder.
        if part.status == STATUS_EXISTING:
            continue

        key = os.path.normpath(part.file_path).lower()
        if key in seen:
            continue
        seen.add(key)

        old_name = os.path.basename(part.file_path)
        new_name = rename_map.get(key, old_name)
        new_path = os.path.join(target_folder, new_name)

        if os.path.exists(part.file_path):
            shutil.copy2(part.file_path, new_path)
        else:
            print(f"  UYARI: dosya bulunamadi, atlaniyor: {part.file_path}")
            continue

        planned.append({"eski": old_name, "yeni": new_name,
                         "degisti": key in rename_map})
        # Kopyalanan her dosyayi ref_updates'e ekle: isim degismemis olsa dahi
        # hedef klasordeki lokal kopyaya referans yonlendirmesi yapilabilsin.
        ref_updates[os.path.normpath(part.file_path)] = new_path

        # Teknik resim (.SLDDRW) kopyalama — hata programi cokertmez
        try:
            drw_src = os.path.splitext(part.file_path)[0] + ".SLDDRW"
            if os.path.exists(drw_src):
                drw_new_name = (f"{part.erp_code}.SLDDRW"
                                if part.erp_code else os.path.basename(drw_src))
                drw_new_path = os.path.join(target_folder, drw_new_name)
                shutil.copy2(drw_src, drw_new_path)
                planned.append({"eski": os.path.basename(drw_src),
                                 "yeni": drw_new_name,
                                 "degisti": bool(part.erp_code)})
                drw_pairs.append((drw_new_path,
                                  os.path.normpath(part.file_path),
                                  new_path))
                print(f"  Teknik resim kopyalandi: {os.path.basename(drw_src)} -> {drw_new_name}")
        except Exception as e:
            print(f"  [UYARI] Teknik resim kopyalanamadi: {os.path.basename(part.file_path)}: {e}")

    return planned, ref_updates, drw_pairs


def _update_references(
    target_folder: str,
    ref_updates: dict[str, str],
) -> None:
    """Asama 2: Kopyalanan montaj dosyalarindaki referanslari gunceller.

    Parametreler:
      target_folder : kopyalanan dosyalarin bulundugu hedef klasor
      ref_updates   : {eski_mutlak_yol -> yeni_mutlak_yol} haritasi
                      (_copy_files tarafindan Part listesinden uretilir)

    Dosyalari acip/kapatmak yerine swApp.ReplaceReferencedDocument ile
    dogrudan uygulama nesnesi uzerinden guncelleme yapilir.
    Imza: swApp.ReplaceReferencedDocument(ReferencingFile, OldDocPath, NewDocPath)
    """
    swApp = _connect_to_solidworks()

    asm_files = [f for f in os.listdir(target_folder)
                 if f.lower().endswith(".sldasm")]

    if not asm_files:
        print("  Hedef klasorde montaj dosyasi yok, referans guncelleme atlaniyor.")
        return

    for asm_file in asm_files:
        asm_path = os.path.join(target_folder, asm_file)
        print(f"  Referanslar guncelleniyor: {asm_file}")

        updates_done = 0
        for old_path, new_path in ref_updates.items():
            if os.path.basename(old_path) == os.path.basename(new_path):
                continue
            try:
                result = swApp.ReplaceReferencedDocument(asm_path, old_path, new_path)
                if result:
                    updates_done += 1
            except Exception:
                pass

        print(f"    {updates_done} referans guncellendi.")


def _write_custom_properties(prop_pairs: list[tuple[str, str]]) -> None:
    """Kopyalanan .SLDPRT/.SLDASM dosyalarina ERP_Kodu Custom Property yazar.

    prop_pairs: [(yeni_parca_yolu, erp_code), ...]
    Orijinal dosyalara DOKUNMAZ; sadece target_folder'daki kopyalara yazar.
    Antet sablonu $PRPSHEET:"ERP_Kodu" iceriyorsa teknik resimde otomatik dolar.
    """
    if not prop_pairs:
        return

    try:
        swApp = _connect_to_solidworks()
    except Exception as e:
        print(f"  [UYARI] Custom Property yazma atlandi (SW baglantisi hatasi): {e}")
        return

    ok_count = 0
    for new_path, erp_code in prop_pairs:
        if not os.path.exists(new_path):
            print(f"  [UYARI] Dosya bulunamadi (Custom Property): {os.path.basename(new_path)}")
            continue
        ext = os.path.splitext(new_path)[1].lower()
        doc_type = SW_DOC_PART if ext == ".sldprt" else SW_DOC_ASSEMBLY
        doc = None
        try:
            doc = swApp.OpenDoc(new_path, doc_type)
            if not doc:
                print(f"  [UYARI] Acilamadi (Custom Property): {os.path.basename(new_path)}")
                continue

            cpm = doc.Extension.CustomPropertyManager("")
            # Add3(Name, Type, Value, OverwriteExisting=1); Type 30 = swCustomInfoText
            try:
                cpm.Add3("ERP_Kodu", 30, erp_code, 1)
            except Exception:
                # Eski API fallback: once sil, sonra ekle
                try:
                    cpm.Delete("ERP_Kodu")
                except Exception:
                    pass
                cpm.Add("ERP_Kodu", 30, erp_code)

            try:
                doc.Save3(1, 0, 0)   # 1 = swSaveAsCurrentVersion
            except Exception:
                doc.Save()

            ok_count += 1
            print(f"  ERP_Kodu yazildi: {os.path.basename(new_path)} -> {erp_code}")
        except Exception as e:
            print(f"  [UYARI] Custom Property hatasi ({os.path.basename(new_path)}): {e}")
        finally:
            if doc:
                try:
                    swApp.CloseDoc(_call(doc.GetTitle))
                except Exception:
                    pass

    print(f"    {ok_count}/{len(prop_pairs)} dosyaya ERP_Kodu yazildi.")


def _load_sw_gen():
    """SW tip kutuphanesi erken baglama modulunu yukler (makepy ile uretilmis).

    Bulunamazsa None dondurur; cagiran kod fallback uygular.
    Arama sirasi: PyInstaller _MEIPASS -> win32com.gen_py -> cok Python yolu.
    """
    import importlib.util, glob as _glob, sys as _sys

    def _scan_dir(d):
        if not os.path.isdir(d):
            return None
        for fname in os.listdir(d):
            if fname.startswith("83A33D31") and fname.endswith(".py"):
                spec = importlib.util.spec_from_file_location(
                    "sldworks_gen", os.path.join(d, fname))
                mod  = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
        return None

    # 1) PyInstaller one-file temp dir (exe icinde bundled ise)
    meipass = getattr(_sys, "_MEIPASS", None)
    if meipass:
        result = _scan_dir(os.path.join(meipass, "win32com", "gen_py"))
        if result:
            return result

    # 2) Aktif Python ortamindaki win32com.gen_py (normal Python kurulumu)
    try:
        import win32com
        result = _scan_dir(os.path.join(os.path.dirname(win32com.__file__), "gen_py"))
        if result:
            return result
    except ImportError:
        pass

    # 3) LOCALAPPDATA altindaki tum Python kurulumlarini tara
    localappdata = os.environ.get("LOCALAPPDATA", "")
    for pattern in (
        os.path.join(localappdata, "Python", "*", "Lib", "site-packages", "win32com", "gen_py"),
        os.path.join(localappdata, "Programs", "Python", "*", "Lib", "site-packages", "win32com", "gen_py"),
    ):
        for d in _glob.glob(pattern):
            result = _scan_dir(d)
            if result:
                return result

    # 4) PATH uzerindeki site-packages
    for p in _sys.path:
        if "site-packages" in p:
            result = _scan_dir(os.path.join(p, "win32com", "gen_py"))
            if result:
                return result

    return None


def _wrap_com(obj, cls):
    """COM nesnesini erken baglamali sinifla sarmalar."""
    if obj is None:
        return None
    oleobj = getattr(obj, "_oleobj_", obj)
    return cls(oleobj)


def _add_antet_notes(drw_files: list[str], pos_x: float = 0.195, pos_y: float = 0.012) -> None:
    """Kopyalanan .SLDDRW dosyalarinin antetine $PRPSHEET:"ERP_Kodu" notu ekler.

    SW tip kutuphanesi erken baglamasi gerektirir (IDrawingDoc, IAnnotation).
    pos_x / pos_y: A4 yatay antet konum tahmini (metre). Kullanici tasiyabilir.
    Hata olusursa program calismaya devam eder.
    """
    sw_gen = _load_sw_gen()
    if sw_gen is None:
        print("  [UYARI] Antet notu: SW tip kutuphanesi bulunamadi — atlaniyor.")
        print("          Cozum: python -m win32com.client.makepy sldworks.tlb")
        return

    try:
        swApp = _connect_to_solidworks()
    except Exception as e:
        print(f"  [UYARI] Antet notu: SW baglantisi hatasi: {e}")
        return

    ok = 0
    for drw_path in drw_files:
        fname = os.path.basename(drw_path)
        doc   = None
        try:
            doc = swApp.OpenDoc(drw_path, 3)
            if not doc:
                print(f"    [UYARI] {fname}: acilamadi")
                continue
            err_act = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            act = swApp.ActivateDoc2(fname, False, err_act)
            if act:
                doc = act

            drw      = _wrap_com(doc, sw_gen.IDrawingDoc)
            drw.EditTemplate()

            note_raw = doc.InsertNote('$PRPSHEET:"ERP_Kodu"')
            if note_raw is None:
                drw.EditSheet()
                print(f"    [UYARI] {fname}: not olusturulamadi")
                continue

            note_e = _wrap_com(note_raw, sw_gen.INote)
            ann_r  = note_e.GetAnnotation()
            if ann_r:
                _wrap_com(ann_r, sw_gen.IAnnotation).SetPosition2(pos_x, pos_y, 0.0)

            drw.EditSheet()
            try:
                doc.Save3(1, 0, 0)
            except Exception:
                doc.Save()

            ok += 1
            print(f"    ERP_Kodu notu eklendi: {fname}")
        except Exception as e:
            print(f"    [UYARI] {fname}: {e}")
        finally:
            if doc:
                try:
                    swApp.CloseDoc(_call(doc.GetTitle))
                except Exception:
                    pass

    print(f"    {ok}/{len(drw_files)} teknik resime antet notu eklendi.")


def _export_drw_to_pdf(drw_files: list[str], target_folder: str) -> None:
    """Her SLDDRW dosyasinin her sheet'ini ayri PDF olarak disari aktarir.

    Adlandirma: GEM-200-123134.SLDDRW -> GEM-200-123134-1.pdf, GEM-200-123134-2.pdf ...
    Antet notu eklendikten (Asama 5) sonra cagrilmali; ERP_Kodu PDF'e yansisin.
    Hata olusursa program calismaya devam eder.
    """
    if not drw_files:
        return

    try:
        swApp = _connect_to_solidworks()
    except Exception as e:
        print(f"  [UYARI] PDF export: SW baglantisi hatasi: {e}")
        return

    ok_count = 0
    for drw_path in drw_files:
        fname = os.path.basename(drw_path)
        base_name = os.path.splitext(fname)[0]
        doc = None
        try:
            doc = swApp.OpenDoc(drw_path, 3)  # 3 = swDocDRAWING
            if not doc:
                print(f"    [UYARI] {fname}: acilamadi, PDF atlaniyor")
                continue

            err_act = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            act = swApp.ActivateDoc2(fname, False, err_act)
            if act:
                doc = act

            # GetSheetNames SW 2019 late-binding'de property (callable degil)
            sheet_names = doc.GetSheetNames
            if not sheet_names:
                sheet_names = ("Sheet1",)

            for i, sheet_name in enumerate(sheet_names, start=1):
                pdf_name = f"{base_name}-{i}.pdf"
                pdf_path = os.path.join(target_folder, pdf_name)
                try:
                    doc.ActivateSheet(sheet_name)

                    # IExportPdfData.SetSheets: 2 parametre (nOption, [sheetNames])
                    pdf_data = swApp.GetExportFileData(1)
                    pdf_data.SetSheets(1, [sheet_name])

                    err_r  = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                    warn_r = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                    # Extension.SaveAs (SaveAs3 degil) — VARIANT BYREF ile calisir
                    doc.Extension.SaveAs(pdf_path, 0, 0, pdf_data, err_r, warn_r)

                    if os.path.exists(pdf_path):
                        print(f"    PDF: {pdf_name}")
                        ok_count += 1
                    else:
                        raise RuntimeError("PDF dosyasi olusturulamadi")

                except Exception:
                    # Fallback: tum sheetleri tek PDF olarak kaydet
                    try:
                        doc.ActivateSheet(sheet_name)
                        doc.SaveAs3(pdf_path, 0, 0)
                        if os.path.exists(pdf_path):
                            print(f"    PDF (fallback): {pdf_name}")
                            ok_count += 1
                        else:
                            print(f"    [UYARI] {fname} sheet {i}: PDF olusturulamadi")
                    except Exception as e2:
                        print(f"    [UYARI] {fname} sheet {i}: PDF hatasi: {e2}")

        except Exception as e:
            print(f"    [UYARI] {fname}: {e}")
        finally:
            if doc:
                try:
                    swApp.CloseDoc(_call(doc.GetTitle))
                except Exception:
                    pass

    print(f"    {ok_count} PDF dosyasi olusturuldu.")


def _update_drw_references(drw_pairs: list[tuple[str, str, str]]) -> None:
    """SLDDRW dosyalarinin icindeki parca referanslarini yeni ERP kodlu yollara yonlendirir.

    drw_pairs: [(yeni_drw_yolu, eski_parca_yolu, yeni_parca_yolu)]
    Her tupledaki yeni_drw_yolu icindeki eski_parca_yolu referansi yeni_parca_yoluna degisir.
    Hata olusursa program calismaya devam eder (try-except).
    """
    if not drw_pairs:
        return
    try:
        swApp = _connect_to_solidworks()
    except Exception as e:
        print(f"  [UYARI] Teknik resim referansi guncellenemedi (SW baglantisi hatasi): {e}")
        return

    for drw_path, old_part_path, new_part_path in drw_pairs:
        try:
            result = swApp.ReplaceReferencedDocument(drw_path, old_part_path, new_part_path)
            if result:
                print(f"    Teknik resim referansi guncellendi: {os.path.basename(drw_path)}")
            else:
                print(f"  [UYARI] Teknik resim referansi guncellenemedi: {os.path.basename(drw_path)}")
        except Exception as e:
            print(f"  [UYARI] Teknik resim referansi guncellenemedi: {os.path.basename(drw_path)}: {e}")


# ═══════════════════════════════════════════════════════════════════════════
#  ANA FONKSIYON
# ═══════════════════════════════════════════════════════════════════════════

def pack_and_go_rename(
    assembly_path: str,
    parts: list[Part],
    target_folder: str | None = None,
    dry_run: bool = True,
) -> dict:
    """Montaji, parcalari ERP koduyla yeniden adlandirarak hedef klasore kopyalar.

    YONTEM: Python shutil ile kopyala + SolidWorks API ile referans guncelle.
    (Pack and Go COM sorunu nedeniyle alternatif yontem kullaniliyor.)

    assembly_path : ana montaj .sldasm yolu
    parts         : erp_code alanlari doldurulmus Part listesi
    target_folder : kodlanmis kopyanin olusturulacagi klasor.
                    VERILMEZSE montajin yanindaki 'kodlanmis' alt klasoru kullanilir.
    dry_run       : True ise sadece plan basilir, dosya OLUSTURULMAZ.

    Donus: {'planned': [...], 'executed': bool, 'target': ...}
    """
    rename_map = _build_rename_map(parts)
    if not rename_map:
        raise ValueError("Hicbir parcaya ERP kodu atanmamis; once assign_codes calistir.")

    abs_assembly = os.path.abspath(assembly_path)
    if not os.path.exists(abs_assembly):
        raise FileNotFoundError(f"Montaj bulunamadi: {abs_assembly}")

    if target_folder is None:
        target_folder = _default_target(abs_assembly)

    # ─── DRY-RUN: COM yok, sadece plan ────────────────────────────────────
    if dry_run:
        return _dry_run_plan(abs_assembly, parts, rename_map, target_folder)

    # ─── CANLI MOD ────────────────────────────────────────────────────────

    # Asama 1: Python ile kopyala ve yeniden adlandir
    print("\n  Asama 1/6: Dosyalar kopyalaniyor...")
    planned, ref_updates, drw_pairs = _copy_files(abs_assembly, parts, rename_map, target_folder)

    _print_plan(planned, target_folder, "CANLI MOD")

    # Asama 2: SolidWorks ile montaj referanslarini guncelle
    print("\n  Asama 2/6: Montaj referanslari guncelleniyor...")
    try:
        _update_references(target_folder, ref_updates)
    except Exception as exc:
        print(f"\n  UYARI: Referans guncelleme basarisiz: {exc}")
        print("  Dosyalar kopyalandi ama referanslar eski isimleri gosterebilir.")
        print("  SolidWorks'te kopyalanmis montaji actiginizda 'Dosya Bul' ile "
              "duzeltilebilir.")

    # Asama 3: Teknik resim (.SLDDRW) referanslarini guncelle
    if drw_pairs:
        print(f"\n  Asama 3/6: Teknik resim referanslari guncelleniyor ({len(drw_pairs)} dosya)...")
        try:
            _update_drw_references(drw_pairs)
        except Exception as exc:
            print(f"\n  [UYARI] Teknik resim referansi guncellenemedi: {exc}")

    # Asama 4: Custom Property yaz — ERP_Kodu -> $PRPSHEET:"ERP_Kodu" ile antet dolar
    seen_paths: set[str] = set()
    prop_pairs: list[tuple[str, str]] = []
    from models import STATUS_EXISTING as _SE
    for p in parts:
        if p.erp_code and p.status != _SE:
            ext = os.path.splitext(p.file_path)[1]
            new_path = os.path.join(target_folder, f"{p.erp_code}{ext}")
            if new_path not in seen_paths:
                seen_paths.add(new_path)
                prop_pairs.append((new_path, p.erp_code))
    if prop_pairs:
        print(f"\n  Asama 4/6: Custom Property yaziliyor ({len(prop_pairs)} dosya)...")
        try:
            _write_custom_properties(prop_pairs)
        except Exception as exc:
            print(f"\n  [UYARI] Custom Property yazma basarisiz: {exc}")

    # Asama 5: Teknik resim antetine $PRPSHEET:"ERP_Kodu" notu ekle
    drw_files = [
        os.path.join(target_folder, f)
        for f in os.listdir(target_folder)
        if f.upper().endswith(".SLDDRW") and not f.startswith("~$")
    ]
    if drw_files:
        print(f"\n  Asama 5/6: Antet notu ekleniyor ({len(drw_files)} teknik resim)...")
        try:
            _add_antet_notes(drw_files)
        except Exception as exc:
            print(f"\n  [UYARI] Antet notu eklenemedi: {exc}")

    # Asama 6: Her SLDDRW sheet'ini ayri PDF olarak disa aktar
    if drw_files:
        print(f"\n  Asama 6/6: PDF olusturuluyor ({len(drw_files)} teknik resim)...")
        try:
            _export_drw_to_pdf(drw_files, target_folder)
        except Exception as exc:
            print(f"\n  [UYARI] PDF export basarisiz: {exc}")

    print(f"\nTAMAMLANDI. Kodlanmis dosyalar: {target_folder}")
    return {"planned": planned, "executed": True, "target": target_folder}


# --- Tek basina test bloku -------------------------------------------------
if __name__ == "__main__":
    print("renamer.py tek basina calistirildi.")
    print("Bu modul main.py icinden, erp_code'lari dolu Part listesiyle cagrilmali.")
    print("Hizli deneme icin asagidaki ornegi duzenleyebilirsin:\n")

    # ORNEK (yollari kendine gore degistir, sonra yorum satirini kaldir):
    # from sw_reader import read_assembly_tree
    # from classifier import classify_parts
    # from excel_handler import assign_codes
    #
    # asm = r"C:\Users\Savas\Desktop\Solidworks Denemeleri\Montaj1.SLDASM"
    # parts = assign_codes(classify_parts(read_assembly_tree(asm)), "konfig.xlsx")
    # pack_and_go_rename(asm, parts, r"C:\sw-erp-agent\kodlanmis_test",
    #                    dry_run=True)   # ILK DENEMEDE MUTLAKA True
