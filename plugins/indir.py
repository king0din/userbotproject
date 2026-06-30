# type: premium
# stars: 100
# days: 30
# title: Şarkı İndirici
# description: .indir <şarkı adı/link> → YouTube'dan şarkı indirir (kapak + isim ile)
# version: 1.0.0
# requires: yt-dlp
"""
.indir <şarkı adı veya YouTube linki>

Premium plugin: kullanıcının aktif aboneliği yoksa bota Yıldız faturası
gönderilir. Sahip ve sudo her zaman kullanabilir.

Sağlamlık:
  • Her indirme KENDİ uuid'li klasörüne yapılır → kullanıcılar/eşzamanlı
    istekler birbirine karışmaz; iş bitince (finally) klasör tamamen silinir.
  • Şarkı gönderimi kapalı/kısıtlı sohbetlerde ÇÖKMEZ; "bu sohbette gönderim
    kapalı" mesajı verir, olmazsa özelden bilgilendirir.
  • yt-dlp / ffmpeg yoksa, süre/boyut limiti aşılırsa nazikçe uyarır.
"""

import os
import shutil
import uuid
import asyncio
import time

from userbot.events import register
from userbot import CMD_HELP

try:
    from utils.logger import get_logger
    log = get_logger(__name__)
except Exception:
    import logging
    log = logging.getLogger("indir")

# Premium çerçeve (yoksa plugin yine çalışır, ücretsiz gibi davranır)
try:
    from utils.premium import (
        has_access, access_reason, get_config, send_star_invoice, prune_expired,
    )
    _PREMIUM = True
except Exception:
    _PREMIUM = False
    log.warning("premium çerçevesi yüklenemedi; .indir ücretsiz çalışacak", exc_info=True)

PLUGIN_NAME = "indir"

# --- İndirme dizini (istek başına izole) -----------------------------------
try:
    from userbot import TEMP_DOWNLOAD_DIRECTORY
except ImportError:
    TEMP_DOWNLOAD_DIRECTORY = "./downloads/"

INDIR_DIR = os.path.join(TEMP_DOWNLOAD_DIRECTORY, "indir")
try:
    os.makedirs(INDIR_DIR, exist_ok=True)
except Exception:
    pass

MAX_DURATION = 60 * 60                 # 1 saatten uzun içerik reddedilir
MAX_FILESIZE = 2 * 1024 * 1024 * 1024  # 2 GB (userbot gönderim limiti)
DL_TIMEOUT = 300                       # indirme için üst zaman sınırı (sn)

# Aynı kullanıcının üst üste indirme başlatmasını engelle (kaynak koruması)
_busy = set()


# --- Manager bot (Yıldız faturası göndermek için) --------------------------
def _get_bot():
    try:
        from userbot import bot as _b
        return _b
    except Exception:
        return None


# ============================================================
#  Yardımcılar
# ============================================================
def _req_dir(uid):
    """Kullanıcı + uuid ile benzersiz indirme klasörü (çakışma olmaz)."""
    d = os.path.join(INDIR_DIR, "%s_%s" % (uid, uuid.uuid4().hex[:8]))
    os.makedirs(d, exist_ok=True)
    return d


def _cleanup_dir(path):
    try:
        if path and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        log.debug("indir geçici klasör silinemedi: %s", path, exc_info=True)


def _humantime(seconds):
    try:
        seconds = int(seconds or 0)
    except Exception:
        return "?"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return "%d:%02d:%02d" % (h, m, s)
    return "%d:%02d" % (m, s)


def _find_thumb(req_dir, base_id):
    """İndirilen kapak görselini bul (jpg/png/webp)."""
    for f in os.listdir(req_dir):
        low = f.lower()
        if low.startswith(str(base_id)) and low.rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "webp"):
            return os.path.join(req_dir, f)
    # base eşleşmese de bir görsel varsa onu kullan
    for f in os.listdir(req_dir):
        if f.lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "webp"):
            return os.path.join(req_dir, f)
    return None


