"""
Belirlediğiniz gruplara otomatik ve zamanlanmış mesaj gönderir.

🔧 Komutlar: .otomsg, .otomsgs, .otomsgl, .otomsgdel, .otomsgstop, .otomsgstart, .otomsghelp
🚨 Tür: #otomasyon

Komutlar hakkında:
.otomsg ekle <chat_id|@username> <aralık_dk> <tekrar> <mesaj>
    - Yeni otomatik mesaj görevi ekler
    - aralık_dk: Kaç dakikada bir gönderilsin (min 1)
    - tekrar: Kaç kere gönderilsin (0 = sınırsız)
    - Örnek: .otomsg ekle @grupadi 30 10 Merhaba!
    - Örnek: .otomsg ekle -1001234567890 5 0 Admin bildirim mesajı

.otomsgs        - Tüm aktif görevlerin durumunu gösterir
.otomsgl        - Kayıtlı görev listesini gösterir
.otomsgdel <id> - Görevi siler (ID .otomsgl'den öğrenilir)
.otomsgstop <id>- Görevi geçici olarak durdurur
.otomsgstart <id>-Durdurulan görevi yeniden başlatır
.otomsghelp     - Detaylı yardım mesajı
"""

import asyncio
import json
import os
import time
from telethon.errors import (
    ChatWriteForbiddenError,
    UserBannedInChannelError,
    ChannelPrivateError,
    FloodWaitError,
    ChatAdminRequiredError,
    SlowModeWaitError,
    UserNotParticipantError,
    PeerIdInvalidError,
)
from userbot import bot
from userbot.events import register as r
from userbot.cmdhelp import CmdHelp

# ==========================================
# SÜRE AYRIŞTIRICISI
# ==========================================

def parse_interval(raw: str):
    """
    '30s' → 30 saniye, '5d' → 300 saniye, '2dk' → 120 saniye vb.
    Sadece sayı girilirse dakika kabul edilir (geriye dönük uyumluluk).
    Döner: (saniye: int, orijinal_label: str) veya (None, hata_mesajı)
    """
    raw = raw.strip().lower()
    if not raw:
        return None, "Boş değer"

    # Birim etiketleri
    if raw.endswith("dk") or raw.endswith("dak") or raw.endswith("d"):
        suffix = "dk" if raw.endswith("dk") else ("dak" if raw.endswith("dak") else "d")
        num_str = raw[:-len(suffix)]
        unit = "dakika"
        multiplier = 60
    elif raw.endswith("sn") or raw.endswith("san") or raw.endswith("s"):
        suffix = "sn" if raw.endswith("sn") else ("san" if raw.endswith("san") else "s")
        num_str = raw[:-len(suffix)]
        unit = "saniye"
        multiplier = 1
    else:
        # Sadece sayı → dakika (eski davranış)
        num_str = raw
        unit = "dakika"
        multiplier = 60

    if not num_str.isdigit():
        return None, f"Geçersiz sayı: `{num_str}`"

    value = int(num_str)
    if value < 1:
        return None, "Değer en az 1 olmalıdır"

    seconds = value * multiplier
    label = f"{value} {unit}"
    return seconds, label


# ==========================================
# ENTITY ÇÖZÜCÜ
# ==========================================

async def resolve_chat(client, chat_raw: str):
    """
    Farklı ID formatlarını deneyerek chat entity'sini döndürür.
    Ham negatif ID, -100 prefix'li ID, int ID, @username hepsini dener.
    Döner: (entity, chat_id, chat_title) veya hata fırlatır.
    """
    attempts = []

    # 1) Olduğu gibi dene
    attempts.append(chat_raw)

    # 2) Sayısal ise çeşitli formatlarda dene
    raw_str = chat_raw.lstrip("-")
    if raw_str.isdigit():
        num = int(chat_raw)
        abs_num = abs(num)

        # -100 prefix'li kanal/grup ID'si (örn: -1001660979054 → 1660979054)
        if str(abs_num).startswith("100") and len(str(abs_num)) > 10:
            plain_id = int(str(abs_num)[3:])  # başındaki 100'ü at
            attempts.append(plain_id)

        # Pozitif halini dene
        attempts.append(abs_num)

        # int olarak doğrudan dene
        attempts.append(num)

        # Telethon PeerChannel formatı
        try:
            from telethon.tl.types import PeerChannel, PeerChat
            if str(abs_num).startswith("100"):
                plain = int(str(abs_num)[3:])
                attempts.append(PeerChannel(plain))
            else:
                attempts.append(PeerChannel(abs_num))
                attempts.append(PeerChat(abs_num))
        except Exception:
            pass

    last_err = None
    for attempt in attempts:
        try:
            entity = await client.get_entity(attempt)
            from telethon import utils as _tl_utils
            chat_id = _tl_utils.get_peer_id(entity)
            chat_title = getattr(entity, "title", None) or getattr(entity, "first_name", str(chat_id))
            return entity, chat_id, chat_title
        except Exception as e:
            last_err = e
            continue

    raise Exception(f"Hiçbir format işe yaramadı. Son hata: {last_err}")


# ==========================================
# VERİ DEPOLAMA
# ==========================================

TASKS_FILE = os.path.join(os.path.dirname(__file__), "otomsg_tasks.json")

# Çalışan asyncio taskları: {task_id: asyncio.Task}
running_tasks: dict = {}

# Görev verisi: {task_id: {...}}
tasks_data: dict = {}

# Yüklenmiş kullanıcı ID'si (cache)
_loaded_user_id = None


# ==========================================
# JSON YÜKLEME / KAYDETME
# ==========================================

def _load_tasks_raw() -> dict:
    """Tüm kullanıcıların görevlerini JSON'dan yükle."""
    if not os.path.exists(TASKS_FILE):
        return {}
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_tasks_raw(data: dict):
    """Tüm kullanıcıların görevlerini JSON'a kaydet."""
    try:
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def cleanup_user_data(user_id, reason="disable"):
    """Kullanıcının oto-mesaj görevlerini temizle. Çıkışta korunur (yapılandırma); devre dışı/silmede silinir."""
    try:
        if reason == "logout":
            return
        raw = _load_tasks_raw()
        if str(user_id) in raw:
            raw.pop(str(user_id), None)
            _save_tasks_raw(raw)
    except Exception:
        pass


async def load_my_tasks(client):
    """Kendi hesabıma ait görevleri yükle."""
    global tasks_data, _loaded_user_id
    me = await client.get_me()
    my_id = str(me.id)
    if _loaded_user_id == my_id:
        return
    raw = _load_tasks_raw()
    tasks_data = raw.get(my_id, {})
    _loaded_user_id = my_id


async def save_my_tasks(client):
    """Kendi hesabıma ait görevleri kaydet."""
    me = await client.get_me()
    my_id = str(me.id)
    raw = _load_tasks_raw()
    raw[my_id] = tasks_data
    _save_tasks_raw(raw)


def _next_task_id() -> str:
    """Mevcut en büyük int ID'den bir sonrakini döndür."""
    if not tasks_data:
        return "1"
    max_id = max(int(k) for k in tasks_data.keys())
    return str(max_id + 1)


# ==========================================
# HATA SINIFLANDIRMASI
# ==========================================

FATAL_ERRORS = (
    ChatWriteForbiddenError,
    UserBannedInChannelError,
    ChannelPrivateError,
    ChatAdminRequiredError,
    UserNotParticipantError,
    PeerIdInvalidError,
)

TEMP_ERRORS = (
    FloodWaitError,
    SlowModeWaitError,
)


def _error_summary(e: Exception) -> str:
    """Hata sınıfına göre kısa açıklama döndür."""
    if isinstance(e, ChatWriteForbiddenError):
        return "Sohbete yazma yasak (ban/kısıtlama)"
    if isinstance(e, UserBannedInChannelError):
        return "Kanaldan banlandınız"
    if isinstance(e, ChannelPrivateError):
        return "Kanal/grup gizli veya erişim yok"
    if isinstance(e, ChatAdminRequiredError):
        return "Admin yetkisi gerekli"
    if isinstance(e, UserNotParticipantError):
        return "Gruba üye değilsiniz"
    if isinstance(e, PeerIdInvalidError):
        return "Geçersiz chat ID/username"
    if isinstance(e, FloodWaitError):
        return f"FloodWait ({e.seconds}s)"
    if isinstance(e, SlowModeWaitError):
        return f"SlowMode ({e.seconds}s)"
    return str(e)[:80]


