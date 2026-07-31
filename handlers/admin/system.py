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
from datetime import datetime
from telethon import events, Button
import config
from database import database as db
from userbot.smart_manager import smart_session_manager
from userbot.plugins import plugin_manager

# Eski uyumluluk için alias
userbot_manager = smart_session_manager
from utils import send_log, get_readable_time, back_button
from utils.bot_api import bot_api, btn, ButtonBuilder

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


def _yerel_degisiklikler(repo, dal=None):
    """pull'u GERÇEKTEN engelleyecek dosyaları döndür.

    Bir dosya ancak hem (a) sunucuda yerel olarak değiştirilmişse hem de
    (b) gelen commit'lerde değişmişse merge'i engeller. Sadece yerelde
    değişmiş (uzakta dokunulmamış) dosyalar pull'u engellemez — onlar için
    kullanıcıyı boşuna durdurmayız.
    """
    yerel = set()
    try:
        for d in repo.index.diff(None):          # working tree değişiklikleri
            if d.a_path:
                yerel.add(d.a_path)
        for d in repo.index.diff("HEAD"):        # stage'lenmiş değişiklikler
            if d.a_path:
                yerel.add(d.a_path)
    except Exception:
        pass
    if not yerel:
        return []
    if dal:
        try:
            ham = repo.git.diff("--name-only", "HEAD..origin/%s" % dal)
            gelen = {s.strip() for s in ham.splitlines() if s.strip()}
            if gelen:
                return sorted(yerel & gelen)
        except Exception:
            pass
    return sorted(yerel)


def _degisiklik_metni(degisen, commit_sayisi):
    """Hangi dosyaların çakıştığını AÇIKÇA göster (git'in kestiği kısım budur)."""
    metin = (f"⚠️ **Güncelleme durduruldu**\n\n"
             f"`{commit_sayisi}` yeni güncelleme var, ancak sunucuda "
             f"**değiştirilmiş `{len(degisen)}` dosya** var. "
             f"Devam edilirse bu değişiklikler silinirdi, o yüzden durdum.\n\n"
             f"**Değişen dosyalar:**\n")
    for d in degisen[:15]:
        metin += f"• `{d}`\n"
    if len(degisen) > 15:
        metin += f"• _...ve {len(degisen) - 15} dosya daha_\n"
    metin += ("\n💾 **Sakla ve güncelle** → değişikliklerin `git stash`'e alınır, "
              "güncelleme sonrası geri uygulanır.\n"
              "🗑 **Değişiklikleri sil** → yerel değişiklikler **kalıcı silinir**, "
              "repo'daki hâline dönülür.")
    return metin


def _git_hata_metni(e):
    """Git hatasını KESMEDEN göster (dosya listesi stderr'in devamındadır)."""
    try:
        import git
        if isinstance(e, git.exc.GitCommandError):
            stderr = (getattr(e, "stderr", "") or "").strip()
            stdout = (getattr(e, "stdout", "") or "").strip()
            ayrinti = (stderr + "\n" + stdout).strip() or str(e)
            ayrinti = ayrinti.replace("stderr:", "").strip()
            if len(ayrinti) > 900:
                ayrinti = ayrinti[:900] + "\n...(kısaltıldı)"
            ipucu = ""
            if "would be overwritten by merge" in ayrinti or "local changes" in ayrinti:
                ipucu = ("\n\n💡 Sunucudaki dosyalar değiştirilmiş. Panelden tekrar "
                         "**🔄 Güncelle**'ye bas — bu sefer sana saklama/silme "
                         "seçeneği sunulacak.")
            elif "Could not resolve host" in ayrinti or "unable to access" in ayrinti:
                ipucu = "\n\n💡 Sunucunun internet/GitHub erişimini kontrol et."
            elif "Authentication failed" in ayrinti or "Permission denied" in ayrinti:
                ipucu = "\n\n💡 Git kimlik bilgileri (token/SSH anahtarı) geçersiz."
            return f"❌ **Güncelleme hatası**\n\n```\n{ayrinti}\n```{ipucu}"
    except Exception:
        pass
    return f"❌ Hata: `{str(e)[:400]}`"


async def _yeniden_baslat(event):
    await event.edit("✅ **Güncellendi!** Yeniden başlatılıyor...")
    with open(".restart_info", "w") as f:
        f.write(f"{event.chat_id}|{event.message_id}")
    await asyncio.sleep(1)
    os.execv(sys.executable, [sys.executable] + sys.argv)


