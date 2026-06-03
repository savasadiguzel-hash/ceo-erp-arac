from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QGridLayout,
    QLineEdit, QPushButton, QRadioButton, QButtonGroup, QDateEdit,
    QDoubleSpinBox, QScrollArea, QFrame, QCheckBox, QSizePolicy, QMessageBox, QFileDialog,
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont
from config import DB_DEFAULTS
from db.sorgular import bom_listesi
from logic.excel import maliyet_excel_kaydet
from ui.stil import etiket, buton, ayrac


class MaliyetSayfasi(QWidget):
    def __init__(self):
        super().__init__()
        self.conn = None
        self._mamul_satirlari: dict[str, tuple] = {}
        self._kur()

    def _kur(self):
        ana = QHBoxLayout(self)
        ana.setContentsMargins(16, 12, 16, 12)
        ana.setSpacing(16)
        ana.addWidget(self._sol_panel(), stretch=4)
        ana.addWidget(self._sag_panel(), stretch=5)

    def _sol_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        bas = QLabel("Maliyet Hesaplama")
        bas.setFont(QFont("Segoe UI", 13, QFont.Bold))
        bas.setStyleSheet("color:#1a237e;")
        lay.addWidget(bas)

        # Veritabanı
        db_grup = QGroupBox("Veritabanı Bağlantısı")
        dg = QGridLayout(db_grup)
        dg.setSpacing(8)
        self.m_sunucu    = QLineEdit(DB_DEFAULTS["sunucu"])
        self.m_db        = QLineEdit(DB_DEFAULTS["veritabani"])
        self.m_kullanici = QLineEdit(DB_DEFAULTS["kullanici"])
        self.m_sifre     = QLineEdit()
        self.m_sifre.setEchoMode(QLineEdit.Password)
        self.m_sifre.setPlaceholderText("••••••••")
        for i, (k, v) in enumerate([("Sunucu:", self.m_sunucu), ("Veritabanı:", self.m_db),
                                     ("Kullanıcı:", self.m_kullanici), ("Şifre:", self.m_sifre)]):
            dg.addWidget(etiket(k), i, 0)
            dg.addWidget(v, i, 1)
        lay.addWidget(db_grup)

        # Tarih aralığı
        tarih_grup = QGroupBox("Tarih Aralığı")
        tg = QGridLayout(tarih_grup)
        tg.setSpacing(8)
        self.tarih_bas = QDateEdit(QDate(2024, 1, 1))
        self.tarih_bas.setCalendarPopup(True)
        self.tarih_bas.setDisplayFormat("dd.MM.yyyy")
        self.tarih_bit = QDateEdit(QDate(2024, 3, 31))
        self.tarih_bit.setCalendarPopup(True)
        self.tarih_bit.setDisplayFormat("dd.MM.yyyy")
        tg.addWidget(etiket("Başlangıç:"), 0, 0)
        tg.addWidget(self.tarih_bas, 0, 1)
        tg.addWidget(etiket("Bitiş:"),     1, 0)
        tg.addWidget(self.tarih_bit, 1, 1)
        lay.addWidget(tarih_grup)

        # Maliyet yöntemi
        yontem_grup = QGroupBox("Maliyet Yöntemi")
        yg = QVBoxLayout(yontem_grup)
        self.metod_grup = QButtonGroup(self)
        for metin, deger_m in [("Ağırlıklı Ortalama", "WA"),
                                ("FIFO (İlk Giren İlk Çıkar)", "FIFO"),
                                ("LIFO (Son Giren İlk Çıkar)", "LIFO")]:
            rb = QRadioButton(metin)
            rb.setProperty("metod", deger_m)
            if deger_m == "WA":
                rb.setChecked(True)
            self.metod_grup.addButton(rb)
            yg.addWidget(rb)
        lay.addWidget(yontem_grup)
        lay.addStretch()

        alt = QHBoxLayout()
        geri_btn = QPushButton("← Ana Menü")
        geri_btn.setStyleSheet("background:#eceff1;color:#37474f;border:1px solid #cfd8dc;"
                               "border-radius:6px;padding:7px 16px;font-weight:bold;")
        geri_btn.clicked.connect(lambda: self.window().sayfa_gec(0))
        self.hesapla_btn = QPushButton("📊  Hesapla ve Excel'e Aktar")
        self.hesapla_btn.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2e7d32,stop:1 #43a047);"
            "color:white;border-radius:6px;padding:9px 20px;font-weight:bold;font-size:13px;")
        self.hesapla_btn.clicked.connect(self._hesapla)
        alt.addWidget(geri_btn)
        alt.addStretch()
        alt.addWidget(self.hesapla_btn)
        lay.addLayout(alt)
        return w

    def _sag_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        mamul_grup = QGroupBox("Mamüller ve İşçilik Tutarları")
        mg = QVBoxLayout(mamul_grup)

        btn_satir = QHBoxLayout()
        tum_sec = QPushButton("Tümünü Seç")
        tum_sec.setStyleSheet("background:#e8eaf6;color:#3949ab;border-radius:5px;"
                              "padding:5px 12px;font-size:11px;font-weight:bold;")
        tum_kaldir = QPushButton("Tümünü Kaldır")
        tum_kaldir.setStyleSheet("background:#fce4ec;color:#c62828;border-radius:5px;"
                                 "padding:5px 12px;font-size:11px;font-weight:bold;")
        tum_sec.clicked.connect(lambda: self._tum_sec(True))
        tum_kaldir.clicked.connect(lambda: self._tum_sec(False))
        btn_satir.addWidget(tum_sec)
        btn_satir.addWidget(tum_kaldir)
        btn_satir.addStretch()
        mg.addLayout(btn_satir)

        baslik_satir = QHBoxLayout()
        baslik_satir.addWidget(QLabel(""), stretch=1)
        lbl_iscilik = QLabel("İşçilik (₺)")
        lbl_iscilik.setStyleSheet("color:#7986cb;font-weight:bold;font-size:11px;")
        lbl_iscilik.setFixedWidth(110)
        lbl_iscilik.setAlignment(Qt.AlignCenter)
        baslik_satir.addWidget(lbl_iscilik)
        mg.addLayout(baslik_satir)
        mg.addWidget(ayrac())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background:white;")
        self.mamul_layout = QVBoxLayout(scroll_widget)
        self.mamul_layout.setSpacing(4)
        self.mamul_layout.setContentsMargins(4, 4, 4, 4)
        self.mamul_layout.addStretch()
        scroll.setWidget(scroll_widget)
        mg.addWidget(scroll, stretch=1)

        lay.addWidget(mamul_grup, stretch=1)

        self.durum_lbl = QLabel("")
        self.durum_lbl.setStyleSheet("color:#555;font-size:11px;padding:4px;")
        self.durum_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.durum_lbl)
        return w

    def baslat(self, conn):
        """Mamül listesini (yeniden) yükler."""
        self.conn = conn
        self._mamul_satirlari.clear()
        # stretch'i koru, diğerlerini temizle
        while self.mamul_layout.count() > 1:
            item = self.mamul_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        bom = bom_listesi(conn)
        for kod, veri in bom.items():
            self._mamul_satiri_ekle(kod, veri["ad"])

    def _mamul_satiri_ekle(self, kod: str, ad: str):
        satir = QFrame()
        satir.setStyleSheet("QFrame{background:white;border-radius:5px;}"
                            "QFrame:hover{background:#f5f5f5;}")
        satir_lay = QHBoxLayout(satir)
        satir_lay.setContentsMargins(4, 4, 4, 4)
        satir_lay.setSpacing(8)

        cb = QCheckBox(f"{kod}  —  {ad}")
        cb.setChecked(True)
        cb.setStyleSheet("font-size:12px;color:#212121;")
        cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        spin = QDoubleSpinBox()
        spin.setRange(0, 9_999_999)
        spin.setDecimals(2)
        spin.setSuffix(" ₺")
        spin.setValue(0.00)
        spin.setFixedWidth(110)
        spin.setAlignment(Qt.AlignRight)

        satir_lay.addWidget(cb, stretch=1)
        satir_lay.addWidget(spin)
        self.mamul_layout.insertWidget(self.mamul_layout.count() - 1, satir)
        self._mamul_satirlari[kod] = (cb, spin)

    def _tum_sec(self, durum: bool):
        for cb, _ in self._mamul_satirlari.values():
            cb.setChecked(durum)

    def _secili_metod(self) -> str:
        for btn_w in self.metod_grup.buttons():
            if btn_w.isChecked():
                return btn_w.property("metod")
        return "WA"

    def _hesapla(self):
        secili = [(kod, cb, spin)
                  for kod, (cb, spin) in self._mamul_satirlari.items()
                  if cb.isChecked()]
        if not secili:
            QMessageBox.warning(self, "Uyarı", "Lütfen en az bir mamül seçin.")
            return

        dosya, _ = QFileDialog.getSaveFileName(
            self, "Excel Kaydet",
            f"ceo_erp_maliyet_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            "Excel Dosyası (*.xlsx)")
        if not dosya:
            return

        metod = self._secili_metod()
        bas   = self.tarih_bas.date().toString("yyyy-MM-dd")
        bit   = self.tarih_bit.date().toString("yyyy-MM-dd")
        bas_g = self.tarih_bas.date().toString("dd.MM.yyyy")
        bit_g = self.tarih_bit.date().toString("dd.MM.yyyy")

        try:
            maliyet_excel_kaydet(dosya, self.conn, secili, metod, bas, bit, bas_g, bit_g)
            self.durum_lbl.setText(f"✓  Rapor oluşturuldu: {dosya}")
            self.durum_lbl.setStyleSheet("color:#2e7d32;font-size:11px;padding:4px;")
            QMessageBox.information(self, "Başarılı", f"Maliyet raporu kaydedildi:\n{dosya}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel oluşturulamadı:\n{e}")
