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

def _filter_accessible(all_plugins, uid):
    """ip_plugins ile AYNI sıralı/filtreli erişilebilir plugin listesi (index tutarlılığı için)."""
    return [
        p for p in all_plugins
        if not p.get("is_disabled")
        and (p.get("is_public", True) or uid in p.get("allowed_users", []))
        and uid not in p.get("restricted_users", [])
    ]


async def _render_plugin_detail(event, target_user_id, gi, full=False):
    """Tek bir plugin için detay panelini ÇİZER (sadece edit, answer çağırmaz)."""
    user_data = await db.get_user(event.sender_id)
    active_plugins = user_data.get("active_plugins", []) if user_data else []
    all_plugins = await db.get_all_plugins()
    accessible = _filter_accessible(all_plugins, event.sender_id)

    if gi < 0 or gi >= len(accessible):
        try:
            await event.edit(
                "⚠️ **Plugin bulunamadı** (liste değişmiş olabilir).",
                buttons=[[Button.inline("🔙 Listeye Dön", f"ip_plugins_{target_user_id}_0".encode())]],
            )
        except Exception:
            pass
        return

    p = accessible[gi]
    name = p.get("name", "?")
    on = name in active_plugins
    page = gi // 8
    desc = p.get("description") or "Açıklama yok."
    cmds = p.get("commands", []) or []
    status = "🟢 **Yüklü (aktif)**" if on else "🔴 **Yüklü değil**"

    text = f"🔌 **{name}**\n\n{status}\n\n📝 {desc}"
    if full:
        if cmds:
            cmd_list = "\n".join(f"• `.{c}`" for c in cmds)
            text += f"\n\n**Komutlar ({len(cmds)}):**\n{cmd_list}"
        else:
            text += "\n\n_Komut bilgisi yok._"
    else:
        if cmds:
            preview = ", ".join(f"`.{c}`" for c in cmds[:3])
            extra = f" +{len(cmds) - 3}" if len(cmds) > 3 else ""
            text += f"\n\n🔧 {preview}{extra}"

    buttons = []
    if p.get("default_active"):
        buttons.append([Button.inline("⭐ Zorunlu Plugin", f"ipt_{target_user_id}_{gi}".encode())])
    elif on:
        buttons.append([Button.inline("⛔ Plugini Kapat", f"ipt_{target_user_id}_{gi}".encode())])
    else:
        buttons.append([Button.inline("✅ Plugini Yükle", f"ipt_{target_user_id}_{gi}".encode())])

    if full:
        buttons.append([Button.inline("🔼 Özet", f"ipd_{target_user_id}_{gi}".encode())])
    else:
        buttons.append([Button.inline("📄 Plugin Detayı", f"ipi_{target_user_id}_{gi}".encode())])

    buttons.append([Button.inline("🔙 Listeye Dön", f"ip_plugins_{target_user_id}_{page}".encode())])

    try:
        await event.edit(text, buttons=buttons)
    except Exception:
        pass


# ── TÜM KOMUTLAR KATALOĞU (keşfedilebilirlik için) ─────────────────
ALL_COMMANDS = [
    ("🏷️ Etiketleme", [
        (".tag", "Gruptaki herkesi etiketle (butonlu akış)"),
        (".tagadmin", "Sadece yöneticileri etiketle"),
        (".tagstop", "Etiketlemeyi durdur"),
        (".tagstat", "Etiketleme durumunu göster"),
        (".tagban / .tagunban", "Kişiyi hariç tut / geri al"),
        (".tagbanlist", "Hariç tutulanları listele"),
        (".tagekle <ifade>", "Özel etiketleme ifadesi ekle (✏️ Özel kategorisi)"),
        (".tagliste", "Özel ifadeleri listele"),
        (".tagsil <no> / .tagtemizle", "Özel ifade sil / tümünü temizle"),
        (".taghelp", "Etiketleme yardımı"),
    ]),
    ("📨 Otomatik Mesaj", [
        (".otomsg <mesaj>", "HIZLI: butonlu oto mesaj (foto/video/dosya yanıtlayabilirsin)"),
        (".otomsg ekle <chat> <dk> <tekrar> <mesaj>", "Detaylı görev ekle"),
        (".otomsgl", "Görevleri listele (butonlu sayfalı)"),
        (".otomsgs", "Görev durumlarını göster"),
        (".otomsgstop / .otomsgstart <id>", "Görevi durdur / başlat"),
        (".otomsgstartall / .otomsgstopall", "Tümünü başlat / durdur"),
        (".otomsgdel <id>", "Görevi sil"),
        (".otomsgduzenle <id> mesaj|aralık|tekrar", "Görevi düzenle"),
        (".otomsghelp", "Oto mesaj yardımı"),
    ]),
    ("🎭 Profil", [
        (".afk / .unafk", "AFK moduna geç / dön (kalıcı)"),
        (".clon <yanıt/@/id>", "Birinin profilini klonla"),
        (".unclon", "Orijinal profile dön"),
        (".saveme", "Mevcut profilini kaydet"),
        (".cloninfo", "Kayıtlı profili göster"),
        (".resetclon", "Klon verilerini sıfırla"),
    ]),
    ("🎉 Eğlence", [
        (".burc <burç>", "Günlük burç yorumu"),
        (".burch / .burca <burç>", "Haftalık / aylık burç"),
        (".ses <metin>", "Metni sese çevir (TTS)"),
        (".sesler", "Mevcut sesleri listele"),
        (".sesayar <ses>", "Sesi değiştir (örn: kadın)"),
        (".q", "Mesajı alıntı sticker'ı yap"),
        (".qs", "Alıntıyı sticker paketine kaydet"),
        (".qd / .qpaket / .qrenkler", "Sticker sil / paket bilgisi / renkler"),
    ]),
    ("🛠️ Araçlar", [
        (".raw", "Mesajın ham verisini göster"),
        (".emojiid", "Custom emoji ID'lerini göster"),
        (".userid", "Kullanıcı bilgisi"),
        (".id / .ping / .alive", "Sohbet-ID / gecikme / bot durumu"),
    ]),
    ("⚙️ Sistem", [
        (".start", "Butonlu kontrol paneli"),
        (".plugins", "Plugin listesi"),
        (".pload / .punload <isim>", "Plugin yükle / kaldır"),
        (".mystats", "İstatistiklerin"),
        (".uhelp", "Komut yardımı"),
    ]),
]


