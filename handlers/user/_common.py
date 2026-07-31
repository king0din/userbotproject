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
# NOT: Session-string (Telethon/Pyrogram) girişi kaldırıldı — yalnızca telefon girişi.

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
# PLUGIN SAYFALARI (ortak butonlu oluşturucular)
# plugins_user.py ve menu.py (deep link) aynı butonlu
# sayfaları kullanır — kopya kod yok.
# ==========================================

# Premium emoji ID'leri (renkli butonların yanındaki ifadeler).
# Projenin başka yerlerinde (pset.py, main menü) kullanılan paletle uyumlu.
# İstersen tek tek değiştirebilirsin — sadece ID'yi güncelle.
EMOJI_AKTIF = 5832249761842864793      # yüklü plugin  → "Aktif Et" emojisi (yeşil)
EMOJI_PASIF = 5830001655701052988      # yüklü değil   → "Devre Dışı" emojisi
EMOJI_TUMU_AC = 5832490468990000458    # tümünü aç     → "Hepsini Genel" (yeşil)
EMOJI_TUMU_KAPAT = 5832636278834733177  # tümünü kapat  → "Hepsini Özel" (kırmızı)
EMOJI_VARSAYILAN = 5832308667319328140  # varsayılanlar → "Varsayılan Aktif" (yıldız)
EMOJI_DETAY = 5832628878606082111       # detay modu    → "Yardım/Bilgi" emojisi

async def accessible_plugins(user_id):
    """Kullanıcının görebileceği plugin listesi"""
    all_plugins = await db.get_all_plugins()
    out = []
    for p in all_plugins:
        if p.get("is_disabled", False):
            continue
        if p.get("is_public", True) or user_id in p.get("allowed_users", []):
            if user_id not in p.get("restricted_users", []):
                out.append(p)
    return out


async def build_plugins_page(user_id, page):
    """Tüm pluginler sayfası: her plugin tek-dokunuş aç/kapat butonu"""
    user_data = await db.get_user(user_id)
    active_plugins = user_data.get("active_plugins", []) if user_data else []
    accessible = await accessible_plugins(user_id)

    if not accessible:
        text = "📭 **Henüz plugin eklenmemiş.**\n\nPlugin duyuruları için kanalı takip edin."
        rows = [
            [btn.url(config.BUTTONS.get("plugin_channel", "📢 Kanal"),
                     f"https://t.me/{config.PLUGIN_CHANNEL}", style=ButtonBuilder.STYLE_PRIMARY)],
            [btn.callback(" Ana Menü", "main_menu", style=ButtonBuilder.STYLE_DANGER,
                          icon_custom_emoji_id=5832654562510511307)],
        ]
        return text, rows

    total_pages = (len(accessible) + PLUGINS_PER_PAGE - 1) // PLUGINS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    start_idx = page * PLUGINS_PER_PAGE
    page_plugins = accessible[start_idx:start_idx + PLUGINS_PER_PAGE]

    text = f"🔌 **Plugin Listesi** (Sayfa {page + 1}/{total_pages})\n\n"
    text += "Bir plugin'e **dokun** → anında açılır/kapanır.\n"
    text += "Detay için **ℹ️ Detay Modu**nu aç, plugin'e dokun.\n\n"
    text += f"🟢 Yüklü · ⚪ Yüklü değil · ⭐ Zorunlu\n"
    text += f"📊 Toplam **{len(accessible)}** · ✅ Aktif **{len(active_plugins)}**"

    rows = []
    row_buf = []
    for p in page_plugins:
        name = p["name"]
        is_active = name in active_plugins
        is_default = p.get("default_active", False)
        star = "⭐" if is_default else ""
        # Renk durumu gösterir: yeşil = yüklü, gri = yüklü değil.
        # Premium emoji: yüklüyken yeşil onay, değilken plugin ikonu.
        style = ButtonBuilder.STYLE_SUCCESS if is_active else ButtonBuilder.STYLE_SECONDARY
        emoji = EMOJI_AKTIF if is_active else EMOJI_PASIF
        row_buf.append(btn.callback(f"{star} {name}".strip(), f"pt_{page}_{name}",
                                    style=style, icon_custom_emoji_id=emoji))
        if len(row_buf) == 2:
            rows.append(row_buf)
            row_buf = []
    if row_buf:
        rows.append(row_buf)

    nav = []
    if page > 0:
        nav.append(btn.callback(" Önceki", f"plugins_page_{page - 1}",
                                icon_custom_emoji_id=5834632747137638263))
    if page < total_pages - 1:
        nav.append(btn.callback(" Sonraki", f"plugins_page_{page + 1}",
                                icon_custom_emoji_id=5834933416323193844))
    if nav:
        rows.append(nav)

    rows.append([
        btn.callback(" Tümünü Aç", "pall_on", style=ButtonBuilder.STYLE_SUCCESS,
                     icon_custom_emoji_id=EMOJI_TUMU_AC),
        btn.callback(" Tümünü Kapat", "pall_off", style=ButtonBuilder.STYLE_DANGER,
                     icon_custom_emoji_id=EMOJI_TUMU_KAPAT),
    ])
    rows.append([
        btn.callback(" Varsayılanları Yükle", "pdefaults", style=ButtonBuilder.STYLE_PRIMARY,
                     icon_custom_emoji_id=EMOJI_VARSAYILAN),
        btn.callback(" Detay Modu", f"pim_{page}", style=ButtonBuilder.STYLE_SECONDARY,
                     icon_custom_emoji_id=EMOJI_DETAY),
    ])
    rows.append([btn.callback(" Pluginlerim", "my_plugins_0", style=ButtonBuilder.STYLE_PRIMARY,
                              icon_custom_emoji_id=5832711694165483426)])
    rows.append([btn.url(f" {config.PLUGIN_CHANNEL}", f"https://t.me/{config.PLUGIN_CHANNEL}",
                         style=ButtonBuilder.STYLE_PRIMARY, icon_custom_emoji_id=5832328832190784454)])
    rows.append([btn.callback(" Ana Menü", "main_menu", style=ButtonBuilder.STYLE_DANGER,
                              icon_custom_emoji_id=5832654562510511307)])
    return text, rows


