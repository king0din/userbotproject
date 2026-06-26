"""
Herhangi bir sohbete günlük, haftalık ve aylık bur yorumu yapın.

🔧 Komutlar:  .burc, .burch, .burca 
🚨 Tür: #eğlence


Komular hakında:
.burc
bu komutla girdiğiniz burcu günlük olarak yorumlayın (yorumlar günlük değişir).
örnek: .burc ikizler

.burch
Bu komutla girilen burcu haftalık olarak yorumlayın (yorumlar haftalık değişir)
örnek: .burch ikizler

.burca
Bu komutla girilen burcuaylık olarak yorumlayın (yorumlar aylık değişir)
örnek: .burca ikizler
"""

from telethon import events
import requests

# Burç emojileri
BURC_EMOJI = {
    'koc': '♈', 'koç': '♈',
    'boga': '♉', 'boğa': '♉',
    'ikizler': '♊',
    'yengec': '♋', 'yengeç': '♋',
    'aslan': '♌',
    'basak': '♍', 'başak': '♍',
    'terazi': '♎',
    'akrep': '♏',
    'yay': '♐',
    'oglak': '♑', 'oğlak': '♑',
    'kova': '♒',
    'balik': '♓', 'balık': '♓'
}

# Element emojileri
ELEMENT_EMOJI = {'Ateş': '🔥', 'Toprak': '🌍', 'Hava': '💨', 'Su': '💧'}


def get_emoji(burc_adi):
    for key, emoji in BURC_EMOJI.items():
        if key in burc_adi.lower():
            return emoji
    return '🔮'


def register(client):
    
    # Günlük burç yorumu
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.bur[cç](?:\s+(.+))?$'))
    async def burc_cmd(event):
        burc_input = event.pattern_match.group(1)
        
        if not burc_input:
            await event.edit(
                "**🔮 Burç Yorumu**\n\n"
                "**Kullanım:**\n"
                "`.burc` \n bu komutla girdiğiniz burcu günlük olarak yorumlayın (yorumlar günlük değişir). \n örnek: `.burc ikizler` \n\n"
                "`.burch` \n bu komutla girdiğiniz burcu haftalık olarak yorumlayın (yorumlar haftalık değişir). \n örnek: `.burch ikizler` \n\n"
                "`.burca` \n bu komutla girdiğiniz burcu aylık olarak yorumlayın (yorumlar aylık değişir). \n örnek: `.burca ikizler` \n\n"
            )
            return
        
        burc_name = burc_input.strip().lower()
        await event.edit(f"🔮 Yükleniyor...")
        
        try:
            response = requests.get(f"https://burc-yorumlari.vercel.app/get/{burc_name}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    b = data[0]
                    
                    emoji = get_emoji(b.get('Burc', ''))
                    element_emoji = ELEMENT_EMOJI.get(b.get('Elementi', ''), '✨')
                    
                    msg = f"{emoji} **{b.get('Burc', '').upper()} BURCU**\n\n"
                    msg += f"💬 Motto: _{b.get('Mottosu', '')}_\n"
                    msg += f"🪐 Gezegen: {b.get('Gezegeni', '')}\n"
                    msg += f"{element_emoji} Element: {b.get('Elementi', '')}\n\n"
                    msg += f"📅 **Günlük Yorum:**\n{b.get('GunlukYorum', 'Yorum bulunamadı.')}"
                    
                    await event.edit(msg)
                else:
                    await event.edit(f"❌ `{burc_name}` bulunamadı.")
            else:
                await event.edit("❌ Servis yanıt vermedi.")
        except Exception as e:
            await event.edit(f"❌ Hata: {e}")
    
    # Haftalık burç yorumu
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.bur[cç]h(?:\s+(.+))?$'))
    async def haftalik_cmd(event):
        burc_input = event.pattern_match.group(1)
        
        if not burc_input:
            await event.edit("**Kullanım:** `.burch <burç>`\n**Örnek:** `.burch aslan`")
            return
        
        burc_name = burc_input.strip().lower()
        await event.edit(f"🔮 Yükleniyor...")
        
        try:
            response = requests.get(f"https://burc-yorumlari.vercel.app/get/{burc_name}/haftalik", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    b = data[0]
                    
                    emoji = get_emoji(b.get('Burc', ''))
                    element_emoji = ELEMENT_EMOJI.get(b.get('Elementi', ''), '✨')
                    
                    msg = f"{emoji} **{b.get('Burc', '').upper()} BURCU**\n\n"
                    msg += f"💬 Motto: _{b.get('Mottosu', '')}_\n"
                    msg += f"🪐 Gezegen: {b.get('Gezegeni', '')}\n"
                    msg += f"{element_emoji} Element: {b.get('Elementi', '')}\n\n"
                    msg += f"📅 **Haftalık Yorum:**\n{b.get('Yorum', 'Yorum bulunamadı.')}"
                    
                    await event.edit(msg)
                else:
                    await event.edit(f"❌ `{burc_name}` bulunamadı.")
            else:
                await event.edit("❌ Servis yanıt vermedi.")
        except Exception as e:
            await event.edit(f"❌ Hata: {e}")
    
    # Aylık burç yorumu
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.bur[cç]a(?:\s+(.+))?$'))
    async def aylik_cmd(event):
        burc_input = event.pattern_match.group(1)
        
        if not burc_input:
            await event.edit("**Kullanım:** `.burca <burç>`\n**Örnek:** `.burca terazi`")
            return
        
        burc_name = burc_input.strip().lower()
        await event.edit(f"🔮 Yükleniyor...")
        
        try:
            response = requests.get(f"https://burc-yorumlari.vercel.app/get/{burc_name}/aylik", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    b = data[0]
                    
                    emoji = get_emoji(b.get('Burc', ''))
                    element_emoji = ELEMENT_EMOJI.get(b.get('Elementi', ''), '✨')
                    
                    msg = f"{emoji} **{b.get('Burc', '').upper()} BURCU**\n\n"
                    msg += f"💬 Motto: _{b.get('Mottosu', '')}_\n"
                    msg += f"🪐 Gezegen: {b.get('Gezegeni', '')}\n"
                    msg += f"{element_emoji} Element: {b.get('Elementi', '')}\n\n"
                    msg += f"📅 **Aylık Yorum:**\n{b.get('Yorum', 'Yorum bulunamadı.')}"
                    
                    await event.edit(msg)
                else:
                    await event.edit(f"❌ `{burc_name}` bulunamadı.")
            else:
                await event.edit("❌ Servis yanıt vermedi.")
        except Exception as e:
            await event.edit(f"❌ Hata: {e}")