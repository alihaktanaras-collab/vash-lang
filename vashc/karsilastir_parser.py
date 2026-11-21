# Vash ile yazılmış ağaç kurucuyu (vashc/parser.vash) Python'dakiyle (derleyici/parser.py) karşılaştırır.
# Python'un 45 çeşit düğümünü, Vash'taki tek tip düğüm biçimine çevirip satır satır karşılaştırır:
#     <girinti>TÜR|DEĞER|EK|SATIR:SÜTUN
#
# Kullanım:  python vashc/karsilastir_parser.py [dosya.vash ...]

import glob
import os
import subprocess
import sys
import tempfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "derleyici"))
from lexer import kelimelere_ayir, LexerHatasi  # noqa: E402
import parser as P  # noqa: E402

EXE = os.path.join(KOK, "vashc", "parser_dene.exe")


def kac(s):
    return str(s).replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t")


def kanonik(d):
    """Python düğümü → (tür, değer, ek, çocuklar, satır, sütun)"""
    def liste(xs):
        return ("[]", "", "", [kanonik(x) for x in xs], 0, 0)

    def ya(x):
        return kanonik(x) if x is not None else ("Bos", "", "", [], 0, 0)

    def isimli(xs):
        return liste_ham([("Isimli", a, "", [kanonik(v)], t.satir, t.sutun) for a, v, t in xs])

    def liste_ham(xs):
        return ("[]", "", "", xs, 0, 0)

    ad = type(d).__name__
    y = d.satir, d.sutun
    if ad == "Program":
        return ("Program", "", "", [kanonik(k) for k in d.komutlar], 0, 0)
    if ad == "DegiskenTanimi":
        return (ad, d.ad, "global" if d.global_mi else "", [ya(d.tip), kanonik(d.deger)], *y)
    if ad == "UseKomutu":
        return (ad, d.ad, "change" if d.degistirebilir else "", [], *y)
    if ad == "Atama":
        return (ad, d.ad, "", [kanonik(d.deger)], *y)
    if ad == "FonksiyonTanimi":
        return (ad, d.ad, "change" if d.degistirir else "", [liste(d.parametreler), ya(d.donus_tipi), liste(d.govde)], *y)
    if ad == "Alan":
        return (ad, d.ad, "", [kanonik(d.tip), ya(d.varsayilan)], *y)
    if ad == "TipTanimi":
        return (ad, d.ad, "", [liste(d.alanlar), liste(d.metotlar)], *y)
    if ad == "ImportKomutu":
        return (ad, d.ad, "", [], *y)
    if ad == "ExternBlok":
        return (ad, d.kutuphane, ",".join(t.deger for t in d.izinler),
                [liste(d.fonksiyonlar), liste_ham([("Izin", t.deger, "", [], t.satir, t.sutun) for t in d.izinler])], *y)
    if ad == "ExternFonksiyon":
        return (ad, d.ad, getattr(d, "c_ad", ""), [liste(d.parametreler), ya(d.donus_tipi)], *y)
    if ad == "EnumTanimi":
        return (ad, d.ad, "", [liste(d.cesitler)], *y)
    if ad == "EnumCesidi":
        return (ad, d.ad, "", [liste(d.alanlar)], *y)
    if ad == "MatchKomutu":
        return (ad, "", "", [kanonik(d.deger), liste(d.durumlar),
                             liste(d.degilse) if d.degilse is not None else ya(None)], *y)
    if ad == "MatchDurumu":
        return (ad, d.cesit, ",".join(d.adlar), [liste(d.govde)], *y)
    if ad == "AlanAtama":
        return (ad, d.alan, "", [kanonik(d.nesne), kanonik(d.deger)], *y)
    if ad == "Parametre":
        return (ad, d.ad, "", [kanonik(d.tip)], *y)
    if ad == "Donus":
        return (ad, "", "", [ya(d.deger)], *y)
    if ad == "IfadeKomutu":
        return (ad, "", "", [kanonik(d.ifade)], *y)
    if ad == "Eger":
        return (ad, "", "", [kanonik(d.kosul), liste(d.govde),
                             liste(d.degilse) if d.degilse is not None else ya(None)], *y)
    if ad == "TekrarSayi":
        return (ad, "", "", [kanonik(d.sayi), liste(d.govde)], *y)
    if ad == "TekrarSurece":
        return (ad, "", "", [kanonik(d.kosul), liste(d.govde)], *y)
    if ad == "TekrarSayac":
        return (ad, d.ad, "", [kanonik(d.bas), kanonik(d.son), ya(d.adim), liste(d.govde)], *y)
    if ad == "WhenKomutu":
        return (ad, "", "later" if d.bekle else "", [kanonik(d.kosul), liste(d.govde)], *y)
    if ad == "Pencere":
        return (ad, "", "", [kanonik(d.baslik), liste(d.ogeler)], *y)
    if ad == "ArayuzOgesi":
        ek = f"{d.hedef or ''},{d.eleman or ''},{d.sira_adi or ''}"
        return (ad, d.tur, ek, [ya(d.metin), liste(d.govde), liste(d.cocuklar), ya(d.kaynak)], *y)
    if ad in ("Dur", "Atla", "Yok"):
        return (ad, "", "", [], *y)
    if ad == "Sayi":
        return (ad, str(d.deger), "", [], *y)
    if ad == "Ondalik":
        return (ad, repr(float(d.deger)), "", [], *y)
    if ad == "Mantiksal":
        return (ad, "true" if d.deger else "false", "", [], *y)
    if ad == "Metin":
        return (ad, d.deger, "", [], *y)
    if ad == "Isim":
        return (ad, d.ad, "", [], *y)
    if ad == "IkiliIslem":
        return (ad, d.isaret, "", [kanonik(d.sol), kanonik(d.sag)], *y)
    if ad == "TekliIslem":
        return (ad, d.isaret, "", [kanonik(d.ifade)], *y)
    if ad == "Cagri":
        return (ad, d.ad, "", [liste(d.argumanlar), isimli(d.isimli)], *y)
    if ad == "Liste":
        return (ad, "", "", [kanonik(x) for x in d.elemanlar], *y)
    if ad == "YedekliDeger":
        return (ad, "", "", [kanonik(d.deger), kanonik(d.yedek)], *y)
    if ad == "SozlukDegeri":
        return (ad, "", "", [liste(d.anahtarlar), liste(d.degerler)], *y)
    if ad == "Aralik":
        return (ad, "", "", [kanonik(d.bas), kanonik(d.son)], *y)
    if ad == "Olcum":
        return (ad, "", "", [liste(d.govde)], *y)
    if ad == "Erisim":
        return (ad, "", "", [kanonik(d.liste), kanonik(d.sira)], *y)
    if ad == "Ozellik":
        return (ad, d.ad, "", [kanonik(d.nesne)], *y)
    if ad == "MetotCagrisi":
        return (ad, d.ad, "", [kanonik(d.nesne), liste(d.argumanlar), ya(getattr(d, "yedek", None)),
                               isimli(getattr(d, "isimli", []))], *y)
    if ad == "ElemanAtama":
        return (ad, "", "", [kanonik(d.liste), kanonik(d.sira), kanonik(d.deger)], *y)
    if ad == "TipAdi":
        return (ad, d.ad, "", [], *y)
    if ad == "ListeTipi":
        return (ad, "", "", [kanonik(d.eleman)], *y)
    if ad == "SecmeliTip":
        return (ad, "", "", [kanonik(d.ic)], *y)
    if ad == "SozlukTipi":
        return (ad, "", "", [kanonik(d.anahtar), kanonik(d.deger)], *y)
    raise ValueError("Bilinmeyen düğüm: " + ad)


