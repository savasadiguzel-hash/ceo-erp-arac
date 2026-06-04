import sys
import logging

# basicConfig burada çağrılmalı; aksi halde config.py gibi erken
# import edilen modüllerdeki log çağrıları dosyaya yazılmaz.
logging.basicConfig(
    filename="ceo_erp.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
    encoding="utf-8",
)

from PyQt5.QtWidgets import QApplication  # noqa: E402
from ui.ana_pencere import AnaPencere     # noqa: E402

if __name__ == "__main__":
    logging.info("Uygulama baslatildi.")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    AnaPencere().show()
    sys.exit(app.exec_())
