"""
AFK moduna geçmenizi ve geri dönmenizi sağlar.

🔧 Komutlar: .afk, .unafk
🚨 Tür: #eğlence


Komutlar hakkında:
.afk:
Bu komutu kullandığınızda profiliniz AFK moduna geçer:
- Mevcut profiliniz otomatik kaydedilir
- İsminiz "AFK" olarak değişir
- Profil fotoğrafınız kaldırılır
- Hakkında kısmı temizlenir
- Premium kullanıcıysanız AFK ifadesi eklenir

.unafk:
Bu komutu kullandığınızda orijinal profilinize geri dönersiniz.
"""

import os
from telethon.tl.functions.photos import GetUserPhotosRequest, DeletePhotosRequest, UploadProfilePhotoRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.account import UpdateEmojiStatusRequest
from telethon import events
from telethon.tl.types import InputPhoto, EmojiStatus, EmojiStatusEmpty
from telethon.tl import functions
from userbot.events import register
from userbot import CMD_HELP

try:
    from userbot import TEMP_DOWNLOAD_DIRECTORY
except ImportError:
    TEMP_DOWNLOAD_DIRECTORY = "./downloads/"
    if not os.path.exists(TEMP_DOWNLOAD_DIRECTORY):
        os.makedirs(TEMP_DOWNLOAD_DIRECTORY)

# Orijinal profil kayıt dizini
AFK_PROFILE_DIR = os.path.join(TEMP_DOWNLOAD_DIRECTORY, "afk_profile")
if not os.path.exists(AFK_PROFILE_DIR):
    os.makedirs(AFK_PROFILE_DIR)

# AFK emoji ID
AFK_EMOJI_ID = 5431438062250892883

# Orijinal profil bilgileri
ORIGINAL_PROFILE = {
    "first_name": None,
    "last_name": None,
    "about": None,
    "photos": [],
    "photo_count": 0,
    "emoji_status": None,
    "is_afk": False
}


async def download_all_profile_photos(client, user_id, save_dir, prefix="photo"):
    """Tüm profil fotoğraflarını indir"""
    photos_info = []
    try:
        result = await client(GetUserPhotosRequest(user_id=user_id, offset=0, max_id=0, limit=100))
        if not result.photos:
            return photos_info
        
        for idx, photo in enumerate(result.photos):
            try:
                is_video = hasattr(photo, 'video_sizes') and photo.video_sizes
                if is_video:
                    file_path = os.path.join(save_dir, f"{prefix}_{idx}.mp4")
                    for video_size in photo.video_sizes:
                        if hasattr(video_size, 'type'):
                            try:
                                downloaded = await client.download_media(photo, file=file_path, thumb=-1)
                                if downloaded:
                                    photos_info.append((downloaded, True))
                                    break
                            except:
                                file_path = os.path.join(save_dir, f"{prefix}_{idx}.jpg")
                                downloaded = await client.download_media(photo, file=file_path)
                                if downloaded:
                                    photos_info.append((downloaded, False))
                                break
                else:
                    file_path = os.path.join(save_dir, f"{prefix}_{idx}.jpg")
                    downloaded = await client.download_media(photo, file=file_path)
                    if downloaded:
                        photos_info.append((downloaded, False))
            except:
                continue
    except:
        pass
    return photos_info


async def delete_all_my_photos(client):
    """Tüm profil fotoğraflarını sil"""
    try:
        while True:
            photos = await client(GetUserPhotosRequest(user_id="me", offset=0, max_id=0, limit=100))
            if not photos.photos:
                break
            input_photos = [InputPhoto(id=p.id, access_hash=p.access_hash, file_reference=p.file_reference) for p in photos.photos]
            if input_photos:
                await client(DeletePhotosRequest(id=input_photos))
            else:
                break
    except:
        pass


