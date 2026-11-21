# Vash ile yazılmış tip kontrolünü (vashc/tipler.vash) Python'dakiyle (derleyici/tipler.py) karşılaştırır.
# İki şey karşılaştırılır:
#   - Hata varsa: hata mesajı birebir aynı mı?
#   - Hata yoksa: ağacın her düğümüne yazılan tür birebir aynı mı?
# Vash sürümünün henüz desteklemediği şeyleri (type, enum, when, window...) içeren dosyalar atlanır.
#
# Kullanım:  python vashc/karsilastir_tipler.py [dosya.vash ...]

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
from lexer import kelimelere_ayir, LexerHatasi  # noqa: E402
import parser as P  # noqa: E402
from tipler import tipleri_kontrol_et, TipHatasi  # noqa: E402
from karsilastir_parser import kanonik as kanonik_parser, kac  # noqa: E402
from moduller import modulleri_bagla  # noqa: E402

EXE = os.path.join(KOK, "vashc", "tipler_dene.exe")


def tip_of(d):
    if type(d).__name__ == "DegiskenTanimi":
        t = getattr(d, "tip_sonuc", "")
    else:
        t = getattr(d, "tip", "")
    return t if isinstance(t, str) else ""


def kanonik(d):
    """kanonik_parser'ın tür bilgisi eklenmiş hâli: (tür, değer, ek, çocuklar, satır, sütun, tip)"""
    # Önce ağaç kurucunun biçimini al, sonra aynı sırayla gezip türleri ekle
    return _ekle(d, kanonik_parser(d))


def _python_cocuklari(d):
    """kanonik_parser'ın çocuk sırasına karşılık gelen Python düğümleri (liste/None için yer tutucu)."""
    ad = type(d).__name__
    L = lambda xs: ("[]", xs)
    Y = lambda x: x if x is not None else ("Bos",)
    if ad == "Program": return list(d.komutlar)
    if ad == "DegiskenTanimi": return [Y(d.tip), d.deger]
    if ad == "Atama": return [d.deger]
    if ad == "FonksiyonTanimi": return [L(d.parametreler), Y(d.donus_tipi), L(d.govde)]
    if ad == "Parametre": return [d.tip]
    if ad == "Donus": return [Y(d.deger)]
    if ad == "IfadeKomutu": return [d.ifade]
    if ad == "Eger": return [d.kosul, L(d.govde), L(d.degilse) if d.degilse is not None else ("Bos",)]
    if ad == "TekrarSayi": return [d.sayi, L(d.govde)]
    if ad == "TekrarSurece": return [d.kosul, L(d.govde)]
    if ad == "TekrarSayac": return [d.bas, d.son, Y(d.adim), L(d.govde)]
    if ad == "IkiliIslem": return [d.sol, d.sag]
    if ad == "TekliIslem": return [d.ifade]
    if ad == "Cagri": return [L(d.argumanlar), ("[]", [("Isimli", v) for _, v, _ in d.isimli])]
    if ad == "Liste": return list(d.elemanlar)
    if ad == "YedekliDeger": return [d.deger, d.yedek]
    if ad == "SozlukDegeri": return [L(d.anahtarlar), L(d.degerler)]
    if ad == "Aralik": return [d.bas, d.son]
    if ad == "Olcum": return [L(d.govde)]
    if ad == "Erisim": return [d.liste, d.sira]
    if ad == "Ozellik": return [d.nesne]
    if ad == "MetotCagrisi":
        return [d.nesne, L(d.argumanlar), Y(getattr(d, "yedek", None)),
                ("[]", [("Isimli", v) for _, v, _ in getattr(d, "isimli", [])])]
    if ad == "ElemanAtama": return [d.liste, d.sira, d.deger]
    if ad == "ListeTipi": return [d.eleman]
    if ad == "SecmeliTip": return [d.ic]
    if ad == "SozlukTipi": return [d.anahtar, d.deger]
    if ad == "Alan": return [d.tip, Y(d.varsayilan)]
    if ad == "TipTanimi": return [L(d.alanlar), L(d.metotlar)]
    if ad == "ExternBlok": return [L(d.fonksiyonlar), ("[]", [("Bos",) for _ in d.izinler])]
    if ad == "ExternFonksiyon": return [L(d.parametreler), Y(d.donus_tipi)]
    if ad == "EnumTanimi": return [L(d.cesitler)]
    if ad == "EnumCesidi": return [L(d.alanlar)]
    if ad == "MatchKomutu":
        return [d.deger, L(d.durumlar), L(d.degilse) if d.degilse is not None else ("Bos",)]
    if ad == "MatchDurumu": return [L(d.govde)]
    if ad == "AlanAtama": return [d.nesne, d.deger]
    if ad == "WhenKomutu": return [d.kosul, L(d.govde)]
    if ad == "Pencere": return [d.baslik, L(d.ogeler)]
    if ad == "ArayuzOgesi": return [Y(d.metin), L(d.govde), L(d.cocuklar), Y(d.kaynak)]
    return []


