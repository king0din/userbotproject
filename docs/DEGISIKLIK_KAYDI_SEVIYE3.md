# 📝 DEĞİŞİKLİK KAYDI — Seviye 3 (Bug/Çakışma Analizi & İnline Sadeleştirme)

Tarih: 2026-07-14

Bu turda **tüm proje bug/çakışma açısından analiz edildi**, kafa karıştıran ve
çift çalışan (ölü) kod parçaları temizlendi, çok-kullanıcılı çakışmaya yol açan
kritik hatalar giderildi. Komutların hepsi **çakışmasız** ve pluginler
Telethon ile **hatasız yükleniyor** (test edildi).

---

## 🔴 KRİTİK DÜZELTMELER

### 1) `ses.py` — çok-kullanıcılı yarış hatası (race condition)
- **Sorun:** `current_voice` **global** değişkendi. Aynı bot birden çok hesaba
  hizmet verdiğinden, A kullanıcısı `.ses` yazınca global sese set ediliyor,
  tam o an B kullanıcısı `.ses` çalıştırırsa **yanlış sesle** üretim yapıyordu.
- **Çözüm:** Global kaldırıldı. Her handler artık `voice = _load_voice(me.id)`
  ile **kullanıcıya özel** sesi okuyor. `.ses`, `.sesler`, `.sesayar` düzeltildi.

### 2) `userbot/plugins.py` — komut çıkarımı hiç çalışmıyordu
- **Sorun:** Plugin komutlarını çıkaran regex (`pattern=r"^\.afk$"` gibi
  yaygın biçimleri) **hiç yakalamıyordu**. Sonuç: yeni yüklenen pluginlerde
  komut listesi boş kalıyor, **komut çakışması kontrolü devre dışı** kalıyordu.
- **Çözüm:** Sağlam `_extract_command_names()` + `_expand_token()` eklendi.
  Artık `.ses/.tts`, `.q/.qs`, `.müzik`, `.burç`, `.klon/.clon` gibi
  alternatif/karakter-sınıflı ve Türkçe karakterli komutlar doğru çıkarılıyor.
  (Test: 62 benzersiz komut, **pluginler arası çakışma yok**.)

### 3) `start.py` — yükleme başarısızsa yanıltıcı "🟢 aktif" durumu
- **Sorun:** Plugin buton/`.pload` ile yüklenirken DB'ye "aktif" yazılıyor,
  ama `activate_plugin` başarısız olsa bile DB'de aktif kalıyordu → panelde
  🟢 görünüp aslında çalışmıyordu.
- **Çözüm:** Yükleme başarısız olursa `active_plugins`'ten **geri alınıyor**.

---

## 🟡 KAFA KARIŞTIRAN / ÖLÜ KOD TEMİZLİĞİ (tag.py)

`tag.py` iki farklı etiketleme sistemi barındırıyordu; eskisi hiç
çağrılmıyordu ama `.tagstat`/`.tagstop`'ta yanıltıcı bilgi üretebiliyordu.

- **Silindi:** kullanılmayan `tag_process()` fonksiyonu (~200 satır ölü kod).
- **Silindi:** hiç çağrılmayan `load_blocked_users()` (tüm hesapların engelini
  karıştırıyordu; hesap-bazlı `load_my_blocked_users` zaten kullanılıyor).
- **Silindi:** kullanılmayan `tag_active` / `tag_data` global durumu.
- **Sadeleştirildi:** `.tag`, `.tagadmin`, `.tagstop`, `.tagstat` artık sadece
  yeni **buton akışını** (`bot._tag_jobs`) kullanıyor; eski global dallar kaldırıldı.
- **Kaldırıldı:** `.tag`'daki boş `try: pass` (ölü) bloğu.
- **Güncellendi:** Plugin başlığındaki eski açıklama (sabit "2.5 sn" vb.)
  yerine güncel buton akışını anlatan metin.
- **Eklendi:** `cleanup_user_data()` — plugin kapatılınca/çıkışta devam eden
  etiketleme işi **durdurulur** (askıda görev/panel state sızıntısı önlenir).

---

## 🟢 KÜÇÜK İYİLEŞTİRMELER
- `start.py`: `__name__ = "inline_start"` gölgelemesi kaldırıldı (plugin
  yöneticisinin modül-adı takibini ve handler temizliğini bozabiliyordu).
- `start.py`: "Yüklü Pluginler" sayfa göstergesindeki `b"noop"` butonu, spinner
  takılmasın diye aynı sayfayı yeniden çizen callback ile değiştirildi.
- `start.py`: Komut kataloğuna eksik `.otomsgkopyala` ve YouTube komutları
  (`.müzik/.video/.ytara`) eklendi.
- Kullanılmayan `from telethon import events` importları temizlendi
  (ses, example, _sablon, burc, q).
- `pload`/buton-yükleme `activate_plugin` çağrıları try/except ile sarmalandı.

---

## ✅ DOĞRULAMA (bu turda yapılan testler)
- Tüm 45 `.py` dosyası **derleniyor** (`py_compile`).
- 12 plugin **gerçek Telethon ile exec** edilip handler kaydı doğrulandı
  (toplam 54 userbot handler sorunsuz kaydedildi).
- Uyumluluk katmanı (`@register`, `set_client`, bilinmeyen parametre filtresi)
  test edildi.
- Pluginler-arası **komut çakışması yok** (62 komut), **callback çakışması yok**.
- `cleanup_user_data(logout)` tüm ilgili pluginlerde sorunsuz.

> Not: Davranışsal mantık korundu; yalnızca hatalar/ölü kod düzeltildi ve
> çok-kullanıcılı güvenlik sağlamlaştırıldı.
