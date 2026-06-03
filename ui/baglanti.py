from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QGridLayout,
    QLineEdit, QHBoxLayout, QCheckBox,
)
from PyQt5.QtCore import Qt, pyqtSignal
from config import DB_DEFAULTS
from ui.stil import etiket, buton


class BaglantiSayfasi(QWidget):
    devam = pyqtSignal()
    geri  = pyqtSignal()

    def __init__(self):
        super().__init__()
        ana = QVBoxLayout(self)
        ana.setAlignment(Qt.AlignCenter)
        ana.setSpacing(14)

        db_grup = QGroupBox("Veritabanı Bağlantısı")
        db_grup.setMaximumWidth(460)
        grid = QGridLayout(db_grup)
        grid.setSpacing(10)
        self.sunucu    = QLineEdit(DB_DEFAULTS["sunucu"])
        self.db_adi    = QLineEdit(DB_DEFAULTS["veritabani"])
        self.kullanici = QLineEdit(DB_DEFAULTS["kullanici"])
        self.sifre     = QLineEdit()
        self.sifre.setEchoMode(QLineEdit.Password)
        self.sifre.setPlaceholderText("••••••••")
        for i, (k, v) in enumerate([("Sunucu:", self.sunucu), ("Veritabanı:", self.db_adi),
                                     ("Kullanıcı:", self.kullanici), ("Şifre:", self.sifre)]):
            grid.addWidget(etiket(k), i, 0)
            grid.addWidget(v, i, 1)

        tur_grup = QGroupBox("Fatura Türleri (alış faturası kontrolü)")
        tur_grup.setMaximumWidth(460)
        tl = QHBoxLayout(tur_grup)
        self.cb_alis    = QCheckBox("Alış");    self.cb_alis.setChecked(True)
        self.cb_masraf  = QCheckBox("Masraf");  self.cb_masraf.setChecked(True)
        self.cb_hizmet  = QCheckBox("Hizmet");  self.cb_hizmet.setChecked(True)
        self.cb_ithalat = QCheckBox("İthalat"); self.cb_ithalat.setChecked(True)
        for cb in [self.cb_alis, self.cb_masraf, self.cb_hizmet, self.cb_ithalat]:
            tl.addWidget(cb)

        baglan_btn = buton("  Bağlan ve Taramayı Başlat  ", "#3f51b5", h=42, min_w=230)
        baglan_btn.clicked.connect(self.devam.emit)
        demo_btn = buton("Demo Modunda Çalıştır", "#eceff1", "#37474f")
        demo_btn.clicked.connect(self.devam.emit)
        geri_btn = buton("← Ana Menü", "#eceff1", "#37474f")
        geri_btn.clicked.connect(self.geri.emit)

        ana.addStretch()
        ana.addWidget(etiket("Mamül Ağacı Bağlantı Aracı", "#1a237e", size=15),
                      alignment=Qt.AlignCenter)
        ana.addSpacing(4)
        ana.addWidget(db_grup,    alignment=Qt.AlignCenter)
        ana.addWidget(tur_grup,   alignment=Qt.AlignCenter)
        ana.addSpacing(6)
        ana.addWidget(baglan_btn, alignment=Qt.AlignCenter)
        ana.addWidget(demo_btn,   alignment=Qt.AlignCenter)
        ana.addSpacing(10)
        ana.addWidget(geri_btn,   alignment=Qt.AlignCenter)
        ana.addStretch()

    def secili_fatura_turleri(self) -> list[str]:
        turleri = []
        if self.cb_alis.isChecked():    turleri.append("Alış")
        if self.cb_masraf.isChecked():  turleri.append("Masraf")
        if self.cb_hizmet.isChecked():  turleri.append("Hizmet")
        if self.cb_ithalat.isChecked(): turleri.append("İthalat")
        return turleri
