# ============================================
# KingTG UserBot Service - Chess Game Handler
# ============================================
# Bot tarafında çalışan satranç oyunu
# Tüm kullanıcılar için çalışır
# Premium Emoji destekli
# ============================================

from telethon import events, Button
from telethon.tl.types import MessageEntityCustomEmoji
import hashlib
import time
import asyncio

# Global oyun deposu - TÜM KULLANICILAR İÇİN
CHESS_GAMES = {}

# ============================================
# PREMIUM EMOJİ ID'LERİ
# ============================================
PREMIUM_PIECES = {
    # Beyaz taşlar
    'wk': ('♔', 5823405294604000011),  # Beyaz Şah
    'wq': ('♕', 5823399745506253558),  # Beyaz Vezir
    'wr': ('♖', 5823328878545870632),  # Beyaz Kale
    'wb': ('♗', 5823419592550129283),  # Beyaz Fil
    'wn': ('♘', 5823545752919481487),  # Beyaz At
    'wp': ('♙', 5823625845469617580),  # Beyaz Piyon
    # Siyah taşlar
    'bk': ('♚', 5823157556595399802),  # Siyah Şah
    'bq': ('♛', 5823186789498896270),  # Siyah Vezir
    'br': ('♜', 5821463801882484808),  # Siyah Kale
    'bb': ('♝', 5823429286291315461),  # Siyah Fil
    'bn': ('♞', 5823310096653885214),  # Siyah At
    'bp': ('♟', 5821369273947266395),  # Siyah Piyon
}

# Fallback (premium yoksa)
PIECES_FALLBACK = {
    'wr': '♖', 'wn': '♘', 'wb': '♗', 'wq': '♕', 'wk': '♔', 'wp': '♙',
    'br': '♜', 'bn': '♞', 'bb': '♝', 'bq': '♛', 'bk': '♚', 'bp': '♟'
}


def get_piece_char(piece):
    """Taş karakterini döndür"""
    if piece in PREMIUM_PIECES:
        return PREMIUM_PIECES[piece][0]
    return PIECES_FALLBACK.get(piece, '')


def utf16_len(s):
    """UTF-16 uzunluğunu hesapla (entity offset için)"""
    return len(s.encode('utf-16-le')) // 2


def create_board():
    return [
        ['br', 'bn', 'bb', 'bq', 'bk', 'bb', 'bn', 'br'],
        ['bp', 'bp', 'bp', 'bp', 'bp', 'bp', 'bp', 'bp'],
        ['', '', '', '', '', '', '', ''],
        ['', '', '', '', '', '', '', ''],
        ['', '', '', '', '', '', '', ''],
        ['', '', '', '', '', '', '', ''],
        ['wp', 'wp', 'wp', 'wp', 'wp', 'wp', 'wp', 'wp'],
        ['wr', 'wn', 'wb', 'wq', 'wk', 'wb', 'wn', 'wr']
    ]


def pos_to_notation(row, col):
    return f"{chr(97+col)}{8-row}"


# ============================================
# SATRANÇ KURALLARI
# ============================================

