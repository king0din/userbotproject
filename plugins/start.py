"""
Açıklama:
herhangi bir sohbete kullanarak bot ayarlarınıza kolaylıkla erişebilirsiniz.

🔧 Komutlar: .start veya .panel, .plugins veya .pluginler,.pload, .punload, .mystats,.uhelp
🚨 Tür: #bot_ayar


Komular hakında:
.start veya .panel: Kontrol panelini açar.
.plugins veya .pluginler: Plugin listesini gösterir.
.pload <isim>: Plugin yükler.
.punload <isim>: Plugin kaldırır.
.uhelp: Userbot yardım komutu.
.mystats: İstatistiklerini gösterir.
"""


from telethon import events, Button
import config
from database import database as db
from utils.logger import get_logger

log = get_logger(__name__)


# Plugin bilgileri
__name__ = "inline_start"
__description__ = "Herhangi bir sohbetten .start ile ayar panelini aç"
__commands__ = ["start", "panel", "plugins", "pluginler", "pload", "punload", "mystats", "uhelp"]

# Handler referanslarını sakla (global)
_handlers = {}
_bot_handlers_registered = False

def get_bot_username():
    """Bot username'ini al"""
    import config as cfg
    import os
    username = getattr(cfg, 'BOT_USERNAME', '') or ''
    if username:
        return username
    try:
        if os.path.exists('.bot_username'):
            with open('.bot_username', 'r') as f:
                return f.read().strip()
    except:
        pass
    return ''

def get_bot():
    """Ana bot objesini al"""
    try:
        # main.py'deki bot objesine eriş
        import sys
        if 'main' in sys.modules:
            return getattr(sys.modules['main'], 'bot', None)
        # Alternatif yol
        import __main__
        return getattr(__main__, 'bot', None)
    except:
        pass
    return None

