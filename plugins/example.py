# ============================================
# Örnek Plugin - KingTG UserBot Service
# ============================================
# description: Temel komutları içeren örnek plugin
# author: @KingOdi
# version: 1.0.0
# ============================================

from telethon import events
from userbot.events import register

"""Plugin'i client'a kaydet"""

@register(outgoing=True, pattern=r'^\.alive$')
async def alive_handler(event):
    """Bot çalışıyor mu kontrol et"""
    await event.edit("✅ **Userbot Aktif!**\n\n🤖 KingTG UserBot Service")

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
    """Ping kontrolü"""
    import time
    start = time.time()
    msg = await event.edit("🏓 Pong!")
    end = time.time()

    await msg.edit(f"🏓 **Pong!**\n\n⚡ Gecikme: `{(end-start)*1000:.2f}ms`")

def unregister():
    """Plugin kaldırılırken çağrılır"""
    pass