def get_valid_moves(board, row, col, check_check=True):
    piece = board[row][col]
    if not piece:
        return []

    color = piece[0]
    piece_type = piece[1]
    moves = []

    def valid(r, c): return 0 <= r < 8 and 0 <= c < 8
    def enemy(r, c): return valid(r, c) and board[r][c] and board[r][c][0] != color
    def empty(r, c): return valid(r, c) and not board[r][c]
    def empty_or_enemy(r, c): return valid(r, c) and (not board[r][c] or board[r][c][0] != color)

    if piece_type == 'p':
        d = -1 if color == 'w' else 1
        start = 6 if color == 'w' else 1
        if empty(row + d, col):
            moves.append((row + d, col))
            if row == start and empty(row + 2*d, col):
                moves.append((row + 2*d, col))
        for dc in [-1, 1]:
            if enemy(row + d, col + dc):
                moves.append((row + d, col + dc))
                
    elif piece_type == 'r':
        for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
            for i in range(1, 8):
                nr, nc = row+dr*i, col+dc*i
                if not valid(nr, nc): break
                if empty(nr, nc): moves.append((nr, nc))
                elif enemy(nr, nc): moves.append((nr, nc)); break
                else: break
                
    elif piece_type == 'n':
        for dr, dc in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
            if empty_or_enemy(row+dr, col+dc):
                moves.append((row+dr, col+dc))
                
    elif piece_type == 'b':
        for dr, dc in [(1,1),(1,-1),(-1,1),(-1,-1)]:
            for i in range(1, 8):
                nr, nc = row+dr*i, col+dc*i
                if not valid(nr, nc): break
                if empty(nr, nc): moves.append((nr, nc))
                elif enemy(nr, nc): moves.append((nr, nc)); break
                else: break
                
    elif piece_type == 'q':
        for dr, dc in [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]:
            for i in range(1, 8):
                nr, nc = row+dr*i, col+dc*i
                if not valid(nr, nc): break
                if empty(nr, nc): moves.append((nr, nc))
                elif enemy(nr, nc): moves.append((nr, nc)); break
                else: break
                
    elif piece_type == 'k':
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0: continue
                if empty_or_enemy(row+dr, col+dc):
                    moves.append((row+dr, col+dc))

    if check_check:
        legal = []
        for move in moves:
            test = [r[:] for r in board]
            test[move[0]][move[1]] = test[row][col]
            test[row][col] = ''
            if not is_in_check(test, color):
                legal.append(move)
        return legal
    return moves


def find_king(board, color):
    for r in range(8):
        for c in range(8):
            if board[r][c] == color + 'k':
                return (r, c)
    return None


def is_in_check(board, color):
    king = find_king(board, color)
    if not king: return False
    enemy_color = 'b' if color == 'w' else 'w'
    for r in range(8):
        for c in range(8):
            if board[r][c] and board[r][c][0] == enemy_color:
                if king in get_valid_moves(board, r, c, False):
                    return True
    return False


def is_checkmate(board, color):
    if not is_in_check(board, color): return False
    for r in range(8):
        for c in range(8):
            if board[r][c] and board[r][c][0] == color:
                if get_valid_moves(board, r, c, True):
                    return False
    return True


def is_stalemate(board, color):
    if is_in_check(board, color): return False
    for r in range(8):
        for c in range(8):
            if board[r][c] and board[r][c][0] == color:
                if get_valid_moves(board, r, c, True):
                    return False
    return True


# ============================================
# TAHTA GÖRÜNTÜLEME
# ============================================

def build_board_text_with_entities(board, selected=None, valid_moves=None, flipped=False, highlight=None):
    """Tahta metnini ve premium emoji entity'lerini oluştur"""
    valid_moves = valid_moves or []
    highlight = highlight or []
    text = ""
    entities = []
    
    rows = range(7, -1, -1) if flipped else range(8)
    cols = range(7, -1, -1) if flipped else range(8)
    
    for row in rows:
        for col in cols:
            piece = board[row][col]
            
            if highlight and (row, col) in highlight:
                symbol = get_piece_char(piece) if piece else "·"
                if piece and piece in PREMIUM_PIECES:
                    offset = utf16_len(text)
                    length = utf16_len(symbol)
                    entities.append(MessageEntityCustomEmoji(
                        offset=offset, length=length, 
                        document_id=PREMIUM_PIECES[piece][1]
                    ))
                text += symbol
            elif (row, col) == selected:
                text += "🔵"
            elif (row, col) in valid_moves:
                if piece:
                    text += "🔴"
                else:
                    text += "🟢"
            elif piece:
                symbol = get_piece_char(piece)
                # Premium emoji entity ekle
                if piece in PREMIUM_PIECES:
                    offset = utf16_len(text)
                    length = utf16_len(symbol)
                    entities.append(MessageEntityCustomEmoji(
                        offset=offset, length=length,
                        document_id=PREMIUM_PIECES[piece][1]
                    ))
                text += symbol
            else:
                text += "·"
        text += "\n"
    
    return text, entities


