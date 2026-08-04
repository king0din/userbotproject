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
        fr.append(f"```\n{satir}\n```")
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


EFFECTS = {
    "kalp":   ("💘 Kalp",    _f_kalp),
    "ates":   ("🔥 Ateş",    _f_ates),
    "bomba":  ("💣 Bomba",   _f_bomba),
    "hack":   ("😈 Hack",    _f_hack),
    "matrix": ("🟩 Matrix",  _f_matrix),
    "tokat":  ("👋 Tokat",   _f_tokat),
    "roket":  ("🚀 Roket",   _f_roket),
    "yildiz": ("🌟 Yıldız",  _f_yildiz),
    "kader":  ("🔮 Kader",   _f_kader),
}

# Türkçe karakter toleransı
_ALIAS = {"ateş": "ates", "yıldız": "yildiz", "yildız": "yildiz", "atesh": "ates"}


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


async def _animate(event, frames):
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
            if peer is not None:
                await event.client(EditMessageRequest(
                    peer=peer, id=mid, message=frame, no_webpage=True))
            else:
                await event.edit(frame)
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
        _, uret = EFFECTS[key]
        await _animate(event, uret(ad))
    finally:
        _busy.discard(uid)


@register(outgoing=True, pattern=r"^\.efektler$")
async def efekt_liste(event):
    if event.fwd_from:
        return
    satir = "\n".join(f"• `.{k}` — {ad}" for k, (ad, _) in EFFECTS.items())
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
          pattern=r"^\.(?:kalp|ates|ateş|bomba|hack|matrix|tokat|roket|yildiz|yıldız|kader)(?:\s+(.+))?$")
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
    "Bir mesajı yanıtla → o kişinin adı kullanılır, ya da komutun yanına isim yaz."
})
