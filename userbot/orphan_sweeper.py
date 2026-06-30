"""Yetim veri temizleyici.

Pasifken (pluginleri yüklü değilken) silinen kullanıcıların artık veri
dosyalarını açılışta süpürür. Plugin'lerin `cleanup_user_data` hook'ları yalnızca
o an YÜKLÜ olan modüller için çalıştığından, kullanıcı pluginleri yüklenmeden
silinirse dosyaları geride kalır. Bu süpürücü o boşluğu kapatır.

NOT: Buradaki veri konumları pluginlerle SENKRON tutulmalıdır. Bir plugin kendi
depolama yolunu değiştirirse aşağıdaki listeleri de güncelle.
"""

import os
import json
import shutil

from utils.logger import get_logger

log = get_logger(__name__)

# Plugin'lerle birebir aynı idiom: userbot dışa aktarmıyorsa ./downloads/ kullanılır.
try:
    from userbot import TEMP_DOWNLOAD_DIRECTORY
except ImportError:
    TEMP_DOWNLOAD_DIRECTORY = "./downloads/"

# userbot/ ile plugins/ kardeş dizinler → proje kökü üzerinden plugins'e ulaş.
_PLUGINS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins"
)


def _json_stores():
    """str(user_id) anahtarlı JSON store'lar → [(etiket, dosya_yolu), ...]."""
    return [
        ("AFK durumu",        os.path.join(TEMP_DOWNLOAD_DIRECTORY, "afk_state.json")),
        ("Klon durumu",       os.path.join(TEMP_DOWNLOAD_DIRECTORY, "clon_state.json")),
        ("Ses tercihi",       os.path.join(_PLUGINS_DIR, "ses_voice.json")),
        ("OtoMsg görevleri",  os.path.join(_PLUGINS_DIR, "otomsg_tasks.json")),
    ]


def _user_photo_dir_roots():
    """Kullanıcı-başına alt dizinli (kök/{uid}/) foto klasörlerinin kök dizinleri."""
    return [
        os.path.join(TEMP_DOWNLOAD_DIRECTORY, "afk_profile"),
        os.path.join(TEMP_DOWNLOAD_DIRECTORY, "original_profile"),
    ]


def _sweep_json_store(label, path, valid):
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log.debug(f"{label} okunamadı, süpürme atlandı: {e}")
        return 0
    if not isinstance(data, dict):
        return 0
    orphans = [k for k in list(data.keys()) if str(k) not in valid]
    if not orphans:
        return 0
    for k in orphans:
        data.pop(k, None)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        log.warning(f"{label} yazılamadı, süpürme iptal: {e}")
        return 0
    log.info(f"{label}: {len(orphans)} yetim kayıt temizlendi")
    return len(orphans)


def _sweep_photo_dir_root(root, valid):
    if not os.path.isdir(root):
        return 0
    removed = 0
    try:
        for name in os.listdir(root):
            sub = os.path.join(root, name)
            if os.path.isdir(sub) and str(name) not in valid:
                shutil.rmtree(sub, ignore_errors=True)
                removed += 1
    except Exception as e:
        log.debug(f"foto dizini süpürülemedi ({root}): {e}")
        return 0
    if removed:
        log.info(f"{os.path.basename(root)}: {removed} yetim foto klasörü silindi")
    return removed


def sweep_orphans(valid_user_ids):
    """valid_user_ids DIŞINDAKİ tüm kullanıcı verilerini temizler.

    valid_user_ids: int veya str id'lerden oluşan iterable (veritabanında HÂLÂ
    var olan kullanıcılar). Bunların dışındaki tüm kayıt/klasör yetim sayılır.
    Toplam temizlenen öğe sayısını döndürür.
    """
    valid = set(str(u) for u in valid_user_ids if u is not None)
    total = 0
    for label, path in _json_stores():
        total += _sweep_json_store(label, path, valid)
    for root in _user_photo_dir_roots():
        total += _sweep_photo_dir_root(root, valid)
    if total:
        log.info(f"Yetim veri temizleme tamamlandı: toplam {total} öğe.")
    return total
