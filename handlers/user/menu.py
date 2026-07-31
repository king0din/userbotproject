# ============================================
# KingTG UserBot Service - User / menu
# /start, ana menü, iptal, kapat
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

    @bot.on(events.NewMessage(pattern=r'^/start(?:\s+(.+))?$'))
    @check_ban
    @check_maintenance
    @check_private_mode
    @register_user
    async def start_handler(event):
        if event.sender_id in user_states:
            del user_states[event.sender_id]
        
        # Deep link parametresi kontrol et
        param = event.pattern_match.group(1)
        
        if param:
            # Deep link ile geldiyse ilgili sayfaya yönlendir
            if param == "panel":
                # Ana menüyü göster
                user = await event.get_sender()
                text, rows = await build_main_menu(event.sender_id, user.first_name)
                await bot_api.send_message(
                    chat_id=event.sender_id,
                    text=text,
                    reply_markup=btn.inline_keyboard(rows)
                )
                return
            
            elif param == "plugins":
                # Plugin sayfasına yönlendir
                user_data = await db.get_user(event.sender_id)
                if user_data and user_data.get("is_logged_in"):
                    # Fake event oluştur ve plugins_menu_handler'ı çağır
                    await event.respond("⏳ Plugin listesi yükleniyor...")
                    # Direkt olarak plugins menüsünü göster
                    all_plugins = await db.get_all_plugins()
                    active_plugins = user_data.get("active_plugins", [])
                    
                    accessible_plugins = []
                    for p in all_plugins:
                        if p.get("is_disabled", False):
                            continue
                        if p.get("is_public", True) or event.sender_id in p.get("allowed_users", []):
                            if event.sender_id not in p.get("restricted_users", []):
                                accessible_plugins.append(p)
                    
                    if not accessible_plugins:
                        text = "📭 **Henüz plugin yok.**"
                        await event.respond(text, buttons=[[Button.inline("🏠 Ana Menü", b"main_menu")]])
                        return
                    
                    text = f"🔌 **Plugin Listesi** (Toplam: {len(accessible_plugins)})\n\n"
                    
                    for p in accessible_plugins[:10]:
                        name = p['name']
                        is_active = name in active_plugins
                        is_default = p.get("default_active", False)
                        status = "🟢" if is_active else "⚪"
                        default_icon = "⭐" if is_default else ""
                        
                        cmds = p.get("commands", [])[:2]
                        cmd_text = ", ".join([f"`.{c}`" for c in cmds])
                        
                        text += f"{status}{default_icon} **{name}**\n"
                        text += f"   └ {cmd_text}\n"
                        text += f"   └ Yükle: `/pactive {name}`\n\n"
                    
                    if len(accessible_plugins) > 10:
                        text += f"... ve {len(accessible_plugins) - 10} plugin daha\n\n"
                    
                    text += f"━━━━━━━━━━━━━━━━━━━━\n"
                    text += f"🟢 Aktif | ⚪ Pasif | ⭐ Zorunlu\n"
                    text += f"✅ Aktif: **{len(active_plugins)}** plugin"
                    
                    buttons = [
                        [Button.inline("📦 Pluginlerim", b"my_plugins_0")],
                        [Button.inline("🏠 Ana Menü", b"main_menu")]
                    ]
                    await event.respond(text, buttons=buttons)
                else:
                    await event.respond("❌ Önce giriş yapmalısınız.", buttons=[[Button.inline("🔐 Giriş Yap", b"login_menu")]])
                return
            
            elif param == "my_plugins":
                # Aktif pluginler sayfasına yönlendir
                user_data = await db.get_user(event.sender_id)
                if user_data and user_data.get("is_logged_in"):
                    active_plugins = user_data.get("active_plugins", [])
                    
                    if not active_plugins:
                        text = "📭 **Aktif plugin yok.**\n\nPlugin yüklemek için:\n`/pactive <isim>`"
                        await event.respond(text, buttons=[
                            [Button.inline("🔌 Plugin Listesi", b"plugins_page_0")],
                            [Button.inline("🏠 Ana Menü", b"main_menu")]
                        ])
                        return
                    
                    text = f"📦 **Aktif Plugin'leriniz** ({len(active_plugins)} adet)\n\n"
                    
                    for name in active_plugins[:10]:
                        plugin = await db.get_plugin(name)
                        if plugin:
                            cmds = ", ".join([f"`.{c}`" for c in plugin.get("commands", [])])
                            is_default = plugin.get("default_active", False)
                            default_icon = "⭐" if is_default else ""
                            text += f"✅{default_icon} **{name}**\n"
                            text += f"   └ {cmds}\n"
                            if not is_default:
                                text += f"   └ Kaldır: `/pinactive {name}`\n\n"
                            else:
                                text += f"   └ _(Zorunlu plugin)_\n\n"
                    
                    if len(active_plugins) > 10:
                        text += f"... ve {len(active_plugins) - 10} plugin daha"
                    
                    buttons = [
                        [Button.inline("🔌 Tüm Plugin'ler", b"plugins_page_0")],
                        [Button.inline("🏠 Ana Menü", b"main_menu")]
                    ]
                    await event.respond(text, buttons=buttons)
                else:
                    await event.respond("❌ Önce giriş yapmalısınız.", buttons=[[Button.inline("🔐 Giriş Yap", b"login_menu")]])
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
                except: pass
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
