# Vash ile yazılmış kelimelere ayırıcıyı (vashc/lexer.vash) Python'dakiyle (derleyici/lexer.py)
# karşılaştırır. Her dosya için iki sürümün ürettiği token'lar BİREBİR aynı olmalı.
#
# Kullanım:  python vashc/karsilastir.py [dosya.vash ...]
#            (dosya verilmezse ornekler/ ve vashc/ içindeki bütün .vash dosyaları + zor durumlar)

import glob
import os
import subprocess
import sys
import tempfile
import time

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "derleyici"))
from lexer import kelimelere_ayir, LexerHatasi  # noqa: E402

EXE = os.path.join(KOK, "vashc", "lexer_dene.exe")

# Zor durumlar: her biri ayrı bir dosya olarak denenir
ZOR_DURUMLAR = {
    "kacislar": 'print("a\\nb\\tc \\"tırnak\\" \\\\ ters \\{ süslü \\}")\n',
    "ic_ice": 'var l = ["a", "b"]\nprint("{l.join(", ")} ve {"iç {l[1]}"}")\n',
    "sayilar": "var a = 3.14\nvar b = 42\nvar c = 1.\nvar d = x.y\nvar e = 10//3\n",
    "turkce": "var çiçek_sayısı = 5\nvar İĞÜŞÖÇ = ığüşöç\n",
    "isaretler": "a <= b >= c -> d // e ? f\n{}[]():,;.+-*/%=<>\n",
    "bos_satirlar": "\n\n# sadece yorum\n\nvar x = 1  # sonda yorum\n\n",
    "hata_esittir": "if x == 5 { }\n",
    "hata_esit_degil": "if x != 5 { }\n",
    "hata_karakter": "var x = 5 @ 3\n",
    "hata_kapanmamis": 'print("merhaba)\n',
    "hata_kacis": 'print("a\\qb")\n',
    "hata_kacis_sonda": 'print("a\\',
    "bos": "",
}


def python_ciktisi(kod):
    try:
        tokenlar = kelimelere_ayir(kod)
    except LexerHatasi as h:
        return ["HATA: " + str(h)]
    satirlar = []
    for t in tokenlar:
        d = t.deger
        if d is None:
            d = ""
        elif isinstance(d, float):
            d = repr(d)
        else:
            d = str(d).replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t")
        satirlar.append(f"{t.tur}\t{d}\t{t.satir}\t{t.sutun}")
    return satirlar


def vash_ciktisi(yol):
    r = subprocess.run([EXE], input=yol + "\n", capture_output=True, text=True, encoding="utf-8")
    satirlar = r.stdout.replace("\r\n", "\n").rstrip("\n").split("\n")
    # ONDALIK sayılar: Vash kodda yazıldığı gibi tutar ("3.140"), Python sayıya çevirir (3.14) → sayı olarak karşılaştır
    duzgun = []
    for s in satirlar:
        p = s.split("\t")
        if len(p) == 4 and p[0] == "ONDALIK":
            p[1] = repr(float(p[1]))
        duzgun.append("\t".join(p))
    return duzgun


def karsilastir(ad, yol):
    with open(yol, encoding="utf-8-sig") as f:
        kod = f.read().replace("\r\n", "\n")
    py = python_ciktisi(kod)
    vs = vash_ciktisi(yol)
    if vs and vs[0].startswith("HATA"):          # hata mesajı birden çok satır olabilir
        vs = ["\n".join(vs)]
    if py == vs:
        return True, len(py)
    for i, (a, b) in enumerate(zip(py, vs)):
        if a != b:
            print(f"  ✗ {ad}: {i + 1}. token farklı\n      Python: {a!r}\n      Vash:   {b!r}")
            break
    else:
        print(f"  ✗ {ad}: token sayısı farklı (Python {len(py)}, Vash {len(vs)})")
    return False, len(py)


if __name__ == "__main__":
    dosyalar = sys.argv[1:] or sorted(glob.glob(os.path.join(KOK, "ornekler", "*.vash")) +
                                      glob.glob(os.path.join(KOK, "vashc", "*.vash")))
    tamam = toplam_token = 0
    hepsi = [(os.path.basename(d), d) for d in dosyalar]
    gecici = tempfile.mkdtemp()
    if not sys.argv[1:]:
        for ad, kod in ZOR_DURUMLAR.items():
            yol = os.path.join(gecici, ad + ".vash")
            with open(yol, "w", encoding="utf-8") as f:
                f.write(kod)
            hepsi.append(("[zor] " + ad, yol))
    for ad, yol in hepsi:
        ok, n = karsilastir(ad, yol)
        tamam += ok
        toplam_token += n
    print(f"\n{tamam}/{len(hepsi)} dosya birebir aynı  ({toplam_token} token karşılaştırıldı)")
    sys.exit(0 if tamam == len(hepsi) else 1)
