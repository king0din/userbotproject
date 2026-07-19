# ============================================
# KingTG UserBot Service - Admin / system
# İstatistik, güncelleme, restart, broadcast, loglar
# (admin.py'dan otomatik bölündü - davranış birebir korundu)
# ============================================

# ============================================
# KingTG UserBot Service - Admin Handlers
# ============================================

import os
import sys
import asyncio
import subprocess
import time
import psutil
from telethon import events, Button
import config
from database import database as db
from userbot.smart_manager import smart_session_manager

# Eski uyumluluk için alias
userbot_manager = smart_session_manager
from utils import get_readable_time, back_button

start_time = time.time()

def get_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024
    return f"{bytes:.1f} PB"

async def get_system_stats():
    stats = {}
    stats['cpu_percent'] = psutil.cpu_percent(interval=0.5)
    stats['cpu_count'] = psutil.cpu_count()
    memory = psutil.virtual_memory()
    stats['ram_total'] = get_size(memory.total)
    stats['ram_used'] = get_size(memory.used)
    stats['ram_percent'] = memory.percent
    disk = psutil.disk_usage('/')
    stats['disk_total'] = get_size(disk.total)
    stats['disk_used'] = get_size(disk.used)
    stats['disk_percent'] = disk.percent
    try:
        import socket
        start = time.time()
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        stats['ping'] = round((time.time() - start) * 1000, 1)
    except Exception:
        stats['ping'] = -1
    net = psutil.net_io_counters()
    stats['net_sent'] = get_size(net.bytes_sent)
    stats['net_recv'] = get_size(net.bytes_recv)
    return stats


