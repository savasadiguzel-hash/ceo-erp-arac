"""pipeline.py — SW-ERP-Agent ana akis motoru (GUI'den bagimsiz).

Tab_SW bu modulu cagirarak parca okuma, siniflandirma, kod atama,
kopyalama adimlarini yurutur.  Tum print() ciktilarini log_fn
callback'ine yonlendirir; dialog isteklerini queue'lara koyar.
"""
from __future__ import annotations

import os
import queue
import sys
import time
from typing import Any, Callable

import sw.sw_reader as _sw_reader_mod
from sw.sw_reader import (read_assembly_tree, export_part_image,
                          export_part_additional_views)
from sw.classifier import classify_parts
from sw.excel_handler import (assign_codes, write_back, clear_old_records,
                               build_existing_mapping, make_working_copy)
from sw.renamer import pack_and_go_rename
from sw.models import STATUS_NEW, STATUS_EXISTING, STATUS_PREVIOUSLY_CODED


# ---------------------------------------------------------------------------
# Yardimci: parcalarin hangileri default secili-degil gelecek
# ---------------------------------------------------------------------------

def exclusion_reason(part) -> str | None:
    """STEP / Imported / Suppressed -> kisa etiket; normal -> None."""
    name_l = (part.original_name or "").strip().lower()
    if part.extension in (".stp", ".step") or name_l.endswith((".stp", ".step")):
        return "STEP"
    if getattr(part, "is_imported", False):
        return "Alınmış"
    if getattr(part, "suppressed", False):
        return "Suppressed"
    return None


# ---------------------------------------------------------------------------
# Log / rapor dosyalari
# ---------------------------------------------------------------------------

def _log_error(exc: Exception, asm: str = "", kfg: str = "",
               is_live: bool = False, base_dir: str = "") -> None:
    import traceback
    from datetime import datetime
    log_path = os.path.join(base_dir or os.getcwd(), "sw_error.txt")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*70}\n")
            f.write(f"HATA ZAMANI  : {ts}\n")
            f.write(f"MONTAJ       : {asm or '(belirtilmedi)'}\n")
            f.write(f"KONFIG       : {kfg or '(belirtilmedi)'}\n")
            f.write(f"MOD          : {'CANLI' if is_live else 'DRY-RUN'}\n")
            f.write(f"HATA TURU    : {type(exc).__name__}\n")
            f.write(f"HATA MESAJI  : {exc}\n")
            f.write("TRACEBACK    :\n")
            f.write(traceback.format_exc())
            f.write(f"{'='*70}\n")
    except Exception:
        pass