def _cmdcat_buttons(uid):
    rows, row = [], []
    for i, (cat, _cmds) in enumerate(ALL_COMMANDS):
        row.append(Button.inline(cat, f"ip_cmdcat_{uid}_{i}".encode()))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([Button.inline("🔙 Geri", f"ip_main_{uid}".encode())])
    return rows


def _render_cmd_category(idx):
    cat, cmds = ALL_COMMANDS[idx]
    lines = [f"**{cat}**", ""]
    for cmd, desc in cmds:
        lines.append(f"`{cmd}`\n  └ {desc}")
    lines.append("")
    lines.append("💡 Komutlar `.` ile başlar.")
    return "\n".join(lines)


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
                    Button.inline("📚 Tüm Komutlar", f"ip_help_{user_id}".encode()),
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
        """Tüm pluginler — her biri buton (🟢/🔴), sayfalı."""
        match = event.pattern_match
        target_user_id = int(match.group(1).decode())
        page = int(match.group(2).decode()) if match.group(2) else 0

        if target_user_id != event.sender_id:
            await event.answer("❌ Bu panel size ait değil!", alert=True)
            return

        user_data = await db.get_user(event.sender_id)
        active_plugins = user_data.get("active_plugins", []) if user_data else []
        all_plugins = await db.get_all_plugins()
        accessible = _filter_accessible(all_plugins, event.sender_id)

        per_page = 8
        total = len(accessible)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        page = max(0, min(page, total_pages - 1))
        start = page * per_page
        page_plugins = accessible[start:start + per_page]

        if not accessible:
            text = "📭 **Henüz plugin yok.**"
            buttons = [[Button.inline("🔙 Geri", f"ip_main_{target_user_id}".encode())]]
        else:
            loaded = sum(1 for p in accessible if p.get("name") in active_plugins)
            text = (
                f"🔌 **Pluginler** — {total} adet · 🟢 {loaded} yüklü\n"
                f"📄 Sayfa {page + 1}/{total_pages}\n\n"
                f"Bir plugine dokun → aç/kapat & detay"
            )
            buttons = []
            for i, p in enumerate(page_plugins):
                gi = start + i
                name = p.get("name", "?")
                on = name in active_plugins
                emoji = "🟢" if on else "🔴"
                star = "⭐" if p.get("default_active") else ""
                label = f"{emoji} {star}{name}".strip()
                buttons.append([Button.inline(label[:60], f"ipd_{target_user_id}_{gi}".encode())])

            nav = []
            if page > 0:
                nav.append(Button.inline("◀️", f"ip_plugins_{target_user_id}_{page - 1}".encode()))
            if total_pages > 1:
                nav.append(Button.inline(f"📄 {page + 1}/{total_pages}", f"ip_plugins_{target_user_id}_{page}".encode()))
            if page < total_pages - 1:
                nav.append(Button.inline("▶️", f"ip_plugins_{target_user_id}_{page + 1}".encode()))
            if nav:
                buttons.append(nav)

            buttons.append([
                Button.inline("📦 Yüklü", f"ip_active_{target_user_id}_0".encode()),
                Button.inline("🔙 Geri", f"ip_main_{target_user_id}".encode()),
            ])

        try:
            await event.edit(text, buttons=buttons)
        except Exception:
            pass
        await event.answer()

    @bot.on(events.CallbackQuery(pattern=rb"ipd_(\d+)_(\d+)"))
    async def ip_pdetail_cb(event):
        """Bir plugine dokununca: detay paneli (özet)."""
        target_user_id = int(event.pattern_match.group(1).decode())
        gi = int(event.pattern_match.group(2).decode())
        if target_user_id != event.sender_id:
            await event.answer("❌ Bu panel size ait değil!", alert=True)
            return
        await _render_plugin_detail(event, target_user_id, gi, full=False)
        try:
            await event.answer()
        except Exception:
            pass

    @bot.on(events.CallbackQuery(pattern=rb"ipi_(\d+)_(\d+)"))
    async def ip_pinfo_cb(event):
        """Plugin Detayı: tüm açıklama + komutlar."""
        target_user_id = int(event.pattern_match.group(1).decode())
        gi = int(event.pattern_match.group(2).decode())
        if target_user_id != event.sender_id:
            await event.answer("❌ Bu panel size ait değil!", alert=True)
            return
        await _render_plugin_detail(event, target_user_id, gi, full=True)
        try:
            await event.answer()
        except Exception:
            pass

    @bot.on(events.CallbackQuery(pattern=rb"ipt_(\d+)_(\d+)"))
    async def ip_ptoggle_cb(event):
        """Plugini aç/kapat (yükle/kaldır) ve paneli yenile."""
        target_user_id = int(event.pattern_match.group(1).decode())
        gi = int(event.pattern_match.group(2).decode())
        if target_user_id != event.sender_id:
            await event.answer("❌ Bu panel size ait değil!", alert=True)
            return

        all_plugins = await db.get_all_plugins()
        accessible = _filter_accessible(all_plugins, event.sender_id)
        if gi < 0 or gi >= len(accessible):
            await event.answer("Plugin bulunamadı.", alert=True)
            return
        p = accessible[gi]
        name = p.get("name")

        user_data = await db.get_user(event.sender_id)
        active = list(user_data.get("active_plugins", []) if user_data else [])

        from userbot.plugins import plugin_manager
        try:
            from userbot.smart_manager import smart_session_manager
            client = smart_session_manager.get_client(event.sender_id)
        except Exception:
            client = None

        if name in active:
            # KAPAT
            if p.get("default_active"):
                await event.answer("⭐ Zorunlu plugin, kapatılamaz.", alert=True)
                return
            active.remove(name)
            await db.update_user(event.sender_id, {"active_plugins": active})
            try:
                await plugin_manager.deactivate_plugin(event.sender_id, name)
            except Exception:
                pass
            try:
                await event.answer(f"⛔ {name} kapatıldı")
            except Exception:
                pass
        else:
            # YÜKLE
            if p.get("is_disabled"):
                await event.answer("⛔ Bu plugin devre dışı.", alert=True)
                return
            active.append(name)
            await db.update_user(event.sender_id, {"active_plugins": active})
            ok, msg = True, ""
            if client is not None:
                try:
                    ok, msg = await plugin_manager.activate_plugin(event.sender_id, name, client)
                except Exception as e:
                    ok, msg = False, str(e)
            try:
                await event.answer(f"✅ {name} yüklendi" if ok else f"❌ {str(msg)[:60]}")
            except Exception:
                pass

        # Paneli yenile (durum güncellensin)
        await _render_plugin_detail(event, target_user_id, gi, full=False)

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
        """Tüm Komutlar — kategori menüsü"""
        target_user_id = int(event.pattern_match.group(1).decode())
        if target_user_id != event.sender_id:
            await event.answer("❌ Bu panel size ait değil!", alert=True)
            return

        text = (
            "📚 **Tüm Komutlar**\n\n"
            "Bir kategori seç; komutları ve ne işe yaradıklarını gör.\n"
            "💡 Tüm komutlar `.` ile başlar."
        )
        try:
            await event.edit(text, buttons=_cmdcat_buttons(target_user_id))
        except Exception:
            pass
        await event.answer()

    @bot.on(events.CallbackQuery(pattern=rb"ip_cmdcat_(\d+)_(\d+)"))
    async def ip_cmdcat_cb(event):
        """Bir kategorinin komutlarını göster"""
        target_user_id = int(event.pattern_match.group(1).decode())
        idx = int(event.pattern_match.group(2).decode())
        if target_user_id != event.sender_id:
            await event.answer("❌ Bu panel size ait değil!", alert=True)
            return
        if idx < 0 or idx >= len(ALL_COMMANDS):
            await event.answer("Kategori bulunamadı.", alert=True)
            return
        text = _render_cmd_category(idx)
        buttons = [[Button.inline("🔙 Kategoriler", f"ip_help_{target_user_id}".encode())]]
        try:
            await event.edit(text, buttons=buttons)
        except Exception:
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