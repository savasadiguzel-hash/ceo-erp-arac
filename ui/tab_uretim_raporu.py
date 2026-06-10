"""tab_uretim_raporu.py — Üretim Eksik Stok Raporu sekmesi."""
import logging
from collections import defaultdict
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QMessageBox, QFileDialog,
    QProgressBar,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import uretim_eksik_stok

_RENK_EMIR     = QColor("#e8eaf6")   # üretim emri satırı arka plan (açık indigo)
_RENK_EKSIK_FG = QColor("#c62828")   # eksik miktar yazı rengi (kırmızı)
_RENK_TAMAM_FG = QColor("#2e7d32")   # fazla stok rengi (yeşil)

_BTN_MAVI = (
    "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1565c0,stop:1 #1976d2);"
    "color:white;border-radius:6px;padding:9px 22px;font-weight:bold;font-size:13px;border:none;"
)
_BTN_YESIL = (
    "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2e7d32,stop:1 #43a047);"
    "color:white;border-radius:6px;padding:9px 22px;font-weight:bold;font-size:13px;border:none;"
)
_BTN_PASIF = (
    "background:#bdbdbd;color:#757575;"
    "border-radius:6px;padding:9px 22px;font-weight:bold;font-size:13px;border:none;"
)

_KOLONLAR = [
    "Kodu",
    "Açıklama / Adı",
    "Emri Tarihi",
    "İhtiyaç Miktarı",
    "Mevcut Bakiye",
    "Eksik Miktar",
]


# ── Thread ────────────────────────────────────────────────────────────────────

class VeriThread(QThread):
    bitti = pyqtSignal(list)
    hata  = pyqtSignal(str)

    def __init__(self, conn):
        super().__init__()
        self.conn = conn

    def run(self):
        try:
            veri = uretim_eksik_stok(self.conn)
            self.bitti.emit(veri)
        except Exception as e:
            logging.error("UretimRaporuTab VeriThread: %s", e)
            self.hata.emit(str(e))


# ── Ana Sekme ─────────────────────────────────────────────────────────────────

