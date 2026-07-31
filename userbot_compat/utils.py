# ============================================
# KingTG UserBot Service - Utils Uyumluluk Modülü
# ============================================
# Eski pluginlerdeki yardımcı fonksiyonlar için
# ============================================

import asyncio
import subprocess
import os

# Geçici dizin
TEMP_DIR = "/tmp"

# Global değişkenler
CMD_HELP = {}
CMD_LIST = {}
SUDO_LIST = []
BLACKLIST = []

async def edit_or_reply(event, text, **kwargs):
    """Mesajı düzenle veya yanıtla"""
    try:
        return await event.edit(text, **kwargs)
    except:
        return await event.reply(text, **kwargs)

async def edit_delete(event, text, time=5):
    """Mesajı düzenle ve belirli süre sonra sil"""
    msg = await event.edit(text)
    await asyncio.sleep(time)
    await msg.delete()

def run_command(cmd):
    """Shell komutu çalıştır (senkron)"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout or result.stderr
    except Exception as e:
        return str(e)

async def run_command_async(cmd):
    """Shell komutu çalıştır (asenkron)"""
    proc = await asyncio.create_subprocess_shell(
        cmd, 
        stdout=asyncio.subprocess.PIPE, 
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode() or stderr.decode()

async def bash(cmd):
    """Bash komutu çalıştır (alias)"""
    return await run_command_async(cmd)

def humanbytes(size):
    """Byte'ları okunabilir formata çevir"""
    if not size:
        return "0 B"
    
    power = 2**10
    n = 0
    units = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    
    while size > power and n < 4:
        size /= power
        n += 1
    
    return f"{size:.2f} {units[n]}"

def time_formatter(seconds):
    """Saniyeyi okunabilir formata çevir"""
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    
    result = []
    if days:
        result.append(f"{days} gün")
    if hours:
        result.append(f"{hours} saat")
    if minutes:
        result.append(f"{minutes} dakika")
    if seconds:
        result.append(f"{seconds} saniye")
    
    return ", ".join(result) if result else "0 saniye"

async def progress(current, total, event, start_time, action="İşleniyor"):
    """İndirme/Yükleme ilerleme göstergesi"""
    import time
    
    now = time.time()
    elapsed = now - start_time
    
    if elapsed == 0:
        return
    
    percentage = current * 100 / total
    speed = current / elapsed
    eta = (total - current) / speed if speed > 0 else 0
    
    progress_bar = "[" + "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5)) + "]"
    
    text = f"**{action}**\n\n"
    text += f"{progress_bar}\n"
    text += f"**İlerleme:** {percentage:.1f}%\n"
    text += f"**Boyut:** {humanbytes(current)} / {humanbytes(total)}\n"
    text += f"**Hız:** {humanbytes(speed)}/s\n"
    text += f"**ETA:** {time_formatter(eta)}"
    
    try:
        await event.edit(text)
    except:
        pass
