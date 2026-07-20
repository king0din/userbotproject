# ============================================================
#  utils/i18n.py — Otomatik çeviri (globale açılım)
# ============================================================
#  - Kaynak dil TÜRKÇE. Kullanıcının diline anlık çevirir.
#  - Ücretsiz backend: deep-translator (Google web). Kurulu değilse/hata olursa
#    ORİJİNAL metni döndürür (bot asla bu yüzden bozulmaz).
#  - KALICI ÖNBELLEK: her dil ayrı dosya → data/lang/<kod>.json
#    Yeni çeviri anında yazılır; restart'ta baştan çevirmez.
# ============================================================

import os
import re
import json
import asyncio
import threading

try:
    from utils.logger import get_logger
    log = get_logger(__name__)
except Exception:
    import logging
    log = logging.getLogger("i18n")

SOURCE_LANG = "tr"

try:
    import config as _config
    _DATA_DIR = getattr(_config, "DATA_DIR", None) or "./data"
except Exception:
    _DATA_DIR = "./data"

LANG_DIR = os.path.join(_DATA_DIR, "lang")
LANGS_FILE = os.path.join(_DATA_DIR, "languages.json")
for _d in (_DATA_DIR, LANG_DIR):
    try:
        os.makedirs(_d, exist_ok=True)
    except Exception:
        pass

DEFAULT_LANGS = {
    "tr": "🇹🇷 Türkçe",
    "en": "🇬🇧 English",
    "ar": "🇸🇦 العربية",
    "ru": "🇷🇺 Русский",
    "de": "🇩🇪 Deutsch",
    "fr": "🇫🇷 Français",
    "es": "🇪🇸 Español",
    "az": "🇦🇿 Azərbaycanca",
    "fa": "🇮🇷 فارسی",
    "uk": "🇺🇦 Українська",
}

_lock = threading.RLock()
_cache = {}            # {lang: {masked: "çeviri"}}
_dirty = set()
_user_lang = {}
_langs = None
_translator_ok = None


def _load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
                return d if isinstance(d, (dict, list)) else default
    except Exception:
        log.debug("i18n json okunamadı: %s", path, exc_info=True)
    return default


def _save_json(path, data):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except Exception:
        log.debug("i18n json yazılamadı: %s", path, exc_info=True)


# ---------- Dil bazlı kalıcı önbellek ----------
def _lang_path(lang):
    return os.path.join(LANG_DIR, "%s.json" % lang)


def _ensure_lang(lang):
    if lang not in _cache:
        d = _load_json(_lang_path(lang), {}) or {}
        if lang != SOURCE_LANG and isinstance(d, dict):
            # Zehirli girdileri temizle: çeviri == kaynak (başarısız kalmış) → at,
            # tekrar denensin. (Harf içermeyenler zaten çevrilmez, onları tutmayız.)
            d = {k: v for k, v in d.items() if v and v != k}
        _cache[lang] = d
    return _cache[lang]


def _cache_get(lang, masked):
    with _lock:
        return _ensure_lang(lang).get(masked)


def _cache_put(lang, masked, translated):
    with _lock:
        _ensure_lang(lang)[masked] = translated
        _dirty.add(lang)


def save_lang(lang):
    with _lock:
        if lang in _cache:
            _save_json(_lang_path(lang), _cache[lang])
            _dirty.discard(lang)


def flush_cache():
    with _lock:
        pending = list(_dirty)
    for lang in pending:
        save_lang(lang)


# ---------- Diller ----------
def all_langs():
    global _langs
    if _langs is None:
        _langs = _load_json(LANGS_FILE, None) or dict(DEFAULT_LANGS)
    return _langs


def add_lang(code, name):
    code = (code or "").strip().lower()
    if not code:
        return False
    lg = all_langs()
    lg[code] = name or code
    _save_json(LANGS_FILE, lg)
    return True


def remove_lang(code):
    lg = all_langs()
    if code in lg and code != "tr":
        lg.pop(code, None)
        _save_json(LANGS_FILE, lg)
        return True
    return False


# ---------- Kullanıcı dili ----------
def norm_lang(code):
    if not code:
        return SOURCE_LANG
    c = str(code).strip().lower().replace("_", "-").split("-")[0]
    return c if c else SOURCE_LANG


def set_user_lang(uid, code):
    _user_lang[int(uid)] = norm_lang(code)


def get_user_lang_cached(uid):
    return _user_lang.get(int(uid), SOURCE_LANG)


def default_lang_from_tg(lang_code):
    c = norm_lang(lang_code)
    return c if c in all_langs() else SOURCE_LANG


