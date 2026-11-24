"""CEO Barkod — ayrı program giriş noktası.

  python barkod_app.py

CEO ERP Araçları'ndan bağımsızdır; yalnız ortak DB katmanını (config.py, db/)
kullanır. Modlar: Sorgula, Sayım, Giriş/Çıkış/Transfer (20/21/23), Etiket, Reçeteye ekle.
"""
import logging
import sys

from PyQt5.QtWidgets import QApplication


def main():
    logging.basicConfig(filename='barkod.log', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    from barkod.ui.ana_pencere import BarkodPencere
    w = BarkodPencere()
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
