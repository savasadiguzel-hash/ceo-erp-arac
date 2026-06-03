from datetime import datetime, date as bugun_tipi
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QGridLayout,
    QLineEdit, QHBoxLayout, QCheckBox, QLabel,
)
from PyQt5.QtCore import Qt, QEvent, pyqtSignal
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
        self.sifre     = QLineEdit(DB_DEFAULTS.get("sifre", ""))
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

        tarih_grup = QGroupBox("Fatura Tarih Aralığı")
        tarih_grup.setMaximumWidth(460)
        tgrid = QGridLayout(tarih_grup)
        tgrid.setSpacing(10)
        self.bas_tarih = QLineEdit()
        self.bas_tarih.setPlaceholderText("GG.AA.YYYY")
        self.bit_tarih = QLineEdit()
        self.bit_tarih.setPlaceholderText("GG.AA.YYYY")
        hint = QLabel("Geçersiz veya gelecek tarih girilirse kutu temizlenir.")
        hint.setStyleSheet("color:#9e9e9e;font-size:10px;")
        tgrid.addWidget(etiket("Başlangıç:"), 0, 0)
        tgrid.addWidget(self.bas_tarih,       0, 1)
        tgrid.addWidget(etiket("Bitiş:"),     1, 0)
        tgrid.addWidget(self.bit_tarih,       1, 1)
        tgrid.addWidget(hint,                 2, 0, 1, 2)

        self.bas_tarih.editingFinished.connect(self._bas_validate)
        self.bit_tarih.editingFinished.connect(self._bit_validate)
        self.bit_tarih.installEventFilter(self)

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
        ana.addWidget(tarih_grup, alignment=Qt.AlignCenter)
        ana.addSpacing(6)
        ana.addWidget(baglan_btn, alignment=Qt.AlignCenter)
        ana.addWidget(demo_btn,   alignment=Qt.AlignCenter)
        ana.addSpacing(10)
        ana.addWidget(geri_btn,   alignment=Qt.AlignCenter)
        ana.addStretch()

    # ── Kısayol tuşları ──────────────────────────────────────────────────────
    def eventFilter(self, obj, event):
        if (obj is self.bit_tarih
                and event.type() == QEvent.KeyPress
                and event.key() == Qt.Key_N
                and event.modifiers() == Qt.ControlModifier):
            self.bit_tarih.setText(bugun_tipi.today().strftime("%d.%m.%Y"))
            return True
        return super().eventFilter(obj, event)

    # ── Tarih doğrulama ──────────────────────────────────────────────────────
    @staticmethod
    def _parse(metin: str):
        """DD.MM.YYYY veya DDMMYYYY → date; geçersiz/gelecekse None döner."""
        metin = metin.strip()
        if len(metin) == 8 and metin.isdigit():
            metin = f"{metin[:2]}.{metin[2:4]}.{metin[4:]}"
        try:
            dt = datetime.strptime(metin, "%d.%m.%Y").date()
            return None if dt > bugun_tipi.today() else dt
        except ValueError:
            return None

    def _bas_validate(self):
        dt = self._parse(self.bas_tarih.text())
        if dt is None:
            self.bas_tarih.clear()
            return
        self.bas_tarih.setText(dt.strftime("%d.%m.%Y"))
        bit_dt = self._parse(self.bit_tarih.text())
        if bit_dt is not None and dt > bit_dt:
            self.bit_tarih.setText(dt.strftime("%d.%m.%Y"))

    def _bit_validate(self):
        dt = self._parse(self.bit_tarih.text())
        if dt is None:
            self.bit_tarih.clear()
            return
        self.bit_tarih.setText(dt.strftime("%d.%m.%Y"))
        bas_dt = self._parse(self.bas_tarih.text())
        if bas_dt is not None and dt < bas_dt:
            self.bit_tarih.setText(bas_dt.strftime("%d.%m.%Y"))

    # ── Dışarıya açık metodlar ───────────────────────────────────────────────
    def secili_fatura_turleri(self) -> list[str]:
        turleri = []
        if self.cb_alis.isChecked():    turleri.append("Alış")
        if self.cb_masraf.isChecked():  turleri.append("Masraf")
        if self.cb_hizmet.isChecked():  turleri.append("Hizmet")
        if self.cb_ithalat.isChecked(): turleri.append("İthalat")
        return turleri

    def tarih_araligi(self) -> tuple[str, str] | None:
        """(bas_str, bit_str) veya eksik/geçersizse None döner."""
        bas = self._parse(self.bas_tarih.text())
        bit = self._parse(self.bit_tarih.text())
        if bas is None or bit is None:
            return None
        return bas.strftime("%d.%m.%Y"), bit.strftime("%d.%m.%Y")
