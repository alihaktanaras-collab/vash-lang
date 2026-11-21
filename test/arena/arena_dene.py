# arena { } testleri: her program iki kez çalışır.
#   1) olduğu gibi (arena ile)
#   2) "arena {" yerine "if true {" yazılarak (arenasız; aynı anlam)
# İkisinin çıktısı birebir aynı olmalı; ikisinde de bellek raporu "0 tanesi geri verilmedi" demeli
# ve "arena bloğundan kaçan" uyarısı çıkmamalı.
#
# Kullanım:  python test/arena/arena_dene.py

import glob
import os
import re
import subprocess
import sys
import tempfile

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VASH = os.path.join(KOK, "vash.cmd")


def calistir(yol):
    ortam = dict(os.environ, DIL_BELLEK="1")
    # cmd /s /c ""...": boşluklu yollarda tırnaklar bozulmasın
    r = subprocess.run(f'cmd /s /c ""{VASH}" run "{yol}""', capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=ortam, cwd=os.path.dirname(yol))
    return r.returncode, r.stdout.replace("\r\n", "\n"), r.stderr.replace("\r\n", "\n")


def sure_sil(metin):
    return re.sub(r"süre: [0-9.e-]+", "süre: ?", metin)


hepsi_tamam = True
gecici = tempfile.mkdtemp()
for yol in sorted(glob.glob(os.path.join(KOK, "test", "arena", "*.vash"))):
    ad = os.path.basename(yol)
    with open(yol, encoding="utf-8") as f:
        kod = f.read()
    arenasiz = os.path.join(gecici, ad)
    with open(arenasiz, "w", encoding="utf-8") as f:
        f.write(kod.replace("arena {", "if true {"))
    k1, c1, h1 = calistir(yol)
    k2, c2, h2 = calistir(arenasiz)
    sorunlar = []
    if k1 != 0 or k2 != 0:
        sorunlar.append(f"çıkış kodu arena={k1} arenasız={k2}\n{h1[-500:]}")
    if sure_sil(c1) != sure_sil(c2):
        sorunlar.append(f"çıktılar farklı:\n--- arena ile ---\n{c1[-800:]}\n--- arenasız ---\n{c2[-800:]}")
    for etiket, h in (("arena ile", h1), ("arenasız", h2)):
        m = re.search(r"şu an hâlâ (\d+) tanesi geri verilmedi", h)
        if not m or m.group(1) != "0":
            sorunlar.append(f"{etiket}: bellek raporu: {h.strip()[-300:]}")
        if "kaçan" in h:
            sorunlar.append(f"{etiket}: {h.strip()[-300:]}")
    sureler = [re.search(r"süre: ([0-9.e-]+)", c) for c in (c1, c2)]
    hiz = ""
    if all(sureler):
        a, b = float(sureler[0].group(1)), float(sureler[1].group(1))
        hiz = f"   (arena ile {a * 1000:.0f} ms, arenasız {b * 1000:.0f} ms)"
    if sorunlar:
        hepsi_tamam = False
        print(f"  ✗ {ad}")
        for s in sorunlar:
            print("     " + s.replace("\n", "\n     "))
    else:
        print(f"  ✓ {ad}: çıktılar aynı, bellek temiz{hiz}")
sys.exit(0 if hepsi_tamam else 1)
