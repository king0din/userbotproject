# ============================================
# KingTG UserBot Service - Yerel Dosya Depolama
# ============================================

import os
import json
from datetime import datetime
from typing import Optional, Dict, List, Any
import config

class LocalStorage:
    """JSON dosyalarında veri saklama sınıfı"""
    
    def __init__(self):
        self._ensure_files()
    
    def _ensure_files(self):
        """Gerekli dosyaları oluştur"""
        files = {
            config.USERS_FILE: {},
            config.SETTINGS_FILE: config.DEFAULT_SETTINGS,
            config.PLUGINS_FILE: {},
            config.BANS_FILE: [],
            config.SUDOS_FILE: []
        }
        
        for file_path, default_data in files.items():
            if not os.path.exists(file_path):
                self._save_json(file_path, default_data)
    
    def _load_json(self, file_path: str) -> Any:
        """JSON dosyasını yükle"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
    
    def _save_json(self, file_path: str, data: Any) -> bool:
        """JSON dosyasına kaydet"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            return True
        except Exception as e:
            print(f"[LOCAL] Dosya kaydetme hatası: {e}")
            return False
    
    # ==========================================
    # KULLANICI İŞLEMLERİ
    # ==========================================
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Kullanıcı bilgilerini getir"""
        users = self._load_json(config.USERS_FILE) or {}
        return users.get(str(user_id))
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None) -> bool:
        """Yeni kullanıcı ekle"""
        users = self._load_json(config.USERS_FILE) or {}
        
        if str(user_id) not in users:
            users[str(user_id)] = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "created_at": datetime.utcnow().isoformat(),
                "last_active": datetime.utcnow().isoformat(),
                "is_logged_in": False,
                "session_data": None,  # Session string burada saklanacak
                "session_type": None,
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
            return self._save_json(config.USERS_FILE, users)
        return True
    
    def update_user(self, user_id: int, data: Dict) -> bool:
        """Kullanıcı bilgilerini güncelle"""
        users = self._load_json(config.USERS_FILE) or {}
        
        if str(user_id) not in users:
            # Kullanıcı yoksa oluştur
            self.add_user(user_id)
            users = self._load_json(config.USERS_FILE) or {}
        
        if str(user_id) in users:
            users[str(user_id)].update(data)
            users[str(user_id)]["last_active"] = datetime.utcnow().isoformat()
            return self._save_json(config.USERS_FILE, users)
        return False
    
    def delete_user(self, user_id: int) -> bool:
        """Kullanıcıyı sil"""
        users = self._load_json(config.USERS_FILE) or {}
        
        if str(user_id) in users:
            del users[str(user_id)]
            return self._save_json(config.USERS_FILE, users)
        return False
    
    def get_all_users(self) -> List[Dict]:
        """Tüm kullanıcıları getir"""
        users = self._load_json(config.USERS_FILE) or {}
        return list(users.values())
    
    def get_logged_in_users(self) -> List[Dict]:
        """Giriş yapmış kullanıcıları getir"""
        users = self._load_json(config.USERS_FILE) or {}
        return [u for u in users.values() if u.get("is_logged_in")]
    
    def get_user_count(self) -> int:
        """Toplam kullanıcı sayısı"""
        users = self._load_json(config.USERS_FILE) or {}
        return len(users)
    
    # ==========================================
    # SESSION İŞLEMLERİ
    # ==========================================
    
    def save_session(self, user_id: int, session_data: str, session_type: str,
                    phone: str = None, remember: bool = False) -> bool:
        """Session bilgilerini kullanıcı verisine kaydet"""
        return self.update_user(user_id, {
            "session_data": session_data,
            "session_type": session_type,
            "phone_number": phone,
            "remember_session": remember,
            "is_logged_in": True
        })
    
    def get_session(self, user_id: int) -> Optional[Dict]:
        """Session bilgilerini getir"""
        user = self.get_user(user_id)
        if user and user.get("session_data"):
            return {
                "data": user.get("session_data"),
                "type": user.get("session_type"),
                "phone": user.get("phone_number"),
                "remember": user.get("remember_session", False)
            }
        return None
    
    def clear_session(self, user_id: int, keep_data: bool = False) -> bool:
        """Session bilgilerini temizle"""
        update_data = {
            "is_logged_in": False,
            "userbot_id": None,
            "userbot_username": None
        }
        
        if not keep_data:
            update_data.update({
                "session_data": None,
                "session_type": None,
                "phone_number": None,
                "remember_session": False
            })
        
        return self.update_user(user_id, update_data)
    
    # ==========================================
    # PLUGİN İŞLEMLERİ
    # ==========================================
    
    def get_plugin(self, plugin_name: str) -> Optional[Dict]:
        """Plugin bilgilerini getir"""
        plugins = self._load_json(config.PLUGINS_FILE) or {}
        return plugins.get(plugin_name)
    
    def add_plugin(self, name: str, filename: str, description: str = "",
                  commands: List[str] = None, is_public: bool = True,
                  allowed_users: List[int] = None) -> bool:
        """Yeni plugin ekle"""
        plugins = self._load_json(config.PLUGINS_FILE) or {}
        
        plugins[name] = {
            "name": name,
            "filename": filename,
            "description": description,
            "commands": commands or [],
            "is_public": is_public,
            "allowed_users": allowed_users or [],
            "restricted_users": [],
            "added_at": datetime.utcnow().isoformat(),
            "added_by": config.OWNER_ID,
            "is_active": True,
            "usage_count": 0
        }
        
        return self._save_json(config.PLUGINS_FILE, plugins)
    
    def update_plugin(self, name: str, data: Dict) -> bool:
        """Plugin bilgilerini güncelle"""
        plugins = self._load_json(config.PLUGINS_FILE) or {}
        
        if name in plugins:
            plugins[name].update(data)
            return self._save_json(config.PLUGINS_FILE, plugins)
        return False
    
    def delete_plugin(self, name: str) -> bool:
        """Plugin sil"""
        plugins = self._load_json(config.PLUGINS_FILE) or {}
        
        if name in plugins:
            del plugins[name]
            return self._save_json(config.PLUGINS_FILE, plugins)
        return False
    
    def get_all_plugins(self) -> List[Dict]:
        """Tüm pluginleri getir"""
        plugins = self._load_json(config.PLUGINS_FILE) or {}
        return list(plugins.values())
    
    def get_public_plugins(self) -> List[Dict]:
        """Genel pluginleri getir"""
        plugins = self._load_json(config.PLUGINS_FILE) or {}
        return [p for p in plugins.values() if p.get("is_public") and p.get("is_active")]
    
    def get_user_accessible_plugins(self, user_id: int) -> List[Dict]:
        """Kullanıcının erişebildiği pluginleri getir"""
        plugins = self._load_json(config.PLUGINS_FILE) or {}
        accessible = []
        
        for plugin in plugins.values():
            if not plugin.get("is_active"):
                continue
            if user_id in plugin.get("restricted_users", []):
                continue
            if plugin.get("is_public") or user_id in plugin.get("allowed_users", []):
                accessible.append(plugin)
        
        return accessible
    
    def check_command_exists(self, command: str, exclude_plugin: str = None) -> Optional[str]:
        """Komutun başka bir pluginde olup olmadığını kontrol et"""
        plugins = self._load_json(config.PLUGINS_FILE) or {}
        
        for name, plugin in plugins.items():
            if exclude_plugin and name == exclude_plugin:
                continue
            if command in plugin.get("commands", []):
                return name
        return None
    
    # ==========================================
    # BAN İŞLEMLERİ
    # ==========================================
    
    def ban_user(self, user_id: int, reason: str = None) -> bool:
        """Kullanıcıyı banla"""
        return self.update_user(user_id, {
            "is_banned": True,
            "ban_reason": reason,
            "banned_at": datetime.utcnow().isoformat()
        })
    
    def unban_user(self, user_id: int) -> bool:
        """Kullanıcının banını kaldır"""
        return self.update_user(user_id, {
            "is_banned": False,
            "ban_reason": None,
            "banned_at": None
        })
    
    def is_banned(self, user_id: int) -> bool:
        """Kullanıcının banlı olup olmadığını kontrol et"""
        user = self.get_user(user_id)
        return user.get("is_banned", False) if user else False
    
    def get_banned_users(self) -> List[Dict]:
        """Banlı kullanıcıları getir"""
        users = self._load_json(config.USERS_FILE) or {}
        return [u for u in users.values() if u.get("is_banned")]
    
    # ==========================================
    # SUDO İŞLEMLERİ
    # ==========================================
    
    def add_sudo(self, user_id: int) -> bool:
        """Sudo ekle"""
        return self.update_user(user_id, {"is_sudo": True})
    
    def remove_sudo(self, user_id: int) -> bool:
        """Sudo kaldır"""
        return self.update_user(user_id, {"is_sudo": False})
    
    def is_sudo(self, user_id: int) -> bool:
        """Sudo kontrolü"""
        if user_id == config.OWNER_ID:
            return True
        user = self.get_user(user_id)
        return user.get("is_sudo", False) if user else False
    
    def get_sudos(self) -> List[Dict]:
        """Sudo listesi"""
        users = self._load_json(config.USERS_FILE) or {}
        return [u for u in users.values() if u.get("is_sudo")]
    
    # ==========================================
    # AYARLAR İŞLEMLERİ
    # ==========================================
    
    def get_settings(self) -> Dict:
        """Bot ayarlarını getir"""
        settings = self._load_json(config.SETTINGS_FILE)
        if settings:
            return settings
        return config.DEFAULT_SETTINGS.copy()
    
    def update_settings(self, data: Dict) -> bool:
        """Bot ayarlarını güncelle"""
        settings = self.get_settings()
        settings.update(data)
        return self._save_json(config.SETTINGS_FILE, settings)
    
    # ==========================================
    # İSTATİSTİK İŞLEMLERİ
    # ==========================================
    
    def get_stats(self) -> Dict:
        """İstatistikleri getir"""
        users = self._load_json(config.USERS_FILE) or {}
        plugins = self._load_json(config.PLUGINS_FILE) or {}
        
        return {
            "total_users": len(users),
            "logged_in_users": len([u for u in users.values() if u.get("is_logged_in")]),
            "banned_users": len([u for u in users.values() if u.get("is_banned")]),
            "sudo_users": len([u for u in users.values() if u.get("is_sudo")]),
            "total_plugins": len(plugins),
            "public_plugins": len([p for p in plugins.values() if p.get("is_public")]),
            "private_plugins": len([p for p in plugins.values() if not p.get("is_public")]),
        }
    
    # ==========================================
    # TEPKİ SİSTEMİ
    # ==========================================
    
    def get_user_reaction(self, reaction_key: str, user_id: int) -> Optional[str]:
        """Kullanıcının tepkisini getir"""
        reactions_file = os.path.join(config.DATA_DIR, "reactions.json")
        reactions = self._load_json(reactions_file) or {}
        key = f"{reaction_key}_{user_id}"
        return reactions.get(key)
    
    def set_user_reaction(self, reaction_key: str, user_id: int, emoji: Optional[str]) -> bool:
        """Kullanıcının tepkisini kaydet veya sil"""
        reactions_file = os.path.join(config.DATA_DIR, "reactions.json")
        reactions = self._load_json(reactions_file) or {}
        key = f"{reaction_key}_{user_id}"
        
        if emoji is None:
            reactions.pop(key, None)
        else:
            reactions[key] = emoji
        
        return self._save_json(reactions_file, reactions)


# Global LocalStorage instance
local_db = LocalStorage()
