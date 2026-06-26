# 🔍 KingTG UserBot Service — Analiz ve Yol Haritası

> Bu belge, projenin baştan sona taranmasıyla çıkarılmış **bulguları**, **hataları** ve
> **adım adım iyileştirme planını** içerir. Hedef: kodu daha **sağlam**, daha **anlaşılır**
> ve acemiler için daha **kolay** hale getirmek.

İncelenen sürüm: **v2.1.0** · Toplam: **~13.600 satır Python**, 9 kayıtlı plugin, 154 kullanıcı kaydı.

---

## 0. ÖNCE BUNU OKU — 🚨 ACİL GÜVENLİK UYARISI

Bu konu kodla ilgili değil ama **her şeyden önce gelir**. Paylaştığın zip dosyasının içinde
şu **gerçek/canlı** dosyalar vardı:

| Dosya | İçinde ne var | Risk |
|-------|---------------|------|
| `.env` | Gerçek `API_HASH`, `BOT_TOKEN`, `MONGO_URI` | Botun tam kontrolü + veritabanı erişimi |
| `.env.txt` | `.env`'in eski bir kopyası (gizlenmemiş!) | Aynı sırlar, üstelik `.gitignore` bunu kapsamıyor |
| `bot_session.session` | Botun giriş yapmış oturumu (36 KB) | Bu dosyayla biri botu **token'sız** çalıştırabilir |
| `data/users.json` | **154 gerçek kullanıcının** Telegram session string'leri | Bu string'lerle o kişilerin **Telegram hesaplarına girilebilir** |

**Yani:** Bu zip'i bana (ya da herhangi birine) gönderdiğinde, kendi botunun ve 154 kişinin
hesabının anahtarlarını da göndermiş oldun.

### Hemen yapman gerekenler
1. **BOT_TOKEN'ı sıfırla:** @BotFather → botun → *Revoke current token*.
2. **API_HASH'i değiştir:** my.telegram.org → uygulamanı sil/yeniden oluştur (mümkünse).
3. **MongoDB şifresini değiştir:** Atlas panelinden kullanıcının şifresini resetle.
4. **`bot_session.session` dosyasını sil**, bot yeni token'la kendi oturumunu açsın.
5. Bundan sonra kod paylaşırken **asla** `.env`, `*.session`, `data/` klasörünü ekleme.
   (Bu repoda `temizle.sh` betiği bunları otomatik temizliyor — aşağıda.)

### Bonus: README yanlış bilgi veriyor
README'de *"Session'lar şifrelenmiş olarak saklanır"* yazıyor. **Saklanmıyor.**
`data/users.json` içinde `session_data` alanı **düz metin** olarak duruyor. Bu cümle
ya düzeltilmeli ya da gerçekten şifreleme eklenmeli (bkz. Bölüm 4, madde S2).

---

## 1. Genel Değerlendirme (özet)

**İyi yanlar** (bunlar gerçekten iyi, korunmalı):
- `config.py` temiz: tüm sırlar ortam değişkeninden okunuyor, kod içine gömülmemiş. ✅
- `main.py` okunabilir ve düzenli; başlatma akışı net. ✅
- `database/__init__.py` birleşik bir arayüz sunuyor (MongoDB + yerel dosya). Mantık doğru. ✅
- Çok kullanıcılı mimari fikri sağlam: merkezi bot + kullanıcı başına userbot + plugin sistemi.

**Temel sorunlar** (projeyi "zor ve anlaşılmaz" yapan asıl şeyler):
1. **Dev dosyalar / "tanrı fonksiyonları":** `handlers/admin.py` tek bir 2185 satırlık fonksiyon.
2. **Hatalar sessizce yutuluyor:** 137 adet `except:` + 126 adet `except Exception` → bir şey
   bozulduğunda *neden* bozulduğu görünmüyor.
3. **Gerçek loglama yok:** 125 adet `print()`. Log seviyesi, zaman damgası, dosyaya yazma yok.
4. **Ölü kod ve çöp dosyalar:** Kullanılmayan `manager.py`, yüklenmeyen `.patched` dosyaları,
   tekrarlı `.env.txt`.
