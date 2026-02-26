# ============================================
# KingTG UserBot Service - Ana Bot Dosyası
# ============================================
# Sürüm: 2.1.0
# Geliştirici: @KingOdi
# Smart Session Manager ile optimize edilmiş
# ============================================

import os
import sys
import asyncio
import time

# Proje dizinini path'e ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telethon import TelegramClient, events
from dotenv import load_dotenv

load_dotenv()

import config
from database import database as db

# Smart Session Manager
from userbot.smart_manager import smart_session_manager
from userbot.plugins import plugin_manager

# Eski uyumluluk için alias
userbot_manager = smart_session_manager

from handlers import register_user_handlers, register_admin_handlers
from utils import send_log, get_readable_time
from utils.bot_api import bot_api

# ============================================
# GLOBAL DEĞİŞKENLER
# ============================================

bot = TelegramClient('bot_session', config.API_ID, config.API_HASH)
start_time = time.time()

RESTART_FILE = ".restart_info"

# ============================================
# LOG FONKSİYONU
# ============================================

def log(text):
    """Konsola log yaz"""
    print(f"\033[94m[KingTG]\033[0m {text}")

# ============================================
# CALLBACK'LER
# ============================================

async def on_session_terminated(user_id: int):
    """Kullanıcının session'ı sonlandırıldığında çağrılır"""
    try:
        await bot.send_message(
            user_id,
            config.MESSAGES["session_terminated"]
        )
        await send_log(
            bot, "warning",
            f"Session sonlandırıldı (Telegram ayarlarından)",
            user_id
        )
    except Exception as e:
        log(f"⚠️ Session sonlandırma bildirimi gönderilemedi: {e}")

async def send_message_callback(user_id: int, text: str, buttons: dict = None):
    """Bot üzerinden kullanıcıya mesaj gönder (onay sistemi için)"""
    try:
        await bot_api.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=buttons
        )
    except Exception as e:
        log(f"⚠️ Mesaj gönderilemedi: user={user_id} - {e}")

# ============================================
# ALWAYS-ON ONAY HANDLER'LARI
# ============================================

def register_always_on_handlers(bot):
    """Always-on onay callback'lerini kaydet"""
    
    @bot.on(events.CallbackQuery(pattern=rb"always_confirm_(\d+)"))
    async def always_on_confirm(event):
        """Always-on onaylandı"""
        user_id = int(event.pattern_match.group(1).decode())
        
        # Sadece ilgili kullanıcı onaylayabilir
        if event.sender_id != user_id:
            await event.answer("❌ Bu buton sana ait değil!", alert=True)
            return
        
        # Onayı işle
        await smart_session_manager.handle_confirmation(user_id, confirmed=True)
        
        # Mesajı güncelle
        await event.edit(
            "✅ **Sürekli Dinleme Onaylandı**\n\n"
            "Plugin'leriniz 3 gün daha aktif kalacak.\n"
            "Sonraki onay: 3 gün sonra"
        )
        
        await event.answer("✅ Onaylandı!")
    
    @bot.on(events.CallbackQuery(pattern=rb"always_stop_(\d+)"))
    async def always_on_stop(event):
        """Always-on durduruldu"""
        user_id = int(event.pattern_match.group(1).decode())
        
        if event.sender_id != user_id:
            await event.answer("❌ Bu buton sana ait değil!", alert=True)
            return
        
        # Onayı reddet
        await smart_session_manager.handle_confirmation(user_id, confirmed=False)
        
        # Mesajı güncelle
        await event.edit(
            "⏸️ **Sürekli Dinleme Durduruldu**\n\n"
            "Plugin'leriniz deaktif edildi.\n"
            "Tekrar aktif etmek için plugin'i yeniden başlatın."
        )
        
        await event.answer("⏸️ Durduruldu!")

# ============================================
# RESTART KONTROLÜ
# ============================================

async def check_restart():
    """Restart sonrası mesaj gönder"""
    if os.path.exists(RESTART_FILE):
        try:
            with open(RESTART_FILE, "r") as f:
                data = f.read().strip()
            os.remove(RESTART_FILE)
            
            if "|" in data:
                chat_id, msg_id = data.split("|")
                
                uptime = get_readable_time(time.time() - start_time)
                text = f"✅ **Bot başarıyla yeniden başlatıldı!**\n\n"
                text += f"🔢 Sürüm: `v{config.__version__}`\n"
                text += f"⏱️ Uptime: `{uptime}`"
                
                await bot.edit_message(int(chat_id), int(msg_id), text)
                log("✅ Restart mesajı güncellendi")
        except Exception as e:
            log(f"⚠️ Restart mesajı güncellenemedi: {e}")

# ============================================
# ANA FONKSİYON
# ============================================

