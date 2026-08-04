"""
Birinin mesajını yanıtlayarak ya da isim yazarak şık animasyonlu efektler gönderin.

🔧 Komutlar: .efektler, .efekt, .kalp, .ates, .bomba, .hack, .matrix, .tokat, .roket, .yildiz, .kader
🚨 Tür: #eğlence


Komular hakında:
.efektler:
kullanılabilir tüm animasyon efektlerini listeler.

.efekt <ad> [isim]:
seçtiğiniz efekti çalıştırır. Örnek: `.efekt kalp Ayşe`

.kalp / .ates / .bomba / .hack / .matrix / .tokat / .roket / .yildiz / .kader:
kısayol komutlarıdır. Bir mesajı yanıtlarsanız o kişinin adını,
komutun yanına isim yazarsanız onu kullanır. Örnek: `.bomba Ali`
"""

import asyncio
import random

from telethon.errors import FloodWaitError, MessageNotModifiedError
from telethon.tl.functions.messages import EditMessageRequest
from telethon.tl.types import MessageEntityPre

from userbot.events import register
from userbot import CMD_HELP
from utils.logger import get_logger

log = get_logger(__name__)

# Kare arası bekleme (Telegram düzenleme limitine takılmayacak kadar)
FRAME_DELAY = 0.45
MAX_FRAMES = 26

# Aynı anda tek animasyon (çift tetikleme / üst üste binme koruması)
_busy = set()


def _bar(pct, width=10):
    dolu = int(width * pct / 100)
    return "[" + "▓" * dolu + "░" * (width - dolu) + f"] {pct}%"


def _f_kalp(n):
    return [
        "💗",
        f"💓  {n}  💓",
        f"💕  💗  {n}  💗  💕",
        f"💞  ❤️  {n}  ❤️  💞",
        f"💖 💗 💓  {n}  💓 💗 💖",
        f"❤️‍🔥  {n}  ❤️‍🔥",
        f"💘  {n}  💘",
        f"💘 {n} kalbimi çaldı! 💘",
    ]


def _f_ates(n):
    return [
        "🔥",
        "🔥🔥",
        f"🔥🔥🔥  {n}",
        f"🔥🔥🔥🔥  {n}  🔥",
        f"🔥🔥🔥🔥🔥  {n}  🔥🔥",
        f"🌋🔥🔥🔥🔥  {n}  🔥🔥🔥",
        f"🌋🌋 {n} kavruldu 🌋🌋",
        f"💨 geriye {n}'den kül kaldı 💨",
    ]


def _f_bomba(n):
    fr = [f"💣 {n} için bomba kuruldu..."]
    for i in (5, 4, 3, 2, 1):
        fr.append(f"💣  {i}")
    fr += ["💥", "💥💥💥", f"☠️ {n} havaya uçtu!", f"🕊️ {n} anısına..."]
    return fr


def _f_hack(n):
    fr = [f"🖥️ hedef kilitlendi: {n}", "🔍 açık aranıyor..."]
    for p in (10, 30, 50, 70, 90, 100):
        fr.append(f"💻 {n}\n{_bar(p)}")
    fr += [f"🔓 şifre kırıldı: ****{random.randint(1000, 9999)}",
           f"😈 {n} hacklendi!"]
    return fr


def _f_matrix(n):
    ch = "01ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘｱﾎﾃﾏｹﾒｴｶ"
    fr = ["🟩 bağlantı kuruluyor..."]
    for _ in range(6):
        satir = "\n".join("".join(random.choice(ch) for _ in range(14)) for _ in range(3))
        fr.append(satir)
    fr += [f"🟩 {n} matrix'e alındı", f"🕶️ hoş geldin, {n}"]
    return fr


def _f_tokat(n):
    return [
        "🤚",
        "🤚      😐",
        "  🤚    😐",
        "    🤚  😮",
        f"      👋😵  {n}",
        f"💫 {n} tokadı yedi!",
        f"😵‍💫 {n} hâlâ dönüyor...",
    ]


def _f_roket(n):
    fr = [f"🚀 {n} fırlatmaya hazır", "3️⃣", "2️⃣", "1️⃣", "🔥 ateşleme!"]
    for i in range(5, 0, -1):
        fr.append("\n" * (i - 1) + f"🚀\n{'☁️' * (6 - i)}")
    fr += [f"🌕 {n} aya ulaştı!", f"👨‍🚀 {n} uzayda kayboldu 🌌"]
    return fr


