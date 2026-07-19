# ============================================
# KingTG UserBot Service - Admin / users
# Kullanıcı listesi (tıklanabilir), detay paneli,
# butonlu ban/sudo yönetimi + ID ile ekleme akışı
# ============================================

from telethon import events, Button
import config
from database import database as db
from userbot.smart_manager import smart_session_manager
from userbot.plugins import plugin_manager
from utils.logger import get_logger

log = get_logger(__name__)

# Eski uyumluluk için alias
userbot_manager = smart_session_manager
from utils import back_button

from ._state import admin_input_state

USERS_PER_PAGE = 10


def register(bot):

    # ==========================================
    # ORTAK: kullanıcı detay paneli oluşturucu
    # /info komutu ve uinfo_ butonu aynı paneli kullanır
    # ==========================================
    async def build_user_info(user_id):
        user_data = await db.get_user(user_id)
        if not user_data:
            return None, None
        try:
            tg_user = await bot.get_entity(user_id)
            tg_username = tg_user.username
            tg_first_name = tg_user.first_name or ""
            tg_last_name = tg_user.last_name or ""
        except Exception:
            tg_username = user_data.get("username")
            tg_first_name = user_data.get("first_name", "")
            tg_last_name = ""
        is_logged_in = user_data.get("is_logged_in", False)
        is_banned = user_data.get("is_banned", False)
        is_sudo = user_data.get("is_sudo", False)
        status = "🚫 Banlı" if is_banned else ("🟢 Aktif" if is_logged_in else "⚪ Pasif")
        text = "👤 **Kullanıcı Bilgileri**\n\n━━━━━━━━━━━━━━━━━━━━\n"
        text += f"🆔 **ID:** `{user_id}`\n👤 **İsim:** {tg_first_name} {tg_last_name}\n"
        if tg_username:
            text += f"📧 **Username:** @{tg_username}\n"
        text += f"🔗 **Profil:** [Tıkla](tg://user?id={user_id})\n📊 **Durum:** {status}\n"
        if is_sudo:
            text += f"👑 **Yetki:** Sudo\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        if is_logged_in or user_data.get("userbot_id"):
            text += "\n🤖 **Userbot:**\n"
            text += f"  • ID: `{user_data.get('userbot_id', 'Yok')}`\n"
            text += f"  • Username: @{user_data.get('userbot_username', 'Yok')}\n"
            text += f"  • Session: `{user_data.get('session_type', '?')}`\n"
            phone = user_data.get("phone_number")
            if phone:
                masked = phone[:4] + "****" + phone[-2:] if len(phone) > 6 else phone
                text += f"  • Telefon: `{masked}`\n"
        active_plugins = user_data.get("active_plugins", [])
        if active_plugins:
            text += f"\n🔌 **Plugin ({len(active_plugins)}):** {', '.join([f'`{p}`' for p in active_plugins[:5]])}"
            if len(active_plugins) > 5:
                text += f" +{len(active_plugins) - 5}"
            text += "\n"
        if is_banned:
            text += f"\n🚫 **Ban:** {user_data.get('ban_reason', 'Sebep yok')}\n"
        buttons = []
        if is_banned:
            buttons.append([Button.inline("✅ Banı Kaldır", f"unban_user_{user_id}".encode())])
        else:
            buttons.append([Button.inline("🚫 Banla", f"ban_user_{user_id}".encode())])
        if is_sudo:
            buttons.append([Button.inline("👑 Sudo Kaldır", f"del_sudo_{user_id}".encode())])
        else:
            buttons.append([Button.inline("👑 Sudo Yap", f"add_sudo_{user_id}".encode())])
        if is_logged_in:
            buttons.append([Button.inline("🚪 Zorla Çıkış", f"force_logout_{user_id}".encode())])
        buttons.append([Button.inline("🔙 Kullanıcı Listesi", b"users_list_0")])
        return text, buttons

    async def _show_user_info(event, user_id):
        """Aksiyondan sonra detay panelini tazele"""
        text, buttons = await build_user_info(user_id)
        if not text:
            return
        try:
            await event.edit(text, buttons=buttons, link_preview=False)
        except Exception:
            log.debug("Detay paneli yenilenemedi", exc_info=True)

    # ==========================================
    # KULLANICI LİSTESİ — her kullanıcı bir BUTON
    # Dokun → detay paneli (ban/sudo/çıkış butonlu)
    # ==========================================
    @bot.on(events.CallbackQuery(pattern=rb"users_list_(\d+)"))
    async def users_list_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        page = int(event.data.decode().split("_")[-1])
        users = await db.get_all_users()
        if not users:
            await event.edit("📭 Henüz kullanıcı yok.", buttons=[back_button("settings_menu")])
            return
        total_pages = (len(users) + USERS_PER_PAGE - 1) // USERS_PER_PAGE
        page = max(0, min(page, total_pages - 1))
        page_users = users[page * USERS_PER_PAGE:(page + 1) * USERS_PER_PAGE]
        text = f"👥 **Kullanıcı Listesi** (Sayfa {page + 1}/{total_pages})\n\n"
        text += "Detay ve işlemler için kullanıcıya **dokun**.\n\n"
        text += f"🟢 Aktif | ⚪ Pasif | 🚫 Banlı | 👑 Sudo\n📊 Toplam: **{len(users)}**"

        buttons = []
        row_buf = []
        for user in page_users:
            user_id = user.get("user_id")
            first_name = (user.get("first_name") or "").strip()
            username = user.get("username")
            is_banned = user.get("is_banned", False)
            status = "🚫" if is_banned else ("🟢" if user.get("is_logged_in", False) else "⚪")
            crown = "👑" if user.get("is_sudo", False) else ""
            label_name = f"@{username}" if username else (first_name or str(user_id))
            row_buf.append(Button.inline(f"{status}{crown} {label_name[:20]}",
                                         f"uinfo_{user_id}".encode()))
            if len(row_buf) == 2:
                buttons.append(row_buf)
                row_buf = []
        if row_buf:
            buttons.append(row_buf)

        nav_buttons = []
        if page > 0:
            nav_buttons.append(Button.inline("⬅️", f"users_list_{page - 1}".encode()))
        if page < total_pages - 1:
            nav_buttons.append(Button.inline("➡️", f"users_list_{page + 1}".encode()))
        if nav_buttons:
            buttons.append(nav_buttons)
        buttons.append([Button.inline("🔄 Yenile", f"users_list_{page}".encode())])
        buttons.append(back_button("settings_menu"))
        await event.edit(text, buttons=buttons, link_preview=False)

    @bot.on(events.CallbackQuery(pattern=rb"uinfo_(\d+)"))
    async def user_info_button(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        user_id = int(event.data.decode().split("_")[-1])
        text, buttons = await build_user_info(user_id)
        if not text:
            await event.answer("Kullanıcı bulunamadı", alert=True)
            return
        await event.edit(text, buttons=buttons, link_preview=False)
        await event.answer()

    @bot.on(events.NewMessage(pattern=r'^/info\s+(\d+)$'))
    async def info_command(event):
        if event.sender_id != config.OWNER_ID:
            return
        user_id = int(event.pattern_match.group(1))
        text, buttons = await build_user_info(user_id)
        if not text:
            await event.respond(f"❌ `{user_id}` bulunamadı.")
            return
        await event.respond(text, buttons=buttons, link_preview=False)

    # ==========================================
    # AKSİYON BUTONLARI — işlemden sonra detay paneli tazelenir
    # ==========================================
    @bot.on(events.CallbackQuery(pattern=rb"ban_user_(\d+)"))
    async def ban_user_button(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        user_id = int(event.data.decode().split("_")[-1])
        if user_id == config.OWNER_ID:
            await event.answer("❌ Kendinizi banlayamazsınız!", alert=True)
            return
        await db.ban_user(user_id, "Admin tarafından", event.sender_id)
        await userbot_manager.logout(user_id)
        plugin_manager.clear_user_plugins(user_id)
        await event.answer(f"✅ {user_id} banlandı!")
        await _show_user_info(event, user_id)

    @bot.on(events.CallbackQuery(pattern=rb"unban_user_(\d+)"))
    async def unban_user_button(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        user_id = int(event.data.decode().split("_")[-1])
        await db.unban_user(user_id)
        await event.answer(f"✅ {user_id} banı kaldırıldı!")
        await _show_user_info(event, user_id)

    @bot.on(events.CallbackQuery(pattern=rb"add_sudo_(\d+)"))
    async def add_sudo_button(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        user_id = int(event.data.decode().split("_")[-1])
        await db.add_sudo(user_id)
        await event.answer(f"✅ {user_id} sudo yapıldı!")
        await _show_user_info(event, user_id)

    @bot.on(events.CallbackQuery(pattern=rb"del_sudo_(\d+)"))
    async def del_sudo_button(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        user_id = int(event.data.decode().split("_")[-1])
        await db.remove_sudo(user_id)
        await event.answer(f"✅ {user_id} sudo kaldırıldı!")
        await _show_user_info(event, user_id)

    @bot.on(events.CallbackQuery(pattern=rb"force_logout_(\d+)"))
    async def force_logout_button(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        user_id = int(event.data.decode().split("_")[-1])
        await userbot_manager.logout(user_id)
        plugin_manager.clear_user_plugins(user_id)
        await db.update_user(user_id, {"is_logged_in": False})
        await event.answer(f"✅ {user_id} çıkış yaptırıldı!")
        try:
            await bot.send_message(user_id, "⚠️ **Oturumunuz admin tarafından sonlandırıldı.**")
        except Exception:
            log.debug("Kullanıcıya çıkış bildirimi gönderilemedi: %s", user_id, exc_info=True)
        await _show_user_info(event, user_id)

    @bot.on(events.NewMessage(pattern=r'^/users$'))
    async def users_command(event):
        if event.sender_id != config.OWNER_ID:
            return
        users = await db.get_all_users()
        if not users:
            await event.respond("📭 Henüz kullanıcı yok.")
            return
        # Komut da butonlu listeyi açar
        await event.respond(
            f"👥 **{len(users)}** kullanıcı kayıtlı.\nListe için butona dokun:",
            buttons=[[Button.inline("👥 Kullanıcı Listesi", b"users_list_0")]]
        )

    # ==========================================
    # BAN YÖNETİMİ — banlılar buton, dokun → kaldır
    # ==========================================
    @bot.on(events.CallbackQuery(data=b"ban_management"))
    async def ban_management_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        banned = await db.get_banned_users()
        text = "🚫 **Ban Yönetimi**\n\n"
        buttons = []
        if banned:
            text += "Banı **kaldırmak** için kullanıcıya dokun:\n"
            for user in banned[:20]:
                uid = user.get("user_id")
                reason = (user.get("ban_reason") or "Sebep yok")[:15]
                buttons.append([Button.inline(f"🚫 {uid} · {reason}", f"unban_user_{uid}".encode())])
        else:
            text += "✅ Banlı kullanıcı yok."
        buttons.append([Button.inline("➕ ID ile Banla", b"adm_input_ban")])
        buttons.append(back_button("settings_menu"))
        await event.edit(text, buttons=buttons)

    @bot.on(events.NewMessage(pattern=r'^/ban\s+(\d+)(?:\s+(.+))?$'))
    async def ban_command(event):
        if event.sender_id != config.OWNER_ID:
            return
        user_id = int(event.pattern_match.group(1))
        reason = event.pattern_match.group(2) or "Sebep yok"
        if user_id == config.OWNER_ID:
            await event.respond("❌ Kendinizi banlayamazsınız!")
            return
        await db.add_user(user_id)
        await db.ban_user(user_id, reason, event.sender_id)
        await userbot_manager.logout(user_id)
        plugin_manager.clear_user_plugins(user_id)
        await event.respond(f"✅ `{user_id}` banlandı.\n📝 {reason}")

    @bot.on(events.NewMessage(pattern=r'^/unban\s+(\d+)$'))
    async def unban_command(event):
        if event.sender_id != config.OWNER_ID:
            return
        user_id = int(event.pattern_match.group(1))
        await db.unban_user(user_id)
        await event.respond(f"✅ `{user_id}` banı kaldırıldı.")

    # ==========================================
    # SUDO YÖNETİMİ — sudolar buton, dokun → kaldır
    # ==========================================
    @bot.on(events.CallbackQuery(data=b"sudo_management"))
    async def sudo_management_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        sudos = await db.get_sudos()
        text = "👑 **Sudo Yönetimi**\n\n"
        buttons = []
        if sudos:
            text += "Sudo'yu **kaldırmak** için kullanıcıya dokun:\n"
            for user in sudos[:20]:
                uid = user.get("user_id")
                uname = user.get("username")
                label = f"@{uname}" if uname else str(uid)
                buttons.append([Button.inline(f"👑 {label}", f"del_sudo_{uid}".encode())])
        else:
            text += "Henüz sudo yok."
        buttons.append([Button.inline("➕ Sudo Ekle", b"adm_input_sudo")])
        buttons.append(back_button("settings_menu"))
        await event.edit(text, buttons=buttons)

    @bot.on(events.NewMessage(pattern=r'^/addsudo\s+(\d+)$'))
    async def addsudo_command(event):
        if event.sender_id != config.OWNER_ID:
            return
        user_id = int(event.pattern_match.group(1))
        await db.add_user(user_id)
        await db.add_sudo(user_id)
        await event.respond(f"✅ `{user_id}` sudo eklendi.")

    @bot.on(events.NewMessage(pattern=r'^/delsudo\s+(\d+)$'))
    async def delsudo_command(event):
        if event.sender_id != config.OWNER_ID:
            return
        user_id = int(event.pattern_match.group(1))
        await db.remove_sudo(user_id)
        await event.respond(f"✅ `{user_id}` sudo kaldırıldı.")

    # ==========================================
    # ID İLE EKLEME AKIŞI (komut yazmaya gerek yok)
    # ➕ butona dokun → ID gönder → işlem yapılır
    # ==========================================
    @bot.on(events.CallbackQuery(pattern=rb"adm_input_(ban|sudo)"))
    async def admin_input_start(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        action = event.data.decode().split("_")[-1]
        admin_input_state[event.sender_id] = {"kind": action, "plugin": None}
        label = "banlanacak" if action == "ban" else "sudo yapılacak"
        await event.edit(
            f"🆔 **{label.capitalize()} kullanıcının ID'sini gönder.**\n\n"
            f"Örnek: `123456789`\n"
            f"💡 ID'yi bilmiyorsan kullanıcı listesinden de seçebilirsin.",
            buttons=[
                [Button.inline("👥 Listeden Seç", b"users_list_0")],
                [Button.inline("❌ İptal", b"adm_input_cancel")],
            ]
        )
        await event.answer()

    @bot.on(events.CallbackQuery(data=b"adm_input_cancel"))
    async def admin_input_cancel(event):
        admin_input_state.pop(event.sender_id, None)
        await event.answer("İptal edildi")
        await event.edit("❌ İşlem iptal edildi.", buttons=[back_button("settings_menu")])

    @bot.on(events.NewMessage(pattern=r'^(\d{5,15})$'))
    async def admin_input_receive(event):
        """Sadece owner bir ban/sudo giriş akışı başlattıysa çalışır"""
        if event.sender_id != config.OWNER_ID:
            return
        state = admin_input_state.get(event.sender_id)
        if not state or state.get("kind") not in ("ban", "sudo"):
            return
        admin_input_state.pop(event.sender_id, None)
        action = state["kind"]
        user_id = int(event.pattern_match.group(1))
        if action == "ban":
            if user_id == config.OWNER_ID:
                await event.respond("❌ Kendinizi banlayamazsınız!")
                return
            await db.add_user(user_id)
            await db.ban_user(user_id, "Admin tarafından", event.sender_id)
            await userbot_manager.logout(user_id)
            plugin_manager.clear_user_plugins(user_id)
            await event.respond(f"✅ `{user_id}` banlandı.",
                                buttons=[[Button.inline("🚫 Ban Yönetimi", b"ban_management")]])
        elif action == "sudo":
            await db.add_user(user_id)
            await db.add_sudo(user_id)
            await event.respond(f"✅ `{user_id}` sudo yapıldı.",
                                buttons=[[Button.inline("👑 Sudo Yönetimi", b"sudo_management")]])
