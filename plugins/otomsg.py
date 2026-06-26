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
    MsgIdInvalidError,
    RPCError,
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
            chat_id = entity.id
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

async def _task_loop(client, task_id: str, notify_chat_id: int):
    """
    Belirtilen görevi çalıştıran ana döngü.
    notify_chat_id: Sorun olursa hata bildirimi gönderilecek chat (komutu yazan chat).
    """
    task = tasks_data.get(task_id)
    if not task:
        return

    chat_id   = task["chat_id"]
    interval  = task.get("interval_seconds") or task.get("interval_minutes", 1) * 60
    max_count = task["repeat_count"]           # 0 = sınırsız
    message   = task["message"]
    sent      = task.get("sent_count", 0)
    consecutive_errors = 0
    MAX_CONSECUTIVE = 5  # üst üste bu kadar hata olursa görevi oto-durdur

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
            await client.send_message(chat_id, message)
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
                await client.send_message(chat_id, message)
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


async def _start_task(client, task_id: str, notify_chat_id: int):
    """Görev döngüsünü başlat ve running_tasks'a ekle."""
    if task_id in running_tasks:
        return
    task_obj = asyncio.create_task(
        _task_loop(client, task_id, notify_chat_id)
    )
    running_tasks[task_id] = task_obj


async def _restore_tasks(client, me_id: int):
    """Bot yeniden başlayınca 'running' durumdaki görevleri yeniden başlat."""
    await load_my_tasks(client)
    for task_id, task in tasks_data.items():
        if task.get("status") == "running":
            await _start_task(client, task_id, me_id)


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
    """Görev listesini detaylı göster."""
    me = await q.client.get_me()
    if q.sender_id != me.id:
        return

    await load_my_tasks(q.client)

    if not tasks_data:
        await q.edit("📭 **Görev yok.**")
        return

    lines = ["**📋 OtoMsg Görev Listesi**\n"]
    for task_id, t in tasks_data.items():
        repeat_text = "sınırsız" if t["repeat_count"] == 0 else f"{t['repeat_count']} kere"
        created = time.strftime("%d.%m.%Y %H:%M", time.localtime(t["created_at"])) if t.get("created_at") else "?"
        last_sent = time.strftime("%d.%m.%Y %H:%M", time.localtime(t["last_sent"])) if t.get("last_sent") else "Henüz gönderilmedi"
        lines.append(
            f"━━━━━━━━━━━━━━━\n"
            f"🆔 **ID:** `{task_id}`\n"
            f"💬 **Chat:** {t['chat_title']} (`{t['chat_id']}`)\n"
            f"⏱️ **Aralık:** {t.get('interval_label', str(t.get('interval_seconds', t.get('interval_minutes',0)*60))+'s')}\n"
            f"🔁 **Tekrar:** {repeat_text}\n"
            f"📨 **Gönderilen:** {t.get('sent_count', 0)}\n"
            f"📅 **Oluşturuldu:** {created}\n"
            f"📬 **Son gönderim:** {last_sent}\n"
            f"📊 **Durum:** {t.get('status', '?')}\n"
            f"📝 **Mesaj:** `{t['message'][:80]}{'...' if len(t['message']) > 80 else ''}`"
        )

    await q.edit("\n".join(lines))


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


@r(outgoing=True, pattern=r"^\.otomsghelp$")
async def otomsg_help(q):
    """Detaylı yardım mesajı."""
    me = await q.client.get_me()
    if q.sender_id != me.id:
        return

    help_text = """**⚙️ OtoMsg PLUGİN — YARDIM**

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
`.otomsgl` → Tüm görevlerin detaylı listesi

**🎮 KONTROL:**
`.otomsgstop <id>` → Görevi geçici durdur
`.otomsgstart <id>` → Durdurulan görevi başlat
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
    """Bot başlayınca çalışan görevleri yeniden yükle."""
    try:
        me = await client.get_me()
        await _restore_tasks(client, me.id)
    except Exception:
        pass


# Userbot'un start hook'una bağla (varsa)
try:
    bot.loop.create_task(_on_start(bot))
except Exception:
    pass


# ==========================================
# CMDHELP AYARLARI
# ==========================================

Help = CmdHelp("otomsg")
Help.add_command("otomsg ekle <chat> <aralık_dk> <tekrar> <mesaj>", None, "Otomatik mesaj görevi ekler")
Help.add_command("otomsgs", None, "Tüm görevlerin durumunu gösterir")
Help.add_command("otomsgl", None, "Görev listesini detaylı gösterir")
Help.add_command("otomsgstop <id>", None, "Görevi geçici durdurur")
Help.add_command("otomsgstart <id>", None, "Durdurulan görevi yeniden başlatır")
Help.add_command("otomsgkopyala <id> <yeni_chat>", None, "Görevin ayarlarını yeni bir chat için kopyalar")
Help.add_command("otomsgdel <id>", None, "Görevi kalıcı olarak siler")
Help.add_command("otomsghelp", None, "Detaylı yardım mesajı gösterir")
Help.add_info("Gruplara/kanallara otomatik zamanlanmış mesaj gönderme — Hata yönetimli & çoklu chat!")
Help.add()
