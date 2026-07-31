# KingTG UserBot - Sticker (Çıkartma) Plugin
# Yanıtlanan resim / video / GIF'i otomatik olarak Telegram çıkartmasına çevirir.
# requires: ffmpeg (video/GIF için)
#
# description: Yanıtladığın resmi, videoyu veya GIF'i otomatik çıkartmaya çevirir
# author: @KingTG
# version: 1.0.0
"""
Bir resmi, videoyu veya GIF'i yanıtlayıp komutu yazmanız yeterli — gerisi otomatik.

🔧 Komutlar: .stic, .sticker
🚨 Tür: #eğlence #araç

Komutlar hakkında:
.stic  → Yanıtladığınız medyayı Telegram çıkartmasına çevirir ve gönderir.
.sticker → .stic ile aynıdır.

Her şey otomatiktir:
 • Boyut Telegram'ın çıkartma ölçüsüne (bir kenarı tam 512px) göre ayarlanır.
 • Videolar sessize alınır, 30 FPS'e düşürülür ve WEBM (VP9) yapılır.
 • 3 saniyeden uzun videolar otomatik hızlandırılıp 3 saniyeye indirilir.
 • Dosya boyutu Telegram sınırının altına inene kadar otomatik optimize edilir.
 • Resimler 512x512 WEBP çıkartmaya dönüştürülür.

Emoji seçmek isterseniz komutun yanına yazın:
Örnek: .stic 😎   → çıkartmanın emojisi 😎 olur (varsayılan: 🔥)

Not: Grupta çıkartma gönderimi kapalıysa uyarı verilir ve oluşturulan çıkartma
Kayıtlı Mesajlar'a gönderilir, emeğiniz boşa gitmez.
"""

import asyncio
import os
import shutil
import sys
import time

from telethon.tl.types import (
    DocumentAttributeFilename,
    DocumentAttributeImageSize,
    DocumentAttributeSticker,
    DocumentAttributeVideo,
    InputStickerSetEmpty,
)
from telethon.errors import (
    ChatAdminRequiredError,
    ChatSendMediaForbiddenError,
    ChatSendStickersForbiddenError,
    ChatWriteForbiddenError,
    FloodWaitError,
    MediaEmptyError,
    SlowModeWaitError,
    StickerDocumentInvalidError,
    StickerVideoBigError,
    StickerVideoNowebmError,
    UserBannedInChannelError,
)

from userbot.events import register
from userbot.cmdhelp import CmdHelp

try:
    from userbot import TEMP_DOWNLOAD_DIRECTORY
except ImportError:
    TEMP_DOWNLOAD_DIRECTORY = "./downloads/"


# ==========================================================
# TELEGRAM ÇIKARTMA SINIRLARI (resmî)
# ==========================================================
SIDE = 512                     # bir kenar TAM 512 olmalı
MAX_VIDEO_BYTES = 256 * 1024   # video çıkartma: en fazla 256 KB
MAX_IMAGE_BYTES = 512 * 1024   # statik çıkartma: en fazla 512 KB
MAX_DURATION = 2.9             # en fazla 3 sn (2.9 güvenlik payı)
MAX_FPS = 30

# Davranış ayarları
SPEEDUP_LIMIT = 10.0           # bu süreye kadar hızlandırılır, üstü kırpılır
MAX_INPUT_MB = 60              # bundan büyük dosyayı indirmeye kalkma
FFMPEG_TIMEOUT = 120           # tek bir ffmpeg çağrısı için saniye
JOB_TIMEOUT = 300              # tüm iş için saniye
MAX_ENCODE_TRIES = 4           # boyut tutturma denemesi
MAX_CONCURRENT = 2             # sunucuyu korumak için aynı anda ffmpeg sayısı
DEFAULT_EMOJI = "🔥"

# Aynı anda çok iş açılmasın (sunucu koruması + kullanıcı başına kilit)
_ffmpeg_slots = asyncio.Semaphore(MAX_CONCURRENT)
_busy_users = set()

_FFMPEG_CACHE = {}


