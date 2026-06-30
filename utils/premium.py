# ============================================================
#  utils/premium.py — KingTG Premium / Abonelik Çerçevesi
# ============================================================
#  Pluginleri 3 tipte yönetir:
#    • genel   → herkes ücretsiz kullanır
#    • ozel    → sadece sahip + sudo + izin verilen kullanıcılar
#    • premium → kullanıcı Telegram Yıldızı (Stars/XTR) ödeyip
#                belirli gün boyunca abone olur; sahip her zaman erişir
#
#  Veriler data/ altında JSON olarak ATOMİK yazılır (bozulma olmaz):
#    • premium_config.json → {plugin: {type, stars, days, title}}
#    • premium_subs.json   → {user_id: {plugin: bitiş_zaman_damgası}}
#    • premium_ozel.json   → {plugin: [izinli_user_id, ...]}
#
#  Hem admin paneli (start.py) hem premium pluginler (indir.py)
#    `from utils.premium import ...` ile bu modülü kullanır.
# ============================================================

import os
import json
import time
import threading

try:
    from utils.logger import get_logger
    log = get_logger(__name__)
except Exception:  # logger yoksa sessiz fallback
    import logging
    log = logging.getLogger("premium")

# --- Sahip / sudo / veri dizini (config'e bağımlı ama güvenli) -------------
try:
    import config as _config
    _DATA_DIR = getattr(_config, "DATA_DIR", None) or "./data"
    OWNER_ID = int(getattr(_config, "OWNER_ID", 0) or 0)
    _SUDOS_FILE = getattr(_config, "SUDOS_FILE", os.path.join(_DATA_DIR, "sudos.json"))
    BOT_USERNAME = getattr(_config, "BOT_USERNAME", "") or ""
except Exception:
    _DATA_DIR = "./data"
    OWNER_ID = 0
    _SUDOS_FILE = os.path.join(_DATA_DIR, "sudos.json")
    BOT_USERNAME = ""

try:
    os.makedirs(_DATA_DIR, exist_ok=True)
except Exception:
    pass

CONFIG_FILE = os.path.join(_DATA_DIR, "premium_config.json")
SUBS_FILE = os.path.join(_DATA_DIR, "premium_subs.json")
OZEL_FILE = os.path.join(_DATA_DIR, "premium_ozel.json")
NOTIFY_FILE = os.path.join(_DATA_DIR, "premium_notify.json")

TYPES = ("genel", "ozel", "premium")
TYPE_LABELS = {"genel": "🌐 Genel", "ozel": "🔒 Özel", "premium": "💎 Premium"}

# Panelde hızlı seçim için hazır değerler
STAR_PRESETS = [25, 50, 100, 250, 500, 1000]
DAY_PRESETS = [("Haftalık", 7), ("Aylık", 30), ("3 Aylık", 90), ("Yıllık", 365)]

DAY_SECONDS = 86400

# Hatırlatma ayarları
REMIND_DAYS = [3, 1]      # bitişe şu kadar gün kala uyar (gün)
EXPIRE_GRACE_DAYS = 2     # bitişten sonra "durduruldu" bildirimi için bekleme

_LOCK = threading.RLock()


# ============================================================
#  Atomik JSON I/O
# ============================================================
def _load(path):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        log.warning("Premium dosyası okunamadı: %s", path, exc_info=True)
    return {}


def _save(path, data):
    """Geçici dosyaya yaz + os.replace ile atomik taşı (yarıda kalırsa bozulmaz)."""
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return True
    except Exception:
        log.warning("Premium dosyası yazılamadı: %s", path, exc_info=True)
        return False


# ============================================================
#  Sahip / sudo
# ============================================================
def is_owner(uid):
    return OWNER_ID and int(uid) == OWNER_ID


def _sudos():
    data = _load(_SUDOS_FILE)
    # sudos.json formatı projeye göre liste ya da {"sudos":[...]} olabilir
    if isinstance(data, dict):
        ids = data.get("sudos") or data.get("users") or list(data.keys())
    else:
        ids = data
    out = set()
    for x in (ids or []):
        try:
            out.add(int(x))
        except Exception:
            pass
    return out


def is_sudo(uid):
    try:
        return int(uid) in _sudos()
    except Exception:
        return False


def is_staff(uid):
    """Sahip veya sudo → premium/özel kısıtlamalarından muaf."""
    return is_owner(uid) or is_sudo(uid)


