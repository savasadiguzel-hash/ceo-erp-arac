import logging
import pyodbc
from contextlib import contextmanager
from config import USE_DEMO

_conn = None

_DSN = (
    "DRIVER={{ODBC Driver 17 for SQL Server}};"
    "SERVER={sunucu};DATABASE={veritabani};"
    "UID={kullanici};PWD={sifre};"
    "TrustServerCertificate=yes;"
)


def get_connection(sunucu: str, veritabani: str, kullanici: str, sifre: str):
    """Oturum boyunca tekil bağlantı döner. USE_DEMO=True ise None döner."""
    global _conn
    if USE_DEMO:
        return None
    if _conn is None:
        dsn = _DSN.format(sunucu=sunucu, veritabani=veritabani,
                          kullanici=kullanici, sifre=sifre)
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


@contextmanager
def cursor_ctx(conn):
    """
    Her sorgu çağrısında cursor'ı finally bloğunda kesinlikle kapatır.

        with cursor_ctx(conn) as cur:
            cur.execute("SELECT ...")
            return cur.fetchall()
    """
    cur = conn.cursor()
    try:
        yield cur
    except pyodbc.Error as e:
        logging.error("Sorgu hatasi: %s", e)
        raise
    finally:
        cur.close()


@contextmanager
def baglanti_ctx(sunucu: str, veritabani: str, kullanici: str, sifre: str):
    """
    Bağımsız tek-seferlik bağlantı için context manager.
    Oturum singleton'ını (_conn) etkilemez; finally'de her koşulda kapatılır.

        with baglanti_ctx(...) as conn:
            with cursor_ctx(conn) as cur:
                cur.execute("SELECT 1")
    """
    dsn = _DSN.format(sunucu=sunucu, veritabani=veritabani,
                      kullanici=kullanici, sifre=sifre)
    conn = None
    try:
        conn = pyodbc.connect(dsn, timeout=10)
        logging.info("baglanti_ctx: baglanti acildi sunucu=%s", sunucu)
        yield conn
    except pyodbc.Error as e:
        logging.error("baglanti_ctx pyodbc hatasi: %s", e)
        raise
    except Exception as e:
        logging.critical("baglanti_ctx beklenmeyen hata: %s", e)
        raise
    finally:
        if conn is not None:
            conn.close()
            logging.info("baglanti_ctx: baglanti kapatildi.")


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
    """Bağlantıyı test eder; singleton'ı etkilemez. (başarılı, mesaj) döner."""
    try:
        with baglanti_ctx(sunucu, veritabani, kullanici, sifre) as conn:
            with cursor_ctx(conn) as cur:
                cur.execute("SELECT 1")
        logging.info("Baglanti testi basarili: sunucu=%s", sunucu)
        return True, "Bağlantı başarılı."
    except pyodbc.Error as e:
        logging.error("Baglanti testi basarisiz: %s", e)
        return False, str(e)
    except Exception as e:
        logging.critical("Baglanti testinde beklenmeyen hata: %s", e)
        return False, str(e)
