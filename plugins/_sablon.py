# ============================================================
#  PLUGIN ŞABLONU — KingTG UserBot Service
# ============================================================
#  Bu dosyayı KOPYALA, adını değiştir (ör. selam.py) ve içini doldur.
#  Aşağıdaki "# description / # author / # version" satırları ÖNEMLİ:
#  bot bunları okuyup plugin listesinde gösterir. Silme.
# ------------------------------------------------------------
# description: Ne işe yaradığını buraya tek cümleyle yaz
# author: @kullanici_adin
# version: 1.0.0
# ============================================================

from telethon import events
from userbot.events import register


# ╔══════════════════════════════════════════════════════════╗
# ║  register(client): Botun her kullanıcı için çağırdığı       ║
# ║  fonksiyon. TÜM komutlarını bunun İÇİNE yaz.               ║
# ║  'client' = o kullanıcının kendi userbot bağlantısı.       ║
# ╚══════════════════════════════════════════════════════════╝

# --------------------------------------------------------
# KOMUT 1:  .selam
# 'outgoing=True' = sadece SEN yazınca çalışır (başkası değil)
# 'pattern'       = komutu tanımlayan kalıp. r'^\.selam$' →
#                   tam olarak ".selam" yazınca tetiklenir.
# --------------------------------------------------------
@register(outgoing=True, pattern=r'^\.selam$')
async def selam_komutu(event):
    # event.edit → senin yazdığın mesajı düzenler (yeni mesaj atmaz)
    await event.edit("👋 Merhaba! Bu benim ilk plugin'im.")

# --------------------------------------------------------
# KOMUT 2:  .topla 4 5   →  argüman almayı gösterir
# pattern içindeki (.*) = komuttan sonra yazılan her şeyi yakalar
# --------------------------------------------------------
@register(outgoing=True, pattern=r'^\.topla (.+)$')
async def topla_komutu(event):
    # Komuttan sonra yazılanı al:  ".topla 4 5"  →  "4 5"
    arguman = event.pattern_match.group(1)

    try:
        sayilar = [int(x) for x in arguman.split()]
        sonuc = sum(sayilar)
        await event.edit(f"🧮 Toplam: **{sonuc}**")
    except ValueError:
        # Kullanıcı sayı yerine harf girdiyse ÇÖKME, nazikçe uyar
        await event.edit("❌ Lütfen sadece sayı gir. Örnek: `.topla 4 5`")

# --------------------------------------------------------
# KOMUT 3:  .yanit  →  bir mesaja yanıt vererek çalışır
# --------------------------------------------------------
@register(outgoing=True, pattern=r'^\.yanit$')
async def yanit_komutu(event):
    if not event.reply_to_msg_id:
        await event.edit("↩️ Bu komutu bir mesaja **yanıt vererek** kullan.")
        return

    yanitlanan = await event.get_reply_message()
    await event.edit(f"Sen şunu yanıtladın:\n\n> {yanitlanan.text}")


# ╔══════════════════════════════════════════════════════════╗
# ║  unregister(): Plugin kapatılırken çağrılır.               ║
# ║  Özel bir temizlik gerekmiyorsa boş bırak (pass).          ║
# ╚══════════════════════════════════════════════════════════╝
def unregister():
    pass


# ============================================================
#  İPUÇLARI
#  • Komut önekiniz "." (nokta). İstersen pattern'i değiştir.
#  • 'await event.edit(...)' yerine 'await event.reply(...)' ile
#    yeni bir mesaj olarak da cevap verebilirsin.
#  • Hata olabilecek yerleri try/except ile sar AMA hatayı
#    yutma — en azından kullanıcıya anlamlı bir mesaj göster.
#  • Daha fazla örnek için: PLUGIN_REHBERI.md
# ============================================================
