from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QProgressBar,
    QGroupBox, QGridLayout, QListWidget, QListWidgetItem,
    QPushButton, QLineEdit, QSplitter, QMessageBox, QAbstractItemView,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from db.sorgular import mamul_agaci_listesi, stoku_mamule_bagla
from ui.stil import etiket


class EslestirmeSayfasi(QWidget):
    rapor_signal = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.stoklar = []
        self.conn    = None
        self.idx     = 0
        self.sonuclar = []
        self.secilen_mamul = None
        self._mamul_listesi_cache = []
        self._kur()

    def _kur(self):
        ana = QVBoxLayout(self)
        ana.setSpacing(10)
        ana.setContentsMargins(16, 12, 16, 10)
        ana.addWidget(self._ilerleme())

        sp = QSplitter(Qt.Horizontal)
        sp.addWidget(self._stok_paneli())
        sp.addWidget(self._sag_panel())
        sp.setSizes([440, 460])
        sp.setStyleSheet("QSplitter::handle{background:#e0e0e0;width:2px;}")
        ana.addWidget(sp, stretch=1)
        ana.addWidget(self._buton_bar())

    def _ilerleme(self):
        frame = QFrame()
        frame.setStyleSheet("background:white;border-radius:8px;border:1.5px solid #c5cae9;")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(14, 8, 14, 8)
        self.ilerleme_lbl = QLabel("Stok 1 / ?")
        self.ilerleme_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.ilerleme_lbl.setStyleSheet("color:#3949ab;border:none;background:transparent;")
        self.prog = QProgressBar()
        self.prog.setRange(0, 1)
        self.prog.setValue(0)
        self.prog.setTextVisible(False)
        self.prog.setFixedHeight(10)
        self.kalan_lbl = QLabel("")
        self.kalan_lbl.setStyleSheet("color:#7986cb;border:none;background:transparent;font-size:11px;")
        self.kalan_lbl.setAlignment(Qt.AlignRight)
        lay.addWidget(self.ilerleme_lbl)
        lay.addWidget(self.prog, stretch=1)
        lay.addWidget(self.kalan_lbl)
        return frame

    def _stok_paneli(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(10)
        detay = QGroupBox("Stok Detayları")
        grid = QGridLayout(detay)
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(10)
        alanlar = [
            ("Stok Kodu:",      "stok_kodu",     "#c62828"),
            ("Stok Adı:",       "stok_adi",      "#212121"),
            ("Fatura Türleri:", "fatura_turleri","#212121"),
            ("Fatura Sayısı:",  "fatura_sayisi", "#212121"),
            ("Toplam Tutar:",   "toplam_tutar",  "#1b5e20"),
            ("İlk Fatura:",     "ilk_fatura",    "#212121"),
            ("Son Fatura:",     "son_fatura",    "#212121"),
            ("Tedarikçi:",      "tedarikci",     "#212121"),
        ]
        self.deger_lbls = {}
        for i, (et, key, renk) in enumerate(alanlar):
            e = etiket(et)
            e.setFixedWidth(105)
            v = QLabel("—")
            v.setWordWrap(True)
            v.setStyleSheet(f"color:{renk};")
            v.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            v.setCursor(Qt.IBeamCursor)
            if key == "stok_kodu":    v.setFont(QFont("Segoe UI", 13, QFont.Bold))
            if key == "toplam_tutar": v.setFont(QFont("Segoe UI", 12, QFont.Bold))
            grid.addWidget(e, i, 0, Qt.AlignTop)
            grid.addWidget(v, i, 1)
            self.deger_lbls[key] = v

        uyari = QLabel("⚠  Bu stok herhangi bir reçete veya mamül ağacında\n"
                       "   yer almıyor. Sağ taraftan atama yapınız.")
        uyari.setStyleSheet("color:#e65100;font-size:11px;background:#fff3e0;"
                            "border-radius:6px;padding:8px;border:1px solid #ffcc80;")
        uyari.setWordWrap(True)
        lay.addWidget(detay)
        lay.addWidget(uyari)
        lay.addStretch()
        return w

    def _sag_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 0, 0, 0)
        lay.setSpacing(10)

        mamul_grup = QGroupBox("Hangi Mamül Ağacına Eklenecek?")
        ml = QVBoxLayout(mamul_grup)
        ml.setSpacing(8)
        self.arama = QLineEdit()
        self.arama.setPlaceholderText("Mamül kodu veya adı ile filtrele...")
        self.arama.textChanged.connect(self._filtrele)
        self.mamul_widget = QListWidget()
        self.mamul_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.mamul_widget.itemClicked.connect(self._mamul_secildi)
        self.secilen_lbl = QLabel("Seçim yapılmadı")
        self.secilen_lbl.setStyleSheet("color:#9e9e9e;font-style:italic;padding:7px;"
                                       "background:#f5f5f5;border-radius:5px;font-size:12px;")
        self.secilen_lbl.setWordWrap(True)
        ml.addWidget(etiket("Ara:", bold=False, renk="#555"))
        ml.addWidget(self.arama)
        ml.addWidget(self.mamul_widget, stretch=1)
        ml.addWidget(self.secilen_lbl)

        gecmis_grup = QGroupBox("İşlem Geçmişi")
        gl = QVBoxLayout(gecmis_grup)
        self.gecmis_liste = QListWidget()
        self.gecmis_liste.setMaximumHeight(150)
        gl.addWidget(self.gecmis_liste)

        lay.addWidget(mamul_grup, stretch=1)
        lay.addWidget(gecmis_grup)
        return w

    def _mamul_doldur(self, filtre=""):
        self.mamul_widget.clear()
        ft = filtre.lower().strip()
        for kod, ad in self._mamul_listesi_cache:
            if ft and ft not in kod.lower() and ft not in ad.lower():
                continue
            item = QListWidgetItem(f"  {kod}   {ad}")
            item.setData(Qt.UserRole, (kod, ad))
            self.mamul_widget.addItem(item)

    def _filtrele(self, txt):
        self.secilen_mamul = None
        self._sifirla_secim()
        self._mamul_doldur(txt)

    def _mamul_secildi(self, item):
        kod, ad = item.data(Qt.UserRole)
        self.secilen_mamul = (kod, ad)
        self.secilen_lbl.setText(f"✓  {kod} — {ad}")
        self.secilen_lbl.setStyleSheet("color:#2e7d32;font-weight:bold;padding:7px;"
                                       "background:#e8f5e9;border-radius:5px;font-size:12px;")

    def _sifirla_secim(self):
        self.secilen_mamul = None
        self.secilen_lbl.setText("Seçim yapılmadı")
        self.secilen_lbl.setStyleSheet("color:#9e9e9e;font-style:italic;padding:7px;"
                                       "background:#f5f5f5;border-radius:5px;font-size:12px;")

    def _buton_bar(self):
        frame = QFrame()
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)

        self.geri_btn = QPushButton("← Geri")
        self.geri_btn.setStyleSheet("background:#eceff1;color:#37474f;border:1px solid #cfd8dc;"
                                    "border-radius:6px;padding:8px 20px;font-weight:bold;")
        self.geri_btn.clicked.connect(self._geri)

        atla_btn = QPushButton("⊘  Şimdilik Atla")
        atla_btn.setStyleSheet("background:#fff3e0;color:#e65100;border:1px solid #ffcc80;"
                               "border-radius:6px;padding:8px 20px;font-weight:bold;")
        atla_btn.clicked.connect(self._atla)

        kaydet_btn = QPushButton("✓  Mamüle Bağla ve İleri")
        kaydet_btn.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3f51b5,stop:1 #5c6bc0);"
            "color:white;border-radius:6px;padding:9px 28px;font-weight:bold;font-size:13px;")
        kaydet_btn.clicked.connect(self._kaydet)

        lay.addWidget(self.geri_btn)
        lay.addStretch()
        lay.addWidget(atla_btn)
        lay.addWidget(kaydet_btn)
        return frame

    def baslat(self, conn, stoklar: list):
        self.conn    = conn
        self.stoklar = stoklar
        self.idx     = 0
        self.sonuclar = []
        self.secilen_mamul = None
        self.gecmis_liste.clear()
        self.prog.setRange(0, max(len(stoklar), 1))
        self._mamul_listesi_cache = mamul_agaci_listesi(conn)
        self._goster()

    def _goster(self):
        n = len(self.stoklar)
        if self.idx >= n:
            self.rapor_signal.emit(self.sonuclar)
            return
        s = self.stoklar[self.idx]
        for key, w in self.deger_lbls.items():
            w.setText(str(s.get(key, "—")))
        self.arama.clear()
        self._sifirla_secim()
        self._mamul_doldur()
        self.ilerleme_lbl.setText(f"Stok {self.idx + 1} / {n}")
        self.prog.setValue(self.idx + 1)
        self.kalan_lbl.setText(f"{n - self.idx} stok bekliyor")
        self.geri_btn.setEnabled(self.idx > 0)

    def _kaydet(self):
        if not self.secilen_mamul:
            QMessageBox.warning(self, "Uyarı", "Lütfen sağ listeden bir mamül ağacı seçin.")
            return
        kod, ad = self.secilen_mamul
        s = self.stoklar[self.idx]
        stoku_mamule_bagla(self.conn, s["stok_kodu"], kod)
        self.sonuclar.append({**s, "mamul_kodu": kod, "mamul_adi": ad, "islem": "Bağlandı"})
        item = QListWidgetItem(f"✓  {s['stok_kodu']}  →  {kod} ({ad})")
        item.setForeground(QColor("#2e7d32"))
        self.gecmis_liste.insertItem(0, item)
        self.idx += 1
        self._goster()

    def _atla(self):
        s = self.stoklar[self.idx]
        self.sonuclar.append({**s, "mamul_kodu": "—", "mamul_adi": "—", "islem": "Atlandı"})
        item = QListWidgetItem(f"⊘  {s['stok_kodu']}  →  Atlandı")
        item.setForeground(QColor("#e65100"))
        self.gecmis_liste.insertItem(0, item)
        self.idx += 1
        self._goster()

    def _geri(self):
        if self.idx > 0:
            self.idx -= 1
            if self.sonuclar:
                self.sonuclar.pop()
            if self.gecmis_liste.count() > 0:
                self.gecmis_liste.takeItem(0)
            self._goster()
