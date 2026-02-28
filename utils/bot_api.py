# ============================================
# KingTG UserBot Service - Bot API HTTP Helper
# ============================================
# Renkli butonlar ve premium emoji desteği için
# Bot API 9.4+ özellikleri
# ============================================

import aiohttp
import re
from typing import Optional, List, Dict, Any, Union
import config

def md_to_html(text: str) -> str:
    """Markdown'ı HTML'e çevir"""
    if not text:
        return text
    
    # **bold** -> <b>bold</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # `code` -> <code>code</code>
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    # __italic__ -> <i>italic</i>
    text = re.sub(r'__(.+?)__', r'<i>\1</i>', text)
    # ~~strike~~ -> <s>strike</s>
    text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)
    
    return text


class BotAPI:
    """Bot API HTTP wrapper for colored buttons and premium emoji"""
    
    def __init__(self, token: str = None):
        self.token = token or config.BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"
    
    async def _request(self, method: str, data: Dict = None) -> Optional[Dict]:
        """API isteği gönder"""
        url = f"{self.base_url}/{method}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    result = await response.json()
                    if result.get('ok'):
                        return result.get('result')
                    else:
                        print(f"[BOT_API] {method} error: {result.get('description')}")
                        return None
        except Exception as e:
            print(f"[BOT_API] {method} exception: {e}")
            return None
    
    async def send_message(
        self,
        chat_id: Union[int, str],
        text: str,
        parse_mode: str = None,
        reply_markup: Dict = None,
        disable_web_page_preview: bool = True
    ) -> Optional[Dict]:
        """Mesaj gönder"""
        data = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview
        }
        
        # Parse mode sadece istenirse ekle
        if parse_mode:
            data["parse_mode"] = parse_mode
        
        if reply_markup:
            data["reply_markup"] = reply_markup
        
        return await self._request("sendMessage", data)
    
    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        parse_mode: str = None,
        reply_markup: Dict = None,
        disable_web_page_preview: bool = True
    ) -> Optional[Dict]:
        """Mesajı düzenle"""
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview
        }
        
        if parse_mode:
            data["parse_mode"] = parse_mode
        
        if reply_markup:
            data["reply_markup"] = reply_markup
        
        return await self._request("editMessageText", data)
    
    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str = None,
        show_alert: bool = False
    ) -> Dict:
        """Callback query yanıtla"""
        data = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert
        }
        if text:
            data["text"] = text
        
        return await self._request("answerCallbackQuery", data)
    
    async def delete_message(self, chat_id: int, message_id: int) -> Dict:
        """Mesaj sil"""
        return await self._request("deleteMessage", {
            "chat_id": chat_id,
            "message_id": message_id
        })
    
    async def send_photo(
        self,
        chat_id: Union[int, str],
        photo: str,
        caption: str = None,
        parse_mode: str = None,
        reply_markup: Dict = None
    ) -> Optional[Dict]:
        """Fotoğraf gönder"""
        import os
        
        url = f"{self.base_url}/sendPhoto"
        
        async with aiohttp.ClientSession() as session:
            # Dosya mı URL mi kontrol et
            if os.path.exists(photo):
                # Dosya olarak gönder
                data = aiohttp.FormData()
                data.add_field('chat_id', str(chat_id))
                data.add_field('photo', open(photo, 'rb'), filename=os.path.basename(photo))
                if caption:
                    data.add_field('caption', caption)
                if parse_mode:
                    data.add_field('parse_mode', parse_mode)
                if reply_markup:
                    import json
                    data.add_field('reply_markup', json.dumps(reply_markup))
                
                async with session.post(url, data=data) as response:
                    result = await response.json()
                    if result.get('ok'):
                        return result.get('result')
                    print(f"[BOT_API] send_photo error: {result.get('description')}")
                    return None
            else:
                # URL olarak gönder
                json_data = {
                    "chat_id": chat_id,
                    "photo": photo
                }
                if caption:
                    json_data["caption"] = caption
                if parse_mode:
                    json_data["parse_mode"] = parse_mode
                if reply_markup:
                    json_data["reply_markup"] = reply_markup
                
                async with session.post(url, json=json_data) as response:
                    result = await response.json()
                    if result.get('ok'):
                        return result.get('result')
                    print(f"[BOT_API] send_photo error: {result.get('description')}")
                    return None
    
    async def send_document(
        self,
        chat_id: Union[int, str],
        document: str,
        caption: str = None,
        parse_mode: str = "HTML",
        reply_markup: Dict = None
    ) -> Optional[Dict]:
        """Dosya gönder"""
        import os
        
        if caption and parse_mode == "HTML":
            caption = md_to_html(caption)
        
        url = f"{self.base_url}/sendDocument"
        
        async with aiohttp.ClientSession() as session:
            if os.path.exists(document):
                data = aiohttp.FormData()
                data.add_field('chat_id', str(chat_id))
                data.add_field('document', open(document, 'rb'), filename=os.path.basename(document))
                if caption:
                    data.add_field('caption', caption)
                    data.add_field('parse_mode', parse_mode)
                if reply_markup:
                    import json
                    data.add_field('reply_markup', json.dumps(reply_markup))
                
                async with session.post(url, data=data) as response:
                    result = await response.json()
                    if result.get('ok'):
                        return result.get('result')
                    print(f"[BOT_API] send_document error: {result}")
                    return None
            else:
                json_data = {
                    "chat_id": chat_id,
                    "document": document,
                    "parse_mode": parse_mode
                }
                if caption:
                    json_data["caption"] = caption
                if reply_markup:
                    json_data["reply_markup"] = reply_markup
                
                async with session.post(url, json=json_data) as response:
                    result = await response.json()
                    if result.get('ok'):
                        return result.get('result')
                    print(f"[BOT_API] send_document error: {result}")
                    return None
    
    async def edit_message_reply_markup(
        self,
        chat_id: int = None,
        message_id: int = None,
        inline_message_id: str = None,
        reply_markup: Dict = None
    ) -> Dict:
        """Sadece butonları düzenle"""
        data = {}
        if chat_id:
            data["chat_id"] = chat_id
        if message_id:
            data["message_id"] = message_id
        if inline_message_id:
            data["inline_message_id"] = inline_message_id
        if reply_markup:
            data["reply_markup"] = reply_markup
        
        return await self._request("editMessageReplyMarkup", data)
    
    async def answer_inline_query(
        self,
        inline_query_id: str,
        results: List[Dict],
        cache_time: int = 0
    ) -> Dict:
        """Inline query yanıtla"""
        return await self._request("answerInlineQuery", {
            "inline_query_id": inline_query_id,
            "results": results,
            "cache_time": cache_time
        })
    
    async def edit_inline_message_text(
        self,
        inline_message_id: str,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Dict = None,
        disable_web_page_preview: bool = True
    ) -> Dict:
        """Inline mesajı düzenle"""
        if parse_mode == "HTML":
            text = md_to_html(text)
        
        data = {
            "inline_message_id": inline_message_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }
        
        if reply_markup:
            data["reply_markup"] = reply_markup
        
        return await self._request("editMessageText", data)