# ---------------------------------------------------------------------
#  Yeni özellikler sadece Vash derleyicisinde (TASARIM.md madde 42): Python derleyicisi dondurulduğu için
#  bunları kullanan dosyalar (ve onları içe alanlar) karşılaştırmada atlanır.
# ---------------------------------------------------------------------
import re as _re

_YENI = _re.compile(r"^\s*(arena \{|parallel \{|parallel repeat )|extern[^{]*\{[^}]*^\s*type\b", _re.M)


def yeni_ozellik_mi(yol, _gorulen=None):
    """Bu dosya ya da içe aldığı bir dosya, sadece Vash derleyicisinde olan bir özellik kullanıyor mu?"""
    import os
    gorulen = _gorulen if _gorulen is not None else set()
    if yol in gorulen or not os.path.exists(yol):
        return False
    gorulen.add(yol)
    with open(yol, encoding="utf-8-sig") as f:
        kod = f.read()
    if _YENI.search(kod):
        return True
    for ad in _re.findall(r"^\s*import\s+(\w+)", kod, _re.M):
        yan = os.path.join(os.path.dirname(yol), ad + ".vash")
        std = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "std", ad + ".vash")
        if yeni_ozellik_mi(yan if os.path.exists(yan) else std, gorulen):
            return True
    return False


