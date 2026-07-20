# YouTube İndirici (premium) — .indir / .vindir / .ytara
# type: premium
# stars: 100
# days: 30
# title: YouTube İndirici
# requires: yt-dlp
#
# Notlar (geliştirici):
# - Sade ve HIZLI: SADECE yt-dlp (tek çağrı: ara + indir birlikte), yedek yöntem yok.
# - Reklam/marka: gönderilen müziğin "sanatçı" alanına botun adı yazılır.
# - .ytara inline panelinde butona sahibinden BAŞKASI dokunursa botu tanıtan uyarı çıkar.
"""
YouTube'dan müzik (MP3) ve video indirir; butonlu, sayfalı arama sunar.

🔧 Komutlar: .indir, .vindir, .ytara
🚨 Tür: #indirici


**Komutlar hakkında:**

**.indir** — YouTube'dan müzik (MP3) indirir. Şarkı adı yazarsanız arayıp ilk
sonucu, link verirseniz doğrudan onu indirir.
Örnek: `.indir tarkan kuzu kuzu` · `.indir <link>` · `.indir 2`

**.vindir** — Aynı şekilde çalışır ama video (720p) olarak indirir.
Örnek: `.vindir doğa belgeseli` · `.vindir 3`

**.ytara** — YouTube'da arama yapar; sonuçları sayfalı, butonlu panelde gösterir.
Bir sonuca dokununca "Video İndir" / "Ses (MP3) İndir" çıkar, seçtiğini indirip
sohbete gönderir.
Örnek: `.ytara tarkan`

Not: `.müzik` ve `.video` eski adlar olarak da çalışmaya devam eder.
"""
import os
import re
import sys
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

# .ytara sonuçları (sohbet başına) → ".indir <numara>" / ".vindir <numara>"
_LAST_SEARCH = {}


# ======================================================================
# YARDIMCILAR
# ======================================================================
def is_youtube_url(text):
    return bool(re.match(YT_REGEX, text or ""))


def _resolve_pick(event, query):
    """query yalnızca bir numaraysa, o sohbetteki son .ytara sonucundan URL döndür."""
    try:
        q = (query or "").strip()
        if q.isdigit():
            items = _LAST_SEARCH.get(event.chat_id) or []
            idx = int(q) - 1
            if 0 <= idx < len(items):
                return "https://youtu.be/%s" % items[idx]["id"]
    except Exception:
        pass
    return None


def _find_cookies():
    """Varsa cookies dosyasını bul (zorunlu değil)."""
    names = ("cookies.txt", "youtube_cookies.txt", "cookie.txt", "youtube.txt")
    dirs = [os.getcwd(), TEMP_DOWNLOAD_DIRECTORY,
            os.path.join(os.getcwd(), "downloads"),
            os.path.join(os.getcwd(), "cookies")]
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
    url = os.environ.get("YT_POT_URL")
    if url:
        return ' --extractor-args "youtubepot-bgutilhttp:base_url=%s"' % url
    return ""


def _sanitize(q):
    return (q or "").replace('"', "").replace("`", "").replace("$", "").strip()


def _ytdlp():
    """Botun kendi Python'undaki yt_dlp modülünü çağır."""
    return '"%s" -m yt_dlp' % sys.executable


def _sub_env():
    env = dict(os.environ)
    home = os.path.expanduser("~")
    extra = [os.path.join(home, ".deno", "bin"),
             os.path.join(home, ".cargo", "bin"),
             os.path.join(home, "AppData", "Local", "Programs", "nodejs"),
             r"C:\Program Files\nodejs"]
    cur = env.get("PATH", "")
    add = os.pathsep.join(x for x in extra if os.path.isdir(x) and x not in cur)
    if add:
        env["PATH"] = cur + os.pathsep + add
    # yt-dlp çıktısı UTF-8 olsun (Windows kod sayfasında Türkçe harfler "?" olmasın)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


async def run_command(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, env=_sub_env())
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


