# Vash ile yazılmış LLVM IR üreticisini (vashc/uretici.vash) Python'dakiyle (derleyici/llvm_uretici.py) karşılaştırır.
# Her program iki derleyiciden de geçer; çıkan LLVM IR metinleri satır satır birebir aynı olmalı.
#
# Kullanım:  python vashc/karsilastir_uretici.py [dosya.vash ...]

import glob
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from karsilastir_parser import yeni_ozellik_mi  # noqa: E402

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "derleyici"))
sys.path.insert(0, os.path.join(KOK, "vashc"))
from derle import ir_uret  # noqa: E402
from karsilastir_tipler import ZOR_DURUMLAR, ZOR_MODULLER  # noqa: E402

EXE = os.environ.get("VASH_EXE") or os.path.join(KOK, "vashc", "uretici_dene.exe")
SABLON = os.path.join(KOK, "derleyici")


def python_ciktisi(yol):
    with open(yol, encoding="utf-8-sig") as f:
        kod = f.read().replace("\r\n", "\n")
    try:
        return ir_uret(kod, os.path.dirname(yol)).rstrip("\n").split("\n")
    except Exception as h:                      # lexer / parser / tip hataları
        return ["HATA: " + str(h)]


def vash_ciktisi(yol):
    # Sadece Vash derleyicisinde olan hızlandırmalar (metin[i] için) kapalı: eski derleyiciyle birebir karşılaştırılabilsin
    ortam = dict(os.environ, VASH_ESKI_URETIM="1")
    r = subprocess.run([EXE], input=yol + "\n" + SABLON + "\n", capture_output=True, text=True, encoding="utf-8", env=ortam)
    cikti = r.stdout.replace("\r\n", "\n").rstrip("\n")
    if r.returncode != 0 and not cikti.startswith("HATA"):
        return ["ÇÖKTÜ (çıkış kodu " + str(r.returncode) + "): " + (r.stderr.strip() or cikti[-300:])[:400]]
    if cikti.startswith("HATA"):
        return [cikti]
    return cikti.split("\n")


# extern'de kullanılabilen tipler listesi artık u8, f32 ve C yapılarını da sayıyor (TASARIM.md madde 45)
# bulunamayan modülün mesajı artık standart kütüphaneyi de anıyor
BEKLENEN_FARKLAR = {"[zor] hata_extern_tip", "[modül] mod_hata_yok"}


def karsilastir(ad, yol):
    py, vs = python_ciktisi(yol), vash_ciktisi(yol)
    if py and py[0].startswith("HATA"):
        py = ["\n".join(py)]
    # Bilerek değişen mesajlar (Vash derleyicisi yeni özellik aldığı için); iki taraf da hata veriyorsa geçer
    if ad in BEKLENEN_FARKLAR and py and vs and py[0].startswith("HATA") and vs[0].startswith("HATA"):
        return True, len(py), py[0].startswith("HATA")
    if py == vs:
        return True, len(py), py[0].startswith("HATA")
    for i, (a, b) in enumerate(zip(py, vs)):
        if a != b:
            print(f"  ✗ {ad}: {i + 1}. satır farklı\n      Python: {a[:300]!r}\n      Vash:   {b[:300]!r}")
            break
    else:
        print(f"  ✗ {ad}: satır sayısı farklı (Python {len(py)}, Vash {len(vs)})")
    return False, len(py), False


if __name__ == "__main__":
    dosyalar = sys.argv[1:] or sorted(glob.glob(os.path.join(KOK, "ornekler", "*.vash")) +
                                      glob.glob(os.path.join(KOK, "vashc", "*.vash")))
    hepsi = [(os.path.basename(d), d) for d in dosyalar]
    yeniler = [d for d in dosyalar if yeni_ozellik_mi(d)]
    if yeniler:
        print(f"(sadece Vash derleyicisinde olan özellikleri kullandığı için atlanan {len(yeniler)} dosya: "
              f"{', '.join(os.path.basename(d) for d in yeniler)})")
    hepsi = [(a, d) for a, d in hepsi if d not in yeniler]
    if not sys.argv[1:]:
        gecici = tempfile.mkdtemp()
        for ad, kod in ZOR_DURUMLAR.items():
            yol = os.path.join(gecici, ad + ".vash")
            with open(yol, "w", encoding="utf-8") as f:
                f.write(kod)
            hepsi.append(("[zor] " + ad, yol))
        for ad, dosyalar_ in ZOR_MODULLER.items():
            klasor = os.path.join(gecici, ad)
            os.makedirs(klasor)
            for dad, kod in dosyalar_.items():
                with open(os.path.join(klasor, dad), "w", encoding="utf-8") as f:
                    f.write(kod)
            hepsi.append(("[modül] " + ad, os.path.join(klasor, "ana.vash")))
    tamam = toplam = hatali = 0
    for ad, yol in hepsi:
        ok, n, hata_mi = karsilastir(ad, yol)
        tamam += ok
        hatali += ok and hata_mi
        toplam += n if ok else 0
    print(f"\n{tamam}/{len(hepsi)} dosya birebir aynı  ({toplam} satır LLVM IR karşılaştırıldı; "
          f"{hatali} tanesi iki tarafta da aynı hatayı veren program)")
    sys.exit(0 if tamam == len(hepsi) else 1)
