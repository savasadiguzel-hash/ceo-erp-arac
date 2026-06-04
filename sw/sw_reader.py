"""sw_reader.py — ASAMA 1: SolidWorks montaj agacini okur.

Onemli fark: bu modul ekrana DOKMEZ, Part nesnelerinin listesini DONDURUR.
Boylece Asama 2 (classifier) dogrudan bu ciktiyi parametre olarak alabilir.

Tek basina test etmek icin:   python sw_reader.py "C:\\yol\\Montaj1.SLDASM"
main.py icinden kullanmak icin: from sw_reader import read_assembly_tree
"""
from __future__ import annotations

import os
import sys

try:
    import win32com.client
    import pythoncom
except ImportError:
    print("HATA: 'pywin32' kutuphanesi eksik. Kurulum: pip install pywin32")
    sys.exit(1)

from sw.models import Part

# --- SolidWorks sabitleri --------------------------------------------------
SW_DOC_ASSEMBLY = 2
SW_OPEN_SILENT = 1
SW_OPEN_READONLY = 2
SW_COMPONENT_SUPPRESSED = 0   # GetSuppression: 0 = suppressed


# --- Yardimcilar -----------------------------------------------------------
_sw_app_cache = None   # read_assembly_tree sonrasi diger modullerin reuse edebilmesi icin


def _call(attr):
    """win32com bazen property bazen method dondurur; ikisini de guvenle calistirir."""
    return attr() if callable(attr) else attr


def _connect_to_solidworks():
    """Acik SolidWorks oturumuna baglanir; yoksa yeni bir oturum baslatir.

    Dispatch ile baslatilanlar COM ROT'a kayit olmayabilir; bu nedenle
    swApp nesnesi _sw_app_cache'e kaydedilir. Cagiran kod once bu cache'i
    kontrol etmeli, boylece ikinci bir SW oturumu acilmaz.
    """
    global _sw_app_cache
    try:
        pythoncom.CoInitialize()
    except Exception:
        pass
    try:
        swApp = win32com.client.GetActiveObject("SldWorks.Application")
        print("Acik SolidWorks oturumu bulundu.")
    except Exception:
        if _sw_app_cache is not None:
            # Dispatch ile acilmis oturum ROT'a kayit olmayabilir; cache'i dene
            try:
                _ = _sw_app_cache.Visible   # yasadigini dogrula
                print("Acik SolidWorks oturumu bulundu (cache).")
                return _sw_app_cache
            except Exception:
                _sw_app_cache = None
        print("Acik SolidWorks yok, yeni oturum baslatiliyor...")
        swApp = win32com.client.Dispatch("SldWorks.Application")
        swApp.Visible = True
    _sw_app_cache = swApp
    return swApp


def _open_assembly(swApp, file_path: str):
    """Verilen montaj dosyasini salt-okunur ve sessiz acar, model nesnesini dondurur."""
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Dosya bulunamadi: {abs_path}")

    try:
        model = swApp.OpenDoc(abs_path, SW_DOC_ASSEMBLY)
    except Exception:
        err = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warn = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        model = swApp.OpenDoc6(
            abs_path, SW_DOC_ASSEMBLY,
            SW_OPEN_SILENT | SW_OPEN_READONLY, "", err, warn,
        )

    if not model:
        raise RuntimeError(f"Montaj acilamadi: {abs_path}")
    return model


def _get_material(component) -> str | None:
    """Bir bilesenin malzemesini okumayi dener; basarisiz olursa None dondurur.

    Once GetMaterialPropertyName2 denenir. Bos donerse CustomPropertyManager
    uzerinden "Malzeme", "Material", "MALZEME", "MATERIAL" ozellikleri taranir.
    """
    try:
        doc = component.GetModelDoc2()
        if not doc:
            return None

        # --- Yontem 1: GetMaterialPropertyName2 ---
        result = None
        for args in (("",), ("", "")):
            try:
                result = doc.GetMaterialPropertyName2(*args)
                break
            except Exception:
                continue
        if isinstance(result, (list, tuple)):
            result = result[0] if result else None
        material = (result or "").strip() or None
        if material:
            return material

        # --- Yontem 2: Custom Properties geri donusu ---
        try:
            mgr = doc.Extension.CustomPropertyManager("")
            if mgr:
                for key in ("Malzeme", "Material", "MALZEME", "MATERIAL"):
                    # Get2: SW 2013+ — degeri dogrudan dondurur
                    try:
                        val = mgr.Get2(key)
                        if val and str(val).strip():
                            return str(val).strip()
                    except Exception:
                        pass
                    # Get: eski API, yedek olarak dene
                    try:
                        val = mgr.Get(key)
                        if val and str(val).strip():
                            return str(val).strip()
                    except Exception:
                        pass
        except Exception:
            pass

        return None
    except Exception:
        return None


