# 🎨 YENİ PLUGIN — Çıkartma (`plugins/stic.py`)

Yanıtlanan **resmi / videoyu / GIF'i** otomatik olarak Telegram çıkartmasına
çevirir. Komutlar: **`.stic`** ve **`.sticker`**

---

## Kullanım

| Komut | Ne yapar |
|---|---|
| `.stic` (bir medyayı yanıtla) | Medyayı çıkartmaya çevirip gönderir |
| `.stic 😎` | Çıkartmayı seçtiğin emoji ile oluşturur (varsayılan 🔥) |
| `.sticker` | `.stic` ile aynısı |

Resim/video gönderirken açıklamaya `.stic` yazmak da çalışır (yanıt şart değil).

---

## Otomatik yapılanlar

| Konu | Davranış |
|---|---|
| **Boyut** | Bir kenar **tam 512px**, diğeri oranı korur ve çift sayıya yuvarlanır |
| **Süre** | En fazla **2.9 sn** (Telegram sınırı 3 sn — güvenlik payı bırakıldı) |
| **3 sn üstü video** | Otomatik **hızlandırılıp** 3 saniyeye indirilir + kullanıcı bilgilendirilir |
| **10 sn üstü video** | 10x+ hızlandırma izlenemez olacağı için **ilk 3 saniye** alınır + bilgilendirme |
| **Ses** | Tamamen kaldırılır (Telegram video çıkartmada ses kabul etmez) |
| **FPS** | 30'a düşürülür |
| **Format** | Video/GIF → **WEBM (VP9)**, Resim → **WEBP** |
| **Şeffaflık** | Alfa kanalı varsa korunur (`yuva420p`) |
| **Dosya boyutu** | Video ≤256 KB, resim ≤512 KB — **ölçüme dayalı** olarak otomatik optimize edilir |

---

## Performans

- **İki aşamalı dönüştürme:** önce hızlı bir ara dosyaya küçültülür, sonra VP9
  kodlanır. Böylece boyut ayarı için yeniden deneme gerekirse dev kaynak dosya
  tekrar tekrar çözülmez.
- **Ölçüme dayalı bitrate:** ilk denemede tutmazsa, gerçek çıktı boyutuna göre
  bir sonraki bitrate hesaplanır (sabit merdivene göre çok daha hızlı yakınsar).
- **Ölçüler önce Telegram meta verisinden** okunur — çoğu durumda `ffprobe`
  çalıştırmaya bile gerek kalmaz.
- Gerçek dünya testleri: **~0.5 – 5 saniye**.

## Sağlamlık (bug/donma koruması)

- ffmpeg **asenkron** çalıştırılır (`asyncio.create_subprocess_exec`) — bot
  hiçbir zaman kilitlenmez. Bloklayan `subprocess.run` **kullanılmaz**.
- Her ffmpeg çağrısında **timeout**, tüm iş için ayrıca **genel timeout** var.
- **Kullanıcı başına kilit:** aynı kişi üst üste `.stic` yazarsa iş çoğalmaz.
- **Global eşzamanlılık sınırı** (aynı anda en fazla 2 ffmpeg) — sunucu koruması.
- Geçici dosyalar **her durumda** (`finally`) silinir.
- `cleanup_user_data()` — plugin kapatılınca kilit ve geçici klasör temizlenir.
- **ffmpeg bulucu:** PATH → `imageio-ffmpeg` → yaygın Windows yolları
  (`C:\ffmpeg\bin`, bot klasörü `bin/` vb.) sırayla denenir.
- `ffprobe` yoksa bile çalışır: ölçüler Telegram meta verisinden alınır, o da
  yoksa oranı koruyan otomatik ölçek ifadesi kullanılır.

## Hata mesajları (hepsi Türkçe ve net)

| Durum | Mesaj |
|---|---|
| Grupta çıkartma kapalı | Uyarı verilir **+ çıkartma Kayıtlı Mesajlar'a gönderilir** |
| Grupta medya kapalı / yazma yasak / susturulmuş | Duruma özel uyarı + Kayıtlı Mesajlar'a gönderim |
| Yavaş mod / flood limiti | Kaç saniye beklemesi gerektiği söylenir |
| Yanıt yok | Kullanım örneği gösterilir |
| Ses dosyası / desteklenmeyen medya | Neyin yanıtlanması gerektiği söylenir |
| Zaten çıkartma | Bilgilendirilir |
| Dosya > 60 MB | İndirmeye kalkmadan uyarır, 3-5 sn'lik video ister |
| ffmpeg yok | Kurulum gerektiği açıkça söylenir |
| Boyut sığdırılamadı / zaman aşımı / bozuk dosya | Ayrı ayrı, anlaşılır mesajlar |

---

## 🔴 Kritik gönderim düzeltmesi (Telethon `1x1` yer tutucu hatası)

Telethon, `.webm` dosyasının ölçülerini kendi başına okuyamadığında
(`hachoir` kurulu değilse) otomatik olarak
**`DocumentAttributeVideo(w=1, h=1, duration=0)`** yer tutucusu ekliyor.
Bu şekilde gönderilen video çıkartma karşı tarafta **bozuk görünür / oynamaz**.

**Çözüm:** Dönüştürme bitince çıktı dosyası ölçülüp, `DocumentAttributeVideo`
**gerçek genişlik / yükseklik / süre** ile **açıkça** gönderiliyor; böylece
Telethon'un yer tutucusu eziliyor.

Doğrulandı — gönderilen attribute'lar üretilen dosyayla birebir eşleşiyor:

| Kaynak | Gönderilen attribute | Gerçek dosya | Sonuç |
|---|---|---|---|
| long.mp4 | 512x288 / 2.90 sn | 512x288 | ✅ |
| portrait.mp4 | 288x512 / 2.00 sn | 288x512 | ✅ |
| wide.mp4 | 512x26 / 2.00 sn | 512x26 | ✅ |
| anim.gif | 512x384 / 2.90 sn | 512x384 | ✅ |

Ayrıca doğrulandı: sticker attribute'u korunuyor, dosya **GIF olarak
işaretlenmiyor** (`DocumentAttributeAnimated` eklenmiyor), mime `video/webm`.

---

## Gereksinim

Video ve GIF dönüştürme için sistemde **ffmpeg** kurulu olmalıdır.
Kurulu değilse `requirements.txt`'e eklenen `imageio-ffmpeg` paketi yedek
olarak devreye girer (yalnız ffmpeg sağlar, ffprobe sağlamaz — plugin bu
durumu da destekler).

## Doğrulama (yapılan testler)

- 512px kenar hesabı: 8 uç durum (aşırı geniş, aşırı dar, minik, sıfır) ✅
- Video: hızlandırma, kırpma, dikey, GIF, şeffaf, 0.4 sn kısa, aşırı geniş ✅
- Her çıktıda: bir kenar tam 512, süre < 3 sn, ses **yok**, VP9, boyut sınır altı ✅
- Resim: büyük foto ve 50x50 küçük görsel → 512x512 WEBP ✅
- `ffprobe` yokmuş gibi (ölçü bilinmeden) tüm dönüşümler ✅
- En kötü senaryo (saf gürültü, 197 MB): boyut yine sınır altına indirildi ✅
- Komut çakışması: proje genelinde **yok** (64 komut) ✅
- 12 pluginin tamamı birlikte yükleniyor, `stic` tam 1 handler, çift kayıt yok ✅
