"""
gruplarınızda toplu veya tekli etiketler atmanızı sağlar.

🔧 Komutlar: .tagstop, .taghelp, .tagadmin, .tagstat, .tag, .tagban, .tagunban, .tagbanlistremove, .tagbanlist
🚨 Tür: #grup_yönetim 


Komular hakında:
.tag  yanıtladığınız mesajı veya girdiğiniz mesajı tüm üyeleri 2.5 saniye aralıklar ile etiketler
örnek:
.tag bir mesajı yanıtlayarak yada yanına örneğin günaydın yazarak atarsanız btün üyeleri bütün üyelere etiket atar.
not:
diyelim teker teker değilde 5'er kişi etiketleyerek tag atmak istiyorsunuz ozaman komutun yanına min 1 max 10 olacak şekilde belirtin.
örnek:
.tag 5 bir mesajı yanıtlayarak yada yanına mesajı yazarak gönderin.
.tag <kişi sayısı>  <mesajınız> - Grup halinde gönder.
.tagadmin bir mesajı yanıtlayarak yada yanına mesajı yazarark - Sadece adminleri etiketler.
örnek:
.tagadmin 5 günaydın sayın grup adminleri. Adminlar 5'er gruplar halinde etiket atar.
.tagstat - etiketleme işlemi yapılırken mevcut işelm durumunu gösterir.
.tagstop - Etiketlemeyi durdurur.
.taghelp - herhangi bir sohbette yazınca komutun yardım mesajını gösterir
.tagban <id/@username> - Kullanıcıyı etiketlemeden engelle
.tagunban <id/@username> - Kullanıcının engelini kaldır
.tagbanlistremove - Tüm engelleri temizle
.tagbanlist - Engellenen kullanıcıları listele
"""

import asyncio
import copy
import re
import random
import os
import json
from telethon.tl.types import (
    ChannelParticipantsAdmins as cp,
    MessageEntityCustomEmoji,
    MessageEntityTextUrl,
    InputMessageEntityMentionName
)
from telethon.tl.functions.users import GetFullUserRequest
from telethon.errors import (
    ChatAdminRequiredError, 
    UserNotParticipantError,
    ChannelPrivateError,
    FloodWaitError
)
from telethon import events
from userbot import CMD_HELP, bot
from userbot.events import register as r
from userbot.cmdhelp import CmdHelp 

# Global değişkenler
tag_active = False
tag_data = {
    "mode": "all",
    "message": "",
    "message_entities": None,
    "group_size": 1,
    "started_by": None,
    "chat_id": None,
    "current_task": None,
    "tagged_count": 0,
    "total_count": 0,
    "skipped_count": 0,
    "is_reply": False
}

# Engelleme sistemi
blocked_users = set()
loaded_user_id = None  # Cache için - gereksiz yüklemeleri önler
BLOCKED_FILE = os.path.join(os.path.dirname(__file__), "tag_blocked.json")