def register_bot_handlers(bot):
    """Bot'a inline handler'ları TÜM hesaplar için yalnızca BİR kez kaydet."""
    
    if not bot:
        return
    # Her hesap start.py'yi ayrı modül olarak yüklediğinden modül-global
    # bayrak ÇİFT KAYDA yol açıyordu (menü kendi kendine ileri-geri gidiyordu).
    # Bayrağı paylaşılan bot nesnesinde tutmak bunu önler.
    if getattr(bot, "_inline_start_registered", False):
        return
    
    bot._inline_start_registered = True
    
    # ==========================================
    # INLINE QUERY HANDLER
    # ==========================================
    
    @bot.on(events.InlineQuery())
    async def inline_panel_query(event):
        """Inline query - .start için panel"""
        query = event.text.strip()
        user_id = event.sender_id
        bot_username = get_bot_username()
        
        try:
            if query.startswith("panel_"):
                target_user_id = int(query.split("_")[1])
                if target_user_id != user_id:
                    return
                
                user_data = await db.get_user(user_id)
                if not user_data:
                    return
                
                active_plugins = user_data.get("active_plugins", [])
                is_logged_in = user_data.get("is_logged_in", False)
                username = user_data.get("userbot_username", "?")
                
                status_emoji = "🟢" if is_logged_in else "🔴"
                status_text = "Aktif" if is_logged_in else "Pasif"
                
                text = f"⚡ **Userbot Kontrol Paneli**\n\n"
                text += f"{status_emoji} **Durum:** {status_text}\n"
                
                if is_logged_in:
                    text += f"👤 **Hesap:** @{username}\n"
                    text += f"🔌 **Aktif Plugin:** {len(active_plugins)}\n"
                
                text += f"\n📱 Aşağıdaki butonları kullanabilirsiniz."
                
                buttons = []
                if is_logged_in:
                    buttons.append([
                        Button.inline("🔌 Tüm Pluginler", f"ip_plugins_{user_id}_0".encode()),
                        Button.inline("📦 Yüklü Pluginler", f"ip_active_{user_id}_0".encode())
                    ])
                buttons.append([
                    Button.inline("❓ Userbot Yardım", f"ip_help_{user_id}".encode()),
                    Button.inline("📢 Plugin Kanalı", f"ip_channel_{user_id}".encode())
                ])
                if bot_username:
                    buttons.append([
                        Button.url("🤖 Bot Ayarları", f"https://t.me/{bot_username}?start=panel")
                    ])
                
                await event.answer(
                    results=[
                        event.builder.article(
                            title="⚡ Userbot Kontrol Paneli",
                            description=f"{status_text} | {len(active_plugins)} plugin",
                            text=text,
                            buttons=buttons
                        )
                    ],
                    cache_time=0
                )
        except Exception as e:
            log.error("Inline query hatası", exc_info=True)
    
    # ==========================================
    # CALLBACK HANDLERS
    # ==========================================
    
    @bot.on(events.CallbackQuery(pattern=rb"ip_plugins_(\d+)_?(\d*)"))
    async def ip_plugins_cb(event):
        """Tüm pluginler - sayfalı"""
        match = event.pattern_match
        target_user_id = int(match.group(1).decode())
        page = int(match.group(2).decode()) if match.group(2) else 0
        
        if target_user_id != event.sender_id:
            await event.answer("❌ Bu panel size ait değil!", alert=True)
            return
        
        user_data = await db.get_user(event.sender_id)
        active_plugins = user_data.get("active_plugins", []) if user_data else []
        all_plugins = await db.get_all_plugins()
        
        accessible = [p for p in all_plugins if not p.get("is_disabled") and 
                     (p.get("is_public", True) or event.sender_id in p.get("allowed_users", [])) and
                     event.sender_id not in p.get("restricted_users", [])]
        
        # Sayfalama
        per_page = 8
        total = len(accessible)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        page = max(0, min(page, total_pages - 1))
        start = page * per_page
        end = start + per_page
        page_plugins = accessible[start:end]
        
        if not accessible:
            text = "📭 **Henüz plugin yok.**"
        else:
            text = f"🔌 **Tüm Pluginler** ({total} adet)\n"
            text += f"📄 Sayfa {page + 1}/{total_pages}\n\n"
            
            for p in page_plugins:
                name = p.get("name", "?")
                status = "🟢" if name in active_plugins else "⚪"
                default = "⭐" if p.get("default_active") else ""
                cmds = ", ".join([f"`.{c}`" for c in p.get("commands", [])[:2]])
                text += f"{status}{default} **{name}**"
                if cmds:
                    text += f" → {cmds}"
                text += "\n"
            
            text += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            text += f"📥 `.pload <isim>` | 📤 `.punload <isim>`"
        
        # Butonlar
        buttons = []
        
        # Sayfalama butonları
        if total_pages > 1:
            nav_row = []
            if page > 0:
                nav_row.append(Button.inline("◀️ Önceki", f"ip_plugins_{target_user_id}_{page-1}".encode()))
            nav_row.append(Button.inline(f"📄 {page+1}/{total_pages}", b"noop"))
            if page < total_pages - 1:
                nav_row.append(Button.inline("Sonraki ▶️", f"ip_plugins_{target_user_id}_{page+1}".encode()))
            buttons.append(nav_row)
        
        buttons.append([
            Button.inline("📦 Yüklü", f"ip_active_{target_user_id}_0".encode()),
            Button.inline("📢 Kanal", f"ip_channel_{target_user_id}".encode())
        ])
        buttons.append([Button.inline("🔙 Geri", f"ip_main_{target_user_id}".encode())])
        
        try:
            await event.edit(text, buttons=buttons)
        except:
            pass
        await event.answer()
    
    @bot.on(events.CallbackQuery(pattern=rb"ip_active_(\d+)_?(\d*)"))
    async def ip_active_cb(event):
        """Yüklü pluginler - sayfalı"""
        match = event.pattern_match
        target_user_id = int(match.group(1).decode())
        page = int(match.group(2).decode()) if match.group(2) else 0
        
        if target_user_id != event.sender_id:
            await event.answer("❌ Bu panel size ait değil!", alert=True)
            return
        
        user_data = await db.get_user(event.sender_id)
        active_plugins = user_data.get("active_plugins", []) if user_data else []
        
        # Sayfalama
        per_page = 8
        total = len(active_plugins)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        page = max(0, min(page, total_pages - 1))
        start = page * per_page
        end = start + per_page
        page_plugins = active_plugins[start:end]
        
        if not active_plugins:
            text = "📭 **Yüklü plugin yok.**\n\n`.pload <isim>` ile yükleyin"
        else:
            text = f"📦 **Yüklü Pluginler** ({total} adet)\n"
            text += f"📄 Sayfa {page + 1}/{total_pages}\n\n"
            
            for name in page_plugins:
                plugin = await db.get_plugin(name)
                if plugin:
                    default = "⭐" if plugin.get("default_active") else ""
                    cmds = ", ".join([f"`.{c}`" for c in plugin.get("commands", [])[:2]])
                    text += f"✅{default} **{name}**"
                    if cmds:
                        text += f" → {cmds}"
                    text += "\n"
                else:
                    text += f"❓ **{name}** (silinmiş?)\n"
            
            text += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            text += f"📤 `.punload <isim>` ile kaldır"
        
        # Butonlar
        buttons = []
        
        # Sayfalama butonları
        if total_pages > 1:
            nav_row = []
            if page > 0:
                nav_row.append(Button.inline("◀️ Önceki", f"ip_active_{target_user_id}_{page-1}".encode()))
            nav_row.append(Button.inline(f"📄 {page+1}/{total_pages}", b"noop"))
            if page < total_pages - 1:
                nav_row.append(Button.inline("Sonraki ▶️", f"ip_active_{target_user_id}_{page+1}".encode()))
            buttons.append(nav_row)
        
        buttons.append([
            Button.inline("🔌 Tümü", f"ip_plugins_{target_user_id}_0".encode()),
            Button.inline("📢 Kanal", f"ip_channel_{target_user_id}".encode())
        ])
        buttons.append([Button.inline("🔙 Geri", f"ip_main_{target_user_id}".encode())])
        
        try:
            await event.edit(text, buttons=buttons)
        except:
            pass
        await event.answer()
    
    @bot.on(events.CallbackQuery(pattern=rb"ip_help_(\d+)"))
    async def ip_help_cb(event):
        """Yardım"""
        target_user_id = int(event.pattern_match.group(1).decode())
        if target_user_id != event.sender_id:
            await event.answer("❌ Bu panel size ait değil!", alert=True)
            return
        
        text = "📚 **Userbot Yardım**\n\n"
        text += "**🎛️ Panel:**\n"
        text += "`.start` → Kontrol paneli\n"
        text += "`.plugins` → Plugin listesi\n"
        text += "`.mystats` → İstatistikler\n\n"
        text += "**🔌 Plugin:**\n"
        text += "`.pload <isim>` → Yükle\n"
        text += "`.punload <isim>` → Kaldır\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        text += "💡 Komutlar `.` ile başlar"
        
        buttons = [
            [Button.inline("🔌 Pluginler", f"ip_plugins_{target_user_id}_0".encode()),
             Button.inline("📦 Yüklü", f"ip_active_{target_user_id}_0".encode())],
            [Button.inline("🔙 Geri", f"ip_main_{target_user_id}".encode())]
        ]
        
        try:
            await event.edit(text, buttons=buttons)
        except:
            pass
        await event.answer()
    
    @bot.on(events.CallbackQuery(pattern=rb"ip_channel_(\d+)"))
    async def ip_channel_cb(event):
        """Plugin kanalı"""
        target_user_id = int(event.pattern_match.group(1).decode())
        if target_user_id != event.sender_id:
            await event.answer("❌ Bu panel size ait değil!", alert=True)
            return
        
        channel = getattr(config, 'PLUGIN_CHANNEL', 'KingTGPlugins')
        text = "📢 **Plugin Kanalı**\n\n"
        text += f"Yeni pluginler için kanalı takip edin!\n\n"
        text += f"📌 @{channel}\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        text += "💡 `.pload <isim>` ile yükleyin"
        
        buttons = [
            [Button.url(f"📢 @{channel}", f"https://t.me/{channel}")],
            [Button.inline("🔙 Geri", f"ip_main_{target_user_id}".encode())]
        ]
        
        try:
            await event.edit(text, buttons=buttons)
        except:
            pass
        await event.answer()
    
    @bot.on(events.CallbackQuery(pattern=rb"ip_main_(\d+)"))
    async def ip_main_cb(event):
        """Ana panel"""
        target_user_id = int(event.pattern_match.group(1).decode())
        if target_user_id != event.sender_id:
            await event.answer("❌ Bu panel size ait değil!", alert=True)
            return
        
        bot_username = get_bot_username()
        user_data = await db.get_user(event.sender_id)
        if not user_data:
            await event.answer("❌ Hata!", alert=True)
            return
        
        active_plugins = user_data.get("active_plugins", [])
        is_logged_in = user_data.get("is_logged_in", False)
        username = user_data.get("userbot_username", "?")
        
        status_emoji = "🟢" if is_logged_in else "🔴"
        
        text = f"⚡ **Userbot Kontrol Paneli**\n\n"
        text += f"{status_emoji} **Durum:** {'Aktif' if is_logged_in else 'Pasif'}\n"
        if is_logged_in:
            text += f"👤 **Hesap:** @{username}\n"
            text += f"🔌 **Aktif Plugin:** {len(active_plugins)}\n"
        text += f"\n📱 Butonları kullanabilirsiniz."
        
        buttons = []
        if is_logged_in:
            buttons.append([
                Button.inline("🔌 Tüm Pluginler", f"ip_plugins_{target_user_id}_0".encode()),
                Button.inline("📦 Yüklü Pluginler", f"ip_active_{target_user_id}_0".encode())
            ])
        buttons.append([
            Button.inline("❓ Yardım", f"ip_help_{target_user_id}".encode()),
            Button.inline("📢 Kanal", f"ip_channel_{target_user_id}".encode())
        ])
        if bot_username:
            buttons.append([Button.url("🤖 Bot Ayarları", f"https://t.me/{bot_username}?start=panel")])
        
        try:
            await event.edit(text, buttons=buttons)
        except:
            pass
        await event.answer()
    
    log.info("Bot inline handler'ları kaydedildi")


