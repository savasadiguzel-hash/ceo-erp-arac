from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QLabel, QPushButton, QFileDialog, QMessageBox,
)
from PyQt5.QtCore import Qt
from logic.excel import baglama_excel_kaydet
from ui.stil import etiket


class RaporSayfasi(QWidget):
    def __init__(self):
        super().__init__()
        self.sonuclar = []
        self._kur()

    def _kur(self):
        ana = QVBoxLayout(self)
        ana.setAlignment(Qt.AlignCenter)
        ana.setSpacing(14)

        self.ozet_grup = QGroupBox("Özet")
        self.ozet_grup.setMaximumWidth(540)
        ol = QVBoxLayout(self.ozet_grup)
        self.ozet_lbl = QLabel()
        self.ozet_lbl.setStyleSheet("font-size:13px;color:#212121;line-height:1.8;")
        ol.addWidget(self.ozet_lbl)

        excel_grup = QGroupBox("Excel Raporu (.xlsx)")
        excel_grup.setMaximumWidth(540)
        el = QVBoxLayout(excel_grup)
        bilgi = QLabel("Tek sayfa: stok kodu, fatura sayısı, birim fiyat, tedarikçi, atanan mamül.\n"
                       "Bağlananlar yeşil — atlandılar sarı renkte gösterilir.")
        bilgi.setStyleSheet("color:#555;font-size:11px;")
        self.excel_btn = QPushButton("📥  Excel Olarak Kaydet (.xlsx)")
        self.excel_btn.setStyleSheet("background:#2e7d32;color:white;border-radius:6px;"
                                     "padding:10px 30px;font-weight:bold;font-size:13px;")
        self.excel_btn.clicked.connect(self._excel_kaydet)
        el.addWidget(bilgi)
        el.addSpacing(6)
        el.addWidget(self.excel_btn, alignment=Qt.AlignCenter)

        geri_btn = QPushButton("← Ana Menü")
        geri_btn.setStyleSheet("background:#eceff1;color:#37474f;border:1px solid #cfd8dc;"
                               "border-radius:6px;padding:8px 20px;font-weight:bold;")
        geri_btn.clicked.connect(lambda: self.window().sayfa_gec(0))

        ana.addStretch()
        ana.addWidget(etiket("İşlem Tamamlandı ✓", "#1a237e", size=15), alignment=Qt.AlignCenter)
        ana.addWidget(self.ozet_grup,  alignment=Qt.AlignCenter)
        ana.addWidget(excel_grup,      alignment=Qt.AlignCenter)
        ana.addWidget(geri_btn,        alignment=Qt.AlignCenter)
        ana.addStretch()

    def goster(self, sonuclar: list):
        self.sonuclar = sonuclar
        baglandi = sum(1 for s in sonuclar if s["islem"] == "Bağlandı")
        atlandi  = sum(1 for s in sonuclar if s["islem"] == "Atlandı")
        self.ozet_lbl.setText(
            f"<b>İşlenen stok:</b>  {len(sonuclar)}<br>"
            f"<b>Mamül ağacına bağlanan:</b>  "
            f"<span style='color:#2e7d32;font-weight:bold;'>{baglandi}</span><br>"
            f"<b>Atlanan / bekleyen:</b>  <span style='color:#e65100;'>{atlandi}</span>"
        )

    def _excel_kaydet(self):
        dosya, _ = QFileDialog.getSaveFileName(
            self, "Excel Kaydet",
            f"ceo_erp_mamul_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            "Excel Dosyası (*.xlsx)")
        if not dosya:
            return
        try:
            baglama_excel_kaydet(dosya, self.sonuclar)
            QMessageBox.information(self, "Başarılı", f"Dosya kaydedildi:\n{dosya}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel kaydedilemedi:\n{e}")