def _is_imported_part(doc) -> bool:
    """Parcanin ozellik agacinda ice aktarilmis (Imported/Alinmis) govde var mi?

    Bir STEP/IGES dosyasi SolidWorks'te acilip .sldprt olarak kaydedildiginde
    FeatureManager'da 'Alinmis1' / 'Imported1' adli bir ozellik olusur; bunun
    TIP ADI (GetTypeName2) SW 2019'da 'BaseBody'dir. Boyle parcalar gercek
    modellenmis degildir; STEP gibi muamele gorur (kod verilmez).

    NOT (SW 2019 late-binding bulgusu, tani_imported.py ile tespit edildi):
      - doc.FirstFeature()/GetNextFeature() 'Uye bulunamadi' verir -> KULLANILAMAZ.
      - Calisan yontem: doc.FeatureManager.GetFeatures(False) -> ozellik dizisi.
      - Imported govde: GetTypeName2 == 'BaseBody' (dil bagimsiz). Ayrica ozellik
        adi 'Alinmis'/'Imported' ile baslar (dil bagimli yedek).
    """
    try:
        feats = doc.FeatureManager.GetFeatures(False)
    except Exception:
        return False
    if not feats:
        return False

    for f in feats:
        # 1) Tip adi — dil bagimsiz, en guvenilir ('BaseBody' = ice aktarilmis govde)
        for getter in ("GetTypeName2", "GetTypeName"):
            try:
                tname = _call(getattr(f, getter))
            except Exception:
                tname = None
            if tname and str(tname).strip().lower() == "basebody":
                return True
        # 2) Ozellik adi — yedek (dil bagimli: Imported / Alinmis)
        try:
            nm = _call(f.Name)
        except Exception:
            nm = None
        if nm:
            low = str(nm).strip().lower()
            if low.startswith("imported") or low.startswith("alınmış") or low.startswith("alinmis"):
                return True
    return False


