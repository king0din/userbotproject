# ============================================================
#  utils/logger.py — KingTG UserBot Service
# ============================================================
#  Tüm "print(...)" çağrılarının yerini alacak gerçek loglama.
#
#  KULLANIM:
#      from utils.logger import get_logger
#      log = get_logger(__name__)
#
#      log.info("Bot başladı")
#      log.warning("MongoDB yok, yerel dosyaya geçiliyor")
#      log.error("Plugin yüklenemedi", exc_info=True)   # <-- hata izini de yazar
#
#  NEDEN print() yerine bu?
#    • Her satırda zaman damgası + seviye + hangi modülden geldiği görünür.
#    • Hatalar (exc_info=True) tam "traceback" ile loglanır → neyin bozulduğu belli olur.
#    • Aynı anda hem konsola hem de logs/bot.log dosyasına yazar.
#    • İstersen seviyeyi LOG_LEVEL ortam değişkeniyle ayarlarsın (DEBUG/INFO/WARNING).
# ============================================================

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# --- Ayarlar ---------------------------------------------------------------
_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "bot.log")
_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()   # .env'e LOG_LEVEL=DEBUG yazıp detay görebilirsin

os.makedirs(_LOG_DIR, exist_ok=True)

# --- Konsolda renkli seviye (okumayı kolaylaştırır) ------------------------
_COLORS = {
    "DEBUG": "\033[90m",     # gri
    "INFO": "\033[94m",      # mavi
    "WARNING": "\033[93m",   # sarı
    "ERROR": "\033[91m",     # kırmızı
    "CRITICAL": "\033[95m",  # mor
}
_RESET = "\033[0m"


class _ColorFormatter(logging.Formatter):
    """Konsol için: seviyeyi renklendirir."""
    def format(self, record):
        color = _COLORS.get(record.levelname, "")
        record.levelname_colored = f"{color}{record.levelname:<8}{_RESET}"
        return super().format(record)


_CONSOLE_FMT = "%(asctime)s %(levelname_colored)s [%(name)s] %(message)s"
_FILE_FMT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
_DATE_FMT = "%H:%M:%S"

_configured = False


def _configure_root():
    """Kök logger'ı bir kez kur (handler'lar tekrar tekrar eklenmesin)."""
    global _configured
    if _configured:
        return

    root = logging.getLogger("kingtg")
    root.setLevel(getattr(logging, _LEVEL, logging.INFO))
    root.propagate = False

    # 1) Konsol handler (renkli)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(_ColorFormatter(_CONSOLE_FMT, datefmt=_DATE_FMT))
    root.addHandler(console)

    # 2) Dosya handler (dönen log: 5 MB x 3 dosya — disk dolmasın)
    try:
        file_handler = RotatingFileHandler(
            _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(_FILE_FMT, datefmt="%Y-%m-%d %H:%M:%S"))
        root.addHandler(file_handler)
    except Exception as e:
        # Dosyaya yazılamıyorsa en azından konsol çalışsın
        root.warning("Log dosyası açılamadı (%s). Sadece konsola yazılacak.", e)

    # Telethon'un aşırı ayrıntılı loglarını biraz kıs
    logging.getLogger("telethon").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str = "kingtg") -> logging.Logger:
    """
    Modülüne özel bir logger döndürür.

    Örnek:
        log = get_logger(__name__)
        log.info("merhaba")
    """
    _configure_root()
    # "kingtg.<modul>" altında topla ki tek noktadan yönetilsin
    if name and not name.startswith("kingtg"):
        name = f"kingtg.{name}"
    return logging.getLogger(name or "kingtg")


# ============================================================
#  print()'ten logger'a GEÇİŞ — hızlı kopya-yapıştır kılavuzu
# ------------------------------------------------------------
#  ESKİ:                              YENİ:
#    print(f"[DB] Kaydedildi")          log.info("Kaydedildi")
#    print(f"⚠️ Hata: {e}")             log.warning("Hata: %s", e)
#    try:                               try:
#        ...                                ...
#    except Exception as e:             except Exception:
#        print(f"Hata: {e}")                log.error("İşlem başarısız", exc_info=True)
#
#  ÖNEMLİ: 'except: pass' yerine MUTLAKA log.error(..., exc_info=True) kullan.
#          Hatayı görmek, onu gizlemekten her zaman iyidir.
# ============================================================
