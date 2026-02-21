# ============================================
# KingTG UserBot Service - Chess Game Handler
# ============================================
# Bot API ile premium emoji butonlar (normal mesajlar)
# Telethon ile normal butonlar (inline mesajlar)
# ============================================

from telethon import events, Button
import hashlib
import time
import asyncio

from utils.bot_api import bot_api, btn, ButtonBuilder

CHESS_GAMES = {}

# Premium Emoji ID'leri - Taşlar
PIECE_EMOJI_IDS = {
    'wk': 5823405294604000011, 'wq': 5823399745506253558, 'wr': 5823328878545870632,
    'wb': 5823419592550129283, 'wn': 5823545752919481487, 'wp': 5823625845469617580,
    'bk': 5823157556595399802, 'bq': 5823186789498896270, 'br': 5821463801882484808,
    'bb': 5823429286291315461, 'bn': 5823310096653885214, 'bp': 5821369273947266395,
}

PIECE_CHARS = {
    'wk': '♔', 'wq': '♕', 'wr': '♖', 'wb': '♗', 'wn': '♘', 'wp': '♙',
    'bk': '♚', 'bq': '♛', 'br': '♜', 'bb': '♝', 'bn': '♞', 'bp': '♟'
}

# Özel emoji ID'leri
EMOJI_SELECTED = 5368324170671202286
EMOJI_VALID_MOVE = 5367807941110988498
EMOJI_CAPTURE = 5368493603028498956
EMOJI_EMPTY = 5367617745632470555


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
    color, piece_type = piece[0], piece[1]
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
            if empty_or_enemy(row+dr, col+dc): moves.append((row+dr, col+dc))
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
                if empty_or_enemy(row+dr, col+dc): moves.append((row+dr, col+dc))

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
                if get_valid_moves(board, r, c, True): return False
    return True


def is_stalemate(board, color):
    if is_in_check(board, color): return False
    for r in range(8):
        for c in range(8):
            if board[r][c] and board[r][c][0] == color:
                if get_valid_moves(board, r, c, True): return False
    return True


# ============================================
# BUTON OLUŞTURUCULAR
# ============================================

def create_buttons_api(game_id, board, selected=None, valid_moves=None, flipped=False, status='active'):
    """Bot API için premium emoji butonları"""
    valid_moves = valid_moves or []
    rows = []
    row_range = range(7, -1, -1) if flipped else range(8)
    col_range = range(7, -1, -1) if flipped else range(8)
    
    for row in row_range:
        row_btns = []
        for col in col_range:
            piece = board[row][col]
            cb = f"chess_{game_id}_{row}_{col}"
            
            if (row, col) == selected:
                row_btns.append(btn.callback("🔵", cb, icon_custom_emoji_id=EMOJI_SELECTED))
            elif (row, col) in valid_moves:
                if piece:
                    row_btns.append(btn.callback("🔴", cb, icon_custom_emoji_id=EMOJI_CAPTURE))
                else:
                    row_btns.append(btn.callback("🟢", cb, icon_custom_emoji_id=EMOJI_VALID_MOVE))
            elif piece:
                row_btns.append(btn.callback(PIECE_CHARS.get(piece, '·'), cb, icon_custom_emoji_id=PIECE_EMOJI_IDS.get(piece)))
            else:
                row_btns.append(btn.callback("·", cb, icon_custom_emoji_id=EMOJI_EMPTY))
        rows.append(row_btns)
    
    if status == 'active':
        rows.append([btn.callback("⏮ Son", f"chesslast_{game_id}"), btn.callback("🏳️ Pes", f"chessres_{game_id}"), btn.callback("🔄 Yeni", f"chessnew_{game_id}")])
    else:
        rows.append([btn.callback("🔄 Rövanş", f"chessnew_{game_id}")])
    
    return btn.inline_keyboard(rows)


def create_buttons_telethon(game_id, board, selected=None, valid_moves=None, flipped=False, status='active'):
    """Telethon için normal butonlar (inline mesajlar)"""
    valid_moves = valid_moves or []
    buttons = []
    row_range = range(7, -1, -1) if flipped else range(8)
    col_range = range(7, -1, -1) if flipped else range(8)
    
    for row in row_range:
        row_btns = []
        for col in col_range:
            piece = board[row][col]
            cb = f"chess_{game_id}_{row}_{col}"
            
            if (row, col) == selected:
                row_btns.append(Button.inline("🔵", cb))
            elif (row, col) in valid_moves:
                row_btns.append(Button.inline("🔴" if piece else "🟢", cb))
            elif piece:
                row_btns.append(Button.inline(PIECE_CHARS.get(piece, '·'), cb))
            else:
                row_btns.append(Button.inline("·", cb))
        buttons.append(row_btns)
    
    if status == 'active':
        buttons.append([Button.inline("⏮ Son", f"chesslast_{game_id}"), Button.inline("🏳️ Pes", f"chessres_{game_id}"), Button.inline("🔄 Yeni", f"chessnew_{game_id}")])
    else:
        buttons.append([Button.inline("🔄 Rövanş", f"chessnew_{game_id}")])
    
    return buttons