async def main():
    """Ana başlatma fonksiyonu"""
    
    log("=" * 50)
    log(f"🤖 KingTG UserBot Service v{config.__version__}")
    log(f"👨‍💻 Geliştirici: {config.__author__}")
    log("🚀 Smart Session Manager aktif")
    log("=" * 50)
    
    # Konfigürasyon kontrolü
    if not config.API_ID or not config.API_HASH or not config.BOT_TOKEN:
        log("❌ API_ID, API_HASH veya BOT_TOKEN eksik!")
        log("📄 .env.example dosyasını .env olarak kopyalayıp doldurun.")
        return
    
    if not config.OWNER_ID:
        log("❌ OWNER_ID belirtilmemiş!")
        return
    
    # Veritabanı bağlantısı
    log("🔄 Veritabanına bağlanılıyor...")
    mongo_connected = await db.connect()
    
    if mongo_connected:
        log("✅ MongoDB bağlantısı başarılı")
    else:
        log("⚠️ MongoDB bağlantısı başarısız, yerel dosya sistemi kullanılacak")
    
    # Bot başlatma
    log("🔄 Bot başlatılıyor...")
    await bot.start(bot_token=config.BOT_TOKEN)
    
    bot_me = await bot.get_me()
    log(f"✅ Bot bağlandı: @{bot_me.username}")
    
    # Bot username'ini config'e kaydet (pluginler için)
    config.BOT_USERNAME = bot_me.username
    
    # Handler'ları kaydet
    log("🔄 Handler'lar yükleniyor...")
    register_user_handlers(bot)
    register_admin_handlers(bot)
    register_always_on_handlers(bot)
    log("✅ Handler'lar yüklendi")
    
    # Smart Session Manager callback'lerini ayarla
    smart_session_manager.set_session_terminated_callback(on_session_terminated)
    smart_session_manager.set_send_message_callback(send_message_callback)
    
    # Plugin bağımlılıklarını önceden kur
    log("🔄 Plugin bağımlılıkları kontrol ediliyor...")
    await plugin_manager.preinstall_all_dependencies()
    
    # Session'ları geri yükle
    log("🔄 Session'lar geri yükleniyor...")
    restored = await smart_session_manager.restore_sessions()
    
    # İstatistikleri göster
    stats = smart_session_manager.get_stats()
    log(f"✅ {restored} kullanıcı aktif (plugin'li)")
    log(f"📦 {stats['session_cache']} session cache'de")
    log(f"🟢 {stats['always_on_users']} always-on")
    
    # Arka plan görevlerini başlat
    log("🔄 Arka plan görevleri başlatılıyor...")
    await smart_session_manager.start_background_tasks()
    log("✅ Arka plan görevleri aktif:")
    log("   • İnaktif client temizleme (her 1 dk)")
    log("   • Always-on onay kontrolü (her 1 saat)")
    log("   • Kullanıcı senkronizasyonu (her 24 saat)")
    
    # Restart kontrolü
    await check_restart()
    
    # Log kanalına başlangıç mesajı
    if config.LOG_CHANNEL:
        try:
            uptime = get_readable_time(time.time() - start_time)
            db_stats = await db.get_stats()
            
            text = f"🤖 **Bot Başlatıldı!**\n\n"
            text += f"🔢 Sürüm: `v{config.__version__}`\n"
            text += f"👥 Kullanıcı: `{db_stats.get('total_users', 0)}`\n"
            text += f"🔌 Plugin: `{db_stats.get('total_plugins', 0)}`\n"
            text += f"🟢 Always-On: `{stats['always_on_users']}`\n"
            text += f"📦 On-Demand Hazır: `{stats['session_cache']}`\n"
            text += f"🔗 MongoDB: `{'Bağlı' if mongo_connected else 'Bağlı Değil'}`"
            
            await bot.send_message(config.LOG_CHANNEL, text)
        except Exception as e:
            log(f"⚠️ Log kanalına mesaj gönderilemedi: {e}")
    
    log("=" * 50)
    log("✅ Bot hazır!")
    log(f"👤 Sahip: {config.OWNER_ID}")
    log(f"📊 Kullanıcılar: {await db.get_user_count()}")
    log(f"🟢 Always-On: {stats['always_on_users']}")
    log(f"📦 On-Demand: {stats['session_cache']}")
    log("=" * 50)
    
    # Bot çalışmaya devam et
    await bot.run_until_disconnected()

# ============================================
# KAPANIŞ İŞLEMLERİ
# ============================================

async def shutdown():
    """Kapanış işlemleri"""
    log("🔄 Bot kapatılıyor...")
    
    # Smart Session Manager'ı kapat
    await smart_session_manager.shutdown()
    
    # Bot bağlantısını kapat
    await bot.disconnect()
    
    log("👋 Bot kapatıldı")

# ============================================
# BAŞLATMA
# ============================================

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("⚠️ Klavye kesintisi algılandı")
    except Exception as e:
        log(f"❌ Kritik hata: {e}")
        import traceback
        traceback.print_exc()