# ======================================================================
# MARKA (botun adı) + SERVİS BOTU
# ======================================================================
def _brand_username():
    u = ""
    try:
        import config as _c
        u = getattr(_c, "BOT_USERNAME", "") or ""
    except Exception:
        u = ""
    if not u:
        try:
            with open(os.path.join(os.getcwd(), ".bot_username"), "r", encoding="utf-8") as f:
                u = f.read().strip()
        except Exception:
            u = ""
    return u.lstrip("@")


def _brand_name():
    """Müziğin 'sanatçı' alanına yazılacak marka (botun adı)."""
    u = _brand_username()
    return ("@" + u) if u else "KingTG UserBot"


def _get_bot():
    """Servis botunu (inline butonları gönderebilen) main modülünden al."""
    import sys as _sys
    try:
        if "main" in _sys.modules:
            b = getattr(_sys.modules["main"], "bot", None)
            if b is not None:
                return b
        import __main__
        return getattr(__main__, "bot", None)
    except Exception:
        return None


# ======================================================================
# İNDİRME (yalnızca yt-dlp, tek çağrı)
# ======================================================================
async def _download_audio(target, dl_dir):
    """Ara + indir + kapak göm. (path, meta, thumb, err) döndürür."""
    cookies = _find_cookies()
    ck = ' --cookies "%s"' % cookies if cookies else ""
    cmd = (_ytdlp() + ' -x --audio-format mp3 --audio-quality 0 '
           "--embed-thumbnail --write-thumbnail --convert-thumbnails jpg "
           "--no-warnings --no-playlist --write-info-json "
           '-o "%s" "%s"%s%s') % (
        os.path.join(dl_dir, "%(id)s.%(ext)s"), target, ck, _extra_args())
    out, err, code = await run_command(cmd)
    mp3 = thumb = None
    for f in os.listdir(dl_dir):
        fl = f.lower()
        if fl.endswith(".mp3"):
            mp3 = os.path.join(dl_dir, f)
        elif fl.endswith((".jpg", ".jpeg")):
            thumb = os.path.join(dl_dir, f)
    if mp3 and os.path.exists(mp3):
        return mp3, _read_meta(dl_dir), thumb, None
    return None, None, None, err


async def _download_video(target, dl_dir):
    """Ara + indir (720p) + önizleme kapağı. (path, meta, thumb, err) döndürür."""
    cookies = _find_cookies()
    ck = ' --cookies "%s"' % cookies if cookies else ""
    cmd = (_ytdlp() + ' -f "bestvideo[height<=720]+bestaudio/best[height<=720]/best" '
           "--merge-output-format mp4 --write-thumbnail --convert-thumbnails jpg "
           "--no-warnings --no-playlist --write-info-json "
           '-o "%s" "%s"%s%s') % (
        os.path.join(dl_dir, "%(id)s.%(ext)s"), target, ck, _extra_args())
    out, err, code = await run_command(cmd)
    vid = thumb = None
    for f in os.listdir(dl_dir):
        fl = f.lower()
        if fl.endswith((".mp4", ".mkv", ".webm")):
            vid = os.path.join(dl_dir, f)
        elif fl.endswith((".jpg", ".jpeg")):
            thumb = os.path.join(dl_dir, f)
    if vid and os.path.exists(vid):
        return vid, _read_meta(dl_dir), thumb, None
    return None, None, None, err


async def _send_audio(client, chat_id, path, meta, thumb):
    """Müziği gönder — SANATÇI alanı = botun adı (reklam)."""
    title, _performer, duration = meta if meta else (None, None, 0)
    _thumb = thumb if (thumb and os.path.exists(thumb)) else None
    try:
        from telethon.tl.types import DocumentAttributeAudio
        attrs = [DocumentAttributeAudio(
            duration=duration, title=(title or "Müzik"), performer=_brand_name())]
    except Exception:
        attrs = []
    return await client.send_file(
        chat_id, path, caption="🎵 **%s**" % (title or "Müzik"),
        attributes=attrs, thumb=_thumb, force_document=False)


