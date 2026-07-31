"""
Herhangi bir sohbete kulanarak istediğiniz kişinin kılığına tek komutla girip orjinal profileze tek komut ile dönün.

🔧 Komutlar:  .clon, .unclon, .saveme, .cloninfo, .resetclon
🚨 Tür: #eğlence


Komular hakında:
.clon:
bu komutu kullanarak istediğiniz telegram kulanıcısının kulanıcı adı, id veya mesajını yanıtlayarak kulandığınızda kişinin profil resmini, adını, hakında mesajını ve premium ifade durumunu taklit eder.

.unclon:
bu komutu herhangi bir sohbete kulandığınızda dilediğiniz zaman orjinal profilinie hızlıcaa geri dönebilirsiniz.

.saveme:
bu komutu klonlama işemi yapmadan önce son yaptığınız klonlama işlemi boyunca profilinizde bir değişiklik yaptıysanız birisini klonlamadan önce bu komutu kulanıp orjinal profilinize dönebilmek için kaydedin (sadece profilinzde bir değişiklik yatığınız zaman bu komutu kulanın).

.cloninfo:
bu omutu herhangi bir sohbete girdiğiniz zaman klonladığınız kişinin bilgilerini gösterir.

.resetclon:
herhangi bir sohbete kulanıldığı zaman kayıtlı profil bilgilerinzizi siler. (bu işlmeden sonra .clon komutu'nu kulandığınız zaman otomotik mevcut profilinizi kaydeder).
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

ORIGINAL_PROFILE_DIR = os.path.join(TEMP_DOWNLOAD_DIRECTORY, "original_profile")
if not os.path.exists(ORIGINAL_PROFILE_DIR):
    os.makedirs(ORIGINAL_PROFILE_DIR)


def _user_original_dir(uid):
    """Kullanıcı-başına orijinal profil foto dizini (çoklu hesapta foto çakışmasını önler)."""
    d = os.path.join(ORIGINAL_PROFILE_DIR, str(uid))
    os.makedirs(d, exist_ok=True)
    return d

# Şeffaf/Görünmez emoji ID (https://t.me/addemoji/blank25 paketinden)
# Premium olmayan kullanıcı klonlanınca bu emoji kullanılır
INVISIBLE_EMOJI_ID = 5420560971674435677

# Klonlarken/geri dönerken en fazla bu kadar fotoğraf işlenir
# (100+ fotoğraflı profillerde çökme ve uzun beklemeyi önler)
MAX_PHOTOS = 10

ORIGINAL_PROFILE = {
    "first_name": None,
    "last_name": None,
    "about": None,
    "photos": [],
    "photo_count": 0,
    "emoji_status": None,
    "is_saved": False,
    "is_cloned": False
}


# ── KALICI DURUM (restart sonrası klon kilidini önler) ─────────────
import json

_CLON_STATE_FILE = os.path.join(TEMP_DOWNLOAD_DIRECTORY, "clon_state.json")


def _clon_load_all():
    try:
        if os.path.exists(_CLON_STATE_FILE):
            with open(_CLON_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as _e:
        log.debug(f"Klon durumu okunamadı: {_e}")
    return {}


def _clon_save_all(data):
    try:
        _tmp = _CLON_STATE_FILE + ".tmp"
        with open(_tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(_tmp, _CLON_STATE_FILE)
    except Exception as _e:
        log.warning(f"Klon durumu kaydedilemedi: {_e}")


def _default_profile():
    return {"first_name": None, "last_name": None, "about": None,
            "photos": [], "photo_count": 0, "emoji_status": None, "is_saved": False, "is_cloned": False}


def _load_state(uid):
    p = _clon_load_all().get(str(uid))
    if not p:
        return _default_profile()
    base = _default_profile()
    base.update(p)
    return base


def _save_state(uid, profile):
    data = _clon_load_all()
    data[str(uid)] = profile
    _clon_save_all(data)


def _clear_state(uid):
    data = _clon_load_all()
    data.pop(str(uid), None)
    _clon_save_all(data)


def cleanup_user_data(user_id, reason="disable"):
    """Kullanıcının klon verilerini temizle (çıkış/devre dışı/silme).
    Kayıtlı orijinal profil varken silmez (.unclon ile dönülebilmeli); geçici klasör her zaman temizlenir."""
    import shutil
    try:
        clone_dir = os.path.join(TEMP_DOWNLOAD_DIRECTORY, "clone_temp")
        if os.path.isdir(clone_dir):
            shutil.rmtree(clone_dir, ignore_errors=True)
        state = _load_state(user_id)
        if state.get("is_saved") and reason != "delete":
            return
        udir = os.path.join(ORIGINAL_PROFILE_DIR, str(user_id))
        if os.path.isdir(udir):
            shutil.rmtree(udir, ignore_errors=True)
        data = _clon_load_all()
        if str(user_id) in data:
            data.pop(str(user_id), None)
            _clon_save_all(data)
    except Exception:
        pass


async def download_all_profile_photos(client, user_id, save_dir, prefix="photo", max_count=None):
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


async def get_target_user(client, event, input_str=None):
    """Hedef kullanıcıyı bul - yanıt, ID veya kullanıcı adı ile"""
    
    # 1. Önce yanıtlanan mesajı kontrol et
    if event.reply_to_msg_id:
        reply = await event.get_reply_message()
        if reply and reply.sender_id:
            try:
                user = await client(GetFullUserRequest(reply.sender_id))
                return user, None
            except Exception as e:
                return None, f"Yanıtlanan kullanıcı bulunamadı: {e}"
    
    # 2. Input string varsa kontrol et
    if input_str:
        input_str = input_str.strip()
        
        # @ işaretini kaldır
        if input_str.startswith('@'):
            input_str = input_str[1:]
        
        # ID olarak dene
        if input_str.isdigit():
            try:
                user = await client(GetFullUserRequest(int(input_str)))
                return user, None
            except Exception as e:
                return None, f"ID bulunamadı: {e}"
        
        # Kullanıcı adı olarak dene
        try:
            entity = await client.get_entity(input_str)
            user = await client(GetFullUserRequest(entity.id))
            return user, None
        except Exception as e:
            return None, f"Kullanıcı bulunamadı: {e}"
    
    return None, "Kullanıcı belirtilmedi"


@register(outgoing=True, pattern=r"^\.[kc]lon$")
async def klon_help(event):
    if event.fwd_from:
        return
    
    # Yanıt varsa klonla
    if event.reply_to_msg_id:
        await do_clone(event, None)
        return
    
    # Yanıt yoksa yardım göster
    await event.edit(
        "**🎭 Klon Plugin**\n\n"
        "**Kullanım:**\n"
        "• `.clon @kullanıcı` - Kullanıcı adıyla\n"
        "• `.clon 123456789` - ID ile\n"
        "• Mesajı yanıtla + `.clon`\n\n"
        "**Diğer:**\n"
        "• `.unclon` - Orijinal profile dön\n"
        "• `.saveme` - Profilini kaydet\n"
        "• `.cloninfo` - Kayıtlı profili göster\n"
        "• `.resetclon` - Verileri sıfırla"
    )


@register(outgoing=True, pattern=r"^\.[kc]lon (.+)")
async def klon_with_input(event):
    if event.fwd_from:
        return
    input_str = event.pattern_match.group(1).strip()
    await do_clone(event, input_str)


async def do_clone(event, input_str):
    global ORIGINAL_PROFILE

    await event.edit("`🔄 Klonlanıyor...`")

    me = await event.client.get_me()
    ORIGINAL_PROFILE = _load_state(me.id)  # diskten (restart sonrası bile)

    # Orijinal profili kaydet (henüz kaydedilmemişse)
    if not ORIGINAL_PROFILE["is_saved"]:
        try:
            await event.edit("`📸 Orijinal profilin kaydediliyor...`")

            my_full = await event.client(GetFullUserRequest(me.id))

            ORIGINAL_PROFILE["first_name"] = me.first_name or ""
            ORIGINAL_PROFILE["last_name"] = me.last_name or ""
            ORIGINAL_PROFILE["about"] = my_full.full_user.about or "" if hasattr(my_full, 'full_user') else ""

            _udir = _user_original_dir(me.id)
            for f in os.listdir(_udir):
                try:
                    os.remove(os.path.join(_udir, f))
                except Exception:
                    pass

            ORIGINAL_PROFILE["photos"] = await download_all_profile_photos(event.client, me.id, _udir, "original", max_count=MAX_PHOTOS)
            ORIGINAL_PROFILE["photo_count"] = len(ORIGINAL_PROFILE["photos"])

            if hasattr(me, 'emoji_status') and me.emoji_status and hasattr(me.emoji_status, 'document_id'):
                ORIGINAL_PROFILE["emoji_status"] = me.emoji_status.document_id
            else:
                ORIGINAL_PROFILE["emoji_status"] = None

            ORIGINAL_PROFILE["is_saved"] = True
            _save_state(me.id, ORIGINAL_PROFILE)  # KALICI: restart'ta kaybolmaz

        except Exception as e:
            await event.edit(f"`❌ Profil kaydedilemedi: {e}`")
            return

    # Hedef kullanıcıyı bul
    replied_user, error = await get_target_user(event.client, event, input_str)

    if not replied_user:
        await event.edit(f"`❌ {error}`")
        return

    try:
        if hasattr(replied_user, 'users') and replied_user.users:
            target_user = replied_user.users[0]
        elif hasattr(replied_user, 'user'):
            target_user = replied_user.user
        else:
            await event.edit("`❌ Kullanıcı bilgisi alınamadı!`")
            return

        user_id = target_user.id
        first_name = target_user.first_name.replace("\u2060", "") if target_user.first_name else ""
        last_name = target_user.last_name.replace("\u2060", "") if target_user.last_name else ""
        user_bio = replied_user.full_user.about if hasattr(replied_user, 'full_user') and replied_user.full_user.about else ""

        clone_dir = os.path.join(TEMP_DOWNLOAD_DIRECTORY, "clone_temp")
        if not os.path.exists(clone_dir):
            os.makedirs(clone_dir)
        for f in os.listdir(clone_dir):
            try:
                os.remove(os.path.join(clone_dir, f))
            except Exception:
                pass

        target_photos = await download_all_profile_photos(event.client, user_id, clone_dir, "clone", max_count=MAX_PHOTOS)

        await event.client(functions.account.UpdateProfileRequest(first_name=first_name, last_name=last_name, about=user_bio))
        await delete_all_my_photos(event.client)

        if target_photos:
            for photo_path, is_video in reversed(target_photos):
                if os.path.exists(photo_path):
                    try:
                        pfile = await event.client.upload_file(photo_path)
                        if is_video:
                            await event.client(UploadProfilePhotoRequest(video=pfile))
                        else:
                            await event.client(UploadProfilePhotoRequest(file=pfile))
                    except Exception:
                        pass

        # Hedefin indirilen fotoğrafları profile yüklendi — yerel kopyaları temizle (çöp bırakma)
        for _cf in os.listdir(clone_dir):
            try:
                os.remove(os.path.join(clone_dir, _cf))
            except Exception:
                pass

        emoji_status_msg = ""
        try:
            if hasattr(target_user, 'emoji_status') and target_user.emoji_status:
                if hasattr(target_user.emoji_status, 'document_id'):
                    await event.client(UpdateEmojiStatusRequest(
                        emoji_status=EmojiStatus(document_id=target_user.emoji_status.document_id)
                    ))
                    emoji_status_msg = ", emoji ✓"
            else:
                await event.client(UpdateEmojiStatusRequest(
                    emoji_status=EmojiStatus(document_id=INVISIBLE_EMOJI_ID)
                ))
                emoji_status_msg = ", emoji 👻"
        except Exception as e:
            if "PREMIUM_ACCOUNT_REQUIRED" in str(e):
                emoji_status_msg = ", emoji ✗ (premium gerekli)"
            pass

        photo_status = f"{len(target_photos)} fotoğraf/video" if target_photos else "fotoğraf yok"
        bio_status = "bio var" if user_bio else "bio yok"

        ORIGINAL_PROFILE["is_cloned"] = True
        _save_state(me.id, ORIGINAL_PROFILE)

        await event.edit(f"`✅ Klonlandı! ({photo_status}, {bio_status}{emoji_status_msg})`")

    except Exception as e:
        await event.edit(f"`❌ Hata: {str(e)}`")


@register(outgoing=True, pattern=r"^\.un[ck]lon$")
async def unclone(event):
    global ORIGINAL_PROFILE
    if event.fwd_from:
        return

    me = await event.client.get_me()
    ORIGINAL_PROFILE = _load_state(me.id)  # diskten: restart sonrası bile geri dönebilir

    if not ORIGINAL_PROFILE["is_saved"]:
        await event.edit("`❌ Kayıtlı profil yok! Önce birini klonla.`")
        return

    await event.edit("`🔄 Orijinal profile dönülüyor...`")

    try:
        await event.client(functions.account.UpdateProfileRequest(
            first_name=ORIGINAL_PROFILE["first_name"],
            last_name=ORIGINAL_PROFILE["last_name"],
            about=ORIGINAL_PROFILE["about"]
        ))

        await delete_all_my_photos(event.client)

        try:
            if ORIGINAL_PROFILE["emoji_status"]:
                await event.client(UpdateEmojiStatusRequest(
                    emoji_status=EmojiStatus(document_id=ORIGINAL_PROFILE["emoji_status"])
                ))
            else:
                await event.client(UpdateEmojiStatusRequest(emoji_status=EmojiStatusEmpty()))
        except Exception:
            pass

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

        ORIGINAL_PROFILE["is_cloned"] = False
        _save_state(me.id, ORIGINAL_PROFILE)

        if uploaded_count > 0:
            await event.edit(f"`✅ Orijinal profile döndün! ({uploaded_count} fotoğraf/video)`")
        else:
            await event.edit("`✅ Orijinal profile döndün!`")

    except Exception as e:
        await event.edit(f"`❌ Hata: {str(e)}`")


@register(outgoing=True, pattern=r"^\.reset[kc]lon$")
async def reset_clone_data(event):
    global ORIGINAL_PROFILE
    if event.fwd_from:
        return

    me = await event.client.get_me()
    ORIGINAL_PROFILE = _load_state(me.id)

    for photo_path, _ in ORIGINAL_PROFILE.get("photos", []):
        if photo_path and os.path.exists(photo_path):
            try:
                os.remove(photo_path)
            except Exception:
                pass

    ORIGINAL_PROFILE = _default_profile()
    _clear_state(me.id)  # diskten de sil
    await event.edit("`✅ Klon verileri sıfırlandı!`")


@register(outgoing=True, pattern=r"^\.saveme$")
async def save_my_profile(event):
    global ORIGINAL_PROFILE
    if event.fwd_from:
        return

    await event.edit("`🔄 Profilin kaydediliyor...`")

    try:
        me = await event.client.get_me()
        ORIGINAL_PROFILE = _load_state(me.id)
        my_full = await event.client(GetFullUserRequest(me.id))

        ORIGINAL_PROFILE["first_name"] = me.first_name or ""
        ORIGINAL_PROFILE["last_name"] = me.last_name or ""
        ORIGINAL_PROFILE["about"] = my_full.full_user.about or "" if hasattr(my_full, 'full_user') else ""

        _udir = _user_original_dir(me.id)
        for f in os.listdir(_udir):
            try:
                os.remove(os.path.join(_udir, f))
            except Exception:
                pass

        ORIGINAL_PROFILE["photos"] = await download_all_profile_photos(event.client, me.id, _udir, "original", max_count=MAX_PHOTOS)
        ORIGINAL_PROFILE["photo_count"] = len(ORIGINAL_PROFILE["photos"])

        if hasattr(me, 'emoji_status') and me.emoji_status and hasattr(me.emoji_status, 'document_id'):
            ORIGINAL_PROFILE["emoji_status"] = me.emoji_status.document_id
        else:
            ORIGINAL_PROFILE["emoji_status"] = None

        ORIGINAL_PROFILE["is_saved"] = True
        _save_state(me.id, ORIGINAL_PROFILE)  # KALICI

        video_count = sum(1 for _, is_video in ORIGINAL_PROFILE["photos"] if is_video)
        photo_count = ORIGINAL_PROFILE["photo_count"] - video_count
        bio_display = ORIGINAL_PROFILE['about'][:50] + '...' if len(ORIGINAL_PROFILE['about']) > 50 else (ORIGINAL_PROFILE['about'] or "(boş)")
        emoji_display = "✓" if ORIGINAL_PROFILE["emoji_status"] else "yok"

        await event.edit(
            f"`✅ Profilin kaydedildi!`\n"
            f"`👤 {ORIGINAL_PROFILE['first_name']} {ORIGINAL_PROFILE['last_name']}`\n"
            f"`📝 {bio_display}`\n"
            f"`📷 {photo_count} 🎥 {video_count} 😀 {emoji_display}`"
        )
    except Exception as e:
        await event.edit(f"`❌ Hata: {str(e)}`")


@register(outgoing=True, pattern=r"^\.[kc]loninfo$")
async def clone_info(event):
    global ORIGINAL_PROFILE
    if event.fwd_from:
        return

    me = await event.client.get_me()
    ORIGINAL_PROFILE = _load_state(me.id)

    if not ORIGINAL_PROFILE["is_saved"]:
        await event.edit("`❌ Kayıtlı profil yok!`")
        return

    video_count = sum(1 for _, is_video in ORIGINAL_PROFILE["photos"] if is_video)
    photo_count = ORIGINAL_PROFILE["photo_count"] - video_count
    bio_display = ORIGINAL_PROFILE['about'] if ORIGINAL_PROFILE['about'] else "(boş)"
    emoji_display = "✓" if ORIGINAL_PROFILE["emoji_status"] else "yok"
    clone_status = "🟢 şu an klonlu" if ORIGINAL_PROFILE.get("is_cloned") else "⚪ klon aktif değil"

    await event.edit(
        f"**📋 Kayıtlı Profil:**\n\n"
        f"`👤` {ORIGINAL_PROFILE['first_name']} {ORIGINAL_PROFILE['last_name']}\n"
        f"`📝` {bio_display}\n"
        f"`📷` {photo_count} `🎥` {video_count} `😀` {emoji_display}\n"
        f"`🔁` {clone_status}"
    )


CMD_HELP.update({
    "clon":
    "`.clon` <yanıt/@kullanıcı/ID> - Profili klonla\n"
    "`.unclon` - Orijinal profile dön\n"
    "`.saveme` - Profilini kaydet\n"
    "`.cloninfo` - Kayıtlı profili göster\n"
    "`.resetclon` - Verileri sıfırla"
})