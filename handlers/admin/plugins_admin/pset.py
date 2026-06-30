# KingTG - Admin / plugins_admin / pset
# Plugin başına ayarlar (erişim/izin/kısıt)
# (plugins_admin.py'dan bölündü - davranış birebir)
# ============================================
# KingTG UserBot Service - Admin / plugins_admin
# Plugin ekleme/silme/yetki + plugin başına ayarlar
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


async def _safe_edit(event, text, rows):
    """Önce bot_api (stilli/emoji butonlar) ile düzenle; api.telegram.org takılırsa
    Telethon'a düş ki panel HER ZAMAN açılsın (stil olmadan ama çalışır)."""
    try:
        res = await bot_api.edit_message_text(
            chat_id=event.sender_id,
            message_id=event.message_id,
            text=text,
            reply_markup=btn.inline_keyboard(rows),
        )
        if res is not None:
            return True
    except Exception:
        pass
    try:
        tbtns = []
        for row in (rows or []):
            trow = [Button.inline(b.get("text", " "), (b.get("callback_data") or " ").encode())
                    for b in row]
            if trow:
                tbtns.append(trow)
        await event.edit(text, buttons=tbtns)
        return True
    except Exception:
        return False


async def _ans(event, text=None, alert=False):
    """Callback'i güvenle yanıtla (QueryIdInvalid / süre dolması paneli çökertmesin)."""
    try:
        await event.answer(text, alert=alert)
    except Exception:
        pass