async def _guncellemeyi_uygula(event, repo, origin, dal, commit_sayisi, restart=True):
    """pull + bağımlılıklar (+ istenirse yeniden başlat)."""
    if commit_sayisi:
        await event.edit(f"⬇️ **{commit_sayisi} güncelleme indiriliyor...**")
    else:
        await event.edit("⬇️ **Güncelleme indiriliyor...**")
    origin.pull(dal)
    if os.path.exists("requirements.txt"):
        await event.edit("📦 **Bağımlılıklar kuruluyor...**")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install",
                                   "-r", "requirements.txt", "-q"])
        except subprocess.CalledProcessError as pe:
            # Bağımlılık hatası güncellemeyi geçersiz kılmasın, ama haber ver
            await event.edit("⚠️ **Kod güncellendi ama bağımlılıklar kurulamadı.**\n"
                             f"`{str(pe)[:200]}`\n\nYeniden başlatılıyor...")
            await asyncio.sleep(2)
    if restart:
        await _yeniden_baslat(event)


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
                await event.edit(f"✅ **Güncel!** v{config.__version__}",
                                 buttons=[back_button("settings_menu")])
                return

            # --- YEREL DEĞİŞİKLİK KONTROLÜ (pull'u patlatmadan ÖNCE) ---
            degisen = _yerel_degisiklikler(repo, current_branch)
            if degisen:
                await event.edit(_degisiklik_metni(degisen, len(commits)),
                                 buttons=[
                                     [Button.inline("💾 Sakla ve güncelle", b"update_stash")],
                                     [Button.inline("🗑 Değişiklikleri sil ve güncelle",
                                                    b"update_force")],
                                     back_button("settings_menu"),
                                 ])
                return

            await _guncellemeyi_uygula(event, repo, origin, current_branch, len(commits))
        except Exception as e:
            await event.edit(_git_hata_metni(e), buttons=[back_button("settings_menu")])


    @bot.on(events.CallbackQuery(data=b"update_stash"))
    async def update_stash_handler(event):
        """Yerel değişiklikleri stash'e al, güncelle, geri uygulamayı dene."""
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        await event.edit("💾 **Yerel değişiklikler saklanıyor...**")
        try:
            import git
            repo = git.Repo(".")
            origin = repo.remotes.origin
            dal = repo.active_branch.name
            repo.git.stash("push", "-u", "-m", "kingtg-auto-update")
            origin.fetch()
            adet = len(list(repo.iter_commits(f'{dal}..origin/{dal}')))
            geri_hata = None
            try:
                await _guncellemeyi_uygula(event, repo, origin, dal, adet, restart=False)
                try:
                    repo.git.stash("pop")
                except Exception as pe:
                    geri_hata = str(pe)
            except Exception:
                # Güncelleme patlarsa değişiklikleri geri koy
                try:
                    repo.git.stash("pop")
                except Exception:
                    pass
                raise
            if geri_hata:
                await event.edit(
                    "⚠️ **Güncelleme tamam ama yerel değişiklikler geri uygulanamadı.**\n\n"
                    "Değişikliklerin **kaybolmadı**, `git stash` içinde duruyor.\n"
                    "Sunucuda çakışmayı çözmek için:\n"
                    "`git stash pop`\n\n"
                    f"Hata: `{str(geri_hata)[:200]}`",
                    buttons=[back_button("settings_menu")])
                return
            await _yeniden_baslat(event)
        except Exception as e:
            await event.edit(_git_hata_metni(e), buttons=[back_button("settings_menu")])


    @bot.on(events.CallbackQuery(data=b"update_force"))
    async def update_force_handler(event):
        """Yerel değişiklikleri SİLİP güncelle (yıkıcı - açık onayla çalışır)."""
        if event.sender_id != config.OWNER_ID:
            await event.answer(config.MESSAGES["owner_only"], alert=True)
            return
        await event.edit("🗑 **Yerel değişiklikler siliniyor...**")
        try:
            import git
            repo = git.Repo(".")
            origin = repo.remotes.origin
            dal = repo.active_branch.name
            repo.git.reset("--hard", "HEAD")
            origin.fetch()
            adet = len(list(repo.iter_commits(f'{dal}..origin/{dal}')))
            await _guncellemeyi_uygula(event, repo, origin, dal, adet)
        except Exception as e:
            await event.edit(_git_hata_metni(e), buttons=[back_button("settings_menu")])

    

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
    

    # ==========================================
    # POST OLUŞTURMA SİSTEMİ
    # ==========================================
    
    # Post state yönetimi
    post_states = {}
