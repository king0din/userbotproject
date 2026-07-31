# 🔄 Güncelle Butonu Hatası — Sebep ve Çözüm

## Hata

```
❌ Hata: Cmd('git') failed due to: exit code(1)
  cmdline: git pull -v -- origin main
  stderr: 'error: Your local changes to the following files would be overwritten by merge:'
```

## Sebep

`git pull`, sunucudaki **değiştirilmiş dosyaların üzerine yazmamak için** merge'i
iptal ediyor. Yani bu bir bot hatası değil, git'in koruma davranışı.

Sunucudaki dosyalar şu yüzden değişmiş olabilir:
1. **Hazır zip paketlerinin repo klasörüne açılması** (en yaygın sebep) — dosyalar
   değişmiş sayılır ama commit'lenmemiştir.
2. Sunucuda doğrudan dosya düzenlenmesi.
3. Repo'ya erkenden commit'lenmiş bir veri dosyasına botun çalışırken yazması.
   (`.gitignore`'a sonradan eklemek yetmez — dosya zaten takip ediliyorsa git
   onu izlemeye devam eder; `git rm --cached <dosya>` gerekir.)

## Eski davranışın iki sorunu

1. **Dosya listesi görünmüyordu.** GitPython, `origin.pull()` sırasında stderr'in
   devamını yutuyor; hangi dosyanın çakıştığı mesajda hiç yer almıyordu.
   (Test edildi: `e.stderr` yalnızca ilk satırı içeriyor, dosya adları kayboluyor.)
2. **Çıkmaz sokaktı.** Panelde yapılabilecek hiçbir şey yoktu.

## Yeni davranış

Güncelle'ye basınca, **pull denenmeden önce** çakışacak dosyalar tespit edilir:

```
⚠️ Güncelleme durduruldu

3 yeni güncelleme var, ancak sunucuda değiştirilmiş 2 dosya var.
Devam edilirse bu değişiklikler silinirdi, o yüzden durdum.

Değişen dosyalar:
• plugins/tag.py
• config.py

💾 Sakla ve güncelle   →  değişikliklerin git stash'e alınır, sonra geri uygulanır
🗑 Değişiklikleri sil ve güncelle  →  yerel değişiklikler kalıcı silinir
```

### Tespit kesinliği

Bir dosya, ancak **hem sunucuda değiştirilmişse hem de gelen commit'lerde
değişmişse** merge'i engeller. Sadece yerelde değişmiş (uzakta dokunulmamış)
dosyalar pull'u engellemez — bu durumda güncelleme **durdurulmadan** devam eder.
Yoksa her runtime veri dosyası boşuna uyarı üretirdi.

### Buton davranışları

| Buton | Ne yapar | Veri güvenliği |
|---|---|---|
| 💾 Sakla ve güncelle | `git stash` → `pull` → `stash pop` | Değişiklikler korunur. `pop` çakışırsa **stash'te kalır**, silinmez; panel bunu ve `git stash pop` komutunu söyler |
| 🗑 Değişiklikleri sil | `git reset --hard HEAD` → `pull` | **Yıkıcı** — sadece açık onayla çalışır |

Ayrıca güncelleme başarısız olursa stash otomatik geri uygulanır.

### Hata mesajları

Git hataları artık kesilmeden gösteriliyor ve duruma özel ipucu ekleniyor
(yerel değişiklik / ağ erişimi / kimlik doğrulama).

Bağımlılık kurulumu (`pip install -r requirements.txt`) başarısız olursa
güncelleme artık tümden çökmüyor; uyarı verip devam ediyor.

---

## Senin durumunda ne yapmalısın

Sana gönderdiğim zip'leri repo klasörüne açtıysan, o dosyalar "yerel değişiklik"
sayılıyor ve her pull'u engelliyor. İki seçenek:

**A) Değişiklikler sende kalsın (önerilen):** Gönderdiğim güncellemeleri kendi
GitHub repo'na commit + push et. Sonra panelden Güncelle sorunsuz çalışır:
```
git add -A
git commit -m "guncelleme"
git push
```

**B) Sunucudaki değişiklikler gitsin, repo'daki hâline dön:**
Panelden **🗑 Değişiklikleri sil ve güncelle** butonuna bas.
(Sunucudaki düzenlemelerin **kalıcı silinir**, önce yedek al.)

### Takip edilen veri dosyası varsa

Bot çalışırken yazdığı bir dosya repo'da takip ediliyorsa, her seferinde
aynı sorun tekrarlar. Kalıcı çözüm:
```
git rm --cached plugins/tag_blocked.json
git commit -m "runtime veri dosyasi takipten cikarildi"
```
(`.gitignore`'da zaten `*.json` var; `git rm --cached` takibi de keser.)

---

## Doğrulama (gerçek git repo'ları ile test edildi)

| Senaryo | Sonuç |
|---|---|
| Yerel değişiklik + uzakta da değişmiş dosya | ✅ Doğru tespit, güncelleme durduruldu |
| Yerel değişiklik + uzakta değişmemiş dosya | ✅ Boşuna durdurmadı, pull geçti, yerel dosya korundu |
| Stash akışı, çakışmayan | ✅ Yerel değişiklik korundu **ve** güncelleme uygulandı |
| Stash akışı, çakışan | ✅ Değişiklik **kaybolmadı**, stash'te duruyor, kullanıcı bilgilendirildi |
| Force akışı | ✅ Yerel silindi, güncelleme uygulandı |
| Handler sayısı | 73 → 75 (tam olarak 2 yeni buton), user 29 değişmedi ✅ |
