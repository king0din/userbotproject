# ============================================
# KingTG UserBot Service - Eski Plugin Uyumluluk Katmanı
# ============================================
# Bu modül eski SedUserBot, AsenaUserBot vb. pluginlerinin
# çalışabilmesi için gerekli değişkenleri ve fonksiyonları sağlar.
# ============================================

# Eski pluginlerin kullandığı global değişkenler
CMD_HELP = {}
CMD_LIST = {}
SUDO_LIST = []
BLACKLIST = []
LOGS = None
COUNT_MSG = 0
USERS = {}
BRAIN_CHECKER = []

# Zalgo karakterleri (bazı pluginlerde kullanılıyor)
ZALG_LIST = [
    "̖", "̗", "̘", "̙", "̜", "̝", "̞", "̟", "̠", "̤", "̥", "̦", "̩", "̪", "̫", 
    "̬", "̭", "̮", "̯", "̰", "̱", "̲", "̳", "̹", "̺", "̻", "̼", "ͅ", "͇", "͈", 
    "͉", "͍", "͎", "͓", "͔", "͕", "͖", "͙", "͚", "̣", "̕", "̛", "̀", "́", 
    "͘", "̡", "̢", "̧", "̨", "̴", "̵", "̶", "͏", "͜", "͝", "͞", "͟", "͠", 
    "͢", "̸", "̷", "͡", "҉", "̍", "̎", "̄", "̅", "̿", "̑", "̆", "̐", "͒", 
    "͗", "͑", "̇", "̈", "̊", "͂", "̓", "̈́", "͊", "͋", "͌", "̃", "̂", "̌", 
    "͐", "̀", "́", "̋", "̏", "̽", "̉", "ͣ", "ͤ", "ͥ", "ͦ", "ͧ", "ͨ", "ͩ", 
    "ͪ", "ͫ", "ͬ", "ͭ", "ͮ", "ͯ", "̾", "͛", "͆", "̚"
]

# Bot referansları (plugin yüklenirken ayarlanacak)
bot = None
tgbot = None

# Temel fonksiyonlar
async def edit_or_reply(event, text, **kwargs):
    """Mesajı düzenle veya yanıtla"""
    try:
        return await event.edit(text, **kwargs)
    except:
        return await event.reply(text, **kwargs)

async def edit_delete(event, text, time=5):
    """Mesajı düzenle ve sil"""
    import asyncio
    msg = await event.edit(text)
    await asyncio.sleep(time)
    await msg.delete()

def run_command(cmd):
    """Shell komutu çalıştır"""
    import subprocess
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout or result.stderr
    except Exception as e:
        return str(e)

async def run_command_async(cmd):
    """Async shell komutu çalıştır"""
    import asyncio
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode() or stderr.decode()

# Geçici dizin
TEMP_DIR = "/tmp"
