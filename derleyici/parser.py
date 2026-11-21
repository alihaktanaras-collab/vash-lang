# =====================================================================
#  2. İSTASYON: PARSER (Ağaç Kurucu)
# =====================================================================
#
#  Görevi: Lexer'ın verdiği kelime listesini alıp kodun ANLAMINI
#  gösteren bir AĞAÇ kurmak. Bu ağaca AST (Abstract Syntax Tree) denir.
#
#  Örnek:   var x = 2 + 3 * 4
#
#  Lexer şunu verir (düz bir liste):
#      [var] [İSİM x] [=] [SAYI 2] [+] [SAYI 3] [*] [SAYI 4]
#
#  Parser şunu kurar (bir ağaç):
#
#      DeğişkenTanımı x
#      └─ İşlem +
#         ├─ Sayı 2
#         └─ İşlem *          ← çarpma daha derinde, çünkü ÖNCE o yapılır
#            ├─ Sayı 3
#            └─ Sayı 4
#
#  Neden ağaç? Çünkü ağaç "neyin neye ait olduğunu" ve "hangi işlemin
#  önce yapılacağını" gösterir. Sonraki istasyonlar ağacı aşağıdan yukarı
#  okuyarak işi kolayca yapar: önce 3*4, sonra 2+12, sonra x'e koy.
#
#  YÖNTEM: "Recursive Descent" (Özyinelemeli İniş)
#  Dilin her kuralı için bir fonksiyon yazıyoruz. Fonksiyonlar birbirini
#  çağırıyor. Elle yazılan derleyicilerin çoğu (GCC, Clang, Rust, Go)
#  bu yöntemi kullanır.
# =====================================================================

from lexer import kelimelere_ayir


# =====================================================================
#  BÖLÜM 1: AĞACIN DÜĞÜMLERİ
# =====================================================================
#  Ağaçtaki her kutucuğa "düğüm" (node) denir. Her düğüm türü kodun bir
#  parçasını temsil eder. Hepsi satır/sütun bilgisini saklar ki sonraki
#  istasyonlar hata bulunca nerede olduğunu söyleyebilsin.

class Dugum:
    satir = 0
    sutun = 0


# ---------- KOMUTLAR (bir iş yapan satırlar) ----------

class Program(Dugum):
    """Bütün dosya. İçinde komutların listesi var."""
    def __init__(self, komutlar):
        self.komutlar = komutlar


class DegiskenTanimi(Dugum):
    """var x: int = 5   /   global var x = 5"""
    def __init__(self, ad, tip, deger, global_mi=False):
        self.ad = ad              # "x"
        self.tip = tip            # TipAdi("int") ya da None (tahmin edilecek)
        self.deger = deger        # bir ifade düğümü
        self.global_mi = global_mi


class UseKomutu(Dugum):
    """use vergi   /   use change sayac"""
    def __init__(self, ad, degistirebilir):
        self.ad = ad
        self.degistirebilir = degistirebilir


class Atama(Dugum):
    """x = 10"""
    def __init__(self, ad, deger):
        self.ad = ad
        self.deger = deger


class FonksiyonTanimi(Dugum):
    """fn topla(a: int, b: int) -> int { ... }"""
    def __init__(self, ad, parametreler, donus_tipi, govde, degistirir=False):
        self.ad = ad
        self.parametreler = parametreler   # [Parametre, Parametre, ...]
        self.donus_tipi = donus_tipi       # tip düğümü ya da None
        self.govde = govde                 # [komut, komut, ...]
        self.degistirir = degistirir       # metotlarda: "fn change ..." mi?


class Alan(Dugum):
    """type içindeki bir alan:  ad: text   /   can: int = 100"""
    def __init__(self, ad, tip, varsayilan):
        self.ad = ad
        self.tip = tip
        self.varsayilan = varsayilan       # ifade ya da None


class TipTanimi(Dugum):
    """type Ogrenci { alanlar...  fn metotlar... }"""
    def __init__(self, ad, alanlar, metotlar):
        self.ad = ad
        self.alanlar = alanlar             # [Alan, ...]
        self.metotlar = metotlar           # [FonksiyonTanimi, ...]


class ImportKomutu(Dugum):
    """import geometri   → geometri.vash dosyasındaki tanımları kullan"""
    def __init__(self, ad):
        self.ad = ad


class ExternBlok(Dugum):
    """extern "kutuphane" { fn ad(x: float) -> float   ... }"""
    def __init__(self, kutuphane, fonksiyonlar, izinler):
        self.kutuphane = kutuphane
        self.fonksiyonlar = fonksiyonlar   # [ExternFonksiyon, ...]
        self.izinler = izinler             # ["files", ...]: bu fonksiyonlar dış dünyanın neresine dokunuyor


class ExternFonksiyon(Dugum):
    def __init__(self, ad, parametreler, donus_tipi):
        self.ad = ad
        self.parametreler = parametreler   # [Parametre, ...]
        self.donus_tipi = donus_tipi       # tip ya da None


class EnumTanimi(Dugum):
    """enum Odeme { Nakit   Kart(no: text, taksit: int)   Havale(iban: text) }"""
    def __init__(self, ad, cesitler):
        self.ad = ad
        self.cesitler = cesitler           # [EnumCesidi, ...]


class EnumCesidi(Dugum):
    def __init__(self, ad, alanlar):
        self.ad = ad
        self.alanlar = alanlar             # [Alan, ...]  (varsayılan değer yok)


class MatchKomutu(Dugum):
    """match deger { Nakit { ... }   Kart(no, taksit) { ... }   else { ... } }"""
    def __init__(self, deger, durumlar, degilse):
        self.deger = deger
        self.durumlar = durumlar           # [MatchDurumu, ...]
        self.degilse = degilse             # else bloğu ya da None


class MatchDurumu(Dugum):
    def __init__(self, cesit, adlar, govde):
        self.cesit = cesit                 # çeşidin adı: "Kart"
        self.adlar = adlar                 # alanlara verilen adlar: ["no", "taksit"]
        self.govde = govde


class AlanAtama(Dugum):
    """nesne.alan = x"""
    def __init__(self, nesne, alan, deger):
        self.nesne = nesne
        self.alan = alan
        self.deger = deger


class Parametre(Dugum):
    """Fonksiyon parametresi: a: int"""
    def __init__(self, ad, tip):
        self.ad = ad
        self.tip = tip


class Donus(Dugum):
    """return x * x"""
    def __init__(self, deger):
        self.deger = deger    # ifade ya da None (sadece "return")


class IfadeKomutu(Dugum):
    """Tek başına duran bir ifade. Genelde bir çağrı: print("merhaba")"""
    def __init__(self, ifade):
        self.ifade = ifade


class Eger(Dugum):
    """if kosul { ... } else if ... { ... } else { ... }"""
    def __init__(self, kosul, govde, degilse):
        self.kosul = kosul
        self.govde = govde          # [komut, ...]
        self.degilse = degilse      # None, [komut, ...] ya da [Eger(...)] (else if)


class TekrarSayi(Dugum):
    """repeat 3 { ... }"""
    def __init__(self, sayi, govde):
        self.sayi = sayi
        self.govde = govde


class TekrarSurece(Dugum):
    """repeat while kosul { ... }"""
    def __init__(self, kosul, govde):
        self.kosul = kosul
        self.govde = govde


