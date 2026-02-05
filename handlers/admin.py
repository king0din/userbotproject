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
from userbot.manager import userbot_manager
from userbot.plugins import plugin_manager
from utils import send_log, get_readable_time, back_button

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
    
    async def get_settings_buttons(settings, is_owner):
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
        buttons = await get_settings_buttons(settings, event.sender_id == config.OWNER_ID)
        await event.edit(text, buttons=buttons)
    
    @bot.on(events.CallbackQuery(data=b"toggle_mode"))
    async def toggle_mode_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        settings = await db.get_settings()
        new_mode = "private" if settings.get("bot_mode") == "public" else "public"
        await db.update_settings({"bot_mode": new_mode})
        text, settings = await get_settings_text()
        buttons = await get_settings_buttons(settings, True)
        await event.edit(text, buttons=buttons)
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
        buttons = await get_settings_buttons(settings, True)
        await event.edit(text, buttons=buttons)
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
                text += f"{status} {access} `{p['name']}` ({len(p.get('commands', []))} cmd)\n"
            text += f"\n**Toplam:** {len(all_plugins)}"
        text += "\n\n• `/addplugin` - Ekle\n• `/delplugin <isim>` - Sil"
        await event.edit(text, buttons=[[Button.inline("🔄 Yenile", b"admin_plugins")], back_button("settings_menu")])
    
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
        await event.edit(text, buttons=[[Button.inline("🔄 Yenile", b"stats")], back_button("settings_menu")])
    
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
        
        # Kullanıcının tepkisini veritabanından kontrol et
        reaction_key = f"reaction_{chat_id}_{msg_id}"
        user_reactions = await db.get_user_reaction(reaction_key, user_id)
        
        # Mevcut butonları al
        current_buttons = event.message.buttons
        if not current_buttons:
            await event.answer("Hata!")
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
                            # Yeni tepki veya değiştirme
                            if user_reactions:
                                # Önceki tepkiyi geri al (sayısını düşür)
                                pass  # Bu aşağıda ele alınacak
                            new_count = current_count + 1
                            await db.set_user_reaction(reaction_key, user_id, emoji)
                            await event.answer(f"{emoji} eklendi!")
                    else:
                        # Tıklanmayan buton
                        if user_reactions == btn_emoji:
                            # Kullanıcı bu tepkiden vazgeçti
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
        except:
            pass  # Aynı butonlarsa hata verebilir
    
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
