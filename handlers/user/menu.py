# ============================================
# KingTG UserBot Service - User / menu
# /start, ana menü, iptal, kapat
# (user.py'dan otomatik bölündü - davranış birebir korundu)
# ============================================

# ============================================
# KingTG UserBot Service - User Handlers
# ============================================

from telethon import events, Button
from database import database as db
from userbot.smart_manager import smart_session_manager
from utils import (
    check_ban, check_private_mode, check_maintenance, 
    register_user
)
from utils.bot_api import bot_api, btn, ButtonBuilder

# Eski uyumluluk için alias
userbot_manager = smart_session_manager

from ._common import (
    user_states, build_main_menu,
    build_plugins_page, build_my_plugins_page,
)


def register(bot):

    @bot.on(events.NewMessage(pattern=r'^/start(?:\s+(.+))?$'))
    @check_ban
    @check_maintenance
    @check_private_mode
    @register_user
    async def start_handler(event):
        if event.sender_id in user_states:
            del user_states[event.sender_id]
        # Yarım kalmış admin "ID gönder" akışını da temizle
        try:
            from handlers.admin._state import admin_input_state
            admin_input_state.pop(event.sender_id, None)
        except Exception:
            pass
        
        # Deep link parametresi kontrol et
        param = event.pattern_match.group(1)

        if param:
            # Deep link ile geldiyse ilgili BUTONLU sayfaya yönlendir
            # (sayfalar _common.py'daki ortak oluşturuculardan gelir)
            if param == "panel":
                user = await event.get_sender()
                text, rows = await build_main_menu(event.sender_id, user.first_name)
                await bot_api.send_message(
                    chat_id=event.sender_id,
                    text=text,
                    reply_markup=btn.inline_keyboard(rows)
                )
                return

            elif param in ("plugins", "my_plugins"):
                user_data = await db.get_user(event.sender_id)
                if not user_data or not user_data.get("is_logged_in"):
                    await event.respond("❌ Önce giriş yapmalısınız.",
                                        buttons=[[Button.inline("🔐 Giriş Yap", b"login_menu")]])
                    return
                if param == "plugins":
                    text, rows = await build_plugins_page(event.sender_id, 0)
                else:
                    text, rows = await build_my_plugins_page(event.sender_id, 0)
                await bot_api.send_message(
                    chat_id=event.sender_id,
                    text=text,
                    reply_markup=btn.inline_keyboard(rows)
                )
                return

        # Normal /start
        user = await event.get_sender()
        text, rows = await build_main_menu(event.sender_id, user.first_name)
        
        await bot_api.send_message(
            chat_id=event.sender_id,
            text=text,
            reply_markup=btn.inline_keyboard(rows)
        )
    
    # ==========================================
    # MESAJ HANDLER
    # ==========================================
    

    @bot.on(events.NewMessage(pattern=r'^/cancel$'))
    async def cancel_handler(event):
        user_id = event.sender_id
        if user_id in user_states:
            del user_states[user_id]
            if user_id in userbot_manager.pending_logins:
                try: await userbot_manager.pending_logins[user_id]["client"].disconnect()
                except Exception: pass
                del userbot_manager.pending_logins[user_id]
            rows = [[btn.callback(" Ana Menü", "main_menu", style=ButtonBuilder.STYLE_PRIMARY, icon_custom_emoji_id=5832654562510511307)]]
            await bot_api.send_message(chat_id=user_id, text="❌ İptal edildi.", reply_markup=btn.inline_keyboard(rows))
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
        text, rows = await build_main_menu(event.sender_id, user.first_name)
        
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
    

    @bot.on(events.CallbackQuery(data=b"close"))
    async def close_handler(event):
        await event.delete()
    

    @bot.on(events.CallbackQuery(data=b"noop"))
    async def noop_handler(event):
        await event.answer()