class TekrarSayac(Dugum):
    """repeat i from 1 to 10 step 2 { ... }"""
    def __init__(self, ad, bas, son, adim, govde):
        self.ad = ad
        self.bas = bas
        self.son = son
        self.adim = adim            # ifade ya da None (1 demek)
        self.govde = govde


class WhenKomutu(Dugum):
    """when kosul { ... }   /   when later kosul { ... }"""
    def __init__(self, kosul, govde, bekle):
        self.kosul = kosul
        self.govde = govde
        self.bekle = bekle          # True: "later" — en baştaki doğruluğu sayma, değişimi bekle


class Pencere(Dugum):
    """window "Başlık" { label ... button ... textbox ... checkbox ... row { } }"""
    def __init__(self, baslik, ogeler):
        self.baslik = baslik        # Metin düğümü
        self.ogeler = ogeler        # ArayuzOgesi listesi


class ArayuzOgesi(Dugum):
    """Penceredeki bir parça.
         label  <yazı>                    → yazı (içindeki {değer}ler kendiliğinden güncellenir)
         button <yazı> { ... }            → basılınca blok çalışır
         textbox <yazı> -> değişken       → yazı kutusu, değişkene iki yönlü bağlı
         checkbox <yazı> -> değişken      → onay kutusu (bool), iki yönlü bağlı
         row { ... }                      → içindekileri yan yana dizer
         list x[, i] in <liste> [-> secili] { ... }
                                          → listenin her elemanı için bir satır; { } satırın şablonu"""
    TURLER = ("label", "button", "textbox", "checkbox", "row", "list")

    def __init__(self, tur, metin=None, govde=None, hedef=None, cocuklar=None,
                 eleman=None, sira_adi=None, kaynak=None):
        self.tur = tur
        self.metin = metin          # gösterilecek yazı (bir ifade)
        self.govde = govde or []    # button: basılınca çalışacak komutlar
        self.hedef = hedef          # textbox/checkbox: bağlı değişkenin adı; list: seçilen sıranın değişkeni
        self.cocuklar = cocuklar or []
        self.eleman = eleman        # list: her satırdaki elemanın adı (urun)
        self.sira_adi = sira_adi    # list: satırın sıra numarasının adı (i), yazılmadıysa None
        self.kaynak = kaynak        # list: gösterilen liste (bir ifade)


class Dur(Dugum):
    """stop"""


class Atla(Dugum):
    """skip"""


# ---------- İFADELER (bir DEĞER üreten parçalar) ----------

class Sayi(Dugum):
    def __init__(self, deger):
        self.deger = deger


class Ondalik(Dugum):
    def __init__(self, deger):
        self.deger = deger


class Mantiksal(Dugum):
    """true / false"""
    def __init__(self, deger):
        self.deger = deger


class Metin(Dugum):
    def __init__(self, deger):
        self.deger = deger


class Isim(Dugum):
    """Bir değişkenin adı: x"""
    def __init__(self, ad):
        self.ad = ad


class IkiliIslem(Dugum):
    """İki değer arasında işlem: a + b, x is 5, y < 3"""
    def __init__(self, isaret, sol, sag):
        self.isaret = isaret
        self.sol = sol
        self.sag = sag


class TekliIslem(Dugum):
    """Tek değerli işlem: -x"""
    def __init__(self, isaret, ifade):
        self.isaret = isaret
        self.ifade = ifade


class Cagri(Dugum):
    """Fonksiyon çağrısı: topla(2, 3)   /   tip oluşturma: Ogrenci(ad: "Ali")"""
    def __init__(self, ad, argumanlar, isimli=None):
        self.ad = ad
        self.argumanlar = argumanlar
        self.isimli = isimli or []         # [(alan adı, ifade, token), ...]


class Liste(Dugum):
    """[1, 2, 3]"""
    def __init__(self, elemanlar):
        self.elemanlar = elemanlar


class Yok(Dugum):
    """none"""


class YedekliDeger(Dugum):
    """bul("Can") else: varsayilan   → soldaki none ise sağdaki"""
    def __init__(self, deger, yedek):
        self.deger = deger
        self.yedek = yedek


class SozlukDegeri(Dugum):
    """{"Ali": 90, "Ayşe": 85}"""
    def __init__(self, anahtarlar, degerler):
        self.anahtarlar = anahtarlar
        self.degerler = degerler


class Aralik(Dugum):
    """random(1 to 6) içindeki '1 to 6'"""
    def __init__(self, bas, son):
        self.bas = bas
        self.son = son


class Olcum(Dugum):
    """measure { ... }  → bloğun kaç saniye sürdüğü"""
    def __init__(self, govde):
        self.govde = govde


class Erisim(Dugum):
    """liste[i]  → listenin i. elemanı"""
    def __init__(self, liste, sira):
        self.liste = liste
        self.sira = sira


class Ozellik(Dugum):
    """liste.length"""
    def __init__(self, nesne, ad):
        self.nesne = nesne
        self.ad = ad


class MetotCagrisi(Dugum):
    """liste.add(x)"""
    def __init__(self, nesne, ad, argumanlar):
        self.nesne = nesne
        self.ad = ad
        self.argumanlar = argumanlar


class ElemanAtama(Dugum):
    """liste[i] = x"""
    def __init__(self, liste, sira, deger):
        self.liste = liste
        self.sira = sira
        self.deger = deger


# ---------- TİPLER ----------

class TipAdi(Dugum):
    """int, integer ..."""
    def __init__(self, ad):
        self.ad = ad


class ListeTipi(Dugum):
    """[int]"""
    def __init__(self, eleman):
        self.eleman = eleman


class SecmeliTip(Dugum):
    """Ogrenci?  → değeri olmayabilir (none)"""
    def __init__(self, ic):
        self.ic = ic


class SozlukTipi(Dugum):
    """{text: int}"""
    def __init__(self, anahtar, deger):
        self.anahtar = anahtar
        self.deger = deger


# =====================================================================
#  BÖLÜM 2: HATA
# =====================================================================

class ParserHatasi(Exception):
    pass


# Diğer dillerden alışkanlıkla yazılabilecek kelimeler → bu dildeki karşılığı
YABANCI_KELIMELER = {
    "while":    "Bu dilde döngüler 'repeat' ile başlar:   repeat while x > 0 { }",
    "for":      "Bu dilde döngüler 'repeat' ile başlar:   repeat i from 1 to 10 { }",
    "break":    "Bu dilde döngüden çıkmak için 'stop' yazılır.",
    "continue": "Bu dilde bir turu atlamak için 'skip' yazılır.",
    "elif":     "Bu dilde 'elif' yok, 'else if' yazılır:   } else if x > 0 {",
    "else":     "'else' tek başına olamaz, bir 'if' bloğunun hemen arkasından gelmeli.",
}


def token_adi(t):
    """Bir token'ı hata mesajında okunur şekilde göster."""
    if t.tur == "YENİ_SATIR":
        return "satır sonu"
    if t.tur == "SON":
        return "dosyanın sonu"
    if t.tur == "İSİM":
        return f"'{t.deger}'"
    if t.tur == "SAYI":
        return f"{t.deger} sayısı"
    if t.tur == "METİN":
        return f'"{t.deger}" metni'
    return f"'{t.tur}'"


# =====================================================================
#  BÖLÜM 3: PARSER
# =====================================================================
#  Parser, token listesinin üzerinde soldan sağa yürüyen bir "okuyucu".
#  "konum" şu an hangi token'a baktığımızı gösterir.

