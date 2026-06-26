# 🔌 Plugin Yazma Rehberi (Acemiler İçin)

Bu rehber, hiç plugin yazmamış biri için. Sonunda kendi komutunu yazıp bota
ekleyebileceksin.

---

## 1. Plugin nedir?

Plugin = userbot'una **yeni bir komut** ekleyen küçük bir Python dosyası.
Örneğin `.selam` yazınca "Merhaba" cevabı veren bir dosya bir plugin'dir.

Her plugin **tek bir `.py` dosyasıdır** ve `plugins/` klasöründe durur.

---

## 2. En basit plugin

Yeni bir dosya aç: `plugins/selam.py`

```python
# description: Selam veren basit plugin
# author: @sen
# version: 1.0.0

from telethon import events

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.selam$'))
    async def selam(event):
        await event.edit("👋 Merhaba!")

def unregister():
    pass
```

Bu kadar. Artık `.selam` yazınca bot "👋 Merhaba!" der.

> Hazır, yorumlu bir başlangıç dosyası için: **`_sablon.py`** kopyala.

---

## 3. Üç altın kural

1. **Üstteki 3 satırı silme:**
   ```
   # description: ...
   # author: ...
   # version: ...
   ```
   Bot bunları okuyup plugin listesinde gösterir.

2. **Tüm komutlarını `def register(client):` içine yaz.**
   `client` = o kullanıcının kendi hesabı. Bot her kullanıcı için bunu çağırır.

3. **`outgoing=True` koy.** Bu, komutun *sadece sen* yazınca çalışmasını sağlar.
   (`incoming=True` yaparsan başkalarının mesajlarına da tepki verir — dikkatli kullan.)

---

## 4. Sık kullanılan kalıplar

### Argüman almak ( `.komut bir şey` )
```python
@client.on(events.NewMessage(outgoing=True, pattern=r'^\.tekrarla (.+)$'))
async def tekrarla(event):
    metin = event.pattern_match.group(1)   # komuttan sonraki kısım
    await event.edit(metin)
```

### Bir mesaja yanıt vererek çalışmak
```python
@client.on(events.NewMessage(outgoing=True, pattern=r'^\.kim$'))
async def kim(event):
    if not event.reply_to_msg_id:
        await event.edit("Bir mesaja yanıt ver.")
        return
    msg = await event.get_reply_message()
    await event.edit(f"Gönderen ID: `{msg.sender_id}`")
```

### Mesaj atıp sonra düzenlemek (ör. "yükleniyor...")
```python
@client.on(events.NewMessage(outgoing=True, pattern=r'^\.bekle$'))
async def bekle(event):
    import asyncio
    await event.edit("⏳ Bekleniyor...")
    await asyncio.sleep(2)
    await event.edit("✅ Bitti!")
```

### `event.edit` vs `event.reply`
- `event.edit(...)` → **senin yazdığın** mesajı değiştirir (komut kaybolur, temiz görünür).
- `event.reply(...)` → **yeni bir mesaj** olarak cevap atar.

---

## 5. Plugin'i bota nasıl eklerim?

İki yol var:

**A) Dosyayı doğrudan koymak (geliştirici):**
1. `.py` dosyanı `plugins/` klasörüne kopyala.
2. Botu yeniden başlat ya da `/addplugin` ile kaydet.

**B) Telegram üzerinden (sahip/sudo):**
1. Plugin `.py` dosyasını bota **gönder**.
2. O dosyaya **yanıt vererek** `/addplugin` yaz.
3. Bot komutları kontrol eder ve plugin'i kaydeder.

Kullanıcı tarafında aktifleştirme:
- `/plugins` → mevcut plugin'leri listeler.
- `/pactive <isim>` → plugin'i kendine aktif eder.
- `/pinactive <isim>` → kapatır.

---

## 6. Hata yapmamak için

| Yapma ❌ | Yap ✅ |
|---------|--------|
| `except: pass` (hatayı yutar) | `except Exception as e: await event.edit(f"Hata: {e}")` |
| `global X` deyip X'i hiç atamamak | Ya gerçekten ata, ya `global`'i sil |
| `pattern="^.komut"` (ham değil) | `pattern=r'^\.komut$'` (başına `r`, noktayı `\.` yap) |
| Aynı komutu iki plugin'de tanımlamak | Komut adının benzersiz olduğundan emin ol |

> Not: `pattern=r'^\.komut$'` içindeki `\.` "gerçek nokta" demektir. Sadece `.` yazarsan
> regex'te "herhangi bir karakter" anlamına gelir ve beklenmedik eşleşmeler olur.

---

## 7. Eski plugin'ler (uyumluluk modu)

Bu projede bazı eski plugin'ler farklı bir stille yazılmış:

```python
from userbot_compat.events import register

@register(outgoing=True, pattern="^.eski")
async def eski(event):
    await event.edit("Eski stil")
```

Bu stil **çalışır** (uyumluluk katmanı sayesinde) ama **yeni plugin yazarken
kullanma.** Yukarıdaki `def register(client):` stiline sadık kal — hem daha net hem
çok kullanıcıda daha güvenli.

> Teknik sebep: eski stil tek bir global bağlantı kullanır; aynı anda birden çok
> kullanıcı plugin açarsa karışabilir. Yeni stil her kullanıcıya kendi `client`'ını verir.

---

## 8. Özet

1. `_sablon.py`'yi kopyala.
2. Üstteki `description/author/version`'ı doldur.
3. Komutlarını `register(client)` içine, `@client.on(...)` ile yaz.
4. `plugins/`'e koy, `/addplugin` ile ekle, `/pactive` ile aç.

Bu kadar. İlk plugin'in 5 dakikada hazır. 🎉
