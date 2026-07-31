# ============================================
# KingTG UserBot Service - Admin / users
# Kullanıcı listesi, bilgi görüntüleme, ban/sudo yönetimi
# (admin.py'dan otomatik bölündü - davranış birebir korundu)
# ============================================

# ============================================
# KingTG UserBot Service - Admin Handlers
# ============================================

import os
import sys
import asyncio
import subprocess
import time
import psutil
from datetime import datetime
from telethon import events, Button
import config
from database import database as db
from userbot.smart_manager import smart_session_manager
from userbot.plugins import plugin_manager

# Eski uyumluluk için alias
userbot_manager = smart_session_manager
from utils import send_log, get_readable_time, back_button
from utils.bot_api import bot_api, btn, ButtonBuilder

USERS_PER_PAGE = 10


def register(bot):

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
        start_idx = page * USERS_PER_PAGE
        end_idx = start_idx + USERS_PER_PAGE
        page_users = users[start_idx:end_idx]
        text = f"👥 **Kullanıcı Listesi** (Sayfa {page + 1}/{total_pages})\n\n"
        for user in page_users:
            user_id = user.get("user_id")
            username = user.get("username")
            first_name = user.get("first_name", "")
            is_logged_in = user.get("is_logged_in", False)
            is_banned = user.get("is_banned", False)
            status = "🚫" if is_banned else ("🟢" if is_logged_in else "⚪")
            user_link = f"[@{username}](tg://user?id={user_id})" if username else f"[{first_name or user_id}](tg://user?id={user_id})"
            text += f"{status} `{user_id}` - {user_link}\n"
        text += f"\n🟢 Aktif | ⚪ Pasif | 🚫 Banlı\n📊 Toplam: **{len(users)}**\n💡 Detay: `/info <id>`"
        nav_buttons = []
        if page > 0:
            nav_buttons.append(Button.inline("⬅️", f"users_list_{page - 1}".encode()))
        if page < total_pages - 1:
            nav_buttons.append(Button.inline("➡️", f"users_list_{page + 1}".encode()))
        buttons = []
        if nav_buttons:
            buttons.append(nav_buttons)
        buttons.append([Button.inline("🔄 Yenile", f"users_list_{page}".encode())])
        buttons.append(back_button("settings_menu"))
        await event.edit(text, buttons=buttons, link_preview=False)
    

    @bot.on(events.NewMessage(pattern=r'^/info\s+(\d+)$'))
    async def info_command(event):
        if event.sender_id != config.OWNER_ID:
            return
        user_id = int(event.pattern_match.group(1))
        user_data = await db.get_user(user_id)
        if not user_data:
            await event.respond(f"❌ `{user_id}` bulunamadı.")
            return
        try:
            tg_user = await bot.get_entity(user_id)
            tg_username = tg_user.username
            tg_first_name = tg_user.first_name or ""
            tg_last_name = tg_user.last_name or ""
        except:
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
        await event.respond(text, buttons=buttons, link_preview=False)
    

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
        try:
            await event.edit(f"✅ `{user_id}` banlandı.", buttons=[[Button.inline("🔙 Geri", b"users_list_0")]])
        except:
            pass
    

    @bot.on(events.CallbackQuery(pattern=rb"unban_user_(\d+)"))
    async def unban_user_button(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        user_id = int(event.data.decode().split("_")[-1])
        await db.unban_user(user_id)
        await event.answer(f"✅ {user_id} banı kaldırıldı!")
        try:
            await event.edit(f"✅ `{user_id}` banı kaldırıldı.", buttons=[[Button.inline("🔙 Geri", b"users_list_0")]])
        except:
            pass
    

    @bot.on(events.CallbackQuery(pattern=rb"add_sudo_(\d+)"))
    async def add_sudo_button(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        user_id = int(event.data.decode().split("_")[-1])
        await db.add_sudo(user_id)
        await event.answer(f"✅ {user_id} sudo yapıldı!")
        try:
            await event.edit(f"✅ `{user_id}` sudo yapıldı.", buttons=[[Button.inline("🔙 Geri", b"users_list_0")]])
        except:
            pass
    

    @bot.on(events.CallbackQuery(pattern=rb"del_sudo_(\d+)"))
    async def del_sudo_button(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        user_id = int(event.data.decode().split("_")[-1])
        await db.remove_sudo(user_id)
        await event.answer(f"✅ {user_id} sudo kaldırıldı!")
        try:
            await event.edit(f"✅ `{user_id}` sudo kaldırıldı.", buttons=[[Button.inline("🔙 Geri", b"users_list_0")]])
        except:
            pass
    

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
        except:
            pass
        try:
            await event.edit(f"✅ `{user_id}` çıkış yaptırıldı.", buttons=[[Button.inline("🔙 Geri", b"users_list_0")]])
        except:
            pass
    

    @bot.on(events.NewMessage(pattern=r'^/users$'))
    async def users_command(event):
        if event.sender_id != config.OWNER_ID:
            return
        users = await db.get_all_users()
        if not users:
            await event.respond("📭 Henüz kullanıcı yok.")
            return
        total_pages = (len(users) + USERS_PER_PAGE - 1) // USERS_PER_PAGE
        page_users = users[:USERS_PER_PAGE]
        text = f"👥 **Kullanıcı Listesi** (1/{total_pages})\n\n"
        for user in page_users:
            user_id = user.get("user_id")
            username = user.get("username")
            first_name = user.get("first_name", "")
            is_logged_in = user.get("is_logged_in", False)
            is_banned = user.get("is_banned", False)
            status = "🚫" if is_banned else ("🟢" if is_logged_in else "⚪")
            user_link = f"[@{username}](tg://user?id={user_id})" if username else f"[{first_name or user_id}](tg://user?id={user_id})"
            text += f"{status} `{user_id}` - {user_link}\n"
        text += f"\n💡 Detay: `/info <id>`"
        buttons = []
        if total_pages > 1:
            buttons.append([Button.inline("➡️", b"users_list_1")])
        await event.respond(text, buttons=buttons if buttons else None, link_preview=False)
    

    @bot.on(events.CallbackQuery(data=b"ban_management"))
    async def ban_management_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        banned = await db.get_banned_users()
        text = "🚫 **Ban Yönetimi**\n\n"
        if banned:
            for user in banned[:10]:
                text += f"• `{user.get('user_id')}` - {user.get('ban_reason', 'Yok')}\n"
        else:
            text += "✅ Banlı kullanıcı yok."
        text += "\n\n• `/ban <id> [sebep]`\n• `/unban <id>`"
        await event.edit(text, buttons=[back_button("settings_menu")])
    

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
    

    @bot.on(events.CallbackQuery(data=b"sudo_management"))
    async def sudo_management_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        sudos = await db.get_sudos()
        text = "👑 **Sudo Yönetimi**\n\n"
        if sudos:
            for user in sudos:
                text += f"• `{user.get('user_id')}` - @{user.get('username', 'Yok')}\n"
        else:
            text += "Henüz sudo yok."
        text += "\n\n• `/addsudo <id>`\n• `/delsudo <id>`"
        await event.edit(text, buttons=[back_button("settings_menu")])
    

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
