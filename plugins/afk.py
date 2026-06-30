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
from telethon.tl.types import InputPhoto, EmojiStatus, EmojiStatusEmpty
from telethon.tl import functions
from userbot.events import register
from userbot import CMD_HELP
from utils.logger import get_logger

log = get_logger(__name__)

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

# Klonlarken/geri dönerken en fazla bu kadar fotoğraf işlenir
# (100+ fotoğraflı profillerde çökme ve uzun beklemeyi önler)
MAX_PHOTOS = 10

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


# ── KALICI DURUM (restart sonrası AFK kilidini önler) ──────────────
import json

_AFK_STATE_FILE = os.path.join(TEMP_DOWNLOAD_DIRECTORY, "afk_state.json")


def _afk_load_all():
    try:
        if os.path.exists(_AFK_STATE_FILE):
            with open(_AFK_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as _e:
        log.debug(f"AFK durumu okunamadı: {_e}")
    return {}


def _afk_save_all(data):
    try:
        with open(_AFK_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as _e:
        log.warning(f"AFK durumu kaydedilemedi: {_e}")


def _default_profile():
    return {"first_name": None, "last_name": None, "about": None,
            "photos": [], "photo_count": 0, "emoji_status": None, "is_afk": False}


def _load_state(uid):
    p = _afk_load_all().get(str(uid))
    if not p:
        return _default_profile()
    base = _default_profile()
    base.update(p)
    return base


def _save_state(uid, profile):
    data = _afk_load_all()
    data[str(uid)] = profile
    _afk_save_all(data)


def _user_photo_dir(uid):
    d = os.path.join(AFK_PROFILE_DIR, str(uid))
    os.makedirs(d, exist_ok=True)
    return d


def cleanup_user_data(user_id, reason="disable"):
    """Kullanıcının AFK verilerini temizle (çıkış/devre dışı/silme).
    AFK aktifken silmez (yoksa gerçek profile dönülemez); aksi halde foto klasörü + kayıt silinir."""
    import shutil
    try:
        state = _load_state(user_id)
        if state.get("is_afk") and reason != "delete":
            return
        pdir = os.path.join(AFK_PROFILE_DIR, str(user_id))
        if os.path.isdir(pdir):
            shutil.rmtree(pdir, ignore_errors=True)
        data = _afk_load_all()
        if str(user_id) in data:
            data.pop(str(user_id), None)
            _afk_save_all(data)
    except Exception:
        pass


async def download_all_profile_photos(client, user_id, save_dir, prefix="photo", max_count=None):
    """Tüm profil fotoğraflarını indir"""
    photos_info = []
    try:
        result = await client(GetUserPhotosRequest(user_id=user_id, offset=0, max_id=0, limit=(max_count or 100)))
        if not result.photos:
            return photos_info
        
        for idx, photo in enumerate(result.photos):
            if max_count and len(photos_info) >= max_count:
                break
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
                            except Exception:
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
            except Exception as _e:
                log.debug(f"profil fotoğrafı atlandı: {_e}")
                continue
    except Exception as _e:
        log.warning(f"profil fotoğrafları indirilemedi: {_e}")
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
    except Exception as _e:
        log.warning(f"profil fotoğrafları silinemedi: {_e}")


@register(outgoing=True, pattern=r"^\.afk$")
async def afk_mode(event):
    """AFK moduna geç"""
    global ORIGINAL_PROFILE
    if event.fwd_from:
        return

    me = await event.client.get_me()
    ORIGINAL_PROFILE = _load_state(me.id)  # diskten (restart sonrası bile doğru)

    if ORIGINAL_PROFILE.get("is_afk"):
        await event.edit("`❌ Zaten AFK modundasın!`\n`Çıkmak için: .unafk`")
        return

    await event.edit("`🔄 AFK moduna geçiliyor...`")

    try:
        await event.edit("`📸 Mevcut profilin kaydediliyor...`")
        my_full = await event.client(GetFullUserRequest(me.id))
        ORIGINAL_PROFILE["first_name"] = me.first_name or ""
        ORIGINAL_PROFILE["last_name"] = me.last_name or ""
        ORIGINAL_PROFILE["about"] = my_full.full_user.about or "" if hasattr(my_full, 'full_user') else ""

        pdir = _user_photo_dir(me.id)
        for f in os.listdir(pdir):
            try:
                os.remove(os.path.join(pdir, f))
            except Exception:
                pass

        ORIGINAL_PROFILE["photos"] = await download_all_profile_photos(event.client, me.id, pdir, "original", max_count=MAX_PHOTOS)
        ORIGINAL_PROFILE["photo_count"] = len(ORIGINAL_PROFILE["photos"])

        if hasattr(me, 'emoji_status') and me.emoji_status and hasattr(me.emoji_status, 'document_id'):
            ORIGINAL_PROFILE["emoji_status"] = me.emoji_status.document_id
        else:
            ORIGINAL_PROFILE["emoji_status"] = None

    except Exception as e:
        await event.edit(f"`❌ Profil kaydedilemedi: {e}`")
        return

    try:
        await event.edit("`⏳ AFK profili uygulanıyor...`")
        await event.client(functions.account.UpdateProfileRequest(first_name="AFK", last_name="", about=""))
        await delete_all_my_photos(event.client)

        emoji_status_msg = ""
        try:
            await event.client(UpdateEmojiStatusRequest(emoji_status=EmojiStatus(document_id=AFK_EMOJI_ID)))
            emoji_status_msg = "✓"
        except Exception as e:
            emoji_status_msg = "✗ (premium gerekli)" if "PREMIUM_ACCOUNT_REQUIRED" in str(e) else "✗"

        ORIGINAL_PROFILE["is_afk"] = True
        _save_state(me.id, ORIGINAL_PROFILE)  # KALICI: restart'ta kaybolmaz

        name_display = f"{ORIGINAL_PROFILE['first_name']} {ORIGINAL_PROFILE['last_name']}".strip()
        await event.edit(
            f"**✅ AFK Modu Aktif!**\n\n"
            f"`👤 Kayıtlı:` {name_display}\n"
            f"`📸 Kayıtlı:` {ORIGINAL_PROFILE['photo_count']} fotoğraf/video\n"
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

    me = await event.client.get_me()
    ORIGINAL_PROFILE = _load_state(me.id)  # diskten: restart sonrası bile geri dönebilir

    if not ORIGINAL_PROFILE.get("is_afk"):
        await event.edit("`❌ AFK modunda değilsin!`")
        return

    await event.edit("`🔄 Orijinal profile dönülüyor...`")

    try:
        await event.client(functions.account.UpdateProfileRequest(
            first_name=ORIGINAL_PROFILE["first_name"],
            last_name=ORIGINAL_PROFILE["last_name"],
            about=ORIGINAL_PROFILE["about"]
        ))

        await delete_all_my_photos(event.client)

        emoji_status_msg = ""
        try:
            if ORIGINAL_PROFILE["emoji_status"]:
                await event.client(UpdateEmojiStatusRequest(emoji_status=EmojiStatus(document_id=ORIGINAL_PROFILE["emoji_status"])))
            else:
                await event.client(UpdateEmojiStatusRequest(emoji_status=EmojiStatusEmpty()))
            emoji_status_msg = "✓"
        except Exception:
            emoji_status_msg = "✗"

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
                    except Exception:
                        pass

        ORIGINAL_PROFILE["is_afk"] = False
        _save_state(me.id, ORIGINAL_PROFILE)  # KALICI

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