class UretimRaporuTab(QWidget):
    durum_guncelle = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.conn = None
        self._veri: list[dict] = []
        self._thread = None
        self._kur()
        self._baglan_otomatik()

    def _kur(self):
        ana = QVBoxLayout(self)
        ana.setContentsMargins(16, 12, 16, 12)
        ana.setSpacing(10)

        # Başlık + butonlar
        ust = QHBoxLayout()
        baslik = QLabel("Üretim Eksik Stok Raporu")
        baslik.setFont(QFont("Segoe UI", 14, QFont.Bold))
        baslik.setStyleSheet("color:#1a237e;")
        ust.addWidget(baslik)
        ust.addStretch()

        self.durum_lbl = QLabel("Bağlanılıyor…")
        self.durum_lbl.setStyleSheet("color:#555;font-size:11px;")
        ust.addWidget(self.durum_lbl)

        self.yenile_btn = QPushButton("🔄  Yenile")
        self.yenile_btn.setStyleSheet(_BTN_MAVI)
        self.yenile_btn.setEnabled(False)
        self.yenile_btn.clicked.connect(self._getir)
        ust.addWidget(self.yenile_btn)

        self.excel_btn = QPushButton("📥  Excel'e Aktar")
        self.excel_btn.setStyleSheet(_BTN_PASIF)
        self.excel_btn.setEnabled(False)
        self.excel_btn.clicked.connect(self._excel_aktar)
        ust.addWidget(self.excel_btn)
        ana.addLayout(ust)

        # Açıklama
        aciklama = QLabel(
            "Durumu 'Devam Ediyor' olan üretim emirlerinin hat planındaki malzemeler için "
            "mevcut stok bakiyesi ihtiyaç miktarının altında olanları gösterir."
        )
        aciklama.setStyleSheet("color:#546e7a;font-size:11px;")
        aciklama.setWordWrap(True)
        ana.addWidget(aciklama)

        # İlerleme çubuğu
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(4)
        self.progress.setStyleSheet(
            "QProgressBar{border:none;background:#e8eaf6;border-radius:2px;}"
            "QProgressBar::chunk{background:#3f51b5;border-radius:2px;}"
        )
        self.progress.setVisible(False)
        ana.addWidget(self.progress)

        # Ağaç
        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(_KOLONLAR))
        self.tree.setHeaderLabels(_KOLONLAR)
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(False)
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #c5cae9;
                border-radius: 6px;
                background: white;
                font-size: 12px;
                gridline-color: #e8eaf6;
            }
            QTreeWidget::item { padding: 4px 6px; }
            QTreeWidget::item:selected { background: #e8eaf6; color: #1a237e; }
            QHeaderView::section {
                background: #3f51b5; color: white;
                padding: 7px 8px; font-weight: bold; font-size: 12px;
                border: none; border-right: 1px solid #5c6bc0;
            }
        """)
        h = self.tree.header()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        ana.addWidget(self.tree)

        # Alt özet
        self.ozet_lbl = QLabel("")
        self.ozet_lbl.setStyleSheet("color:#3949ab;font-size:12px;font-weight:bold;padding:2px;")
        ana.addWidget(self.ozet_lbl)

    def _baglan_otomatik(self):
        try:
            self.conn = get_connection(
                DB_DEFAULTS["sunucu"],
                DB_DEFAULTS["veritabani"],
                DB_DEFAULTS["kullanici"],
                DB_DEFAULTS["sifre"],
            )
            self.yenile_btn.setEnabled(True)
            self._getir()
        except Exception as e:
            logging.error("UretimRaporuTab baglanti: %s", e)
            self.durum_lbl.setText(f"Bağlantı hatası: {e}")
            self.durum_lbl.setStyleSheet("color:#c62828;font-size:11px;")

    def _getir(self):
        if not self.conn:
            return
        self.yenile_btn.setEnabled(False)
        self.excel_btn.setEnabled(False)
        self.excel_btn.setStyleSheet(_BTN_PASIF)
        self.tree.clear()
        self.ozet_lbl.setText("")
        self.progress.setVisible(True)
        self.durum_lbl.setText("Veriler çekiliyor…")
        self.durum_lbl.setStyleSheet("color:#1565c0;font-size:11px;")
        self.durum_guncelle.emit("Üretim eksik stok raporu yükleniyor…")

        self._thread = VeriThread(self.conn)
        self._thread.bitti.connect(self._veri_geldi)
        self._thread.hata.connect(self._hata)
        self._thread.start()

    def _veri_geldi(self, veri: list[dict]):
        self.progress.setVisible(False)
        self.yenile_btn.setEnabled(True)
        self._veri = veri
        self._tabloya_doldur(veri)
        self.durum_lbl.setText(f"Son güncelleme: {datetime.now().strftime('%H:%M:%S')}")
        self.durum_lbl.setStyleSheet("color:#2e7d32;font-size:11px;")
        self.durum_guncelle.emit(f"Üretim raporu: {len(veri)} eksik malzeme kaydı bulundu.")
        if veri:
            self.excel_btn.setEnabled(True)
            self.excel_btn.setStyleSheet(_BTN_YESIL)

    def _hata(self, mesaj: str):
        self.progress.setVisible(False)
        self.yenile_btn.setEnabled(True)
        self.durum_lbl.setText(f"Hata: {mesaj}")
        self.durum_lbl.setStyleSheet("color:#c62828;font-size:11px;")
        QMessageBox.critical(self, "Veri Çekme Hatası", mesaj)

    def _tabloya_doldur(self, veri: list[dict]):
        self.tree.clear()
        if not veri:
            self.ozet_lbl.setText("Tüm üretim emirleri için stok yeterli — eksik malzeme yok.")
            return

        # Emirlere göre grupla
        emirler: dict[int, list[dict]] = defaultdict(list)
        emir_bilgi: dict[int, dict] = {}
        for satir in veri:
            eid = satir['emir_id']
            emirler[eid].append(satir)
            if eid not in emir_bilgi:
                emir_bilgi[eid] = {
                    'kodu':      satir['emir_kodu'],
                    'aciklama':  satir['emir_aciklama'],
                    'tarih':     satir['emir_tarihi'],
                }

        emir_font = QFont("Segoe UI", 11, QFont.Bold)
        malz_font = QFont("Segoe UI", 11)

        toplam_malzeme = 0
        for eid, malzemeler in emirler.items():
            bi = emir_bilgi[eid]

            # Üretim emri satırı (parent)
            parent = QTreeWidgetItem(self.tree)
            parent.setText(0, bi['kodu'])
            parent.setText(1, bi['aciklama'])
            parent.setText(2, bi['tarih'])
            parent.setText(3, "")
            parent.setText(4, "")
            parent.setText(5, f"{len(malzemeler)} eksik kalem")
            for col in range(len(_KOLONLAR)):
                parent.setBackground(col, QBrush(_RENK_EMIR))
                parent.setFont(col, emir_font)
            parent.setForeground(0, QBrush(QColor("#1a237e")))
            parent.setForeground(5, QBrush(QColor("#c62828")))

            # Malzeme satırları (child)
            for m in malzemeler:
                child = QTreeWidgetItem(parent)
                child.setText(0, m['malzeme_kodu'])
                child.setText(1, m['malzeme_adi'])
                child.setText(2, "")
                child.setText(3, f"{m['ihtiyac']:.2f}")
                child.setText(4, f"{m['bakiye']:.2f}")
                child.setText(5, f"{m['eksik']:.2f}")
                child.setFont(0, malz_font)
                child.setFont(1, malz_font)
                child.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)
                child.setTextAlignment(4, Qt.AlignRight | Qt.AlignVCenter)
                child.setTextAlignment(5, Qt.AlignRight | Qt.AlignVCenter)
                # Eksik miktarı kırmızı
                child.setForeground(5, QBrush(_RENK_EKSIK_FG))
                # Sıfır bakiye = hiç yok → arka planı daha koyulaştır
                if m['bakiye'] <= 0:
                    child.setForeground(4, QBrush(QColor("#c62828")))
                toplam_malzeme += 1

            parent.setExpanded(True)

        emir_sayisi = len(emirler)
        self.ozet_lbl.setText(
            f"Toplam {emir_sayisi} üretim emrinde {toplam_malzeme} eksik malzeme kalemi bulundu."
        )

    def _excel_aktar(self):
        if not self._veri:
            return
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

            dosya, _ = QFileDialog.getSaveFileName(
                self, "Excel Olarak Kaydet", "uretim_eksik_stok.xlsx",
                "Excel Dosyaları (*.xlsx)"
            )
            if not dosya:
                return

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Eksik Stok Raporu"

            # Başlıklar
            basliklar = [
                "Emir Kodu", "Emri Tarihi", "Emri Açıklaması",
                "Malzeme Kodu", "Malzeme Adı",
                "İhtiyaç Miktarı", "Mevcut Bakiye", "Eksik Miktar",
            ]
            ws.append(basliklar)
            header_fill = PatternFill("solid", fgColor="3F51B5")
            header_font = Font(name="Segoe UI", bold=True, color="FFFFFF", size=11)
            thin = Side(border_style="thin", color="CCCCCC")
            for cell in ws[1]:
                cell.fill  = header_fill
                cell.font  = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = Border(bottom=Side(border_style="medium", color="FFFFFF"))

            # Veri satırları
            emir_fill  = PatternFill("solid", fgColor="E8EAF6")
            eksik_font = Font(name="Segoe UI", size=11, color="C62828")

            from collections import defaultdict
            emirler: dict[int, list] = defaultdict(list)
            emir_sira: list[int] = []
            for s in self._veri:
                if s['emir_id'] not in emirler:
                    emir_sira.append(s['emir_id'])
                emirler[s['emir_id']].append(s)

            for eid in emir_sira:
                malzemeler = emirler[eid]
                bi = malzemeler[0]

                # Emir özet satırı
                emir_satir = [
                    bi['emir_kodu'], bi['emir_tarihi'], bi['emir_aciklama'],
                    "", "", "", "", f"{len(malzemeler)} eksik kalem",
                ]
                ws.append(emir_satir)
                r = ws.max_row
                for c in range(1, len(basliklar) + 1):
                    cell = ws.cell(row=r, column=c)
                    cell.fill = emir_fill
                    cell.font = Font(name="Segoe UI", bold=True, size=11, color="1A237E")
                    cell.alignment = Alignment(vertical="center")

                # Malzeme satırları
                for m in malzemeler:
                    ws.append([
                        "", "", "",
                        m['malzeme_kodu'], m['malzeme_adi'],
                        round(m['ihtiyac'], 2),
                        round(m['bakiye'],  2),
                        round(m['eksik'],   2),
                    ])
                    r2 = ws.max_row
                    for c in [6, 7, 8]:
                        ws.cell(row=r2, column=c).alignment = Alignment(horizontal="right")
                    ws.cell(row=r2, column=8).font = eksik_font

            # Sütun genişlikleri
            genislikler = [20, 12, 50, 25, 45, 16, 16, 14]
            for i, g in enumerate(genislikler, 1):
                ws.column_dimensions[
                    openpyxl.utils.get_column_letter(i)
                ].width = g

            ws.freeze_panes = "A2"
            wb.save(dosya)
            QMessageBox.information(self, "Başarılı", f"Excel dosyası kaydedildi:\n{dosya}")
            self.durum_guncelle.emit(f"Excel kaydedildi: {dosya}")
        except Exception as e:
            logging.error("UretimRaporuTab excel: %s", e)
            QMessageBox.critical(self, "Excel Hatası", str(e))
