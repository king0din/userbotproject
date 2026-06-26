"""
gruplarınızda toplu veya tekli etiketler atmanızı sağlar.

🔧 Komutlar: .tagstop, .taghelp, .tagadmin, .tagstat, .tag, .tagban, .tagunban, .tagbanlistremove, .tagbanlist
🚨 Tür: #grup_yönetim 


Komular hakında:
.tag  yanıtladığınız mesajı veya girdiğiniz mesajı tüm üyeleri 2.5 saniye aralıklar ile etiketler
örnek:
.tag bir mesajı yanıtlayarak yada yanına örneğin günaydın yazarak atarsanız btün üyeleri bütün üyelere etiket atar.
not:
diyelim teker teker değilde 5'er kişi etiketleyerek tag atmak istiyorsunuz ozaman komutun yanına min 1 max 10 olacak şekilde belirtin.
örnek:
.tag 5 bir mesajı yanıtlayarak yada yanına mesajı yazarak gönderin.
.tag <kişi sayısı>  <mesajınız> - Grup halinde gönder.
.tagadmin bir mesajı yanıtlayarak yada yanına mesajı yazarark - Sadece adminleri etiketler.
örnek:
.tagadmin 5 günaydın sayın grup adminleri. Adminlar 5'er gruplar halinde etiket atar.
.tagstat - etiketleme işlemi yapılırken mevcut işelm durumunu gösterir.
.tagstop - Etiketlemeyi durdurur.
.taghelp - herhangi bir sohbette yazınca komutun yardım mesajını gösterir
.tagban <id/@username> - Kullanıcıyı etiketlemeden engelle
.tagunban <id/@username> - Kullanıcının engelini kaldır
.tagbanlistremove - Tüm engelleri temizle
.tagbanlist - Engellenen kullanıcıları listele
"""

import asyncio
import copy
import re
import os
import json
from telethon.tl.types import (
    ChannelParticipantsAdmins as cp,
    MessageEntityCustomEmoji,
    MessageEntityTextUrl,
    InputMessageEntityMentionName
)
from telethon.tl.functions.users import GetFullUserRequest
from telethon.errors import (
    ChatAdminRequiredError, 
    UserNotParticipantError,
    ChannelPrivateError,
    FloodWaitError
)
from telethon import events
from userbot import CMD_HELP, bot
from userbot.events import register as r
from userbot.cmdhelp import CmdHelp 

# Global değişkenler
tag_active = False
tag_data = {
    "mode": "all",
    "message": "",
    "message_entities": None,
    "group_size": 1,
    "started_by": None,
    "chat_id": None,
    "current_task": None,
    "tagged_count": 0,
    "total_count": 0,
    "skipped_count": 0,
    "is_reply": False
}

# Engelleme sistemi
blocked_users = set()
loaded_user_id = None  # Cache için - gereksiz yüklemeleri önler
BLOCKED_FILE = os.path.join(os.path.dirname(__file__), "tag_blocked.json")