def build_board_text(board, selected=None, valid_moves=None, flipped=False, highlight=None):
    """Sadece metin döndür (entity'siz - inline query için)"""
    text, _ = build_board_text_with_entities(board, selected, valid_moves, flipped, highlight)
    return text


async def edit_with_premium(event, text_prefix, board, buttons, 
                            selected=None, valid_moves=None, 
                            flipped=False, highlight=None):
    """Premium emoji entity'leri ile mesaj düzenle"""
    board_text, board_entities = build_board_text_with_entities(
        board, selected, valid_moves, flipped, highlight
    )
    
    full_text = text_prefix + board_text
    
    # Entity offset'lerini prefix uzunluğu kadar kaydır
    prefix_len = utf16_len(text_prefix)
    for entity in board_entities:
        entity.offset += prefix_len
    
    try:
        if board_entities:
            await event.edit(full_text, buttons=buttons, formatting_entities=board_entities)
        else:
            await event.edit(full_text, buttons=buttons)
    except Exception:
        # Fallback - entity'siz dene
        try:
            await event.edit(full_text, buttons=buttons)
        except:
            pass


def create_board_buttons(game_id, board, selected=None, valid_moves=None,
                         flipped=False, highlight=None, status='active'):
    valid_moves = valid_moves or []
    highlight = highlight or []
    buttons = []
    
    rows = range(7, -1, -1) if flipped else range(8)
    cols = range(7, -1, -1) if flipped else range(8)
    
    for row in rows:
        row_buttons = []
        for col in cols:
            piece = board[row][col]
            
            if highlight and (row, col) in highlight:
                symbol = get_piece_char(piece) if piece else "·"
            elif (row, col) == selected:
                symbol = "🔵"
            elif (row, col) in valid_moves:
                symbol = "🔴" if piece else "🟢"
            elif piece:
                symbol = get_piece_char(piece)
            else:
                symbol = "·"
            
            row_buttons.append(Button.inline(symbol, f"chess_{game_id}_{row}_{col}"))
        buttons.append(row_buttons)
    
    if status == 'active':
        buttons.append([
            Button.inline("⏮ Son", f"chesslast_{game_id}"),
            Button.inline("🏳️ Pes", f"chessres_{game_id}"),
            Button.inline("🔄 Yeni", f"chessnew_{game_id}"),
        ])
    else:
        buttons.append([Button.inline("🔄 Rövanş", f"chessnew_{game_id}")])
    
    return buttons


# ============================================
# OYUN OLUŞTURMA
# ============================================

def create_chess_game(white_id, white_name, black_id, black_name, chat_id):
    """Yeni oyun oluştur ve game_id döndür"""
    game_id = hashlib.md5(f"{white_id}{black_id}{time.time()}".encode()).hexdigest()[:8]
    
    CHESS_GAMES[game_id] = {
        'chat_id': chat_id,
        'white_id': white_id,
        'black_id': black_id,
        'white_name': white_name,
        'black_name': black_name,
        'board': create_board(),
        'turn': 'w',
        'selected': None,
        'valid_moves': [],
        'last_move': None,
        'last_move_data': None,
        'status': 'active',
        'moves': []
    }
    
    return game_id


def get_chess_game(game_id):
    """Oyunu getir"""
    return CHESS_GAMES.get(game_id)


# ============================================
# HANDLER'LARI KAYDET
# ============================================