class ButtonBuilder:
    """Renkli buton oluşturucu"""
    
    # Buton stilleri
    STYLE_PRIMARY = "primary"    # Mavi
    STYLE_SUCCESS = "success"    # Yeşil
    STYLE_DANGER = "danger"      # Kırmızı
    STYLE_SECONDARY = "secondary"  # Gri/Beyaz
    
    # Premium emoji ID'leri
    EMOJI_LOGIN = 5233408828313192030      # Giriş
    EMOJI_PLUGIN = 5237699328843200584     # Plugin
    EMOJI_SETTINGS = 5237830824684428925   # Ayarlar
    EMOJI_HELP = 5238091390690068061       # Yardım
    EMOJI_LOGOUT = 5237758235143248994     # Çıkış
    EMOJI_CROWN = 5236355067455607791      # Taç (owner/premium)
    EMOJI_STAR = 5236243168716752946       # Yıldız
    EMOJI_CHECK = 5237960420075530397      # Onay
    EMOJI_CROSS = 5237830779385321298      # İptal
    EMOJI_BACK = 5237707207794498594       # Geri
    
    @staticmethod
    def callback(
        text: str,
        callback_data: str,
        style: str = None,
        icon_custom_emoji_id: int = None
    ) -> Dict:
        """Callback butonu oluştur"""
        btn = {
            "text": text,
            "callback_data": callback_data
        }
        if style:
            btn["style"] = style
        if icon_custom_emoji_id:
            btn["icon_custom_emoji_id"] = str(icon_custom_emoji_id)
        return btn
    
    @staticmethod
    def url(
        text: str,
        url: str,
        style: str = None,
        icon_custom_emoji_id: int = None
    ) -> Dict:
        """URL butonu oluştur"""
        btn = {
            "text": text,
            "url": url
        }
        if style:
            btn["style"] = style
        if icon_custom_emoji_id:
            btn["icon_custom_emoji_id"] = str(icon_custom_emoji_id)
        return btn
    
    @staticmethod
    def inline_keyboard(rows: List[List[Dict]]) -> Dict:
        """Inline keyboard oluştur"""
        return {
            "inline_keyboard": rows
        }


# Global instance
bot_api = BotAPI()
btn = ButtonBuilder()
