"""İş Emri Formu sekmesi — çoklu seçim + toplu PDF üretme desteği."""

from __future__ import annotations

import os
from datetime import datetime

from PyQt5.QtCore    import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QListWidget, QListWidgetItem, QGroupBox,
    QFormLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QLineEdit,
    QFileDialog, QMessageBox, QHeaderView, QAbstractItemView,
    QProgressDialog,
)

from config       import DB_DEFAULTS
from db.baglanti  import get_connection
from db.sorgular  import tum_is_emirleri_listesi, is_emri_malzeme_listesi
from logic.pdf_is_emri import is_emri_pdf_olustur


DURUM_ETIKET = {
    0: "Tüm Durumlar",
    1: "Başlamadı",
    2: "Tasarım Aşamasında",
    3: "Devam Ediyor",
    4: "Beklemeye Alındı",
    5: "Tamamlandı",
}

DURUM_RENK = {
    1: "#F5F5F5",
    2: "#E3F2FD",
    3: "#FFF9C4",
    4: "#F3E5F5",
    5: "#E8F5E9",
}


# ── Worker thread'ler ──────────────────────────────────────────────────────────

class _EmirlerThread(QThread):
    bitti = pyqtSignal(list)
    hata  = pyqtSignal(str)

    def __init__(self, conn):
        super().__init__()
        self._conn = conn

    def run(self):
        try:
            self.bitti.emit(tum_is_emirleri_listesi(self._conn))
        except Exception as e:
            self.hata.emit(str(e))


class _MalzemeThread(QThread):
    bitti = pyqtSignal(list)
    hata  = pyqtSignal(str)

    def __init__(self, conn, emir_id: int):
        super().__init__()
        self._conn    = conn
        self._emir_id = emir_id

    def run(self):
        try:
            self.bitti.emit(is_emri_malzeme_listesi(self._conn, self._emir_id))
        except Exception as e:
            self.hata.emit(str(e))


class _TopluPDFThread(QThread):
    """Seçili emirlerin tümü için sırayla DB'den malzeme çekip PDF üretir."""
    ilerleme = pyqtSignal(int, int, str)   # tamamlanan, toplam, dosya_adı
    bitti    = pyqtSignal(int, list)       # toplam, hata_mesajları

    def __init__(self, conn, emirler: list[dict], klasor: str):
        super().__init__()
        self._conn    = conn
        self._emirler = emirler
        self._klasor  = klasor

    def run(self):
        hatalar: list[str] = []
        toplam = len(self._emirler)
        tarih  = datetime.now().strftime("%Y%m%d")
        for i, emir in enumerate(self._emirler, 1):
            try:
                malzemeler = is_emri_malzeme_listesi(self._conn, emir["Id"])
                kodu_dosya = (emir.get("Kodu") or "emir").replace("/", "_").replace("\\", "_")
                dosya = os.path.join(self._klasor, f"is_emri_{kodu_dosya}_{tarih}.pdf")
                is_emri_pdf_olustur(dosya, emir, malzemeler)
                self.ilerleme.emit(i, toplam, os.path.basename(dosya))
            except Exception as e:
                hatalar.append(f"{emir.get('Kodu','?')}: {e}")
        self.bitti.emit(toplam, hatalar)


# ── Ana sekme ─────────────────────────────────────────────────────────────────