def _ekle(d, k):
    """k = kanonik_parser çıktısı (tur, deger, ek, cocuklar, s, c); d = karşılık gelen Python düğümü"""
    tur, deger, ek, cocuklar, s, c = k
    if isinstance(d, tuple):                      # yer tutucu: ("Bos",) / ("[]", liste) / ("Isimli", deger)
        if d[0] == "[]":
            return (tur, deger, ek, [_ekle(x, kx) for x, kx in zip(d[1], cocuklar)], s, c, "")
        if d[0] == "Isimli":
            return (tur, deger, ek, [_ekle(d[1], cocuklar[0])], s, c, "")
        return (tur, deger, ek, [], s, c, "")
    ad = type(d).__name__
    if ad == "Metin":
        # Tip kontrolünden sonra metin parçalarına ayrılmış olur: sabit parçalar + {…} içindeki ifadeler
        parcalar = []
        for pt, p in getattr(d, "parcalar", []):
            if pt == "metin":
                parcalar.append(("Parca", p, "", [], 0, 0, ""))
            else:
                parcalar.append(kanonik(p))
        return ("Metin", d.deger, ek, parcalar, s, c, tip_of(d))
    if ad == "ElemanAtama" and getattr(d, "sozluk", False):
        ek = "sozluk"                             # Python bunu düğüme 'sozluk = True' diye not ediyor
    pc = _python_cocuklari(d)
    return (tur, deger, ek, [_ekle(x, kx) for x, kx in zip(pc, cocuklar)], s, c, tip_of(d))


def satirlar(k, girinti=""):
    tur, deger, ek, cocuklar, s, c, tip = k
    yield f"{girinti}{tur}|{kac(deger)}|{ek}|{s}:{c}|{tip}"
    for x in cocuklar:
        yield from satirlar(x, girinti + "  ")


def python_ciktisi(kod, klasor=""):
    try:
        agac = P.Parser(kelimelere_ayir(kod)).program()
        agac = modulleri_bagla(agac, klasor)
        tipleri_kontrol_et(agac)
    except (LexerHatasi, P.ParserHatasi, TipHatasi) as h:
        return ["HATA: " + str(h)]
    return list(satirlar(kanonik(agac)))