def _log_rapor(parts: list, asm: str, kfg: str, is_live: bool,
               kopya: str = "", proje_kodu: str = "", elapsed_secs: int = 0,
               base_dir: str = "") -> None:
    from datetime import datetime
    log_path = os.path.join(base_dir or os.getcwd(), "sw_rapor.txt")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    coded   = [p for p in parts if p.erp_code]
    skipped = [p for p in parts if not p.erp_code]
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*70}\n")
            f.write(f"RAPOR ZAMANI : {ts}\n")
            f.write(f"MONTAJ       : {asm}\n")
            f.write(f"KONFIG       : {kfg}\n")
            f.write(f"PROJE KODU   : {proje_kodu or '(girilmedi)'}\n")
            f.write(f"MOD          : {'CANLI' if is_live else 'DRY-RUN'}\n")
            if elapsed_secs > 0:
                m, s = divmod(elapsed_secs, 60)
                f.write(f"SURE         : {m} dk {s:02d} sn\n" if m else f"SURE         : {s} sn\n")
            f.write(f"{'-'*70}\n")
            f.write(f"ATANAN KODLAR ({len(coded)}):\n")
            for p in coded:
                f.write(f"  {p.original_name:30} -> {p.erp_code:20} [{p.category}]\n")
            if skipped:
                f.write(f"{'-'*70}\n")
                f.write(f"ATLANANLAR ({len(skipped)}):\n")
                for p in skipped:
                    f.write(f"  {p.original_name:30}    {p.reason[:50]}\n")
            f.write(f"{'='*70}\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# ANA AKIS
# ---------------------------------------------------------------------------

def run(
    assembly_path: str,
    konfig_path: str,
    live: bool = False,
    auto_yes: bool = False,
    proje_kodu: str = "",
    selected_paths: set[str] | None = None,
    parts: list | None = None,
    # --- iletisim kanalları ---
    log_fn: Callable[[str], None] = print,
    dialog_req_q: queue.Queue | None = None,
    dialog_res_q: queue.Queue | None = None,
    override_req_q: queue.Queue | None = None,
    override_res_q: queue.Queue | None = None,
    confirm_req_q: queue.Queue | None = None,
    confirm_res_q: queue.Queue | None = None,
    base_dir: str = "",
) -> list:
    """Pipeline'i calistirir; islenen Part listesini dondurur."""

    _start = time.time()

    def _log(msg: str):
        log_fn(msg)

    def _manuel_siniflandirma(parca_adi: str, image_path: str = "",
                               has_timeout: bool = True,
                               is_assembly: bool = False) -> str:
        if dialog_req_q is not None:
            dialog_req_q.put((parca_adi, image_path, has_timeout, is_assembly))
            return dialog_res_q.get()  # type: ignore[union-attr]
        return "TEKRAR_DENE"

    def _override_dialog(parca_adi, gorsel_ozet, ai_kat, ai_guven) -> str:
        if override_req_q is not None:
            override_req_q.put((parca_adi, gorsel_ozet, ai_kat, ai_guven))
            return override_res_q.get()  # type: ignore[union-attr]
        return ai_kat

    def _confirm() -> bool:
        if auto_yes:
            _log("\n[--yes] Otomatik onaylandi.")
            return True
        if confirm_req_q is not None:
            confirm_req_q.put(True)
            return confirm_res_q.get()  # type: ignore[union-attr]
        return True

    _log(f"Montaj      : {assembly_path}")
    _log(f"Konfig      : {konfig_path}")
    _log(f"Proje Kodu  : {proje_kodu or '(girilmedi)'}")
    _log(f"Mod         : {'CANLI (gercek yazma)' if live else 'DRY-RUN (deneme)'}")

    konfig_path = make_working_copy(konfig_path)

    # --- 1. OKU ---
    if parts is None:
        _log("\n[1/4] Montaj okunuyor...")
        parts = read_assembly_tree(assembly_path)
        _log(f"      {len(parts)} benzersiz dosya bulundu.")
    else:
        _log(f"\n[1/4] Onceden okunmus {len(parts)} parca kullaniliyor.")

    if selected_paths is not None:
        before = len(parts)
        parts = [p for p in parts if p.file_path in selected_paths]
        skipped_sel = before - len(parts)
        if skipped_sel:
            _log(f"      {skipped_sel} parca secilmedi, atlaniyor.")
        _log(f"      {len(parts)} parca isleme alinacak.")

    # --- 2. SINIFLANDIR ---
    _log("[2/4] Siniflandiriliyor...")
    parts = classify_parts(parts)

    step_count = imported_count = 0
    for p in parts:
        name_l = (p.original_name or "").strip().lower()
        is_step = p.extension in (".stp", ".step") or name_l.endswith((".stp", ".step"))
        if is_step:
            p.status = STATUS_EXISTING
            p.reason = "STEP dosyasi/adi — kod verilmez"
            step_count += 1
        elif getattr(p, "is_imported", False):
            p.status = STATUS_EXISTING
            p.reason = "Alinmis (imported) parca — kod verilmez"
            imported_count += 1
    if step_count:
        _log(f"      {step_count} STEP istisnaya alindi.")
    if imported_count:
        _log(f"      {imported_count} Alinmis parca istisnaya alindi.")

    existing_mapping = build_existing_mapping(konfig_path)
    geo_matched = 0
    for p in parts:
        if p.status == STATUS_EXISTING:
            continue
        if p.geometric_signature and p.geometric_signature in existing_mapping:
            p.status   = STATUS_PREVIOUSLY_CODED
            p.erp_code = existing_mapping[p.geometric_signature]
            p.reason   = f"Geometrik imza eslesti: {p.erp_code}"
            geo_matched += 1
    if geo_matched:
        _log(f"      {geo_matched} parca geo imzayla eslesti.")

    # --- YAPAY ZEKA KATMANI ---
    unknown_parts = [
        p for p in parts
        if p.status == "unknown" or
        (p.category == "Mekanik" and p.reason and "Sistem kararsiz kaldi" in p.reason)
    ]
    if unknown_parts:
        swApp = None
        temp_dir = None
        _log("\n[Gorsel Zeka Hazirligi] Kararsiz parcalar fotograflaniyor...")
        try:
            swApp = _sw_reader_mod._connect_to_solidworks()
            temp_dir = os.path.join(os.path.dirname(os.path.abspath(konfig_path)), "temp_images")
            for p in unknown_parts:
                img_path = export_part_image(swApp, p.file_path, temp_dir)
                if img_path:
                    p.image_path = img_path
                    _log(f"      -> Fotograf: {os.path.basename(img_path)}")
        except Exception as e:
            _log(f"      -> Goruntuleme hatasi: {e}")

        try:
            from sw.vision_handler import analyze_part_with_vision, update_ai_memory
            parts_with_image = [p for p in unknown_parts if p.image_path]
            _log(f"\n[Yapay Zeka Analizi] {len(parts_with_image)} fotograf...")

            for p in parts_with_image:
                _ai_retry = 0
                while True:
                    result = analyze_part_with_vision(p.image_path)
                    kategori = result.get("kategori")

                    if kategori == "API_ARIZASI":
                        has_to = (_ai_retry == 0)
                        _log(f"\n  [DIKKAT] '{p.original_name}' icin YZ'ye ulasilamadi. GUI aciliyor...")
                        secim = _manuel_siniflandirma(
                            p.original_name, getattr(p, "image_path", "") or "",
                            has_timeout=has_to, is_assembly=p.is_assembly)
                        if secim == "TEKRAR_DENE":
                            _ai_retry += 1
                            _log("      -> Tekrar deneniyor...")
                        else:
                            p.category = secim
                            p.status   = STATUS_NEW
                            break

                    elif kategori:
                        guven       = result.get("guven_orani", 0)
                        gerekce     = result.get("gerekce", "")
                        gorsel_ozet = result.get("gorsel_ozet", "")
                        _log(f"      -> {p.original_name}: {kategori} (guven: {guven:.0%})")
                        if gerekce:
                            _log(f"         Gerekce: {gerekce[:100]}")

                        if guven >= 0.94:
                            p.category = kategori
                            p.status   = STATUS_NEW
                            if gorsel_ozet:
                                update_ai_memory(gorsel_ozet, kategori)
                        else:
                            best_kat  = kategori
                            best_ozet = gorsel_ozet
                            if swApp and temp_dir:
                                _log("         Guven dusuk, ek gorunumler...")
                                extra = export_part_additional_views(swApp, p.file_path, temp_dir)
                                if extra:
                                    all_imgs = [p.image_path] + extra
                                    r2 = analyze_part_with_vision(all_imgs)
                                    k2 = r2.get("kategori")
                                    if k2 and k2 != "API_ARIZASI":
                                        best_kat  = k2
                                        best_ozet = r2.get("gorsel_ozet", "") or gorsel_ozet
                                        _log(f"         Ek: {k2} ({r2.get('guven_orani',0):.0%})")
                            secim = _override_dialog(p.original_name, best_ozet, best_kat, guven)
                            p.category = secim
                            p.status   = STATUS_NEW
                            if best_ozet:
                                update_ai_memory(best_ozet, secim)
                        break
                    else:
                        break

        except ImportError:
            _log("      -> vision_handler bulunamadi, AI atlaniyor.")
        except Exception as e:
            _log(f"      -> AI hata: {e}")

    # --- TEMIZLIK ---
    if selected_paths is not None:
        temizlenecek = [p for p in parts
                        if p.status not in (STATUS_EXISTING, STATUS_PREVIOUSLY_CODED)
                        and p.category]
        if temizlenecek:
            _log(f"\n[Temizlik] {len(temizlenecek)} parca icin eski kayitlar temizleniyor...")
            clear_old_records([p.original_name for p in temizlenecek], konfig_path)

    # --- 3. KOD ATA ---
    _log("[3/4] Kodlar ataniyor...")
    parts = assign_codes(parts, konfig_path)

    coded   = [p for p in parts if p.erp_code]
    skipped = [p for p in parts if not p.erp_code]
    _log("\n" + "="*60)
    _log("ATAMA PLANI:")
    for p in coded:
        _log(f"  {p.original_name:28} -> {p.erp_code:18} [{p.category}]")
    if skipped:
        _log("-"*60)
        _log("ATLANANLAR:")
        for p in skipped:
            _log(f"  {p.original_name:28}   {p.reason[:50]}")
    _log("="*60)

    if not coded:
        _log("\nKodlanacak parca yok. Islem durduruldu.")
        return parts

    # --- DRY-RUN ---
    if not live:
        _log("\nDRY-RUN modu: hicbir dosya degistirilmedi.")
        pack_and_go_rename(assembly_path, parts, dry_run=True)
        _log_rapor(parts, assembly_path, konfig_path, is_live=False,
                   proje_kodu=proje_kodu,
                   elapsed_secs=int(time.time() - _start), base_dir=base_dir)
        return parts

    # --- 4. ONAY ---
    if not _confirm():
        _log("Iptal edildi.")
        return parts

    # --- 5a. EXCEL ---
    _log("\n[4/4] konfig.xlsx guncelleniyor...")
    write_back(parts, konfig_path, proje_kodu=proje_kodu)

    # --- 5b. KOPYALA ---
    _log("Kodlanmis kopya uretiliyor...")
    pack_result = pack_and_go_rename(assembly_path, parts, dry_run=False)
    _log(f"\nTAMAMLANDI. Dosyalar: {pack_result['target']}")
    _log_rapor(parts, assembly_path, konfig_path, is_live=True,
               kopya=pack_result["target"], proje_kodu=proje_kodu,
               elapsed_secs=int(time.time() - _start), base_dir=base_dir)
    return parts
