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
        _conn = pyodbc.connect(dsn, timeout=10)
    return _conn


def baglanti_kapat():
    global _conn
    if _conn:
        _conn.close()
        _conn = None


def test_baglanti(sunucu: str, veritabani: str, kullanici: str, sifre: str) -> tuple[bool, str]:
    """Bağlantı testler. (başarılı: bool, mesaj: str) döner."""
    try:
        conn = get_connection(sunucu, veritabani, kullanici, sifre)
        conn.cursor().execute("SELECT 1")
        return True, "Bağlantı başarılı."
    except Exception as e:
        return False, str(e)