def register_chess_handlers(bot):
    """Chess handler'larını bot'a kaydet"""
    
    @bot.on(events.InlineQuery(pattern=r'^chess_([a-f0-9]+)$'))
    async def chess_inline_handler(event):
        """Inline query handler - tüm kullanıcılar için çalışır"""
        game_id = event.pattern_match.group(1)
        game = CHESS_GAMES.get(game_id)
        
        if not game:
            await event.answer([], cache_time=0)
            return
        
        turn_name = game['white_name'] if game['turn'] == 'w' else game['black_name']
        turn_emoji = "⚪" if game['turn'] == 'w' else "⚫"
        
        # Inline query'de entity desteklenmez - düz metin
        board_text = build_board_text(game['board'])
        
        text = (
            f"♟️ **Satranç**\n\n"
            f"⚪ {game['white_name']} vs ⚫ {game['black_name']}\n"
            f"Sıra: {turn_emoji} **{turn_name}**\n\n"
            f"{board_text}"
        )
        
        buttons = create_board_buttons(game_id, game['board'])
        
        result = event.builder.article(
            title="♟️ Satranç",
            description=f"⚪ {game['white_name']} vs ⚫ {game['black_name']}",
            text=text,
            buttons=buttons
        )
        
        await event.answer([result], cache_time=0)
    
    @bot.on(events.CallbackQuery(pattern=rb"chess_([a-f0-9]+)_(\d)_(\d)"))
    async def chess_click_handler(event):
        """Tahta tıklama handler"""
        match = event.pattern_match
        game_id = match.group(1).decode()
        row, col = int(match.group(2)), int(match.group(3))
        
        game = CHESS_GAMES.get(game_id)
        if not game or game['status'] != 'active':
            await event.answer("❌ Oyun bulunamadı veya bitti!", alert=True)
            return
        
        user_id = event.sender_id
        color = game['turn']
        flipped = color == 'b'
        
        # Sıra kontrolü
        if (color == 'w' and user_id != game['white_id']) or \
           (color == 'b' and user_id != game['black_id']):
            await event.answer("⏳ Sıra sende değil!", alert=True)
            return
        
        board = game['board']
        piece = board[row][col]
        selected = game['selected']
        valid_moves = game['valid_moves']
        
        # --- Hamle Yap ---
        if selected and (row, col) in valid_moves:
            sr, sc = selected
            moved = board[sr][sc]
            captured = board[row][col]
            
            game['last_move_data'] = {
                'from': (sr, sc),
                'to': (row, col),
                'piece': moved,
                'captured': captured
            }
            
            board[row][col] = moved
            board[sr][sc] = ''
            
            # Piyon terfi
            if moved[1] == 'p' and row in [0, 7]:
                board[row][col] = moved[0] + 'q'
            
            notation = (
                f"{PIECES_FALLBACK.get(moved, '')}"
                f"{pos_to_notation(sr, sc)}"
                f"{'x' if captured else '-'}"
                f"{pos_to_notation(row, col)}"
            )
            game['moves'].append(notation)
            game['last_move'] = notation
            
            game['turn'] = 'b' if color == 'w' else 'w'
            game['selected'] = None
            game['valid_moves'] = []
            
            new_flipped = game['turn'] == 'b'
            next_color = game['turn']
            status_text = ""
            
            if is_checkmate(board, next_color):
                winner = game['white_name'] if next_color == 'b' else game['black_name']
                game['status'] = 'checkmate'
                status_text = f"\n\n🏆 **ŞAH MAT!** {winner} kazandı!"
            elif is_stalemate(board, next_color):
                game['status'] = 'stalemate'
                status_text = "\n\n🤝 **PAT!** Berabere!"
            elif is_in_check(board, next_color):
                status_text = "\n\n⚠️ **ŞAH!**"
            
            turn_name = game['white_name'] if game['turn'] == 'w' else game['black_name']
            turn_emoji = "⚪" if game['turn'] == 'w' else "⚫"
            
            text_prefix = f"♟️ **Satranç**\n\n"
            text_prefix += f"⚪ {game['white_name']} vs ⚫ {game['black_name']}\n"
            
            if game['status'] == 'active':
                text_prefix += f"Sıra: {turn_emoji} **{turn_name}**"
            
            text_prefix += status_text
            text_prefix += f"\n📝 {game['last_move']}\n\n"
            
            buttons = create_board_buttons(game_id, board, flipped=new_flipped, status=game['status'])
            
            await edit_with_premium(event, text_prefix, board, buttons, flipped=new_flipped)
            await event.answer(f"✅ {notation}")
            return
        
        # --- Taş Seç ---
        if piece and piece[0] == color:
            moves = get_valid_moves(board, row, col)
            if moves:
                game['selected'] = (row, col)
                game['valid_moves'] = moves
                
                turn_name = game['white_name'] if game['turn'] == 'w' else game['black_name']
                turn_emoji = "⚪" if game['turn'] == 'w' else "⚫"
                
                text_prefix = (
                    f"♟️ **Satranç**\n\n"
                    f"⚪ {game['white_name']} vs ⚫ {game['black_name']}\n"
                    f"Sıra: {turn_emoji} **{turn_name}**\n"
                    f"Seçili: {PIECES_FALLBACK.get(piece, '')} `{pos_to_notation(row, col)}`\n\n"
                )
                
                buttons = create_board_buttons(game_id, board, (row, col), moves, flipped)
                
                await edit_with_premium(event, text_prefix, board, buttons, 
                                        selected=(row, col), valid_moves=moves, flipped=flipped)
                await event.answer(f"{PIECES_FALLBACK.get(piece, '')} seçildi")
            else:
                await event.answer("❌ Bu taş hareket edemiyor!", alert=True)
        
        elif piece:
            await event.answer("❌ Rakibin taşı!", alert=True)
        
        else:
            if selected:
                game['selected'] = None
                game['valid_moves'] = []
                
                turn_name = game['white_name'] if game['turn'] == 'w' else game['black_name']
                turn_emoji = "⚪" if game['turn'] == 'w' else "⚫"
                
                text_prefix = (
                    f"♟️ **Satranç**\n\n"
                    f"⚪ {game['white_name']} vs ⚫ {game['black_name']}\n"
                    f"Sıra: {turn_emoji} **{turn_name}**\n\n"
                )
                
                buttons = create_board_buttons(game_id, board, flipped=flipped)
                
                await edit_with_premium(event, text_prefix, board, buttons, flipped=flipped)
                await event.answer("İptal")
    
    @bot.on(events.CallbackQuery(pattern=rb"chesslast_([a-f0-9]+)"))
    async def chess_last_handler(event):
        """Son hamleyi göster"""
        game_id = event.pattern_match.group(1).decode()
        game = CHESS_GAMES.get(game_id)
        
        if not game:
            await event.answer("❌ Oyun bulunamadı!", alert=True)
            return
        
        if not game['last_move_data']:
            await event.answer("Henüz hamle yapılmadı!", alert=True)
            return
        
        lm = game['last_move_data']
        board = game['board']
        flipped = game['turn'] == 'b'
        
        temp = [r[:] for r in board]
        temp[lm['to'][0]][lm['to'][1]] = lm['captured'] or ''
        temp[lm['from'][0]][lm['from'][1]] = lm['piece']
        
        highlight = [lm['from'], lm['to']]
        
        text_prefix = (
            f"♟️ **Satranç** ⏮️\n\n"
            f"⚪ {game['white_name']} vs ⚫ {game['black_name']}\n"
            f"📝 Son hamle: **{game['last_move']}**\n\n"
        )
        
        buttons = create_board_buttons(game_id, temp, flipped=flipped, highlight=highlight, status=game['status'])
        
        await edit_with_premium(event, text_prefix, temp, buttons, flipped=flipped, highlight=highlight)
        await event.answer(f"⏮️ {game['last_move']}")
        
        await asyncio.sleep(2)
        
        turn_name = game['white_name'] if game['turn'] == 'w' else game['black_name']
        turn_emoji = "⚪" if game['turn'] == 'w' else "⚫"
        
        text_prefix = f"♟️ **Satranç**\n\n"
        text_prefix += f"⚪ {game['white_name']} vs ⚫ {game['black_name']}\n"
        
        if game['status'] == 'active':
            text_prefix += f"Sıra: {turn_emoji} **{turn_name}**"
        elif game['status'] == 'checkmate':
            winner = game['white_name'] if game['turn'] == 'b' else game['black_name']
            text_prefix += f"\n🏆 **ŞAH MAT!** {winner} kazandı!"
        elif game['status'] == 'stalemate':
            text_prefix += "\n🤝 **PAT!** Berabere!"
        
        if game['last_move']:
            text_prefix += f"\n📝 {game['last_move']}"
        
        text_prefix += "\n\n"
        
        buttons = create_board_buttons(game_id, board, flipped=flipped, status=game['status'])
        
        await edit_with_premium(event, text_prefix, board, buttons, flipped=flipped)
    
    @bot.on(events.CallbackQuery(pattern=rb"chessres_([a-f0-9]+)"))
    async def chess_resign_handler(event):
        """Pes et"""
        game_id = event.pattern_match.group(1).decode()
        game = CHESS_GAMES.get(game_id)
        
        if not game or game['status'] != 'active':
            await event.answer("❌ Oyun bulunamadı veya bitti!", alert=True)
            return
        
        user_id = event.sender_id
        if user_id not in [game['white_id'], game['black_id']]:
            await event.answer("❌ Bu oyunda değilsin!", alert=True)
            return
        
        game['status'] = 'resigned'
        loser = game['white_name'] if user_id == game['white_id'] else game['black_name']
        winner = game['black_name'] if user_id == game['white_id'] else game['white_name']
        
        try:
            await event.edit(
                f"♟️ **Satranç**\n\n"
                f"🏳️ **{loser}** pes etti!\n"
                f"🏆 **{winner}** kazandı!",
                buttons=[[Button.inline("🔄 Rövanş", f"chessnew_{game_id}")]]
            )
        except:
            pass
        
        await event.answer("🏳️ Pes ettin!", alert=True)
    
    @bot.on(events.CallbackQuery(pattern=rb"chessnew_([a-f0-9]+)"))
    async def chess_new_handler(event):
        """Yeni oyun / Rövanş"""
        game_id = event.pattern_match.group(1).decode()
        game = CHESS_GAMES.get(game_id)
        
        if not game:
            await event.answer("❌ Oyun bulunamadı!", alert=True)
            return
        
        user_id = event.sender_id
        if user_id not in [game['white_id'], game['black_id']]:
            await event.answer("❌ Bu oyunda değilsin!", alert=True)
            return
        
        # Tarafları değiştir
        game['white_id'], game['black_id'] = game['black_id'], game['white_id']
        game['white_name'], game['black_name'] = game['black_name'], game['white_name']
        
        game['board'] = create_board()
        game['turn'] = 'w'
        game['selected'] = None
        game['valid_moves'] = []
        game['last_move'] = None
        game['last_move_data'] = None
        game['status'] = 'active'
        game['moves'] = []
        
        text_prefix = (
            f"♟️ **Satranç** (Rövanş)\n\n"
            f"⚪ {game['white_name']} vs ⚫ {game['black_name']}\n"
            f"Sıra: ⚪ **{game['white_name']}**\n\n"
        )
        
        buttons = create_board_buttons(game_id, game['board'])
        
        await edit_with_premium(event, text_prefix, game['board'], buttons)
        await event.answer("🔄 Rövanş başladı!", alert=True)
    
    print("[CHESS] ✅ Satranç handler'ları yüklendi (Premium Emoji)")
