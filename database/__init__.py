# ============================================
# KingTG UserBot Service - Database Package
# ============================================

from .mongo import db, MongoDB
from .local import local_db, LocalStorage
from typing import Optional, Dict, List, Any
import config

class Database:
    """
    Birleşik veritabanı arayüzü.
    MongoDB bağlıysa onu kullanır, değilse yerel dosyalara düşer.
    Veriler her iki yerde de senkronize tutulur.
    """
    
    def __init__(self):
        self.mongo = db
        self.local = local_db
    
    async def connect(self) -> bool:
        """Veritabanlarına bağlan"""
        return await self.mongo.connect()
    
    @property
    def is_mongo_connected(self) -> bool:
        return self.mongo.connected
    
    # ==========================================
    # KULLANICI İŞLEMLERİ
    # ==========================================
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Kullanıcı bilgilerini getir"""
        if self.mongo.connected:
            user = await self.mongo.get_user(user_id)
            if user:
                return user
        return self.local.get_user(user_id)
    
    async def add_user(self, user_id: int, username: str = None, first_name: str = None) -> bool:
        """Yeni kullanıcı ekle (her iki DB'ye)"""
        local_result = self.local.add_user(user_id, username, first_name)
        
        if self.mongo.connected:
            mongo_result = await self.mongo.add_user(user_id, username, first_name)
            return local_result and mongo_result
        
        return local_result
    
    async def update_user(self, user_id: int, data: Dict) -> bool:
        """Kullanıcı bilgilerini güncelle (her iki DB'ye)"""
        local_result = self.local.update_user(user_id, data)
        
        if self.mongo.connected:
            mongo_result = await self.mongo.update_user(user_id, data)
            return local_result and mongo_result
        
        return local_result
    
    async def delete_user(self, user_id: int) -> bool:
        """Kullanıcıyı sil"""
        local_result = self.local.delete_user(user_id)
        
        if self.mongo.connected:
            mongo_result = await self.mongo.delete_user(user_id)
            return local_result and mongo_result
        
        return local_result
    
    async def get_all_users(self) -> List[Dict]:
        """Tüm kullanıcıları getir"""
        if self.mongo.connected:
            return await self.mongo.get_all_users()
        return self.local.get_all_users()
    
    async def get_logged_in_users(self) -> List[Dict]:
        """Giriş yapmış kullanıcıları getir"""
        if self.mongo.connected:
            return await self.mongo.get_logged_in_users()
        return self.local.get_logged_in_users()
    
    async def get_user_count(self) -> int:
        """Toplam kullanıcı sayısı"""
        if self.mongo.connected:
            return await self.mongo.get_user_count()
        return self.local.get_user_count()
    
    # ==========================================
    # SESSION İŞLEMLERİ
    # ==========================================
    
    async def save_session(self, user_id: int, session_data: str, session_type: str,
                          phone: str = None, remember: bool = False) -> bool:
        """Session kaydet"""
        # Yerel dosyaya kaydet
        self.local.save_session_file(user_id, session_data, session_type)
        self.local.update_user(user_id, {
            "session_type": session_type,
            "phone_number": phone,
            "remember_session": remember,
            "is_logged_in": True
        })
        
        # MongoDB'ye kaydet
        if self.mongo.connected:
            await self.mongo.save_session(user_id, session_data, session_type, phone, remember)
        
        return True
    
    async def get_session(self, user_id: int) -> Optional[Dict]:
        """Session bilgilerini getir"""
        # Önce MongoDB'den dene
        if self.mongo.connected:
            user = await self.mongo.get_user(user_id)
            if user and user.get("session_data"):
                return {
                    "type": user.get("session_type"),
                    "data": user.get("session_data"),
                    "phone": user.get("phone_number"),
                    "remember": user.get("remember_session")
                }
        
        # Yerel dosyadan dene
        session = self.local.load_session_file(user_id)
        if session:
            return session
        
        return None
    
    async def clear_session(self, user_id: int, keep_data: bool = False) -> bool:
        """Session temizle"""
        if not keep_data:
            self.local.delete_session_file(user_id)
        
        self.local.update_user(user_id, {
            "is_logged_in": False,
            "userbot_id": None,
            "userbot_username": None,
            **({"session_type": None, "phone_number": None, "remember_session": False} if not keep_data else {})
        })
        
        if self.mongo.connected:
            await self.mongo.clear_session(user_id, keep_data)
        
        return True
    
    # ==========================================
    # PLUGİN İŞLEMLERİ
    # ==========================================
    
    async def get_plugin(self, plugin_name: str) -> Optional[Dict]:
        """Plugin bilgilerini getir"""
        if self.mongo.connected:
            plugin = await self.mongo.get_plugin(plugin_name)
            if plugin:
                return plugin
        return self.local.get_plugin(plugin_name)
    
    async def add_plugin(self, name: str, filename: str, description: str = "",
                        commands: List[str] = None, is_public: bool = True,
                        allowed_users: List[int] = None) -> bool:
        """Plugin ekle"""
        local_result = self.local.add_plugin(name, filename, description, commands, is_public, allowed_users)
        
        if self.mongo.connected:
            mongo_result = await self.mongo.add_plugin(name, filename, description, commands, is_public, allowed_users)
            return local_result and mongo_result
        
        return local_result
    
    async def update_plugin(self, name: str, data: Dict) -> bool:
        """Plugin güncelle"""
        local_result = self.local.update_plugin(name, data)
        
        if self.mongo.connected:
            mongo_result = await self.mongo.update_plugin(name, data)
            return local_result and mongo_result
        
        return local_result
    
    async def delete_plugin(self, name: str) -> bool:
        """Plugin sil"""
        local_result = self.local.delete_plugin(name)
        
        if self.mongo.connected:
            mongo_result = await self.mongo.delete_plugin(name)
            return local_result and mongo_result
        
        return local_result
    
    async def get_all_plugins(self) -> List[Dict]:
        """Tüm pluginleri getir"""
        if self.mongo.connected:
            return await self.mongo.get_all_plugins()
        return self.local.get_all_plugins()
    
    async def get_public_plugins(self) -> List[Dict]:
        """Genel pluginleri getir"""
        if self.mongo.connected:
            return await self.mongo.get_public_plugins()
        return self.local.get_public_plugins()
    
    async def get_user_accessible_plugins(self, user_id: int) -> List[Dict]:
        """Kullanıcının erişebildiği pluginleri getir"""
        if self.mongo.connected:
            return await self.mongo.get_user_accessible_plugins(user_id)
        return self.local.get_user_accessible_plugins(user_id)
    
    async def check_command_exists(self, command: str, exclude_plugin: str = None) -> Optional[str]:
        """Komut kontrolü"""
        if self.mongo.connected:
            return await self.mongo.check_command_exists(command, exclude_plugin)
        return self.local.check_command_exists(command, exclude_plugin)
    
    async def add_plugin_user_access(self, plugin_name: str, user_id: int) -> bool:
        """Plugin erişimi ekle"""
        # Yerel güncelle
        plugin = self.local.get_plugin(plugin_name)
        if plugin:
            allowed = plugin.get("allowed_users", [])
            if user_id not in allowed:
                allowed.append(user_id)
                self.local.update_plugin(plugin_name, {"allowed_users": allowed})
        
        if self.mongo.connected:
            await self.mongo.add_plugin_user_access(plugin_name, user_id)
        
        return True
    
    async def remove_plugin_user_access(self, plugin_name: str, user_id: int) -> bool:
        """Plugin erişimi kaldır"""
        plugin = self.local.get_plugin(plugin_name)
        if plugin:
            allowed = plugin.get("allowed_users", [])
            if user_id in allowed:
                allowed.remove(user_id)
                self.local.update_plugin(plugin_name, {"allowed_users": allowed})
        
        if self.mongo.connected:
            await self.mongo.remove_plugin_user_access(plugin_name, user_id)
        
        return True
    
    async def restrict_plugin_user(self, plugin_name: str, user_id: int) -> bool:
        """Plugin kısıtla"""
        plugin = self.local.get_plugin(plugin_name)
        if plugin:
            restricted = plugin.get("restricted_users", [])
            if user_id not in restricted:
                restricted.append(user_id)
                self.local.update_plugin(plugin_name, {"restricted_users": restricted})
        
        if self.mongo.connected:
            await self.mongo.restrict_plugin_user(plugin_name, user_id)
        
        return True
    
    async def unrestrict_plugin_user(self, plugin_name: str, user_id: int) -> bool:
        """Plugin kısıtlamayı kaldır"""
        plugin = self.local.get_plugin(plugin_name)
        if plugin:
            restricted = plugin.get("restricted_users", [])
            if user_id in restricted:
                restricted.remove(user_id)
                self.local.update_plugin(plugin_name, {"restricted_users": restricted})
        
        if self.mongo.connected:
            await self.mongo.unrestrict_plugin_user(plugin_name, user_id)
        
        return True
    
    # ==========================================
    # BAN İŞLEMLERİ
    # ==========================================
    
    async def ban_user(self, user_id: int, reason: str = None, banned_by: int = None) -> bool:
        """Kullanıcıyı banla"""
        self.local.ban_user(user_id, reason)
        
        if self.mongo.connected:
            await self.mongo.ban_user(user_id, reason, banned_by)
        
        return True
    
    async def unban_user(self, user_id: int) -> bool:
        """Ban kaldır"""
        self.local.unban_user(user_id)
        
        if self.mongo.connected:
            await self.mongo.unban_user(user_id)
        
        return True
    
    async def is_banned(self, user_id: int) -> bool:
        """Ban kontrolü"""
        if self.mongo.connected:
            return await self.mongo.is_banned(user_id)
        return self.local.is_banned(user_id)
    
    async def get_banned_users(self) -> List[Dict]:
        """Banlı kullanıcılar"""
        if self.mongo.connected:
            return await self.mongo.get_banned_users()
        return self.local.get_banned_users()
    
    # ==========================================
    # SUDO İŞLEMLERİ
    # ==========================================
    
    async def add_sudo(self, user_id: int) -> bool:
        """Sudo ekle"""
        self.local.add_sudo(user_id)
        
        if self.mongo.connected:
            await self.mongo.add_sudo(user_id)
        
        return True
    
    async def remove_sudo(self, user_id: int) -> bool:
        """Sudo kaldır"""
        self.local.remove_sudo(user_id)
        
        if self.mongo.connected:
            await self.mongo.remove_sudo(user_id)
        
        return True
    
    async def is_sudo(self, user_id: int) -> bool:
        """Sudo kontrolü"""
        if user_id == config.OWNER_ID:
            return True
        if self.mongo.connected:
            return await self.mongo.is_sudo(user_id)
        return self.local.is_sudo(user_id)
    
    async def get_sudos(self) -> List[Dict]:
        """Sudo listesi"""
        if self.mongo.connected:
            return await self.mongo.get_sudos()
        return self.local.get_sudos()
    
    # ==========================================
    # AYARLAR İŞLEMLERİ
    # ==========================================
    
    async def get_settings(self) -> Dict:
        """Ayarları getir"""
        if self.mongo.connected:
            return await self.mongo.get_settings()
        return self.local.get_settings()
    
    async def update_settings(self, data: Dict) -> bool:
        """Ayarları güncelle"""
        self.local.update_settings(data)
        
        if self.mongo.connected:
            await self.mongo.update_settings(data)
        
        return True
    
    # ==========================================
    # LOG İŞLEMLERİ
    # ==========================================
    
    async def add_log(self, log_type: str, user_id: int = None,
                     message: str = "", data: Dict = None) -> bool:
        """Log ekle"""
        if self.mongo.connected:
            return await self.mongo.add_log(log_type, user_id, message, data)
        return True
    
    async def get_logs(self, limit: int = 100, log_type: str = None) -> List[Dict]:
        """Logları getir"""
        if self.mongo.connected:
            return await self.mongo.get_logs(limit, log_type)
        return []
    
    # ==========================================
    # İSTATİSTİK İŞLEMLERİ
    # ==========================================
    
    async def get_stats(self) -> Dict:
        """İstatistikleri getir"""
        if self.mongo.connected:
            return await self.mongo.get_stats()
        return self.local.get_stats()


# Global Database instance
database = Database()
