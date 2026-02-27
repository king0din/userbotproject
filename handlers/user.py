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

# State management
user_states = {}
STATE_WAITING_PHONE = "waiting_phone"
STATE_WAITING_CODE = "waiting_code"
STATE_WAITING_2FA = "waiting_2fa"
STATE_WAITING_SESSION_TELETHON = "waiting_session_telethon"
STATE_WAITING_SESSION_PYROGRAM = "waiting_session_pyrogram"

PLUGINS_PER_PAGE = 8

def register_user_handlers(bot):
    """Kullanıcı handler'larını kaydet"""
    
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
        except: pass
        
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
        except: pass
        
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
        except: pass
        
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
        except: pass
        
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
    
    @bot.on(events.CallbackQuery(pattern=b"plugins_page_(\d+)"))
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
    
    @bot.on(events.CallbackQuery(pattern=b"my_plugins_(\d+)"))
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
    
    @bot.on(events.NewMessage(pattern=r'^/help$'))
    @check_ban
    async def help_command(event):
        """Help komutu - yardım menüsünü açar"""
        text, rows = await get_help_main_content(event.sender_id)
        await bot_api.send_message(chat_id=event.sender_id, text=text, reply_markup=btn.inline_keyboard(rows))
    
    async def get_help_main_content(user_id):
        """Ana yardım menüsü içeriği"""
        text = "❓ **Yardım Merkezi**\n\n"
        text += "Hoş geldiniz! Bu bot ile Telegram hesabınıza\n"
        text += "**Userbot** kurarak ek özellikler kazanabilirsiniz.\n\n"
        text += "📚 **Konu Seçin:**"
        
        rows = [
            [btn.callback("🤖 Userbot Nedir?", "help_what", style=ButtonBuilder.STYLE_PRIMARY)],
            [btn.callback("🔐 Nasıl Giriş Yapılır?", "help_login", style=ButtonBuilder.STYLE_PRIMARY)],
            [btn.callback("🔌 Plugin Nedir?", "help_plugins", style=ButtonBuilder.STYLE_PRIMARY)],
            [btn.callback("⚙️ Komutlar Nasıl Kullanılır?", "help_commands", style=ButtonBuilder.STYLE_PRIMARY)],
            [btn.callback("❓ Sıkça Sorulan Sorular", "help_faq", style=ButtonBuilder.STYLE_PRIMARY)],
            [btn.callback(" Ana Menü", "main_menu", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832654562510511307)]
        ]
        
        return text, rows
    
    @bot.on(events.CallbackQuery(data=b"help_main"))
    async def help_main_handler(event):
        text, rows = await get_help_main_content(event.sender_id)
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id, text=text, reply_markup=btn.inline_keyboard(rows))
        await event.answer()
    
    @bot.on(events.CallbackQuery(data=b"help_what"))
    async def help_what_handler(event):
        text = "🤖 **Userbot Nedir?**\n\n"
        text += "Userbot, Telegram hesabınızda çalışan bir bottur.\n"
        text += "Normal botlardan farklı olarak **sizin hesabınızla**\n"
        text += "işlem yapar.\n\n"
        
        text += "📌 **Ne İşe Yarar?**\n"
        text += "• Mesajları otomatik yanıtlama\n"
        text += "• Medya indirme (YouTube, Instagram vb.)\n"
        text += "• Çeviri yapma\n"
        text += "• AFK (meşgul) modu\n"
        text += "• Ve daha fazlası...\n\n"
        
        text += "⚠️ **Önemli:**\n"
        text += "Userbot sizin hesabınızla çalıştığı için\n"
        text += "komutları kendinize yazarsınız. Örneğin\n"
        text += "`.afk` yazıp gönderdiğinizde AFK moduna geçersiniz."
        
        rows = [[btn.callback(" Geri", "help_main", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832646161554480591)]]
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id, text=text, reply_markup=btn.inline_keyboard(rows))
        await event.answer()
    
    @bot.on(events.CallbackQuery(data=b"help_login"))
    async def help_login_handler(event):
        text = "🔐 **Nasıl Giriş Yapılır?**\n\n"
        text += "Userbot kullanmak için hesabınızla giriş yapmalısınız.\n"
        text += "3 farklı yöntem vardır:\n\n"
        
        text += "📱 **1. Telefon Numarası (Önerilen)**\n"
        text += "• `🔐 Giriş Yap` butonuna tıklayın\n"
        text += "• `📱 Telefon Numarası` seçin\n"
        text += "• Numaranızı girin: `+905551234567`\n"
        text += "• Telegram'dan gelen kodu girin\n"
        text += "• 2FA varsa şifrenizi girin\n\n"
        
        text += "📄 **2. Session String**\n"
        text += "• Daha önce oluşturduğunuz session'ı\n"
        text += "  yapıştırarak giriş yapabilirsiniz\n"
        text += "• Telethon veya Pyrogram desteklenir\n\n"
        
        text += "💾 **Oturum Kaydetme:**\n"
        text += "Giriş sonrası oturumu kaydederseniz,\n"
        text += "bir dahaki sefere tek tıkla giriş yapabilirsiniz."
        
        rows = [[btn.callback(" Geri", "help_main", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832646161554480591)]]
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id, text=text, reply_markup=btn.inline_keyboard(rows))
        await event.answer()
    
    @bot.on(events.CallbackQuery(data=b"help_plugins"))
    async def help_plugins_handler(event):
        text = "🔌 **Plugin Nedir & Nasıl Yüklenir?**\n\n"
        text += "Plugin'ler userbot'a özellik ekleyen eklentilerdir.\n"
        text += "Her plugin farklı komutlar sunar.\n\n"
        
        text += "📥 **Plugin Yükleme:**\n"
        text += "1️⃣ `🔌 Plugin'ler` menüsüne gidin\n"
        text += "2️⃣ İstediğiniz plugini bulun\n"
        text += "3️⃣ `/pactive <isim>` yazın\n"
        text += "   Örnek: `/pactive ses`\n\n"
        
        text += "📤 **Plugin Kaldırma:**\n"
        text += "• `/pinactive <isim>` yazın\n"
        text += "   Örnek: `/pinactive ses`\n\n"
        
        text += "ℹ️ **Plugin Bilgisi:**\n"
        text += "• `/pinfo <isim>` ile detayları görün\n"
        text += "   Örnek: `/pinfo ses`\n\n"
        
        text += "📢 **Yeni Plugin'ler:**\n"
        text += "Plugin kanalımızı takip ederek yeni\n"
        text += "plugin duyurularından haberdar olun!"
        
        rows = [
            [btn.url(f" Plugin Kanalı", f"https://t.me/{config.PLUGIN_CHANNEL}", style=ButtonBuilder.STYLE_PRIMARY, icon_custom_emoji_id=5832328832190784454)],
            [btn.callback(" Geri", "help_main", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832646161554480591)]
        ]
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id, text=text, reply_markup=btn.inline_keyboard(rows))
        await event.answer()
    
    @bot.on(events.CallbackQuery(data=b"help_commands"))
    async def help_commands_handler(event):
        text = "⚙️ **Komutlar Nasıl Kullanılır?**\n\n"
        
        text += "🤖 **Bot Komutları (Bu botta):**\n"
        text += "Bot komutları `/` ile başlar ve\n"
        text += "bu bota yazılır.\n\n"
        text += "Örnekler:\n"
        text += "• `/start` - Ana menü\n"
        text += "• `/pactive ses` - Plugin yükle\n"
        text += "• `/pinfo afk` - Plugin bilgisi\n\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        text += "⚡ **Userbot Komutları (Telegram'da):**\n"
        text += "Userbot komutları `.` ile başlar ve\n"
        text += "**herhangi bir sohbete** yazılır.\n\n"
        text += "Örnekler:\n"
        text += "• `.afk Meşgulüm` - AFK modu aç\n"
        text += "• `.tts Merhaba` - Sesli mesaj\n"
        text += "• `.tr Hello` - Çeviri yap\n\n"
        
        text += "💡 **İpucu:**\n"
        text += "Userbot komutlarını kendinize (Kayıtlı\n"
        text += "Mesajlar) yazarak test edebilirsiniz."
        
        rows = [[btn.callback(" Geri", "help_main", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832646161554480591)]]
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id, text=text, reply_markup=btn.inline_keyboard(rows))
        await event.answer()
    
    @bot.on(events.CallbackQuery(data=b"help_faq"))
    async def help_faq_handler(event):
        text = "❓ **Sıkça Sorulan Sorular**\n\n"
        
        text += "**S: Hesabım yasaklanır mı?**\n"
        text += "C: Normal kullanımda risk düşüktür.\n"
        text += "Spam yapmayın, çok hızlı mesaj atmayın.\n\n"
        
        text += "**S: Şifremi veriyor muyum?**\n"
        text += "C: Hayır! Sadece Telegram'ın gönderdiği\n"
        text += "doğrulama kodunu giriyorsunuz.\n\n"
        
        text += "**S: Birisi hesabıma erişebilir mi?**\n"
        text += "C: Session'ınız şifreli saklanır.\n"
        text += "Çıkış yapınca silinir.\n\n"
        
        text += "**S: Plugin çalışmıyor?**\n"
        text += "C: Önce giriş yaptığınızdan emin olun.\n"
        text += "Sonra plugini yeniden yükleyin.\n\n"
        
        text += "**S: Komut yazdım ama olmuyor?**\n"
        text += "C: Userbot komutları `.` ile başlar\n"
        text += "ve Telegram'da yazılır, bu botta değil.\n\n"
        
        text += f"📞 **Destek:** @{config.OWNER_USERNAME}"
        
        rows = [[btn.callback(" Geri", "help_main", style=ButtonBuilder.STYLE_DANGER, icon_custom_emoji_id=5832646161554480591)]]
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id, text=text, reply_markup=btn.inline_keyboard(rows))
        await event.answer()
    
    @bot.on(events.CallbackQuery(data=b"commands"))
    async def commands_handler(event):
        text = "📝 **Bot Komutları**\n\n"
        
        text += "**👤 Genel Komutlar:**\n"
        for cmd, desc in config.COMMANDS["user"].items():
            text += f"• `{cmd}` - {desc}\n"
        
        if event.sender_id == config.OWNER_ID or await db.is_sudo(event.sender_id):
            text += "\n**👑 Admin Komutları:**\n"
            for cmd, desc in config.COMMANDS["admin"].items():
                text += f"• `{cmd}` - {desc}\n"
        
        await event.edit(text, buttons=[[Button.inline("🏠 Ana Menü", b"main_menu")]])
        await event.answer()
    
    @bot.on(events.CallbackQuery(data=b"close"))
    async def close_handler(event):
        await event.delete()
    
    @bot.on(events.CallbackQuery(data=b"noop"))
    async def noop_handler(event):
        await event.answer()
    
    # ==========================================
    # INLINE QUERY HANDLER
    # ==========================================
    
    @bot.on(events.InlineQuery())
    async def inline_query_handler(event):
        """Inline query handler - .start komutu için butonlu mesaj"""
        query = event.text.strip()
        user_id = event.sender_id
        
        # panel_USER_ID formatını kontrol et
        if query.startswith("panel_"):
            try:
                target_user_id = int(query.split("_")[1])
                
                # Sadece kendi panelini görebilir
                if target_user_id != user_id:
                    return
                
                # Kullanıcı bilgilerini al
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
                
                text += f"\n📱 Detaylı ayarlar için butona tıklayın."
                
                # Butonlar
                bot_username = config.BOT_USERNAME or ""
                buttons = []
                
                if bot_username:
                    buttons.append([Button.url("⚙️ Ayarları Aç", f"https://t.me/{bot_username}?start=panel")])
                    
                    if is_logged_in:
                        buttons.append([
                            Button.url("🔌 Pluginler", f"https://t.me/{bot_username}?start=plugins"),
                            Button.url("📦 Aktifler", f"https://t.me/{bot_username}?start=my_plugins")
                        ])
                
                # Inline sonuç oluştur
                from telethon.tl.types import InputBotInlineResult, InputBotInlineMessageText
                
                await event.answer(
                    results=[
                        event.builder.article(
                            title="⚡ Userbot Kontrol Paneli",
                            description=f"{status_text} | {len(active_plugins)} plugin",
                            text=text,
                            buttons=buttons if buttons else None
                        )
                    ],
                    cache_time=0
                )
            except Exception as e:
                print(f"[INLINE] Hata: {e}")
                import traceback
                traceback.print_exc()
