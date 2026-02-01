# ============================================
# KingTG UserBot Service - User Handlers
# ============================================

from telethon import events, Button
from telethon.tl.custom import Message
import config
from database import database as db
from userbot import userbot_manager, plugin_manager
from utils import (
    check_ban, check_private_mode, check_maintenance, 
    register_user, send_log, get_readable_time,
    is_valid_phone, is_valid_session_string,
    back_button, close_button, yes_no_buttons
)

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
        """Başlangıç komutu"""
        user = await event.get_sender()
        user_data = await db.get_user(event.sender_id)
        
        # Kullanıcı giriş yapmış mı?
        is_logged_in = user_data.get("is_logged_in", False) if user_data else False
        
        text = config.MESSAGES["welcome"]
        text += f"\n\n👋 Merhaba **{user.first_name}**!"
        
        if is_logged_in:
            text += f"\n✅ Userbot aktif: `{user_data.get('userbot_username', 'Bilinmiyor')}`"
        
        buttons = []
        
        if is_logged_in:
            buttons.append([Button.inline(config.BUTTONS["plugins"], b"plugins_menu")])
            buttons.append([Button.inline(config.BUTTONS["my_plugins"], b"my_plugins")])
            buttons.append([Button.inline(config.BUTTONS["logout"], b"logout_confirm")])
        else:
            # Kaydedilmiş session var mı?
            session_data = await db.get_session(event.sender_id)
            if session_data and session_data.get("remember"):
                buttons.append([Button.inline("⚡ Hızlı Giriş", b"quick_login")])
            buttons.append([Button.inline(config.BUTTONS["login"], b"login_menu")])
        
        buttons.append([Button.inline(config.BUTTONS["help"], b"help")])
        
        # Owner/Sudo için ayarlar butonu
        if event.sender_id == config.OWNER_ID or await db.is_sudo(event.sender_id):
            buttons.append([Button.inline(config.BUTTONS["settings"], b"settings_menu")])
        
        await event.respond(text, buttons=buttons)
    
    # ==========================================
    # GİRİŞ MENÜSÜ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"login_menu"))
    @check_ban
    @check_maintenance
    @check_private_mode
    async def login_menu_handler(event):
        """Giriş yöntemi seçimi"""
        text = config.MESSAGES["login_method"]
        
        buttons = [
            [Button.inline(config.BUTTONS["phone"], b"login_phone")],
            [Button.inline(config.BUTTONS["telethon_session"], b"login_telethon")],
            [Button.inline(config.BUTTONS["pyrogram_session"], b"login_pyrogram")],
            back_button("main_menu")
        ]
        
        await event.edit(text, buttons=buttons)
    
    # ==========================================
    # TELEFON İLE GİRİŞ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"login_phone"))
    async def login_phone_start(event):
        """Telefon ile giriş başlat"""
        text = config.MESSAGES["login_phone"]
        
        # Conversation başlat
        async with bot.conversation(event.chat_id) as conv:
            await event.edit(text, buttons=[back_button("login_menu")])
            
            try:
                response = await conv.get_response(timeout=120)
                phone = response.text.strip()
                
                if not is_valid_phone(phone):
                    await event.respond("❌ Geçersiz telefon numarası formatı.\n\nÖrnek: `+905551234567`")
                    return
                
                await response.delete()
                msg = await event.respond("⏳ Kod gönderiliyor...")
                
                result = await userbot_manager.start_phone_login(event.sender_id, phone)
                
                if not result["success"]:
                    if result.get("error") == "flood_wait":
                        await msg.edit(config.MESSAGES["error_flood"].format(seconds=result["seconds"]))
                    else:
                        await msg.edit(config.MESSAGES["login_failed"].format(error=result["error"]))
                    return
                
                # Kod bekleme
                await msg.edit(config.MESSAGES["login_code"])
                
                code_response = await conv.get_response(timeout=300)
                code = code_response.text.strip().replace(" ", "")
                await code_response.delete()
                
                await msg.edit("⏳ Doğrulanıyor...")
                
                verify_result = await userbot_manager.verify_code(event.sender_id, code)
                
                if verify_result.get("stage") == "2fa":
                    # 2FA gerekli
                    await msg.edit(config.MESSAGES["login_2fa"])
                    
                    password_response = await conv.get_response(timeout=120)
                    password = password_response.text.strip()
                    await password_response.delete()
                    
                    await msg.edit("⏳ 2FA doğrulanıyor...")
                    
                    verify_result = await userbot_manager.verify_2fa(event.sender_id, password)
                
                if verify_result["success"]:
                    user_info = verify_result["user_info"]
                    session_string = verify_result["session_string"]
                    
                    # Kaydet
                    await db.update_user(event.sender_id, {
                        "is_logged_in": True,
                        "userbot_id": user_info["id"],
                        "userbot_username": user_info["username"]
                    })
                    
                    # Beni hatırla sorusu
                    await msg.edit(
                        config.MESSAGES["login_success"].format(
                            name=user_info["first_name"],
                            user_id=user_info["id"]
                        ) + "\n\n" + config.MESSAGES["login_remember"],
                        buttons=[
                            [
                                Button.inline(config.BUTTONS["remember_yes"], f"save_session_{phone}".encode()),
                                Button.inline(config.BUTTONS["remember_no"], b"dont_save_session")
                            ]
                        ]
                    )
                    
                    # Geçici olarak session'ı sakla
                    bot.session_temp = {
                        event.sender_id: {
                            "session": session_string,
                            "phone": phone,
                            "type": "phone"
                        }
                    }
                    
                    await send_log(
                        bot, "login",
                        f"Yeni giriş (Telefon)\n"
                        f"Userbot: @{user_info['username']} ({user_info['id']})",
                        event.sender_id
                    )
                else:
                    error = verify_result.get("error", "Bilinmeyen hata")
                    error_messages = {
                        "invalid_code": "Geçersiz kod",
                        "code_expired": "Kodun süresi doldu",
                        "invalid_password": "Yanlış 2FA şifresi"
                    }
                    await msg.edit(config.MESSAGES["login_failed"].format(
                        error=error_messages.get(error, error)
                    ))
                    
            except TimeoutError:
                await event.respond(config.MESSAGES["error_timeout"])
    
    # ==========================================
    # SESSION İLE GİRİŞ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"login_telethon"))
    async def login_telethon_start(event):
        """Telethon session ile giriş"""
        await session_login_flow(event, "telethon")
    
    @bot.on(events.CallbackQuery(data=b"login_pyrogram"))
    async def login_pyrogram_start(event):
        """Pyrogram session ile giriş"""
        await session_login_flow(event, "pyrogram")
    
    async def session_login_flow(event, session_type: str):
        """Session giriş akışı"""
        if session_type == "telethon":
            text = config.MESSAGES["login_session_telethon"]
        else:
            text = config.MESSAGES["login_session_pyrogram"]
        
        async with bot.conversation(event.chat_id) as conv:
            await event.edit(text, buttons=[back_button("login_menu")])
            
            try:
                response = await conv.get_response(timeout=120)
                session_string = response.text.strip()
                await response.delete()
                
                msg = await event.respond("⏳ Session doğrulanıyor...")
                
                result = await userbot_manager.login_with_session(
                    event.sender_id, 
                    session_string, 
                    session_type
                )
                
                if result["success"]:
                    user_info = result["user_info"]
                    
                    await db.update_user(event.sender_id, {
                        "is_logged_in": True,
                        "userbot_id": user_info["id"],
                        "userbot_username": user_info["username"]
                    })
                    
                    await msg.edit(
                        config.MESSAGES["login_success"].format(
                            name=user_info["first_name"],
                            user_id=user_info["id"]
                        ) + "\n\n" + config.MESSAGES["login_remember"],
                        buttons=[
                            [
                                Button.inline(config.BUTTONS["remember_yes"], b"save_session_direct"),
                                Button.inline(config.BUTTONS["remember_no"], b"dont_save_session")
                            ]
                        ]
                    )
                    
                    # Geçici olarak session'ı sakla
                    if not hasattr(bot, 'session_temp'):
                        bot.session_temp = {}
                    bot.session_temp[event.sender_id] = {
                        "session": session_string,
                        "phone": None,
                        "type": session_type
                    }
                    
                    await send_log(
                        bot, "login",
                        f"Yeni giriş ({session_type.title()} Session)\n"
                        f"Userbot: @{user_info['username']} ({user_info['id']})",
                        event.sender_id
                    )
                else:
                    error = result.get("error", "Bilinmeyen hata")
                    error_messages = {
                        "invalid_session": "Geçersiz session string",
                        "session_terminated": "Session sonlandırılmış",
                        "account_banned": "Hesap yasaklı"
                    }
                    await msg.edit(config.MESSAGES["login_failed"].format(
                        error=error_messages.get(error, error)
                    ))
                    
            except TimeoutError:
                await event.respond(config.MESSAGES["error_timeout"])
    
    # ==========================================
    # SESSION KAYDETME
    # ==========================================
    
    @bot.on(events.CallbackQuery(pattern=b"save_session_.*"))
    async def save_session_handler(event):
        """Session'ı kaydet"""
        if not hasattr(bot, 'session_temp') or event.sender_id not in bot.session_temp:
            await event.answer("⚠️ Session bulunamadı", alert=True)
            return
        
        temp_data = bot.session_temp[event.sender_id]
        
        await db.save_session(
            event.sender_id,
            temp_data["session"],
            temp_data["type"],
            temp_data.get("phone"),
            remember=True
        )
        
        del bot.session_temp[event.sender_id]
        
        await event.edit(
            "✅ **Giriş tamamlandı ve session kaydedildi!**\n\n"
            "Artık plugin'leri kullanabilirsiniz.",
            buttons=[
                [Button.inline(config.BUTTONS["plugins"], b"plugins_menu")],
                [Button.inline("🏠 Ana Menü", b"main_menu")]
            ]
        )
    
    @bot.on(events.CallbackQuery(data=b"dont_save_session"))
    async def dont_save_session_handler(event):
        """Session'ı kaydetme"""
        if hasattr(bot, 'session_temp') and event.sender_id in bot.session_temp:
            temp_data = bot.session_temp[event.sender_id]
            
            await db.save_session(
                event.sender_id,
                temp_data["session"],
                temp_data["type"],
                temp_data.get("phone"),
                remember=False
            )
            
            del bot.session_temp[event.sender_id]
        
        await event.edit(
            "✅ **Giriş tamamlandı!**\n\n"
            "Session kaydedilmedi. Bir sonraki girişte tekrar bilgi girmeniz gerekecek.",
            buttons=[
                [Button.inline(config.BUTTONS["plugins"], b"plugins_menu")],
                [Button.inline("🏠 Ana Menü", b"main_menu")]
            ]
        )
    
    # ==========================================
    # HIZLI GİRİŞ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"quick_login"))
    async def quick_login_handler(event):
        """Kaydedilmiş session ile hızlı giriş"""
        session_data = await db.get_session(event.sender_id)
        
        if not session_data or not session_data.get("data"):
            await event.answer("⚠️ Kaydedilmiş session bulunamadı", alert=True)
            return
        
        await event.edit("⏳ Giriş yapılıyor...")
        
        result = await userbot_manager.login_with_session(
            event.sender_id,
            session_data["data"],
            session_data.get("type", "telethon")
        )
        
        if result["success"]:
            user_info = result["user_info"]
            
            await db.update_user(event.sender_id, {
                "is_logged_in": True,
                "userbot_id": user_info["id"],
                "userbot_username": user_info["username"]
            })
            
            # Eski pluginleri geri yükle
            client = userbot_manager.get_client(event.sender_id)
            if client:
                restored = await plugin_manager.restore_user_plugins(event.sender_id, client)
            else:
                restored = 0
            
            text = config.MESSAGES["login_success"].format(
                name=user_info["first_name"],
                user_id=user_info["id"]
            )
            
            if restored > 0:
                text += f"\n\n🔌 {restored} plugin geri yüklendi."
            
            await event.edit(
                text,
                buttons=[
                    [Button.inline(config.BUTTONS["plugins"], b"plugins_menu")],
                    [Button.inline("🏠 Ana Menü", b"main_menu")]
                ]
            )
            
            await send_log(bot, "login", f"Hızlı giriş\nUserbot: @{user_info['username']}", event.sender_id)
        else:
            # Session geçersiz, temizle
            await db.clear_session(event.sender_id, keep_data=False)
            
            await event.edit(
                "❌ Kaydedilmiş session geçersiz.\n\n"
                "Lütfen yeniden giriş yapın.",
                buttons=[
                    [Button.inline(config.BUTTONS["login"], b"login_menu")],
                    [Button.inline("🏠 Ana Menü", b"main_menu")]
                ]
            )
    
    # ==========================================
    # ÇIKIŞ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"logout_confirm"))
    async def logout_confirm_handler(event):
        """Çıkış onayı"""
        await event.edit(
            config.MESSAGES["logout_confirm"],
            buttons=[
                [
                    Button.inline(config.BUTTONS["keep_data"], b"logout_keep"),
                    Button.inline(config.BUTTONS["delete_data"], b"logout_delete")
                ],
                back_button("main_menu")
            ]
        )
    
    @bot.on(events.CallbackQuery(pattern=b"logout_(keep|delete)"))
    async def logout_handler(event):
        """Çıkış işlemi"""
        keep_data = event.data == b"logout_keep"
        
        await event.edit("⏳ Çıkış yapılıyor...")
        
        # Userbot'u kapat
        await userbot_manager.logout(event.sender_id)
        
        # Pluginleri temizle
        plugin_manager.clear_user_plugins(event.sender_id)
        
        # Veritabanını güncelle
        await db.clear_session(event.sender_id, keep_data=keep_data)
        
        text = config.MESSAGES["logout_success"]
        if keep_data:
            text += "\n\n💾 Bilgileriniz saklandı. Hızlı giriş yapabilirsiniz."
        else:
            text += "\n\n🗑️ Tüm bilgileriniz silindi."
        
        await event.edit(
            text,
            buttons=[[Button.inline("🏠 Ana Menü", b"main_menu")]]
        )
        
        await send_log(bot, "logout", f"Çıkış yapıldı (Veri sakla: {keep_data})", event.sender_id)
    
    # ==========================================
    # PLUGİN MENÜSÜ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"plugins_menu"))
    async def plugins_menu_handler(event):
        """Plugin menüsü"""
        user_data = await db.get_user(event.sender_id)
        
        if not user_data or not user_data.get("is_logged_in"):
            await event.answer("⚠️ Önce giriş yapmalısınız", alert=True)
            return
        
        text = await plugin_manager.get_all_plugins_formatted(event.sender_id)
        text += "\n\n📌 Aktif etmek için: `/pactive <isim>`\n"
        text += "📌 Deaktif etmek için: `/pinactive <isim>`"
        
        buttons = [
            [Button.inline(config.BUTTONS["my_plugins"], b"my_plugins")],
            back_button("main_menu")
        ]
        
        await event.edit(text, buttons=buttons)
    
    @bot.on(events.CallbackQuery(data=b"my_plugins"))
    async def my_plugins_handler(event):
        """Kullanıcının aktif pluginleri"""
        user_data = await db.get_user(event.sender_id)
        
        if not user_data or not user_data.get("is_logged_in"):
            await event.answer("⚠️ Önce giriş yapmalısınız", alert=True)
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
                    text += f"✅ `{name}` - {cmds}\n"
            text += f"\n**Toplam:** {len(active_plugins)} aktif plugin"
        
        buttons = [
            [Button.inline("🔌 Tüm Plugin'ler", b"plugins_menu")],
            back_button("main_menu")
        ]
        
        await event.edit(text, buttons=buttons)
    
    # ==========================================
    # PLUGİN KOMUTLARI
    # ==========================================
    
    @bot.on(events.NewMessage(pattern=r'^/pactive\s+(\S+)$'))
    @check_ban
    @check_maintenance
    async def pactive_command(event):
        """Plugin aktif et"""
        plugin_name = event.pattern_match.group(1)
        
        user_data = await db.get_user(event.sender_id)
        if not user_data or not user_data.get("is_logged_in"):
            await event.respond(config.MESSAGES["not_registered"])
            return
        
        client = userbot_manager.get_client(event.sender_id)
        if not client:
            await event.respond("❌ Userbot bağlantısı bulunamadı. Lütfen yeniden giriş yapın.")
            return
        
        success, message = await plugin_manager.activate_plugin(
            event.sender_id, 
            plugin_name, 
            client
        )
        
        await event.respond(message)
        
        if success:
            await send_log(bot, "plugin", f"Plugin aktif: {plugin_name}", event.sender_id)
    
    @bot.on(events.NewMessage(pattern=r'^/pinactive\s+(\S+)$'))
    @check_ban
    async def pinactive_command(event):
        """Plugin deaktif et"""
        plugin_name = event.pattern_match.group(1)
        
        success, message = await plugin_manager.deactivate_plugin(
            event.sender_id, 
            plugin_name
        )
        
        await event.respond(message)
        
        if success:
            await send_log(bot, "plugin", f"Plugin deaktif: {plugin_name}", event.sender_id)
    
    @bot.on(events.NewMessage(pattern=r'^/plugins$'))
    @check_ban
    @check_maintenance
    async def plugins_command(event):
        """Plugin listesi"""
        user_data = await db.get_user(event.sender_id)
        
        text = await plugin_manager.get_all_plugins_formatted(event.sender_id)
        
        if user_data and user_data.get("is_logged_in"):
            active = user_data.get("active_plugins", [])
            if active:
                text += f"\n\n✅ **Aktif plugin'leriniz:** {', '.join([f'`{p}`' for p in active])}"
        
        await event.respond(text)
    
    # ==========================================
    # ANA MENÜ VE YARDIM
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"main_menu"))
    async def main_menu_handler(event):
        """Ana menüye dön"""
        # Start komutunu simüle et
        user = await event.get_sender()
        user_data = await db.get_user(event.sender_id)
        
        is_logged_in = user_data.get("is_logged_in", False) if user_data else False
        
        text = config.MESSAGES["welcome"]
        text += f"\n\n👋 Merhaba **{user.first_name}**!"
        
        if is_logged_in:
            text += f"\n✅ Userbot aktif: `{user_data.get('userbot_username', 'Bilinmiyor')}`"
        
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
        
        buttons.append([Button.inline(config.BUTTONS["help"], b"help")])
        
        if event.sender_id == config.OWNER_ID or await db.is_sudo(event.sender_id):
            buttons.append([Button.inline(config.BUTTONS["settings"], b"settings_menu")])
        
        await event.edit(text, buttons=buttons)
    
    @bot.on(events.CallbackQuery(data=b"help"))
    async def help_handler(event):
        """Yardım menüsü"""
        text = "❓ **Yardım**\n\n"
        text += "**Kullanıcı Komutları:**\n"
        text += "• `/start` - Ana menü\n"
        text += "• `/plugins` - Plugin listesi\n"
        text += "• `/pactive <isim>` - Plugin aktif et\n"
        text += "• `/pinactive <isim>` - Plugin deaktif et\n\n"
        text += "**Giriş Yöntemleri:**\n"
        text += "• 📱 Telefon numarası\n"
        text += "• 📄 Telethon Session String\n"
        text += "• 📄 Pyrogram Session String\n\n"
        text += f"**Destek:** @{config.OWNER_USERNAME}\n"
        text += f"**Sürüm:** `v{config.__version__}`"
        
        await event.edit(text, buttons=[back_button("main_menu")])
    
    @bot.on(events.CallbackQuery(data=b"close"))
    async def close_handler(event):
        """Mesajı sil"""
        await event.delete()
    
    @bot.on(events.CallbackQuery(data=b"noop"))
    async def noop_handler(event):
        """Hiçbir şey yapma"""
        await event.answer()