# ==========================================
# GÖREV ÇALIŞMA DÖNGÜSÜ
# ==========================================

async def _resolve_target(client, chat_id):
    """Hedef peer'ı güvenli biçimde çözer.

    Eski görevlerde ID işaretsiz (ham) saklanmış olabilir; pozitif ham ID'yi
    Telethon kullanıcı (PeerUser) sanıp 'input entity bulunamadı' hatası verir.
    Bu yüzden işaretli (-100..) formu, PeerChannel/PeerChat/PeerUser varyantlarını
    sırayla dener; hiçbiri tutmazsa dialogs'u bir kez tazeleyip tekrar dener.
    Bulursa input entity döner, bulamazsa None.
    """
    from telethon.tl.types import PeerChannel, PeerChat, PeerUser
    cands = [chat_id]
    try:
        n = int(chat_id)
        a = abs(n)
        s = str(a)
        if s.startswith("100") and len(s) > 10:
            inner = int(s[3:])
            cands.append(int("-100" + s[3:]))
            cands.append(PeerChannel(inner))
            cands.append(inner)
        else:
            cands.append(int("-100" + s))   # ham kanal ID'sini -100 ile dene
            cands.append(PeerChannel(a))
            cands.append(PeerChat(a))
        if n > 0:
            cands.append(PeerUser(a))
    except Exception:
        pass

    async def _try():
        for c in cands:
            try:
                return await client.get_input_entity(c)
            except Exception:
                continue
        return None

    ent = await _try()
    if ent is not None:
        return ent
    # Son çare: dialogs'u tazele (entity cache'ini doldurur) ve tekrar dene
    try:
        async for _d in client.iter_dialogs(limit=500):
            pass
    except Exception:
        pass
    return await _try()


async def _task_loop(client, task_id: str, notify_chat_id: int, initial_delay: int = 0):
    """
    Belirtilen görevi çalıştıran ana döngü.
    notify_chat_id: Sorun olursa hata bildirimi gönderilecek chat (komutu yazan chat).
    """
    # Toplu başlatmada aynı anda atıp spam tetiklememek için kademeli gecikme
    if initial_delay and initial_delay > 0:
        await asyncio.sleep(initial_delay)

    task = tasks_data.get(task_id)
    if not task:
        return

    chat_id   = task["chat_id"]
    interval  = task.get("interval_seconds") or task.get("interval_minutes", 1) * 60
    max_count = task["repeat_count"]           # 0 = sınırsız
    message   = task["message"]
    media_path = task.get("media_path")
    sent      = task.get("sent_count", 0)
    consecutive_errors = 0
    MAX_CONSECUTIVE = 5  # üst üste bu kadar hata olursa görevi oto-durdur

    # Hedef peer'ı güvenli çöz (eski/işaretsiz ID'ler PeerUser sanılıp hata veriyordu)
    target = await _resolve_target(client, chat_id)
    if target is None:
        tasks_data[task_id]["status"] = "error"
        tasks_data[task_id]["last_error"] = "Hedef sohbet çözümlenemedi (ekli değil ya da ID geçersiz)"
        await save_my_tasks(client)
        try:
            await client.send_message(
                notify_chat_id,
                f"🚨 **OtoMsg Görev #{task_id} başlatılamadı!**\n\n"
                f"💬 **Chat:** `{chat_id}`\n"
                f"❌ Hedef sohbet çözümlenemedi.\n"
                f"   • Userbot bu gruba/kanala ekli mi?\n"
                f"   • En güvenlisi: o grupta `.otomsg <mesaj> <dakika>` yazın."
            )
        except Exception:
            pass
        running_tasks.pop(task_id, None)
        return

    while True:
        # Görev silinmiş mi kontrol et
        if task_id not in tasks_data:
            break

        # Tekrar limiti
        if max_count > 0 and sent >= max_count:
            tasks_data[task_id]["status"] = "completed"
            tasks_data[task_id]["sent_count"] = sent
            await save_my_tasks(client)
            try:
                await client.send_message(
                    notify_chat_id,
                    f"✅ **OtoMsg Görev #{task_id} tamamlandı!**\n"
                    f"📨 Toplam gönderildi: {sent} mesaj\n"
                    f"💬 Chat: `{chat_id}`"
                )
            except Exception:
                pass
            break

        # Bekleme (interval)
        await asyncio.sleep(interval)

        # Tekrar kontrol et (bekleme sırasında silinmiş/durdurulmuş olabilir)
        if task_id not in tasks_data:
            break
        current_status = tasks_data[task_id].get("status", "running")
        if current_status != "running":
            # Durdurulmuşsa bekle, silinmişse çık
            while True:
                await asyncio.sleep(10)
                if task_id not in tasks_data:
                    return
                st = tasks_data[task_id].get("status", "stopped")
                if st == "running":
                    break
                if st in ("completed", "deleted"):
                    return

        # Mesajı gönder
        try:
            await _om_send(client, target, media_path, message)
            sent += 1
            consecutive_errors = 0
            tasks_data[task_id]["sent_count"] = sent
            tasks_data[task_id]["last_sent"] = int(time.time())
            await save_my_tasks(client)

        except FATAL_ERRORS as e:
            consecutive_errors += 1
            err_msg = _error_summary(e)
            tasks_data[task_id]["status"] = "error"
            tasks_data[task_id]["last_error"] = err_msg
            await save_my_tasks(client)
            # Admini bilgilendir
            try:
                await client.send_message(
                    notify_chat_id,
                    f"🚨 **OtoMsg Görev #{task_id} — KRİTİK HATA!**\n\n"
                    f"💬 **Chat:** `{chat_id}`\n"
                    f"❌ **Hata:** {err_msg}\n\n"
                    f"⚠️ Görev otomatik durduruldu.\n"
                    f"Tekrar başlatmak için: `.otomsgstart {task_id}`"
                )
            except Exception:
                pass
            break  # ölümcül hata → döngüden çık

        except FloodWaitError as e:
            wait = e.seconds + 5
            tasks_data[task_id]["last_error"] = f"FloodWait ({wait}s) bekleniyor"
            await save_my_tasks(client)
            await asyncio.sleep(wait)

        except SlowModeWaitError as e:
            wait = e.seconds + 2
            await asyncio.sleep(wait)
            # Slow mode bittikten sonra tekrar gönder
            try:
                await _om_send(client, target, media_path, message)
                sent += 1
                tasks_data[task_id]["sent_count"] = sent
                tasks_data[task_id]["last_sent"] = int(time.time())
                await save_my_tasks(client)
            except Exception as e2:
                tasks_data[task_id]["last_error"] = _error_summary(e2)
                await save_my_tasks(client)

        except Exception as e:
            consecutive_errors += 1
            err_msg = _error_summary(e)
            tasks_data[task_id]["last_error"] = err_msg
            await save_my_tasks(client)

            if consecutive_errors >= MAX_CONSECUTIVE:
                tasks_data[task_id]["status"] = "error"
                await save_my_tasks(client)
                try:
                    await client.send_message(
                        notify_chat_id,
                        f"🚨 **OtoMsg Görev #{task_id} — Çok Fazla Hata!**\n\n"
                        f"💬 **Chat:** `{chat_id}`\n"
                        f"❌ **Son hata:** {err_msg}\n"
                        f"📊 **Üst üste hata:** {consecutive_errors}\n\n"
                        f"⚠️ Görev otomatik durduruldu.\n"
                        f"Tekrar başlatmak için: `.otomsgstart {task_id}`"
                    )
                except Exception:
                    pass
                break

    # Döngü bitince running_tasks'tan kaldır
    running_tasks.pop(task_id, None)


async def _start_task(client, task_id: str, notify_chat_id: int, initial_delay: int = 0):
    """Görev döngüsünü başlat ve running_tasks'a ekle."""
    if task_id in running_tasks:
        return
    task_obj = asyncio.create_task(
        _task_loop(client, task_id, notify_chat_id, initial_delay)
    )
    running_tasks[task_id] = task_obj