class IsEmriFormuTab(QWidget):
    durum_guncelle = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._conn:           object | None = None
        self._tum_emirler:    list[dict]    = []
        self._secili_emir:    dict | None   = None
        self._malzemeler:     list[dict]    = []
        self._emirler_thread: _EmirlerThread  | None = None
        self._malzeme_thread: _MalzemeThread  | None = None
        self._toplu_thread:   _TopluPDFThread | None = None
        self._ilerleme_dlg:   QProgressDialog | None = None
        self._kur()
        self._baglan_otomatik()

    # ── UI kurulumu ───────────────────────────────────────────────────────────

    def _kur(self):
        ana = QVBoxLayout(self)
        ana.setContentsMargins(8, 8, 8, 8)
        ana.setSpacing(6)

        ust = QHBoxLayout()
        baslik = QLabel("İş Emri Formu")
        baslik.setStyleSheet("font-size:15px;font-weight:bold;color:#1a237e;")
        ust.addWidget(baslik)
        ust.addStretch()
        self._durum_lbl = QLabel("")
        self._durum_lbl.setStyleSheet("color:#555;font-size:11px;")
        ust.addWidget(self._durum_lbl)
        ana.addLayout(ust)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)
        ana.addWidget(splitter, 1)
        splitter.addWidget(self._sol_panel())
        splitter.addWidget(self._sag_panel())
        splitter.setSizes([320, 660])

    def _sol_panel(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 4, 0)
        lay.setSpacing(4)

        filtre_row = QHBoxLayout()
        self._durum_combo = QComboBox()
        for did, etiket in DURUM_ETIKET.items():
            self._durum_combo.addItem(etiket, did)
        self._durum_combo.currentIndexChanged.connect(self._filtrele)
        filtre_row.addWidget(self._durum_combo, 1)
        self._yenile_btn = QPushButton("🔄 Yenile")
        self._yenile_btn.setFixedWidth(80)
        self._yenile_btn.clicked.connect(self._emirleri_yukle)
        filtre_row.addWidget(self._yenile_btn)
        lay.addLayout(filtre_row)

        self._ara_kutu = QLineEdit()
        self._ara_kutu.setPlaceholderText("Emir kodu veya açıklama ara…")
        self._ara_kutu.textChanged.connect(self._filtrele)
        lay.addWidget(self._ara_kutu)

        self._liste = QListWidget()
        self._liste.setAlternatingRowColors(True)
        self._liste.setSelectionMode(QAbstractItemView.SingleSelection)
        self._liste.setStyleSheet(
            "QListWidget{border:1px solid #c5cae9;border-radius:4px;}"
            "QListWidget::item{padding:6px 8px;border-bottom:1px solid #e8eaf6;}"
            "QListWidget::item:selected{background:#3f51b5;color:white;}"
        )
        self._liste.currentItemChanged.connect(self._emir_odak_degisti)
        self._liste.itemChanged.connect(self._secim_degisti)
        lay.addWidget(self._liste, 1)

        self._liste_ozet = QLabel("")
        self._liste_ozet.setStyleSheet("color:#666;font-size:10px;")
        lay.addWidget(self._liste_ozet)

        return w

    def _sag_panel(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 0, 0, 0)
        lay.setSpacing(6)

        kart = QGroupBox("Seçili İş Emri")
        kart.setStyleSheet(
            "QGroupBox{font-weight:bold;font-size:12px;color:#1a237e;"
            "border:1px solid #c5cae9;border-radius:6px;margin-top:6px;padding:8px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;}"
        )
        form = QFormLayout(kart)
        form.setLabelAlignment(Qt.AlignRight)
        self._kart_kodu     = QLabel("—")
        self._kart_tarih    = QLabel("—")
        self._kart_durum    = QLabel("—")
        self._kart_aciklama = QLabel("—")
        self._kart_aciklama.setWordWrap(True)
        for lbl, val in [
            ("Emir No:",  self._kart_kodu),
            ("Tarih:",    self._kart_tarih),
            ("Durum:",    self._kart_durum),
            ("Açıklama:", self._kart_aciklama),
        ]:
            form.addRow(lbl, val)
        lay.addWidget(kart)

        mal_baslik = QLabel("Malzeme Listesi")
        mal_baslik.setStyleSheet("font-weight:bold;color:#3949ab;font-size:11px;")
        lay.addWidget(mal_baslik)

        self._tablo = QTableWidget(0, 3)
        self._tablo.setHorizontalHeaderLabels(["Kod", "Adı", "Talep Miktarı"])
        self._tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._tablo.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tablo.setSelectionBehavior(QTableWidget.SelectRows)
        self._tablo.setAlternatingRowColors(True)
        self._tablo.verticalHeader().setDefaultSectionSize(22)
        self._tablo.setStyleSheet(
            "QTableWidget{border:1px solid #c5cae9;border-radius:4px;font-size:11px;}"
        )
        lay.addWidget(self._tablo, 1)

        self._tablo_ozet = QLabel("")
        self._tablo_ozet.setStyleSheet("color:#666;font-size:10px;")
        lay.addWidget(self._tablo_ozet)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._bos_form_btn = QPushButton("📋 Boş Form")
        self._bos_form_btn.setFixedHeight(34)
        self._bos_form_btn.setStyleSheet(
            "QPushButton{background:#546e7a;color:white;font-weight:bold;"
            "border-radius:5px;padding:0 14px;}"
            "QPushButton:hover{background:#37474f;}"
        )
        self._bos_form_btn.clicked.connect(self._bos_form_olustur)
        btn_row.addWidget(self._bos_form_btn)
        self._pdf_btn = QPushButton("📄 PDF Oluştur")
        self._pdf_btn.setEnabled(False)
        self._pdf_btn.setFixedHeight(34)
        self._pdf_btn.setStyleSheet(
            "QPushButton{background:#3f51b5;color:white;font-weight:bold;"
            "border-radius:5px;padding:0 18px;}"
            "QPushButton:hover{background:#303f9f;}"
            "QPushButton:disabled{background:#b0bec5;}"
        )
        self._pdf_btn.clicked.connect(self._pdf_olustur)
        btn_row.addWidget(self._pdf_btn)
        lay.addLayout(btn_row)

        return w

    # ── Bağlantı & Veri yükleme ───────────────────────────────────────────────

    def _baglan_otomatik(self):
        try:
            self._conn = get_connection(
                DB_DEFAULTS["sunucu"], DB_DEFAULTS["veritabani"],
                DB_DEFAULTS["kullanici"], DB_DEFAULTS["sifre"],
            )
            self._emirleri_yukle()
        except Exception as e:
            self._durum_lbl.setText(f"Bağlantı hatası: {e}")

    def _emirleri_yukle(self):
        if not self._conn:
            return
        self._yenile_btn.setEnabled(False)
        self._durum_lbl.setText("Emirler yükleniyor…")
        self._liste.clear()
        self._tum_emirler = []

        self._emirler_thread = _EmirlerThread(self._conn)
        self._emirler_thread.bitti.connect(self._emirler_geldi)
        self._emirler_thread.hata.connect(self._hata)
        self._emirler_thread.start()

    def _emirler_geldi(self, emirler: list[dict]):
        self._tum_emirler = emirler
        self._yenile_btn.setEnabled(True)
        self._durum_lbl.setText(f"{len(emirler)} emir yüklendi")
        self._filtrele()

    def _filtrele(self):
        self._liste.clear()
        durum_filtre = self._durum_combo.currentData()
        arama = self._ara_kutu.text().strip().lower()

        from PyQt5.QtGui import QColor
        gosterilenler = 0
        for e in self._tum_emirler:
            if durum_filtre and durum_filtre != 0 and e.get("DurumId") != durum_filtre:
                continue
            kodu = (e.get("Kodu") or "").lower()
            acik = (e.get("Aciklama") or "").lower()
            if arama and arama not in kodu and arama not in acik:
                continue

            did      = e.get("DurumId", 0)
            d_etiket = DURUM_ETIKET.get(did, f"Durum {did}")
            aciklama = e.get("Aciklama") or ""
            tarih    = e.get("EmirTarihi") or ""
            item = QListWidgetItem(
                f"{e.get('Kodu', '')}\n"
                f"{tarih}  [{d_etiket}]  •  {aciklama[:50]}"
            )
            item.setSizeHint(item.sizeHint().__class__(0, 52))
            item.setBackground(QColor(DURUM_RENK.get(did, "#FFFFFF")))
            item.setData(Qt.UserRole, e)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self._liste.addItem(item)
            gosterilenler += 1

        self._liste_ozet.setText(f"{gosterilenler} emir gösteriliyor")

    # ── Seçim olayları ────────────────────────────────────────────────────────

    def _emir_odak_degisti(self, current: QListWidgetItem | None, _prev):
        """Odaklanan (current) emir için sağ paneli güncelle."""
        if current is None:
            self._secili_emir = None
            self._kart_kodu.setText("—")
            self._kart_tarih.setText("—")
            self._kart_durum.setText("—")
            self._kart_aciklama.setText("—")
            self._tablo.setRowCount(0)
            self._tablo_ozet.setText("")
            return

        emir = current.data(Qt.UserRole)
        self._secili_emir = emir
        did = emir.get("DurumId", 0)
        self._kart_kodu.setText(emir.get("Kodu", ""))
        self._kart_tarih.setText(emir.get("EmirTarihi", ""))
        self._kart_durum.setText(DURUM_ETIKET.get(did, f"Durum {did}"))
        self._kart_aciklama.setText(emir.get("Aciklama") or "—")

        self._tablo.setRowCount(0)
        self._tablo_ozet.setText("Malzemeler yükleniyor…")

        self._malzeme_thread = _MalzemeThread(self._conn, emir.get("Id"))
        self._malzeme_thread.bitti.connect(self._malzeme_geldi)
        self._malzeme_thread.hata.connect(self._hata)
        self._malzeme_thread.start()

    def _secim_degisti(self, _item=None):
        """Checkbox değişince PDF butonunu ve etiketini güncelle."""
        n = self._tikli_sayisi()
        if n == 0:
            self._pdf_btn.setEnabled(False)
            self._pdf_btn.setText("📄 PDF Oluştur")
        elif n == 1:
            self._pdf_btn.setEnabled(True)
            self._pdf_btn.setText("📄 PDF Oluştur")
        else:
            self._pdf_btn.setEnabled(True)
            self._pdf_btn.setText(f"📄 PDF Oluştur ({n} emir)")

    def _tikli_sayisi(self) -> int:
        return sum(
            1 for i in range(self._liste.count())
            if self._liste.item(i).checkState() == Qt.Checked
        )

    def _tikli_emirler(self) -> list[dict]:
        return [
            self._liste.item(i).data(Qt.UserRole)
            for i in range(self._liste.count())
            if self._liste.item(i).checkState() == Qt.Checked
        ]

    def _malzeme_geldi(self, malzemeler: list[dict]):
        self._malzemeler = malzemeler
        self._tablo.setRowCount(len(malzemeler))
        for i, m in enumerate(malzemeler):
            miktar     = m.get("Miktar") or 0
            miktar_str = f"{float(miktar):,.4f}".rstrip("0").rstrip(".")
            for col, val in enumerate([m.get("Kodu", ""), m.get("Adi", ""), miktar_str]):
                it = QTableWidgetItem(val)
                if col == 2:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._tablo.setItem(i, col, it)
        self._tablo_ozet.setText(f"{len(malzemeler)} malzeme")
        self.durum_guncelle.emit(f"Malzeme listesi yüklendi — {len(malzemeler)} kalem")

    # ── PDF oluşturma ─────────────────────────────────────────────────────────

    def _pdf_olustur(self):
        tikli = self._tikli_emirler()
        if not tikli:
            return
        if len(tikli) == 1:
            self._tek_pdf(tikli[0])
        else:
            self._toplu_pdf(tikli)

    def _tek_pdf(self, emir: dict):
        kodu  = emir.get("Kodu", "emir")
        oneri = f"is_emri_{kodu}_{datetime.now().strftime('%Y%m%d')}.pdf"
        dosya, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet", oneri, "PDF Dosyası (*.pdf)"
        )
        if not dosya:
            return
        try:
            malzemeler = is_emri_malzeme_listesi(self._conn, emir["Id"])
            is_emri_pdf_olustur(dosya, emir, malzemeler)
            self.durum_guncelle.emit(f"PDF kaydedildi: {dosya}")
            QMessageBox.information(self, "Başarılı", f"PDF oluşturuldu:\n{dosya}")
        except Exception as e:
            QMessageBox.critical(self, "PDF Hatası", f"PDF oluşturulamadı:\n{e}")

    def _toplu_pdf(self, emirler: list[dict]):
        klasor = QFileDialog.getExistingDirectory(
            self, f"{len(emirler)} emir için kayıt klasörü seçin"
        )
        if not klasor:
            return

        self._pdf_btn.setEnabled(False)
        self._ilerleme_dlg = QProgressDialog(
            "PDF'ler oluşturuluyor…", "İptal", 0, len(emirler), self
        )
        self._ilerleme_dlg.setWindowTitle("Toplu PDF")
        self._ilerleme_dlg.setMinimumWidth(380)
        self._ilerleme_dlg.setWindowModality(Qt.WindowModal)
        self._ilerleme_dlg.show()

        self._toplu_thread = _TopluPDFThread(self._conn, emirler, klasor)
        self._toplu_thread.ilerleme.connect(self._toplu_ilerleme)
        self._toplu_thread.bitti.connect(self._toplu_bitti)
        self._toplu_thread.start()

    def _toplu_ilerleme(self, tamamlanan: int, toplam: int, dosya_adi: str):
        if self._ilerleme_dlg:
            self._ilerleme_dlg.setValue(tamamlanan)
            self._ilerleme_dlg.setLabelText(f"{dosya_adi} ({tamamlanan}/{toplam})")
        self.durum_guncelle.emit(f"PDF oluşturuldu: {dosya_adi} ({tamamlanan}/{toplam})")

    def _toplu_bitti(self, toplam: int, hatalar: list[str]):
        if self._ilerleme_dlg:
            self._ilerleme_dlg.close()
            self._ilerleme_dlg = None
        self._secim_degisti()  # butonu geri aç

        if hatalar:
            hata_str = "\n".join(hatalar)
            QMessageBox.warning(
                self, "Toplu PDF",
                f"{toplam - len(hatalar)}/{toplam} PDF oluşturuldu.\n\nHatalar:\n{hata_str}"
            )
        else:
            QMessageBox.information(
                self, "Toplu PDF",
                f"{toplam} PDF başarıyla oluşturuldu."
            )
        self.durum_guncelle.emit(f"Toplu PDF tamamlandı — {toplam} dosya")

    # ── Boş Form (Excel) ──────────────────────────────────────────────────────

    def _bos_form_olustur(self):
        dosya, _ = QFileDialog.getSaveFileName(
            self, "Boş Form Kaydet",
            f"is_emri_bos_{datetime.now().strftime('%Y%m%d')}.xlsx",
            "Excel Dosyası (*.xlsx)",
        )
        if not dosya:
            return
        try:
            from logic.excel_is_emri import bos_is_emri_excel_olustur
            bos_is_emri_excel_olustur(dosya)
            import subprocess
            subprocess.Popen(["start", "", dosya], shell=True)
            self.durum_guncelle.emit(f"Boş form oluşturuldu: {dosya}")
        except Exception as e:
            QMessageBox.critical(self, "Excel Hatası", f"Form oluşturulamadı:\n{e}")

    # ── Hata ─────────────────────────────────────────────────────────────────

    def _hata(self, mesaj: str):
        self._yenile_btn.setEnabled(True)
        self._durum_lbl.setText("Hata!")
        QMessageBox.critical(self, "Bağlantı Hatası", mesaj)
