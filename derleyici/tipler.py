# =====================================================================
#  3. İSTASYON: TİP KONTROLÜ (Anlam Denetçisi)
# =====================================================================
#
#  Parser kodun YAPISININ doğru olduğuna baktı ("cümle dilbilgisine uygun mu?").
#  Bu istasyon kodun ANLAMININ doğru olduğuna bakar ("cümle mantıklı mı?").
#
#  Türkçede "Elma kitabı içti." cümlesinin dilbilgisi doğrudur ama anlamsızdır.
#  Kodda da öyle:
#
#      var x = 5
#      x = "merhaba"      ← yapı doğru, ama x bir sayı, metin olamaz!
#      print(toplm)       ← yapı doğru, ama "toplm" diye bir şey yok!
#
#  Bu istasyon ağacı baştan sona gezer ve her şeyin TİPİNİ bulur:
#    - Tip yazılmamışsa tahmin eder:   var x = 5   →  x: int
#    - Kurallara uymayan her şeyi yakalar ve anlaşılır bir hata verir.
#
#  Neden önemli? C++ hızının sırrı bu: program ÇALIŞMADAN ÖNCE her şeyin
#  tipi bilinirse, makine kodu "bu bir sayı mı, metin mi?" diye her seferinde
#  kontrol etmek zorunda kalmaz. Python ise bunu çalışırken sürekli yapar,
#  bu yüzden yavaştır.
#
#  KAPSAM (scope): Hangi değişken nerede görülebilir?
#    Her fonksiyonun kendi "kapsamı" (görme alanı) vardır. Fonksiyon dışarıyı
#    göremez; dışarıdaki bir değişkeni "use" ile çağırması gerekir.
#    "global var" ile oluşturulanlar ise her yerden okunabilir. (TASARIM.md madde 15)
# =====================================================================

import difflib
import re

from parser import (
    Program, DegiskenTanimi, UseKomutu, Atama, FonksiyonTanimi, Donus, IfadeKomutu,
    Eger, TekrarSayi, TekrarSurece, TekrarSayac, Dur, Atla,
    Sayi, Ondalik, Mantiksal, Metin, Isim, IkiliIslem, TekliIslem, Cagri, Liste,
    Erisim, Ozellik, MetotCagrisi, ElemanAtama, WhenKomutu, Dugum,
    TipTanimi, AlanAtama, Aralik, Olcum, Pencere, ArayuzOgesi,
    TipAdi, ListeTipi, SozlukTipi, SozlukDegeri, EnumTanimi, MatchKomutu,
    SecmeliTip, Yok, YedekliDeger, ExternBlok,
)


def adlari_topla(d, adlar=None):
    """Bir ağaç parçasında geçen bütün değişken adlarını topla
    (x, x = ..., "Merhaba {x}" ...). when'in neyi izlediğini bulmak için."""
    if adlar is None:
        adlar = set()
    if isinstance(d, (list, tuple)):
        for x in d:
            adlari_topla(x, adlar)
        return adlar
    if not isinstance(d, Dugum):
        return adlar
    if isinstance(d, (Isim, Atama)):
        adlar.add(d.ad)
    if isinstance(d, Metin):
        for tur, parca in getattr(d, "parcalar", []):
            if tur == "ifade":
                adlari_topla(parca, adlar)
    for deger in vars(d).values():
        if isinstance(deger, (Dugum, list, tuple)):
            adlari_topla(deger, adlar)
    return adlar


class TipHatasi(Exception):
    pass


# Kodda yazılabilen tip adları → derleyicinin içinde kullandığı ad
TIP_ADLARI = {
    "int": "int", "integer": "int",
    "float": "float",
    "text": "text",
    "bool": "bool",
    "ptr": "ptr",           # C'nin verdiği bir "tutamaç" (açık dosya gibi); içine bakılmaz, sadece geri verilir
}

# İZİNLER: bir fonksiyon dış dünyanın neresine dokunuyor? (use files / extern ... needs files)
IZINLER = {
    "files":  "dosyalara dokunuyor",
    "net":    "internete bağlanıyor",
    "system": "bilgisayarda program çalıştırıyor ya da sistem bilgisi okuyor",
    "screen": "ekrana pencere ya da grafik çiziyor",
    "sound":  "ses çalıyor",
    "time":   "saati okuyor ya da bekliyor",
}


def izinleri_topla(d, izinler=None):
    """Bir fonksiyonun gövdesindeki 'use files' gibi izin satırlarını bul (iç bloklar dahil)."""
    if izinler is None:
        izinler = set()
    if isinstance(d, (list, tuple)):
        for x in d:
            izinleri_topla(x, izinler)
        return izinler
    if not isinstance(d, Dugum):
        return izinler
    if isinstance(d, UseKomutu) and d.ad in IZINLER:
        izinler.add(d.ad)
    for deger in vars(d).values():
        if isinstance(deger, (Dugum, list, tuple)):
            izinleri_topla(deger, izinler)
    return izinler


# extern fonksiyonlarında kullanılabilen tipler: Vash'taki karşılığı ve C'deki hâli
#   i32 → C'nin küçük tam sayısı (int). Vash tarafında normal bir int gibi görünür.
EXTERN_TIPLERI = {"int": "i64", "i32": "i32", "float": "double", "bool": "i32", "text": "ptr", "ptr": "ptr"}

# dilin hazır gelen fonksiyonları
YERLESIK_FONKSIYONLAR = {"print", "write", "input", "random", "time", "int", "float", "text",
                         "read_file", "read_lines", "write_file", "append_file", "file_exists",
                         "code", "char"}

# Dosya fonksiyonları: (aldıkları, döndürdükleri). Hepsi 'files' izni ister.
DOSYA_FONKSIYONLARI = {
    "read_file":   (["text"], "text?"),            # okunamazsa none
    "read_lines":  (["text"], "[text]?"),
    "write_file":  (["text", "text"], "bool"),     # oldu mu?
    "append_file": (["text", "text"], "bool"),
    "file_exists": (["text"], "bool"),
}

# Metinlerin işleri: ad → (kabul edilen parametre listeleri, dönüş tipi)
METIN_METOTLARI = {
    "contains":    ([["text"]], "bool"),
    "starts_with": ([["text"]], "bool"),
    "ends_with":   ([["text"]], "bool"),
    "split":       ([["text"], []], "[text]"),      # split(",")  /  split() → kelimeler
    "trim":        ([[]], "text"),
    "replace":     ([["text", "text"]], "text"),
    "upper":       ([[], ["text"]], "text"),        # upper()  /  upper("tr")
    "lower":       ([[], ["text"]], "text"),
    "is_digit":    ([[]], "bool"),                  # bütün harfleri rakam mı?
    "is_letter":   ([[]], "bool"),                  # bütün harfleri harf mi? (Türkçe dahil)
    "is_space":    ([[]], "bool"),                  # bütün harfleri boşluk mu?
}
YAZDIRILABILIR = {"int", "float", "text", "bool"}
BOS_LISTE = "[?]"     # tipi henüz bilinmeyen boş liste: []
BOS_SOZLUK = "{?}"    # tipi henüz bilinmeyen boş sözlük: {}
YOK = "none"          # none'ın kendi tipi (her T?'ye verilebilir)


def secmeli_mi(t):
    return (t or "").endswith("?") and t != BOS_LISTE and t != BOS_SOZLUK
SOZLUK_ANAHTARLARI = ("text", "int")
SOZLUK_METOTLARI = ["get", "has", "remove", "keys", "values"]


def sozluk_mu(t):
    return (t or "").startswith("{")


def sozluk_parcalari(t):
    """"{text:[int]}" → ("text", "[int]")   (anahtar hep text ya da int; içinde ':' olmaz)"""
    i = t.index(":")
    return t[1:i], t[i + 1:-1]
HICBIR_SEY = "void"   # değer döndürmeyen fonksiyonun "tipi"


# ---------------------------------------------------------------------
#  Yardımcılar
# ---------------------------------------------------------------------
def _dosya_yaz(d, dosya):
    """Bir ağaç parçasındaki bütün düğümlere hangi dosyadan geldiğini yaz."""
    if isinstance(d, (list, tuple)):
        for x in d:
            _dosya_yaz(x, dosya)
        return
    if not isinstance(d, Dugum):
        return
    d.dosya = dosya
    for v in vars(d).values():
        if isinstance(v, (Dugum, list, tuple)):
            _dosya_yaz(v, dosya)


def hata(dugum, mesaj):
    yer = f"{dugum.dosya}, " if getattr(dugum, "dosya", None) else ""     # başka bir dosyadaysa adı
    raise TipHatasi(f"{yer}Satır {dugum.satir}, sütun {dugum.sutun}: {mesaj}")


def oneri(ad, adaylar):
    """Yazım hatası mı? En yakın ismi bul: 'topalm' → 'toplam'"""
    yakin = difflib.get_close_matches(ad, list(adaylar), n=1, cutoff=0.6)
    return f"\n   Bunu mu demek istedin: '{yakin[0]}'?" if yakin else ""


def tip_aciklama(tip):
    """Hata mesajlarında tipi yeni başlayanın anlayacağı şekilde yaz."""
    aciklamalar = {
        "int": "int (tam sayı)", "float": "float (ondalık sayı)",
        "text": "text (metin)", "bool": "bool (doğru/yanlış)",
        HICBIR_SEY: "hiçbir değer", BOS_LISTE: "boş liste", BOS_SOZLUK: "boş sözlük",
    }
    if tip in aciklamalar:
        return aciklamalar[tip]
    if tip == YOK:
        return "none (yok)"
    if secmeli_mi(tip):
        return f"{tip} (yok olabilir; önce 'if x is not none' ile kontrol et)"
    if tip.startswith("["):
        return f"{tip} (liste)"
    if sozluk_mu(tip):
        return f"{tip} (sözlük)"
    return tip


def sayisal_mi(tip):
    return tip in ("int", "float")


def izlenen_var_mi(adlar):
    return len(adlar) > 0


def her_zaman_doner_mu(komutlar):
    """Bu komutlar, hangi yoldan gidilirse gidilsin, bir 'return'e ulaşıyor mu?
       - Doğrudan bir return varsa: evet
       - if VE else'in ikisi de her zaman dönüyorsa: evet
       - Döngüler sayılmaz (hiç çalışmayabilirler)"""
    for k in komutlar:
        if isinstance(k, Donus):
            return True
        if isinstance(k, Eger) and k.degilse is not None:
            if her_zaman_doner_mu(k.govde) and her_zaman_doner_mu(k.degilse):
                return True
        if isinstance(k, MatchKomutu) and getattr(k, "tam", False):     # bütün çeşitler yazılmış
            if all(her_zaman_doner_mu(d.govde) for d in k.durumlar) and \
                    (k.degilse is None or her_zaman_doner_mu(k.degilse)):
                return True
    return False


# ---------------------------------------------------------------------
#  Bilgi kutuları
# ---------------------------------------------------------------------
class Degisken:
    """Bir değişken hakkında bildiklerimiz."""
    def __init__(self, ad, tip, tur, satir):
        self.ad = ad
        self.tip = tip
        self.tur = tur      # "ana", "yerel", "parametre", "global", "dis-okur", "dis-degistirir", "sayac"
        self.satir = satir
        self.blokta = False  # bir if/repeat bloğunun içinde mi oluşturuldu?


class Fonksiyon:
    def __init__(self, ad, parametreler, donus, satir, degistirir=False, tip_adi=None):
        self.ad = ad
        self.parametreler = parametreler    # [(ad, tip), ...]
        self.donus = donus                  # tip ya da "void"
        self.satir = satir
        self.degistirir = degistirir        # metotlarda: "fn change ..." mi?
        self.tip_adi = tip_adi              # metotlarda: hangi tipin metodu?


class TipBilgisi:
    """Bir 'type' hakkında bildiklerimiz."""
    def __init__(self, ad, dugum):
        self.ad = ad
        self.dugum = dugum
        self.alanlar = {}                   # ad → (tip, Alan düğümü)   (sıra korunur)
        self.metotlar = {}                  # ad → Fonksiyon

    def alan_sirasi(self, ad):
        return list(self.alanlar).index(ad)