class Parser:

    def __init__(self, tokenlar):
        self.tokenlar = tokenlar
        self.konum = 0

    # ---------- Küçük yardımcılar ----------

    def simdiki(self):
        """Şu an baktığımız token."""
        return self.tokenlar[self.konum]

    def sonraki(self):
        """Bir sonraki token (ileriye bakmak için, ilerlemeden)."""
        return self.tokenlar[min(self.konum + 1, len(self.tokenlar) - 1)]

    def bu_mu(self, *turler):
        """Şu anki token bu türlerden biri mi?"""
        return self.simdiki().tur in turler

    def ilerle(self):
        """Şu anki token'ı al ve bir adım ilerle."""
        t = self.simdiki()
        if t.tur != "SON":
            self.konum += 1
        return t

    def bekle(self, tur, aciklama):
        """Burada mutlaka 'tur' gelmeli. Gelmezse anlaşılır bir hata ver."""
        if self.bu_mu(tur):
            return self.ilerle()
        t = self.simdiki()
        raise ParserHatasi(
            f"Satır {t.satir}, sütun {t.sutun}: {aciklama} bekliyordum, "
            f"ama {token_adi(t)} geldi."
        )

    def dugum(self, d, token):
        """Düğüme, hangi token'dan başladığını (satır/sütun) yaz."""
        d.satir = token.satir
        d.sutun = token.sutun
        return d

    def bosluklari_atla(self):
        """Komutlar arasındaki satır sonlarını ve ';' işaretlerini atla."""
        while self.bu_mu("YENİ_SATIR", ";"):
            self.ilerle()

    def komut_sonu(self):
        """Bir komut bitti: arkasından satır sonu, ';', '}' ya da dosya sonu gelmeli."""
        if self.bu_mu("YENİ_SATIR", ";"):
            self.ilerle()
        elif not self.bu_mu("}", "SON"):
            t = self.simdiki()
            raise ParserHatasi(
                f"Satır {t.satir}, sütun {t.sutun}: Komut burada bitmeliydi, "
                f"ama {token_adi(t)} geldi.\n"
                f"   Aynı satıra iki komut yazmak istiyorsan araya ';' koy."
            )

    # =================================================================
    #  PROGRAM ve BLOKLAR
    # =================================================================

    def program(self):
        """Program = komutlar, dosya bitene kadar."""
        komutlar = []
        self.bosluklari_atla()
        while not self.bu_mu("SON"):
            if self.bu_mu("}"):
                t = self.simdiki()
                raise ParserHatasi(
                    f"Satır {t.satir}, sütun {t.sutun}: Bu '}}' hiçbir bloğu kapatmıyor, fazladan yazılmış."
                )
            komutlar.append(self.komut())
            self.bosluklari_atla()
        return Program(komutlar)

    def blok(self):
        """Blok = '{' komutlar '}'"""
        acilis = self.bekle("{", "bloğu başlatan '{'")
        komutlar = []
        self.bosluklari_atla()
        while not self.bu_mu("}"):
            if self.bu_mu("SON"):
                raise ParserHatasi(
                    f"Satır {acilis.satir}, sütun {acilis.sutun}: Bu '{{' hiç kapatılmamış.\n"
                    f"   Bloğun sonuna '}}' eklemeyi unutmuş olabilirsin."
                )
            komutlar.append(self.komut())
            self.bosluklari_atla()
        self.ilerle()  # '}'
        return komutlar

    # =================================================================
    #  KOMUTLAR
    # =================================================================
    #  İlk kelimeye bakarak hangi komut olduğuna karar veriyoruz.

    def komut(self):
        if self.bu_mu("var"):
            k = self.degisken_tanimi()
        elif self.bu_mu("global"):
            bas = self.ilerle()  # 'global'
            if not self.bu_mu("var"):
                raise ParserHatasi(
                    f"Satır {bas.satir}, sütun {bas.sutun}: 'global' kelimesinden sonra 'var' gelmeli.\n"
                    f"   Örnek:   global var PI = 3.14"
                )
            k = self.degisken_tanimi()
            k.global_mi = True
            self.dugum(k, bas)
        elif self.bu_mu("use"):
            k = self.use_komutu()
        elif self.bu_mu("if"):
            return self.eger()                  # '}' ile bitiyor
        elif self.bu_mu("repeat"):
            return self.tekrar()                # '}' ile bitiyor
        elif self.bu_mu("when"):
            return self.when_komutu()           # '}' ile bitiyor
        elif self.bu_mu("type"):
            return self.tip_tanimi()            # '}' ile bitiyor
        elif self.bu_mu("enum"):
            return self.enum_tanimi()           # '}' ile bitiyor
        elif self.bu_mu("extern"):
            return self.extern_blogu()          # '}' ile bitiyor
        elif self.bu_mu("import"):
            bas = self.ilerle()
            k = self.dugum(ImportKomutu(self.bekle("İSİM", "içe alınacak dosyanın adını, .vash olmadan (ör: import geometri)").deger), bas)
        elif self.bu_mu("match"):
            return self.match_komutu()          # '}' ile bitiyor
        elif self.bu_mu("İSİM") and self.simdiki().deger == "window" and self.sonraki().tur == "METİN":
            return self.pencere()               # '}' ile bitiyor
        elif self.bu_mu("stop"):
            k = self.dugum(Dur(), self.ilerle())
        elif self.bu_mu("skip"):
            k = self.dugum(Atla(), self.ilerle())
        elif self.bu_mu("while", "else"):
            self.yabanci_kelime(self.simdiki().tur)
        elif (self.bu_mu("İSİM") and self.simdiki().deger in YABANCI_KELIMELER
              and self.sonraki().tur not in ("=", "(")):
            self.yabanci_kelime(self.simdiki().deger)
        elif self.bu_mu("fn"):
            return self.fonksiyon_tanimi()      # '}' ile bitiyor, komut_sonu gerekmez
        elif self.bu_mu("return"):
            k = self.donus()
        elif self.bu_mu("İSİM") and self.sonraki().tur == "=":
            k = self.atama()
        else:
            bas = self.simdiki()
            e = self.ifade()
            if self.bu_mu("="):                          # liste[i] = x   /   nesne.alan = x
                esittir = self.ilerle()
                if isinstance(e, Erisim):
                    k = self.dugum(ElemanAtama(e.liste, e.sira, self.ifade()), bas)
                elif isinstance(e, Ozellik):
                    k = self.dugum(AlanAtama(e.nesne, e.ad, self.ifade()), bas)
                else:
                    raise ParserHatasi(
                        f"Satır {esittir.satir}, sütun {esittir.sutun}: '=' işaretinin solunda bir değişken, "
                        f"liste elemanı (liste[i]) ya da alan (nesne.alan) olmalı."
                    )
            else:
                k = self.dugum(IfadeKomutu(e), bas)
        self.komut_sonu()
        return k

    def degisken_tanimi(self):
        """var İSİM [: tip] = ifade"""
        bas = self.ilerle()  # 'var'
        ad = self.bekle("İSİM", "değişkenin adını").deger
        tip = None
        if self.bu_mu(":"):
            self.ilerle()
            tip = self.tip()
        self.bekle("=", f"'{ad}' değişkenine değer vermek için '='")
        deger = self.ifade()
        return self.dugum(DegiskenTanimi(ad, tip, deger), bas)

    # ---------- if / else ----------
    def eger(self):
        """if kosul blok [else if ... | else blok]"""
        bas = self.ilerle()  # 'if'
        kosul = self.ifade()
        govde = self.blok()
        degilse = None
        # "else" aynı satırda da ("} else {") alt satırda da olabilir
        geri = self.konum
        self.bosluklari_atla()
        if self.bu_mu("else"):
            self.ilerle()
            if self.bu_mu("if"):
                degilse = [self.eger()]          # else if → içinde yeni bir if
            else:
                degilse = self.blok()
        else:
            self.konum = geri
        return self.dugum(Eger(kosul, govde, degilse), bas)

    # ---------- type ----------
    def tip_tanimi(self):
        """type Ad { alan: tip [= değer]   ...   fn [change] metot(...) { } ... }"""
        bas = self.ilerle()  # 'type'
        ad = self.bekle("İSİM", "tipin adını").deger
        acilis = self.bekle("{", "tipin içini başlatan '{'")
        alanlar, metotlar = [], []
        self.bosluklari_atla()
        while not self.bu_mu("}"):
            if self.bu_mu("SON"):
                raise ParserHatasi(f"Satır {acilis.satir}, sütun {acilis.sutun}: '{ad}' tipinin '{{' işareti kapatılmamış.")
            if self.bu_mu("fn"):
                metotlar.append(self.fonksiyon_tanimi())
            else:
                t = self.bekle("İSİM", f"'{ad}' tipinin içinde bir alan (ör: ad: text) ya da metot (fn ...)")
                self.bekle(":", f"'{t.deger}' alanının tipini yazmak için ':'")
                tip = self.tip()
                varsayilan = None
                if self.bu_mu("="):
                    self.ilerle()
                    varsayilan = self.ifade()
                alanlar.append(self.dugum(Alan(t.deger, tip, varsayilan), t))
                self.komut_sonu()
            self.bosluklari_atla()
        self.ilerle()  # '}'
        return self.dugum(TipTanimi(ad, alanlar, metotlar), bas)

    # ---------- extern: C'de yazılmış hazır fonksiyonlar ----------
    def extern_blogu(self):
        """extern "kutuphane" { fn ad(p: tip, ...) [-> tip] ... }"""
        bas = self.ilerle()  # 'extern'
        k = self.bekle("METİN", 'kütüphanenin adını tırnak içinde (ör: extern "msvcrt" { ... })')
        izinler = []
        if self.baglamsal_mi("needs"):                 # extern "msvcrt" needs files { ... }
            self.ilerle()
            izinler.append(self.bekle("İSİM", "gereken iznin adını (ör: needs files)"))
            while self.bu_mu(","):
                self.ilerle()
                izinler.append(self.bekle("İSİM", "gereken iznin adını"))
        acilis = self.bekle("{", "fonksiyonların listesini başlatan '{'")
        fonksiyonlar = []
        self.bosluklari_atla()
        while not self.bu_mu("}"):
            if self.bu_mu("SON"):
                raise ParserHatasi(f"Satır {acilis.satir}, sütun {acilis.sutun}: extern bloğunun '{{' işareti kapatılmamış.")
            fn = self.bekle("fn", "'fn' ile başlayan bir fonksiyon tanıtımı (ör: fn sqrt(x: float) -> float)")
            ad = self.bekle("İSİM", "fonksiyonun adını").deger
            self.bekle("(", "parametreleri başlatan '('")
            parametreler = []
            while not self.bu_mu(")"):
                p = self.bekle("İSİM", "parametrenin adını")
                self.bekle(":", f"'{p.deger}' parametresinin tipini yazmak için ':'")
                parametreler.append(self.dugum(Parametre(p.deger, self.tip()), p))
                if not self.bu_mu(")"):
                    self.bekle(",", "parametreleri ayıran ',' ya da kapatan ')'")
            self.ilerle()  # ')'
            donus = None
            if self.bu_mu("->"):
                self.ilerle()
                donus = self.tip()
            if self.bu_mu("{"):
                t = self.simdiki()
                raise ParserHatasi(f"Satır {t.satir}, sütun {t.sutun}: extern içindeki fonksiyonların gövdesi yazılmaz; "
                                   f"kodu zaten kütüphanede hazır. Sadece adını ve tiplerini yaz.")
            fonksiyonlar.append(self.dugum(ExternFonksiyon(ad, parametreler, donus), fn))
            self.bosluklari_atla()
        self.ilerle()  # '}'
        return self.dugum(ExternBlok(k.deger, fonksiyonlar, izinler), bas)

    # ---------- enum ve match ----------
    def enum_tanimi(self):
        """enum Ad { Cesit   Cesit(alan: tip, ...)   ... }   (çeşitler satırla, ';' ya da ',' ile ayrılır)"""
        bas = self.ilerle()  # 'enum'
        ad = self.bekle("İSİM", "enum'un adını").deger
        acilis = self.bekle("{", f"'{ad}' enum'unun çeşitlerini başlatan '{{'")
        cesitler = []
        self.bosluklari_atla()
        while not self.bu_mu("}"):
            if self.bu_mu("SON"):
                raise ParserHatasi(f"Satır {acilis.satir}, sütun {acilis.sutun}: '{ad}' enum'unun '{{' işareti kapatılmamış.")
            t = self.bekle("İSİM", f"'{ad}' enum'unun bir çeşidinin adını (ör: Nakit ya da Kart(no: text))")
            alanlar = []
            if self.bu_mu("("):
                self.ilerle()
                while not self.bu_mu(")"):
                    a = self.bekle("İSİM", "alanın adını (ör: no: text)")
                    self.bekle(":", f"'{a.deger}' alanının tipini yazmak için ':'")
                    alanlar.append(self.dugum(Alan(a.deger, self.tip(), None), a))
                    if not self.bu_mu(")"):
                        self.bekle(",", "alanları ayıran ',' ya da kapatan ')'")
                self.ilerle()  # ')'
            cesitler.append(self.dugum(EnumCesidi(t.deger, alanlar), t))
            if self.bu_mu(","):
                self.ilerle()
            self.bosluklari_atla()
        self.ilerle()  # '}'
        return self.dugum(EnumTanimi(ad, cesitler), bas)

    def match_komutu(self):
        """match ifade { Cesit [ (ad, ad...) ] { ... }   ...   [else { ... }] }"""
        bas = self.ilerle()  # 'match'
        deger = self.ifade()
        acilis = self.bekle("{", "match'in durumlarını başlatan '{'")
        durumlar, degilse = [], None
        self.bosluklari_atla()
        while not self.bu_mu("}"):
            if self.bu_mu("SON"):
                raise ParserHatasi(f"Satır {acilis.satir}, sütun {acilis.sutun}: match'in '{{' işareti kapatılmamış.")
            if self.bu_mu("else"):
                e = self.ilerle()
                if degilse is not None:
                    raise ParserHatasi(f"Satır {e.satir}, sütun {e.sutun}: Bir match'te tek bir 'else' olabilir.")
                degilse = self.blok()
            else:
                t = self.bekle("İSİM", "bir çeşidin adını (ör: Kart(no, taksit) { ... }) ya da 'else'")
                adlar = []
                if self.bu_mu("("):
                    self.ilerle()
                    while not self.bu_mu(")"):
                        adlar.append(self.bekle("İSİM", "alana verilecek adı").deger)
                        if not self.bu_mu(")"):
                            self.bekle(",", "adları ayıran ',' ya da kapatan ')'")
                    self.ilerle()  # ')'
                durumlar.append(self.dugum(MatchDurumu(t.deger, adlar, self.blok()), t))
            self.bosluklari_atla()
        self.ilerle()  # '}'
        return self.dugum(MatchKomutu(deger, durumlar, degilse), bas)

    # ---------- window (görsel arayüz) ----------
    def pencere(self):
        """window "Başlık" { arayüz parçaları }"""
        bas = self.ilerle()  # 'window'
        t = self.ilerle()    # başlık metni
        baslik = self.dugum(Metin(t.deger), t)
        return self.dugum(Pencere(baslik, self.arayuz_blogu("pencerenin")), bas)

    def arayuz_blogu(self, kimin):
        acilis = self.bekle("{", f"{kimin} içini başlatan '{{'")
        ogeler = []
        self.bosluklari_atla()
        while not self.bu_mu("}"):
            if self.bu_mu("SON"):
                raise ParserHatasi(f"Satır {acilis.satir}, sütun {acilis.sutun}: Bu '{{' hiç kapatılmamış.")
            ogeler.append(self.arayuz_ogesi())
            self.bosluklari_atla()
        self.ilerle()  # '}'
        return ogeler

    def arayuz_ogesi(self):
        t = self.simdiki()
        tur = t.deger if t.tur == "İSİM" else None
        if tur not in ArayuzOgesi.TURLER:
            ne = f"'{t.deger}'" if t.deger is not None else f"'{t.tur}'"
            raise ParserHatasi(
                f"Satır {t.satir}, sütun {t.sutun}: Pencerenin içinde {ne} yazılamaz.\n"
                f"   Kullanılabilenler: label, button, textbox, checkbox, row, list\n"
                f"   Hesap yapmak istiyorsan bunu bir button'un bloğuna ya da pencereden önceye yaz."
            )
        self.ilerle()
        if tur == "row":
            return self.dugum(ArayuzOgesi("row", cocuklar=self.arayuz_blogu("row'un")), t)
        if tur == "list":
            # list urun, i in urunler -> secili { şablon }
            ornek = "(ör: list urun, i in urunler { label urun })"
            eleman = self.bekle("İSİM", f"her satırdaki elemana verilecek adı {ornek}").deger
            sira_adi = None
            if self.bu_mu(","):
                self.ilerle()
                sira_adi = self.bekle("İSİM", f"satırın sıra numarasına verilecek adı {ornek}").deger
            if not self.baglamsal_mi("in"):
                s = self.simdiki()
                raise ParserHatasi(f"Satır {s.satir}, sütun {s.sutun}: '{eleman}' adından sonra 'in' ve "
                                   f"gösterilecek liste gelmeli {ornek}.")
            self.ilerle()
            kaynak = self.ifade()
            hedef = None
            if self.bu_mu("->"):
                self.ilerle()
                hedef = self.bekle("İSİM", "seçilen satırın sırasını tutacak değişkenin adını").deger
            o = ArayuzOgesi("list", hedef=hedef, cocuklar=self.arayuz_blogu("list'in"),
                            eleman=eleman, sira_adi=sira_adi, kaynak=kaynak)
            return self.dugum(o, t)
        metin = self.ifade()
        if tur == "label":
            o = ArayuzOgesi("label", metin)
        elif tur == "button":
            o = ArayuzOgesi("button", metin, govde=self.blok())
        else:                                        # textbox / checkbox
            self.bekle("->", f"{tur}'un bağlanacağı değişkeni göstermek için '->' (ör: {tur} \"Adın\" -> ad)")
            hedef = self.bekle("İSİM", "bağlanacak değişkenin adını").deger
            o = ArayuzOgesi(tur, metin, hedef=hedef)
        if tur != "button":
            self.komut_sonu()
        return self.dugum(o, t)

    # ---------- when ----------
    def when_komutu(self):
        """when [later] kosul blok"""
        bas = self.ilerle()  # 'when'
        bekle = False
        # "later" bağlamsal kelime: arkasından bir ifadenin BAŞLANGICI geliyorsa özel anlamlı.
        # "when later is 5" yazılırsa 'is' bir ifade başlatamaz → 'later' bir değişkendir.
        if (self.bu_mu("İSİM") and self.simdiki().deger == "later"
                and self.sonraki().tur in ("İSİM", "SAYI", "ONDALIK", "METİN", "(", "[", "-",
                                            "not", "true", "false")):
            self.ilerle()
            bekle = True
        kosul = self.ifade()
        return self.dugum(WhenKomutu(kosul, self.blok(), bekle), bas)

    # ---------- Döngüler ----------
    def baglamsal_mi(self, kelime):
        """Şu anki token, özel anlamlı bir isim mi? (from, to, step)"""
        return self.bu_mu("İSİM") and self.simdiki().deger == kelime

    def tekrar(self):
        bas = self.ilerle()  # 'repeat'

        # repeat while kosul { }
        if self.bu_mu("while"):
            self.ilerle()
            kosul = self.ifade()
            return self.dugum(TekrarSurece(kosul, self.blok()), bas)

        # repeat i from 1 to 10 [step 2] { }
        if self.bu_mu("İSİM") and self.sonraki().tur == "İSİM" and self.sonraki().deger == "from":
            ad = self.ilerle().deger
            self.ilerle()  # 'from'
            bas_deger = self.ifade()
            if not self.baglamsal_mi("to"):
                t = self.simdiki()
                raise ParserHatasi(
                    f"Satır {t.satir}, sütun {t.sutun}: Nereye kadar sayılacağını yazmak için 'to' bekliyordum.\n"
                    f"   Örnek:   repeat {ad} from 1 to 10 {{ }}"
                )
            self.ilerle()  # 'to'
            son = self.ifade()
            adim = None
            if self.baglamsal_mi("step"):
                self.ilerle()
                adim = self.ifade()
            return self.dugum(TekrarSayac(ad, bas_deger, son, adim, self.blok()), bas)

        # repeat 3 { }
        sayi = self.ifade()
        return self.dugum(TekrarSayi(sayi, self.blok()), bas)

    def yabanci_kelime(self, kelime):
        """Başka dillerden alışkanlıkla yazılan kelimeler için yardımcı hata."""
        t = self.simdiki()
        raise ParserHatasi(f"Satır {t.satir}, sütun {t.sutun}: {YABANCI_KELIMELER[kelime]}")

    def use_komutu(self):
        """use İSİM   /   use change İSİM"""
        bas = self.ilerle()  # 'use'
        degistirebilir = False
        # "change" bağlamsal kelime: sadece "use"dan hemen sonra ve
        # arkasından bir isim daha geliyorsa özel anlam taşır.
        # (Böylece "use change" diye "change" adlı bir değişken de çağrılabilir.)
        if (self.bu_mu("İSİM") and self.simdiki().deger == "change"
                and self.sonraki().tur == "İSİM"):
            self.ilerle()
            degistirebilir = True
        ad = self.bekle("İSİM", "dışarıdan çağrılacak değişkenin adını").deger
        return self.dugum(UseKomutu(ad, degistirebilir), bas)

    def atama(self):
        """İSİM = ifade"""
        ad_token = self.ilerle()
        self.ilerle()  # '='
        deger = self.ifade()
        return self.dugum(Atama(ad_token.deger, deger), ad_token)

    def fonksiyon_tanimi(self):
        """fn İSİM ( [parametre, ...] ) [-> tip] blok"""
        bas = self.ilerle()  # 'fn'
        # "fn change ad(...)": nesneyi değiştiren metot. "change" bağlamsal: arkasından bir ad geliyorsa özel.
        degistirir = False
        if (self.bu_mu("İSİM") and self.simdiki().deger == "change"
                and self.sonraki().tur == "İSİM"):
            self.ilerle()
            degistirir = True
        ad = self.bekle("İSİM", "fonksiyonun adını").deger
        self.bekle("(", "parametreleri başlatan '('")

        parametreler = []
        while not self.bu_mu(")"):
            p_token = self.bekle("İSİM", "parametrenin adını")
            self.bekle(":", f"'{p_token.deger}' parametresinin tipini yazmak için ':'")
            parametreler.append(self.dugum(Parametre(p_token.deger, self.tip()), p_token))
            if not self.bu_mu(")"):
                self.bekle(",", "parametreleri ayıran ',' ya da kapatan ')'")
        self.ilerle()  # ')'

        donus_tipi = None
        if self.bu_mu("->"):
            self.ilerle()
            donus_tipi = self.tip()

        govde = self.blok()
        return self.dugum(FonksiyonTanimi(ad, parametreler, donus_tipi, govde, degistirir), bas)

    def donus(self):
        """return [ifade]"""
        bas = self.ilerle()  # 'return'
        deger = None
        if not self.bu_mu("YENİ_SATIR", ";", "}", "SON"):
            deger = self.ifade()
        return self.dugum(Donus(deger), bas)

    # =================================================================
    #  TİPLER
    # =================================================================

    def satir_sonlarini_atla(self):
        while self.bu_mu("YENİ_SATIR"):
            self.ilerle()

    def tip(self):
        """tip = (İSİM  |  [ tip ]  |  { tip: tip }) [?]"""
        bas = self.simdiki()
        t = self.temel_tip()
        if self.bu_mu("?"):                          # Ogrenci?  → yok olabilir
            self.ilerle()
            return self.dugum(SecmeliTip(t), bas)
        return t

    def temel_tip(self):
        bas = self.simdiki()
        if self.bu_mu("["):
            self.ilerle()
            eleman = self.tip()
            self.bekle("]", "liste tipini kapatan ']'")
            return self.dugum(ListeTipi(eleman), bas)
        if self.bu_mu("{"):
            self.ilerle()
            anahtar = self.tip()
            self.bekle(":", "sözlük tipinde anahtarı değerden ayıran ':' (ör: {text: int})")
            deger = self.tip()
            self.bekle("}", "sözlük tipini kapatan '}'")
            return self.dugum(SozlukTipi(anahtar, deger), bas)
        t = self.bekle("İSİM", "bir tip adı (ör: int)")
        ad = t.deger
        while self.bu_mu(".") and self.sonraki().tur == "İSİM":       # geometri.Nokta
            self.ilerle()
            ad += "." + self.ilerle().deger
        return self.dugum(TipAdi(ad), t)

    # =================================================================
    #  İFADELER ve İŞLEM ÖNCELİĞİ
    # =================================================================
    #  İşlem önceliğini fonksiyonların SIRASI belirliyor.
    #  Her seviye, kendinden bir sonraki (daha öncelikli) seviyeyi çağırır:
    #
    #    ifade
    #     └─ karsilastirma    is, is not, <, >, <=, >=   (en son yapılır)
    #         └─ toplama      +  -
    #             └─ carpma   *  /  //  %
    #                 └─ tekli       -x
    #                     └─ birincil   5, "metin", x, f(), ( ... )  (en önce)
    #
    #  Ağacın DERİNİNDE kalan işlem ÖNCE yapılır. "2 + 3 * 4" yazınca
    #  toplama, çarpmayı bir alt seviyede çağırdığı için "3 * 4" ağaçta
    #  daha derine yerleşir.

    #  Mantık seviyeleri karşılaştırmanın da üstünde (en son yapılırlar):
    #    veya (or) → ve (and) → degil (not) → karsilastirma → ...

    def ifade(self):
        e = self.veya()
        if self.bu_mu("else") and self.sonraki().tur == ":":     # bul("Can") else: yedek
            t = self.ilerle()
            self.ilerle()  # ':'
            e = self.dugum(YedekliDeger(e, self.ifade()), t)
        return e

    def veya(self):
        sol = self.ve()
        while self.bu_mu("or"):
            op = self.ilerle()
            sol = self.dugum(IkiliIslem("or", sol, self.ve()), op)
        return sol

    def ve(self):
        sol = self.degil()
        while self.bu_mu("and"):
            op = self.ilerle()
            sol = self.dugum(IkiliIslem("and", sol, self.degil()), op)
        return sol

    def degil(self):
        if self.bu_mu("not"):
            op = self.ilerle()
            return self.dugum(TekliIslem("not", self.degil()), op)
        return self.karsilastirma()

    def karsilastirma(self):
        sol = self.toplama()
        if self.bu_mu("is", "<", ">", "<=", ">="):
            op = self.ilerle()
            isaret = op.tur
            if isaret == "is" and self.bu_mu("not"):
                self.ilerle()
                isaret = "is not"
            sag = self.toplama()
            sol = self.dugum(IkiliIslem(isaret, sol, sag), op)
        return sol

    def toplama(self):
        sol = self.carpma()
        while self.bu_mu("+", "-"):           # 1 + 2 + 3 → (1 + 2) + 3
            op = self.ilerle()
            sag = self.carpma()
            sol = self.dugum(IkiliIslem(op.tur, sol, sag), op)
        return sol

    def carpma(self):
        sol = self.tekli()
        while self.bu_mu("*", "/", "//", "%"):
            op = self.ilerle()
            sag = self.tekli()
            sol = self.dugum(IkiliIslem(op.tur, sol, sag), op)
        return sol

    def tekli(self):
        if self.bu_mu("-"):
            op = self.ilerle()
            return self.dugum(TekliIslem("-", self.tekli()), op)
        return self.sonek(self.birincil())

    def sonek(self, e):
        """Bir değerin arkasından gelen [ ] ve . işlemleri:
           liste[2]   liste.length   liste.add(5)   tablo[1][2]"""
        while True:
            if self.bu_mu("["):
                ac = self.ilerle()
                sira = self.ifade()
                if self.baglamsal_mi("to"):                  # metin[2 to 4]
                    to = self.ilerle()
                    sira = self.dugum(Aralik(sira, self.ifade()), to)
                self.bekle("]", "elemanın sırasını kapatan ']'")
                e = self.dugum(Erisim(e, sira), ac)
            elif self.bu_mu("."):
                nokta = self.ilerle()
                ad = self.bekle("İSİM", "noktadan sonra bir ad (ör: length, add)").deger
                if self.bu_mu("("):
                    self.ilerle()
                    argumanlar, yedek, isimli = [], None, []
                    self.satir_sonlarini_atla()
                    while not self.bu_mu(")"):
                        if self.bu_mu("else") and self.sonraki().tur == ":":     # sozluk.get(k, else: 0)
                            self.ilerle()
                            self.ilerle()
                            yedek = self.ifade()
                        elif self.bu_mu("İSİM") and self.sonraki().tur == ":":  # Odeme.Kart(no: "1234")
                            at = self.ilerle()
                            self.ilerle()  # ':'
                            isimli.append((at.deger, self.ifade(), at))
                        else:
                            argumanlar.append(self.ifade())
                        self.satir_sonlarini_atla()
                        if not self.bu_mu(")"):
                            self.bekle(",", "değerleri ayıran ',' ya da kapatan ')'")
                            self.satir_sonlarini_atla()
                    self.ilerle()  # ')'
                    e = self.dugum(MetotCagrisi(e, ad, argumanlar), nokta)
                    e.yedek = yedek
                    e.isimli = isimli
                else:
                    e = self.dugum(Ozellik(e, ad), nokta)
            else:
                return e

    def birincil(self):
        t = self.simdiki()

        if t.tur == "SAYI":
            self.ilerle()
            return self.dugum(Sayi(t.deger), t)

        if t.tur == "ONDALIK":
            self.ilerle()
            return self.dugum(Ondalik(t.deger), t)

        if t.tur == "measure":                       # measure { ... }
            self.ilerle()
            return self.dugum(Olcum(self.blok()), t)

        if t.tur in ("true", "false"):
            self.ilerle()
            return self.dugum(Mantiksal(t.tur == "true"), t)

        if t.tur == "none":
            self.ilerle()
            return self.dugum(Yok(), t)

        if t.tur == "METİN":
            self.ilerle()
            return self.dugum(Metin(t.deger), t)

        if t.tur == "İSİM":
            self.ilerle()
            if self.bu_mu("("):                      # isim( → fonksiyon çağrısı / tip oluşturma
                self.ilerle()
                argumanlar, isimli = [], []
                self.satir_sonlarini_atla()                # argümanlar birden çok satıra yazılabilir
                while not self.bu_mu(")"):
                    if self.bu_mu("İSİM", "else") and self.sonraki().tur == ":":   # ad: "Ali"  /  else: 0
                        at = self.ilerle()
                        self.ilerle()  # ':'
                        isimli.append((at.deger if at.tur == "İSİM" else "else", self.ifade(), at))
                    else:
                        arg = self.ifade()
                        if self.baglamsal_mi("to"):            # random(1 to 6)
                            to = self.ilerle()
                            arg = self.dugum(Aralik(arg, self.ifade()), to)
                        argumanlar.append(arg)
                    self.satir_sonlarini_atla()
                    if not self.bu_mu(")"):
                        self.bekle(",", "değerleri ayıran ',' ya da kapatan ')'")
                        self.satir_sonlarini_atla()
                self.ilerle()  # ')'
                return self.dugum(Cagri(t.deger, argumanlar, isimli), t)
            return self.dugum(Isim(t.deger), t)      # sadece isim → değişken

        if t.tur == "(":
            self.ilerle()
            ic = self.ifade()
            self.bekle(")", "parantezi kapatan ')'")
            return ic                                 # parantezin kendisi ağaçta yer almaz!

        if t.tur == "[":
            self.ilerle()
            elemanlar = []
            self.satir_sonlarini_atla()                # liste birden çok satıra yazılabilir
            while not self.bu_mu("]"):
                elemanlar.append(self.ifade())
                self.satir_sonlarini_atla()
                if not self.bu_mu("]"):
                    self.bekle(",", "elemanları ayıran ',' ya da kapatan ']'")
                    self.satir_sonlarini_atla()
            self.ilerle()  # ']'
            return self.dugum(Liste(elemanlar), t)

        if t.tur == "{":                             # {"Ali": 90, "Ayşe": 85}
            self.ilerle()
            anahtarlar, degerler = [], []
            self.satir_sonlarini_atla()
            while not self.bu_mu("}"):
                anahtarlar.append(self.ifade())
                if not anahtarlar[1:] and self.bu_mu("}"):
                    # {fiyat * 2} → büyük ihtimalle metnin dışında { } kullanıldı
                    raise ParserHatasi(
                        f"Satır {t.satir}, sütun {t.sutun}: Süslü parantez {{ }} sadece tırnak içindeki yazılarda, "
                        f"bir değeri yazının içine koymak için kullanılır:   print(\"Toplam: {{fiyat * 2}}\")\n"
                        f"   Yazının dışında parantezsiz yaz:   var toplam = fiyat * 2"
                    )
                self.bekle(":", "anahtarı değerinden ayıran ':' (ör: {\"Ali\": 90})")
                degerler.append(self.ifade())
                self.satir_sonlarini_atla()
                if not self.bu_mu("}"):
                    self.bekle(",", "çiftleri ayıran ',' ya da kapatan '}'")
                    self.satir_sonlarini_atla()
            self.ilerle()  # '}'
            return self.dugum(SozlukDegeri(anahtarlar, degerler), t)

        raise ParserHatasi(
            f"Satır {t.satir}, sütun {t.sutun}: Burada bir değer bekliyordum "
            f"(sayı, metin, değişken...), ama {token_adi(t)} geldi."
        )


