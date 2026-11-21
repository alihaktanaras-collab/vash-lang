# =====================================================================
#  VASH DERLEYİCİSİ: Bütün istasyonları sırayla çalıştırır
# =====================================================================
#
#   oyun.vash ─► 1. Lexer ─► 2. Parser ─► 3. Tipler ─► 4. LLVM IR ─► clang ─► oyun.exe
#
#  Kullanım (proje klasöründe, vash.cmd sayesinde):
#      vash run   oyun.vash     → derle ve çalıştır
#      vash build oyun.vash     → sadece oyun.exe üret
#      vash ir    oyun.vash     → üretilen LLVM IR'ı göster
# =====================================================================

import os
import shutil
import subprocess
import sys

from lexer import kelimelere_ayir
from parser import Parser
from tipler import tipleri_kontrol_et
from llvm_uretici import llvm_ir_uret
from moduller import modulleri_bagla

DERLEYICI_KLASORU = os.path.dirname(os.path.abspath(__file__))
CALISMA_C = os.path.join(DERLEYICI_KLASORU, "calisma.c")
CALISMA_O = os.path.join(DERLEYICI_KLASORU, "calisma_lto.o")


class DerlemeHatasi(Exception):
    pass


def clang_bul():
    """clang'ın yerini bul.
    1) Şu anki PATH'te
    2) Windows'un kayıtlı PATH ayarında (yeni kurulan programlar, eski açılmış
       pencerelerin PATH'ine görünmez; bu yüzden kayıt defterine de bakıyoruz)
    3) winget'in paketleri kurduğu klasörde"""
    yol = shutil.which("clang")
    if yol:
        return yol

    if sys.platform == "win32":
        import winreg
        kayitli = []
        for kok, anahtar in [(winreg.HKEY_CURRENT_USER, "Environment"),
                             (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")]:
            try:
                with winreg.OpenKey(kok, anahtar) as k:
                    kayitli.append(os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]))
            except OSError:
                pass
        yol = shutil.which("clang", path=os.pathsep.join(kayitli))
        if yol:
            return yol

        import glob
        paketler = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages")
        bulunan = glob.glob(os.path.join(paketler, "*LLVM*", "*", "bin", "clang.exe"))
        if bulunan:
            return bulunan[0]

    raise DerlemeHatasi("clang bulunamadı. LLVM kurulu mu?")


def calisma_zamanini_hazirla(clang):
    """calisma.c'yi bir kere derle; değişmedikçe tekrar derleme (hız için)."""
    if os.path.exists(CALISMA_O) and os.path.getmtime(CALISMA_O) >= os.path.getmtime(CALISMA_C):
        return
    # -flto: makine koduna değil LLVM'in ara diline derle; böylece son adımda LLVM,
    # çalışma zamanı fonksiyonlarını (tut, birak...) programın içine gömebilir.
    sonuc = subprocess.run([clang, "-O2", "-flto", "-c", CALISMA_C, "-o", CALISMA_O],
                           capture_output=True, text=True)
    if sonuc.returncode != 0:
        raise DerlemeHatasi("Çalışma zamanı derlenemedi:\n" + sonuc.stderr)


def ir_uret(kod, klasor=None):
    """1-4. istasyonlar: kodu LLVM IR'a çevir. klasor: import edilen dosyaların aranacağı yer."""
    tokenlar = kelimelere_ayir(kod)
    agac = Parser(tokenlar).program()
    agac = modulleri_bagla(agac, klasor or os.getcwd())
    kontrolcu = tipleri_kontrol_et(agac)
    return llvm_ir_uret(agac, kontrolcu)