def load_user_langs(users):
    n = 0
    for u in (users or []):
        try:
            uid = u.get("user_id")
            lang = u.get("lang")
            if uid and lang:
                _user_lang[int(uid)] = norm_lang(lang)
                n += 1
        except Exception:
            pass
    return n


# ---------- Maskeleme ----------
_MASK_PATTERNS = [
    r"`[^`]*`",
    r"\{[^}{]*\}",
    r"https?://\S+",
    r"@[A-Za-z0-9_]{3,}",
    r"(?<!\w)[./][A-Za-z_][A-Za-z0-9_]*",
    r"-?\d[\d.,:]*",
]
_MASK_RE = re.compile("|".join("(?:%s)" % _p for _p in _MASK_PATTERNS))
_SENT_OPEN = "[["
_SENT_CLOSE = "]]"
_UNMASK_RE = re.compile(r"\[\[\s*(\d+)\s*\]\]")


def _mask(text):
    tokens = []

    def _repl(m):
        tokens.append(m.group(0))
        return _SENT_OPEN + str(len(tokens) - 1) + _SENT_CLOSE

    return _MASK_RE.sub(_repl, text), tokens


def _unmask(text, tokens):
    def _repl(m):
        i = int(m.group(1))
        return tokens[i] if 0 <= i < len(tokens) else m.group(0)
    return _UNMASK_RE.sub(_repl, text)


def _has_letters(s):
    return bool(re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]", s))


# ---------- Backend ----------
def _mark_backend_down():
    global _translator_ok
    if _translator_ok is None:
        _translator_ok = False
        log.warning("Çeviri backend'i yok (deep-translator kurulu mu?). "
                    "Metinler çevrilmeden gönderilecek.")


def _translate_one_sync(text, lang):
    global _translator_ok
    try:
        from deep_translator import GoogleTranslator
        out = GoogleTranslator(source=SOURCE_LANG, target=lang).translate(text)
        _translator_ok = True
        return out or None
    except Exception:
        _mark_backend_down()
        return None  # BAŞARISIZ → çağıran cache'lemesin, sonra tekrar denesin


def _translate_batch_sync(texts, lang):
    global _translator_ok
    try:
        from deep_translator import GoogleTranslator
        out = GoogleTranslator(source=SOURCE_LANG, target=lang).translate_batch(texts)
        _translator_ok = True
        if out and len(out) == len(texts):
            return list(out)
        return None
    except Exception:
        _mark_backend_down()
        return None  # BAŞARISIZ → çağıran cache'lemesin


# ---------- Genel API ----------
async def translate(text, lang):
    if not text or not lang:
        return text
    lang = norm_lang(lang)
    if lang == SOURCE_LANG:
        return text
    masked, tokens = _mask(text)
    if not _has_letters(masked):
        return text
    hit = _cache_get(lang, masked)
    if hit is not None:
        return _unmask(hit, tokens)
    try:
        loop = asyncio.get_event_loop()
        translated = await loop.run_in_executor(None, _translate_one_sync, masked, lang)
    except Exception:
        translated = None
    if not translated or translated == masked:
        return text  # başarısız/çevrilmedi → orijinal, CACHE'LEME (sonra tekrar)
    _cache_put(lang, masked, translated)
    save_lang(lang)
    return _unmask(translated, tokens)


async def translate_many(texts, lang):
    texts = list(texts)
    if not texts or not lang:
        return texts
    lang = norm_lang(lang)
    if lang == SOURCE_LANG:
        return texts
    results = [None] * len(texts)
    pending = []
    for i, txt in enumerate(texts):
        if not txt:
            results[i] = txt
            continue
        masked, tokens = _mask(txt)
        if not _has_letters(masked):
            results[i] = txt
            continue
        hit = _cache_get(lang, masked)
        if hit is not None:
            results[i] = _unmask(hit, tokens)
        else:
            pending.append((i, masked, tokens))
    if pending:
        maskeds = [m for (_i, m, _t) in pending]
        try:
            loop = asyncio.get_event_loop()
            translated = await loop.run_in_executor(None, _translate_batch_sync, maskeds, lang)
        except Exception:
            translated = None
        changed = False
        if translated is None:
            # BAŞARISIZ batch → hepsini orijinal bırak, CACHE'LEME (sonra tekrar denenir)
            for (i, masked, tokens) in pending:
                results[i] = _unmask(masked, tokens)
        else:
            for (i, masked, tokens), tr in zip(pending, translated):
                if tr and tr != masked:
                    _cache_put(lang, masked, tr)
                    changed = True
                    results[i] = _unmask(tr, tokens)
                else:
                    results[i] = _unmask(masked, tokens)  # çevrilmedi → cache'leme
        if changed:
            save_lang(lang)
    return results