async def _send_video(client, chat_id, path, meta, thumb):
    title = (meta[0] if meta else None) or "Video"
    _thumb = thumb if (thumb and os.path.exists(thumb)) else None
    return await client.send_file(
        chat_id, path, caption="🎬 **%s**" % title,
        thumb=_thumb, supports_streaming=True)


# ======================================================================
# BOT TARAFI: .ytara inline panel + dokun-indir (TEK SEFER kaydedilir)
# ======================================================================
def _register_dl_bot_handlers(bot):
    if getattr(bot, "_dl_flow_registered", False):
        return
    bot._dl_flow_registered = True
    from telethon import events as _ev, Button as _Btn
    import re as _re

    PER_PAGE = 5

    def _not_yours():
        bu = _brand_username()
        if bu:
            return ("\U0001F512 Bu panel sana ait değil.\n\n"
                    "Bu özelliği kullanmak için @%s userbotunu kullanabilirsin!" % bu)
        return "\U0001F512 Bu panel sana ait değil. Bu özellik için userbot kullan!"

    async def _list_markup(owner, page):
        import utils.i18n as _i18n
        data = getattr(bot, "_yt_search", {}).get(owner) or {}
        items = data.get("items", [])
        total = len(items)
        pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        page = max(0, min(page, pages - 1))
        start = page * PER_PAGE
        chunk = items[start:start + PER_PAGE]
        text = "\U0001F50D **YouTube Arama Sonuçları**\n\nBir sonuca dokun → indirme türünü seç:"
        rows = []
        for j, it in enumerate(chunk):
            gidx = start + j
            label = "%d. %s (%s)" % (gidx + 1, it["title"][:38], it.get("dur", "?"))
            rows.append([_Btn.inline(label, ("ytpk_%d_%d_%d" % (owner, gidx, page)).encode())])
        nav = []
        if page > 0:
            nav.append(_Btn.inline("\u25C0\uFE0F Önceki", ("ytpg_%d_%d" % (owner, page - 1)).encode()))
        nav.append(_Btn.inline("%d/%d" % (page + 1, pages), b"ytnoop"))
        if page < pages - 1:
            nav.append(_Btn.inline("Sonraki \u25B6\uFE0F", ("ytpg_%d_%d" % (owner, page + 1)).encode()))
        rows.append(nav)
        lang = _i18n.get_user_lang_cached(owner)
        if lang and lang != "tr":
            text = await _i18n.translate(text, lang)
            rows = await _i18n.translate_telethon_buttons(rows, lang, skip_prefixes=("ytpk",))
        return text, rows

    async def _pick_markup(owner, idx, page):
        import utils.i18n as _i18n
        data = getattr(bot, "_yt_search", {}).get(owner) or {}
        items = data.get("items", [])
        title = items[idx]["title"] if 0 <= idx < len(items) else "?"
        lang = _i18n.get_user_lang_cached(owner)
        sel, how = "\U0001F3A7 **Seçildi:**", "Nasıl indireyim?"
        if lang and lang != "tr":
            sel = await _i18n.translate(sel, lang)
            how = await _i18n.translate(how, lang)
        text = "%s %s\n\n%s" % (sel, title[:60], how)
        rows = [
            [_Btn.inline("\U0001F3AC Video İndir", ("ytgo_%d_%d_v" % (owner, idx)).encode()),
             _Btn.inline("\U0001F3B5 Ses (MP3)", ("ytgo_%d_%d_a" % (owner, idx)).encode())],
            [_Btn.inline("\U0001F519 Geri", ("ytpg_%d_%d" % (owner, page)).encode())],
        ]
        if lang and lang != "tr":
            rows = await _i18n.translate_telethon_buttons(rows, lang)
        return text, rows

    bot._yt_list_markup = _list_markup

    @bot.on(_ev.InlineQuery())
    async def _yt_search_inline(event):
        m = _re.match(r"ytsq_(\d+)$", event.text or "")
        if not m:
            return
        owner = int(m.group(1))
        if not getattr(bot, "_yt_search", {}).get(owner):
            return
        text, rows = await _list_markup(owner, 0)
        try:
            result = event.builder.article(
                title="\U0001F50D YouTube Arama",
                description="Sonuç seç → Video/Ses indir",
                text=text, buttons=rows)
            await event.answer([result], cache_time=0)
        except Exception:
            pass

    @bot.on(_ev.CallbackQuery(pattern=rb"ytnoop"))
    async def _yt_noop(event):
        try:
            await event.answer()
        except Exception:
            pass

    @bot.on(_ev.CallbackQuery(pattern=rb"ytpg_(\d+)_(\d+)"))
    async def _yt_page_cb(event):
        owner = int(event.pattern_match.group(1))
        page = int(event.pattern_match.group(2))
        if event.sender_id != owner:
            await event.answer(_not_yours(), alert=True); return
        text, rows = await _list_markup(owner, page)
        try:
            await event.edit(text, buttons=rows)
        except Exception:
            pass

    @bot.on(_ev.CallbackQuery(pattern=rb"ytpk_(\d+)_(\d+)_(\d+)"))
    async def _yt_pick_cb(event):
        owner = int(event.pattern_match.group(1))
        idx = int(event.pattern_match.group(2))
        page = int(event.pattern_match.group(3))
        if event.sender_id != owner:
            await event.answer(_not_yours(), alert=True); return
        text, rows = await _pick_markup(owner, idx, page)
        try:
            await event.edit(text, buttons=rows)
        except Exception:
            pass

    @bot.on(_ev.CallbackQuery(pattern=rb"ytgo_(\d+)_(\d+)_([av])"))
    async def _yt_go_cb(event):
        owner = int(event.pattern_match.group(1))
        idx = int(event.pattern_match.group(2))
        kind = event.pattern_match.group(3).decode()
        if event.sender_id != owner:
            await event.answer(_not_yours(), alert=True); return
        data = getattr(bot, "_yt_search", {}).get(owner)
        items = (data or {}).get("items", [])
        if not data or idx >= len(items):
            await event.answer("Arama süresi doldu, tekrar `.ytara` yaz.", alert=True); return
        from userbot.smart_manager import smart_session_manager
        client = smart_session_manager.get_client(owner)
        if client is None:
            await event.answer("Userbot aktif değil, önce bir komut çalıştır.", alert=True); return
        it = items[idx]
        url = "https://youtu.be/%s" % it["id"]
        chat_id = data.get("chat_id")
        title = it.get("title", "?")
        mod = "Ses (MP3)" if kind == "a" else "Video"
        await event.answer("⏳ İndiriliyor...")

        # Paneli sil — kim gönderdiyse o silsin (inline=userbot, özel=bot)
        pid = data.get("panel_msg_id")
        pchat = data.get("panel_chat", chat_id)
        if pid:
            try:
                if data.get("panel_by_bot"):
                    await bot.delete_messages(pchat, [pid])
                else:
                    await client.delete_messages(pchat, [pid])
            except Exception:
                pass

        # Net durum mesajı: indiriliyor mu belli olsun
        status = None
        try:
            status = await client.send_message(
                chat_id, "⏳ **%s** indiriliyor... (%s)" % (title[:50], mod))
        except Exception:
            status = None

        dl_dir = os.path.join(TEMP_DOWNLOAD_DIRECTORY, "yt_pick_%d" % owner)
        os.makedirs(dl_dir, exist_ok=True)
        _clean_dir(dl_dir)
        try:
            if kind == "a":
                path, meta, thumb, err = await _download_audio(url, dl_dir)
            else:
                path, meta, thumb, err = await _download_video(url, dl_dir)
            if not path:
                if status:
                    try:
                        await status.edit("❌ **%s** indirilemedi." % title[:50])
                    except Exception:
                        pass
                return
            if kind == "a":
                await _send_audio(client, chat_id, path, meta, thumb)
            else:
                await _send_video(client, chat_id, path, meta, thumb)
            if status:
                try:
                    await status.delete()
                except Exception:
                    pass
        except Exception:
            if status:
                try:
                    await status.edit("❌ Gönderilemedi.")
                except Exception:
                    pass
        finally:
            _clean_dir(dl_dir)


