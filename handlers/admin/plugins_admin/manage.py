# KingTG - Admin / plugins_admin / manage
# Plugin ekle/sil/güncelle/al/yetki
# (plugins_admin.py'dan bölündü - davranış birebir)
# ============================================
# KingTG UserBot Service - Admin / plugins_admin
# Plugin ekleme/silme/yetki + plugin başına ayarlar
# (admin.py'dan otomatik bölündü - davranış birebir korundu)
# ============================================

# ============================================
# KingTG UserBot Service - Admin Handlers
# ============================================

import os
import sys
import asyncio
from telethon import events, Button
import config
from database import database as db
from userbot.smart_manager import smart_session_manager
from userbot.plugins import plugin_manager

# Eski uyumluluk için alias
userbot_manager = smart_session_manager
from utils import send_log, back_button


def register(bot):
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