def satirlar(k, girinti=""):
    tur, deger, ek, cocuklar, s, c = k
    yield f"{girinti}{tur}|{kac(deger)}|{ek}|{s}:{c}"
    for x in cocuklar:
        yield from satirlar(x, girinti + "  ")


def python_ciktisi(kod):
    try:
        agac = P.Parser(kelimelere_ayir(kod)).program()
    except (LexerHatasi, P.ParserHatasi) as h:
        return ["HATA: " + str(h)]
    return list(satirlar(kanonik(agac)))


def vash_ciktisi(yol):
    r = subprocess.run([EXE], input=yol + "\n", capture_output=True, text=True, encoding="utf-8")
    cikti = r.stdout.replace("\r\n", "\n").rstrip("\n")
    if r.returncode != 0 and not cikti.startswith("HATA"):
        return ["ÇÖKTÜ (çıkış kodu " + str(r.returncode) + "): " + r.stderr.strip()[:300]]
    if cikti.startswith("HATA"):
        return [cikti]
    duzgun = []
    for s in cikti.split("\n"):
        bas = len(s) - len(s.lstrip(" "))
        p = s.lstrip(" ").split("|")
        if p[0] == "Ondalik":
            p[1] = repr(float(p[1]))
        duzgun.append(" " * bas + "|".join(p))
    return duzgun


ZOR_DURUMLAR = {
    "oncelik": "var x = 2 + 3 * 4 - -5 // 2 % 3\nvar b = not a and b or c is not d\nvar c = (1 + 2) * 3\n",
    "else_if": "if a > 1 {\n    print(1)\n}\nelse if a < 0 { print(2) } else {\n    print(3)\n}\n",
    "sonekler": 'a[1][2].b.c(1, x: 2, else: 3).d = 5\nl[i] = 3\no.f = "x"\n',
    "aralik": "var r = random(1 to 6)\nvar p = m[2 to 4]\n",
    "tipler": "var a: [int] = []\nvar b: {text: [float]}? = none\nvar c: geometri.Nokta? = none\n",
    "cagrilar": 'f(\n    1,\n    2\n)\nT(ad: "x", yas: 3)\nint("5", else: 0)\n',
    "hata_fazla_kapanis": "}\n",
    "hata_kapanmamis_blok": "if x {\n    print(1)\n",
    "hata_bekle": "var = 5\n",
    "hata_while": "while x { }\n",
    "hata_for": "for i in x { }\n",
    "hata_iki_komut": "var a = 1 var b = 2\n",
    "hata_atama": "f() = 3\n",
    "hata_suslu": "var t = {a * 2}\n",
    "hata_to": "repeat i from 1 { }\n",
    "hata_deger": "var x = )\n",
    "hata_global": "global x = 1\n",
    "hata_match_else": "match x {\n    else { }\n    else { }\n}\n",
    "hata_extern_govde": 'extern "m" {\n    fn f() { }\n}\n',
    "hata_pencere": 'window "A" {\n    print(1)\n}\n',
    "hata_list_in": 'window "A" {\n    list x of l { }\n}\n',
    "bos": "",
}


def karsilastir(ad, yol):
    with open(yol, encoding="utf-8-sig") as f:
        kod = f.read().replace("\r\n", "\n")
    py, vs = python_ciktisi(kod), vash_ciktisi(yol)
    if py == vs:
        return True, len(py)
    for i, (a, b) in enumerate(zip(py, vs)):
        if a != b:
            print(f"  ✗ {ad}: {i + 1}. satır farklı\n      Python: {a!r}\n      Vash:   {b!r}")
            break
    else:
        print(f"  ✗ {ad}: satır sayısı farklı (Python {len(py)}, Vash {len(vs)})")
    return False, len(py)


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
    tamam = toplam = 0
    for ad, yol in hepsi:
        ok, n = karsilastir(ad, yol)
        tamam += ok
        toplam += n
    print(f"\n{tamam}/{len(hepsi)} dosya birebir aynı  ({toplam} ağaç düğümü karşılaştırıldı)")
    sys.exit(0 if tamam == len(hepsi) else 1)
