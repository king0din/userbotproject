# ============================================
# KingTG UserBot Service - Bot API HTTP Helper
# ============================================
# Renkli butonlar ve premium emoji desteği için
# Bot API 9.4+ özellikleri
# ============================================

import aiohttp
import re
from typing import Optional, List, Dict, Union
import config
from utils.logger import get_logger

log = get_logger(__name__)


def md_to_html(text: str) -> str:
    """Markdown'ı HTML'e çevir ve HTML karakterlerini escape et"""
    if not text:
        return text
    
    import html
    
    # Önce Markdown pattern'lerini bul ve kaydet
    bold_pattern = re.compile(r'\*\*(.+?)\*\*')
    code_pattern = re.compile(r'`(.+?)`')
    italic_pattern = re.compile(r'__(.+?)__')
    strike_pattern = re.compile(r'~~(.+?)~~')
    
    # Markdown içeriklerini çıkar
    bolds = bold_pattern.findall(text)
    codes = code_pattern.findall(text)
    italics = italic_pattern.findall(text)
    strikes = strike_pattern.findall(text)
    
    # Placeholder'larla değiştir
    for i, b in enumerate(bolds):
        text = text.replace(f'**{b}**', f'__BOLD{i}__', 1)
    for i, c in enumerate(codes):
        text = text.replace(f'`{c}`', f'__CODE{i}__', 1)
    for i, it in enumerate(italics):
        text = text.replace(f'__{it}__', f'__ITALIC{i}__', 1)
    for i, s in enumerate(strikes):
        text = text.replace(f'~~{s}~~', f'__STRIKE{i}__', 1)
    
    # HTML escape (< > & karakterleri)
    text = html.escape(text)
    
    # Placeholder'ları HTML tag'leriyle değiştir
    for i, b in enumerate(bolds):
        text = text.replace(f'__BOLD{i}__', f'<b>{html.escape(b)}</b>')
    for i, c in enumerate(codes):
        text = text.replace(f'__CODE{i}__', f'<code>{html.escape(c)}</code>')
    for i, it in enumerate(italics):
        text = text.replace(f'__ITALIC{i}__', f'<i>{html.escape(it)}</i>')
    for i, s in enumerate(strikes):
        text = text.replace(f'__STRIKE{i}__', f'<s>{html.escape(s)}</s>')
    
    return text


async def _tr_out(text, reply_markup, chat_id):
    """Metni + TÜM buton metinlerini TEK batch çağrısıyla alıcının diline çevirir."""
    try:
        import copy
        import utils.i18n as _i18n
        uid = None
        if isinstance(chat_id, int):
            uid = chat_id
        elif isinstance(chat_id, str) and chat_id.lstrip("-").isdigit():
            uid = int(chat_id)
        if uid is None:
            return text, reply_markup
        lang = _i18n.get_user_lang_cached(uid)
        if not lang or lang == "tr":
            return text, reply_markup
        mk = copy.deepcopy(reply_markup) if reply_markup else None
        btns = []
        if mk and isinstance(mk, dict):
            for row in mk.get("inline_keyboard", []):
                for b in row:
                    if isinstance(b, dict) and b.get("text"):
                        btns.append(b)
        collect = ([text] if text else []) + [b["text"] for b in btns]
        if not collect:
            return text, mk if mk is not None else reply_markup
        tr = await _i18n.translate_many(collect, lang)
        idx = 0
        if text:
            text = tr[idx]; idx += 1
        for b in btns:
            b["text"] = tr[idx]; idx += 1
        return text, (mk if mk is not None else reply_markup)
    except Exception:
        return text, reply_markup


class BotAPI:
    """Bot API HTTP wrapper for colored buttons and premium emoji"""
    
    def __init__(self, token: str = None):
        self.token = token or config.BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self._session = None

    async def _get_session(self):
        """Tek bir oturumu yeniden kullan (her istekte yeni session açma + kısa timeout)."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=12, connect=6, sock_connect=6, sock_read=10
            )
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    @staticmethod
    def _strip_button_styles(markup):
        """Bot API stil/emoji alanlarını çıkar (Telegram reddederse sade buton kalsın)."""
        try:
            rows = markup.get('inline_keyboard') if isinstance(markup, dict) else None
            for row in (rows or []):
                for b in row:
                    if isinstance(b, dict):
                        b.pop('style', None)
                        b.pop('icon_custom_emoji_id', None)
        except Exception:
            pass

    async def _request(self, method: str, data: Dict = None, _retry: bool = True, _stripped: bool = False) -> Optional[Dict]:
        """API isteği gönder (kısa timeout + geçici hata/stil reddi durumunda yeniden dener)"""
        url = f"{self.base_url}/{method}"

        try:
            session = await self._get_session()
            async with session.post(url, json=data) as response:
                result = await response.json()
                if result.get('ok'):
                    return result.get('result')
                desc = result.get('description') or ''
                dl = desc.lower()
                # "message is not modified" → içerik ZATEN aynı; ZARARSIZ.
                # Stilleri SOYMA (yoksa buton düz'e düşer), sessizce geç.
                if 'not modified' in dl:
                    log.debug("editMessageText: içerik değişmedi (zararsız, atlandı)")
                    return None
                # SADECE gerçek stil/premium-emoji reddinde stilleri atıp sade gönder
                if (not _stripped) and data and data.get('reply_markup') and (
                        'button style' in dl or 'custom_emoji' in dl or 'custom emoji' in dl
                        or 'button_type' in dl or ('button' in dl and 'invalid' in dl)):
                    log.warning("⚠️ Buton stili/premium-emoji REDDEDİLDİ (%s) → sade butona düşülüyor. "
                                "SEBEP: %s", method, desc)
                    self._strip_button_styles(data['reply_markup'])
                    return await self._request(method, data, _retry=False, _stripped=True)
                log.warning("%s error: %s", method, desc)
                return None
        except Exception:
            # geçici bağlantı/timeout → session'ı tazeleyip bir kez daha dene
            if _retry:
                try:
                    if self._session and not self._session.closed:
                        await self._session.close()
                except Exception:
                    pass
                self._session = None
                return await self._request(method, data, _retry=False)
            log.error("%s exception", method, exc_info=True)
            return None
    
    async def send_message(
        self,
        chat_id: Union[int, str],
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Dict = None,
        disable_web_page_preview: bool = True,
        translate: bool = True
    ) -> Optional[Dict]:
        """Mesaj gönder (alıcının diline otomatik çevirir; translate=False ile ham)."""
        if translate:
            text, reply_markup = await _tr_out(text, reply_markup, chat_id)
        # Markdown'ı HTML'e çevir
        if parse_mode == "HTML":
            text = md_to_html(text)

        data = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview
        }
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
        parse_mode: str = "HTML",
        reply_markup: Dict = None,
        disable_web_page_preview: bool = True,
        translate: bool = True
    ) -> Optional[Dict]:
        """Mesajı düzenle (alıcının diline otomatik çevirir; translate=False ile ham)."""
        if translate:
            text, reply_markup = await _tr_out(text, reply_markup, chat_id)
        # Markdown'ı HTML'e çevir
        if parse_mode == "HTML":
            text = md_to_html(text)
        
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }
        
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
                    log.warning("send_photo error: %s", result.get('description'))
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
                    log.warning("send_photo error: %s", result.get('description'))
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
                    log.warning("send_document error: %s", result)
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
                    log.warning("send_document error: %s", result)
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
    STYLE_SECONDARY = "primary"  # Bot API "secondary" desteklemiyor → geçerli "primary"e eşlendi (renkli kalsın)
    
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
