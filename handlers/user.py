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
from utils.bot_api import bot_api, btn, ButtonBuilder

# State management
user_states = {}
STATE_WAITING_PHONE = "waiting_phone"
STATE_WAITING_CODE = "waiting_code"
STATE_WAITING_2FA = "waiting_2fa"
STATE_WAITING_SESSION_TELETHON = "waiting_session_telethon"
STATE_WAITING_SESSION_PYROGRAM = "waiting_session_pyrogram"

PLUGINS_PER_PAGE = 8

def register_user_handlers(bot):
    """Kullanıcı handler'larını kaydet"""
    
    # ==========================================
    # /start KOMUTU (Bot API - Renkli Butonlar)
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
        text += f"\n\n👋 Merhaba <b>{user.first_name}</b>!"
        
        if is_logged_in:
            active_count = len(user_data.get("active_plugins", []))
            text += f"\n✅ Userbot aktif: <code>{user_data.get('userbot_username', '?')}</code>"
            text += f"\n🔌 Aktif plugin: <code>{active_count}</code>"
        
        rows = []
        
        if is_logged_in:
            # Giriş yapılmış - Plugin butonları
            rows.append([
                btn.callback("🔌 Pluginler", "plugins_page_0", 
                            style=ButtonBuilder.STYLE_PRIMARY,
                            icon_custom_emoji_id=5237699328843200584)
            ])
            rows.append([
                btn.callback("📦 Pluginlerim", "my_plugins_0",
                            style=ButtonBuilder.STYLE_PRIMARY)
            ])
            rows.append([
                btn.callback("🚪 Çıkış Yap", "logout_confirm",
                            style=ButtonBuilder.STYLE_DANGER,
                            icon_custom_emoji_id=5237758235143248994)
            ])
        else:
            # Giriş yapılmamış
            session_data = await db.get_session(event.sender_id)
            if session_data and session_data.get("remember"):
                rows.append([
                    btn.callback("⚡ Hızlı Giriş", "quick_login",
                                style=ButtonBuilder.STYLE_SUCCESS,
                                icon_custom_emoji_id=5233408828313192030)
                ])
            rows.append([
                btn.callback("🔐 Giriş Yap", "login_menu",
                            style=ButtonBuilder.STYLE_SUCCESS,
                            icon_custom_emoji_id=5233408828313192030)
            ])
        
        # Yardım ve Komutlar
        rows.append([
            btn.callback("❓ Yardım", "help_main",
                        icon_custom_emoji_id=5238091390690068061),
            btn.callback("📝 Komutlar", "commands")
        ])
        
        # Plugin Kanalı
        rows.append([
            btn.url(f"📢 {config.PLUGIN_CHANNEL}", f"https://t.me/{config.PLUGIN_CHANNEL}",
                   style=ButtonBuilder.STYLE_PRIMARY)
        ])
        
        # Admin butonu
        if event.sender_id == config.OWNER_ID or await db.is_sudo(event.sender_id):
            rows.append([
                btn.callback("⚙️ Yönetim Paneli", "settings_menu",
                            style=ButtonBuilder.STYLE_DANGER,
                            icon_custom_emoji_id=5237830824684428925)
            ])
        
        # Bot API ile gönder
        await bot_api.send_message(
            chat_id=event.sender_id,
            text=text,
            reply_markup=btn.inline_keyboard(rows)
        )
    
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
        
        rows = [
            [btn.callback("📱 Telefon Numarası", "login_phone",
                         style=ButtonBuilder.STYLE_SUCCESS,
                         icon_custom_emoji_id=5233408828313192030)],
            [btn.callback("🔑 Telethon Session", "login_telethon",
                         style=ButtonBuilder.STYLE_PRIMARY)],
            [btn.callback("🔑 Pyrogram Session", "login_pyrogram",
                         style=ButtonBuilder.STYLE_PRIMARY)],
            [btn.callback("◀️ Geri", "main_menu",
                         icon_custom_emoji_id=5237707207794498594)]
        ]
        
        await bot_api.edit_message_text(
            chat_id=event.sender_id,
            message_id=event.message_id,
            text=config.MESSAGES["login_method"].replace("**", "<b>").replace("`", "<code>").replace("**", "</b>").replace("`", "</code>"),
            reply_markup=btn.inline_keyboard(rows)
        )
        await event.answer()
    
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
            [Button.inline(config.BUTTONS["plugins"], b"plugins_page_0")],
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
            [Button.inline(config.BUTTONS["plugins"], b"plugins_page_0")],
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
                [Button.inline(config.BUTTONS["plugins"], b"plugins_page_0")],
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
    # PLUGİN MENÜSÜ - SAYFALI
    # ==========================================
    
    @bot.on(events.CallbackQuery(pattern=b"plugins_page_(\d+)"))
    async def plugins_menu_handler(event):
        user_id = event.sender_id
        user_data = await db.get_user(user_id)
        
        if not user_data or not user_data.get("is_logged_in"):
            await event.answer("Önce giriş yapmalısınız", alert=True)
            return
        
        page = int(event.data.decode().split("_")[-1])
        all_plugins = await db.get_all_plugins()
        active_plugins = user_data.get("active_plugins", [])
        
        # Kullanıcının erişebileceği pluginleri filtrele
        accessible_plugins = []
        for p in all_plugins:
            if p.get("is_public", True) or user_id in p.get("allowed_users", []):
                accessible_plugins.append(p)
        
        if not accessible_plugins:
            text = "📭 **Henüz plugin eklenmemiş.**\n\nPlugin duyuruları için kanalı takip edin."
            buttons = [
                [Button.url(config.BUTTONS["plugin_channel"], f"https://t.me/{config.PLUGIN_CHANNEL}")],
                back_button("main_menu")
            ]
            await event.edit(text, buttons=buttons)
            return
        
        total_pages = (len(accessible_plugins) + PLUGINS_PER_PAGE - 1) // PLUGINS_PER_PAGE
        start_idx = page * PLUGINS_PER_PAGE
        end_idx = start_idx + PLUGINS_PER_PAGE
        page_plugins = accessible_plugins[start_idx:end_idx]
        
        text = f"🔌 **Plugin Listesi** (Sayfa {page + 1}/{total_pages})\n\n"
        
        for p in page_plugins:
            name = p['name']
            is_active = name in active_plugins
            status = "🟢" if is_active else "⚪"
            
            # Komutları göster
            cmds = p.get("commands", [])[:2]
            cmd_text = ", ".join([f"`.{c}`" for c in cmds])
            if len(p.get("commands", [])) > 2:
                cmd_text += "..."
            
            text += f"{status} **{name}**\n"
            text += f"   └ {cmd_text}\n"
            text += f"   └ Yükle: `/pactive {name}`\n\n"
        
        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        text += f"🟢 Yüklü | ⚪ Yüklü değil\n"
        text += f"📊 Toplam: **{len(accessible_plugins)}** plugin\n"
        text += f"✅ Aktif: **{len(active_plugins)}** plugin\n\n"
        text += f"💡 **Detay için:** `/pinfo <isim>`"
        
        # Sayfalama butonları
        nav_buttons = []
        if page > 0:
            nav_buttons.append(Button.inline("⬅️ Önceki", f"plugins_page_{page - 1}".encode()))
        if page < total_pages - 1:
            nav_buttons.append(Button.inline("Sonraki ➡️", f"plugins_page_{page + 1}".encode()))
        
        buttons = []
        if nav_buttons:
            buttons.append(nav_buttons)
        buttons.append([Button.inline(config.BUTTONS["my_plugins"], b"my_plugins_0")])
        buttons.append([Button.url(config.BUTTONS["plugin_channel"], f"https://t.me/{config.PLUGIN_CHANNEL}")])
        buttons.append(back_button("main_menu"))
        
        await event.edit(text, buttons=buttons)
    
    # ==========================================
    # PLUGİNLERİM - SAYFALI
    # ==========================================
    
    @bot.on(events.CallbackQuery(pattern=b"my_plugins_(\d+)"))
    async def my_plugins_handler(event):
        user_data = await db.get_user(event.sender_id)
        
        if not user_data or not user_data.get("is_logged_in"):
            await event.answer("Önce giriş yapmalısınız", alert=True)
            return
        
        page = int(event.data.decode().split("_")[-1])
        active_plugins = user_data.get("active_plugins", [])
        
        if not active_plugins:
            text = config.MESSAGES["no_active_plugins"]
            text += "\n\n💡 Plugin yüklemek için:\n"
            text += "1️⃣ Plugin listesinden birini seçin\n"
            text += "2️⃣ `/pactive <isim>` yazın"
            buttons = [
                [Button.inline("🔌 Plugin Listesi", b"plugins_page_0")],
                back_button("main_menu")
            ]
            await event.edit(text, buttons=buttons)
            return
        
        total_pages = (len(active_plugins) + PLUGINS_PER_PAGE - 1) // PLUGINS_PER_PAGE
        start_idx = page * PLUGINS_PER_PAGE
        end_idx = start_idx + PLUGINS_PER_PAGE
        page_plugins = active_plugins[start_idx:end_idx]
        
        text = f"📦 **Aktif Plugin'leriniz** (Sayfa {page + 1}/{total_pages})\n\n"
        
        for name in page_plugins:
            plugin = await db.get_plugin(name)
            if plugin:
                cmds = ", ".join([f"`.{c}`" for c in plugin.get("commands", [])])
                text += f"✅ **{name}**\n"
                text += f"   └ {cmds}\n"
                text += f"   └ Kaldır: `/pinactive {name}`\n\n"
        
        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        text += f"**Toplam:** {len(active_plugins)} aktif plugin"
        
        # Sayfalama butonları
        nav_buttons = []
        if page > 0:
            nav_buttons.append(Button.inline("⬅️ Önceki", f"my_plugins_{page - 1}".encode()))
        if page < total_pages - 1:
            nav_buttons.append(Button.inline("Sonraki ➡️", f"my_plugins_{page + 1}".encode()))
        
        buttons = []
        if nav_buttons:
            buttons.append(nav_buttons)
        buttons.append([Button.inline("🔌 Tüm Plugin'ler", b"plugins_page_0")])
        buttons.append(back_button("main_menu"))
        
        await event.edit(text, buttons=buttons)
    
    # ==========================================
    # PLUGİN KOMUTLARI
    # ==========================================
    
    @bot.on(events.NewMessage(pattern=r'^/pinfo\s+(\S+)$'))
    async def pinfo_command(event):
        plugin_name = event.pattern_match.group(1)
        plugin = await db.get_plugin(plugin_name)
        
        if not plugin:
            await event.respond(f"❌ `{plugin_name}` bulunamadı.")
            return
        
        user_data = await db.get_user(event.sender_id)
        active_plugins = user_data.get("active_plugins", []) if user_data else []
        is_active = plugin_name in active_plugins
        
        text = f"🔌 **Plugin: `{plugin_name}`**\n\n"
        text += f"📝 **Açıklama:** {plugin.get('description') or 'Açıklama yok'}\n"
        text += f"🔓 **Erişim:** {'Genel' if plugin.get('is_public', True) else 'Özel'}\n"
        text += f"📊 **Durum:** {'🟢 Yüklü' if is_active else '⚪ Yüklü değil'}\n\n"
        
        commands = plugin.get("commands", [])
        if commands:
            text += f"🔧 **Komutlar ({len(commands)}):**\n"
            for cmd in commands:
                text += f"  • `.{cmd}`\n"
        else:
            text += "🔧 **Komutlar:** Yok\n"
        
        text += f"\n━━━━━━━━━━━━━━━━━━━━\n"
        text += f"💡 **Hızlı Kullanım:**\n"
        if is_active:
            text += f"  • Kaldır: `/pinactive {plugin_name}`"
        else:
            text += f"  • Yükle: `/pactive {plugin_name}`"
        
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
        for p in all_plugins[:10]:
            status = "🟢" if p['name'] in active_plugins else "⚪"
            text += f"{status} `{p['name']}` → `/pactive {p['name']}`\n"
        
        if len(all_plugins) > 10:
            text += f"\n... ve {len(all_plugins) - 10} plugin daha"
        
        text += f"\n\n🟢 Yüklü | ⚪ Yüklü değil"
        text += f"\n📊 Detay: `/pinfo <isim>`"
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
    # ANA MENÜ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"main_menu"))
    async def main_menu_handler(event):
        if event.sender_id in user_states:
            del user_states[event.sender_id]
        
        user = await event.get_sender()
        user_data = await db.get_user(event.sender_id)
        is_logged_in = user_data.get("is_logged_in", False) if user_data else False
        
        text = config.MESSAGES["welcome"].replace("**", "<b>").replace("**", "</b>").replace("`", "<code>").replace("`", "</code>")
        text += f"\n\n👋 Merhaba <b>{user.first_name}</b>!"
        
        if is_logged_in:
            active_count = len(user_data.get("active_plugins", []))
            text += f"\n✅ Userbot: <code>{user_data.get('userbot_username', '?')}</code>"
            text += f"\n🔌 Aktif: <code>{active_count}</code> plugin"
        
        rows = []
        
        if is_logged_in:
            rows.append([
                btn.callback("🔌 Pluginler", "plugins_page_0", 
                            style=ButtonBuilder.STYLE_PRIMARY,
                            icon_custom_emoji_id=5237699328843200584)
            ])
            rows.append([
                btn.callback("📦 Pluginlerim", "my_plugins_0",
                            style=ButtonBuilder.STYLE_PRIMARY)
            ])
            rows.append([
                btn.callback("🚪 Çıkış Yap", "logout_confirm",
                            style=ButtonBuilder.STYLE_DANGER,
                            icon_custom_emoji_id=5237758235143248994)
            ])
        else:
            session_data = await db.get_session(event.sender_id)
            if session_data and session_data.get("remember"):
                rows.append([
                    btn.callback("⚡ Hızlı Giriş", "quick_login",
                                style=ButtonBuilder.STYLE_SUCCESS,
                                icon_custom_emoji_id=5233408828313192030)
                ])
            rows.append([
                btn.callback("🔐 Giriş Yap", "login_menu",
                            style=ButtonBuilder.STYLE_SUCCESS,
                            icon_custom_emoji_id=5233408828313192030)
            ])
        
        rows.append([
            btn.callback("❓ Yardım", "help_main",
                        icon_custom_emoji_id=5238091390690068061),
            btn.callback("📝 Komutlar", "commands")
        ])
        
        rows.append([
            btn.url(f"📢 {config.PLUGIN_CHANNEL}", f"https://t.me/{config.PLUGIN_CHANNEL}",
                   style=ButtonBuilder.STYLE_PRIMARY)
        ])
        
        if event.sender_id == config.OWNER_ID or await db.is_sudo(event.sender_id):
            rows.append([
                btn.callback("⚙️ Yönetim Paneli", "settings_menu",
                            style=ButtonBuilder.STYLE_DANGER,
                            icon_custom_emoji_id=5237830824684428925)
            ])
        
        await bot_api.edit_message_text(
            chat_id=event.sender_id,
            message_id=event.message_id,
            text=text,
            reply_markup=btn.inline_keyboard(rows)
        )
        await event.answer()
    
    # ==========================================
    # YARDIM MENÜSÜ - DETAYLI
    # ==========================================
    
    @bot.on(events.NewMessage(pattern=r'^/help$'))
    @check_ban
    async def help_command(event):
        """Help komutu - yardım menüsünü açar"""
        text, buttons = await get_help_main_content(event.sender_id)
        await event.respond(text, buttons=buttons)
    
    async def get_help_main_content(user_id):
        """Ana yardım menüsü içeriği"""
        text = "❓ **Yardım Merkezi**\n\n"
        text += "Hoş geldiniz! Bu bot ile Telegram hesabınıza\n"
        text += "**Userbot** kurarak ek özellikler kazanabilirsiniz.\n\n"
        text += "📚 **Konu Seçin:**"
        
        buttons = [
            [Button.inline("🤖 Userbot Nedir?", b"help_what")],
            [Button.inline("🔐 Nasıl Giriş Yapılır?", b"help_login")],
            [Button.inline("🔌 Plugin Nedir?", b"help_plugins")],
            [Button.inline("⚙️ Komutlar Nasıl Kullanılır?", b"help_commands")],
            [Button.inline("❓ Sıkça Sorulan Sorular", b"help_faq")],
            back_button("main_menu")
        ]
        
        return text, buttons
    
    @bot.on(events.CallbackQuery(data=b"help_main"))
    async def help_main_handler(event):
        text, buttons = await get_help_main_content(event.sender_id)
        await event.edit(text, buttons=buttons)
    
    @bot.on(events.CallbackQuery(data=b"help_what"))
    async def help_what_handler(event):
        text = "🤖 **Userbot Nedir?**\n\n"
        text += "Userbot, Telegram hesabınızda çalışan bir bottur.\n"
        text += "Normal botlardan farklı olarak **sizin hesabınızla**\n"
        text += "işlem yapar.\n\n"
        
        text += "📌 **Ne İşe Yarar?**\n"
        text += "• Mesajları otomatik yanıtlama\n"
        text += "• Medya indirme (YouTube, Instagram vb.)\n"
        text += "• Çeviri yapma\n"
        text += "• AFK (meşgul) modu\n"
        text += "• Ve daha fazlası...\n\n"
        
        text += "⚠️ **Önemli:**\n"
        text += "Userbot sizin hesabınızla çalıştığı için\n"
        text += "komutları kendinize yazarsınız. Örneğin\n"
        text += "`.afk` yazıp gönderdiğinizde AFK moduna geçersiniz."
        
        await event.edit(text, buttons=[[Button.inline("🔙 Geri", b"help_main")]])
    
    @bot.on(events.CallbackQuery(data=b"help_login"))
    async def help_login_handler(event):
        text = "🔐 **Nasıl Giriş Yapılır?**\n\n"
        text += "Userbot kullanmak için hesabınızla giriş yapmalısınız.\n"
        text += "3 farklı yöntem vardır:\n\n"
        
        text += "📱 **1. Telefon Numarası (Önerilen)**\n"
        text += "• `🔐 Giriş Yap` butonuna tıklayın\n"
        text += "• `📱 Telefon Numarası` seçin\n"
        text += "• Numaranızı girin: `+905551234567`\n"
        text += "• Telegram'dan gelen kodu girin\n"
        text += "• 2FA varsa şifrenizi girin\n\n"
        
        text += "📄 **2. Session String**\n"
        text += "• Daha önce oluşturduğunuz session'ı\n"
        text += "  yapıştırarak giriş yapabilirsiniz\n"
        text += "• Telethon veya Pyrogram desteklenir\n\n"
        
        text += "💾 **Oturum Kaydetme:**\n"
        text += "Giriş sonrası oturumu kaydederseniz,\n"
        text += "bir dahaki sefere tek tıkla giriş yapabilirsiniz."
        
        await event.edit(text, buttons=[[Button.inline("🔙 Geri", b"help_main")]])
    
    @bot.on(events.CallbackQuery(data=b"help_plugins"))
    async def help_plugins_handler(event):
        text = "🔌 **Plugin Nedir & Nasıl Yüklenir?**\n\n"
        text += "Plugin'ler userbot'a özellik ekleyen eklentilerdir.\n"
        text += "Her plugin farklı komutlar sunar.\n\n"
        
        text += "📥 **Plugin Yükleme:**\n"
        text += "1️⃣ `🔌 Plugin'ler` menüsüne gidin\n"
        text += "2️⃣ İstediğiniz plugini bulun\n"
        text += "3️⃣ `/pactive <isim>` yazın\n"
        text += "   Örnek: `/pactive ses`\n\n"
        
        text += "📤 **Plugin Kaldırma:**\n"
        text += "• `/pinactive <isim>` yazın\n"
        text += "   Örnek: `/pinactive ses`\n\n"
        
        text += "ℹ️ **Plugin Bilgisi:**\n"
        text += "• `/pinfo <isim>` ile detayları görün\n"
        text += "   Örnek: `/pinfo ses`\n\n"
        
        text += "📢 **Yeni Plugin'ler:**\n"
        text += "Plugin kanalımızı takip ederek yeni\n"
        text += "plugin duyurularından haberdar olun!"
        
        await event.edit(text, buttons=[
            [Button.url("📢 Plugin Kanalı", f"https://t.me/{config.PLUGIN_CHANNEL}")],
            [Button.inline("🔙 Geri", b"help_main")]
        ])
    
    @bot.on(events.CallbackQuery(data=b"help_commands"))
    async def help_commands_handler(event):
        text = "⚙️ **Komutlar Nasıl Kullanılır?**\n\n"
        
        text += "🤖 **Bot Komutları (Bu botta):**\n"
        text += "Bot komutları `/` ile başlar ve\n"
        text += "bu bota yazılır.\n\n"
        text += "Örnekler:\n"
        text += "• `/start` - Ana menü\n"
        text += "• `/pactive ses` - Plugin yükle\n"
        text += "• `/pinfo afk` - Plugin bilgisi\n\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        text += "⚡ **Userbot Komutları (Telegram'da):**\n"
        text += "Userbot komutları `.` ile başlar ve\n"
        text += "**herhangi bir sohbete** yazılır.\n\n"
        text += "Örnekler:\n"
        text += "• `.afk Meşgulüm` - AFK modu aç\n"
        text += "• `.tts Merhaba` - Sesli mesaj\n"
        text += "• `.tr Hello` - Çeviri yap\n\n"
        
        text += "💡 **İpucu:**\n"
        text += "Userbot komutlarını kendinize (Kayıtlı\n"
        text += "Mesajlar) yazarak test edebilirsiniz."
        
        await event.edit(text, buttons=[[Button.inline("🔙 Geri", b"help_main")]])
    
    @bot.on(events.CallbackQuery(data=b"help_faq"))
    async def help_faq_handler(event):
        text = "❓ **Sıkça Sorulan Sorular**\n\n"
        
        text += "**S: Hesabım yasaklanır mı?**\n"
        text += "C: Normal kullanımda risk düşüktür.\n"
        text += "Spam yapmayın, çok hızlı mesaj atmayın.\n\n"
        
        text += "**S: Şifremi veriyor muyum?**\n"
        text += "C: Hayır! Sadece Telegram'ın gönderdiği\n"
        text += "doğrulama kodunu giriyorsunuz.\n\n"
        
        text += "**S: Birisi hesabıma erişebilir mi?**\n"
        text += "C: Session'ınız şifreli saklanır.\n"
        text += "Çıkış yapınca silinir.\n\n"
        
        text += "**S: Plugin çalışmıyor?**\n"
        text += "C: Önce giriş yaptığınızdan emin olun.\n"
        text += "Sonra plugini yeniden yükleyin.\n\n"
        
        text += "**S: Komut yazdım ama olmuyor?**\n"
        text += "C: Userbot komutları `.` ile başlar\n"
        text += "ve Telegram'da yazılır, bu botta değil.\n\n"
        
        text += f"📞 **Destek:** @{config.OWNER_USERNAME}"
        
        await event.edit(text, buttons=[[Button.inline("🔙 Geri", b"help_main")]])
    
    @bot.on(events.CallbackQuery(data=b"commands"))
    async def commands_handler(event):
        text = "📝 **Bot Komutları**\n\n"
        
        text += "**👤 Genel Komutlar:**\n"
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