def vash_ciktisi(yol):
    r = subprocess.run([EXE], input=yol + "\n", capture_output=True, text=True, encoding="utf-8")
    cikti = r.stdout.replace("\r\n", "\n").rstrip("\n")
    if r.returncode != 0 and not cikti.startswith(("HATA", "DESTEKLENMIYOR")):
        return ["ÇÖKTÜ (çıkış kodu " + str(r.returncode) + "): " + (r.stderr.strip() or cikti[-300:])[:400]]
    if cikti.startswith(("HATA", "DESTEKLENMIYOR")):
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
    "tamam_temel": 'var a = 5\nvar b: float = a\nvar c = a / 2 + b\nvar d = "x {a} y {c * 2} z"\nprint(a, b, c, d)\n',
    "tamam_fonksiyon": 'fn kare(x: int) -> int {\n    return x * x\n}\nfn yaz(m: text) {\n    print(m)\n}\nyaz("{kare(3)}")\n',
    "tamam_kontrol": 'fn bul(l: [text], a: text) -> text? {\n    repeat i from 1 to l.length {\n        if l[i] is a { return l[i] }\n    }\n    return none\n}\nvar s = bul(["a"], "a")\nif s is none {\n    print("yok")\n} else {\n    print(s.length)\n}\n',
    "tamam_sozluk": 'var n = {"a": 1, "b": 2.5}\nn["c"] = 3\nprint(n.get("x", else: 0.0), n.keys(), n.has("a"))\nn.remove("a")\n',
    "tamam_hazir": 'var x: int = input("sayı: ")\nvar r = random(1 to 6)\nvar f = random(1.0 to 2)\nvar l = [1, 2]\nvar e = random(l)\nvar t = time()\nvar i = int("5", else: 0)\nvar c = code("A")\nvar h = char(66)\n',
    "tamam_olcum": 'var s = measure {\n    var k = 0\n    repeat 3 { k = k + 1 }\n}\nprint(s)\n',
    "hata_tip": 'var a = 5\na = "x"\n',
    "hata_yok": "print(toplm)\nvar toplam = 1\n",
    "hata_oneri": "var toplam = 1\nprint(toplm)\n",
    "hata_fonksiyon_disi": "var a = 1\nfn f() {\n    print(a)\n}\n",
    "hata_global": "global var g = 1\nfn f() {\n    g = 2\n}\n",
    "hata_donus": "fn f() -> int {\n    if true { return 1 }\n}\n",
    "hata_metin": 'var a = [1]\nprint("{a}")\n',
    "hata_metin_kapali": 'print("{a")\n',
    "hata_metin_bos": 'print("{ }")\n',
    "hata_metin_tek": 'var a = 1\nprint("{a a}")\n',
    "hata_plus": 'var a = "x" + "y"\n',
    "hata_karsilastir": 'var a = 1 is "x"\n',
    "hata_none": 'fn f() -> text? {\n    return none\n}\nvar x = f()\nprint(x.length)\n',
    "hata_izin": 'fn f() -> text? {\n    return read_file("a")\n}\n',
    "hata_izin_dolayli": 'fn f() {\n    use files\n    write_file("a", "b")\n}\nfn g() {\n    f()\n}\n',
    "hata_stop": "stop\n",
    "hata_sayac": "repeat i from 1 to 3 {\n    i = 2\n}\n",
    "hata_blok": "if true {\n    var a = 1\n}\nprint(a)\n",
    "hata_liste_karisik": 'var l = [1, "a"]\n',
    "hata_bos_liste": "var l = []\n",
    "hata_metot": 'var m = "x"\nprint(m.uper())\n',
    "hata_buyuk": "var x = 99999999999999999999\n",
    "hata_step0": "repeat i from 1 to 3 step 0 { }\n",
    "hata_ifade_komutu": "var a = 1\na + 1\n",
    "hata_use": "var sayac = 0\nfn f() {\n    use sayaç\n}\n",
    # --- ikinci yarı ---
    "tamam_tip": 'type Kisi {\n    ad: text\n    yas: int = 0\n    fn change buyu() {\n        yas = yas + 1\n    }\n    fn yazi() -> text {\n        return "{ad} {yas}"\n    }\n}\nvar k = Kisi(ad: "Ali")\nk.buyu()\nk.yas = 5\nprint(k.yazi(), k.ad, k)\n',
    "tamam_enum": 'enum Sekil {\n    Kare(kenar: float)\n    Daire(r: float)\n    Bos\n}\nfn alan(s: Sekil) -> float {\n    match s {\n        Kare(k) { return k * k }\n        Daire(r) { return 3.14 * r * r }\n        Bos { return 0.0 }\n    }\n}\nprint(alan(Sekil.Kare(kenar: 2.0)), alan(Sekil.Bos))\n',
    "tamam_when": 'var a = 0\nvar b = 1\nwhen a > b {\n    print("büyük")\n}\na = 5\n',
    "tamam_pencere": 'var ad = ""\nvar l = ["a", "b"]\nvar s = 0\nwindow "Deneme" {\n    textbox "Ad" -> ad\n    label "Merhaba {ad}"\n    list x, i in l -> s {\n        label "{i}. {x}"\n    }\n    button "Ekle" {\n        l.add(ad)\n    }\n}\n',
    "tamam_extern": 'extern "m" needs system {\n    fn sqrt(x: float) -> float\n    fn abs(x: i32) -> i32\n}\nfn f() {\n    use system\n    print(sqrt(2.0), abs(3))\n}\n',
    "hata_tip_alan": 'type K {\n    a: int\n}\nvar k = K(a: 1)\nprint(k.b)\n',
    "hata_tip_eksik": 'type K {\n    a: int\n    b: text\n}\nvar k = K(a: 1)\n',
    "hata_tip_metot": 'type K {\n    a: int\n    fn f() {\n        a = 2\n    }\n}\n',
    "hata_tip_kendi": 'type K {\n    a: K\n}\n',
    "hata_tip_degismez": 'type K {\n    a: int\n    fn change f() { a = 1 }\n}\nfn g(k: K) {\n    k.f()\n}\n',
    "hata_enum_eksik": 'enum E {\n    A\n    B\n}\nvar e = E.A\nmatch e {\n    A { print(1) }\n}\n',
    "hata_enum_else": 'enum E {\n    A\n}\nvar e = E.A\nmatch e {\n    A { print(1) }\n    else { print(2) }\n}\n',
    "hata_enum_cesit": 'enum E {\n    A\n}\nvar e = E.Ab\n',
    "hata_enum_alan": 'enum E {\n    A(x: int)\n}\nvar e = E.A\n',
    "hata_enum_is": 'enum E {\n    A\n}\nvar e = E.A\nprint(e is E.A)\n',
    "hata_match_ad": 'enum E {\n    A(x: int, y: int)\n}\nvar e = E.A(x: 1, y: 2)\nmatch e {\n    A(x) { print(x) }\n}\n',
    "hata_when_sabit": 'when 1 > 2 {\n    print(1)\n}\n',
    "hata_pencere_iki": 'window "A" {\n    label "x"\n}\nwindow "B" {\n    label "y"\n}\n',
    "hata_pencere_tip": 'var a = 1\nwindow "A" {\n    checkbox "x" -> a\n}\n',
    "hata_extern_tip": 'extern "m" {\n    fn f(x: [int])\n}\n',
    "hata_extern_izin": 'extern "m" needs system {\n    fn f()\n}\nf()\n',
    "hata_type_icerde": 'fn f() {\n    print(1)\n}\nif true {\n    type K {\n        a: int\n    }\n}\n',
}