# ==========================================================
# FFMPEG BULMA (Windows/Linux uyumlu)
# ==========================================================
def _find_exe(name):
    """ffmpeg/ffprobe'u PATH, imageio, yaygın Windows yolları ve bot klasöründe ara."""
    if name in _FFMPEG_CACHE:
        return _FFMPEG_CACHE[name]

    found = shutil.which(name) or shutil.which(name + ".exe")

    if not found and name == "ffmpeg":
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and os.path.isfile(exe):
                found = exe
        except Exception:
            pass

    if not found:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        adaylar = [
            os.path.join(base, "bin", name),
            os.path.join(base, "bin", name + ".exe"),
            os.path.join(base, "ffmpeg", "bin", name + ".exe"),
            os.path.join(os.getcwd(), name + ".exe"),
            r"C:\ffmpeg\bin\%s.exe" % name,
            r"C:\Program Files\ffmpeg\bin\%s.exe" % name,
            os.path.join(os.path.dirname(sys.executable), name + ".exe"),
        ]
        for a in adaylar:
            if os.path.isfile(a):
                found = a
                break

    _FFMPEG_CACHE[name] = found
    return found


async def _run(args, timeout=FFMPEG_TIMEOUT):
    """ffmpeg'i ASENKRON çalıştır (event loop'u asla bloklama)."""
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, err.decode("utf-8", "replace")
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        return -9, "TIMEOUT"
    except FileNotFoundError:
        return -2, "FFMPEG_YOK"
    except Exception as e:
        return -1, str(e)


# ==========================================================
# YARDIMCILAR
# ==========================================================
def _target_dims(w, h):
    """Bir kenarı TAM 512, diğeri oranı koruyan ÇİFT sayı yap."""
    if not w or not h or w <= 0 or h <= 0:
        return SIDE, SIDE
    if w >= h:
        nw = SIDE
        nh = int(round(h * SIDE / w))
        nh -= nh % 2
        nh = max(2, min(nh, SIDE))
    else:
        nh = SIDE
        nw = int(round(w * SIDE / h))
        nw -= nw % 2
        nw = max(2, min(nw, SIDE))
    return nw, nh


def _scale_filter(w, h):
    """Ölçek filtresi. Ölçüler biliniyorsa kesin değer, bilinmiyorsa
    (ffprobe yoksa) oranı koruyan otomatik ifade kullanılır."""
    if w and h and w > 0 and h > 0:
        nw, nh = _target_dims(w, h)
        return "scale=%d:%d:flags=lanczos" % (nw, nh)
    return ("scale=%d:%d:force_original_aspect_ratio=decrease:flags=lanczos,"
            "scale=trunc(iw/2)*2:trunc(ih/2)*2" % (SIDE, SIDE))


