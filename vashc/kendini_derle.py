# Vash derleyicisi kendini derliyor (self-hosting / bootstrap):
#   1. aşama: uretici_dene.exe   ← Python'daki derleyiciyle derlenmiş Vash derleyicisi
#   2. aşama: vashc2.exe         ← 1. aşamanın, KENDİ kaynak kodunu derleyerek ürettiği derleyici
#   3. aşama: vashc3.exe         ← 2. aşamanın kendini derlemesiyle
# 2. ve 3. aşamanın ürettiği LLVM IR birebir aynıysa derleyici kendi kendine yetiyor demektir.
import os, subprocess, sys, time

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "derleyici"))
from derle import exe_uret  # noqa: E402

KAYNAK = os.path.join(KOK, "vashc", "uretici_dene.vash")
SABLON = os.path.join(KOK, "derleyici")


def ir_al(exe):
    bas = time.perf_counter()
    r = subprocess.run([exe], input=KAYNAK + "\n" + SABLON + "\n", capture_output=True, text=True, encoding="utf-8")
    sure = time.perf_counter() - bas
    if r.returncode != 0 or r.stdout.startswith("HATA"):
        sys.exit("Derlenemedi: " + (r.stdout[:500] or r.stderr[:500]))
    return r.stdout.replace("\r\n", "\n"), sure


onceki = os.path.join(KOK, "vashc", "uretici_dene.exe")
irler = []
for asama in (2, 3):
    ir, sure = ir_al(onceki)
    irler.append(ir)
    yeni = os.path.join(KOK, "vashc", f"vashc{asama}.exe")
    exe_uret(ir, os.path.join(KOK, "vashc", f"vashc{asama}.ll"), yeni)
    print(f"{asama}. aşama: {os.path.basename(onceki)} kendi kaynağını {sure:.2f} sn'de çevirdi "
          f"({ir.count(chr(10))} satır IR) → {os.path.basename(yeni)}")
    onceki = yeni
print("2. ve 3. aşamanın ürettiği IR birebir aynı mı?", irler[0] == irler[1])