5. **İki farklı plugin yazım stili:** Acemi hangisini kullanacağını bilemiyor.
6. **Test yok:** Tek bir otomatik test bile yok; her değişiklik "elle dene ve gör".
7. **Birkaç gerçek bug** (aşağıda Bölüm 3).

---

## 2. Dosya/Klasör Sağlık Tablosu

| Dosya | Satır | Durum | Not |
|-------|------:|-------|-----|
| `handlers/admin.py` | 2185 | 🔴 Bölünmeli | Tek fonksiyonda ~75 iç fonksiyon |
| `plugins/tag.py` | 1139 | 🟠 Büyük | 31 `except:`, 4 gereksiz `global` |
| `handlers/user.py` | 1079 | 🟠 Bölünebilir | Login + plugin + yardım hepsi bir arada |
| `userbot/smart_manager.py` | 1014 | 🟡 Kabul edilir | İyi yapılı ama büyük |
| `plugins/q.py` | 968 | 🟠 Büyük | Çok sayıda kullanılmayan değişken |
| `plugins/otomsg.py` | 900 | 🟠 Büyük | — |
| `userbot/plugins.py` | 874 | 🟡 Kritik çekirdek | `exec()` + import yamalama; dikkatli olunmalı |
| `userbot/manager.py` | 397 | 🔴 **ÖLÜ KOD** | Hiçbir yer import etmiyor → **silinebilir** |
| `plugins/*.patched` | — | 🔴 **ÖLÜ KOD** | `.py` olmadığı için hiç yüklenmiyor |
| `.env.txt` | — | 🔴 **SİL** | Sır içeren gereksiz kopya |
| `tests/` | yok | 🔴 Eksik | Hiç test yok |
| `.env.example` | var | ✅ İyi | Mevcut |
| `config.py` | 204 | ✅ İyi | Temiz |
| `main.py` | 300 | ✅ İyi | Temiz |

---

## 3. Somut Hatalar (gerçek bug'lar)

Bunlar "stil" değil, gerçekten yanlış davranan ya da davranabilecek şeyler:

### 🔴 B1 — Çoklu kullanıcıda plugin'ler yanlış hesaba bağlanabilir
**Yer:** `userbot_compat/events.py` (global `_client`) + `userbot/plugins.py` `activate_plugin`.
Eski stil plugin'lerde `@register(...)` dekoratörü, modül seviyesindeki **tek bir global**
`_client`'ı okuyor. Plugin yüklenirken `compat_events.set_client(client)` bu global'i
ayarlıyor. İki kullanıcı **aynı anda** plugin aktive ederse, global `_client` üzerine yazılır
ve bir kullanıcının handler'ı diğerinin hesabına bağlanabilir.
**Çözüm:** Plugin yüklemeyi kullanıcı başına bir kilit (lock) altına almak (kısmî çözüm),
uzun vadede ise eski stil dekoratörü tamamen `register(client)` modeline taşımak.

### 🔴 B2 — `btn` ismi döngü değişkeniyle eziliyor
**Yer:** `handlers/admin.py:1304` ve `1352`.
Üstte `import ... as btn` (satır 21) var ama `for btn in ...` döngüsü bu ismi eziyor.
Döngüden sonra `btn.inline(...)` gibi bir çağrı olursa `AttributeError` ile çöker.
**Çözüm:** Döngü değişkenini yeniden adlandır (`for b in ...`).

### 🟠 B3 — `global ... is never assigned` (niyetlenen güncelleme gerçekleşmiyor)
**Yerler:** `plugins/afk.py:115,209` (`ORIGINAL_PROFILE`), `plugins/tag.py` (7 yerde
`tag_data`, `tag_active`, `blocked_users`), `plugins/start.py` (`_handlers`),
`plugins/ses.py:183` (`current_voice`).
Fonksiyon içinde `global X` deniyor ama `X` hiç yeniden atanmıyor. Eğer amaç değeri
güncellemekse bu **çalışmıyor** (yalnızca yerinde değişiklik — `liste.append()` gibi — çalışır;
`X = yeni_değer` çalışmaz çünkü kod aslında atama yapmıyor). En azından kafa karışıklığı,
kötü ihtimalle sessiz mantık hatası.
**Çözüm:** Ya gerçekten ata, ya da gereksiz `global` satırını sil.