async def _restore_tasks(client, me_id: int):
    """Bot yeniden başlayınca 'running' durumdaki görevleri yeniden başlat."""
    await load_my_tasks(client)
    i = 0
    for task_id, task in tasks_data.items():
        if task.get("status") == "running":
            await _start_task(client, task_id, me_id, initial_delay=i * 5)
            i += 1


# ==========================================
# BUTONLU SAYFALAMA (liste cokmesini onler)
# ==========================================

OMSG_PAGE_SIZE = 5


def _get_bot():
    import sys
    try:
        if 'main' in sys.modules:
            b = getattr(sys.modules['main'], 'bot', None)
            if b is not None:
                return b
        import __main__
        return getattr(__main__, 'bot', None)
    except Exception:
        return None


def _get_bot_username():
    try:
        import config as cfg
        u = getattr(cfg, 'BOT_USERNAME', '') or ''
        if u:
            return u.lstrip('@')
    except Exception:
        pass
    try:
        if os.path.exists('.bot_username'):
            with open('.bot_username') as f:
                return f.read().strip().lstrip('@')
    except Exception:
        pass
    return ''


def _render_omsg_lines(owner_id):
    """Bu hesabin gorevlerini (JSON'dan, paylasimli) satir listesi olarak dondurur."""
    raw = _load_tasks_raw().get(str(owner_id), {})
    lines = []
    for tid, t in raw.items():
        repeat_text = "sınırsız" if t.get("repeat_count", 0) == 0 else f"{t.get('repeat_count')} kere"
        status = t.get("status", "?")
        emoji = {"running": "🟢", "stopped": "⏸️", "completed": "✅", "error": "⚠️"}.get(status, "⚪")
        msg = t.get("message", "") or ""
        msg_short = (msg[:60] + "…") if len(msg) > 60 else msg
        interval = t.get("interval_label", str(t.get("interval_seconds", "?")) + "s")
        lines.append(
            f"🆔 `{tid}` · {emoji} {status}\n"
            f"💬 {t.get('chat_title','?')} (`{t.get('chat_id','?')}`)\n"
            f"⏱️ {interval} · 🔁 {repeat_text} · 📨 {t.get('sent_count', 0)}\n"
            f"📝 `{msg_short}`"
        )
    return lines


def _render_omsg_page(owner_id, page):
    """(text, total_pages, total) dondurur."""
    lines = _render_omsg_lines(owner_id)
    total = len(lines)
    if total == 0:
        return "📭 **Görev yok.**", 0, 0
    ps = OMSG_PAGE_SIZE
    total_pages = (total + ps - 1) // ps
    page = max(0, min(page, total_pages - 1))
    chunk = lines[page * ps:(page + 1) * ps]
    header = f"**📋 OtoMsg Görevleri** — sayfa {page + 1}/{total_pages} (toplam {total})\n"
    body = "\n━━━━━━━━\n".join(chunk)
    foot = "\n\n▶️ Hepsini başlat: `.otomsgstartall`  ·  ⏸️ Hepsini durdur: `.otomsgstopall`"
    return header + "\n" + body + foot, total_pages, total


def _omsg_page_buttons(owner, page, total_pages):
    from telethon import Button
    rows = []
    nav = []
    if page > 0:
        nav.append(Button.inline("◀️", f"omsgpg_{owner}_{page - 1}".encode()))
    nav.append(Button.inline(f"{page + 1}/{total_pages}", f"omsgpg_{owner}_{page}".encode()))
    if page < total_pages - 1:
        nav.append(Button.inline("▶️", f"omsgpg_{owner}_{page + 1}".encode()))
    if nav:
        rows.append(nav)
    rows.append([
        Button.inline("🔄 Yenile", f"omsgpg_{owner}_{page}".encode()),
        Button.inline("❌ Kapat", f"omsgcls_{owner}".encode()),
    ])
    return rows


# ── BUTONLU EKLEME AKIŞI (.otomsg <metin> → butonlarla aralık + adet) ──
import uuid as _uuid

OM_MAX_TASKS = 50  # kullanıcı başına maksimum görev sayısı
OM_COUNT_CHOICES = [5, 30, 60, 120, 300, 500, 1000, 10000, 0]  # 0 = sınırsız


def _user_task_count(owner_id):
    """Kullanıcının diskteki görev sayısı (limit kontrolü için)."""
    try:
        return len(_load_tasks_raw().get(str(owner_id), {}))
    except Exception:
        return 0


def _om_pending_store(bot):
    """Bekleyen akış durumunu bot nesnesinde tutar (instance'lar arası paylaşımlı)."""
    if not hasattr(bot, "_om_pending"):
        bot._om_pending = {}
    return bot._om_pending


OM_PENDING_TTL = 600  # bekleyen akış ömrü (sn): 10 dk sonra terk edilmiş sayılır


def _om_prune_pending(bot):
    """Terk edilmiş (tamamlanmamış) bekleyen akışları temizler — bellek sızıntısını önler."""
    store = _om_pending_store(bot)
    if not store:
        return
    now = int(time.time())
    stale = [pid for pid, p in list(store.items()) if now - p.get("ts", now) > OM_PENDING_TTL]
    for pid in stale:
        sp = store.pop(pid, None)
        if sp and sp.get("media_path"):
            _om_remove_media(sp["media_path"])


def _om_interval_text():
    return "**⏱️ OtoMsg — Aralık**\n\nMesaj kaç **dakikada bir** gönderilsin?"


def _om_interval_buttons(pid):
    from telethon import Button
    rows, row = [], []
    for n in range(1, 31):
        row.append(Button.inline(str(n), f"om_iv_{pid}_{n}".encode()))
        if len(row) == 6:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([Button.inline("❌ İptal", f"om_cx_{pid}".encode())])
    return rows


def _om_count_text(minutes):
    return (f"**🔁 OtoMsg — Adet**\n\nHer **{minutes} dakikada** bir gönderilecek.\n"
            f"Kaç **kez** gönderilsin?")


def _om_count_buttons(pid):
    from telethon import Button
    labels = [("5", "5"), ("30", "30"), ("60", "60"), ("120", "120"),
              ("300", "300"), ("500", "500"), ("1000", "1000"), ("10000", "10000"),
              ("♾️ Sınırsız", "0")]
    rows, row = [], []
    for label, val in labels:
        row.append(Button.inline(label, f"om_ct_{pid}_{val}".encode()))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([Button.inline("⬅️ Geri", f"om_bk_{pid}".encode()),
                 Button.inline("❌ İptal", f"om_cx_{pid}".encode())])
    return rows


def _om_help_text():
    return (
        "**⚙️ OtoMsg — Kullanım**\n\n"
        "**En kolay yol:** Eklemek istediğin grupta sadece mesajı yaz:\n"
        "`.otomsg <mesaj>`\n"
        "→ Ardından **butonlardan** kaç dakikada bir ve kaç kez gönderileceğini seç.\n"
        "Komut silinir, grupta iz kalmaz.\n\n"
        "**📎 Medya:** Bir foto/video/dosyayı **yanıtlayıp** `.otomsg <caption>` yaz "
        "(caption boş olabilir) → o medya tekrar tekrar gönderilir.\n\n"
        "**Diğer komutlar:**\n"
        "`.otomsgl` → Görevlerin (butonlu liste)\n"
        "`.otomsgstop <id>` / `.otomsgstart <id>` → Durdur / başlat\n"
        "`.otomsgstartall` / `.otomsgstopall` → Tümünü\n"
        "`.otomsgdel <id>` → Sil\n"
        "`.otomsgduzenle <id> mesaj|aralık|tekrar <değer>` → Görevi düzenle\n"
        "`.otomsg ekle <chat> <dk> <tekrar> <mesaj>` → Elle ekleme (ileri düzey)\n"
        "`.otomsghelp` → Detaylı yardım"
    )


def _om_help_buttons(owner):
    from telethon import Button
    return [[Button.inline("📋 Görevlerim", f"om_list_{owner}".encode()),
             Button.inline("❌ Kapat", f"omsgcls_{owner}".encode())]]