def agac_kur(kod):
    """Kodu önce lexer'dan, sonra parser'dan geçir; ağacı döndür."""
    tokenlar = kelimelere_ayir(kod)
    return Parser(tokenlar).program()


# =====================================================================
#  BÖLÜM 4: AĞACI GÖSTERME
# =====================================================================
#  Ağacı hem terminalde hem arayüzde göstermek için her düğümü
#  {etiket, bilgi, satır, çocuklar} şeklinde sade bir sözlüğe çeviriyoruz.

def tip_yazisi(tip):
    if tip is None:
        return None
    if isinstance(tip, ListeTipi):
        return f"[{tip_yazisi(tip.eleman)}]"
    if isinstance(tip, SozlukTipi):
        return f"{{{tip_yazisi(tip.anahtar)}: {tip_yazisi(tip.deger)}}}"
    if isinstance(tip, SecmeliTip):
        return tip_yazisi(tip.ic) + "?"
    return tip.ad


def sozluge_cevir(d):
    def k(etiket, bilgi=None, cocuklar=()):
        return {"etiket": etiket, "bilgi": bilgi, "satir": d.satir,
                "cocuklar": [sozluge_cevir(c) for c in cocuklar if c is not None]}

    if isinstance(d, Program):
        return k("Program", cocuklar=d.komutlar)
    if isinstance(d, DegiskenTanimi):
        tip = tip_yazisi(d.tip)
        etiket = "GlobalDeğişken" if d.global_mi else "DeğişkenTanımı"
        return k(etiket, d.ad + (f": {tip}" if tip else "  (tip tahmin edilecek)"), [d.deger])
    if isinstance(d, Eger):
        cocuklar = [d.kosul, *d.govde]
        sonuc = k("If", cocuklar=[d.kosul])
        sonuc["cocuklar"].append({"etiket": "Doğruysa", "bilgi": None, "satir": d.satir,
                                  "cocuklar": [sozluge_cevir(c) for c in d.govde]})
        if d.degilse:
            sonuc["cocuklar"].append({"etiket": "Değilse", "bilgi": None, "satir": d.satir,
                                      "cocuklar": [sozluge_cevir(c) for c in d.degilse]})
        return sonuc
    if isinstance(d, TekrarSayi):
        return k("Repeat", "(sayı kadar)", [d.sayi, *d.govde])
    if isinstance(d, TekrarSurece):
        return k("Repeat while", None, [d.kosul, *d.govde])
    if isinstance(d, TekrarSayac):
        adim = [d.adim] if d.adim else []
        return k("Repeat", f"{d.ad} from…to" + ("…step" if d.adim else ""), [d.bas, d.son, *adim, *d.govde])
    if isinstance(d, TipTanimi):
        alanlar = [{"etiket": "Alan", "bilgi": f"{a.ad}: {tip_yazisi(a.tip)}" + (" = ..." if a.varsayilan else ""),
                    "satir": a.satir, "cocuklar": []} for a in d.alanlar]
        return {"etiket": "Tip", "bilgi": d.ad, "satir": d.satir,
                "cocuklar": alanlar + [sozluge_cevir(m) for m in d.metotlar]}
    if isinstance(d, Aralik):
        return k("Aralık", "to", [d.bas, d.son])
    if isinstance(d, Olcum):
        return k("Measure", "(süre)", d.govde)
    if isinstance(d, AlanAtama):
        return k("AlanAtama", "." + d.alan + " =", [d.nesne, d.deger])
    if isinstance(d, WhenKomutu):
        sonuc = k("When", "later (değişimi bekle)" if d.bekle else None, [d.kosul])
        sonuc["cocuklar"].append({"etiket": "Olunca", "bilgi": None, "satir": d.satir,
                                  "cocuklar": [sozluge_cevir(c) for c in d.govde]})
        return sonuc
    if isinstance(d, ImportKomutu):
        return k("Import", d.ad + ".vash")
    if isinstance(d, ExternBlok):
        izin = (" needs " + ", ".join(t.deger for t in d.izinler)) if d.izinler else ""
        return {"etiket": "Extern", "bilgi": f'"{d.kutuphane}"{izin}', "satir": d.satir, "cocuklar": [
            {"etiket": "C fonksiyonu", "satir": f.satir, "cocuklar": [],
             "bilgi": f.ad + "(" + ", ".join(f"{p.ad}: {tip_yazisi(p.tip)}" for p in f.parametreler) + ")"
                      + (f" -> {tip_yazisi(f.donus_tipi)}" if f.donus_tipi else "")} for f in d.fonksiyonlar]}
    if isinstance(d, EnumTanimi):
        cesitler = [{"etiket": "Çeşit", "bilgi": c.ad + (
            "(" + ", ".join(f"{a.ad}: {tip_yazisi(a.tip)}" for a in c.alanlar) + ")" if c.alanlar else ""),
            "satir": c.satir, "cocuklar": []} for c in d.cesitler]
        return {"etiket": "Enum", "bilgi": d.ad, "satir": d.satir, "cocuklar": cesitler}
    if isinstance(d, MatchKomutu):
        sonuc = k("Match", None, [d.deger])
        for m in d.durumlar:
            sonuc["cocuklar"].append({"etiket": "Durum", "bilgi": m.cesit + (f"({', '.join(m.adlar)})" if m.adlar else ""),
                                      "satir": m.satir, "cocuklar": [sozluge_cevir(c) for c in m.govde]})
        if d.degilse:
            sonuc["cocuklar"].append({"etiket": "Değilse", "bilgi": None, "satir": d.satir,
                                      "cocuklar": [sozluge_cevir(c) for c in d.degilse]})
        return sonuc
    if isinstance(d, Pencere):
        return k("Window", f'"{d.baslik.deger}"', d.ogeler)
    if isinstance(d, ArayuzOgesi):
        bilgi = f"-> {d.hedef}" if d.hedef else None
        if d.tur == "list":
            bilgi = d.eleman + (f", {d.sira_adi}" if d.sira_adi else "") + " in …" + (f"  -> {d.hedef}" if d.hedef else "")
        return k(d.tur.capitalize(), bilgi, [d.kaynak, d.metin, *d.govde, *d.cocuklar])
    if isinstance(d, Dur):
        return k("Stop")
    if isinstance(d, Atla):
        return k("Skip")
    if isinstance(d, UseKomutu):
        return k("Use", d.ad + ("  (değiştirebilir)" if d.degistirebilir else "  (sadece okur)"))
    if isinstance(d, Ondalik):
        return k("Ondalık", str(d.deger))
    if isinstance(d, Mantiksal):
        return k("Bool", "true" if d.deger else "false")
    if isinstance(d, Atama):
        return k("Atama", d.ad, [d.deger])
    if isinstance(d, FonksiyonTanimi):
        parametreler = ", ".join(f"{p.ad}: {tip_yazisi(p.tip)}" for p in d.parametreler)
        donus = f" -> {tip_yazisi(d.donus_tipi)}" if d.donus_tipi else ""
        on_ek = "change " if d.degistirir else ""
        return k("FonksiyonTanımı", f"{on_ek}{d.ad}({parametreler}){donus}", d.govde)
    if isinstance(d, Donus):
        return k("Dönüş", cocuklar=[d.deger])
    if isinstance(d, IfadeKomutu):
        return sozluge_cevir(d.ifade)
    if isinstance(d, Sayi):
        return k("Sayı", str(d.deger))
    if isinstance(d, Metin):
        return k("Metin", f'"{d.deger}"')
    if isinstance(d, Isim):
        return k("Değişken", d.ad)
    if isinstance(d, IkiliIslem):
        return k("İşlem", d.isaret, [d.sol, d.sag])
    if isinstance(d, TekliIslem):
        return k("İşlem", d.isaret + (" (eksi)" if d.isaret == "-" else ""), [d.ifade])
    if isinstance(d, Cagri):
        return k("Çağrı", d.ad + "(...)", list(d.argumanlar) + [deger for _, deger, _ in d.isimli])
    if isinstance(d, Liste):
        return k("Liste", f"{len(d.elemanlar)} eleman", d.elemanlar)
    if isinstance(d, Yok):
        return k("None")
    if isinstance(d, YedekliDeger):
        return k("Yedekli", "else:", [d.deger, d.yedek])
    if isinstance(d, SozlukDegeri):
        return k("Sözlük", f"{len(d.anahtarlar)} çift", [x for c in zip(d.anahtarlar, d.degerler) for x in c])
    if isinstance(d, Erisim):
        return k("Eleman", "[ ]", [d.liste, d.sira])
    if isinstance(d, Ozellik):
        return k("Özellik", "." + d.ad, [d.nesne])
    if isinstance(d, MetotCagrisi):
        return k("Metot", "." + d.ad + "(...)", [d.nesne, *d.argumanlar])
    if isinstance(d, ElemanAtama):
        return k("ElemanAtama", "[ ] =", [d.liste, d.sira, d.deger])
    return k(type(d).__name__)


def agaci_yazdir(s, on_ek="", son_mu=True, kok=True):
    """Ağacı terminale ├─ └─ çizgileriyle yazdır."""
    baglanti = "" if kok else ("└─ " if son_mu else "├─ ")
    bilgi = f" {s['bilgi']}" if s["bilgi"] else ""
    print(f"{on_ek}{baglanti}{s['etiket']}{bilgi}")
    yeni_on_ek = on_ek + ("" if kok else ("   " if son_mu else "│  "))
    for i, c in enumerate(s["cocuklar"]):
        agaci_yazdir(c, yeni_on_ek, i == len(s["cocuklar"]) - 1, False)


# ---------------------------------------------------------------------
#  Kullanım:  python derleyici\parser.py ornekler\ilk.vash
# ---------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from lexer import LexerHatasi

    with open(sys.argv[1], encoding="utf-8-sig") as f:
        kod = f.read()
    try:
        agac = agac_kur(kod)
    except (LexerHatasi, ParserHatasi) as hata:
        print("HATA:", hata)
        sys.exit(1)
    agaci_yazdir(sozluge_cevir(agac))
