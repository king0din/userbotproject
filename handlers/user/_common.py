# ============================================
# KingTG UserBot Service - User / Ortak
# Paylaşılan login state'i + ana menü oluşturucu
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


# --- Paylaşılan login durumu (TÜM modüller AYNI sözlüğü kullanır) ---
# State management
user_states = {}
STATE_WAITING_PHONE = "waiting_phone"
STATE_WAITING_CODE = "waiting_code"
STATE_WAITING_2FA = "waiting_2fa"
STATE_WAITING_SESSION_TELETHON = "waiting_session_telethon"
STATE_WAITING_SESSION_PYROGRAM = "waiting_session_pyrogram"

PLUGINS_PER_PAGE = 8


async def build_main_menu(user_id, user_first_name):
    """Ana menü içeriğini oluştur - /start ve main_menu için ortak"""
    user_data = await db.get_user(user_id)
    is_logged_in = user_data.get("is_logged_in", False) if user_data else False
    
    text = config.MESSAGES["welcome"]
    text += f"\n\n👋 Merhaba **{user_first_name}**!"
    
    if is_logged_in:
        active_count = len(user_data.get("active_plugins", []))
        text += f"\n✅ Userbot aktif: `{user_data.get('userbot_username', '?')}`"
        text += f"\n🔌 Aktif plugin: `{active_count}`"
    
    rows = []
    
    if is_logged_in:
        # Giriş yapılmış - Plugin butonları
        rows.append([
            btn.callback(" Pluginler", "plugins_page_0", 
                        style=ButtonBuilder.STYLE_PRIMARY,
                        icon_custom_emoji_id=5830184853236097449)
        ])
        rows.append([
            btn.callback(" Pluginlerim", "my_plugins_0",
                        style=ButtonBuilder.STYLE_PRIMARY,
                        icon_custom_emoji_id=5832711694165483426)
        ])
        rows.append([
            btn.callback(" Çıkış Yap", "logout_confirm",
                        style=ButtonBuilder.STYLE_DANGER,
                        icon_custom_emoji_id=5832183129720233237)
        ])
    else:
        # Giriş yapılmamış
        session_data = await db.get_session(user_id)
        if session_data and session_data.get("remember"):
            rows.append([
                btn.callback(" Hızlı Giriş", "quick_login",
                            style=ButtonBuilder.STYLE_SUCCESS,
                            icon_custom_emoji_id=5832277107899636698)
            ])
        rows.append([
            btn.callback(" Giriş Yap", "login_menu",
                        style=ButtonBuilder.STYLE_SUCCESS,
                        icon_custom_emoji_id=5832668083067559171)
        ])
    
    # Yardım ve Komutlar
    rows.append([
        btn.callback(" Yardım", "help_main",
                    icon_custom_emoji_id=5832628878606082111),
        btn.callback(" Komutlar", "commands",
                    icon_custom_emoji_id=5832365506916523096)
    ])
    
    # Plugin Kanalı
    rows.append([
        btn.url(f" {config.PLUGIN_CHANNEL}", f"https://t.me/{config.PLUGIN_CHANNEL}",
               style=ButtonBuilder.STYLE_PRIMARY,
               icon_custom_emoji_id=5832328832190784454)
    ])
    
    # Admin butonu
    if user_id == config.OWNER_ID or await db.is_sudo(user_id):
        rows.append([
            btn.callback(" Yönetim Paneli", "settings_menu",
                        style=ButtonBuilder.STYLE_DANGER,
                        icon_custom_emoji_id=5832502928690127854)
        ])
    
    return text, rows

# ==========================================
# /start KOMUTU (Bot API - Renkli Butonlar)
# ==========================================
