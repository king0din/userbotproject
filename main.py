# ============================================
# KingTG UserBot Service - Ana Bot Dosyası
# ============================================
# Sürüm: 2.0.0
# Geliştirici: @KingOdi
# ============================================

import os
import sys
import asyncio
import time

# Proje dizinini path'e ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

import config
from database import database as db
from userbot import userbot_manager, plugin_manager
from handlers import register_user_handlers, register_admin_handlers
from utils import send_log, get_readable_time

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
# SESSION SONLANDIRMA CALLBACK
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
    
    # Handler'ları kaydet
    log("🔄 Handler'lar yükleniyor...")
    register_user_handlers(bot)
    register_admin_handlers(bot)
    log("✅ Handler'lar yüklendi")
    
    # Userbot manager callback'ini ayarla
    userbot_manager.set_session_terminated_callback(on_session_terminated)
    
    # Kaydedilmiş session'ları geri yükle
    log("🔄 Kaydedilmiş session'lar yükleniyor...")
    restored = await userbot_manager.restore_sessions()
    log(f"✅ {restored} session geri yüklendi")
    
    # Restart kontrolü
    await check_restart()
    
    # Log kanalına başlangıç mesajı
    if config.LOG_CHANNEL:
        try:
            uptime = get_readable_time(time.time() - start_time)
            stats = await db.get_stats()
            
            text = f"🤖 **Bot Başlatıldı!**\n\n"
            text += f"🔢 Sürüm: `v{config.__version__}`\n"
            text += f"👥 Kullanıcı: `{stats.get('total_users', 0)}`\n"
            text += f"🔌 Plugin: `{stats.get('total_plugins', 0)}`\n"
            text += f"✅ Aktif Userbot: `{restored}`\n"
            text += f"🔗 MongoDB: `{'Bağlı' if mongo_connected else 'Bağlı Değil'}`"
            
            await bot.send_message(config.LOG_CHANNEL, text)
        except Exception as e:
            log(f"⚠️ Log kanalına mesaj gönderilemedi: {e}")
    
    log("=" * 50)
    log("✅ Bot hazır!")
    log(f"👤 Sahip: {config.OWNER_ID}")
    log(f"📊 Kullanıcılar: {await db.get_user_count()}")
    log(f"🔌 Aktif Userbot: {len(userbot_manager.active_clients)}")
    log("=" * 50)
    
    # Bot çalışmaya devam et
    await bot.run_until_disconnected()

# ============================================
# KAPANIŞ İŞLEMLERİ
# ============================================

async def shutdown():
    """Kapanış işlemleri"""
    log("🔄 Bot kapatılıyor...")
    
    # Tüm userbot'ları kapat
    await userbot_manager.shutdown()
    
    # Bot bağlantısını kapat
    await bot.disconnect()
    
    log("👋 Bot kapatıldı")

# ============================================
# BAŞLATMA
# ============================================

if __name__ == '__main__':
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        log("⚠️ Klavye kesintisi algılandı")
        asyncio.get_event_loop().run_until_complete(shutdown())
    except Exception as e:
        log(f"❌ Kritik hata: {e}")
        import traceback
        traceback.print_exc()