def register_handlers(client, user_id):
    """Userbot handler'larını kaydet"""
    global _handlers
    
    # Bot handler'larını kaydet (bir kez)
    bot = get_bot()
    if bot:
        register_bot_handlers(bot)
    
    # Önceki handler'ları temizle
    if user_id in _handlers:
        for handler, event in _handlers[user_id]:
            try:
                client.remove_event_handler(handler, event)
            except:
                pass
        del _handlers[user_id]
    
    _handlers[user_id] = []
    
    # ==========================================
    # USERBOT KOMUTLARI
    # ==========================================
    
    async def cmd_start(event):
        """.start komutu"""
        if not event.out:
            return
        
        bot_username = get_bot_username()
        try:
            await event.delete()
        except:
            pass
        
        user_data = await db.get_user(user_id)
        if not user_data:
            await client.send_message(event.chat_id, "❌ Kullanıcı verisi bulunamadı.")
            return
        
        if bot_username:
            try:
                results = await client.inline_query(bot_username, f"panel_{user_id}")
                if results:
                    await results[0].click(event.chat_id)
                    return
            except Exception as e:
                err = str(e).lower()
                if "inline" in err:
                    await client.send_message(event.chat_id, 
                        f"⚠️ Bu sohbette inline mod kapalı.\n💡 @{bot_username} botuna gidin.")
                    return
        
        # Fallback
        text = "⚡ **Userbot Paneli**\n\n"
        text += "`.plugins` → Plugin listesi\n"
        text += "`.pload <isim>` → Plugin yükle\n"
        text += "`.punload <isim>` → Plugin kaldır\n"
        text += "`.mystats` → İstatistikler"
        await client.send_message(event.chat_id, text)
    
    async def cmd_plugins(event):
        """.plugins komutu"""
        if not event.out:
            return
        try:
            await event.delete()
        except:
            pass
        
        user_data = await db.get_user(user_id)
        if not user_data or not user_data.get("is_logged_in"):
            await event.respond("❌ Önce giriş yapın.")
            return
        
        active = user_data.get("active_plugins", [])
        all_p = await db.get_all_plugins()
        accessible = [p for p in all_p if not p.get("is_disabled") and 
                     (p.get("is_public", True) or user_id in p.get("allowed_users", [])) and
                     user_id not in p.get("restricted_users", [])]
        
        if not accessible:
            await event.respond("📭 Henüz plugin yok.")
            return
        
        text = f"🔌 **Pluginler** ({len(accessible)})\n\n"
        for p in accessible[:15]:
            name = p.get("name", "?")
            st = "🟢" if name in active else "⚪"
            df = "⭐" if p.get("default_active") else ""
            text += f"{st}{df} `{name}`\n"
        if len(accessible) > 15:
            text += f"... +{len(accessible)-15}\n"
        text += f"\n📥 `.pload <isim>`"
        await event.respond(text)
    
    async def cmd_pload(event):
        """.pload komutu"""
        if not event.out:
            return
        match = event.pattern_match
        if not match:
            return
        name = match.group(1)
        try:
            await event.delete()
        except:
            pass
        
        plugin = await db.get_plugin(name)
        if not plugin:
            await event.respond(f"❌ `{name}` bulunamadı.")
            return
        if plugin.get("is_disabled"):
            await event.respond(f"⛔ `{name}` devre dışı.")
            return
        
        user_data = await db.get_user(user_id)
        active = user_data.get("active_plugins", []) if user_data else []
        if name in active:
            await event.respond(f"ℹ️ `{name}` zaten aktif.")
            return
        
        active.append(name)
        await db.update_user(user_id, {"active_plugins": active})
        
        from userbot.plugins import plugin_manager
        ok, msg = await plugin_manager.activate_plugin(user_id, name, client)
        if ok:
            cmds = ", ".join([f"`.{c}`" for c in plugin.get("commands", [])[:3]])
            await event.respond(f"✅ **{name}** yüklendi!\n🔧 {cmds}")
        else:
            await event.respond(f"❌ {msg}")
    
    async def cmd_punload(event):
        """.punload komutu"""
        if not event.out:
            return
        match = event.pattern_match
        if not match:
            return
        name = match.group(1)
        try:
            await event.delete()
        except:
            pass
        
        plugin = await db.get_plugin(name)
        if not plugin:
            await event.respond(f"❌ `{name}` bulunamadı.")
            return
        if plugin.get("default_active"):
            await event.respond(f"⭐ `{name}` zorunlu, kaldırılamaz.")
            return
        
        user_data = await db.get_user(user_id)
        active = user_data.get("active_plugins", []) if user_data else []
        if name not in active:
            await event.respond(f"ℹ️ `{name}` zaten aktif değil.")
            return
        
        active.remove(name)
        await db.update_user(user_id, {"active_plugins": active})
        
        from userbot.plugins import plugin_manager
        await plugin_manager.deactivate_plugin(user_id, name)
        await event.respond(f"✅ **{name}** kaldırıldı.")
    
    async def cmd_mystats(event):
        """.mystats komutu"""
        if not event.out:
            return
        try:
            await event.delete()
        except:
            pass
        
        user_data = await db.get_user(user_id)
        if not user_data:
            await event.respond("❌ Veri yok.")
            return
        
        active = user_data.get("active_plugins", [])
        logged = user_data.get("is_logged_in", False)
        uname = user_data.get("userbot_username", "?")
        
        text = "📊 **İstatistikler**\n\n"
        text += f"{'🟢' if logged else '🔴'} {'Aktif' if logged else 'Pasif'}\n"
        if logged:
            text += f"👤 @{uname}\n"
            text += f"🔌 {len(active)} plugin\n"
        text += f"\n💡 `.start` → Panel"
        await event.respond(text)
    
    async def cmd_uhelp(event):
        """.uhelp komutu"""
        if not event.out:
            return
        try:
            await event.delete()
        except:
            pass
        
        text = "📚 **Komutlar**\n\n"
        text += "`.start` → Panel (butonlu)\n"
        text += "`.plugins` → Liste\n"
        text += "`.pload <isim>` → Yükle\n"
        text += "`.punload <isim>` → Kaldır\n"
        text += "`.mystats` → İstatistik\n"
        text += "`.uhelp` → Yardım"
        await event.respond(text)
    
    # Handler'ları kaydet
    h1 = events.NewMessage(pattern=r'^\.(start|panel)$', outgoing=True)
    h2 = events.NewMessage(pattern=r'^\.(plugins|pluginler)$', outgoing=True)
    h3 = events.NewMessage(pattern=r'^\.pload\s+(\S+)$', outgoing=True)
    h4 = events.NewMessage(pattern=r'^\.punload\s+(\S+)$', outgoing=True)
    h5 = events.NewMessage(pattern=r'^\.mystats$', outgoing=True)
    h6 = events.NewMessage(pattern=r'^\.uhelp$', outgoing=True)
    
    client.add_event_handler(cmd_start, h1)
    client.add_event_handler(cmd_plugins, h2)
    client.add_event_handler(cmd_pload, h3)
    client.add_event_handler(cmd_punload, h4)
    client.add_event_handler(cmd_mystats, h5)
    client.add_event_handler(cmd_uhelp, h6)
    
    _handlers[user_id] = [(cmd_start, h1), (cmd_plugins, h2), (cmd_pload, h3),
                          (cmd_punload, h4), (cmd_mystats, h5), (cmd_uhelp, h6)]
    
    log.info("Yüklendi: user=%s", user_id)


def unregister_handlers(client, user_id):
    """Handler'ları kaldır"""
    global _handlers
    if user_id in _handlers:
        for h, e in _handlers[user_id]:
            try:
                client.remove_event_handler(h, e)
            except:
                pass
        del _handlers[user_id]
    log.info("Kaldırıldı: user=%s", user_id)