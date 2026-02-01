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

# Kullanıcı durumları (state management)
user_states = {}

# State sabitleri
STATE_NONE = None
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
        """Başlangıç komutu"""
        # Kullanıcı state'ini temizle
        if event.sender_id in user_states:
            del user_states[event.sender_id]
        
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
        
        await event.respond(text, buttons=buttons)
    
    # ==========================================
    # MESAJ HANDLER (State-based)
    # ==========================================
    
    @bot.on(events.NewMessage(func=lambda e: e.is_private and not e.text.startswith('/')))
    async def message_handler(event):
        """Kullanıcı mesajlarını state'e göre işle"""
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
    # GİRİŞ MENÜSÜ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"login_menu"))
    @check_ban
    @check_maintenance
    @check_private_mode
    async def login_menu_handler(event):
        """Giriş yöntemi seçimi"""
        # State temizle
        if event.sender_id in user_states:
            del user_states[event.sender_id]
        
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
        user_id = event.sender_id
        
        # State ayarla
        user_states[user_id] = {
            "state": STATE_WAITING_PHONE,
            "message_id": event.message_id
        }
        
        text = config.MESSAGES["login_phone"]
        text += "\n\n⚠️ **İptal etmek için:** /cancel"
        
        await event.edit(text, buttons=[
            [Button.inline("❌ İptal", b"login_menu")]
        ])
    
    async def handle_phone_input(event, bot):
        """Telefon numarası girişini işle"""
        user_id = event.sender_id
        phone = event.text.strip()
        
        if not is_valid_phone(phone):
            await event.respond(
                "❌ Geçersiz telefon numarası formatı.\n\n"
                "✅ Örnek: `+905551234567`\n\n"
                "Tekrar deneyin veya /cancel yazın."
            )
            return
        
        # Mesajı sil (gizlilik için)
        try:
            await event.delete()
        except:
            pass
        
        msg = await bot.send_message(user_id, "⏳ Doğrulama kodu gönderiliyor...")
        
        result = await userbot_manager.start_phone_login(user_id, phone)
        
        if not result["success"]:
            if result.get("error") == "flood_wait":
                await msg.edit(
                    config.MESSAGES["error_flood"].format(seconds=result["seconds"]),
                    buttons=[[Button.inline("🔙 Geri", b"login_menu")]]
                )
            else:
                await msg.edit(
                    config.MESSAGES["login_failed"].format(error=result["error"]),
                    buttons=[[Button.inline("🔙 Geri", b"login_menu")]]
                )
            
            if user_id in user_states:
                del user_states[user_id]
            return
        
        # State güncelle
        user_states[user_id] = {
            "state": STATE_WAITING_CODE,
            "phone": phone,
            "message_id": msg.id
        }
        
        await msg.edit(
            config.MESSAGES["login_code"] + "\n\n⚠️ **İptal etmek için:** /cancel",
            buttons=[[Button.inline("❌ İptal", b"login_menu")]]
        )
    
    async def handle_code_input(event, bot):
        """Doğrulama kodu girişini işle"""
        user_id = event.sender_id
        code = event.text.strip().replace(" ", "").replace("-", "")
        
        # Mesajı sil
        try:
            await event.delete()
        except:
            pass
        
        msg = await bot.send_message(user_id, "⏳ Kod doğrulanıyor...")
        
        result = await userbot_manager.verify_code(user_id, code)
        
        if result.get("stage") == "2fa":
            # 2FA gerekli
            user_states[user_id]["state"] = STATE_WAITING_2FA
            user_states[user_id]["message_id"] = msg.id
            
            await msg.edit(
                config.MESSAGES["login_2fa"] + "\n\n⚠️ **İptal etmek için:** /cancel",
                buttons=[[Button.inline("❌ İptal", b"login_menu")]]
            )
            return
        
        if result["success"]:
            await handle_login_success(event, bot, result, msg)
        else:
            error = result.get("error", "Bilinmeyen hata")
            error_messages = {
                "invalid_code": "Geçersiz kod. Tekrar deneyin.",
                "code_expired": "Kodun süresi doldu. Baştan başlayın.",
                "no_pending_login": "Giriş işlemi bulunamadı. Baştan başlayın."
            }
            
            if error == "code_expired" or error == "no_pending_login":
                if user_id in user_states:
                    del user_states[user_id]
                await msg.edit(
                    f"❌ {error_messages.get(error, error)}",
                    buttons=[[Button.inline("🔙 Geri", b"login_menu")]]
                )
            else:
                await msg.edit(
                    f"❌ {error_messages.get(error, error)}\n\nTekrar deneyin:",
                    buttons=[[Button.inline("❌ İptal", b"login_menu")]]
                )
    
    async def handle_2fa_input(event, bot):
        """2FA şifre girişini işle"""
        user_id = event.sender_id
        password = event.text.strip()
        
        # Mesajı sil
        try:
            await event.delete()
        except:
            pass
        
        msg = await bot.send_message(user_id, "⏳ 2FA doğrulanıyor...")
        
        result = await userbot_manager.verify_2fa(user_id, password)
        
        if result["success"]:
            await handle_login_success(event, bot, result, msg)
        else:
            error = result.get("error", "Bilinmeyen hata")
            if error == "invalid_password":
                await msg.edit(
                    "❌ Yanlış şifre. Tekrar deneyin:",
                    buttons=[[Button.inline("❌ İptal", b"login_menu")]]
                )
            else:
                if user_id in user_states:
                    del user_states[user_id]
                await msg.edit(
                    f"❌ Hata: {error}",
                    buttons=[[Button.inline("🔙 Geri", b"login_menu")]]
                )
    
    async def handle_login_success(event, bot, result, msg):
        """Başarılı giriş işle"""
        user_id = event.sender_id
        user_info = result["user_info"]
        session_string = result["session_string"]
        phone = user_states.get(user_id, {}).get("phone")
        
        # Veritabanı güncelle
        await db.update_user(user_id, {
            "is_logged_in": True,
            "userbot_id": user_info["id"],
            "userbot_username": user_info["username"]
        })
        
        # Geçici session bilgisi
        if not hasattr(bot, 'session_temp'):
            bot.session_temp = {}
        
        bot.session_temp[user_id] = {
            "session": session_string,
            "phone": phone,
            "type": user_states.get(user_id, {}).get("session_type", "phone")
        }
        
        # State temizle
        if user_id in user_states:
            del user_states[user_id]
        
        await msg.edit(
            config.MESSAGES["login_success"].format(
                name=user_info["first_name"] or "Kullanıcı",
                user_id=user_info["id"]
            ) + "\n\n" + config.MESSAGES["login_remember"],
            buttons=[
                [
                    Button.inline(config.BUTTONS["remember_yes"], b"save_session"),
                    Button.inline(config.BUTTONS["remember_no"], b"dont_save_session")
                ]
            ]
        )
        
        await send_log(
            bot, "login",
            f"Yeni giriş\nUserbot: @{user_info['username']} ({user_info['id']})",
            user_id
        )
    
    # ==========================================
    # SESSION İLE GİRİŞ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"login_telethon"))
    async def login_telethon_start(event):
        """Telethon session ile giriş"""
        user_id = event.sender_id
        
        user_states[user_id] = {
            "state": STATE_WAITING_SESSION_TELETHON,
            "session_type": "telethon",
            "message_id": event.message_id
        }
        
        text = config.MESSAGES["login_session_telethon"]
        text += "\n\n⚠️ **İptal etmek için:** /cancel"
        
        await event.edit(text, buttons=[
            [Button.inline("❌ İptal", b"login_menu")]
        ])
    
    @bot.on(events.CallbackQuery(data=b"login_pyrogram"))
    async def login_pyrogram_start(event):
        """Pyrogram session ile giriş"""
        user_id = event.sender_id
        
        user_states[user_id] = {
            "state": STATE_WAITING_SESSION_PYROGRAM,
            "session_type": "pyrogram",
            "message_id": event.message_id
        }
        
        text = config.MESSAGES["login_session_pyrogram"]
        text += "\n\n⚠️ **İptal etmek için:** /cancel"
        
        await event.edit(text, buttons=[
            [Button.inline("❌ İptal", b"login_menu")]
        ])
    
    async def handle_session_input(event, bot, session_type):
        """Session string girişini işle"""
        user_id = event.sender_id
        session_string = event.text.strip()
        
        # Mesajı sil
        try:
            await event.delete()
        except:
            pass
        
        msg = await bot.send_message(user_id, "⏳ Session doğrulanıyor...")
        
        result = await userbot_manager.login_with_session(user_id, session_string, session_type)
        
        if result["success"]:
            user_info = result["user_info"]
            
            await db.update_user(user_id, {
                "is_logged_in": True,
                "userbot_id": user_info["id"],
                "userbot_username": user_info["username"]
            })
            
            if not hasattr(bot, 'session_temp'):
                bot.session_temp = {}
            
            bot.session_temp[user_id] = {
                "session": session_string,
                "phone": None,
                "type": session_type
            }
            
            # State temizle
            if user_id in user_states:
                del user_states[user_id]
            
            await msg.edit(
                config.MESSAGES["login_success"].format(
                    name=user_info["first_name"] or "Kullanıcı",
                    user_id=user_info["id"]
                ) + "\n\n" + config.MESSAGES["login_remember"],
                buttons=[
                    [
                        Button.inline(config.BUTTONS["remember_yes"], b"save_session"),
                        Button.inline(config.BUTTONS["remember_no"], b"dont_save_session")
                    ]
                ]
            )
            
            await send_log(
                bot, "login",
                f"Yeni giriş ({session_type.title()} Session)\nUserbot: @{user_info['username']}",
                user_id
            )
        else:
            error = result.get("error", "Bilinmeyen hata")
            error_messages = {
                "invalid_session": "Geçersiz session string",
                "session_terminated": "Session sonlandırılmış",
                "account_banned": "Hesap yasaklı"
            }
            
            # State temizle
            if user_id in user_states:
                del user_states[user_id]
            
            await msg.edit(
                config.MESSAGES["login_failed"].format(error=error_messages.get(error, error)),
                buttons=[[Button.inline("🔙 Geri", b"login_menu")]]
            )
    
    # ==========================================
    # CANCEL KOMUTU
    # ==========================================
    
    @bot.on(events.NewMessage(pattern=r'^/cancel$'))
    async def cancel_handler(event):
        """İşlemi iptal et"""
        user_id = event.sender_id
        
        if user_id in user_states:
            del user_states[user_id]
            
            # Pending login varsa temizle
            if user_id in userbot_manager.pending_logins:
                try:
                    await userbot_manager.pending_logins[user_id]["client"].disconnect()
                except:
                    pass
                del userbot_manager.pending_logins[user_id]
            
            await event.respond(
                "❌ İşlem iptal edildi.",
                buttons=[[Button.inline("🏠 Ana Menü", b"main_menu")]]
            )
        else:
            await event.respond("ℹ️ İptal edilecek bir işlem yok.")
    
    # ==========================================
    # SESSION KAYDETME
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"save_session"))
    async def save_session_handler(event):
        """Session'ı kaydet"""
        user_id = event.sender_id
        
        if not hasattr(bot, 'session_temp') or user_id not in bot.session_temp:
            await event.answer("⚠️ Session bulunamadı", alert=True)
            return
        
        temp_data = bot.session_temp[user_id]
        
        await db.save_session(
            user_id,
            temp_data["session"],
            temp_data["type"],
            temp_data.get("phone"),
            remember=True
        )
        
        del bot.session_temp[user_id]
        
        await event.edit(
            "✅ **Giriş tamamlandı ve session kaydedildi!**\n\n"
            "💾 Bir sonraki girişte hızlı giriş yapabilirsiniz.\n\n"
            "Artık plugin'leri kullanabilirsiniz.",
            buttons=[
                [Button.inline(config.BUTTONS["plugins"], b"plugins_menu")],
                [Button.inline("🏠 Ana Menü", b"main_menu")]
            ]
        )
    
    @bot.on(events.CallbackQuery(data=b"dont_save_session"))
    async def dont_save_session_handler(event):
        """Session'ı kaydetme"""
        user_id = event.sender_id
        
        if hasattr(bot, 'session_temp') and user_id in bot.session_temp:
            temp_data = bot.session_temp[user_id]
            
            await db.save_session(
                user_id,
                temp_data["session"],
                temp_data["type"],
                temp_data.get("phone"),
                remember=False
            )
            
            del bot.session_temp[user_id]
        
        await event.edit(
            "✅ **Giriş tamamlandı!**\n\n"
            "Session kaydedilmedi. Bir sonraki girişte tekrar bilgi girmeniz gerekecek.\n\n"
            "Artık plugin'leri kullanabilirsiniz.",
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
        user_id = event.sender_id
        
        session_data = await db.get_session(user_id)
        
        if not session_data or not session_data.get("data"):
            await event.answer("⚠️ Kaydedilmiş session bulunamadı", alert=True)
            return
        
        await event.edit("⏳ Giriş yapılıyor...")
        
        result = await userbot_manager.login_with_session(
            user_id,
            session_data["data"],
            session_data.get("type", "telethon")
        )
        
        if result["success"]:
            user_info = result["user_info"]
            
            await db.update_user(user_id, {
                "is_logged_in": True,
                "userbot_id": user_info["id"],
                "userbot_username": user_info["username"]
            })
            
            # Eski pluginleri geri yükle
            client = userbot_manager.get_client(user_id)
            restored = 0
            if client:
                restored = await plugin_manager.restore_user_plugins(user_id, client)
            
            text = config.MESSAGES["login_success"].format(
                name=user_info["first_name"] or "Kullanıcı",
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
            
            await send_log(bot, "login", f"Hızlı giriş\nUserbot: @{user_info['username']}", user_id)
        else:
            # Session geçersiz
            await db.clear_session(user_id, keep_data=False)
            
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
        user_id = event.sender_id
        keep_data = event.data == b"logout_keep"
        
        await event.edit("⏳ Çıkış yapılıyor...")
        
        # Userbot'u kapat
        await userbot_manager.logout(user_id)
        
        # Pluginleri temizle
        plugin_manager.clear_user_plugins(user_id)
        
        # Veritabanını güncelle
        await db.clear_session(user_id, keep_data=keep_data)
        
        text = config.MESSAGES["logout_success"]
        if keep_data:
            text += "\n\n💾 Bilgileriniz saklandı. Hızlı giriş yapabilirsiniz."
        else:
            text += "\n\n🗑️ Tüm bilgileriniz silindi."
        
        await event.edit(
            text,
            buttons=[[Button.inline("🏠 Ana Menü", b"main_menu")]]
        )
        
        await send_log(bot, "logout", f"Çıkış yapıldı (Veri sakla: {keep_data})", user_id)
    
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
        # State temizle
        if event.sender_id in user_states:
            del user_states[event.sender_id]
        
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
        text += "• `/pinactive <isim>` - Plugin deaktif et\n"
        text += "• `/cancel` - İşlemi iptal et\n\n"
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