async def build_info_mode_page(user_id, page):
    """Detay modu: plugin'e dokun → aç/kapa yerine bilgi kartı göster"""
    accessible = await accessible_plugins(user_id)
    if not accessible:
        return await build_plugins_page(user_id, page)

    user_data = await db.get_user(user_id)
    active_plugins = user_data.get("active_plugins", []) if user_data else []

    total_pages = (len(accessible) + PLUGINS_PER_PAGE - 1) // PLUGINS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    page_plugins = accessible[page * PLUGINS_PER_PAGE:(page + 1) * PLUGINS_PER_PAGE]

    text = f"ℹ️ **Detay Modu** (Sayfa {page + 1}/{total_pages})\n\n"
    text += "Bir plugin'e **dokun** → komutları ve açıklaması gösterilir.\n"
    text += "Aç/kapat için **Listeye Dön**."

    rows = []
    row_buf = []
    for p in page_plugins:
        name = p["name"]
        is_active = name in active_plugins
        style = ButtonBuilder.STYLE_SUCCESS if is_active else ButtonBuilder.STYLE_SECONDARY
        emoji = EMOJI_AKTIF if is_active else EMOJI_PASIF
        row_buf.append(btn.callback(f" {name}", f"pi_{page}_{name}",
                                    style=style, icon_custom_emoji_id=emoji))
        if len(row_buf) == 2:
            rows.append(row_buf)
            row_buf = []
    if row_buf:
        rows.append(row_buf)

    nav = []
    if page > 0:
        nav.append(btn.callback(" Önceki", f"pim_{page - 1}",
                                icon_custom_emoji_id=5834632747137638263))
    if page < total_pages - 1:
        nav.append(btn.callback(" Sonraki", f"pim_{page + 1}",
                                icon_custom_emoji_id=5834933416323193844))
    if nav:
        rows.append(nav)
    rows.append([btn.callback(" 🔌 Listeye Dön", f"plugins_page_{page}", style=ButtonBuilder.STYLE_PRIMARY)])
    rows.append([btn.callback(" Ana Menü", "main_menu", style=ButtonBuilder.STYLE_DANGER,
                              icon_custom_emoji_id=5832654562510511307)])
    return text, rows


