# ============================================
# KingTG UserBot - Chess (Satranç) Plugin
# ============================================

from telethon import events, Button
from telethon.tl.functions.messages import AddChatUserRequest
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.errors import ChatAdminRequiredError, UserAlreadyParticipantError
import sys
import hashlib
import time
import asyncio
import aiohttp

def register(client):
    main_module = sys.modules.get('__main__')
    bot = getattr(main_module, 'bot', None)
    
    if not bot:
        print("[CHESS PLUGIN] ❌ Bot bulunamadı!")
        return
    
    # Config'den BOT_TOKEN al
    try:
        import config
        BOT_TOKEN = config.BOT_TOKEN
    except:
        print("[CHESS PLUGIN] ❌ Config bulunamadı!")
        return
    
    # GAMES referansını handler'dan al
    try:
        from handlers.chess import CHESS_GAMES
    except:
        # Eğer import edilemezse global bir dict oluştur
        # Bu durumda handler ile senkron olmaz ama en azından çalışır
        print("[CHESS PLUGIN] ⚠️ CHESS_GAMES import edilemedi, yerel dict kullanılıyor")
        CHESS_GAMES = {}
    
    # Bot API fonksiyonları
    API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
    
    async def api_request(method, data):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_URL}/{method}", json=data) as resp:
                return await resp.json()
    
    async def send_message(chat_id, text, reply_markup=None):
        data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            data["reply_markup"] = reply_markup
        return await api_request("sendMessage", data)
    
    async def edit_message(chat_id, message_id, text, reply_markup=None):
        data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            data["reply_markup"] = reply_markup
        return await api_request("editMessageText", data)
    
    # Markdown to HTML
    def md_to_html(text):
        import re
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        return text
    
    # Taş karakterleri
    PIECE_CHARS = {
        'wk': '♔', 'wq': '♕', 'wr': '♖', 'wb': '♗', 'wn': '♘', 'wp': '♙',
        'bk': '♚', 'bq': '♛', 'br': '♜', 'bb': '♝', 'bn': '♞', 'bp': '♟'
    }
    
    # Premium Emoji ID'leri
    PIECE_EMOJI_IDS = {
        'wk': 5823405294604000011, 'wq': 5823399745506253558, 'wr': 5823328878545870632,
        'wb': 5823419592550129283, 'wn': 5823545752919481487, 'wp': 5823625845469617580,
        'bk': 5823157556595399802, 'bq': 5823186789498896270, 'br': 5821463801882484808,
        'bb': 5823429286291315461, 'bn': 5823310096653885214, 'bp': 5821369273947266395,
    }
    EMOJI_SELECTED = 5368324170671202286
    EMOJI_VALID_MOVE = 5367807941110988498
    EMOJI_CAPTURE = 5368493603028498956
    EMOJI_EMPTY = 5367617745632470555
    
    def create_board():
        return [
            ['br', 'bn', 'bb', 'bq', 'bk', 'bb', 'bn', 'br'],
            ['bp'] * 8, [''] * 8, [''] * 8, [''] * 8, [''] * 8, ['wp'] * 8,
            ['wr', 'wn', 'wb', 'wq', 'wk', 'wb', 'wn', 'wr']
        ]
    
    def build_text(board, flipped=False):
        t = ""
        for row in (range(7,-1,-1) if flipped else range(8)):
            for col in (range(7,-1,-1) if flipped else range(8)):
                t += PIECE_CHARS.get(board[row][col], '·') if board[row][col] else '·'
            t += "\n"
        return t
    
    def create_buttons(game_id, board, selected=None, valid_moves=None, flipped=False, status='active'):
        valid_moves = valid_moves or []
        rows = []
        for row in (range(7,-1,-1) if flipped else range(8)):
            r = []
            for col in (range(7,-1,-1) if flipped else range(8)):
                piece = board[row][col]
                cb = f"ch_{game_id}_{row}_{col}"
                
                btn_data = {"text": "·", "callback_data": cb}
                
                if (row, col) == selected:
                    btn_data["text"] = "🔵"
                    btn_data["icon_custom_emoji_id"] = str(EMOJI_SELECTED)
                elif (row, col) in valid_moves:
                    btn_data["text"] = "🔴" if piece else "🟢"
                    btn_data["icon_custom_emoji_id"] = str(EMOJI_CAPTURE if piece else EMOJI_VALID_MOVE)
                elif piece:
                    btn_data["text"] = PIECE_CHARS.get(piece, '·')
                    if piece in PIECE_EMOJI_IDS:
                        btn_data["icon_custom_emoji_id"] = str(PIECE_EMOJI_IDS[piece])
                else:
                    btn_data["icon_custom_emoji_id"] = str(EMOJI_EMPTY)
                
                r.append(btn_data)
            rows.append(r)
        
        if status == 'active':
            rows.append([
                {"text": "⏮", "callback_data": f"chl_{game_id}"},
                {"text": "🏳️", "callback_data": f"chr_{game_id}"},
                {"text": "🔄", "callback_data": f"chn_{game_id}"}
            ])
        else:
            rows.append([{"text": "🔄 Rövanş", "callback_data": f"chn_{game_id}"}])
        
        return {"inline_keyboard": rows}
    
    def create_game(wid, wname, bid, bname, is_group, gid=None):
        game_id = hashlib.md5(f"{wid}{bid}{time.time()}".encode()).hexdigest()[:8]
        CHESS_GAMES[game_id] = {
            'wid': wid, 'bid': bid, 'wname': wname, 'bname': bname,
            'board': create_board(), 'turn': 'w', 'sel': None, 'moves': [],
            'last': None, 'last_data': None, 'status': 'active', 'history': [],
            'is_group': is_group, 'gid': gid, 'gmsg': None,
            'wmsg': None, 'bmsg': None, 'b_started': is_group
        }
        return game_id
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.chess(?:\s+(.+))?$'))
    async def chess_cmd(event):
        """Satranç oyunu başlat"""
        target = event.pattern_match.group(1)
        white_id = event.sender_id
        white_name = "Sen"
        black_id = None
        black_name = None
        
        # Rakibi belirle
        reply = await event.get_reply_message()
        if reply:
            black_id = reply.sender_id
            try:
                u = await client.get_entity(black_id)
                black_name = f"@{u.username}" if u.username else (u.first_name or f"ID:{black_id}")
            except:
                black_name = f"ID:{black_id}"
        elif target:
            t = target.strip().lstrip('@')
            try:
                if t.isdigit():
                    black_id = int(t)
                    u = await client.get_entity(black_id)
                else:
                    u = await client.get_entity(t)
                    black_id = u.id
                black_name = f"@{u.username}" if u.username else (u.first_name or f"ID:{black_id}")
            except Exception as e:
                await event.edit(f"❌ Kullanıcı bulunamadı: `{t}`")
                return
        else:
            await event.edit(
                "♟️ **Satranç**\n\n"
                "**Kullanım:**\n"
                "• `.chess @kullanıcı`\n"
                "• `.chess kullanıcı_id`\n"
                "• Mesajı yanıtla + `.chess`"
            )
            return
        
        if not black_id:
            await event.edit("❌ Rakip belirlenemedi!")
            return
        if black_id == white_id:
            await event.edit("❌ Kendinle oynayamazsın!")
            return
        
        is_group = event.is_group or event.is_channel
        chat_id = event.chat_id
        
        await event.edit("♟️ Oyun hazırlanıyor...")
        
        game_id = create_game(white_id, white_name, black_id, black_name, is_group, chat_id if is_group else None)
        game = CHESS_GAMES[game_id]
        
        bot_me = await bot.get_me()
        bot_username = bot_me.username
        
        if is_group:
            # GRUP MODU
            try:
                if event.is_channel:
                    await client(InviteToChannelRequest(chat_id, [bot_username]))
                else:
                    await client(AddChatUserRequest(chat_id, bot_username, fwd_limit=0))
            except UserAlreadyParticipantError:
                pass
            except Exception as e:
                await event.edit(
                    f"♟️ **Satranç**\n\n"
                    f"⚠️ Bot gruba eklenemedi!\n"
                    f"Lütfen @{bot_username} botunu gruba ekleyin."
                )
                return
            
            await asyncio.sleep(1)
            
            board_text = build_text(game['board'])
            text = md_to_html(f"♟️ **Satranç**\n\n⚪ {white_name} vs ⚫ {black_name}\nSıra: ⚪ **{white_name}**\n\n{board_text}")
            kb = create_buttons(game_id, game['board'])
            
            result = await send_message(chat_id, text, kb)
            
            if result.get('ok'):
                game['gmsg'] = result['result']['message_id']
                await event.delete()
            else:
                await event.edit(f"❌ Bot mesaj gönderemedi: {result.get('description', 'Bilinmiyor')}")
        
        else:
            # ÖZEL SOHBET MODU
            board_text = build_text(game['board'])
            white_text = md_to_html(f"♟️ **Satranç**\n\nSen: ⚪ Beyaz\nRakip: {black_name}\nSıra: **SEN**\n\n{board_text}")
            white_kb = create_buttons(game_id, game['board'], flipped=False)
            
            white_result = await send_message(white_id, white_text, white_kb)
            
            if white_result.get('ok'):
                game['wmsg'] = white_result['result']['message_id']
            else:
                await event.edit(f"❌ Size mesaj gönderilemedi!\n\nÖnce @{bot_username} botunu başlatın.")
                return
            
            # Siyaha mesaj gönder
            black_text = md_to_html(f"♟️ **Satranç Daveti**\n\n{white_name} seni satranç oynamaya davet etti!")
            black_kb = {"inline_keyboard": [[{"text": "✅ Kabul Et", "callback_data": f"chess_accept_{game_id}"}]]}
            
            black_result = await send_message(black_id, black_text, black_kb)
            
            if black_result.get('ok'):
                game['bmsg'] = black_result['result']['message_id']
                await event.edit(f"✅ Davet gönderildi!\n\n@{bot_username} botundan oynayın.")
            else:
                game['b_started'] = False
                await event.edit(
                    f"♟️ **Satranç Daveti**\n\n"
                    f"{black_name} botu başlatmamış!\n"
                    f"Rakibine linki gönder:",
                    buttons=[[Button.url("♟️ Oyuna Katıl", f"https://t.me/{bot_username}?start=chess_{game_id}")]]
                )
    
    print("[CHESS PLUGIN] ✅ Komut yüklendi")
