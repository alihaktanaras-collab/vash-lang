# =====================================================================
#  ARAYÜZ SUNUCUSU
# =====================================================================
#
#  Tarayıcıdaki arayüz (index.html) ile derleyicimiz arasında köprü.
#
#    Tarayıcı  ──(kod)──►  bu sunucu  ──►  lexer.py (ve ileride diğer istasyonlar)
#    Tarayıcı  ◄──(sonuç)──  bu sunucu
#
#  Neden gerekli? Tarayıcı güvenlik nedeniyle bilgisayarındaki Python
#  programlarını doğrudan çalıştıramaz. Bu küçük sunucu onun yerine çalıştırır.
#
#  Başlatmak için:   python arayuz\sunucu.py
#  Sonra tarayıcıda: http://localhost:8765
# =====================================================================

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Klasör yolları
ARAYUZ_KLASORU = os.path.dirname(os.path.abspath(__file__))
PROJE_KLASORU = os.path.dirname(ARAYUZ_KLASORU)
ORNEKLER_KLASORU = os.path.join(PROJE_KLASORU, "ornekler")

# derleyici/ klasöründeki dosyaları "import" edebilmek için yolu ekle
sys.path.insert(0, os.path.join(PROJE_KLASORU, "derleyici"))
from lexer import kelimelere_ayir, LexerHatasi  # noqa: E402
from parser import Parser, ParserHatasi, sozluge_cevir  # noqa: E402
from tipler import TipHatasi, tipleri_kontrol_et  # noqa: E402
from derle import clang_bul  # noqa: E402
from moduller import modulleri_bagla  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402

PORT = 8765

# Asıl derleme işini VASH İLE YAZILMIŞ derleyici yapar (vashc/vash.vash → vashc/vash.exe).
# Python'daki istasyonlar sadece arayüzün "içeriden görünüm" sekmelerini (kelimeler, ağaç, tipler) çizer.
VASH_EXE = os.path.join(PROJE_KLASORU, "vashc", "vash.exe")


