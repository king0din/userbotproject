# ============================================
# KingTG UserBot Service - MongoDB İşlemleri
# ============================================

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from typing import Optional, Dict, List, Any
import config

class MongoDB:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.connected = False
    
    async def connect(self):
        """MongoDB'ye bağlan"""
        try:
            self.client = AsyncIOMotorClient(config.MONGO_URI)
            self.db = self.client[config.MONGO_DB_NAME]
            # Bağlantıyı test et
            await self.client.admin.command('ping')
            self.connected = True
            print("[MONGO] ✅ MongoDB bağlantısı başarılı")
            return True
        except Exception as e:
            print(f"[MONGO] ❌ MongoDB bağlantı hatası: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """MongoDB bağlantısını kapat"""
        if self.client:
            self.client.close()
            self.connected = False
            print("[MONGO] 🔌 MongoDB bağlantısı kapatıldı")
    
    # ==========================================
    # KULLANICI İŞLEMLERİ
    # ==========================================
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Kullanıcı bilgilerini getir"""
        if not self.connected:
            return None
        return await self.db.users.find_one({"user_id": user_id})
    
    async def add_user(self, user_id: int, username: str = None, first_name: str = None) -> bool:
        """Yeni kullanıcı ekle"""
        if not self.connected:
            return False
        
        user_data = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "created_at": datetime.utcnow(),
            "last_active": datetime.utcnow(),
            "is_logged_in": False,
            "session_data": None,
            "session_type": None,  # telethon, pyrogram, phone
            "remember_session": False,
            "phone_number": None,
            "userbot_id": None,
            "userbot_username": None,
            "active_plugins": [],
            "plugin_settings": {},
            "is_banned": False,
            "is_sudo": False,
            "ban_reason": None,
            "settings": {}
        }
        
        try:
            await self.db.users.update_one(
                {"user_id": user_id},
                {"$setOnInsert": user_data},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"[MONGO] Kullanıcı ekleme hatası: {e}")
            return False
    
    async def update_user(self, user_id: int, data: Dict) -> bool:
        """Kullanıcı bilgilerini güncelle"""
        if not self.connected:
            return False
        
        data["last_active"] = datetime.utcnow()
        
        try:
            await self.db.users.update_one(
                {"user_id": user_id},
                {"$set": data}
            )
            return True
        except Exception as e:
            print(f"[MONGO] Kullanıcı güncelleme hatası: {e}")
            return False
    
    async def delete_user(self, user_id: int) -> bool:
        """Kullanıcıyı sil"""
        if not self.connected:
            return False
        
        try:
            await self.db.users.delete_one({"user_id": user_id})
            return True
        except Exception as e:
            print(f"[MONGO] Kullanıcı silme hatası: {e}")
            return False
    
    async def get_all_users(self) -> List[Dict]:
        """Tüm kullanıcıları getir"""
        if not self.connected:
            return []
        
        cursor = self.db.users.find({})
        return await cursor.to_list(length=None)
    
    async def get_logged_in_users(self) -> List[Dict]:
        """Giriş yapmış kullanıcıları getir"""
        if not self.connected:
            return []
        
        cursor = self.db.users.find({"is_logged_in": True})
        return await cursor.to_list(length=None)
    
    async def get_user_count(self) -> int:
        """Toplam kullanıcı sayısı"""
        if not self.connected:
            return 0
        return await self.db.users.count_documents({})
    
    # ==========================================
    # SESSION İŞLEMLERİ
    # ==========================================
    
    async def save_session(self, user_id: int, session_data: str, session_type: str, 
                          phone: str = None, remember: bool = False) -> bool:
        """Session bilgilerini kaydet"""
        return await self.update_user(user_id, {
            "session_data": session_data,
            "session_type": session_type,
            "phone_number": phone,
            "remember_session": remember,
            "is_logged_in": True
        })
    
    async def clear_session(self, user_id: int, keep_data: bool = False) -> bool:
        """Session bilgilerini temizle"""
        if keep_data:
            return await self.update_user(user_id, {
                "is_logged_in": False,
                "userbot_id": None,
                "userbot_username": None
            })
        else:
            return await self.update_user(user_id, {
                "session_data": None,
                "session_type": None,
                "phone_number": None,
                "remember_session": False,
                "is_logged_in": False,
                "userbot_id": None,
                "userbot_username": None
            })
    
    # ==========================================
    # PLUGİN İŞLEMLERİ
    # ==========================================
    
    async def get_plugin(self, plugin_name: str) -> Optional[Dict]:
        """Plugin bilgilerini getir"""
        if not self.connected:
            return None
        return await self.db.plugins.find_one({"name": plugin_name})
    
    async def add_plugin(self, name: str, filename: str, description: str = "",
                        commands: List[str] = None, is_public: bool = True,
                        allowed_users: List[int] = None) -> bool:
        """Yeni plugin ekle"""
        if not self.connected:
            return False
        
        plugin_data = {
            "name": name,
            "filename": filename,
            "description": description,
            "commands": commands or [],
            "is_public": is_public,
            "allowed_users": allowed_users or [],
            "restricted_users": [],  # Bu kullanıcılar plugini kullanamaz
            "added_at": datetime.utcnow(),
            "added_by": config.OWNER_ID,
            "is_active": True,
            "usage_count": 0
        }
        
        try:
            await self.db.plugins.update_one(
                {"name": name},
                {"$set": plugin_data},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"[MONGO] Plugin ekleme hatası: {e}")
            return False
    
    async def update_plugin(self, name: str, data: Dict) -> bool:
        """Plugin bilgilerini güncelle"""
        if not self.connected:
            return False
        
        try:
            await self.db.plugins.update_one(
                {"name": name},
                {"$set": data}
            )
            return True
        except Exception as e:
            print(f"[MONGO] Plugin güncelleme hatası: {e}")
            return False
    
    async def delete_plugin(self, name: str) -> bool:
        """Plugin sil"""
        if not self.connected:
            return False
        
        try:
            await self.db.plugins.delete_one({"name": name})
            return True
        except Exception as e:
            print(f"[MONGO] Plugin silme hatası: {e}")
            return False
    
    async def get_all_plugins(self) -> List[Dict]:
        """Tüm pluginleri getir"""
        if not self.connected:
            return []
        
        cursor = self.db.plugins.find({})
        return await cursor.to_list(length=None)
    
    async def get_public_plugins(self) -> List[Dict]:
        """Genel pluginleri getir"""
        if not self.connected:
            return []
        
        cursor = self.db.plugins.find({"is_public": True, "is_active": True})
        return await cursor.to_list(length=None)
    
    async def get_user_accessible_plugins(self, user_id: int) -> List[Dict]:
        """Kullanıcının erişebildiği pluginleri getir"""
        if not self.connected:
            return []
        
        # Genel pluginler + kullanıcıya özel izin verilenler
        cursor = self.db.plugins.find({
            "$and": [
                {"is_active": True},
                {"restricted_users": {"$ne": user_id}},  # Kısıtlanmamış
                {"$or": [
                    {"is_public": True},
                    {"allowed_users": user_id}
                ]}
            ]
        })
        return await cursor.to_list(length=None)
    
    async def check_command_exists(self, command: str, exclude_plugin: str = None) -> Optional[str]:
        """Komutun başka bir pluginde olup olmadığını kontrol et"""
        if not self.connected:
            return None
        
        query = {"commands": command}
        if exclude_plugin:
            query["name"] = {"$ne": exclude_plugin}
        
        plugin = await self.db.plugins.find_one(query)
        return plugin["name"] if plugin else None
    
    async def add_plugin_user_access(self, plugin_name: str, user_id: int) -> bool:
        """Plugin'e kullanıcı erişimi ekle"""
        if not self.connected:
            return False
        
        try:
            await self.db.plugins.update_one(
                {"name": plugin_name},
                {"$addToSet": {"allowed_users": user_id}}
            )
            return True
        except Exception as e:
            print(f"[MONGO] Plugin erişim ekleme hatası: {e}")
            return False
    
    async def remove_plugin_user_access(self, plugin_name: str, user_id: int) -> bool:
        """Plugin'den kullanıcı erişimini kaldır"""
        if not self.connected:
            return False
        
        try:
            await self.db.plugins.update_one(
                {"name": plugin_name},
                {"$pull": {"allowed_users": user_id}}
            )
            return True
        except Exception as e:
            print(f"[MONGO] Plugin erişim kaldırma hatası: {e}")
            return False
    
    async def restrict_plugin_user(self, plugin_name: str, user_id: int) -> bool:
        """Kullanıcıyı plugin kullanımından kısıtla"""
        if not self.connected:
            return False
        
        try:
            await self.db.plugins.update_one(
                {"name": plugin_name},
                {"$addToSet": {"restricted_users": user_id}}
            )
            return True
        except Exception as e:
            print(f"[MONGO] Plugin kısıtlama hatası: {e}")
            return False
    
    async def unrestrict_plugin_user(self, plugin_name: str, user_id: int) -> bool:
        """Kullanıcının plugin kısıtlamasını kaldır"""
        if not self.connected:
            return False
        
        try:
            await self.db.plugins.update_one(
                {"name": plugin_name},
                {"$pull": {"restricted_users": user_id}}
            )
            return True
        except Exception as e:
            print(f"[MONGO] Plugin kısıtlama kaldırma hatası: {e}")
            return False
    
    # ==========================================
    # BAN İŞLEMLERİ
    # ==========================================
    
    async def ban_user(self, user_id: int, reason: str = None, banned_by: int = None) -> bool:
        """Kullanıcıyı banla"""
        if not self.connected:
            return False
        
        try:
            await self.db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "is_banned": True,
                    "ban_reason": reason,
                    "banned_at": datetime.utcnow(),
                    "banned_by": banned_by
                }}
            )
            return True
        except Exception as e:
            print(f"[MONGO] Ban hatası: {e}")
            return False
    
    async def unban_user(self, user_id: int) -> bool:
        """Kullanıcının banını kaldır"""
        if not self.connected:
            return False
        
        try:
            await self.db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "is_banned": False,
                    "ban_reason": None,
                    "banned_at": None,
                    "banned_by": None
                }}
            )
            return True
        except Exception as e:
            print(f"[MONGO] Unban hatası: {e}")
            return False
    
    async def is_banned(self, user_id: int) -> bool:
        """Kullanıcının banlı olup olmadığını kontrol et"""
        user = await self.get_user(user_id)
        return user.get("is_banned", False) if user else False
    
    async def get_banned_users(self) -> List[Dict]:
        """Banlı kullanıcıları getir"""
        if not self.connected:
            return []
        
        cursor = self.db.users.find({"is_banned": True})
        return await cursor.to_list(length=None)
    
    # ==========================================
    # SUDO İŞLEMLERİ
    # ==========================================
    
    async def add_sudo(self, user_id: int) -> bool:
        """Sudo ekle"""
        return await self.update_user(user_id, {"is_sudo": True})
    
    async def remove_sudo(self, user_id: int) -> bool:
        """Sudo kaldır"""
        return await self.update_user(user_id, {"is_sudo": False})
    
    async def is_sudo(self, user_id: int) -> bool:
        """Sudo kontrolü"""
        if user_id == config.OWNER_ID:
            return True
        user = await self.get_user(user_id)
        return user.get("is_sudo", False) if user else False
    
    async def get_sudos(self) -> List[Dict]:
        """Sudo listesi"""
        if not self.connected:
            return []
        
        cursor = self.db.users.find({"is_sudo": True})
        return await cursor.to_list(length=None)
    
    # ==========================================
    # AYARLAR İŞLEMLERİ
    # ==========================================
    
    async def get_settings(self) -> Dict:
        """Bot ayarlarını getir"""
        if not self.connected:
            return config.DEFAULT_SETTINGS.copy()
        
        settings = await self.db.settings.find_one({"_id": "bot_settings"})
        if settings:
            del settings["_id"]
            return settings
        return config.DEFAULT_SETTINGS.copy()
    
    async def update_settings(self, data: Dict) -> bool:
        """Bot ayarlarını güncelle"""
        if not self.connected:
            return False
        
        try:
            await self.db.settings.update_one(
                {"_id": "bot_settings"},
                {"$set": data},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"[MONGO] Ayar güncelleme hatası: {e}")
            return False
    
    # ==========================================
    # LOG İŞLEMLERİ
    # ==========================================
    
    async def add_log(self, log_type: str, user_id: int = None, 
                     message: str = "", data: Dict = None) -> bool:
        """Log ekle"""
        if not self.connected:
            return False
        
        log_data = {
            "type": log_type,
            "user_id": user_id,
            "message": message,
            "data": data or {},
            "timestamp": datetime.utcnow()
        }
        
        try:
            await self.db.logs.insert_one(log_data)
            return True
        except Exception as e:
            print(f"[MONGO] Log ekleme hatası: {e}")
            return False
    
    async def get_logs(self, limit: int = 100, log_type: str = None) -> List[Dict]:
        """Logları getir"""
        if not self.connected:
            return []
        
        query = {}
        if log_type:
            query["type"] = log_type
        
        cursor = self.db.logs.find(query).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=None)
    
    # ==========================================
    # İSTATİSTİK İŞLEMLERİ
    # ==========================================
    
    async def get_stats(self) -> Dict:
        """İstatistikleri getir"""
        if not self.connected:
            return {}
        
        return {
            "total_users": await self.db.users.count_documents({}),
            "logged_in_users": await self.db.users.count_documents({"is_logged_in": True}),
            "banned_users": await self.db.users.count_documents({"is_banned": True}),
            "sudo_users": await self.db.users.count_documents({"is_sudo": True}),
            "total_plugins": await self.db.plugins.count_documents({}),
            "public_plugins": await self.db.plugins.count_documents({"is_public": True}),
            "private_plugins": await self.db.plugins.count_documents({"is_public": False}),
        }


# Global MongoDB instance
db = MongoDB()