async def create_task_from_flow(client, chat_id, chat_title, message, minutes, count, notify_to, media_path=None):
    """Buton akışından görev oluştur + başlat.
    SAHİBİN modül instance'ında çağrılır → tasks_data/running_tasks doğru sahibe ait."""
    await load_my_tasks(client)
    task_id = _next_task_id()
    tasks_data[task_id] = {
        "chat_id": chat_id,
        "chat_title": chat_title,
        "chat_raw": str(chat_id),
        "interval_seconds": minutes * 60,
        "interval_label": f"{minutes} dakika",
        "repeat_count": count,  # 0 = sınırsız
        "message": message,
        "media_path": media_path,
        "sent_count": 0,
        "status": "running",
        "created_at": int(time.time()),
        "last_sent": None,
        "last_error": None,
    }
    await save_my_tasks(client)
    await _start_task(client, task_id, notify_to)
    return task_id


async def _show_om_flow_panel(q, pid):
    """Aralık panelini gösterir: sohbet inline destekliyorsa satıriçi, değilse bottan özelden."""
    bot = _get_bot()
    if bot is not None:
        _register_otomsg_bot_handlers(bot)
    bu = _get_bot_username()
    if bot is not None and bu:
        try:
            results = await q.client.inline_query(bu, f"omadd_{pid}")
            if results:
                await results[0].click(q.chat_id)
                return True
        except Exception:
            pass
    if bot is not None:
        try:
            owner = _om_pending_store(bot).get(pid, {}).get("owner")
            if owner:
                await bot.send_message(owner, _om_interval_text(), buttons=_om_interval_buttons(pid))
                return True
        except Exception:
            pass
    return False


async def _show_om_help_panel(q, owner):
    """Kullanım kılavuzu panelini gösterir (inline ya da özelden)."""
    bot = _get_bot()
    if bot is not None:
        _register_otomsg_bot_handlers(bot)
    bu = _get_bot_username()
    if bot is not None and bu:
        try:
            results = await q.client.inline_query(bu, f"omhelp_{owner}")
            if results:
                await results[0].click(q.chat_id)
                return True
        except Exception:
            pass
    if bot is not None:
        try:
            await bot.send_message(owner, _om_help_text(), buttons=_om_help_buttons(owner))
            return True
        except Exception:
            pass
    return False


def _register_otomsg_bot_handlers(bot):
    if getattr(bot, "_otomsg_pag_registered", False):
        return
    bot._otomsg_pag_registered = True
    from telethon import events
    import re as _re

    @bot.on(events.InlineQuery())
    async def _omsg_inline(event):
        m = _re.match(r"omsgl_(\d+)$", event.text or "")
        if not m:
            return
        owner = int(m.group(1))
        text, total_pages, total = _render_omsg_page(owner, 0)
        try:
            result = event.builder.article(
                title="📋 OtoMsg Görevleri",
                description=f"{total} görev",
                text=text,
                buttons=_omsg_page_buttons(owner, 0, total_pages) if total_pages else None,
            )
            await event.answer([result], cache_time=0)
        except Exception:
            pass

    @bot.on(events.CallbackQuery(pattern=rb"omsgpg_(\d+)_(\d+)"))
    async def _omsg_pg_cb(event):
        owner = int(event.pattern_match.group(1))
        page = int(event.pattern_match.group(2))
        if event.sender_id != owner:
            await event.answer("Bu liste sana ait değil.", alert=True)
            return
        text, total_pages, total = _render_omsg_page(owner, page)
        try:
            await event.edit(text, buttons=_omsg_page_buttons(owner, page, total_pages) if total_pages else None)
        except Exception:
            pass

    @bot.on(events.CallbackQuery(pattern=rb"omsgcls_(\d+)"))
    async def _omsg_cls_cb(event):
        owner = int(event.pattern_match.group(1))
        if event.sender_id != owner:
            await event.answer("Bu liste sana ait değil.", alert=True)
            return
        try:
            await event.edit("✅ Liste kapatıldı.")
        except Exception:
            pass

    @bot.on(events.InlineQuery())
    async def _om_flow_inline(event):
        qtext = event.text or ""
        ma = _re.match(r"omadd_([0-9a-f]+)$", qtext)
        mh = _re.match(r"omhelp_(\d+)$", qtext)
        if ma:
            pid = ma.group(1)
            try:
                result = event.builder.article(
                    title="⏱️ OtoMsg — Aralık seç",
                    description="Kaç dakikada bir gönderilsin?",
                    text=_om_interval_text(),
                    buttons=_om_interval_buttons(pid),
                )
                await event.answer([result], cache_time=0)
            except Exception:
                pass
        elif mh:
            owner = int(mh.group(1))
            try:
                result = event.builder.article(
                    title="⚙️ OtoMsg — Kullanım",
                    description="Buton menüsü",
                    text=_om_help_text(),
                    buttons=_om_help_buttons(owner),
                )
                await event.answer([result], cache_time=0)
            except Exception:
                pass

    @bot.on(events.CallbackQuery(pattern=rb"om_iv_([0-9a-f]+)_(\d+)"))
    async def _om_iv_cb(event):
        pid = event.pattern_match.group(1).decode()
        minutes = int(event.pattern_match.group(2).decode())
        pend = _om_pending_store(bot).get(pid)
        if not pend or event.sender_id != pend.get("owner"):
            await event.answer("Bu menü sana ait değil veya süresi doldu.", alert=True)
            return
        pend["interval"] = minutes
        try:
            await event.edit(_om_count_text(minutes), buttons=_om_count_buttons(pid))
        except Exception:
            pass

    @bot.on(events.CallbackQuery(pattern=rb"om_bk_([0-9a-f]+)"))
    async def _om_bk_cb(event):
        pid = event.pattern_match.group(1).decode()
        pend = _om_pending_store(bot).get(pid)
        if not pend or event.sender_id != pend.get("owner"):
            await event.answer("Bu menü sana ait değil veya süresi doldu.", alert=True)
            return
        try:
            await event.edit(_om_interval_text(), buttons=_om_interval_buttons(pid))
        except Exception:
            pass

    @bot.on(events.CallbackQuery(pattern=rb"om_cx_([0-9a-f]+)"))
    async def _om_cx_cb(event):
        pid = event.pattern_match.group(1).decode()
        store = _om_pending_store(bot)
        pend = store.get(pid)
        if pend and event.sender_id != pend.get("owner"):
            await event.answer("Bu menü sana ait değil.", alert=True)
            return
        store.pop(pid, None)
        try:
            await event.edit("❌ OtoMsg ekleme iptal edildi.")
        except Exception:
            pass

    @bot.on(events.CallbackQuery(pattern=rb"om_ct_([0-9a-f]+)_(\d+)"))
    async def _om_ct_cb(event):
        pid = event.pattern_match.group(1).decode()
        count = int(event.pattern_match.group(2).decode())
        store = _om_pending_store(bot)
        pend = store.get(pid)
        if not pend or event.sender_id != pend.get("owner"):
            await event.answer("Bu menü sana ait değil veya süresi doldu.", alert=True)
            return
        owner = pend["owner"]
        minutes = pend.get("interval") or 1
        try:
            from userbot.smart_manager import smart_session_manager
            client = smart_session_manager.get_client(owner)
        except Exception:
            client = None
        if client is None:
            await event.answer("Hesap bağlantısı bulunamadı.", alert=True)
            return
        if _user_task_count(owner) >= OM_MAX_TASKS:
            store.pop(pid, None)
            try:
                await event.edit(f"❌ En fazla {OM_MAX_TASKS} görev olabilir.")
            except Exception:
                pass
            return
        task_id = None
        try:
            owner_module = None
            try:
                from userbot.plugins import plugin_manager
                owner_module = plugin_manager.user_active_plugins.get(owner, {}).get("otomsg")
            except Exception:
                owner_module = None
            creator = getattr(owner_module, "create_task_from_flow", None) or create_task_from_flow
            task_id = await creator(client, pend["chat_id"], pend["chat_title"],
                                    pend["text"], minutes, count, pend["notify_to"], pend.get("media_path"))
        except Exception as e:
            store.pop(pid, None)
            try:
                await event.edit(f"❌ Görev oluşturulamadı: {e}")
            except Exception:
                pass
            return
        store.pop(pid, None)
        cnt_label = "sınırsız" if count == 0 else f"{count} kez"
        msg_short = (pend["text"][:60] + "…") if len(pend["text"]) > 60 else pend["text"]
        try:
            await event.edit(
                f"✅ **OtoMsg eklendi!**\n\n"
                f"🆔 `{task_id}`\n"
                f"💬 {pend['chat_title']}\n"
                f"⏱️ Her {minutes} dk · 🔁 {cnt_label}\n"
                f"📝 `{msg_short}`\n\n"
                f"📋 `.otomsgl`  ·  ⏸️ `.otomsgstop {task_id}`  ·  🗑️ `.otomsgdel {task_id}`"
            )
        except Exception:
            pass

    @bot.on(events.CallbackQuery(pattern=rb"om_list_(\d+)"))
    async def _om_list_cb(event):
        owner = int(event.pattern_match.group(1).decode())
        if event.sender_id != owner:
            await event.answer("Bu liste sana ait değil.", alert=True)
            return
        text, total_pages, total = _render_omsg_page(owner, 0)
        try:
            await event.edit(text, buttons=_omsg_page_buttons(owner, 0, total_pages) if total_pages else None)
        except Exception:
            pass


