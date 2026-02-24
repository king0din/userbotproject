# ============================================
# KingTG UserBot Service - Userbot Manager
# ============================================

import asyncio
import os
from typing import Optional, Dict, Callable
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError, 
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PasswordHashInvalidError,
    AuthKeyUnregisteredError,
    UserDeactivatedBanError,
    FloodWaitError
)
import config
from database import database as db

class UserbotManager:
    """Kullanıcı userbot'larını yöneten sınıf"""
    
    def __init__(self):
        self.active_clients: Dict[int, TelegramClient] = {}
        self.pending_logins: Dict[int, Dict] = {}
        self.session_monitors: Dict[int, asyncio.Task] = {}
        self.on_session_terminated_callback = None
        self._plugin_manager = None  # Lazy load için
    
    @property
    def plugin_manager(self):
        """Plugin manager'ı lazy load et"""
        if self._plugin_manager is None:
            from userbot.plugins import plugin_manager
            self._plugin_manager = plugin_manager
        return self._plugin_manager
    
    async def create_client_from_session(self, user_id: int, session_string: str, 
                                         session_type: str = "telethon") -> Optional[TelegramClient]:
        """Session string'den client oluştur"""
        try:
            print(f"[USERBOT] Client oluşturuluyor: user={user_id}, type={session_type}")
            
            client = TelegramClient(
                StringSession(session_string),
                config.API_ID,
                config.API_HASH
            )
            
            await client.connect()
            
            if not await client.is_user_authorized():
                print(f"[USERBOT] Kullanıcı yetkili değil: user={user_id}")
                await client.disconnect()
                return None
            
            self.active_clients[user_id] = client
            self.start_session_monitor(user_id)
            
            print(f"[USERBOT] Client başarıyla oluşturuldu: user={user_id}")
            return client
            
        except AuthKeyUnregisteredError:
            print(f"[USERBOT] AuthKey geçersiz: user={user_id}")
            return None
        except Exception as e:
            print(f"[USERBOT] Client oluşturma hatası: {e}")
            return None
    
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
            print(f"[USERBOT] Telefon giriş hatası: {e}")
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
            del self.pending_logins[user_id]
            
            self.start_session_monitor(user_id)
            
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
            print(f"[USERBOT] Kod doğrulama hatası: {e}")
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
            del self.pending_logins[user_id]
            
            self.start_session_monitor(user_id)
            
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
            print(f"[USERBOT] 2FA hatası: {e}")
            return {"success": False, "error": str(e)}
    
    async def login_with_session(self, user_id: int, session_string: str, 
                                 session_type: str = "telethon") -> Dict:
        """Session string ile giriş"""
        try:
            print(f"[USERBOT] Session ile giriş: user={user_id}, type={session_type}")
            
            client = await self.create_client_from_session(user_id, session_string, session_type)
            
            if client:
                me = await client.get_me()
                print(f"[USERBOT] Giriş başarılı: @{me.username}")
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
            else:
                return {"success": False, "error": "invalid_session"}
                
        except UserDeactivatedBanError:
            return {"success": False, "error": "account_banned"}
        except AuthKeyUnregisteredError:
            return {"success": False, "error": "session_terminated"}
        except Exception as e:
            print(f"[USERBOT] Session giriş hatası: {e}")
            return {"success": False, "error": str(e)}
    
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
                
                try:
                    await client.disconnect()
                except:
                    pass
                
                del self.active_clients[user_id]
            
            self.stop_session_monitor(user_id)
            
            if user_id in self.pending_logins:
                try:
                    await self.pending_logins[user_id]["client"].disconnect()
                except:
                    pass
                del self.pending_logins[user_id]
            
            return True
            
        except Exception as e:
            print(f"[USERBOT] Çıkış hatası: {e}")
            return False
    
    def get_client(self, user_id: int) -> Optional[TelegramClient]:
        """Kullanıcının client'ını getir"""
        return self.active_clients.get(user_id)
    
    def is_logged_in(self, user_id: int) -> bool:
        """Kullanıcının giriş yapıp yapmadığını kontrol et"""
        return user_id in self.active_clients
    
    async def check_session_valid(self, user_id: int) -> bool:
        """Session'ın hala geçerli olup olmadığını kontrol et"""
        client = self.active_clients.get(user_id)
        if not client:
            return False
        
        try:
            await client.get_me()
            return True
        except:
            return False
    
    def start_session_monitor(self, user_id: int):
        """Session izleyiciyi başlat"""
        if user_id in self.session_monitors:
            self.session_monitors[user_id].cancel()
        
        async def monitor():
            while user_id in self.active_clients:
                await asyncio.sleep(300)
                
                if not await self.check_session_valid(user_id):
                    await self.on_session_terminated(user_id)
                    break
        
        self.session_monitors[user_id] = asyncio.create_task(monitor())
    
    def stop_session_monitor(self, user_id: int):
        """Session izleyiciyi durdur"""
        if user_id in self.session_monitors:
            self.session_monitors[user_id].cancel()
            del self.session_monitors[user_id]
    
    async def on_session_terminated(self, user_id: int):
        """Session sonlandırıldığında çağrılır"""
        print(f"[USERBOT] Session sonlandırıldı: user={user_id}")
        
        if user_id in self.active_clients:
            try:
                await self.active_clients[user_id].disconnect()
            except:
                pass
            del self.active_clients[user_id]
        
        await db.update_user(user_id, {"is_logged_in": False})
        
        if self.on_session_terminated_callback:
            try:
                await self.on_session_terminated_callback(user_id)
            except Exception as e:
                print(f"[USERBOT] Callback hatası: {e}")
    
    def set_session_terminated_callback(self, callback: Callable):
        """Session sonlandırma callback'ini ayarla"""
        self.on_session_terminated_callback = callback
    
    async def restore_sessions(self) -> int:
        """Kaydedilmiş session'ları geri yükle ve pluginleri aktif et - PARALEL"""
        print("[USERBOT] Session'lar geri yükleniyor (paralel)...")
        
        users = await db.get_logged_in_users()
        print(f"[USERBOT] {len(users)} giriş yapmış kullanıcı bulundu")
        
        if not users:
            return 0
        
        async def restore_single_session(user):
            """Tek bir kullanıcının session'ını geri yükle"""
            user_id = user.get("user_id")
            
            try:
                session_data = user.get("session_data")
                session_type = user.get("session_type", "telethon")
                
                if not session_data:
                    session_info = await db.get_session(user_id)
                    if session_info:
                        session_data = session_info.get("data")
                        session_type = session_info.get("type", "telethon")
                
                if not session_data:
                    print(f"[USERBOT] Session bulunamadı: user={user_id}")
                    await db.update_user(user_id, {"is_logged_in": False})
                    return False
                
                print(f"[USERBOT] Session yükleniyor: user={user_id}")
                
                result = await self.login_with_session(user_id, session_data, session_type)
                
                if result.get("success"):
                    print(f"[USERBOT] ✅ Session OK: user={user_id}")
                    
                    # Kullanıcının pluginlerini geri yükle
                    client = self.get_client(user_id)
                    if client:
                        active_plugins = user.get("active_plugins", [])
                        if active_plugins:
                            plugin_count = await self.plugin_manager.restore_user_plugins(user_id, client)
                            print(f"[USERBOT] 🔌 {plugin_count} plugin: user={user_id}")
                    return True
                else:
                    await db.update_user(user_id, {"is_logged_in": False})
                    print(f"[USERBOT] ❌ Session geçersiz: user={user_id}")
                    return False
                    
            except Exception as e:
                print(f"[USERBOT] ❌ Hata: user={user_id} - {e}")
                await db.update_user(user_id, {"is_logged_in": False})
                return False
        
        # Tüm session'ları paralel olarak başlat
        tasks = [restore_single_session(user) for user in users]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Başarılı olanları say
        restored = sum(1 for r in results if r is True)
        
        print(f"[USERBOT] ✅ Toplam {restored}/{len(users)} session geri yüklendi (paralel)")
        return restored
    
    async def shutdown(self):
        """Tüm client'ları kapat"""
        print("[USERBOT] Tüm client'lar kapatılıyor...")
        
        for user_id in list(self.active_clients.keys()):
            await self.logout(user_id)
        
        for user_id in list(self.pending_logins.keys()):
            try:
                await self.pending_logins[user_id]["client"].disconnect()
            except:
                pass
        
        print("[USERBOT] Tüm client'lar kapatıldı")


# Global UserBot Manager instance
userbot_manager = UserbotManager()
