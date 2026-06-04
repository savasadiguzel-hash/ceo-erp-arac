import sys
import logging
import traceback

logging.basicConfig(
    filename="ceo_erp.log",
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