def _download(query, req_dir):
    """yt-dlp ile şarkı indir. SENKRON (asyncio.to_thread içinde çağrılır).
    Dönüş: dict(file, thumb, title, performer, duration) | hata fırlatır.
    """
    try:
        import yt_dlp
    except Exception:
        raise RuntimeError("yt-dlp kurulu değil (`pip install yt-dlp`).")

    is_url = query.startswith("http://") or query.startswith("https://")
    target = query if is_url else "ytsearch1:%s" % query

    base_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(req_dir, "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "writethumbnail": True,
        "ignoreerrors": False,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "source_address": "0.0.0.0",   # IPv4 zorla (bazı engelleri aşar)
        "retries": 3,
        "fragment_retries": 3,
        "extractor_retries": 2,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
            {"key": "FFmpegThumbnailsConvertor", "format": "jpg"},
        ],
    }

    # COOKIE KULLANMADAN indir. YouTube'un "bot değilsin" doğrulamasını aşmak için
    # farklı oynatıcı istemcilerini (android/ios/mweb/tv/web) sırayla dener;
    # gerçekten ses dosyası indiren ilk istemcide durur.
    _audio_exts = ("mp3", "m4a", "opus", "webm", "ogg")
    client_attempts = [
        ["android"],
        ["ios"],
        ["android", "ios", "mweb"],
        ["tv_embedded"],
        ["web"],
    ]
    info = None
    last_err = None
    for clients in client_attempts:
        # önceki yarım denemenin dosyalarını temizle
        for _f in list(os.listdir(req_dir)):
            try:
                os.remove(os.path.join(req_dir, _f))
            except Exception:
                pass
        opts = dict(base_opts)
        opts["extractor_args"] = {"youtube": {"player_client": clients}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(target, download=True)
        except Exception as e:
            last_err = e
            info = None
            continue
        # gerçekten ses indi mi? (metadata gelip indirme engellenebilir)
        got_audio = any(
            f.lower().rsplit(".", 1)[-1] in _audio_exts for f in os.listdir(req_dir)
        )
        if info and got_audio:
            break
        info = None  # dosya yoksa sonraki istemciyi dene

    # ytsearch sonucu 'entries' içinde gelir
    if info and "entries" in info:
        entries = [e for e in info["entries"] if e]
        if not entries:
            raise RuntimeError("Sonuç bulunamadı.")
        info = entries[0]

    if not info:
        raise RuntimeError(
            "İndirilemedi (YouTube engellemiş olabilir). Son hata: %s" % (last_err,))

    base_id = info.get("id", "")
    # Ses dosyasını bul (postprocessor mp3'e çevirir)
    audio = None
    for f in os.listdir(req_dir):
        low = f.lower()
        if low.startswith(str(base_id)) and low.rsplit(".", 1)[-1] in ("mp3", "m4a", "opus", "webm", "ogg"):
            audio = os.path.join(req_dir, f)
            if low.endswith(".mp3"):  # mp3'ü tercih et
                break
    if not audio:
        # base eşleşmediyse klasördeki ilk sesi al
        for f in os.listdir(req_dir):
            if f.lower().rsplit(".", 1)[-1] in ("mp3", "m4a", "opus", "webm", "ogg"):
                audio = os.path.join(req_dir, f)
                break
    if not audio or not os.path.exists(audio):
        raise RuntimeError("Ses dosyası indirilemedi.")

    return {
        "file": audio,
        "thumb": _find_thumb(req_dir, base_id),
        "title": info.get("title") or "Bilinmeyen",
        "performer": info.get("uploader") or info.get("channel") or info.get("artist") or "",
        "duration": info.get("duration") or 0,
        "webpage_url": info.get("webpage_url") or "",
    }


def _is_restricted_send_error(e):
    """Gönderim hatası 'bu sohbette gönderim kapalı/kısıtlı' türü mü?"""
    name = type(e).__name__.lower()
    msg = str(e).lower()
    name_keys = ("chatwriteforbidden", "chatsendmediaforbidden", "chatsendmedia",
                 "chatadminrequired", "userbannedinchannel", "channelprivate",
                 "chatrestricted", "mediaforbidden", "chatwrite")
    msg_keys = ("forbidden", "banned", "not have", "admin", "restrict",
                "cannot send", "can't send", "can't write", "cannot write",
                "send media", "not allowed", "private")
    return any(k in name for k in name_keys) or any(k in msg for k in msg_keys)


async def _safe_send_song(event, status, info, me):
    """Şarkıyı kapak + isim ile gönder; kısıtlı sohbette çökmeden bilgilendir.
    Dönüş: True başarılı, False kısıtlı/başarısız.
    """
    from telethon.tl.types import DocumentAttributeAudio

    title = info["title"]
    performer = info["performer"]
    dur = info["duration"]
    caption = "🎵 **%s**" % title
    if performer:
        caption += "\n👤 %s" % performer
    caption += "\n⏱️ %s" % _humantime(dur)

    attrs = [DocumentAttributeAudio(
        duration=int(dur or 0),
        title=title[:64],
        performer=(performer or "")[:64],
    )]

    send_kwargs = dict(
        caption=caption,
        attributes=attrs,
        supports_streaming=True,
    )
    if info.get("thumb") and os.path.exists(info["thumb"]):
        send_kwargs["thumb"] = info["thumb"]

    try:
        await event.client.send_file(event.chat_id, info["file"], **send_kwargs)
        try:
            await status.delete()
        except Exception:
            pass
        return True
    except Exception as e:
        if _is_restricted_send_error(e):
            log.info(".indir kısıtlı sohbet: %s", type(e).__name__)
            warn = "🚫 **Bu sohbette şarkı/medya gönderimi kapalı.**\n`%s`" % title
            # Önce durum mesajını uyarıya çevir
            try:
                await status.edit(warn)
            except Exception:
                # O da olmuyorsa kullanıcıya özelden bildir
                try:
                    await event.client.send_message(
                        "me", warn + "\n\n_(İndirilen şarkı bu sohbete gönderilemedi.)_"
                    )
                except Exception:
                    log.warning(".indir kısıtlı sohbet uyarısı da gönderilemedi", exc_info=True)
            return False
        # Beklenmeyen gönderim hatası
        log.warning(".indir gönderim hatası", exc_info=True)
        try:
            await status.edit("❌ Gönderim hatası: `%s`" % str(e)[:120])
        except Exception:
            pass
        return False


async def _require_access(event, me):
    """Premium kapısı. Erişim varsa True; yoksa kullanıcıyı bilgilendirip fatura
    gönderir ve False döndürür."""
    if not _PREMIUM:
        return True
    try:
        prune_expired()
    except Exception:
        pass
    status, cfg = access_reason(me.id, PLUGIN_NAME)
    if status == "ok":
        return True

    if status == "need_pay":
        stars = int(cfg.get("stars", 100))
        days = int(cfg.get("days", 30))
        title = cfg.get("title", "Şarkı İndirici")
        bot = _get_bot()
        sent = False
        if bot is not None:
            try:
                sent = await send_star_invoice(bot, me.id, PLUGIN_NAME)
            except Exception:
                log.warning(".indir fatura gönderilemedi", exc_info=True)
        if sent:
            await event.edit(
                "💎 **%s — Premium**\n\n"
                "Bu özelliği kullanmak için **%s ⭐ / %s gün** abonelik gerekir.\n"
                "📩 Bota **fatura gönderildi**, oradan ödeyip tekrar dene." % (title, stars, days)
            )
        else:
            await event.edit(
                "💎 **%s — Premium**\n\n"
                "Bu özellik **%s ⭐ / %s gün**. Ödeme için bota `/start` deyip "
                "premium menüsünden satın al." % (title, stars, days)
            )
        return False

    # need_grant (özel plugin, izin yok)
    await event.edit(
        "🔒 **Bu özel bir özellik.**\nErişim için yöneticiden izin iste."
    )
    return False


# ============================================================
#  Komut
# ============================================================
@register(outgoing=True, pattern=r"(?s)^\.indir(?: |$)(.*)")
async def indir_cmd(event):
    me = await event.client.get_me()
    if event.sender_id != me.id:
        return

    query = (event.pattern_match.group(1) or "").strip()
    if not query:
        await event.edit("🎵 **Kullanım:** `.indir <şarkı adı veya link>`")
        return

    # Premium kapısı
    if not await _require_access(event, me):
        return

    # Eşzamanlı indirme koruması
    if me.id in _busy:
        await event.edit("⏳ Zaten bir indirme sürüyor, bitince tekrar dene.")
        return
    _busy.add(me.id)

    req_dir = _req_dir(me.id)
    try:
        try:
            status = await event.edit("🔎 **Aranıyor / indiriliyor...**")
        except Exception:
            status = event

        # yt-dlp bloklayıcı → ayrı thread + zaman sınırı
        try:
            info = await asyncio.wait_for(
                asyncio.to_thread(_download, query, req_dir), timeout=DL_TIMEOUT
            )
        except asyncio.TimeoutError:
            await status.edit("⏱️ İndirme zaman aşımına uğradı, tekrar dene.")
            return
        except Exception as e:
            await status.edit("❌ İndirilemedi: `%s`" % str(e)[:160])
            return

        # Limit kontrolleri
        if info["duration"] and info["duration"] > MAX_DURATION:
            await status.edit(
                "⚠️ İçerik çok uzun (%s). En fazla %s indirilebilir." %
                (_humantime(info["duration"]), _humantime(MAX_DURATION))
            )
            return
        try:
            if os.path.getsize(info["file"]) > MAX_FILESIZE:
                await status.edit("⚠️ Dosya çok büyük (2 GB üstü), gönderilemez.")
                return
        except Exception:
            pass

        try:
            await status.edit("⬆️ **Gönderiliyor...**")
        except Exception:
            pass
        await _safe_send_song(event, status, info, me)

    finally:
        _cleanup_dir(req_dir)
        _busy.discard(me.id)


# ============================================================
#  Kullanıcı verisi temizliği (hesap silindiğinde / orphan)
# ============================================================
def cleanup_user_data(user_id, reason=None):
    """Bu kullanıcıya ait artık indirme klasörlerini sil."""
    try:
        if not os.path.isdir(INDIR_DIR):
            return
        prefix = "%s_" % user_id
        for name in os.listdir(INDIR_DIR):
            if name.startswith(prefix):
                _cleanup_dir(os.path.join(INDIR_DIR, name))
    except Exception:
        log.debug("indir cleanup_user_data hata", exc_info=True)


CMD_HELP.update({
    "indir":
    "💎 **Şarkı İndirici (Premium)**\n\n"
    "`.indir <şarkı adı>` → YouTube'dan şarkıyı indirip kapak + isim ile gönderir.\n"
    "`.indir <link>` → Belirli bir YouTube linkini indirir.\n\n"
    "Premium abonelik gerektirir (sahip/sudo muaf). Abonelik bitince tekrar "
    "fatura gönderilir. Kısıtlı/gönderimi kapalı sohbetlerde uyarı verir."
})
