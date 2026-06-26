#!/usr/bin/env bash
# ============================================================
#  temizle.sh — KingTG UserBot Service temizlik betiği
# ------------------------------------------------------------
#  Ölü kodu ve çöp/sır dosyalarını temizler.
#
#  GÜVENLİ KULLANIM:
#    1) Önce SADECE NE SİLECEĞİNİ GÖSTERİR (hiçbir şey silmez):
#         bash temizle.sh
#    2) İçeriği görüp onayladıktan sonra GERÇEKTEN sil:
#         bash temizle.sh --uygula
#
#  NOT: Bu betiği projenin KÖK dizininde çalıştır (main.py'nin olduğu yer).
# ============================================================

set -u

APPLY=0
if [ "${1:-}" = "--uygula" ] || [ "${1:-}" = "--apply" ]; then
    APPLY=1
fi

# main.py burada mı? Yanlış dizinde çalıştırmayı önle.
if [ ! -f "main.py" ]; then
    echo "❌ main.py bulunamadı. Bu betiği projenin kök dizininde çalıştır."
    exit 1
fi

echo "============================================================"
if [ "$APPLY" -eq 1 ]; then
    echo "  TEMİZLİK MODU: GERÇEKTEN SİLİNECEK"
else
    echo "  ÖNİZLEME MODU (hiçbir şey silinmez)"
    echo "  Gerçekten silmek için:  bash temizle.sh --uygula"
fi
echo "============================================================"
echo ""

# Bir hedefi (dosya/klasör/glob) işleyen yardımcı
sil() {
    local aciklama="$1"; shift
    local bulundu=0
    for hedef in "$@"; do
        # glob genişlet
        for f in $hedef; do
            if [ -e "$f" ]; then
                bulundu=1
                if [ "$APPLY" -eq 1 ]; then
                    rm -rf "$f" && echo "   🗑️  silindi:  $f"
                else
                    echo "   • silinecek: $f"
                fi
            fi
        done
    done
    if [ "$bulundu" -eq 0 ]; then
        echo "   (yok / zaten temiz)"
    fi
}

echo "▶ 1) ÖLÜ KOD (güvenle silinir — hiçbir yer kullanmıyor)"
sil "ölü kod" \
    "userbot/manager.py" \
    "plugins/pixelator.py.patched" \
    "plugins/poto.py.patched"
echo ""

echo "▶ 2) PYTHON ÖNBELLEĞİ (__pycache__, .pyc — otomatik yeniden oluşur)"
if [ "$APPLY" -eq 1 ]; then
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    find . -type f -name "*.pyc" -delete 2>/dev/null
    echo "   🗑️  tüm __pycache__ ve .pyc temizlendi"
else
    cnt=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l | tr -d ' ')
    echo "   • silinecek: $cnt adet __pycache__ klasörü (+ .pyc dosyaları)"
fi
echo ""

echo "▶ 3) GEÇİCİ DOSYALAR"
sil "geçici" ".restart_info" ".bot_username" "*.tmp" "*.temp" "*.session-journal"
echo ""

echo "============================================================"
echo "  🔒 GÜVENLİK — sır içeren dosyalar"
echo "============================================================"
echo "  Aşağıdaki dosyalar HASSAS bilgi içerir. Bu KOPYADAN silmek"
echo "  güvenliğini artırır AMA gerçek kurulumunda .env'e ihtiyacın var."
echo "  Bu yüzden betik bunları OTOMATİK SİLMEZ; karar senin."
echo ""
for f in ".env.txt" "bot_session.session"; do
    if [ -e "$f" ]; then
        echo "   ⚠️  VAR: $f"
        echo "       → Paylaşım/yedek kopyalarında bunu MUTLAKA sil."
        echo "       → Elle silmek için:  rm -f \"$f\""
    fi
done
echo ""
echo "   NOT: '.env' dosyasını SİLME (bota lazım), ama asla paylaşma."
echo "   NOT: 'data/' klasörü gerçek kullanıcı verisi — yedeğini al, paylaşma."
echo ""

echo "============================================================"
if [ "$APPLY" -eq 1 ]; then
    echo "  ✅ Temizlik tamamlandı."
else
    echo "  ℹ️  Bu bir önizlemeydi. Onaylıyorsan:  bash temizle.sh --uygula"
fi
echo "============================================================"
