import logging
import pyodbc
from config import USE_DEMO

_conn = None


def get_connection(sunucu: str, veritabani: str, kullanici: str, sifre: str):
    """Tekil bağlantı nesnesi döner. USE_DEMO=True ise None döner."""
    global _conn
    if USE_DEMO:
        return None
    if _conn is None:
        dsn = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={sunucu};DATABASE={veritabani};"
            f"UID={kullanici};PWD={sifre};"
            f"TrustServerCertificate=yes;"
        )
        try:
            _conn = pyodbc.connect(dsn, timeout=10)
            logging.info("Veritabani baglantisi kuruldu: sunucu=%s db=%s", sunucu, veritabani)
        except pyodbc.Error as e:
            logging.error("Veritabani baglanti hatasi: %s", e)
            raise
        except Exception as e:
            logging.critical("Beklenmeyen baglanti hatasi: %s", e)
            raise
    return _conn


def baglanti_kapat():
    global _conn
    if _conn:
        try:
            _conn.close()
            logging.info("Veritabani baglantisi kapatildi.")
        except Exception as e:
            logging.error("Baglanti kapatma hatasi: %s", e)
        finally:
            _conn = None


def test_baglanti(sunucu: str, veritabani: str, kullanici: str, sifre: str) -> tuple[bool, str]:
    """Bağlantı testler. (başarılı: bool, mesaj: str) döner."""
    try:
        conn = get_connection(sunucu, veritabani, kullanici, sifre)
        conn.cursor().execute("SELECT 1")
        logging.info("Baglanti testi basarili: sunucu=%s", sunucu)
        return True, "Bağlantı başarılı."
    except pyodbc.Error as e:
        logging.error("Baglanti testi basarisiz: %s", e)
        return False, str(e)
    except Exception as e:
        logging.critical("Baglanti testinde beklenmeyen hata: %s", e)
        return False, str(e)
