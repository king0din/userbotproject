# ============================================
# KingTG UserBot Service - Chess Game Handler
# ============================================
# Grup: Bot gruba eklenir, tek mesaj, tahta döner
# Özel: Her kullanıcıya ayrı mesaj, tahta dönmez
# Premium emoji butonlar
# ============================================

from telethon import events, Button
import hashlib
import time
import config

from utils.bot_api import bot_api, btn

CHESS_GAMES = {}

# Premium Emoji ID'leri
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


def pos_to_notation(r, c):
    return f"{chr(97+c)}{8-r}"


def get_valid_moves(board, row, col, check_check=True):
    piece = board[row][col]
    if not piece: return []
    color, ptype = piece[0], piece[1]
    moves = []
    
    def ok(r, c): return 0 <= r < 8 and 0 <= c < 8
    def enemy(r, c): return ok(r, c) and board[r][c] and board[r][c][0] != color
    def empty(r, c): return ok(r, c) and not board[r][c]
    def can_go(r, c): return ok(r, c) and (not board[r][c] or board[r][c][0] != color)

    if ptype == 'p':
        d = -1 if color == 'w' else 1
        start = 6 if color == 'w' else 1
        if empty(row+d, col):
            moves.append((row+d, col))
            if row == start and empty(row+2*d, col): moves.append((row+2*d, col))
        for dc in [-1, 1]:
            if enemy(row+d, col+dc): moves.append((row+d, col+dc))
    elif ptype in ['r', 'q']:
        for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)] + ([(1,1),(1,-1),(-1,1),(-1,-1)] if ptype == 'q' else []):
            for i in range(1, 8):
                nr, nc = row+dr*i, col+dc*i
                if not ok(nr, nc): break
                if empty(nr, nc): moves.append((nr, nc))
                elif enemy(nr, nc): moves.append((nr, nc)); break
                else: break
    elif ptype == 'b':
        for dr, dc in [(1,1),(1,-1),(-1,1),(-1,-1)]:
            for i in range(1, 8):
                nr, nc = row+dr*i, col+dc*i
                if not ok(nr, nc): break
                if empty(nr, nc): moves.append((nr, nc))
                elif enemy(nr, nc): moves.append((nr, nc)); break
                else: break
    elif ptype == 'n':
        for dr, dc in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
            if can_go(row+dr, col+dc): moves.append((row+dr, col+dc))
    elif ptype == 'k':
        for dr in [-1,0,1]:
            for dc in [-1,0,1]:
                if (dr or dc) and can_go(row+dr, col+dc): moves.append((row+dr, col+dc))

    if check_check:
        legal = []
        for m in moves:
            test = [r[:] for r in board]
            test[m[0]][m[1]], test[row][col] = test[row][col], ''
            if not is_in_check(test, color): legal.append(m)
        return legal
    return moves


def find_king(board, color):
    for r in range(8):
        for c in range(8):
            if board[r][c] == color + 'k': return (r, c)
    return None


def is_in_check(board, color):
    king = find_king(board, color)
    if not king: return False
    enemy = 'b' if color == 'w' else 'w'
    for r in range(8):
        for c in range(8):
            if board[r][c] and board[r][c][0] == enemy:
                if king in get_valid_moves(board, r, c, False): return True
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


def create_buttons(game_id, board, selected=None, valid_moves=None, flipped=False, status='active'):
    valid_moves = valid_moves or []
    rows = []
    for row in (range(7,-1,-1) if flipped else range(8)):
        r = []
        for col in (range(7,-1,-1) if flipped else range(8)):
            piece = board[row][col]
            cb = f"ch_{game_id}_{row}_{col}"
            if (row, col) == selected:
                r.append(btn.callback("🔵", cb, icon_custom_emoji_id=EMOJI_SELECTED))
            elif (row, col) in valid_moves:
                r.append(btn.callback("🔴" if piece else "🟢", cb, icon_custom_emoji_id=EMOJI_CAPTURE if piece else EMOJI_VALID_MOVE))
            elif piece:
                r.append(btn.callback(PIECE_CHARS.get(piece, '·'), cb, icon_custom_emoji_id=PIECE_EMOJI_IDS.get(piece)))
            else:
                r.append(btn.callback("·", cb, icon_custom_emoji_id=EMOJI_EMPTY))
        rows.append(r)
    
    if status == 'active':
        rows.append([btn.callback("⏮", f"chl_{game_id}"), btn.callback("🏳️", f"chr_{game_id}"), btn.callback("🔄", f"chn_{game_id}")])
    else:
        rows.append([btn.callback("🔄 Rövanş", f"chn_{game_id}")])
    return btn.inline_keyboard(rows)


