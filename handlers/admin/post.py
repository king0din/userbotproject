# ============================================
# KingTG UserBot Service - Admin / post
# Plugin kanalı için butonlu/tepkili post oluşturucu
# (admin.py'dan otomatik bölündü - davranış birebir korundu)
# ============================================

# ============================================
# KingTG UserBot Service - Admin Handlers
# ============================================

from telethon import events, Button
import config
from database import database as db
from userbot.smart_manager import smart_session_manager

# Eski uyumluluk için alias
userbot_manager = smart_session_manager
from utils import send_log


def register(bot):

    post_states = {}

    @bot.on(events.NewMessage(pattern=r'^/post$'))
    async def post_command(event):
        """Plugin kanalına post oluştur"""
        if event.sender_id != config.OWNER_ID and not await db.is_sudo(event.sender_id):
            return
        
        post_states[event.sender_id] = {
            'stage': 'waiting_content',
            'content': None,
            'media': None,
            'buttons': [],
            'current_row': []
        }
        
        await event.respond(
            "📝 **Post Oluşturma**\n\n"
            "Göndermek istediğiniz postu yazın veya medya gönderin.\n"
            "Başka bir mesajı iletmek için mesajı **forward** edin.\n\n"
            "⚠️ İptal: /cancelpost",
            buttons=[[Button.inline("❌ İptal", b"cancel_post")]]
        )
    

    @bot.on(events.NewMessage(pattern=r'^/cancelpost$'))
    async def cancelpost_command(event):
        if event.sender_id in post_states:
            del post_states[event.sender_id]
        await event.respond("❌ Post oluşturma iptal edildi.")
    

    @bot.on(events.NewMessage(func=lambda e: e.is_private and e.sender_id in post_states and not e.text.startswith('/')))
    async def post_content_handler(event):
        """Post içeriğini al"""
        user_id = event.sender_id
        state = post_states.get(user_id)
        
        if not state:
            return
        
        stage = state.get('stage')
        
        if stage == 'waiting_content':
            # Orijinal mesajı tamamen kaydet
            state['content'] = event.message
            state['stage'] = 'adding_buttons'
            
            await event.respond(
                "✅ **İçerik alındı!**\n\n"
                "Şimdi buton ekleyebilirsiniz:",
                buttons=[
                    [Button.inline("🔗 Link Butonu", b"post_add_link")],
                    [Button.inline("👍 Tepki Butonu", b"post_add_reaction")],
                    [Button.inline("➡️ Aynı Satıra Ekle", b"post_same_row"),
                     Button.inline("⬇️ Alt Satıra Geç", b"post_new_row")],
                    [Button.inline("👁️ Önizleme", b"post_preview")],
                    [Button.inline("✅ Gönder", b"post_confirm"),
                     Button.inline("❌ İptal", b"cancel_post")]
                ]
            )
        
        elif stage == 'waiting_link_text':
            state['temp_link_text'] = event.text
            state['stage'] = 'waiting_link_url'
            await event.respond("🔗 Şimdi **URL** girin:\nÖrnek: `https://t.me/KingTGPlugins`")
        
        elif stage == 'waiting_link_url':
            url = event.text.strip()
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            btn = {'type': 'url', 'text': state['temp_link_text'], 'url': url}
            
            if state.get('add_to_current_row', True) and state['current_row']:
                state['current_row'].append(btn)
            else:
                if state['current_row']:
                    state['buttons'].append(state['current_row'])
                state['current_row'] = [btn]
            
            state['stage'] = 'adding_buttons'
            await event.respond(
                f"✅ **Link butonu eklendi!**\n`{state['temp_link_text']}` → `{url}`",
                buttons=[
                    [Button.inline("🔗 Link Butonu", b"post_add_link")],
                    [Button.inline("👍 Tepki Butonu", b"post_add_reaction")],
                    [Button.inline("➡️ Aynı Satıra Ekle", b"post_same_row"),
                     Button.inline("⬇️ Alt Satıra Geç", b"post_new_row")],
                    [Button.inline("👁️ Önizleme", b"post_preview")],
                    [Button.inline("✅ Gönder", b"post_confirm"),
                     Button.inline("❌ İptal", b"cancel_post")]
                ]
            )
        
        elif stage == 'waiting_reactions':
            # Emoji'leri al
            import re
            emojis = re.findall(r'[\U0001F300-\U0001F9FF]|[\u2600-\u26FF]|[\u2700-\u27BF]|[\U0001FA00-\U0001FA6F]|[\U0001FA70-\U0001FAFF]', event.text)
            
            if not emojis:
                await event.respond("⚠️ Emoji bulunamadı. Tekrar deneyin:\nÖrnek: `👍❤️🔥`")
                return
            
            state['temp_reactions'] = emojis
            state['stage'] = 'waiting_reaction_layout'
            
            await event.respond(
                f"✅ **Tepkiler:** {' '.join(emojis)}\n\n"
                "Nasıl dizilsin?",
                buttons=[
                    [Button.inline("➡️ Yan Yana", b"reaction_horizontal")],
                    [Button.inline("⬇️ Alt Alta", b"reaction_vertical")],
                    [Button.inline("❌ İptal", b"post_back_to_buttons")]
                ]
            )
    

    @bot.on(events.CallbackQuery(data=b"post_add_link"))
    async def post_add_link_handler(event):
        user_id = event.sender_id
        if user_id not in post_states:
            await event.answer("Önce /post komutu kullanın", alert=True)
            return
        
        post_states[user_id]['stage'] = 'waiting_link_text'
        post_states[user_id]['add_to_current_row'] = False
        await event.edit("🔗 **Link Butonu Ekle**\n\nButon **metnini** girin:\nÖrnek: `📢 Kanala Katıl`")
    

    @bot.on(events.CallbackQuery(data=b"post_add_reaction"))
    async def post_add_reaction_handler(event):
        user_id = event.sender_id
        if user_id not in post_states:
            await event.answer("Önce /post komutu kullanın", alert=True)
            return
        
        post_states[user_id]['stage'] = 'waiting_reactions'
        await event.edit(
            "👍 **Tepki Butonu Ekle**\n\n"
            "Eklemek istediğiniz emojileri gönderin:\n"
            "Örnek: `👍❤️🔥😂👎`"
        )
    

    @bot.on(events.CallbackQuery(data=b"reaction_horizontal"))
    async def reaction_horizontal_handler(event):
        user_id = event.sender_id
        state = post_states.get(user_id)
        if not state:
            return
        
        # Yan yana tepki butonları
        reactions = state.get('temp_reactions', [])
        row = [{'type': 'reaction', 'emoji': e} for e in reactions]
        
        if state['current_row']:
            state['buttons'].append(state['current_row'])
        state['buttons'].append(row)
        state['current_row'] = []
        state['stage'] = 'adding_buttons'
        
        await event.edit(
            f"✅ **Tepkiler eklendi (yan yana):** {' '.join(reactions)}",
            buttons=[
                [Button.inline("🔗 Link Butonu", b"post_add_link")],
                [Button.inline("👍 Tepki Butonu", b"post_add_reaction")],
                [Button.inline("➡️ Aynı Satıra Ekle", b"post_same_row"),
                 Button.inline("⬇️ Alt Satıra Geç", b"post_new_row")],
                [Button.inline("👁️ Önizleme", b"post_preview")],
                [Button.inline("✅ Gönder", b"post_confirm"),
                 Button.inline("❌ İptal", b"cancel_post")]
            ]
        )
    

    @bot.on(events.CallbackQuery(data=b"reaction_vertical"))
    async def reaction_vertical_handler(event):
        user_id = event.sender_id
        state = post_states.get(user_id)
        if not state:
            return
        
        # Alt alta tepki butonları
        reactions = state.get('temp_reactions', [])
        
        if state['current_row']:
            state['buttons'].append(state['current_row'])
            state['current_row'] = []
        
        for e in reactions:
            state['buttons'].append([{'type': 'reaction', 'emoji': e}])
        
        state['stage'] = 'adding_buttons'
        
        await event.edit(
            f"✅ **Tepkiler eklendi (alt alta):** {' '.join(reactions)}",
            buttons=[
                [Button.inline("🔗 Link Butonu", b"post_add_link")],
                [Button.inline("👍 Tepki Butonu", b"post_add_reaction")],
                [Button.inline("➡️ Aynı Satıra Ekle", b"post_same_row"),
                 Button.inline("⬇️ Alt Satıra Geç", b"post_new_row")],
                [Button.inline("👁️ Önizleme", b"post_preview")],
                [Button.inline("✅ Gönder", b"post_confirm"),
                 Button.inline("❌ İptal", b"cancel_post")]
            ]
        )
    

    @bot.on(events.CallbackQuery(data=b"post_same_row"))
    async def post_same_row_handler(event):
        user_id = event.sender_id
        state = post_states.get(user_id)
        if not state:
            return
        
        state['add_to_current_row'] = True
        await event.answer("➡️ Sonraki buton aynı satıra eklenecek")
    

    @bot.on(events.CallbackQuery(data=b"post_new_row"))
    async def post_new_row_handler(event):
        user_id = event.sender_id
        state = post_states.get(user_id)
        if not state:
            return
        
        if state['current_row']:
            state['buttons'].append(state['current_row'])
            state['current_row'] = []
        
        state['add_to_current_row'] = False
        await event.answer("⬇️ Sonraki buton yeni satıra eklenecek")
    

    @bot.on(events.CallbackQuery(data=b"post_back_to_buttons"))
    async def post_back_to_buttons_handler(event):
        user_id = event.sender_id
        state = post_states.get(user_id)
        if not state:
            return
        
        state['stage'] = 'adding_buttons'
        await event.edit(
            "📝 **Buton Ekleme**",
            buttons=[
                [Button.inline("🔗 Link Butonu", b"post_add_link")],
                [Button.inline("👍 Tepki Butonu", b"post_add_reaction")],
                [Button.inline("➡️ Aynı Satıra Ekle", b"post_same_row"),
                 Button.inline("⬇️ Alt Satıra Geç", b"post_new_row")],
                [Button.inline("👁️ Önizleme", b"post_preview")],
                [Button.inline("✅ Gönder", b"post_confirm"),
                 Button.inline("❌ İptal", b"cancel_post")]
            ]
        )
    

    def build_post_buttons(state):
        """State'den Telethon butonları oluştur"""
        all_buttons = state['buttons'].copy()
        if state['current_row']:
            all_buttons.append(state['current_row'])
        
        telethon_buttons = []
        for row in all_buttons:
            btn_row = []
            for btn in row:
                if btn['type'] == 'url':
                    btn_row.append(Button.url(btn['text'], btn['url']))
                elif btn['type'] == 'reaction':
                    # Tepki butonları - başlangıçta 0
                    btn_row.append(Button.inline(f"{btn['emoji']} 0", f"react_{btn['emoji']}_0".encode()))
            if btn_row:
                telethon_buttons.append(btn_row)
        
        return telethon_buttons if telethon_buttons else None
    

    @bot.on(events.CallbackQuery(pattern=rb"react_(.+)_(\d+)"))
    async def reaction_handler(event):
        """Tepki butonuna tıklandığında"""
        user_id = event.sender_id
        data = event.data.decode()
        
        # Emoji'yi çıkar (react_👍_5 -> 👍)
        parts = data.split("_")
        emoji = parts[1]
        
        # Mesaj ID ve Chat ID
        msg_id = event.message_id
        chat_id = event.chat_id
        
        # Mesajı al
        try:
            message = await event.get_message()
            if not message:
                await event.answer("Mesaj bulunamadı!")
                return
        except Exception:
            await event.answer("Hata!")
            return
        
        # Kullanıcının tepkisini veritabanından kontrol et
        reaction_key = f"reaction_{chat_id}_{msg_id}"
        user_reactions = await db.get_user_reaction(reaction_key, user_id)
        
        # Mevcut butonları al
        current_buttons = message.buttons
        if not current_buttons:
            await event.answer("Buton bulunamadı!")
            return
        
        new_buttons = []
        for row in current_buttons:
            new_row = []
            for btn in row:
                btn_data = btn.data.decode() if btn.data else ""
                btn_text = btn.text
                
                if btn_data.startswith("react_"):
                    # Bu bir tepki butonu
                    btn_parts = btn_data.split("_")
                    btn_emoji = btn_parts[1]
                    
                    # Mevcut sayıyı al
                    try:
                        current_count = int(btn_text.split()[-1])
                    except Exception:
                        current_count = 0
                    
                    if btn_emoji == emoji:
                        # Tıklanan buton
                        if user_reactions == emoji:
                            # Aynı tepkiye tekrar tıkladı - geri al
                            new_count = max(0, current_count - 1)
                            await db.set_user_reaction(reaction_key, user_id, None)
                            await event.answer(f"{emoji} geri alındı")
                        else:
                            # Yeni tepki
                            new_count = current_count + 1
                            await db.set_user_reaction(reaction_key, user_id, emoji)
                            await event.answer(f"{emoji}")
                    else:
                        # Tıklanmayan buton
                        if user_reactions == btn_emoji:
                            # Kullanıcı bu tepkiden vazgeçti (başka tepkiye geçti)
                            new_count = max(0, current_count - 1)
                        else:
                            new_count = current_count
                    
                    new_row.append(Button.inline(f"{btn_emoji} {new_count}", f"react_{btn_emoji}_{new_count}".encode()))
                else:
                    # URL butonu - olduğu gibi bırak
                    if btn.url:
                        new_row.append(Button.url(btn_text, btn.url))
                    else:
                        new_row.append(Button.inline(btn_text, btn.data))
            
            if new_row:
                new_buttons.append(new_row)
        
        # Mesajı güncelle
        try:
            await event.edit(buttons=new_buttons)
        except Exception as e:
            # Aynı butonlarsa veya başka hata
            pass
    

    @bot.on(events.CallbackQuery(data=b"post_preview"))
    async def post_preview_handler(event):
        user_id = event.sender_id
        state = post_states.get(user_id)
        if not state or not state.get('content'):
            await event.answer("İçerik bulunamadı", alert=True)
            return
        
        await event.answer("👁️ Önizleme gönderiliyor...")
        
        buttons = build_post_buttons(state)
        content = state['content']
        
        try:
            # Mesajı butonlarla birlikte gönder
            if content.media:
                preview = await bot.send_file(
                    user_id,
                    file=content.media,
                    caption=content.message,
                    buttons=buttons,
                    formatting_entities=content.entities
                )
            else:
                preview = await bot.send_message(
                    user_id,
                    content.message,
                    buttons=buttons,
                    formatting_entities=content.entities,
                    link_preview=False
                )
            
            state['preview_id'] = preview.id
            
            await bot.send_message(
                user_id,
                "👆 **Önizleme**\n\nBu şekilde gönderilecek.",
                buttons=[
                    [Button.inline("✅ Onayla ve Gönder", b"post_confirm")],
                    [Button.inline("✏️ Buton Düzenle", b"post_back_to_buttons")],
                    [Button.inline("❌ İptal", b"cancel_post")]
                ]
            )
        except Exception as e:
            await event.respond(f"❌ Önizleme hatası: `{e}`")
    

    @bot.on(events.CallbackQuery(data=b"post_confirm"))
    async def post_confirm_handler(event):
        user_id = event.sender_id
        state = post_states.get(user_id)
        if not state or not state.get('content'):
            await event.answer("İçerik bulunamadı", alert=True)
            return
        
        await event.edit("⏳ **Gönderiliyor...**")
        
        buttons = build_post_buttons(state)
        content = state['content']
        channel = config.PLUGIN_CHANNEL
        
        try:
            # Kanala gönder
            if content.media:
                msg = await bot.send_file(
                    f"@{channel}",
                    file=content.media,
                    caption=content.message,
                    buttons=buttons,
                    formatting_entities=content.entities
                )
            else:
                msg = await bot.send_message(
                    f"@{channel}",
                    content.message,
                    buttons=buttons,
                    formatting_entities=content.entities,
                    link_preview=False
                )
            
            del post_states[user_id]
            
            await event.edit(
                f"✅ **Post gönderildi!**\n\n"
                f"📢 Kanal: @{channel}\n"
                f"🔗 [Gönderiye Git](https://t.me/{channel}/{msg.id})"
            )
            await send_log(bot, "post", f"Plugin kanalına post gönderildi", user_id)
            
        except Exception as e:
            await event.edit(f"❌ **Hata:** `{e}`\n\nBot'un kanala mesaj atma yetkisi var mı kontrol edin.")
    

    @bot.on(events.CallbackQuery(data=b"cancel_post"))
    async def cancel_post_handler(event):
        user_id = event.sender_id
        if user_id in post_states:
            del post_states[user_id]
        await event.edit("❌ Post oluşturma iptal edildi.")

    # ==========================================
    # PLUGİN AYARLARI (/psettings)
    # ==========================================