async def _show_otomsg_list_panel(q, owner):
    """Inline (bot uzerinden) butonlu liste panelini gosterir. Basarisizsa False."""
    bot = _get_bot()
    if bot is not None:
        _register_otomsg_bot_handlers(bot)
    bu = _get_bot_username()
    if bot is not None and bu:
        try:
            results = await q.client.inline_query(bu, f"omsgl_{owner}")
            if results:
                await results[0].click(q.chat_id)
                try:
                    await q.delete()
                except Exception:
                    pass
                return True
        except Exception:
            pass
    return False


# ==========================================
# KOMUTLAR
# ==========================================

@r(outgoing=True, pattern=r"^\.otomsg ekle(?: |$)(.*)")
async def otomsg_add(q):
    """Yeni otomatik mesaj görevi ekle. Reply ile veya düz metin ile kullanılabilir."""
    me = await q.client.get_me()
    if q.sender_id != me.id:
        return

    await load_my_tasks(q.client)

    raw = q.pattern_match.group(1).strip()
    reply_msg = await q.get_reply_message()

    # ── Parametre ayrıştırma ──────────────────────────────────────────
    # Reply modunda söz dizimi: <chat> <aralık_dk> <tekrar>   (mesaj yok)
    # Normal modda söz dizimi : <chat> <aralık_dk> <tekrar> <mesaj>
    parts = raw.split(maxsplit=3)

    # Kaç parametre gerekli: reply varsa 3, yoksa 4
    min_parts = 3 if reply_msg else 4

    if len(parts) < min_parts:
        await q.edit(
            "❌ **Eksik parametre!**\n\n"
            "**📌 Normal kullanım:**\n"
            "`.otomsg ekle <chat> <aralık_dk> <tekrar> <mesaj>`\n\n"
            "**📌 Reply ile kullanım:**\n"
            "Göndermek istediğin mesajı yanıtlayıp:\n"
            "`.otomsg ekle <chat> <aralık_dk> <tekrar>`\n\n"
            "**Parametreler:**\n"
            "• `chat` — @username veya chat ID\n"
            "• `aralık_dk` — Kaç dakikada bir (min 1)\n"
            "• `tekrar` — Kaç kere (0 = sınırsız)\n\n"
            "**Örnekler:**\n"
            "`.otomsg ekle @grupadi 30 10 Merhaba!`\n"
            "`[mesajı yanıtla]` `.otomsg ekle @grupadi 30 10`"
        )
        return

    chat_raw     = parts[0]
    interval_raw = parts[1]
    repeat_raw   = parts[2]
    # Mesaj kaynağını belirle
    if reply_msg:
        message = reply_msg.text or reply_msg.message or ""
        if not message:
            await q.edit("❌ **Yanıtlanan mesajda metin bulunamadı!**\n\nSadece metin içeren mesajları yanıtlayın.")
            return
        source_label = "↩️ Reply"
    else:
        message = parts[3] if len(parts) > 3 else ""
        if not message:
            await q.edit("❌ **Mesaj metni boş olamaz!**")
            return
        source_label = "✏️ Metin"

    # Aralık kontrolü
    interval_seconds, interval_label = parse_interval(interval_raw)
    if interval_seconds is None:
        await q.edit(f"❌ **Geçersiz aralık!** {interval_label}\n\n"
                     "**Örnekler:** `30s` (30 saniye), `5d` (5 dakika), `10` (10 dakika)")
        return

    # Tekrar kontrolü
    if not repeat_raw.isdigit():
        await q.edit("❌ **Tekrar sayısı sayı olmalıdır! (0 = sınırsız)**")
        return

    repeat_count = int(repeat_raw)

    # Chat doğrulama
    await q.edit("⏳ **Chat doğrulanıyor...**")
    try:
        _, chat_id, chat_title = await resolve_chat(q.client, chat_raw)
    except Exception as e:
        await q.edit(
            f"❌ **Chat bulunamadı!**\n\n"
            f"`{chat_raw}` → `{str(e)[:120]}`\n\n"
            f"• @username, tam ID veya t.me/grupadi formatı deneyin\n"
            f"• Botu/hesabı önce gruba ekleyin, sonra tekrar deneyin"
        )
        return

    # Görevi kaydet
    task_id = _next_task_id()
    tasks_data[task_id] = {
        "chat_id": chat_id,
        "chat_title": chat_title,
        "chat_raw": chat_raw,
        "interval_seconds": interval_seconds,
        "interval_label": interval_label,
        "repeat_count": repeat_count,
        "message": message,
        "sent_count": 0,
        "status": "running",
        "created_at": int(time.time()),
        "last_sent": None,
        "last_error": None,
    }
    await save_my_tasks(q.client)

    # Döngüyü başlat
    await _start_task(q.client, task_id, q.chat_id)

    repeat_text = "sınırsız" if repeat_count == 0 else f"{repeat_count} kere"
    await q.edit(
        f"✅ **OtoMsg görevi eklendi!**\n\n"
        f"🆔 **Görev ID:** `{task_id}`\n"
        f"💬 **Chat:** {chat_title} (`{chat_id}`)\n"
        f"⏱️ **Aralık:** {interval_label}\n"
        f"🔁 **Tekrar:** {repeat_text}\n"
        f"📝 **Mesaj kaynağı:** {source_label}\n"
        f"📄 **Mesaj:** `{message[:60]}{'...' if len(message) > 60 else ''}`\n\n"
        f"Durdurmak için: `.otomsgstop {task_id}`\n"
        f"Silmek için: `.otomsgdel {task_id}`"
    )


# ── MEDYA DESTEĞİ (bir medyayı yanıtlayıp .otomsg → medyalı görev) ──
OM_MEDIA_DIR = os.path.join(os.path.dirname(__file__), "otomsg_media")
try:
    os.makedirs(OM_MEDIA_DIR, exist_ok=True)
except Exception:
    pass


async def _om_reply_has_media(q):
    """Komut bir MEDYA mesajını yanıtlıyor mu?"""
    try:
        if getattr(q, "reply_to_msg_id", None):
            r = await q.get_reply_message()
            return bool(r and getattr(r, "media", None))
    except Exception:
        pass
    return False


async def _om_download_reply_media(q, pid):
    """Yanıtlanan medyayı OM_MEDIA_DIR/{pid}* olarak indirir, yolu döndürür (yoksa None)."""
    try:
        if not getattr(q, "reply_to_msg_id", None):
            return None
        r = await q.get_reply_message()
        if not r or not getattr(r, "media", None):
            return None
        return await q.client.download_media(r, file=os.path.join(OM_MEDIA_DIR, pid))
    except Exception:
        return None