# extern'de kullanılabilen tipler listesi artık u8, f32 ve C yapılarını da sayıyor (TASARIM.md madde 45)
BEKLENEN_FARKLAR = {"[zor] hata_extern_tip", "[modül] mod_hata_yok"}   # ikincisi: mesaj artık standart kütüphaneyi de anıyor


def karsilastir(ad, yol):
    with open(yol, encoding="utf-8-sig") as f:
        kod = f.read().replace("\r\n", "\n")
    vs = vash_ciktisi(yol)
    if vs and vs[0].startswith("DESTEKLENMIYOR"):
        return None, 0
    py = python_ciktisi(kod, os.path.dirname(yol))
    if vs and vs[0].startswith("HATA"):
        vs = ["\n".join(vs)]
    # Bilerek değişen mesajlar (Vash derleyicisi yeni özellik aldığı için); iki taraf da hata veriyorsa geçer
    if ad in BEKLENEN_FARKLAR and py and vs and py[0].startswith("HATA") and vs[0].startswith("HATA"):
        return True, len(py)
    if py == vs:
        return True, len(py)
    for i, (a, b) in enumerate(zip(py, vs)):
        if a != b:
            print(f"  ✗ {ad}: {i + 1}. satır farklı\n      Python: {a!r}\n      Vash:   {b!r}")
            break
    else:
        print(f"  ✗ {ad}: satır sayısı farklı (Python {len(py)}, Vash {len(vs)})")
    return False, len(py)