class EnumBilgisi:
    """Bir 'enum' hakkında bildiklerimiz."""
    def __init__(self, ad, dugum):
        self.ad = ad
        self.dugum = dugum
        self.cesitler = {}                  # çeşit adı → {alan adı: tip}  (sıra korunur)

    def sira(self, cesit):
        return list(self.cesitler).index(cesit)


class Kapsam:
    """Bir görme alanı: içinde hangi değişkenler var?

    Kapsamlar iç içe olabilir: bir fonksiyonun kapsamının içinde bir if
    bloğunun kapsamı, onun içinde bir repeat bloğunun kapsamı...
    İçerideki kapsam dışarıdakileri görür, dışarıdaki içeridekileri GÖRMEZ."""
    def __init__(self, ad, ust=None):
        self.ad = ad
        self.ust = ust                          # bir dıştaki kapsam (yoksa None)
        self.degiskenler = {}                   # ad → Degisken (sadece bu bloktakiler)
        self.kok = ust.kok if ust else self     # fonksiyonun (ya da ana programın) en dış kapsamı
        self.tum = []                           # (sadece kökte) bütün değişkenler, rapor için

    def ekle(self, d):
        d.blokta = self.ust is not None
        self.degiskenler[d.ad] = d
        self.kok.tum.append(d)

    def ara(self, ad):
        """Bu kapsamda ya da dışındaki kapsamlarda (fonksiyonun sınırına kadar) ara."""
        k = self
        while k:
            if ad in k.degiskenler:
                return k.degiskenler[ad]
            k = k.ust
        return None


