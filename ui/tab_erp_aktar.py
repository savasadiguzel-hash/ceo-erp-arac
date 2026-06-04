"""tab_erp_aktar.py — Stok Kartı Aktar sekmesi + diyaloğu (PyQt5).

Sekme olarak: son SW çalışmasının kodlu parçalarını listeler, Kuru/Canlı aktarım yapar.
Diyalog (ErpAktarDialog): tab_sw.py'dan veya bağımsız çağrılabilir.
"""
from __future__ import annotations

import threading
import queue
from typing import Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QDialog, QMessageBox, QGroupBox,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QTextCursor

try:
    from sw import erp_handler as _erp_mod
    ERP_ENABLED = True
except Exception as _erp_err:
    _erp_mod = None  # type: ignore[assignment]
    ERP_ENABLED = False
    _erp_err_msg = str(_erp_err)

_BTN_MAVI  = "background:#0078d4;color:white;border-radius:6px;padding:8px 18px;font-weight:bold;"
_BTN_YESIL = "background:#2d7a2d;color:white;border-radius:6px;padding:8px 18px;font-weight:bold;"
_BTN_GERI  = "background:#eceff1;color:#37474f;border-radius:6px;padding:8px 18px;"
_LOG_STYLE = "background:#1e1e1e;color:#d4d4d4;font-family:Consolas,monospace;font-size:11px;"


