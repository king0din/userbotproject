# ============================================
# KingTG UserBot Service - User / help
# Yardım menüsü ve komut listesi
# (user.py'dan otomatik bölündü - davranış birebir korundu)
# ============================================

# ============================================
# KingTG UserBot Service - User Handlers
# ============================================

from telethon import events
import config
from database import database as db
from userbot.smart_manager import smart_session_manager
from utils import (
    check_ban
)
from utils.bot_api import bot_api, btn, ButtonBuilder

# Eski uyumluluk için alias
userbot_manager = smart_session_manager



def register(bot):

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
            [btn.callback("📝 Komutlar Listesi", "commands", style=ButtonBuilder.STYLE_SUCCESS)],
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
        text += "Giriş çok basit — sadece telefon numaranızla:\n\n"
        
        text += "📱 **Adımlar:**\n"
        text += "1️⃣ `🔐 Giriş Yap` butonuna tıklayın\n"
        text += "2️⃣ Numaranızı girin: `+905551234567`\n"
        text += "3️⃣ Telegram'dan gelen kodu girin\n"
        text += "4️⃣ 2FA (iki adımlı doğrulama) varsa şifrenizi girin\n\n"
        
        text += "🔒 **Güvenli mi?**\n"
        text += "Evet. Telegram'ın size gönderdiği doğrulama\n"
        text += "kodunu girersiniz; hesap şifreniz botla paylaşılmaz.\n"
        text += "Girdiğiniz numara/kod mesajı otomatik silinir.\n\n"
        
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
        
        text += "📥 **Plugin Yükleme (en kolay yol):**\n"
        text += "1️⃣ `🔌 Plugin'ler` menüsüne girin\n"
        text += "2️⃣ İstediğiniz plugin'e **dokunun** — anında açılır 🟢\n"
        text += "   Tekrar dokununca kapanır ⚪\n\n"
        
        text += "ℹ️ **Plugin Bilgisi (butonla):**\n"
        text += "Plugin listesinde `ℹ️ Detay Modu`na dokunun,\n"
        text += "sonra plugin'e dokunun — komutları ve açıklaması gelir.\n\n"

        text += "⌨️ **Komutla da olur:**\n"
        text += "• Yükle: `/pactive <isim>` · Kaldır: `/pinactive <isim>`\n"
        text += "• Bilgi: `/pinfo <isim>`\n\n"
        
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
        text += "Bunlar **bu botun** kendi komutlarıdır.\n"
        text += "`/` ile başlar ve **bu bota** yazılır.\n\n"
        text += "Örnekler:\n"
        text += "• `/start` - Ana menü\n"
        text += "• `/pactive ses` - Plugin yükle\n"
        text += "• `/pinfo afk` - Plugin bilgisi\n\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        text += "⚡ **Userbot Komutları (Telegram'da):**\n"
        text += "Bunlar **hesabınızı yöneten userbot'un** komutlarıdır.\n"
        text += "`.` ile başlar ve **herhangi bir sohbete** yazılır.\n\n"
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
        text += "C: Oturum bilgileriniz sunucuda güvenle saklanır ve\n"
        text += "yalnızca sizin userbot'unuz için kullanılır.\n"
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
        """Komutlar hub'ı: Bot komutları vs Userbot komutları farkını anlatır."""
        text = "📝 **Komutlar**\n\n"
        text += "İki tür komut vardır, karıştırma:\n\n"
        text += "🤖 **Bot Komutları** — **bu botun** komutlarıdır.\n"
        text += "`/` ile başlar, **bu bota** yazılır (ör. `/start`).\n\n"
        text += "⚡ **Userbot Komutları** — **hesabınızı yöneteceğiniz "
        text += "userbot'un** komutlarıdır.\n"
        text += "`.` ile başlar, **Telegram'da herhangi bir sohbete** yazılır (ör. `.afk`).\n\n"
        text += "👇 Görmek istediğin komut türünü seç:"
        rows = [
            [btn.callback(" Bot Komutları", "cmds_bot", style=ButtonBuilder.STYLE_PRIMARY,
                          icon_custom_emoji_id=5832365506916523096)],
            [btn.callback(" Userbot Komutları", "cmds_userbot", style=ButtonBuilder.STYLE_SUCCESS,
                          icon_custom_emoji_id=5830184853236097449)],
            [btn.callback(" Ana Menü", "main_menu", style=ButtonBuilder.STYLE_DANGER,
                          icon_custom_emoji_id=5832654562510511307)],
        ]
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id,
                                        text=text, reply_markup=btn.inline_keyboard(rows))
        await event.answer()

    @bot.on(events.CallbackQuery(data=b"cmds_bot"))
    async def cmds_bot_handler(event):
        """Bu botun / komutları."""
        text = "🤖 **Bot Komutları**\n\n"
        text += "_Bu botun komutları. `/` ile **bu bota** yazılır._\n\n"
        text += "**👤 Genel:**\n"
        for cmd, desc in config.COMMANDS["user"].items():
            text += f"• `{cmd}` — {desc}\n"
        if event.sender_id == config.OWNER_ID or await db.is_sudo(event.sender_id):
            text += "\n**👑 Admin:**\n"
            for cmd, desc in config.COMMANDS["admin"].items():
                text += f"• `{cmd}` — {desc}\n"
        rows = [[btn.callback(" Geri", "commands", style=ButtonBuilder.STYLE_DANGER,
                              icon_custom_emoji_id=5832646161554480591)]]
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id,
                                        text=text, reply_markup=btn.inline_keyboard(rows))
        await event.answer()

    @bot.on(events.CallbackQuery(data=b"cmds_userbot"))
    async def cmds_userbot_handler(event):
        """Userbot (.) komutları — pluginlerden derlenir."""
        text = "⚡ **Userbot Komutları**\n\n"
        text += "_Hesabınızı yöneten userbot'un komutları._\n"
        text += "_`.` ile **Telegram'da herhangi bir sohbete** yazılır._\n\n"
        try:
            plugins = await db.get_all_plugins()
        except Exception:
            plugins = []
        listed = 0
        for pl in (plugins or []):
            if pl.get("is_disabled"):
                continue
            cmds = pl.get("commands", [])
            if not cmds:
                continue
            name = pl.get("name", "?")
            cmd_text = ", ".join(f"`.{c}`" for c in cmds)
            line = f"🔌 **{name}:** {cmd_text}\n"
            if len(text) + len(line) > 3800:  # Telegram mesaj sınırı güvenliği
                text += "…ve daha fazlası. Detay: `/pinfo <plugin>`\n"
                break
            text += line
            listed += 1
        if listed == 0:
            text += "_Henüz plugin komutu yok._\n"
        text += "\n💡 Bir plugin'in detayı için: `/pinfo <isim>`"
        rows = [[btn.callback(" Geri", "commands", style=ButtonBuilder.STYLE_DANGER,
                              icon_custom_emoji_id=5832646161554480591)]]
        await bot_api.edit_message_text(chat_id=event.sender_id, message_id=event.message_id,
                                        text=text, reply_markup=btn.inline_keyboard(rows))
        await event.answer()

