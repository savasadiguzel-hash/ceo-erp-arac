"""tab_sw.py — SW Kodlama sekmesi (PyQt5).

SW-ERP-Agent'in Tkinter arayuzunun PyQt5 karsiligi.
Mimarisi ayni: kuyruk + QTimer polling.
"""
from __future__ import annotations

import os
import queue
import sys
import threading
from typing import Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QCheckBox, QPlainTextEdit,
    QFileDialog, QGroupBox, QGridLayout, QSizePolicy, QMessageBox,
    QDialog, QDialogButtonBox,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor

SW_ENABLED = True
try:
    from sw import sw_reader as _sw_reader_mod
    from sw.sw_reader import read_assembly_tree
    from sw.pipeline import run as pipeline_run, exclusion_reason
except Exception as _sw_err:
    SW_ENABLED = False
    _sw_err_msg = str(_sw_err)

try:
    from sw import erp_handler as _erp_mod
except Exception:
    _erp_mod = None  # type: ignore[assignment]


# ── renk sabitleri ──────────────────────────────────────────────────────────
_BTN_MAVI   = "background:#0078d4;color:white;border-radius:6px;padding:8px 18px;font-weight:bold;"
_BTN_YESIL  = "background:#2d7a2d;color:white;border-radius:6px;padding:8px 18px;font-weight:bold;"
_BTN_GERI   = "background:#eceff1;color:#37474f;border-radius:6px;padding:8px 18px;"
_LOG_STYLE  = "background:#1e1e1e;color:#d4d4d4;font-family:Consolas,monospace;font-size:11px;"


# ---------------------------------------------------------------------------
# Manuel Sınıflandırma Diyaloğu
# ---------------------------------------------------------------------------
class ManuelSinifDialog(QDialog):
    def __init__(self, parca_adi: str, image_path: str = "",
                 has_timeout: bool = True, is_assembly: bool = False,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manuel Sınıflandırma Gerekli")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(420)
        self.setModal(True)
        self._secim = None
        self._countdown = has_timeout
        self._sure = 60

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        # goruntu
        if image_path and os.path.exists(image_path):
            try:
                from PyQt5.QtGui import QPixmap
                pix = QPixmap(image_path).scaled(360, 360, Qt.KeepAspectRatio,
                                                  Qt.SmoothTransformation)
                lbl = QLabel()
                lbl.setPixmap(pix)
                lbl.setAlignment(Qt.AlignCenter)
                lay.addWidget(lbl)
            except Exception:
                pass

        lay.addWidget(QLabel(f"'{parca_adi}' için\nYapay zekaya ulaşılamadı.\n"
                             "Kategori seçin:"))
        if has_timeout:
            self._cd_lbl = QLabel(f"Otomatik tekrar: {self._sure} sn")
            self._cd_lbl.setStyleSheet("color:#e67e22;font-size:10px;")
            lay.addWidget(self._cd_lbl)

        for kat in ["Mekanik", "Elektronik", "Montaj", "Optik"]:
            disabled = (kat == "Montaj" and not is_assembly)
            btn = QPushButton(kat)
            btn.setEnabled(not disabled)
            btn.setStyleSheet(_BTN_MAVI)
            btn.clicked.connect(lambda _, k=kat: self._sec(k))
            lay.addWidget(btn)

        tekrar_btn = QPushButton("Yapay Zeka ile Tekrar Dene")
        tekrar_btn.setStyleSheet(_BTN_GERI)
        tekrar_btn.clicked.connect(lambda: self._sec("TEKRAR_DENE"))
        lay.addWidget(tekrar_btn)

        if has_timeout:
            self._timer = QTimer(self)
            self._timer.setInterval(1000)
            self._timer.timeout.connect(self._tick)
            self._timer.start()

    def _tick(self):
        self._sure -= 1
        self._cd_lbl.setText(f"Otomatik tekrar: {self._sure} sn")
        if self._sure <= 0:
            self._timer.stop()
            self._sec("TEKRAR_DENE")

    def _sec(self, kat: str):
        if hasattr(self, "_timer"):
            self._timer.stop()
        self._secim = kat
        self.accept()

    def secim(self) -> str:
        return self._secim or "TEKRAR_DENE"


# ---------------------------------------------------------------------------
# Override Diyaloğu (düşük güven AI)
# ---------------------------------------------------------------------------
class OverrideDialog(QDialog):
    def __init__(self, parca_adi, gorsel_ozet, ai_kat, ai_guven, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Düşük Güven — AI Tahmini Onayı")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(380)
        self.setModal(True)
        self._secim = ai_kat

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<b>{parca_adi}</b>"))
        lay.addWidget(QLabel(f"AI Tahmini: <b>{ai_kat}</b>"))
        lay.addWidget(QLabel(f"Güven: {ai_guven:.0%}"))
        if gorsel_ozet:
            lbl = QLabel(f"<i>{gorsel_ozet}</i>")
            lbl.setWordWrap(True)
            lay.addWidget(lbl)

        onayla = QPushButton(f"Onayla  ({ai_kat})")
        onayla.setStyleSheet(_BTN_MAVI)
        onayla.clicked.connect(lambda: self._sec(ai_kat))
        lay.addWidget(onayla)

        lay.addWidget(QLabel("— veya farklı kategori seç —"))
        for kat in ["Mekanik", "Elektronik", "Montaj", "Optik"]:
            if kat != ai_kat:
                btn = QPushButton(kat)
                btn.setStyleSheet(_BTN_GERI)
                btn.clicked.connect(lambda _, k=kat: self._sec(k))
                lay.addWidget(btn)

    def _sec(self, kat):
        self._secim = kat
        self.accept()

    def secim(self):
        return self._secim


# ---------------------------------------------------------------------------
# Onay Diyaloğu
# ---------------------------------------------------------------------------
class OnayDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Onay Gerekli")
        self.setModal(True)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Bu kodlar konfig.xlsx'e yazılsın\n"
                             "ve kodlanmış kopya üretilsin mi?"))
        bb = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def onaylandi(self) -> bool:
        return self.exec_() == QDialog.Accepted


