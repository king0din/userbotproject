# ============================================
# KingTG UserBot Service - Yapılandırma
# ============================================
# Sürüm: 2.0.0
# Geliştirici: @KingOdi
# ============================================

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================
# BOT SÜRÜM BİLGİSİ
# ============================================
__version__ = "2.0.0"
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
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "")

# ============================================
# MONGODB BAĞLANTISI
# ============================================
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://myuserbot:myusebot@cluster0.psgkpo1.mongodb.net/?appName=Cluster0")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "kingtg_userbot")

# ============================================
# LOG KANALI/GRUBU
# ============================================
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", 0))

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

# Klasörleri oluştur
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
    "bot_mode": "public",  # public veya private
    "maintenance": False,
    "max_users": 1000,
    "session_timeout": 86400 * 30,  # 30 gün
    "plugin_approval": False,  # Plugin onay sistemi
}

# ============================================
# MESAJLAR (Türkçe)
# ============================================
MESSAGES = {
    # Genel
    "welcome": "🤖 **KingTG UserBot Service'e Hoşgeldiniz!**\n\n"
               "Bu bot ile kendi Telegram hesabınıza userbot kurabilirsiniz.\n\n"
               "📌 **Özellikler:**\n"
               "• Kolay kurulum\n"
               "• Plugin sistemi\n"
               "• Güvenli oturum yönetimi\n\n"
               "Başlamak için aşağıdaki butonları kullanın.",
    
    "maintenance": "🔧 **Bot şu anda bakım modunda.**\n\nLütfen daha sonra tekrar deneyin.",
    
    "banned": "🚫 **Bu botu kullanmanız yasaklanmış.**\n\nİtiraz için: {owner}",
    
    "private_mode": "🔒 **Bot şu anda özel modda.**\n\nSadece yetkili kullanıcılar kullanabilir.",
    
    "not_registered": "❌ Henüz kayıtlı değilsiniz.\n\n/start komutu ile başlayın.",
    
    # Giriş
    "login_method": "🔐 **Giriş Yöntemi Seçin:**\n\n"
                    "Hangi yöntemle giriş yapmak istiyorsunuz?",
    
    "login_phone": "📱 **Telefon Numarası ile Giriş**\n\n"
                   "Lütfen telefon numaranızı uluslararası formatta girin:\n"
                   "Örnek: `+905551234567`",
    
    "login_code": "🔢 **Doğrulama Kodu**\n\n"
                  "Telegram'dan gelen kodu girin:\n"
                  "⚠️ Kodu boşluksuz yazın.",
    
    "login_2fa": "🔑 **İki Faktörlü Doğrulama**\n\n"
                 "Lütfen 2FA şifrenizi girin:",
    
    "login_session_telethon": "📄 **Telethon Session String**\n\n"
                              "Session string'inizi gönderin:",
    
    "login_session_pyrogram": "📄 **Pyrogram Session String**\n\n"
                              "Session string'inizi gönderin:",
    
    "login_success": "✅ **Giriş Başarılı!**\n\n"
                     "👤 Hesap: `{name}`\n"
                     "🆔 ID: `{user_id}`\n\n"
                     "Artık plugin'leri aktif edebilirsiniz.",
    
    "login_failed": "❌ **Giriş Başarısız!**\n\n"
                    "Hata: `{error}`\n\n"
                    "Lütfen tekrar deneyin.",
    
    "login_remember": "💾 **Oturum Kaydetme**\n\n"
                      "Oturumunuz kaydedilsin mi?\n"
                      "(Bir dahaki sefere hızlı giriş için)",
    
    # Çıkış
    "logout_confirm": "⚠️ **Çıkış Onayı**\n\n"
                      "Userbot oturumunuzu sonlandırmak istediğinize emin misiniz?\n\n"
                      "📌 Kayıtlı bilgileriniz silinsin mi?",
    
    "logout_success": "✅ **Çıkış yapıldı.**\n\n"
                      "Userbot oturumunuz sonlandırıldı.",
    
    "session_terminated": "⚠️ **Oturum Sonlandırıldı!**\n\n"
                          "Telegram ayarlarından userbot oturumunuz sonlandırılmış.\n\n"
                          "Tekrar kullanmak için yeniden giriş yapmanız gerekiyor.",
    
    # Plugin
    "plugins_list": "🔌 **Mevcut Plugin'ler:**\n\n{plugins}\n\n"
                    "📌 Aktif etmek için: `/pactive <isim>`\n"
                    "📌 Deaktif etmek için: `/pinactive <isim>`",
    
    "plugin_activated": "✅ **Plugin Aktif Edildi!**\n\n"
                        "🔌 Plugin: `{name}`\n"
                        "📝 Açıklama: {desc}",
    
    "plugin_deactivated": "❌ **Plugin Deaktif Edildi!**\n\n"
                          "🔌 Plugin: `{name}`",
    
    "plugin_not_found": "❌ `{name}` adında bir plugin bulunamadı.",
    
    "plugin_no_access": "🚫 Bu plugin'e erişim yetkiniz yok.",
    
    "plugin_already_active": "⚠️ `{name}` zaten aktif.",
    
    "plugin_already_inactive": "⚠️ `{name}` zaten deaktif.",
    
    "no_active_plugins": "📭 Aktif plugin'iniz bulunmuyor.",
    
    # Admin
    "admin_only": "🚫 Bu komut sadece bot yöneticileri içindir.",
    
    "owner_only": "🚫 Bu komut sadece bot sahibi içindir.",
    
    "user_banned": "✅ `{user}` yasaklandı.",
    
    "user_unbanned": "✅ `{user}` yasağı kaldırıldı.",
    
    "sudo_added": "✅ `{user}` sudo olarak eklendi.",
    
    "sudo_removed": "✅ `{user}` sudo listesinden çıkarıldı.",
    
    # Ayarlar
    "settings_menu": "⚙️ **Bot Ayarları**\n\n"
                     "🔹 Mod: `{mode}`\n"
                     "🔹 Bakım: `{maintenance}`\n"
                     "🔹 Kullanıcı Sayısı: `{users}`\n"
                     "🔹 Plugin Sayısı: `{plugins}`\n"
                     "🔹 Sudo Sayısı: `{sudos}`\n"
                     "🔹 Ban Sayısı: `{bans}`",
    
    # Güncelleme
    "update_checking": "🔄 Güncelleme kontrol ediliyor...",
    
    "update_available": "🆕 **Güncelleme Mevcut!**\n\n"
                        "Mevcut: `v{current}`\n"
                        "Yeni: `v{new}`\n\n"
                        "Güncellemek için butona tıklayın.",
    
    "update_latest": "✅ Bot zaten güncel!\n\nSürüm: `v{version}`",
    
    "update_success": "✅ **Güncelleme Tamamlandı!**\n\n"
                      "Yeni sürüm: `v{version}`\n\n"
                      "Bot yeniden başlatılıyor...",
    
    # Hatalar
    "error_general": "❌ Bir hata oluştu: `{error}`",
    
    "error_timeout": "⏱️ İşlem zaman aşımına uğradı. Lütfen tekrar deneyin.",
    
    "error_flood": "⚠️ Çok fazla istek gönderdiniz. Lütfen {seconds} saniye bekleyin.",
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
    "remember_no": "🗑️ Hayır, Kaydetme",
    "keep_data": "💾 Bilgileri Sakla",
    "delete_data": "🗑️ Bilgileri Sil",
    "public_mode": "🌐 Genel Mod",
    "private_mode": "🔒 Özel Mod",
    "maintenance_on": "🔧 Bakım Aç",
    "maintenance_off": "✅ Bakım Kapat",
    "user_management": "👥 Kullanıcı Yönetimi",
    "plugin_management": "🔌 Plugin Yönetimi",
    "sudo_management": "👑 Sudo Yönetimi",
    "ban_management": "🚫 Ban Yönetimi",
    "stats": "📊 İstatistikler",
    "update": "🔄 Güncelle",
    "restart": "🔃 Yeniden Başlat",
    "broadcast": "📢 Duyuru",
    "logs": "📋 Loglar",
}