def register(bot):

    @bot.on(events.CallbackQuery(data=b"stats"))
    async def stats_handler(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        await event.edit("⏳ **Yükleniyor...**")
        
        import aiohttp
        import time as time_module
        
        # Hız testi fonksiyonları
        async def test_speed():
            results = {'ping': None, 'download': None, 'upload': None}
            
            # Ping
            try:
                start = time_module.time()
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                    async with session.head("https://www.google.com"):
                        pass
                results['ping'] = (time_module.time() - start) * 1000
            except Exception:
                pass
            
            # Download
            try:
                start = time_module.time()
                total_bytes = 0
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                    async with session.get("https://speed.cloudflare.com/__down?bytes=5000000") as response:
                        async for chunk in response.content.iter_chunked(1024 * 64):
                            total_bytes += len(chunk)
                elapsed = time_module.time() - start
                if elapsed > 0:
                    results['download'] = (total_bytes * 8) / (elapsed * 1_000_000)
            except Exception:
                pass
            
            # Upload
            try:
                data = b'0' * (1 * 1024 * 1024)  # 1MB
                start = time_module.time()
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                    async with session.post("https://speed.cloudflare.com/__up", data=data):
                        pass
                elapsed = time_module.time() - start
                if elapsed > 0:
                    results['upload'] = (len(data) * 8) / (elapsed * 1_000_000)
            except Exception:
                pass
            
            return results
        
        db_stats = await db.get_stats()
        sys_stats = await get_system_stats()
        speed = await test_speed()
        uptime = get_readable_time(time.time() - start_time)
        
        # Emoji'ler
        ping_emoji = "🟢" if speed['ping'] and speed['ping'] <= 50 else "🟡" if speed['ping'] and speed['ping'] <= 100 else "🔴"
        dl_emoji = "🚀" if speed['download'] and speed['download'] >= 100 else "⚡" if speed['download'] and speed['download'] >= 50 else "📶"
        ul_emoji = "🚀" if speed['upload'] and speed['upload'] >= 50 else "⚡" if speed['upload'] and speed['upload'] >= 25 else "📶"
        
        text = "📊 **Bot İstatistikleri**\n\n"
        text += f"👥 **Kullanıcı:** `{db_stats.get('total_users', 0)}` (Aktif: `{db_stats.get('logged_in_users', 0)}`)\n"
        text += f"🔌 **Plugin:** `{db_stats.get('total_plugins', 0)}`\n"
        text += f"👑 **Sudo:** `{db_stats.get('sudo_users', 0)}` | 🚫 **Ban:** `{db_stats.get('banned_users', 0)}`\n\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━\n🖥️ **Sistem:**\n\n"
        text += f"💻 **CPU:** `{sys_stats['cpu_percent']}%` ({sys_stats['cpu_count']} core)\n"
        text += f"🧠 **RAM:** `{sys_stats['ram_used']}` / `{sys_stats['ram_total']}` ({sys_stats['ram_percent']}%)\n"
        text += f"💾 **Disk:** `{sys_stats['disk_used']}` / `{sys_stats['disk_total']}` ({sys_stats['disk_percent']}%)\n\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━\n🌐 **Ağ:**\n\n"
        if speed['ping']:
            text += f"{ping_emoji} **Ping:** `{speed['ping']:.1f} ms`\n"
        else:
            text += "📶 **Ping:** `N/A`\n"
        if speed['download']:
            text += f"{dl_emoji} **İndirme:** `{speed['download']:.2f} Mbps`\n"
        else:
            text += "⬇️ **İndirme:** `N/A`\n"
        if speed['upload']:
            text += f"{ul_emoji} **Yükleme:** `{speed['upload']:.2f} Mbps`\n"
        else:
            text += "⬆️ **Yükleme:** `N/A`\n"
        
        text += f"\n━━━━━━━━━━━━━━━━━━━━\n⏱️ **Uptime:** `{uptime}`\n🔢 **Sürüm:** `v{config.__version__}`"
        
        await event.edit(text, buttons=[
            [Button.inline("🔄 Yenile", b"stats")],
            back_button("settings_menu")
        ])
    

    @bot.on(events.NewMessage(pattern=r'^/stats$'))
    async def stats_command(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        msg = await event.respond("⏳ **Yükleniyor...**")
        db_stats = await db.get_stats()
        sys_stats = await get_system_stats()
        uptime = get_readable_time(time.time() - start_time)
        text = "📊 **İstatistikler**\n\n"
        text += f"👥 Kullanıcı: `{db_stats.get('total_users', 0)}` (Aktif: `{db_stats.get('logged_in_users', 0)}`)\n"
        text += f"🔌 Plugin: `{db_stats.get('total_plugins', 0)}`\n\n"
        text += f"💻 CPU: `{sys_stats['cpu_percent']}%` | 🧠 RAM: `{sys_stats['ram_percent']}%`\n"
        text += f"💾 Disk: `{sys_stats['disk_percent']}%` | 📶 Ping: `{sys_stats['ping']} ms`\n\n"
        text += f"⏱️ Uptime: `{uptime}`"
        await msg.edit(text)
    

    @bot.on(events.CallbackQuery(data=b"update_bot"))
    async def update_bot_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        await event.edit("🔄 **Kontrol ediliyor...**")
        try:
            import git
            if not os.path.exists(".git"):
                await event.edit("❌ Git repository değil!", buttons=[back_button("settings_menu")])
                return
            repo = git.Repo(".")
            origin = repo.remotes.origin
            origin.fetch()
            current_branch = repo.active_branch.name
            commits = list(repo.iter_commits(f'{current_branch}..origin/{current_branch}'))
            if not commits:
                await event.edit(f"✅ **Güncel!** v{config.__version__}", buttons=[back_button("settings_menu")])
                return
            await event.edit(f"⬇️ **{len(commits)} güncelleme indiriliyor...**")
            origin.pull(current_branch)
            if os.path.exists("requirements.txt"):
                await event.edit("📦 **Bağımlılıklar kuruluyor...**")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"])
            await event.edit("✅ **Güncellendi!** Yeniden başlatılıyor...")
            with open(".restart_info", "w") as f:
                f.write(f"{event.chat_id}|{event.message_id}")
            await asyncio.sleep(1)
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            await event.edit(f"❌ Hata: `{e}`", buttons=[back_button("settings_menu")])
    

    @bot.on(events.CallbackQuery(data=b"restart_bot"))
    async def restart_bot_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        await event.edit("🔃 **Yeniden başlatılıyor...**")
        with open(".restart_info", "w") as f:
            f.write(f"{event.chat_id}|{event.message_id}")
        await asyncio.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    

    @bot.on(events.CallbackQuery(data=b"view_logs"))
    async def view_logs_handler(event):
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        logs = await db.get_logs(limit=15)
        text = "📋 **Son Loglar:**\n\n"
        if logs:
            for log in logs:
                text += f"• [{log.get('type', '?')}] {log.get('message', '')[:30]}\n"
        else:
            text += "Henüz log yok."
        await event.edit(text, buttons=[back_button("settings_menu")])
    

    @bot.on(events.CallbackQuery(data=b"admin_commands"))
    async def admin_commands_handler(event):
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            await event.answer(config.MESSAGES["admin_only"], alert=True)
            return
        text = "📝 **Admin Komutları**\n\n"
        text += "**👥 Kullanıcı:**\n• `/users` - Liste\n• `/info <id>` - Detay\n\n"
        text += "**🔌 Plugin:**\n• `/addplugin` - Ekle\n• `/delplugin <isim>` - Sil\n• `/getplugin <isim>` - İndir\n• `/setpublic <isim>`\n• `/setprivate <isim>`\n\n"
        text += "**🚫 Ban:** `/ban <id>` `/unban <id>`\n"
        text += "**👑 Sudo:** `/addsudo <id>` `/delsudo <id>`\n\n"
        text += "**📢 Diğer:** `/broadcast` `/stats`"
        await event.edit(text, buttons=[back_button("settings_menu")])
    

    @bot.on(events.NewMessage(pattern=r'^/broadcast$'))
    async def broadcast_command(event):
        if event.sender_id != config.OWNER_ID:
            return
        reply = await event.get_reply_message()
        if not reply:
            await event.respond("⚠️ Mesaja yanıt verin.")
            return
        users = await db.get_all_users()
        total = len(users)
        msg = await event.respond(f"📢 Gönderiliyor... (0/{total})")
        sent, failed = 0, 0
        from telethon import errors as _terr
        for i, user in enumerate(users, 1):
            try:
                # Mesaj objesini gönder: medya + format korunur (reply.text değil!)
                await bot.send_message(user["user_id"], reply)
                sent += 1
            except _terr.FloodWaitError as e:
                # Telegram bekleme istedi: bekle ve aynı kullanıcıyı tekrar dene
                await asyncio.sleep(e.seconds + 1)
                try:
                    await bot.send_message(user["user_id"], reply)
                    sent += 1
                except Exception:
                    failed += 1
            except Exception:
                failed += 1
            # Flood koruması: gönderimler arasında kısa bekleme
            await asyncio.sleep(0.06)
            if i % 20 == 0 or i == total:
                try:
                    await msg.edit(f"📢 Gönderiliyor... ({i}/{total})")
                except Exception:
                    pass
        await msg.edit(f"✅ **Tamamlandı!**\n📤 Gönderildi: `{sent}`\n❌ Başarısız: `{failed}`")
    

    # NOT: Post oluşturma sistemi handlers/admin/post.py içindedir.
