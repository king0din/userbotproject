# ============================================
# KingTG UserBot Service - Admin / settings
# Ayarlar menüsü, mod/bakım toggle, admin panel girişi
# (admin.py'dan otomatik bölündü - davranış birebir korundu)
# ============================================

# ============================================
# KingTG UserBot Service - Admin Handlers
# ============================================

import os
import sys
import asyncio
import subprocess
import time
import psutil
from datetime import datetime
from telethon import events, Button
import config
from database import database as db
from userbot.smart_manager import smart_session_manager
from userbot.plugins import plugin_manager

# Eski uyumluluk için alias
userbot_manager = smart_session_manager
from utils import send_log, get_readable_time, back_button
from utils.bot_api import bot_api, btn, ButtonBuilder


def register(bot):

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
    

    def get_settings_buttons_api(settings, is_owner):
        """Bot API için renkli butonlar"""
        mode = settings.get("bot_mode", "public")
        maint = settings.get("maintenance", False)
        
        if is_owner:
            rows = [
                # Mod ve Bakım toggle butonları
                [
                    btn.callback(" Özel Yap" if mode == "public" else " Genel Yap", "toggle_mode",
                                style=ButtonBuilder.STYLE_PRIMARY if mode == "public" else ButtonBuilder.STYLE_SUCCESS,
                                icon_custom_emoji_id=5832551281431946000 if mode == "public" else 5832490468990000458),
                    btn.callback(" Bakım Kapat" if maint else " Bakım Aç", "toggle_maintenance",
                                style=ButtonBuilder.STYLE_SUCCESS if maint else ButtonBuilder.STYLE_DANGER,
                                icon_custom_emoji_id=5832308667319328140 if maint else 5832499024564854704)
                ],
                # Kullanıcılar ve Pluginler
                [
                    btn.callback(" Kullanıcılar", "users_list_0", 
                                style=ButtonBuilder.STYLE_PRIMARY,
                                icon_custom_emoji_id=5832570548655234693),
                    btn.callback(" Plugin'ler", "admin_plugins", 
                                style=ButtonBuilder.STYLE_PRIMARY,
                                icon_custom_emoji_id=5830184853236097449)
                ],
                # Sudo ve Ban
                [
                    btn.callback(" Sudo", "sudo_management", 
                                style=ButtonBuilder.STYLE_SUCCESS,
                                icon_custom_emoji_id=5832280088606939924),
                    btn.callback(" Ban", "ban_management", 
                                style=ButtonBuilder.STYLE_DANGER,
                                icon_custom_emoji_id=5832507597319577197)
                ],
                # İstatistik ve Loglar
                [
                    btn.callback(" İstatistik", "stats", 
                                style=ButtonBuilder.STYLE_PRIMARY,
                                icon_custom_emoji_id=5832499024564854704),
                    btn.callback(" Loglar", "view_logs", 
                                style=ButtonBuilder.STYLE_PRIMARY,
                                icon_custom_emoji_id=5832261714736848714)
                ],
                # Güncelle ve Restart
                [
                    btn.callback(" Güncelle", "update_bot", 
                                style=ButtonBuilder.STYLE_SUCCESS,
                                icon_custom_emoji_id=5832202083410911000),
                    btn.callback(" Restart", "restart_bot", 
                                style=ButtonBuilder.STYLE_DANGER,
                                icon_custom_emoji_id=5832381458425062093)
                ],
                # Komutlar
                [btn.callback(" Komutlar", "admin_commands", 
                             style=ButtonBuilder.STYLE_PRIMARY,
                             icon_custom_emoji_id=5832365506916523096)],
                # Geri
                [btn.callback(" Ana Menü", "main_menu", 
                             style=ButtonBuilder.STYLE_DANGER,
                             icon_custom_emoji_id=5832654562510511307)]
            ]
        else:
            rows = [
                [btn.callback(" Plugin'ler", "admin_plugins", 
                             style=ButtonBuilder.STYLE_PRIMARY,
                             icon_custom_emoji_id=5830184853236097449)],
                [btn.callback(" İstatistik", "stats", 
                             style=ButtonBuilder.STYLE_PRIMARY,
                             icon_custom_emoji_id=5832499024564854704)],
                [btn.callback(" Ana Menü", "main_menu", 
                             style=ButtonBuilder.STYLE_DANGER,
                             icon_custom_emoji_id=5832654562510511307)]
            ]
        return rows
    

    async def get_settings_buttons(settings, is_owner):
        """Telethon için eski butonlar (fallback)"""
        mode = settings.get("bot_mode", "public")
        maint = settings.get("maintenance", False)
        if is_owner:
            buttons = [
                [Button.inline("🔒 Özel Yap" if mode == "public" else "🌐 Genel Yap", b"toggle_mode"),
                 Button.inline("✅ Bakım Kapat" if maint else "🔧 Bakım Aç", b"toggle_maintenance")],
                [Button.inline("👥 Kullanıcılar", b"users_list_0"), Button.inline("🔌 Plugin'ler", b"admin_plugins")],
                [Button.inline("👑 Sudo", b"sudo_management"), Button.inline("🚫 Ban", b"ban_management")],
                [Button.inline("📊 İstatistik", b"stats"), Button.inline("📋 Loglar", b"view_logs")],
                [Button.inline("🔄 Güncelle", b"update_bot"), Button.inline("🔃 Restart", b"restart_bot")],
                [Button.inline("📝 Komutlar", b"admin_commands")],
                back_button("main_menu")
            ]
        else:
            buttons = [[Button.inline("🔌 Plugin'ler", b"admin_plugins")], [Button.inline("📊 İstatistik", b"stats")], back_button("main_menu")]
        return buttons
    

    @bot.on(events.CallbackQuery(data=b"settings_menu"))
    async def settings_menu_handler(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        text, settings = await get_settings_text()
        rows = get_settings_buttons_api(settings, event.sender_id == config.OWNER_ID)
        
        await bot_api.edit_message_text(
            chat_id=event.sender_id,
            message_id=event.message_id,
            text=text,
            reply_markup=btn.inline_keyboard(rows)
        )
        await event.answer()
    

    @bot.on(events.CallbackQuery(data=b"toggle_mode"))
    async def toggle_mode_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        settings = await db.get_settings()
        new_mode = "private" if settings.get("bot_mode") == "public" else "public"
        await db.update_settings({"bot_mode": new_mode})
        text, settings = await get_settings_text()
        rows = get_settings_buttons_api(settings, True)
        
        await bot_api.edit_message_text(
            chat_id=event.sender_id,
            message_id=event.message_id,
            text=text,
            reply_markup=btn.inline_keyboard(rows)
        )
        await event.answer(f"✅ Mod: {'Özel' if new_mode == 'private' else 'Genel'}")
    

    @bot.on(events.CallbackQuery(data=b"toggle_maintenance"))
    async def toggle_maintenance_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        settings = await db.get_settings()
        new_state = not settings.get("maintenance", False)
        await db.update_settings({"maintenance": new_state})
        text, settings = await get_settings_text()
        rows = get_settings_buttons_api(settings, True)
        
        await bot_api.edit_message_text(
            chat_id=event.sender_id,
            message_id=event.message_id,
            text=text,
            reply_markup=btn.inline_keyboard(rows)
        )
        await event.answer(f"✅ Bakım: {'Açık' if new_state else 'Kapalı'}")
    

    @bot.on(events.CallbackQuery(data=b"admin_panel"))
    async def admin_panel_callback(event):
        """Admin paneline geri dön - settings_menu'ya yönlendir"""
        # settings_menu_handler ile aynı işlevi yapar
        await settings_menu_handler(event)