def exe_uret(ir, ll_yolu, exe_yolu):
    """LLVM IR'ı clang ile optimize edip makine koduna (.exe) çevir."""
    clang = clang_bul()
    calisma_zamanini_hazirla(clang)
    with open(ll_yolu, "w", encoding="utf-8") as f:
        f.write(ir)
    # -O2: LLVM'in optimizasyonlarını aç (C++ derleyicilerinin kullandığının aynısı)
    # -flto: programı ve çalışma zamanını BİRLİKTE optimize et (LTO, ~%10 hız)
    # extern "kutuphane" ile istenen kütüphaneler (IR'ın içine not edilmişti)
    ekler = []
    for satir in ir.splitlines():
        if satir.startswith("; vash-kutuphane: "):
            k = satir.split(": ", 1)[1].strip()
            if k.lower() in ("c", "m", "msvcrt", "ucrt"):
                continue                                  # C'nin temel kütüphanesi zaten bağlı
            if k.lower().endswith((".lib", ".a")) or os.path.sep in k or "/" in k:
                ekler.append(k)                            # dosya yolu verilmiş
            else:
                ekler.append("-l" + k)
    sonuc = subprocess.run(
        [clang, "-O2", "-flto", "-fuse-ld=lld", "-Wno-override-module", ll_yolu, CALISMA_O,
         "-lws2_32", "-lshell32", "-lwinhttp", "-lsecur32", "-lcrypt32", "-lncrypt", *ekler, "-o", exe_yolu],
        capture_output=True, text=True,
    )
    if sonuc.returncode != 0:
        import re
        bulunamayan = re.search(r"unable to find library -l(\S+)", sonuc.stderr)
        if bulunamayan:
            raise DerlemeHatasi(f"'{bulunamayan.group(1)}' kütüphanesi bulunamadı. extern bloğundaki adı kontrol et.")
        tanimsiz = re.search(r"undefined symbol: (\S+)", sonuc.stderr)
        if tanimsiz:
            raise DerlemeHatasi(f"'{tanimsiz.group(1)}' fonksiyonu, extern'de yazılan kütüphanelerin hiçbirinde bulunamadı.\n"
                                f"   Adını ve hangi kütüphanede olduğunu kontrol et.")
        raise DerlemeHatasi("clang derleyemedi (bu, derleyicimizde bir hata demek):\n" + sonuc.stderr)


if __name__ == "__main__":
    from lexer import LexerHatasi
    from parser import ParserHatasi
    from tipler import TipHatasi

    KULLANIM = (
        "Vash derleyicisi\n\n"
        "Kullanım:\n"
        "  vash run   dosya.vash    derle ve çalıştır\n"
        "  vash build dosya.vash    sadece .exe üret\n"
        "  vash ir    dosya.vash    üretilen LLVM IR'ı göster\n"
    )
    argumanlar = sys.argv[1:]
    komut = argumanlar.pop(0) if argumanlar and argumanlar[0] in ("run", "build", "ir") else "build"
    # Eski yazılış da çalışsın: derle.py dosya --calistir / --ir
    if "--calistir" in argumanlar:
        komut = "run"
    if "--ir" in argumanlar:
        komut = "ir"
    dosyalar = [a for a in argumanlar if not a.startswith("--")]
    if not dosyalar:
        print(KULLANIM)
        sys.exit(1)

    kaynak = dosyalar[0]
    if not os.path.exists(kaynak):
        print(f"HATA: '{kaynak}' diye bir dosya yok.")
        sys.exit(1)
    if not kaynak.endswith(".vash"):
        print(f"UYARI: Vash dosyalarının uzantısı .vash olmalı ('{kaynak}').")
    temel = os.path.splitext(kaynak)[0]
    with open(kaynak, encoding="utf-8-sig") as f:
        kod = f.read()

    try:
        ir = ir_uret(kod, os.path.dirname(os.path.abspath(kaynak)))
    except (LexerHatasi, ParserHatasi, TipHatasi) as h:
        print("HATA:", h)
        sys.exit(1)

    if komut == "ir":
        print(ir)
        sys.exit(0)

    try:
        exe_uret(ir, temel + ".ll", temel + ".exe")
    except DerlemeHatasi as h:
        print("HATA:", h)
        sys.exit(1)

    if komut == "run":
        sys.stdout.flush()
        sys.exit(subprocess.run([os.path.abspath(temel + ".exe")]).returncode)
    print(f"✓ {temel}.exe hazır")
