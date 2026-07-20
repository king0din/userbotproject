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
import asyncio
from typing import Dict, List, Tuple, Set
from telethon import TelegramClient
import config
from database import database as db
from utils.logger import get_logger

log = get_logger(__name__)


class PluginManager:
    """Plugin yönetim sistemi"""
    
    def __init__(self):
        self.loaded_plugins: Dict[str, Dict] = {}
        self.user_active_plugins: Dict[int, Dict[str, any]] = {}
        # Kullanıcı başına kaydedilen handler'lar
        self.user_handlers: Dict[int, Dict[str, List]] = {}
        self._retry_count: Dict[str, int] = {}
        self._compat_installed = False
        self._installed_packages: Set[str] = set()  # Kurulu paket cache
        self._packages_checked = False
        # B1 düzeltmesi: eski stil (@register) pluginler global `_client`
        # okuduğu için, iki kullanıcı aynı anda plugin aktive ederse
        # handler yanlış hesaba bağlanabilir. Bu kilit, `set_client -> exec ->
        # register` kritik bölgesini kullanıcılar arasında atomik tutar.
        self._activation_lock = asyncio.Lock()
    
    async def preinstall_all_dependencies(self):
        """Tüm pluginlerin bağımlılıklarını önceden kur"""
        log.info("Bağımlılıklar kontrol ediliyor...")
        
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
            except Exception:
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
            log.info("%s paket kuruluyor: %s", len(unique_packages), ', '.join(unique_packages))
            
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install"] + unique_packages + ["-q", "--disable-pip-version-check"],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode == 0:
                    log.info("Tüm bağımlılıklar kuruldu")
                    for pkg in unique_packages:
                        self._installed_packages.add(pkg)
                else:
                    log.warning("Bazı paketler kurulamadı")
            except Exception as e:
                log.warning("Paket kurulum hatası: %s", e)
        else:
            log.info("Tüm bağımlılıklar mevcut")
        
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
            log.info("Uyumluluk katmanı hazır")
        except Exception as e:
            log.warning("Uyumluluk katmanı hatası: %s", e)
    
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
            
            # Cache kontrolü - zaten kuruluysa atla
            if clean_name in self._installed_packages:
                return True, f"{clean_name} zaten kurulu"
            
            # Import ile kontrol et
            try:
                importlib.import_module(clean_name)
                self._installed_packages.add(clean_name)
                return True, f"{clean_name} zaten kurulu"
            except ImportError:
                pass
            
            log.info("%s kuruluyor...", clean_name)
            
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package_name, "-q", "--disable-pip-version-check"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                log.info("%s kuruldu", clean_name)
                self._installed_packages.add(clean_name)
                return True, f"{clean_name} kuruldu"
            else:
                log.error("%s kurulamadı: %s", clean_name, result.stderr)
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
                    
                    log.warning("'%s' bulunamadı, '%s' kuruluyor...", module_name, package_name)
                    
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
            except Exception:
                pass
            
            # Komutları pattern string'lerinden çıkar (kaçışlı '\.' ve '(?: )' grupları dahil)
            cmds = []
            for _pm in re.finditer(r"pattern\s*=\s*[rfb]{0,2}(['\"])(.*?)\1", content, re.DOTALL):
                _body = _pm.group(2)
                for _cm in re.finditer(r"\\?\.\(?\??:?(\w+)", _body):
                    _w = _cm.group(1)
                    if _w and _w not in cmds:
                        cmds.append(_w)
            info["commands"] = cmds
            
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
            log.error("Bilgi çıkarma hatası", exc_info=True)
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
        
        # Devre dışı kontrolü
        if plugin.get("is_disabled", False):
            return False, f"⛔ `{plugin_name}` devre dışı bırakılmış"
        
        if not plugin.get("is_active", True):
            return False, f"`{plugin_name}` şu anda devre dışı"
        
        # Premium kapısı: premium plugin ise abonelik/sahip/sudo şartı (TÜM yükleme yolları)
        _is_premium_plugin = False
        try:
            from utils import premium as _prem
            if _prem.plugin_type(plugin_name) == "premium":
                _is_premium_plugin = True
                if not _prem.has_access(user_id, plugin_name):
                    _pc = _prem.get_config(plugin_name) or {}
                    return False, ("💎 `%s` premium bir plugin (%s⭐ / %s gün). Kullanmak için abonelik gerekir." % (plugin_name, _pc.get("stars", 100), _pc.get("days", 30)))
        except Exception:
            pass

        if not _is_premium_plugin and not plugin.get("is_public", True):
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
            # B1: global `_client` yarış durumunu önlemek için, compat kurulumu
            # ve handler kaydını (senkron kritik bölge) kilit altında yap.
            async with self._activation_lock:
                # YARIŞ KORUMASI: "zaten aktif" kontrolü kilit DIŞINDA yapıldığı için,
                # iki eşzamanlı aktivasyon (paralel yükleme) kilidi beklerken ikisi de
                # geçebilir; kilit içinde TEKRAR kontrol et → aksi halde plugin ikinci
                # kez exec edilip handler'lar ÇİFT kaydolur (komutlar iki kez tetiklenir).
                if plugin_name in self.user_active_plugins.get(user_id, {}):
                    return True, f"`{plugin_name}` zaten aktif"

                # userbot_compat'ı hazırla
                try:
                    from userbot_compat import events as compat_events
                    compat_events.set_client(client)
                except Exception:
                    log.error("compat_events hatası", exc_info=True)

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

                # Mevcut handler sayısını kaydet (önceki durum)
                handlers_before = len(client.list_event_handlers())

                # Kodu çalıştır
                exec(compile(patched_content, file_path, 'exec'), module.__dict__)

                # Register fonksiyonu varsa çağır (eski stil)
                if hasattr(module, 'register') and callable(module.register):
                    module.register(client)

                # register_handlers fonksiyonu varsa çağır (yeni stil)
                if hasattr(module, 'register_handlers') and callable(module.register_handlers):
                    try:
                        module.register_handlers(client, user_id)
                        log.info("register_handlers çağrıldı: %s", plugin_name)
                    except Exception:
                        log.error("register_handlers hatası", exc_info=True)

                # Yeni eklenen handler'ları tespit et ve kaydet
                handlers_after = client.list_event_handlers()
                new_handlers = handlers_after[handlers_before:]
            
            # Handler'ları kullanıcı ve plugin bazında sakla
            if user_id not in self.user_handlers:
                self.user_handlers[user_id] = {}
            self.user_handlers[user_id][plugin_name] = new_handlers
            
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
            
            log.error("Import hatası: %s", missing_module, exc_info=True)
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
    
    async def deactivate_plugin(self, user_id: int, plugin_name: str, reason: str = "disable") -> Tuple[bool, str]:
        """Kullanıcı için plugin deaktif et"""
        
        handlers_removed = 0
        module = None
        client = None
        
        # Modülü bul
        if user_id in self.user_active_plugins and plugin_name in self.user_active_plugins[user_id]:
            module = self.user_active_plugins[user_id][plugin_name]
            client = getattr(module, 'client', None)
        
        # Client yoksa smart_session_manager'dan al
        if not client:
            try:
                from userbot.smart_manager import smart_session_manager
                client = smart_session_manager.get_client(user_id)
            except Exception:
                pass
        
        try:
            # Önce unregister_handlers fonksiyonu varsa çağır
            if module and hasattr(module, 'unregister_handlers') and callable(module.unregister_handlers):
                try:
                    module.unregister_handlers(client, user_id)
                    handlers_removed += 1
                    log.info("unregister_handlers çağrıldı: %s", plugin_name)
                except Exception as e:
                    log.error("unregister_handlers hatası", exc_info=True)
            
            # Handler'ları kaldır
            if client:
                module_name = f"plugin_{plugin_name}_{user_id}"
                all_handlers = list(client.list_event_handlers())  # Kopya al
                
                for callback, event in all_handlers:
                    should_remove = False
                    
                    try:
                        # Callback'in modülünü kontrol et
                        cb_module = getattr(callback, '__module__', '') or ''
                        cb_name = getattr(callback, '__name__', '') or ''
                        cb_qualname = getattr(callback, '__qualname__', '') or ''
                        
                        # Bu plugin'e ait mi kontrol et
                        if module_name in cb_module:
                            should_remove = True
                        elif module_name in cb_qualname:
                            should_remove = True
                        elif plugin_name in cb_module and str(user_id) in cb_module:
                            should_remove = True
                        
                        # Modül referansı ile kontrol
                        if module and hasattr(module, cb_name):
                            module_func = getattr(module, cb_name, None)
                            if module_func is callback or module_func == callback:
                                should_remove = True
                        
                        if should_remove:
                            client.remove_event_handler(callback, event)
                            handlers_removed += 1
                            log.info("Handler kaldırıldı: %s - %s", plugin_name, cb_name)
                    except Exception as e:
                        log.error("Handler kontrol hatası", exc_info=True)
                
                # Modüldeki tüm fonksiyonları tara
                if module:
                    for attr_name in dir(module):
                        if attr_name.startswith('_'):
                            continue
                        try:
                            attr = getattr(module, attr_name)
                            if not callable(attr):
                                continue
                            
                            # Yeniden handler listesini al (değişmiş olabilir)
                            current_handlers = list(client.list_event_handlers())
                            for callback, event in current_handlers:
                                try:
                                    if callback is attr:
                                        client.remove_event_handler(callback, event)
                                        handlers_removed += 1
                                        log.info("Handler kaldırıldı (ref): %s - %s", plugin_name, attr_name)
                                except Exception:
                                    pass
                        except Exception:
                            pass
            
            # Kayıtlı handler'ları temizle
            if user_id in self.user_handlers and plugin_name in self.user_handlers[user_id]:
                del self.user_handlers[user_id][plugin_name]
            
            # Unregister fonksiyonu varsa çağır
            if module and hasattr(module, 'unregister') and callable(module.unregister):
                try:
                    module.unregister()
                except Exception:
                    pass

            # Kullanıcı verilerini temizle (depoda çöp birikmesini önler)
            if module and hasattr(module, 'cleanup_user_data') and callable(module.cleanup_user_data):
                try:
                    module.cleanup_user_data(user_id, reason)
                    log.info("cleanup_user_data çağrıldı: %s (reason=%s)", plugin_name, reason)
                except Exception:
                    log.error("cleanup_user_data hatası: %s", plugin_name, exc_info=True)
            
            # sys.modules'dan kaldır
            module_name = f"plugin_{plugin_name}_{user_id}"
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            # user_active_plugins'den kaldır
            if user_id in self.user_active_plugins and plugin_name in self.user_active_plugins[user_id]:
                del self.user_active_plugins[user_id][plugin_name]
            
            # DB'den kaldır
            user = await db.get_user(user_id)
            active_plugins = user.get("active_plugins", []) if user else []
            if plugin_name in active_plugins:
                active_plugins.remove(plugin_name)
                await db.update_user(user_id, {"active_plugins": active_plugins})
            
            log.info("%s deaktif edildi (user=%s), %s handler kaldırıldı", plugin_name, user_id, handlers_removed)
            return True, f"✅ `{plugin_name}` deaktif edildi"
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"Hata: `{str(e)}`"
    
    async def purge_user_data(self, user_id: int, reason: str = "logout") -> int:
        """Kullanıcının YÜKLÜ tüm pluginlerindeki verilerini temizler (çıkış/silme).
        Her plugin kendi cleanup_user_data'sını uygular; kurtarma/yapılandırma reason'a göre korunur."""
        cleaned = 0
        modules = dict(self.user_active_plugins.get(user_id, {}))
        for plugin_name, module in modules.items():
            if module and hasattr(module, 'cleanup_user_data') and callable(module.cleanup_user_data):
                try:
                    module.cleanup_user_data(user_id, reason)
                    cleaned += 1
                except Exception:
                    log.error("purge cleanup hatası: %s", plugin_name, exc_info=True)
        if cleaned:
            log.info("purge_user_data: user=%s, %s plugin temizlendi (reason=%s)", user_id, cleaned, reason)
        return cleaned

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
        """Kullanıcının pluginlerini geri yükle - PARALEL + Varsayılan aktif pluginler"""
        user = await db.get_user(user_id)
        if not user:
            return 0
        
        active_plugins = user.get("active_plugins", [])
        
        # Varsayılan aktif pluginleri ekle
        all_plugins = await db.get_all_plugins()
        default_active_plugins = [
            p["name"] for p in all_plugins 
            if p.get("default_active", False) and not p.get("is_disabled", False)
        ]
        
        # Varsayılan aktif pluginleri kullanıcının listesine ekle (yoksa)
        plugins_to_load = list(set(active_plugins + default_active_plugins))
        
        if not plugins_to_load:
            return 0
        
        async def load_single_plugin(plugin_name):
            """Tek bir plugini yükle"""
            try:
                success, msg = await self.activate_plugin(user_id, plugin_name, client)
                if success:
                    return plugin_name
            except Exception:
                pass
            return None
        
        # Tüm pluginleri paralel yükle
        tasks = [load_single_plugin(p) for p in plugins_to_load]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        restored = sum(1 for r in results if r is not None and not isinstance(r, Exception))
        return restored
    
    async def activate_default_plugins(self, user_id: int, client: TelegramClient) -> int:
        """Yeni kullanıcı için varsayılan aktif pluginleri aktif et"""
        all_plugins = await db.get_all_plugins()
        default_plugins = [
            p["name"] for p in all_plugins 
            if p.get("default_active", False) and not p.get("is_disabled", False)
        ]
        
        if not default_plugins:
            return 0
        
        activated = 0
        for plugin_name in default_plugins:
            try:
                success, _ = await self.activate_plugin(user_id, plugin_name, client)
                if success:
                    activated += 1
            except Exception:
                pass
        
        return activated
    
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
                module = self.user_active_plugins[user_id].get(plugin_name)
                
                # Handler'ları kaldır
                if user_id in self.user_handlers and plugin_name in self.user_handlers[user_id]:
                    handlers = self.user_handlers[user_id][plugin_name]
                    client = getattr(module, 'client', None) if module else None
                    
                    if client and handlers:
                        for callback, event in handlers:
                            try:
                                client.remove_event_handler(callback, event)
                            except Exception:
                                pass
                
                # sys.modules'dan kaldır
                module_name = f"plugin_{plugin_name}_{user_id}"
                if module_name in sys.modules:
                    del sys.modules[module_name]
            
            del self.user_active_plugins[user_id]
        
        # Handler kayıtlarını temizle
        if user_id in self.user_handlers:
            del self.user_handlers[user_id]

    async def sync_folder_plugins(self):
        """plugins/ klasöründeki, DB'de OLMAYAN pluginleri otomatik kaydet.
        Dosyayı klasöre atınca panele düşmesi için. Mevcut kayıtlar KORUNUR.
        Başlıkta '# type:/# stars:/# days:' varsa premium ayarını da uygular."""
        try:
            from database import database as _db
        except Exception:
            return 0
        try:
            existing = {p.get("name") for p in await _db.get_all_plugins()}
        except Exception:
            existing = set()
        try:
            files = [f for f in os.listdir(config.PLUGINS_DIR) if f.endswith(".py")]
        except Exception:
            files = []
        added = 0
        for fn in files:
            name = fn[:-3]
            if name.startswith("_") or name.startswith("temp_") or name == "__init__":
                continue
            path = os.path.join(config.PLUGINS_DIR, fn)
            if name in existing:
                # Var olan plugin: komut/açıklama metadatasını dosyadan TAZELE
                # (is_public/premium/izin gibi admin ayarlarına dokunmaz)
                try:
                    _info = self.extract_plugin_info(path)
                    await _db.update_plugin(name, {
                        "commands": _info.get("commands", []),
                        "description": _info.get("description", ""),
                    })
                except Exception:
                    pass
                continue
            try:
                info = self.extract_plugin_info(path)
                await _db.add_plugin(
                    name=name, filename=fn,
                    description=info.get("description", ""),
                    commands=info.get("commands", []),
                    is_public=True, allowed_users=[],
                )
                self._apply_header_premium(path, name)
                added += 1
                log.info("Klasörden plugin kaydedildi: %s", name)
            except Exception:
                log.warning("Plugin senkron hatası: %s", name, exc_info=True)
        if added:
            log.info("%d yeni plugin klasörden senkronlandı", added)
        return added

    def _apply_header_premium(self, path, name):
        """Plugin başlığındaki '# type:/# stars:/# days:' satırlarını premium
        config'e uygular (yalnızca daha önce ayarlanmamışsa; panel ayarları korunur)."""
        try:
            from utils import premium as _prem
        except Exception:
            return
        try:
            if _prem.is_configured(name):
                return
            ptype = None
            stars = None
            days = None
            with open(path, "r", encoding="utf-8") as f:
                head = f.read().split("\n")[:25]
            for line in head:
                s = line.strip().lower()
                if s.startswith("# type:"):
                    v = line.split(":", 1)[1].strip().lower()
                    if v in ("genel", "ozel", "özel", "premium"):
                        ptype = "ozel" if v == "özel" else v
                elif s.startswith("# stars:") or s.startswith("# yıldız:"):
                    d = "".join(c for c in line.split(":", 1)[1] if c.isdigit())
                    stars = int(d) if d else None
                elif s.startswith("# days:") or s.startswith("# gün:"):
                    d = "".join(c for c in line.split(":", 1)[1] if c.isdigit())
                    days = int(d) if d else None
            if ptype:
                _prem.set_config(name, ptype=ptype, stars=stars, days=days)
                log.info("Plugin başlığından premium ayarı uygulandı: %s (%s)", name, ptype)
        except Exception:
            log.debug("header premium uygulanamadı: %s", name, exc_info=True)


# Global instance
plugin_manager = PluginManager()
