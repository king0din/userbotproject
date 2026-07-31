# ============================================
# KingTG UserBot Service - Smart Session Manager
# ============================================
# On-Demand + Always-On Hibrit Sistem
# Düşük kaynak kullanımı için optimize edilmiş
# ============================================

import asyncio
import time
from typing import Optional, Dict, Callable, Set, List
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError, 
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PasswordHashInvalidError,
    AuthKeyUnregisteredError,
    UserDeactivatedBanError,
    UserDeactivatedError,
    FloodWaitError
)
import config
from database import database as db

# ============================================
# PLUGIN KATEGORİLERİ
# ============================================

# Sürekli dinleme gerektiren plugin'ler
ALWAYS_ON_PLUGINS = {
    'filter',       # Gelen mesaj filtreleri
    'autoreply',    # Otomatik yanıt
    'antispam',     # Spam koruması
    'welcome',      # Hoşgeldin mesajı
    'goodbye',      # Güle güle mesajı
}

# On-demand plugin'ler (komutla çalışır, sürekli dinleme gerektirmez)
ON_DEMAND_PLUGINS = {
    'afk', 'burc', 'clon', 'q', 'ses', 'tag',
    'example', 'translate', 'download', 'upload',
    'sticker', 'gif', 'info', 'admin', 'tools'
}


