# ============================================
# KingTG UserBot Service - Userbot Manager
# ============================================

import asyncio
import os
import re
from typing import Optional, Dict, Callable, Any
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
        self.pending_logins: Dict[int, Dict] = {}  # Giriş işlemi bekleyenler
        self.session_monitors: Dict[int, asyncio.Task] = {}  # Oturum izleyicileri
    
    async def create_client_from_session(self, user_id: int, session_string: str, 
                                         session_type: str = "telethon") -> Optional[TelegramClient]:
        """Session string'den client oluştur"""
        try:
            if session_type == "telethon":
                client = TelegramClient(
                    StringSession(session_string),
                    config.API_ID,
                    config.API_HASH
                )
            elif session_type == "pyrogram":
                # Pyrogram session'ı Telethon'a dönüştür
                # Bu basit bir dönüşüm, gerçek implementasyon daha karmaşık olabilir
                client = TelegramClient(
                    StringSession(session_string),
                    config.API_ID,
                    config.API_HASH
                )
            else:
                return None
            
            await client.connect()
            
            if not await client.is_user_authorized():
                await client.disconnect()
                return None
            
            self.active_clients[user_id] = client
            
            # Session izleyiciyi başlat
            self.start_session_monitor(user_id)
            
            return client
            
        except AuthKeyUnregisteredError:
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
            return {"success": False, "error": f"flood_wait", "seconds": e.seconds}
        except Exception as e:
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
            
            # Başarılı giriş
            me = await client.get_me()
            session_string = client.session.save()
            
            self.active_clients[user_id] = client
            del self.pending_logins[user_id]
            
            # Session izleyiciyi başlat
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
            
            # Session izleyiciyi başlat
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
            return {"success": False, "error": str(e)}
    
    async def login_with_session(self, user_id: int, session_string: str, 
                                 session_type: str = "telethon") -> Dict:
        """Session string ile giriş"""
        try:
            client = await self.create_client_from_session(user_id, session_string, session_type)
            
            if client:
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
            else:
                return {"success": False, "error": "invalid_session"}
                
        except UserDeactivatedBanError:
            return {"success": False, "error": "account_banned"}
        except AuthKeyUnregisteredError:
            return {"success": False, "error": "session_terminated"}
        except Exception as e:
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
                
                await client.disconnect()
                del self.active_clients[user_id]
            
            # Session izleyiciyi durdur
            self.stop_session_monitor(user_id)
            
            # Pending login varsa temizle
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
        except AuthKeyUnregisteredError:
            return False
        except Exception:
            return False
    
    def start_session_monitor(self, user_id: int):
        """Session izleyiciyi başlat"""
        if user_id in self.session_monitors:
            self.session_monitors[user_id].cancel()
        
        async def monitor():
            while True:
                await asyncio.sleep(300)  # 5 dakikada bir kontrol
                
                if not await self.check_session_valid(user_id):
                    # Session sonlandırılmış
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
        # Client'ı temizle
        if user_id in self.active_clients:
            try:
                await self.active_clients[user_id].disconnect()
            except:
                pass
            del self.active_clients[user_id]
        
        # Veritabanını güncelle
        await db.update_user(user_id, {"is_logged_in": False})
        
        # Bildirim callback'i çağır (main.py'de ayarlanacak)
        if hasattr(self, 'on_session_terminated_callback') and self.on_session_terminated_callback:
            await self.on_session_terminated_callback(user_id)
    
    def set_session_terminated_callback(self, callback: Callable):
        """Session sonlandırma callback'ini ayarla"""
        self.on_session_terminated_callback = callback
    
    async def restore_sessions(self) -> int:
        """Kaydedilmiş session'ları geri yükle"""
        restored = 0
        users = await db.get_logged_in_users()
        
        for user in users:
            user_id = user.get("user_id")
            session_data = await db.get_session(user_id)
            
            if session_data and session_data.get("data"):
                result = await self.login_with_session(
                    user_id,
                    session_data["data"],
                    session_data.get("type", "telethon")
                )
                
                if result.get("success"):
                    restored += 1
                    print(f"[USERBOT] ✅ Session geri yüklendi: {user_id}")
                else:
                    # Session geçersiz, veritabanını güncelle
                    await db.update_user(user_id, {"is_logged_in": False})
                    print(f"[USERBOT] ❌ Session geçersiz: {user_id} - {result.get('error')}")
        
        return restored
    
    async def shutdown(self):
        """Tüm client'ları kapat"""
        for user_id in list(self.active_clients.keys()):
            await self.logout(user_id)
        
        for user_id in list(self.pending_logins.keys()):
            try:
                await self.pending_logins[user_id]["client"].disconnect()
            except:
                pass


# Global UserBot Manager instance
userbot_manager = UserbotManager()
