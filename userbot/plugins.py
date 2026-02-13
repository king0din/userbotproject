# ============================================
# KingTG UserBot Service - Plugin System
# ============================================

import os
import re
import ast
import importlib
import importlib.util
import subprocess
import sys
import tempfile
import asyncio
from typing import Optional, Dict, List, Tuple, Set
from telethon import TelegramClient
import config
from database import database as db

class PluginManager:
    """Plugin yönetim sistemi"""
    
    def __init__(self):
        self.loaded_plugins: Dict[str, Dict] = {}
        self.user_active_plugins: Dict[int, Dict[str, any]] = {}
        self._retry_count: Dict[str, int] = {}
        self._compat_installed = False
        self._installed_packages: Set[str] = set()  # Kurulu paket cache
        self._packages_checked = False
    
    async def preinstall_all_dependencies(self):
        """Tüm pluginlerin bağımlılıklarını önceden kur"""
        print("[PLUGIN] 📦 Bağımlılıklar kontrol ediliyor...")
        
        all_plugins = await db.get_all_plugins()
        if not all_plugins:
            return
        
        all_imports = set()
        
        # Tüm pluginlerin import'larını topla
        for plugin in all_plugins:
            filename = plugin.get("filename", f"{plugin['name']}.py")
            filepath = os.path.join(config.PLUGINS_DIR, filename)
            
            if not os.path.exists(filepath):
                continue
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            module_name = alias.name.split('.')[0]
                            all_imports.add(module_name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            module_name = node.module.split('.')[0]
                            all_imports.add(module_name)
            except:
                continue
        
        # Standart kütüphaneler ve zaten kurulu olanları atla
        skip_modules = {
            'os', 'sys', 'time', 'datetime', 'json', 'random', 'math', 're',
            'asyncio', 'subprocess', 'shutil', 'glob', 'pathlib', 'tempfile',
            'base64', 'hashlib', 'uuid', 'io', 'collections', 'itertools',
            'functools', 'typing', 'abc', 'copy', 'pickle', 'sqlite3',
            'urllib', 'http', 'html', 'xml', 'email', 'mimetypes',
            'logging', 'traceback', 'inspect', 'importlib', 'ast',
            'struct', 'codecs', 'string', 'textwrap', 'difflib',
            'threading', 'multiprocessing', 'concurrent', 'queue',
            'socket', 'ssl', 'select', 'selectors', 'signal',
            'contextlib', 'weakref', 'gc', 'platform', 'locale',
            'getpass', 'gettext', 'argparse', 'configparser',
            'csv', 'zipfile', 'tarfile', 'gzip', 'bz2', 'lzma',
            'secrets', 'statistics', 'decimal', 'fractions',
            'numbers', 'cmath', 'array', 'bisect', 'heapq',
            'enum', 'graphlib', 'dataclasses', 'contextvars',
            '__future__', 'builtins', 'warnings', 'atexit',
            'telethon', 'pyrogram', 'motor', 'pymongo', 'dotenv', 'git',
            'userbot', 'userbot_compat', 'config', 'database', 'utils',
            'seduserbot', 'asena'
        }
        
        package_mapping = {
            'cv2': 'opencv-python',
            'PIL': 'Pillow',
            'sklearn': 'scikit-learn',
            'yaml': 'pyyaml',
            'bs4': 'beautifulsoup4',
        }
        
        to_install = []
        
        for module in all_imports:
            if module in skip_modules:
                continue
            
            # Zaten kurulu mu kontrol et
            try:
                importlib.import_module(module)
                self._installed_packages.add(module)
            except ImportError:
                package_name = package_mapping.get(module, module)
                to_install.append(package_name)
        
        # Eksik paketleri toplu kur
        if to_install:
            unique_packages = list(set(to_install))
            print(f"[PLUGIN] 📦 {len(unique_packages)} paket kuruluyor: {', '.join(unique_packages)}")
            
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install"] + unique_packages + ["-q", "--disable-pip-version-check"],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode == 0:
                    print(f"[PLUGIN] ✅ Tüm bağımlılıklar kuruldu")
                    for pkg in unique_packages:
                        self._installed_packages.add(pkg)
                else:
                    print(f"[PLUGIN] ⚠️ Bazı paketler kurulamadı")
            except Exception as e:
                print(f"[PLUGIN] ⚠️ Paket kurulum hatası: {e}")
        else:
            print("[PLUGIN] ✅ Tüm bağımlılıklar mevcut")
        
        self._packages_checked = True
    
    def _setup_compatibility(self):
        """Eski userbot pluginleri için uyumluluk katmanını kur"""
        if self._compat_installed:
            return
        
        try:
            import userbot_compat
            import userbot_compat.events
            import userbot_compat.cmdhelp
            import userbot_compat.utils
            
            sys.modules['seduserbot'] = userbot_compat
            sys.modules['seduserbot.events'] = userbot_compat.events
            sys.modules['seduserbot.cmdhelp'] = userbot_compat.cmdhelp
            sys.modules['seduserbot.utils'] = userbot_compat.utils
            
            sys.modules['asena'] = userbot_compat
            sys.modules['asena.events'] = userbot_compat.events
            
            self._compat_installed = True
            print("[PLUGIN] ✅ Uyumluluk katmanı hazır")
        except Exception as e:
            print(f"[PLUGIN] ⚠️ Uyumluluk katmanı hatası: {e}")
    
    def _patch_plugin_content(self, content: str) -> str:
        """Plugin içeriğindeki eski import'ları düzelt"""
        # from userbot import ... -> from userbot_compat import ...
        content = re.sub(
            r'^from userbot import',
            'from userbot_compat import',
            content,
            flags=re.MULTILINE
        )
        
        # from userbot.xxx import ... -> from userbot_compat.xxx import ...
        content = re.sub(
            r'^from userbot\.',
            'from userbot_compat.',
            content,
            flags=re.MULTILINE
        )
        
        # import userbot -> import userbot_compat as userbot
        content = re.sub(
            r'^import userbot$',
            'import userbot_compat as userbot',
            content,
            flags=re.MULTILINE
        )
        
        return content
    
    def install_package(self, package_name: str) -> Tuple[bool, str]:
        """Pip ile paket kur"""
        try:
            clean_name = package_name.split('>=')[0].split('==')[0].split('[')[0].strip()
            
            if clean_name.lower() in ['userbot', 'userbot_compat']:
                return True, "userbot uyumluluk katmanı mevcut"
            
            print(f"[PLUGIN] 📦 {clean_name} kuruluyor...")
            
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package_name, "-q", "--disable-pip-version-check"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                print(f"[PLUGIN] ✅ {clean_name} kuruldu")
                return True, f"{clean_name} kuruldu"
            else:
                print(f"[PLUGIN] ❌ {clean_name} kurulamadı: {result.stderr}")
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            return False, "Kurulum zaman aşımına uğradı"
        except Exception as e:
            return False, str(e)
    
    def check_and_install_imports(self, content: str) -> Tuple[bool, List[str], List[str]]:
        """Plugin içeriğindeki import'ları kontrol et ve eksik olanları kur"""
        installed = []
        failed = []
        
        try:
            tree = ast.parse(content)
            imports = set()
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split('.')[0]
                        imports.add(module_name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module.split('.')[0]
                        imports.add(module_name)
            
            skip_modules = {
                'os', 'sys', 'time', 'datetime', 'json', 'random', 'math', 're',
                'asyncio', 'subprocess', 'shutil', 'glob', 'pathlib', 'tempfile',
                'base64', 'hashlib', 'uuid', 'io', 'collections', 'itertools',
                'functools', 'typing', 'abc', 'copy', 'pickle', 'sqlite3',
                'urllib', 'http', 'html', 'xml', 'email', 'mimetypes',
                'logging', 'traceback', 'inspect', 'importlib', 'ast',
                'struct', 'codecs', 'string', 'textwrap', 'difflib',
                'threading', 'multiprocessing', 'concurrent', 'queue',
                'socket', 'ssl', 'select', 'selectors', 'signal',
                'contextlib', 'weakref', 'gc', 'platform', 'locale',
                'getpass', 'gettext', 'argparse', 'configparser',
                'csv', 'zipfile', 'tarfile', 'gzip', 'bz2', 'lzma',
                'secrets', 'statistics', 'decimal', 'fractions',
                'numbers', 'cmath', 'array', 'bisect', 'heapq',
                'enum', 'graphlib', 'dataclasses', 'contextvars',
                '__future__', 'builtins', 'warnings', 'atexit',
                'telethon', 'pyrogram', 'motor', 'pymongo', 'dotenv', 'git',
                'userbot', 'userbot_compat', 'config', 'database', 'utils',
                'seduserbot', 'asena'
            }
            
            package_mapping = {
                'cv2': 'opencv-python',
                'PIL': 'Pillow',
                'sklearn': 'scikit-learn',
                'yaml': 'pyyaml',
                'bs4': 'beautifulsoup4',
                'dotenv': 'python-dotenv',
                'gtts': 'gTTS',
                'edge_tts': 'edge-tts',
                'pydub': 'pydub',
                'mutagen': 'mutagen',
                'aiohttp': 'aiohttp',
                'aiofiles': 'aiofiles',
                'requests': 'requests',
                'httpx': 'httpx',
                'numpy': 'numpy',
                'pandas': 'pandas',
                'matplotlib': 'matplotlib',
                'scipy': 'scipy',
                'tqdm': 'tqdm',
                'colorama': 'colorama',
                'rich': 'rich',
                'emoji': 'emoji',
                'qrcode': 'qrcode',
                'barcode': 'python-barcode',
                'googletrans': 'googletrans==3.1.0a0',
                'translate': 'translate',
                'wikipedia': 'wikipedia',
                'speedtest': 'speedtest-cli',
                'psutil': 'psutil',
                'pytz': 'pytz',
                'dateutil': 'python-dateutil',
                'humanize': 'humanize',
                'validators': 'validators',
                'phonenumbers': 'phonenumbers',
                'pycountry': 'pycountry',
                'forex_python': 'forex-python',
                'cryptocompare': 'cryptocompare',
                'yfinance': 'yfinance',
                'instaloader': 'instaloader',
                'yt_dlp': 'yt-dlp',
                'pytube': 'pytube',
                'spotipy': 'spotipy',
                'lyricsgenius': 'lyricsgenius',
                'ffmpeg': 'ffmpeg-python',
                'speech_recognition': 'SpeechRecognition',
                'openai': 'openai',
                'anthropic': 'anthropic',
            }
            
            for module_name in imports:
                if module_name in skip_modules:
                    continue
                
                try:
                    importlib.import_module(module_name)
                except ImportError:
                    package_name = package_mapping.get(module_name, module_name)
                    
                    print(f"[PLUGIN] ⚠️ '{module_name}' bulunamadı, '{package_name}' kuruluyor...")
                    
                    success, msg = self.install_package(package_name)
                    
                    if success:
                        installed.append(package_name)
                        importlib.invalidate_caches()
                    else:
                        failed.append(f"{package_name}: {msg}")
            
            return len(failed) == 0, installed, failed
            
        except SyntaxError as e:
            return False, [], [f"Sözdizimi hatası: {e}"]
        except Exception as e:
            return False, [], [f"Hata: {e}"]
    
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
            
            try:
                tree = ast.parse(content)
                if (tree.body and isinstance(tree.body[0], ast.Expr) and 
                    isinstance(tree.body[0].value, ast.Constant)):
                    info["description"] = tree.body[0].value.value.strip()
            except:
                pass
            
            patterns = re.findall(r"pattern\s*=\s*[rf]?['\"][\^]?\.?(\w+)", content)
            info["commands"] = list(set(patterns))
            
            for line in content.split('\n')[:30]:
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
            print(f"[PLUGIN] Bilgi çıkarma hatası: {e}")
            return info
    
    async def register_plugin(self, file_path: str, is_public: bool = True,
                             allowed_users: List[int] = None) -> Tuple[bool, str]:
        """Yeni plugin kaydet"""
        if not os.path.exists(file_path):
            return False, "Dosya bulunamadı"
        
        info = self.extract_plugin_info(file_path)
        plugin_name = info["name"]
        
        existing = await db.get_plugin(plugin_name)
        if existing:
            return False, f"`{plugin_name}` adında bir plugin zaten mevcut"
        
        for cmd in info["commands"]:
            existing_plugin = await db.check_command_exists(cmd)
            if existing_plugin:
                return False, f"`.{cmd}` komutu `{existing_plugin}` plugininde zaten mevcut"
        
        dest_path = os.path.join(config.PLUGINS_DIR, os.path.basename(file_path))
        if file_path != dest_path:
            import shutil
            shutil.copy2(file_path, dest_path)
        
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
        
        for user_id in list(self.user_active_plugins.keys()):
            if plugin_name in self.user_active_plugins[user_id]:
                await self.deactivate_plugin(user_id, plugin_name)
        
        file_path = os.path.join(config.PLUGINS_DIR, plugin["filename"])
        if os.path.exists(file_path):
            os.remove(file_path)
        
        await db.delete_plugin(plugin_name)
        
        if plugin_name in self.loaded_plugins:
            del self.loaded_plugins[plugin_name]
        
        return True, f"✅ `{plugin_name}` silindi"
    
    async def activate_plugin(self, user_id: int, plugin_name: str, 
                             client: TelegramClient) -> Tuple[bool, str]:
        """Kullanıcı için plugin aktif et"""
        
        retry_key = f"{user_id}_{plugin_name}"
        if retry_key in self._retry_count and self._retry_count[retry_key] >= 3:
            del self._retry_count[retry_key]
            return False, "❌ Plugin yüklenemedi. Uyumsuz olabilir."
        
        plugin = await db.get_plugin(plugin_name)
        if not plugin:
            return False, f"`{plugin_name}` adında bir plugin bulunamadı"
        
        if not plugin.get("is_active", True):
            return False, f"`{plugin_name}` şu anda devre dışı"
        
        if not plugin.get("is_public", True):
            if user_id not in plugin.get("allowed_users", []):
                return False, f"`{plugin_name}` pluginine erişim yetkiniz yok"
        
        if user_id in plugin.get("restricted_users", []):
            return False, f"`{plugin_name}` plugini sizin için kısıtlanmış"
        
        if user_id in self.user_active_plugins:
            if plugin_name in self.user_active_plugins[user_id]:
                return False, f"`{plugin_name}` zaten aktif"
        else:
            self.user_active_plugins[user_id] = {}
        
        file_path = os.path.join(config.PLUGINS_DIR, plugin["filename"])
        if not os.path.exists(file_path):
            return False, f"Plugin dosyası bulunamadı: {plugin['filename']}"
        
        # Uyumluluk katmanını kur
        self._setup_compatibility()
        
        # Plugin dosyasını oku
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
        except Exception as e:
            return False, f"❌ Dosya okunamadı: {e}"
        
        # Import'ları patch'le
        patched_content = self._patch_plugin_content(original_content)
        
        # Bağımlılıkları kontrol et
        success, installed, failed = self.check_and_install_imports(patched_content)
        
        status_messages = []
        if installed:
            status_messages.append(f"📦 Kurulan: {', '.join(installed)}")
        
        if failed:
            return False, f"❌ Paket kurulamadı:\n" + "\n".join(failed)
        
        # Plugin'i yükle - exec kullanarak
        try:
            # userbot_compat'ı hazırla
            try:
                from userbot_compat import events as compat_events
                compat_events.set_client(client)
            except Exception as e:
                print(f"[PLUGIN] compat_events hatası: {e}")
            
            # Modül için namespace oluştur
            module_name = f"plugin_{plugin_name}_{user_id}"
            
            # Yeni modül oluştur
            import types
            module = types.ModuleType(module_name)
            module.__file__ = file_path
            module.__name__ = module_name
            module.client = client
            
            # Modülü sys.modules'a ekle
            sys.modules[module_name] = module
            
            # Kodu çalıştır
            exec(compile(patched_content, file_path, 'exec'), module.__dict__)
            
            # Register fonksiyonu varsa çağır
            if hasattr(module, 'register') and callable(module.register):
                module.register(client)
            
            self.user_active_plugins[user_id][plugin_name] = module
            
            user = await db.get_user(user_id)
            active_plugins = user.get("active_plugins", []) if user else []
            if plugin_name not in active_plugins:
                active_plugins.append(plugin_name)
                await db.update_user(user_id, {"active_plugins": active_plugins})
            
            if retry_key in self._retry_count:
                del self._retry_count[retry_key]
            
            result_msg = f"✅ `{plugin_name}` aktif edildi!\n\n"
            result_msg += f"📝 {plugin.get('description', 'Açıklama yok')}\n"
            result_msg += f"🔧 Komutlar: {', '.join([f'`.{c}`' for c in plugin.get('commands', [])])}"
            
            if status_messages:
                result_msg += "\n\n" + "\n".join(status_messages)
            
            return True, result_msg
            
        except ImportError as e:
            error_str = str(e)
            
            if "No module named" in error_str:
                if "'" in error_str:
                    missing_module = error_str.split("'")[1].split('.')[0]
                else:
                    missing_module = error_str.replace("No module named ", "").strip()
            else:
                missing_module = error_str
            
            if missing_module.lower() == 'userbot':
                self._retry_count[retry_key] = self._retry_count.get(retry_key, 0) + 1
                return await self.activate_plugin(user_id, plugin_name, client)
            
            print(f"[PLUGIN] Import hatası: {missing_module}")
            success, msg = self.install_package(missing_module)
            
            if success:
                importlib.invalidate_caches()
                self._retry_count[retry_key] = self._retry_count.get(retry_key, 0) + 1
                return await self.activate_plugin(user_id, plugin_name, client)
            else:
                if retry_key in self._retry_count:
                    del self._retry_count[retry_key]
                return False, f"❌ Modül kurulamadı: `{missing_module}`"
            
        except Exception as e:
            if retry_key in self._retry_count:
                del self._retry_count[retry_key]
            import traceback
            traceback.print_exc()
            return False, f"❌ Plugin hatası:\n`{str(e)}`"
    
    async def deactivate_plugin(self, user_id: int, plugin_name: str) -> Tuple[bool, str]:
        """Kullanıcı için plugin deaktif et"""
        if user_id not in self.user_active_plugins:
            return False, f"Aktif plugininiz bulunmuyor"
        
        if plugin_name not in self.user_active_plugins[user_id]:
            return False, f"`{plugin_name}` zaten aktif değil"
        
        try:
            module = self.user_active_plugins[user_id][plugin_name]
            
            if hasattr(module, 'unregister') and callable(module.unregister):
                try:
                    module.unregister()
                except:
                    pass
            
            # sys.modules'dan kaldır
            module_name = f"plugin_{plugin_name}_{user_id}"
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            del self.user_active_plugins[user_id][plugin_name]
            
            user = await db.get_user(user_id)
            active_plugins = user.get("active_plugins", []) if user else []
            if plugin_name in active_plugins:
                active_plugins.remove(plugin_name)
                await db.update_user(user_id, {"active_plugins": active_plugins})
            
            return True, f"✅ `{plugin_name}` deaktif edildi"
            
        except Exception as e:
            return False, f"Hata: `{str(e)}`"
    
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
        """Kullanıcının pluginlerini geri yükle - PARALEL"""
        user = await db.get_user(user_id)
        if not user:
            return 0
        
        active_plugins = user.get("active_plugins", [])
        if not active_plugins:
            return 0
        
        async def load_single_plugin(plugin_name):
            """Tek bir plugini yükle"""
            try:
                success, msg = await self.activate_plugin(user_id, plugin_name, client)
                if success:
                    return plugin_name
            except:
                pass
            return None
        
        # Tüm pluginleri paralel yükle
        tasks = [load_single_plugin(p) for p in active_plugins]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        restored = sum(1 for r in results if r is not None and not isinstance(r, Exception))
        return restored
    
    async def get_all_plugins_formatted(self, user_id: int = None) -> str:
        """Tüm pluginleri formatla"""
        all_plugins = await db.get_all_plugins()
        
        if not all_plugins:
            return "📭 Henüz plugin eklenmemiş."
        
        text = "🔌 **Mevcut Plugin'ler:**\n\n"
        
        public_plugins = [p for p in all_plugins if p.get("is_public", True)]
        private_plugins = [p for p in all_plugins if not p.get("is_public", True)]
        
        if public_plugins:
            text += "**🌐 Genel:**\n"
            for p in public_plugins:
                status = "✅" if p.get("is_active", True) else "❌"
                cmds = ", ".join([f"`.{c}`" for c in p.get("commands", [])[:3]])
                text += f"{status} `{p['name']}` - {cmds}\n"
            text += "\n"
        
        if private_plugins:
            text += "**🔒 Özel:**\n"
            for p in private_plugins:
                status = "✅" if p.get("is_active", True) else "❌"
                text += f"{status} `{p['name']}`\n"
        
        text += f"\n**Toplam:** {len(all_plugins)} plugin"
        
        return text
    
    def clear_user_plugins(self, user_id: int):
        """Kullanıcının pluginlerini temizle"""
        if user_id in self.user_active_plugins:
            for plugin_name in list(self.user_active_plugins[user_id].keys()):
                module_name = f"plugin_{plugin_name}_{user_id}"
                if module_name in sys.modules:
                    del sys.modules[module_name]
            del self.user_active_plugins[user_id]


# Global instance
plugin_manager = PluginManager()