# =====================================================================
#  TİP KONTROLCÜSÜ
# =====================================================================
class TipKontrolcu:

    def __init__(self):
        self.fonksiyonlar = {}                  # ad → Fonksiyon
        self.tipler = {}                        # ad → TipBilgisi (kendi tipler)
        self.enumlar = {}                       # ad → EnumBilgisi
        self.tip_icinde = None                  # şu an hangi tipin metodundayız?
        self.ana_kapsam = Kapsam("Ana program")
        self.kapsamlar = [self.ana_kapsam]      # arayüzde göstermek için
        self.kapsam = self.ana_kapsam           # şu an içinde bulunduğumuz kapsam
        self.fonksiyon_icinde = None            # şu an hangi fonksiyonun içindeyiz?
        self.ust_tanimlar = {}                  # ana programdaki bütün "var"lar: ad → satır
        self.dongu_derinligi = 0                # kaç döngünün içindeyiz? (stop/skip için)
        self.when_derinligi = 0                 # kaç when bloğunun içindeyiz? (return için)
        self.olcum_derinligi = 0                # kaç measure bloğunun içindeyiz? (return için)
        self.kapanan_bloklar = {}               # bloğu bitmiş değişkenler: ad → satır (iyi hata mesajı için)

    # =================================================================
    #  ANA AKIŞ: 3 tur
    # =================================================================
    def kontrol_et(self, program):
        # 0. TUR: Kendi tipleri topla (adlarını, sonra alanlarını ve metotlarının imzalarını).
        #    Böylece tipler birbirini ve fonksiyonlar tipleri sırası fark etmeden kullanabilir.
        tip_tanimlari = [k for k in program.komutlar if isinstance(k, TipTanimi)]
        for t in tip_tanimlari:
            if t.ad in TIP_ADLARI:
                hata(t, f"'{t.ad}' dilin hazır bir tipi, aynı adla yeni tip tanımlanamaz.")
            if t.ad in self.tipler:
                hata(t, f"'{t.ad}' adında bir tip zaten var (satır {self.tipler[t.ad].dugum.satir}).")
            self.tipler[t.ad] = TipBilgisi(t.ad, t)
        enum_tanimlari = [k for k in program.komutlar if isinstance(k, EnumTanimi)]
        for t in enum_tanimlari:
            if t.ad in TIP_ADLARI or t.ad in self.tipler or t.ad in self.enumlar:
                hata(t, f"'{t.ad}' adında bir tip zaten var.")
            self.enumlar[t.ad] = EnumBilgisi(t.ad, t)
        for t in enum_tanimlari:
            self.enum_ayrintilari(t)
        for t in tip_tanimlari:
            self.tip_ayrintilari(t)

        # 1. TUR: Bütün fonksiyonların "imzasını" topla (adı, parametreleri, dönüş tipi).
        #    Böylece bir fonksiyon, tanımlandığı satırdan ÖNCE de çağrılabilir.
        self.kutuphaneler = []
        for k in program.komutlar:
            if isinstance(k, ExternBlok):
                self.extern_kaydet(k)
        for k in program.komutlar:
            if isinstance(k, FonksiyonTanimi):
                self.imza_kaydet(k)
            elif isinstance(k, DegiskenTanimi) and k.ad not in self.ust_tanimlar:
                self.ust_tanimlar[k.ad] = k.satir

        # 2. TUR: Ana programı yukarıdan aşağı kontrol et.
        for k in program.komutlar:
            if not isinstance(k, (FonksiyonTanimi, TipTanimi, EnumTanimi, ExternBlok)):
                self.komut(k)

        # 3. TUR: Her fonksiyonun ve her metodun içini kendi kapsamında kontrol et.
        for k in program.komutlar:
            if isinstance(k, FonksiyonTanimi):
                self.fonksiyon_govdesi(k, self.fonksiyonlar[k.ad])
        for t in tip_tanimlari:
            bilgi = self.tipler[t.ad]
            for m in t.metotlar:
                self.fonksiyon_govdesi(m, bilgi.metotlar[m.ad], bilgi)

    def tip_ayrintilari(self, t):
        """Bir tipin alanlarını ve metot imzalarını kaydet."""
        bilgi = self.tipler[t.ad]
        for a in t.alanlar:
            if a.ad in bilgi.alanlar:
                hata(a, f"'{a.ad}' alanı iki kere yazılmış.")
            tip = self.tip_coz(a.tip)
            if tip == t.ad:
                hata(a, f"'{t.ad}' kendi tipinde bir alan içeremez (sonsuz büyük olurdu).\n"
                        f"   Birden fazla tutmak istiyorsan liste kullan:   {a.ad}: [{t.ad}] = []")
            if a.varsayilan is not None:
                if adlari_topla(a.varsayilan):
                    hata(a.varsayilan, "Varsayılan değer sabit olmalı (değişken kullanılamaz).")
                onceki = self.kapsam
                self.kapsam = Kapsam("varsayılan")
                gelen = self.ifade(a.varsayilan, beklenen=tip)
                self.kapsam = onceki
                if not self.uyumlu_mu(tip, gelen):
                    hata(a.varsayilan, f"'{a.ad}' alanı {tip_aciklama(tip)}, varsayılan değeri {tip_aciklama(gelen)} olamaz.")
            bilgi.alanlar[a.ad] = (tip, a)
        for m in t.metotlar:
            if m.ad in bilgi.metotlar:
                hata(m, f"'{t.ad}' tipinde '{m.ad}' adında bir metot zaten var.")
            if m.ad in bilgi.alanlar:
                hata(m, f"'{m.ad}' hem alan hem metot adı olamaz.")
            f = self.imza_olustur(m)
            f.degistirir = m.degistirir
            f.tip_adi = t.ad
            for p_ad, _ in f.parametreler:
                if p_ad in bilgi.alanlar:
                    hata(m, f"'{m.ad}' metodunun '{p_ad}' parametresi, tipin bir alanıyla aynı adda; başka bir ad ver.")
            bilgi.metotlar[m.ad] = f

    def enum_ayrintilari(self, t):
        bilgi = self.enumlar[t.ad]
        if not t.cesitler:
            hata(t, f"'{t.ad}' enum'unun hiç çeşidi yok. Örnek:   enum {t.ad} {{ Birinci  Ikinci(deger: int) }}")
        for c in t.cesitler:
            if c.ad in bilgi.cesitler:
                hata(c, f"'{c.ad}' çeşidi iki kere yazılmış.")
            alanlar = {}
            for a in c.alanlar:
                if a.ad in alanlar:
                    hata(a, f"'{a.ad}' alanı iki kere yazılmış.")
                alanlar[a.ad] = self.tip_coz(a.tip)      # kendi enum'una işaret edebilir (ağaçlar için)
            bilgi.cesitler[c.ad] = alanlar

    def extern_kaydet(self, blok):
        """extern "kutuphane" { ... }: her C fonksiyonunu normal bir fonksiyon gibi kaydet."""
        if blok.kutuphane not in self.kutuphaneler:
            self.kutuphaneler.append(blok.kutuphane)
        izinler = set()
        for t in blok.izinler:
            if t.deger not in IZINLER:
                hata(t, f"'{t.deger}' diye bir izin yok." + oneri(t.deger, IZINLER) +
                        f"\n   İzinler: {', '.join(IZINLER)}")
            izinler.add(t.deger)

        def c_tipi(t, ne):
            ad = getattr(t, "ad", None)
            if ad == "i32":
                return "int", "i32"
            vt = self.tip_coz(t)
            if vt not in EXTERN_TIPLERI:
                hata(t, f"{ne} C'ye {tip_aciklama(vt)} verilemez/alınamaz. Kullanılabilenler: "
                        f"int, i32 (C'nin küçük tam sayısı), float, bool, text, ptr")
            return vt, EXTERN_TIPLERI[vt]

        for f in blok.fonksiyonlar:
            if f.ad in YERLESIK_FONKSIYONLAR or f.ad in self.fonksiyonlar:
                hata(f, f"'{f.ad}' adında bir fonksiyon zaten var.")
            parametreler, c_param = [], []
            for p in f.parametreler:
                vt, ct = c_tipi(p.tip, f"'{p.ad}' parametresi olarak")
                parametreler.append((p.ad, vt))
                c_param.append(ct)
            donus, c_donus = HICBIR_SEY, "void"
            if f.donus_tipi is not None:
                donus, c_donus = c_tipi(f.donus_tipi, "Dönüş değeri olarak")
            fn = Fonksiyon(f.ad, parametreler, donus, f.satir)
            fn.extern = True
            # C'deki asıl ad. '_' ile başlıyorsa bu sadece "gizli" demek: _DrawCircle → C'de DrawCircle
            c_ad = getattr(f, "c_ad", f.ad)
            fn.c_ad = c_ad[1:] if c_ad.startswith("_") else c_ad
            fn.izinler = izinler
            fn.c_parametreler = c_param
            fn.c_donus = c_donus
            self.fonksiyonlar[f.ad] = fn

    def imza_olustur(self, f):
        parametreler = []
        gorulen = set()
        for p in f.parametreler:
            if p.ad in gorulen:
                hata(p, f"'{p.ad}' parametresi iki kere yazılmış.")
            gorulen.add(p.ad)
            parametreler.append((p.ad, self.tip_coz(p.tip)))
        donus = self.tip_coz(f.donus_tipi) if f.donus_tipi else HICBIR_SEY
        fn = Fonksiyon(f.ad, parametreler, donus, f.satir)
        fn.izinler = izinleri_topla(f.govde)          # use files / use net ... (önceden bilinsin)
        return fn

    def imza_kaydet(self, f):
        if f.ad in YERLESIK_FONKSIYONLAR:
            hata(f, f"'{f.ad}' dilin hazır fonksiyonu, aynı adla yeni fonksiyon yazılamaz.")
        if f.ad in self.fonksiyonlar:
            hata(f, f"'{f.ad}' adında bir fonksiyon zaten var (satır {self.fonksiyonlar[f.ad].satir}).")
        if f.ad in self.tipler:
            hata(f, f"'{f.ad}' bir tipin adı; fonksiyona aynı ad verilemez.")
        if f.degistirir:
            hata(f, "'fn change' sadece bir 'type' içindeki metotlar için kullanılır.")
        self.fonksiyonlar[f.ad] = self.imza_olustur(f)

    def tip_coz(self, t):
        """Ağaçtaki tip düğümünü tip adına çevir: TipAdi('integer') → 'int'"""
        if isinstance(t, ListeTipi):
            return "[" + self.tip_coz(t.eleman) + "]"
        if isinstance(t, SecmeliTip):
            ic = self.tip_coz(t.ic)
            if ic in ("int", "float", "bool"):
                hata(t, f"'{ic}?' henüz yok: yok olabilen değer şimdilik metin, liste, sözlük, kendi tipler ve "
                        f"enum'lar için var.\n   Sayılar için bir enum ya da özel bir değer (ör: -1) kullan.")
            if secmeli_mi(ic):
                hata(t, f"'{ic}?' iki kere '?' olamaz.")
            return ic + "?"
        if isinstance(t, SozlukTipi):
            anahtar = self.tip_coz(t.anahtar)
            if anahtar not in SOZLUK_ANAHTARLARI:
                hata(t, f"Sözlüğün anahtarı şimdilik text ya da int olabilir, {tip_aciklama(anahtar)} olamaz.")
            return "{" + anahtar + ":" + self.tip_coz(t.deger) + "}"
        if t.ad in self.tipler or t.ad in self.enumlar:
            return t.ad                                  # kendi tipin: Ogrenci / enum: Odeme
        if t.ad not in TIP_ADLARI:
            hata(t, f"'{t.ad}' diye bir tip yok." + oneri(t.ad, list(TIP_ADLARI) + list(self.tipler)))
        return TIP_ADLARI[t.ad]

    def uyumlu_mu(self, beklenen, gelen):
        if beklenen == gelen:
            return True
        if beklenen == "ptr" and gelen == YOK:           # C'ye "boş tutamaç" vermek
            return True
        if secmeli_mi(beklenen):                        # Ogrenci? ← none ya da Ogrenci
            return gelen == YOK or self.uyumlu_mu(beklenen[:-1], gelen)
        if beklenen == "float" and gelen == "int":      # 5 → 5.0 olabilir
            return True
        if gelen == BOS_LISTE and beklenen.startswith("["):
            return True
        if gelen == BOS_SOZLUK and sozluk_mu(beklenen):
            return True
        return False

    # =================================================================
    #  DEĞİŞKEN BULMA (kapsam kurallarının kalbi)
    # =================================================================
    def bul(self, ad, dugum):
        # 1) Şu anki kapsamda ya da dışındaki bloklarda var mı?
        d = self.kapsam.ara(ad)
        if d:
            return d

        # 2) Bir metodun içindeysek: tipin alanları normal değişken gibi görünür.
        #    "change" metotta değiştirilebilir, diğerlerinde sadece okunabilir.
        if self.tip_icinde and ad in self.tip_icinde.alanlar:
            tip, alan = self.tip_icinde.alanlar[ad]
            tur = "alan" if self.fonksiyon_icinde.degistirir else "alan-okur"
            return Degisken(ad, tip, tur, alan.satir)

        # Bir bloğun içinde oluşturulmuştu ama o blok bitti
        if ad in self.kapanan_bloklar:
            hata(dugum,
                 f"'{ad}' satır {self.kapanan_bloklar[ad]}'deki bir bloğun içinde oluşturulmuştu; "
                 f"sadece o bloğun içinde geçerli.\n"
                 f"   Blok dışında da kullanmak istiyorsan, onu bloktan önce oluştur.")

        if self.fonksiyon_icinde:
            disarida = self.ana_kapsam.degiskenler.get(ad)
            # 2) "global var" ise use yazmadan okunabilir
            if disarida and disarida.tur == "global":
                return disarida
            # 3) Dışarıda var ama fonksiyon onu göremez
            if disarida or ad in self.ust_tanimlar:
                hata(dugum,
                     f"'{ad}' fonksiyonun dışında oluşturulmuş. Fonksiyonlar dışarıyı göremez.\n"
                     f"   Kullanmak için fonksiyonun içinde şunu yaz:   use {ad}")
        elif ad in self.ust_tanimlar:
            hata(dugum,
                 f"'{ad}' henüz oluşturulmadı. Satır {self.ust_tanimlar[ad]}'de oluşturuluyor;\n"
                 f"   kullanmadan önce oluşturmalısın.")

        if ad in self.fonksiyonlar or ad in YERLESIK_FONKSIYONLAR:
            hata(dugum, f"'{ad}' bir fonksiyon. Çağırmak için parantez kullan:   {ad}(...)")

        adaylar = []
        k = self.kapsam
        while k:
            adaylar += list(k.degiskenler)
            k = k.ust
        if self.fonksiyon_icinde:
            adaylar += [d.ad for d in self.ana_kapsam.degiskenler.values() if d.tur == "global"]
        hata(dugum, f"'{ad}' diye bir değişken yok." + oneri(ad, adaylar))

    def degistirilebilir_olmali(self, ad, dugum):
        """Bu değişken burada değiştirilebilir mi? (x = ..., liste[i] = ..., liste.add(...))"""
        d = self.bul(ad, dugum)
        if self.fonksiyon_icinde and d.tur == "global":
            hata(dugum, f"'{ad}' bir global değişken; fonksiyonlar onu sadece okuyabilir.\n"
                        f"   Değiştirmek için fonksiyonun içinde şunu yaz:   use change {ad}")
        if d.tur == "dis-okur":
            hata(dugum, f"'{ad}' 'use' ile çağrıldığı için sadece okunabilir.\n"
                        f"   Değiştirmek için şöyle çağır:   use change {ad}")
        if d.tur == "sayac":
            hata(dugum, f"'{ad}' bir döngü sayacı; döngünün içinde değiştirilemez, sadece okunabilir.\n"
                        f"   Farklı adımlarla saymak istiyorsan 'step' kullan:   repeat {ad} from 1 to 10 step 2")
        if d.tur == "eslesme":
            hata(dugum, f"'{ad}' match'te bir alana verilen ad; sadece okunabilir.\n"
                        f"   Değiştirilmiş bir değer istiyorsan yeni bir değişken oluştur:   var yeni_{ad} = {ad} ...")
        if d.tur == "satir":
            hata(dugum, f"'{ad}' listenin bir satırını gösteriyor; buradan değiştirilemez, sadece okunabilir.\n"
                        f"   Listeyi değiştirmek için listenin kendisini kullan (ör: liste[i] = ..., liste.remove(i)).")
        if d.tur == "alan-okur":
            m = self.fonksiyon_icinde
            hata(dugum, f"'{m.ad}' metodu nesneyi değiştirmeyen bir metot; '{ad}' alanını değiştiremez.\n"
                        f"   Değiştirmesi gerekiyorsa şöyle işaretle:   fn change {m.ad}(...)")
        return d

    def nesne_degiskeni_olmali(self, nesne, ne):
        """nesne.alan = x / nesne.change_metot(): şimdilik doğrudan bir değişkenin üzerinde."""
        if not isinstance(nesne, Isim):
            hata(nesne, f"{ne} şimdilik sadece doğrudan bir değişkenin üzerinde yapılabilir.")
        d = self.degistirilebilir_olmali(nesne.ad, nesne)
        nesne.tip = d.tip
        return d

    def liste_degiskeni_olmali(self, nesne, ne):
        """liste.add(x) / liste[i] = x: şimdilik sadece bir DEĞİŞKENİN üzerinde yapılabilir."""
        if not isinstance(nesne, Isim):
            hata(nesne, f"{ne} şimdilik sadece doğrudan bir liste değişkeninin üzerinde yapılabilir "
                        f"(ör: liste.add(x)).")
        d = self.degistirilebilir_olmali(nesne.ad, nesne)
        if d.tip == "text":
            hata(nesne, f"Metinler değiştirilemez; harfini değiştirmek yerine yeni bir metin oluştur.\n"
                        f"   Örneğin:   {nesne.ad} = {nesne.ad}.replace(\"eski\", \"yeni\")")
        if not d.tip.startswith("["):
            hata(nesne, f"'{nesne.ad}' bir liste değil, {tip_aciklama(d.tip)}.")
        nesne.tip = d.tip
        return d

    # =================================================================
    #  KOMUTLAR
    # =================================================================
    def komut(self, k):
        if isinstance(k, DegiskenTanimi):
            self.degisken_tanimi(k)

        elif isinstance(k, Atama):
            d = self.degistirilebilir_olmali(k.ad, k)
            asil = getattr(d, "asil", d)                 # kontrolle daraltılmışsa: asıl (T?) tipi
            gelen = self.ifade(k.deger, beklenen=asil.tip)
            if asil is not d and not self.uyumlu_mu(d.tip, gelen):
                # x kontrol edilmişti ama yeniden none olabilecek bir değer alıyor
                if self.dongu_derinligi > d.derinlik:
                    hata(k, f"'{k.ad}' bu döngünün dışında kontrol edildi; döngünün içinde yeniden none olabilir.\n"
                            f"   Kontrolü döngünün içine al:   repeat while {k.ad} is not none {{ ... }}")
                d.tip = asil.tip                         # bundan sonra yine kontrol gerekir
                d = asil
            if not self.uyumlu_mu(d.tip, gelen):
                hata(k.deger, f"'{k.ad}' bir {tip_aciklama(d.tip)}, ona {tip_aciklama(gelen)} verilemez.\n"
                              f"   (Bir değişkenin tipi bir kere belirlenir, sonra değişmez.)")
            k.tip = d.tip

        elif isinstance(k, UseKomutu):
            self.use_komutu(k)

        elif isinstance(k, FonksiyonTanimi):
            hata(k, "Fonksiyon içinde fonksiyon tanımlanamaz. Onu en dışarıya taşı.")

        elif isinstance(k, TipTanimi):
            hata(k, "'type' sadece en dışarıda (fonksiyonların ve blokların dışında) yazılabilir.")

        elif isinstance(k, ExternBlok):
            hata(k, "'extern' sadece en dışarıda (fonksiyonların ve blokların dışında) yazılabilir.")

        elif isinstance(k, EnumTanimi):
            hata(k, "'enum' sadece en dışarıda (fonksiyonların ve blokların dışında) yazılabilir.")

        elif isinstance(k, MatchKomutu):
            self.match_komutu(k)

        elif isinstance(k, AlanAtama):            # nesne.alan = x
            d = self.nesne_degiskeni_olmali(k.nesne, f"'.{k.alan} = ...'")
            bilgi = self.tipler.get(d.tip)
            if not bilgi:
                hata(k.nesne, f"'{k.nesne.ad}' bir {tip_aciklama(d.tip)}; alanı olan bir tip değil.")
            if k.alan not in bilgi.alanlar:
                hata(k, f"'{d.tip}' tipinin '{k.alan}' diye bir alanı yok." + oneri(k.alan, bilgi.alanlar))
            alan_tipi = bilgi.alanlar[k.alan][0]
            gelen = self.ifade(k.deger, beklenen=alan_tipi)
            if not self.uyumlu_mu(alan_tipi, gelen):
                hata(k.deger, f"'{k.alan}' alanı {tip_aciklama(alan_tipi)}, ona {tip_aciklama(gelen)} verilemez.")
            k.alan_tipi = alan_tipi
            k.alan_sirasi = bilgi.alan_sirasi(k.alan)

        elif isinstance(k, Donus):
            self.donus(k)

        elif isinstance(k, ElemanAtama) and sozluk_mu(self.ifade(k.liste)):    # sozluk["Ali"] = 90
            d = self.sozluk_degiskeni_olmali(k.liste, "'sozluk[anahtar] = ...'")
            _, deger_tipi = self.sozluk_anahtari(k, d.tip, k.sira)
            gelen = self.ifade(k.deger, beklenen=deger_tipi)
            if not self.uyumlu_mu(deger_tipi, gelen):
                hata(k.deger, f"'{k.liste.ad}' sözlüğünün değerleri {tip_aciklama(deger_tipi)}, "
                              f"buraya {tip_aciklama(gelen)} konamaz.")
            k.sozluk = True

        elif isinstance(k, ElemanAtama):
            d = self.liste_degiskeni_olmali(k.liste, "'liste[i] = ...'")
            eleman_tipi = d.tip[1:-1]
            t = self.ifade(k.sira)
            if t != "int":
                hata(k.sira, f"Elemanın sırası bir tam sayı (int) olmalı, burada {tip_aciklama(t)} var.")
            gelen = self.ifade(k.deger, beklenen=eleman_tipi)
            if not self.uyumlu_mu(eleman_tipi, gelen):
                hata(k.deger, f"'{k.liste.ad}' listesinin elemanları {tip_aciklama(eleman_tipi)}, "
                              f"buraya {tip_aciklama(gelen)} konamaz.")

        elif isinstance(k, IfadeKomutu):
            self.ifade(k.ifade)
            if not isinstance(k.ifade, (Cagri, MetotCagrisi)):
                hata(k, "Bu satır bir şey yapmıyor: hesaplanan değer hiçbir yere konmuyor.\n"
                        "   Saklamak istiyorsan:   var sonuc = ...      Yazdırmak istiyorsan:   print(...)")

        elif isinstance(k, Eger):
            self.sart_olmali(k.kosul, "if")
            var_olanlar, yok_olanlar = self.none_kontrolleri(k.kosul)
            self.blok(k.govde, "if bloğu", daralt=var_olanlar)
            if k.degilse:
                self.blok(k.degilse, "else bloğu", daralt=yok_olanlar)
            # if x is none { return }  → bu satırdan sonra x kesin var
            if yok_olanlar and (her_zaman_doner_mu(k.govde) or (k.govde and isinstance(k.govde[-1], (Dur, Atla)))):
                for ad in yok_olanlar:
                    self.kapsam.degiskenler[ad] = self.daraltilmis(ad, k)

        elif isinstance(k, TekrarSayi):
            t = self.ifade(k.sayi)
            if t != "int":
                hata(k.sayi, f"'repeat' kaç kere tekrar edeceğini bir tam sayı (int) olarak ister, "
                             f"burada {tip_aciklama(t)} var.")
            self.dongu(k.govde)

        elif isinstance(k, TekrarSurece):
            self.sart_olmali(k.kosul, "repeat while")
            var_olanlar, _ = self.none_kontrolleri(k.kosul)
            self.dongu(k.govde, daralt=var_olanlar)

        elif isinstance(k, TekrarSayac):
            for parca, ad in ((k.bas, "from"), (k.son, "to"), (k.adim, "step")):
                if parca is not None:
                    t = self.ifade(parca)
                    if t != "int":
                        hata(parca, f"'{ad}' bir tam sayı (int) olmalı, burada {tip_aciklama(t)} var.")
            if isinstance(k.adim, Sayi) and k.adim.deger == 0:
                hata(k.adim, "'step 0' olamaz: sayaç hiç ilerlemez, döngü sonsuza kadar sürer.")
            if self.kapsam.ara(k.ad):
                hata(k, f"'{k.ad}' adında bir değişken zaten var; sayaca başka bir ad ver.")
            sayac = Degisken(k.ad, "int", "sayac", k.satir)
            self.dongu(k.govde, sayac)

        elif isinstance(k, WhenKomutu):
            self.when_komutu(k)

        elif isinstance(k, Pencere):
            self.pencere(k)

        elif isinstance(k, (Dur, Atla)):
            if self.dongu_derinligi == 0 and self.when_derinligi > 0:
                kelime = "stop" if isinstance(k, Dur) else "skip"
                hata(k, f"'{kelime}' bir when bloğunun içinden dışarıdaki döngüyü etkileyemez.\n"
                        f"   (when, değişkenin değiştiği her yerde çalışabilir; o anda bir döngüde olmayabilir.)")
            if self.dongu_derinligi == 0:
                kelime = "stop" if isinstance(k, Dur) else "skip"
                hata(k, f"'{kelime}' sadece bir 'repeat' döngüsünün içinde kullanılabilir.")

    def when_komutu(self, k):
        self.sart_olmali(k.kosul, "when")
        izlenenler = sorted(adlari_topla(k.kosul))
        if not izlenen_var_mi(izlenenler):
            hata(k.kosul, "when'in şartında hiç değişken yok; şart hiçbir zaman değişmez, when hiç çalışmaz.")
        for ad in izlenenler:
            d = self.bul(ad, k.kosul)
            if d.tur == "sayac":
                hata(k.kosul, f"'{ad}' bir döngü sayacı; when döngü sayaçlarını izleyemez.")
        k.izlenenler = izlenenler
        # Ana programın en dışında yazılan when, program boyunca geçerli "küresel" bir kuraldır
        k.kuresel = self.fonksiyon_icinde is None and self.kapsam.ust is None

        # when bloğunun içinde: return yok, dışarıdaki döngünün stop/skip'i yok
        onceki_dongu = self.dongu_derinligi
        self.dongu_derinligi = 0
        self.when_derinligi += 1
        self.blok(k.govde, "when bloğu")
        self.when_derinligi -= 1
        self.dongu_derinligi = onceki_dongu

        if k.kuresel:
            # Küresel when gizli bir fonksiyona dönüşecek; kullandığı ana program
            # değişkenleri o fonksiyondan erişilebilsin diye global olmalı.
            k.gereken_globaller = {ad for ad in adlari_topla([k.kosul, k.govde])
                                   if ad in self.ana_kapsam.degiskenler}

    # ---------- window: görsel arayüz ----------
    def pencere(self, k):
        if self.fonksiyon_icinde or self.kapsam.ust is not None:
            hata(k, "'window' şimdilik sadece ana programın en dışında yazılabilir "
                    "(bir fonksiyonun ya da bloğun içinde değil).")
        if getattr(self, "pencere_var", None):
            hata(k, f"Şimdilik bir programda tek pencere olabilir (ilki satır {self.pencere_var}'de).")
        self.pencere_var = k.satir
        self.ifade(k.baslik)
        if any(tur == "ifade" for tur, _ in k.baslik.parcalar):
            hata(k.baslik, "Pencere başlığı sabit bir metin olmalı (içinde {değer} olamaz).")
        sayac = [0]
        self.arayuz_ogeleri(k.ogeler, sayac)
        k.oge_sayisi = sayac[0]

    def arayuz_ogeleri(self, ogeler, sayac, liste=None):
        for o in ogeler:
            o.no = sayac[0]                     # her parçanın numarası: tarayıcıyla bu numarayla konuşulur
            o.liste = liste                     # bir list'in şablonundaysa: o list
            sayac[0] += 1
            if o.tur == "row":
                self.arayuz_ogeleri(o.cocuklar, sayac, liste)
                continue
            if o.tur == "list":
                self.liste_gorunumu(o, sayac)
                continue
            if liste is not None and o.tur in ("textbox", "checkbox"):
                hata(o, f"'{o.tur}' şimdilik bir list'in satırlarına konamaz; sadece label, button ve row olabilir.")
            t = self.ifade(o.metin)
            if t not in YAZDIRILABILIR:
                hata(o.metin, f"'{o.tur}' yazısı olarak sayı, metin ya da bool yazılabilir; "
                              f"burada {tip_aciklama(t)} var.")
            if o.tur == "button":
                # Düğmenin bloğu, ana programın bir parçası gibi çalışır (değişkenleri görür, değiştirir)
                onceki_dongu = self.dongu_derinligi
                self.dongu_derinligi = 0
                self.blok(o.govde, "button bloğu")
                self.dongu_derinligi = onceki_dongu
            elif o.tur in ("textbox", "checkbox"):
                d = self.degistirilebilir_olmali(o.hedef, o)
                uygun = ("bool",) if o.tur == "checkbox" else ("int", "float", "text")
                if d.tip not in uygun:
                    ornek = (f'checkbox "Kabul ediyorum" -> onay   (var onay = false)' if o.tur == "checkbox"
                             else f'textbox "Adın" -> ad   (var ad = "")')
                    hata(o, f"'{o.hedef}' bir {tip_aciklama(d.tip)}; {o.tur} sadece "
                            f"{' / '.join(uygun)} bir değişkene bağlanabilir.\n   Örnek:   {ornek}")
                o.hedef_tipi = d.tip

    def liste_gorunumu(self, o, sayac):
        """list urun, i in urunler -> secili { şablon }"""
        if o.liste is not None:
            hata(o, "Bir list'in satırının içine başka bir list konamaz (şimdilik).")
        t = self.ifade(o.kaynak)
        if not t.startswith("[") or t == BOS_LISTE:
            hata(o.kaynak, f"'list ... in' bir liste ister, burada {tip_aciklama(t)} var.")
        o.eleman_tipi = t[1:-1]
        if o.hedef:
            d = self.degistirilebilir_olmali(o.hedef, o)
            if d.tip != "int":
                hata(o, f"Seçilen satırın sırası bir int (tam sayı) değişkene bağlanır; '{o.hedef}' bir "
                        f"{tip_aciklama(d.tip)}.\n   Örnek:   var secili = 0   (0 = seçim yok)")
            o.hedef_tipi = "int"
        # Şablonun içinde: eleman ve sıra numarası okunabilir ama değiştirilemez
        self.kapsam = Kapsam("list şablonu", self.kapsam)
        for ad, tip in ((o.eleman, o.eleman_tipi), (o.sira_adi, "int")):
            if ad is None:
                continue
            if self.kapsam.ara(ad):
                hata(o, f"'{ad}' adında bir değişken zaten var; satırdaki elemana başka bir ad ver.")
            self.kapsam.ekle(Degisken(ad, tip, "satir", o.satir))
        if o.sira_adi == o.eleman:
            hata(o, "Eleman ile sıra numarasına farklı adlar ver (ör: list urun, i in urunler).")
        self.arayuz_ogeleri(o.cocuklar, sayac, o)
        self.kapsam = self.kapsam.ust

    def match_komutu(self, k):
        t = self.ifade(k.deger)
        bilgi = self.enumlar.get(t)
        if not bilgi:
            hata(k.deger, f"'match' bir enum değeri ister, burada {tip_aciklama(t)} var.\n"
                          f"   (Diğer değerler için if / else if kullan.)")
        k.enum = bilgi
        gorulen = set()
        for d in k.durumlar:
            if d.cesit not in bilgi.cesitler:
                hata(d, f"'{bilgi.ad}' enum'unun '{d.cesit}' diye bir çeşidi yok." + oneri(d.cesit, bilgi.cesitler))
            if d.cesit in gorulen:
                hata(d, f"'{d.cesit}' durumu iki kere yazılmış.")
            gorulen.add(d.cesit)
            alanlar = bilgi.cesitler[d.cesit]
            if d.adlar and len(d.adlar) != len(alanlar):
                ornek = f"{d.cesit}({', '.join(alanlar)})" if alanlar else d.cesit
                hata(d, f"'{d.cesit}' çeşidinin {len(alanlar)} alanı var, {len(d.adlar)} ad verilmiş.   Örnek:   {ornek} {{ ... }}")
            self.kapsam = Kapsam(f"match {d.cesit}", self.kapsam)
            for ad, tip in zip(d.adlar, alanlar.values()):
                if self.kapsam.ara(ad):
                    hata(d, f"'{ad}' adında bir değişken zaten var; alana başka bir ad ver.")
                self.kapsam.ekle(Degisken(ad, tip, "eslesme", d.satir))
            d.alan_tipleri = list(alanlar.values())
            for komut in d.govde:
                self.komut(komut)
            for v in self.kapsam.degiskenler.values():
                self.kapanan_bloklar[v.ad] = v.satir
            self.kapsam = self.kapsam.ust
        eksik = [c for c in bilgi.cesitler if c not in gorulen]
        if eksik and k.degilse is None:
            hata(k, f"match '{bilgi.ad}' değerinin şu çeşitlerini ele almıyor: {', '.join(eksik)}\n"
                    f"   Hepsini yaz ya da geri kalanlar için bir 'else {{ ... }}' ekle.")
        if k.degilse is not None:
            if not eksik:
                hata(k, f"Bütün çeşitler zaten yazılmış; 'else' hiç çalışmaz, silebilirsin.")
            self.blok(k.degilse, "match else bloğu")
        k.tam = True

    def sart_olmali(self, kosul, kelime):
        t = self.ifade(kosul)
        if t != "bool":
            ornek = "x is not 0" if t in ("int", "float") else "x is not \"\""
            hata(kosul, f"'{kelime}' bir doğru/yanlış (bool) sorusu bekler, burada {tip_aciklama(t)} var.\n"
                        f"   Ne sorduğunu açıkça yaz, örneğin:   {kelime} {ornek} {{ }}")

    def none_kontrolleri(self, kosul):
        """Şarttan 'x is not none' / 'x is none' kontrollerini çıkar.
        Döndürür: (şart doğruysa kesin var olanlar, şart YANLIŞSA kesin var olanlar)"""
        if isinstance(kosul, IkiliIslem) and kosul.isaret == "and":
            a, _ = self.none_kontrolleri(kosul.sol)
            b, _ = self.none_kontrolleri(kosul.sag)
            return a + b, []
        if isinstance(kosul, IkiliIslem) and kosul.isaret in ("is", "is not"):
            taraflar = (kosul.sol, kosul.sag)
            if any(isinstance(x, Yok) for x in taraflar):
                isim = next((x for x in taraflar if isinstance(x, Isim)), None)
                if isim is not None and secmeli_mi(getattr(isim, "tip", "")):
                    return ([isim.ad], []) if kosul.isaret == "is not" else ([], [isim.ad])
        return [], []

    def daraltilmis(self, ad, dugum):
        """x'in, kontrolden sonraki hâli: aynı değişken, ama tipi 'T?' yerine 'T'."""
        d = self.bul(ad, dugum)
        asil = getattr(d, "asil", d)
        g = Degisken(ad, asil.tip[:-1] if secmeli_mi(asil.tip) else asil.tip, d.tur, d.satir)
        g.asil = asil                       # atamalarda asıl tip (T?) geçerli
        g.derinlik = self.dongu_derinligi   # hangi döngü seviyesinde kontrol edildi
        return g

    def blok(self, komutlar, ad, ilk_degisken=None, daralt=()):
        """Yeni bir iç kapsam aç, komutları kontrol et, kapsamı kapat."""
        golgeler = [self.daraltilmis(a, komutlar[0] if komutlar else None) for a in daralt]
        self.kapsam = Kapsam(ad, self.kapsam)
        if ilk_degisken:
            self.kapsam.ekle(ilk_degisken)
        for g in golgeler:
            self.kapsam.degiskenler[g.ad] = g
        for komut in komutlar:
            self.komut(komut)
        for d in self.kapsam.degiskenler.values():
            if d not in golgeler:
                self.kapanan_bloklar[d.ad] = d.satir
        self.kapsam = self.kapsam.ust

    def dongu(self, komutlar, sayac=None, daralt=()):
        self.dongu_derinligi += 1
        self.blok(komutlar, "repeat bloğu", sayac, daralt)
        self.dongu_derinligi -= 1

    def degisken_tanimi(self, k):
        if k.global_mi and self.fonksiyon_icinde:
            hata(k, "'global var' sadece fonksiyonların dışında yazılabilir.")
        onceki = self.kapsam.ara(k.ad)
        if onceki:
            hata(k, f"'{k.ad}' zaten oluşturulmuş (satır {onceki.satir}).\n"
                    f"   Değerini değiştirmek istiyorsan 'var' yazmadan:   {k.ad} = ...")
        if k.ad in self.fonksiyonlar or k.ad in YERLESIK_FONKSIYONLAR:
            hata(k, f"'{k.ad}' bir fonksiyonun adı, değişkene aynı ad verilemez.")
        if k.ad in self.tipler:
            hata(k, f"'{k.ad}' bir tipin adı, değişkene aynı ad verilemez.")
        if self.tip_icinde and k.ad in self.tip_icinde.alanlar:
            hata(k, f"'{k.ad}' bu tipin bir alanı; metodun içinde aynı adla değişken oluşturulamaz.")

        beklenen = self.tip_coz(k.tip) if k.tip else None
        gelen = self.ifade(k.deger, beklenen=beklenen)

        if gelen == HICBIR_SEY:
            hata(k.deger, "Bu fonksiyon bir değer döndürmüyor, değişkene konacak bir şey yok.")
        if beklenen:
            if not self.uyumlu_mu(beklenen, gelen):
                hata(k.deger, f"'{k.ad}' bir {tip_aciklama(beklenen)} olarak tanımlandı, "
                              f"ama değeri {tip_aciklama(gelen)}.")
            tip = beklenen
        else:
            if gelen == YOK:
                hata(k, f"'none' ile başlayan değişkenin tipi tahmin edilemez. Tipini yaz:\n"
                        f"   var {k.ad}: Ogrenci? = none")
            if gelen == BOS_SOZLUK:
                hata(k, f"Boş sözlüğün içine ne konacağı tahmin edilemez. Tipini yaz:\n"
                        f"   var {k.ad}: {{text: int}} = {{}}")
            if gelen == BOS_LISTE:
                hata(k, f"Boş listenin içine ne konacağı tahmin edilemez. Tipini yaz:\n"
                        f"   var {k.ad}: [int] = []")
            tip = gelen

        k.tip_sonuc = tip     # sonraki istasyon için not al
        tur = "global" if k.global_mi else ("yerel" if self.fonksiyon_icinde else "ana")
        if k.global_mi and self.kapsam.ust is not None:
            hata(k, "'global var' bir bloğun içinde yazılamaz, en dışarıda olmalı.")
        self.kapsam.ekle(Degisken(k.ad, tip, tur, k.satir))

    def use_komutu(self, k):
        if k.ad in IZINLER:                                    # use files → izin, değişken değil
            if not self.fonksiyon_icinde:
                hata(k, f"'use {k.ad}' sadece fonksiyonların içinde yazılır; ana program zaten her şeye izinli.")
            if k.degistirebilir:
                hata(k, f"İzinler 'use change' ile değil, sadece 'use' ile yazılır:   use {k.ad}")
            k.izin = True
            return
        if not self.fonksiyon_icinde:
            hata(k, "'use' sadece fonksiyonların içinde yazılır. Burada zaten her şeyi görebilirsin.")
        if self.kapsam.ara(k.ad):
            hata(k, f"'{k.ad}' bu fonksiyonda zaten var.")
        disarida = self.ana_kapsam.degiskenler.get(k.ad)
        if not disarida:
            adaylar = list(self.ana_kapsam.degiskenler) + list(IZINLER)
            hata(k, f"Dışarıda '{k.ad}' diye bir değişken (ya da izin) yok." + oneri(k.ad, adaylar))
        tur = "dis-degistirir" if k.degistirebilir else "dis-okur"
        k.tip = disarida.tip
        self.kapsam.ekle(Degisken(k.ad, disarida.tip, tur, k.satir))

    def donus(self, k):
        f = self.fonksiyon_icinde
        if self.when_derinligi > 0:
            hata(k, "'return' bir when bloğunun içinde kullanılamaz.")
        if self.olcum_derinligi > 0:
            hata(k, "'return' bir measure bloğunun içinde kullanılamaz (ölçüm yarıda kalırdı).")
        if not f:
            hata(k, "'return' sadece fonksiyonların içinde kullanılabilir.")
        if k.deger is None:
            if f.donus != HICBIR_SEY:
                hata(k, f"'{f.ad}' bir {tip_aciklama(f.donus)} döndürmeli:   return ...")
            return
        if f.donus == HICBIR_SEY:
            hata(k, f"'{f.ad}' fonksiyonunun dönüş tipi yazılmamış, bu yüzden değer döndüremez.\n"
                    f"   Değer döndürmesi için tanımına tip ekle:   fn {f.ad}(...) -> int")
        gelen = self.ifade(k.deger, beklenen=f.donus)
        if not self.uyumlu_mu(f.donus, gelen):
            hata(k.deger, f"'{f.ad}' bir {tip_aciklama(f.donus)} döndürmeli, ama burada {tip_aciklama(gelen)} döndürülüyor.")

    def fonksiyon_govdesi(self, k, f, tip=None):
        self.fonksiyon_icinde = f
        self.tip_icinde = tip
        self.kapsam = Kapsam(f"{tip.ad}.{k.ad}" if tip else f"fn {k.ad}")
        self.kapsamlar.append(self.kapsam)
        self.kapanan_bloklar = {}

        for (ad, tip), p in zip(f.parametreler, k.parametreler):
            self.kapsam.ekle(Degisken(ad, tip, "parametre", p.satir))

        for komut in k.govde:
            self.komut(komut)

        if f.donus != HICBIR_SEY and not her_zaman_doner_mu(k.govde):
            hata(k, f"'{k.ad}' bir {tip_aciklama(f.donus)} döndürmeli, ama her durumda 'return' ile bitmiyor.\n"
                    f"   Örneğin bir 'if' içinde return var ama 'else' durumunda yok olabilir.")

        self.fonksiyon_icinde = None
        self.tip_icinde = None
        self.kapsam = self.ana_kapsam
        self.kapanan_bloklar = {}

    # =================================================================
    #  İFADELER: her ifadenin tipini bul ve düğüme yaz (e.tip)
    # =================================================================
    def ifade(self, e, beklenen=None):
        tip = self._ifade(e, beklenen)
        e.tip = tip
        return tip

    def _ifade(self, e, beklenen):
        if isinstance(e, Sayi):
            if e.deger > 9223372036854775807:
                hata(e, f"{e.deger} bir int'e sığmayacak kadar büyük "
                        f"(en fazla 9223372036854775807 olabilir).")
            return "int"
        if isinstance(e, Ondalik):
            return "float"
        if isinstance(e, Mantiksal):
            return "bool"
        if isinstance(e, Metin):
            self.metin_parcala(e)
            return "text"
        if isinstance(e, Isim):
            return self.bul(e.ad, e).tip
        if isinstance(e, Liste):
            return self.liste(e, beklenen)
        if isinstance(e, SozlukDegeri):
            return self.sozluk(e, beklenen)
        if isinstance(e, Yok):
            return YOK
        if isinstance(e, YedekliDeger):                  # x else: yedek
            t = self.ifade(e.deger)
            if not secmeli_mi(t):
                hata(e, f"'else:' yok olabilen (T?) bir değerden sonra yazılır; soldaki değer {tip_aciklama(t)}, "
                        f"zaten hiç none olamaz.")
            y = self.ifade(e.yedek, beklenen=t[:-1])
            if not self.uyumlu_mu(t[:-1], y):
                hata(e.yedek, f"Yedek değer {tip_aciklama(t[:-1])} olmalı, burada {tip_aciklama(y)} var.")
            return t[:-1]
        if isinstance(e, TekliIslem) and e.isaret == "not":
            t = self.ifade(e.ifade)
            if t != "bool":
                hata(e, f"'not' sadece doğru/yanlış (bool) değerlerle kullanılır, burada {tip_aciklama(t)} var.")
            return "bool"
        if isinstance(e, TekliIslem):
            t = self.ifade(e.ifade)
            if not sayisal_mi(t):
                hata(e, f"'-' sadece sayılarla kullanılır, burada {tip_aciklama(t)} var.")
            return t
        if isinstance(e, IkiliIslem):
            return self.ikili_islem(e)
        if isinstance(e, Cagri):
            return self.cagri(e, beklenen)
        if isinstance(e, Aralik):
            hata(e, "'a to b' aralığı burada kullanılamaz; sadece repeat'te ve random(1 to 6) içinde yazılır.")
        if isinstance(e, Olcum):                         # measure { ... } → kaç saniye sürdü
            onceki_dongu = self.dongu_derinligi
            self.dongu_derinligi = 0
            self.olcum_derinligi += 1
            self.blok(e.govde, "measure bloğu")
            self.olcum_derinligi -= 1
            self.dongu_derinligi = onceki_dongu
            return "float"
        if isinstance(e, Erisim):
            t = self.ifade(e.liste)
            self.secmeli_kullanilamaz(e.liste, t)
            if sozluk_mu(t):                             # sozluk["Ali"]
                return self.sozluk_anahtari(e, t, e.sira)[1]
            if t != "text" and not t.startswith("["):
                hata(e, f"[ ] ile sadece listelerden ve metinlerden eleman alınabilir, burada {tip_aciklama(t)} var.")
            parcalar = [e.sira.bas, e.sira.son] if isinstance(e.sira, Aralik) else [e.sira]
            if isinstance(e.sira, Aralik) and t != "text":
                hata(e.sira, "Parça alma (a to b) şimdilik sadece metinlerde var:   metin[2 to 4]")
            for p in parcalar:
                s = self.ifade(p)
                if s != "int":
                    hata(p, f"Sıra bir tam sayı (int) olmalı, burada {tip_aciklama(s)} var.")
            if t == "text":
                return "text"                            # metin[1] → tek harflik metin
            return t[1:-1]
        if isinstance(e, (Ozellik, MetotCagrisi)) and self.enum_adi_mi(e.nesne):
            return self.enum_olusturma(e)
        if isinstance(e, Ozellik):
            t = self.ifade(e.nesne)
            self.secmeli_kullanilamaz(e.nesne, t)
            if (t.startswith("[") or t == "text" or sozluk_mu(t)) and e.ad == "length":
                return "int"
            if t == "text":
                if e.ad in METIN_METOTLARI:
                    hata(e, f"'{e.ad}' bir iş; çağırmak için parantez kullan:   .{e.ad}(...)")
                hata(e, f"Metinlerin '{e.ad}' diye bir özelliği yok." + oneri(e.ad, ["length"]))
            if t.startswith("["):
                hata(e, f"Listelerin '{e.ad}' diye bir özelliği yok." + oneri(e.ad, ["length"]))
            if sozluk_mu(t):
                if e.ad in SOZLUK_METOTLARI:
                    hata(e, f"'{e.ad}' bir iş; çağırmak için parantez kullan:   .{e.ad}(...)")
                hata(e, f"Sözlüklerin '{e.ad}' diye bir özelliği yok." + oneri(e.ad, ["length"]))
            if t in self.enumlar:
                hata(e, f"Bir enum değerinin alanları 'match' ile okunur:\n"
                        f"   match deger {{ Cesit({e.ad}) {{ print({e.ad}) }} ... }}")
            if t in self.tipler:                          # nesne.alan
                bilgi = self.tipler[t]
                if e.ad in bilgi.alanlar:
                    e.alan_sirasi = bilgi.alan_sirasi(e.ad)
                    return bilgi.alanlar[e.ad][0]
                if e.ad in bilgi.metotlar:
                    hata(e, f"'{e.ad}' bir metot; çağırmak için parantez kullan:   .{e.ad}(...)")
                hata(e, f"'{t}' tipinin '{e.ad}' diye bir alanı yok." + oneri(e.ad, bilgi.alanlar))
            hata(e, f"{tip_aciklama(t)} değerlerinin '{e.ad}' diye bir özelliği yok (henüz).")
        if isinstance(e, MetotCagrisi):
            return self.metot_cagrisi(e)
        hata(e, "Bunu anlayamadım.")

    def secmeli_kullanilamaz(self, dugum, t):
        if secmeli_mi(t):
            ad = dugum.ad if isinstance(dugum, Isim) else "değer"
            ornek = f"if {ad} is not none {{ ... }}" if isinstance(dugum, Isim) else "önce bir değişkene koy, sonra: if x is not none { ... }"
            hata(dugum, f"'{ad}' yok (none) olabilir ({t}); kullanmadan önce kontrol et:\n   {ornek}\n"
                        f"   ya da yedekle oku:   ({ad} else: yedek)")
        if t == YOK:
            hata(dugum, "none'ın hiçbir alanı ya da işi yok.")

    def enum_adi_mi(self, d):
        return isinstance(d, Isim) and d.ad in self.enumlar and not self.kapsam.ara(d.ad)

    def enum_olusturma(self, e):
        """Odeme.Nakit  /  Odeme.Kart(no: "1234", taksit: 3)"""
        bilgi = self.enumlar[e.nesne.ad]
        e.nesne.tip = bilgi.ad
        if e.ad not in bilgi.cesitler:
            hata(e, f"'{bilgi.ad}' enum'unun '{e.ad}' diye bir çeşidi yok." + oneri(e.ad, bilgi.cesitler))
        alanlar = bilgi.cesitler[e.ad]
        isimli = getattr(e, "isimli", []) if isinstance(e, MetotCagrisi) else []
        ornek = f"{bilgi.ad}.{e.ad}(" + ", ".join(f"{a}: ..." for a in alanlar) + ")" if alanlar else f"{bilgi.ad}.{e.ad}"
        if isinstance(e, MetotCagrisi) and (e.argumanlar or getattr(e, "yedek", None) is not None):
            hata(e, f"Çeşidin alanlarına değerler adlarıyla verilir:   {ornek}")
        if alanlar and not isinstance(e, MetotCagrisi):
            hata(e, f"'{e.ad}' çeşidinin alanları var, değerlerini ver:   {ornek}")
        if not alanlar and isinstance(e, MetotCagrisi):
            hata(e, f"'{e.ad}' çeşidinin alanı yok; parantez olmadan yaz:   {bilgi.ad}.{e.ad}")
        verilen = {}
        for ad, deger, token in isimli:
            if ad not in alanlar:
                hata(token, f"'{e.ad}' çeşidinin '{ad}' diye bir alanı yok." + oneri(ad, alanlar))
            if ad in verilen:
                hata(token, f"'{ad}' alanına iki kere değer verilmiş.")
            gelen = self.ifade(deger, beklenen=alanlar[ad])
            if not self.uyumlu_mu(alanlar[ad], gelen):
                hata(deger, f"'{ad}' alanı {tip_aciklama(alanlar[ad])}, ona {tip_aciklama(gelen)} verilemez.")
            verilen[ad] = deger
        eksik = [a for a in alanlar if a not in verilen]
        if eksik:
            hata(e, f"'{e.ad}' oluşturulurken şu alanlara değer verilmedi: {', '.join(eksik)}   Örnek:   {ornek}")
        e.enum_olusturma = (bilgi.ad, e.ad)
        e.alan_degerleri = verilen
        return bilgi.ad

    def izin_kontrol(self, e, f):
        """Çağrılan fonksiyon bir izin istiyorsa (dosya, internet...), çağıran fonksiyon da o izni yazmış olmalı.
        Böylece bir fonksiyonun dış dünyanın neresine dokunduğu, başındaki 'use' satırlarından her zaman görünür."""
        gereken = getattr(f, "izinler", set())
        cagiran = self.fonksiyon_icinde
        if not gereken or cagiran is None:              # ana program her şeye izinli
            return
        eksik = sorted(gereken - getattr(cagiran, "izinler", set()))
        if eksik:
            izin = eksik[0]
            ne = "C fonksiyonu" if getattr(f, "extern", False) else "fonksiyonu"
            hata(e, f"'{f.ad}' {ne} {IZINLER[izin]} ('{izin}' izni).\n"
                    f"   Onu çağırabilmek için '{cagiran.ad}' fonksiyonunun başına şunu yaz:   use {izin}"
                    + (f"\n   (Ayrıca gereken: {', '.join(eksik[1:])})" if len(eksik) > 1 else ""))

    def argumanlari_kontrol_et(self, e, f, ne):
        if len(e.argumanlar) != len(f.parametreler):
            beklenen = ", ".join(f"{a}: {t}" for a, t in f.parametreler) or "hiçbir şey"
            hata(e, f"'{f.ad}' {len(f.parametreler)} değer bekliyor ({beklenen}), "
                    f"ama {len(e.argumanlar)} değer verildi.")
        for (p_ad, p_tip), a in zip(f.parametreler, e.argumanlar):
            t = self.ifade(a, beklenen=p_tip)
            if not self.uyumlu_mu(p_tip, t):
                hata(a, f"'{f.ad}' {ne} '{p_ad}' parametresi {tip_aciklama(p_tip)} bekliyor, "
                        f"ama {tip_aciklama(t)} verildi.")

    def metot_cagrisi(self, e):
        """liste.add(x) / liste.remove(i) / nesne.metot(...) / metin.split(",")"""
        t = self.ifade(e.nesne)
        self.secmeli_kullanilamaz(e.nesne, t)
        if t == "text":                                   # metin işleri
            if e.ad not in METIN_METOTLARI:
                if e.ad == "length":
                    hata(e, "'length' bir özellik; parantez olmadan yaz:   metin.length")
                hata(e, f"Metinlerin '{e.ad}' diye bir işi yok." + oneri(e.ad, METIN_METOTLARI))
            secenekler, donus = METIN_METOTLARI[e.ad]
            uygun = [s for s in secenekler if len(s) == len(e.argumanlar)]
            if not uygun:
                sayilar = " ya da ".join(str(len(s)) for s in secenekler)
                hata(e, f"'.{e.ad}' {sayilar} değer bekliyor, {len(e.argumanlar)} değer verildi.")
            for a, b in zip(e.argumanlar, uygun[0]):
                gelen = self.ifade(a)
                if gelen != b:
                    hata(a, f"'.{e.ad}' bir {tip_aciklama(b)} bekliyor, burada {tip_aciklama(gelen)} var.")
            return donus
        if t in self.tipler:                              # kendi tipin metodu
            bilgi = self.tipler[t]
            m = bilgi.metotlar.get(e.ad)
            if not m:
                if e.ad in bilgi.alanlar:
                    hata(e, f"'{e.ad}' bir alan, metot değil; parantez olmadan yaz:   .{e.ad}")
                hata(e, f"'{t}' tipinin '{e.ad}' diye bir metodu yok." + oneri(e.ad, bilgi.metotlar))
            if m.degistirir:                              # nesneyi değiştirecek: değişken değiştirilebilir olmalı
                self.nesne_degiskeni_olmali(e.nesne, f"'.{e.ad}(...)' (change metot)")
            self.argumanlari_kontrol_et(e, m, "metodunun")
            self.izin_kontrol(e, m)
            e.metot = m
            return m.donus
        if sozluk_mu(t):
            return self.sozluk_metodu(e, t)
        if t.startswith("[") and e.ad == "join":           # liste.join(", ") → metin
            eleman = t[1:-1]
            if eleman not in YAZDIRILABILIR:
                hata(e, f"'.join' metin, sayı ya da bool listelerini birleştirir; bu liste {tip_aciklama(t)}.")
            if len(e.argumanlar) != 1 or self.ifade(e.argumanlar[0]) != "text":
                hata(e, "'.join' araya konacak bir metin bekler:   liste.join(\", \")")
            return "text"
        if e.ad not in ("add", "remove"):
            if t.startswith("["):
                hata(e, f"Listelerin '{e.ad}' diye bir işi yok." + oneri(e.ad, ["add", "remove", "join"]))
            hata(e, f"{tip_aciklama(t)} değerlerinin '{e.ad}' diye bir işi yok (henüz).")
        d = self.liste_degiskeni_olmali(e.nesne, f"'.{e.ad}(...)'")
        eleman_tipi = d.tip[1:-1]
        if len(e.argumanlar) != 1:
            hata(e, f"'.{e.ad}' tek bir değer bekliyor, {len(e.argumanlar)} değer verildi.")
        a = e.argumanlar[0]
        if e.ad == "add":
            gelen = self.ifade(a, beklenen=eleman_tipi)
            if not self.uyumlu_mu(eleman_tipi, gelen):
                hata(a, f"'{e.nesne.ad}' listesinin elemanları {tip_aciklama(eleman_tipi)}, "
                        f"buna {tip_aciklama(gelen)} eklenemez.")
        else:
            t = self.ifade(a)
            if t != "int":
                hata(a, f"'.remove' silinecek elemanın sırasını (int) bekliyor, burada {tip_aciklama(t)} var.")
        return HICBIR_SEY

    def metin_parcala(self, e):
        """ "Toplam: {fiyat * adet} TL" → [("metin", "Toplam: "), ("ifade", <fiyat * adet>), ("metin", " TL")]
        { } içindeki yazı, lexer ve parser'dan geçirilip gerçek bir ifadeye dönüştürülür;
        sonra tipi her ifade gibi kontrol edilir."""
        from lexer import kelimelere_ayir, LexerHatasi
        from parser import Parser, ParserHatasi
        parcalar = []
        metin = e.deger
        geri = lambda s: s.replace("", "{").replace("", "}")   # \{ ve \} → gerçek parantez

        def kapanis_bul(bas):
            """bas'taki '{' ile eşleşen '}' — içteki metinleri ve iç içe parantezleri atlayarak."""
            derinlik, j = 0, bas
            while j < len(metin):
                h = metin[j]
                if h == '"':
                    j += 1
                    while j < len(metin) and metin[j] != '"':
                        j += 2 if metin[j] == "\\" else 1
                elif h == "{":
                    derinlik += 1
                elif h == "}":
                    derinlik -= 1
                    if derinlik == 0:
                        return j
                j += 1
            return -1

        i = 0
        while i < len(metin):
            ac = metin.find("{", i)
            if ac == -1:
                parcalar.append(("metin", geri(metin[i:])))
                break
            if ac > i:
                parcalar.append(("metin", geri(metin[i:ac])))
            kapa = kapanis_bul(ac)
            if kapa == -1:
                hata(e, "Metnin içindeki '{' kapatılmamış. Değer yazmak için:   \"Merhaba {isim}\"")
            kaynak = metin[ac + 1:kapa]
            if not kaynak.strip():
                hata(e, "Metnin içinde boş bir { } var; içine bir değer yaz:   \"{isim}\"")
            # { } içini küçük bir program parçası gibi oku
            try:
                tokenlar = kelimelere_ayir(kaynak)
                for t in tokenlar:              # hata mesajları metnin bulunduğu satırı göstersin
                    t.satir = e.satir
                    t.sutun = e.sutun + 1 + ac + t.sutun
                p = Parser(tokenlar)
                ic = p.ifade()
                if getattr(e, "yeniden_adlandir", None):   # modül içindeyse adları düzelt (moduller.py)
                    ic = e.yeniden_adlandir(ic)
                if getattr(e, "dosya", None):              # hata mesajları hangi dosyada olduğunu söylesin
                    _dosya_yaz(ic, e.dosya)
                while p.bu_mu("YENİ_SATIR"):
                    p.ilerle()
                if not p.bu_mu("SON"):
                    hata(e, f"Metnin içindeki {{{kaynak}}} tek bir değer olmalı.")
            except (LexerHatasi, ParserHatasi) as h:
                raise TipHatasi(f"{h}\n   (metnin içindeki {{{kaynak.strip()}}} kısmında)")
            t = self.ifade(ic)
            if t not in YAZDIRILABILIR:
                hata(e, f"{{{kaynak.strip()}}} bir {tip_aciklama(t)}; metnin içine sadece sayı, metin ve "
                        f"bool yazılabilir.")
            parcalar.append(("ifade", ic))
            i = kapa + 1
        e.parcalar = parcalar
        if all(tur == "metin" for tur, _ in parcalar):
            e.deger = "".join(p for _, p in parcalar)  # sabit metin: \{ \} işaretleri temizlenmiş hâli

    # ---------- Sözlükler ----------
    def sozluk(self, e, beklenen):
        """{"Ali": 90, "Ayşe": 85}"""
        if not e.anahtarlar:
            return beklenen if sozluk_mu(beklenen) else BOS_SOZLUK
        b_anahtar, b_deger = sozluk_parcalari(beklenen) if sozluk_mu(beklenen) else (None, None)
        anahtar_tipi = self.ifade(e.anahtarlar[0], b_anahtar)
        if anahtar_tipi not in SOZLUK_ANAHTARLARI:
            hata(e.anahtarlar[0], f"Sözlüğün anahtarı şimdilik text ya da int olabilir, "
                                  f"burada {tip_aciklama(anahtar_tipi)} var.")
        for a in e.anahtarlar[1:]:
            t = self.ifade(a, b_anahtar)
            if t != anahtar_tipi:
                hata(a, f"Bir sözlükteki bütün anahtarlar aynı tipte olmalı. İlki {tip_aciklama(anahtar_tipi)}, "
                        f"bu ise {tip_aciklama(t)}.")
        tipler = [self.ifade(d, b_deger) for d in e.degerler]
        if all(sayisal_mi(t) for t in tipler):
            ortak = "float" if "float" in tipler else "int"
        else:
            ortak = tipler[0]
            for d, t in zip(e.degerler, tipler):
                if t != ortak:
                    hata(d, f"Bir sözlükteki bütün değerler aynı tipte olmalı. İlki {tip_aciklama(ortak)}, "
                            f"bu ise {tip_aciklama(t)}.")
        if b_deger and self.uyumlu_mu(b_deger, ortak):
            ortak = b_deger                          # {"a": 1} ama {text: float} bekleniyor
        e.anahtar_tipi, e.deger_tipi = anahtar_tipi, ortak
        return "{" + anahtar_tipi + ":" + ortak + "}"

    def sozluk_anahtari(self, dugum, t, anahtar):
        """sozluk[anahtar] / .get / .has / .remove: anahtarın tipi uygun mu?"""
        anahtar_tipi, deger_tipi = sozluk_parcalari(t)
        gelen = self.ifade(anahtar)
        if gelen != anahtar_tipi:
            hata(anahtar, f"Bu sözlüğün anahtarları {tip_aciklama(anahtar_tipi)}, burada {tip_aciklama(gelen)} var.")
        return anahtar_tipi, deger_tipi

    def sozluk_degiskeni_olmali(self, nesne, ne):
        if not isinstance(nesne, Isim):
            hata(nesne, f"{ne} şimdilik sadece doğrudan bir sözlük değişkeninin üzerinde yapılabilir.")
        d = self.degistirilebilir_olmali(nesne.ad, nesne)
        nesne.tip = d.tip
        return d

    def sozluk_metodu(self, e, t):
        """has(k) / get(k, else: v) / remove(k) / keys() / values()"""
        if e.ad not in SOZLUK_METOTLARI:
            if e.ad == "length":
                hata(e, "'length' bir özellik; parantez olmadan yaz:   sozluk.length")
            hata(e, f"Sözlüklerin '{e.ad}' diye bir işi yok." + oneri(e.ad, SOZLUK_METOTLARI))
        anahtar_tipi, deger_tipi = sozluk_parcalari(t)
        arg_sayisi = 0 if e.ad in ("keys", "values") else 1
        if len(e.argumanlar) != arg_sayisi:
            ornek = {"get": 'notlar.get("Can", else: 0)', "has": 'notlar.has("Ali")',
                     "remove": 'notlar.remove("Ali")'}.get(e.ad, f"notlar.{e.ad}()")
            hata(e, f"'.{e.ad}' {arg_sayisi} değer bekliyor, {len(e.argumanlar)} verildi.   Örnek:   {ornek}")
        yedek = getattr(e, "yedek", None)
        if e.ad == "get":
            if yedek is None:
                hata(e, "'.get' anahtar yoksa ne döneceğini de ister:   notlar.get(\"Can\", else: 0)\n"
                        "   (Anahtarın kesin olduğunu biliyorsan doğrudan:   notlar[\"Ali\"])")
            g = self.ifade(yedek, beklenen=deger_tipi)
            if not self.uyumlu_mu(deger_tipi, g):
                hata(yedek, f"Yedek değer sözlüğün değerleriyle aynı tipte olmalı ({tip_aciklama(deger_tipi)}), "
                            f"burada {tip_aciklama(g)} var.")
        elif yedek is not None:
            hata(yedek, "'else:' sadece '.get' ile kullanılır.")
        if e.ad in ("get", "has", "remove"):
            self.sozluk_anahtari(e, t, e.argumanlar[0])
        if e.ad == "remove":
            self.sozluk_degiskeni_olmali(e.nesne, "'.remove(...)'")
        return {"get": deger_tipi, "has": "bool", "remove": HICBIR_SEY,
                "keys": f"[{anahtar_tipi}]", "values": f"[{deger_tipi}]"}[e.ad]

    def liste(self, e, beklenen):
        if not e.elemanlar:
            return beklenen if beklenen and beklenen.startswith("[") else BOS_LISTE
        eleman_beklenen = beklenen[1:-1] if beklenen and beklenen.startswith("[") else None
        tipler = [self.ifade(x, eleman_beklenen) for x in e.elemanlar]
        ilk = tipler[0]
        if all(sayisal_mi(t) for t in tipler):
            ortak = "float" if "float" in tipler else "int"
        else:
            for x, t in zip(e.elemanlar, tipler):
                if t != ilk:
                    hata(x, f"Bir listedeki her şey aynı tipte olmalı. İlk eleman {tip_aciklama(ilk)}, "
                            f"bu ise {tip_aciklama(t)}.")
            ortak = ilk
        return f"[{ortak}]"

    def ikili_islem(self, e):
        sol = self.ifade(e.sol)
        sag = self.ifade(e.sag)
        op = e.isaret

        if op in ("and", "or"):
            for taraf, t in ((e.sol, sol), (e.sag, sag)):
                if t != "bool":
                    hata(taraf, f"'{op}' iki doğru/yanlış (bool) değeri birleştirir, burada {tip_aciklama(t)} var.")
            return "bool"

        if op in ("+", "-", "*"):
            if op == "+" and "text" in (sol, sag):
                hata(e, "Metinler '+' ile birleştirilmez. Metnin içine yazabilirsin:\n"
                        "   \"Merhaba {isim}\"")
            self.sayisal_olmali(e, sol, sag)
            return "float" if "float" in (sol, sag) else "int"

        if op == "/":
            self.sayisal_olmali(e, sol, sag)
            return "float"            # / her zaman tam sonuç verir: 7 / 2 = 3.5

        if op in ("//", "%"):
            if sol != "int" or sag != "int":
                hata(e, f"'{op}' sadece tam sayılarla (int) kullanılır, burada "
                        f"{tip_aciklama(sol)} ve {tip_aciklama(sag)} var.")
            return "int"

        if op in ("<", ">", "<=", ">="):
            self.sayisal_olmali(e, sol, sag)
            return "bool"

        if op in ("is", "is not") and YOK in (sol, sag):          # x is none / x is not none
            diger, dt = (e.sag, sag) if sol == YOK else (e.sol, sol)
            if not secmeli_mi(dt) and dt != YOK and dt != "ptr":
                hata(diger, f"Bu değer {tip_aciklama(dt)}; hiçbir zaman none olamaz, kontrol etmeye gerek yok.")
            return "bool"
        if op in ("is", "is not"):
            if sol.startswith("[") or sag.startswith("["):
                hata(e, "Listeler henüz 'is' ile karşılaştırılamaz.")
            if sozluk_mu(sol) or sozluk_mu(sag):
                hata(e, "Sözlükler henüz 'is' ile karşılaştırılamaz.")
            if sol in self.enumlar or sag in self.enumlar:
                hata(e, "Enum değerleri 'is' ile karşılaştırılamaz; hangi çeşit olduğunu 'match' ile sor.")
            if sol in self.tipler or sag in self.tipler:
                hata(e, "Kendi tiplerin değerleri henüz 'is' ile karşılaştırılamaz; alanlarını karşılaştır (ör: a.ad is b.ad).")
            if not (sol == sag or (sayisal_mi(sol) and sayisal_mi(sag))):
                hata(e, f"{tip_aciklama(sol)} ile {tip_aciklama(sag)} karşılaştırılamaz.")
            return "bool"

        hata(e, f"'{op}' işlemini tanımıyorum.")

    def sayisal_olmali(self, e, sol, sag):
        for t in (sol, sag):
            if not sayisal_mi(t):
                hata(e, f"'{e.isaret}' sadece sayılarla kullanılır, burada {tip_aciklama(t)} var.")

    def cagri(self, e, beklenen=None):
        # --- Tip oluşturma: Ogrenci(ad: "Ali", ...) ---
        if e.ad in self.tipler:
            return self.olusturma(e)
        if e.ad in YERLESIK_FONKSIYONLAR and e.ad not in ("print", "write"):
            return self.hazir_fonksiyon(e, beklenen)
        if e.isimli:
            hata(e.isimli[0][2], f"'{e.ad}(...)' bir fonksiyon; değerler adlarıyla (ad: değer) verilemez, sırayla yazılır.")

        if e.ad in ("print", "write"):
            for a in e.argumanlar:
                t = self.ifade(a)
                if t not in YAZDIRILABILIR and not t.startswith("[") and not sozluk_mu(t) and t not in self.tipler and t not in self.enumlar and not secmeli_mi(t) and t != YOK:
                    hata(a, f"{e.ad}() şimdilik {tip_aciklama(t)} yazdıramaz.")
            return HICBIR_SEY

        # --- Metodun içinden aynı tipin başka bir metodunu adıyla çağırmak ---
        if self.tip_icinde and e.ad in self.tip_icinde.metotlar:
            m = self.tip_icinde.metotlar[e.ad]
            if m.degistirir and not self.fonksiyon_icinde.degistirir:
                hata(e, f"'{self.fonksiyon_icinde.ad}' nesneyi değiştirmeyen bir metot; nesneyi değiştiren "
                        f"'{e.ad}' metodunu çağıramaz.\n"
                        f"   Gerekiyorsa şöyle işaretle:   fn change {self.fonksiyon_icinde.ad}(...)")
            self.argumanlari_kontrol_et(e, m, "metodunun")
            self.izin_kontrol(e, m)
            e.metot = m
            return m.donus

        f = self.fonksiyonlar.get(e.ad)
        if not f:
            if self.kapsam.ara(e.ad):
                hata(e, f"'{e.ad}' bir değişken, fonksiyon değil; çağrılamaz.")
            adaylar = list(self.fonksiyonlar) + list(YERLESIK_FONKSIYONLAR) + list(self.tipler)
            hata(e, f"'{e.ad}' diye bir fonksiyon yok." + oneri(e.ad, adaylar))

        self.argumanlari_kontrol_et(e, f, "fonksiyonunun")
        self.izin_kontrol(e, f)
        return f.donus

    def hazir_fonksiyon(self, e, beklenen=None):
        """input, random, time, int, float, text"""
        def sayi_olmali(n):
            if len(e.argumanlar) != n:
                hata(e, f"'{e.ad}' {n} değer bekliyor, {len(e.argumanlar)} değer verildi.")

        e.yedek = None
        if e.isimli and not (e.ad in ("int", "float") and len(e.isimli) == 1 and e.isimli[0][0] == "else"):
            ad, _, token = e.isimli[0]
            if ad == "else":
                hata(token, f"'else:' sadece int(...) ve float(...) çevirmelerinde kullanılır.")
            hata(token, f"'{e.ad}(...)' değerleri adlarıyla (ad: değer) almaz.")

        if e.ad == "input":
            if len(e.argumanlar) > 1:
                hata(e, "'input' en fazla bir değer (ekrana yazılacak soru) alır:   input(\"Adın: \")")
            if e.argumanlar and self.ifade(e.argumanlar[0]) != "text":
                hata(e.argumanlar[0], "'input'e verilen soru bir metin (text) olmalı.")
            # Vash'a özgü: beklenen tip neyse input onu okur (int/float ise geçerli değer gelene kadar sorar)
            if beklenen in ("int", "float"):
                e.input_tipi = beklenen
            elif beklenen in (None, "text"):
                e.input_tipi = "text"
            else:
                hata(e, f"input bir {tip_aciklama(beklenen)} okuyamaz; metin, int ya da float okuyabilir.")
            return e.input_tipi
        if e.ad == "random":
            if len(e.argumanlar) == 2:
                hata(e, "Vash'ta aralık 'to' ile yazılır (iki sınır da dahil):   random(1 to 6)")
            sayi_olmali(1)
            a = e.argumanlar[0]
            if isinstance(a, Aralik):                     # random(1 to 6)
                ta, tb = self.ifade(a.bas), self.ifade(a.son)
                for parca, t in ((a.bas, ta), (a.son, tb)):
                    if not sayisal_mi(t):
                        hata(parca, f"random'ın sınırları sayı olmalı, burada {tip_aciklama(t)} var.")
                a.tip = "float" if "float" in (ta, tb) else "int"
                return a.tip
            t = self.ifade(a)                             # random(liste)
            if t.startswith("["):
                return t[1:-1]
            hata(a, f"random bir aralık (random(1 to 6)) ya da bir liste (random(renkler)) bekler, "
                    f"burada {tip_aciklama(t)} var.")
        if e.ad in ("code", "char"):                  # code("A") → 65   char(65) → "A"
            sayi_olmali(1)
            t = self.ifade(e.argumanlar[0])
            istenen = "text" if e.ad == "code" else "int"
            if t != istenen:
                ornek = 'code("A")  → 65' if e.ad == "code" else 'char(65)  → "A"'
                hata(e.argumanlar[0], f"'{e.ad}' bir {tip_aciklama(istenen)} bekliyor, {tip_aciklama(t)} verildi.   Örnek:   {ornek}")
            return "int" if e.ad == "code" else "text"
        if e.ad in DOSYA_FONKSIYONLARI:
            beklenenler, donus = DOSYA_FONKSIYONLARI[e.ad]
            if len(e.argumanlar) != len(beklenenler):
                ornek = {"read_file": 'read_file("notlar.txt")', "read_lines": 'read_lines("liste.txt")',
                         "write_file": 'write_file("sonuc.txt", "Merhaba")',
                         "append_file": 'append_file("gunluk.txt", "yeni satır\\n")',
                         "file_exists": 'file_exists("ayar.txt")'}[e.ad]
                hata(e, f"'{e.ad}' {len(beklenenler)} değer bekliyor, {len(e.argumanlar)} verildi.   Örnek:   {ornek}")
            for a, b in zip(e.argumanlar, beklenenler):
                t = self.ifade(a)
                if t != b:
                    hata(a, f"'{e.ad}' burada {tip_aciklama(b)} bekliyor (dosya adı/yazı), {tip_aciklama(t)} verildi.")
            cagiran = self.fonksiyon_icinde
            if cagiran is not None and "files" not in getattr(cagiran, "izinler", set()):
                hata(e, f"'{e.ad}' dosyalara dokunuyor ('files' izni).\n"
                        f"   Onu kullanabilmek için '{cagiran.ad}' fonksiyonunun başına şunu yaz:   use files")
            return donus
        if e.ad == "time":
            sayi_olmali(0)
            return "float"
        # int(x) / float(x) / text(x): çevirme
        sayi_olmali(1)
        t = self.ifade(e.argumanlar[0])
        kabul = {"int": ("int", "float", "text", "bool"),
                 "float": ("int", "float", "text"),
                 "text": ("int", "float", "text", "bool")}[e.ad]
        if t not in kabul:
            hata(e.argumanlar[0], f"{tip_aciklama(t)} değeri {e.ad}'e çevrilemez.")
        if e.isimli:                                      # int("abc", else: 0)
            _, yedek, token = e.isimli[0]
            if t != "text":
                hata(token, "'else:' sadece bir metni çevirirken gerekir (sayılar her zaman çevrilebilir).")
            gelen = self.ifade(yedek, beklenen=e.ad)
            if not self.uyumlu_mu(e.ad, gelen):
                hata(yedek, f"Yedek değer bir {tip_aciklama(e.ad)} olmalı, burada {tip_aciklama(gelen)} var.")
            e.yedek = yedek
        return e.ad

    def olusturma(self, e):
        """Ogrenci(ad: "Ali", notlar: [90])  → her alana bir değer (ya da varsayılanı)"""
        bilgi = self.tipler[e.ad]
        if e.argumanlar:
            ornek = ", ".join(f"{a}: ..." for a in bilgi.alanlar)
            hata(e, f"'{e.ad}' oluşturulurken değerler alan adlarıyla yazılır:   {e.ad}({ornek})")
        verilen = {}
        for ad, deger, token in e.isimli:
            if ad not in bilgi.alanlar:
                hata(token, f"'{e.ad}' tipinin '{ad}' diye bir alanı yok." + oneri(ad, bilgi.alanlar))
            if ad in verilen:
                hata(token, f"'{ad}' alanına iki kere değer verilmiş.")
            alan_tipi = bilgi.alanlar[ad][0]
            gelen = self.ifade(deger, beklenen=alan_tipi)
            if not self.uyumlu_mu(alan_tipi, gelen):
                hata(deger, f"'{ad}' alanı {tip_aciklama(alan_tipi)}, ona {tip_aciklama(gelen)} verilemez.")
            verilen[ad] = deger
        eksik = [ad for ad, (_, alan) in bilgi.alanlar.items() if ad not in verilen and alan.varsayilan is None]
        if eksik:
            hata(e, f"'{e.ad}' oluşturulurken şu alanlara değer verilmedi (varsayılanları yok): {', '.join(eksik)}")
        e.alan_degerleri = verilen        # sonraki istasyon için
        return e.ad

    # =================================================================
    #  RAPOR (arayüzde ve terminalde göstermek için)
    # =================================================================
    def rapor(self):
        tur_adi = {"ana": "değişken", "yerel": "değişken", "parametre": "parametre",
                   "global": "global", "dis-okur": "use (okur)", "dis-degistirir": "use change",
                   "sayac": "döngü sayacı", "alan": "alan", "alan-okur": "alan",
                   "eslesme": "match alanı", "satir": "list satırı"}
        fonksiyonlar = []
        tum = list(self.fonksiyonlar.values())
        for bilgi in self.tipler.values():
            for m in bilgi.metotlar.values():
                tum.append(m)
        for f in tum:
            parametreler = ", ".join(f"{a}: {t}" for a, t in f.parametreler)
            donus = "" if f.donus == HICBIR_SEY else f" -> {f.donus}"
            on_ek = (f"{f.tip_adi}." if f.tip_adi else "") + ("change " if f.degistirir else "")
            fonksiyonlar.append({"ad": f.ad, "imza": f"{on_ek}{f.ad}({parametreler}){donus}", "satir": f.satir})
        kapsamlar = []
        for k in self.kapsamlar:
            kapsamlar.append({
                "ad": k.ad,
                "degiskenler": [{"ad": d.ad, "tip": d.tip,
                                 "tur": tur_adi[d.tur] + (" · blokta" if d.blokta and d.tur != "sayac" else ""),
                                 "satir": d.satir}
                                for d in k.tum],
            })
        return {"fonksiyonlar": fonksiyonlar, "kapsamlar": kapsamlar}


def tipleri_kontrol_et(program):
    k = TipKontrolcu()
    k.kontrol_et(program)
    return k


# ---------------------------------------------------------------------
#  Kullanım:  python derleyici\tipler.py ornekler\ilk.vash
# ---------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from lexer import LexerHatasi
    from parser import ParserHatasi, agac_kur

    with open(sys.argv[1], encoding="utf-8-sig") as f:
        kod = f.read()
    try:
        kontrolcu = tipleri_kontrol_et(agac_kur(kod))
    except (LexerHatasi, ParserHatasi, TipHatasi) as h:
        print("HATA:", h)
        sys.exit(1)

    r = kontrolcu.rapor()
    print("FONKSİYONLAR")
    for f in r["fonksiyonlar"]:
        print(f"   {f['imza']}")
    for k in r["kapsamlar"]:
        print(f"\n{k['ad'].upper()}")
        for d in k["degiskenler"]:
            print(f"   {d['ad']:<10} {d['tip']:<8} {d['tur']}")
    print("\n✓ Tip hatası yok.")
