# ============================================
# KingTG UserBot Service - Utils & Helpers
# ============================================

import time
import functools
from typing import Callable, Union, List
from telethon import events, Button
from telethon.tl.types import User
import config
from database import database as db
from utils.logger import get_logger

log = get_logger(__name__)


# ==========================================
# ZAMAN FONKSİYONLARI
# ==========================================

def get_readable_time(seconds: float) -> str:
    """Saniyeyi okunabilir formata çevir"""
    intervals = (
        ('gün', 86400),
        ('saat', 3600),
        ('dakika', 60),
        ('saniye', 1),
    )
    result = []
    for name, count in intervals:
        value = int(seconds // count)
        if value:
            seconds -= value * count
            result.append(f"{value} {name}")
    return ', '.join(result[:2]) if result else '0 saniye'

def format_datetime(dt) -> str:
    """Datetime'ı Türkçe formata çevir"""
    if not dt:
        return "Bilinmiyor"
    if hasattr(dt, 'strftime'):
        return dt.strftime("%d.%m.%Y %H:%M")
    return str(dt)

# ==========================================
# KULLANICI FONKSİYONLARI
# ==========================================

def get_user_link(user: User) -> str:
    """Kullanıcı bağlantısı oluştur"""
    name = user.first_name or "Kullanıcı"
    if user.username:
        return f"[{name}](https://t.me/{user.username})"
    return f"[{name}](tg://user?id={user.id})"

def get_user_mention(user: User) -> str:
    """Kullanıcı mention'ı oluştur"""
    name = user.first_name or "Kullanıcı"
    return f"[{name}](tg://user?id={user.id})"

async def get_user_info(user_id: int, bot) -> str:
    """Kullanıcı bilgilerini getir"""
    try:
        user = await bot.get_entity(user_id)
        return f"👤 **{user.first_name or 'Kullanıcı'}**\n" \
               f"🆔 ID: `{user.id}`\n" \
               f"📍 Username: @{user.username or 'Yok'}"
    except:
        return f"🆔 ID: `{user_id}`"

# ==========================================
# DEKORATÖRLER
# ==========================================

def owner_only(func: Callable) -> Callable:
    """Sadece bot sahibi kullanabilir"""
    @functools.wraps(func)
    async def wrapper(event, *args, **kwargs):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        return await func(event, *args, **kwargs)
    return wrapper

def sudo_only(func: Callable) -> Callable:
    """Sadece sudo ve owner kullanabilir"""
    @functools.wraps(func)
    async def wrapper(event, *args, **kwargs):
        if event.sender_id == config.OWNER_ID:
            return await func(event, *args, **kwargs)
        
        is_sudo = await db.is_sudo(event.sender_id)
        if not is_sudo:
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        return await func(event, *args, **kwargs)
    return wrapper

def check_ban(func: Callable) -> Callable:
    """Ban kontrolü"""
    @functools.wraps(func)
    async def wrapper(event, *args, **kwargs):
        is_banned = await db.is_banned(event.sender_id)
        if is_banned:
            await event.respond(
                config.MESSAGES["banned"].format(owner=f"@{config.OWNER_USERNAME}")
            )
            return
        return await func(event, *args, **kwargs)
    return wrapper

def check_private_mode(func: Callable) -> Callable:
    """Özel mod kontrolü"""
    @functools.wraps(func)
    async def wrapper(event, *args, **kwargs):
        # Owner ve sudo her zaman geçer
        if event.sender_id == config.OWNER_ID:
            return await func(event, *args, **kwargs)
        
        is_sudo = await db.is_sudo(event.sender_id)
        if is_sudo:
            return await func(event, *args, **kwargs)
        
        # Ayarları kontrol et
        settings = await db.get_settings()
        if settings.get("bot_mode") == "private":
            await event.respond(config.MESSAGES["private_mode"])
            return
        
        return await func(event, *args, **kwargs)
    return wrapper

def check_maintenance(func: Callable) -> Callable:
    """Bakım modu kontrolü"""
    @functools.wraps(func)
    async def wrapper(event, *args, **kwargs):
        # Owner ve sudo her zaman geçer
        if event.sender_id == config.OWNER_ID:
            return await func(event, *args, **kwargs)
        
        is_sudo = await db.is_sudo(event.sender_id)
        if is_sudo:
            return await func(event, *args, **kwargs)
        
        settings = await db.get_settings()
        if settings.get("maintenance"):
            await event.respond(config.MESSAGES["maintenance"])
            return
        
        return await func(event, *args, **kwargs)
    return wrapper

def register_user(func: Callable) -> Callable:
    """Kullanıcıyı otomatik kaydet"""
    @functools.wraps(func)
    async def wrapper(event, *args, **kwargs):
        user = await event.get_sender()
        await db.add_user(
            user_id=event.sender_id,
            username=user.username if hasattr(user, 'username') else None,
            first_name=user.first_name if hasattr(user, 'first_name') else None
        )
        return await func(event, *args, **kwargs)
    return wrapper

# ==========================================
# LOG FONKSİYONLARI
# ==========================================

async def send_log(bot, log_type: str, message: str, user_id: int = None):
    """Log kanalına mesaj gönder"""
    if not config.LOG_CHANNEL:
        return
    
    try:
        emoji_map = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "login": "🔐",
            "logout": "🚪",
            "plugin": "🔌",
            "ban": "🚫",
            "sudo": "👑",
            "update": "🔄",
            "system": "🤖"
        }
        
        emoji = emoji_map.get(log_type, "📋")
        
        log_text = f"{emoji} **{log_type.upper()}**\n\n"
        log_text += message
        
        if user_id:
            log_text += f"\n\n👤 User ID: `{user_id}`"
        
        log_text += f"\n⏱️ {format_datetime(time.time())}"
        
        await bot.send_message(config.LOG_CHANNEL, log_text)
        
        # MongoDB'ye de kaydet
        await db.add_log(log_type, user_id, message)
        
    except Exception as e:
        log.error("Hata", exc_info=True)

