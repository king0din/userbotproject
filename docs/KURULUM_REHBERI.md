# 🚀 Kurulum Rehberi (Sıfırdan, Adım Adım)

Bu rehber, daha önce hiç bot kurmamış biri için yazıldı. Komutları **sırayla**
kopyala-yapıştır yap, yeter. Takıldığın yerde "Sık Sorulanlar" bölümüne bak.

---

## 0. Neye ihtiyacın var?

| Gereken | Nereden alınır | Ücretli mi? |
|---------|----------------|-------------|
| Bir bilgisayar veya sunucu (VPS) | — | Sunucu ücretli olabilir |
| Python 3.10 veya üstü | python.org | Ücretsiz |
| Bir Telegram hesabı | — | Ücretsiz |
| API_ID + API_HASH | my.telegram.org | Ücretsiz |
| BOT_TOKEN | Telegram'da @BotFather | Ücretsiz |
| (İsteğe bağlı) MongoDB | mongodb.com/atlas | Ücretsiz katman var |

> **MongoDB zorunlu değil.** Kurmaz isen bot yerel dosyalarla (`data/` klasörü) çalışır.
> Yeni başlıyorsan MongoDB'yi atla, sonra eklersin.

---

## 1. Anahtarları topla

### 1.1. API_ID ve API_HASH (Telegram uygulama anahtarı)
1. https://my.telegram.org adresine gir, Telegram numaranla giriş yap.
2. **API development tools**'a tıkla.
3. Bir uygulama oluştur (isim ne olursa olur, ör. "mybot").
4. Sana **App api_id** (sayı) ve **App api_hash** (uzun bir metin) verecek. İkisini de kaydet.

### 1.2. BOT_TOKEN (botun kimliği)
1. Telegram'da **@BotFather**'a yaz.
2. `/newbot` gönder, isim ve kullanıcı adı ver (kullanıcı adı `_bot` ile bitmeli).
3. Sana `123456:ABC-DEF...` gibi bir **token** verecek. Kaydet.

### 1.3. OWNER_ID (senin Telegram ID'n)
1. Telegram'da **@userinfobot**'a yaz.
2. Sana bir **Id** sayısı verecek (ör. `987654321`). Bu senin sahip ID'n. Kaydet.

---

## 2. Projeyi indir ve hazırla

```bash
# 1) Projeyi indir
git clone https://github.com/KingOdi/userbotproject.git
cd userbotproject

# 2) (Önerilir) Sanal ortam oluştur — sistemin Python'unu kirletmemek için
python3 -m venv venv
source venv/bin/activate      # Windows'ta:  venv\Scripts\activate

# 3) Gereksinimleri kur
pip install -r requirements.txt
```

> **Hata mı aldın?** `pip` bulunamıyorsa `python3 -m pip install -r requirements.txt` dene.

---

## 3. Ayar dosyasını (.env) doldur

```bash
# Örnek dosyayı kopyala
cp .env.example .env
```

Şimdi `.env` dosyasını bir metin editörüyle aç (`nano .env` veya herhangi bir editör) ve
**sadece şu satırları** doldur:

```ini
API_ID=12345678                 # 1.1'de aldığın sayı
API_HASH=buraya_api_hash        # 1.1'de aldığın metin
BOT_TOKEN=123456:ABCabc...      # 1.2'de aldığın token
OWNER_ID=987654321              # 1.3'te aldığın ID
OWNER_USERNAME=kullanici_adin   # @ olmadan

# Aşağıdakiler İSTEĞE BAĞLI — boş bırakabilirsin:
MONGO_URI=                      # MongoDB kullanmıyorsan boş bırak
LOG_CHANNEL=                    # Log kanalı yoksa boş bırak
```

> 🔒 **Çok önemli:** `.env` dosyasını **kimseye gönderme**, GitHub'a **yükleme**.
> İçinde botunun ve hesabının şifreleri var. (`.gitignore` zaten onu gizler.)

---

## 4. Botu başlat

```bash
python main.py
```

Her şey doğruysa şuna benzer satırlar görmelisin:

```
[KingTG] 🤖 KingTG UserBot Service v2.1.0
[KingTG] ✅ Bot bağlandı: @senin_botun
[KingTG] ✅ Bot hazır!
```

Artık Telegram'da botuna `/start` yazıp deneyebilirsin. 🎉

---

## 5. 7/24 Çalışır Halde Tutmak (sunucuda)

Bilgisayarını/SSH'ı kapatınca bot durur. Sürekli çalışsın istiyorsan:

**Kolay yol — `screen`:**
```bash
screen -S bot          # yeni bir oturum aç
python main.py         # botu başlat
# Ctrl+A sonra D ile oturumdan çık (bot çalışmaya devam eder)
# Geri dönmek için:  screen -r bot
```

**Daha sağlam yol — `systemd` servisi** (Linux sunucu): İleri seviye; istersen ayrı
bir rehber hazırlanabilir.

---

## 6. Sık Sorulanlar / Hata Çözümleri

**❓ "API_ID, API_HASH veya BOT_TOKEN eksik!" yazıyor.**
→ `.env` dosyası ya yok ya da boş. 3. adımı tekrar yap. Dosya adının tam `.env` olduğundan
emin ol (`.env.txt` değil).

**❓ "ModuleNotFoundError: No module named 'telethon'"**
→ Gereksinimler kurulmamış ya da sanal ortam aktif değil.
`source venv/bin/activate` sonra `pip install -r requirements.txt`.

**❓ MongoDB bağlanmıyor.**
→ Sorun değil! "⚠️ MongoDB bağlantısı başarısız, yerel dosya sistemi kullanılacak" mesajını
görürsen bot yine çalışır. MongoDB'yi tamamen kullanmak istemiyorsan `MONGO_URI`'yi boş bırak.

**❓ Bot açılıyor ama `/start`'a cevap vermiyor.**
→ Doğru bota mı yazıyorsun? `@BotFather`'dan aldığın token hangi bota aitse o bota yaz.

**❓ Plugin nasıl eklerim?**
→ `PLUGIN_REHBERI.md` dosyasına bak. Kısaca: plugin dosyasını bota gönderip ona yanıt olarak
`/addplugin` yazarsın (sahip/sudo iseniz).

**❓ "Doğrulama kodu çalışmıyor."**
→ Kodu **rakamların arasına boşluk koyarak** gir: `1 2 3 4 5`. Bu, Telegram'ın kodu
"paylaşıldı" sanıp iptal etmesini önler. (Bot zaten bunu söylüyor.)

---

## 7. Güvenlik Hatırlatması (kısa)

- `.env`, `*.session` ve `data/` klasörünü **asla** paylaşma/yükleme.
- Plugin'leri yalnızca **güvendiğin** kaynaklardan ekle — plugin'ler sunucunda kod çalıştırır.
- Bir yerde token'ın sızdıysa @BotFather'dan **hemen revoke** et.
