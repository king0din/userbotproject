# ============================================
# KingTG UserBot Service - User / plugins_user
# Kullanıcının plugin listesi + TEK DOKUNUŞ inline aç/kapat
# + ℹ️ Detay Modu (butonlu /pinfo)
# Sayfa oluşturucular _common.py'da (menu.py ile ortak)
# ============================================

from telethon import events
import config
from database import database as db
from userbot.smart_manager import smart_session_manager
from userbot.plugins import plugin_manager
from utils import (
    check_ban, send_log
)
from utils.bot_api import bot_api, btn, ButtonBuilder
from utils.logger import get_logger

log = get_logger(__name__)

# Eski uyumluluk için alias
userbot_manager = smart_session_manager

from ._common import (
    accessible_plugins,
    build_plugins_page,
    build_my_plugins_page,
    build_info_mode_page,
    build_plugin_info,
)


def register(bot):

    async def _render(event, text, rows):
        await bot_api.edit_message_text(
            chat_id=event.sender_id, message_id=event.message_id,
            text=text, reply_markup=btn.inline_keyboard(rows)
        )

    async def _ensure_logged(event):
        u = await db.get_user(event.sender_id)
        if not u or not u.get("is_logged_in"):
            await event.answer("Önce giriş yapmalısınız", alert=True)
            return None
        return u

    # ==========================================
    # PLUGİN LİSTESİ (sayfalı)
    # ==========================================
    @bot.on(events.CallbackQuery(pattern=rb"plugins_page_(\d+)"))
    async def plugins_menu_handler(event):
        if not await _ensure_logged(event):
            return
        page = int(event.data.decode().split("_")[-1])
        text, rows = await build_plugins_page(event.sender_id, page)
        await _render(event, text, rows)
        await event.answer()

    @bot.on(events.CallbackQuery(pattern=rb"my_plugins_(\d+)"))
    async def my_plugins_handler(event):
        if not await _ensure_logged(event):
            return
        page = int(event.data.decode().split("_")[-1])
        text, rows = await build_my_plugins_page(event.sender_id, page)
        await _render(event, text, rows)
        await event.answer()

    # ==========================================
    # ℹ️ DETAY MODU (butonlu /pinfo)
    # ==========================================
    @bot.on(events.CallbackQuery(pattern=rb"pim_(\d+)$"))
    async def info_mode_handler(event):
        if not await _ensure_logged(event):
            return
        page = int(event.data.decode().split("_")[-1])
        text, rows = await build_info_mode_page(event.sender_id, page)
        await _render(event, text, rows)
        await event.answer()

    @bot.on(events.CallbackQuery(pattern=rb"pi_(\d+)_(.+)"))
    async def plugin_info_handler(event):
        if not await _ensure_logged(event):
            return
        _, page_str, name = event.data.decode().split("_", 2)
        text, rows = await build_plugin_info(event.sender_id, int(page_str), name)
        if not text:
            await event.answer("Plugin bulunamadı", alert=True)
            return
        await _render(event, text, rows)
        await event.answer()

    # Bilgi kartından yükle/kaldır: pi<page>_on_<name> / pi<page>_off_<name>
    @bot.on(events.CallbackQuery(pattern=rb"pi(\d+)_(on|off)_(.+)"))
    @check_ban
    async def plugin_info_toggle_handler(event):
        user_id = event.sender_id
        if not await _ensure_logged(event):
            return
        import re
        m = re.match(r"pi(\d+)_(on|off)_(.+)", event.data.decode())
        page, action, name = int(m.group(1)), m.group(2), m.group(3)

        toast = await _toggle_plugin(event, user_id, name, want_on=(action == "on"))
        if toast:
            await event.answer(toast)
        text, rows = await build_plugin_info(user_id, page, name)
        if text:
            try:
                await _render(event, text, rows)
            except Exception:
                log.debug("Bilgi kartı yenilenemedi", exc_info=True)

    # ==========================================
    # ORTAK AÇ/KAPAT ÇEKİRDEĞİ
    # Premium ise komut yazdırmaz — faturayı DİREKT gönderir.
    # Dönen değer: toast metni (None = toast'ı kendisi gösterdi)
    # ==========================================
    async def _toggle_plugin(event, user_id, name, want_on):
        plugin = await db.get_plugin(name)
        if not plugin:
            await event.answer("Plugin bulunamadı", alert=True)
            return None
        if plugin.get("is_disabled", False):
            await event.answer("⛔ Bu plugin yönetici tarafından devre dışı", alert=True)
            return None

        if not want_on:
            if plugin.get("default_active", False):
                await event.answer("⭐ Zorunlu plugin, kapatılamaz", alert=True)
                return None
            success, _ = await plugin_manager.deactivate_plugin(user_id, name)
            if success:
                await send_log(bot, "plugin", f"Deaktif: {name}", user_id)
            return f"⚪ {name} kapatıldı" if success else "❌ İşlem başarısız"

        # AÇ — önce erişim (premium/özel) kontrolü
        try:
            from utils import premium
            reason, pcfg = premium.access_reason(user_id, name)
        except Exception:
            log.warning("Premium kontrolü başarısız: %s", name, exc_info=True)
            reason, pcfg = "ok", {}
        if reason == "need_pay":
            stars = (pcfg or {}).get("stars", 100)
            days = (pcfg or {}).get("days", 30)
            # Faturayı direkt gönder — kullanıcıya komut yazdırma
            try:
                sent = await premium.send_star_invoice(bot, user_id, name)
            except Exception:
                log.warning("Fatura gönderilemedi: %s", name, exc_info=True)
                sent = False
            if sent:
                await event.answer(
                    f"💎 Premium plugin ({stars}⭐/{days}g). Fatura gönderildi — ödeme sonrası otomatik açılır.",
                    alert=True)
            else:
                await event.answer(
                    f"💎 Premium plugin ({stars}⭐/{days}g). Fatura gönderilemedi, tekrar dene.",
                    alert=True)
            return None
        if reason == "need_grant":
            await event.answer("🔒 Özel plugin. Erişim için yöneticiye başvur.", alert=True)
            return None

        client = await smart_session_manager.get_or_create_client(user_id)
        if not client:
            await event.answer("❌ Userbot bağlantısı kurulamadı, tekrar giriş yap", alert=True)
            return None
        success, _ = await plugin_manager.activate_plugin(user_id, name, client)
        if success:
            await send_log(bot, "plugin", f"Aktif: {name}", user_id)
        return f"🟢 {name} açıldı" if success else "❌ Yüklenemedi"

    # ==========================================
    # TOPLU İŞLEMLER (tek dokunuş)
    # ==========================================
    @bot.on(events.CallbackQuery(pattern=rb"pall_on_(\d+)"))
    @check_ban
    async def pall_on_handler(event):
        user_id = event.sender_id
        page = int(event.data.decode().rsplit("_", 1)[-1])
        u = await _ensure_logged(event)
        if not u:
            return
        await event.answer("⚡ Tümü açılıyor...")
        client = await smart_session_manager.get_or_create_client(user_id)
        if not client:
            await event.answer("❌ Bağlantı kurulamadı, tekrar giriş yap", alert=True)
            return
        active = u.get("active_plugins", [])
        done = 0
        for p in await accessible_plugins(user_id):
            name = p["name"]
            if name in active:
                continue
            try:
                from utils import premium
                reason, _ = premium.access_reason(user_id, name)
            except Exception:
                reason = "ok"
            if reason != "ok":
                continue  # premium/özel olanları atla
            try:
                ok, _ = await plugin_manager.activate_plugin(user_id, name, client)
                if ok:
                    done += 1
            except Exception:
                log.warning("Toplu aç: %s yüklenemedi (user=%s)", name, user_id, exc_info=True)
        await send_log(bot, "plugin", f"Toplu aç: {done}", user_id)
        text, rows = await build_plugins_page(user_id, page)
        await _render(event, f"✅ {done} plugin açıldı.\n\n" + text, rows)

    @bot.on(events.CallbackQuery(pattern=rb"pall_off_(\d+)"))
    @check_ban
    async def pall_off_handler(event):
        user_id = event.sender_id
        page = int(event.data.decode().rsplit("_", 1)[-1])
        u = await _ensure_logged(event)
        if not u:
            return
        await event.answer("⏹ Tümü kapatılıyor...")
        done = 0
        for name in list(u.get("active_plugins", [])):
            plugin = await db.get_plugin(name)
            if plugin and plugin.get("default_active", False):
                continue  # zorunlu olanlar kalsın
            try:
                ok, _ = await plugin_manager.deactivate_plugin(user_id, name)
                if ok:
                    done += 1
            except Exception:
                log.warning("Toplu kapat: %s kapatılamadı (user=%s)", name, user_id, exc_info=True)
        await send_log(bot, "plugin", f"Toplu kapat: {done}", user_id)
        text, rows = await build_plugins_page(user_id, page)
        await _render(event, f"⏹ {done} plugin kapatıldı.\n\n" + text, rows)

    # ==========================================
    # TEK DOKUNUŞ AÇ/KAPAT  (pt_<page>_<name> / pm_<page>_<name>)
    # ==========================================
    @bot.on(events.CallbackQuery(pattern=rb"p[tm]_(\d+)_(.+)"))
    @check_ban
    async def plugin_toggle_handler(event):
        user_id = event.sender_id
        data = event.data.decode()
        # p{t|m}_<page>_<name> -> name içinde '_' olabilir
        prefix, page_str, name = data.split("_", 2)
        page = int(page_str)

        user_data = await db.get_user(user_id)
        if not user_data or not user_data.get("is_logged_in"):
            await event.answer("Önce giriş yapmalısınız", alert=True)
            return

        is_active = name in user_data.get("active_plugins", [])
        toast = await _toggle_plugin(event, user_id, name, want_on=not is_active)
        if toast:
            await event.answer(toast)

        # Geldiği görünümü tazele (pt_ = liste, pm_ = pluginlerim)
        try:
            if prefix == "pm":
                text, rows = await build_my_plugins_page(user_id, page)
            else:
                text, rows = await build_plugins_page(user_id, page)
            await _render(event, text, rows)
        except Exception:
            log.debug("Plugin sayfası yenilenemedi (user=%s)", user_id, exc_info=True)

    # ==========================================
    # KOMUTLAR (geriye uyumlu — aynen korundu)
    # ==========================================
    @bot.on(events.NewMessage(pattern=r'^/pinfo\s+(\S+)$'))
    async def pinfo_command(event):
        plugin_name = event.pattern_match.group(1)
        text, rows = await build_plugin_info(event.sender_id, 0, plugin_name)
        if not text:
            await event.respond(f"❌ `{plugin_name}` bulunamadı.")
            return
        await bot_api.send_message(chat_id=event.sender_id, text=text,
                                   reply_markup=btn.inline_keyboard(rows))

    @bot.on(events.NewMessage(pattern=r'^/pactive\s+(\S+)$'))
    @check_ban
    async def pactive_command(event):
        plugin_name = event.pattern_match.group(1)
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
        client = await smart_session_manager.get_or_create_client(event.sender_id)
        if not client:
            await msg.edit("❌ Userbot bağlantısı kurulamadı. Lütfen tekrar giriş yapın.")
            return
        try:
            from utils import premium
            reason, pcfg = premium.access_reason(event.sender_id, plugin_name)
        except Exception:
            log.warning("Premium kontrolü başarısız: %s", plugin_name, exc_info=True)
            reason, pcfg = "ok", {}
        if reason == "need_pay":
            stars = (pcfg or {}).get("stars", 100)
            days = (pcfg or {}).get("days", 30)
            title = (pcfg or {}).get("title", plugin_name)
            try:
                sent = await premium.send_star_invoice(bot, event.sender_id, plugin_name)
            except Exception:
                log.warning("Fatura gönderilemedi: %s", plugin_name, exc_info=True)
                sent = False
            if sent:
                await msg.edit(
                    f"💎 **{title}** premium bir plugin.\n\n"
                    f"⭐ **{stars}** Yıldız · **{days}** gün\n\n"
                    f"Gönderdiğim faturadan ödeme yapınca otomatik açılacak."
                )
            else:
                await msg.edit(
                    f"💎 **{title}** premium ({stars}⭐ / {days} gün).\n"
                    f"Fatura gönderilemedi, lütfen tekrar dene."
                )
            return
        if reason == "need_grant":
            await msg.edit(
                f"🔒 **`{plugin_name}`** özel bir plugin.\n"
                f"Erişim için yöneticiye başvurmalısın."
            )
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
        """Komut da artık butonlu sayfayı açar — metin listesi yok"""
        user_data = await db.get_user(event.sender_id)
        if not user_data or not user_data.get("is_logged_in"):
            await event.respond("❌ Önce giriş yapmalısınız. /start → 🔐 Giriş Yap")
            return
        text, rows = await build_plugins_page(event.sender_id, 0)
        await bot_api.send_message(chat_id=event.sender_id, text=text,
                                   reply_markup=btn.inline_keyboard(rows))