# ==========================================
# BUTON OLUŞTURUCULAR
# ==========================================

def make_button(text: str, data: str) -> Button:
    """Inline buton oluştur"""
    return Button.inline(text, data.encode())

def make_url_button(text: str, url: str) -> Button:
    """URL buton oluştur"""
    return Button.url(text, url)

def back_button(data: str = "main_menu") -> List[Button]:
    """Geri butonu satırı"""
    return [Button.inline(config.BUTTONS["back"], data.encode())]

def close_button() -> List[Button]:
    """Kapat butonu satırı"""
    return [Button.inline(config.BUTTONS["close"], b"close")]

def confirm_cancel_buttons(confirm_data: str, cancel_data: str = "main_menu") -> List[List[Button]]:
    """Onay/İptal butonları"""
    return [
        [
            Button.inline(config.BUTTONS["confirm"], confirm_data.encode()),
            Button.inline(config.BUTTONS["cancel"], cancel_data.encode())
        ]
    ]

def yes_no_buttons(yes_data: str, no_data: str) -> List[List[Button]]:
    """Evet/Hayır butonları"""
    return [
        [
            Button.inline(config.BUTTONS["yes"], yes_data.encode()),
            Button.inline(config.BUTTONS["no"], no_data.encode())
        ]
    ]

# ==========================================
# METİN İŞLEMLERİ
# ==========================================

def truncate_text(text: str, max_length: int = 4000) -> str:
    """Metni belirli uzunlukta kes"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."

def escape_markdown(text: str) -> str:
    """Markdown karakterlerini escape et"""
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f"\\{char}")
    return text

# ==========================================
# PAGINATION
# ==========================================

def paginate(items: list, page: int, per_page: int = 10) -> dict:
    """Liste için pagination"""
    total = len(items)
    total_pages = (total + per_page - 1) // per_page
    
    start = (page - 1) * per_page
    end = start + per_page
    
    return {
        "items": items[start:end],
        "page": page,
        "total_pages": total_pages,
        "total_items": total,
        "has_prev": page > 1,
        "has_next": page < total_pages
    }

def pagination_buttons(prefix: str, page: int, total_pages: int) -> List[Button]:
    """Pagination butonları"""
    buttons = []
    
    if page > 1:
        buttons.append(Button.inline("◀️", f"{prefix}_{page - 1}".encode()))
    
    buttons.append(Button.inline(f"{page}/{total_pages}", b"noop"))
    
    if page < total_pages:
        buttons.append(Button.inline("▶️", f"{prefix}_{page + 1}".encode()))
    
    return buttons

# ==========================================
# DOĞRULAMA
# ==========================================

def is_valid_phone(phone: str) -> bool:
    """Telefon numarası doğrulama"""
    import re
    pattern = r'^\+?[1-9]\d{1,14}$'
    return bool(re.match(pattern, phone.replace(" ", "").replace("-", "")))

def is_valid_session_string(session: str) -> bool:
    """Session string doğrulama (basit)"""
    # Telethon session stringleri genellikle base64 encoded
    import base64
    try:
        decoded = base64.urlsafe_b64decode(session + '===')
        return len(decoded) > 100  # Minimum uzunluk kontrolü
    except:
        return False
