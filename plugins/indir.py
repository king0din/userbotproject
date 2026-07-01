# YouTube İndirici (premium) — .müzik / .video / .ytara
# type: premium
# stars: 100
# days: 30
# title: YouTube İndirici
# requires: yt-dlp
"""
YouTube'dan müzik/video indirir (KingTG premium plugin).

Önemli:
- Cookie GEREKTİRMEZ: tv/ios/android/mweb istemcileri sırayla denenir
  (YouTube'un "bot değilsin" doğrulamasını cookie olmadan aşmaya çalışır).
- İsteğe bağlı: bir cookies.txt varsa OTOMATİK kullanılır (zorunlu değil).
- Hız: tek yt-dlp çağrısında arama + indirme birlikte yapılır (eski sürüm
  önce bilgi sonra indirme diye İKİ çağrı yapıyordu — o yüzden yavaştı).
"""
import os
import re
import json
import asyncio

from userbot.events import register
from userbot import CMD_HELP

try:
    from userbot import TEMP_DOWNLOAD_DIRECTORY
except ImportError:
    TEMP_DOWNLOAD_DIRECTORY = "./downloads/"

if not os.path.exists(TEMP_DOWNLOAD_DIRECTORY):
    try:
        os.makedirs(TEMP_DOWNLOAD_DIRECTORY)
    except Exception:
        pass

YT_REGEX = r"(https?://)?(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/.+"
MAX_AUDIO_MB = 50
MAX_VIDEO_MB = 2000


def is_youtube_url(text):
    return bool(re.match(YT_REGEX, text or ""))


def _find_cookies():
    """Varsa cookies dosyasını bul (zorunlu değil). Birçok yere ve isme bakar."""
    names = ("cookies.txt", "youtube_cookies.txt", "cookie.txt", "youtube.txt")
    dirs = [
        os.getcwd(),
        TEMP_DOWNLOAD_DIRECTORY,
        os.path.join(os.getcwd(), "downloads"),
        os.path.join(os.getcwd(), "cookies"),
        os.path.join(TEMP_DOWNLOAD_DIRECTORY, "cookies"),
    ]
    try:
        import config as _c
        dirs.append(getattr(_c, "DATA_DIR", "."))
    except Exception:
        pass
    for d in dirs:
        for n in names:
            try:
                pth = os.path.join(d, n)
                if os.path.isfile(pth):
                    return os.path.abspath(pth)
            except Exception:
                pass
    return None


def _extra_args():
    """PO Token sağlayıcı özel bir portta çalışıyorsa ekle.
    Varsayılan 127.0.0.1:4416 zaten otomatik bulunur; farklı port için YT_POT_URL kullan."""
    url = os.environ.get("YT_POT_URL")
    if url:
        return ' --extractor-args "youtubepot-bgutilhttp:base_url=%s"' % url
    return ""


def _sanitize(q):
    """Sorguyu shell için güvenli hale getir."""
    return (q or "").replace('"', "").replace("`", "").replace("$", "").strip()