async def build_plugin_info(user_id, page, name):
    """Tek plugin bilgi kartı (butonlu /pinfo karşılığı)"""
    plugin = await db.get_plugin(name)
    if not plugin:
        return None, None
    user_data = await db.get_user(user_id)
    active_plugins = user_data.get("active_plugins", []) if user_data else []
    is_active = name in active_plugins
    is_default = plugin.get("default_active", False)

    text = f"🔌 **Plugin: `{name}`**\n\n"
    text += f"📝 **Açıklama:** {plugin.get('description') or 'Açıklama yok'}\n"
    text += f"🔓 **Erişim:** {'Genel' if plugin.get('is_public', True) else 'Özel'}\n"
    text += f"📊 **Durum:** {'🟢 Yüklü' if is_active else '⚪ Yüklü değil'}"
    if is_default:
        text += " · ⭐ Zorunlu"
    text += "\n\n"
    commands = plugin.get("commands", [])
    if commands:
        text += f"🔧 **Komutlar ({len(commands)}):**\n"
        for cmd in commands:
            text += f"  • `.{cmd}`\n"
    else:
        text += "🔧 **Komutlar:** Yok\n"

    rows = []
    if is_active and not is_default:
        rows.append([btn.callback(f" ⚪ Kapat: {name}", f"pi{page}_off_{name}",
                                  style=ButtonBuilder.STYLE_DANGER)])
    elif not is_active:
        rows.append([btn.callback(f" 🟢 Yükle: {name}", f"pi{page}_on_{name}",
                                  style=ButtonBuilder.STYLE_SUCCESS)])
    rows.append([btn.callback(" Geri", f"pim_{page}", style=ButtonBuilder.STYLE_SECONDARY)])
    rows.append([btn.callback(" Ana Menü", "main_menu", style=ButtonBuilder.STYLE_DANGER,
                              icon_custom_emoji_id=5832654562510511307)])
    return text, rows


async def build_my_plugins_page(user_id, page):
    """Aktif pluginler sayfası: dokun → kaldır"""
    user_data = await db.get_user(user_id)
    active_plugins = user_data.get("active_plugins", []) if user_data else []

    if not active_plugins:
        text = config.MESSAGES["no_active_plugins"]
        text += "\n\n💡 Plugin listesinden bir plugin'e dokunarak yükleyebilirsin."
        rows = [
            [btn.callback(" Plugin Listesi", "plugins_page_0", style=ButtonBuilder.STYLE_PRIMARY,
                          icon_custom_emoji_id=5830184853236097449)],
            [btn.callback(" Ana Menü", "main_menu", style=ButtonBuilder.STYLE_DANGER,
                          icon_custom_emoji_id=5832654562510511307)],
        ]
        return text, rows

    total_pages = (len(active_plugins) + PLUGINS_PER_PAGE - 1) // PLUGINS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    start_idx = page * PLUGINS_PER_PAGE
    page_names = active_plugins[start_idx:start_idx + PLUGINS_PER_PAGE]

    text = f"📦 **Aktif Plugin'leriniz** (Sayfa {page + 1}/{total_pages})\n\n"
    text += "Kaldırmak için plugin'e **dokun**.\n\n"
    text += f"**Toplam:** {len(active_plugins)} aktif plugin"

    rows = []
    row_buf = []
    for name in page_names:
        plugin = await db.get_plugin(name)
        is_default = plugin.get("default_active", False) if plugin else False
        star = "⭐" if is_default else ""
        row_buf.append(btn.callback(f"{star} {name}".strip(), f"pm_{page}_{name}",
                                    style=ButtonBuilder.STYLE_SUCCESS,
                                    icon_custom_emoji_id=EMOJI_AKTIF))
        if len(row_buf) == 2:
            rows.append(row_buf)
            row_buf = []
    if row_buf:
        rows.append(row_buf)

    nav = []
    if page > 0:
        nav.append(btn.callback(" Önceki", f"my_plugins_{page - 1}",
                                icon_custom_emoji_id=5834632747137638263))
    if page < total_pages - 1:
        nav.append(btn.callback(" Sonraki", f"my_plugins_{page + 1}",
                                icon_custom_emoji_id=5834933416323193844))
    if nav:
        rows.append(nav)
    rows.append([btn.callback(" Tüm Plugin'ler", "plugins_page_0", style=ButtonBuilder.STYLE_PRIMARY,
                              icon_custom_emoji_id=5830184853236097449)])
    rows.append([btn.callback(" Ana Menü", "main_menu", style=ButtonBuilder.STYLE_DANGER,
                              icon_custom_emoji_id=5832654562510511307)])
    return text, rows


# ==========================================
# /start KOMUTU (Bot API - Renkli Butonlar)
# ==========================================