# ============================================================
#  Plugin yapılandırması
# ============================================================
def all_configs():
    with _LOCK:
        return _load(CONFIG_FILE)


def get_config(plugin):
    """Plugin yapılandırmasını döndürür (yoksa None)."""
    return all_configs().get(str(plugin))


def plugin_type(plugin):
    """Yapılandırılmamış plugin 'genel' (ücretsiz) sayılır."""
    cfg = get_config(plugin)
    t = (cfg or {}).get("type")
    return t if t in TYPES else "genel"


def is_configured(plugin):
    """Plugin için tip seçilmiş mi? (panel 'ekleyince sor' için)."""
    cfg = get_config(plugin)
    return bool(cfg and cfg.get("type") in TYPES)


def set_config(plugin, ptype=None, stars=None, days=None, title=None):
    """Plugin ayarlarını günceller (verilen alanları). Diğerleri korunur."""
    plugin = str(plugin)
    with _LOCK:
        data = _load(CONFIG_FILE)
        cfg = data.get(plugin, {})
        if ptype is not None:
            if ptype not in TYPES:
                raise ValueError("geçersiz tip: %s" % ptype)
            cfg["type"] = ptype
        if stars is not None:
            cfg["stars"] = max(1, int(stars))
        if days is not None:
            cfg["days"] = max(1, int(days))
        if title is not None:
            cfg["title"] = str(title)[:64]
        # Varsayılanlar (premium ise mantıklı default'lar)
        cfg.setdefault("type", ptype or "genel")
        cfg.setdefault("stars", 100)
        cfg.setdefault("days", 30)
        cfg.setdefault("title", plugin)
        data[plugin] = cfg
        _save(CONFIG_FILE, data)
        return cfg


def delete_config(plugin):
    plugin = str(plugin)
    with _LOCK:
        data = _load(CONFIG_FILE)
        if plugin in data:
            data.pop(plugin, None)
            _save(CONFIG_FILE, data)
            return True
    return False


# ============================================================
#  Abonelikler (premium)
# ============================================================
def _subs():
    return _load(SUBS_FILE)


def active_until(uid, plugin):
    """Aboneliğin bitiş zaman damgası (yoksa/expired ise 0)."""
    uid = str(uid)
    plugin = str(plugin)
    exp = _subs().get(uid, {}).get(plugin, 0)
    try:
        exp = int(exp)
    except Exception:
        exp = 0
    return exp if exp > time.time() else 0


def is_active(uid, plugin):
    return active_until(uid, plugin) > 0


def time_left(uid, plugin):
    """Kalan abonelik saniyesi (yoksa 0)."""
    exp = active_until(uid, plugin)
    return max(0, int(exp - time.time())) if exp else 0


def grant(uid, plugin, days):
    """Abonelik ver/uzat. Mevcut abonelik aktifse ÜZERİNE ekler."""
    uid = str(uid)
    plugin = str(plugin)
    days = max(1, int(days))
    with _LOCK:
        data = _load(SUBS_FILE)
        user = data.get(uid, {})
        now = int(time.time())
        base = user.get(plugin, 0)
        try:
            base = int(base)
        except Exception:
            base = 0
        start = base if base > now else now  # aktifse uzat, değilse şimdi başlat
        user[plugin] = start + days * DAY_SECONDS
        data[uid] = user
        _save(SUBS_FILE, data)
        log.info("Premium abonelik verildi: user=%s plugin=%s gün=%s", uid, plugin, days)
        return user[plugin]


def revoke(uid, plugin):
    uid = str(uid)
    plugin = str(plugin)
    with _LOCK:
        data = _load(SUBS_FILE)
        if uid in data and plugin in data[uid]:
            data[uid].pop(plugin, None)
            if not data[uid]:
                data.pop(uid, None)
            _save(SUBS_FILE, data)
            return True
    return False


def list_active_subs(plugin):
    """Bir plugin için aktif abonelikler: {user_id: bitiş_ts}."""
    plugin = str(plugin)
    now = time.time()
    out = {}
    for uid, plugins in _subs().items():
        exp = plugins.get(plugin, 0)
        try:
            exp = int(exp)
        except Exception:
            exp = 0
        if exp > now:
            out[uid] = exp
    return out


