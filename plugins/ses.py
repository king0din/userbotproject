# KingTG UserBot - Ses (TTS) Plugin
# Metni doğal sese dönüştürür
# requires: edge-tts pydub
#
# Kullanım:
#   .ses <metin>
#   .ses (mesaja yanıt vererek)
#   .ses (txt dosyasına yanıt vererek)
#   .sesler (mevcut sesleri listele)
#   .sesayar <ses_kodu> (varsayılan sesi değiştir)
"""
Herhangi bir sohbete yazdığınız yazıyı yada bir yazıyı yanıtlayarak kullandığınızda o yazıyı ses dosyası olarak gönderir.

🔧 Komutlar:  .ses, .sesler, .sesayar
🚨 Tür: #eğlence


Komular hakında:
.ses: Bu komutla yanıtlanan veya girilen metni sese çevir.
      Ayrıca bir .txt dosyasına yanıt vererek dosyadaki metni sese çevirebilirsiniz.
      Uzun metinler otomatik olarak parçalanır ve birleştirilir.

.sesler: Bu komut gönderildiği zaman mevcut seslerin listesini ve değiştirme komutlarının listesini gösterir.

.sesayar: Bu komutla ses ayarı yapılır.
Örnek: .sesayar kadın
Örnek2: .sesayar erkek

Veya başka bir dile çevirmek istiyorsanız başına ülke kodu ekleyerek:
Örnek: .sesayar en-erkek
Örnek2: .sesayar en-kadın
İngilizce dilindeki yazıyı ingilizce sese çevirir.

Not: Türkçe için ülke kodu girmenize gerek yok sadece cinsiyet yazmanız yeterlidir.
Örnek: .sesayar erkek
"""

from telethon import events
import os
import tempfile
import edge_tts
import json

# Varsayılan ses (Türkçe erkek)
DEFAULT_VOICE = "tr-TR-AhmetNeural"

# Mevcut ses ayarı
current_voice = DEFAULT_VOICE


# ── SES TERCİHİ KALICILIĞI (restart'ta seçtiğin ses kaybolmasın) ──
_VOICE_FILE = os.path.join(os.path.dirname(__file__), "ses_voice.json")