class SmartSessionManager:
    """
    Akıllı Session Yöneticisi
    
    - On-Demand: Komut gelince aktif, 5dk inaktifse kapat
    - Always-On: Sürekli aktif (filter vb.), 3 günde bir onay iste
    """
    
    def __init__(self):
        # Aktif client'lar
        self.active_clients: Dict[int, TelegramClient] = {}
        
        # Session verileri (DB'den cache)
        self.session_cache: Dict[int, Dict] = {}
        
        # Pending login işlemleri
        self.pending_logins: Dict[int, Dict] = {}
        
        # Kullanıcı kilitleri (race condition önleme)
        self.user_locks: Dict[int, asyncio.Lock] = {}
        
        # Son aktivite zamanları (on-demand için)
        self.last_activity: Dict[int, float] = {}
        
        # Always-on kullanıcıları
        self.always_on_users: Dict[int, Dict] = {}
        # Yapı: {user_id: {'plugins': ['filter'], 'enabled_at': timestamp}}
        
        # Son onay zamanları
        self.last_confirm: Dict[int, float] = {}
        
        # Bekleyen onaylar
        self.pending_confirms: Dict[int, float] = {}
        
        # Session izleyicileri
        self.session_monitors: Dict[int, asyncio.Task] = {}
        
        # Callback'ler
        self.on_session_terminated_callback = None
        self.on_send_message_callback = None  # Bot üzerinden mesaj göndermek için
        
        # Plugin manager (lazy load)
        self._plugin_manager = None
        
        # Ayarlar
        self.ON_DEMAND_TIMEOUT = 5 * 60          # 5 dakika (saniye)
        self.ALWAYS_ON_CONFIRM_INTERVAL = 3 * 24 * 60 * 60  # 3 gün (saniye)
        self.CONFIRM_WAIT_TIME = 24 * 60 * 60   # 24 saat onay bekleme
        self.CLEANUP_INTERVAL = 60              # Her dakika cleanup kontrolü
        
        # Arka plan görevleri
        self._cleanup_task = None
        self._confirm_task = None
        self._sync_task = None
    
    @property
    def plugin_manager(self):
        """Plugin manager'ı lazy load et"""
        if self._plugin_manager is None:
            from userbot.plugins import plugin_manager
            self._plugin_manager = plugin_manager
        return self._plugin_manager
    
    # ============================================
    # KİLİT YÖNETİMİ
    # ============================================
    
    def get_lock(self, user_id: int) -> asyncio.Lock:
        """Kullanıcı için kilit al veya oluştur"""
        if user_id not in self.user_locks:
            self.user_locks[user_id] = asyncio.Lock()
        return self.user_locks[user_id]
    
    # ============================================
    # CLIENT YÖNETİMİ
    # ============================================
    
    async def get_or_create_client(self, user_id: int, keep_alive: bool = False) -> Optional[TelegramClient]:
        """
        Client'ı getir veya oluştur (thread-safe)
        
        Args:
            user_id: Kullanıcı ID
            keep_alive: True ise always-on moda al
        """
        lock = self.get_lock(user_id)
        
        async with lock:
            # Zaten aktif mi?
            if user_id in self.active_clients:
                client = self.active_clients[user_id]
                
                # Bağlantı hala geçerli mi?
                try:
                    if client.is_connected():
                        self.last_activity[user_id] = time.time()
                        return client
                except:
                    pass
                
                # Geçersiz, temizle
                await self._disconnect_client(user_id)
            
            # Session verisi var mı?
            session_data = await self._get_session_data(user_id)
            if not session_data:
                print(f"[SMART] Session verisi yok: user={user_id}")
                return None
            
            # Yeni client oluştur
            client = await self._create_client(user_id, session_data)
            
            if client:
                self.active_clients[user_id] = client
                self.last_activity[user_id] = time.time()
                
                if keep_alive:
                    # Always-on moduna al
                    self.always_on_users[user_id] = {
                        'plugins': [],
                        'enabled_at': time.time()
                    }
                    self.last_confirm[user_id] = time.time()
                
                # Session monitor başlat
                self._start_session_monitor(user_id)
                
                print(f"[SMART] Client oluşturuldu: user={user_id}, keep_alive={keep_alive}")
            
            return client
    
    async def _get_session_data(self, user_id: int) -> Optional[Dict]:
        """Session verisini cache'den veya DB'den al"""
        # Cache'de var mı?
        if user_id in self.session_cache:
            return self.session_cache[user_id]
        
        # DB'den al
        user = await db.get_user(user_id)
        if not user:
            return None
        
        session_data = user.get("session_data")
        if not session_data:
            session_info = await db.get_session(user_id)
            if session_info:
                session_data = session_info.get("data")
        
        if session_data:
            self.session_cache[user_id] = {
                'data': session_data,
                'type': user.get("session_type", "telethon")
            }
            return self.session_cache[user_id]
        
        return None
    
    async def _create_client(self, user_id: int, session_info: Dict) -> Optional[TelegramClient]:
        """Session verisinden client oluştur"""
        try:
            session_data = session_info.get('data')
            
            client = TelegramClient(
                StringSession(session_data),
                config.API_ID,
                config.API_HASH
            )
            
            await client.connect()
            
            if not await client.is_user_authorized():
                print(f"[SMART] Kullanıcı yetkili değil: user={user_id}")
                await client.disconnect()
                return None
            
            return client
            
        except (AuthKeyUnregisteredError, UserDeactivatedBanError, UserDeactivatedError) as e:
            print(f"[SMART] Session geçersiz: user={user_id} - {e}")
            await self._handle_invalid_session(user_id)
            return None
        except Exception as e:
            print(f"[SMART] Client oluşturma hatası: user={user_id} - {e}")
            return None
    
    async def _disconnect_client(self, user_id: int):
        """Client'ı güvenli şekilde kapat"""
        if user_id in self.active_clients:
            try:
                await self.active_clients[user_id].disconnect()
            except:
                pass
            del self.active_clients[user_id]
        
        if user_id in self.last_activity:
            del self.last_activity[user_id]
        
        self._stop_session_monitor(user_id)
        
        print(f"[SMART] Client kapatıldı: user={user_id}")
    
    async def _handle_invalid_session(self, user_id: int):
        """Geçersiz session'ı işle"""
        # Cache'den sil
        if user_id in self.session_cache:
            del self.session_cache[user_id]
        
        # Always-on'dan sil
        if user_id in self.always_on_users:
            del self.always_on_users[user_id]
        
        # DB güncelle
        await db.update_user(user_id, {"is_logged_in": False})
        
        # Callback çağır
        if self.on_session_terminated_callback:
            try:
                await self.on_session_terminated_callback(user_id)
            except:
                pass
    
    # ============================================
    # ALWAYS-ON YÖNETİMİ
    # ============================================
    
    async def enable_always_on(self, user_id: int, plugin_name: str) -> bool:
        """Sürekli dinleme modunu aktif et"""
        if plugin_name.lower() not in ALWAYS_ON_PLUGINS:
            return False
        
        # Client'ı always-on modda al
        client = await self.get_or_create_client(user_id, keep_alive=True)
        if not client:
            return False
        
        # Plugin listesine ekle
        if user_id not in self.always_on_users:
            self.always_on_users[user_id] = {
                'plugins': [],
                'enabled_at': time.time()
            }
        
        if plugin_name not in self.always_on_users[user_id]['plugins']:
            self.always_on_users[user_id]['plugins'].append(plugin_name)
        
        self.last_confirm[user_id] = time.time()
        
        # DB'ye kaydet
        await db.update_user(user_id, {
            "always_on_plugins": self.always_on_users[user_id]['plugins']
        })
        
        print(f"[SMART] Always-on aktif: user={user_id}, plugin={plugin_name}")
        return True
    
    async def disable_always_on(self, user_id: int, plugin_name: str = None):
        """Sürekli dinleme modunu kapat"""
        if user_id not in self.always_on_users:
            return
        
        if plugin_name:
            # Sadece belirtilen plugin'i kaldır
            plugins = self.always_on_users[user_id]['plugins']
            if plugin_name in plugins:
                plugins.remove(plugin_name)
            
            # Başka always-on plugin yoksa
            if not plugins:
                del self.always_on_users[user_id]
                if user_id in self.last_confirm:
                    del self.last_confirm[user_id]
        else:
            # Tüm always-on'u kapat
            del self.always_on_users[user_id]
            if user_id in self.last_confirm:
                del self.last_confirm[user_id]
        
        # DB güncelle
        plugins = self.always_on_users.get(user_id, {}).get('plugins', [])
        await db.update_user(user_id, {"always_on_plugins": plugins})
        
        print(f"[SMART] Always-on deaktif: user={user_id}, plugin={plugin_name}")
    
    def is_always_on(self, user_id: int) -> bool:
        """Kullanıcı always-on modda mı?"""
        return user_id in self.always_on_users
    
    # ============================================
    # ON-DEMAND YÖNETİMİ
    # ============================================
    
    async def touch_activity(self, user_id: int):
        """Aktivite zamanını güncelle"""
        self.last_activity[user_id] = time.time()
    
    async def has_active_plugins(self, user_id: int) -> bool:
        """Kullanıcının aktif plugin'i var mı kontrol et"""
        user = await db.get_user(user_id)
        if user:
            active_plugins = user.get("active_plugins", [])
            return len(active_plugins) > 0
        return False
    
    async def cleanup_inactive_clients(self):
        """İnaktif on-demand client'ları kapat (plugin'i olmayanları)"""
        now = time.time()
        to_close = []
        
        for user_id, last_time in list(self.last_activity.items()):
            # Always-on kullanıcıları atlat
            if user_id in self.always_on_users:
                continue
            
            # Aktif plugin'i olan kullanıcıları atlat
            if await self.has_active_plugins(user_id):
                continue
            
            # Timeout kontrolü (sadece plugin'i olmayan ve inaktif olanlar)
            if now - last_time > self.ON_DEMAND_TIMEOUT:
                to_close.append(user_id)
        
        for user_id in to_close:
            print(f"[SMART] İnaktif client kapatılıyor: user={user_id}")
            await self._disconnect_client(user_id)
    
    # ============================================
    # ONAY SİSTEMİ (3 günlük)
    # ============================================
    
    async def check_confirmations(self):
        """Always-on kullanıcılarının onay durumunu kontrol et"""
        now = time.time()
        
        for user_id in list(self.always_on_users.keys()):
            # Zaten bekleyen onay var mı?
            if user_id in self.pending_confirms:
                # 24 saat geçti mi?
                if now - self.pending_confirms[user_id] > self.CONFIRM_WAIT_TIME:
                    # Onay gelmedi, kapat
                    await self._handle_no_confirmation(user_id)
                continue
            
            # Son onaydan 3 gün geçti mi?
            last = self.last_confirm.get(user_id, 0)
            if now - last > self.ALWAYS_ON_CONFIRM_INTERVAL:
                # Onay iste
                await self._request_confirmation(user_id)
    
    async def _request_confirmation(self, user_id: int):
        """Kullanıcıdan onay iste"""
        plugins = self.always_on_users.get(user_id, {}).get('plugins', [])
        
        if not plugins:
            return
        
        self.pending_confirms[user_id] = time.time()
        
        # Bot üzerinden mesaj gönder
        if self.on_send_message_callback:
            text = (
                "🔔 <b>Sürekli Dinleme Onayı</b>\n\n"
                f"Aktif plugin'leriniz: <code>{', '.join(plugins)}</code>\n\n"
                "Bu plugin'ler arka planda çalışmaya devam etsin mi?\n\n"
                "⚠️ 24 saat içinde onay vermezseniz otomatik durdurulacak."
            )
            
            buttons = {
                "inline_keyboard": [
                    [{"text": "✅ Evet, devam etsin", "callback_data": f"always_confirm_{user_id}"}],
                    [{"text": "❌ Hayır, durdur", "callback_data": f"always_stop_{user_id}"}]
                ]
            }
            
            try:
                await self.on_send_message_callback(user_id, text, buttons)
                print(f"[SMART] Onay isteği gönderildi: user={user_id}")
            except Exception as e:
                print(f"[SMART] Onay mesajı gönderilemedi: user={user_id} - {e}")
    
    async def handle_confirmation(self, user_id: int, confirmed: bool):
        """Onay yanıtını işle"""
        if user_id in self.pending_confirms:
            del self.pending_confirms[user_id]
        
        if confirmed:
            # Onaylandı, 3 gün daha
            self.last_confirm[user_id] = time.time()
            print(f"[SMART] Always-on onaylandı: user={user_id}")
        else:
            # Reddedildi, kapat
            await self._handle_no_confirmation(user_id)
    
    async def _handle_no_confirmation(self, user_id: int):
        """Onay gelmezse always-on'u kapat"""
        if user_id in self.pending_confirms:
            del self.pending_confirms[user_id]
        
        plugins = self.always_on_users.get(user_id, {}).get('plugins', [])
        
        # Plugin'leri deaktif et
        client = self.active_clients.get(user_id)
        if client and plugins:
            for plugin_name in plugins:
                await self.plugin_manager.deactivate_plugin(user_id, plugin_name)
        
        # Always-on'dan çıkar
        await self.disable_always_on(user_id)
        
        # Client'ı kapat (on-demand'a geç)
        await self._disconnect_client(user_id)
        
        # Kullanıcıyı bilgilendir
        if self.on_send_message_callback:
            text = (
                "⏸️ <b>Sürekli Dinleme Durduruldu</b>\n\n"
                f"Plugin'ler: <code>{', '.join(plugins)}</code>\n\n"
                "24 saat içinde onay vermediğiniz için durduruldu.\n"
                "Tekrar aktif etmek için plugin'i yeniden başlatın."
            )
            try:
                await self.on_send_message_callback(user_id, text, None)
            except:
                pass
        
        print(f"[SMART] Always-on durduruldu (onay yok): user={user_id}")
    
    # ============================================
    # KULLANICI SENKRONİZASYONU
    # ============================================
    
    async def sync_user_info(self, user_id: int) -> Optional[Dict]:
        """Kullanıcı bilgilerini Telegram'dan senkronize et"""
        client = await self.get_or_create_client(user_id)
        if not client:
            return None
        
        try:
            me = await client.get_me()
            
            user_info = {
                "telegram_id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "phone": me.phone,
                "is_premium": getattr(me, 'premium', False),
                "last_sync": time.time()
            }
            
            # DB güncelle
            await db.update_user(user_id, user_info)
            
            return user_info
            
        except (UserDeactivatedError, UserDeactivatedBanError):
            # Hesap silinmiş/banlanmış
            await self._handle_deleted_account(user_id)
            return None
        except Exception as e:
            print(f"[SMART] Sync hatası: user={user_id} - {e}")
            return None
    
    async def _handle_deleted_account(self, user_id: int):
        """Silinen hesabı işle"""
        print(f"[SMART] Hesap silindi/banlandı: user={user_id}")
        
        # Client'ı kapat
        await self._disconnect_client(user_id)
        
        # Cache temizle
        if user_id in self.session_cache:
            del self.session_cache[user_id]
        
        # Always-on temizle
        if user_id in self.always_on_users:
            del self.always_on_users[user_id]
        
        # DB'den kullanıcıyı işaretle veya sil
        await db.update_user(user_id, {
            "is_logged_in": False,
            "is_deleted": True,
            "deleted_at": time.time()
        })
    
    async def sync_all_users(self) -> Dict:
        """Tüm kullanıcıları senkronize et"""
        print("[SMART] Tüm kullanıcılar senkronize ediliyor...")
        
        users = await db.get_all_users()
        
        results = {
            "total": len(users),
            "synced": 0,
            "deleted": 0,
            "errors": 0
        }
        
        for user in users:
            user_id = user.get("user_id")
            
            # Zaten silinmiş olarak işaretli mi?
            if user.get("is_deleted"):
                continue
            
            # Giriş yapmamış kullanıcıları atla
            if not user.get("is_logged_in"):
                continue
            
            try:
                info = await self.sync_user_info(user_id)
                if info:
                    results["synced"] += 1
                else:
                    results["deleted"] += 1
            except:
                results["errors"] += 1
            
            # Rate limiting
            await asyncio.sleep(0.5)
        
        print(f"[SMART] Sync tamamlandı: {results}")
        return results
    
    async def cleanup_deleted_users(self) -> int:
        """Silinen hesapları DB'den temizle"""
        deleted_users = await db.get_deleted_users()
        
        count = 0
        for user in deleted_users:
            user_id = user.get("user_id")
            deleted_at = user.get("deleted_at", 0)
            
            # 7 günden eski silinen hesapları tamamen sil
            if time.time() - deleted_at > 7 * 24 * 60 * 60:
                await db.delete_user(user_id)
                count += 1
        
        if count > 0:
            print(f"[SMART] {count} silinen hesap temizlendi")
        
        return count
    
    # ============================================
    # SESSION İZLEYİCİ
    # ============================================
    
    def _start_session_monitor(self, user_id: int):
        """Session izleyiciyi başlat"""
        if user_id in self.session_monitors:
            self.session_monitors[user_id].cancel()
        
        async def monitor():
            while user_id in self.active_clients:
                await asyncio.sleep(300)  # 5 dakikada bir kontrol
                
                client = self.active_clients.get(user_id)
                if not client:
                    break
                
                try:
                    await client.get_me()
                except:
                    await self._handle_invalid_session(user_id)
                    break
        
        self.session_monitors[user_id] = asyncio.create_task(monitor())
    
    def _stop_session_monitor(self, user_id: int):
        """Session izleyiciyi durdur"""
        if user_id in self.session_monitors:
            self.session_monitors[user_id].cancel()
            del self.session_monitors[user_id]
    
    # ============================================
    # ARKA PLAN GÖREVLERİ
    # ============================================
    
    async def start_background_tasks(self):
        """Arka plan görevlerini başlat"""
        
        async def cleanup_loop():
            """İnaktif client temizleme döngüsü"""
            while True:
                await asyncio.sleep(self.CLEANUP_INTERVAL)
                try:
                    await self.cleanup_inactive_clients()
                except Exception as e:
                    print(f"[SMART] Cleanup hatası: {e}")
        
        async def confirm_loop():
            """Onay kontrolü döngüsü"""
            while True:
                await asyncio.sleep(60 * 60)  # Her saat
                try:
                    await self.check_confirmations()
                except Exception as e:
                    print(f"[SMART] Confirm hatası: {e}")
        
        async def sync_loop():
            """Kullanıcı senkronizasyon döngüsü"""
            while True:
                await asyncio.sleep(24 * 60 * 60)  # Her 24 saat
                try:
                    await self.sync_all_users()
                    await self.cleanup_deleted_users()
                except Exception as e:
                    print(f"[SMART] Sync hatası: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        self._confirm_task = asyncio.create_task(confirm_loop())
        self._sync_task = asyncio.create_task(sync_loop())
        
        print("[SMART] Arka plan görevleri başlatıldı")
    
    def stop_background_tasks(self):
        """Arka plan görevlerini durdur"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._confirm_task:
            self._confirm_task.cancel()
        if self._sync_task:
            self._sync_task.cancel()
    
    # ============================================
    # GİRİŞ İŞLEMLERİ (Mevcut uyumluluk)
    # ============================================
    
    async def start_phone_login(self, user_id: int, phone: str) -> Dict:
        """Telefon ile giriş başlat"""
        try:
            client = TelegramClient(
                StringSession(),
                config.API_ID,
                config.API_HASH
            )
            await client.connect()
            
            result = await client.send_code_request(phone)
            
            self.pending_logins[user_id] = {
                "client": client,
                "phone": phone,
                "phone_code_hash": result.phone_code_hash,
                "stage": "code"
            }
            
            return {"success": True, "stage": "code"}
            
        except FloodWaitError as e:
            return {"success": False, "error": "flood_wait", "seconds": e.seconds}
        except Exception as e:
            print(f"[SMART] Telefon giriş hatası: {e}")
            return {"success": False, "error": str(e)}
    
    async def verify_code(self, user_id: int, code: str) -> Dict:
        """Doğrulama kodunu kontrol et"""
        if user_id not in self.pending_logins:
            return {"success": False, "error": "no_pending_login"}
        
        login_data = self.pending_logins[user_id]
        client = login_data["client"]
        phone = login_data["phone"]
        phone_code_hash = login_data["phone_code_hash"]
        
        try:
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            
            me = await client.get_me()
            session_string = client.session.save()
            
            self.active_clients[user_id] = client
            self.last_activity[user_id] = time.time()
            del self.pending_logins[user_id]
            
            # Cache'e ekle
            self.session_cache[user_id] = {
                'data': session_string,
                'type': 'telethon'
            }
            
            self._start_session_monitor(user_id)
            
            return {
                "success": True,
                "session_string": session_string,
                "user_info": {
                    "id": me.id,
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "username": me.username,
                    "phone": me.phone
                }
            }
            
        except SessionPasswordNeededError:
            self.pending_logins[user_id]["stage"] = "2fa"
            return {"success": True, "stage": "2fa"}
            
        except PhoneCodeInvalidError:
            return {"success": False, "error": "invalid_code"}
            
        except PhoneCodeExpiredError:
            del self.pending_logins[user_id]
            return {"success": False, "error": "code_expired"}
            
        except Exception as e:
            print(f"[SMART] Kod doğrulama hatası: {e}")
            return {"success": False, "error": str(e)}
    
    async def verify_2fa(self, user_id: int, password: str) -> Dict:
        """2FA şifresini kontrol et"""
        if user_id not in self.pending_logins:
            return {"success": False, "error": "no_pending_login"}
        
        login_data = self.pending_logins[user_id]
        client = login_data["client"]
        
        try:
            await client.sign_in(password=password)
            
            me = await client.get_me()
            session_string = client.session.save()
            
            self.active_clients[user_id] = client
            self.last_activity[user_id] = time.time()
            del self.pending_logins[user_id]
            
            # Cache'e ekle
            self.session_cache[user_id] = {
                'data': session_string,
                'type': 'telethon'
            }
            
            self._start_session_monitor(user_id)
            
            return {
                "success": True,
                "session_string": session_string,
                "user_info": {
                    "id": me.id,
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "username": me.username,
                    "phone": me.phone
                }
            }
            
        except PasswordHashInvalidError:
            return {"success": False, "error": "invalid_password"}
            
        except Exception as e:
            print(f"[SMART] 2FA hatası: {e}")
            return {"success": False, "error": str(e)}
    
    async def login_with_session(self, user_id: int, session_string: str, 
                                 session_type: str = "telethon") -> Dict:
        """Session string ile giriş"""
        # Cache'e ekle
        self.session_cache[user_id] = {
            'data': session_string,
            'type': session_type
        }
        
        # Client oluştur
        client = await self.get_or_create_client(user_id)
        
        if client:
            try:
                me = await client.get_me()
                return {
                    "success": True,
                    "session_string": session_string,
                    "user_info": {
                        "id": me.id,
                        "first_name": me.first_name,
                        "last_name": me.last_name,
                        "username": me.username,
                        "phone": me.phone
                    }
                }
            except:
                pass
        
        # Cache'den sil
        if user_id in self.session_cache:
            del self.session_cache[user_id]
        
        return {"success": False, "error": "invalid_session"}
    
    async def logout(self, user_id: int, terminate_session: bool = False) -> bool:
        """Çıkış yap"""
        try:
            if user_id in self.active_clients:
                client = self.active_clients[user_id]
                
                if terminate_session:
                    try:
                        await client.log_out()
                    except:
                        pass
                
                await self._disconnect_client(user_id)
            
            # Always-on'dan çıkar
            if user_id in self.always_on_users:
                del self.always_on_users[user_id]
            
            # Cache temizle
            if user_id in self.session_cache:
                del self.session_cache[user_id]
            
            # Pending login temizle
            if user_id in self.pending_logins:
                try:
                    await self.pending_logins[user_id]["client"].disconnect()
                except:
                    pass
                del self.pending_logins[user_id]
            
            return True
            
        except Exception as e:
            print(f"[SMART] Çıkış hatası: {e}")
            return False
    
    # ============================================
    # UYUMLULUK (Eski API)
    # ============================================
    
    def get_client(self, user_id: int) -> Optional[TelegramClient]:
        """Kullanıcının client'ını getir (senkron, sadece aktif olanlar)"""
        return self.active_clients.get(user_id)
    
    def is_logged_in(self, user_id: int) -> bool:
        """Kullanıcının giriş yapıp yapmadığını kontrol et"""
        return user_id in self.active_clients or user_id in self.session_cache
    
    async def restore_sessions(self) -> int:
        """
        Session'ları geri yükle:
        - Aktif plugin'i olan kullanıcılar başlatılır
        - Plugin'i olmayan kullanıcılar cache'de tutulur (on-demand)
        """
        print("[SMART] Session'lar geri yükleniyor...")
        
        users = await db.get_logged_in_users()
        restored = 0
        cached = 0
        
        async def restore_single_user(user):
            """Tek kullanıcıyı restore et"""
            nonlocal restored, cached
            
            user_id = user.get("user_id")
            active_plugins = user.get("active_plugins", [])
            always_on_plugins = user.get("always_on_plugins", [])
            
            # Session verisini cache'e al
            session_data = user.get("session_data")
            if not session_data:
                session_info = await db.get_session(user_id)
                if session_info:
                    session_data = session_info.get("data")
            
            if not session_data:
                print(f"[SMART] Session verisi yok: user={user_id}")
                return False
            
            self.session_cache[user_id] = {
                'data': session_data,
                'type': user.get("session_type", "telethon")
            }
            
            # Aktif plugin'i olan kullanıcıları başlat
            if active_plugins or always_on_plugins:
                # Always-on mu kontrol et
                is_always_on = bool(always_on_plugins)
                
                client = await self.get_or_create_client(user_id, keep_alive=is_always_on)
                
                if client:
                    # Always-on kullanıcıları kaydet
                    if always_on_plugins:
                        self.always_on_users[user_id] = {
                            'plugins': always_on_plugins,
                            'enabled_at': time.time()
                        }
                        self.last_confirm[user_id] = user.get("last_confirm", time.time())
                    
                    # Tüm aktif plugin'leri yükle
                    all_plugins = list(set(active_plugins + always_on_plugins))
                    plugin_count = 0
                    
                    for plugin_name in all_plugins:
                        try:
                            success = await self.plugin_manager.activate_plugin(user_id, plugin_name, client)
                            if success:
                                plugin_count += 1
                        except Exception as e:
                            print(f"[SMART] Plugin yükleme hatası: {plugin_name} - {e}")
                    
                    print(f"[SMART] ✅ user={user_id}, {plugin_count} plugin yüklendi")
                    restored += 1
                    return True
                else:
                    print(f"[SMART] ❌ Client oluşturulamadı: user={user_id}")
                    return False
            else:
                # Plugin'i yok, sadece cache'de tut
                cached += 1
                return True
        
        # Paralel olarak restore et
        tasks = [restore_single_user(user) for user in users]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        print(f"[SMART] ✅ {restored} kullanıcı aktif (plugin'li)")
        print(f"[SMART] 📦 {cached} kullanıcı cache'de (on-demand)")
        print(f"[SMART] 🟢 {len(self.always_on_users)} always-on")
        
        return restored
    
    async def shutdown(self):
        """Tüm client'ları kapat"""
        print("[SMART] Kapatılıyor...")
        
        self.stop_background_tasks()
        
        for user_id in list(self.active_clients.keys()):
            await self._disconnect_client(user_id)
        
        for user_id in list(self.pending_logins.keys()):
            try:
                await self.pending_logins[user_id]["client"].disconnect()
            except:
                pass
        
        print("[SMART] Tüm client'lar kapatıldı")
    
    # ============================================
    # İSTATİSTİKLER
    # ============================================
    
    def get_stats(self) -> Dict:
        """Sistem istatistiklerini getir"""
        return {
            "active_clients": len(self.active_clients),
            "always_on_users": len(self.always_on_users),
            "on_demand_active": len(self.active_clients) - len(self.always_on_users),
            "session_cache": len(self.session_cache),
            "pending_logins": len(self.pending_logins),
            "pending_confirms": len(self.pending_confirms)
        }
    
    def set_session_terminated_callback(self, callback: Callable):
        """Session sonlandırma callback'ini ayarla"""
        self.on_session_terminated_callback = callback
    
    def set_send_message_callback(self, callback: Callable):
        """Mesaj gönderme callback'ini ayarla (bot üzerinden)"""
        self.on_send_message_callback = callback


# Global instance
smart_session_manager = SmartSessionManager()

# Eski uyumluluk için alias
userbot_manager = smart_session_manager