async def translate_for(text, uid):
    try:
        return await translate(text, get_user_lang_cached(uid))
    except Exception:
        return text


# Başlangıçta doldurulan ana metin listesi (yeni dil seçilince ısıtmak için)
_prewarm_strings = []


def set_prewarm_strings(strings):
    global _prewarm_strings
    _prewarm_strings = list(dict.fromkeys(s for s in (strings or []) if s))


def get_prewarm_strings():
    return list(_prewarm_strings)


def inuse_langs():
    """Kullanıcıların gerçekten seçtiği diller (tr hariç). Boşsa boş liste."""
    out = []
    for v in set(_user_lang.values()):
        if v and v != SOURCE_LANG and v not in out:
            out.append(v)
    return out


async def prewarm(strings, langs=None, flush=True, attempts=6):
    # langs verilmediyse: SADECE kullanımdaki dilleri çevir (10 dili birden değil).
    if langs is None:
        langs = inuse_langs()
    langs = [l for l in (langs or []) if l and l != SOURCE_LANG]
    if not langs:
        return 0
    uniq = [s for s in dict.fromkeys(strings) if s]

    def _missing(lang):
        out = []
        for s in uniq:
            masked, _tok = _mask(s)
            if _has_letters(masked) and _cache_get(lang, masked) is None:
                out.append(s)
        return out

    for lang in langs:
        # ÇEVRİLENE KADAR devam: başarısız (cache'lenmemiş) kalanları tekrar dene.
        prev = None
        for attempt in range(attempts):
            miss = _missing(lang)
            if not miss:
                break
            # Sürekli aynı sayı kalıyorsa (hepsi gerçekten no-op) sonsuz döngüye girme
            if prev is not None and len(miss) >= prev and attempt >= 2:
                break
            prev = len(miss)
            for i in range(0, len(miss), 25):
                await translate_many(miss[i:i + 25], lang)
                await asyncio.sleep(0.5)
            save_lang(lang)
            if _missing(lang):
                # Kalan başarısızlar için soğuma (kota/geçici hata), artan bekleme
                await asyncio.sleep(3 * (attempt + 1))
        save_lang(lang)
        _rem = len(_missing(lang))
        log.info("Ön-çeviri [%s]: %s metin, kalan %s", lang, len(uniq), _rem)
    if flush:
        flush_cache()
    return len(langs)


# ============================================================
#  Userbot client hook'u: plugin çıktılarını (send/edit) sahibin diline çevirir
#  - formatting_entities olan mesajlar (premium emoji/offset) ATLANIR (bozulmasın)
#  - Sahip dili 'tr' ise hiç dokunmaz
# ============================================================
def install_client_translation(client, owner_id):
    """Userbot client'ının plugin çıktılarını (send/edit/send_file) sahibin diline
    çevirir. Entity'li (mention/premium-emoji) mesajlarda entity'ler KORUNUR."""
    if client is None or getattr(client, "_i18n_hooked", False):
        return
    try:
        oid = int(owner_id)
    except Exception:
        return
    client._i18n_hooked = True
    try:
        from telethon.errors import MessageNotModifiedError as _MNM, MessageIdInvalidError as _MII
        _BENIGN_EDIT = (_MNM, _MII)
    except Exception:
        _BENIGN_EDIT = ()
    _orig_send = client.send_message
    _orig_edit = client.edit_message
    _orig_file = getattr(client, "send_file", None)

    async def _tr_text_ents(text, kw):
        """kw['formatting_entities'] varsa entity koruyarak, yoksa düz çevir."""
        lang = get_user_lang_cached(oid)
        if not lang or lang == SOURCE_LANG or not isinstance(text, str) or not text:
            return text
        ents = kw.get("formatting_entities")
        if ents:
            text, new_ents = await translate_keep_entities(text, ents, lang)
            kw["formatting_entities"] = new_ents
        else:
            text = await translate(text, lang)
        return text

    async def _send(entity, message="", **kw):
        try:
            message = await _tr_text_ents(message, kw)
        except Exception:
            pass
        return await _orig_send(entity, message, **kw)

    async def _edit(entity, message=None, text=None, **kw):
        try:
            if isinstance(text, str) and text:
                text = await _tr_text_ents(text, kw)
            elif text is None and isinstance(message, str) and message:
                message = await _tr_text_ents(message, kw)
        except Exception:
            pass
        try:
            return await _orig_edit(entity, message, text, **kw)
        except _BENIGN_EDIT:
            # "içerik değişmedi" / geçersiz mesaj → zararsız; handler'ı ÇÖKERTME
            return None

    async def _sendfile(entity, file, **kw):
        try:
            cap = kw.get("caption")
            if isinstance(cap, str) and cap:
                kw["caption"] = await _tr_text_ents(cap, kw)
        except Exception:
            pass
        return await _orig_file(entity, file, **kw)

    try:
        client.send_message = _send
        client.edit_message = _edit
        if _orig_file is not None:
            client.send_file = _sendfile
    except Exception:
        client._i18n_hooked = False