def prune_expired():
    """Süresi dolmuş abonelikleri temizler. 'Durduruldu' bildirimi gönderilene
    VEYA grace süresi geçene kadar bekler (hatırlatma döngüsü haber verebilsin)."""
    now = time.time()
    notify = _load(NOTIFY_FILE)
    with _LOCK:
        data = _load(SUBS_FILE)
        changed = False
        for uid in list(data.keys()):
            plugins = data[uid]
            for pl in list(plugins.keys()):
                try:
                    exp = int(plugins[pl])
                except Exception:
                    plugins.pop(pl, None); changed = True; continue
                if exp > now:
                    continue  # aktif, dokunma
                ns = notify.get(uid, {}).get(pl, {})
                notified = (ns.get("exp") == exp and "expired" in ns.get("sent", []))
                grace_passed = (now - exp) > EXPIRE_GRACE_DAYS * DAY_SECONDS
                if notified or grace_passed:
                    plugins.pop(pl, None); changed = True
            if not plugins:
                data.pop(uid, None); changed = True
        if changed:
            _save(SUBS_FILE, data)
    return changed


def expiry_str(ts):
    """Bitiş zaman damgasını okunur tarihe çevirir (gg.aa.yyyy)."""
    try:
        return time.strftime("%d.%m.%Y", time.localtime(int(ts)))
    except Exception:
        return "?"


def _notify_all():
    return _load(NOTIFY_FILE)


def due_reminders():
    """Şu an gönderilmesi gereken hatırlatmaları döndürür.
    Her öğe: dict(uid, plugin, kind, days_left, expiry, stars, days, title, mark)
      kind: 'soon' (yaklaşıyor) | 'expired' (bitti)
      mark: gönderildiğinde işaretlenecek etiket(ler) listesi
    Bildirim durumu bitiş zamanına bağlıdır → abonelik yenilenince otomatik sıfırlanır.
    """
    import math
    now = time.time()
    out = []
    subs = _subs()
    notify = _load(NOTIFY_FILE)
    cfgs = all_configs()
    changed = False
    for uid, plugins in list(subs.items()):
        for plugin, exp in list(plugins.items()):
            try:
                exp = int(exp)
            except Exception:
                continue
            cfg = cfgs.get(plugin) or {}
            if cfg.get("type") != "premium":
                continue  # sadece premium aboneliklere hatırlatma
            stars = int(cfg.get("stars", 100))
            days = int(cfg.get("days", 30))
            title = cfg.get("title", plugin)
            ns = notify.get(uid, {}).get(plugin, {})
            if ns.get("exp") != exp:                # yeni dönem → bildirimleri sıfırla
                ns = {"exp": exp, "sent": []}
                notify.setdefault(uid, {})[plugin] = ns
                changed = True
            sent = ns.get("sent", [])
            secs = exp - now
            dleft = secs / float(DAY_SECONDS)
            if secs > 0:
                active = [T for T in REMIND_DAYS if dleft <= T]
                unsent = [T for T in active if ("soon%d" % T) not in sent]
                if unsent:
                    out.append(dict(
                        uid=int(uid), plugin=plugin, kind="soon",
                        days_left=max(1, int(math.ceil(dleft))),
                        expiry=exp, stars=stars, days=days, title=title,
                        mark=["soon%d" % T for T in active],
                    ))
            else:
                if "expired" not in sent:
                    out.append(dict(
                        uid=int(uid), plugin=plugin, kind="expired",
                        days_left=0, expiry=exp, stars=stars, days=days,
                        title=title, mark=["expired"],
                    ))
    if changed:
        _save(NOTIFY_FILE, notify)
    return out


def mark_reminded(uid, plugin, tags):
    """Gönderilen hatırlatma etiketlerini kaydet (tekrar gönderilmesin)."""
    if isinstance(tags, str):
        tags = [tags]
    uid = str(uid)
    plugin = str(plugin)
    with _LOCK:
        notify = _load(NOTIFY_FILE)
        ns = notify.setdefault(uid, {}).setdefault(plugin, {})
        sent = ns.setdefault("sent", [])
        ch = False
        for t in (tags or []):
            if t not in sent:
                sent.append(t)
                ch = True
        if ch:
            _save(NOTIFY_FILE, notify)


# ============================================================
#  Özel (private) izin listesi
# ============================================================
def ozel_users(plugin):
    plugin = str(plugin)
    lst = _load(OZEL_FILE).get(plugin, [])
    out = []
    for x in (lst or []):
        try:
            out.append(int(x))
        except Exception:
            pass
    return out