def register(bot):
    @bot.on(events.NewMessage(pattern=r'^/psettings$'))
    async def psettings_command(event):
        """Plugin ayarları ana menüsü"""
        try:
            # Yetki kontrolü
            if event.sender_id != config.OWNER_ID:
                is_sudo = await db.is_sudo(event.sender_id)
                if not is_sudo:
                    return
            
            await show_psettings_menu(event, edit=False)
        except Exception as e:
            await event.respond(f"❌ Hata: {e}")
            import traceback
            traceback.print_exc()
    

    async def show_psettings_menu(event, edit=True, page=0):
        """Plugin ayarları menüsünü göster"""
        try:
            PER_PAGE = 6
            plugins = await db.get_all_plugins()
            
            if not plugins:
                text = "📭 Henüz plugin eklenmemiş."
                if edit:
                    await event.edit(text)
                else:
                    await event.respond(text)
                return
            
            total = len(plugins)
            total_pages = (total + PER_PAGE - 1) // PER_PAGE
            page = max(0, min(page, total_pages - 1))
            
            start = page * PER_PAGE
            end = start + PER_PAGE
            page_plugins = plugins[start:end]
            
            text = "⚙️ **Plugin Ayarları**\n\n"
            text += "Ayarlamak istediğiniz plugin'i seçin:\n\n"
            
            # İstatistikler
            public_count = sum(1 for p in plugins if p.get("is_public", True))
            private_count = total - public_count
            disabled_count = sum(1 for p in plugins if p.get("is_disabled", False))
            default_count = sum(1 for p in plugins if p.get("default_active", False))
            
            text += f"📊 **İstatistikler:**\n"
            text += f"├ Toplam: `{total}` plugin\n"
            text += f"├ 🌐 Genel: `{public_count}`\n"
            text += f"├ 🔒 Özel: `{private_count}`\n"
            text += f"├ ⛔ Devre Dışı: `{disabled_count}`\n"
            text += f"└ ⭐ Varsayılan Aktif: `{default_count}`\n"
            
            rows = []
            
            # Plugin listesi
            for p in page_plugins:
                name = p.get("name", "?")
                status_icons = ""
                
                if p.get("is_disabled"):
                    status_icons += "⛔"
                elif p.get("is_public", True):
                    status_icons += "🌐"
                else:
                    status_icons += "🔒"
                
                if p.get("default_active"):
                    status_icons += "⭐"
                
                rows.append([
                    btn.callback(f"{status_icons} {name}", f"psetsel_{name}",
                                style=ButtonBuilder.STYLE_PRIMARY)
                ])
            
            # Sayfalama
            nav_row = []
            if page > 0:
                nav_row.append(btn.callback(" Önceki", f"psettings_page_{page-1}",
                                           icon_custom_emoji_id=5834632747137638263))
            nav_row.append(btn.callback(f"📄 {page+1}/{total_pages}", "noop"))
            if page < total_pages - 1:
                nav_row.append(btn.callback(" Sonraki", f"psettings_page_{page+1}",
                                           icon_custom_emoji_id=5834933416323193844))
            
            if nav_row:
                rows.append(nav_row)
            
            # Toplu işlemler
            rows.append([
                btn.callback(" Hepsini Genel", "pset_bulk_public",
                            style=ButtonBuilder.STYLE_SUCCESS,
                            icon_custom_emoji_id=5832490468990000458),
                btn.callback(" Hepsini Özel", "pset_bulk_private",
                            style=ButtonBuilder.STYLE_DANGER,
                            icon_custom_emoji_id=5832636278834733177)
            ])
            
            rows.append([
                btn.callback(" Plugin'ler", "admin_plugins",
                            style=ButtonBuilder.STYLE_PRIMARY,
                            icon_custom_emoji_id=5830184853236097449)
            ])
            
            if edit:
                await _safe_edit(event, text, rows)
                await _ans(event)
            else:
                sent = await bot_api.send_message(
                    chat_id=event.sender_id,
                    text=text,
                    reply_markup=btn.inline_keyboard(rows)
                )
                if sent is None:
                    try:
                        await event.respond(text)
                    except Exception:
                        pass
        
        except Exception as e:
            error_text = f"❌ Hata: {e}"
            import traceback
            traceback.print_exc()
            if edit:
                await event.edit(error_text)
            else:
                await event.respond(error_text)
    

    @bot.on(events.CallbackQuery(pattern=rb"psettings_page_(\d+)"))
    async def psettings_page_handler(event):
        """Plugin ayarları sayfalama"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        page = int(event.pattern_match.group(1).decode())
        await show_psettings_menu(event, edit=True, page=page)
    

    @bot.on(events.CallbackQuery(pattern=rb"pset_bulk_(public|private)"))
    async def pset_bulk_handler(event):
        """Toplu plugin ayarı"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        action = event.pattern_match.group(1).decode()
        is_public = action == "public"
        
        plugins = await db.get_all_plugins()
        for p in plugins:
            await db.update_plugin(p["name"], {"is_public": is_public})
        
        await event.answer(f"✅ Tüm plugin'ler {'genel' if is_public else 'özel'} yapıldı!", alert=True)
        await show_psettings_menu(event, edit=True)
    

    @bot.on(events.CallbackQuery(pattern=rb"psetsel_([a-zA-Z0-9_]+)$"))
    async def pset_plugin_handler(event):
        """Tek plugin ayar menüsü"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        plugin_name = event.pattern_match.group(1).decode()
        
        plugin = await db.get_plugin(plugin_name)
        
        if not plugin:
            await event.answer("❌ Plugin bulunamadı!", alert=True)
            return
        
        await show_plugin_settings(event, plugin_name)
    

    async def show_plugin_settings(event, plugin_name):
        """Tek plugin'in ayar menüsünü göster"""
        plugin = await db.get_plugin(plugin_name)
        
        if not plugin:
            await event.edit("❌ Plugin bulunamadı.")
            return
        
        # Durum bilgileri
        is_public = plugin.get("is_public", True)
        is_disabled = plugin.get("is_disabled", False)
        default_active = plugin.get("default_active", False)
        allowed_users = plugin.get("allowed_users", [])
        restricted_users = plugin.get("restricted_users", [])
        
        text = f"⚙️ **{plugin_name}** Ayarları\n\n"
        text += f"📝 {plugin.get('description', 'Açıklama yok')[:100]}\n\n"
        
        text += "**Mevcut Durum:**\n"
        text += f"├ Erişim: {'🌐 Genel' if is_public else '🔒 Özel'}\n"
        text += f"├ Durum: {'⛔ Devre Dışı' if is_disabled else '✅ Aktif'}\n"
        text += f"├ Varsayılan: {'⭐ Aktif' if default_active else '◽ Pasif'}\n"
        text += f"├ İzinli Kullanıcı: `{len(allowed_users)}`\n"
        text += f"└ Engelli Kullanıcı: `{len(restricted_users)}`\n"
        try:
            from utils import premium as _prem
            if _prem.is_configured(plugin_name) and _prem.plugin_type(plugin_name) == "premium":
                _pc = _prem.get_config(plugin_name) or {}
                text += f"\n💎 Premium: `{_pc.get('stars',100)}⭐ / {_pc.get('days',30)} gün`\n"
        except Exception:
            pass
        
        # Komutlar
        commands = plugin.get("commands", [])
        if commands:
            cmd_text = ", ".join([f"`.{c}`" for c in commands[:5]])
            if len(commands) > 5:
                cmd_text += f" +{len(commands)-5}"
            text += f"\n🔧 Komutlar: {cmd_text}\n"
        
        rows = []
        
        # Erişim ayarı
        if is_public:
            rows.append([
                btn.callback(" Özel Yap", f"pset_access_{plugin_name}_private",
                            style=ButtonBuilder.STYLE_DANGER,
                            icon_custom_emoji_id=5832636278834733177)
            ])
        else:
            rows.append([
                btn.callback(" Genel Yap", f"pset_access_{plugin_name}_public",
                            style=ButtonBuilder.STYLE_SUCCESS,
                            icon_custom_emoji_id=5832532705698388983)
            ])
        
        # Devre dışı/aktif
        if is_disabled:
            rows.append([
                btn.callback(" Aktif Et", f"pset_status_{plugin_name}_enable",
                            style=ButtonBuilder.STYLE_SUCCESS,
                            icon_custom_emoji_id=5832249761842864793)
            ])
        else:
            rows.append([
                btn.callback(" Devre Dışı Bırak", f"pset_status_{plugin_name}_disable",
                            style=ButtonBuilder.STYLE_DANGER,
                            icon_custom_emoji_id=5830001655701052988)
            ])
        
        # Varsayılan aktif
        if default_active:
            rows.append([
                btn.callback(" Varsayılan Pasif", f"pset_default_{plugin_name}_off",
                            style=ButtonBuilder.STYLE_DANGER,
                            icon_custom_emoji_id=5830287159357087904)
            ])
        else:
            rows.append([
                btn.callback(" Varsayılan Aktif", f"pset_default_{plugin_name}_on",
                            style=ButtonBuilder.STYLE_SUCCESS,
                            icon_custom_emoji_id=5832308667319328140)
            ])
        
        # Kullanıcı yönetimi
        rows.append([
            btn.callback(" İzin Ver", f"psetallow_{plugin_name}",
                        style=ButtonBuilder.STYLE_SUCCESS,
                        icon_custom_emoji_id=5832365979362925905),
            btn.callback(" Engelle", f"psetrestrict_{plugin_name}",
                        style=ButtonBuilder.STYLE_DANGER,
                        icon_custom_emoji_id=5832507597319577197)
        ])
        
        rows.append([
            btn.callback(" İzinli Liste", f"psetallowls_{plugin_name}",
                        style=ButtonBuilder.STYLE_PRIMARY,
                        icon_custom_emoji_id=5832687998830910706),
            btn.callback(" Engelli Liste", f"psetrestrictls_{plugin_name}",
                        style=ButtonBuilder.STYLE_PRIMARY,
                        icon_custom_emoji_id=5832685469095173542)
        ])
        
        # Aktif kullanıcıları göster
        rows.append([
            btn.callback(" Kullananlar", f"psetusers_{plugin_name}",
                        style=ButtonBuilder.STYLE_PRIMARY,
                        icon_custom_emoji_id=5832570548655234693)
        ])
        
        # Premium ayarları
        rows.append([
            btn.callback(" 💎 Premium Ayarları", f"psetprem_{plugin_name}",
                        style=ButtonBuilder.STYLE_PRIMARY)
        ])
        
        # Geri
        rows.append([
            btn.callback(" Geri", "psettings_page_0",
                        style=ButtonBuilder.STYLE_DANGER,
                        icon_custom_emoji_id=5832646161554480591)
        ])
        
        await _safe_edit(event, text, rows)
        await _ans(event)
    

    # ============ PREMIUM AYARLARI ============
    async def _is_admin(event):
        return event.sender_id == config.OWNER_ID or await db.is_sudo(event.sender_id)

    async def show_plugin_premium(event, plugin_name):
        from utils import premium as _prem
        plugin = await db.get_plugin(plugin_name)
        if not plugin:
            await event.answer("❌ Plugin bulunamadı.", alert=True)
            return
        cfg = _prem.get_config(plugin_name)
        configured = bool(cfg and cfg.get("type") in _prem.TYPES)
        ptype = (cfg or {}).get("type", "genel")
        stars = int((cfg or {}).get("stars", 100))
        days = int((cfg or {}).get("days", 30))

        text = f"💎 **{plugin_name} — Premium Ayarları**\n\n"
        if not configured:
            text += ("Bu plugin için tip seçilmedi.\n\n"
                     "🌐 **Genel** — herkes ücretsiz kullanır\n"
                     "🔒 **Özel** — sadece izin verdiğin kullanıcılar\n"
                     "💎 **Premium** — yıldız karşılığı süreli abonelik")
        else:
            text += f"Tip: {_prem.TYPE_LABELS.get(ptype, ptype)}\n"
            if ptype == "premium":
                text += f"⭐ Fiyat: `{stars}` yıldız\n📅 Süre: `{days}` gün\n"
                text += f"👥 Aktif abone: `{len(_prem.list_active_subs(plugin_name))}`"
            elif ptype == "ozel":
                text += f"👥 İzinli kullanıcı: `{len(_prem.ozel_users(plugin_name))}`"

        def _m(t):
            return ("✅ " if (configured and ptype == t) else "") + _prem.TYPE_LABELS.get(t, t)
        rows = [[
            btn.callback(" " + _m("genel"), f"psetptype_{plugin_name}_genel", style=ButtonBuilder.STYLE_SUCCESS),
            btn.callback(" " + _m("ozel"), f"psetptype_{plugin_name}_ozel", style=ButtonBuilder.STYLE_PRIMARY),
            btn.callback(" " + _m("premium"), f"psetptype_{plugin_name}_premium", style=ButtonBuilder.STYLE_PRIMARY),
        ]]
        if configured and ptype == "premium":
            sp = _prem.STAR_PRESETS
            rows.append([btn.callback(("✅" if s == stars else "") + f"{s}⭐", f"psetpstars_{plugin_name}_{s}", style=ButtonBuilder.STYLE_SECONDARY) for s in sp[:3]])
            rows.append([btn.callback(("✅" if s == stars else "") + f"{s}⭐", f"psetpstars_{plugin_name}_{s}", style=ButtonBuilder.STYLE_SECONDARY) for s in sp[3:]])
            rows.append([btn.callback(("✅" if d == days else "") + lbl, f"psetpdays_{plugin_name}_{d}", style=ButtonBuilder.STYLE_SECONDARY) for lbl, d in _prem.DAY_PRESETS])
            rows.append([btn.callback(" 👥 Aboneler", f"psetpsubs_{plugin_name}", style=ButtonBuilder.STYLE_PRIMARY)])
        rows.append([btn.callback(" 🔙 Geri", f"psetsel_{plugin_name}", style=ButtonBuilder.STYLE_DANGER)])
        await _safe_edit(event, text, rows)
        try:
            await _ans(event)
        except Exception:
            pass

    @bot.on(events.CallbackQuery(pattern=rb"psetprem_([a-zA-Z0-9_]+)$"))
    async def pset_premium_handler(event):
        if not await _is_admin(event):
            await event.answer("❌ Yetkiniz yok.", alert=True); return
        await show_plugin_premium(event, event.pattern_match.group(1).decode())

    @bot.on(events.CallbackQuery(pattern=rb"psetptype_([a-zA-Z0-9_]+)_(genel|ozel|premium)$"))
    async def pset_ptype_handler(event):
        if not await _is_admin(event):
            await event.answer("❌ Yetkiniz yok.", alert=True); return
        from utils import premium as _prem
        name = event.pattern_match.group(1).decode()
        ptype = event.pattern_match.group(2).decode()
        _prem.set_config(name, ptype=ptype)
        try:
            await event.answer(f"Tip: {_prem.TYPE_LABELS.get(ptype, ptype)}")
        except Exception:
            pass
        await show_plugin_premium(event, name)

    @bot.on(events.CallbackQuery(pattern=rb"psetpstars_([a-zA-Z0-9_]+)_(\d+)$"))
    async def pset_pstars_handler(event):
        if not await _is_admin(event):
            await event.answer("❌ Yetkiniz yok.", alert=True); return
        from utils import premium as _prem
        name = event.pattern_match.group(1).decode()
        stars = int(event.pattern_match.group(2).decode())
        _prem.set_config(name, stars=stars)
        try:
            await event.answer(f"Fiyat: {stars} ⭐")
        except Exception:
            pass
        await show_plugin_premium(event, name)

    @bot.on(events.CallbackQuery(pattern=rb"psetpdays_([a-zA-Z0-9_]+)_(\d+)$"))
    async def pset_pdays_handler(event):
        if not await _is_admin(event):
            await event.answer("❌ Yetkiniz yok.", alert=True); return
        from utils import premium as _prem
        name = event.pattern_match.group(1).decode()
        days = int(event.pattern_match.group(2).decode())
        _prem.set_config(name, days=days)
        try:
            await event.answer(f"Süre: {days} gün")
        except Exception:
            pass
        await show_plugin_premium(event, name)

    @bot.on(events.CallbackQuery(pattern=rb"psetpsubs_([a-zA-Z0-9_]+)$"))
    async def pset_psubs_handler(event):
        if not await _is_admin(event):
            await event.answer("❌ Yetkiniz yok.", alert=True); return
        from utils import premium as _prem
        import time as _t
        name = event.pattern_match.group(1).decode()
        subs = _prem.list_active_subs(name)
        if not subs:
            text = f"👥 **{name} — Aboneler**\n\nAktif abone yok."
        else:
            lines = []
            for uid, exp in sorted(subs.items(), key=lambda x: x[1]):
                left = max(0, int((int(exp) - _t.time()) // 86400))
                lines.append(f"• `{uid}` — {left} gün")
            text = f"👥 **{name} — Aboneler ({len(subs)})**\n\n" + "\n".join(lines[:40])
        await _safe_edit(event, text, [[btn.callback(" 🔙 Geri", f"psetprem_{name}", style=ButtonBuilder.STYLE_DANGER)]])
        try:
            await _ans(event)
        except Exception:
            pass

    @bot.on(events.CallbackQuery(pattern=rb"pset_access_([a-zA-Z0-9_]+)_(public|private)"))
    async def pset_access_handler(event):
        """Plugin erişim ayarı"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        match = event.pattern_match
        plugin_name = match.group(1).decode()
        access = match.group(2).decode()
        
        is_public = access == "public"
        
        # Önceki durumu kaydet (genel yapılırken eski kullanıcıları bulmak için)
        plugin = await db.get_plugin(plugin_name)
        previous_users = []
        if is_public and plugin:
            # Özel yapılmadan önce kimler kullanıyordu - DB'de hala active_plugins'de olanlar
            users = await db.get_all_users()
            for user in users:
                if plugin_name in user.get("active_plugins", []):
                    previous_users.append(user.get("user_id"))
        
        await db.update_plugin(plugin_name, {"is_public": is_public})
        
        count = 0
        
        if not is_public:
            # Özel yapıldığında izinsiz kullanıcılarda deaktif et
            allowed_users = plugin.get("allowed_users", []) if plugin else []
            
            users = await db.get_all_users()
            for user in users:
                user_id = user.get("user_id")
                
                # İzinli kullanıcıları atla
                if user_id in allowed_users:
                    continue
                
                # Owner ve sudo'ları atla
                if user_id == config.OWNER_ID or await db.is_sudo(user_id):
                    continue
                
                active = user.get("active_plugins", [])
                if plugin_name in active:
                    active.remove(plugin_name)
                    await db.update_user(user_id, {"active_plugins": active})
                    
                    # Handler'ları kaldır
                    try:
                        success, _ = await plugin_manager.deactivate_plugin(user_id, plugin_name)
                        if success:
                            count += 1
                    except:
                        pass
            
            if count > 0:
                await event.answer(f"✅ Özel yapıldı! {count} kullanıcıda kaldırıldı.", alert=True)
            else:
                await event.answer(f"✅ Özel yapıldı!", alert=True)
        else:
            # Genel yapıldığında önceden yüklenmiş kullanıcılarda tekrar aktif et
            users = await db.get_all_users()
            for user in users:
                user_id = user.get("user_id")
                active = user.get("active_plugins", [])
                
                # Zaten aktifse atla
                if plugin_name in active:
                    # Ama handler yüklü olmayabilir, client varsa yükle
                    client = smart_session_manager.get_client(user_id)
                    if client:
                        # user_active_plugins'de yoksa yükle
                        if user_id not in plugin_manager.user_active_plugins or \
                           plugin_name not in plugin_manager.user_active_plugins.get(user_id, {}):
                            try:
                                success, _ = await plugin_manager.activate_plugin(user_id, plugin_name, client)
                                if success:
                                    count += 1
                            except:
                                pass
            
            if count > 0:
                await event.answer(f"✅ Genel yapıldı! {count} kullanıcıda yüklendi.", alert=True)
            else:
                await event.answer(f"✅ Genel yapıldı!", alert=True)
        
        await show_plugin_settings(event, plugin_name)
    

    @bot.on(events.CallbackQuery(pattern=rb"pset_status_([a-zA-Z0-9_]+)_(enable|disable)"))
    async def pset_status_handler(event):
        """Plugin aktif/devre dışı"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        match = event.pattern_match
        plugin_name = match.group(1).decode()
        status = match.group(2).decode()
        
        is_disabled = status == "disable"
        await db.update_plugin(plugin_name, {"is_disabled": is_disabled})
        
        deactivated_count = 0
        if is_disabled:
            # Tüm kullanıcılarda deaktif et
            users = await db.get_all_users()
            for user in users:
                user_id = user.get("user_id")
                active = user.get("active_plugins", [])
                if plugin_name in active:
                    active.remove(plugin_name)
                    await db.update_user(user_id, {"active_plugins": active})
                    
                    # Handler'ları kaldır (client aktifse)
                    try:
                        success, _ = await plugin_manager.deactivate_plugin(user_id, plugin_name)
                        if success:
                            deactivated_count += 1
                    except:
                        pass
            
            await event.answer(f"✅ Devre dışı! {deactivated_count} kullanıcıda kaldırıldı.", alert=True)
        else:
            await event.answer(f"✅ Aktif edildi!", alert=True)
        
        await show_plugin_settings(event, plugin_name)
    

    @bot.on(events.CallbackQuery(pattern=rb"pset_default_([a-zA-Z0-9_]+)_(on|off)"))
    async def pset_default_handler(event):
        """Plugin varsayılan aktif ayarı"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        match = event.pattern_match
        plugin_name = match.group(1).decode()
        default = match.group(2).decode()
        
        default_active = default == "on"
        await db.update_plugin(plugin_name, {"default_active": default_active})
        
        if default_active:
            # Tüm giriş yapmış kullanıcılarda bu plugin'i aktif et
            users = await db.get_logged_in_users()
            activated_count = 0
            
            for user in users:
                user_id = user.get("user_id")
                active_plugins = user.get("active_plugins", [])
                
                # Zaten aktif değilse ekle
                if plugin_name not in active_plugins:
                    active_plugins.append(plugin_name)
                    await db.update_user(user_id, {"active_plugins": active_plugins})
                    
                    # Eğer client aktifse plugin'i yükle
                    client = smart_session_manager.get_client(user_id)
                    if client:
                        try:
                            await plugin_manager.activate_plugin(user_id, plugin_name, client)
                            activated_count += 1
                        except:
                            pass
            
            await event.answer(f"✅ Varsayılan aktif! {activated_count} kullanıcıda yüklendi.", alert=True)
        else:
            await event.answer(f"✅ Varsayılan pasif yapıldı!", alert=True)
        
        await show_plugin_settings(event, plugin_name)
    

    @bot.on(events.CallbackQuery(pattern=rb"psetallow_([a-zA-Z0-9_]+)$"))
    async def pset_allow_prompt(event):
        """Kullanıcıya izin ver - ID iste"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        plugin_name = event.pattern_match.group(1).decode()
        
        text = f"👤 **{plugin_name}** için İzin Ver\n\n"
        text += "Kullanıcı ID'sini yazın:\n"
        text += f"Örnek: `/pallow {plugin_name} 123456789`"
        
        await event.edit(text, buttons=[
            [Button.inline("🔙 Geri", f"psetsel_{plugin_name}")]
        ])
    

    @bot.on(events.NewMessage(pattern=r'^/pallow\s+(\S+)\s+(\d+)$'))
    async def pallow_command(event):
        """Plugin'e kullanıcı izni ver"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        plugin_name = event.pattern_match.group(1)
        user_id = int(event.pattern_match.group(2))
        
        plugin = await db.get_plugin(plugin_name)
        if not plugin:
            await event.respond(f"❌ `{plugin_name}` bulunamadı.")
            return
        
        await db.add_plugin_user_access(plugin_name, user_id)
        await event.respond(f"✅ `{user_id}` kullanıcısına `{plugin_name}` izni verildi.")
    

    @bot.on(events.CallbackQuery(pattern=rb"psetrestrict_([a-zA-Z0-9_]+)$"))
    async def pset_restrict_prompt(event):
        """Kullanıcıyı engelle - ID iste"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        plugin_name = event.pattern_match.group(1).decode()
        
        text = f"🚫 **{plugin_name}** için Engelle\n\n"
        text += "Kullanıcı ID'sini yazın:\n"
        text += f"Örnek: `/prestrict {plugin_name} 123456789`"
        
        await event.edit(text, buttons=[
            [Button.inline("🔙 Geri", f"psetsel_{plugin_name}")]
        ])
    

    @bot.on(events.NewMessage(pattern=r'^/prestrict\s+(\S+)\s+(\d+)$'))
    async def prestrict_command(event):
        """Plugin'den kullanıcıyı engelle"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        plugin_name = event.pattern_match.group(1)
        user_id = int(event.pattern_match.group(2))
        
        plugin = await db.get_plugin(plugin_name)
        if not plugin:
            await event.respond(f"❌ `{plugin_name}` bulunamadı.")
            return
        
        await db.restrict_plugin_user(plugin_name, user_id)
        
        # Eğer kullanıcının aktif plugin'i varsa kaldır
        user = await db.get_user(user_id)
        if user:
            active = user.get("active_plugins", [])
            if plugin_name in active:
                active.remove(plugin_name)
                await db.update_user(user_id, {"active_plugins": active})
                await plugin_manager.deactivate_plugin(user_id, plugin_name)
        
        await event.respond(f"✅ `{user_id}` kullanıcısı `{plugin_name}` için engellendi.")
    

    @bot.on(events.CallbackQuery(pattern=rb"psetallowls_([a-zA-Z0-9_]+)"))
    async def pset_allowlist_handler(event):
        """İzinli kullanıcıları listele"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        plugin_name = event.pattern_match.group(1).decode()
        plugin = await db.get_plugin(plugin_name)
        
        if not plugin:
            await event.answer("❌ Plugin bulunamadı!", alert=True)
            return
        
        allowed = plugin.get("allowed_users", [])
        
        text = f"👤 **{plugin_name}** İzinli Kullanıcılar\n\n"
        
        if not allowed:
            text += "📭 Henüz izinli kullanıcı yok.\n"
            text += "(Özel plugin'ler için izin gerekir)"
        else:
            for uid in allowed[:20]:
                user = await db.get_user(uid)
                if user:
                    name = user.get("username") or user.get("first_name") or str(uid)
                    text += f"• `{uid}` - {name}\n"
                else:
                    text += f"• `{uid}`\n"
            
            if len(allowed) > 20:
                text += f"\n... ve {len(allowed)-20} kişi daha"
        
        text += f"\n\n🗑️ İzni kaldır: `/premove {plugin_name} <id>`"
        
        await event.edit(text, buttons=[
            [Button.inline("🔙 Geri", f"psetsel_{plugin_name}")]
        ])
    

    @bot.on(events.CallbackQuery(pattern=rb"psetrestrictls_([a-zA-Z0-9_]+)"))
    async def pset_restrictlist_handler(event):
        """Engelli kullanıcıları listele"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        plugin_name = event.pattern_match.group(1).decode()
        plugin = await db.get_plugin(plugin_name)
        
        if not plugin:
            await event.answer("❌ Plugin bulunamadı!", alert=True)
            return
        
        restricted = plugin.get("restricted_users", [])
        
        text = f"🚫 **{plugin_name}** Engelli Kullanıcılar\n\n"
        
        if not restricted:
            text += "📭 Henüz engelli kullanıcı yok."
        else:
            for uid in restricted[:20]:
                user = await db.get_user(uid)
                if user:
                    name = user.get("username") or user.get("first_name") or str(uid)
                    text += f"• `{uid}` - {name}\n"
                else:
                    text += f"• `{uid}`\n"
            
            if len(restricted) > 20:
                text += f"\n... ve {len(restricted)-20} kişi daha"
        
        text += f"\n\n✅ Engeli kaldır: `/punrestrict {plugin_name} <id>`"
        
        await event.edit(text, buttons=[
            [Button.inline("🔙 Geri", f"psetsel_{plugin_name}")]
        ])
    

    @bot.on(events.NewMessage(pattern=r'^/premove\s+(\S+)\s+(\d+)$'))
    async def premove_command(event):
        """Plugin iznini kaldır"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        plugin_name = event.pattern_match.group(1)
        user_id = int(event.pattern_match.group(2))
        
        await db.remove_plugin_user_access(plugin_name, user_id)
        await event.respond(f"✅ `{user_id}` kullanıcısının `{plugin_name}` izni kaldırıldı.")
    

    @bot.on(events.NewMessage(pattern=r'^/punrestrict\s+(\S+)\s+(\d+)$'))
    async def punrestrict_command(event):
        """Plugin engelini kaldır"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        plugin_name = event.pattern_match.group(1)
        user_id = int(event.pattern_match.group(2))
        
        await db.unrestrict_plugin_user(plugin_name, user_id)
        await event.respond(f"✅ `{user_id}` kullanıcısının `{plugin_name}` engeli kaldırıldı.")
    

    @bot.on(events.CallbackQuery(pattern=rb"psetusers_([a-zA-Z0-9_]+)"))
    async def pset_users_handler(event):
        """Plugin'i kullanan kullanıcıları listele"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer("❌ Yetkiniz yok!", alert=True)
            return
        
        plugin_name = event.pattern_match.group(1).decode()
        
        users = await db.get_all_users()
        active_users = []
        
        for user in users:
            if plugin_name in user.get("active_plugins", []):
                active_users.append(user)
        
        text = f"👥 **{plugin_name}** Kullananlar\n\n"
        
        if not active_users:
            text += "📭 Bu plugin'i kullanan yok."
        else:
            text += f"Toplam: `{len(active_users)}` kullanıcı\n\n"
            for user in active_users[:20]:
                uid = user.get("user_id")
                name = user.get("username") or user.get("first_name") or str(uid)
                text += f"• `{uid}` - {name}\n"
            
            if len(active_users) > 20:
                text += f"\n... ve {len(active_users)-20} kişi daha"
        
        await event.edit(text, buttons=[
            [Button.inline("🔙 Geri", f"psetsel_{plugin_name}")]
        ])
    

    @bot.on(events.CallbackQuery(data=b"noop"))
    async def noop_handler(event):
        """Boş callback - sayfa numarası için"""
        await _ans(event)