async def _resolve_target(event, query):
    """query'yi indirilecek hedefe çevir:
      • YouTube linki → doğrudan
      • sadece numara → o sohbetteki son .ytara sonucundan URL
      • serbest metin → ytsearch1: ile ara
    """
    q = (query or "").strip()
    if is_youtube_url(q):
        return q
    pick = _resolve_pick(event, q)
    if pick:
        return pick
    return "ytsearch1:%s" % _sanitize(q)


@register(outgoing=True, pattern=r"^\.indir(?:\s+(.+))?$")
async def indir_audio(event):
    """MP3 indir. Kullanım: .indir <şarkı/link/numara>"""
    if event.fwd_from:
        return
    query = event.pattern_match.group(1)
    if not query:
        await event.edit(
            "**🎵 YouTube MP3 İndirme**\n\n"
            "`.indir <şarkı adı>` — arayıp indirir\n"
            "`.indir <youtube linki>` — direkt indirir\n"
            "`.indir <numara>` — son `.ytara` sonucundan seçer"
        )
        return
    target = await _resolve_target(event, query)
    await event.edit("`🎵 İndiriliyor...`")
    # Operatörün KENDİ id'sine göre klasör: eşzamanlı indirmede dosyalar karışmaz
    owner = (await event.client.get_me()).id
    dl_dir = os.path.join(TEMP_DOWNLOAD_DIRECTORY, "dl_audio_%d" % owner)
    os.makedirs(dl_dir, exist_ok=True)
    _clean_dir(dl_dir)
    try:
        path, meta, thumb, err = await _download_audio(target, dl_dir)
        if not path:
            await event.edit("`❌ İndirilemedi:` `%s`" % _last_err_line(err))
            return
        size = os.path.getsize(path)
        if size > MAX_AUDIO_MB * 1024 * 1024:
            await event.edit("`❌ Dosya çok büyük (>%dMB)!`" % MAX_AUDIO_MB)
            return
        await event.edit("`📤 Gönderiliyor: %s`" % _fmt_size(size))
        await _send_audio(event.client, event.chat_id, path, meta, thumb)
        await event.delete()
    except Exception as e:
        await event.edit("`❌ Gönderme hatası: %s`" % e)
    finally:
        _clean_dir(dl_dir)