def add_ozel(plugin, uid):
    plugin = str(plugin)
    uid = int(uid)
    with _LOCK:
        data = _load(OZEL_FILE)
        lst = data.get(plugin, [])
        if uid not in lst:
            lst.append(uid)
        data[plugin] = lst
        _save(OZEL_FILE, data)
        return lst


def remove_ozel(plugin, uid):
    plugin = str(plugin)
    uid = int(uid)
    with _LOCK:
        data = _load(OZEL_FILE)
        lst = data.get(plugin, [])
        if uid in lst:
            lst.remove(uid)
            data[plugin] = lst
            _save(OZEL_FILE, data)
            return True
    return False


# ============================================================
#  Erişim kontrolü  (pluginlerin çağıracağı ana fonksiyon)
# ============================================================
def has_access(uid, plugin):
    """Kullanıcı bu plugini kullanabilir mi?"""
    if is_staff(uid):
        return True
    t = plugin_type(plugin)
    if t == "genel":
        return True
    if t == "ozel":
        return int(uid) in ozel_users(plugin)
    if t == "premium":
        return is_active(uid, plugin)
    return True


def access_reason(uid, plugin):
    """(durum, config) döndürür.
    durum: 'ok' | 'need_pay' | 'need_grant'
      ok         → erişim var
      need_pay   → premium, ödeme gerek
      need_grant → özel, sahip izni gerek
    """
    cfg = get_config(plugin) or {}
    if has_access(uid, plugin):
        return "ok", cfg
    t = plugin_type(plugin)
    if t == "premium":
        return "need_pay", cfg
    if t == "ozel":
        return "need_grant", cfg
    return "ok", cfg


# ============================================================
#  Telegram Yıldızı (Stars / XTR) ödeme yardımcıları
# ============================================================
_PAYLOAD_PREFIX = "kingprem"


def make_payload(plugin, uid, days):
    """Fatura yükü (invoice payload) — ödeme dönünce ne verileceğini kodlar."""
    return ("%s:%s:%s:%s" % (_PAYLOAD_PREFIX, plugin, int(uid), int(days))).encode("utf-8")


def parse_payload(payload):
    """Ödeme yükünü çözer → (plugin, uid, days) ya da None."""
    try:
        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode("utf-8", "ignore")
        parts = payload.split(":")
        if len(parts) == 4 and parts[0] == _PAYLOAD_PREFIX:
            return parts[1], int(parts[2]), int(parts[3])
    except Exception:
        pass
    return None


async def send_star_invoice(bot, peer, plugin, title=None, description=None):
    """Belirtilen kişiye plugin için Yıldız (XTR) faturası gönderir.
    Telethon tembel import edilir (test ortamında modül yine yüklenebilsin).
    Başarılı/başarısız (bool) döndürür.
    """
    cfg = get_config(plugin)
    if not cfg or cfg.get("type") != "premium":
        return False
    stars = int(cfg.get("stars", 100))
    days = int(cfg.get("days", 30))
    title = (title or cfg.get("title") or plugin)[:32]
    description = description or (
        "%s — %s gün erişim (%s ⭐)" % (cfg.get("title", plugin), days, stars)
    )
    try:
        import random
        from telethon.tl import functions, types

        invoice = types.Invoice(
            currency="XTR",
            prices=[types.LabeledPrice(label=title, amount=stars)],
        )
        media = types.InputMediaInvoice(
            title=title,
            description=description[:255],
            invoice=invoice,
            payload=make_payload(plugin, getattr(peer, "user_id", peer), days)
            if isinstance(peer, int) else make_payload(plugin, 0, days),
            provider="",  # Stars (XTR) için sağlayıcı boş
            provider_data=types.DataJSON(data="{}"),
        )
        await bot(functions.messages.SendMediaRequest(
            peer=peer,
            media=media,
            message="",
            random_id=random.randrange(-(2 ** 63), 2 ** 63),
        ))
        return True
    except Exception:
        log.warning("Yıldız faturası gönderilemedi (plugin=%s)", plugin, exc_info=True)
        return False


def grant_from_payment(payload):
    """Ödeme yükünden aboneliği uygula. (plugin, uid, days) ya da None döndürür."""
    parsed = parse_payload(payload)
    if not parsed:
        return None
    plugin, uid, days = parsed
    grant(uid, plugin, days)
    return parsed