# --- Ana fonksiyon ---------------------------------------------------------
def read_assembly_tree(file_path: str | None = None, progress_cb=None,
                       only_paths: "set[str] | None" = None) -> list[Part]:
    """Montaji okur, icindeki benzersiz parca/alt-montajlari Part listesi olarak dondurur.

    file_path verilmezse SolidWorks'te o an acik olan aktif belge okunur.
    Ayni dosya birden cok kez geciyorsa tek Part olarak tutulur, instance_count artar.

    progress_cb: opsiyonel. Her BENZERSIZ parca/alt-montaj okundukça
        progress_cb(islenen: int, toplam: int, ad: str) seklinde cagrilir
        (GUI'de 'Parca X/Y okunuyor' gostermek icin). Hata sessizce yutulur.
    """
    swApp = _connect_to_solidworks()

    if file_path:
        model = _open_assembly(swApp, file_path)
    else:
        model = swApp.ActiveDoc
        if not model:
            raise RuntimeError("Acik bir belge yok ve dosya yolu da verilmedi.")

    if _call(model.GetType) != SW_DOC_ASSEMBLY:
        raise ValueError("Belge bir montaj (assembly) degil. Montaj dosyasi gerekli.")

    config = model.ConfigurationManager.ActiveConfiguration
    config_name = _call(config.Name) if config else None

    root_comp = config.GetRootComponent3(True)
    if not root_comp:
        raise RuntimeError("Kok montaj bileseni alinamadi.")

    parts: dict[str, Part] = {}   # benzersizlik icin anahtar = dosya yolu

    # --- Ilerleme icin: toplam benzersiz bilesen sayisini hizlica say (parca ACMADAN) ---
    _total = {"n": 0}
    _done = {"n": 0}
    if progress_cb:
        try:
            _seen: set[str] = set()

            def _count(comp):
                ch = _call(comp.GetChildren)
                if not ch:
                    return
                for c in ch:
                    p = (_call(c.GetPathName) or "").strip()
                    if not p or p in _seen:
                        continue
                    _seen.add(p)
                    if p.lower().endswith(".sldasm"):
                        _count(c)

            _count(root_comp)
            _total["n"] = len(_seen)
        except Exception:
            _total["n"] = 0

    def traverse(component):
        children = _call(component.GetChildren)
        if not children:
            return
        for child in children:
            path = (_call(child.GetPathName) or "").strip()
            if not path:
                continue

            ext = os.path.splitext(path)[1].lower()
            is_asm = ext == ".sldasm"

            if path in parts:
                parts[path].instance_count += 1
            else:
                # --- Bounding box + Geometrik Parmak Izi (sadece parcalar icin) ---
                bb_x = bb_y = bb_z = 0.0
                base_name = os.path.splitext(os.path.basename(path))[0]
                geo_sig = None   # alt montajlar icin None; parcalar asagida doldurulur
                is_imported = False   # ice aktarilmis (Imported/Alinmis) parca mi?
                material = None
                # only_paths verilmisse SADECE bu yollardaki parcalar TAM okunur (doc acilir:
                # malzeme + atalet + imported). Digerleri hafif gecer -> HIZ. only_paths=set()
                # => hicbiri acilmaz (montaj seciminde aninda liste icin). None => hepsi (eski).
                do_full = (not is_asm) and (only_paths is None or path in only_paths)
                if do_full:
                    material = _get_material(child)
                    _opened = False   # bu dongu adiminda biz mi actik?
                    doc    = None

                    # 1. Adim: bilesenden direkt doc al (zaten bellekteyse hizli yol)
                    try:
                        doc = child.GetModelDoc2()
                    except Exception:
                        doc = None   # Lightweight veya API hatasi -> 2. adima gec

                    # 2. Adim: hala doc=None ise parçayi dogrudan ac (Lightweight cozumu)
                    if not doc:
                        try:
                            doc    = swApp.OpenDoc(path, 1)   # 1 = swDocPART
                            _opened = bool(doc)
                        except Exception:
                            doc = None

                    # Bounding box — Yontem 1: IComponent2.GetBox(True)
                    # True = Lightweight bileseni resolve et + BB hesapla.
                    # GetBox(False) yeni oturumda render cache olmadigi icin 0 donuyor.
                    try:
                        cbox = child.GetBox(True)
                        if cbox and len(cbox) >= 6:
                            bb_x = abs(cbox[3] - cbox[0]) * 1000
                            bb_y = abs(cbox[4] - cbox[1]) * 1000
                            bb_z = abs(cbox[5] - cbox[2]) * 1000
                    except Exception:
                        pass

                    # Bounding box — Yontem 2: doc ac + ActivateDoc2 + GetBoundingBox
                    # ActivateDoc2 SW'nin geometriyi hesaplamasini tetikliyor.
                    if bb_x == 0 and bb_y == 0 and bb_z == 0 and doc:
                        try:
                            err_act = win32com.client.VARIANT(
                                pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                            activated = swApp.ActivateDoc2(
                                os.path.basename(path), False, err_act)
                            active_doc = activated if activated else doc
                            box = active_doc.Extension.GetBoundingBox(0)
                            if box and len(box) >= 6:
                                bb_x = abs(box[3] - box[0]) * 1000
                                bb_y = abs(box[4] - box[1]) * 1000
                                bb_z = abs(box[5] - box[2]) * 1000
                        except Exception:
                            pass

                    if doc:
                        # GetMassProperties: props[6]=Ixx, [7]=Iyy, [8]=Izz (kg*m²)
                        # Not: Extension.CreateMassProperty() SW 2019 late-binding'de calismaz.
                        # GetBoundingBox/GetBox vtable-only oldugu icin bb_x/bb_y/bb_z yerine
                        # bu atalet momentleri classifier'a geometrik ipucu olarak aktarilir.
                        try:
                            props = doc.GetMassProperties
                            if props and len(props) >= 8:
                                v0 = abs(float(props[6]))
                                v1 = abs(float(props[7]))
                                v2 = abs(float(props[8])) if len(props) >= 9 else 0.0
                                if v0 > 0 or v1 > 0:
                                    geo_sig = f"{v0:.8e}_{v1:.8e}"
                                    bb_x, bb_y, bb_z = v0, v1, v2
                                else:
                                    geo_sig = f"HATA_OKUNAMADI_{base_name}"
                            else:
                                geo_sig = f"HATA_OKUNAMADI_{base_name}"
                        except Exception:
                            geo_sig = f"HATA_OKUNAMADI_{base_name}"
                    else:
                        geo_sig = f"HATA_OKUNAMADI_{base_name}"

                    # --- ICE AKTARILMIS (Imported/Alinmis) ozelligi tespiti ---
                    if doc:
                        try:
                            is_imported = _is_imported_part(doc)
                            if is_imported:
                                print(f"      -> Alinmis (imported) parca tespit edildi: "
                                      f"{base_name} — kod verilmeyecek")
                        except Exception:
                            is_imported = False

                    # Bizim actigimiz dokumanı kapat (assembly'nin bilesenleri degil)
                    if _opened and doc:
                        try:
                            swApp.CloseDoc(_call(doc.GetTitle))
                        except Exception:
                            pass

                parts[path] = Part(
                    file_path=path,
                    original_name=base_name,
                    is_assembly=is_asm,
                    config_name=config_name,
                    suppressed=(_call(child.GetSuppression) == SW_COMPONENT_SUPPRESSED),
                    material=material,
                    bb_x=bb_x,
                    bb_y=bb_y,
                    bb_z=bb_z,
                    geometric_signature=geo_sig,
                    is_imported=is_imported,
                )

                # --- Ilerleme bildirimi (her benzersiz bilesen okundukca) ---
                if progress_cb:
                    _done["n"] += 1
                    try:
                        progress_cb(_done["n"], _total["n"], base_name)
                    except Exception:
                        pass

            if is_asm:        # alt montajlarin icine de in
                traverse(child)

    traverse(root_comp)
    return list(parts.values())


def export_part_image(swApp, file_path: str, output_folder: str) -> str | None:
    """Kararsiz parcayi arka planda sessizce acar, izometrik yapip ekran goruntusunu kaydeder."""
    import os
    try:
        os.makedirs(output_folder, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        target_img = os.path.join(output_folder, f"{base_name}.png")

        # 1 = swDocPART
        mod_doc = swApp.OpenDoc(file_path, 1)
        if not mod_doc:
            print(f"      [Hata]: {os.path.basename(file_path)} API tarafindan acilamadi.")
            return None

        # OpenDoc aktif gorunumu degistirmiyor; ActivateDoc2 ile parçayi one getir.
        # Aksi halde SaveAs montaj gorunumunu yakaliyor (tum parcalar gorunur).
        err_act = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        activated = swApp.ActivateDoc2(os.path.basename(file_path), False, err_act)
        if activated:
            mod_doc = activated

        # Gorunumu temizlemek icin teknik duzlemleri/sketcleri gizle (Command ID: 2097 = View Hide All Types)
        try:
            swApp.ExecuteCommand(2097, "")
        except Exception:
            pass

        # Ekrana sigdir
        mod_doc.ViewZoomtofit2()

        # Fotograf olarak kaydet — Extension.SaveAs SW 2019 SP4 dynamic dispatch ile
        # calismiyor (Tur uyusmazligi). doc.SaveAs(filename) en kararlı yontem.
        success = mod_doc.SaveAs(target_img)

        # Belgeyi hafizadan kapat
        title = _call(mod_doc.GetTitle)
        swApp.CloseDoc(title)

        if success:
            return target_img
    except Exception as e:
        print(f"      [Gorsel Oluşturma Hatasi]: {e}")
    return None


def export_part_additional_views(swApp, file_path: str, output_folder: str) -> list[str]:
    """Dimetrik (id=8) ve trimetrik (id=9) standart gorunumleri yakalar.

    Donus: basariyla kaydedilen goruntu yollarinin listesi (bos olabilir).
    Guven skoru dusuk cikan parcalar icin export_part_image'dan sonra cagrilir.
    """
    import os
    results: list[str] = []
    try:
        os.makedirs(output_folder, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(file_path))[0]

        mod_doc = swApp.OpenDoc(file_path, 1)
        if not mod_doc:
            print(f"      [Ek Goruntu]: {os.path.basename(file_path)} acilamadi.")
            return results

        err_act = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        activated = swApp.ActivateDoc2(os.path.basename(file_path), False, err_act)
        if activated:
            mod_doc = activated

        try:
            swApp.ExecuteCommand(2097, "")
        except Exception:
            pass

        for view_id, suffix in ((8, "dimetrik"), (9, "trimetrik")):
            target_img = os.path.join(output_folder, f"{base_name}_{suffix}.png")
            try:
                active_view = mod_doc.ActiveView
                if active_view:
                    active_view.ShowStandardView(view_id)
                mod_doc.ViewZoomtofit2()
                if mod_doc.SaveAs(target_img):
                    results.append(target_img)
            except Exception as e:
                print(f"      [Ek Goruntu - {suffix}]: {e}")

        title = _call(mod_doc.GetTitle)
        swApp.CloseDoc(title)

    except Exception as e:
        print(f"      [Ek Goruntu Genel Hata]: {e}")
    return results


def prescan_assembly(file_path: str) -> list[dict]:
    """Hizli on tarama: fotograf cekmeden montaj agacindaki benzersiz
    parca ve alt-montajlarin listesini dondurur.

    Donus: [{"file_path": str, "original_name": str, "is_assembly": bool}, ...]
    Orijinal isme gore sirali.
    """
    swApp = _connect_to_solidworks()
    model = _open_assembly(swApp, file_path)

    if _call(model.GetType) != SW_DOC_ASSEMBLY:
        raise ValueError("Belge bir montaj (assembly) degil.")

    config    = model.ConfigurationManager.ActiveConfiguration
    root_comp = config.GetRootComponent3(True)
    if not root_comp:
        raise RuntimeError("Kok montaj bileseni alinamadi.")

    parts: dict[str, dict] = {}

    def traverse(component):
        children = _call(component.GetChildren)
        if not children:
            return
        for child in children:
            path = (_call(child.GetPathName) or "").strip()
            if not path:
                continue
            ext    = os.path.splitext(path)[1].lower()
            is_asm = ext == ".sldasm"
            if path not in parts:
                parts[path] = {
                    "file_path":     path,
                    "original_name": os.path.splitext(os.path.basename(path))[0],
                    "is_assembly":   is_asm,
                }
            if is_asm:
                traverse(child)

    traverse(root_comp)
    return sorted(parts.values(), key=lambda x: x["original_name"].lower())


# --- Tek basina test bloku -------------------------------------------------
# main.py bu modulu import ettiginde asagidaki blok CALISMAZ.
# Sadece "python sw_reader.py ..." denildiginde devreye girer.
if __name__ == "__main__":
    target = (
        sys.argv[1] if len(sys.argv) > 1
        else r"C:\Users\Savas\Desktop\Solidworks Denemeleri\Montaj1.SLDASM"
    )

    print(f"Okunuyor: {target}\n")
    try:
        found = read_assembly_tree(target)
    except Exception as exc:
        print(f"HATA: {exc}")
        sys.exit(1)

    print("=" * 70)
    print(f"Toplam {len(found)} benzersiz dosya bulundu:\n")
    for p in found:
        tip = "ALT MONTAJ" if p.is_assembly else "PARCA"
        mat = f" | malzeme: {p.material}" if p.material else ""
        supp = " | (suppressed)" if p.suppressed else ""
        bb = f" | bb: {p.bb_x:.1f}x{p.bb_y:.1f}x{p.bb_z:.1f} mm" if not p.is_assembly else ""
        print(f"  [{tip:10}] {p.original_name}  x{p.instance_count}{mat}{bb}{supp}")
    print("=" * 70)