def _load_voice(uid):
    try:
        if os.path.exists(_VOICE_FILE):
            with open(_VOICE_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get(str(uid))
    except Exception:
        pass
    return None


def _save_voice(uid, code):
    data = {}
    try:
        if os.path.exists(_VOICE_FILE):
            with open(_VOICE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
    except Exception:
        pass
    data[str(uid)] = code
    try:
        with open(_VOICE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def cleanup_user_data(user_id, reason="disable"):
    """Kullanıcının ses tercihini temizle. Çıkışta korunur (tercih); devre dışı/silmede silinir."""
    try:
        if reason == "logout":
            return
        if os.path.exists(_VOICE_FILE):
            with open(_VOICE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if str(user_id) in data:
                data.pop(str(user_id), None)
                with open(_VOICE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f)
    except Exception:
        pass

# Chunk boyutu (karakter)
CHUNK_SIZE = 4000

# Popüler Türkçe sesler
TURKISH_VOICES = {
    "erkek": "tr-TR-AhmetNeural",
    "kadın": "tr-TR-EmelNeural",
}

# Diğer dil sesleri
OTHER_VOICES = {
    "en-erkek": "en-US-ChristopherNeural",
    "en-kadın": "en-US-JennyNeural",
    "de-erkek": "de-DE-ConradNeural",
    "de-kadın": "de-DE-KatjaNeural",
    "fr-erkek": "fr-FR-HenriNeural",
    "fr-kadın": "fr-FR-DeniseNeural",
    "ar-erkek": "ar-SA-HamedNeural",
    "ar-kadın": "ar-SA-ZariyahNeural",
    "ru-erkek": "ru-RU-DmitryNeural",
    "ru-kadın": "ru-RU-SvetlanaNeural",
}

ALL_VOICES = {**TURKISH_VOICES, **OTHER_VOICES}


def split_text_into_chunks(text, chunk_size=CHUNK_SIZE):
    """
    Metni parçalara böl. Cümle sonlarından bölmeye çalış.
    """
    chunks = []
    
    while len(text) > chunk_size:
        # Chunk boyutuna kadar olan kısmı al
        chunk = text[:chunk_size]
        
        # Son cümle sonunu bul (. ! ? veya \n)
        last_period = -1
        for sep in ['. ', '.\n', '! ', '!\n', '? ', '?\n', '\n\n']:
            pos = chunk.rfind(sep)
            if pos > last_period:
                last_period = pos + len(sep) - 1
        
        # Cümle sonu bulunamadıysa, son boşluğu bul
        if last_period < chunk_size // 2:
            last_space = chunk.rfind(' ')
            if last_space > chunk_size // 2:
                last_period = last_space
        
        # Hiçbir şey bulunamadıysa zorla böl
        if last_period < chunk_size // 2:
            last_period = chunk_size - 1
        
        chunks.append(text[:last_period + 1].strip())
        text = text[last_period + 1:].strip()
    
    if text:
        chunks.append(text)
    
    return chunks


async def text_to_speech_chunk(text, voice, output_path):
    """Tek bir chunk'ı sese çevir"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


async def combine_audio_files(audio_files, output_path):
    """
    Ses dosyalarını birleştir.
    pydub yoksa basit binary birleştirme yap.
    """
    try:
        from pydub import AudioSegment
        
        combined = AudioSegment.empty()
        for audio_file in audio_files:
            segment = AudioSegment.from_mp3(audio_file)
            combined += segment
        
        combined.export(output_path, format="mp3")
        return True
    except ImportError:
        # pydub yoksa binary olarak birleştir
        with open(output_path, 'wb') as outfile:
            for audio_file in audio_files:
                with open(audio_file, 'rb') as infile:
                    outfile.write(infile.read())
        return True
    except Exception:
        return False


async def get_text_from_file(client, message):
    """Dosyadan metin oku"""
    tmp_path = None
    try:
        # Dosyayı indir
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name
        
        await client.download_media(message, tmp_path)
        
        # Dosyayı oku - farklı encoding'leri dene
        text = None
        for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1254', 'iso-8859-9']:
            try:
                with open(tmp_path, 'r', encoding=encoding) as f:
                    text = f.read()
                break
            except UnicodeDecodeError:
                continue
        
        # Geçici dosyayı sil
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        
        return text.strip() if text else None
        
    except Exception:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass
        return None


def register(client):
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.(?:ses|tts)(?:\s+(.+))?$'))
    async def tts_cmd(event):
        global current_voice
        me = await event.client.get_me()
        _saved = _load_voice(me.id)
        if _saved:
            current_voice = _saved
        
        text = event.pattern_match.group(1)
        
        # Yanıt verilen mesajdan metin al
        reply = await event.get_reply_message()
        if reply and not text:
            # Önce dosya var mı kontrol et
            if reply.document:
                # Dosya adını kontrol et
                file_name = ""
                if hasattr(reply.document, 'attributes'):
                    for attr in reply.document.attributes:
                        if hasattr(attr, 'file_name'):
                            file_name = attr.file_name or ""
                            break
                
                # .txt dosyası mı?
                if file_name.lower().endswith('.txt') or reply.document.mime_type == 'text/plain':
                    await event.edit("📄 **Dosya okunuyor...**")
                    text = await get_text_from_file(client, reply)
                    
                    if not text:
                        await event.edit("❌ Dosya okunamadı!")
                        return
                else:
                    await event.edit("❌ Sadece `.txt` dosyaları desteklenir!")
                    return
            else:
                # Normal metin mesajı
                text = reply.raw_text
        
        if not text:
            await event.edit(
                "❌ **Kullanım:**\n"
                "`.ses <metin>`\n"
                "veya bir mesaja yanıt vererek: `.ses`\n"
                "veya bir `.txt` dosyasına yanıt vererek: `.ses`"
            )
            return
        
        char_count = len(text)
        
        # Kısa metin - direkt işle
        if char_count <= CHUNK_SIZE:
            await event.edit(f"🎙️ **Ses oluşturuluyor...**\n`{char_count} karakter`")
            
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                    tmp_path = tmp.name
                
                communicate = edge_tts.Communicate(text, current_voice)
                await communicate.save(tmp_path)
                
                await event.edit("📤 **Gönderiliyor...**")
                
                if reply:
                    await client.send_file(
                        event.chat_id,
                        tmp_path,
                        voice_note=True,
                        reply_to=reply.id
                    )
                else:
                    await client.send_file(
                        event.chat_id,
                        tmp_path,
                        voice_note=True
                    )
                
                await event.delete()
            except Exception as e:
                await event.edit(f"❌ **Hata:** `{e}`")
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
            return
        
        # Uzun metin - parçalara böl
        chunks = split_text_into_chunks(text)
        total_chunks = len(chunks)
        
        await event.edit(
            f"🎙️ **Uzun metin işleniyor...**\n"
            f"`{char_count} karakter` → `{total_chunks} parça`"
        )
        
        temp_files = []
        
        try:
            # Her chunk'ı işle
            for i, chunk in enumerate(chunks):
                await event.edit(
                    f"🎙️ **Ses oluşturuluyor...**\n"
                    f"`Parça {i + 1}/{total_chunks}`"
                )
                
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                    chunk_path = tmp.name
                
                await text_to_speech_chunk(chunk, current_voice, chunk_path)
                temp_files.append(chunk_path)
            
            # Dosyaları birleştir
            await event.edit(f"🔗 **Ses dosyaları birleştiriliyor...**\n`{total_chunks} parça`")
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                final_path = tmp.name
            
            success = await combine_audio_files(temp_files, final_path)
            
            if not success:
                await event.edit("❌ Ses dosyaları birleştirilemedi!")
                return
            
            # Gönder
            await event.edit("📤 **Gönderiliyor...**")
            
            # Dosya boyutunu kontrol et
            file_size = os.path.getsize(final_path)
            file_size_mb = file_size / (1024 * 1024)
            
            if file_size_mb > 50:
                # 50MB'dan büyükse dosya olarak gönder
                if reply:
                    await client.send_file(
                        event.chat_id,
                        final_path,
                        caption=f"🎙️ TTS ({char_count} karakter, {file_size_mb:.1f}MB)",
                        reply_to=reply.id
                    )
                else:
                    await client.send_file(
                        event.chat_id,
                        final_path,
                        caption=f"🎙️ TTS ({char_count} karakter, {file_size_mb:.1f}MB)"
                    )
            else:
                # Voice note olarak gönder
                if reply:
                    await client.send_file(
                        event.chat_id,
                        final_path,
                        voice_note=True,
                        reply_to=reply.id
                    )
                else:
                    await client.send_file(
                        event.chat_id,
                        final_path,
                        voice_note=True
                    )
            
            await event.delete()
            
        except Exception as e:
            await event.edit(f"❌ **Hata:** `{e}`")
        
        finally:
            # Geçici dosyaları temizle
            for tmp_file in temp_files:
                try:
                    os.unlink(tmp_file)
                except:
                    pass
            try:
                os.unlink(final_path)
            except:
                pass
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.sesler$'))
    async def list_voices(event):
        global current_voice
        me = await event.client.get_me()
        _saved = _load_voice(me.id)
        if _saved:
            current_voice = _saved
        text = "🎙️ **Mevcut Sesler**\n\n"
        
        text += "**🇹🇷 Türkçe:**\n"
        for name, code in TURKISH_VOICES.items():
            marker = " ✓" if code == current_voice else ""
            text += f"• `{name}` - {code}{marker}\n"
        
        text += "\n**🌍 Diğer Diller:**\n"
        for name, code in OTHER_VOICES.items():
            marker = " ✓" if code == current_voice else ""
            text += f"• `{name}` - {code}{marker}\n"
        
        text += f"\n**Şu anki ses:** `{current_voice}`"
        text += "\n\n💡 Değiştirmek için: `.sesayar <isim>`"
        
        await event.edit(text)
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.sesayar\s+(\S+)$'))
    async def set_voice(event):
        global current_voice
        
        voice_input = event.pattern_match.group(1).lower()
        
        if voice_input in ALL_VOICES:
            current_voice = ALL_VOICES[voice_input]
        elif voice_input.count("-") >= 2:
            # Direkt ses kodu girilmiş olabilir (örn: tr-TR-AhmetNeural)
            current_voice = voice_input
        else:
            await event.edit(f"❌ Ses bulunamadı: `{voice_input}`\n\n💡 Mevcut sesler için: `.sesler`")
            return

        # Başarılı: kalıcı kaydet + bildir
        me = await event.client.get_me()
        _save_voice(me.id, current_voice)
        await event.edit(f"✅ Ses değiştirildi: `{current_voice}` (kalıcı)")