def _f_yildiz(n):
    return [
        "✨",
        f"✨  ⭐  {n}",
        f"⭐ 🌟 {n} 🌟 ⭐",
        f"🌟 💫 ✨ {n} ✨ 💫 🌟",
        f"💫 {n} parlıyor 💫",
        f"🌠 dilek tut: {n}",
    ]


def _f_kader(n):
    sonuclar = ["efsanevi 🏆", "şanslı 🍀", "gizemli 🔮", "tehlikeli ☠️",
                "tatlı 🍬", "kaotik 🌪️", "efsane ötesi 🚀", "uykucu 😴"]
    return [
        "🔮 kader taşları atılıyor...",
        "🔮 ◽◽◽",
        "🔮 ◼️◽◽",
        "🔮 ◼️◼️◽",
        "🔮 ◼️◼️◼️",
        f"✨ {n} bugün {random.choice(sonuclar)}",
    ]


# ============================================================
#  ASCII SAHNE MOTORU
#  Kareler sabit bir tuval üzerine çizilir → hizalama bozulmaz.
#  Telegram'da monospace (```) blok içinde gönderilir.
# ============================================================
SW, SH = 30, 6          # tuval genişlik / yükseklik (mobil ekrana sığar)
ZEMIN = "‾" * SW

# Çöp adam pozları
_DUR = " O \n/|\\\n/ \\"
_YUR = " O \n/|\\\n/| "
_AT  = " O/\n/| \n/ \\"
_SEV = "\\O/\n | \n/ \\"


def _tuval():
    return [[" "] * SW for _ in range(SH)]


def _ciz(c, x, y, art):
    """Şekli tuvale çizer. BOŞLUKLAR ŞEFFAFTIR → çizimler birbirini silmez."""
    for dy, satir in enumerate(art.split("\n")):
        for dx, ch in enumerate(satir):
            if ch == " ":
                continue
            X, Y = x + dx, y + dy
            if 0 <= Y < SH and 0 <= X < SW:
                c[Y][X] = ch


def _bas(c):
    """Tuvali Telegram monospace bloğuna çevirir."""
    return "\n".join("".join(r).rstrip() for r in c)


def _s_cop(n):
    """Çöp adam ismi taşıyıp çöp kovasına fırlatır."""
    n = n[:7]
    e = f"[{n}]"
    KOVA = " __ \n|::|\n|__|"
    KAPAK = "____\n|::|\n|__|"
    fr = []
    for i, x in enumerate((1, 4, 7, 10)):          # isimle yürüyor
        c = _tuval(); _ciz(c, 23, 1, KOVA); _ciz(c, 0, 5, ZEMIN)
        _ciz(c, x, 1, _YUR if i % 2 else _DUR); _ciz(c, x + 4, 2, e)
        fr.append(_bas(c))
    for x, y in ((16, 0), (19, 0), (22, 0), (23, 0)):   # fırlatıyor
        c = _tuval(); _ciz(c, 23, 1, KOVA); _ciz(c, 0, 5, ZEMIN)
        _ciz(c, 12, 1, _AT); _ciz(c, x, y, e)
        fr.append(_bas(c))
    c = _tuval(); _ciz(c, 23, 1, KOVA); _ciz(c, 0, 5, ZEMIN)      # kovaya düştü
    _ciz(c, 12, 1, _DUR); _ciz(c, 24, 2, n[:2]); fr.append(_bas(c))
    c = _tuval(); _ciz(c, 23, 1, KAPAK); _ciz(c, 0, 5, ZEMIN)     # kapak kapandı
    _ciz(c, 12, 1, _SEV); fr.append(_bas(c))
    return fr