def load_blocked_users():
    """Engellenen kullanıcıları JSON dosyasından yükle"""
    global blocked_users
    try:
        if os.path.exists(BLOCKED_FILE):
            with open(BLOCKED_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    blocked_users = set()
                    for user_id_list in data.values():
                        blocked_users.update(user_id_list)
                elif isinstance(data, list):
                    blocked_users = set(data)
                else:
                    blocked_users = set()
        else:
            blocked_users = set()
    except Exception:
        blocked_users = set()


async def save_blocked_users(client):
    """Engellenen kullanıcıları JSON dosyasına kaydet - her hesap için ayrı"""
    try:
        me = await client.get_me()
        my_id = str(me.id)
        
        data = {}
        if os.path.exists(BLOCKED_FILE):
            try:
                with open(BLOCKED_FILE, 'r') as f:
                    data = json.load(f)
            except:
                data = {}
        
        data[my_id] = list(blocked_users)
        
        with open(BLOCKED_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


async def load_my_blocked_users(client):
    """Sadece kendi hesabımın engellediklerini yükle"""
    global blocked_users, loaded_user_id
    try:
        me = await client.get_me()
        my_id = str(me.id)
        
        if loaded_user_id == my_id:
            return
        
        if os.path.exists(BLOCKED_FILE):
            with open(BLOCKED_FILE, 'r') as f:
                data = json.load(f)
                
                if my_id in data:
                    blocked_users = set(data[my_id])
                else:
                    blocked_users = set()
        else:
            blocked_users = set()
        
        loaded_user_id = my_id
    except Exception:
        blocked_users = set()


def telegram_text_length(text):
    """
    Telegram'ın kullandığı UTF-16 code unit sayısını hesaplar.
    """
    return len(text.encode('utf-16-le')) // 2


def adjust_entities(entities, offset_shift):
    """
    Entity'lerin offset'lerini ayarlar.
    """
    if not entities:
        return None
    
    adjusted = []
    for entity in entities:
        try:
            new_entity = copy.deepcopy(entity)
            new_entity.offset = entity.offset + offset_shift
            adjusted.append(new_entity)
        except Exception:
            continue
    
    return adjusted if adjusted else None


def extract_entities_for_text(full_text, text_start, original_entities):
    """
    Komut mesajındaki entity'leri, mesaj kısmına göre ayarlar.
    """
    if not original_entities:
        return None
    
    adjusted = []
    
    for entity in original_entities:
        if entity.offset >= text_start:
            new_offset = entity.offset - text_start
            try:
                new_entity = copy.deepcopy(entity)
                new_entity.offset = new_offset
                adjusted.append(new_entity)
            except:
                continue
    
    return adjusted if adjusted else None


async def get_input_user(client, user):
    """
    Kullanıcının InputUser nesnesini al.
    InputMessageEntityMentionName için gerekli.
    """
    try:
        input_user = await client.get_input_entity(user.id)
        return input_user
    except Exception:
        return None


async def build_mention_text_and_entities(client, users, start_offset=0):
    """
    Kullanıcılar için mention metni ve entity listesi oluşturur.
    InputMessageEntityMentionName kullanarak GERÇEK mention bildirimi gönderir.
    
    Args:
        client: Telethon client
        users: Kullanıcı listesi
        start_offset: Mention metninin başlayacağı UTF-16 offset
    
    Returns:
        (mention_text, mention_entities, successful_users)
    """
    mention_entities = []
    names = []
    current_offset = start_offset
    successful_users = []
    
    for i, user in enumerate(users):
        name = user.first_name or "Kullanıcı"
        if not name.strip():
            name = "Kullanıcı"
        name = name[:30].replace("[", "(").replace("]", ")")
        
        name_utf16_len = telegram_text_length(name)
        
        # InputUser nesnesini al
        input_user = await get_input_user(client, user)
        
        if input_user:
            # GERÇEK mention - bildirim gönderir!
            mention_entities.append(
                InputMessageEntityMentionName(
                    offset=current_offset,
                    length=name_utf16_len,
                    user_id=input_user
                )
            )
            successful_users.append(user)
        else:
            # Fallback: TextUrl ile mention (bildirim göndermez ama en azından link olur)
            mention_entities.append(
                MessageEntityTextUrl(
                    offset=current_offset,
                    length=name_utf16_len,
                    url=f"tg://user?id={user.id}"
                )
            )
            successful_users.append(user)
        
        names.append(name)
        
        if i < len(users) - 1:
            current_offset += name_utf16_len + 2  # ", " = 2 UTF-16 unit
        else:
            current_offset += name_utf16_len
    
    mention_text = ", ".join(names)
    
    return mention_text, mention_entities, successful_users


def _utf16_slice(text, start_u16, end_u16=None):
    """Metni UTF-16 code-unit sınırlarından dilimler (Telegram offset sistemi)."""
    buf = text.encode('utf-16-le')
    s = start_u16 * 2
    e = None if end_u16 is None else end_u16 * 2
    return buf[s:e].decode('utf-16-le', errors='ignore')


def slice_text_and_entities(full_text, full_entities, start_u16, end_u16=None):
    """
    full_text'in [start_u16, end_u16) UTF-16 penceresini ve o pencereye denk
    gelen entity'leri (offset'leri yeniden tabanlanmis halde) dondurur.
    Metin ve entity'ler AYNI UTF-16 dilimden uretildigi icin offset'ler her
    zaman tutarlidir -> premium (custom) emoji bozulmaz.
    """
    body = _utf16_slice(full_text, start_u16, end_u16)
    body_len = telegram_text_length(body)
    win_end = start_u16 + body_len
    out = []
    for ent in (full_entities or []):
        e_start = ent.offset
        e_end = ent.offset + ent.length
        if e_start >= start_u16 and e_end <= win_end:
            new_ent = copy.deepcopy(ent)
            new_ent.offset = e_start - start_u16
            out.append(new_ent)
    return body, (out or None)


def parse_tag_command(q):
    """
    .tag / .tagadmin argumanlarini UTF-16 guvenli sekilde cozer.

    Donus: (group_size, message_text, message_entities, is_reply)

    - Offset'ler kod-noktasi degil UTF-16 ile hesaplanir.
    - Mesaj govdesi regex grubundan degil, komut sonrasi ham metnin TAMAMINDAN
      (newline'lar dahil) alinir; boylece cok satirli mesajlar kesilmez.
    - message_text ile message_entities her zaman ayni dilimden uretilir,
      dolayisiyla premium emoji offset'i kaymaz.
    """
    full_msg = getattr(q, "raw_text", None)
    if full_msg is None:
        full_msg = q.text or ""
    entities = list(q.entities or [])

    group_size = 1
    message_text = ""
    message_entities = None
    is_reply = False

    # Komut govdesinin basladigi UTF-16 offset'i (".tag " / ".tagadmin " sonrasi)
    if q.pattern_match is not None and q.pattern_match.group(1) is not None:
        body_start = telegram_text_length(full_msg[:q.pattern_match.start(1)])
    else:
        body_start = telegram_text_length(full_msg)

    body_text, body_entities = slice_text_and_entities(full_msg, entities, body_start)
    stripped = body_text.strip()

    if not stripped:
        is_reply = True
    else:
        m_num = re.match(r"(\d+)(\s+)", body_text)
        if m_num and len(body_text) > m_num.end():
            group_size = max(1, min(10, int(m_num.group(1))))
            skip = telegram_text_length(body_text[:m_num.end()])
            message_text, message_entities = slice_text_and_entities(
                full_msg, entities, body_start + skip
            )
        elif stripped.isdigit():
            group_size = max(1, min(10, int(stripped)))
            is_reply = True
        else:
            message_text, message_entities = body_text, body_entities

    return group_size, message_text, message_entities, is_reply



# ======================================================================
# RASTGELE SOZLER  (her kategori kolayca genisletilebilir - daha fazla
# soz ekledikce "her 50 kiside bir tekrar etmeme" garantisi guclenir)
# ======================================================================
TAG_PHRASES = {
    "gun": [
        "{mention} günaydın, naber?",
        "{mention} günaydın, iyi uyudun mu?",
        "{mention} hadi kalk artık, günaydın 😄",
        "{mention} günaydın, kahveni içtin mi?",
        "{mention} günaydın be, bugün ne var ne yok?",
        "{mention} kalktın mı sen, günaydın",
        "{mention} günaydın, güzel bir gün olsun sana",
        "{mention} selam, günaydın bakalım",
        "{mention} günaydın, keyifler nasıl?",
        "{mention} aç gözlerini, günaydın",
        "{mention} günaydın, erkenci kuş",
        "{mention} günaydın, kahvaltı ettin mi?",
        "{mention} günaydın, bol şans bugün",
        "{mention} hadi bakalım günaydın, başlayalım güne",
        "{mention} günaydın, umarım güzel uyumuşsundur",
        "{mention} günaydın, çayını koydun mu?",
        "{mention} günaydın, nasıl gidiyor?",
        "{mention} günaydın, bugün biraz daha iyi olsun",
        "{mention} merhaba, günaydın diyeyim dedim",
        "{mention} günaydın, yataktan çıkabildin mi?",
        "{mention} günaydın, kolay gelsin bugün",
        "{mention} günaydın, ne planın var bugün?",
        "{mention} günaydın, üşenme kalk 😅",
        "{mention} günaydın, gününe güzel başla",
        "{mention} günaydın, sabah sabah selam",
        "{mention} günaydın, hava güzelmiş bugün",
        "{mention} günaydın, keyfin yerinde mi?",
        "{mention} günaydın, hadi güne",
        "{mention} günaydın, iyi ki varsın",
        "{mention} günaydın, bol kahveli bir gün olsun",
        "{mention} günaydın, nasıl bir uyku çektin?",
        "{mention} günaydın, bugünü güzel geçir",
        "{mention} günaydın, daha uyuyor musun yoksa?",
        "{mention} günaydın, sana da iyi bir gün",
        "{mention} günaydın, kalk gün ortası oldu 😄",
        "{mention} günaydın, bugün işler nasıl?",
        "{mention} günaydın, çabuk uyan da sohbet edelim",
        "{mention} günaydın, sabahın hayrına",
        "{mention} günaydın, dinlenebildin mi?",
        "{mention} günaydın, hadi bir kahve içelim",
        "{mention} günaydın, moralin yüksek olsun",
        "{mention} günaydın, gözünü ovuştur ve kalk",
        "{mention} günaydın, naber bakalım",
        "{mention} günaydın, güzel bir gün seni bekliyor",
        "{mention} günaydın, kahven sade mi sütlü mü?",
        "{mention} günaydın, bugün kendine iyi davran",
        "{mention} günaydın, hadi gözünü aç",
        "{mention} günaydın, sabah oldu bile",
        "{mention} günaydın, iyi günler sana",
        "{mention} günaydın, ne haber, nasılsın?",
    ],
    "gec": [
        "{mention} iyi geceler, tatlı rüyalar",
        "{mention} iyi geceler, rahat bir uyku çek",
        "{mention} hadi iyi geceler, yarın görüşürüz",
        "{mention} iyi geceler, güzel uykular sana",
        "{mention} iyi geceler, yorgunsundur, dinlen",
        "{mention} iyi geceler, kafanı dinle biraz",
        "{mention} iyi geceler, yarın daha iyi olacak",
        "{mention} iyi geceler, gözlerin kapanıyordur",
        "{mention} iyi geceler, mışıl mışıl uyu",
        "{mention} iyi geceler, bugünlük bu kadar",
        "{mention} iyi geceler, yatağa geçme vakti",
        "{mention} iyi geceler, rüyanda güzel şeyler gör",
        "{mention} iyi geceler, telefonu bırak da uyu 😄",
        "{mention} iyi geceler, yarın enerjik kalk",
        "{mention} iyi geceler, huzurlu uykular",
        "{mention} iyi geceler, kendine iyi bak",
        "{mention} iyi geceler, hadi gözünü kapat",
        "{mention} iyi geceler, güzel bir uyku hak ettin",
        "{mention} iyi geceler, yorgunluğun geçsin",
        "{mention} iyi geceler, sabah görüşmek üzere",
        "{mention} iyi geceler, deliksiz bir uyku dilerim",
        "{mention} iyi geceler, bugünü geride bırak",
        "{mention} iyi geceler, yastığa kafanı koy ve rahatla",
        "{mention} iyi geceler, hayırlı geceler",
        "{mention} iyi geceler, uykun bölünmesin",
        "{mention} iyi geceler, yarın yeni bir gün",
        "{mention} iyi geceler, tatlı tatlı uyu",
        "{mention} iyi geceler, dinlenmeye bak",
        "{mention} iyi geceler, gece güzeldir, uykun da öyle olsun",
        "{mention} iyi geceler, biraz dinlen artık",
        "{mention} iyi geceler, gözün açık kalmasın",
        "{mention} iyi geceler, rüyalar tatlı olsun",
        "{mention} iyi geceler, derin bir uyku çek",
        "{mention} iyi geceler, yorulduysan dinlen",
        "{mention} iyi geceler, yarına güçlü uyan",
        "{mention} iyi geceler, kapat gözlerini",
        "{mention} iyi geceler, sıcak yatağın keyfini çıkar",
        "{mention} iyi geceler, güzel düşlere dal",
        "{mention} iyi geceler, sabaha dinç çık",
        "{mention} iyi geceler, bugün yoruldun, uyu artık",
        "{mention} iyi geceler, rahat uykular",
        "{mention} iyi geceler, yıldızları say ve uyu",
        "{mention} iyi geceler, kafanı boşalt biraz",
        "{mention} iyi geceler, hadi uykuya",
        "{mention} iyi geceler, erken kalkacaksan dinlen",
        "{mention} iyi geceler, mutlu uyu",
        "{mention} iyi geceler, yarın bol enerji",
        "{mention} iyi geceler, gece yarısı oldu, uyu",
        "{mention} iyi geceler, tatlı uykular dilerim",
        "{mention} iyi geceler, görüşürüz yarın",
    ],
    "sor": [
        "{mention} naber, nasılsın?",
        "{mention} bugün ne yaptın bakalım?",
        "{mention} kahve mi çay mı, hangisi?",
        "{mention} akşama ne yiyorsun?",
        "{mention} hafta sonu planın ne?",
        "{mention} en son hangi diziyi izledin?",
        "{mention} şu an ne dinliyorsun?",
        "{mention} nasıl gidiyor hayat?",
        "{mention} bir tatil olsa nereye giderdin?",
        "{mention} bugün keyfin nasıl?",
        "{mention} en sevdiğin mevsim hangisi?",
        "{mention} şu an aklında ne var?",
        "{mention} bu gruba ne zaman katıldın hatırlıyor musun?",
        "{mention} canın ne yapmak istiyor?",
        "{mention} bugün kaç kahve içtin?",
        "{mention} en son ne zaman güldün?",
        "{mention} dağ mı deniz mi?",
        "{mention} bugün nasıldı, anlat",
        "{mention} ne işle meşgulsün şu an?",
        "{mention} sabahçı mısın gececi mi?",
        "{mention} en sevdiğin yemek ne?",
        "{mention} bu akşam ne yapıyorsun?",
        "{mention} hangi şehirde yaşamak isterdin?",
        "{mention} bugün seni ne mutlu etti?",
        "{mention} film mi kitap mı?",
        "{mention} su içtin mi bugün?",
        "{mention} en sevdiğin içecek ne?",
        "{mention} bir süper gücün olsa ne olurdu?",
        "{mention} bugün havalar nasıl orada?",
        "{mention} ne zamandır buradasın?",
        "{mention} şu sıralar en sevdiğin şarkı ne?",
        "{mention} bugün kendine vakit ayırdın mı?",
        "{mention} yağmuru mu seversin güneşi mi?",
        "{mention} en son ne öğrendin?",
        "{mention} canın tatlı mı çekiyor tuzlu mu?",
        "{mention} bugün planların tuttu mu?",
        "{mention} hangi ülkeyi gezmek isterdin?",
        "{mention} şu an mutlu musun?",
        "{mention} en sevdiğin atıştırmalık ne?",
        "{mention} bugün nasıl bir gündü?",
        "{mention} sabah ilk işin ne olur?",
        "{mention} en çok neye gülersin?",
        "{mention} bir hayvan olsan ne olurdun?",
        "{mention} bugün birine iyilik yaptın mı?",
        "{mention} şu an canın ne çekiyor?",
        "{mention} hangi diziyi baştan izlerdin?",
        "{mention} bugün enerjin nasıl?",
        "{mention} en sevdiğin koku ne?",
        "{mention} ne yapıyorsun şu an?",
        "{mention} bugün gününü nasıl geçirdin?",
    ],
    "kom": [
        "{mention} yine mi buradasın, hiç mi işin yok 😄",
        "{mention} seni görmeyeli özlemişim, neredeydin?",
        "{mention} bugün de online, helal sana",
        "{mention} kaybolmuşsun, nerelerdeydin bakalım",
        "{mention} az çalış biraz, yorulacaksın 😅",
        "{mention} sessiz kalma, bir şeyler yaz",
        "{mention} seni etiketledim, kaçış yok artık",
        "{mention} buralarda mısın yoksa uyudun mu?",
        "{mention} bir merhaba bile mi yok kanka",
        "{mention} bu sessizlik de ne, konuşsana 😄",
        "{mention} çay koy bize de",
        "{mention} nerede kaybettik seni?",
        "{mention} bir haber ver, merak ettik",
        "{mention} yine kayıplara karıştın",
        "{mention} aç telefonu, seni arıyoruz",
        "{mention} bu kadar sessizlik suç sayılır 😄",
        "{mention} seni buraya almışlar, hayırdır",
        "{mention} uyuma, sohbet var",
        "{mention} biraz ortaya çık bakalım",
        "{mention} seni de görelim arada",
        "{mention} yaz bir şeyler, parmakların mı yoruldu",
        "{mention} hayalet gibisin, görünmez oldun",
        "{mention} buraya gel, muhabbet kuruyoruz",
        "{mention} seni etiketlemesem unutacaktın bizi",
        "{mention} online görünüp yazmamak ne iş 😄",
        "{mention} az gülümse, bedava",
        "{mention} neredesin, yine kahve mi içiyorsun",
        "{mention} bir selam çak en azından",
        "{mention} seni bulmak define avı gibi",
        "{mention} grup seni özledi, dön artık",
        "{mention} bu sessizliğin şifresi ne 😅",
        "{mention} yaz da bir hayat belirtisi görelim",
        "{mention} kaçma, yakaladım seni",
        "{mention} biraz da sen konuş, biz yorulduk",
        "{mention} seni görünce keyifler yerine geldi",
        "{mention} telefonu bırak demiyorum ama yaz biraz",
        "{mention} burada mısın gerçekten?",
        "{mention} merhaba de, zor değil 😄",
        "{mention} seni etiketledim, görmezden gelme",
        "{mention} nerelerde geziyorsun bakalım",
        "{mention} az ortaya çık, özledik",
        "{mention} sessiz sedasız geçme, selam ver",
        "{mention} bir kahve ısmarla bari",
        "{mention} grup seni bekliyor",
        "{mention} uyandın mı yoksa hâlâ rüyada mısın",
        "{mention} yaz bir şey, sıkıldık 😅",
        "{mention} seni de aramıza alalım",
        "{mention} kaybolma, buradayız",
        "{mention} merhaba demeye üşenme",
        "{mention} hadi bir laf et bakalım",
    ],
    "sog": [
        "{mention} sana bir fıkra: balık neden okula gidemedi? oltaya gelmedi 🥶",
        "{mention} soğuk bir tane: limonun derdi neymiş? içi ekşimiş",
        "{mention} bunu duydun mu, saat neden yorulur? hep akrep peşinde",
        "{mention} sana özel: çaydanlık neden mutlu? kaynamaya bayılıyor",
        "{mention} bir tane patlatayım: ampul neden parladı? aklına fikir geldi",
        "{mention} dinle: defter neden sustu? çizgiyi aştı",
        "{mention} hazır mısın: ekmek neden küstü? dilimlendi",
        "{mention} şuna gül: buzdolabı neden konuşmaz? içi soğuk",
        "{mention} sana bir tane: kalem neden kırıldı? baskıya dayanamadı",
        "{mention} soğuktan donduracak: süt neden kaçtı? kaçık oldu",
        "{mention} al sana espri: pencere neden açıldı? cam sıkıldı",
        "{mention} bak: mum neden eridi? içten içe yandı",
        "{mention} bir tane daha: bulut neden ağladı? içine attı",
        "{mention} dinle bakalım: anahtar neden döndü? kilitlenip kaldı",
        "{mention} şunu duy: priz neden şaşırdı? fişi gördü",
        "{mention} sana özel: makas neden ayrıldı? araları açıldı",
        "{mention} gülmek yasak: tencere neden taştı? kaynayası geldi",
        "{mention} al bakalım: ütü neden kızdı? buruşukluğa dayanamadı",
        "{mention} bir soğuk: sünger neden doldu? her şeyi içine attı",
        "{mention} dinle: musluk neden ağladı? damla damla doldu",
        "{mention} sana fıkra: terlik neden kayboldu? tek ayak üstünde kaldı",
        "{mention} hazır ol: lamba neden sustu? düğmeye basıldı",
        "{mention} şunu beğen: tabak neden kızdı? hep ortaya kondu",
        "{mention} bir tane: pil neden yoruldu? hep şarj oldu",
        "{mention} al sana: halı neden sessiz? hep ezildi",
        "{mention} dinle: klima neden mutlu? havası var",
        "{mention} gül bakalım: perde neden çekildi? utandı",
        "{mention} sana özel: kibrit neden parladı? biraz sürtüşme yaşadı",
        "{mention} bir soğuk espri: battaniye neden sıcak? içine attı",
        "{mention} şunu duy: fincan neden doldu? çay ısrarcıydı",
        "{mention} al bakalım: saksı neden büyüdü? içinde umut vardı",
        "{mention} dinle: yastık neden yumuşadı? baş ağrıttı",
        "{mention} sana fıkra: cam neden buğulandı? içi geçti",
        "{mention} bir tane daha: çekmece neden kapandı? içine kapanıktı",
        "{mention} hazır mısın: çorba neden sıcaktı? ortam gergindi",
        "{mention} şunu beğen: buz neden eridi? ortam ısındı",
        "{mention} al sana espri: kapı neden gülümsedi? kolu okşandı",
        "{mention} dinle bakalım: bardak neden doldu? sabrı taştı",
        "{mention} gül: sandalye neden kalkamadı? ayakları sabit",
        "{mention} sana özel: lastik neden döndü? yolu sevdi",
        "{mention} bir soğuk: kalemtıraş neden döndü? başını döndürdü",
        "{mention} şunu duy: zil neden çaldı? çalınası geldi",
        "{mention} al bakalım: masa neden sessiz? ayakları bağlı",
        "{mention} dinle: çatal neden küstü? kaşığa kaşık attılar",
        "{mention} sana fıkra: telefon neden titredi? mesaj korkuttu",
        "{mention} bir tane: çorap neden kayboldu? yalnız gezmeyi sevdi",
        "{mention} hazır ol: kazak neden asabi? dolaba asıldı",
        "{mention} şunu beğen: patates neden ünlü? kızarmaktan çekinmedi",
        "{mention} al sana: bilgisayara espri yaptım, 'işlemedi' dedi",
        "{mention} son bir tane: limon neden üzgün? içi ekşidi",
    ],
}

# kategori anahtari -> (buton etiketi, kisa ad)
_CATS = {
    "gun": ("🌅 Günaydın", "günaydın"),
    "gec": ("🌙 İyi Geceler", "iyi geceler"),
    "sor": ("❓ Soru", "soru"),
    "kom": ("😂 Komik", "komik"),
    "sog": ("🥶 Soğuk Espri", "soğuk espri"),
}


def _make_phrase_picker(category):
    """
    Bir kategori icin "son K kisi icinde tekrar etmeyen" soz secici dondurur.
    K = min(50, havuz-1)  -> havuz >= 50 ise ARDISIK 50 kiside ayni soz gelmez.
    (Bir kisi zaten tek sefer etiketlendigi icin "ayni kisiye ayni soz"
     kosulu da otomatik saglanir.)
    """
    from collections import deque
    pool = list(TAG_PHRASES.get(category) or ["📢"])
    K = min(50, max(0, len(pool) - 1))
    recent = deque(maxlen=K)

    def pick():
        if len(pool) == 1:
            return pool[0]
        choices = [p for p in pool if p not in recent] or pool
        p = random.choice(choices)
        if K > 0:
            recent.append(p)
        return p

    return pick


# ======================================================================
# PANEL METIN / BUTONLARI
# ======================================================================
def _panel_text_step1(has_msg):
    if has_msg:
        return ("🏷️ **Etiketleme**\n\n"
                "Kaç kişilik gruplar halinde etiketleyeyim?\n\n"
                "⏹️ İşlemi durdurmak için: `.tagstop`")
    return ("🏷️ **Etiketleme**\n\n"
            "Mesaj girmediniz / bir mesaj yanıtlamadınız.\n"
            "Rastgele hangi mesajlarla etiketleyeyim?\n\n"
            "⏹️ İşlemi durdurmak için: `.tagstop`")


def _panel_text_interval():
    return ("⏱️ Kaç saniyede bir göndereyim?\n\n"
            "_(Düşük süre flood riskini artırır.)_\n\n"
            "⏹️ Durdurmak için: `.tagstop`")


def _step1_buttons(owner, has_msg):
    from telethon import Button
    if has_msg:
        return [
            [Button.inline("1'erli", f"tgrp_{owner}_1".encode()),
             Button.inline("3'erli", f"tgrp_{owner}_3".encode())],
            [Button.inline("5'erli", f"tgrp_{owner}_5".encode()),
             Button.inline("10'arlı", f"tgrp_{owner}_10".encode())],
        ]
    rows, row = [], []
    for key, (label, _short) in _CATS.items():
        row.append(Button.inline(label, f"tcat_{owner}_{key}".encode()))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def _interval_buttons(owner):
    from telethon import Button
    return [
        [Button.inline("2.5 sn", f"tint_{owner}_25".encode()),
         Button.inline("3 sn", f"tint_{owner}_30".encode())],
        [Button.inline("5 sn", f"tint_{owner}_50".encode()),
         Button.inline("6 sn", f"tint_{owner}_60".encode())],
    ]


# ======================================================================
# BOT / CLIENT ERISIM YARDIMCILARI
# ======================================================================
def _get_bot():
    import sys
    try:
        if 'main' in sys.modules:
            b = getattr(sys.modules['main'], 'bot', None)
            if b is not None:
                return b
        import __main__
        return getattr(__main__, 'bot', None)
    except Exception:
        return None


def _get_bot_username():
    try:
        import config as cfg
        u = getattr(cfg, 'BOT_USERNAME', '') or ''
        if u:
            return u.lstrip('@')
    except Exception:
        pass
    try:
        if os.path.exists('.bot_username'):
            with open('.bot_username') as f:
                return f.read().strip().lstrip('@')
    except Exception:
        pass
    return ''


def _get_user_client(owner_id):
    try:
        from userbot.smart_manager import smart_session_manager
        return smart_session_manager.get_client(owner_id)
    except Exception:
        return None


def _ensure_state(bot):
    if not hasattr(bot, "_tag_pending"):
        bot._tag_pending = {}
    if not hasattr(bot, "_tag_jobs"):
        bot._tag_jobs = {}


async def _load_blocked_for(client):
    """Sadece bu hesabin engelli listesini (lokal kume olarak) dondurur."""
    try:
        me = await client.get_me()
        mid = str(me.id)
        if os.path.exists(BLOCKED_FILE):
            with open(BLOCKED_FILE) as f:
                data = json.load(f)
            if isinstance(data, dict):
                return set(data.get(mid, []))
            if isinstance(data, list):
                return set(data)
    except Exception:
        pass
    return set()


# ======================================================================
# BOT TARAFI: inline panel + callback'ler (TEK SEFER kaydedilir)
# ======================================================================
def _register_tag_bot_handlers(bot):
    if getattr(bot, "_tag_flow_registered", False):
        return
    bot._tag_flow_registered = True
    _ensure_state(bot)

    from telethon import events
    import re as _re

    @bot.on(events.InlineQuery())
    async def _tag_inline(event):
        m = _re.match(r"tagq_(\d+)$", event.text or "")
        if not m:
            return
        owner = int(m.group(1))
        _ensure_state(bot)
        pend = bot._tag_pending.get(owner)
        has_msg = bool(pend and pend.get("has_msg"))
        try:
            result = event.builder.article(
                title="🏷️ Etiketleme Paneli",
                description="Seçim yapmak için dokunun",
                text=_panel_text_step1(has_msg),
                buttons=_step1_buttons(owner, has_msg),
            )
            await event.answer([result], cache_time=0)
        except Exception:
            pass

    @bot.on(events.CallbackQuery(pattern=rb"tgrp_(\d+)_(\d+)"))
    async def _tag_grp_cb(event):
        owner = int(event.pattern_match.group(1))
        n = int(event.pattern_match.group(2))
        if event.sender_id != owner:
            await event.answer("Bu panel sana ait değil.", alert=True)
            return
        _ensure_state(bot)
        pend = bot._tag_pending.get(owner)
        if not pend:
            await event.answer("Panel zaman aşımına uğradı, tekrar .tag yazın.", alert=True)
            return
        pend["group_size"] = max(1, min(10, n))
        try:
            await event.edit(_panel_text_interval(), buttons=_interval_buttons(owner))
        except Exception:
            pass

    @bot.on(events.CallbackQuery(pattern=rb"tcat_(\d+)_([a-z]+)"))
    async def _tag_cat_cb(event):
        owner = int(event.pattern_match.group(1))
        key = event.pattern_match.group(2).decode()
        if event.sender_id != owner:
            await event.answer("Bu panel sana ait değil.", alert=True)
            return
        _ensure_state(bot)
        pend = bot._tag_pending.get(owner)
        if not pend or key not in TAG_PHRASES:
            await event.answer("Panel zaman aşımına uğradı, tekrar .tag yazın.", alert=True)
            return
        pend["category"] = key
        pend["group_size"] = 1  # rastgele söz modunda teker teker
        try:
            await event.edit(_panel_text_interval(), buttons=_interval_buttons(owner))
        except Exception:
            pass

    @bot.on(events.CallbackQuery(pattern=rb"tint_(\d+)_(\d+)"))
    async def _tag_int_cb(event):
        owner = int(event.pattern_match.group(1))
        x10 = int(event.pattern_match.group(2))
        if event.sender_id != owner:
            await event.answer("Bu panel sana ait değil.", alert=True)
            return
        _ensure_state(bot)
        pend = bot._tag_pending.pop(owner, None)
        if not pend:
            await event.answer("Panel zaman aşımına uğradı, tekrar .tag yazın.", alert=True)
            return
        job = bot._tag_jobs.get(owner)
        if job and job.get("active"):
            await event.answer("Zaten bir etiketleme sürüyor (.tagstop).", alert=True)
            return
        interval = x10 / 10.0
        gsize = pend.get("group_size") or 1
        task = asyncio.create_task(run_tag_job(
            owner,
            pend["chat_id"],
            pend.get("mode", "all"),
            gsize,
            interval,
            pend.get("message") or "📢",
            pend.get("entities"),
            pend.get("category"),
        ))
        bot._tag_jobs[owner] = {"active": True, "task": task, "tagged": 0, "total": 0}

        mode_txt = "adminleri" if pend.get("mode") == "admin" else "üyeleri"
        if pend.get("category"):
            src = f"rastgele {_CATS[pend['category']][1]} mesajlarıyla"
        else:
            src = "girdiğiniz mesajla"
        try:
            await event.edit(
                f"✅ **Etiketleme başladı!**\n\n"
                f"Tüm {mode_txt}, {gsize}'erli gruplar halinde, {interval:g} sn arayla "
                f"{src} etiketliyorum.\n\n"
                f"⏹️ Durdurmak için: `.tagstop`"
            )
        except Exception:
            pass


# ======================================================================
# PANELI GOSTER (userbot komut handler'indan cagrilir)
# ======================================================================
async def _show_tag_panel(q, mode, message_text, message_entities, has_msg):
    owner = (await q.client.get_me()).id
    bot = _get_bot()
    if bot is None:
        try:
            await q.edit("❌ **Bot bulunamadı, panel açılamadı.**")
        except Exception:
            pass
        return
    _register_tag_bot_handlers(bot)
    _ensure_state(bot)

    job = bot._tag_jobs.get(owner)
    if job and job.get("active"):
        try:
            await q.edit("❌ **Zaten bir etiketleme sürüyor!**\nKapatmak için: `.tagstop`")
        except Exception:
            pass
        return

    bot._tag_pending[owner] = {
        "chat_id": q.chat_id,
        "mode": mode,
        "has_msg": bool(has_msg),
        "message": message_text,
        "entities": message_entities,
        "group_size": None,
        "category": None,
    }

    bot_username = _get_bot_username()

    # 1) Grup içinde inline panel dene
    if bot_username:
        try:
            results = await q.client.inline_query(bot_username, f"tagq_{owner}")
            if results:
                await results[0].click(q.chat_id)
                try:
                    await q.delete()
                except Exception:
                    pass
                return
        except Exception:
            pass  # inline kapalı olabilir -> özelden gönder

    # 2) Fallback: paneli özelde (bot PM) gönder + grupta bilgilendir
    try:
        await bot.send_message(
            owner,
            _panel_text_step1(has_msg),
            buttons=_step1_buttons(owner, has_msg),
        )
        try:
            await q.edit(
                "⚠️ **Bu grupta satıriçi (inline) gönderim kapalı.**\n"
                "Seçim panelini sizinle özelden (bot sohbeti) paylaştım, "
                "lütfen oradan devam edin.\n\n"
                "⏹️ Durdurmak için: `.tagstop`"
            )
        except Exception:
            pass
    except Exception:
        try:
            await q.edit(
                "❌ **Panel açılamadı.**\n"
                "Botla özelden bir kez sohbet başlatmış olmalısınız (`/start`)."
            )
        except Exception:
            pass


async def _compose_message(client, template, template_entities, group):
    """
    Etiket mesajini kurar.
    - template icinde {mention} varsa: etiket(ler) tam o konuma yerlestirilir;
      placeholder sonrasi entity'ler (premium emoji vb.) UTF-16 farkina gore kaydirilir.
    - {mention} yoksa: eski davranis -> mesaj + bos satir + altta etiketler.
    Donus: (final_text, final_entities, ok_users)
    """
    PH = "{mention}"
    if PH in template:
        idx = template.index(PH)
        before = template[:idx]
        after = template[idx + len(PH):]
        before_u16 = telegram_text_length(before)
        ph_u16 = telegram_text_length(PH)

        mention_text, mention_entities, ok_users = await build_mention_text_and_entities(
            client, group, before_u16
        )
        m_u16 = telegram_text_length(mention_text)
        shift = m_u16 - ph_u16

        final_text = before + mention_text + after
        final_entities = []
        for e in (template_entities or []):
            e_start = e.offset
            e_end = e.offset + e.length
            if e_end <= before_u16:
                final_entities.append(copy.deepcopy(e))
            elif e_start >= before_u16 + ph_u16:
                ne = copy.deepcopy(e)
                ne.offset = e_start + shift
                final_entities.append(ne)
            # placeholder ile cakisan entity'ler atlanir
        final_entities.extend(mention_entities)
        return final_text, final_entities, ok_users

    # {mention} yok -> klasik: mesaj + bos satir + altta etiketler
    separator = "\n\n"
    start_offset = telegram_text_length(template) + telegram_text_length(separator)
    mention_text, mention_entities, ok_users = await build_mention_text_and_entities(
        client, group, start_offset
    )
    final_text = f"{template}{separator}{mention_text}"
    final_entities = []
    if template_entities:
        final_entities.extend(copy.deepcopy(template_entities))
    final_entities.extend(mention_entities)
    return final_text, final_entities, ok_users


# ======================================================================
# ASIL ETIKETLEME ISI (client tabanli, bot callback'inden baslatilir)
# ======================================================================
async def run_tag_job(owner_id, chat_id, mode, group_size, interval,
                      message, entities, category):
    from telethon.tl.types import ChannelParticipantsAdmins
    from telethon.errors import (
        ChatAdminRequiredError, ChannelPrivateError, FloodWaitError
    )

    bot = _get_bot()
    client = _get_user_client(owner_id)
    if client is None:
        return
    _ensure_state(bot)
    job = bot._tag_jobs.setdefault(owner_id, {})
    job["active"] = True
    job.setdefault("tagged", 0)
    job.setdefault("total", 0)

    blocked = await _load_blocked_for(client)
    try:
        me = await client.get_me()
        my_id = me.id
    except Exception:
        my_id = None

    picker = _make_phrase_picker(category) if category else None
    flt = ChannelParticipantsAdmins() if mode == "admin" else None

    try:
        status = await client.send_message(chat_id, "⏳ **Etiketleme başlıyor...**")
    except Exception:
        status = None

    # Katılımcıları topla
    participants = []
    try:
        async for u in client.iter_participants(chat_id, filter=flt):
            if not job.get("active"):
                break
            if getattr(u, "bot", False) or getattr(u, "deleted", False):
                continue
            if my_id is not None and u.id == my_id:
                continue
            if u.id in blocked:
                continue
            participants.append(u)
            if len(participants) >= 5000:
                break
    except (ChatAdminRequiredError, ChannelPrivateError):
        if status:
            try:
                await status.edit("❌ **Üye listesine erişilemedi** (yönetici olmalısınız).")
            except Exception:
                pass
        job["active"] = False
        return
    except Exception:
        pass

    total = len(participants)
    job["total"] = total
    if total == 0:
        if status:
            try:
                await status.edit("❌ **Etiketlenecek kimse bulunamadı.**")
            except Exception:
                pass
        job["active"] = False
        return

    tagged = 0
    for i in range(0, total, group_size):
        if not job.get("active"):
            break
        group = participants[i:i + group_size]
        if not group:
            continue

        if picker:
            msg_text = picker()
            msg_ents = None
        else:
            msg_text = message
            msg_ents = entities

        try:
            full_message, all_entities, ok_users = await _compose_message(
                client, msg_text, msg_ents, group
            )
            if len(full_message) <= 4096:
                await client.send_message(
                    chat_id,
                    full_message,
                    formatting_entities=all_entities if all_entities else None,
                    silent=True,
                )
                tagged += len(ok_users)
                job["tagged"] = tagged
        except FloodWaitError as e:
            if status:
                try:
                    await status.edit(f"⏳ **FloodWait:** {e.seconds}s bekleniyor...")
                except Exception:
                    pass
            await asyncio.sleep(e.seconds)
            continue
        except Exception:
            continue

        if status and (i % max(1, total // 10) == 0 or i + group_size >= total):
            pct = min(100, (i + group_size) * 100 // total)
            try:
                await status.edit(
                    f"⏳ **Etiketleniyor...** %{pct}\n"
                    f"✅ {tagged}/{total}\n"
                    f"⏱️ {interval:g}s\n\n"
                    f"⏹️ Durdurmak için: `.tagstop`"
                )
            except Exception:
                pass

        await asyncio.sleep(interval)

    finished = bool(job.get("active"))
    job["active"] = False
    if status:
        try:
            head = "✅ **Etiketleme tamamlandı!**" if finished else "⏹️ **Etiketleme durduruldu.**"
            await status.edit(f"{head}\n✅ Etiketlenen: {tagged}/{total}")
        except Exception:
            pass


@r(outgoing=True, pattern="^.tag(?: |$)(.*)")
async def tag_all(q):
    """Tüm üyeleri etiketler"""
    global tag_active, tag_data
    
    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return
    
    await load_my_blocked_users(q.client)
    
    if tag_active:
        try:
            await q.edit("❌ **Zaten bir etiketleme işlemi devam ediyor!**\nKapatmak için: `.tagstop`")
        except:
            pass
        return
    
    if q.fwd_from:
        return
    
    group_size, message_text, message_entities, is_reply = parse_tag_command(q)
    
    reply_msg = await q.get_reply_message()
    if reply_msg and (is_reply or not message_text):
        message_text = (getattr(reply_msg, "raw_text", None) or reply_msg.text or "📢")
        message_entities = reply_msg.entities
        is_reply = True
    
    has_msg = bool(message_text)
    if not message_text:
        message_text = "📢"
    
    chat = await q.get_input_chat()
    
    try:
        pass
    except Exception as e:
        await q.edit(f"❌ **İzin kontrolü hatası:** `{str(e)}`")
        return
    
    try:
        test_participant = await q.client.get_participants(chat, limit=1)
        if not test_participant:
            await q.edit("❌ **Grupta katılımcı bulunamadı!**")
            return
    except ChatAdminRequiredError:
        await q.edit("❌ **Katılımcı listesini almak için admin olmalısınız!**\n\n"
                    "⚠️ *Grup gizli olabilir veya üye listesini görme izniniz yok.*")
        return
    except ChannelPrivateError:
        await q.edit("❌ **Bu gruba erişimim yok!**\n\n"
                    "⚠️ *Grup gizli olabilir veya gruptan çıkarılmış olabilirim.*")
        return
    except UserNotParticipantError:
        await q.edit("❌ **Bu grupta değilim!**\n\n"
                    "⚠️ *Önce gruba katılmalıyım.*")
        return
    except FloodWaitError as e:
        await q.edit(f"⏳ **FloodWait: {e.seconds} saniye bekleyin!**")
        return
    except Exception as e:
        await q.edit(f"❌ **Katılımcı listesi alınamadı:** `{str(e)}`")
        return
    
    await _show_tag_panel(q, "all", message_text, message_entities, has_msg)


@r(outgoing=True, pattern="^.tagadmin(?: |$)(.*)")
async def tag_admins(q):
    """Sadece adminleri etiketler"""
    global tag_active, tag_data
    
    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return
    
    await load_my_blocked_users(q.client)
    
    if tag_active:
        try:
            await q.edit("❌ **Zaten bir etiketleme işlemi devam ediyor!**\nKapatmak için: `.tagstop`")
        except:
            pass
        return
    
    if q.fwd_from:
        return
    
    group_size, message_text, message_entities, is_reply = parse_tag_command(q)
    
    reply_msg = await q.get_reply_message()
    if reply_msg and (is_reply or not message_text):
        message_text = (getattr(reply_msg, "raw_text", None) or reply_msg.text or "📢 Adminler!")
        message_entities = reply_msg.entities
        is_reply = True
    
    has_msg = bool(message_text)
    if not message_text:
        message_text = "📢 Adminler!"
    
    chat = await q.get_input_chat()
    
    try:
        test_admin = await q.client.get_participants(chat, filter=cp, limit=1)
    except ChatAdminRequiredError:
        await q.edit("❌ **Admin listesini almak için admin olmalısınız!**\n\n"
                    "⚠️ *Grup gizli olabilir veya admin değilsiniz.*")
        return
    except ChannelPrivateError:
        await q.edit("❌ **Bu gruba erişimim yok!**")
        return
    except FloodWaitError as e:
        await q.edit(f"⏳ **FloodWait: {e.seconds} saniye bekleyin!**")
        return
    except Exception as e:
        await q.edit(f"❌ **Admin kontrolü yapılamadı:** `{str(e)}`")
        return
    
    await _show_tag_panel(q, "admin", message_text, message_entities, has_msg)


async def tag_process(q, chat, mode, status_msg, group_size=1):
    """Etiketleme işlemini gerçekleştir - Gerçek mention bildirimi ile"""
    global tag_active, tag_data
    
    userbot_id = (await q.client.get_me()).id
    
    filter_type = cp if mode == "admin" else None
    
    try:
        participants = []
        
        try:
            async for user in q.client.iter_participants(chat, filter=filter_type):
                if not tag_active:
                    break
                
                if user.bot or user.deleted:
                    tag_data["skipped_count"] += 1
                    continue
                
                if user.id == userbot_id:
                    tag_data["skipped_count"] += 1
                    continue
                
                if user.id in blocked_users:
                    tag_data["skipped_count"] += 1
                    continue
                
                participants.append(user)
                
                if len(participants) >= 5000:
                    break
        
        except ChatAdminRequiredError:
            try:
                await status_msg.edit("❌ **Katılımcı listesini almak için admin olmalısınız!**\n\n"
                                    "⚠️ *Grup gizli olabilir veya üye listesini görme izniniz yok.*")
            except:
                pass
            tag_active = False
            return
        except ChannelPrivateError:
            try:
                await status_msg.edit("❌ **Bu gruba erişimim yok!**")
            except:
                pass
            tag_active = False
            return
        except FloodWaitError as e:
            try:
                await status_msg.edit(f"⏳ **FloodWait: {e.seconds} saniye bekleyin!**\n"
                                    "İşlem durduruldu.")
            except:
                pass
            tag_active = False
            return
        except Exception as e:
            try:
                await status_msg.edit(f"❌ **Katılımcı alınamadı:** `{str(e)}`")
            except:
                pass
            tag_active = False
            return
        
        tag_data["total_count"] = len(participants)
        
        if not participants:
            try:
                await status_msg.edit("❌ **Etiketlenecek kimse bulunamadı!**")
            except:
                pass
            tag_active = False
            return
        
        if len(participants) > 1000:
            try:
                await status_msg.edit(f"⚠️ **Çok fazla katılımcı:** {len(participants)}\n"
                                    "İşlem uzun sürebilir.")
                await asyncio.sleep(2)
            except:
                pass
        
        try:
            await status_msg.edit(f"⏳ **Etiketleme başlıyor...**\n"
                                 f"👥 Toplam: {len(participants)} kişi\n"
                                 f"📦 **Grup Boyutu:** {group_size}\n"
                                 f"⏱️ **Bekleme:** 2.5s")
        except:
            pass
        
        for i in range(0, len(participants), group_size):
            if not tag_active:
                break
            
            group = participants[i:i + group_size]
            if not group:
                continue
            
            try:
                original_message = tag_data['message']
                original_entities = tag_data.get("message_entities")
                
                message_utf16_len = telegram_text_length(original_message)
                separator = "\n\n"
                separator_len = 2
                
                mention_start_offset = message_utf16_len + separator_len
                
                # DÜZELTME: async fonksiyon - InputMessageEntityMentionName kullanır
                mention_text, mention_entities, successful_users = await build_mention_text_and_entities(
                    q.client, group, mention_start_offset
                )
                
                full_message = f"{original_message}{separator}{mention_text}"
                
                all_entities = []
                
                if original_entities:
                    all_entities.extend(copy.deepcopy(original_entities))
                
                all_entities.extend(mention_entities)
                
                if len(full_message) <= 4096:
                    await q.client.send_message(
                        q.chat_id,
                        full_message,
                        formatting_entities=all_entities if all_entities else None,
                        silent=True
                    )
                    tag_data["tagged_count"] += len(successful_users)
                else:
                    max_tags_per_msg = 3 if group_size > 3 else group_size
                    for j in range(0, len(group), max_tags_per_msg):
                        sub_group = group[j:j + max_tags_per_msg]
                        
                        sub_mention_text, sub_mention_entities, sub_successful = await build_mention_text_and_entities(
                            q.client, sub_group, mention_start_offset
                        )
                        sub_message = f"{original_message}{separator}{sub_mention_text}"
                        
                        sub_all_entities = []
                        if original_entities:
                            sub_all_entities.extend(copy.deepcopy(original_entities))
                        sub_all_entities.extend(sub_mention_entities)
                        
                        await q.client.send_message(
                            q.chat_id,
                            sub_message,
                            formatting_entities=sub_all_entities if sub_all_entities else None,
                            silent=True
                        )
                        tag_data["tagged_count"] += len(sub_successful)
                
                if i % max(1, len(participants) // 10) == 0 or i + group_size >= len(participants):
                    percentage = min(100, (i + group_size) * 100 // len(participants))
                    
                    try:
                        await status_msg.edit(f"⏳ **Etiketleniyor...**\n\n"
                                             f"📊 %{percentage} tamamlandı\n"
                                             f"✅ **Etiketlenen:** {tag_data['tagged_count']}/{len(participants)}\n"
                                             f"📦 **Grup:** {group_size} kişi\n"
                                             f"⏱️ **Bekleme:** 2.5s")
                    except:
                        pass
                
                await asyncio.sleep(2.5)
                
            except FloodWaitError as e:
                try:
                    await status_msg.edit(f"⏳ **FloodWait: {e.seconds} saniye bekleniyor...**\n"
                                         "İşlem duraklatıldı.")
                except:
                    pass
                await asyncio.sleep(e.seconds)
                continue
            except Exception as e:
                tag_data["skipped_count"] += len(group)
                continue
        
        if tag_active:
            try:
                await status_msg.edit(f"✅ **Etiketleme Tamamlandı!**\n\n"
                                     f"📊 **Sonuçlar:**\n"
                                     f"✅ Etiketlenen: {tag_data['tagged_count']}\n"
                                     f"❌ Atlanan: {tag_data['skipped_count']}\n"
                                     f"👥 Toplam: {len(participants)}\n"
                                     f"📦 Grup Boyutu: {group_size}\n"
                                     f"⏱️ Bekleme: 2.5s")
            except:
                pass
    
    except Exception as e:
        try:
            await status_msg.edit(f"❌ **Hata oluştu:** `{str(e)}`")
        except:
            pass
    
    finally:
        tag_active = False
        tag_data["current_task"] = None


@r(outgoing=True, pattern="^.tagstop$")
async def tag_stop(q):
    """Etiketlemeyi durdurur"""
    global tag_active, tag_data

    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return

    bot = _get_bot()
    job = None
    if bot is not None and hasattr(bot, "_tag_jobs"):
        job = bot._tag_jobs.get(userbot_id)

    active = bool(job and job.get("active")) or tag_active
    if not active:
        try:
            await q.edit("❌ **Şu anda aktif bir etiketleme yok!**")
        except:
            pass
        return

    # Yeni buton akışı işini durdur (döngü son mesajdan sonra nazikçe biter)
    if job:
        job["active"] = False

    # Eski akış (varsa)
    tag_active = False
    if tag_data.get("current_task"):
        try:
            tag_data["current_task"].cancel()
        except:
            pass

    try:
        await q.edit("⏹️ **Etiketleme durduruluyor...**\n"
                     "Son gönderilen mesajdan sonra duracak.")
    except:
        pass


@r(outgoing=True, pattern="^.tagstat$")
async def tag_status(q):
    """Etiketleme durumunu gösterir"""
    global tag_active, tag_data

    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return

    bot = _get_bot()
    job = None
    if bot is not None and hasattr(bot, "_tag_jobs"):
        job = bot._tag_jobs.get(userbot_id)

    if job and job.get("active"):
        tagged = job.get("tagged", 0)
        total = job.get("total", 0)
        status_text = ("🟢 **ETİKETLEME AKTİF**\n\n"
                       f"✅ **Etiketlenen:** {tagged}/{total}\n\n"
                       "⏹️ Durdurmak için: `.tagstop`")
    elif tag_active:
        mode_text = "👥 Tüm Üyeler" if tag_data.get("mode") == "all" else "👑 Sadece Adminler"
        status_text = ("🟢 **ETİKETLEME AKTİF**\n\n"
                       f"👤 **Mod:** {mode_text}\n"
                       f"✅ **Etiketlenen:** {tag_data.get('tagged_count', 0)}\n\n"
                       "⏹️ Durdurmak için: `.tagstop`")
    else:
        await load_my_blocked_users(q.client)
        status_text = ("🔴 **ETİKETLEME PASİF**\n\n"
                       "**Kullanım:**\n"
                       "• `.tag <mesaj>` → Mesajla etiketle (buton paneli açılır)\n"
                       "• `.tag` (boş) → Rastgele mesajlarla etiketle (kategori seçersin)\n"
                       "• Mesaja `{mention}` koyarsan etiket oraya gelir\n"
                       "• `.tagadmin <mesaj>` → Sadece adminleri etiketle\n"
                       "• `.tagstop` → Aktif etiketlemeyi durdurur\n")
        if blocked_users:
            status_text += f"\n🚫 **Engelli:** {len(blocked_users)} kişi\n"

    try:
        await q.edit(status_text)
    except:
        pass


@r(outgoing=True, pattern="^.tagban(?: |$)(.*)")
async def block_user(q):
    """Kullanıcıyı etiketlemeden engelle"""
    global blocked_users
    
    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return
    
    await load_my_blocked_users(q.client)
    
    args = q.pattern_match.group(1).strip()
    
    user_id = None
    user_name = None
    
    reply_msg = await q.get_reply_message()
    if reply_msg:
        user_id = reply_msg.sender_id
        try:
            user_entity = await q.client.get_entity(user_id)
            user_name = user_entity.first_name or "Kullanıcı"
        except:
            user_name = "Kullanıcı"
    
    elif args:
        if args.startswith("@"):
            try:
                user_entity = await q.client.get_entity(args)
                user_id = user_entity.id
                user_name = user_entity.first_name or args
            except Exception as e:
                await q.edit(f"❌ **Kullanıcı bulunamadı:** `{args}`\n\n`{str(e)}`")
                return
        elif args.isdigit():
            user_id = int(args)
            try:
                user_entity = await q.client.get_entity(user_id)
                user_name = user_entity.first_name or "Kullanıcı"
            except:
                user_name = f"ID: {user_id}"
        else:
            await q.edit("❌ **Geçersiz format!**\n\n"
                        "**Kullanım:**\n"
                        "• `.tagban <id>` - ID ile engelle\n"
                        "• `.tagban @username` - Username ile engelle\n"
                        "• `[mesajı yanıtla] .tagban` - Reply ile engelle")
            return
    else:
        await q.edit("❌ **Kullanıcı belirtmelisiniz!**\n\n"
                    "**Kullanım:**\n"
                    "• `.tagban <id>` - ID ile engelle\n"
                    "• `.tagban @username` - Username ile engelle\n"
                    "• `[mesajı yanıtla] .tagban` - Reply ile engelle")
        return
    
    if user_id == userbot_id:
        await q.edit("❌ **Kendinizi engelleyemezsiniz!**")
        return
    
    if user_id in blocked_users:
        await q.edit(f"⚠️ **Bu kullanıcı zaten engelli!**\n\n"
                    f"👤 **İsim:** {user_name}\n"
                    f"🆔 **ID:** `{user_id}`")
        return
    
    blocked_users.add(user_id)
    await save_blocked_users(q.client)
    
    await q.edit(f"✅ **Kullanıcı engellendi!**\n\n"
                f"👤 **İsim:** {user_name}\n"
                f"🆔 **ID:** `{user_id}`\n\n"
                f"Bu kullanıcı artık etiketlenmeyecek.\n"
                f"Engeli kaldırmak için: `.tagunban {user_id}`")


@r(outgoing=True, pattern="^.tagunban(?: |$)(.*)")
async def unblock_user(q):
    """Kullanıcının engelini kaldır"""
    global blocked_users
    
    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return
    
    await load_my_blocked_users(q.client)
    
    args = q.pattern_match.group(1).strip()
    
    user_id = None
    user_name = None
    
    reply_msg = await q.get_reply_message()
    if reply_msg:
        user_id = reply_msg.sender_id
        try:
            user_entity = await q.client.get_entity(user_id)
            user_name = user_entity.first_name or "Kullanıcı"
        except:
            user_name = "Kullanıcı"
    
    elif args:
        if args.startswith("@"):
            try:
                user_entity = await q.client.get_entity(args)
                user_id = user_entity.id
                user_name = user_entity.first_name or args
            except Exception as e:
                await q.edit(f"❌ **Kullanıcı bulunamadı:** `{args}`\n\n`{str(e)}`")
                return
        elif args.isdigit():
            user_id = int(args)
            try:
                user_entity = await q.client.get_entity(user_id)
                user_name = user_entity.first_name or "Kullanıcı"
            except:
                user_name = f"ID: {user_id}"
        else:
            await q.edit("❌ **Geçersiz format!**\n\n"
                        "**Kullanım:**\n"
                        "• `.tagunban <id>` - ID ile engel kaldır\n"
                        "• `.tagunban @username` - Username ile engel kaldır\n"
                        "• `[mesajı yanıtla] .tagunban` - Reply ile engel kaldır")
            return
    else:
        await q.edit("❌ **Kullanıcı belirtmelisiniz!**\n\n"
                    "**Kullanım:**\n"
                    "• `.tagunban <id>` - ID ile engel kaldır\n"
                    "• `.tagunban @username` - Username ile engel kaldır\n"
                    "• `[mesajı yanıtla] .tagunban` - Reply ile engel kaldır")
        return
    
    if user_id not in blocked_users:
        await q.edit(f"⚠️ **Bu kullanıcı zaten engelli değil!**\n\n"
                    f"👤 **İsim:** {user_name}\n"
                    f"🆔 **ID:** `{user_id}`")
        return
    
    blocked_users.discard(user_id)
    await save_blocked_users(q.client)
    
    await q.edit(f"✅ **Engel kaldırıldı!**\n\n"
                f"👤 **İsim:** {user_name}\n"
                f"🆔 **ID:** `{user_id}`\n\n"
                f"Bu kullanıcı artık etiketlenebilir.")


@r(outgoing=True, pattern="^.tagbanlistremove$")
async def clear_blocks(q):
    """Tüm engelleri temizle"""
    global blocked_users
    
    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return
    
    await load_my_blocked_users(q.client)
    
    if not blocked_users:
        await q.edit("⚠️ **Engelli kullanıcı yok!**")
        return
    
    count = len(blocked_users)
    blocked_users.clear()
    await save_blocked_users(q.client)
    
    await q.edit(f"✅ **Tüm engeller temizlendi!**\n\n"
                f"🗑️ **Temizlenen:** {count} kullanıcı")


@r(outgoing=True, pattern="^.tagbanlist$")
async def list_blocks(q):
    """Engellenen kullanıcıları listele"""
    global blocked_users
    
    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return
    
    await load_my_blocked_users(q.client)
    
    if not blocked_users:
        await q.edit("✅ **Engelli kullanıcı yok!**")
        return
    
    msg = f"🚫 **ENGELLİ KULLANICILAR** ({len(blocked_users)})\n\n"
    
    for i, user_id in enumerate(sorted(blocked_users), 1):
        try:
            user_entity = await q.client.get_entity(user_id)
            user_name = user_entity.first_name or "Kullanıcı"
        except:
            user_name = "Bilinmeyen"
        
        msg += f"{i}. **{user_name}** - `{user_id}`\n"
        
        if len(msg) > 3500:
            msg += f"\n... ve {len(blocked_users) - i} kişi daha"
            break
    
    msg += f"\n💡 Engeli kaldırmak için: `.tagunban <id>`"
    
    await q.edit(msg)


@r(outgoing=True, pattern="^.taghelp$")
async def tag_help(q):
    """Yardım mesajı gösterir"""
    userbot_id = (await q.client.get_me()).id
    if q.sender_id != userbot_id:
        return
    
    help_text = """
**📢 TAG PLUGİN — YARDIM**

`.tag` artık **butonlu panel** ile çalışır.

**🎯 NASIL ÇALIŞIR:**
1) Bir grupta `.tag` yaz (dilersen yanına mesaj yaz ya da bir mesajı yanıtla).
2) Açılan panelden seç:
 • Mesaj girdiysen → kaç kişilik grup (1 / 3 / 5 / 10)
 • Mesaj girmediysen → rastgele mesaj türü (günaydın, iyi geceler, soru, komik, soğuk espri)
3) Sonra kaç saniyede bir göndereceğini seç (2.5 / 3 / 5 / 6 sn).
4) Etiketleme başlar.

**🏷️ ETİKETİ İSTEDİĞİN YERE KOY:**
Mesajının içine `{mention}` yaz, etiket tam oraya gelir:
 • `merhaba {mention} nasılsın` → "merhaba [kişi] nasılsın"
 • `{mention} iyi geceler` → "[kişi] iyi geceler"
`{mention}` yazmazsan etiket eskisi gibi mesajın altına eklenir.
(En kişisel his için 1'erli gönderim önerilir.)

**📎 YANITLI KULLANIM:**
Bir mesajı yanıtlayıp `.tag` yaz → o mesaj kullanılır (premium emoji korunur).
İçine `{mention}` koyarsan yine istediğin yere etiket gelir.

**👑 SADECE ADMİNLER:**
`.tagadmin` → aynı panel, ama yalnızca grup adminlerini etiketler.

**🚫 ENGELLEME:**
 • `.tagban <id/@kullanıcı>` veya bir mesajı yanıtlayıp `.tagban`
 • `.tagunban <id/@kullanıcı>`
 • `.tagbanlist` / `.tagbanlistremove`

**🛑 KONTROL:**
 • `.tagstop` → durdurur (gönderilen son mesajdan sonra biter)
 • `.tagstat` → durumu gösterir

**⚙️ NOTLAR:**
 • Botlar, silinmiş hesaplar, sen ve engellediklerin atlanır.
 • Üyeleri görebilmek için grupta yönetici olman gerekebilir.
 • Grupta inline (satıriçi) gönderim kapalıysa panel sana özelden gelir.
 • Rastgele sözler her kişiye farklı gelir; her 50 kişide söz tekrar etmez.
"""
    
    try:
        await q.edit(help_text)
    except:
        pass


# ==========================================
# CMDHELP AYARLARI
# ==========================================

Help = CmdHelp('tag')
Help.add_command('tag <mesaj>', None, 'Buton paneli açar; mesajla üyeleri etiketler ({mention} ile konum)')
Help.add_command('tag', None, 'Mesajsız: rastgele mesaj kategorisi + süre paneli açar')
Help.add_command('tagadmin <mesaj>', None, 'Buton paneli açar; sadece adminleri etiketler')
Help.add_command('tagadmin', None, 'Mesajsız: adminler için kategori + süre paneli açar')
Help.add_command('tagban <id/@username>', None, 'Kullanıcıyı etiketlemeden engelle (reply destekli)')
Help.add_command('tagunban <id/@username>', None, 'Kullanıcının engelini kaldır (reply destekli)')
Help.add_command('tagbanlistremove', None, 'Tüm engelleri temizle')
Help.add_command('tagbanlist', None, 'Engellenen kullanıcıları listele')
Help.add_command('tagstop', None, 'Aktif etiketlemeyi durdurur')
Help.add_command('tagstat', None, 'Etiketleme durumunu gösterir')
Help.add_command('taghelp', None, 'Detaylı yardım mesajı gösterir')
Help.add_info('Gruplarda toplu etiketleme - Premium emoji & Engelleme sistemi!')
Help.add()