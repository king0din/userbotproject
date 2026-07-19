# ============================================
# KingTG UserBot Service - Admin / ortak durum
# "ID gönder" akışları için paylaşılan bekleme durumu.
# Tek sözlük kullanılır ki iki ayrı akış aynı anda
# çakışmasın (yeni akış başlatınca eskisi ezilir).
#
# Biçim: {admin_id: {"kind": str, "plugin": str | None}}
#   kind: "ban" | "sudo" | "pallow" | "prestrict"
# ============================================

admin_input_state = {}