### 🟡 B4 — Geçersiz kaçış dizisi (deprecation)
**Yer:** `handlers/user.py:586,672` → `pattern=b"plugins_page_(\d+)"`.
`\d` ham (raw) byte değil; Python `SyntaxWarning` veriyor ve gelecekte hata olacak.
**Çözüm:** `rb"plugins_page_(\d+)"` yap.

### 🟡 B5 — Hesaplanıp kullanılmayan değişkenler
**Yer:** `main.py:246` (`uptime`), `plugins/q.py` (`resp1/resp2/error_detail`), vb.
Çökme yapmaz ama "burada bir şey eksik kalmış" sinyali; çoğu, yarım kalmış mantık.

> Bunların **B1–B4'ü** birlikte gelen `temizle.sh` / yama notlarında ele alınıyor.

---

## 4. İyileştirme Planı — 3 Seviye

Aşağıdaki planı **seviye seviye** uygulayabilirsin. Her seviye kendi başına projeyi
iyileştirir; istemediğin yerde durabilirsin.

### 🟢 SEVİYE 1 — "Temel temizlik" (risk düşük, etki yüksek)
> Davranışı değiştirmeden kodu temizler ve hataları görünür yapar. **Önce bunu yap.**

- **T1. Ölü kodu sil:** `userbot/manager.py`, `plugins/*.patched`, tüm `__pycache__/`,
  `.env.txt`, `.restart_info`. → `temizle.sh` bunu yapar.
- **T2. `.gitignore`'u sağlamlaştır:** `.env.txt`, `.env.*`, `*.session-journal`,
  `_IYILESTIRME` dışı geçici dosyalar. (Düzeltilmiş sürüm bu pakette.)
- **T3. Gerçek loglama ekle:** `utils/logger.py` (bu pakette). Sonra `print(...)` →
  `log.info(...)` / `log.error(...)` dönüşümü. Tek seferde değil, dosya dosya yapılabilir.
- **T4. `except: pass` avı:** En azından `except Exception as e: log.error(..., exc_info=e)`
  yap ki hata kaybolmasın. (137 + 126 yer var; öncelik: `userbot/`, `handlers/`.)
- **T5. README'deki yanlış "şifreli session" cümlesini düzelt.**

**Tahmini kazanç:** Bir şey bozulduğunda artık *nerede* ve *neden* bozulduğunu göreceksin.

### 🟡 SEVİYE 2 — "Yapısal düzen" (orta risk, çok yüksek etki)
> "Anlaşılır değil" şikâyetinin asıl ilacı. Dev dosyaları parçalara böler.

- **O1. `handlers/admin.py`'ı böl.** Konuya göre dosyalara ayır:
  ```
  handlers/admin/
  ├── __init__.py        # register_admin_handlers() — alt modülleri çağırır
  ├── settings.py        # ayarlar menüsü, mod/bakım toggle
  ├── users.py           # kullanıcı listesi, ban/sudo butonları
  ├── plugins_admin.py   # addplugin/delplugin/get/setpublic...
  ├── post.py            # plugin kanalı post oluşturucu (en karmaşık parça)
  └── system.py          # stats, update, restart, broadcast, logs
  ```
- **O2. `handlers/user.py`'ı böl:** `login.py`, `plugins_user.py`, `help.py`, `menu.py`.
- **O3. Sabit metinleri ayır:** Tüm mesaj/buton metinleri zaten `config.py`'de ama hâlâ
  kod içinde gömülü çok metin var. Hepsini `messages.py`/`strings.py`'ye topla → çeviri
  ve düzenleme kolaylaşır.
- **O4. Plugin yazımını teke indir:** Tek resmî stil = `register(client)` (bkz.
  `PLUGIN_REHBERI.md` ve `plugins/_sablon.py`). Eski `@register` stilini sadece
  "uyumluluk modu" olarak belgele.

**Tahmini kazanç:** Yeni biri projeye baktığında "bu dosya neyi yapıyor" sorusunu
dosya adından cevaplayabilir.

### 🔴 SEVİYE 3 — "Kökten modernizasyon" (yüksek emek, uzun vadeli)
> Sadece uzun ömürlü/ciddi bir servis hedefliyorsan.

