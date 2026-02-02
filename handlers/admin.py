# ============================================
# KingTG UserBot Service - Admin Handlers
# ============================================

import os
import sys
import asyncio
import subprocess
import time
from datetime import datetime
from telethon import events, Button
from telethon.tl.functions.users import GetFullUserRequest
import config
from database import database as db
from userbot.manager import userbot_manager
from userbot.plugins import plugin_manager
from utils import owner_only, sudo_only, send_log, get_readable_time, back_button

start_time = time.time()
USERS_PER_PAGE = 10

def register_admin_handlers(bot):
    """Admin handler'larını kaydet"""
    
    # ==========================================
    # AYARLAR MENÜSÜ
    # ==========================================
    
    async def get_settings_text():
        settings = await db.get_settings()
        stats = await db.get_stats()
        
        mode = settings.get("bot_mode", "public")
        maint = settings.get("maintenance", False)
        
        mode_text = "🌐 Genel" if mode == "public" else "🔒 Özel"
        maint_text = "🔧 Açık" if maint else "✅ Kapalı"
        
        text = "⚙️ **Bot Ayarları**\n\n"
        text += f"📍 **Mod:** {mode_text}\n"
        text += f"🔧 **Bakım:** {maint_text}\n\n"
        text += f"👥 **Kullanıcı:** `{stats.get('total_users', 0)}`\n"
        text += f"✅ **Aktif Userbot:** `{stats.get('logged_in_users', 0)}`\n"
        text += f"🔌 **Plugin:** `{stats.get('total_plugins', 0)}`\n"
        text += f"👑 **Sudo:** `{stats.get('sudo_users', 0)}`\n"
        text += f"🚫 **Ban:** `{stats.get('banned_users', 0)}`"
        
        return text, settings
    
    async def get_settings_buttons(settings, is_owner: bool):
        mode = settings.get("bot_mode", "public")
        maint = settings.get("maintenance", False)
        
        if is_owner:
            buttons = [
                [
                    Button.inline("🔒 Özel Yap" if mode == "public" else "🌐 Genel Yap", b"toggle_mode"),
                    Button.inline("✅ Bakım Kapat" if maint else "🔧 Bakım Aç", b"toggle_maintenance")
                ],
                [Button.inline("👥 Kullanıcılar", b"users_list_0"),
                 Button.inline("🔌 Plugin'ler", b"admin_plugins")],
                [Button.inline("👑 Sudo", b"sudo_management"),
                 Button.inline("🚫 Ban", b"ban_management")],
                [Button.inline("📊 İstatistik", b"stats"),
                 Button.inline("📋 Loglar", b"view_logs")],
                [Button.inline("🔄 Güncelle", b"update_bot"),
                 Button.inline("🔃 Yeniden Başlat", b"restart_bot")],
                [Button.inline("📝 Komutlar", b"admin_commands")],
                back_button("main_menu")
            ]
        else:
            buttons = [
                [Button.inline("🔌 Plugin'ler", b"admin_plugins")],
                [Button.inline("📊 İstatistik", b"stats")],
                back_button("main_menu")
            ]
        return buttons
    
    @bot.on(events.CallbackQuery(data=b"settings_menu"))
    async def settings_menu_handler(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        
        text, settings = await get_settings_text()
        buttons = await get_settings_buttons(settings, event.sender_id == config.OWNER_ID)
        await event.edit(text, buttons=buttons)
    
    @bot.on(events.CallbackQuery(data=b"toggle_mode"))
    async def toggle_mode_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        settings = await db.get_settings()
        new_mode = "private" if settings.get("bot_mode") == "public" else "public"
        await db.update_settings({"bot_mode": new_mode})
        
        text, settings = await get_settings_text()
        buttons = await get_settings_buttons(settings, True)
        await event.edit(text, buttons=buttons)
        await event.answer(f"✅ Mod: {'Özel' if new_mode == 'private' else 'Genel'}")
        await send_log(bot, "system", f"Mod değişti: {new_mode}")
    
    @bot.on(events.CallbackQuery(data=b"toggle_maintenance"))
    async def toggle_maintenance_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        settings = await db.get_settings()
        new_state = not settings.get("maintenance", False)
        await db.update_settings({"maintenance": new_state})
        
        text, settings = await get_settings_text()
        buttons = await get_settings_buttons(settings, True)
        await event.edit(text, buttons=buttons)
        await event.answer(f"✅ Bakım: {'Açık' if new_state else 'Kapalı'}")
        await send_log(bot, "system", f"Bakım: {'Açık' if new_state else 'Kapalı'}")
    
    # ==========================================
    # KULLANICI LİSTESİ - SAYFALAMA
    # ==========================================
    
    @bot.on(events.CallbackQuery(pattern=b"users_list_(\d+)"))
    async def users_list_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        page = int(event.data.decode().split("_")[-1])
        users = await db.get_all_users()
        
        if not users:
            await event.edit("📭 Henüz kullanıcı yok.", buttons=[back_button("settings_menu")])
            return
        
        total_pages = (len(users) + USERS_PER_PAGE - 1) // USERS_PER_PAGE
        start_idx = page * USERS_PER_PAGE
        end_idx = start_idx + USERS_PER_PAGE
        page_users = users[start_idx:end_idx]
        
        text = f"👥 **Kullanıcı Listesi** (Sayfa {page + 1}/{total_pages})\n\n"
        
        for user in page_users:
            user_id = user.get("user_id")
            username = user.get("username")
            first_name = user.get("first_name", "")
            is_logged_in = user.get("is_logged_in", False)
            is_banned = user.get("is_banned", False)
            
            # Durum emoji
            if is_banned:
                status = "🚫"
            elif is_logged_in:
                status = "🟢"
            else:
                status = "⚪"
            
            # Kullanıcı linki
            if username:
                user_link = f"[@{username}](tg://user?id={user_id})"
            else:
                user_link = f"[{first_name or user_id}](tg://user?id={user_id})"
            
            text += f"{status} `{user_id}` - {user_link}\n"
        
        text += f"\n🟢 Aktif | ⚪ Pasif | 🚫 Banlı"
        text += f"\n\n📊 Toplam: **{len(users)}** kullanıcı"
        text += f"\n\n💡 Detay için: `/info <user_id>`"
        
        # Sayfalama butonları
        nav_buttons = []
        if page > 0:
            nav_buttons.append(Button.inline("⬅️ Önceki", f"users_list_{page - 1}".encode()))
        if page < total_pages - 1:
            nav_buttons.append(Button.inline("Sonraki ➡️", f"users_list_{page + 1}".encode()))
        
        buttons = []
        if nav_buttons:
            buttons.append(nav_buttons)
        buttons.append([Button.inline("🔄 Yenile", f"users_list_{page}".encode())])
        buttons.append(back_button("settings_menu"))
        
        await event.edit(text, buttons=buttons, link_preview=False)
    
    # ==========================================
    # KULLANICI BİLGİSİ - /info KOMUTU
    # ==========================================
    
    @bot.on(events.NewMessage(pattern=r'^/info\s+(\d+)$'))
    async def info_command(event):
        """Kullanıcı detaylı bilgisi"""
        
        # 1. ADIM: Sudo kullanıcılarının da komutu kullanabilmesi için izni güncelledik.
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        user_id = int(event.pattern_match.group(1))
        user_data = await db.get_user(user_id)
        
        if not user_data:
            await event.respond(f"❌ `{user_id}` ID'li kullanıcı bulunamadı.")
            return
        
        # Telegram'dan kullanıcı bilgisi al
        try:
            tg_user = await bot.get_entity(user_id)
            tg_username = tg_user.username
            tg_first_name = tg_user.first_name or ""
            tg_last_name = tg_user.last_name or ""
            tg_phone = getattr(tg_user, 'phone', None)
        except:
            tg_username = user_data.get("username")
            tg_first_name = user_data.get("first_name", "")
            tg_last_name = ""
            tg_phone = None
        
        # Durum
        is_logged_in = user_data.get("is_logged_in", False)
        is_banned = user_data.get("is_banned", False)
        is_sudo = user_data.get("is_sudo", False)
        
        if is_banned:
            status = "🚫 Banlı"
        elif is_logged_in:
            status = "🟢 Aktif"
        else:
            status = "⚪ Pasif"
        
        text = "👤 **Kullanıcı Bilgileri**\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        text += f"🆔 **ID:** `{user_id}`\n"
        text += f"👤 **İsim:** {tg_first_name} {tg_last_name}\n"
        
        if tg_username:
            text += f"📧 **Username:** @{tg_username}\n"
        
        text += f"🔗 **Profil:** [Tıkla](tg://user?id={user_id})\n"
        text += f"📊 **Durum:** {status}\n"
        
        if is_sudo:
            text += f"👑 **Yetki:** Sudo\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        
        # Userbot bilgileri
        if is_logged_in or user_data.get("userbot_id"):
            text += "\n🤖 **Userbot Bilgileri:**\n"
            text += f"  • ID: `{user_data.get('userbot_id', 'Yok')}`\n"
            text += f"  • Username: @{user_data.get('userbot_username', 'Yok')}\n"
            
            # Session bilgileri
            session_type = user_data.get("session_type", "Bilinmiyor")
            text += f"  • Session: `{session_type}`\n"
            
            phone = user_data.get("phone_number")
            if phone:
                # 2. ADIM: Telefon numarası gösterim mantığı
                if event.sender_id == config.OWNER_ID:
                    # Eğer komutu yazan SAHİP ise numarayı olduğu gibi göster
                    phone_display = phone
                else:
                    # Eğer komutu yazan SUDO ise numarayı sansürle
                    phone_display = phone[:4] + "****" + phone[-2:] if len(phone) > 6 else phone
                
                text += f"  • Telefon: `{phone_display}`\n"
            
            remember = user_data.get("remember_session", False)
            text += f"  • Oturum Kayıtlı: {'✅ Evet' if remember else '❌ Hayır'}\n"
        
        # Aktif pluginler
        active_plugins = user_data.get("active_plugins", [])
        if active_plugins:
            text += f"\n🔌 **Aktif Plugin'ler ({len(active_plugins)}):**\n"
            text += f"  {', '.join([f'`{p}`' for p in active_plugins[:5]])}"
            if len(active_plugins) > 5:
                text += f" +{len(active_plugins) - 5} daha"
            text += "\n"
        
        # Tarihler
        text += "\n📅 **Tarihler:**\n"
        created = user_data.get("created_at", "")
        if created:
            try:
                created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                text += f"  • Kayıt: `{created_dt.strftime('%d.%m.%Y %H:%M')}`\n"
            except:
                text += f"  • Kayıt: `{str(created)[:16]}`\n"
        
        last_active = user_data.get("last_active", "")
        if last_active:
            try:
                active_dt = datetime.fromisoformat(last_active.replace('Z', '+00:00'))
                text += f"  • Son Aktif: `{active_dt.strftime('%d.%m.%Y %H:%M')}`\n"
            except:
                text += f"  • Son Aktif: `{str(last_active)[:16]}`\n"
        
        # Ban bilgisi
        if is_banned:
            text += f"\n🚫 **Ban Bilgisi:**\n"
            text += f"  • Sebep: {user_data.get('ban_reason', 'Belirtilmemiş')}\n"
        
        # Aksiyon butonları
        buttons = []
        
        if is_banned:
            buttons.append([Button.inline("✅ Banı Kaldır", f"unban_user_{user_id}".encode())])
        else:
            buttons.append([Button.inline("🚫 Banla", f"ban_user_{user_id}".encode())])
        
        if is_sudo:
            buttons.append([Button.inline("👑 Sudo Kaldır", f"del_sudo_{user_id}".encode())])
        else:
            buttons.append([Button.inline("👑 Sudo Yap", f"add_sudo_{user_id}".encode())])
        
        if is_logged_in:
            buttons.append([Button.inline("🚪 Zorla Çıkış Yap", f"force_logout_{user_id}".encode())])
        
        await event.respond(text, buttons=buttons, link_preview=False)
    
    # ==========================================
    # INFO BUTON AKSIYONLARI
    # ==========================================
    
    @bot.on(events.CallbackQuery(pattern=b"ban_user_(\d+)"))
    async def ban_user_button(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        user_id = int(event.data.decode().split("_")[-1])
        
        if user_id == config.OWNER_ID:
            await event.answer("❌ Kendinizi banlayamazsınız!", alert=True)
            return
        
        await db.ban_user(user_id, "Admin tarafından banlandı", event.sender_id)
        await userbot_manager.logout(user_id)
        plugin_manager.clear_user_plugins(user_id)
        
        await event.answer(f"✅ {user_id} banlandı!")
        await send_log(bot, "ban", f"Ban: {user_id}", event.sender_id)
        
        # Mesajı güncelle
        try:
            await event.edit(f"✅ `{user_id}` banlandı.", buttons=[[Button.inline("🔙 Kullanıcılar", b"users_list_0")]])
        except:
            pass
    
    @bot.on(events.CallbackQuery(pattern=b"unban_user_(\d+)"))
    async def unban_user_button(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        user_id = int(event.data.decode().split("_")[-1])
        await db.unban_user(user_id)
        
        await event.answer(f"✅ {user_id} banı kaldırıldı!")
        await send_log(bot, "ban", f"Unban: {user_id}", event.sender_id)
        
        try:
            await event.edit(f"✅ `{user_id}` banı kaldırıldı.", buttons=[[Button.inline("🔙 Kullanıcılar", b"users_list_0")]])
        except:
            pass
    
    @bot.on(events.CallbackQuery(pattern=b"add_sudo_(\d+)"))
    async def add_sudo_button(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        user_id = int(event.data.decode().split("_")[-1])
        await db.add_sudo(user_id)
        
        await event.answer(f"✅ {user_id} sudo yapıldı!")
        await send_log(bot, "sudo", f"Sudo eklendi: {user_id}", event.sender_id)
        
        try:
            await event.edit(f"✅ `{user_id}` sudo yapıldı.", buttons=[[Button.inline("🔙 Kullanıcılar", b"users_list_0")]])
        except:
            pass
    
    @bot.on(events.CallbackQuery(pattern=b"del_sudo_(\d+)"))
    async def del_sudo_button(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        user_id = int(event.data.decode().split("_")[-1])
        await db.remove_sudo(user_id)
        
        await event.answer(f"✅ {user_id} sudo kaldırıldı!")
        await send_log(bot, "sudo", f"Sudo kaldırıldı: {user_id}", event.sender_id)
        
        try:
            await event.edit(f"✅ `{user_id}` sudo kaldırıldı.", buttons=[[Button.inline("🔙 Kullanıcılar", b"users_list_0")]])
        except:
            pass
    
    @bot.on(events.CallbackQuery(pattern=b"force_logout_(\d+)"))
    async def force_logout_button(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        user_id = int(event.data.decode().split("_")[-1])
        
        await userbot_manager.logout(user_id)
        plugin_manager.clear_user_plugins(user_id)
        await db.update_user(user_id, {"is_logged_in": False})
        
        await event.answer(f"✅ {user_id} çıkış yaptırıldı!")
        await send_log(bot, "system", f"Zorla çıkış: {user_id}", event.sender_id)
        
        # Kullanıcıya bildir
        try:
            await bot.send_message(user_id, "⚠️ **Oturumunuz admin tarafından sonlandırıldı.**")
        except:
            pass
        
        try:
            await event.edit(f"✅ `{user_id}` çıkış yaptırıldı.", buttons=[[Button.inline("🔙 Kullanıcılar", b"users_list_0")]])
        except:
            pass
    
    # ==========================================
    # /users KOMUTU
    # ==========================================
    
    @bot.on(events.NewMessage(pattern=r'^/users$'))
    async def users_command(event):
        """Kullanıcı listesi komutu"""
        if event.sender_id != config.OWNER_ID:
            return
        
        users = await db.get_all_users()
        
        if not users:
            await event.respond("📭 Henüz kullanıcı yok.")
            return
        
        total_pages = (len(users) + USERS_PER_PAGE - 1) // USERS_PER_PAGE
        page_users = users[:USERS_PER_PAGE]
        
        text = f"👥 **Kullanıcı Listesi** (Sayfa 1/{total_pages})\n\n"
        
        for user in page_users:
            user_id = user.get("user_id")
            username = user.get("username")
            first_name = user.get("first_name", "")
            is_logged_in = user.get("is_logged_in", False)
            is_banned = user.get("is_banned", False)
            
            if is_banned:
                status = "🚫"
            elif is_logged_in:
                status = "🟢"
            else:
                status = "⚪"
            
            if username:
                user_link = f"[@{username}](tg://user?id={user_id})"
            else:
                user_link = f"[{first_name or user_id}](tg://user?id={user_id})"
            
            text += f"{status} `{user_id}` - {user_link}\n"
        
        text += f"\n🟢 Aktif | ⚪ Pasif | 🚫 Banlı"
        text += f"\n\n📊 Toplam: **{len(users)}** kullanıcı"
        text += f"\n\n💡 Detay için: `/info <user_id>`"
        
        nav_buttons = []
        if total_pages > 1:
            nav_buttons.append(Button.inline("Sonraki ➡️", b"users_list_1"))
        
        buttons = []
        if nav_buttons:
            buttons.append(nav_buttons)
        buttons.append([Button.inline("🔄 Yenile", b"users_list_0")])
        
        await event.respond(text, buttons=buttons, link_preview=False)
    
    # ==========================================
    # ADMİN PLUGİN YÖNETİMİ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"admin_plugins"))
    async def admin_plugins_handler(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        
        all_plugins = await db.get_all_plugins()
        
        if not all_plugins:
            text = "📭 **Henüz plugin eklenmemiş.**"
        else:
            text = "🔌 **Yüklü Plugin'ler:**\n\n"
            
            for p in all_plugins:
                status = "✅" if p.get("is_active", True) else "❌"
                access = "🌐" if p.get("is_public", True) else "🔒"
                cmds = len(p.get("commands", []))
                text += f"{status} {access} `{p['name']}` ({cmds} komut)\n"
            
            text += f"\n**Toplam:** {len(all_plugins)} plugin"
        
        text += "\n\n**Komutlar:**\n"
        text += "• `/addplugin` - Ekle\n"
        text += "• `/delplugin <isim>` - Sil\n"
        text += "• `/pinfo <isim>` - Detay"
        
        buttons = [
            [Button.inline("🔄 Yenile", b"admin_plugins")],
            back_button("settings_menu")
        ]
        await event.edit(text, buttons=buttons)
    
    # ==========================================
    # BAN YÖNETİMİ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"ban_management"))
    async def ban_management_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        banned = await db.get_banned_users()
        
        text = "🚫 **Ban Yönetimi**\n\n"
        
        if banned:
            for user in banned[:10]:
                user_id = user.get('user_id')
                text += f"• `{user_id}` - {user.get('ban_reason', 'Sebep yok')}\n"
            if len(banned) > 10:
                text += f"\n... ve {len(banned) - 10} kişi daha"
        else:
            text += "✅ Banlı kullanıcı yok."
        
        text += "\n\n**Komutlar:**\n"
        text += "• `/ban <user_id> [sebep]`\n"
        text += "• `/unban <user_id>`"
        
        await event.edit(text, buttons=[back_button("settings_menu")])
    
    @bot.on(events.NewMessage(pattern=r'^/ban\s+(\d+)(?:\s+(.+))?$'))
    async def ban_command(event):
        if event.sender_id != config.OWNER_ID:
            return
        
        user_id = int(event.pattern_match.group(1))
        reason = event.pattern_match.group(2) or "Sebep belirtilmedi"
        
        if user_id == config.OWNER_ID:
            await event.respond("❌ Kendinizi banlayamazsınız!")
            return
        
        await db.add_user(user_id)
        await db.ban_user(user_id, reason, event.sender_id)
        await userbot_manager.logout(user_id)
        plugin_manager.clear_user_plugins(user_id)
        
        await event.respond(f"✅ `{user_id}` banlandı.\n📝 Sebep: {reason}")
        await send_log(bot, "ban", f"Ban: {user_id} - {reason}", event.sender_id)
    
    @bot.on(events.NewMessage(pattern=r'^/unban\s+(\d+)$'))
    async def unban_command(event):
        if event.sender_id != config.OWNER_ID:
            return
        
        user_id = int(event.pattern_match.group(1))
        await db.unban_user(user_id)
        await event.respond(f"✅ `{user_id}` banı kaldırıldı.")
        await send_log(bot, "ban", f"Unban: {user_id}", event.sender_id)
    
    # ==========================================
    # SUDO YÖNETİMİ
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"sudo_management"))
    async def sudo_management_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        sudos = await db.get_sudos()
        
        text = "👑 **Sudo Yönetimi**\n\n"
        
        if sudos:
            for user in sudos:
                user_id = user.get('user_id')
                username = user.get('username', 'Yok')
                text += f"• `{user_id}` - @{username}\n"
        else:
            text += "Henüz sudo yok."
        
        text += "\n\n**Komutlar:**\n"
        text += "• `/addsudo <user_id>`\n"
        text += "• `/delsudo <user_id>`"
        
        await event.edit(text, buttons=[back_button("settings_menu")])
    
    @bot.on(events.NewMessage(pattern=r'^/addsudo\s+(\d+)$'))
    async def addsudo_command(event):
        if event.sender_id != config.OWNER_ID:
            return
        
        user_id = int(event.pattern_match.group(1))
        await db.add_user(user_id)
        await db.add_sudo(user_id)
        await event.respond(f"✅ `{user_id}` sudo eklendi.")
        await send_log(bot, "sudo", f"Sudo eklendi: {user_id}", event.sender_id)
    
    @bot.on(events.NewMessage(pattern=r'^/delsudo\s+(\d+)$'))
    async def delsudo_command(event):
        if event.sender_id != config.OWNER_ID:
            return
        
        user_id = int(event.pattern_match.group(1))
        await db.remove_sudo(user_id)
        await event.respond(f"✅ `{user_id}` sudo kaldırıldı.")
        await send_log(bot, "sudo", f"Sudo kaldırıldı: {user_id}", event.sender_id)
    
    # ==========================================
    # PLUGİN EKLEME/SİLME
    # ==========================================
    
    @bot.on(events.NewMessage(pattern=r'^/addplugin$'))
    async def addplugin_command(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        reply = await event.get_reply_message()
        
        if not reply or not reply.file or not reply.file.name.endswith('.py'):
            await event.respond("⚠️ Bir `.py` dosyasına yanıt verin.")
            return
        
        path = await reply.download_media(file=config.PLUGINS_DIR + "/")
        info = plugin_manager.extract_plugin_info(path)
        
        for cmd in info["commands"]:
            existing = await db.check_command_exists(cmd)
            if existing:
                os.remove(path)
                await event.respond(f"❌ `.{cmd}` komutu `{existing}` plugininde mevcut!")
                return
        
        if not hasattr(bot, 'pending_plugins'):
            bot.pending_plugins = {}
        bot.pending_plugins[info['name']] = path
        
        await event.respond(
            f"🔌 **Plugin: `{info['name']}`**\n\n"
            f"📝 {info['description'] or 'Açıklama yok'}\n"
            f"🔧 Komutlar: {', '.join([f'`.{c}`' for c in info['commands']])}\n\n"
            f"Nasıl eklensin?",
            buttons=[
                [Button.inline("🌐 Genel", f"confirm_plugin_public_{info['name']}".encode()),
                 Button.inline("🔒 Özel", f"confirm_plugin_private_{info['name']}".encode())],
                [Button.inline("❌ İptal", b"cancel_plugin")]
            ]
        )
    
    @bot.on(events.CallbackQuery(pattern=b"confirm_plugin_(public|private)_(.+)"))
    async def confirm_plugin_handler(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        data = event.data.decode()
        is_public = "public" in data
        plugin_name = data.split("_", 3)[-1]
        
        if not hasattr(bot, 'pending_plugins') or plugin_name not in bot.pending_plugins:
            await event.answer("Plugin bulunamadı", alert=True)
            return
        
        path = bot.pending_plugins[plugin_name]
        success, message = await plugin_manager.register_plugin(path, is_public=is_public)
        del bot.pending_plugins[plugin_name]
        
        await event.edit(message)
        if success:
            await send_log(bot, "plugin", f"Eklendi: {plugin_name}", event.sender_id)
    
    @bot.on(events.CallbackQuery(data=b"cancel_plugin"))
    async def cancel_plugin_handler(event):
        if hasattr(bot, 'pending_plugins'):
            for path in bot.pending_plugins.values():
                if os.path.exists(path):
                    os.remove(path)
            bot.pending_plugins.clear()
        await event.edit("❌ İptal edildi.")
    
    @bot.on(events.NewMessage(pattern=r'^/delplugin\s+(\S+)$'))
    async def delplugin_command(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        plugin_name = event.pattern_match.group(1)
        success, message = await plugin_manager.unregister_plugin(plugin_name)
        await event.respond(message)
        
        if success:
            await send_log(bot, "plugin", f"Silindi: {plugin_name}", event.sender_id)
    
    @bot.on(events.NewMessage(pattern=r'^/setpublic\s+(\S+)$'))
    async def setpublic_command(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        plugin_name = event.pattern_match.group(1)
        await db.update_plugin(plugin_name, {"is_public": True})
        await event.respond(f"✅ `{plugin_name}` genel yapıldı.")
    
    @bot.on(events.NewMessage(pattern=r'^/setprivate\s+(\S+)$'))
    async def setprivate_command(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        plugin_name = event.pattern_match.group(1)
        await db.update_plugin(plugin_name, {"is_public": False})
        await event.respond(f"✅ `{plugin_name}` özel yapıldı.")
    
    # ==========================================
    # İSTATİSTİK
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"stats"))
    async def stats_handler(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        
        stats = await db.get_stats()
        uptime = get_readable_time(time.time() - start_time)
        
        text = "📊 **İstatistikler**\n\n"
        text += f"👥 Kullanıcı: `{stats.get('total_users', 0)}`\n"
        text += f"✅ Aktif Userbot: `{stats.get('logged_in_users', 0)}`\n"
        text += f"🚫 Banlı: `{stats.get('banned_users', 0)}`\n"
        text += f"👑 Sudo: `{stats.get('sudo_users', 0)}`\n\n"
        text += f"🔌 Plugin: `{stats.get('total_plugins', 0)}`\n"
        text += f"  └ Genel: `{stats.get('public_plugins', 0)}`\n"
        text += f"  └ Özel: `{stats.get('private_plugins', 0)}`\n\n"
        text += f"⏱️ Uptime: `{uptime}`\n"
        text += f"🔢 Sürüm: `v{config.__version__}`"
        
        await event.edit(text, buttons=[back_button("settings_menu")])
    
    @bot.on(events.NewMessage(pattern=r'^/stats$'))
    async def stats_command(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        stats = await db.get_stats()
        uptime = get_readable_time(time.time() - start_time)
        
        text = "📊 **İstatistikler**\n\n"
        text += f"👥 Kullanıcı: `{stats.get('total_users', 0)}`\n"
        text += f"✅ Aktif: `{stats.get('logged_in_users', 0)}`\n"
        text += f"🔌 Plugin: `{stats.get('total_plugins', 0)}`\n"
        text += f"⏱️ Uptime: `{uptime}`"
        
        await event.respond(text)
    
    # ==========================================
    # GÜNCELLEME & RESTART
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"update_bot"))
    async def update_bot_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        await event.edit("🔄 **Güncelleme kontrol ediliyor...**")
        
        try:
            import git
            
            if not os.path.exists(".git"):
                await event.edit("❌ Git repository değil!", buttons=[back_button("settings_menu")])
                return
            
            repo = git.Repo(".")
            origin = repo.remotes.origin
            origin.fetch()
            
            current_branch = repo.active_branch.name
            commits = list(repo.iter_commits(f'{current_branch}..origin/{current_branch}'))
            
            if not commits:
                await event.edit(f"✅ **Bot güncel!**\n\nSürüm: `v{config.__version__}`", buttons=[back_button("settings_menu")])
                return
            
            await event.edit(f"⬇️ **{len(commits)} güncelleme indiriliyor...**")
            origin.pull(current_branch)
            
            if os.path.exists("requirements.txt"):
                await event.edit("📦 **Bağımlılıklar kuruluyor...**")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"])
            
            await event.edit("✅ **Güncelleme tamamlandı!**\n\n🔃 Yeniden başlatılıyor...")
            
            with open(".restart_info", "w") as f:
                f.write(f"{event.chat_id}|{event.message_id}")
            
            await send_log(bot, "update", "Bot güncellendi")
            await asyncio.sleep(1)
            os.execv(sys.executable, [sys.executable] + sys.argv)
            
        except Exception as e:
            await event.edit(f"❌ **Hata:** `{e}`", buttons=[back_button("settings_menu")])
    
    @bot.on(events.CallbackQuery(data=b"restart_bot"))
    async def restart_bot_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        await event.edit("🔃 **Yeniden başlatılıyor...**")
        
        with open(".restart_info", "w") as f:
            f.write(f"{event.chat_id}|{event.message_id}")
        
        await send_log(bot, "system", "Bot yeniden başlatılıyor")
        await asyncio.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    
    # ==========================================
    # LOGLAR & KOMUTLAR
    # ==========================================
    
    @bot.on(events.CallbackQuery(data=b"view_logs"))
    async def view_logs_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        
        logs = await db.get_logs(limit=15)
        
        text = "📋 **Son Loglar:**\n\n"
        
        if logs:
            for log in logs:
                text += f"• [{log.get('type', '?')}] {log.get('message', '')[:30]}\n"
        else:
            text += "Henüz log yok."
        
        await event.edit(text, buttons=[back_button("settings_menu")])
    
    @bot.on(events.CallbackQuery(data=b"admin_commands"))
    async def admin_commands_handler(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        
        text = "📝 **Admin Komutları**\n\n"
        
        text += "**👥 Kullanıcı:**\n"
        text += "• `/users` - Kullanıcı listesi\n"
        text += "• `/info <id>` - Kullanıcı detayı\n\n"
        
        text += "**🔌 Plugin:**\n"
        text += "• `/addplugin` - Plugin ekle\n"
        text += "• `/delplugin <isim>` - Plugin sil\n"
        text += "• `/setpublic <isim>` - Genel yap\n"
        text += "• `/setprivate <isim>` - Özel yap\n\n"
        
        text += "**🚫 Ban:**\n"
        text += "• `/ban <id> [sebep]` - Banla\n"
        text += "• `/unban <id>` - Ban kaldır\n\n"
        
        text += "**👑 Sudo:**\n"
        text += "• `/addsudo <id>` - Sudo ekle\n"
        text += "• `/delsudo <id>` - Sudo kaldır\n\n"
        
        text += "**📢 Diğer:**\n"
        text += "• `/broadcast` - Duyuru gönder\n"
        text += "• `/stats` - İstatistik"
        
        await event.edit(text, buttons=[back_button("settings_menu")])
    
    # ==========================================
    # BROADCAST
    # ==========================================
    
    @bot.on(events.NewMessage(pattern=r'^/broadcast$'))
    async def broadcast_command(event):
        if event.sender_id != config.OWNER_ID:
            return
        
        reply = await event.get_reply_message()
        if not reply:
            await event.respond("⚠️ Mesaja yanıt verin.")
            return
        
        users = await db.get_all_users()
        msg = await event.respond(f"📢 Gönderiliyor... (0/{len(users)})")
        
        sent, failed = 0, 0
        for user in users:
            try:
                await bot.send_message(user["user_id"], reply.text)
                sent += 1
            except:
                failed += 1
        
        await msg.edit(f"✅ **Tamamlandı!**\n\n📤 Gönderildi: `{sent}`\n❌ Başarısız: `{failed}`")