def build_board_text(board, flipped=False):
    text = ""
    for row in (range(7, -1, -1) if flipped else range(8)):
        for col in (range(7, -1, -1) if flipped else range(8)):
            piece = board[row][col]
            text += PIECE_CHARS.get(piece, '·') if piece else '·'
        text += "\n"
    return text


# ============================================
# OYUN YÖNETİMİ
# ============================================

def create_chess_game(white_id, white_name, black_id, black_name, chat_id):
    game_id = hashlib.md5(f"{white_id}{black_id}{time.time()}".encode()).hexdigest()[:8]
    CHESS_GAMES[game_id] = {
        'chat_id': chat_id, 'white_id': white_id, 'black_id': black_id,
        'white_name': white_name, 'black_name': black_name,
        'board': create_board(), 'turn': 'w', 'selected': None, 'valid_moves': [],
        'last_move': None, 'last_move_data': None, 'status': 'active', 'moves': []
    }
    return game_id


async def update_game(event, game_id, game, text, flipped=False, selected=None, valid_moves=None):
    """Oyunu güncelle - inline ise Telethon, değilse Bot API"""
    chat_id = event.chat_id
    message_id = event.message_id
    is_inline = chat_id is None
    
    try:
        if is_inline:
            buttons = create_buttons_telethon(game_id, game['board'], selected, valid_moves, flipped, game['status'])
            await event.edit(text, buttons=buttons)
        else:
            keyboard = create_buttons_api(game_id, game['board'], selected, valid_moves, flipped, game['status'])
            await bot_api.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=keyboard)
    except:
        try:
            buttons = create_buttons_telethon(game_id, game['board'], selected, valid_moves, flipped, game['status'])
            await event.edit(text, buttons=buttons)
        except:
            pass


# ============================================
# HANDLER'LAR
# ============================================

