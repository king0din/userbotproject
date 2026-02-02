# ============================================
# KingTG UserBot Service - User Handlers
# ============================================

from telethon import events, Button
import config
from database import database as db
from userbot.manager import userbot_manager
from userbot.plugins import plugin_manager
from utils import (
    check_ban, check_private_mode, check_maintenance, 
    register_user, send_log, is_valid_phone, back_button
)

# State management
user_states = {}
STATE_WAITING_PHONE = "waiting_phone"
STATE_WAITING_CODE = "waiting_code"
STATE_WAITING_2FA = "waiting_2fa"
STATE_WAITING_SESSION_TELETHON = "waiting_session_telethon"
STATE_WAITING_SESSION_PYROGRAM = "waiting_session_pyrogram"

def register_user_handlers(bot):
    """Kullanıcı handler'larını kaydet"""
    
    # ==========================================
    # /start KOMUTU
    # ==========================================
    
    @bot.on(events.NewMessage(pattern=r'^/start$'))
    @check_ban
    @check_maintenance
    @check_private_mode
    @register_user
    async def start_handler(event):
        if event.sender_id in user_states:
            del user_states[event.sender_id]
        
        user = await event.get_sender()
        user_data = await db.get_user(event.sender_id)
        is_logged_in = user_data.get("is_logged_in", False) if user_data else False
        
        text = config.MESSAGES["welcome"]
        text += f"\n\n👋 Merhaba **{user.first_name}**!"
        
        if is_logged_in:
            active_count = len(user_data.get("active_plugins", []))
            text += f"\n✅ Userbot aktif: `{user_data.get('userbot_username', '?')}`"
            text += f"\n🔌 Aktif plugin: `{active_count}`"
        
        buttons = []
        
        if is_logged_in:
            buttons.append([Button.inline(config.BUTTONS["plugins"], b"plugins_menu")])
            buttons.append([Button.inline(config.BUTTONS["my_plugins"], b"my_plugins")])
            buttons.append([Button.inline(config.BUTTONS["logout"], b"logout_confirm")])
        else:
            session_data = await db.get_session(event.sender_id)
            if session_data and session_data.get("remember"):
                buttons.append([Button.inline("⚡ Hızlı Giriş", b"quick_login")])
            buttons.append([Button.inline(config.BUTTONS["login"], b"login_menu")])
        
        buttons.append([
            Button.inline(config.BUTTONS["help"], b"help"),
            Button.inline(config.BUTTONS["commands"], b"commands")
        ])
        buttons.append([Button.url(config.BUTTONS["plugin_channel"], f"https://t.me/{config.PLUGIN_CHANNEL}")])
        
        if event.sender_id == config.OWNER_ID or await db.is_sudo(event.sender_id):
            buttons.append([Button.inline(config.BUTTONS["settings"], b"settings_menu")])
        
        await event.respond(text, buttons=buttons)
    
    # ==========================================
    # MESAJ HANDLER
    # ==========================================
    
    @bot.on(events.NewMessage(func=lambda e: e.is_private and not e.text.startswith('/')))
    async def message_handler(event):
        user_id = event.sender_id
        if user_id not in user_states:
            return
        
        state = user_states[user_id].get("state")
        
        if state == STATE_WAITING_PHONE:
            await handle_phone_input(event, bot)
        elif state == STATE_WAITING_CODE:
            await handle_code_input(event, bot)
        elif state == STATE_WAITING_2FA:
            await handle_2fa_input(event, bot)
        elif state == STATE_WAITING_SESSION_TELETHON:
            await handle_session_input(event, bot, "telethon")
        elif state == STATE_WAITING_SESSION_PYROGRAM:
            await handle_session_input(event, bot, "pyrogram")
    
    # ==========================================
    # GİRİŞ İŞLEMLERİ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"login_menu"))
    @check_ban
    async def login_menu_handler(event):
        if event.sender_id in user_states:
            del user_states[event.sender_id]
        
        buttons = [
            [Button.inline(config.BUTTONS["phone"], b"login_phone")],
            [Button.inline(config.BUTTONS["telethon_session"], b"login_telethon")],
            [Button.inline(config.BUTTONS["pyrogram_session"], b"login_pyrogram")],
            back_button("main_menu")
        ]
        await event.edit(config.MESSAGES["login_method"], buttons=buttons)
    
    @bot.on(events.CallbackQuery(data=b"login_phone"))
    async def login_phone_start(event):
        user_states[event.sender_id] = {"state": STATE_WAITING_PHONE}
        text = config.MESSAGES["login_phone"] + "\n\n⚠️ İptal: /cancel"
        await event.edit(text, buttons=[[Button.inline("❌ İptal", b"login_menu")]])
    
    @bot.on(events.CallbackQuery(data=b"login_telethon"))
    async def login_telethon_start(event):
        user_states[event.sender_id] = {"state": STATE_WAITING_SESSION_TELETHON, "session_type": "telethon"}
        text = config.MESSAGES["login_session_telethon"] + "\n\n⚠️ İptal: /cancel"
        await event.edit(text, buttons=[[Button.inline("❌ İptal", b"login_menu")]])
    
    @bot.on(events.CallbackQuery(data=b"login_pyrogram"))
    async def login_pyrogram_start(event):
        user_states[event.sender_id] = {"state": STATE_WAITING_SESSION_PYROGRAM, "session_type": "pyrogram"}
        text = config.MESSAGES["login_session_pyrogram"] + "\n\n⚠️ İptal: /cancel"
        await event.edit(text, buttons=[[Button.inline("❌ İptal", b"login_menu")]])
    
    async def handle_phone_input(event, bot):
        user_id = event.sender_id
        phone = event.text.strip()
        
        if not is_valid_phone(phone):
            await event.respond("❌ Geçersiz format. Örnek: `+905551234567`")
            return
        
        try: await event.delete()
        except: pass
        
        msg = await bot.send_message(user_id, "⏳ Kod gönderiliyor...")
        result = await userbot_manager.start_phone_login(user_id, phone)
        
        if not result["success"]:
            if user_id in user_states: del user_states[user_id]
            error = result.get("error", "Bilinmeyen hata")
            if result.get("error") == "flood_wait":
                error = f"{result['seconds']} saniye bekleyin"
            await msg.edit(f"❌ Hata: {error}", buttons=[[Button.inline("🔙 Geri", b"login_menu")]])
            return
        
        user_states[user_id] = {"state": STATE_WAITING_CODE, "phone": phone}
        await msg.edit(config.MESSAGES["login_code"] + "\n\n⚠️ İptal: /cancel", 
                       buttons=[[Button.inline("❌ İptal", b"login_menu")]])
    
    async def handle_code_input(event, bot):
        user_id = event.sender_id
        code = event.text.strip().replace(" ", "").replace("-", "")
        
        try: await event.delete()
        except: pass
        
        msg = await bot.send_message(user_id, "⏳ Doğrulanıyor...")
        result = await userbot_manager.verify_code(user_id, code)
        
        if result.get("stage") == "2fa":
            user_states[user_id]["state"] = STATE_WAITING_2FA
            await msg.edit(config.MESSAGES["login_2fa"] + "\n\n⚠️ İptal: /cancel",
                          buttons=[[Button.inline("❌ İptal", b"login_menu")]])
            return
        
        if result["success"]:
            await handle_login_success(event, bot, result, msg)
        else:
            error = result.get("error", "Bilinmeyen hata")
            if error in ["code_expired", "no_pending_login"]:
                if user_id in user_states: del user_states[user_id]
            await msg.edit(f"❌ {error}", buttons=[[Button.inline("🔙 Geri", b"login_menu")]])
    
    async def handle_2fa_input(event, bot):
        user_id = event.sender_id
        password = event.text.strip()
        
        try: await event.delete()
        except: pass
        
        msg = await bot.send_message(user_id, "⏳ Doğrulanıyor...")
        result = await userbot_manager.verify_2fa(user_id, password)
        
        if result["success"]:
            await handle_login_success(event, bot, result, msg)
        else:
            await msg.edit(f"❌ {result.get('error', 'Hata')}", 
                          buttons=[[Button.inline("🔙 Geri", b"login_menu")]])
    
    async def handle_session_input(event, bot, session_type):
        user_id = event.sender_id
        session_string = event.text.strip()
        
        try: await event.delete()
        except: pass
        
        msg = await bot.send_message(user_id, "⏳ Session doğrulanıyor...")
        result = await userbot_manager.login_with_session(user_id, session_string, session_type)
        
        if result["success"]:
            if not hasattr(bot, 'session_temp'): bot.session_temp = {}
            bot.session_temp[user_id] = {"session": session_string, "phone": None, "type": session_type}
            await handle_login_success(event, bot, result, msg)
        else:
            if user_id in user_states: del user_states[user_id]
            await msg.edit(f"❌ {result.get('error', 'Session geçersiz')}", 
                          buttons=[[Button.inline("🔙 Geri", b"login_menu")]])
    
    async def handle_login_success(event, bot, result, msg):
        user_id = event.sender_id
        user_info = result["user_info"]
        session_string = result["session_string"]
        phone = user_states.get(user_id, {}).get("phone")
        
        await db.update_user(user_id, {
            "is_logged_in": True,
            "userbot_id": user_info["id"],
            "userbot_username": user_info["username"]
        })
        
        if not hasattr(bot, 'session_temp'): bot.session_temp = {}
        bot.session_temp[user_id] = {
            "session": session_string,
            "phone": phone,
            "type": user_states.get(user_id, {}).get("session_type", "phone")
        }
        
        if user_id in user_states: del user_states[user_id]
        
        await msg.edit(
            config.MESSAGES["login_success"].format(
                name=user_info["first_name"] or "Kullanıcı",
                user_id=user_info["id"]
            ) + "\n\n" + config.MESSAGES["login_remember"],
            buttons=[
                [Button.inline(config.BUTTONS["remember_yes"], b"save_session"),
                 Button.inline(config.BUTTONS["remember_no"], b"dont_save_session")]
            ]
        )
        await send_log(bot, "login", f"Giriş: @{user_info['username']}", user_id)
    
    # ==========================================
    # SESSION KAYDETME
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"save_session"))
    async def save_session_handler(event):
        user_id = event.sender_id
        if not hasattr(bot, 'session_temp') or user_id not in bot.session_temp:
            await event.answer("Session bulunamadı", alert=True)
            return
        
        temp = bot.session_temp[user_id]
        await db.save_session(user_id, temp["session"], temp["type"], temp.get("phone"), remember=True)
        del bot.session_temp[user_id]
        
        await event.edit("✅ **Giriş tamamlandı!**\n\n💾 Session kaydedildi.", buttons=[
            [Button.inline(config.BUTTONS["plugins"], b"plugins_menu")],
            [Button.inline("🏠 Ana Menü", b"main_menu")]
        ])
    
    @bot.on(events.CallbackQuery(data=b"dont_save_session"))
    async def dont_save_session_handler(event):
        user_id = event.sender_id
        if hasattr(bot, 'session_temp') and user_id in bot.session_temp:
            temp = bot.session_temp[user_id]
            await db.save_session(user_id, temp["session"], temp["type"], temp.get("phone"), remember=False)
            del bot.session_temp[user_id]
        
        await event.edit("✅ **Giriş tamamlandı!**", buttons=[
            [Button.inline(config.BUTTONS["plugins"], b"plugins_menu")],
            [Button.inline("🏠 Ana Menü", b"main_menu")]
        ])
    
    # ==========================================
    # HIZLI GİRİŞ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"quick_login"))
    async def quick_login_handler(event):
        user_id = event.sender_id
        session_data = await db.get_session(user_id)
        
        if not session_data or not session_data.get("data"):
            await event.answer("Session bulunamadı", alert=True)
            return
        
        await event.edit("⏳ Giriş yapılıyor...")
        
        result = await userbot_manager.login_with_session(
            user_id, session_data["data"], session_data.get("type", "telethon")
        )
        
        if result["success"]:
            user_info = result["user_info"]
            await db.update_user(user_id, {
                "is_logged_in": True,
                "userbot_id": user_info["id"],
                "userbot_username": user_info["username"]
            })
            
            client = userbot_manager.get_client(user_id)
            restored = 0
            if client:
                restored = await plugin_manager.restore_user_plugins(user_id, client)
            
            text = f"✅ **Giriş başarılı!**\n\n👤 `{user_info['first_name']}`"
            if restored > 0:
                text += f"\n🔌 {restored} plugin yüklendi"
            
            await event.edit(text, buttons=[
                [Button.inline(config.BUTTONS["plugins"], b"plugins_menu")],
                [Button.inline("🏠 Ana Menü", b"main_menu")]
            ])
            await send_log(bot, "login", f"Hızlı giriş: @{user_info['username']}", user_id)
        else:
            await db.clear_session(user_id, keep_data=False)
            await event.edit("❌ Session geçersiz. Yeniden giriş yapın.", buttons=[
                [Button.inline(config.BUTTONS["login"], b"login_menu")]
            ])
    
    # ==========================================
    # ÇIKIŞ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"logout_confirm"))
    async def logout_confirm_handler(event):
        await event.edit(config.MESSAGES["logout_confirm"], buttons=[
            [Button.inline(config.BUTTONS["keep_data"], b"logout_keep"),
             Button.inline(config.BUTTONS["delete_data"], b"logout_delete")],
            back_button("main_menu")
        ])
    
    @bot.on(events.CallbackQuery(pattern=b"logout_(keep|delete)"))
    async def logout_handler(event):
        user_id = event.sender_id
        keep_data = event.data == b"logout_keep"
        
        await event.edit("⏳ Çıkış yapılıyor...")
        await userbot_manager.logout(user_id)
        plugin_manager.clear_user_plugins(user_id)
        await db.clear_session(user_id, keep_data=keep_data)
        
        text = config.MESSAGES["logout_success"]
        text += "\n\n💾 Bilgiler saklandı." if keep_data else "\n\n🗑️ Bilgiler silindi."
        
        await event.edit(text, buttons=[[Button.inline("🏠 Ana Menü", b"main_menu")]])
        await send_log(bot, "logout", f"Çıkış (sakla: {keep_data})", user_id)
    
    # ==========================================
    # PLUGİN MENÜSÜ - YENİLENDİ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"plugins_menu"))
    async def plugins_menu_handler(event):
        user_id = event.sender_id
        user_data = await db.get_user(user_id)
        
        if not user_data or not user_data.get("is_logged_in"):
            await event.answer("Önce giriş yapmalısınız", alert=True)
            return
        
        all_plugins = await db.get_all_plugins()
        active_plugins = user_data.get("active_plugins", [])
        
        if not all_plugins:
            text = "📭 **Henüz plugin eklenmemiş.**\n\nPlugin duyuruları için kanalı takip edin."
        else:
            text = "🔌 **Mevcut Plugin'ler:**\n\n"
            
            for p in all_plugins:
                if not p.get("is_public", True) and user_id not in p.get("allowed_users", []):
                    continue
                
                name = p['name']
                is_active = name in active_plugins
                status = "🟢" if is_active else "⚪"
                cmds = p.get("commands", [])[:2]
                cmd_text = ", ".join([f"`.{c}`" for c in cmds])
                if len(p.get("commands", [])) > 2:
                    cmd_text += "..."
                
                text += f"{status} `{name}` - {cmd_text}\n"
            
            text += f"\n🟢 = Yüklü | ⚪ = Yüklü değil"
            text += f"\n\n**Toplam:** {len(all_plugins)} plugin"
            text += f"\n**Aktif:** {len(active_plugins)} plugin"
        
        text += "\n\n📌 Plugin detay için: `/pinfo` komutu ile plugin adı girin.\n⬇️Plugin aktif etmek için: `/pactive` komutu ile plugin adı girin\n-**nörnek**`/pactive tag` veya devredışı bırakmak için: `/pinactive tag`"
        
        buttons = [
            [Button.inline(config.BUTTONS["my_plugins"], b"my_plugins")],
            [Button.url(config.BUTTONS["plugin_channel"], f"https://t.me/{config.PLUGIN_CHANNEL}")],
            back_button("main_menu")
        ]
        
        await event.edit(text, buttons=buttons)
    
    @bot.on(events.CallbackQuery(data=b"my_plugins"))
    async def my_plugins_handler(event):
        user_data = await db.get_user(event.sender_id)
        
        if not user_data or not user_data.get("is_logged_in"):
            await event.answer("Önce giriş yapmalısınız", alert=True)
            return
        
        active_plugins = user_data.get("active_plugins", [])
        
        if not active_plugins:
            text = config.MESSAGES["no_active_plugins"]
        else:
            text = "📦 **Aktif Plugin'leriniz:**\n\n"
            for name in active_plugins:
                plugin = await db.get_plugin(name)
                if plugin:
                    cmds = ", ".join([f"`.{c}`" for c in plugin.get("commands", [])])
                    text += f"✅ `{name}`\n   └ {cmds}\n"
            text += f"\n**Toplam:** {len(active_plugins)}"
        
        buttons = [
            [Button.inline("🔌 Tüm Plugin'ler", b"plugins_menu")],
            back_button("main_menu")
        ]
        await event.edit(text, buttons=buttons)
    
    # ==========================================
    # PLUGİN KOMUTLARI
    # ==========================================
    
    @bot.on(events.NewMessage(pattern=r'^/pinfo\s+(\S+)$'))
    async def pinfo_command(event):
        """Plugin detaylarını göster"""
        plugin_name = event.pattern_match.group(1)
        plugin = await db.get_plugin(plugin_name)
        
        if not plugin:
            await event.respond(f"❌ `{plugin_name}` bulunamadı.")
            return
        
        user_data = await db.get_user(event.sender_id)
        active_plugins = user_data.get("active_plugins", []) if user_data else []
        is_active = plugin_name in active_plugins
        
        text = f"🔌 **Plugin: `{plugin_name}`**\n\n"
        text += f"📝 **Açıklama:** {plugin.get('description') or 'Yok'}\n"
        text += f"🔓 **Erişim:** {'Genel' if plugin.get('is_public', True) else 'Özel'}\n"
        text += f"📊 **Durum:** {'🟢 Yüklü' if is_active else '⚪ Yüklü değil'}\n\n"
        
        commands = plugin.get("commands", [])
        if commands:
            text += f"🔧 **Komutlar ({len(commands)}):**\n"
            for cmd in commands:
                text += f"  • `.{cmd}`\n"
        else:
            text += "🔧 **Komutlar:** Yok\n"
        
        text += f"\n💡 **Kullanım:**\n"
        text += f"  • Yükle: `/pactive {plugin_name}`\n"
        text += f"  • Kaldır: `/pinactive {plugin_name}`"
        
        await event.respond(text)
    
    @bot.on(events.NewMessage(pattern=r'^/pactive\s+(\S+)$'))
    @check_ban
    async def pactive_command(event):
        plugin_name = event.pattern_match.group(1)
        
        user_data = await db.get_user(event.sender_id)
        if not user_data or not user_data.get("is_logged_in"):
            await event.respond("❌ Önce giriş yapmalısınız.")
            return
        
        client = userbot_manager.get_client(event.sender_id)
        if not client:
            await event.respond("❌ Userbot bağlantısı yok.")
            return
        
        msg = await event.respond("⏳ Plugin yükleniyor...")
        success, message = await plugin_manager.activate_plugin(event.sender_id, plugin_name, client)
        await msg.edit(message)
        
        if success:
            await send_log(bot, "plugin", f"Aktif: {plugin_name}", event.sender_id)
    
    @bot.on(events.NewMessage(pattern=r'^/pinactive\s+(\S+)$'))
    @check_ban
    async def pinactive_command(event):
        plugin_name = event.pattern_match.group(1)
        success, message = await plugin_manager.deactivate_plugin(event.sender_id, plugin_name)
        await event.respond(message)
        
        if success:
            await send_log(bot, "plugin", f"Deaktif: {plugin_name}", event.sender_id)
    
    @bot.on(events.NewMessage(pattern=r'^/plugins$'))
    @check_ban
    async def plugins_command(event):
        user_data = await db.get_user(event.sender_id)
        all_plugins = await db.get_all_plugins()
        active_plugins = user_data.get("active_plugins", []) if user_data else []
        
        if not all_plugins:
            await event.respond("📭 Henüz plugin eklenmemiş.")
            return
        
        text = "🔌 **Plugin Listesi:**\n\n"
        for p in all_plugins:
            status = "🟢" if p['name'] in active_plugins else "⚪"
            text += f"{status} `{p['name']}`\n"
        
        text += f"\n🟢 Yüklü | ⚪ Yüklü değil"
        text += f"\n\nDetay: `/pinfo <isim>`"
        await event.respond(text)
    
    @bot.on(events.NewMessage(pattern=r'^/cancel$'))
    async def cancel_handler(event):
        user_id = event.sender_id
        if user_id in user_states:
            del user_states[user_id]
            if user_id in userbot_manager.pending_logins:
                try: await userbot_manager.pending_logins[user_id]["client"].disconnect()
                except: pass
                del userbot_manager.pending_logins[user_id]
            await event.respond("❌ İptal edildi.", buttons=[[Button.inline("🏠 Ana Menü", b"main_menu")]])
        else:
            await event.respond("ℹ️ İptal edilecek işlem yok.")
    
    # ==========================================
    # ANA MENÜ, YARDIM, KOMUTLAR
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"main_menu"))
    async def main_menu_handler(event):
        if event.sender_id in user_states:
            del user_states[event.sender_id]
        
        user = await event.get_sender()
        user_data = await db.get_user(event.sender_id)
        is_logged_in = user_data.get("is_logged_in", False) if user_data else False
        
        text = config.MESSAGES["welcome"]
        text += f"\n\n👋 Merhaba **{user.first_name}**!"
        
        if is_logged_in:
            active_count = len(user_data.get("active_plugins", []))
            text += f"\n✅ Userbot: `{user_data.get('userbot_username', '?')}`"
            text += f"\n🔌 Aktif: `{active_count}` plugin"
        
        buttons = []
        if is_logged_in:
            buttons.append([Button.inline(config.BUTTONS["plugins"], b"plugins_menu")])
            buttons.append([Button.inline(config.BUTTONS["my_plugins"], b"my_plugins")])
            buttons.append([Button.inline(config.BUTTONS["logout"], b"logout_confirm")])
        else:
            session_data = await db.get_session(event.sender_id)
            if session_data and session_data.get("remember"):
                buttons.append([Button.inline("⚡ Hızlı Giriş", b"quick_login")])
            buttons.append([Button.inline(config.BUTTONS["login"], b"login_menu")])
        
        buttons.append([Button.inline(config.BUTTONS["help"], b"help"), 
                       Button.inline(config.BUTTONS["commands"], b"commands")])
        buttons.append([Button.url(config.BUTTONS["plugin_channel"], f"https://t.me/{config.PLUGIN_CHANNEL}")])
        
        if event.sender_id == config.OWNER_ID or await db.is_sudo(event.sender_id):
            buttons.append([Button.inline(config.BUTTONS["settings"], b"settings_menu")])
        
        await event.edit(text, buttons=buttons)
    
    @bot.on(events.CallbackQuery(data=b"help"))
    async def help_handler(event):
        text = "❓ **Yardım**\n\n"
        text += "Bu bot ile Telegram hesabınıza userbot kurabilirsiniz.\n\n"
        text += "**Nasıl Kullanılır:**\n"
        text += "1️⃣ Giriş yapın (telefon veya session)\n"
        text += "2️⃣ Plugin'ler menüsünden plugin seçin\n"
        text += "3️⃣ Plugin'i aktif edin\n"
        text += "4️⃣ Telegram'da komutları kullanın\n\n"
        text += f"**Destek:** @{config.OWNER_USERNAME}\n"
        text += f"**Sürüm:** `v{config.__version__}`"
        
        await event.edit(text, buttons=[back_button("main_menu")])
    
    @bot.on(events.CallbackQuery(data=b"commands"))
    async def commands_handler(event):
        text = "📝 **Komutlar**\n\n"
        
        text += "**👤 Kullanıcı Komutları:**\n"
        for cmd, desc in config.COMMANDS["user"].items():
            text += f"• `{cmd}` - {desc}\n"
        
        if event.sender_id == config.OWNER_ID or await db.is_sudo(event.sender_id):
            text += "\n**👑 Admin Komutları:**\n"
            for cmd, desc in config.COMMANDS["admin"].items():
                text += f"• `{cmd}` - {desc}\n"
        
        await event.edit(text, buttons=[back_button("main_menu")])
    
    @bot.on(events.CallbackQuery(data=b"close"))
    async def close_handler(event):
        await event.delete()
    
    @bot.on(events.CallbackQuery(data=b"noop"))
    async def noop_handler(event):
        await event.answer()