# ============================================================
#  Plugin/handler dosyalarından çevrilecek metinleri çıkar (ön-çeviri için)
#  - Düz string sabitleri
#  - f-string'ler: dinamik kısımlar {} ile → maskelenince runtime ile AYNI iskelet
# ============================================================
def extract_translatable_strings(paths, min_len=2, max_len=400):
    import ast as _ast
    out = []
    seen = set()

    _ident_re = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")
    _pathlike_re = re.compile(r"[a-z0-9_./%-]+$")

    def _looks_message(st):
        # Regex/desen/kod → atla
        if ("\\" in st) or ("(?:" in st) or ("(?<" in st) or st.startswith("^") or st.endswith("$"):
            return False
        # Tanımlayıcı / dict anahtarı / yol → mesaj değil, atla
        if _ident_re.match(st) or _pathlike_re.match(st):
            return False
        # Boşluk, cümle işareti veya emoji/Türkçe (ASCII dışı) → muhtemelen mesaj
        return (" " in st) or bool(re.search(r"[.!?:]", st)) or bool(re.search(r"[^\x00-\x7F]", st))

    def _add(s):
        if not s:
            return
        st = s.strip("\n").strip()
        if not (min_len <= len(st) <= max_len):
            return
        if not _has_letters(st):
            return
        if not _looks_message(st):
            return
        if s in seen:
            return
        seen.add(s)
        out.append(s)

    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                tree = _ast.parse(f.read())
        except Exception:
            continue
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Constant) and isinstance(node.value, str):
                _add(node.value)
            elif isinstance(node, _ast.JoinedStr):  # f-string
                parts = []
                for v in node.values:
                    if isinstance(v, _ast.Constant) and isinstance(v.value, str):
                        parts.append(v.value)
                    else:
                        parts.append("{}")  # dinamik → maskede [[N]] olur
                _add("".join(parts))
    return out


# ============================================================
#  Entity KORUYARAK çeviri (mention/premium-emoji bozulmaz)
#  - Entity kaplı metin (isim/emoji) OLDUĞU GİBİ kalır, çevrilmez.
#  - Aradaki düz metin çevrilir. UTF-16 offset'ler yeniden hesaplanır.
#  - Herhangi bir aksilikte ORİJİNAL döner (asla bozmaz).
# ============================================================
def _u16len(s):
    return len(s.encode("utf-16-le")) // 2 if s else 0


def _u16_to_idx(text, u16off):
    cur = 0
    for i, ch in enumerate(text):
        if cur >= u16off:
            return i
        cur += 2 if ord(ch) > 0xFFFF else 1
    return len(text)


_ENT_UNMASK_RE = re.compile(r"\[\[E([a-z])\]\]")


async def translate_keep_entities(text, entities, lang):
    """(yeni_text, yeni_entities) döndürür. Entity'siz ise düz çeviri yapar."""
    lang = norm_lang(lang)
    if not text or lang == SOURCE_LANG:
        return text, entities
    if not entities:
        return await translate(text, lang), entities
    try:
        import copy as _copy
        spans = []
        for e in entities:
            off = getattr(e, "offset", None)
            length = getattr(e, "length", None)
            if off is None or length is None:
                raise ValueError("offset yok")
            a = _u16_to_idx(text, off)
            b = _u16_to_idx(text, off + length)
            spans.append((a, b, e))
        spans.sort(key=lambda x: x[0])
        # çakışmayanları seç (çakışma varsa güvenli tarafta kal → çeviri iptal)
        chosen, last = [], -1
        for a, b, e in spans:
            if a >= last:
                chosen.append((a, b, e))
                last = b
            else:
                raise ValueError("overlap")
        if len(chosen) > 26:
            raise ValueError("çok fazla entity")

        # düz + [[Ex]] sentinel dizisi kur
        pieces, covered, pos = [], [], 0
        for i, (a, b, e) in enumerate(chosen):
            pieces.append(text[pos:a])
            pieces.append("[[E%s]]" % chr(97 + i))
            covered.append(text[a:b])
            pos = b
        pieces.append(text[pos:])
        masked = "".join(pieces)

        translated = await translate(masked, lang)  # düz kısımlar çevrilir, [[Ex]] korunur

        # sentinelleri geri koy + yeni UTF-16 offset'leri hesapla
        out, new_ents, u16 = [], [], 0
        for tok in re.split(r"(\[\[E[a-z]\]\])", translated):
            m = _ENT_UNMASK_RE.match(tok)
            if m:
                ei = ord(m.group(1)) - 97
                cov = covered[ei]
                ne = _copy.deepcopy(chosen[ei][2])
                ne.offset = u16
                ne.length = _u16len(cov)
                new_ents.append(ne)
                out.append(cov)
                u16 += _u16len(cov)
            else:
                out.append(tok)
                u16 += _u16len(tok)
        return "".join(out), new_ents
    except Exception:
        return text, entities