@register(outgoing=True, pattern=r"^\.vindir(?:\s+(.+))?$")
async def vindir_video(event):
    """Video indir (720p). Kullanım: .vindir <video/link/numara>"""
    if event.fwd_from:
        return
    query = event.pattern_match.group(1)
    if not query:
        await event.edit(
            "**🎬 YouTube Video İndirme**\n\n"
            "`.vindir <video adı>` — arayıp indirir\n"
            "`.vindir <youtube linki>` — direkt indirir\n"
            "`.vindir <numara>` — son `.ytara` sonucundan seçer"
        )
        return
    target = await _resolve_target(event, query)
    await event.edit("`🎬 İndiriliyor...`")
    owner = (await event.client.get_me()).id
    dl_dir = os.path.join(TEMP_DOWNLOAD_DIRECTORY, "dl_video_%d" % owner)
    os.makedirs(dl_dir, exist_ok=True)
    _clean_dir(dl_dir)
    try:
        path, meta, thumb, err = await _download_video(target, dl_dir)
        if not path:
            await event.edit("`❌ İndirilemedi:` `%s`" % _last_err_line(err))
            return
        size = os.path.getsize(path)
        if size > MAX_VIDEO_MB * 1024 * 1024:
            await event.edit("`❌ Dosya çok büyük (>%dMB)!`" % MAX_VIDEO_MB)
            return
        await event.edit("`📤 Gönderiliyor: %s`" % _fmt_size(size))
        await _send_video(event.client, event.chat_id, path, meta, thumb)
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

    await event.edit("`\U0001F50D Aranıyor: %s`" % query)
    cookies = _find_cookies()
    ck = ' --cookies "%s"' % cookies if cookies else ""
    cmd = (_ytdlp() + ' "ytsearch10:%s" --get-id --get-title --get-duration '
           '--no-warnings') % _sanitize(query) + ck + _extra_args()
    out, err, code = await run_command(cmd)
    if code != 0 or not out.strip():
        await event.edit("`❌ Sonuç bulunamadı.`")
        return

    lines = out.strip().split("\n")
    items = []
    i, count = 0, 1
    while i + 1 < len(lines) and count <= 10:
        title = lines[i]
        video_id = lines[i + 1]
        duration = lines[i + 2] if i + 2 < len(lines) else "?"
        try:
            d = int(duration)
            duration = "%d:%02d" % (d // 60, d % 60)
        except Exception:
            duration = "?"
        items.append({"id": video_id, "title": title, "dur": duration})
        count += 1
        i += 3
    if not items:
        await event.edit("`❌ Sonuç bulunamadı.`")
        return

    # Numaralı seçim için hafızaya al (.indir <n> / .vindir <n> fallback)
    _LAST_SEARCH[event.chat_id] = items

    # BUTONLU sayfalı panel (dokun → sonuç seç → Video/Ses indir)
    bu = _brand_username()
    bot = _get_bot()
    if bu and bot is not None:
        _register_dl_bot_handlers(bot)
        if not hasattr(bot, "_yt_search"):
            bot._yt_search = {}
        owner = (await event.client.get_me()).id

        # 1) Bu sohbette inline panel dene
        try:
            bot._yt_search[owner] = {"chat_id": event.chat_id, "items": items,
                                     "panel_msg_id": None, "panel_chat": event.chat_id,
                                     "panel_by_bot": False}
            res = await event.client.inline_query(bu, "ytsq_%d" % owner)
            if res:
                sent = await res[0].click(event.chat_id)
                try:
                    bot._yt_search[owner]["panel_msg_id"] = getattr(sent, "id", None)
                except Exception:
                    pass
                try:
                    await event.delete()
                except Exception:
                    pass
                return
        except Exception:
            pass  # inline kapalı → bot özelden göndersin

        # 2) Inline kapalı → paneli BOT ÖZEL sohbetinden gönder (medya da özele)
        try:
            render = getattr(bot, "_yt_list_markup", None)
            bot._yt_search[owner] = {"chat_id": owner, "items": items,
                                     "panel_msg_id": None, "panel_chat": owner,
                                     "panel_by_bot": True}
            if render:
                ptext, prows = await render(owner, 0)
            else:
                ptext, prows = ("🔍 YouTube Arama Sonuçları", None)
            msg = await bot.send_message(owner, ptext, buttons=prows)
            bot._yt_search[owner]["panel_msg_id"] = getattr(msg, "id", None)
            await event.edit(
                "⚠️ **Bu sohbette satır içi (inline) mod kapalı.**\n"
                "Arama paneli sana **özelden (bot sohbeti)** gönderildi. 📩\n"
                "_Seçtiğin şarkı/video oraya indirilecek._")
            return
        except Exception:
            pass

    # 3) Son çare: numaralı metin (.indir <numara> ile seç)
    lines2 = ["`%d.` %s `(%s)`" % (n + 1, it["title"][:40], it["dur"])
              for n, it in enumerate(items)]
    text = "**🔍 YouTube Arama: %s**\n\n" % query + "\n".join(lines2)
    text += "\n\n🎵 MP3: `.indir <numara>`  ·  🎬 Video: `.vindir <numara>`"
    await event.edit(text, link_preview=False)


CMD_HELP.update({
    "youtube":
    "`.indir <şarkı/link/numara>` - YouTube'dan MP3 indir (kapak + marka etiketli)\n"
    "`.vindir <video/link/numara>` - YouTube'dan video indir (720p)\n"
    "`.ytara <sorgu>` - Butonlu sayfalı arama: sonuç seç → Video/Ses indir\n"
    "_(.müzik/.video eski adlar olarak da çalışır)_"
})