def build_text(board, flipped=False):
    t = ""
    for row in (range(7,-1,-1) if flipped else range(8)):
        for col in (range(7,-1,-1) if flipped else range(8)):
            t += PIECE_CHARS.get(board[row][col], '·') if board[row][col] else '·'
        t += "\n"
    return t


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


async def update_user(uid, mid, gid, game, is_w):
    flipped = not is_w
    color = 'w' if is_w else 'b'
    my_turn = game['turn'] == color
    sel = game['sel'] if my_turn else None
    vm = game['moves'] if my_turn else []
    
    opp = game['bname'] if is_w else game['wname']
    side = "⚪ Beyaz" if is_w else "⚫ Siyah"
    
    txt = f"♟️ **Satranç**\n\nSen: {side}\nRakip: {opp}\n"
    
    if game['status'] == 'active':
        txt += f"Sıra: {'**SEN**' if my_turn else ('Rakip' if not my_turn else '')}\n"
    
    if game['status'] == 'checkmate':
        winner = game['wname'] if game['turn'] == 'b' else game['bname']
        txt += f"\n🏆 **ŞAH MAT!** {winner} kazandı!\n"
    elif game['status'] == 'stalemate':
        txt += "\n🤝 **PAT!** Berabere!\n"
    elif game['status'] == 'resigned':
        txt += "\n🏳️ Oyun bitti!\n"
    elif is_in_check(game['board'], game['turn']):
        txt += "⚠️ **ŞAH!**\n"
    
    if game['last']:
        txt += f"📝 {game['last']}\n"
    if sel:
        p = game['board'][sel[0]][sel[1]]
        txt += f"Seçili: {PIECE_CHARS.get(p,'')} `{pos_to_notation(sel[0],sel[1])}`\n"
    
    txt += f"\n{build_text(game['board'], flipped)}"
    kb = create_buttons(gid, game['board'], sel, vm, flipped, game['status'])
    
    await bot_api.edit_message_text(chat_id=uid, message_id=mid, text=txt, reply_markup=kb)


async def update_group(gid, game, sel=None, vm=None):
    flipped = game['turn'] == 'b'
    turn_name = game['wname'] if game['turn'] == 'w' else game['bname']
    te = "⚪" if game['turn'] == 'w' else "⚫"
    
    txt = f"♟️ **Satranç**\n\n⚪ {game['wname']} vs ⚫ {game['bname']}\n"
    
    if game['status'] == 'active':
        txt += f"Sıra: {te} **{turn_name}**\n"
    
    if game['status'] == 'checkmate':
        winner = game['wname'] if game['turn'] == 'b' else game['bname']
        txt += f"\n🏆 **ŞAH MAT!** {winner} kazandı!\n"
    elif game['status'] == 'stalemate':
        txt += "\n🤝 **PAT!** Berabere!\n"
    elif game['status'] == 'resigned':
        txt += "\n🏳️ Oyun bitti!\n"
    elif is_in_check(game['board'], game['turn']):
        txt += "⚠️ **ŞAH!**\n"
    
    if game['last']:
        txt += f"📝 {game['last']}\n"
    if sel:
        p = game['board'][sel[0]][sel[1]]
        txt += f"Seçili: {PIECE_CHARS.get(p,'')} `{pos_to_notation(sel[0],sel[1])}`\n"
    
    txt += f"\n{build_text(game['board'], flipped)}"
    kb = create_buttons(gid, game['board'], sel, vm, flipped, game['status'])
    
    await bot_api.edit_message_text(chat_id=game['gid'], message_id=game['gmsg'], text=txt, reply_markup=kb)