def vash_hazirla():
    """vash.exe yoksa (ilk seferde) Python'daki derleyiciyle bir kere üret."""
    if os.path.exists(VASH_EXE):
        return None
    r = subprocess.run([sys.executable, os.path.join(PROJE_KLASORU, "derleyici", "derle.py"), "build",
                        os.path.join(PROJE_KLASORU, "vashc", "vash.vash")],
                       capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    if r.returncode != 0 or not os.path.exists(VASH_EXE):
        return "Vash derleyicisi üretilemedi:\n" + (r.stdout + r.stderr).strip()
    return None


def vash_derleyicisi(kod, komut, klasor):
    """Kodu Vash derleyicisinden geçir. komut: "ir" (LLVM IR'ı döndürür) ya da "build" (.exe üretir).
    Döndürür: (çıktı, hata mesajı ya da None)"""
    hata = vash_hazirla()
    if hata:
        return None, hata
    yol = os.path.join(klasor, "program.vash")
    with open(yol, "w", encoding="utf-8") as f:
        f.write(kod)
    ortam = dict(os.environ,
                 VASH_KOMUT=komut, VASH_DOSYA=yol,
                 VASH_TAM=os.path.join(ORNEKLER_KLASORU, "atolye.vash"),   # import'lar ornekler/ klasöründe aranır
                 VASH_KOK=PROJE_KLASORU)
    try:
        ortam["VASH_CLANG"] = clang_bul()
    except Exception:
        ortam["VASH_CLANG"] = ""
    r = subprocess.run([VASH_EXE], env=ortam, capture_output=True, timeout=60)
    cikti = r.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")
    for onek in ("HATA: ", "ERROR: "):                     # derleyici Türkçe ya da İngilizce olabilir
        if cikti.startswith(onek):
            return None, cikti[len(onek):].rstrip("\n")
    if r.returncode != 0:
        return None, "Vash derleyicisi beklenmedik şekilde durdu:\n" + r.stderr.decode("utf-8", errors="replace")
    return cikti, None


# ---------------------------------------------------------------------
#  Hata mesajından satır ve sütun numarasını çıkar
#  ("Satır 3, sütun 7: ..." → satir=3, sutun=7)
#  Arayüz bununla hatalı satırı kırmızı gösteriyor.
# ---------------------------------------------------------------------
def hata_bilgisi(istasyon, mesaj):
    eslesme = re.search(r"(?:Satır|Line) (\d+)(?:, (?:sütun|column) (\d+))?", mesaj)
    satir = int(eslesme.group(1)) if eslesme else None
    sutun = int(eslesme.group(2)) if eslesme and eslesme.group(2) else None
    return {"istasyon": istasyon, "mesaj": mesaj, "satir": satir, "sutun": sutun}


# ---------------------------------------------------------------------
#  Kodu derleyicinin istasyonlarından geçir, her istasyonun sonucunu topla
# ---------------------------------------------------------------------
def derle(kod, calistir=False, girdi=""):
    sonuc = {
        "asamalar": {},          # her istasyonun ürettiği şey
        "hata": None,            # bir istasyon hata verirse burada
        "cikti": None,           # program çalışınca ekrana yazdıkları
        "calisma_hatasi": None,  # program çalışırken hata olursa (ör: sıfıra bölme)
        "sure_ms": None,         # programın çalışma süresi
    }

    with tempfile.TemporaryDirectory() as klasor:
        # --- Asıl derleme: Vash ile yazılmış derleyici ---
        ir, vash_hatasi = vash_derleyicisi(kod, "ir", klasor)
        if ir is not None:
            sonuc["asamalar"]["llvm"] = ir.rstrip("\n")

        # --- Sekmeler için içeriden görünüm (Python istasyonları; sadece göstermek için) ---
        # Hata varsa hangi istasyonda olduğunu da buradan öğreniyoruz (iki derleyici aynı hatayı verir).
        istasyon = "Vash derleyicisi"
        try:
            istasyon = "1. Lexer"
            tokenlar = kelimelere_ayir(kod)
            sonuc["asamalar"]["lexer"] = [
                {"tur": t.tur, "deger": t.deger, "satir": t.satir, "sutun": t.sutun}
                for t in tokenlar
            ]
            istasyon = "2. Parser"
            agac = Parser(tokenlar).program()
            sonuc["asamalar"]["parser"] = sozluge_cevir(agac)
            istasyon = "3. Tipler"
            agac = modulleri_bagla(agac, ORNEKLER_KLASORU)
            kontrolcu = tipleri_kontrol_et(agac)
            sonuc["asamalar"]["tipler"] = kontrolcu.rapor()
            istasyon = "4. LLVM IR"
        except (LexerHatasi, ParserHatasi, TipHatasi):
            pass

        if vash_hatasi is not None:
            sonuc["hata"] = hata_bilgisi(istasyon, vash_hatasi)
            return sonuc

        # --- Derle ve çalıştır (sadece "Çalıştır"a basılınca; yazarken değil) ---
        if not calistir:
            return sonuc

        exe = os.path.join(klasor, "program.exe")
        _, vash_hatasi = vash_derleyicisi(kod, "build", klasor)
        if vash_hatasi is not None or not os.path.exists(exe):
            sonuc["hata"] = {"istasyon": "4. LLVM IR", "mesaj": vash_hatasi or "program.exe üretilemedi.",
                             "satir": None, "sutun": None}
            return sonuc

        import time
        bas = time.perf_counter()
        try:
            # Arayüzdeki "Program girdisi" kutusu, programa klavyeden yazılmış gibi verilir
            calisma = subprocess.run([exe], capture_output=True, timeout=10,
                                     input=(girdi or "").encode("utf-8"))
        except subprocess.TimeoutExpired:
            sonuc["cikti"] = ""
            sonuc["calisma_hatasi"] = "Program 10 saniyede bitmedi, durduruldu. (Sonsuz döngü olabilir mi?)"
            return sonuc
        sonuc["sure_ms"] = round((time.perf_counter() - bas) * 1000, 1)
        sonuc["cikti"] = calisma.stdout.decode("utf-8", errors="replace")
        if calisma.returncode != 0:
            mesaj = calisma.stderr.decode("utf-8", errors="replace").strip()
            sonuc["calisma_hatasi"] = mesaj or f"Program hata koduyla bitti ({calisma.returncode})."

    return sonuc


# ---------------------------------------------------------------------
#  Tarayıcıdan gelen istekleri karşılayan kısım
# ---------------------------------------------------------------------
class Istekci(BaseHTTPRequestHandler):

    def cevap_gonder(self, kod, icerik, tur="application/json; charset=utf-8"):
        if isinstance(icerik, (dict, list)):
            icerik = json.dumps(icerik, ensure_ascii=False)
        veri = icerik.encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(veri)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(veri)

    # Sayfa ve örnek dosyalar
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(ARAYUZ_KLASORU, "index.html"), encoding="utf-8") as f:
                self.cevap_gonder(200, f.read(), "text/html; charset=utf-8")

        elif self.path == "/ornekler":
            adlar = sorted(a for a in os.listdir(ORNEKLER_KLASORU) if a.endswith(".vash"))
            self.cevap_gonder(200, adlar)

        elif self.path.startswith("/ornek/"):
            ad = os.path.basename(self.path[len("/ornek/"):])  # klasör dışına çıkılmasın
            yol = os.path.join(ORNEKLER_KLASORU, ad)
            if ad.endswith(".vash") and os.path.isfile(yol):
                with open(yol, encoding="utf-8-sig") as f:
                    self.cevap_gonder(200, {"kod": f.read()})
            else:
                self.cevap_gonder(404, {"hata": "örnek bulunamadı"})

        else:
            self.cevap_gonder(404, {"hata": "sayfa bulunamadı"})

    # Kodu derle
    def do_POST(self):
        if self.path != "/derle":
            self.cevap_gonder(404, {"hata": "sayfa bulunamadı"})
            return
        uzunluk = int(self.headers.get("Content-Length", 0))
        istek = json.loads(self.rfile.read(uzunluk).decode("utf-8"))
        self.cevap_gonder(200, derle(istek.get("kod", ""), bool(istek.get("calistir")), istek.get("girdi", "")))

    # Her istekte terminale yazı basmasın
    def log_message(self, *args):
        pass


if __name__ == "__main__":
    # Sadece bu bilgisayardan erişilebilsin (127.0.0.1)
    sunucu = ThreadingHTTPServer(("127.0.0.1", PORT), Istekci)
    print(f"Arayüz hazır: http://localhost:{PORT}")
    print("Durdurmak için Ctrl+C")
    sunucu.serve_forever()