# ---------------------------------------------------------------------------
# Ana Sekme Widget'ı
# ---------------------------------------------------------------------------
class TabSW(QWidget):
    durum_guncelle  = pyqtSignal(str)
    kodlama_bitti   = pyqtSignal(bool, list, str)   # success, parts, err_msg

    def __init__(self):
        super().__init__()
        self._asm_path = ""
        self._kfg_path = ""
        self._part_checks: dict[str, QCheckBox] = {}
        self._scan_state: dict[str, Any] = {"done": False, "error": None, "parts": []}
        self._result: dict[str, Any] = {"parts": [], "success": False}

        # kuyruklar
        self._log_q:      queue.Queue = queue.Queue()
        self._dialog_req_q: queue.Queue = queue.Queue()
        self._dialog_res_q: queue.Queue = queue.Queue()
        self._override_req_q: queue.Queue = queue.Queue()
        self._override_res_q: queue.Queue = queue.Queue()
        self._confirm_req_q: queue.Queue = queue.Queue()
        self._confirm_res_q: queue.Queue = queue.Queue()
        self._prescan_q: queue.Queue = queue.Queue()
        self._done_q: queue.Queue = queue.Queue()

        self._build_ui()

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(100)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start()

    # ── UI inşa ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 6)
        root.setSpacing(6)

        if not SW_ENABLED:
            uyari = QLabel(f"⚠  SolidWorks modülleri yüklenemedi:\n{_sw_err_msg}\n\n"
                           "pywin32, openpyxl ve SolidWorks kurulu bir makinede çalıştırın.")
            uyari.setWordWrap(True)
            uyari.setStyleSheet("color:#b00000;padding:20px;font-size:12px;")
            root.addWidget(uyari)
            return

        # ── üst panel ───────────────────────────────────────────────────────
        top = QGroupBox(f" Ayarlar ")
        top_lay = QGridLayout(top)
        top_lay.setSpacing(8)

        self._asm_lbl = QLabel("Seçilmedi")
        self._asm_lbl.setStyleSheet("color:#555;font-size:11px;")
        self._kfg_lbl = QLabel("Seçilmedi")
        self._kfg_lbl.setStyleSheet("color:#555;font-size:11px;")

        asm_btn = QPushButton("Montaj Seç")
        asm_btn.setStyleSheet(_BTN_MAVI)
        asm_btn.clicked.connect(self._sec_montaj)

        kfg_btn = QPushButton("Konfig Seç")
        kfg_btn.setStyleSheet(_BTN_MAVI)
        kfg_btn.clicked.connect(self._sec_konfig)

        top_lay.addWidget(asm_btn,       0, 0)
        top_lay.addWidget(self._asm_lbl, 0, 1)
        top_lay.addWidget(kfg_btn,       1, 0)
        top_lay.addWidget(self._kfg_lbl, 1, 1)

        proje_lbl = QLabel("Proje Kodu:")
        proje_lbl.setStyleSheet("font-weight:bold;")
        self._proje_edit = QLineEdit()
        self._proje_edit.setPlaceholderText("Sadece rakam, zorunlu")
        self._proje_edit.setMaximumWidth(160)
        self._proje_edit.textChanged.connect(self._check_ready)
        top_lay.addWidget(proje_lbl,        2, 0)
        top_lay.addWidget(self._proje_edit, 2, 1, 1, 1, Qt.AlignLeft)

        # buton satırı
        btn_row = QHBoxLayout()
        self._basla_btn = QPushButton("BAŞLA")
        self._basla_btn.setStyleSheet(_BTN_YESIL)
        self._basla_btn.setEnabled(False)
        self._basla_btn.clicked.connect(self._basla)
        btn_row.addWidget(self._basla_btn)

        self._erp_btn = QPushButton("ERP'ye Aktar")
        self._erp_btn.setStyleSheet(_BTN_MAVI)
        self._erp_btn.clicked.connect(self._erp_aktar)
        btn_row.addWidget(self._erp_btn)

        self._sure_lbl = QLabel("")
        self._sure_lbl.setStyleSheet("color:#0078d4;font-weight:bold;")
        btn_row.addWidget(self._sure_lbl)
        btn_row.addStretch()
        top_lay.addLayout(btn_row, 3, 0, 1, 2)

        root.addWidget(top)

        # ── orta: parca listesi ──────────────────────────────────────────────
        self._parca_gb = QGroupBox(" Parçalar ")
        parca_lay = QVBoxLayout(self._parca_gb)
        parca_lay.setContentsMargins(4, 4, 4, 4)

        self._parca_msg = QLabel("Montaj dosyasını seçtikten sonra parça listesi yüklenir.")
        self._parca_msg.setStyleSheet("color:#888;")
        self._parca_msg.setAlignment(Qt.AlignCenter)
        parca_lay.addWidget(self._parca_msg)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFixedHeight(180)
        self._scroll.hide()
        self._inner = QWidget()
        self._inner_lay = QVBoxLayout(self._inner)
        self._inner_lay.setContentsMargins(6, 4, 6, 4)
        self._inner_lay.setSpacing(2)
        self._scroll.setWidget(self._inner)
        parca_lay.addWidget(self._scroll)

        root.addWidget(self._parca_gb)

        # ── log alanı ────────────────────────────────────────────────────────
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(_LOG_STYLE)
        self._log.setMinimumHeight(200)
        root.addWidget(self._log, stretch=1)

        # durum
        self._durum_lbl = QLabel("Dosyaları seçin ve proje kodunu girin.")
        self._durum_lbl.setStyleSheet("color:#666;font-size:10px;")
        root.addWidget(self._durum_lbl)

    # ── dosya seçimi ─────────────────────────────────────────────────────────
    def _sec_montaj(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "SolidWorks Montaj Seç", "",
            "SolidWorks Montaj (*.sldasm *.SLDASM);;Tüm Dosyalar (*.*)")
        if p:
            self._asm_path = p
            self._asm_lbl.setText(os.path.basename(p))
            self._asm_lbl.setToolTip(p)
            self._start_prescan(p)

    def _sec_konfig(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Konfig Dosyası Seç", "",
            "Excel (*.xlsx *.XLSX);;Tüm Dosyalar (*.*)")
        if p:
            self._kfg_path = p
            self._kfg_lbl.setText(os.path.basename(p))
            self._kfg_lbl.setToolTip(p)
            self._check_ready()

    # ── hazır kontrolü ───────────────────────────────────────────────────────
    def _check_ready(self):
        proje_ok = self._proje_edit.text().strip().isdigit() and len(self._proje_edit.text().strip()) > 0
        scan_ok  = self._scan_state["done"] or bool(self._scan_state["error"])
        files_ok = bool(self._asm_path and self._kfg_path)
        self._basla_btn.setEnabled(bool(files_ok and proje_ok and scan_ok))

    # ── ön tarama ────────────────────────────────────────────────────────────
    def _start_prescan(self, path: str):
        self._scan_state = {"done": False, "error": None, "parts": []}
        self._part_checks.clear()
        for i in reversed(range(self._inner_lay.count())):
            w = self._inner_lay.itemAt(i).widget()
            if w:
                w.deleteLater()
        self._scroll.hide()
        self._parca_msg.setText("SolidWorks başlatılıyor, montaj okunuyor…")
        self._parca_msg.setStyleSheet("color:#e67e22;")
        self._parca_msg.show()
        self._parca_gb.setTitle(" Parçalar — Okunuyor… ")
        self._check_ready()

        def _thread():
            try:
                result = read_assembly_tree(path, only_paths=set())
                self._prescan_q.put(("ok", result))
            except Exception as exc:
                self._prescan_q.put(("err", exc))

        threading.Thread(target=_thread, daemon=True).start()

    def _prescan_tamamlandi(self, scan_parts: list):
        self._scan_state["done"]  = True
        self._scan_state["parts"] = scan_parts

        for i in reversed(range(self._inner_lay.count())):
            w = self._inner_lay.itemAt(i).widget()
            if w:
                w.deleteLater()
        self._part_checks.clear()

        n = len(scan_parts)
        excl = 0

        # "Tümünü Seç" checkbox
        self._tum_cb = QCheckBox("Tümünü Seç / Kaldır")
        self._tum_cb.setStyleSheet("font-weight:bold;")
        self._tum_cb.setChecked(False)
        self._tum_cb.stateChanged.connect(self._toggle_all)
        self._inner_lay.addWidget(self._tum_cb)
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#cccccc;")
        self._inner_lay.addWidget(sep)

        for p in scan_parts:
            reason  = exclusion_reason(p)
            checked = reason is None
            if not checked:
                excl += 1
            cb = QCheckBox()
            prefix = "[A] " if p.is_assembly else "    "
            tag    = f"[{reason}] " if reason else ""
            cb.setText(f"{prefix}{tag}{p.original_name}")
            cb.setChecked(checked)
            if reason:
                cb.setStyleSheet("color:#b00000;")
            cb.stateChanged.connect(self._update_parca_baslik)
            self._part_checks[p.file_path] = cb
            self._inner_lay.addWidget(cb)

        self._parca_msg.hide()
        self._scroll.show()
        self._update_parca_baslik()
        self._durum_lbl.setText(
            f"Okuma tamamlandı: {n} parça — {n-excl} seçili, "
            f"{excl} otomatik seçilmedi (STEP/Alınmış/Suppressed).")
        self._check_ready()

    def _prescan_hatasi(self, exc: Exception):
        self._scan_state["error"] = exc
        self._parca_msg.setText(f"Ön tarama hatası: {exc}\nBaşla'ya basınca tüm parçalar işlenir.")
        self._parca_msg.setStyleSheet("color:#cc0000;")
        self._parca_msg.show()
        self._parca_gb.setTitle(" Parçalar (Ön Tarama Hatası) ")
        self._check_ready()

    def _toggle_all(self, state: int):
        checked = bool(state == Qt.Checked)
        for cb in self._part_checks.values():
            cb.setChecked(checked)

    def _update_parca_baslik(self):
        sel = sum(1 for cb in self._part_checks.values() if cb.isChecked())
        tot = len(self._part_checks)
        self._parca_gb.setTitle(f" Parçalar (Seçili: {sel} / {tot}) ")
        if tot > 0 and sel == tot:
            self._tum_cb.blockSignals(True)
            self._tum_cb.setChecked(True)
            self._tum_cb.blockSignals(False)
        elif sel == 0:
            self._tum_cb.blockSignals(True)
            self._tum_cb.setChecked(False)
            self._tum_cb.blockSignals(False)

    # ── log yardımcısı ───────────────────────────────────────────────────────
    def _append_log(self, msg: str):
        self._log.moveCursor(QTextCursor.End)
        self._log.insertPlainText(msg)
        self._log.moveCursor(QTextCursor.End)

    # ── polling ──────────────────────────────────────────────────────────────
    def _poll(self):
        # stdout log kuyruğu
        try:
            while True:
                msg = self._log_q.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass

        # ön tarama sonucu
        try:
            tag, payload = self._prescan_q.get_nowait()
            if tag == "ok":
                self._prescan_tamamlandi(payload)
            else:
                self._prescan_hatasi(payload)
        except queue.Empty:
            pass

        # sınıflandırma diyaloğu isteği
        try:
            item = self._dialog_req_q.get_nowait()
            parca_adi, image_path, has_timeout, is_asm = item
            dlg = ManuelSinifDialog(parca_adi, image_path, has_timeout, is_asm, self)
            dlg.exec_()
            self._dialog_res_q.put(dlg.secim())
        except queue.Empty:
            pass

        # override diyaloğu
        try:
            item = self._override_req_q.get_nowait()
            parca_adi, gorsel_ozet, ai_kat, ai_guven = item
            dlg = OverrideDialog(parca_adi, gorsel_ozet, ai_kat, ai_guven, self)
            dlg.exec_()
            self._override_res_q.put(dlg.secim())
        except queue.Empty:
            pass

        # onay diyaloğu
        try:
            self._confirm_req_q.get_nowait()
            dlg = OnayDialog(self)
            self._confirm_res_q.put(dlg.onaylandi())
        except queue.Empty:
            pass

        # işlem bitti
        try:
            success, parts, err_msg = self._done_q.get_nowait()
            self._result["parts"]   = parts
            self._result["success"] = success
            self._islem_bitti(success, parts, err_msg)
            self.kodlama_bitti.emit(success, parts, err_msg)
        except queue.Empty:
            pass

    # ── BAŞLA ────────────────────────────────────────────────────────────────
    def _basla(self):
        if not self._asm_path or not self._kfg_path:
            return
        proje = self._proje_edit.text().strip()
        if not proje:
            return

        # seçili parça yolları
        if self._scan_state["done"] and self._part_checks:
            sel_paths = {fp for fp, cb in self._part_checks.items() if cb.isChecked()}
            if not sel_paths:
                QMessageBox.warning(self, "Seçim Yok",
                                    "En az bir parça seçilmeli.")
                return
        else:
            sel_paths = None

        # UI kilitle
        self._basla_btn.setEnabled(False)
        self._erp_btn.setEnabled(False)
        self._log.clear()

        # sayaç
        import time as _time
        self._start_ts = _time.time()
        self._sure_timer = QTimer(self)
        self._sure_timer.setInterval(1000)
        self._sure_timer.timeout.connect(self._sure_guncelle)
        self._sure_timer.start()

        # stdout yönlendirme (sadece bu thread için)
        log_q = self._log_q

        class _LogStream:
            def write(self, msg):
                log_q.put(msg)
            def flush(self):
                pass

        def _worker():
            old_stdout = sys.stdout
            sys.stdout = _LogStream()
            try:
                # sadece seçili parçaları tam oku
                full_parts = None
                if sel_paths:
                    full_parts = read_assembly_tree(
                        self._asm_path, only_paths=set(sel_paths),
                        progress_cb=lambda d, t, n: print(f"  Okunuyor {d}/{t}: {n}"))

                parts = pipeline_run(
                    assembly_path=self._asm_path,
                    konfig_path=self._kfg_path,
                    live=True,
                    auto_yes=False,
                    proje_kodu=proje,
                    selected_paths=sel_paths,
                    parts=full_parts,
                    log_fn=print,
                    dialog_req_q=self._dialog_req_q,
                    dialog_res_q=self._dialog_res_q,
                    override_req_q=self._override_req_q,
                    override_res_q=self._override_res_q,
                    confirm_req_q=self._confirm_req_q,
                    confirm_res_q=self._confirm_res_q,
                    base_dir=os.path.dirname(os.path.abspath(self._kfg_path)),
                )
                self._done_q.put((True, parts or [], ""))
            except Exception as exc:
                self._done_q.put((False, [], str(exc)))
            finally:
                sys.stdout = old_stdout
                if _sw_reader_mod._sw_app_cache is not None:
                    try:
                        _sw_reader_mod._sw_app_cache.ExitApp()
                        print("SolidWorks kapatıldı.")
                    except Exception:
                        pass

        threading.Thread(target=_worker, daemon=True).start()

    def _sure_guncelle(self):
        import time as _time
        el = int(_time.time() - self._start_ts)
        m, s = divmod(el, 60)
        self._sure_lbl.setText(f"{m}:{s:02d}")

    def _islem_bitti(self, success: bool, parts: list, err_msg: str):
        if hasattr(self, "_sure_timer"):
            self._sure_timer.stop()
        self._basla_btn.setEnabled(True)
        self._erp_btn.setEnabled(True)

        coded = [p for p in parts if getattr(p, "erp_code", None)]
        if success:
            self._durum_lbl.setText(
                f"✔ Tamamlandı — {len(coded)} kod atandı.")
            self._durum_lbl.setStyleSheet("color:#2d7a2d;font-size:10px;")
            self.durum_guncelle.emit(f"SW Kodlama tamamlandı: {len(coded)} kod atandı.")
        else:
            self._durum_lbl.setText(f"✘ Hata: {err_msg}")
            self._durum_lbl.setStyleSheet("color:#b00000;font-size:10px;")

    # ── ERP'ye Aktar ─────────────────────────────────────────────────────────
    def _erp_aktar(self):
        coded = [p for p in self._result.get("parts", [])
                 if getattr(p, "erp_code", None)]
        if not coded:
            QMessageBox.information(
                self, "ERP'ye Aktar",
                "Aktarılacak kodlu parça yok.\n\n"
                "Önce 'BAŞLA' ile bir çalışma tamamlayın.")
            return
        if _erp_mod is None:
            QMessageBox.critical(self, "ERP Modülü Yok",
                                 "erp_handler yüklenemedi.")
            return

        from ui.tab_erp_aktar import ErpAktarDialog
        dlg = ErpAktarDialog(coded, parent=self)
        dlg.exec_()