async def _probe(path):
    """(w, h, süre, alfa_var_mı). Önce ffprobe, yoksa ffmpeg çıktısından tahmin."""
    probe = _find_exe("ffprobe")
    if probe:
        try:
            proc = await asyncio.create_subprocess_exec(
                probe, "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,pix_fmt:format=duration",
                "-of", "default=nw=1", path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, _e = await asyncio.wait_for(proc.communicate(), timeout=30)
            data = {}
            for line in out.decode("utf-8", "replace").splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    data[k.strip()] = v.strip()
            w = int(float(data.get("width") or 0))
            h = int(float(data.get("height") or 0))
            try:
                dur = float(data.get("duration") or 0)
            except ValueError:
                dur = 0.0
            pix = (data.get("pix_fmt") or "").lower()
            alpha = ("a" in pix and "yuva" in pix) or pix in ("rgba", "bgra", "argb",
                                                             "abgr", "pal8", "ya8")
            return w, h, dur, alpha
        except Exception:
            pass
    return 0, 0, 0.0, False


def _tg_meta(msg):
    """Telegram'ın kendi meta verisinden (w,h,süre) oku — ffprobe'suz, hızlı."""
    w = h = 0
    dur = 0.0
    try:
        if getattr(msg, "photo", None):
            sizes = [s for s in (msg.photo.sizes or []) if getattr(s, "w", None)]
            if sizes:
                big = max(sizes, key=lambda s: s.w * s.h)
                w, h = big.w, big.h
        doc = getattr(msg, "document", None)
        if doc:
            for a in (doc.attributes or []):
                if isinstance(a, DocumentAttributeVideo):
                    w, h = a.w or w, a.h or h
                    dur = float(a.duration or 0)
                elif isinstance(a, DocumentAttributeImageSize):
                    w, h = a.w or w, a.h or h
    except Exception:
        pass
    return w, h, dur


def _media_kind(msg):
    """Yanıtlanan medyanın türünü belirle."""
    if not msg:
        return None
    try:
        if getattr(msg, "sticker", None):
            return "sticker"
        if getattr(msg, "photo", None):
            return "image"
        if getattr(msg, "video_note", None) or getattr(msg, "video", None) \
                or getattr(msg, "gif", None):
            return "video"
        if getattr(msg, "voice", None) or getattr(msg, "audio", None):
            return "audio"
        doc = getattr(msg, "document", None)
        if doc:
            mime = (doc.mime_type or "").lower()
            if mime.startswith("video/") or mime in ("image/gif", "application/x-shockwave-flash"):
                return "video"
            if mime.startswith("image/"):
                return "image"
            if mime.startswith("audio/"):
                return "audio"
        if getattr(msg, "media", None):
            return "other"
    except Exception:
        pass
    return None


async def _safe_edit(event, text):
    """Mesajı düzenle; silinmişse/edit edilemiyorsa yanıt olarak gönder."""
    try:
        return await event.edit(text)
    except Exception:
        try:
            return await event.reply(text)
        except Exception:
            return None


# ==========================================================
# DÖNÜŞTÜRME
# ==========================================================
async def _to_webp(src, dst, w, h):
    """Resmi 512px WEBP çıkartmaya çevir. (hata_mesajı | None)"""
    ff = _find_exe("ffmpeg")
    if not ff:
        return "FFMPEG_YOK"
    olcek = _scale_filter(w, h)
    son_hata = None
    for q in (90, 80, 68, 55, 42, 30):
        rc, err = await _run([
            ff, "-y", "-hide_banner", "-loglevel", "error",
            "-i", src, "-frames:v", "1",
            "-vf", olcek,
            "-c:v", "libwebp", "-lossless", "0", "-q:v", str(q),
            "-preset", "picture", "-an", "-map_metadata", "-1",
            "-f", "webp", dst,
        ])
        if rc != 0 or not os.path.exists(dst):
            son_hata = err
            continue
        if os.path.getsize(dst) <= MAX_IMAGE_BYTES:
            return None
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return None if os.path.getsize(dst) <= MAX_IMAGE_BYTES else "BOYUT"
    return son_hata or "DONUSTURULEMEDI"


async def _cikti_olculeri(dst, bilgi, w, h):
    """Üretilen çıkartmanın GERÇEK ölçülerini bilgiye yaz.

    Bu şart: Telethon webm için ölçüyü okuyamazsa
    DocumentAttributeVideo(1x1, 0sn) yer tutucusu ekliyor ve çıkartma
    bozuk görünüyor. Doğru değerleri açıkça göndererek bunu eziyoruz.
    """
    ow, oh, odur, _a = await _probe(dst)
    if not ow or not oh:
        ow, oh = _target_dims(w, h)
    bilgi["w"], bilgi["h"] = ow, oh
    bilgi["dur"] = odur or min(bilgi.get("dur") or MAX_DURATION, MAX_DURATION)
    return bilgi


async def _to_webm(src, dst, w, h, dur, alpha, workdir):
    """Videoyu/GIF'i WEBM(VP9) çıkartmaya çevir.

    Dönen: (hata_mesajı|None, bilgi_sözlüğü)
    bilgi: {"speed": x, "trim": bool, "dur": çıkış_süresi}
    """
    ff = _find_exe("ffmpeg")
    if not ff:
        return "FFMPEG_YOK", {}

    bilgi = {"speed": 1.0, "trim": False, "dur": dur or MAX_DURATION}

    # --- süre stratejisi -------------------------------------------------
    filtreler = []
    if dur and dur > MAX_DURATION:
        if dur <= SPEEDUP_LIMIT:
            # 3-10 sn: hızlandırıp 3 saniyeye sığdır (izlenebilir kalır)
            speed = dur / MAX_DURATION
            filtreler.append("setpts=PTS/%.6f" % speed)
            bilgi["speed"] = speed
        else:
            # 10 sn üstü: 10x+ hızlandırma izlenemez olur -> ilk 3 sn'yi al
            bilgi["trim"] = True
        bilgi["dur"] = MAX_DURATION
    filtreler.append(_scale_filter(w, h))
    filtreler.append("fps=%d" % MAX_FPS)
    vf = ",".join(filtreler)
    pix = "yuva420p" if alpha else "yuv420p"

    # --- 1. aşama: hızlı ara dosya (yeniden denemeler ucuzlasın) ---------
    # Alfa (şeffaflık) varsa x264 kullanılamaz -> doğrudan kodla.
    enc_src, enc_vf = src, vf
    ara = None
    if not alpha:
        ara = os.path.join(workdir, "_ara.mp4")
        rc, _err = await _run([
            ff, "-y", "-hide_banner", "-loglevel", "error",
            "-i", src, "-t", "%.2f" % MAX_DURATION, "-vf", vf,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16",
            "-pix_fmt", "yuv420p", "-an", "-sn", "-dn", "-f", "mp4", ara,
        ])
        if rc == 0 and os.path.exists(ara) and os.path.getsize(ara) > 0:
            enc_src, enc_vf = ara, None
        else:
            ara = None

    # --- 2. aşama: ölçüme dayalı VP9 (tek geçişte oturur, gerekirse ayarlar)
    hedef = int(MAX_VIDEO_BYTES * 0.93)
    cikis_sure = max(0.2, min(bilgi["dur"], MAX_DURATION))
    br = int(hedef * 8 / cikis_sure / 1000)
    br = max(60, min(br, 800))

    son_hata = None
    try:
        for deneme in range(MAX_ENCODE_TRIES):
            komut = [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", enc_src]
            if enc_vf:
                komut += ["-t", "%.2f" % MAX_DURATION, "-vf", enc_vf]
            komut += [
                "-c:v", "libvpx-vp9", "-pix_fmt", pix,
                "-b:v", "%dk" % br, "-crf", str(min(30 + deneme * 8, 63)),
                "-deadline", "good", "-cpu-used", "5", "-row-mt", "1",
                "-an", "-sn", "-dn", "-map_metadata", "-1",
                "-f", "webm", dst,
            ]
            rc, err = await _run(komut)
            if rc != 0 or not os.path.exists(dst):
                son_hata = err
                break
            boyut = os.path.getsize(dst)
            if boyut <= MAX_VIDEO_BYTES:
                return None, await _cikti_olculeri(dst, bilgi, w, h)
            # Ölçülen boyuta göre bir sonraki bitrate'i hesapla (hızlı yakınsar)
            br = max(40, int(br * (hedef / boyut) * 0.88))
    finally:
        if ara and os.path.exists(ara):
            try:
                os.remove(ara)
            except Exception:
                pass

    if os.path.exists(dst) and 0 < os.path.getsize(dst) <= MAX_VIDEO_BYTES:
        return None, await _cikti_olculeri(dst, bilgi, w, h)
    if os.path.exists(dst) and os.path.getsize(dst) > MAX_VIDEO_BYTES:
        return "BOYUT", bilgi
    return son_hata or "DONUSTURULEMEDI", bilgi


# ==========================================================
# GÖNDERME
# ==========================================================
async def _send_sticker(client, entity, path, emoji, video, reply_to=None, bilgi=None):
    """Çıkartmayı gerçek sticker olarak gönder.

    ÖNEMLİ: webm için DocumentAttributeVideo'yu ölçüleriyle birlikte AÇIKÇA
    veriyoruz. Aksi halde Telethon dosyayı okuyamayıp 1x1 / 0 sn yer tutucusu
    ekliyor ve çıkartma karşı tarafta bozuk görünüyor.
    """
    ad = "sticker.webm" if video else "sticker.webp"
    attrs = [DocumentAttributeFilename(ad)]
    if video:
        bilgi = bilgi or {}
        vw = int(bilgi.get("w") or SIDE)
        vh = int(bilgi.get("h") or SIDE)
        vd = float(bilgi.get("dur") or MAX_DURATION)
        attrs.append(DocumentAttributeVideo(
            duration=min(max(vd, 0.1), MAX_DURATION),
            w=vw, h=vh,
            round_message=False,
            supports_streaming=False,
        ))
    attrs.append(DocumentAttributeSticker(alt=emoji or DEFAULT_EMOJI,
                                          stickerset=InputStickerSetEmpty()))
    return await client.send_file(
        entity,
        file=path,
        mime_type="video/webm" if video else "image/webp",
        attributes=attrs,
        force_document=False,
        reply_to=reply_to,
    )


def _hata_metni(e):
    """Telethon hatasını anlaşılır Türkçe uyarıya çevir."""
    if isinstance(e, ChatSendStickersForbiddenError):
        return ("🚫 **Bu sohbette çıkartma gönderimi kapalı.**\n"
                "Grup yöneticileri çıkartmaları kısıtlamış görünüyor.")
    if isinstance(e, ChatSendMediaForbiddenError):
        return ("🚫 **Bu sohbette medya gönderimi kapalı.**\n"
                "Grup ayarları medya paylaşımına izin vermiyor.")
    if isinstance(e, (ChatWriteForbiddenError, UserBannedInChannelError)):
        return "🚫 **Bu sohbete mesaj gönderemiyorsun.** (kısıtlanmış veya susturulmuşsun)"
    if isinstance(e, ChatAdminRequiredError):
        return "🚫 **Bu işlem için yönetici yetkisi gerekiyor.**"
    if isinstance(e, SlowModeWaitError):
        return ("🐌 **Yavaş mod aktif.**\n"
                "`%s` saniye sonra tekrar dene." % getattr(e, "seconds", "?"))
    if isinstance(e, FloodWaitError):
        return ("⏳ **Telegram hız sınırı.**\n"
                "`%s` saniye beklemen gerekiyor." % getattr(e, "seconds", "?"))
    if isinstance(e, (StickerVideoNowebmError, StickerDocumentInvalidError)):
        return ("❌ **Telegram bu dosyayı çıkartma olarak kabul etmedi.**\n"
                "Farklı bir medya ile dene.")
    if isinstance(e, StickerVideoBigError):
        return "❌ **Çıkartma dosyası Telegram için fazla büyük.** Daha kısa bir video dene."
    if isinstance(e, MediaEmptyError):
        return "❌ **Medya boş/geçersiz.** Dosya bozuk olabilir."
    return "❌ **Gönderilemedi:** `%s`" % (str(e)[:120] or type(e).__name__)


# ==========================================================
# ANA KOMUT
# ==========================================================
@register(outgoing=True, pattern=r"^\.stic(?:ker)?(?:\s+(\S+))?$")
async def sticker_yap(event):
    kullanici = None
    try:
        kullanici = (await event.client.get_me()).id
    except Exception:
        pass

    # Aynı kullanıcı üst üste çalıştırmasın (sunucu + çakışma koruması)
    if kullanici in _busy_users:
        await _safe_edit(event, "⏳ **Zaten bir çıkartma hazırlanıyor.** Bitmesini bekle.")
        return

    emoji = (event.pattern_match.group(1) or DEFAULT_EMOJI).strip()
    if len(emoji) > 8:          # yanlışlıkla uzun metin girilmişse
        emoji = DEFAULT_EMOJI

    kaynak = None
    try:
        kaynak = await event.get_reply_message()
    except Exception:
        kaynak = None
    # Yanıt yoksa komutun kendi mesajındaki medyayı kullan (resim + açıklama)
    if kaynak is None and getattr(event.message, "media", None):
        kaynak = event.message

    if kaynak is None:
        await _safe_edit(
            event,
            "🖼 **Çıkartma yapmak için bir medyayı yanıtla.**\n\n"
            "Kullanım: bir resmi/videoyu/GIF'i yanıtlayıp `.stic` yaz.\n"
            "Emoji seçmek için: `.stic 😎`")
        return

    tur = _media_kind(kaynak)
    if tur == "sticker":
        await _safe_edit(event, "ℹ️ **Bu zaten bir çıkartma.** Resim, video veya GIF yanıtla.")
        return
    if tur == "audio":
        await _safe_edit(event, "🎵 **Ses dosyası çıkartmaya çevrilemez.**\n"
                                "Resim, video veya GIF yanıtla.")
        return
    if tur not in ("image", "video"):
        await _safe_edit(event, "❌ **Desteklenmeyen medya.**\n"
                                "Sadece resim, video ve GIF çıkartma yapılabilir.")
        return

    # Boyut kontrolü — devasa dosyayı indirmeye kalkma
    try:
        gelen = getattr(kaynak, "file", None)
        boyut = getattr(gelen, "size", 0) or 0
        if boyut > MAX_INPUT_MB * 1024 * 1024:
            await _safe_edit(
                event,
                "📦 **Dosya çok büyük** (`%.0f MB`).\n"
                "Lütfen **3 ila 5 saniye** arası, daha küçük bir video yanıtla."
                % (boyut / 1024 / 1024))
            return
    except Exception:
        pass

    ff = _find_exe("ffmpeg")
    if tur == "video" and not ff:
        await _safe_edit(
            event,
            "⚙️ **ffmpeg bulunamadı.**\n"
            "Video/GIF çıkartma için sunucuda `ffmpeg` kurulu olmalı.\n"
            "(Resimler için de gereklidir.)")
        return
    if tur == "image" and not ff:
        await _safe_edit(event, "⚙️ **ffmpeg bulunamadı.** Çıkartma oluşturulamıyor.")
        return

    _busy_users.add(kullanici)
    calisma = os.path.join(TEMP_DOWNLOAD_DIRECTORY, "stickers", str(kullanici or 0),
                           str(int(time.time() * 1000)))
    indirilen = cikti = None
    try:
        os.makedirs(calisma, exist_ok=True)

        await _safe_edit(event, "⏳ **Medya indiriliyor...**")
        try:
            indirilen = await asyncio.wait_for(
                event.client.download_media(kaynak, file=calisma), timeout=JOB_TIMEOUT)
        except asyncio.TimeoutError:
            await _safe_edit(event, "⌛ **İndirme çok uzun sürdü.** Daha küçük bir dosya dene.")
            return
        if not indirilen or not os.path.exists(indirilen):
            await _safe_edit(event, "❌ **Medya indirilemedi.** Tekrar dene.")
            return

        # Ölçüler: önce Telegram meta (hızlı), eksikse ffprobe
        w, h, sure = _tg_meta(kaynak)
        alfa = False
        if not w or not h or (tur == "video" and not sure):
            pw, ph, psure, palfa = await _probe(indirilen)
            w = w or pw
            h = h or ph
            sure = sure or psure
            alfa = palfa
        else:
            _pw, _ph, _ps, alfa = await _probe(indirilen)
        if tur == "video" and (indirilen.lower().endswith(".gif")):
            alfa = True

        async with _ffmpeg_slots:
            if tur == "image":
                await _safe_edit(event, "🎨 **Çıkartma hazırlanıyor...**")
                cikti = os.path.join(calisma, "sticker.webp")
                hata = await asyncio.wait_for(
                    _to_webp(indirilen, cikti, w, h), timeout=JOB_TIMEOUT)
                bilgi = {}
            else:
                # Kullanıcıya süre bilgisi ver (istenen bilgilendirme)
                if sure and sure > MAX_DURATION:
                    if sure <= SPEEDUP_LIMIT:
                        await _safe_edit(
                            event,
                            "🎬 **Video 3 saniyeden uzun** (`%.1f sn`).\n"
                            "En iyi sonuç için **3 ila 5 saniye** arası bir video yanıtla.\n"
                            "⚡ Bu video otomatik **hızlandırılıp 3 saniyeye** indiriliyor..."
                            % sure)
                    else:
                        await _safe_edit(
                            event,
                            "🎬 **Video çok uzun** (`%.1f sn`).\n"
                            "Lütfen **3 ila 5 saniye** arası bir video yanıtla.\n"
                            "✂️ Şimdilik **ilk 3 saniyesi** kullanılıyor..." % sure)
                else:
                    await _safe_edit(event, "🎬 **Çıkartma hazırlanıyor...**")

                cikti = os.path.join(calisma, "sticker.webm")
                hata, bilgi = await asyncio.wait_for(
                    _to_webm(indirilen, cikti, w, h, sure, alfa, calisma),
                    timeout=JOB_TIMEOUT)

        if hata == "FFMPEG_YOK":
            await _safe_edit(event, "⚙️ **ffmpeg bulunamadı.** Çıkartma oluşturulamıyor.")
            return
        if hata == "TIMEOUT":
            await _safe_edit(event, "⌛ **Dönüştürme çok uzun sürdü.**\n"
                                    "Daha kısa (3-5 sn) bir video yanıtla.")
            return
        if hata == "BOYUT":
            await _safe_edit(
                event,
                "📦 **Çıkartma Telegram sınırına sığdırılamadı.**\n"
                "Lütfen **3 ila 5 saniye** arası, daha sade bir video yanıtla.")
            return
        if hata or not cikti or not os.path.exists(cikti) or os.path.getsize(cikti) == 0:
            await _safe_edit(event, "❌ **Dönüştürme başarısız.**\n"
                                    "Medya bozuk olabilir; başka bir dosya dene.")
            return

        # ---- gönder ----
        await _safe_edit(event, "📤 **Gönderiliyor...**")
        video = cikti.endswith(".webm")
        yanit = kaynak.id if kaynak.id != event.message.id else None
        try:
            await _send_sticker(event.client, event.chat_id, cikti, emoji, video,
                                yanit, bilgi)
            try:
                await event.delete()
            except Exception:
                await _safe_edit(event, "✅ **Çıkartma hazır!**")
            return
        except Exception as e:
            uyari = _hata_metni(e)
            # Sohbet çıkartmayı kabul etmiyorsa emeği boşa çıkarma:
            # Kayıtlı Mesajlar'a gönder ve kullanıcıyı bilgilendir.
            if isinstance(e, (ChatSendStickersForbiddenError, ChatSendMediaForbiddenError,
                              ChatWriteForbiddenError, UserBannedInChannelError,
                              ChatAdminRequiredError)):
                try:
                    await _send_sticker(event.client, "me", cikti, emoji, video, None, bilgi)
                    uyari += "\n\n💾 Çıkartma **Kayıtlı Mesajlar**'a gönderildi."
                except Exception:
                    pass
            await _safe_edit(event, uyari)
            return

    except asyncio.TimeoutError:
        await _safe_edit(event, "⌛ **İşlem zaman aşımına uğradı.**\n"
                                "Daha kısa (3-5 sn) bir video yanıtla.")
    except Exception as e:
        await _safe_edit(event, "❌ **Beklenmeyen hata:** `%s`" % (str(e)[:120] or type(e).__name__))
    finally:
        _busy_users.discard(kullanici)
        try:
            shutil.rmtree(calisma, ignore_errors=True)
        except Exception:
            pass


def cleanup_user_data(user_id, reason="disable"):
    """Plugin kapatılınca/çıkışta kullanıcının kilidini ve geçici dosyalarını temizle."""
    try:
        _busy_users.discard(user_id)
    except Exception:
        pass
    try:
        klasor = os.path.join(TEMP_DOWNLOAD_DIRECTORY, "stickers", str(user_id))
        if os.path.isdir(klasor):
            shutil.rmtree(klasor, ignore_errors=True)
    except Exception:
        pass


# ==========================================================
# CMDHELP
# ==========================================================
Help = CmdHelp('stic')
Help.add_command('stic', None,
                 'Yanıtlanan resmi/videoyu/GIF\'i otomatik çıkartmaya çevirir')
Help.add_command('stic <emoji>', None,
                 'Çıkartmayı belirtilen emoji ile oluşturur', '.stic 😎')
Help.add_command('sticker', None, '.stic komutunun aynısı')
Help.add_info('Otomatik çıkartma: 512px boyutlandırma, 3 sn sınırı, '
              'ses kaldırma ve boyut optimizasyonu tamamen otomatiktir.')
Help.add()