@register(outgoing=True, pattern=r"^\.afk$")
async def afk_mode(event):
    """AFK moduna geç"""
    global ORIGINAL_PROFILE
    
    if event.fwd_from:
        return
    
    # Zaten AFK modundaysa
    if ORIGINAL_PROFILE["is_afk"]:
        await event.edit("`❌ Zaten AFK modundasın!`\n`Çıkmak için: .unafk`")
        return
    
    await event.edit("`🔄 AFK moduna geçiliyor...`")
    
    # Mevcut profili kaydet
    try:
        await event.edit("`📸 Mevcut profilin kaydediliyor...`")
        
        me = await event.client.get_me()
        my_full = await event.client(GetFullUserRequest(me.id))
        
        ORIGINAL_PROFILE["first_name"] = me.first_name or ""
        ORIGINAL_PROFILE["last_name"] = me.last_name or ""
        ORIGINAL_PROFILE["about"] = my_full.full_user.about or "" if hasattr(my_full, 'full_user') else ""
        
        # Eski fotoğrafları temizle
        for f in os.listdir(AFK_PROFILE_DIR):
            try:
                os.remove(os.path.join(AFK_PROFILE_DIR, f))
            except:
                pass
        
        # Fotoğrafları indir
        ORIGINAL_PROFILE["photos"] = await download_all_profile_photos(event.client, me.id, AFK_PROFILE_DIR, "original")
        ORIGINAL_PROFILE["photo_count"] = len(ORIGINAL_PROFILE["photos"])
        
        # Emoji status kaydet
        if hasattr(me, 'emoji_status') and me.emoji_status:
            if hasattr(me.emoji_status, 'document_id'):
                ORIGINAL_PROFILE["emoji_status"] = me.emoji_status.document_id
            else:
                ORIGINAL_PROFILE["emoji_status"] = None
        else:
            ORIGINAL_PROFILE["emoji_status"] = None
        
    except Exception as e:
        await event.edit(f"`❌ Profil kaydedilemedi: {e}`")
        return
    
    # AFK profilini uygula
    try:
        await event.edit("`⏳ AFK profili uygulanıyor...`")
        
        # İsmi "AFK" yap, soyismi ve bio'yu temizle
        await event.client(functions.account.UpdateProfileRequest(
            first_name="AFK",
            last_name="",
            about=""
        ))
        
        # Tüm fotoğrafları sil
        await delete_all_my_photos(event.client)
        
        # AFK emoji status ayarla (premium gerektirir)
        emoji_status_msg = ""
        try:
            await event.client(UpdateEmojiStatusRequest(
                emoji_status=EmojiStatus(document_id=AFK_EMOJI_ID)
            ))
            emoji_status_msg = "✓"
        except Exception as e:
            if "PREMIUM_ACCOUNT_REQUIRED" in str(e):
                emoji_status_msg = "✗ (premium gerekli)"
            else:
                emoji_status_msg = "✗"
        
        ORIGINAL_PROFILE["is_afk"] = True
        
        photo_count = ORIGINAL_PROFILE["photo_count"]
        name_display = f"{ORIGINAL_PROFILE['first_name']} {ORIGINAL_PROFILE['last_name']}".strip()
        
        await event.edit(
            f"**✅ AFK Modu Aktif!**\n\n"
            f"`👤 Kayıtlı:` {name_display}\n"
            f"`📸 Kayıtlı:` {photo_count} fotoğraf/video\n"
            f"`😴 Emoji:` {emoji_status_msg}\n\n"
            f"`Çıkmak için:` `.unafk`"
        )
        
    except Exception as e:
        await event.edit(f"`❌ AFK modu uygulanamadı: {str(e)}`")


@register(outgoing=True, pattern=r"^\.unafk$")
async def unafk_mode(event):
    """AFK modundan çık"""
    global ORIGINAL_PROFILE
    
    if event.fwd_from:
        return
    
    # AFK modunda değilse
    if not ORIGINAL_PROFILE["is_afk"]:
        await event.edit("`❌ AFK modunda değilsin!`")
        return
    
    await event.edit("`🔄 Orijinal profile dönülüyor...`")
    
    try:
        # İsim ve bio'yu geri yükle
        await event.client(functions.account.UpdateProfileRequest(
            first_name=ORIGINAL_PROFILE["first_name"],
            last_name=ORIGINAL_PROFILE["last_name"],
            about=ORIGINAL_PROFILE["about"]
        ))
        
        # Mevcut fotoğrafları sil
        await delete_all_my_photos(event.client)
        
        # Emoji status geri yükle
        emoji_status_msg = ""
        try:
            if ORIGINAL_PROFILE["emoji_status"]:
                await event.client(UpdateEmojiStatusRequest(
                    emoji_status=EmojiStatus(document_id=ORIGINAL_PROFILE["emoji_status"])
                ))
                emoji_status_msg = "✓"
            else:
                await event.client(UpdateEmojiStatusRequest(emoji_status=EmojiStatusEmpty()))
                emoji_status_msg = "✓"
        except:
            emoji_status_msg = "✗"
        
        # Fotoğrafları geri yükle
        uploaded_count = 0
        if ORIGINAL_PROFILE["photos"]:
            for photo_path, is_video in reversed(ORIGINAL_PROFILE["photos"]):
                if os.path.exists(photo_path):
                    try:
                        pfile = await event.client.upload_file(photo_path)
                        if is_video:
                            await event.client(UploadProfilePhotoRequest(video=pfile))
                        else:
                            await event.client(UploadProfilePhotoRequest(file=pfile))
                        uploaded_count += 1
                    except:
                        pass
        
        ORIGINAL_PROFILE["is_afk"] = False
        
        name_display = f"{ORIGINAL_PROFILE['first_name']} {ORIGINAL_PROFILE['last_name']}".strip()
        
        await event.edit(
            f"**✅ Orijinal Profile Döndün!**\n\n"
            f"`👤` {name_display}\n"
            f"`📸` {uploaded_count} fotoğraf/video yüklendi\n"
            f"`😀 Emoji:` {emoji_status_msg}"
        )
        
    except Exception as e:
        await event.edit(f"`❌ Hata: {str(e)}`")


CMD_HELP.update({
    "afk":
    "`.afk` - AFK moduna geç (profil otomatik kaydedilir)\n"
    "`.unafk` - Orijinal profile dön"
})