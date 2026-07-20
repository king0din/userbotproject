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

        # Otomatik dil tespiti (çeviri için): kayıtlı dil varsa onu, yoksa
        # kullanıcının Telegram diline göre başlangıç dili ayarla.
        try:
            import utils.i18n as _i18n
            _snd = await event.get_sender()
            _ud = await db.get_user(event.sender_id)
            _saved = (_ud or {}).get("lang")
            if _saved:
                _i18n.set_user_lang(event.sender_id, _saved)
            else:
                _dl = _i18n.default_lang_from_tg(getattr(_snd, "lang_code", None))
                _i18n.set_user_lang(event.sender_id, _dl)
                if _dl != "tr":
                    await db.update_user(event.sender_id, {"lang": _dl})
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
    

    @bot.on(events.CallbackQuery(data=b"lang_menu"))
    async def lang_menu_handler(event):
        """Dil seçim menüsü — dil adları kendi dilinde (çeviri KAPALI)."""
        import utils.i18n as _i18n
        cur = _i18n.get_user_lang_cached(event.sender_id)
        langs = _i18n.all_langs()
        text = ("🌐 **Dil / Language**\n\n"
                f"Şu an / Current: **{langs.get(cur, cur)}**\n\n"
                "Bir dil seç / Choose your language:")
        rows, row = [], []
        for code, name in langs.items():
            mark = "✅ " if code == cur else ""
            row.append(btn.callback(mark + name, f"setlang_{code}"))
            if len(row) == 2:
                rows.append(row); row = []
        if row:
            rows.append(row)
        rows.append([btn.callback(" Ana Menü / Home", "main_menu",
                                  style=ButtonBuilder.STYLE_DANGER,
                                  icon_custom_emoji_id=5832654562510511307)])
        # translate=False → dil adları olduğu gibi kalsın (herkes kendi dilini bulsun)
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id,
                                        text=text, reply_markup=btn.inline_keyboard(rows),
                                        translate=False)
        await event.answer()

    @bot.on(events.CallbackQuery(pattern=rb"setlang_([a-zA-Z]{2,5})"))
    async def setlang_handler(event):
        import utils.i18n as _i18n
        code = event.data.decode().split("_", 1)[1]
        _i18n.set_user_lang(event.sender_id, code)
        _nl = _i18n.norm_lang(code)
        try:
            await db.update_user(event.sender_id, {"lang": _nl})
        except Exception:
            pass
        # Yeni dili ARKA PLANDA ön-çevir (bot + plugin metinleri hızlı olsun)
        if _nl != "tr":
            try:
                import asyncio as _a
                _a.create_task(_i18n.prewarm(_i18n.get_prewarm_strings(), langs=[_nl]))
            except Exception:
                pass
        try:
            await event.answer("✅ " + _i18n.all_langs().get(_i18n.norm_lang(code), code))
        except Exception:
            pass
        # Ana menüyü YENİ dilde göster (bot_api otomatik çevirir)
        user = await event.get_sender()
        text, rows = await build_main_menu(event.sender_id, user.first_name)
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id,
                                        text=text, reply_markup=btn.inline_keyboard(rows))

    @bot.on(events.CallbackQuery(data=b"noop"))
    async def noop_handler(event):
        await event.answer()