import re as _re_pn

# Plugin ADLARI (identifier) — buton etiketlerinde çeviriye kapatılır ("indir" -> "download" olmasın)
_PLUGIN_NAMES = set()

def note_plugin_names(names):
    try:
        for n in names:
            if n and isinstance(n, str):
                _PLUGIN_NAMES.add(n)
    except Exception:
        pass

def _label_core(label):
    """Baştaki emoji/yıldız/boşlukları at → çıplak etiket (plugin adı tespiti için)."""
    try:
        return _re_pn.sub(r'^[^\w]+', '', label, flags=_re_pn.U).strip()
    except Exception:
        return label


def _uid_of(entity):
    if isinstance(entity, int):
        return entity
    for a in ("user_id", "id"):
        v = getattr(entity, a, None)
        if isinstance(v, int):
            return v
    return None


def install_bot_translation(bot):
    """Servis botunun DOĞRUDAN gönderdiği (bot_api dışı) mesajları ALICIYA göre çevirir.
    otomsg panelleri, faturalar, özel-sohbet fallback'leri vb. Entity'ler korunur."""
    if bot is None or getattr(bot, "_i18n_bot_hooked", False):
        return
    bot._i18n_bot_hooked = True
    _orig_send = bot.send_message
    _orig_file = getattr(bot, "send_file", None)

    async def _tr(entity, text, kw):
        try:
            uid = _uid_of(entity)
            if uid is None or not isinstance(text, str) or not text:
                return text
            lang = get_user_lang_cached(uid)
            if not lang or lang == SOURCE_LANG:
                return text
            ents = kw.get("formatting_entities")
            if ents:
                text, ne = await translate_keep_entities(text, ents, lang)
                kw["formatting_entities"] = ne
            else:
                text = await translate(text, lang)
        except Exception:
            pass
        return text

    async def _send(entity, message="", **kw):
        message = await _tr(entity, message, kw)
        return await _orig_send(entity, message, **kw)

    async def _sendfile(entity, file, **kw):
        cap = kw.get("caption")
        if isinstance(cap, str) and cap:
            kw["caption"] = await _tr(entity, cap, kw)
        return await _orig_file(entity, file, **kw)

    try:
        bot.send_message = _send
        if _orig_file is not None:
            bot.send_file = _sendfile
    except Exception:
        bot._i18n_bot_hooked = False


async def translate_telethon_buttons(rows, lang, skip_prefixes=(), skip_labels=()):
    """Telethon inline buton satırlarındaki etiketleri çevirir.
    skip_prefixes: callback_data'sı bu öneklerle başlayan butonlar (ör. dinamik
    sonuçlar) ATLANIR."""
    lang = norm_lang(lang)
    if not rows or lang == SOURCE_LANG:
        return rows
    try:
        from telethon import Button
        out = []
        for row in rows:
            nr = []
            for b in row:
                txt = getattr(b, "text", None)
                data = getattr(b, "data", None)
                url = getattr(b, "url", None)
                skip = False
                if data:
                    try:
                        ds = data.decode() if isinstance(data, (bytes, bytearray)) else str(data)
                        skip = any(ds.startswith(p) for p in skip_prefixes)
                    except Exception:
                        skip = False
                if txt and not skip:
                    _core = _label_core(txt)
                    if _core and (_core in _PLUGIN_NAMES or _core in skip_labels):
                        skip = True
                if txt and not skip:
                    nt = await translate(txt, lang)
                    if url:
                        nr.append(Button.url(nt, url))
                    elif data is not None:
                        nr.append(Button.inline(nt, data))
                    else:
                        nr.append(b)
                else:
                    nr.append(b)
            out.append(nr)
        return out
    except Exception:
        return rows