def register_chess_handlers(bot):
    
    @bot.on(events.InlineQuery(pattern=r'^chess_([a-f0-9]+)$'))
    async def chess_inline(event):
        game_id = event.pattern_match.group(1)
        game = CHESS_GAMES.get(game_id)
        if not game:
            await event.answer([], cache_time=0)
            return
        
        turn_name = game['white_name'] if game['turn'] == 'w' else game['black_name']
        turn_emoji = "⚪" if game['turn'] == 'w' else "⚫"
        board_text = build_board_text(game['board'])
        
        text = f"♟️ **Satranç**\n\n⚪ {game['white_name']} vs ⚫ {game['black_name']}\nSıra: {turn_emoji} **{turn_name}**\n\n{board_text}"
        buttons = create_buttons_telethon(game_id, game['board'])
        
        result = event.builder.article(title="♟️ Satranç", description=f"⚪ vs ⚫", text=text, buttons=buttons)
        await event.answer([result], cache_time=0)
    
    @bot.on(events.CallbackQuery(pattern=rb"chess_([a-f0-9]+)_(\d)_(\d)"))
    async def chess_click(event):
        match = event.pattern_match
        game_id, row, col = match.group(1).decode(), int(match.group(2)), int(match.group(3))
        
        game = CHESS_GAMES.get(game_id)
        if not game or game['status'] != 'active':
            await event.answer("❌ Oyun bulunamadı!", alert=True)
            return
        
        user_id, color = event.sender_id, game['turn']
        flipped = color == 'b'
        
        if (color == 'w' and user_id != game['white_id']) or (color == 'b' and user_id != game['black_id']):
            await event.answer("⏳ Sıra sende değil!", alert=True)
            return
        
        board, piece = game['board'], game['board'][row][col]
        selected, valid_moves = game['selected'], game['valid_moves']
        
        # Hamle yap
        if selected and (row, col) in valid_moves:
            sr, sc = selected
            moved, captured = board[sr][sc], board[row][col]
            
            game['last_move_data'] = {'from': (sr, sc), 'to': (row, col), 'piece': moved, 'captured': captured}
            board[row][col], board[sr][sc] = moved, ''
            
            if moved[1] == 'p' and row in [0, 7]:
                board[row][col] = moved[0] + 'q'
            
            notation = f"{PIECE_CHARS.get(moved, '')}{pos_to_notation(sr, sc)}{'x' if captured else '-'}{pos_to_notation(row, col)}"
            game['moves'].append(notation)
            game['last_move'] = notation
            game['turn'] = 'b' if color == 'w' else 'w'
            game['selected'], game['valid_moves'] = None, []
            
            new_flipped, next_color = game['turn'] == 'b', game['turn']
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
            board_text = build_board_text(board, new_flipped)
            
            text = f"♟️ **Satranç**\n\n⚪ {game['white_name']} vs ⚫ {game['black_name']}\n"
            if game['status'] == 'active':
                text += f"Sıra: {turn_emoji} **{turn_name}**"
            text += f"{status_text}\n📝 {notation}\n\n{board_text}"
            
            await update_game(event, game_id, game, text, new_flipped)
            await event.answer(f"✅ {notation}")
            return
        
        # Taş seç
        if piece and piece[0] == color:
            moves = get_valid_moves(board, row, col)
            if moves:
                game['selected'], game['valid_moves'] = (row, col), moves
                turn_name = game['white_name'] if game['turn'] == 'w' else game['black_name']
                turn_emoji = "⚪" if game['turn'] == 'w' else "⚫"
                board_text = build_board_text(board, flipped)
                
                text = f"♟️ **Satranç**\n\n⚪ {game['white_name']} vs ⚫ {game['black_name']}\nSıra: {turn_emoji} **{turn_name}**\nSeçili: {PIECE_CHARS.get(piece, '')} `{pos_to_notation(row, col)}`\n\n{board_text}"
                
                await update_game(event, game_id, game, text, flipped, (row, col), moves)
                await event.answer(f"{PIECE_CHARS.get(piece, '')} seçildi")
            else:
                await event.answer("❌ Bu taş hareket edemiyor!", alert=True)
        elif piece:
            await event.answer("❌ Rakibin taşı!", alert=True)
        else:
            if selected:
                game['selected'], game['valid_moves'] = None, []
                turn_name = game['white_name'] if game['turn'] == 'w' else game['black_name']
                turn_emoji = "⚪" if game['turn'] == 'w' else "⚫"
                board_text = build_board_text(board, flipped)
                
                text = f"♟️ **Satranç**\n\n⚪ {game['white_name']} vs ⚫ {game['black_name']}\nSıra: {turn_emoji} **{turn_name}**\n\n{board_text}"
                
                await update_game(event, game_id, game, text, flipped)
                await event.answer("İptal")
    
    @bot.on(events.CallbackQuery(pattern=rb"chesslast_([a-f0-9]+)"))
    async def chess_last(event):
        game_id = event.pattern_match.group(1).decode()
        game = CHESS_GAMES.get(game_id)
        
        if not game:
            await event.answer("❌ Oyun bulunamadı!", alert=True)
            return
        if not game['last_move_data']:
            await event.answer("Henüz hamle yok!", alert=True)
            return
        
        await event.answer(f"⏮️ {game['last_move']}")
    
    @bot.on(events.CallbackQuery(pattern=rb"chessres_([a-f0-9]+)"))
    async def chess_resign(event):
        game_id = event.pattern_match.group(1).decode()
        game = CHESS_GAMES.get(game_id)
        
        if not game or game['status'] != 'active':
            await event.answer("❌ Oyun bulunamadı!", alert=True)
            return
        
        user_id = event.sender_id
        if user_id not in [game['white_id'], game['black_id']]:
            await event.answer("❌ Bu oyunda değilsin!", alert=True)
            return
        
        game['status'] = 'resigned'
        loser = game['white_name'] if user_id == game['white_id'] else game['black_name']
        winner = game['black_name'] if user_id == game['white_id'] else game['white_name']
        
        text = f"♟️ **Satranç**\n\n🏳️ **{loser}** pes etti!\n🏆 **{winner}** kazandı!"
        
        chat_id, message_id = event.chat_id, event.message_id
        is_inline = chat_id is None
        
        try:
            if is_inline:
                await event.edit(text, buttons=[[Button.inline("🔄 Rövanş", f"chessnew_{game_id}")]])
            else:
                keyboard = btn.inline_keyboard([[btn.callback("🔄 Rövanş", f"chessnew_{game_id}")]])
                await bot_api.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=keyboard)
        except:
            try:
                await event.edit(text, buttons=[[Button.inline("🔄 Rövanş", f"chessnew_{game_id}")]])
            except:
                pass
        
        await event.answer("🏳️ Pes ettin!", alert=True)
    
    @bot.on(events.CallbackQuery(pattern=rb"chessnew_([a-f0-9]+)"))
    async def chess_new(event):
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
        game['turn'], game['selected'], game['valid_moves'] = 'w', None, []
        game['last_move'], game['last_move_data'], game['status'], game['moves'] = None, None, 'active', []
        
        board_text = build_board_text(game['board'])
        text = f"♟️ **Satranç** (Rövanş)\n\n⚪ {game['white_name']} vs ⚫ {game['black_name']}\nSıra: ⚪ **{game['white_name']}**\n\n{board_text}"
        
        await update_game(event, game_id, game, text)
        await event.answer("🔄 Rövanş başladı!", alert=True)
    
    print("[CHESS] ✅ Handler'lar yüklendi")
