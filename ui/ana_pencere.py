from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget, QStatusBar,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ui.stil                    import STIL
from ui.mamul_agaci_tab         import MamulAgaciTab
from ui.maliyet                 import MaliyetSayfasi
from ui.tab_sw                  import TabSW
from ui.tab_erp_aktar           import TabErpAktar
from ui.tab_satis_faturalari    import SatisFaturalariTab


class AnaPencere(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CEO ERP Araçları")
        self.setMinimumSize(960, 700)
        self.resize(1080, 780)
        self.setStyleSheet(STIL + _TAB_STIL)
        # Pencereyi her zaman ekran merkezinde aç
        from PyQt5.QtWidgets import QDesktopWidget
        geo = QDesktopWidget().availableGeometry()
        self.move(
            geo.left() + (geo.width()  - 1080) // 2,
            geo.top()  + (geo.height() - 780)  // 2,
        )

        # ── sekmeler ────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.setDocumentMode(True)

        self.mamul_tab   = MamulAgaciTab()
        self.maliyet_tab = MaliyetSayfasi()
        self.sw_tab      = TabSW()
        self.erp_tab     = TabErpAktar()
        self.satis_tab   = SatisFaturalariTab()

        self.tabs.addTab(self.mamul_tab,   "🔗  Mamül Ağacı")
        self.tabs.addTab(self.maliyet_tab, "💰  Maliyet")
        self.tabs.addTab(self.sw_tab,      "⚙  SW Kodlama")
        self.tabs.addTab(self.erp_tab,     "📦  Stok Kartı Aktar")
        self.tabs.addTab(self.satis_tab,   "🧾  Satış Faturaları")

        # ── sinyal bağlantıları ──────────────────────────────────────────────
        self.mamul_tab.durum_guncelle.connect(self._durum)
        self.sw_tab.durum_guncelle.connect(self._durum)
        self.erp_tab.durum_guncelle.connect(self._durum)
        self.satis_tab.durum_guncelle.connect(self._durum)

        # SW çalışması bitince Stok Kartı sekmesini güncelle
        self.sw_tab.kodlama_bitti.connect(self._sw_bitti)

        # ── merkez widget ────────────────────────────────────────────────────
        merkez = QWidget()
        lay = QVBoxLayout(merkez)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.tabs)
        self.setCentralWidget(merkez)

        # ── status bar ───────────────────────────────────────────────────────
        self.sb = QStatusBar()
        self.sb.setStyleSheet("background:#f5f5f5;color:#555;font-size:11px;")
        self.setStatusBar(self.sb)
        self.sb.showMessage("Kullanmak istediğiniz sekmeyi seçin.")

    def _durum(self, msg: str):
        self.sb.showMessage(msg)

    def _sw_bitti(self, success: bool, parts: list, _err: str):
        """SW Kodlama tamamlandığında Stok Kartı sekmesini günceller."""
        if success:
            kodlu = [p for p in parts if getattr(p, "erp_code", None)]
            self.erp_tab.set_kodlu_parcalar(kodlu)


_TAB_STIL = """
QTabWidget::pane {
    border: none;
    background: #f0f2f5;
}
QTabBar::tab {
    background: #e8eaf6;
    color: #3949ab;
    padding: 10px 22px;
    font-size: 13px;
    font-weight: bold;
    border: none;
    border-bottom: 3px solid transparent;
    min-width: 160px;
}
QTabBar::tab:selected {
    background: #f0f2f5;
    color: #1a237e;
    border-bottom: 3px solid #3f51b5;
}
QTabBar::tab:hover:!selected {
    background: #d1d5f0;
}
"""
