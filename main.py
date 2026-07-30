import os
import sys
import logging
import traceback
from pathlib import Path

# Program Files altına kurulduğunda normal kullanıcı bu klasöre yazamaz;
# log dosyasını her zaman yazılabilir olan kullanıcıya özel klasöre koy.
if getattr(sys, "frozen", False):
    _LOG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CEO ERP Araclar"
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
else:
    _LOG_DIR = Path(__file__).parent

logging.basicConfig(
    filename=str(_LOG_DIR / "ceo_erp.log"),
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
    encoding="utf-8",
)

try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from ui.ana_pencere import AnaPencere
except Exception as e:
    logging.critical("Import hatasi: %s\n%s", e, traceback.format_exc())
    raise

if __name__ == "__main__":
    try:
        logging.info("Uygulama baslatildi.")
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        pencere = AnaPencere()
        pencere.show()
        logging.info("Pencere gosterildi.")
        sys.exit(app.exec_())
    except Exception as e:
        logging.critical("Pencere olusturma hatasi: %s\n%s", e, traceback.format_exc())
        try:
            QMessageBox.critical(None, "Hata", f"Uygulama başlatılamadı:\n\n{e}")
        except Exception:
            pass
        sys.exit(1)
