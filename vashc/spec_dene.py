# VASH_SPEC.md'deki her ```vash bloğunu ayrı bir program olarak `vash check --json` ile sınar.
# Belge dilin gerçek hâlinden kopmasın diye: her örnek derlenebilmeli.
#
# Kullanım:  python vashc/spec_dene.py

import json
import os
import re
import subprocess
import sys
import tempfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(KOK, "VASH_SPEC.md")

with open(SPEC, encoding="utf-8") as f:
    metin = f.read()

bloklar = []
baslik = ""
for satir_no, satir in enumerate(metin.split("\n"), 1):
    if satir.startswith("## "):
        baslik = satir[3:]
for m in re.finditer(r"^```vash\n(.*?)^```", metin, re.S | re.M):
    satir = metin[:m.start()].count("\n") + 1
    onceki = [b for b in re.finditer(r"^## (.*)$", metin[:m.start()], re.M)]
    bloklar.append((onceki[-1].group(1) if onceki else "?", satir, m.group(1)))

gecici = tempfile.mkdtemp()
tamam = 0
for i, (baslik, satir, kod) in enumerate(bloklar, 1):
    yol = os.path.join(gecici, f"ornek{i}.vash")
    with open(yol, "w", encoding="utf-8") as f:
        f.write(kod)
    vash = os.path.join(KOK, "vash.cmd")
    r = subprocess.run(f'cmd /s /c ""{vash}" check --json "{yol}""',
                       capture_output=True, text=True, encoding="utf-8")
    try:
        sonuc = json.loads(r.stdout.strip().split("\n")[-1])
    except (ValueError, IndexError):
        print(f"  ✗ {baslik} (VASH_SPEC.md satır {satir}): JSON okunamadı: {r.stdout[:300]!r} {r.stderr[:300]!r}")
        continue
    if sonuc["ok"]:
        tamam += 1
    else:
        h = sonuc["errors"][0]
        print(f"  ✗ {baslik} (VASH_SPEC.md satır {satir}): blok içi satır {h['line']}, sütun {h['column']}: "
              f"{h['message']} {h['details']}")
print(f"\n{tamam}/{len(bloklar)} örnek hatasız derleniyor")
sys.exit(0 if tamam == len(bloklar) else 1)
