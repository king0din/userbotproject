# 🤖 KingTG UserBot Service

Telegram kullanıcıları için kolay userbot kurulum ve plugin yönetim servisi.

## ✨ Özellikler

- **Kolay Kurulum**: Telegram kullanıcıları 3 farklı yöntemle userbot kurabilir
  - 📱 Telefon numarası + doğrulama kodu
  - 📄 Telethon Session String
  - 📄 Pyrogram Session String

- **Plugin Sistemi**: 
  - Merkezi plugin yönetimi
  - Genel ve özel plugin desteği
  - Kullanıcı bazlı erişim kontrolü
  - Plugin kısıtlama sistemi

- **Oturum Yönetimi**:
  - "Beni Hatırla" özelliği
  - Otomatik oturum sonlandırma tespiti
  - Güvenli session saklama

- **Yönetim Paneli**:
  - Bot modu (Genel/Özel)
  - Bakım modu
  - Ban/Unban sistemi
  - Sudo yönetimi
  - İstatistikler ve loglar

- **Hibrit Veritabanı**:
  - MongoDB + Yerel dosya sistemi
  - Otomatik yedekleme ve senkronizasyon

## 📦 Kurulum

### 1. Repoyu klonlayın

```bash
git clone https://github.com/KingOdi/KingTG-UserBot-Service.git
cd KingTG-UserBot-Service
```

### 2. Gereksinimleri yükleyin

```bash
pip install -r requirements.txt
```

### 3. `.env` dosyasını oluşturun

```bash
cp .env.example .env
nano .env  # Değerleri doldurun
```

### 4. Botu başlatın

```bash
python main.py
```

## ⚙️ Yapılandırma

`.env` dosyasında aşağıdaki değişkenleri ayarlayın:

| Değişken | Açıklama |
|----------|----------|
| `API_ID` | Telegram API ID (my.telegram.org) |
| `API_HASH` | Telegram API Hash |
| `BOT_TOKEN` | Bot Token (@BotFather) |
| `OWNER_ID` | Bot sahibinin Telegram ID'si |
| `OWNER_USERNAME` | Bot sahibinin kullanıcı adı |
| `MONGO_URI` | MongoDB bağlantı dizesi |
| `LOG_CHANNEL` | Log kanalı/grubu ID'si |

## 📱 Kullanıcı Komutları

| Komut | Açıklama |
|-------|----------|
| `/start` | Ana menü |
| `/plugins` | Plugin listesi |
| `/pactive <isim>` | Plugin aktif et |
| `/pinactive <isim>` | Plugin deaktif et |

## 👑 Admin Komutları

| Komut | Açıklama |
|-------|----------|
| `/addplugin` | Plugin ekle (dosyaya yanıt verin) |
| `/delplugin <isim>` | Plugin sil |
| `/setpublic <isim>` | Plugin'i genel yap |
| `/setprivate <isim>` | Plugin'i özel yap |
| `/grantplugin <isim> <id>` | Plugin erişimi ver |
| `/revokeplugin <isim> <id>` | Plugin erişimi al |
| `/restrictplugin <isim> <id>` | Kullanıcıyı kısıtla |
| `/unrestrictplugin <isim> <id>` | Kısıtlamayı kaldır |
| `/ban <id> [sebep]` | Kullanıcı banla |
| `/unban <id>` | Ban kaldır |
| `/addsudo <id>` | Sudo ekle |
| `/delsudo <id>` | Sudo kaldır |
| `/broadcast` | Duyuru gönder (mesaja yanıt) |

## 📁 Proje Yapısı

```
userbot_service/
├── main.py              # Ana bot dosyası
├── config.py            # Yapılandırma
├── requirements.txt     # Python gereksinimleri
├── .env.example         # Örnek ortam değişkenleri
├── database/
│   ├── __init__.py      # Birleşik DB arayüzü
│   ├── mongo.py         # MongoDB işlemleri
│   └── local.py         # Yerel dosya işlemleri
├── handlers/
│   ├── __init__.py
│   ├── user.py          # Kullanıcı handler'ları
│   └── admin.py         # Admin handler'ları
├── userbot/
│   ├── __init__.py
│   ├── manager.py       # Userbot yönetimi
│   └── plugins.py       # Plugin sistemi
├── utils/
│   ├── __init__.py
│   └── helpers.py       # Yardımcı fonksiyonlar
├── plugins/             # Plugin dosyaları
├── sessions/            # Session dosyaları
└── data/                # JSON veri dosyaları
```

## 🔌 Plugin Yazma

Plugin dosyası örneği:

```python
# description: Örnek plugin
# author: @KingOdi
# version: 1.0.0

from telethon import events

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ornek$'))
    async def ornek_handler(event):
        await event.edit("✅ Örnek plugin çalışıyor!")
```

## 🔒 Güvenlik

- Session'lar şifrelenmiş olarak saklanır
- Her kullanıcı sadece kendi hesabını bağlayabilir
- Oturum sonlandırma otomatik tespit edilir
- Ban ve kısıtlama sistemi

## 📊 Sürüm

- **v2.0.0** - İlk çok kullanıcılı sürüm

## 👨‍💻 Geliştirici

- Telegram: [@KingOdi](https://t.me/KingOdi)

## 📄 Lisans

MIT License