def load_blocked_users():
    """Engellenen kullanıcıları JSON dosyasından yükle"""
    global blocked_users
    try:
        if os.path.exists(BLOCKED_FILE):
            with open(BLOCKED_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    blocked_users = set()
                    for user_id_list in data.values():
                        blocked_users.update(user_id_list)
                elif isinstance(data, list):
                    blocked_users = set(data)
                else:
                    blocked_users = set()
        else:
            blocked_users = set()
    except Exception:
        blocked_users = set()


async def save_blocked_users(client):
    """Engellenen kullanıcıları JSON dosyasına kaydet - her hesap için ayrı"""
    try:
        me = await client.get_me()
        my_id = str(me.id)
        
        data = {}
        if os.path.exists(BLOCKED_FILE):
            try:
                with open(BLOCKED_FILE, 'r') as f:
                    data = json.load(f)
            except:
                data = {}
        
        data[my_id] = list(blocked_users)
        
        with open(BLOCKED_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


async def load_my_blocked_users(client):
    """Sadece kendi hesabımın engellediklerini yükle"""
    global blocked_users, loaded_user_id
    try:
        me = await client.get_me()
        my_id = str(me.id)
        
        if loaded_user_id == my_id:
            return
        
        if os.path.exists(BLOCKED_FILE):
            with open(BLOCKED_FILE, 'r') as f:
                data = json.load(f)
                
                if my_id in data:
                    blocked_users = set(data[my_id])
                else:
                    blocked_users = set()
        else:
            blocked_users = set()
        
        loaded_user_id = my_id
    except Exception:
        blocked_users = set()


def telegram_text_length(text):
    """
    Telegram'ın kullandığı UTF-16 code unit sayısını hesaplar.
    """
    return len(text.encode('utf-16-le')) // 2


def adjust_entities(entities, offset_shift):
    """
    Entity'lerin offset'lerini ayarlar.
    """
    if not entities:
        return None
    
    adjusted = []
    for entity in entities:
        try:
            new_entity = copy.deepcopy(entity)
            new_entity.offset = entity.offset + offset_shift
            adjusted.append(new_entity)
        except Exception:
            continue
    
    return adjusted if adjusted else None


def extract_entities_for_text(full_text, text_start, original_entities):
    """
    Komut mesajındaki entity'leri, mesaj kısmına göre ayarlar.
    """
    if not original_entities:
        return None
    
    adjusted = []
    
    for entity in original_entities:
        if entity.offset >= text_start:
            new_offset = entity.offset - text_start
            try:
                new_entity = copy.deepcopy(entity)
                new_entity.offset = new_offset
                adjusted.append(new_entity)
            except:
                continue
    
    return adjusted if adjusted else None


async def get_input_user(client, user):
    """
    Kullanıcının InputUser nesnesini al.
    InputMessageEntityMentionName için gerekli.
    """
    try:
        input_user = await client.get_input_entity(user.id)
        return input_user
    except Exception:
        return None


async def build_mention_text_and_entities(client, users, start_offset=0):
    """
    Kullanıcılar için mention metni ve entity listesi oluşturur.
    InputMessageEntityMentionName kullanarak GERÇEK mention bildirimi gönderir.
    
    Args:
        client: Telethon client
        users: Kullanıcı listesi
        start_offset: Mention metninin başlayacağı UTF-16 offset
    
    Returns:
        (mention_text, mention_entities, successful_users)
    """
    mention_entities = []
    names = []
    current_offset = start_offset
    successful_users = []
    
    for i, user in enumerate(users):
        name = user.first_name or "Kullanıcı"
        if not name.strip():
            name = "Kullanıcı"
        name = name[:30].replace("[", "(").replace("]", ")")
        
        name_utf16_len = telegram_text_length(name)
        
        # InputUser nesnesini al
        input_user = await get_input_user(client, user)
        
        if input_user:
            # GERÇEK mention - bildirim gönderir!
            mention_entities.append(
                InputMessageEntityMentionName(
                    offset=current_offset,
                    length=name_utf16_len,
                    user_id=input_user
                )
            )
            successful_users.append(user)
        else:
            # Fallback: TextUrl ile mention (bildirim göndermez ama en azından link olur)
            mention_entities.append(
                MessageEntityTextUrl(
                    offset=current_offset,
                    length=name_utf16_len,
                    url=f"tg://user?id={user.id}"
                )
            )
            successful_users.append(user)
        
        names.append(name)
        
        if i < len(users) - 1:
            current_offset += name_utf16_len + 2  # ", " = 2 UTF-16 unit
        else:
            current_offset += name_utf16_len
    
    mention_text = ", ".join(names)
    
    return mention_text, mention_entities, successful_users


def _utf16_slice(text, start_u16, end_u16=None):
    """Metni UTF-16 code-unit sınırlarından dilimler (Telegram offset sistemi)."""
    buf = text.encode('utf-16-le')
    s = start_u16 * 2
    e = None if end_u16 is None else end_u16 * 2
    return buf[s:e].decode('utf-16-le', errors='ignore')


def slice_text_and_entities(full_text, full_entities, start_u16, end_u16=None):
    """
    full_text'in [start_u16, end_u16) UTF-16 penceresini ve o pencereye denk
    gelen entity'leri (offset'leri yeniden tabanlanmis halde) dondurur.
    Metin ve entity'ler AYNI UTF-16 dilimden uretildigi icin offset'ler her
    zaman tutarlidir -> premium (custom) emoji bozulmaz.
    """
    body = _utf16_slice(full_text, start_u16, end_u16)
    body_len = telegram_text_length(body)
    win_end = start_u16 + body_len
    out = []
    for ent in (full_entities or []):
        e_start = ent.offset
        e_end = ent.offset + ent.length
        if e_start >= start_u16 and e_end <= win_end:
            new_ent = copy.deepcopy(ent)
            new_ent.offset = e_start - start_u16
            out.append(new_ent)
    return body, (out or None)


def parse_tag_command(q):
    """
    .tag / .tagadmin argumanlarini UTF-16 guvenli sekilde cozer.

    Donus: (group_size, message_text, message_entities, is_reply)

    - Offset'ler kod-noktasi degil UTF-16 ile hesaplanir.
    - Mesaj govdesi regex grubundan degil, komut sonrasi ham metnin TAMAMINDAN
      (newline'lar dahil) alinir; boylece cok satirli mesajlar kesilmez.
    - message_text ile message_entities her zaman ayni dilimden uretilir,
      dolayisiyla premium emoji offset'i kaymaz.
    """
    full_msg = getattr(q, "raw_text", None)
    if full_msg is None:
        full_msg = q.text or ""
    entities = list(q.entities or [])

    group_size = 1
    message_text = ""
    message_entities = None
    is_reply = False

    # Komut govdesinin basladigi UTF-16 offset'i (".tag " / ".tagadmin " sonrasi)
    if q.pattern_match is not None and q.pattern_match.group(1) is not None:
        body_start = telegram_text_length(full_msg[:q.pattern_match.start(1)])
    else:
        body_start = telegram_text_length(full_msg)

    body_text, body_entities = slice_text_and_entities(full_msg, entities, body_start)
    stripped = body_text.strip()

    if not stripped:
        is_reply = True
    else:
        m_num = re.match(r"(\d+)(\s+)", body_text)
        if m_num and len(body_text) > m_num.end():
            group_size = max(1, min(10, int(m_num.group(1))))
            skip = telegram_text_length(body_text[:m_num.end()])
            message_text, message_entities = slice_text_and_entities(
                full_msg, entities, body_start + skip
            )
        elif stripped.isdigit():
            group_size = max(1, min(10, int(stripped)))
            is_reply = True
        else:
            message_text, message_entities = body_text, body_entities

    return group_size, message_text, message_entities, is_reply


@r(outgoing=True, pattern="^.tag(?: |$)(.*)")
async def tag_all(q):
    """Tüm üyeleri etiketler"""
    global tag_active, tag_data
    
    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return
    
    await load_my_blocked_users(q.client)
    
    if tag_active:
        try:
            await q.edit("❌ **Zaten bir etiketleme işlemi devam ediyor!**\nKapatmak için: `.tagstop`")
        except:
            pass
        return
    
    if q.fwd_from:
        return
    
    group_size, message_text, message_entities, is_reply = parse_tag_command(q)
    
    reply_msg = await q.get_reply_message()
    if reply_msg and (is_reply or not message_text):
        message_text = (getattr(reply_msg, "raw_text", None) or reply_msg.text or "📢")
        message_entities = reply_msg.entities
        is_reply = True
    
    if not message_text:
        message_text = "📢"
    
    chat = await q.get_input_chat()
    
    try:
        pass
    except Exception as e:
        await q.edit(f"❌ **İzin kontrolü hatası:** `{str(e)}`")
        return
    
    try:
        test_participant = await q.client.get_participants(chat, limit=1)
        if not test_participant:
            await q.edit("❌ **Grupta katılımcı bulunamadı!**")
            return
    except ChatAdminRequiredError:
        await q.edit("❌ **Katılımcı listesini almak için admin olmalısınız!**\n\n"
                    "⚠️ *Grup gizli olabilir veya üye listesini görme izniniz yok.*")
        return
    except ChannelPrivateError:
        await q.edit("❌ **Bu gruba erişimim yok!**\n\n"
                    "⚠️ *Grup gizli olabilir veya gruptan çıkarılmış olabilirim.*")
        return
    except UserNotParticipantError:
        await q.edit("❌ **Bu grupta değilim!**\n\n"
                    "⚠️ *Önce gruba katılmalıyım.*")
        return
    except FloodWaitError as e:
        await q.edit(f"⏳ **FloodWait: {e.seconds} saniye bekleyin!**")
        return
    except Exception as e:
        await q.edit(f"❌ **Katılımcı listesi alınamadı:** `{str(e)}`")
        return
    
    tag_data.update({
        "mode": "all",
        "message": message_text,
        "message_entities": message_entities,
        "group_size": group_size,
        "started_by": q.sender_id,
        "chat_id": q.chat_id,
        "tagged_count": 0,
        "skipped_count": 0,
        "total_count": 0,
        "is_reply": is_reply
    })
    
    tag_active = True
    
    group_text = f" (📦 {group_size}'li grup)" if group_size > 1 else ""
    
    try:
        status_msg = await q.edit(f"✅ **Etiketleme başlatıldı!**\n\n"
                                 f"📝 **Mesaj:** `{message_text[:50]}{'...' if len(message_text) > 50 else ''}`\n"
                                 f"👥 **Mod:** Tüm üyeler{group_text}\n"
                                 f"⏱️ **Bekleme:** 2.5s (güvenli)\n\n"
                                 f"Durdurmak için: `.tagstop`")
    except:
        status_msg = q
    
    tag_data["current_task"] = asyncio.create_task(
        tag_process(q, chat, "all", status_msg, group_size)
    )
    
    try:
        await tag_data["current_task"]
    except asyncio.CancelledError:
        try:
            await status_msg.edit(f"⏹️ **Etiketleme durduruldu!**\n\n"
                                 f"✅ Etiketlenen: {tag_data['tagged_count']}\n"
                                 f"❌ Atlanan: {tag_data['skipped_count']}")
        except:
            pass
    except Exception as e:
        try:
            await status_msg.edit(f"❌ **Hata oluştu:** `{str(e)}`")
        except:
            pass


@r(outgoing=True, pattern="^.tagadmin(?: |$)(.*)")
async def tag_admins(q):
    """Sadece adminleri etiketler"""
    global tag_active, tag_data
    
    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return
    
    await load_my_blocked_users(q.client)
    
    if tag_active:
        try:
            await q.edit("❌ **Zaten bir etiketleme işlemi devam ediyor!**\nKapatmak için: `.tagstop`")
        except:
            pass
        return
    
    if q.fwd_from:
        return
    
    group_size, message_text, message_entities, is_reply = parse_tag_command(q)
    
    reply_msg = await q.get_reply_message()
    if reply_msg and (is_reply or not message_text):
        message_text = (getattr(reply_msg, "raw_text", None) or reply_msg.text or "📢 Adminler!")
        message_entities = reply_msg.entities
        is_reply = True
    
    if not message_text:
        message_text = "📢 Adminler!"
    
    chat = await q.get_input_chat()
    
    try:
        test_admin = await q.client.get_participants(chat, filter=cp, limit=1)
    except ChatAdminRequiredError:
        await q.edit("❌ **Admin listesini almak için admin olmalısınız!**\n\n"
                    "⚠️ *Grup gizli olabilir veya admin değilsiniz.*")
        return
    except ChannelPrivateError:
        await q.edit("❌ **Bu gruba erişimim yok!**")
        return
    except FloodWaitError as e:
        await q.edit(f"⏳ **FloodWait: {e.seconds} saniye bekleyin!**")
        return
    except Exception as e:
        await q.edit(f"❌ **Admin kontrolü yapılamadı:** `{str(e)}`")
        return
    
    tag_data.update({
        "mode": "admin",
        "message": message_text,
        "message_entities": message_entities,
        "group_size": group_size,
        "started_by": q.sender_id,
        "chat_id": q.chat_id,
        "tagged_count": 0,
        "skipped_count": 0,
        "total_count": 0,
        "is_reply": is_reply
    })
    
    tag_active = True
    
    group_text = f" (📦 {group_size}'li grup)" if group_size > 1 else ""
    
    try:
        status_msg = await q.edit(f"✅ **Admin Etiketleme Başlatıldı!**\n\n"
                                 f"📝 **Mesaj:** `{message_text[:50]}{'...' if len(message_text) > 50 else ''}`\n"
                                 f"👑 **Mod:** Sadece Adminler{group_text}\n"
                                 f"⏱️ **Bekleme:** 2.5s (güvenli)\n\n"
                                 f"Durdurmak için: `.tagstop`")
    except:
        status_msg = q
    
    tag_data["current_task"] = asyncio.create_task(
        tag_process(q, chat, "admin", status_msg, group_size)
    )
    
    try:
        await tag_data["current_task"]
    except asyncio.CancelledError:
        try:
            await status_msg.edit(f"⏹️ **Etiketleme durduruldu!**\n\n"
                                 f"✅ Etiketlenen: {tag_data['tagged_count']}\n"
                                 f"❌ Atlanan: {tag_data['skipped_count']}")
        except:
            pass
    except Exception as e:
        try:
            await status_msg.edit(f"❌ **Hata oluştu:** `{str(e)}`")
        except:
            pass


async def tag_process(q, chat, mode, status_msg, group_size=1):
    """Etiketleme işlemini gerçekleştir - Gerçek mention bildirimi ile"""
    global tag_active, tag_data
    
    userbot_id = (await q.client.get_me()).id
    
    filter_type = cp if mode == "admin" else None
    
    try:
        participants = []
        
        try:
            async for user in q.client.iter_participants(chat, filter=filter_type):
                if not tag_active:
                    break
                
                if user.bot or user.deleted:
                    tag_data["skipped_count"] += 1
                    continue
                
                if user.id == userbot_id:
                    tag_data["skipped_count"] += 1
                    continue
                
                if user.id in blocked_users:
                    tag_data["skipped_count"] += 1
                    continue
                
                participants.append(user)
                
                if len(participants) >= 5000:
                    break
        
        except ChatAdminRequiredError:
            try:
                await status_msg.edit("❌ **Katılımcı listesini almak için admin olmalısınız!**\n\n"
                                    "⚠️ *Grup gizli olabilir veya üye listesini görme izniniz yok.*")
            except:
                pass
            tag_active = False
            return
        except ChannelPrivateError:
            try:
                await status_msg.edit("❌ **Bu gruba erişimim yok!**")
            except:
                pass
            tag_active = False
            return
        except FloodWaitError as e:
            try:
                await status_msg.edit(f"⏳ **FloodWait: {e.seconds} saniye bekleyin!**\n"
                                    "İşlem durduruldu.")
            except:
                pass
            tag_active = False
            return
        except Exception as e:
            try:
                await status_msg.edit(f"❌ **Katılımcı alınamadı:** `{str(e)}`")
            except:
                pass
            tag_active = False
            return
        
        tag_data["total_count"] = len(participants)
        
        if not participants:
            try:
                await status_msg.edit("❌ **Etiketlenecek kimse bulunamadı!**")
            except:
                pass
            tag_active = False
            return
        
        if len(participants) > 1000:
            try:
                await status_msg.edit(f"⚠️ **Çok fazla katılımcı:** {len(participants)}\n"
                                    "İşlem uzun sürebilir.")
                await asyncio.sleep(2)
            except:
                pass
        
        try:
            await status_msg.edit(f"⏳ **Etiketleme başlıyor...**\n"
                                 f"👥 Toplam: {len(participants)} kişi\n"
                                 f"📦 **Grup Boyutu:** {group_size}\n"
                                 f"⏱️ **Bekleme:** 2.5s")
        except:
            pass
        
        for i in range(0, len(participants), group_size):
            if not tag_active:
                break
            
            group = participants[i:i + group_size]
            if not group:
                continue
            
            try:
                original_message = tag_data['message']
                original_entities = tag_data.get("message_entities")
                
                message_utf16_len = telegram_text_length(original_message)
                separator = "\n\n"
                separator_len = 2
                
                mention_start_offset = message_utf16_len + separator_len
                
                # DÜZELTME: async fonksiyon - InputMessageEntityMentionName kullanır
                mention_text, mention_entities, successful_users = await build_mention_text_and_entities(
                    q.client, group, mention_start_offset
                )
                
                full_message = f"{original_message}{separator}{mention_text}"
                
                all_entities = []
                
                if original_entities:
                    all_entities.extend(copy.deepcopy(original_entities))
                
                all_entities.extend(mention_entities)
                
                if len(full_message) <= 4096:
                    await q.client.send_message(
                        q.chat_id,
                        full_message,
                        formatting_entities=all_entities if all_entities else None,
                        silent=True
                    )
                    tag_data["tagged_count"] += len(successful_users)
                else:
                    max_tags_per_msg = 3 if group_size > 3 else group_size
                    for j in range(0, len(group), max_tags_per_msg):
                        sub_group = group[j:j + max_tags_per_msg]
                        
                        sub_mention_text, sub_mention_entities, sub_successful = await build_mention_text_and_entities(
                            q.client, sub_group, mention_start_offset
                        )
                        sub_message = f"{original_message}{separator}{sub_mention_text}"
                        
                        sub_all_entities = []
                        if original_entities:
                            sub_all_entities.extend(copy.deepcopy(original_entities))
                        sub_all_entities.extend(sub_mention_entities)
                        
                        await q.client.send_message(
                            q.chat_id,
                            sub_message,
                            formatting_entities=sub_all_entities if sub_all_entities else None,
                            silent=True
                        )
                        tag_data["tagged_count"] += len(sub_successful)
                
                if i % max(1, len(participants) // 10) == 0 or i + group_size >= len(participants):
                    percentage = min(100, (i + group_size) * 100 // len(participants))
                    
                    try:
                        await status_msg.edit(f"⏳ **Etiketleniyor...**\n\n"
                                             f"📊 %{percentage} tamamlandı\n"
                                             f"✅ **Etiketlenen:** {tag_data['tagged_count']}/{len(participants)}\n"
                                             f"📦 **Grup:** {group_size} kişi\n"
                                             f"⏱️ **Bekleme:** 2.5s")
                    except:
                        pass
                
                await asyncio.sleep(2.5)
                
            except FloodWaitError as e:
                try:
                    await status_msg.edit(f"⏳ **FloodWait: {e.seconds} saniye bekleniyor...**\n"
                                         "İşlem duraklatıldı.")
                except:
                    pass
                await asyncio.sleep(e.seconds)
                continue
            except Exception as e:
                tag_data["skipped_count"] += len(group)
                continue
        
        if tag_active:
            try:
                await status_msg.edit(f"✅ **Etiketleme Tamamlandı!**\n\n"
                                     f"📊 **Sonuçlar:**\n"
                                     f"✅ Etiketlenen: {tag_data['tagged_count']}\n"
                                     f"❌ Atlanan: {tag_data['skipped_count']}\n"
                                     f"👥 Toplam: {len(participants)}\n"
                                     f"📦 Grup Boyutu: {group_size}\n"
                                     f"⏱️ Bekleme: 2.5s")
            except:
                pass
    
    except Exception as e:
        try:
            await status_msg.edit(f"❌ **Hata oluştu:** `{str(e)}`")
        except:
            pass
    
    finally:
        tag_active = False
        tag_data["current_task"] = None


@r(outgoing=True, pattern="^.tagstop$")
async def tag_stop(q):
    """Etiketlemeyi durdurur"""
    global tag_active, tag_data
    
    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return
    
    if not tag_active:
        try:
            await q.edit("❌ **Şu anda aktif bir etiketleme yok!**")
        except:
            pass
        return
    
    if q.sender_id != tag_data["started_by"]:
        try:
            await q.edit("❌ **Bu etiketlemeyi sadece başlatan kişi durdurabilir!**")
        except:
            pass
        return
    
    tag_active = False
    
    if tag_data["current_task"]:
        tag_data["current_task"].cancel()
    
    try:
        await q.edit(f"⏹️ **Etiketleme durduruldu!**\n\n"
                    f"✅ Etiketlenen: {tag_data['tagged_count']}\n"
                    f"❌ Atlanan: {tag_data['skipped_count']}\n"
                    f"👥 Toplam Katılımcı: {tag_data['total_count']}")
    except:
        pass


@r(outgoing=True, pattern="^.tagstat$")
async def tag_status(q):
    """Etiketleme durumunu gösterir"""
    global tag_active, tag_data
    
    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return
    
    if tag_active:
        mode_text = "👥 Tüm Üyeler" if tag_data["mode"] == "all" else "👑 Sadece Adminler"
        group_text = f" (📦 {tag_data['group_size']}'li grup)" if tag_data["group_size"] > 1 else ""
        
        has_premium_emoji = False
        if tag_data.get("message_entities"):
            for entity in tag_data["message_entities"]:
                if isinstance(entity, MessageEntityCustomEmoji):
                    has_premium_emoji = True
                    break
        
        status_text = f"🟢 **ETİKETLEME AKTİF**\n\n"
        status_text += f"📝 **Mesaj:** `{tag_data['message'][:50]}{'...' if len(tag_data['message']) > 50 else ''}`\n"
        status_text += f"👤 **Mod:** {mode_text}{group_text}\n"
        status_text += f"✅ **Etiketlenen:** {tag_data['tagged_count']}\n"
        status_text += f"❌ **Atlanan:** {tag_data['skipped_count']}\n"
        status_text += f"👥 **Toplam:** {tag_data['total_count']}\n"
        status_text += f"⏱️ **Bekleme:** 2.5s (güvenli)\n"
        
        if blocked_users:
            status_text += f"🚫 **Engelli:** {len(blocked_users)} kişi\n"
        
        if has_premium_emoji:
            status_text += f"✨ **Premium Emoji:** Destekleniyor\n"
        
        if tag_data["is_reply"]:
            status_text += f"📎 **Kaynak:** Yanıtlanan mesaj\n"
        
        status_text += f"\nDurdurmak için: `.tagstop`"
    else:
        await load_my_blocked_users(q.client)
        
        status_text = "🔴 **ETİKETLEME PASİF**\n\n"
        status_text += "**Kullanım:**\n"
        status_text += "• `.tag <mesaj>` - Tüm üyeleri etiketler\n"
        status_text += "• `.tag <numara> <mesaj>` - Grup halinde etiketler\n"
        status_text += "• `.tagadmin <mesaj>` - Sadece adminleri etiketler\n"
        status_text += "• `.tagadmin <numara> <mesaj>` - Adminleri grup halinde etiketler\n"
        status_text += "• `.tagstop` - Aktif etiketlemeyi durdurur\n\n"
        
        if blocked_users:
            status_text += f"🚫 **Engelli Kullanıcılar:** {len(blocked_users)} kişi\n\n"
        
        status_text += "**Varsayılan:** 1 kişi teker teker etiketlenir\n"
    
    try:
        await q.edit(status_text)
    except:
        pass


@r(outgoing=True, pattern="^.tagban(?: |$)(.*)")
async def block_user(q):
    """Kullanıcıyı etiketlemeden engelle"""
    global blocked_users
    
    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return
    
    await load_my_blocked_users(q.client)
    
    args = q.pattern_match.group(1).strip()
    
    user_id = None
    user_name = None
    
    reply_msg = await q.get_reply_message()
    if reply_msg:
        user_id = reply_msg.sender_id
        try:
            user_entity = await q.client.get_entity(user_id)
            user_name = user_entity.first_name or "Kullanıcı"
        except:
            user_name = "Kullanıcı"
    
    elif args:
        if args.startswith("@"):
            try:
                user_entity = await q.client.get_entity(args)
                user_id = user_entity.id
                user_name = user_entity.first_name or args
            except Exception as e:
                await q.edit(f"❌ **Kullanıcı bulunamadı:** `{args}`\n\n`{str(e)}`")
                return
        elif args.isdigit():
            user_id = int(args)
            try:
                user_entity = await q.client.get_entity(user_id)
                user_name = user_entity.first_name or "Kullanıcı"
            except:
                user_name = f"ID: {user_id}"
        else:
            await q.edit("❌ **Geçersiz format!**\n\n"
                        "**Kullanım:**\n"
                        "• `.tagban <id>` - ID ile engelle\n"
                        "• `.tagban @username` - Username ile engelle\n"
                        "• `[mesajı yanıtla] .tagban` - Reply ile engelle")
            return
    else:
        await q.edit("❌ **Kullanıcı belirtmelisiniz!**\n\n"
                    "**Kullanım:**\n"
                    "• `.tagban <id>` - ID ile engelle\n"
                    "• `.tagban @username` - Username ile engelle\n"
                    "• `[mesajı yanıtla] .tagban` - Reply ile engelle")
        return
    
    if user_id == userbot_id:
        await q.edit("❌ **Kendinizi engelleyemezsiniz!**")
        return
    
    if user_id in blocked_users:
        await q.edit(f"⚠️ **Bu kullanıcı zaten engelli!**\n\n"
                    f"👤 **İsim:** {user_name}\n"
                    f"🆔 **ID:** `{user_id}`")
        return
    
    blocked_users.add(user_id)
    await save_blocked_users(q.client)
    
    await q.edit(f"✅ **Kullanıcı engellendi!**\n\n"
                f"👤 **İsim:** {user_name}\n"
                f"🆔 **ID:** `{user_id}`\n\n"
                f"Bu kullanıcı artık etiketlenmeyecek.\n"
                f"Engeli kaldırmak için: `.tagunban {user_id}`")


@r(outgoing=True, pattern="^.tagunban(?: |$)(.*)")
async def unblock_user(q):
    """Kullanıcının engelini kaldır"""
    global blocked_users
    
    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return
    
    await load_my_blocked_users(q.client)
    
    args = q.pattern_match.group(1).strip()
    
    user_id = None
    user_name = None
    
    reply_msg = await q.get_reply_message()
    if reply_msg:
        user_id = reply_msg.sender_id
        try:
            user_entity = await q.client.get_entity(user_id)
            user_name = user_entity.first_name or "Kullanıcı"
        except:
            user_name = "Kullanıcı"
    
    elif args:
        if args.startswith("@"):
            try:
                user_entity = await q.client.get_entity(args)
                user_id = user_entity.id
                user_name = user_entity.first_name or args
            except Exception as e:
                await q.edit(f"❌ **Kullanıcı bulunamadı:** `{args}`\n\n`{str(e)}`")
                return
        elif args.isdigit():
            user_id = int(args)
            try:
                user_entity = await q.client.get_entity(user_id)
                user_name = user_entity.first_name or "Kullanıcı"
            except:
                user_name = f"ID: {user_id}"
        else:
            await q.edit("❌ **Geçersiz format!**\n\n"
                        "**Kullanım:**\n"
                        "• `.tagunban <id>` - ID ile engel kaldır\n"
                        "• `.tagunban @username` - Username ile engel kaldır\n"
                        "• `[mesajı yanıtla] .tagunban` - Reply ile engel kaldır")
            return
    else:
        await q.edit("❌ **Kullanıcı belirtmelisiniz!**\n\n"
                    "**Kullanım:**\n"
                    "• `.tagunban <id>` - ID ile engel kaldır\n"
                    "• `.tagunban @username` - Username ile engel kaldır\n"
                    "• `[mesajı yanıtla] .tagunban` - Reply ile engel kaldır")
        return
    
    if user_id not in blocked_users:
        await q.edit(f"⚠️ **Bu kullanıcı zaten engelli değil!**\n\n"
                    f"👤 **İsim:** {user_name}\n"
                    f"🆔 **ID:** `{user_id}`")
        return
    
    blocked_users.discard(user_id)
    await save_blocked_users(q.client)
    
    await q.edit(f"✅ **Engel kaldırıldı!**\n\n"
                f"👤 **İsim:** {user_name}\n"
                f"🆔 **ID:** `{user_id}`\n\n"
                f"Bu kullanıcı artık etiketlenebilir.")


@r(outgoing=True, pattern="^.tagbanlistremove$")
async def clear_blocks(q):
    """Tüm engelleri temizle"""
    global blocked_users
    
    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return
    
    await load_my_blocked_users(q.client)
    
    if not blocked_users:
        await q.edit("⚠️ **Engelli kullanıcı yok!**")
        return
    
    count = len(blocked_users)
    blocked_users.clear()
    await save_blocked_users(q.client)
    
    await q.edit(f"✅ **Tüm engeller temizlendi!**\n\n"
                f"🗑️ **Temizlenen:** {count} kullanıcı")


@r(outgoing=True, pattern="^.tagbanlist$")
async def list_blocks(q):
    """Engellenen kullanıcıları listele"""
    global blocked_users
    
    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return
    
    await load_my_blocked_users(q.client)
    
    if not blocked_users:
        await q.edit("✅ **Engelli kullanıcı yok!**")
        return
    
    msg = f"🚫 **ENGELLİ KULLANICILAR** ({len(blocked_users)})\n\n"
    
    for i, user_id in enumerate(sorted(blocked_users), 1):
        try:
            user_entity = await q.client.get_entity(user_id)
            user_name = user_entity.first_name or "Kullanıcı"
        except:
            user_name = "Bilinmeyen"
        
        msg += f"{i}. **{user_name}** - `{user_id}`\n"
        
        if len(msg) > 3500:
            msg += f"\n... ve {len(blocked_users) - i} kişi daha"
            break
    
    msg += f"\n💡 Engeli kaldırmak için: `.tagunban <id>`"
    
    await q.edit(msg)


@r(outgoing=True, pattern="^.taghelp$")
async def tag_help(q):
    """Yardım mesajı gösterir"""
    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return
    
    help_text = """
**📢 TAG PLUGİN - YARDIM**

**📌 TEMEL KOMUTLAR:**
• `.tag <mesaj>` - Tüm üyeleri etiketler (teker teker)
• `.tagadmin <mesaj>` - Sadece adminleri etiketler (teker teker)

**🎯 GRUP ETİKETLEME:**
• `.tag <numara> <mesaj>` - Grup halinde etiketler
• `.tagadmin <numara> <mesaj>` - Adminleri grup halinde etiketler
• **Sayı aralığı:** 1-10

**📎 YANITLI KULLANIM:**
Bir mesajı yanıtlayıp:
• `.tag` - Yanıtlanan mesajı tüm üyelere gönderir
• `.tag <numara>` - Yanıtlanan mesajı grup halinde gönderir
• `.tagadmin` - Yanıtlanan mesajı adminlere gönderir
• `.tagadmin <numara>` - Yanıtlanan mesajı adminlere grup halinde gönderir

**✨ PREMİUM EMOJİ DESTEĞİ:**
Hem komutla yazılan hem de yanıtlanan mesajdaki premium emojiler korunur!

**🚫 ENGELLEME SİSTEMİ:**
• `.tagban <id>` - ID ile engelle
• `.tagban @username` - Username ile engelle
• `[mesajı yanıtla] .tagban` - Reply ile engelle
• `.tagunban <id/@username>` - Engeli kaldır
• `.tagbanlistremove` - Tüm engelleri temizle
• `.tagbanlist` - Engellileri listele

**🛑 KONTROL:**
• `.tagstop` - Aktif etiketlemeyi durdurur
• `.tagstat` - Etiketleme durumunu gösterir

**💡 ÖRNEKLER:**
1) Teker teker etiketleme:
   `.tag Merhaba arkadaşlar!`
   `.tagadmin Toplantı zamanı!`

2) Grup etiketleme:
   `.tag 5 Merhaba herkese!` (5'li gruplar)
   `.tagadmin 3 Toplantı var!` (3'lü gruplar)

3) Yanıtlı kullanım:
   [Bir mesajı yanıtla] `.tag`
   [Bir mesajı yanıtla] `.tag 4`
   [Bir mesajı yanıtla] `.tagadmin 2`

4) Engelleme:
   `.tagban 123456789`
   `.tagban @kullaniciadi`
   [Mesajı yanıtla] `.tagban`

**⚙️ TEKNİK:**
• **Varsayılan grup boyutu:** 1 (teker teker)
• **Bekleme süresi:** 2.5s (güvenli)
• **Max grup boyutu:** 10
• Botlar otomatik atlanır
• Bot sahibi etiketlenmez
• Engellenenler etiketlenmez
• Sadece başlatan durdurabilir
• Flood korumalı
"""
    
    try:
        await q.edit(help_text)
    except:
        pass


# ==========================================
# CMDHELP AYARLARI
# ==========================================

Help = CmdHelp('tag')
Help.add_command('tag <mesaj>', None, 'Üyeleri teker teker etiketler (premium emoji destekli)')
Help.add_command('tag <numara> <mesaj>', None, 'Üyeleri grup halinde etiketler (örn: .tag 5 Merhaba)')
Help.add_command('tagadmin <mesaj>', None, 'Adminleri teker teker etiketler')
Help.add_command('tagadmin <numara> <mesaj>', None, 'Adminleri grup halinde etiketler')
Help.add_command('tagban <id/@username>', None, 'Kullanıcıyı etiketlemeden engelle (reply destekli)')
Help.add_command('tagunban <id/@username>', None, 'Kullanıcının engelini kaldır (reply destekli)')
Help.add_command('tagbanlistremove', None, 'Tüm engelleri temizle')
Help.add_command('tagbanlist', None, 'Engellenen kullanıcıları listele')
Help.add_command('tagstop', None, 'Aktif etiketlemeyi durdurur')
Help.add_command('tagstat', None, 'Etiketleme durumunu gösterir')
Help.add_command('taghelp', None, 'Detaylı yardım mesajı gösterir')
Help.add_info('Gruplarda toplu etiketleme - Premium emoji & Engelleme sistemi!')
Help.add()