"""CEO Barkod — ayrı program giriş noktası.

  python barkod_app.py

CEO ERP Araçları'ndan bağımsızdır; yalnız ortak DB katmanını (config.py, db/)
kullanır. Faz 1: Sorgula + Sayım (ERP'ye yazmaz).
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