def _s_ufo(n):
    """UFO ışın tutup ismi kaçırır."""
    n = n[:8]
    e = f"[{n}]"
    U = "  _____ \n (_____)\n  o o o "
    ex = (SW - len(e)) // 2
    fr = []
    for x in (0, 5, 9):                              # yaklaşıyor
        c = _tuval(); _ciz(c, 0, 5, ZEMIN); _ciz(c, x, 0, U); _ciz(c, ex, 4, e)
        fr.append(_bas(c))
    for i in range(3):                               # ışın nabzı
        c = _tuval(); _ciz(c, 0, 5, ZEMIN); _ciz(c, 11, 0, U)
        _ciz(c, 12, 3, "\\   /" if i % 2 else " \\ / ")
        _ciz(c, ex, 4, e); fr.append(_bas(c))
    c = _tuval(); _ciz(c, 0, 5, ZEMIN); _ciz(c, 11, 0, U)         # yükseldi
    _ciz(c, ex, 3, e); fr.append(_bas(c))
    c = _tuval(); _ciz(c, 0, 5, ZEMIN); _ciz(c, 11, 0, U); fr.append(_bas(c))
    for x in (15, 21, 27):                           # kaçıyor
        c = _tuval(); _ciz(c, 0, 5, ZEMIN); _ciz(c, x, 0, U); fr.append(_bas(c))
    return fr


def _s_pota(n):
    """İsmi potaya atar, sayı olur."""
    n = n[:5]
    e = f"({n})"
    P = "  _______\n |       |\n |_______|"
    def taban(c):
        _ciz(c, 19, 0, P); _ciz(c, 0, 5, ZEMIN)
    fr = []
    c = _tuval(); taban(c); _ciz(c, 1, 1, _AT); _ciz(c, 5, 1, e); fr.append(_bas(c))
    for x, y in ((7, 0), (11, 0), (15, 0)):
        c = _tuval(); taban(c); _ciz(c, 1, 1, _AT); _ciz(c, x, y, e); fr.append(_bas(c))
    c = _tuval(); taban(c); _ciz(c, 1, 1, _AT); _ciz(c, 21, 1, e); fr.append(_bas(c))
    c = _tuval(); taban(c); _ciz(c, 1, 1, _AT); _ciz(c, 21, 3, e); fr.append(_bas(c))
    c = _tuval(); taban(c); _ciz(c, 1, 1, _SEV); _ciz(c, 21, 3, e); fr.append(_bas(c))
    return fr


def _s_balyoz(n):
    """Çöp adam balyozu kaldırır ve ismi yerle bir eder."""
    n = n[:8]
    e = f"[{n}]"
    CEKIC_UST = "____\n|__|\n |"
    CEKIC_YAN = "  ____\n /|__|\n/"
    KALK = " O_\n/| \n/ \\"
    VUR  = " O \n/|\\\n/ \\"
    SEV  = "\\O/\n | \n/ \\"
    fr = []

    def zem(c):
        _ciz(c, 0, 5, ZEMIN)

    c = _tuval(); zem(c); _ciz(c, 6, 2, KALK); _ciz(c, 8, 0, CEKIC_UST); _ciz(c, 18, 4, e)
    fr.append(_bas(c))                                    # balyozu kaldırdı
    c = _tuval(); zem(c); _ciz(c, 6, 2, KALK); _ciz(c, 9, 0, CEKIC_UST); _ciz(c, 18, 4, e)
    fr.append(_bas(c))                                    # tepede sallanıyor
    c = _tuval(); zem(c); _ciz(c, 6, 2, VUR); _ciz(c, 13, 1, CEKIC_YAN); _ciz(c, 18, 4, e)
    fr.append(_bas(c))                                    # iniyor
    c = _tuval(); zem(c); _ciz(c, 6, 2, VUR); _ciz(c, 16, 2, "____\n|__|")
    _ciz(c, 15, 4, "*"); _ciz(c, 24, 4, "*"); _ciz(c, 18, 4, e)
    fr.append(_bas(c))                                    # ÇARPTI
    c = _tuval(); zem(c); _ciz(c, 6, 2, VUR); _ciz(c, 16, 2, "____\n|__|")
    _ciz(c, 15, 4, "*  ~~~  *")
    fr.append(_bas(c))                                    # toz bulutu
    c = _tuval(); zem(c); _ciz(c, 6, 2, SEV); _ciz(c, 18, 4, "_" * len(e))
    fr.append(_bas(c))                                    # yerle bir
    return fr


# --- Poz varyantları (romantik sahneler için) ---
_DIZ = " O \n/|\\\n_|_"
_OLTA = " O /\n/|/\n/ \\"