# ---------------------------------------------------------------------------
# Aktarım Diyaloğu — tab_sw.py ve sekme ikisi de kullanır
# ---------------------------------------------------------------------------
class ErpAktarDialog(QDialog):
    def __init__(self, coded_parts: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ERP'ye Aktar — CEO Stok Kartı")
        self.setMinimumSize(680, 500)
        self.setModal(True)

        self._coded = [(p.erp_code, getattr(p, "original_name", ""))
                       if hasattr(p, "erp_code") else p
                       for p in coded_parts]
        self._q: queue.Queue = queue.Queue()
        self._running = False

        lay = QVBoxLayout(self)

        firma = _erp_mod.FIRMA_GERCEK if _erp_mod else "?"
        lay.addWidget(QLabel(
            f"<b>CEO Firma: {firma}  —  {len(self._coded)} kodlu parça</b>"))

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(_LOG_STYLE)
        lay.addWidget(self._log, stretch=1)

        btn_row = QHBoxLayout()
        self._kuru_btn  = QPushButton("Kuru Çalışma (Önizleme)")
        self._kuru_btn.setStyleSheet(_BTN_GERI)
        self._kuru_btn.clicked.connect(lambda: self._calistir(False))
        self._canli_btn = QPushButton("CANLI Aktar")
        self._canli_btn.setStyleSheet(_BTN_YESIL)
        self._canli_btn.clicked.connect(lambda: self._calistir(True))
        self._kapat_btn = QPushButton("Kapat")
        self._kapat_btn.setStyleSheet(_BTN_GERI)
        self._kapat_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._kuru_btn)
        btn_row.addWidget(self._canli_btn)
        btn_row.addWidget(self._kapat_btn)
        lay.addLayout(btn_row)

        self._log_metin("Hazır. Önce 'Kuru Çalışma' ile önizleyin, sonra 'CANLI Aktar'.")
        self._log_metin(f"Bağlantı: .env → CEO_SQL_CONN  |  Firma: {firma}")

        self._poll_t = QTimer(self)
        self._poll_t.setInterval(120)
        self._poll_t.timeout.connect(self._poll)
        self._poll_t.start()

    def _log_metin(self, s: str):
        self._log.moveCursor(QTextCursor.End)
        self._log.insertPlainText(s + "\n")
        self._log.moveCursor(QTextCursor.End)

    def _poll(self):
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "log":
                    self._log_metin(payload)
                elif kind == "done":
                    self._running = False
                    oz = payload or {}
                    self._log_metin("")
                    self._log_metin(
                        "=== ÖZET: oluşturuldu=%d  atlandı=%d  hata=%d ===" % (
                            oz.get("olusturuldu", 0), oz.get("atlandi", 0), oz.get("hata", 0)))
                    for b in (self._kuru_btn, self._canli_btn, self._kapat_btn):
                        b.setEnabled(True)
        except queue.Empty:
            pass

    def _calistir(self, live: bool):
        if self._running or not self._coded:
            if not self._coded:
                self._log_metin("Aktarılacak kodlu parça yok.")
            return
        if live:
            firma = _erp_mod.FIRMA_GERCEK if _erp_mod else "?"
            if QMessageBox.question(
                    self, "CANLI Aktarım Onayı",
                    f"{firma} firmasına {len(self._coded)} kart için\n"
                    f"GERÇEK yazma yapılacak. Mevcut kodlar atlanır.\n\n"
                    "Devam edilsin mi?",
                    QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return

        self._running = True
        for b in (self._kuru_btn, self._canli_btn, self._kapat_btn):
            b.setEnabled(False)
        mod_str = "CANLI AKTARIM" if live else "KURU ÇALIŞMA (önizleme)"
        self._log_metin(f"\n--- {mod_str} başlatıldı ---")
        q = self._q
        coded = self._coded

        def _work():
            try:
                oz = _erp_mod.toplu_kart_ac(
                    coded,
                    firma_db=_erp_mod.FIRMA_GERCEK,
                    live=live,
                    log=lambda s: q.put(("log", s)))
                q.put(("done", oz))
            except Exception as e:
                q.put(("log", f"HATA: {e}"))
                q.put(("done", {}))

        threading.Thread(target=_work, daemon=True).start()


# ---------------------------------------------------------------------------
# Sekme Widget'ı (bağımsız kullanım veya son SW sonucunu gösterme)
# ---------------------------------------------------------------------------
class TabErpAktar(QWidget):
    durum_guncelle = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._kodlu_parcalar: list = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 10)
        lay.setSpacing(12)

        if not ERP_ENABLED:
            uyari = QLabel(
                f"⚠  ERP modülü yüklenemedi:\n{_erp_err_msg}\n\n"
                "pyodbc kurulu ve CEO_SQL_CONN .env'de tanımlı olmalı.")
            uyari.setWordWrap(True)
            uyari.setStyleSheet("color:#b00000;padding:20px;font-size:12px;")
            lay.addWidget(uyari)
            return

        firma = _erp_mod.FIRMA_GERCEK if _erp_mod else "?"
        baslik = QLabel(f"<b>CEO ERP — Stok Kartı Aktarımı</b>")
        baslik.setStyleSheet("font-size:15px;color:#1a237e;")
        lay.addWidget(baslik)

        bilgi = QLabel(
            f"Firma: <b>{firma}</b>\n\n"
            "Bu sekme; SW Kodlama sekmesinde tamamlanan çalışmanın kodlu parçalarını\n"
            "CEO ERP'ye (StokKarti + StokKumulatif + StokKartiBolge) aktarır.\n\n"
            "SW Kodlama → BAŞLA → ERP'ye Aktar butonunu kullanın,\n"
            "veya aşağıdan bağımsız aktarım başlatın.")
        bilgi.setWordWrap(True)
        bilgi.setStyleSheet("color:#444;font-size:12px;")
        lay.addWidget(bilgi)

        self._durum_gb = QGroupBox(" Son SW Çalışması ")
        durum_lay = QVBoxLayout(self._durum_gb)
        self._durum_lbl = QLabel("Henüz SW Kodlama çalıştırılmadı.")
        self._durum_lbl.setStyleSheet("color:#888;")
        durum_lay.addWidget(self._durum_lbl)

        self._aktar_btn = QPushButton("Stok Kartlarını Aktar (Son Çalışma)")
        self._aktar_btn.setStyleSheet(_BTN_MAVI)
        self._aktar_btn.setEnabled(False)
        self._aktar_btn.clicked.connect(self._aktar)
        durum_lay.addWidget(self._aktar_btn)

        lay.addWidget(self._durum_gb)
        lay.addStretch()

    def set_kodlu_parcalar(self, parcalar: list):
        """TabSW tarafından çalışma bitince çağrılır."""
        self._kodlu_parcalar = parcalar
        n = len(parcalar)
        if n:
            self._durum_lbl.setText(
                f"{n} kodlu parça aktarıma hazır.")
            self._durum_lbl.setStyleSheet("color:#2d7a2d;font-weight:bold;")
            self._aktar_btn.setEnabled(True)
        else:
            self._durum_lbl.setText("Kodlu parça bulunamadı (son çalışma).")
            self._durum_lbl.setStyleSheet("color:#888;")
            self._aktar_btn.setEnabled(False)

    def _aktar(self):
        if not self._kodlu_parcalar:
            return
        dlg = ErpAktarDialog(self._kodlu_parcalar, parent=self)
        dlg.exec_()
