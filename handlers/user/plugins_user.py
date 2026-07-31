# ============================================
# KingTG UserBot Service - User / plugins_user
# Kullanıcının plugin listesi ve aktif/pasif etme
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

    @bot.on(events.CallbackQuery(pattern=rb"plugins_page_(\d+)"))
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
        # Devre dışı pluginleri gösterme
        accessible_plugins = []
        for p in all_plugins:
            # Devre dışı pluginleri atla
            if p.get("is_disabled", False):
                continue
            # Genel veya izinli ise ekle
            if p.get("is_public", True) or user_id in p.get("allowed_users", []):
                # Kısıtlı kullanıcıysa atla
                if user_id not in p.get("restricted_users", []):
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
            is_default = p.get("default_active", False)
            status = "🟢" if is_active else "⚪"
            default_icon = "⭐" if is_default else ""
            
            # Komutları göster
            cmds = p.get("commands", [])[:2]
            cmd_text = ", ".join([f"`.{c}`" for c in cmds])
            if len(p.get("commands", [])) > 2:
                cmd_text += "..."
            
            text += f"{status}{default_icon} **{name}**\n"
            text += f"   └ {cmd_text}\n"
            text += f"   └ Yükle: `/pactive {name}`\n\n"
        
        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        text += f"🟢 Yüklü | ⚪ Yüklü değil | ⭐ Zorunlu\n"
        text += f"📊 Toplam: **{len(accessible_plugins)}** plugin\n"
        text += f"✅ Aktif: **{len(active_plugins)}** plugin\n\n"
        text += f"💡 **Detay için:** `/pinfo <isim>`"
        
        # Sayfalama butonları
        nav_buttons = []
        if page > 0:
            nav_buttons.append(btn.callback(" Önceki", f"plugins_page_{page - 1}", icon_custom_emoji_id=5834632747137638263))
        if page < total_pages - 1:
            nav_buttons.append(btn.callback(" Sonraki", f"plugins_page_{page + 1}", icon_custom_emoji_id=5834933416323193844))
        
        rows = []
        if nav_buttons:
            rows.append(nav_buttons)
        rows.append([btn.callback(" Pluginlerim", "my_plugins_0", style=ButtonBuilder.STYLE_PRIMARY, icon_custom_emoji_id=5832711694165483426)])
        rows.append([btn.url(f" {config.PLUGIN_CHANNEL}", f"https://t.me/{config.PLUGIN_CHANNEL}", style=ButtonBuilder.STYLE_PRIMARY, icon_custom_emoji_id=5832328832190784454)])
        rows.append([btn.callback(" Ana Menü", "main_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832654562510511307)])
        
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id, text=text, reply_markup=btn.inline_keyboard(rows))
        await event.answer()
    
    # ==========================================
    # PLUGİNLERİM - SAYFALI
    # ==========================================
    

    @bot.on(events.CallbackQuery(pattern=rb"my_plugins_(\d+)"))
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
            rows = [
                [btn.callback(" Plugin Listesi", "plugins_page_0", style=ButtonBuilder.STYLE_PRIMARY, icon_custom_emoji_id=5830184853236097449)],
                [btn.callback(" Ana Menü", "main_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832654562510511307)]
            ]
            await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id, text=text, reply_markup=btn.inline_keyboard(rows))
            await event.answer()
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
            nav_buttons.append(btn.callback(" Önceki", f"my_plugins_{page - 1}", icon_custom_emoji_id=5834632747137638263))
        if page < total_pages - 1:
            nav_buttons.append(btn.callback(" Sonraki", f"my_plugins_{page + 1}", icon_custom_emoji_id=5834933416323193844))
        
        rows = []
        if nav_buttons:
            rows.append(nav_buttons)
        rows.append([btn.callback(" Tüm Plugin'ler", "plugins_page_0", style=ButtonBuilder.STYLE_PRIMARY, icon_custom_emoji_id=5830184853236097449)])
        rows.append([btn.callback(" Ana Menü", "main_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832654562510511307)])
        
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id, text=text, reply_markup=btn.inline_keyboard(rows))
        await event.answer()
    
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
        
        # Devre dışı plugin kontrolü
        plugin = await db.get_plugin(plugin_name)
        if plugin and plugin.get("is_disabled", False):
            await event.respond(
                f"⛔ **`{plugin_name}` devre dışı!**\n\n"
                f"Bu plugin yönetici tarafından devre dışı bırakılmış.\n"
                f"Şu anda kullanılamaz."
            )
            return
        
        user_data = await db.get_user(event.sender_id)
        if not user_data or not user_data.get("is_logged_in"):
            await event.respond("❌ Önce giriş yapmalısınız.")
            return
        
        msg = await event.respond("⏳ Bağlantı kuruluyor...")
        
        # Smart manager ile client al veya oluştur
        client = await smart_session_manager.get_or_create_client(event.sender_id)
        if not client:
            await msg.edit("❌ Userbot bağlantısı kurulamadı. Lütfen tekrar giriş yapın.")
            return
        
        await msg.edit("⏳ Plugin yükleniyor...")
        success, message = await plugin_manager.activate_plugin(event.sender_id, plugin_name, client)
        await msg.edit(message)
        
        if success:
            await send_log(bot, "plugin", f"Aktif: {plugin_name}", event.sender_id)
    

    @bot.on(events.NewMessage(pattern=r'^/pinactive\s+(\S+)$'))
    @check_ban
    async def pinactive_command(event):
        plugin_name = event.pattern_match.group(1)
        
        # Varsayılan aktif plugin kontrolü
        plugin = await db.get_plugin(plugin_name)
        if plugin and plugin.get("default_active", False):
            await event.respond(
                f"⚠️ **`{plugin_name}` deaktif edilemez!**\n\n"
                f"Bu plugin yönetici tarafından varsayılan olarak aktif ayarlanmış.\n"
                f"Tüm kullanıcılarda zorunlu olarak çalışır."
            )
            return
        
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
