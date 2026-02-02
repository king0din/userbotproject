# ============================================
# KingTG UserBot Service - Admin Handlers
# ============================================

import os
import sys
import asyncio
import subprocess
from telethon import events, Button
import config
from database import database as db
from userbot.manager import userbot_manager
from userbot.plugins import plugin_manager
from utils import (
    owner_only, sudo_only, send_log, get_readable_time,
    back_button, close_button, paginate, pagination_buttons,
    get_user_info
)

import time
start_time = time.time()

def register_admin_handlers(bot):
    """Admin handler'larını kaydet"""
    
    # ==========================================
    # AYARLAR MENÜSÜ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"settings_menu"))
    async def settings_menu_handler(event):
        """Ayarlar menüsü"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        
        settings = await db.get_settings()
        stats = await db.get_stats()
        
        mode_emoji = "🌐" if settings.get("bot_mode") == "public" else "🔒"
        mode_text = "Genel" if settings.get("bot_mode") == "public" else "Özel"
        maint_emoji = "🔧" if settings.get("maintenance") else "✅"
        maint_text = "Açık" if settings.get("maintenance") else "Kapalı"
        
        text = config.MESSAGES["settings_menu"].format(
            mode=f"{mode_emoji} {mode_text}",
            maintenance=f"{maint_emoji} {maint_text}",
            users=stats.get("total_users", 0),
            plugins=stats.get("total_plugins", 0),
            sudos=stats.get("sudo_users", 0),
            bans=stats.get("banned_users", 0)
        )
        
        if event.sender_id == config.OWNER_ID:
            buttons = [
                [
                    Button.inline(config.BUTTONS["public_mode"] if settings.get("bot_mode") == "private" else config.BUTTONS["private_mode"], b"toggle_mode"),
                    Button.inline(config.BUTTONS["maintenance_off"] if settings.get("maintenance") else config.BUTTONS["maintenance_on"], b"toggle_maintenance")
                ],
                [Button.inline(config.BUTTONS["user_management"], b"user_management")],
                [Button.inline(config.BUTTONS["plugin_management"], b"plugin_management")],
                [Button.inline(config.BUTTONS["sudo_management"], b"sudo_management")],
                [Button.inline(config.BUTTONS["ban_management"], b"ban_management")],
                [Button.inline(config.BUTTONS["stats"], b"stats")],
                [
                    Button.inline(config.BUTTONS["update"], b"update_bot"),
                    Button.inline(config.BUTTONS["restart"], b"restart_bot")
                ],
                [Button.inline(config.BUTTONS["logs"], b"view_logs")],
                back_button("main_menu")
            ]
        else:
            buttons = [
                [Button.inline(config.BUTTONS["plugin_management"], b"plugin_management")],
                [Button.inline(config.BUTTONS["stats"], b"stats")],
                back_button("main_menu")
            ]
        
        await event.edit(text, buttons=buttons)
    
    @bot.on(events.CallbackQuery(data=b"toggle_mode"))
    async def toggle_mode_handler(event):
        """Bot modunu değiştir"""
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        settings = await db.get_settings()
        new_mode = "private" if settings.get("bot_mode") == "public" else "public"
        
        await db.update_settings({"bot_mode": new_mode})
        await event.answer(f"✅ Bot modu: {new_mode}", alert=True)
        await send_log(bot, "system", f"Bot modu: {new_mode}")
    
    @bot.on(events.CallbackQuery(data=b"toggle_maintenance"))
    async def toggle_maintenance_handler(event):
        """Bakım modunu değiştir"""
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        settings = await db.get_settings()
        new_state = not settings.get("maintenance", False)
        
        await db.update_settings({"maintenance": new_state})
        await event.answer(f"✅ Bakım: {'Açık' if new_state else 'Kapalı'}", alert=True)
        await send_log(bot, "system", f"Bakım: {'Açık' if new_state else 'Kapalı'}")
    
    # ==========================================
    # BAN YÖNETİMİ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"ban_management"))
    async def ban_management_handler(event):
        """Ban yönetimi"""
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        banned = await db.get_banned_users()
        
        text = "🚫 **Ban Yönetimi**\n\n"
        
        if banned:
            for user in banned[:10]:
                text += f"• `{user['user_id']}` - {user.get('ban_reason', 'Sebep yok')}\n"
        else:
            text += "✅ Banlı kullanıcı yok."
        
        text += "\n\n**Komutlar:**\n"
        text += "• `/ban <user_id> [sebep]`\n"
        text += "• `/unban <user_id>`"
        
        await event.edit(text, buttons=[back_button("settings_menu")])
    
    @bot.on(events.NewMessage(pattern=r'^/ban\s+(\d+)(?:\s+(.+))?$'))
    async def ban_command(event):
        """Kullanıcı banla"""
        if event.sender_id != config.OWNER_ID:
            return
        
        user_id = int(event.pattern_match.group(1))
        reason = event.pattern_match.group(2) or "Sebep belirtilmedi"
        
        if user_id == config.OWNER_ID:
            await event.respond("❌ Kendinizi banlayamazsınız!")
            return
        
        await db.add_user(user_id)
        await db.ban_user(user_id, reason, event.sender_id)
        await userbot_manager.logout(user_id)
        plugin_manager.clear_user_plugins(user_id)
        
        await event.respond(f"✅ `{user_id}` banlandı.\nSebep: {reason}")
        await send_log(bot, "ban", f"Banlanan: {user_id}\nSebep: {reason}", event.sender_id)
    
    @bot.on(events.NewMessage(pattern=r'^/unban\s+(\d+)$'))
    async def unban_command(event):
        """Ban kaldır"""
        if event.sender_id != config.OWNER_ID:
            return
        
        user_id = int(event.pattern_match.group(1))
        await db.unban_user(user_id)
        
        await event.respond(f"✅ `{user_id}` banı kaldırıldı.")
        await send_log(bot, "ban", f"Ban kaldırıldı: {user_id}", event.sender_id)
    
    # ==========================================
    # SUDO YÖNETİMİ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"sudo_management"))
    async def sudo_management_handler(event):
        """Sudo yönetimi"""
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        sudos = await db.get_sudos()
        
        text = "👑 **Sudo Yönetimi**\n\n"
        
        if sudos:
            for user in sudos:
                text += f"• `{user['user_id']}` - @{user.get('username', 'Yok')}\n"
        else:
            text += "Henüz sudo yok."
        
        text += "\n\n**Komutlar:**\n"
        text += "• `/addsudo <user_id>`\n"
        text += "• `/delsudo <user_id>`"
        
        await event.edit(text, buttons=[back_button("settings_menu")])
    
    @bot.on(events.NewMessage(pattern=r'^/addsudo\s+(\d+)$'))
    async def addsudo_command(event):
        """Sudo ekle"""
        if event.sender_id != config.OWNER_ID:
            return
        
        user_id = int(event.pattern_match.group(1))
        await db.add_user(user_id)
        await db.add_sudo(user_id)
        
        await event.respond(f"✅ `{user_id}` sudo eklendi.")
        await send_log(bot, "sudo", f"Sudo eklendi: {user_id}", event.sender_id)
    
    @bot.on(events.NewMessage(pattern=r'^/delsudo\s+(\d+)$'))
    async def delsudo_command(event):
        """Sudo kaldır"""
        if event.sender_id != config.OWNER_ID:
            return
        
        user_id = int(event.pattern_match.group(1))
        await db.remove_sudo(user_id)
        
        await event.respond(f"✅ `{user_id}` sudo kaldırıldı.")
        await send_log(bot, "sudo", f"Sudo kaldırıldı: {user_id}", event.sender_id)
    
    # ==========================================
    # PLUGİN YÖNETİMİ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"plugin_management"))
    async def plugin_management_handler(event):
        """Plugin yönetimi"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        
        plugins = await db.get_all_plugins()
        
        text = "🔌 **Plugin Yönetimi**\n\n"
        text += f"Toplam: `{len(plugins)}`\n\n"
        text += "**Komutlar:**\n"
        text += "• `/addplugin` - Plugin ekle\n"
        text += "• `/delplugin <isim>` - Plugin sil\n"
        text += "• `/setpublic <isim>` - Genel yap\n"
        text += "• `/setprivate <isim>` - Özel yap"
        
        await event.edit(text, buttons=[back_button("settings_menu")])
    
    @bot.on(events.NewMessage(pattern=r'^/addplugin$'))
    async def addplugin_command(event):
        """Plugin ekle"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        reply = await event.get_reply_message()
        
        if not reply or not reply.file or not reply.file.name.endswith('.py'):
            await event.respond("⚠️ Bir `.py` dosyasına yanıt verin.")
            return
        
        path = await reply.download_media(file=config.PLUGINS_DIR + "/")
        info = plugin_manager.extract_plugin_info(path)
        
        for cmd in info["commands"]:
            existing = await db.check_command_exists(cmd)
            if existing:
                os.remove(path)
                await event.respond(f"❌ `.{cmd}` komutu `{existing}` plugininde mevcut!")
                return
        
        if not hasattr(bot, 'pending_plugins'):
            bot.pending_plugins = {}
        bot.pending_plugins[info['name']] = path
        
        await event.respond(
            f"🔌 **Plugin: `{info['name']}`**\n\n"
            f"📝 {info['description'] or 'Açıklama yok'}\n"
            f"🔧 Komutlar: {', '.join([f'`.{c}`' for c in info['commands']])}\n\n"
            f"Nasıl eklensin?",
            buttons=[
                [
                    Button.inline("🌐 Genel", f"confirm_plugin_public_{info['name']}".encode()),
                    Button.inline("🔒 Özel", f"confirm_plugin_private_{info['name']}".encode())
                ],
                [Button.inline("❌ İptal", b"cancel_plugin")]
            ]
        )
    
    @bot.on(events.CallbackQuery(pattern=b"confirm_plugin_(public|private)_(.+)"))
    async def confirm_plugin_handler(event):
        """Plugin onay"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        data = event.data.decode()
        is_public = "public" in data
        plugin_name = data.split("_", 3)[-1]
        
        if not hasattr(bot, 'pending_plugins') or plugin_name not in bot.pending_plugins:
            await event.answer("Plugin bulunamadı", alert=True)
            return
        
        path = bot.pending_plugins[plugin_name]
        success, message = await plugin_manager.register_plugin(path, is_public=is_public)
        
        del bot.pending_plugins[plugin_name]
        await event.edit(message)
        
        if success:
            await send_log(bot, "plugin", f"Eklendi: {plugin_name}", event.sender_id)
    
    @bot.on(events.CallbackQuery(data=b"cancel_plugin"))
    async def cancel_plugin_handler(event):
        """Plugin iptal"""
        if hasattr(bot, 'pending_plugins'):
            for path in bot.pending_plugins.values():
                if os.path.exists(path):
                    os.remove(path)
            bot.pending_plugins.clear()
        await event.edit("❌ İptal edildi.")
    
    @bot.on(events.NewMessage(pattern=r'^/delplugin\s+(\S+)$'))
    async def delplugin_command(event):
        """Plugin sil"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        plugin_name = event.pattern_match.group(1)
        success, message = await plugin_manager.unregister_plugin(plugin_name)
        await event.respond(message)
        
        if success:
            await send_log(bot, "plugin", f"Silindi: {plugin_name}", event.sender_id)
    
    @bot.on(events.NewMessage(pattern=r'^/setpublic\s+(\S+)$'))
    async def setpublic_command(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        plugin_name = event.pattern_match.group(1)
        await db.update_plugin(plugin_name, {"is_public": True})
        await event.respond(f"✅ `{plugin_name}` genel yapıldı.")
    
    @bot.on(events.NewMessage(pattern=r'^/setprivate\s+(\S+)$'))
    async def setprivate_command(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        plugin_name = event.pattern_match.group(1)
        await db.update_plugin(plugin_name, {"is_public": False})
        await event.respond(f"✅ `{plugin_name}` özel yapıldı.")
    
    # ==========================================
    # İSTATİSTİKLER
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"stats"))
    async def stats_handler(event):
        """İstatistikler"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        
        stats = await db.get_stats()
        uptime = get_readable_time(time.time() - start_time)
        
        text = "📊 **İstatistikler**\n\n"
        text += f"👥 Kullanıcı: `{stats.get('total_users', 0)}`\n"
        text += f"✅ Aktif: `{stats.get('logged_in_users', 0)}`\n"
        text += f"🚫 Banlı: `{stats.get('banned_users', 0)}`\n"
        text += f"👑 Sudo: `{stats.get('sudo_users', 0)}`\n\n"
        text += f"🔌 Plugin: `{stats.get('total_plugins', 0)}`\n\n"
        text += f"⏱️ Uptime: `{uptime}`\n"
        text += f"🔢 Sürüm: `v{config.__version__}`"
        
        await event.edit(text, buttons=[back_button("settings_menu")])
    
    # ==========================================
    # GÜNCELLEME & RESTART
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"update_bot"))
    async def update_bot_handler(event):
        """Güncelleme"""
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        await event.edit("🔄 Kontrol ediliyor...")
        
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
                await event.edit(f"✅ Güncel!\nSürüm: `v{config.__version__}`", buttons=[back_button("settings_menu")])
                return
            
            await event.edit(
                f"🆕 {len(commits)} güncelleme mevcut!",
                buttons=[
                    [Button.inline("✅ Güncelle", b"do_update")],
                    back_button("settings_menu")
                ]
            )
        except Exception as e:
            await event.edit(f"❌ Hata: {e}", buttons=[back_button("settings_menu")])
    
    @bot.on(events.CallbackQuery(data=b"do_update"))
    async def do_update_handler(event):
        """Güncellemeyi yap"""
        if event.sender_id != config.OWNER_ID:
            return
        
        await event.edit("⏳ Güncelleniyor...")
        
        try:
            import git
            repo = git.Repo(".")
            origin = repo.remotes.origin
            current_branch = repo.active_branch.name
            
            origin.pull(current_branch)
            
            if os.path.exists("requirements.txt"):
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"])
            
            await event.edit("✅ Güncellendi!", buttons=[[Button.inline("🔃 Yeniden Başlat", b"restart_bot")]])
            await send_log(bot, "update", "Bot güncellendi")
        except Exception as e:
            await event.edit(f"❌ Hata: {e}", buttons=[back_button("settings_menu")])
    
    @bot.on(events.CallbackQuery(data=b"restart_bot"))
    async def restart_bot_handler(event):
        """Yeniden başlat"""
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        await event.edit("🔄 Yeniden başlatılıyor...")
        
        with open(".restart_info", "w") as f:
            f.write(f"{event.chat_id}|{event.message_id}")
        
        await send_log(bot, "system", "Bot yeniden başlatılıyor")
        await asyncio.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    
    # ==========================================
    # LOGLAR & KULLANICI YÖNETİMİ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"view_logs"))
    async def view_logs_handler(event):
        """Logları görüntüle"""
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        logs = await db.get_logs(limit=15)
        
        text = "📋 **Son Loglar:**\n\n"
        
        if logs:
            for log in logs:
                text += f"• [{log.get('type', '?')}] {log.get('message', '')[:40]}\n"
        else:
            text += "Henüz log yok."
        
        await event.edit(text, buttons=[back_button("settings_menu")])
    
    @bot.on(events.CallbackQuery(data=b"user_management"))
    async def user_management_handler(event):
        """Kullanıcı yönetimi"""
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        stats = await db.get_stats()
        
        text = "👥 **Kullanıcı Yönetimi**\n\n"
        text += f"Toplam: `{stats.get('total_users', 0)}`\n"
        text += f"Aktif: `{stats.get('logged_in_users', 0)}`\n"
        text += f"Banlı: `{stats.get('banned_users', 0)}`"
        
        await event.edit(text, buttons=[back_button("settings_menu")])
    
    # ==========================================
    # BROADCAST
    # ==========================================
    
    @bot.on(events.NewMessage(pattern=r'^/broadcast$'))
    async def broadcast_command(event):
        """Duyuru"""
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
        
        await msg.edit(f"✅ Tamamlandı!\n📤 Gönderildi: {sent}\n❌ Başarısız: {failed}")