# Birden çok dosyalı durumlar: her biri kendi klasöründe; ana dosya "ana.vash"
G = 'global var SAYI = 1\ntype Nokta {\n    x: float\n}\nenum Renk {\n    Kirmizi\n    Mavi\n}\nfn iki_kat(a: int) -> int {\n    return a * 2\n}\nfn _gizli() -> int {\n    return 1\n}\n'
ZOR_MODULLER = {
    "mod_tamam": {"ana.vash": 'import m\nvar n = m.Nokta(x: 1.0)\nvar r = m.Renk.Mavi\nprint(m.iki_kat(m.SAYI), n.x, "{m.iki_kat(3)} {m.SAYI}")\nfn f(p: m.Nokta) -> m.Renk {\n    return m.Renk.Kirmizi\n}\n',
                  "m.vash": G + 'fn artir() {\n    use change SAYI\n    SAYI = SAYI + _gizli()\n    var k = Nokta(x: 2.0)\n    print("{iki_kat(SAYI)} {k.x}")\n}\n'},
    "mod_zincir": {"ana.vash": 'import a\nprint(a.f())\n', "a.vash": 'import b\nfn f() -> int {\n    return b.g() + 1\n}\n',
                   "b.vash": 'import a\nfn g() -> int {\n    return 41\n}\n'},
    "mod_extern": {"ana.vash": 'import c\nprint(c.kok(2.0))\n', "c.vash": 'extern "m" {\n    fn sqrt(x: float) -> float\n}\nfn kok(x: float) -> float {\n    return sqrt(x)\n}\n'},
    "mod_hata_yok": {"ana.vash": 'import yokki\n'},
    "mod_hata_gizli": {"ana.vash": 'import m\nprint(m._gizli())\n', "m.vash": G},
    "mod_hata_oneri": {"ana.vash": 'import m\nprint(m.iki_kt(1))\n', "m.vash": G},
    "mod_hata_kod": {"ana.vash": 'import k\n', "k.vash": 'fn f() { }\nprint(1)\n'},
    "mod_hata_ic": {"ana.vash": 'if true {\n    import m\n}\n', "m.vash": G},
    "mod_hata_tip": {"ana.vash": 'import m\nvar n: m.Nokt? = none\n', "m.vash": G},
    "mod_hata_atama": {"ana.vash": 'import m\nm.SAYI = 3\n', "m.vash": G},
    "mod_hata_ad": {"ana.vash": 'import m\nvar m = 1\n', "m.vash": G},
    "mod_hata_cagri": {"ana.vash": 'import m\nprint(m.SAYI())\n', "m.vash": G},
    "mod_hata_parantez": {"ana.vash": 'import m\nprint(m.iki_kat)\n', "m.vash": G},
    "mod_hata_use": {"ana.vash": 'import m\n', "m.vash": 'fn f() {\n    use change yok\n}\n'},
    "mod_hata_yerel": {"ana.vash": 'import m\n', "m.vash": G + 'fn f() {\n    var SAYI = 2\n}\n'},
    "mod_hata_icerde_tip": {"ana.vash": 'import m\nm.iki_kat("x")\n', "m.vash": G},
    "mod_hata_modulde_tip": {"ana.vash": 'import m\n', "m.vash": 'fn f() -> int {\n    return "x"\n}\n'},
    "mod_hata_metin": {"ana.vash": 'import m\n', "m.vash": G + 'fn f() {\n    print("{iki_kat(true)}")\n}\n'},
    "mod_hata_metin_gizli": {"ana.vash": 'import m\nprint("{m._gizli()}")\n', "m.vash": G},
    "mod_hata_sozdizimi": {"ana.vash": 'import m\n', "m.vash": 'fn f( {\n}\n'},
}


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
    tamam = atlanan = toplam = 0
    for ad, yol in hepsi:
        ok, n = karsilastir(ad, yol)
        if ok is None:
            atlanan += 1
            continue
        tamam += ok
        toplam += n
    denenen = len(hepsi) - atlanan
    print(f"\n{tamam}/{denenen} dosya birebir aynı  ({toplam} satır karşılaştırıldı; "
          f"{atlanan} dosya henüz desteklenmeyen şeyler içerdiği için atlandı)")
    sys.exit(0 if tamam == denenen else 1)