- **K1. Pydantic + `Settings` sınıfı** ile config doğrulama (eksik env'de net hata).
- **K2. Veri katmanını sadeleştir:** "Çift yazma" (hem Mongo hem dosya) yerine tek
  kaynak + isteğe bağlı yedek. Şu an iki kaynak çakışırsa hangisi doğru belirsiz.
- **K3. Session şifreleme (S2):** `data/users.json` içindeki session'ları `cryptography`
  (Fernet) ile şifrele; anahtar `.env`'de. README'nin sözü ancak böyle doğru olur.
- **K4. Plugin güvenlik sınırı:** Plugin'ler `exec()` ile **sınırsız** kod çalıştırıyor
  (`run_command` ile shell dahil). Çok kullanıcılı bir serviste bu, bir kullanıcının
  sunucuyu ele geçirmesi demek. En azından plugin'leri yalnızca güvendiğin kişilerden
  al, idealde sandbox/izin sistemi düşün.
- **K5. Testler:** `pytest` ile en azından veri katmanı ve yardımcılar için testler.
- **K6. Tip ipuçları + `mypy`/`ruff`** CI'da.

---

## 5. Önerilen Hedef Klasör Yapısı (Seviye 2 sonrası)

```
userbotproject/
├── main.py
├── config.py
├── messages.py              # YENİ: tüm metinler burada
├── requirements.txt
├── .env.example
├── .gitignore               # düzeltilmiş
├── database/                # (mevcut, iyi)
├── handlers/
│   ├── admin/               # admin.py'dan bölündü
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── users.py
│   │   ├── plugins_admin.py
│   │   ├── post.py
│   │   └── system.py
│   └── user/                # user.py'dan bölündü
│       ├── __init__.py
│       ├── login.py
│       ├── plugins_user.py
│       ├── help.py
│       └── menu.py
├── userbot/
│   ├── smart_manager.py     # (mevcut)
│   └── plugins.py           # (mevcut çekirdek)
├── userbot_compat/          # (mevcut uyumluluk katmanı)
├── utils/
│   ├── logger.py            # YENİ
│   ├── helpers.py
│   └── bot_api.py
├── plugins/
│   ├── _sablon.py           # YENİ: temiz plugin şablonu
│   └── ...
├── tests/                   # YENİ (Seviye 3)
└── docs/
    ├── KURULUM_REHBERI.md   # YENİ
    └── PLUGIN_REHBERI.md    # YENİ
```

---

## 6. Bu Paketin İçindekiler (hemen kullanabilirsin)

`_IYILESTIRME/` klasöründe:
1. **`01_ANALIZ_VE_YOL_HARITASI.md`** — bu belge.
2. **`KURULUM_REHBERI.md`** — acemiler için sıfırdan, adım adım kurulum.
3. **`PLUGIN_REHBERI.md`** — "nasıl plugin yazılır" düz anlatım + komut tablosu.
4. **`utils_logger.py`** — `utils/logger.py` olarak kopyalanacak gerçek loglama modülü.
5. **`plugins__sablon.py`** — `plugins/_sablon.py` olarak kopyalanacak temiz şablon.
6. **`.gitignore.duzeltilmis`** — kök dizindeki `.gitignore` ile değiştirilecek.
7. **`temizle.sh`** — ölü kodu/çöp dosyaları **güvenle** temizleyen, önce ne sileceğini
   gösterip onay isteyen betik.

> Bu dosyalar **mevcut kodu bozmaz**; ayrı bir klasörde durur. İstediğini, istediğin
> zaman ana projeye taşırsın.

---

## 7. Sıradaki Adım İçin Öneri

En mantıklı sıra:
1. **Önce güvenlik** (Bölüm 0) — token/şifre sıfırla.
2. **Seviye 1** — `temizle.sh` çalıştır + `logger.py` ekle. (Yarım gün.)
3. **Seviye 2 / O1** — sadece `admin.py`'ı bölmekle başla; en büyük rahatlamayı bu verir.
4. Gerisi ihtiyaç oldukça.

İstersen bir sonraki adımda **`admin.py`'ı gerçekten parçalara bölünmüş haliyle** yazıp
sana hazır verebilirim — söylemen yeterli.
