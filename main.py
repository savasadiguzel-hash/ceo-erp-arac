import sys
import logging
from PyQt5.QtWidgets import QApplication
from ui.ana_pencere import AnaPencere

logging.basicConfig(
    filename="ceo_erp.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
    encoding="utf-8",
)

if __name__ == "__main__":
    logging.info("Uygulama baslatildi.")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    AnaPencere().show()
    sys.exit(app.exec_())
