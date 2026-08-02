# ============================================
# Örnek Plugin - KingTG UserBot Service
# ============================================
# description: Temel komutları içeren örnek plugin
# author: @KingOdi
# version: 1.0.0
# ============================================

import os
import time as _time
from userbot.events import register

# Plugin yüklendiği an → userbot oturum süresi (uptime) için referans
_LOAD_TIME = _time.time()


def _brand_username():
    """Botun @kullanıcı adını al (varsa) — tanıtım için."""
    try:
        import config as _c
        u = getattr(_c, "BOT_USERNAME", "") or ""
        if u:
            return u
    except Exception:
        pass
    try:
        with open(os.path.join(os.getcwd(), ".bot_username"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _readable(secs):
    secs = int(secs)
    d, secs = divmod(secs, 86400)
    h, secs = divmod(secs, 3600)
    m, s = divmod(secs, 60)
    parts = []
    if d: parts.append(f"{d}g")
    if h: parts.append(f"{h}s")
    if m: parts.append(f"{m}dk")
    parts.append(f"{s}sn")
    return " ".join(parts)


@register(outgoing=True, pattern=r'^\.(?:alive|durum)$')
async def alive_handler(event):
    """Şık durum paneli: aktiflik + gecikme + uptime + hesap."""
    start = _time.time()
    msg = await event.edit("⏳ **Durum ölçülüyor...**")
    latency = (_time.time() - start) * 1000
    try:
        me = await event.client.get_me()
        who = f"@{me.username}" if me.username else (me.first_name or "?")
    except Exception:
        who = "?"
    uptime = _readable(_time.time() - _LOAD_TIME)
    brand = _brand_username()

    text = "✅ **Userbot Aktif!**\n\n"
    text += f"👤 Hesap: `{who}`\n"
    text += f"⚡ Gecikme: `{latency:.0f} ms`\n"
    text += f"⏱️ Oturum süresi: `{uptime}`\n"
    text += "🤖 KingTG UserBot Service"
    if brand:
        text += f"\n\n💡 Kurulum: @{brand}"
    await msg.edit(text)

@register(outgoing=True, pattern=r'^\.id$')
async def id_handler(event):
    """ID bilgisi göster"""
    chat = await event.get_chat()
    sender = await event.get_sender()

    text = f"**🆔 ID Bilgileri**\n\n"
    text += f"👤 Sizin ID: `{sender.id}`\n"
    text += f"💬 Sohbet ID: `{chat.id}`"

    if event.reply_to_msg_id:
        reply = await event.get_reply_message()
        if reply.sender:
            text += f"\n↩️ Yanıtlanan: `{reply.sender_id}`"

    await event.edit(text)

@register(outgoing=True, pattern=r'^\.ping$')
async def ping_handler(event):
    """Ping kontrolü + oturum süresi"""
    start = _time.time()
    msg = await event.edit("🏓 Pong!")
    latency = (_time.time() - start) * 1000
    uptime = _readable(_time.time() - _LOAD_TIME)
    await msg.edit(f"🏓 **Pong!**\n\n⚡ Gecikme: `{latency:.0f} ms`\n⏱️ Uptime: `{uptime}`")

def unregister():
    """Plugin kaldırılırken çağrılır"""
    pass
