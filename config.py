# ============================================
# KingTG UserBot Service - Yapılandırma
# ============================================
# Sürüm: 2.1.0
# Geliştirici: @KingOdi
# ============================================

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================
# BOT SÜRÜM BİLGİSİ
# ============================================
__version__ = "2.1.0"
__author__ = "@KingOdi"
__repo__ = "https://github.com/KingOdi/KingTG-UserBot-Service"

# ============================================
# TELEGRAM API BİLGİLERİ
# ============================================
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ============================================
# BOT SAHİBİ BİLGİLERİ
# ============================================
OWNER_ID = int(os.getenv("OWNER_ID", 0))
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "KingOdi")

# ============================================
# KANALLAR
# ============================================
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", 0))
PLUGIN_CHANNEL = os.getenv("PLUGIN_CHANNEL", "KingTGPlugins")  # Plugin duyuru kanalı

# ============================================
# MONGODB BAĞLANTISI
# ============================================
MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "kingtg_userbot")

# ============================================
# GITHUB REPO (Güncelleme için)
# ============================================
GITHUB_REPO = os.getenv("GITHUB_REPO", "")

# ============================================
# DOSYA YOLLARI
# ============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
PLUGINS_DIR = os.path.join(BASE_DIR, "plugins")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

for directory in [DATA_DIR, SESSIONS_DIR, PLUGINS_DIR, LOGS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# ============================================
# VERİ DOSYALARI
# ============================================
USERS_FILE = os.path.join(DATA_DIR, "users.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
PLUGINS_FILE = os.path.join(DATA_DIR, "plugins.json")
BANS_FILE = os.path.join(DATA_DIR, "bans.json")
SUDOS_FILE = os.path.join(DATA_DIR, "sudos.json")

# ============================================
# VARSAYILAN AYARLAR
# ============================================
DEFAULT_SETTINGS = {
    "bot_mode": "public",
    "maintenance": False,
    "max_users": 1000,
    "session_timeout": 86400 * 30,
    "plugin_approval": False,
}

# ============================================
# MESAJLAR (Türkçe)
# ============================================
MESSAGES = {
    "welcome": "🤖 **KingTG UserBot Service'e Hoşgeldiniz!**\n\n"
               "Bu bot ile kendi Telegram hesabınıza userbot kurabilirsiniz.\n\n"
               "📌 **Özellikler:**\n"
               "• Kolay kurulum\n"
               "• Plugin sistemi\n"
               "• Güvenli oturum yönetimi",
    
    "maintenance": "🔧 **Bot şu anda bakım modunda.**\n\nLütfen daha sonra tekrar deneyin.",
    "banned": "🚫 **Bu botu kullanmanız yasaklanmış.**\n\nİtiraz için: @{owner}",
    "private_mode": "🔒 **Bot şu anda özel modda.**\n\nSadece yetkili kullanıcılar kullanabilir.",
    "not_registered": "❌ Henüz kayıtlı değilsiniz.\n\n/start komutu ile başlayın.",
    
    # Giriş
    "login_method": "🔐 **Giriş Yöntemi Seçin:**",
    "login_phone": "📱 **Telefon Numarası ile Giriş**\n\n"
                   "Telefon numaranızı girin:\n"
                   "Örnek: `+905551234567`",
    "login_code": "🔢 **Doğrulama Kodu**\n\n"
                  "Telegram'dan gelen kodu girin.\n\n"
                  "⚠️ **ÖNEMLİ:** Kodu aralarında **boşluk** bırakarak yazın!\n"
                  "Örnek: `1 2 3 4 5`\n\n"
                  "🔒 Bu sayede Telegram kod paylaşımını engellemez.",
    "login_2fa": "🔑 **İki Faktörlü Doğrulama**\n\n2FA şifrenizi girin:",
    "login_session_telethon": "📄 **Telethon Session String**\n\nSession string gönderin:",
    "login_session_pyrogram": "📄 **Pyrogram Session String**\n\nSession string gönderin:",
    "login_success": "✅ **Giriş Başarılı!**\n\n"
                     "👤 Hesap: `{name}`\n"
                     "🆔 ID: `{user_id}`",
    "login_failed": "❌ **Giriş Başarısız!**\n\nHata: `{error}`",
    "login_remember": "💾 **Oturum kaydedilsin mi?**\n(Hızlı giriş için)",
    
    # Çıkış
    "logout_confirm": "⚠️ **Çıkış Onayı**\n\nKayıtlı bilgileriniz silinsin mi?",
    "logout_success": "✅ **Çıkış yapıldı.**",
    "session_terminated": "⚠️ **Oturum Sonlandırıldı!**\n\n"
                          "Telegram ayarlarından oturumunuz kapatılmış.\n"
                          "Tekrar giriş yapmalısınız.",
    
    # Plugin
    "no_active_plugins": "📭 Aktif plugin'iniz bulunmuyor.",
    
    # Admin
    "admin_only": "🚫 Bu işlem sadece yöneticiler içindir.",
    "owner_only": "🚫 Bu işlem sadece bot sahibi içindir.",
    
    # Hatalar
    "error_flood": "⚠️ Lütfen {seconds} saniye bekleyin.",
}

# ============================================
# BUTON METİNLERİ
# ============================================
BUTTONS = {
    "login": "🔐 Giriş Yap",
    "logout": "🚪 Çıkış Yap",
    "plugins": "🔌 Plugin'ler",
    "my_plugins": "📦 Plugin'lerim",
    "settings": "⚙️ Ayarlar",
    "help": "❓ Yardım",
    "back": "🔙 Geri",
    "close": "❌ Kapat",
    "confirm": "✅ Onayla",
    "cancel": "❌ İptal",
    "yes": "✅ Evet",
    "no": "❌ Hayır",
    "phone": "📱 Telefon Numarası",
    "telethon_session": "📄 Telethon Session",
    "pyrogram_session": "📄 Pyrogram Session",
    "remember_yes": "💾 Evet, Kaydet",
    "remember_no": "🗑️ Hayır",
    "keep_data": "💾 Bilgileri Sakla",
    "delete_data": "🗑️ Bilgileri Sil",
    "public_mode": "🌐 Genel Mod",
    "private_mode": "🔒 Özel Mod",
    "maintenance_on": "🔧 Bakım Aç",
    "maintenance_off": "✅ Bakım Kapat",
    "user_management": "👥 Kullanıcılar",
    "plugin_management": "🔌 Plugin'ler",
    "sudo_management": "👑 Sudo",
    "ban_management": "🚫 Ban",
    "stats": "📊 İstatistik",
    "update": "🔄 Güncelle",
    "restart": "🔃 Yeniden Başlat",
    "broadcast": "📢 Duyuru",
    "logs": "📋 Loglar",
    "commands": "📝 Komutlar",
    "plugin_channel": "📢 Plugin Kanalı",
}

# ============================================
# KOMUT AÇIKLAMALARI
# ============================================
COMMANDS = {
    # Kullanıcı komutları
    "user": {
        "/start": "Ana menüyü açar",
        "/plugins": "Plugin listesini gösterir",
        "/pactive <isim>": "Plugin aktif eder",
        "/pinactive <isim>": "Plugin deaktif eder",
        "/pinfo <isim>": "Plugin detaylarını gösterir",
        "/cancel": "İşlemi iptal eder",
    },
    # Admin komutları
    "admin": {
        "/addplugin": "Plugin ekler (dosyaya yanıt)",
        "/delplugin <isim>": "Plugin siler",
        "/getplugin <isim>": "Plugin dosyasını indirir",
        "/setpublic <isim>": "Plugini genel yapar",
        "/setprivate <isim>": "Plugini özel yapar",
        "/ban <id> [sebep]": "Kullanıcı banlar",
        "/unban <id>": "Ban kaldırır",
        "/addsudo <id>": "Sudo ekler",
        "/delsudo <id>": "Sudo kaldırır",
        "/broadcast": "Duyuru gönderir (mesaja yanıt)",
        "/stats": "İstatistikleri gösterir",
    }
}