def register_chess_handlers(bot):
    
    @bot.on(events.NewMessage(pattern=r'^/start chess_(\w+)$'))
    async def chess_deep_link(event):
        gid = event.pattern_match.group(1)
        game = CHESS_GAMES.get(gid)
        if not game:
            await event.respond("❌ Oyun bulunamadı veya süresi doldu!")
            return
        
        uid = event.sender_id
        if uid != game['bid']:
            await event.respond("❌ Bu oyun sana ait değil!")
            return
        
        if game['b_started']:
            await event.respond("✅ Zaten katıldın!")
            return
        
        game['b_started'] = True
        
        # Siyaha tahta gönder
        txt = f"♟️ **Satranç**\n\nSen: ⚫ Siyah\nRakip: {game['wname']}\nSıra: Rakip\n\n{build_text(game['board'], True)}"
        kb = create_buttons(gid, game['board'], flipped=True)
        res = await bot_api.send_message(chat_id=uid, text=txt, reply_markup=kb)
        if res.get('ok'):
            game['bmsg'] = res['result']['message_id']
        
        # Beyazı güncelle
        if game['wmsg']:
            await update_user(game['wid'], game['wmsg'], gid, game, True)
        
        await event.respond("✅ Oyuna katıldın! Yukarıdaki mesajdan oyna.")
    
    @bot.on(events.CallbackQuery(pattern=rb"chess_accept_([a-f0-9]+)"))
    async def chess_accept(event):
        """Oyun davetini kabul et"""
        gid = event.pattern_match.group(1).decode()
        game = CHESS_GAMES.get(gid)
        
        if not game:
            await event.answer("❌ Oyun bulunamadı!", alert=True)
            return
        
        uid = event.sender_id
        if uid != game['bid']:
            await event.answer("❌ Bu oyun sana ait değil!", alert=True)
            return
        
        if game['b_started']:
            await event.answer("✅ Zaten katıldın!")
            return
        
        game['b_started'] = True
        
        # Siyahın mesajını güncelle - tahta göster
        txt = f"♟️ **Satranç**\n\nSen: ⚫ Siyah\nRakip: {game['wname']}\nSıra: Rakip\n\n{build_text(game['board'], True)}"
        kb = create_buttons(gid, game['board'], flipped=True)
        
        await bot_api.edit_message_text(
            chat_id=uid,
            message_id=event.message_id,
            text=txt,
            reply_markup=kb
        )
        
        # Beyazı güncelle
        if game['wmsg']:
            await update_user(game['wid'], game['wmsg'], gid, game, True)
        
        await event.answer("✅ Oyun başladı!")
    
    @bot.on(events.CallbackQuery(pattern=rb"ch_([a-f0-9]+)_(\d)_(\d)"))
    async def chess_click(event):
        m = event.pattern_match
        gid, row, col = m.group(1).decode(), int(m.group(2)), int(m.group(3))
        
        game = CHESS_GAMES.get(gid)
        if not game or game['status'] != 'active':
            await event.answer("❌ Oyun bulunamadı!", alert=True)
            return
        
        uid = event.sender_id
        color = game['turn']
        cur = game['wid'] if color == 'w' else game['bid']
        
        if uid != cur:
            await event.answer("⏳ Sıra sende değil!", alert=True)
            return
        
        # Özel sohbette rakip başlatmadıysa
        if not game['is_group'] and not game['b_started']:
            await event.answer("⏳ Rakip henüz katılmadı!", alert=True)
            return
        
        board = game['board']
        piece = board[row][col]
        sel, vm = game['sel'], game['moves']
        is_w = uid == game['wid']
        
        # Hamle yap
        if sel and (row, col) in vm:
            sr, sc = sel
            moved, captured = board[sr][sc], board[row][col]
            game['last_data'] = {'from': sel, 'to': (row, col), 'piece': moved, 'captured': captured}
            board[row][col], board[sr][sc] = moved, ''
            
            if moved[1] == 'p' and row in [0, 7]:
                board[row][col] = moved[0] + 'q'
            
            notation = f"{PIECE_CHARS.get(moved,'')}{pos_to_notation(sr,sc)}{'x' if captured else '-'}{pos_to_notation(row,col)}"
            game['history'].append(notation)
            game['last'] = notation
            game['turn'] = 'b' if color == 'w' else 'w'
            game['sel'], game['moves'] = None, []
            
            if is_checkmate(board, game['turn']): game['status'] = 'checkmate'
            elif is_stalemate(board, game['turn']): game['status'] = 'stalemate'
            
            if game['is_group']:
                await update_group(gid, game)
            else:
                if game['wmsg']: await update_user(game['wid'], game['wmsg'], gid, game, True)
                if game['bmsg']: await update_user(game['bid'], game['bmsg'], gid, game, False)
            
            await event.answer(f"✅ {notation}")
            return
        
        # Taş seç
        if piece and piece[0] == color:
            mvs = get_valid_moves(board, row, col)
            if mvs:
                game['sel'], game['moves'] = (row, col), mvs
                if game['is_group']:
                    await update_group(gid, game, (row, col), mvs)
                else:
                    mid = game['wmsg'] if is_w else game['bmsg']
                    if mid:
                        # Sadece tıklayan kullanıcının mesajını güncelle
                        flipped = not is_w
                        txt = f"♟️ **Satranç**\n\nSen: {'⚪ Beyaz' if is_w else '⚫ Siyah'}\nRakip: {game['bname'] if is_w else game['wname']}\nSıra: **SEN**\n"
                        txt += f"Seçili: {PIECE_CHARS.get(piece,'')} `{pos_to_notation(row,col)}`\n"
                        txt += f"\n{build_text(board, flipped)}"
                        kb = create_buttons(gid, board, (row,col), mvs, flipped)
                        await bot_api.edit_message_text(chat_id=uid, message_id=mid, text=txt, reply_markup=kb)
                await event.answer(f"{PIECE_CHARS.get(piece,'')} seçildi")
            else:
                await event.answer("❌ Bu taş hareket edemiyor!", alert=True)
        elif piece:
            await event.answer("❌ Rakibin taşı!", alert=True)
        else:
            if sel:
                game['sel'], game['moves'] = None, []
                if game['is_group']:
                    await update_group(gid, game)
                else:
                    mid = game['wmsg'] if is_w else game['bmsg']
                    if mid: await update_user(uid, mid, gid, game, is_w)
                await event.answer("İptal")
    
    @bot.on(events.CallbackQuery(pattern=rb"chl_([a-f0-9]+)"))
    async def chess_last(event):
        gid = event.pattern_match.group(1).decode()
        game = CHESS_GAMES.get(gid)
        if game and game['last']:
            await event.answer(f"⏮️ {game['last']}")
        else:
            await event.answer("Henüz hamle yok!", alert=True)
    
    @bot.on(events.CallbackQuery(pattern=rb"chr_([a-f0-9]+)"))
    async def chess_resign(event):
        gid = event.pattern_match.group(1).decode()
        game = CHESS_GAMES.get(gid)
        if not game or game['status'] != 'active':
            await event.answer("❌ Oyun bulunamadı!", alert=True)
            return
        
        uid = event.sender_id
        if uid not in [game['wid'], game['bid']]:
            await event.answer("❌ Bu oyunda değilsin!", alert=True)
            return
        
        game['status'] = 'resigned'
        loser = game['wname'] if uid == game['wid'] else game['bname']
        winner = game['bname'] if uid == game['wid'] else game['wname']
        
        txt = f"♟️ **Satranç**\n\n🏳️ **{loser}** pes etti!\n🏆 **{winner}** kazandı!"
        kb = btn.inline_keyboard([[btn.callback("🔄 Rövanş", f"chn_{gid}")]])
        
        if game['is_group']:
            await bot_api.edit_message_text(chat_id=game['gid'], message_id=game['gmsg'], text=txt, reply_markup=kb)
        else:
            if game['wmsg']:
                try: await bot_api.edit_message_text(chat_id=game['wid'], message_id=game['wmsg'], text=txt, reply_markup=kb)
                except: pass
            if game['bmsg']:
                try: await bot_api.edit_message_text(chat_id=game['bid'], message_id=game['bmsg'], text=txt, reply_markup=kb)
                except: pass
        
        await event.answer("🏳️ Pes ettin!", alert=True)
    
    @bot.on(events.CallbackQuery(pattern=rb"chn_([a-f0-9]+)"))
    async def chess_new(event):
        gid = event.pattern_match.group(1).decode()
        game = CHESS_GAMES.get(gid)
        if not game:
            await event.answer("❌ Oyun bulunamadı!", alert=True)
            return
        
        uid = event.sender_id
        if uid not in [game['wid'], game['bid']]:
            await event.answer("❌ Bu oyunda değilsin!", alert=True)
            return
        
        # Taraf değiştir
        game['wid'], game['bid'] = game['bid'], game['wid']
        game['wname'], game['bname'] = game['bname'], game['wname']
        game['wmsg'], game['bmsg'] = game['bmsg'], game['wmsg']
        game['board'] = create_board()
        game['turn'], game['sel'], game['moves'] = 'w', None, []
        game['last'], game['last_data'], game['status'], game['history'] = None, None, 'active', []
        
        if game['is_group']:
            await update_group(gid, game)
        else:
            if game['wmsg']: await update_user(game['wid'], game['wmsg'], gid, game, True)
            if game['bmsg']: await update_user(game['bid'], game['bmsg'], gid, game, False)
        
        await event.answer("🔄 Rövanş!", alert=True)
    
    print("[CHESS] ✅ Handler'lar yüklendi")
