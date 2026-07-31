@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title KingTG - Sunucu Guncelleme
cd /d "%~dp0"

echo ==================================================
echo    KingTG - Sunucudaki repoyu GitHub ile esitle
echo ==================================================
echo.

REM ---------- 0) Git deposu mu? ----------
if not exist ".git" (
    echo [HATA] Bu klasor bir git deposu DEGIL.
    echo.
    echo Ilk kurulum icin repoyu klonlamalisin:
    echo     git clone https://github.com/KULLANICI/REPO.git kingtg
    echo Sonra .env , sessions\ ve data\ klasorlerini eski klasorden kopyala.
    echo.
    pause
    exit /b 1
)

REM ---------- 1) Bot calisiyor mu uyarisi ----------
echo [!] Devam etmeden once BOTU KAPAT (calisan python penceresini kapat).
echo     Acik dosyalar guncellemeyi engelleyebilir.
echo.
set /p HAZIR="Bot kapali mi? (E/H): "
if /i not "!HAZIR!"=="E" (
    echo Once botu kapat, sonra bu dosyayi tekrar calistir.
    pause
    exit /b 0
)
echo.

REM ---------- 2) Aktif dal ve uzak repo ----------
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set DAL=%%b
if "!DAL!"=="" set DAL=main
echo Aktif dal   : !DAL!
echo Uzak repo   :
git remote -v | findstr /i "fetch"
echo.

REM ---------- 3) Yedek ----------
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set DT=%%I
if "!DT!"=="" set DT=%RANDOM%
set YEDEK=..\kingtg_yedek_!DT!
echo [1/5] Yedek aliniyor -^> !YEDEK!
mkdir "!YEDEK!" 2>nul
if exist ".env"     copy /y ".env" "!YEDEK!\" >nul
if exist "sessions" xcopy "sessions" "!YEDEK!\sessions\" /E /I /Y /Q >nul
if exist "data"     xcopy "data"     "!YEDEK!\data\"     /E /I /Y /Q >nul
echo       Tamam. (.env , sessions , data yedeklendi)
echo.

REM ---------- 4) GitHub'dan cek ----------
echo [2/5] GitHub'dan son surum aliniyor...
git fetch origin
if errorlevel 1 (
    echo.
    echo [HATA] GitHub'a erisilemedi.
    echo   - Internet baglantisini kontrol et
    echo   - Ozel repo ise kimlik bilgisi / token gerekebilir
    pause
    exit /b 1
)
echo.

REM ---------- 5) Durum goster + onay ----------
echo [3/5] Sunucudaki yerel degisiklikler:
git status --short
if errorlevel 1 goto :hata
echo.
echo  ------------------------------------------------
echo   DIKKAT: Devam edilirse sunucudaki TUM yerel KOD
echo   degisiklikleri silinip GitHub surumune donulecek.
echo.
echo   DOKUNULMAZ: .env , sessions\ , data\ , *.json , logs\
echo   (ustelik hepsinin yedegi yukarida alindi)
echo  ------------------------------------------------
echo.
set /p ONAY="Devam edilsin mi? (E/H): "
if /i not "!ONAY!"=="E" (
    echo Iptal edildi. Hicbir sey degismedi.
    pause
    exit /b 0
)
echo.

REM ---------- 6) Esitle ----------
echo [4/5] GitHub surumune donuluyor...
git reset --hard origin/!DAL!
if errorlevel 1 goto :hata
echo.

REM ---------- 7) Bagimliliklar ----------
echo [5/5] Bagimliliklar kuruluyor...
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [UYARI] Bazi bagimliliklar kurulamadi. Kod yine de guncellendi.
)
echo.

echo ==================================================
echo    GUNCELLEME TAMAMLANDI
echo    Yedek klasoru: !YEDEK!
echo ==================================================
echo.
set /p BASLAT="Bot simdi baslatilsin mi? (E/H): "
if /i "!BASLAT!"=="E" (
    python main.py
)
pause
exit /b 0

:hata
echo.
echo [HATA] Islem basarisiz oldu. Yedek: !YEDEK!
pause
exit /b 1
