# ============================================
# KingTG UserBot Service - User / login
# Giriş/çıkış akışı (telefon, kod, 2FA, session, hızlı giriş)
# (user.py'dan otomatik bölündü - davranış birebir korundu)
# ============================================

# ============================================
# KingTG UserBot Service - User Handlers
# ============================================

from telethon import events, Button
import config
from database import database as db
from userbot.smart_manager import smart_session_manager
from userbot.plugins import plugin_manager
from utils import (
    check_ban, check_private_mode, check_maintenance, 
    register_user, send_log, is_valid_phone, back_button
)
from utils.bot_api import bot_api, btn, ButtonBuilder

# Eski uyumluluk için alias
userbot_manager = smart_session_manager

from ._common import (
    user_states, build_main_menu,
    STATE_WAITING_PHONE, STATE_WAITING_CODE, STATE_WAITING_2FA,
    STATE_WAITING_SESSION_TELETHON, STATE_WAITING_SESSION_PYROGRAM,
    PLUGINS_PER_PAGE,
)


def register(bot):

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
            [btn.callback(" Telefon Numarası", "login_phone",
                         style=ButtonBuilder.STYLE_SUCCESS,
                         icon_custom_emoji_id=5832225314889015431)],
            [btn.callback(" Telethon Session", "login_telethon",
                         style=ButtonBuilder.STYLE_PRIMARY,
                         icon_custom_emoji_id=5832345561088400364)],
            [btn.callback(" Pyrogram Session", "login_pyrogram",
                         style=ButtonBuilder.STYLE_PRIMARY,
                         icon_custom_emoji_id=5832345561088400364)],
            [btn.callback(" Geri", "main_menu",
                         style=ButtonBuilder.STYLE_DANGER,
                         icon_custom_emoji_id=5832646161554480591)]
        ]
        
        await bot_api.edit_message_text(
            chat_id=event.sender_id,
            message_id=event.message_id,
            text=config.MESSAGES["login_method"],
            reply_markup=btn.inline_keyboard(rows)
        )
        await event.answer()
    

    @bot.on(events.CallbackQuery(data=b"login_phone"))
    async def login_phone_start(event):
        user_states[event.sender_id] = {"state": STATE_WAITING_PHONE}
        text = config.MESSAGES["login_phone"] + "\n\n⚠️ İptal: /cancel"
        rows = [[btn.callback(" İptal", "login_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832236194041176208)]]
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id, text=text, reply_markup=btn.inline_keyboard(rows))
        await event.answer()
    

    @bot.on(events.CallbackQuery(data=b"login_telethon"))
    async def login_telethon_start(event):
        user_states[event.sender_id] = {"state": STATE_WAITING_SESSION_TELETHON, "session_type": "telethon"}
        text = config.MESSAGES["login_session_telethon"] + "\n\n⚠️ İptal: /cancel"
        rows = [[btn.callback(" İptal", "login_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832236194041176208)]]
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id, text=text, reply_markup=btn.inline_keyboard(rows))
        await event.answer()
    

    @bot.on(events.CallbackQuery(data=b"login_pyrogram"))
    async def login_pyrogram_start(event):
        user_states[event.sender_id] = {"state": STATE_WAITING_SESSION_PYROGRAM, "session_type": "pyrogram"}
        text = config.MESSAGES["login_session_pyrogram"] + "\n\n⚠️ İptal: /cancel"
        rows = [[btn.callback(" İptal", "login_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832236194041176208)]]
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id, text=text, reply_markup=btn.inline_keyboard(rows))
        await event.answer()
    

    async def handle_phone_input(event, bot):
        user_id = event.sender_id
        phone = event.text.strip()
        
        if not is_valid_phone(phone):
            await event.respond("❌ Geçersiz format. Örnek: `+905551234567`")
            return
        
        try: await event.delete()
        except Exception: pass
        
        msg = await bot.send_message(user_id, "⏳ Kod gönderiliyor...")
        result = await userbot_manager.start_phone_login(user_id, phone)
        
        if not result["success"]:
            if user_id in user_states: del user_states[user_id]
            error = result.get("error", "Bilinmeyen hata")
            if result.get("error") == "flood_wait":
                error = f"{result['seconds']} saniye bekleyin"
            rows = [[btn.callback(" Geri", "login_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832646161554480591)]]
            await bot_api.edit_message_text(chat_id=user_id, message_id=msg.id, text=f"❌ Hata: {error}", reply_markup=btn.inline_keyboard(rows))
            return
        
        user_states[user_id] = {"state": STATE_WAITING_CODE, "phone": phone}
        rows = [[btn.callback(" İptal", "login_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832236194041176208)]]
        await bot_api.edit_message_text(chat_id=user_id, message_id=msg.id, text=config.MESSAGES["login_code"] + "\n\n⚠️ İptal: /cancel", reply_markup=btn.inline_keyboard(rows))
    

    async def handle_code_input(event, bot):
        user_id = event.sender_id
        code = event.text.strip().replace(" ", "").replace("-", "")
        
        try: await event.delete()
        except Exception: pass
        
        msg = await bot.send_message(user_id, "⏳ Doğrulanıyor...")
        result = await userbot_manager.verify_code(user_id, code)
        
        if result.get("stage") == "2fa":
            user_states[user_id]["state"] = STATE_WAITING_2FA
            rows = [[btn.callback(" İptal", "login_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832236194041176208)]]
            await bot_api.edit_message_text(chat_id=user_id, message_id=msg.id, text=config.MESSAGES["login_2fa"] + "\n\n⚠️ İptal: /cancel", reply_markup=btn.inline_keyboard(rows))
            return
        
        if result["success"]:
            await handle_login_success(event, bot, result, msg)
        else:
            error = result.get("error", "Bilinmeyen hata")
            if error in ["code_expired", "no_pending_login"]:
                if user_id in user_states: del user_states[user_id]
            rows = [[btn.callback(" Geri", "login_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832646161554480591)]]
            await bot_api.edit_message_text(chat_id=user_id, message_id=msg.id, text=f"❌ {error}", reply_markup=btn.inline_keyboard(rows))
    

    async def handle_2fa_input(event, bot):
        user_id = event.sender_id
        password = event.text.strip()
        
        try: await event.delete()
        except Exception: pass
        
        msg = await bot.send_message(user_id, "⏳ Doğrulanıyor...")
        result = await userbot_manager.verify_2fa(user_id, password)
        
        if result["success"]:
            await handle_login_success(event, bot, result, msg)
        else:
            rows = [[btn.callback(" Geri", "login_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832646161554480591)]]
            await bot_api.edit_message_text(chat_id=user_id, message_id=msg.id, text=f"❌ {result.get('error', 'Hata')}", reply_markup=btn.inline_keyboard(rows))
    

    async def handle_session_input(event, bot, session_type):
        user_id = event.sender_id
        session_string = event.text.strip()
        
        try: await event.delete()
        except Exception: pass
        
        msg = await bot.send_message(user_id, "⏳ Session doğrulanıyor...")
        result = await userbot_manager.login_with_session(user_id, session_string, session_type)
        
        if result["success"]:
            if not hasattr(bot, 'session_temp'): bot.session_temp = {}
            bot.session_temp[user_id] = {"session": session_string, "phone": None, "type": session_type}
            await handle_login_success(event, bot, result, msg)
        else:
            if user_id in user_states: del user_states[user_id]
            rows = [[btn.callback(" Geri", "login_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832646161554480591)]]
            await bot_api.edit_message_text(chat_id=user_id, message_id=msg.id, text=f"❌ {result.get('error', 'Session geçersiz')}", reply_markup=btn.inline_keyboard(rows))
    

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
        
        rows = [
            [btn.callback(" Kaydet", "save_session", style=ButtonBuilder.STYLE_SUCCESS, icon_custom_emoji_id=5832181205574884602),
             btn.callback(" Kaydetme", "dont_save_session", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832236194041176208)]
        ]
        await bot_api.edit_message_text(
            chat_id=user_id,
            message_id=msg.id,
            text=config.MESSAGES["login_success"].format(
                name=user_info["first_name"] or "Kullanıcı",
                user_id=user_info["id"]
            ) + "\n\n" + config.MESSAGES["login_remember"],
            reply_markup=btn.inline_keyboard(rows)
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
        
        # Varsayılan aktif pluginleri yükle
        client = await smart_session_manager.get_or_create_client(user_id)
        default_count = 0
        if client:
            default_count = await plugin_manager.activate_default_plugins(user_id, client)
        
        text = "✅ **Giriş tamamlandı!**\n\n💾 Session kaydedildi."
        if default_count > 0:
            text += f"\n🔌 {default_count} varsayılan plugin aktif edildi."
        
        rows = [
            [btn.callback(" Pluginler", "plugins_page_0", style=ButtonBuilder.STYLE_PRIMARY, icon_custom_emoji_id=5830184853236097449)],
            [btn.callback(" Ana Menü", "main_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832654562510511307)]
        ]
        await bot_api.edit_message_text(chat_id=user_id, message_id=event.message_id, text=text, reply_markup=btn.inline_keyboard(rows))
        await event.answer()
    

    @bot.on(events.CallbackQuery(data=b"dont_save_session"))
    async def dont_save_session_handler(event):
        user_id = event.sender_id
        if hasattr(bot, 'session_temp') and user_id in bot.session_temp:
            temp = bot.session_temp[user_id]
            await db.save_session(user_id, temp["session"], temp["type"], temp.get("phone"), remember=False)
            del bot.session_temp[user_id]
        
        # Varsayılan aktif pluginleri yükle
        client = await smart_session_manager.get_or_create_client(user_id)
        default_count = 0
        if client:
            default_count = await plugin_manager.activate_default_plugins(user_id, client)
        
        text = "✅ **Giriş tamamlandı!**"
        if default_count > 0:
            text += f"\n\n🔌 {default_count} varsayılan plugin aktif edildi."
        
        rows = [
            [btn.callback(" Pluginler", "plugins_page_0", style=ButtonBuilder.STYLE_PRIMARY, icon_custom_emoji_id=5830184853236097449)],
            [btn.callback(" Ana Menü", "main_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832654562510511307)]
        ]
        await bot_api.edit_message_text(chat_id=user_id, message_id=event.message_id, text=text, reply_markup=btn.inline_keyboard(rows))
        await event.answer()
    
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
            
            # Client'ı al (login_with_session zaten oluşturmuş olmalı)
            client = smart_session_manager.get_client(user_id)
            if not client:
                client = await smart_session_manager.get_or_create_client(user_id)
            
            restored = 0
            if client:
                restored = await plugin_manager.restore_user_plugins(user_id, client)
            
            text = f"✅ **Giriş başarılı!**\n\n👤 `{user_info['first_name']}`"
            if restored > 0:
                text += f"\n🔌 {restored} plugin yüklendi"
            
            rows = [
                [btn.callback(" Pluginler", "plugins_page_0", style=ButtonBuilder.STYLE_PRIMARY, icon_custom_emoji_id=5830184853236097449)],
                [btn.callback(" Ana Menü", "main_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832654562510511307)]
            ]
            await bot_api.edit_message_text(chat_id=user_id, message_id=event.message_id, text=text, reply_markup=btn.inline_keyboard(rows))
            await send_log(bot, "login", f"Hızlı giriş: @{user_info['username']}", user_id)
        else:
            await db.clear_session(user_id, keep_data=False)
            rows = [[btn.callback(" Giriş Yap", "login_menu", style=ButtonBuilder.STYLE_SUCCESS, icon_custom_emoji_id=5832668083067559171)]]
            await bot_api.edit_message_text(chat_id=user_id, message_id=event.message_id, text="❌ Session geçersiz. Yeniden giriş yapın.", reply_markup=btn.inline_keyboard(rows))
        await event.answer()
    
    # ==========================================
    # ÇIKIŞ
    # ==========================================
    

    @bot.on(events.CallbackQuery(data=b"logout_confirm"))
    async def logout_confirm_handler(event):
        rows = [
            [btn.callback(" Sakla", "logout_keep", style=ButtonBuilder.STYLE_SUCCESS, icon_custom_emoji_id=5832181205574884602),
             btn.callback(" Sil", "logout_delete", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832236194041176208)],
            [btn.callback(" Geri", "main_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832646161554480591)]
        ]
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id, text=config.MESSAGES["logout_confirm"], reply_markup=btn.inline_keyboard(rows))
        await event.answer()
    

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
        
        rows = [[btn.callback(" Ana Menü", "main_menu", style=ButtonBuilder.STYLE_PRIMARY, icon_custom_emoji_id=5832654562510511307)]]
        await bot_api.edit_message_text(chat_id=user_id, message_id=event.message_id, text=text, reply_markup=btn.inline_keyboard(rows))
        await send_log(bot, "logout", f"Çıkış (sakla: {keep_data})", user_id)
    
    # ==========================================
    # PLUGİN MENÜSÜ - SAYFALI
    # ==========================================
