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
from typing import Optional, Dict, List, Tuple
from telethon import TelegramClient
import config
from database import database as db

class PluginManager:
    """Plugin yönetim sistemi"""
    
    def __init__(self):
        self.loaded_plugins: Dict[str, Dict] = {}
        self.user_active_plugins: Dict[int, Dict[str, any]] = {}
        self._retry_count: Dict[str, int] = {}
        
        # Uyumluluk katmanını hazırla
        self._setup_compatibility()
    
    def _setup_compatibility(self):
        """Eski userbot pluginleri için uyumluluk katmanını kur"""
        try:
            # userbot_compat modülünü 'userbot' olarak sys.modules'a ekle
            import userbot_compat
            import userbot_compat.events
            import userbot_compat.cmdhelp
            import userbot_compat.utils
            
            # 'userbot' ismiyle erişilebilir yap
            sys.modules['userbot'] = userbot_compat
            sys.modules['userbot.events'] = userbot_compat.events
            sys.modules['userbot.cmdhelp'] = userbot_compat.cmdhelp
            sys.modules['userbot.utils'] = userbot_compat.utils
            
            print("[PLUGIN] ✅ Uyumluluk katmanı hazır")
        except Exception as e:
            print(f"[PLUGIN] ⚠️ Uyumluluk katmanı hatası: {e}")
    
    def install_package(self, package_name: str) -> Tuple[bool, str]:
        """Pip ile paket kur"""
        try:
            clean_name = package_name.split('>=')[0].split('==')[0].split('[')[0].strip()
            
            # userbot paketini kurmaya çalışma - bu bizim uyumluluk katmanımız
            if clean_name.lower() == 'userbot':
                return True, "userbot uyumluluk katmanı zaten mevcut"
            
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
    
    def check_and_install_imports(self, file_path: str) -> Tuple[bool, List[str], List[str]]:
        """Plugin dosyasındaki import'ları kontrol et ve eksik olanları kur"""
        installed = []
        failed = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
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
            
            # Standart kütüphane ve yerleşik modüller
            stdlib_modules = {
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
                # Proje modülleri ve uyumluluk
                'telethon', 'pyrogram', 'motor', 'pymongo', 'dotenv', 'git',
                'userbot', 'userbot_compat', 'config', 'database', 'utils'
            }
            
            # Modül adı -> pip paket adı eşleştirmesi
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
                'google': 'google-api-python-client',
                'tweepy': 'tweepy',
                'discord': 'discord.py',
                'flask': 'flask',
                'fastapi': 'fastapi',
                'uvicorn': 'uvicorn',
                'jinja2': 'Jinja2',
                'markdown': 'markdown',
                'newspaper': 'newspaper3k',
                'feedparser': 'feedparser',
                'fake_useragent': 'fake-useragent',
                'cloudscraper': 'cloudscraper',
                'selenium': 'selenium',
                'playwright': 'playwright',
                'undetected_chromedriver': 'undetected-chromedriver',
            }
            
            for module_name in imports:
                if module_name in stdlib_modules:
                    continue
                
                try:
                    importlib.import_module(module_name)
                except ImportError:
                    package_name = package_mapping.get(module_name, module_name)
                    
                    print(f"[PLUGIN] ⚠️ '{module_name}' modülü bulunamadı, '{package_name}' kuruluyor...")
                    
                    success, msg = self.install_package(package_name)
                    
                    if success:
                        installed.append(package_name)
                        try:
                            importlib.invalidate_caches()
                            importlib.import_module(module_name)
                        except ImportError:
                            pass
                    else:
                        failed.append(f"{package_name}: {msg}")
            
            return len(failed) == 0, installed, failed
            
        except SyntaxError as e:
            return False, [], [f"Sözdizimi hatası: {e}"]
        except Exception as e:
            return False, [], [f"Hata: {e}"]
    
    def extract_requirements_from_file(self, file_path: str) -> List[str]:
        """Plugin dosyasındaki requirements yorumunu çıkar"""
        requirements = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('# requires:') or line.startswith('# requirements:'):
                        packages = line.split(':', 1)[1].strip().split(',')
                        requirements.extend([p.strip() for p in packages if p.strip()])
                    if not line.startswith('#') and line:
                        break
        except:
            pass
        
        return requirements
    
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
            
            tree = ast.parse(content)
            if (tree.body and isinstance(tree.body[0], ast.Expr) and 
                isinstance(tree.body[0].value, ast.Constant)):
                info["description"] = tree.body[0].value.value.strip()
            
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
            print(f"[PLUGIN] Bilgi çıkarma hatası ({file_path}): {e}")
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
        
        # Retry kontrolü
        retry_key = f"{user_id}_{plugin_name}"
        if retry_key in self._retry_count and self._retry_count[retry_key] >= 3:
            del self._retry_count[retry_key]
            return False, "❌ Çok fazla kurulum denemesi. Plugin uyumsuz olabilir."
        
        plugin = await db.get_plugin(plugin_name)
        if not plugin:
            return False, f"`{plugin_name}` adında bir plugin bulunamadı"
        
        if not plugin.get("is_active"):
            return False, f"`{plugin_name}` şu anda devre dışı"
        
        if not plugin.get("is_public"):
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
            return False, f"Plugin dosyası bulunamadı"
        
        # Uyumluluk katmanını yeniden kur (her plugin için)
        self._setup_compatibility()
        
        # Uyumluluk katmanına client'ı ver
        try:
            from userbot_compat import events as compat_events
            compat_events.set_client(client)
        except:
            pass
        
        status_messages = []
        
        # Requirements kontrol
        requirements = self.extract_requirements_from_file(file_path)
        if requirements:
            for req in requirements:
                if req.lower() == 'userbot':
                    continue
                try:
                    pkg_name = req.split('>=')[0].split('==')[0].strip()
                    importlib.import_module(pkg_name.replace('-', '_'))
                except ImportError:
                    success, msg = self.install_package(req)
                    if success:
                        status_messages.append(f"  ✅ {req} kuruldu")
                    else:
                        return False, f"❌ `{req}` paketi kurulamadı:\n`{msg}`"
        
        # Import kontrolü
        success, installed, failed = self.check_and_install_imports(file_path)
        
        if installed:
            status_messages.append(f"📦 Kurulan paketler: {', '.join(installed)}")
        
        if failed:
            return False, f"❌ Bazı paketler kurulamadı:\n" + "\n".join(failed)
        
        # Plugin'i yükle
        try:
            importlib.invalidate_caches()
            
            spec = importlib.util.spec_from_file_location(
                f"{plugin_name}_{user_id}", 
                file_path
            )
            module = importlib.util.module_from_spec(spec)
            
            module.client = client
            
            spec.loader.exec_module(module)
            
            if hasattr(module, 'register') and callable(module.register):
                module.register(client)
            
            self.user_active_plugins[user_id][plugin_name] = module
            
            user = await db.get_user(user_id)
            active_plugins = user.get("active_plugins", []) if user else []
            if plugin_name not in active_plugins:
                active_plugins.append(plugin_name)
                await db.update_user(user_id, {"active_plugins": active_plugins})
            
            # Retry sayacını temizle
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
            
            # userbot için özel işlem - kurulum yapma, uyumluluk katmanı var
            if missing_module.lower() == 'userbot':
                self._setup_compatibility()
                self._retry_count[retry_key] = self._retry_count.get(retry_key, 0) + 1
                return await self.activate_plugin(user_id, plugin_name, client)
            
            print(f"[PLUGIN] ⚠️ Import hatası: {missing_module}")
            success, msg = self.install_package(missing_module)
            
            if success:
                importlib.invalidate_caches()
                self._retry_count[retry_key] = self._retry_count.get(retry_key, 0) + 1
                return await self.activate_plugin(user_id, plugin_name, client)
            else:
                if retry_key in self._retry_count:
                    del self._retry_count[retry_key]
                return False, f"❌ Eksik modül kurulamadı: `{missing_module}`\n\nHata: `{msg}`"
            
        except Exception as e:
            if retry_key in self._retry_count:
                del self._retry_count[retry_key]
            import traceback
            traceback.print_exc()
            return False, f"❌ Plugin yüklenirken hata:\n`{str(e)}`"
    
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
            
            del self.user_active_plugins[user_id][plugin_name]
            
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