def _om_remove_media(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


async def _om_send(client, target, media_path, message):
    """Görev mesajını gönderir: medya varsa caption ile dosya, yoksa düz metin."""
    if media_path and os.path.exists(media_path):
        await client.send_file(target, media_path, caption=(message or None))
    else:
        await client.send_message(target, message)


async def _om_begin_flow(q, me, message):
    """50 limit + hedef + bot + (varsa) medya indir + bekleyen kayıt + buton paneli."""
    bu = _get_bot_username()
    notify_to = f"@{bu}" if bu else "me"
    if _user_task_count(me.id) >= OM_MAX_TASKS:
        try:
            await q.delete()
        except Exception:
            pass
        try:
            await q.client.send_message(notify_to, f"❌ OtoMsg: en fazla {OM_MAX_TASKS} görev olabilir. Sil: `.otomsgdel <id>`")
        except Exception:
            pass
        return
    chat_id = q.chat_id
    try:
        chat = await q.get_chat()
        chat_title = getattr(chat, "title", None) or getattr(chat, "first_name", None) or str(chat_id)
    except Exception:
        chat_title = str(chat_id)
    bot = _get_bot()
    if bot is None:
        try:
            await q.delete()
        except Exception:
            pass
        try:
            await q.client.send_message(notify_to, "❌ OtoMsg: bot bulunamadı, panel açılamadı.")
        except Exception:
            pass
        return
    _om_prune_pending(bot)
    pid = _uuid.uuid4().hex[:8]
    media_path = await _om_download_reply_media(q, pid)
    if media_path is None and not message:
        return
    _om_pending_store(bot)[pid] = {
        "owner": me.id,
        "text": message,
        "chat_id": chat_id,
        "chat_title": chat_title,
        "notify_to": notify_to,
        "interval": None,
        "media_path": media_path,
        "ts": int(time.time()),
    }
    ok = await _show_om_flow_panel(q, pid)
    try:
        await q.delete()
    except Exception:
        pass
    if not ok:
        pp = _om_pending_store(bot).pop(pid, None)
        if pp and pp.get("media_path"):
            _om_remove_media(pp["media_path"])
        try:
            await q.client.send_message(notify_to, "❌ OtoMsg: buton paneli açılamadı. Elle: `.otomsg ekle ...`")
        except Exception:
            pass


@r(outgoing=True, pattern=r"^\.otomsg$")
async def otomsg_menu(q):
    """`.otomsg` → bir medyayı yanıtladıysan medyalı görev akışı, yoksa butonlu kullanım kılavuzu."""
    me = await q.client.get_me()
    if q.sender_id != me.id:
        return
    if await _om_reply_has_media(q):
        await _om_begin_flow(q, me, "")
        return
    ok = await _show_om_help_panel(q, me.id)
    try:
        await q.delete()
    except Exception:
        pass
    if not ok:
        try:
            await q.client.send_message("me", _om_help_text())
        except Exception:
            pass


@r(outgoing=True, pattern=r"(?s)^\.otomsg (?!ekle(?: |$))(.+)$")
async def otomsg_flow(q):
    """`.otomsg <mesaj>` → metin veya (yanıtlanan medya + caption) görevi; butonlarla aralık+adet."""
    me = await q.client.get_me()
    if q.sender_id != me.id:
        return
    message = (q.pattern_match.group(1) or "").strip()
    if not message and not await _om_reply_has_media(q):
        return
    await _om_begin_flow(q, me, message)


@r(outgoing=True, pattern=r"^\.otomsgs$")
async def otomsg_status(q):
    """Tüm görevlerin durumunu göster."""
    me = await q.client.get_me()
    if q.sender_id != me.id:
        return

    await load_my_tasks(q.client)

    if not tasks_data:
        await q.edit("📭 **Kayıtlı otomatik mesaj görevi yok.**\n\nEklemek için: `.otomsghelp`")
        return

    status_icons = {
        "running": "🟢",
        "stopped": "🔴",
        "error": "🚨",
        "completed": "✅",
    }

    lines = ["**📊 OtoMsg Görev Durumları**\n"]
    for task_id, t in tasks_data.items():
        icon = status_icons.get(t.get("status", "stopped"), "⚪")
        repeat_text = "∞" if t["repeat_count"] == 0 else f"{t['sent_count']}/{t['repeat_count']}"
        is_alive = task_id in running_tasks and not running_tasks[task_id].done()
        alive_icon = "⚡" if is_alive else "💤"
        last_err = f"\n   ⚠️ Son hata: {t['last_error'][:50]}" if t.get("last_error") and t.get("status") == "error" else ""
        lines.append(
            f"{icon} **#{task_id}** {alive_icon} — {t['chat_title'][:25]}\n"
            f"   ⏱️ {t.get('interval_label', str(t.get('interval_seconds', t.get('interval_minutes',0)*60))+'s')} | 📨 {repeat_text} | {t.get('status','?')}{last_err}"
        )

    await q.edit("\n".join(lines))


@r(outgoing=True, pattern=r"^\.otomsgl$")
async def otomsg_list(q):
    """Görev listesini butonlu/sayfalı gösterir (uzun listede çökmez)."""
    me = await q.client.get_me()
    if q.sender_id != me.id:
        return

    await load_my_tasks(q.client)
    if not tasks_data:
        await q.edit("📭 **Görev yok.**")
        return

    # 1) Butonlu inline panel dene
    ok = await _show_otomsg_list_panel(q, me.id)
    if ok:
        return

    # 2) Fallback: inline kapalıysa parçalı düz mesajlar (4096 limitini aşmaz)
    lines = _render_omsg_lines(me.id)
    blocks = []
    cur = f"**📋 OtoMsg Görevleri** (toplam {len(lines)})\n"
    for ln in lines:
        piece = "\n━━━━━━━━\n" + ln
        if len(cur) + len(piece) > 3800:
            blocks.append(cur)
            cur = ""
        cur += piece
    if cur:
        blocks.append(cur)

    try:
        await q.edit(blocks[0])
    except Exception:
        pass
    for b in blocks[1:]:
        try:
            await q.respond(b)
        except Exception:
            pass


@r(outgoing=True, pattern=r"^\.otomsgdel(?: |$)(.*)")
async def otomsg_delete(q):
    """Görevi sil."""
    me = await q.client.get_me()
    if q.sender_id != me.id:
        return

    await load_my_tasks(q.client)

    task_id = q.pattern_match.group(1).strip()
    if not task_id:
        await q.edit("❌ **Görev ID gerekli!**\n\nÖrnek: `.otomsgdel 1`\nID için: `.otomsgl`")
        return

    if task_id not in tasks_data:
        await q.edit(f"❌ **#{task_id} ID'li görev bulunamadı!**")
        return

    # Çalışan task'ı iptal et
    if task_id in running_tasks:
        running_tasks[task_id].cancel()
        running_tasks.pop(task_id, None)

    chat_title = tasks_data[task_id].get("chat_title", "?")
    _om_remove_media(tasks_data[task_id].get("media_path"))
    del tasks_data[task_id]
    await save_my_tasks(q.client)

    await q.edit(
        f"🗑️ **Görev silindi!**\n\n"
        f"🆔 **ID:** `{task_id}`\n"
        f"💬 **Chat:** {chat_title}"
    )


@r(outgoing=True, pattern=r"^\.otomsgkopyala(?: |$)(.*)")
async def otomsg_copy(q):
    """Mevcut görevin ayarlarını yeni bir chat için kopyala."""
    me = await q.client.get_me()
    if q.sender_id != me.id:
        return

    await load_my_tasks(q.client)

    raw = q.pattern_match.group(1).strip()
    parts = raw.split(maxsplit=1)

    if len(parts) < 2:
        await q.edit(
            "❌ **Eksik parametre!**\n\n"
            "**Kullanım:**\n"
            "`.otomsgkopyala <id> <yeni_chat>`\n\n"
            "**Örnek:**\n"
            "`.otomsgkopyala 3 @yenigrup`\n"
            "`.otomsgkopyala 1 -1001234567890`\n\n"
            "Görev ID'leri için: `.otomsgl`"
        )
        return

    src_id, chat_raw = parts[0], parts[1]

    if src_id not in tasks_data:
        await q.edit(f"❌ **#{src_id} ID'li görev bulunamadı!**\n\nMevcut görevler için: `.otomsgl`")
        return

    src = tasks_data[src_id]

    # Yeni chat doğrula
    await q.edit("⏳ **Chat doğrulanıyor...**")
    try:
        _, new_chat_id, new_chat_title = await resolve_chat(q.client, chat_raw)
    except Exception as e:
        await q.edit(
            f"❌ **Chat bulunamadı!**\n\n"
            f"`{chat_raw}` → `{str(e)[:120]}`\n\n"
            f"• @username, tam ID veya t.me/grupadi formatı deneyin\n"
            f"• Botu/hesabı önce gruba ekleyin, sonra tekrar deneyin"
        )
        return

    # Yeni görevi oluştur (kaynak görevin ayarlarını kopyala, sadece chat değişir)
    new_id = _next_task_id()
    tasks_data[new_id] = {
        "chat_id": new_chat_id,
        "chat_title": new_chat_title,
        "chat_raw": chat_raw,
        "interval_seconds": src.get("interval_seconds", src.get("interval_minutes", 1) * 60),
        "interval_label": src.get("interval_label", f"{src.get('interval_minutes','?')} dakika"),
        "repeat_count": src["repeat_count"],
        "message": src["message"],
        "sent_count": 0,
        "status": "running",
        "created_at": int(time.time()),
        "last_sent": None,
        "last_error": None,
    }
    await save_my_tasks(q.client)

    # Döngüyü başlat
    await _start_task(q.client, new_id, q.chat_id)

    repeat_text = "sınırsız" if src["repeat_count"] == 0 else f"{src['repeat_count']} kere"
    await q.edit(
        f"✅ **Görev kopyalandı!**\n\n"
        f"📋 **Kaynak görev:** #{src_id} ({src['chat_title']})\n"
        f"🆔 **Yeni görev ID:** `{new_id}`\n"
        f"💬 **Yeni chat:** {new_chat_title} (`{new_chat_id}`)\n"
        f"⏱️ **Aralık:** {src.get('interval_label', str(src.get('interval_seconds','?'))+'s')}\n"
        f"🔁 **Tekrar:** {repeat_text}\n"
        f"📝 **Mesaj:** `{src['message'][:60]}{'...' if len(src['message']) > 60 else ''}`\n\n"
        f"Durdurmak için: `.otomsgstop {new_id}`\n"
        f"Silmek için: `.otomsgdel {new_id}`"
    )


@r(outgoing=True, pattern=r"(?s)^\.otomsgduzenle (\S+)\s+(mesaj|aralık|aralik|tekrar|adet)\s+(.+)$")
async def otomsg_edit(q):
    """Var olan görevi düzenle: `.otomsgduzenle <id> mesaj|aralık|tekrar <değer>`.
    Çalışan görev yeni ayarla yeniden başlatılır (gönderim sayacı korunur)."""
    me = await q.client.get_me()
    if q.sender_id != me.id:
        return
    await load_my_tasks(q.client)

    task_id = q.pattern_match.group(1).strip()
    field = q.pattern_match.group(2).strip().lower()
    value = q.pattern_match.group(3).strip()

    if task_id not in tasks_data:
        await q.edit(f"❌ **#{task_id} ID'li görev bulunamadı!**")
        return

    if field == "mesaj":
        if not value:
            await q.edit("❌ Mesaj boş olamaz.")
            return
        tasks_data[task_id]["message"] = value
        changed = f"📝 Mesaj güncellendi: `{value[:60]}{'…' if len(value) > 60 else ''}`"
    elif field in ("aralık", "aralik"):
        try:
            minutes = int(value)
        except ValueError:
            await q.edit("❌ Aralık bir sayı (dakika) olmalı. Örn: `.otomsgduzenle 1 aralık 15`")
            return
        if minutes < 1:
            await q.edit("❌ Aralık en az 1 dakika olmalı.")
            return
        tasks_data[task_id]["interval_seconds"] = minutes * 60
        tasks_data[task_id]["interval_label"] = f"{minutes} dakika"
        changed = f"⏱️ Aralık güncellendi: her {minutes} dakika"
    else:  # tekrar / adet
        try:
            count = int(value)
        except ValueError:
            await q.edit("❌ Tekrar bir sayı olmalı (0 = sınırsız). Örn: `.otomsgduzenle 1 tekrar 100`")
            return
        if count < 0:
            await q.edit("❌ Tekrar 0 veya daha büyük olmalı (0 = sınırsız).")
            return
        tasks_data[task_id]["repeat_count"] = count
        # Tamamlanmış görevi yeni limit yeterliyse yeniden canlandır
        if tasks_data[task_id].get("status") == "completed" and (count == 0 or count > tasks_data[task_id].get("sent_count", 0)):
            tasks_data[task_id]["status"] = "running"
        changed = f"🔁 Tekrar güncellendi: {'sınırsız' if count == 0 else str(count) + ' kez'}"

    await save_my_tasks(q.client)

    # Çalışan görevi yeni ayarlarla yeniden başlat (döngü interval/mesaj'ı başta okur)
    t = running_tasks.pop(task_id, None)
    if t is not None and not t.done():
        t.cancel()
    if tasks_data[task_id].get("status") == "running":
        bu = _get_bot_username()
        notify_to = f"@{bu}" if bu else "me"
        await _start_task(q.client, task_id, notify_to)

    await q.edit(f"✅ **Görev #{task_id} düzenlendi**\n\n{changed}")


@r(outgoing=True, pattern=r"^\.otomsgstop(?: |$)(.*)")
async def otomsg_stop(q):
    """Görevi geçici durdur."""
    me = await q.client.get_me()
    if q.sender_id != me.id:
        return

    await load_my_tasks(q.client)

    task_id = q.pattern_match.group(1).strip()
    if not task_id:
        await q.edit("❌ **Görev ID gerekli!**\n\nÖrnek: `.otomsgstop 1`")
        return

    if task_id not in tasks_data:
        await q.edit(f"❌ **#{task_id} ID'li görev bulunamadı!**")
        return

    if tasks_data[task_id].get("status") == "stopped":
        await q.edit(f"⚠️ **Görev #{task_id} zaten durdurulmuş!**")
        return

    tasks_data[task_id]["status"] = "stopped"
    await save_my_tasks(q.client)

    # Task'ı iptal etme — döngü 'stopped' durumunu fark edip bekleyecek
    await q.edit(
        f"⏸️ **Görev #{task_id} durduruldu!**\n\n"
        f"💬 **Chat:** {tasks_data[task_id]['chat_title']}\n"
        f"Yeniden başlatmak için: `.otomsgstart {task_id}`"
    )


@r(outgoing=True, pattern=r"^\.otomsgstart(?: |$)(.*)")
async def otomsg_start(q):
    """Durdurulan görevi yeniden başlat."""
    me = await q.client.get_me()
    if q.sender_id != me.id:
        return

    await load_my_tasks(q.client)

    task_id = q.pattern_match.group(1).strip()
    if not task_id:
        await q.edit("❌ **Görev ID gerekli!**\n\nÖrnek: `.otomsgstart 1`")
        return

    if task_id not in tasks_data:
        await q.edit(f"❌ **#{task_id} ID'li görev bulunamadı!**")
        return

    current_status = tasks_data[task_id].get("status")
    if current_status == "completed":
        await q.edit(f"✅ **Görev #{task_id} tamamlanmış!**\n\nYeniden başlatmak için önce tekrar sayısını güncelleyin veya yeni görev ekleyin.")
        return

    if current_status == "running":
        # Döngü çalışıyor mu kontrol et
        if task_id in running_tasks and not running_tasks[task_id].done():
            await q.edit(f"⚠️ **Görev #{task_id} zaten çalışıyor!**")
            return

    # Durumu 'running' yap
    tasks_data[task_id]["status"] = "running"
    tasks_data[task_id]["last_error"] = None
    await save_my_tasks(q.client)

    # Eğer task döngüsü ölmüşse yeniden başlat
    if task_id not in running_tasks or running_tasks[task_id].done():
        await _start_task(q.client, task_id, q.chat_id)

    await q.edit(
        f"▶️ **Görev #{task_id} başlatıldı!**\n\n"
        f"💬 **Chat:** {tasks_data[task_id]['chat_title']}\n"
        f"⏱️ **Aralık:** {tasks_data[task_id].get('interval_label', str(tasks_data[task_id].get('interval_seconds','?'))+'s')}\n"
        f"📨 **Gönderilen:** {tasks_data[task_id].get('sent_count', 0)}"
    )


@r(outgoing=True, pattern=r"^\.otomsgstartall$")
async def otomsg_start_all(q):
    """Tüm (tamamlanmamış) görevleri tek seferde başlatır."""
    me = await q.client.get_me()
    if q.sender_id != me.id:
        return

    await load_my_tasks(q.client)
    if not tasks_data:
        await q.edit("📭 **Görev yok.**")
        return

    started = 0
    already = 0
    for task_id, t in tasks_data.items():
        if t.get("status") == "completed":
            continue
        t["status"] = "running"
        t["last_error"] = None
        if task_id not in running_tasks or running_tasks[task_id].done():
            await _start_task(q.client, task_id, q.chat_id, initial_delay=started * 5)
            started += 1
        else:
            already += 1
    await save_my_tasks(q.client)

    await q.edit(
        f"▶️ **Tüm görevler başlatıldı!**\n\n"
        f"🆕 Yeni başlatılan: {started}\n"
        f"🟢 Zaten çalışan: {already}"
    )


@r(outgoing=True, pattern=r"^\.otomsgstopall$")
async def otomsg_stop_all(q):
    """Tüm çalışan görevleri tek seferde durdurur."""
    me = await q.client.get_me()
    if q.sender_id != me.id:
        return

    await load_my_tasks(q.client)
    if not tasks_data:
        await q.edit("📭 **Görev yok.**")
        return

    stopped = 0
    for task_id, t in tasks_data.items():
        if t.get("status") == "running":
            t["status"] = "stopped"
            stopped += 1
        if task_id in running_tasks:
            try:
                running_tasks[task_id].cancel()
            except Exception:
                pass
            running_tasks.pop(task_id, None)
    await save_my_tasks(q.client)

    await q.edit(f"⏸️ **Tüm görevler durduruldu!**\n\nDurdurulan: {stopped}")


@r(outgoing=True, pattern=r"^\.otomsghelp$")
async def otomsg_help(q):
    """Detaylı yardım mesajı."""
    me = await q.client.get_me()
    if q.sender_id != me.id:
        return

    help_text = """**⚙️ OtoMsg PLUGİN — YARDIM**

**⚡ HIZLI EKLEME (önerilen):**
Eklemek istediğin grupta şunu yaz:
`.otomsg <mesaj> <dakika>`
→ Komut **silinir**, grupta bildirim **çıkmaz**, onay **sana (bota)** gelir.
Örnek: `.otomsg Grup aktif kalsın 30`

**📌 GÖREV EKLEME — Normal:**
`.otomsg ekle <chat> <aralık_dk> <tekrar> <mesaj>`

• `chat` → @username **veya** chat ID (örn: `-1001234567890`)
• `aralık_dk` → Kaç dakikada bir gönderilsin (min 1)
• `tekrar` → Kaç kere gönderilsin (`0` = sınırsız)
• `mesaj` → Gönderilecek metin

**📌 GÖREV EKLEME — Reply ile:**
Göndermek istediğin mesajı **yanıtlayıp** şunu yaz:
`.otomsg ekle <chat> <aralık_dk> <tekrar>`
(mesaj parametresi gerekmez, yanıtlanan mesaj kullanılır)

**💡 Örnekler:**
`.otomsg ekle @grupadi 30 10 Merhaba!`
→ Her 30 dakikada bir, 10 kere "Merhaba!" gönderir

`[mesajı yanıtla]` `.otomsg ekle @grupadi 30d 10`
→ Yanıtlanan mesajı her 30 dakikada bir, 10 kere gönderir

`.otomsg ekle @grupadi 45s 0 Bildirim`
→ Her 45 saniyede bir, sınırsız "Bildirim" gönderir

`.otomsg ekle -100123456 5d 0 Bildirim`
→ Her 5 dakikada bir, sınırsız "Bildirim" gönderir

`.otomsg ekle @kanal 60d 24 Günlük duyuru`
→ Saatte bir, 24 kere gönderir (1 gün)

**📋 GÖREV KOPYALAMA:**
`.otomsgkopyala <id> <yeni_chat>` → Görevin mesaj/aralık/tekrar ayarlarını koruyarak farklı bir chat için kopyalar

**Örnek:**
`.otomsgkopyala 3 @yenigrup`
→ Görev #3'ün aynı mesaj ve ayarlarıyla @yenigrup için yeni görev başlatır

**📊 DURUM & LİSTE:**
`.otomsgs` → Tüm görevlerin kısa durumu
`.otomsgl` → Tüm görevlerin **butonlu/sayfalı** listesi (uzun listede çökmez)

**🎮 KONTROL:**
`.otomsgstop <id>` → Görevi geçici durdur
`.otomsgstart <id>` → Durdurulan görevi başlat
`.otomsgstartall` → **Tüm** görevleri başlat (toplu)
`.otomsgstopall` → **Tüm** görevleri durdur (toplu)
`.otomsgdel <id>` → Görevi kalıcı sil

**🚨 HATA YÖNETİMİ:**
• Grup kapalı/ban/gizli gibi ölümcül hatalarda görev **otomatik durur**
• Size bildirim mesajı gelir
• Sorunu çözüp `.otomsgstart <id>` ile devam edebilirsiniz
• Üst üste 5 hata olursa da görev otomatik durur

**📁 VERİ:**
Görevler `otomsg_tasks.json` dosyasına kaydedilir.
Bot yeniden başlasa bile aktif görevler devam eder.

**⚠️ NOTLAR:**
• Flood almamak için çok kısa aralık kullanmayın (min 5dk önerilir)
• `repeat=0` sınırsız anlamına gelir, manuel silmeniz gerekir
• Her hesap kendi görevlerini görür (çoklu hesap desteği var)
"""
    try:
        await q.edit(help_text)
    except Exception:
        pass


# ==========================================
# BOT BAŞLADIĞINDA GÖREVLERİ RESTORE ET
# ==========================================

async def _on_start(client):
    """Bot/userbot başlayınca BU HESABIN çalışan görevlerini yeniden başlatır."""
    try:
        # Client tam bağlanana kadar kısa bekle
        await asyncio.sleep(5)
        me = await client.get_me()
        await _restore_tasks(client, me.id)
    except Exception:
        pass


# Bu plugin örneğine bağlı USERBOT client'ını YÜK ANINDA yakala (bot değil!).
# (Her hesap için plugin ayrı exec edildiğinden, set_client ile bağlanan
#  doğru userbot client'ı bu noktada get_client() ile alınır.)
try:
    from userbot.events import get_client as _get_bound_client
    _omsg_my_client = _get_bound_client()
except Exception:
    _omsg_my_client = None

try:
    _omsg_loop = getattr(_omsg_my_client, "loop", None) or bot.loop
    _omsg_loop.create_task(_on_start(_omsg_my_client if _omsg_my_client is not None else bot))
except Exception:
    pass


# ==========================================
# CMDHELP AYARLARI
# ==========================================

Help = CmdHelp("otomsg")
Help.add_command("otomsg <mesaj> <dakika>", None, "HIZLI: bulunduğun gruba oto mesaj ekler (komut silinir, onay bota gider)")
Help.add_command("otomsg ekle <chat> <aralık_dk> <tekrar> <mesaj>", None, "Otomatik mesaj görevi ekler")
Help.add_command("otomsgs", None, "Tüm görevlerin durumunu gösterir")
Help.add_command("otomsgl", None, "Görev listesini detaylı gösterir")
Help.add_command("otomsgstop <id>", None, "Görevi geçici durdurur")
Help.add_command("otomsgstart <id>", None, "Durdurulan görevi yeniden başlatır")
Help.add_command("otomsgkopyala <id> <yeni_chat>", None, "Görevin ayarlarını yeni bir chat için kopyalar")
Help.add_command("otomsgdel <id>", None, "Görevi kalıcı olarak siler")
Help.add_command("otomsgstartall", None, "Tüm görevleri tek seferde başlatır")
Help.add_command("otomsgstopall", None, "Tüm görevleri tek seferde durdurur")
Help.add_command("otomsghelp", None, "Detaylı yardım mesajı gösterir")
Help.add_info("Gruplara/kanallara otomatik zamanlanmış mesaj gönderme — Hata yönetimli & çoklu chat!")
Help.add()