async def run_command(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return out.decode("utf-8", "replace"), err.decode("utf-8", "replace"), proc.returncode


def _clean_dir(d):
    for f in os.listdir(d):
        try:
            os.remove(os.path.join(d, f))
        except Exception:
            pass


def _read_meta(d):
    """İndirilen .info.json'dan (başlık, sanatçı, süre) oku."""
    title, performer, duration = None, "YouTube", 0
    for f in os.listdir(d):
        if f.endswith(".info.json"):
            try:
                with open(os.path.join(d, f), "r", encoding="utf-8") as jf:
                    info = json.load(jf)
                title = info.get("title") or title
                performer = info.get("uploader") or info.get("channel") or performer
                duration = int(info.get("duration") or 0)
            except Exception:
                pass
            break
    return title, performer, duration


def _fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.1f %s" % (n, unit)
        n /= 1024.0
    return "%.1f TB" % n


def _last_err_line(err):
    lines = [l for l in (err or "").strip().split("\n") if l.strip()]
    return (lines[-1][:160] if lines else "bilinmeyen hata")


async def _download_audio(target, dl_dir):
    """TEK çağrı: ara + indir birlikte. (path, meta, err) döndürür."""
    cookies = _find_cookies()
    ck = ' --cookies "%s"' % cookies if cookies else ""
    cmd = (
        'yt-dlp -x --audio-format mp3 --audio-quality 0 '
        "--no-warnings --no-playlist --write-info-json "
        '-o "%s" "%s"%s%s'
    ) % (os.path.join(dl_dir, "%(id)s.%(ext)s"), target, ck, _extra_args())
    out, err, code = await run_command(cmd)
    mp3 = None
    for f in os.listdir(dl_dir):
        if f.endswith(".mp3"):
            mp3 = os.path.join(dl_dir, f)
            break
    if mp3 and os.path.exists(mp3):
        return mp3, _read_meta(dl_dir), None
    return None, None, err


async def _download_video(target, dl_dir):
    """TEK çağrı: ara + indir birlikte (720p)."""
    cookies = _find_cookies()
    ck = ' --cookies "%s"' % cookies if cookies else ""
    cmd = (
        'yt-dlp -f "bestvideo[height<=720]+bestaudio/best[height<=720]/best" '
        "--merge-output-format mp4 --no-warnings --no-playlist --write-info-json "
        '-o "%s" "%s"%s%s'
    ) % (os.path.join(dl_dir, "%(id)s.%(ext)s"), target, ck, _extra_args())
    out, err, code = await run_command(cmd)
    vid = None
    for f in os.listdir(dl_dir):
        if f.lower().endswith((".mp4", ".mkv", ".webm")):
            vid = os.path.join(dl_dir, f)
            break
    if vid and os.path.exists(vid):
        return vid, _read_meta(dl_dir), None
    return None, None, err


@register(outgoing=True, pattern=r"^\.m[uü]zik(?:\s+(.+))?$")
async def music_download(event):
    if event.fwd_from:
        return
    query = event.pattern_match.group(1)
    if not query:
        await event.edit(
            "**🎵 YouTube Müzik İndirme**\n\n"
            "`.müzik <şarkı adı>` — arayıp indirir\n"
            "`.müzik <youtube linki>` — direkt indirir"
        )
        return

    is_url = is_youtube_url(query)
    target = query.strip() if is_url else "ytsearch1:%s" % _sanitize(query)

    await event.edit("`🎵 İndiriliyor...`")
    dl_dir = os.path.join(TEMP_DOWNLOAD_DIRECTORY, "yt_music")
    os.makedirs(dl_dir, exist_ok=True)
    _clean_dir(dl_dir)
    try:
        path, meta, err = await _download_audio(target, dl_dir)
        if not path:
            _ck = _find_cookies()
            _ci = ("🍪 cookie: %s" % _ck) if _ck else "🍪 cookie: BULUNAMADI"
            await event.edit(
                "`❌ İndirilemedi`\n%s\n\n`%s`" % (_ci, _last_err_line(err)))
            return
        size = os.path.getsize(path)
        if size > MAX_AUDIO_MB * 1024 * 1024:
            await event.edit("`❌ Dosya çok büyük (>%dMB)!`" % MAX_AUDIO_MB)
            return
        title, performer, duration = meta
        await event.edit("`📤 Gönderiliyor: %s`" % _fmt_size(size))
        try:
            from telethon.tl.types import DocumentAttributeAudio
            attrs = [DocumentAttributeAudio(duration=duration, title=title, performer=performer)]
        except Exception:
            attrs = []
        await event.client.send_file(
            event.chat_id,
            path,
            caption="🎵 **%s**" % (title or "Müzik"),
            attributes=attrs,
            force_document=False,
        )
        await event.delete()
    except Exception as e:
        await event.edit("`❌ Gönderme hatası: %s`" % e)
    finally:
        _clean_dir(dl_dir)


@register(outgoing=True, pattern=r"^\.video(?:\s+(.+))?$")
async def video_download(event):
    if event.fwd_from:
        return
    query = event.pattern_match.group(1)
    if not query:
        await event.edit(
            "**🎬 YouTube Video İndirme**\n\n"
            "`.video <video adı>` — arayıp indirir\n"
            "`.video <youtube linki>` — direkt indirir"
        )
        return

    is_url = is_youtube_url(query)
    target = query.strip() if is_url else "ytsearch1:%s" % _sanitize(query)

    await event.edit("`🎬 İndiriliyor...`")
    dl_dir = os.path.join(TEMP_DOWNLOAD_DIRECTORY, "yt_video")
    os.makedirs(dl_dir, exist_ok=True)
    _clean_dir(dl_dir)
    try:
        path, meta, err = await _download_video(target, dl_dir)
        if not path:
            _ck = _find_cookies()
            _ci = ("🍪 cookie: %s" % _ck) if _ck else "🍪 cookie: BULUNAMADI"
            await event.edit(
                "`❌ İndirilemedi`\n%s\n\n`%s`" % (_ci, _last_err_line(err)))
            return
        size = os.path.getsize(path)
        if size > MAX_VIDEO_MB * 1024 * 1024:
            await event.edit("`❌ Dosya çok büyük (>%dMB)!`" % MAX_VIDEO_MB)
            return
        title, performer, duration = meta
        await event.edit("`📤 Gönderiliyor: %s`" % _fmt_size(size))
        await event.client.send_file(
            event.chat_id,
            path,
            caption="🎬 **%s**" % (title or "Video"),
            supports_streaming=True,
        )
        await event.delete()
    except Exception as e:
        await event.edit("`❌ Gönderme hatası: %s`" % e)
    finally:
        _clean_dir(dl_dir)


@register(outgoing=True, pattern=r"^\.ytara(?:\s+(.+))?$")
async def yt_search(event):
    if event.fwd_from:
        return
    query = event.pattern_match.group(1)
    if not query:
        await event.edit("`❌ Aranacak şeyi yaz: .ytara <sorgu>`")
        return

    await event.edit("`🔍 Aranıyor: %s`" % query)
    cookies = _find_cookies()
    ck = ' --cookies "%s"' % cookies if cookies else ""
    cmd = (
        'yt-dlp "ytsearch5:%s" --get-id --get-title --get-duration '
        '--no-warnings'
    ) % _sanitize(query) + ck + _extra_args()
    out, err, code = await run_command(cmd)
    if code != 0 or not out.strip():
        await event.edit("`❌ Sonuç bulunamadı.`")
        return

    lines = out.strip().split("\n")
    results = []
    i, count = 0, 1
    while i + 1 < len(lines) and count <= 5:
        title = lines[i]
        video_id = lines[i + 1]
        duration = lines[i + 2] if i + 2 < len(lines) else "?"
        try:
            d = int(duration)
            duration = "%d:%02d" % (d // 60, d % 60)
        except Exception:
            duration = "?"
        url = "https://youtu.be/%s" % video_id
        ts = title[:40] + "..." if len(title) > 40 else title
        results.append("`%d.` [%s](%s) `(%s)`" % (count, ts, url, duration))
        count += 1
        i += 3
    if results:
        text = "**🔍 YouTube Arama: %s**\n\n" % query + "\n".join(results)
        text += "\n\n_İndir: `.müzik <link>` veya `.video <link>`_"
        await event.edit(text, link_preview=False)
    else:
        await event.edit("`❌ Sonuç bulunamadı.`")


CMD_HELP.update({
    "youtube":
    "`.müzik <şarkı/link>` - YouTube'dan MP3 indir\n"
    "`.video <video/link>` - YouTube'dan video indir (720p)\n"
    "`.ytara <sorgu>` - YouTube'da arama yap"
})