def _s_evlen(n):
    """Diz çöküp yüzükle evlenme teklifi eder."""
    n = n[:8]
    gx = 20
    nx = max(0, gx - (len(n) - 3) // 2)
    fr = []

    def base(c):
        _ciz(c, 0, 5, ZEMIN); _ciz(c, gx, 2, _DUR); _ciz(c, nx, 1, n)

    for x in (2, 5, 8):
        c = _tuval(); base(c); _ciz(c, x, 2, _YUR); fr.append(_bas(c))
    c = _tuval(); base(c); _ciz(c, 12, 2, _DIZ); fr.append(_bas(c))
    for r in ("o", "O", "o"):
        c = _tuval(); base(c); _ciz(c, 12, 2, _DIZ); _ciz(c, 16, 2, r); fr.append(_bas(c))
    c = _tuval(); base(c); _ciz(c, 12, 2, _DIZ); _ciz(c, 16, 2, "o")
    _ciz(c, 1, 0, "benimle evlenir misin?"); fr.append(_bas(c))
    c = _tuval(); _ciz(c, 0, 5, ZEMIN); _ciz(c, nx, 1, n)
    _ciz(c, 12, 2, _SEV); _ciz(c, gx, 2, _SEV); _ciz(c, 16, 0, "<3"); fr.append(_bas(c))
    return fr


def _s_gul(n):
    """Elinde gülle yürüyüp hediye eder."""
    n = n[:8]
    GUL = "@\n|\n|"
    gx = 22
    nx = max(0, gx - (len(n) - 3) // 2)
    fr = []

    def base(c):
        _ciz(c, 0, 5, ZEMIN); _ciz(c, gx, 2, _DUR); _ciz(c, nx, 1, n)

    for x in (1, 5, 9, 13):
        c = _tuval(); base(c); _ciz(c, x, 2, _YUR); _ciz(c, x + 4, 2, GUL); fr.append(_bas(c))
    c = _tuval(); base(c); _ciz(c, 15, 2, _DUR); _ciz(c, 19, 2, GUL); fr.append(_bas(c))
    c = _tuval(); base(c); _ciz(c, 15, 2, _DUR); _ciz(c, 20, 2, "@")
    _ciz(c, 4, 0, "senin icin"); fr.append(_bas(c))
    c = _tuval(); _ciz(c, 0, 5, ZEMIN); _ciz(c, nx, 1, n)
    _ciz(c, 15, 2, _SEV); _ciz(c, gx, 2, _SEV); _ciz(c, 18, 0, ". * ."); fr.append(_bas(c))
    return fr


def _s_ask(n):
    """İsmin altında atan büyük ASCII kalp."""
    n = n[:10]
    KUCUK = "  ,d8b.d8b,\n  88888888'\n   `Y88Y'"
    BUYUK = " ,d88b.d88b,\n 88888888888\n `Y8888888Y'\n   `Y888Y'"
    fr = []
    for a in (KUCUK, BUYUK, KUCUK, BUYUK, KUCUK, BUYUK):
        c = _tuval()
        _ciz(c, 9, 1, a)
        _ciz(c, max(0, (SW - len(n)) // 2), 0, n)
        fr.append(_bas(c))
    return fr


def _s_tren(n):
    """İsim rayda kalır, tren geçer."""
    n = n[:6]
    e = f"[{n}]"
    T = " ____\n|[]|_n_\n|__|_|_|\n(o)(o)(o)"
    RAY = "=" * SW
    fr = []
    for x in (-8, -2, 4, 10):
        c = _tuval(); _ciz(c, 0, 5, RAY); _ciz(c, 20, 4, e); _ciz(c, x, 1, T); fr.append(_bas(c))
    c = _tuval(); _ciz(c, 0, 5, RAY); _ciz(c, 16, 1, T); _ciz(c, 20, 4, "* ~ *"); fr.append(_bas(c))
    for x in (22, 28):
        c = _tuval(); _ciz(c, 0, 5, RAY); _ciz(c, x, 1, T); fr.append(_bas(c))
    return fr


def _s_balik(n):
    """Oltayla ismi sudan çeker."""
    n = n[:7]
    e = f"<{n}>"
    SU = "~" * SW
    fr = []

    def base(c):
        _ciz(c, 0, 4, SU); _ciz(c, 1, 1, _OLTA); _ciz(c, 14, 2, "\\")

    for i in range(3):
        c = _tuval(); base(c); _ciz(c, 15, 3, "|")
        _ciz(c, 15, 4, "o" if i % 2 else "O"); fr.append(_bas(c))
    c = _tuval(); base(c); _ciz(c, 15, 3, "|"); _ciz(c, 13, 5, e); fr.append(_bas(c))
    for y in (4, 3, 2):
        c = _tuval(); base(c); _ciz(c, 13, y, e); fr.append(_bas(c))
    c = _tuval(); _ciz(c, 0, 4, SU); _ciz(c, 1, 1, _SEV); _ciz(c, 12, 1, e); fr.append(_bas(c))
    return fr


def _s_gol(n):
    """İsmi kaleye gönderir."""
    n = n[:6]
    e = f"({n})"
    KALE = "  ____\n |    |\n |____|"
    fr = []

    def base(c):
        _ciz(c, 0, 5, ZEMIN); _ciz(c, 21, 1, KALE)

    c = _tuval(); base(c); _ciz(c, 1, 2, _DUR); _ciz(c, 5, 3, e); fr.append(_bas(c))
    c = _tuval(); base(c); _ciz(c, 1, 2, _YUR); _ciz(c, 7, 3, e); fr.append(_bas(c))
    for x, y in ((10, 2), (14, 1), (16, 1), (22, 2)):
        c = _tuval(); base(c); _ciz(c, 1, 2, _YUR); _ciz(c, x, y, e); fr.append(_bas(c))
    c = _tuval(); base(c); _ciz(c, 1, 2, _SEV); _ciz(c, 22, 2, e)
    _ciz(c, 10, 0, "G O L !"); fr.append(_bas(c))
    return fr


EFFECTS = {
    "kalp": ("💘 Kalp", _f_kalp, False),
    "ates": ("🔥 Ateş", _f_ates, False),
    "bomba": ("💣 Bomba", _f_bomba, False),
    "hack": ("😈 Hack", _f_hack, False),
    "matrix": ("🟩 Matrix", _f_matrix, True),
    "tokat": ("👋 Tokat", _f_tokat, False),
    "roket": ("🚀 Roket", _f_roket, False),
    "yildiz": ("🌟 Yıldız", _f_yildiz, False),
    "kader": ("🔮 Kader", _f_kader, False),
    # --- ASCII sahneler (çöp adam animasyonları) ---
    "cop": ("🗑️ Çöpe At", _s_cop, True),
    "ufo": ("🛸 UFO", _s_ufo, True),
    "pota": ("🏀 Pota", _s_pota, True),
    "balyoz": ("🔨 Balyoz", _s_balyoz, True),
    # --- romantik sahneler ---
    "evlen":  ("💍 Evlenme Teklifi", _s_evlen, True),
    "gul":    ("🌹 Gül Ver", _s_gul, True),
    "ask":    ("💖 Atan Kalp", _s_ask, True),
    # --- diğer sahneler ---
    "tren":   ("🚂 Tren", _s_tren, True),
    "balik":  ("🎣 Balık Tut", _s_balik, True),
    "gol":    ("⚽ Gol", _s_gol, True),
}

# Türkçe karakter toleransı
_ALIAS = {"ateş": "ates", "yıldız": "yildiz", "yildız": "yildiz", "atesh": "ates", "çöp": "cop", "cöp": "cop", "gül": "gul", "aşk": "ask", "balık": "balik"}


async def _target_name(event, arg):
    """İsim: önce komut argümanı, yoksa yanıtlanan kişi, o da yoksa 'birisi'."""
    if arg:
        return arg.strip()[:40]
    try:
        reply = await event.get_reply_message()
        if reply:
            sender = await reply.get_sender()
            ad = (getattr(sender, "first_name", None)
                  or getattr(sender, "title", None)
                  or getattr(sender, "username", None))
            if ad:
                return str(ad)[:40]
    except Exception:
        log.debug("Hedef isim alınamadı", exc_info=True)
    return "birisi"


def _u16len(s):
    return len(s.encode("utf-16-le")) // 2


async def _animate(event, frames, mono=False):
    """Kareleri sırayla mesaja yazar.
    NOT: client.edit_message yerine ham istek kullanılır — böylece çeviri
    katmanı her kareyi tek tek çevirmeye çalışıp animasyonu yavaşlatmaz."""
    try:
        peer = await event.get_input_chat()
    except Exception:
        peer = None
    mid = event.id

    for frame in frames[:MAX_FRAMES]:
        try:
            ents = None
            if mono:
                # ASCII sahneler hizalı görünsün diye monospace ENTITY ile gönderilir.
                # (Ham istek markdown işlemez; ``` yazmak düz metin olarak görünürdü.)
                ents = [MessageEntityPre(offset=0, length=_u16len(frame), language="")]
            if peer is not None:
                await event.client(EditMessageRequest(
                    peer=peer, id=mid, message=frame, no_webpage=True, entities=ents))
            else:
                await event.edit(f"`{frame}`" if mono else frame)
        except MessageNotModifiedError:
            pass
        except FloodWaitError as fw:
            bekle = int(getattr(fw, "seconds", 0) or 0)
            if bekle > 5:
                log.info("Efekt durduruldu (FloodWait %ss)", bekle)
                return
            await asyncio.sleep(bekle + 1)
        except Exception:
            log.debug("Efekt karesi yazılamadı", exc_info=True)
            return
        await asyncio.sleep(FRAME_DELAY)


async def _run_effect(event, key, arg):
    key = _ALIAS.get(key, key)
    if key not in EFFECTS:
        await event.edit(f"`❌ Böyle bir efekt yok. Liste için:` `.efektler`")
        return
    uid = event.sender_id
    if uid in _busy:
        return
    _busy.add(uid)
    try:
        ad = await _target_name(event, arg)
        _, uret, mono = EFFECTS[key]
        await _animate(event, uret(ad), mono=mono)
    finally:
        _busy.discard(uid)


@register(outgoing=True, pattern=r"^\.efektler$")
async def efekt_liste(event):
    if event.fwd_from:
        return
    satir = "\n".join(f"• `.{k}` — {ad}" for k, (ad, _f, _m) in EFFECTS.items())
    await event.edit(
        "**✨ Animasyon Efektleri**\n\n"
        f"{satir}\n\n"
        "**Kullanım:**\n"
        "• Bir mesajı yanıtla → `.kalp`\n"
        "• Ya da isim yaz → `.bomba Ali`\n"
        "• Genel kullanım → `.efekt hack Ayşe`"
    )


@register(outgoing=True, pattern=r"^\.efekt(?:\s+(\S+))?(?:\s+(.+))?$")
async def efekt_genel(event):
    if event.fwd_from:
        return
    key = (event.pattern_match.group(1) or "").strip().lower()
    arg = event.pattern_match.group(2)
    if not key:
        await event.edit("`✨ Kullanım: .efekt <ad> [isim]  ·  Liste: .efektler`")
        return
    await _run_effect(event, key, arg)


@register(outgoing=True,
          pattern=r"^\.(?:kalp|ates|ateş|bomba|hack|matrix|tokat|roket|yildiz|yıldız|kader|cop|çöp|ufo|pota|balyoz|evlen|gul|gül|ask|aşk|tren|balik|balık|gol)(?:\s+(.+))?$")
async def efekt_kisayol(event):
    # NOT: alternatifler (?:...) ile yazıldı — plugin komut çıkarıcısı yalnızca
    # bu biçimi tanıyor; (a|b) yazılırsa kısayollar menüde görünmüyor.
    if event.fwd_from:
        return
    try:
        key = (event.text or "").split()[0].lstrip(".").lower()
    except Exception:
        return
    arg = event.pattern_match.group(1)
    await _run_effect(event, key, arg)


CMD_HELP.update({
    "efekt":
    "`.efektler` - Tüm animasyon efektlerini listeler\n"
    "`.efekt <ad> [isim]` - Seçilen efekti çalıştırır\n"
    "`.kalp` `.ates` `.bomba` `.hack` `.matrix` `.tokat` `.roket` `.yildiz` `.kader`\n"
    "`.cop` `.ufo` `.pota` `.balyoz` `.tren` `.balik` `.gol` — ASCII sahneler\n"
    "`.evlen` `.gul` `.ask` — romantik sahneler\n"
    "Bir mesajı yanıtla → o kişinin adı kullanılır, ya da komutun yanına isim yaz."
})
