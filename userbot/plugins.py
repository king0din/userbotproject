# ============================================
# KingTG UserBot Service - Plugin System
# ============================================

import os
import re
import ast
import importlib.util
import sys
from typing import Optional, Dict, List, Tuple
from telethon import TelegramClient
import config
from database import database as db

class PluginManager:
    """Plugin yönetim sistemi"""
    
    def __init__(self):
        self.loaded_plugins: Dict[str, Dict] = {}  # plugin_name -> plugin_info
        self.user_active_plugins: Dict[int, Dict[str, any]] = {}  # user_id -> {plugin_name -> module}
    
    def extract_plugin_info(self, file_path: str) -> Dict:
        """Plugin dosyasından bilgileri çıkar"""
        info = {
            "name": os.path.basename(file_path).replace('.py', ''),
            "commands": [],
            "description": "",
            "author": "",
            "version": "1.0.0",
            "requirements": []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Docstring'den açıklama çıkar
            tree = ast.parse(content)
            if (tree.body and isinstance(tree.body[0], ast.Expr) and 
                isinstance(tree.body[0].value, ast.Constant)):
                info["description"] = tree.body[0].value.value.strip()
            
            # Komutları bul (pattern parametresinden)
            patterns = re.findall(r"pattern\s*=\s*[rf]?['\"][\^]?\.?(\w+)", content)
            info["commands"] = list(set(patterns))
            
            # Yorum satırlarından bilgi çıkar
            for line in content.split('\n')[:30]:  # İlk 30 satır
                line = line.strip()
                if line.startswith('# author:') or line.startswith('# Author:'):
                    info["author"] = line.split(':', 1)[1].strip()
                elif line.startswith('# version:') or line.startswith('# Version:'):
                    info["version"] = line.split(':', 1)[1].strip()
                elif line.startswith('# requires:') or line.startswith('# requirements:'):
                    reqs = line.split(':', 1)[1].strip().split(',')
                    info["requirements"] = [r.strip() for r in reqs if r.strip()]
                elif line.startswith('# description:') or line.startswith('# Description:'):
                    if not info["description"]:
                        info["description"] = line.split(':', 1)[1].strip()
            
            return info
            
        except Exception as e:
            print(f"[PLUGIN] Bilgi çıkarma hatası ({file_path}): {e}")
            return info
    
    async def register_plugin(self, file_path: str, is_public: bool = True,
                             allowed_users: List[int] = None) -> Tuple[bool, str]:
        """Yeni plugin kaydet"""
        if not os.path.exists(file_path):
            return False, "Dosya bulunamadı"
        
        # Plugin bilgilerini çıkar
        info = self.extract_plugin_info(file_path)
        plugin_name = info["name"]
        
        # Aynı isimde plugin var mı kontrol et
        existing = await db.get_plugin(plugin_name)
        if existing:
            return False, f"`{plugin_name}` adında bir plugin zaten mevcut"
        
        # Komut çakışması kontrol et
        for cmd in info["commands"]:
            existing_plugin = await db.check_command_exists(cmd)
            if existing_plugin:
                return False, f"`.{cmd}` komutu `{existing_plugin}` plugininde zaten mevcut"
        
        # Plugin dosyasını plugins klasörüne kopyala
        dest_path = os.path.join(config.PLUGINS_DIR, os.path.basename(file_path))
        if file_path != dest_path:
            import shutil
            shutil.copy2(file_path, dest_path)
        
        # Veritabanına kaydet
        await db.add_plugin(
            name=plugin_name,
            filename=os.path.basename(file_path),
            description=info["description"],
            commands=info["commands"],
            is_public=is_public,
            allowed_users=allowed_users or []
        )
        
        self.loaded_plugins[plugin_name] = info
        
        return True, f"✅ `{plugin_name}` başarıyla kaydedildi!\n\n" \
                     f"📝 Açıklama: {info['description'] or 'Yok'}\n" \
                     f"🔧 Komutlar: {', '.join([f'`.{c}`' for c in info['commands']]) or 'Yok'}\n" \
                     f"🔓 Erişim: {'Genel' if is_public else 'Özel'}"
    
    async def unregister_plugin(self, plugin_name: str) -> Tuple[bool, str]:
        """Plugin kaydını sil"""
        plugin = await db.get_plugin(plugin_name)
        if not plugin:
            return False, f"`{plugin_name}` adında bir plugin bulunamadı"
        
        # Tüm kullanıcılardan deaktif et
        for user_id in list(self.user_active_plugins.keys()):
            if plugin_name in self.user_active_plugins[user_id]:
                await self.deactivate_plugin(user_id, plugin_name)
        
        # Dosyayı sil
        file_path = os.path.join(config.PLUGINS_DIR, plugin["filename"])
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Veritabanından sil
        await db.delete_plugin(plugin_name)
        
        if plugin_name in self.loaded_plugins:
            del self.loaded_plugins[plugin_name]
        
        return True, f"✅ `{plugin_name}` silindi"
    
    async def activate_plugin(self, user_id: int, plugin_name: str, 
                             client: TelegramClient) -> Tuple[bool, str]:
        """Kullanıcı için plugin aktif et"""
        # Plugin var mı?
        plugin = await db.get_plugin(plugin_name)
        if not plugin:
            return False, f"`{plugin_name}` adında bir plugin bulunamadı"
        
        # Plugin aktif mi?
        if not plugin.get("is_active"):
            return False, f"`{plugin_name}` şu anda devre dışı"
        
        # Erişim kontrolü
        if not plugin.get("is_public"):
            if user_id not in plugin.get("allowed_users", []):
                return False, f"`{plugin_name}` pluginine erişim yetkiniz yok"
        
        # Kısıtlama kontrolü
        if user_id in plugin.get("restricted_users", []):
            return False, f"`{plugin_name}` plugini sizin için kısıtlanmış"
        
        # Zaten aktif mi?
        if user_id in self.user_active_plugins:
            if plugin_name in self.user_active_plugins[user_id]:
                return False, f"`{plugin_name}` zaten aktif"
        else:
            self.user_active_plugins[user_id] = {}
        
        # Plugin'i yükle
        file_path = os.path.join(config.PLUGINS_DIR, plugin["filename"])
        if not os.path.exists(file_path):
            return False, f"Plugin dosyası bulunamadı"
        
        try:
            # Modülü yükle
            spec = importlib.util.spec_from_file_location(
                f"{plugin_name}_{user_id}", 
                file_path
            )
            module = importlib.util.module_from_spec(spec)
            
            # Client'ı modüle ekle
            module.client = client
            
            # Modülü çalıştır
            spec.loader.exec_module(module)
            
            # Register fonksiyonu varsa çağır
            if hasattr(module, 'register') and callable(module.register):
                module.register(client)
            
            # Kaydet
            self.user_active_plugins[user_id][plugin_name] = module
            
            # Kullanıcı veritabanını güncelle
            user = await db.get_user(user_id)
            active_plugins = user.get("active_plugins", []) if user else []
            if plugin_name not in active_plugins:
                active_plugins.append(plugin_name)
                await db.update_user(user_id, {"active_plugins": active_plugins})
            
            return True, f"✅ `{plugin_name}` aktif edildi!\n\n" \
                        f"📝 {plugin.get('description', 'Açıklama yok')}\n" \
                        f"🔧 Komutlar: {', '.join([f'`.{c}`' for c in plugin.get('commands', [])])}"
            
        except Exception as e:
            return False, f"Plugin yüklenirken hata: `{str(e)}`"
    
    async def deactivate_plugin(self, user_id: int, plugin_name: str) -> Tuple[bool, str]:
        """Kullanıcı için plugin deaktif et"""
        if user_id not in self.user_active_plugins:
            return False, f"Aktif plugininiz bulunmuyor"
        
        if plugin_name not in self.user_active_plugins[user_id]:
            return False, f"`{plugin_name}` zaten aktif değil"
        
        try:
            # Modülü kaldır
            module = self.user_active_plugins[user_id][plugin_name]
            
            # Unregister fonksiyonu varsa çağır
            if hasattr(module, 'unregister') and callable(module.unregister):
                try:
                    module.unregister()
                except:
                    pass
            
            del self.user_active_plugins[user_id][plugin_name]
            
            # Kullanıcı veritabanını güncelle
            user = await db.get_user(user_id)
            active_plugins = user.get("active_plugins", []) if user else []
            if plugin_name in active_plugins:
                active_plugins.remove(plugin_name)
                await db.update_user(user_id, {"active_plugins": active_plugins})
            
            return True, f"✅ `{plugin_name}` deaktif edildi"
            
        except Exception as e:
            return False, f"Plugin deaktif edilirken hata: `{str(e)}`"
    
    async def get_user_plugins(self, user_id: int) -> Dict:
        """Kullanıcının plugin durumunu getir"""
        user = await db.get_user(user_id)
        accessible = await db.get_user_accessible_plugins(user_id)
        active = user.get("active_plugins", []) if user else []
        
        return {
            "accessible": accessible,
            "active": active,
            "inactive": [p for p in accessible if p["name"] not in active]
        }
    
    async def restore_user_plugins(self, user_id: int, client: TelegramClient) -> int:
        """Kullanıcının önceden aktif pluginlerini geri yükle"""
        user = await db.get_user(user_id)
        if not user:
            return 0
        
        active_plugins = user.get("active_plugins", [])
        restored = 0
        
        for plugin_name in active_plugins:
            success, _ = await self.activate_plugin(user_id, plugin_name, client)
            if success:
                restored += 1
        
        return restored
    
    async def get_all_plugins_formatted(self, user_id: int = None) -> str:
        """Tüm pluginleri formatlanmış olarak getir"""
        all_plugins = await db.get_all_plugins()
        
        if not all_plugins:
            return "📭 Henüz plugin eklenmemiş."
        
        text = "🔌 **Mevcut Plugin'ler:**\n\n"
        
        public_plugins = [p for p in all_plugins if p.get("is_public")]
        private_plugins = [p for p in all_plugins if not p.get("is_public")]
        
        if public_plugins:
            text += "**🌐 Genel Plugin'ler:**\n"
            for p in public_plugins:
                status = "✅" if p.get("is_active") else "❌"
                cmds = ", ".join([f"`.{c}`" for c in p.get("commands", [])[:3]])
                if len(p.get("commands", [])) > 3:
                    cmds += "..."
                text += f"{status} `{p['name']}` - {cmds}\n"
            text += "\n"
        
        if private_plugins:
            text += "**🔒 Özel Plugin'ler:**\n"
            for p in private_plugins:
                status = "✅" if p.get("is_active") else "❌"
                access = "🔓" if (user_id and user_id in p.get("allowed_users", [])) else "🔐"
                text += f"{status} {access} `{p['name']}`\n"
        
        text += f"\n**Toplam:** {len(all_plugins)} plugin"
        
        return text
    
    def clear_user_plugins(self, user_id: int):
        """Kullanıcının tüm aktif pluginlerini temizle"""
        if user_id in self.user_active_plugins:
            del self.user_active_plugins[user_id]


# Global Plugin Manager instance
plugin_manager = PluginManager()
