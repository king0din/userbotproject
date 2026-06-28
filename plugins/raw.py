# KingTG UserBot - Raw Data Plugin
# Mesajın ham verisini gösterir
# Kullanım: .raw (mesajı yanıtla)

import os
import tempfile
from userbot.events import register
from userbot import CMD_HELP


@register(outgoing=True, pattern=r"^\.raw$")
async def raw_data(event):
    if event.fwd_from:
        return
    
    reply = await event.get_reply_message()
    if not reply:
        await event.edit("`❌ Bir mesajı yanıtla!`")
        return
    
    await event.edit("`🔍 Raw data alınıyor...`")
    
    try:
        raw = reply.stringify()
        
        # Çok uzunsa dosya olarak gönder
        if len(raw) > 4000:
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
                    f.write(raw)
                    tmp_path = f.name
                await event.client.send_file(
                    event.chat_id,
                    tmp_path,
                    caption="`📄 Raw data (dosya olarak)`",
                    reply_to=reply.id
                )
                await event.delete()
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
        else:
            await event.edit(f"```\n{raw}\n```")
    
    except Exception as e:
        await event.edit(f"`❌ Hata: {e}`")


@register(outgoing=True, pattern=r"^\.emojiid$")
async def emoji_id(event):
    """Mesajdaki custom emoji ID'lerini gösterir"""
    if event.fwd_from:
        return
    
    reply = await event.get_reply_message()
    if not reply:
        await event.edit("`❌ Custom emoji içeren bir mesajı yanıtla!`")
        return
    
    if not reply.entities:
        await event.edit("`❌ Bu mesajda entity yok!`")
        return
    
    emoji_ids = []
    for i, entity in enumerate(reply.entities):
        entity_type = type(entity).__name__
        
        if entity_type == "MessageEntityCustomEmoji":
            doc_id = entity.document_id
            offset = entity.offset
            length = entity.length
            emoji_char = reply.text[offset:offset+length] if reply.text else "?"
            emoji_ids.append(f"`{i+1}.` {emoji_char} → `{doc_id}`")
    
    if emoji_ids:
        result = "**🎨 Custom Emoji ID'leri:**\n\n" + "\n".join(emoji_ids)
        await event.edit(result)
    else:
        await event.edit("`❌ Bu mesajda custom emoji yok!`")


@register(outgoing=True, pattern=r"^\.userid$")
async def user_id_cmd(event):
    """Kullanıcı ID'sini gösterir"""
    if event.fwd_from:
        return
    
    reply = await event.get_reply_message()
    if reply:
        user = await event.client.get_entity(reply.sender_id)
        emoji_info = ""
        
        if hasattr(user, 'emoji_status') and user.emoji_status:
            if hasattr(user.emoji_status, 'document_id'):
                emoji_info = f"\n`😀 Emoji Status:` `{user.emoji_status.document_id}`"
        
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        username = f"@{user.username}" if user.username else "yok"
        premium = "✅" if getattr(user, 'premium', False) else "❌"
        
        await event.edit(
            f"**👤 Kullanıcı Bilgisi:**\n\n"
            f"`🆔 ID:` `{user.id}`\n"
            f"`📛 İsim:` {name}\n"
            f"`📧 Username:` {username}\n"
            f"`⭐ Premium:` {premium}"
            f"{emoji_info}"
        )
    else:
        me = await event.client.get_me()
        emoji_info = ""
        
        if hasattr(me, 'emoji_status') and me.emoji_status:
            if hasattr(me.emoji_status, 'document_id'):
                emoji_info = f"\n`😀 Emoji Status:` `{me.emoji_status.document_id}`"
        
        await event.edit(
            f"**👤 Sen:**\n\n"
            f"`🆔 ID:` `{me.id}`\n"
            f"`📛 İsim:` {me.first_name or ''} {me.last_name or ''}\n"
            f"`📧 Username:` @{me.username if me.username else 'yok'}\n"
            f"`⭐ Premium:` {'✅' if getattr(me, 'premium', False) else '❌'}"
            f"{emoji_info}"
        )


CMD_HELP.update({
    "raw":
    "`.raw` - Yanıtlanan mesajın raw datasını gösterir\n"
    "`.emojiid` - Mesajdaki custom emoji ID'lerini gösterir\n"
    "`.userid` - Kullanıcı ID ve emoji status bilgisi"
})