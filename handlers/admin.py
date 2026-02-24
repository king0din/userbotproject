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

start_time = time.time()
USERS_PER_PAGE = 10

def get_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024
    return f"{bytes:.1f} PB"

async def get_system_stats():
    stats = {}
    stats['cpu_percent'] = psutil.cpu_percent(interval=0.5)
    stats['cpu_count'] = psutil.cpu_count()
    memory = psutil.virtual_memory()
    stats['ram_total'] = get_size(memory.total)
    stats['ram_used'] = get_size(memory.used)
    stats['ram_percent'] = memory.percent
    disk = psutil.disk_usage('/')
    stats['disk_total'] = get_size(disk.total)
    stats['disk_used'] = get_size(disk.used)
    stats['disk_percent'] = disk.percent
    try:
        import socket
        start = time.time()
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        stats['ping'] = round((time.time() - start) * 1000, 1)
    except:
        stats['ping'] = -1
    net = psutil.net_io_counters()
    stats['net_sent'] = get_size(net.bytes_sent)
    stats['net_recv'] = get_size(net.bytes_recv)
    return stats

def register_admin_handlers(bot):
    
    async def get_settings_text():
        settings = await db.get_settings()
        stats = await db.get_stats()
        mode = settings.get("bot_mode", "public")
        maint = settings.get("maintenance", False)
        mode_text = "🌐 Genel" if mode == "public" else "🔒 Özel"
        maint_text = "🔧 Açık" if maint else "✅ Kapalı"
        text = "⚙️ **Bot Ayarları**\n\n"
        text += f"📍 **Mod:** {mode_text}\n"
        text += f"🔧 **Bakım:** {maint_text}\n\n"
        text += f"👥 **Kullanıcı:** `{stats.get('total_users', 0)}`\n"
        text += f"✅ **Aktif Userbot:** `{stats.get('logged_in_users', 0)}`\n"
        text += f"🔌 **Plugin:** `{stats.get('total_plugins', 0)}`\n"
        text += f"👑 **Sudo:** `{stats.get('sudo_users', 0)}`\n"
        text += f"🚫 **Ban:** `{stats.get('banned_users', 0)}`"
        return text, settings
    
    def get_settings_buttons_api(settings, is_owner):
        """Bot API için renkli butonlar"""
        mode = settings.get("bot_mode", "public")
        maint = settings.get("maintenance", False)
        
        if is_owner:
            rows = [
                # Mod ve Bakım toggle butonları
                [
                    btn.callback("🔒 Özel Yap" if mode == "public" else "🌐 Genel Yap", "toggle_mode",
                                style=ButtonBuilder.STYLE_PRIMARY if mode == "public" else ButtonBuilder.STYLE_SUCCESS),
                    btn.callback("✅ Bakım Kapat" if maint else "🔧 Bakım Aç", "toggle_maintenance",
                                style=ButtonBuilder.STYLE_SUCCESS if maint else ButtonBuilder.STYLE_DANGER)
                ],
                # Kullanıcılar ve Pluginler
                [
                    btn.callback("👥 Kullanıcılar", "users_list_0", style=ButtonBuilder.STYLE_PRIMARY),
                    btn.callback("🔌 Plugin'ler", "admin_plugins", style=ButtonBuilder.STYLE_PRIMARY)
                ],
                # Sudo ve Ban
                [
                    btn.callback("👑 Sudo", "sudo_management", style=ButtonBuilder.STYLE_SUCCESS),
                    btn.callback("🚫 Ban", "ban_management", style=ButtonBuilder.STYLE_DANGER)
                ],
                # İstatistik ve Loglar
                [
                    btn.callback("📊 İstatistik", "stats", style=ButtonBuilder.STYLE_PRIMARY),
                    btn.callback("📋 Loglar", "view_logs", style=ButtonBuilder.STYLE_PRIMARY)
                ],
                # Güncelle ve Restart
                [
                    btn.callback("🔄 Güncelle", "update_bot", style=ButtonBuilder.STYLE_SUCCESS),
                    btn.callback("🔃 Restart", "restart_bot", style=ButtonBuilder.STYLE_DANGER)
                ],
                # Komutlar
                [btn.callback("📝 Komutlar", "admin_commands", style=ButtonBuilder.STYLE_PRIMARY)],
                # Geri
                [btn.callback("◀️ Ana Menü", "main_menu", icon_custom_emoji_id=5237707207794498594)]
            ]
        else:
            rows = [
                [btn.callback("🔌 Plugin'ler", "admin_plugins", style=ButtonBuilder.STYLE_PRIMARY)],
                [btn.callback("📊 İstatistik", "stats", style=ButtonBuilder.STYLE_PRIMARY)],
                [btn.callback("◀️ Ana Menü", "main_menu", icon_custom_emoji_id=5237707207794498594)]
            ]
        return rows
    
    async def get_settings_buttons(settings, is_owner):
        """Telethon için eski butonlar (fallback)"""
        mode = settings.get("bot_mode", "public")
        maint = settings.get("maintenance", False)
        if is_owner:
            buttons = [
                [Button.inline("🔒 Özel Yap" if mode == "public" else "🌐 Genel Yap", b"toggle_mode"),
                 Button.inline("✅ Bakım Kapat" if maint else "🔧 Bakım Aç", b"toggle_maintenance")],
                [Button.inline("👥 Kullanıcılar", b"users_list_0"), Button.inline("🔌 Plugin'ler", b"admin_plugins")],
                [Button.inline("👑 Sudo", b"sudo_management"), Button.inline("🚫 Ban", b"ban_management")],
                [Button.inline("📊 İstatistik", b"stats"), Button.inline("📋 Loglar", b"view_logs")],
                [Button.inline("🔄 Güncelle", b"update_bot"), Button.inline("🔃 Restart", b"restart_bot")],
                [Button.inline("📝 Komutlar", b"admin_commands")],
                back_button("main_menu")
            ]
        else:
            buttons = [[Button.inline("🔌 Plugin'ler", b"admin_plugins")], [Button.inline("📊 İstatistik", b"stats")], back_button("main_menu")]
        return buttons
    
    @bot.on(events.CallbackQuery(data=b"settings_menu"))
    async def settings_menu_handler(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        text, settings = await get_settings_text()
        rows = get_settings_buttons_api(settings, event.sender_id == config.OWNER_ID)
        
        await bot_api.edit_message_text(
            chat_id=event.sender_id,
            message_id=event.message_id,
            text=text,
            reply_markup=btn.inline_keyboard(rows)
        )
        await event.answer()
    
    @bot.on(events.CallbackQuery(data=b"toggle_mode"))
    async def toggle_mode_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        settings = await db.get_settings()
        new_mode = "private" if settings.get("bot_mode") == "public" else "public"
        await db.update_settings({"bot_mode": new_mode})
        text, settings = await get_settings_text()
        rows = get_settings_buttons_api(settings, True)
        
        await bot_api.edit_message_text(
            chat_id=event.sender_id,
            message_id=event.message_id,
            text=text,
            reply_markup=btn.inline_keyboard(rows)
        )
        await event.answer(f"✅ Mod: {'Özel' if new_mode == 'private' else 'Genel'}")
    
    @bot.on(events.CallbackQuery(data=b"toggle_maintenance"))
    async def toggle_maintenance_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        settings = await db.get_settings()
        new_state = not settings.get("maintenance", False)
        await db.update_settings({"maintenance": new_state})
        text, settings = await get_settings_text()
        rows = get_settings_buttons_api(settings, True)
        
        await bot_api.edit_message_text(
            chat_id=event.sender_id,
            message_id=event.message_id,
            text=text,
            reply_markup=btn.inline_keyboard(rows)
        )
        await event.answer(f"✅ Bakım: {'Açık' if new_state else 'Kapalı'}")
    
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
    
    @bot.on(events.CallbackQuery(data=b"admin_plugins"))
    async def admin_plugins_handler(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        all_plugins = await db.get_all_plugins()
        if not all_plugins:
            text = "📭 **Henüz plugin eklenmemiş.**"
        else:
            text = "🔌 **Yüklü Plugin'ler:**\n\n"
            for p in all_plugins:
                status = "✅" if p.get("is_active", True) else "❌"
                access = "🌐" if p.get("is_public", True) else "🔒"
                disabled = "⛔" if p.get("is_disabled", False) else ""
                text += f"{status} {access}{disabled} `{p['name']}` ({len(p.get('commands', []))} cmd)\n"
            text += f"\n**Toplam:** {len(all_plugins)}"
        text += "\n\n• `/addplugin` - Ekle\n• `/delplugin <isim>` - Sil\n• `/psettings` - Ayarlar"
        
        buttons = [
            [Button.inline("⚙️ Plugin Ayarları", b"psettings_page_0")],
            [Button.inline("🔄 Yenile", b"admin_plugins")],
            back_button("settings_menu")
        ]
        await event.edit(text, buttons=buttons)
    
    @bot.on(events.CallbackQuery(data=b"admin_panel"))
    async def admin_panel_callback(event):
        """Admin paneline geri dön - settings_menu'ya yönlendir"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        
        # settings_menu ile aynı içeriği göster
        text, settings = await get_settings_text()
        rows = get_settings_buttons_api(settings, event.sender_id == config.OWNER_ID)
        
        await bot_api.edit_message_text(
            chat_id=event.sender_id,
            message_id=event.message_id,
            text=text,
            reply_markup=btn.inline_keyboard(rows)
        )
        await event.answer()
    
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
    
    @bot.on(events.NewMessage(pattern=r'^/addplugin$'))
    async def addplugin_command(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        reply = await event.get_reply_message()
        if not reply or not reply.file or not reply.file.name.endswith('.py'):
            await event.respond("⚠️ Bir `.py` dosyasına yanıt verin.")
            return
        
        # Orijinal dosya adını al
        original_filename = reply.file.name
        
        # Geçici olarak indir
        temp_path = await reply.download_media(file=os.path.join(config.PLUGINS_DIR, f"temp_{original_filename}"))
        info = plugin_manager.extract_plugin_info(temp_path)
        
        # Plugin adını dosya adından al (uzantısız)
        plugin_name = original_filename.replace('.py', '')
        info['name'] = plugin_name
        
        # Aynı isimde plugin var mı kontrol et
        existing_plugin = await db.get_plugin(plugin_name)
        
        if existing_plugin:
            # Plugin zaten var - güncelleme seçenekleri sun
            if not hasattr(bot, 'pending_updates'):
                bot.pending_updates = {}
            bot.pending_updates[plugin_name] = {
                'temp_path': temp_path,
                'info': info,
                'existing': existing_plugin,
                'filename': original_filename
            }
            
            old_cmds = ", ".join([f"`.{c}`" for c in existing_plugin.get("commands", [])[:5]])
            new_cmds = ", ".join([f"`.{c}`" for c in info.get("commands", [])[:5]])
            
            await event.respond(
                f"⚠️ **`{plugin_name}` zaten mevcut!**\n\n"
                f"📦 **Mevcut:**\n"
                f"   └ {old_cmds or 'Komut yok'}\n\n"
                f"📦 **Yeni:**\n"
                f"   └ {new_cmds or 'Komut yok'}\n\n"
                f"Ne yapmak istiyorsunuz?",
                buttons=[
                    [Button.inline("🔄 Güncelle", f"update_plugin_{plugin_name}".encode())],
                    [Button.inline("🔄 Güncelle + 🔃 Restart", f"update_restart_{plugin_name}".encode())],
                    [Button.inline("❌ İptal", f"cancel_update_{plugin_name}".encode())]
                ]
            )
            return
        
        # Yeni plugin - komut çakışması kontrolü (başka pluginlerle)
        for cmd in info["commands"]:
            existing = await db.check_command_exists(cmd)
            if existing and existing != plugin_name:
                os.remove(temp_path)
                await event.respond(f"❌ `.{cmd}` komutu `{existing}` plugininde mevcut!")
                return
        
        # Dosyayı doğru isimle taşı
        final_path = os.path.join(config.PLUGINS_DIR, original_filename)
        if os.path.exists(final_path):
            os.remove(final_path)
        os.rename(temp_path, final_path)
        
        if not hasattr(bot, 'pending_plugins'):
            bot.pending_plugins = {}
        bot.pending_plugins[plugin_name] = {
            'path': final_path,
            'info': info,
            'filename': original_filename
        }
        
        await event.respond(
            f"🔌 **Yeni Plugin: `{plugin_name}`**\n\n"
            f"📝 {info['description'] or 'Açıklama yok'}\n"
            f"🔧 {', '.join([f'`.{c}`' for c in info['commands']]) or 'Komut yok'}\n\n"
            f"Nasıl eklensin?",
            buttons=[
                [Button.inline("🌐 Genel", f"confirm_plugin_public_{plugin_name}".encode()),
                 Button.inline("🔒 Özel", f"confirm_plugin_private_{plugin_name}".encode())],
                [Button.inline("❌ İptal", f"cancel_newplugin_{plugin_name}".encode())]
            ]
        )
    
    @bot.on(events.CallbackQuery(pattern=rb"update_plugin_(.+)"))
    async def update_plugin_handler(event):
        """Plugini güncelle (restart yok)"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        plugin_name = event.data.decode().split("_", 2)[-1]
        
        if not hasattr(bot, 'pending_updates') or plugin_name not in bot.pending_updates:
            await event.answer("Güncelleme bilgisi bulunamadı", alert=True)
            return
        
        update_data = bot.pending_updates[plugin_name]
        temp_path = update_data['temp_path']
        existing = update_data['existing']
        
        await event.edit("⏳ **Plugin güncelleniyor...**")
        
        try:
            # Eski dosyayı sil
            old_path = os.path.join(config.PLUGINS_DIR, existing.get("filename", f"{plugin_name}.py"))
            if os.path.exists(old_path):
                os.remove(old_path)
            
            # Yeni dosyayı taşı
            new_path = os.path.join(config.PLUGINS_DIR, f"{plugin_name}.py")
            os.rename(temp_path, new_path)
            
            # DB güncelle
            await db.update_plugin(plugin_name, {
                "filename": f"{plugin_name}.py",
                "commands": update_data['info'].get("commands", []),
                "description": update_data['info'].get("description", "")
            })
            
            del bot.pending_updates[plugin_name]
            
            await event.edit(
                f"✅ **`{plugin_name}` güncellendi!**\n\n"
                f"⚠️ Aktif kullanıcıların plugini yeniden yüklemesi gerekiyor.\n"
                f"💡 Tüm kullanıcılar için aktif etmek isterseniz botu yeniden başlatın."
            )
            await send_log(bot, "plugin", f"Güncellendi: {plugin_name}", event.sender_id)
            
        except Exception as e:
            await event.edit(f"❌ Hata: `{e}`")
    
    @bot.on(events.CallbackQuery(pattern=rb"update_restart_(.+)"))
    async def update_restart_handler(event):
        """Plugini güncelle ve botu yeniden başlat"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        plugin_name = event.data.decode().split("_", 2)[-1]
        
        if not hasattr(bot, 'pending_updates') or plugin_name not in bot.pending_updates:
            await event.answer("Güncelleme bilgisi bulunamadı", alert=True)
            return
        
        update_data = bot.pending_updates[plugin_name]
        temp_path = update_data['temp_path']
        existing = update_data['existing']
        
        await event.edit("⏳ **Plugin güncelleniyor...**")
        
        try:
            # Eski dosyayı sil
            old_path = os.path.join(config.PLUGINS_DIR, existing.get("filename", f"{plugin_name}.py"))
            if os.path.exists(old_path):
                os.remove(old_path)
            
            # Yeni dosyayı taşı
            new_path = os.path.join(config.PLUGINS_DIR, f"{plugin_name}.py")
            os.rename(temp_path, new_path)
            
            # DB güncelle
            await db.update_plugin(plugin_name, {
                "filename": f"{plugin_name}.py",
                "commands": update_data['info'].get("commands", []),
                "description": update_data['info'].get("description", "")
            })
            
            del bot.pending_updates[plugin_name]
            
            await event.edit(f"✅ **`{plugin_name}` güncellendi!**\n\n🔃 Yeniden başlatılıyor...")
            await send_log(bot, "plugin", f"Güncellendi + Restart: {plugin_name}", event.sender_id)
            
            # Restart
            with open(".restart_info", "w") as f:
                f.write(f"{event.chat_id}|{event.message_id}")
            
            await asyncio.sleep(1)
            os.execv(sys.executable, [sys.executable] + sys.argv)
            
        except Exception as e:
            await event.edit(f"❌ Hata: `{e}`")
    
    @bot.on(events.CallbackQuery(pattern=rb"cancel_update_(.+)"))
    async def cancel_update_handler(event):
        """Plugin güncellemeyi iptal et"""
        plugin_name = event.data.decode().split("_", 2)[-1]
        
        if hasattr(bot, 'pending_updates') and plugin_name in bot.pending_updates:
            temp_path = bot.pending_updates[plugin_name].get('temp_path')
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            del bot.pending_updates[plugin_name]
        
        await event.edit("❌ Güncelleme iptal edildi.")
    
    @bot.on(events.CallbackQuery(pattern=rb"confirm_plugin_(public|private)_(.+)"))
    async def confirm_plugin_handler(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        data = event.data.decode()
        is_public = "public" in data
        plugin_name = data.split("_", 3)[-1]
        if not hasattr(bot, 'pending_plugins') or plugin_name not in bot.pending_plugins:
            await event.answer("Plugin bulunamadı", alert=True)
            return
        
        pending = bot.pending_plugins[plugin_name]
        
        # Yeni format (dict) veya eski format (string path)
        if isinstance(pending, dict):
            path = pending['path']
            info = pending['info']
            filename = pending['filename']
        else:
            path = pending
            info = plugin_manager.extract_plugin_info(path)
            filename = f"{plugin_name}.py"
        
        success, message = await plugin_manager.register_plugin(path, is_public=is_public)
        
        if success:
            # DB'deki bilgileri düzelt
            await db.update_plugin(plugin_name, {
                "filename": filename,
                "commands": info.get("commands", []),
                "description": info.get("description", "")
            })
        
        del bot.pending_plugins[plugin_name]
        await event.edit(message)
    
    @bot.on(events.CallbackQuery(pattern=rb"cancel_newplugin_(.+)"))
    async def cancel_newplugin_handler(event):
        """Yeni plugin eklemeyi iptal et"""
        plugin_name = event.data.decode().split("_", 2)[-1]
        
        if hasattr(bot, 'pending_plugins') and plugin_name in bot.pending_plugins:
            pending = bot.pending_plugins[plugin_name]
            if isinstance(pending, dict):
                path = pending.get('path')
            else:
                path = pending
            if path and os.path.exists(path):
                os.remove(path)
            del bot.pending_plugins[plugin_name]
        
        await event.edit("❌ İptal edildi.")
    
    @bot.on(events.CallbackQuery(data=b"cancel_plugin"))
    async def cancel_plugin_handler(event):
        if hasattr(bot, 'pending_plugins'):
            for pending in bot.pending_plugins.values():
                if isinstance(pending, dict):
                    path = pending.get('path')
                else:
                    path = pending
                if path and os.path.exists(path):
                    os.remove(path)
            bot.pending_plugins.clear()
        await event.edit("❌ İptal edildi.")
    
    @bot.on(events.NewMessage(pattern=r'^/delplugin\s+(\S+)$'))
    async def delplugin_command(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        plugin_name = event.pattern_match.group(1)
        success, message = await plugin_manager.unregister_plugin(plugin_name)
        await event.respond(message)
    
    @bot.on(events.NewMessage(pattern=r'^/getplugin\s+(\S+)$'))
    async def getplugin_command(event):
        """Plugin dosyasını gönder"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        plugin_name = event.pattern_match.group(1)
        plugin = await db.get_plugin(plugin_name)
        
        if not plugin:
            await event.respond(f"❌ `{plugin_name}` bulunamadı.")
            return
        
        file_path = os.path.join(config.PLUGINS_DIR, plugin.get("filename", f"{plugin_name}.py"))
        
        if not os.path.exists(file_path):
            await event.respond(f"❌ Plugin dosyası bulunamadı: `{plugin.get('filename')}`")
            return
        
        # Kısa caption (Telegram limiti 1024 karakter)
        cmds = plugin.get("commands", [])[:5]
        cmd_text = ", ".join([f".{c}" for c in cmds])
        if len(plugin.get("commands", [])) > 5:
            cmd_text += "..."
        
        caption = f"🔌 {plugin_name}\n"
        caption += f"🔧 {cmd_text}" if cmd_text else ""
        
        await bot.send_file(
            event.chat_id,
            file_path,
            caption=caption,
            force_document=True
        )
    
    @bot.on(events.NewMessage(pattern=r'^/setpublic\s+(\S+)$'))
    async def setpublic_command(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        await db.update_plugin(event.pattern_match.group(1), {"is_public": True})
        await event.respond(f"✅ `{event.pattern_match.group(1)}` genel yapıldı.")
    
    @bot.on(events.NewMessage(pattern=r'^/setprivate\s+(\S+)$'))
    async def setprivate_command(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        await db.update_plugin(event.pattern_match.group(1), {"is_public": False})
        await event.respond(f"✅ `{event.pattern_match.group(1)}` özel yapıldı.")
    
    @bot.on(events.CallbackQuery(data=b"stats"))
    async def stats_handler(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        await event.edit("⏳ **Yükleniyor...**")
        db_stats = await db.get_stats()
        sys_stats = await get_system_stats()
        uptime = get_readable_time(time.time() - start_time)
        text = "📊 **Bot İstatistikleri**\n\n"
        text += f"👥 **Kullanıcı:** `{db_stats.get('total_users', 0)}` (Aktif: `{db_stats.get('logged_in_users', 0)}`)\n"
        text += f"🔌 **Plugin:** `{db_stats.get('total_plugins', 0)}`\n"
        text += f"👑 **Sudo:** `{db_stats.get('sudo_users', 0)}` | 🚫 **Ban:** `{db_stats.get('banned_users', 0)}`\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n🖥️ **Sistem:**\n\n"
        text += f"💻 **CPU:** `{sys_stats['cpu_percent']}%` ({sys_stats['cpu_count']} core)\n"
        text += f"🧠 **RAM:** `{sys_stats['ram_used']}` / `{sys_stats['ram_total']}` ({sys_stats['ram_percent']}%)\n"
        text += f"💾 **Disk:** `{sys_stats['disk_used']}` / `{sys_stats['disk_total']}` ({sys_stats['disk_percent']}%)\n"
        text += f"📶 **Ping:** `{sys_stats['ping']} ms`\n" if sys_stats['ping'] > 0 else "📶 **Ping:** `N/A`\n"
        text += f"📤 **Gönderilen:** `{sys_stats['net_sent']}`\n"
        text += f"📥 **Alınan:** `{sys_stats['net_recv']}`\n\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n⏱️ **Uptime:** `{uptime}`\n🔢 **Sürüm:** `v{config.__version__}`"
        await event.edit(text, buttons=[
            [Button.inline("🚀 Hız Testi", b"speedtest")],
            [Button.inline("🔄 Yenile", b"stats")],
            back_button("settings_menu")
        ])
    
    @bot.on(events.NewMessage(pattern=r'^/stats$'))
    async def stats_command(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        msg = await event.respond("⏳ **Yükleniyor...**")
        db_stats = await db.get_stats()
        sys_stats = await get_system_stats()
        uptime = get_readable_time(time.time() - start_time)
        text = "📊 **İstatistikler**\n\n"
        text += f"👥 Kullanıcı: `{db_stats.get('total_users', 0)}` (Aktif: `{db_stats.get('logged_in_users', 0)}`)\n"
        text += f"🔌 Plugin: `{db_stats.get('total_plugins', 0)}`\n\n"
        text += f"💻 CPU: `{sys_stats['cpu_percent']}%` | 🧠 RAM: `{sys_stats['ram_percent']}%`\n"
        text += f"💾 Disk: `{sys_stats['disk_percent']}%` | 📶 Ping: `{sys_stats['ping']} ms`\n\n"
        text += f"⏱️ Uptime: `{uptime}`"
        await msg.edit(text)
    
    @bot.on(events.NewMessage(pattern=r'^/speedtest$'))
    async def speedtest_command(event):
        """İnternet hız testi"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        msg = await event.respond(
            "🚀 **İnternet Hız Testi**\n\n"
            "⏳ Test başlatılıyor...\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        
        try:
            import speedtest
        except ImportError:
            await msg.edit(
                "❌ **speedtest-cli yüklü değil!**\n\n"
                "Yüklemek için: `pip install speedtest-cli`"
            )
            return
        
        import concurrent.futures
        
        def run_speedtest():
            """Senkron speedtest çalıştır"""
            st = speedtest.Speedtest()
            st.get_best_server()
            server = st.best
            download = st.download() / 1_000_000
            upload = st.upload() / 1_000_000
            return {
                'server': server,
                'download': download,
                'upload': upload,
                'ping': server['latency']
            }
        
        try:
            await msg.edit(
                "🚀 **İnternet Hız Testi**\n\n"
                "🔍 En iyi sunucu aranıyor...\n"
                "⬇️ İndirme test ediliyor...\n"
                "⬆️ Yükleme test ediliyor...\n\n"
                "⏳ Bu işlem 20-40 saniye sürebilir...\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )
            
            # Thread'de çalıştır
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = await loop.run_in_executor(pool, run_speedtest)
            
            server = result['server']
            download = result['download']
            upload = result['upload']
            ping = result['ping']
            
            # Hız değerlendirmesi
            if download >= 100:
                download_emoji = "🚀"
                download_rating = "Mükemmel"
            elif download >= 50:
                download_emoji = "⚡"
                download_rating = "Çok İyi"
            elif download >= 25:
                download_emoji = "✅"
                download_rating = "İyi"
            elif download >= 10:
                download_emoji = "📶"
                download_rating = "Orta"
            else:
                download_emoji = "🐌"
                download_rating = "Yavaş"
            
            if upload >= 50:
                upload_emoji = "🚀"
                upload_rating = "Mükemmel"
            elif upload >= 25:
                upload_emoji = "⚡"
                upload_rating = "Çok İyi"
            elif upload >= 10:
                upload_emoji = "✅"
                upload_rating = "İyi"
            elif upload >= 5:
                upload_emoji = "📶"
                upload_rating = "Orta"
            else:
                upload_emoji = "🐌"
                upload_rating = "Yavaş"
            
            # Ping değerlendirmesi
            if ping <= 20:
                ping_emoji = "🟢"
                ping_rating = "Mükemmel"
            elif ping <= 50:
                ping_emoji = "🟡"
                ping_rating = "İyi"
            elif ping <= 100:
                ping_emoji = "🟠"
                ping_rating = "Orta"
            else:
                ping_emoji = "🔴"
                ping_rating = "Yüksek"
            
            result_text = (
                "🚀 **İnternet Hız Testi - Sonuç**\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🌐 **Sunucu:** `{server['sponsor']}`\n"
                f"📍 **Konum:** `{server['name']}, {server['country']}`\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{ping_emoji} **Ping:** `{ping:.1f} ms` ({ping_rating})\n\n"
                f"{download_emoji} **İndirme:** `{download:.2f} Mbps`\n"
                f"   └ {download_rating}\n\n"
                f"{upload_emoji} **Yükleme:** `{upload:.2f} Mbps`\n"
                f"   └ {upload_rating}\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ 100%"
            )
            
            await msg.edit(result_text)
            
        except Exception as e:
            await msg.edit(f"❌ **Hata:** `{str(e)}`")
    
    @bot.on(events.CallbackQuery(data=b"speedtest"))
    async def speedtest_callback(event):
        """Callback ile hız testi"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        
        await event.answer("🚀 Hız testi başlatılıyor...")
        
        try:
            import speedtest
        except ImportError:
            await event.edit(
                "❌ **speedtest-cli yüklü değil!**\n\n"
                "Yüklemek için: `pip install speedtest-cli`",
                buttons=[back_button("stats")]
            )
            return
        
        import concurrent.futures
        
        def run_speedtest():
            """Senkron speedtest çalıştır"""
            st = speedtest.Speedtest()
            st.get_best_server()
            server = st.best
            download = st.download() / 1_000_000
            upload = st.upload() / 1_000_000
            return {
                'server': server,
                'download': download,
                'upload': upload,
                'ping': server['latency']
            }
        
        try:
            await event.edit(
                "🚀 **İnternet Hız Testi**\n\n"
                "🔍 Sunucu aranıyor...\n"
                "⬇️ İndirme test ediliyor...\n"
                "⬆️ Yükleme test ediliyor...\n\n"
                "⏳ 20-40 saniye sürebilir...\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )
            
            # Thread'de çalıştır
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = await loop.run_in_executor(pool, run_speedtest)
            
            server = result['server']
            download = result['download']
            upload = result['upload']
            ping = result['ping']
            
            # Emoji seç
            dl_emoji = "🚀" if download >= 100 else "⚡" if download >= 50 else "✅" if download >= 25 else "📶" if download >= 10 else "🐌"
            ul_emoji = "🚀" if upload >= 50 else "⚡" if upload >= 25 else "✅" if upload >= 10 else "📶" if upload >= 5 else "🐌"
            ping_emoji = "🟢" if ping <= 20 else "🟡" if ping <= 50 else "🟠" if ping <= 100 else "🔴"
            
            await event.edit(
                "🚀 **Hız Testi Sonucu**\n\n"
                f"🌐 `{server['sponsor']}`\n"
                f"📍 `{server['name']}, {server['country']}`\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"{ping_emoji} **Ping:** `{ping:.1f} ms`\n"
                f"{dl_emoji} **İndirme:** `{download:.2f} Mbps`\n"
                f"{ul_emoji} **Yükleme:** `{upload:.2f} Mbps`\n"
                "━━━━━━━━━━━━━━━━━━━━",
                buttons=[
                    [Button.inline("🔄 Tekrar Test", b"speedtest")],
                    back_button("stats")
                ]
            )
            
        except Exception as e:
            await event.edit(
                f"❌ **Hata:** `{str(e)}`",
                buttons=[back_button("stats")]
            )
    
    @bot.on(events.CallbackQuery(data=b"update_bot"))
    async def update_bot_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        await event.edit("🔄 **Kontrol ediliyor...**")
        try:
            import git
            if not os.path.exists(".git"):
                await event.edit("❌ Git repository değil!", buttons=[back_button("settings_menu")])
                return
            repo = git.Repo(".")
            origin = repo.remotes.origin
            origin.fetch()
            current_branch = repo.active_branch.name
            commits = list(repo.iter_commits(f'{current_branch}..origin/{current_branch}'))
            if not commits:
                await event.edit(f"✅ **Güncel!** v{config.__version__}", buttons=[back_button("settings_menu")])
                return
            await event.edit(f"⬇️ **{len(commits)} güncelleme indiriliyor...**")
            origin.pull(current_branch)
            if os.path.exists("requirements.txt"):
                await event.edit("📦 **Bağımlılıklar kuruluyor...**")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"])
            await event.edit("✅ **Güncellendi!** Yeniden başlatılıyor...")
            with open(".restart_info", "w") as f:
                f.write(f"{event.chat_id}|{event.message_id}")
            await asyncio.sleep(1)
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            await event.edit(f"❌ Hata: `{e}`", buttons=[back_button("settings_menu")])
    
    @bot.on(events.CallbackQuery(data=b"restart_bot"))
    async def restart_bot_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        await event.edit("🔃 **Yeniden başlatılıyor...**")
        with open(".restart_info", "w") as f:
            f.write(f"{event.chat_id}|{event.message_id}")
        await asyncio.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    
    @bot.on(events.CallbackQuery(data=b"view_logs"))
    async def view_logs_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        logs = await db.get_logs(limit=15)
        text = "📋 **Son Loglar:**\n\n"
        if logs:
            for log in logs:
                text += f"• [{log.get('type', '?')}] {log.get('message', '')[:30]}\n"
        else:
            text += "Henüz log yok."
        await event.edit(text, buttons=[back_button("settings_menu")])
    
    @bot.on(events.CallbackQuery(data=b"admin_commands"))
    async def admin_commands_handler(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        text = "📝 **Admin Komutları**\n\n"
        text += "**👥 Kullanıcı:**\n• `/users` - Liste\n• `/info <id>` - Detay\n\n"
        text += "**🔌 Plugin:**\n• `/addplugin` - Ekle\n• `/delplugin <isim>` - Sil\n• `/getplugin <isim>` - İndir\n• `/setpublic <isim>`\n• `/setprivate <isim>`\n\n"
        text += "**🚫 Ban:** `/ban <id>` `/unban <id>`\n"
        text += "**👑 Sudo:** `/addsudo <id>` `/delsudo <id>`\n\n"
        text += "**📢 Diğer:** `/broadcast` `/stats`"
        await event.edit(text, buttons=[back_button("settings_menu")])
    
    @bot.on(events.NewMessage(pattern=r'^/broadcast$'))
    async def broadcast_command(event):
        if event.sender_id != config.OWNER_ID:
            return
        reply = await event.get_reply_message()
        if not reply:
            await event.respond("⚠️ Mesaja yanıt verin.")
            return
        users = await db.get_all_users()
        msg = await event.respond(f"📢 Gönderiliyor... (0/{len(users)})")
        sent, failed = 0, 0
        for user in users:
            try:
                await bot.send_message(user["user_id"], reply.text)
                sent += 1
            except:
                failed += 1
        await msg.edit(f"✅ **Tamamlandı!**\n📤 Gönderildi: `{sent}`\n❌ Başarısız: `{failed}`")
    
    # ==========================================
    # POST OLUŞTURMA SİSTEMİ
    # ==========================================
    
    # Post state yönetimi
    post_states = {}
    
    @bot.on(events.NewMessage(pattern=r'^/post$'))
    async def post_command(event):
        """Plugin kanalına post oluştur"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        post_states[event.sender_id] = {
            'stage': 'waiting_content',
            'content': None,
            'media': None,
            'buttons': [],
            'current_row': []
        }
        
        await event.respond(
            "📝 **Post Oluşturma**\n\n"
            "Göndermek istediğiniz postu yazın veya medya gönderin.\n"
            "Başka bir mesajı iletmek için mesajı **forward** edin.\n\n"
            "⚠️ İptal: /cancelpost",
            buttons=[[Button.inline("❌ İptal", b"cancel_post")]]
        )
    
    @bot.on(events.NewMessage(pattern=r'^/cancelpost$'))
    async def cancelpost_command(event):
        if event.sender_id in post_states:
            del post_states[event.sender_id]
        await event.respond("❌ Post oluşturma iptal edildi.")
    
    @bot.on(events.NewMessage(func=lambda e: e.is_private and e.sender_id in post_states and not e.text.startswith('/')))
    async def post_content_handler(event):
        """Post içeriğini al"""
        user_id = event.sender_id
        state = post_states.get(user_id)
        
        if not state:
            return
        
        stage = state.get('stage')
        
        if stage == 'waiting_content':
            # Orijinal mesajı tamamen kaydet
            state['content'] = event.message
            state['stage'] = 'adding_buttons'
            
            await event.respond(
                "✅ **İçerik alındı!**\n\n"
                "Şimdi buton ekleyebilirsiniz:",
                buttons=[
                    [Button.inline("🔗 Link Butonu", b"post_add_link")],
                    [Button.inline("👍 Tepki Butonu", b"post_add_reaction")],
                    [Button.inline("➡️ Aynı Satıra Ekle", b"post_same_row"),
                     Button.inline("⬇️ Alt Satıra Geç", b"post_new_row")],
                    [Button.inline("👁️ Önizleme", b"post_preview")],
                    [Button.inline("✅ Gönder", b"post_confirm"),
                     Button.inline("❌ İptal", b"cancel_post")]
                ]
            )
        
        elif stage == 'waiting_link_text':
            state['temp_link_text'] = event.text
            state['stage'] = 'waiting_link_url'
            await event.respond("🔗 Şimdi **URL** girin:\nÖrnek: `https://t.me/KingTGPlugins`")
        
        elif stage == 'waiting_link_url':
            url = event.text.strip()
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            btn = {'type': 'url', 'text': state['temp_link_text'], 'url': url}
            
            if state.get('add_to_current_row', True) and state['current_row']:
                state['current_row'].append(btn)
            else:
                if state['current_row']:
                    state['buttons'].append(state['current_row'])
                state['current_row'] = [btn]
            
            state['stage'] = 'adding_buttons'
            await event.respond(
                f"✅ **Link butonu eklendi!**\n`{state['temp_link_text']}` → `{url}`",
                buttons=[
                    [Button.inline("🔗 Link Butonu", b"post_add_link")],
                    [Button.inline("👍 Tepki Butonu", b"post_add_reaction")],
                    [Button.inline("➡️ Aynı Satıra Ekle", b"post_same_row"),
                     Button.inline("⬇️ Alt Satıra Geç", b"post_new_row")],
                    [Button.inline("👁️ Önizleme", b"post_preview")],
                    [Button.inline("✅ Gönder", b"post_confirm"),
                     Button.inline("❌ İptal", b"cancel_post")]
                ]
            )
        
        elif stage == 'waiting_reactions':
            # Emoji'leri al
            import re
            emojis = re.findall(r'[\U0001F300-\U0001F9FF]|[\u2600-\u26FF]|[\u2700-\u27BF]|[\U0001FA00-\U0001FA6F]|[\U0001FA70-\U0001FAFF]', event.text)
            
            if not emojis:
                await event.respond("⚠️ Emoji bulunamadı. Tekrar deneyin:\nÖrnek: `👍❤️🔥`")
                return
            
            state['temp_reactions'] = emojis
            state['stage'] = 'waiting_reaction_layout'
            
            await event.respond(
                f"✅ **Tepkiler:** {' '.join(emojis)}\n\n"
                "Nasıl dizilsin?",
                buttons=[
                    [Button.inline("➡️ Yan Yana", b"reaction_horizontal")],
                    [Button.inline("⬇️ Alt Alta", b"reaction_vertical")],
                    [Button.inline("❌ İptal", b"post_back_to_buttons")]
                ]
            )
    
    @bot.on(events.CallbackQuery(data=b"post_add_link"))
    async def post_add_link_handler(event):
        user_id = event.sender_id
        if user_id not in post_states:
            await event.answer("Önce /post komutu kullanın", alert=True)
            return
        
        post_states[user_id]['stage'] = 'waiting_link_text'
        post_states[user_id]['add_to_current_row'] = False
        await event.edit("🔗 **Link Butonu Ekle**\n\nButon **metnini** girin:\nÖrnek: `📢 Kanala Katıl`")
    
    @bot.on(events.CallbackQuery(data=b"post_add_reaction"))
    async def post_add_reaction_handler(event):
        user_id = event.sender_id
        if user_id not in post_states:
            await event.answer("Önce /post komutu kullanın", alert=True)
            return
        
        post_states[user_id]['stage'] = 'waiting_reactions'
        await event.edit(
            "👍 **Tepki Butonu Ekle**\n\n"
            "Eklemek istediğiniz emojileri gönderin:\n"
            "Örnek: `👍❤️🔥😂👎`"
        )
    
    @bot.on(events.CallbackQuery(data=b"reaction_horizontal"))
    async def reaction_horizontal_handler(event):
        user_id = event.sender_id
        state = post_states.get(user_id)
        if not state:
            return
        
        # Yan yana tepki butonları
        reactions = state.get('temp_reactions', [])
        row = [{'type': 'reaction', 'emoji': e} for e in reactions]
        
        if state['current_row']:
            state['buttons'].append(state['current_row'])
        state['buttons'].append(row)
        state['current_row'] = []
        state['stage'] = 'adding_buttons'
        
        await event.edit(
            f"✅ **Tepkiler eklendi (yan yana):** {' '.join(reactions)}",
            buttons=[
                [Button.inline("🔗 Link Butonu", b"post_add_link")],
                [Button.inline("👍 Tepki Butonu", b"post_add_reaction")],
                [Button.inline("➡️ Aynı Satıra Ekle", b"post_same_row"),
                 Button.inline("⬇️ Alt Satıra Geç", b"post_new_row")],
                [Button.inline("👁️ Önizleme", b"post_preview")],
                [Button.inline("✅ Gönder", b"post_confirm"),
                 Button.inline("❌ İptal", b"cancel_post")]
            ]
        )
    
    @bot.on(events.CallbackQuery(data=b"reaction_vertical"))
    async def reaction_vertical_handler(event):
        user_id = event.sender_id
        state = post_states.get(user_id)
        if not state:
            return
        
        # Alt alta tepki butonları
        reactions = state.get('temp_reactions', [])
        
        if state['current_row']:
            state['buttons'].append(state['current_row'])
            state['current_row'] = []
        
        for e in reactions:
            state['buttons'].append([{'type': 'reaction', 'emoji': e}])
        
        state['stage'] = 'adding_buttons'
        
        await event.edit(
            f"✅ **Tepkiler eklendi (alt alta):** {' '.join(reactions)}",
            buttons=[
                [Button.inline("🔗 Link Butonu", b"post_add_link")],
                [Button.inline("👍 Tepki Butonu", b"post_add_reaction")],
                [Button.inline("➡️ Aynı Satıra Ekle", b"post_same_row"),
                 Button.inline("⬇️ Alt Satıra Geç", b"post_new_row")],
                [Button.inline("👁️ Önizleme", b"post_preview")],
                [Button.inline("✅ Gönder", b"post_confirm"),
                 Button.inline("❌ İptal", b"cancel_post")]
            ]
        )
    
    @bot.on(events.CallbackQuery(data=b"post_same_row"))
    async def post_same_row_handler(event):
        user_id = event.sender_id
        state = post_states.get(user_id)
        if not state:
            return
        
        state['add_to_current_row'] = True
        await event.answer("➡️ Sonraki buton aynı satıra eklenecek")
    
    @bot.on(events.CallbackQuery(data=b"post_new_row"))
    async def post_new_row_handler(event):
        user_id = event.sender_id
        state = post_states.get(user_id)
        if not state:
            return
        
        if state['current_row']:
            state['buttons'].append(state['current_row'])
            state['current_row'] = []
        
        state['add_to_current_row'] = False
        await event.answer("⬇️ Sonraki buton yeni satıra eklenecek")
    
    @bot.on(events.CallbackQuery(data=b"post_back_to_buttons"))
    async def post_back_to_buttons_handler(event):
        user_id = event.sender_id
        state = post_states.get(user_id)
        if not state:
            return
        
        state['stage'] = 'adding_buttons'
        await event.edit(
            "📝 **Buton Ekleme**",
            buttons=[
                [Button.inline("🔗 Link Butonu", b"post_add_link")],
                [Button.inline("👍 Tepki Butonu", b"post_add_reaction")],
                [Button.inline("➡️ Aynı Satıra Ekle", b"post_same_row"),
                 Button.inline("⬇️ Alt Satıra Geç", b"post_new_row")],
                [Button.inline("👁️ Önizleme", b"post_preview")],
                [Button.inline("✅ Gönder", b"post_confirm"),
                 Button.inline("❌ İptal", b"cancel_post")]
            ]
        )
    
    def build_post_buttons(state):
        """State'den Telethon butonları oluştur"""
        all_buttons = state['buttons'].copy()
        if state['current_row']:
            all_buttons.append(state['current_row'])
        
        telethon_buttons = []
        for row in all_buttons:
            btn_row = []
            for btn in row:
                if btn['type'] == 'url':
                    btn_row.append(Button.url(btn['text'], btn['url']))
                elif btn['type'] == 'reaction':
                    # Tepki butonları - başlangıçta 0
                    btn_row.append(Button.inline(f"{btn['emoji']} 0", f"react_{btn['emoji']}_0".encode()))
            if btn_row:
                telethon_buttons.append(btn_row)
        
        return telethon_buttons if telethon_buttons else None
    
    @bot.on(events.CallbackQuery(pattern=rb"react_(.+)_(\d+)"))
    async def reaction_handler(event):
        """Tepki butonuna tıklandığında"""
        user_id = event.sender_id
        data = event.data.decode()
        
        # Emoji'yi çıkar (react_👍_5 -> 👍)
        parts = data.split("_")
        emoji = parts[1]
        
        # Mesaj ID ve Chat ID
        msg_id = event.message_id
        chat_id = event.chat_id
        
        # Mesajı al
        try:
            message = await event.get_message()
            if not message:
                await event.answer("Mesaj bulunamadı!")
                return
        except:
            await event.answer("Hata!")
            return
        
        # Kullanıcının tepkisini veritabanından kontrol et
        reaction_key = f"reaction_{chat_id}_{msg_id}"
        user_reactions = await db.get_user_reaction(reaction_key, user_id)
        
        # Mevcut butonları al
        current_buttons = message.buttons
        if not current_buttons:
            await event.answer("Buton bulunamadı!")
            return
        
        new_buttons = []
        for row in current_buttons:
            new_row = []
            for btn in row:
                btn_data = btn.data.decode() if btn.data else ""
                btn_text = btn.text
                
                if btn_data.startswith("react_"):
                    # Bu bir tepki butonu
                    btn_parts = btn_data.split("_")
                    btn_emoji = btn_parts[1]
                    
                    # Mevcut sayıyı al
                    try:
                        current_count = int(btn_text.split()[-1])
                    except:
                        current_count = 0
                    
                    if btn_emoji == emoji:
                        # Tıklanan buton
                        if user_reactions == emoji:
                            # Aynı tepkiye tekrar tıkladı - geri al
                            new_count = max(0, current_count - 1)
                            await db.set_user_reaction(reaction_key, user_id, None)
                            await event.answer(f"{emoji} geri alındı")
                        else:
                            # Yeni tepki
                            new_count = current_count + 1
                            await db.set_user_reaction(reaction_key, user_id, emoji)
                            await event.answer(f"{emoji}")
                    else:
                        # Tıklanmayan buton
                        if user_reactions == btn_emoji:
                            # Kullanıcı bu tepkiden vazgeçti (başka tepkiye geçti)
                            new_count = max(0, current_count - 1)
                        else:
                            new_count = current_count
                    
                    new_row.append(Button.inline(f"{btn_emoji} {new_count}", f"react_{btn_emoji}_{new_count}".encode()))
                else:
                    # URL butonu - olduğu gibi bırak
                    if btn.url:
                        new_row.append(Button.url(btn_text, btn.url))
                    else:
                        new_row.append(Button.inline(btn_text, btn.data))
            
            if new_row:
                new_buttons.append(new_row)
        
        # Mesajı güncelle
        try:
            await event.edit(buttons=new_buttons)
        except Exception as e:
            # Aynı butonlarsa veya başka hata
            pass
    
    @bot.on(events.CallbackQuery(data=b"post_preview"))
    async def post_preview_handler(event):
        user_id = event.sender_id
        state = post_states.get(user_id)
        if not state or not state.get('content'):
            await event.answer("İçerik bulunamadı", alert=True)
            return
        
        await event.answer("👁️ Önizleme gönderiliyor...")
        
        buttons = build_post_buttons(state)
        content = state['content']
        
        try:
            # Mesajı butonlarla birlikte gönder
            if content.media:
                preview = await bot.send_file(
                    user_id,
                    file=content.media,
                    caption=content.message,
                    buttons=buttons,
                    formatting_entities=content.entities
                )
            else:
                preview = await bot.send_message(
                    user_id,
                    content.message,
                    buttons=buttons,
                    formatting_entities=content.entities,
                    link_preview=False
                )
            
            state['preview_id'] = preview.id
            
            await bot.send_message(
                user_id,
                "👆 **Önizleme**\n\nBu şekilde gönderilecek.",
                buttons=[
                    [Button.inline("✅ Onayla ve Gönder", b"post_confirm")],
                    [Button.inline("✏️ Buton Düzenle", b"post_back_to_buttons")],
                    [Button.inline("❌ İptal", b"cancel_post")]
                ]
            )
        except Exception as e:
            await event.respond(f"❌ Önizleme hatası: `{e}`")
    
    @bot.on(events.CallbackQuery(data=b"post_confirm"))
    async def post_confirm_handler(event):
        user_id = event.sender_id
        state = post_states.get(user_id)
        if not state or not state.get('content'):
            await event.answer("İçerik bulunamadı", alert=True)
            return
        
        await event.edit("⏳ **Gönderiliyor...**")
        
        buttons = build_post_buttons(state)
        content = state['content']
        channel = config.PLUGIN_CHANNEL
        
        try:
            # Kanala gönder
            if content.media:
                msg = await bot.send_file(
                    f"@{channel}",
                    file=content.media,
                    caption=content.message,
                    buttons=buttons,
                    formatting_entities=content.entities
                )
            else:
                msg = await bot.send_message(
                    f"@{channel}",
                    content.message,
                    buttons=buttons,
                    formatting_entities=content.entities,
                    link_preview=False
                )
            
            del post_states[user_id]
            
            await event.edit(
                f"✅ **Post gönderildi!**\n\n"
                f"📢 Kanal: @{channel}\n"
                f"🔗 [Gönderiye Git](https://t.me/{channel}/{msg.id})"
            )
            await send_log(bot, "post", f"Plugin kanalına post gönderildi", user_id)
            
        except Exception as e:
            await event.edit(f"❌ **Hata:** `{e}`\n\nBot'un kanala mesaj atma yetkisi var mı kontrol edin.")
    
    @bot.on(events.CallbackQuery(data=b"cancel_post"))
    async def cancel_post_handler(event):
        user_id = event.sender_id
        if user_id in post_states:
            del post_states[user_id]
        await event.edit("❌ Post oluşturma iptal edildi.")
    
    # ==========================================
    # PLUGİN AYARLARI (/psettings)
    # ==========================================
    
    @bot.on(events.NewMessage(pattern=r'^/psettings$'))
    async def psettings_command(event):
        """Plugin ayarları ana menüsü"""
        try:
            # Yetki kontrolü
            if event.sender_id != config.OWNER_ID:
                is_sudo = await db.is_sudo(event.sender_id)
                if not is_sudo:
                    return
            
            await show_psettings_menu(event, edit=False)
        except Exception as e:
            await event.respond(f"❌ Hata: {e}")
            import traceback
            traceback.print_exc()
    
    async def show_psettings_menu(event, edit=True, page=0):
        """Plugin ayarları menüsünü göster"""
        try:
            PER_PAGE = 6
            plugins = await db.get_all_plugins()
            
            if not plugins:
                text = "📭 Henüz plugin eklenmemiş."
                if edit:
                    await event.edit(text)
                else:
                    await event.respond(text)
                return
            
            total = len(plugins)
            total_pages = (total + PER_PAGE - 1) // PER_PAGE
            page = max(0, min(page, total_pages - 1))
            
            start = page * PER_PAGE
            end = start + PER_PAGE
            page_plugins = plugins[start:end]
            
            text = "⚙️ **Plugin Ayarları**\n\n"
            text += "Ayarlamak istediğiniz plugin'i seçin:\n\n"
            
            # İstatistikler
            public_count = sum(1 for p in plugins if p.get("is_public", True))
            private_count = total - public_count
            disabled_count = sum(1 for p in plugins if p.get("is_disabled", False))
            default_count = sum(1 for p in plugins if p.get("default_active", False))
            
            text += f"📊 **İstatistikler:**\n"
            text += f"├ Toplam: `{total}` plugin\n"
            text += f"├ 🌐 Genel: `{public_count}`\n"
            text += f"├ 🔒 Özel: `{private_count}`\n"
            text += f"├ ⛔ Devre Dışı: `{disabled_count}`\n"
            text += f"└ ⭐ Varsayılan Aktif: `{default_count}`\n"
            
            buttons = []
            
            # Plugin listesi
            for p in page_plugins:
                name = p.get("name", "?")
                status_icons = ""
                
                if p.get("is_disabled"):
                    status_icons += "⛔"
                elif p.get("is_public", True):
                    status_icons += "🌐"
                else:
                    status_icons += "🔒"
                
                if p.get("default_active"):
                    status_icons += "⭐"
                
                buttons.append([
                    Button.inline(f"{status_icons} {name}", f"psetsel_{name}")
                ])
            
            # Sayfalama
            nav_row = []
            if page > 0:
                nav_row.append(Button.inline("◀️ Önceki", f"psettings_page_{page-1}"))
            nav_row.append(Button.inline(f"📄 {page+1}/{total_pages}", "noop"))
            if page < total_pages - 1:
                nav_row.append(Button.inline("Sonraki ▶️", f"psettings_page_{page+1}"))
            
            if nav_row:
                buttons.append(nav_row)
            
            # Toplu işlemler
            buttons.append([
                Button.inline("🌐 Hepsini Genel", "pset_bulk_public"),
                Button.inline("🔒 Hepsini Özel", "pset_bulk_private")
            ])
            
            buttons.append([
                Button.inline("🔙 Plugin'ler", "admin_plugins")
            ])
            
            if edit:
                await event.edit(text, buttons=buttons)
            else:
                await event.respond(text, buttons=buttons)
        
        except Exception as e:
            error_text = f"❌ Hata: {e}"
            import traceback
            traceback.print_exc()
            if edit:
                await event.edit(error_text)
            else:
                await event.respond(error_text)
    
    @bot.on(events.CallbackQuery(pattern=rb"psettings_page_(\d+)"))
    async def psettings_page_handler(event):
        """Plugin ayarları sayfalama"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        page = int(event.pattern_match.group(1).decode())
        await show_psettings_menu(event, edit=True, page=page)
    
    @bot.on(events.CallbackQuery(pattern=rb"pset_bulk_(public|private)"))
    async def pset_bulk_handler(event):
        """Toplu plugin ayarı"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        action = event.pattern_match.group(1).decode()
        is_public = action == "public"
        
        plugins = await db.get_all_plugins()
        for p in plugins:
            await db.update_plugin(p["name"], {"is_public": is_public})
        
        await event.answer(f"✅ Tüm plugin'ler {'genel' if is_public else 'özel'} yapıldı!", alert=True)
        await show_psettings_menu(event, edit=True)
    
    @bot.on(events.CallbackQuery(pattern=rb"psetsel_([a-zA-Z0-9_]+)$"))
    async def pset_plugin_handler(event):
        """Tek plugin ayar menüsü"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        plugin_name = event.pattern_match.group(1).decode()
        
        plugin = await db.get_plugin(plugin_name)
        
        if not plugin:
            await event.answer("❌ Plugin bulunamadı!", alert=True)
            return
        
        await show_plugin_settings(event, plugin_name)
    
    async def show_plugin_settings(event, plugin_name):
        """Tek plugin'in ayar menüsünü göster"""
        plugin = await db.get_plugin(plugin_name)
        
        if not plugin:
            await event.edit("❌ Plugin bulunamadı.")
            return
        
        # Durum bilgileri
        is_public = plugin.get("is_public", True)
        is_disabled = plugin.get("is_disabled", False)
        default_active = plugin.get("default_active", False)
        allowed_users = plugin.get("allowed_users", [])
        restricted_users = plugin.get("restricted_users", [])
        
        text = f"⚙️ **{plugin_name}** Ayarları\n\n"
        text += f"📝 {plugin.get('description', 'Açıklama yok')[:100]}\n\n"
        
        text += "**Mevcut Durum:**\n"
        text += f"├ Erişim: {'🌐 Genel' if is_public else '🔒 Özel'}\n"
        text += f"├ Durum: {'⛔ Devre Dışı' if is_disabled else '✅ Aktif'}\n"
        text += f"├ Varsayılan: {'⭐ Aktif' if default_active else '◽ Pasif'}\n"
        text += f"├ İzinli Kullanıcı: `{len(allowed_users)}`\n"
        text += f"└ Engelli Kullanıcı: `{len(restricted_users)}`\n"
        
        # Komutlar
        commands = plugin.get("commands", [])
        if commands:
            cmd_text = ", ".join([f"`.{c}`" for c in commands[:5]])
            if len(commands) > 5:
                cmd_text += f" +{len(commands)-5}"
            text += f"\n🔧 Komutlar: {cmd_text}\n"
        
        buttons = []
        
        # Erişim ayarı
        if is_public:
            buttons.append([
                Button.inline("🔒 Özel Yap", f"pset_access_{plugin_name}_private")
            ])
        else:
            buttons.append([
                Button.inline("🌐 Genel Yap", f"pset_access_{plugin_name}_public")
            ])
        
        # Devre dışı/aktif
        if is_disabled:
            buttons.append([
                Button.inline("✅ Aktif Et", f"pset_status_{plugin_name}_enable")
            ])
        else:
            buttons.append([
                Button.inline("⛔ Devre Dışı Bırak", f"pset_status_{plugin_name}_disable")
            ])
        
        # Varsayılan aktif
        if default_active:
            buttons.append([
                Button.inline("◽ Varsayılan Pasif", f"pset_default_{plugin_name}_off")
            ])
        else:
            buttons.append([
                Button.inline("⭐ Varsayılan Aktif", f"pset_default_{plugin_name}_on")
            ])
        
        # Kullanıcı yönetimi
        buttons.append([
            Button.inline("👤 İzin Ver", f"psetallow_{plugin_name}"),
            Button.inline("🚫 Engelle", f"psetrestrict_{plugin_name}")
        ])
        
        buttons.append([
            Button.inline("📋 İzinli Liste", f"psetallowls_{plugin_name}"),
            Button.inline("📋 Engelli Liste", f"psetrestrictls_{plugin_name}")
        ])
        
        # Aktif kullanıcıları göster
        buttons.append([
            Button.inline("👥 Kullananlar", f"psetusers_{plugin_name}")
        ])
        
        # Geri
        buttons.append([
            Button.inline("🔙 Geri", "psettings_page_0")
        ])
        
        await event.edit(text, buttons=buttons)
    
    @bot.on(events.CallbackQuery(pattern=rb"pset_access_([a-zA-Z0-9_]+)_(public|private)"))
    async def pset_access_handler(event):
        """Plugin erişim ayarı"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        match = event.pattern_match
        plugin_name = match.group(1).decode()
        access = match.group(2).decode()
        
        is_public = access == "public"
        
        # Önceki durumu kaydet (genel yapılırken eski kullanıcıları bulmak için)
        plugin = await db.get_plugin(plugin_name)
        previous_users = []
        if is_public and plugin:
            # Özel yapılmadan önce kimler kullanıyordu - DB'de hala active_plugins'de olanlar
            users = await db.get_all_users()
            for user in users:
                if plugin_name in user.get("active_plugins", []):
                    previous_users.append(user.get("user_id"))
        
        await db.update_plugin(plugin_name, {"is_public": is_public})
        
        count = 0
        
        if not is_public:
            # Özel yapıldığında izinsiz kullanıcılarda deaktif et
            allowed_users = plugin.get("allowed_users", []) if plugin else []
            
            users = await db.get_all_users()
            for user in users:
                user_id = user.get("user_id")
                
                # İzinli kullanıcıları atla
                if user_id in allowed_users:
                    continue
                
                # Owner ve sudo'ları atla
                if user_id == config.OWNER_ID or await db.is_sudo(user_id):
                    continue
                
                active = user.get("active_plugins", [])
                if plugin_name in active:
                    active.remove(plugin_name)
                    await db.update_user(user_id, {"active_plugins": active})
                    
                    # Handler'ları kaldır
                    try:
                        success, _ = await plugin_manager.deactivate_plugin(user_id, plugin_name)
                        if success:
                            count += 1
                    except:
                        pass
            
            if count > 0:
                await event.answer(f"✅ Özel yapıldı! {count} kullanıcıda kaldırıldı.", alert=True)
            else:
                await event.answer(f"✅ Özel yapıldı!", alert=True)
        else:
            # Genel yapıldığında önceden yüklenmiş kullanıcılarda tekrar aktif et
            users = await db.get_all_users()
            for user in users:
                user_id = user.get("user_id")
                active = user.get("active_plugins", [])
                
                # Zaten aktifse atla
                if plugin_name in active:
                    # Ama handler yüklü olmayabilir, client varsa yükle
                    client = smart_session_manager.get_client(user_id)
                    if client:
                        # user_active_plugins'de yoksa yükle
                        if user_id not in plugin_manager.user_active_plugins or \
                           plugin_name not in plugin_manager.user_active_plugins.get(user_id, {}):
                            try:
                                success, _ = await plugin_manager.activate_plugin(user_id, plugin_name, client)
                                if success:
                                    count += 1
                            except:
                                pass
            
            if count > 0:
                await event.answer(f"✅ Genel yapıldı! {count} kullanıcıda yüklendi.", alert=True)
            else:
                await event.answer(f"✅ Genel yapıldı!", alert=True)
        
        await show_plugin_settings(event, plugin_name)
    
    @bot.on(events.CallbackQuery(pattern=rb"pset_status_([a-zA-Z0-9_]+)_(enable|disable)"))
    async def pset_status_handler(event):
        """Plugin aktif/devre dışı"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        match = event.pattern_match
        plugin_name = match.group(1).decode()
        status = match.group(2).decode()
        
        is_disabled = status == "disable"
        await db.update_plugin(plugin_name, {"is_disabled": is_disabled})
        
        deactivated_count = 0
        if is_disabled:
            # Tüm kullanıcılarda deaktif et
            users = await db.get_all_users()
            for user in users:
                user_id = user.get("user_id")
                active = user.get("active_plugins", [])
                if plugin_name in active:
                    active.remove(plugin_name)
                    await db.update_user(user_id, {"active_plugins": active})
                    
                    # Handler'ları kaldır (client aktifse)
                    try:
                        success, _ = await plugin_manager.deactivate_plugin(user_id, plugin_name)
                        if success:
                            deactivated_count += 1
                    except:
                        pass
            
            await event.answer(f"✅ Devre dışı! {deactivated_count} kullanıcıda kaldırıldı.", alert=True)
        else:
            await event.answer(f"✅ Aktif edildi!", alert=True)
        
        await show_plugin_settings(event, plugin_name)
    
    @bot.on(events.CallbackQuery(pattern=rb"pset_default_([a-zA-Z0-9_]+)_(on|off)"))
    async def pset_default_handler(event):
        """Plugin varsayılan aktif ayarı"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        match = event.pattern_match
        plugin_name = match.group(1).decode()
        default = match.group(2).decode()
        
        default_active = default == "on"
        await db.update_plugin(plugin_name, {"default_active": default_active})
        
        if default_active:
            # Tüm giriş yapmış kullanıcılarda bu plugin'i aktif et
            users = await db.get_logged_in_users()
            activated_count = 0
            
            for user in users:
                user_id = user.get("user_id")
                active_plugins = user.get("active_plugins", [])
                
                # Zaten aktif değilse ekle
                if plugin_name not in active_plugins:
                    active_plugins.append(plugin_name)
                    await db.update_user(user_id, {"active_plugins": active_plugins})
                    
                    # Eğer client aktifse plugin'i yükle
                    client = smart_session_manager.get_client(user_id)
                    if client:
                        try:
                            await plugin_manager.activate_plugin(user_id, plugin_name, client)
                            activated_count += 1
                        except:
                            pass
            
            await event.answer(f"✅ Varsayılan aktif! {activated_count} kullanıcıda yüklendi.", alert=True)
        else:
            await event.answer(f"✅ Varsayılan pasif yapıldı!", alert=True)
        
        await show_plugin_settings(event, plugin_name)
    
    @bot.on(events.CallbackQuery(pattern=rb"psetallow_([a-zA-Z0-9_]+)$"))
    async def pset_allow_prompt(event):
        """Kullanıcıya izin ver - ID iste"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        plugin_name = event.pattern_match.group(1).decode()
        
        text = f"👤 **{plugin_name}** için İzin Ver\n\n"
        text += "Kullanıcı ID'sini yazın:\n"
        text += f"Örnek: `/pallow {plugin_name} 123456789`"
        
        await event.edit(text, buttons=[
            [Button.inline("🔙 Geri", f"psetsel_{plugin_name}")]
        ])
    
    @bot.on(events.NewMessage(pattern=r'^/pallow\s+(\S+)\s+(\d+)$'))
    async def pallow_command(event):
        """Plugin'e kullanıcı izni ver"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        plugin_name = event.pattern_match.group(1)
        user_id = int(event.pattern_match.group(2))
        
        plugin = await db.get_plugin(plugin_name)
        if not plugin:
            await event.respond(f"❌ `{plugin_name}` bulunamadı.")
            return
        
        await db.add_plugin_user_access(plugin_name, user_id)
        await event.respond(f"✅ `{user_id}` kullanıcısına `{plugin_name}` izni verildi.")
    
    @bot.on(events.CallbackQuery(pattern=rb"psetrestrict_([a-zA-Z0-9_]+)$"))
    async def pset_restrict_prompt(event):
        """Kullanıcıyı engelle - ID iste"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        plugin_name = event.pattern_match.group(1).decode()
        
        text = f"🚫 **{plugin_name}** için Engelle\n\n"
        text += "Kullanıcı ID'sini yazın:\n"
        text += f"Örnek: `/prestrict {plugin_name} 123456789`"
        
        await event.edit(text, buttons=[
            [Button.inline("🔙 Geri", f"psetsel_{plugin_name}")]
        ])
    
    @bot.on(events.NewMessage(pattern=r'^/prestrict\s+(\S+)\s+(\d+)$'))
    async def prestrict_command(event):
        """Plugin'den kullanıcıyı engelle"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        plugin_name = event.pattern_match.group(1)
        user_id = int(event.pattern_match.group(2))
        
        plugin = await db.get_plugin(plugin_name)
        if not plugin:
            await event.respond(f"❌ `{plugin_name}` bulunamadı.")
            return
        
        await db.restrict_plugin_user(plugin_name, user_id)
        
        # Eğer kullanıcının aktif plugin'i varsa kaldır
        user = await db.get_user(user_id)
        if user:
            active = user.get("active_plugins", [])
            if plugin_name in active:
                active.remove(plugin_name)
                await db.update_user(user_id, {"active_plugins": active})
                await plugin_manager.deactivate_plugin(user_id, plugin_name)
        
        await event.respond(f"✅ `{user_id}` kullanıcısı `{plugin_name}` için engellendi.")
    
    @bot.on(events.CallbackQuery(pattern=rb"psetallowls_([a-zA-Z0-9_]+)"))
    async def pset_allowlist_handler(event):
        """İzinli kullanıcıları listele"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        plugin_name = event.pattern_match.group(1).decode()
        plugin = await db.get_plugin(plugin_name)
        
        if not plugin:
            await event.answer("❌ Plugin bulunamadı!", alert=True)
            return
        
        allowed = plugin.get("allowed_users", [])
        
        text = f"👤 **{plugin_name}** İzinli Kullanıcılar\n\n"
        
        if not allowed:
            text += "📭 Henüz izinli kullanıcı yok.\n"
            text += "(Özel plugin'ler için izin gerekir)"
        else:
            for uid in allowed[:20]:
                user = await db.get_user(uid)
                if user:
                    name = user.get("username") or user.get("first_name") or str(uid)
                    text += f"• `{uid}` - {name}\n"
                else:
                    text += f"• `{uid}`\n"
            
            if len(allowed) > 20:
                text += f"\n... ve {len(allowed)-20} kişi daha"
        
        text += f"\n\n🗑️ İzni kaldır: `/premove {plugin_name} <id>`"
        
        await event.edit(text, buttons=[
            [Button.inline("🔙 Geri", f"psetsel_{plugin_name}")]
        ])
    
    @bot.on(events.CallbackQuery(pattern=rb"psetrestrictls_([a-zA-Z0-9_]+)"))
    async def pset_restrictlist_handler(event):
        """Engelli kullanıcıları listele"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        plugin_name = event.pattern_match.group(1).decode()
        plugin = await db.get_plugin(plugin_name)
        
        if not plugin:
            await event.answer("❌ Plugin bulunamadı!", alert=True)
            return
        
        restricted = plugin.get("restricted_users", [])
        
        text = f"🚫 **{plugin_name}** Engelli Kullanıcılar\n\n"
        
        if not restricted:
            text += "📭 Henüz engelli kullanıcı yok."
        else:
            for uid in restricted[:20]:
                user = await db.get_user(uid)
                if user:
                    name = user.get("username") or user.get("first_name") or str(uid)
                    text += f"• `{uid}` - {name}\n"
                else:
                    text += f"• `{uid}`\n"
            
            if len(restricted) > 20:
                text += f"\n... ve {len(restricted)-20} kişi daha"
        
        text += f"\n\n✅ Engeli kaldır: `/punrestrict {plugin_name} <id>`"
        
        await event.edit(text, buttons=[
            [Button.inline("🔙 Geri", f"psetsel_{plugin_name}")]
        ])
    
    @bot.on(events.NewMessage(pattern=r'^/premove\s+(\S+)\s+(\d+)$'))
    async def premove_command(event):
        """Plugin iznini kaldır"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        plugin_name = event.pattern_match.group(1)
        user_id = int(event.pattern_match.group(2))
        
        await db.remove_plugin_user_access(plugin_name, user_id)
        await event.respond(f"✅ `{user_id}` kullanıcısının `{plugin_name}` izni kaldırıldı.")
    
    @bot.on(events.NewMessage(pattern=r'^/punrestrict\s+(\S+)\s+(\d+)$'))
    async def punrestrict_command(event):
        """Plugin engelini kaldır"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        plugin_name = event.pattern_match.group(1)
        user_id = int(event.pattern_match.group(2))
        
        await db.unrestrict_plugin_user(plugin_name, user_id)
        await event.respond(f"✅ `{user_id}` kullanıcısının `{plugin_name}` engeli kaldırıldı.")
    
    @bot.on(events.CallbackQuery(pattern=rb"psetusers_([a-zA-Z0-9_]+)"))
    async def pset_users_handler(event):
        """Plugin'i kullanan kullanıcıları listele"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        plugin_name = event.pattern_match.group(1).decode()
        
        users = await db.get_all_users()
        active_users = []
        
        for user in users:
            if plugin_name in user.get("active_plugins", []):
                active_users.append(user)
        
        text = f"👥 **{plugin_name}** Kullananlar\n\n"
        
        if not active_users:
            text += "📭 Bu plugin'i kullanan yok."
        else:
            text += f"Toplam: `{len(active_users)}` kullanıcı\n\n"
            for user in active_users[:20]:
                uid = user.get("user_id")
                name = user.get("username") or user.get("first_name") or str(uid)
                text += f"• `{uid}` - {name}\n"
            
            if len(active_users) > 20:
                text += f"\n... ve {len(active_users)-20} kişi daha"
        
        await event.edit(text, buttons=[
            [Button.inline("🔙 Geri", f"psetsel_{plugin_name}")]
        ])
    
    @bot.on(events.CallbackQuery(data=b"noop"))
    async def noop_handler(event):
        """Boş callback - sayfa numarası için"""
        await event.answer()
