# =====================================================================
#  1. İSTASYON: LEXER (Kelimelere Ayırıcı)
# =====================================================================
#
#  Görevi: Kodu harf harf okuyup "kelimelere" (token) ayırmak.
#
#  Örnek:
#      var x: int = 5
#  şuna dönüşür:
#      [var] [İSİM x] [:] [İSİM int] [=] [SAYI 5] [YENİ_SATIR]
#
#  Lexer kodun ANLAMINI bilmez. Sadece "bu bir sayı", "bu bir isim",
#  "bu bir iki nokta" der. Anlamı 2. istasyon (parser) çıkaracak.
# =====================================================================


# ---------------------------------------------------------------------
#  TOKEN: Tek bir "kelime"
# ---------------------------------------------------------------------
#  Her token'ın 4 bilgisi var:
#    tur   : Ne tür bir kelime? ("SAYI", "İSİM", "+" ...)
#    deger : Kelimenin kendisi (5, "x" ...)
#    satir : Kodun kaçıncı satırında? (hata mesajı için)
#    sutun : Satırın kaçıncı harfinde? (hata mesajı için)
class Token:
    def __init__(self, tur, deger, satir, sutun):
        self.tur = tur
        self.deger = deger
        self.satir = satir
        self.sutun = sutun

    # Token'ı ekrana yazdırınca nasıl görüneceği
    def __repr__(self):
        if self.deger is None:
            return f"[{self.tur}]"
        return f"[{self.tur} {self.deger!r}]"


# ---------------------------------------------------------------------
#  ANAHTAR KELİMELER (TASARIM.md'de kararlaştırdıklarımız)
# ---------------------------------------------------------------------
#  Solda: kodda yazılabilecek kelime
#  Sağda: lexer'ın onu hangi isimle etiketleyeceği
#
#  Uzun ve kısa hal AYNI etikete gider. Böylece "function" da "fn" de
#  [fn] olur ve sonraki istasyonlar aradaki farkı hiç bilmek zorunda kalmaz.
ANAHTAR_KELIMELER = {
    "fn":       "fn",       # fonksiyon tanımla
    "function": "fn",       #   (uzun hali)
    "var":      "var",      # yeni değişken oluştur
    "variable": "var",      #   (uzun hali)
    "return":   "return",   # fonksiyondan değer döndür
    "is":       "is",       # eşit mi?        (x is 5)
    "not":      "not",      # değil           (x is not 5)
    "true":     "true",     # doğru
    "false":    "false",    # yanlış
    "use":      "use",      # dışarıdaki değişkeni fonksiyona çağır
    "global":   "global",   # her fonksiyondan okunabilen değişken
    "if":       "if",       # eğer
    "else":     "else",     # değilse
    "repeat":   "repeat",   # tekrarla (bütün döngüler)
    "while":    "while",    # ... olduğu sürece  (repeat while ...)
    "stop":     "stop",     # döngüden çık
    "skip":     "skip",     # bu turu atla
    "when":     "when",     # şart doğru olduğu an çalış (senin fikrin)
    "type":     "type",     # kendi tipini tanımla
    "enum":     "enum",     # birden çok çeşidi olan tip (Nakit / Kart / Havale)
    "match":    "match",    # bir enum değerinin hangi çeşit olduğuna göre dallan
    "none":     "none",     # yok (Ogrenci? tipinde bir değişkenin değeri olmayabilir)
    "extern":   "extern",   # başka bir dilde (C) yazılmış hazır fonksiyonları tanıt
    "import":   "import",   # başka bir .vash dosyasını kullan
    "measure":  "measure",  # bir bloğun süresini ölç
    "and":      "and",      # ve
    "or":       "or",       # veya
}

# NOT: "change", "from", "to", "step" burada YOK. Bunlar BAĞLAMSAL kelimeler:
#   "use change sayac"            → change sadece use'dan sonra özel
#   "repeat i from 1 to 9 step 2" → from/to/step sadece repeat içinde özel
# Başka her yerde normal isimdirler (ör: "var step = 5" yazılabilir).

# NOT: "int" / "integer" burada YOK!
# Tip isimleri anahtar kelime değil, normal İSİM olarak kalır.
# Hangi ismin bir tip olduğuna ileride tip kontrolü (3. istasyon) karar verecek.
# Böylece yeni tipler eklemek için lexer'ı değiştirmemiz gerekmeyecek.

# İki karakterli işaretler. Bunlara ÖNCE bakmalıyız:
# yoksa "==" işaretini yanlışlıkla iki ayrı "=" sanırız.
# ("==" ve "!=" bilerek YOK: eşitlik için "is" / "is not" kullanıyoruz)
IKI_KARAKTERLI = {"<=", ">=", "->", "//"}

# Tek karakterli işaretler
TEK_KARAKTERLI = set("+-*/%=<>(){}[]:,;.?")   # "." → liste.add(x), liste.length


# ---------------------------------------------------------------------
#  Hata: Kodda anlamadığımız bir şey olursa bunu fırlatırız
# ---------------------------------------------------------------------
class LexerHatasi(Exception):
    pass


# ---------------------------------------------------------------------
#  ANA FONKSİYON: kodu alır, token listesi döndürür
# ---------------------------------------------------------------------
# Metin içindeki özel yazımlar: "\n" → yeni satır, "\t" → sekme, "\"" → tırnak, "\\" → ters bölü.
# "\{" ve "\}" gerçek süslü parantez yazar (değer yerleştirme sayılmaz). Bunları ayırt edebilmek
# için şimdilik özel (görünmez) işaretlerle saklıyoruz; tip kontrolü sonra geri çevirir.
KACISLAR = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "{": "", "}": ""}


def metin_oku(satir, i, satir_no):
    """Açılış tırnağından sonrasını oku; (metin, kapanış tırnağından sonraki konum) döndür.
    { } içindeki kısım ham bırakılır, çünkü orası küçük bir program parçasıdır:
    "{liste.join(", ")}" yazınca içteki tırnaklar metni kapatmaz."""
    sonuc = []
    derinlik = 0                     # kaç tane açık { içindeyiz?
    while i < len(satir):
        h = satir[i]
        if derinlik == 0:
            if h == '"':
                return "".join(sonuc), i + 1
            if h == "\\":
                if i + 1 >= len(satir) or satir[i + 1] not in KACISLAR:
                    gorulen = satir[i:i + 2]
                    raise LexerHatasi(
                        f"Satır {satir_no}: Metinde '{gorulen}' diye bir özel yazım yok. Kullanılabilenler: "
                        f"\\n (yeni satır), \\t (sekme), \\\" (tırnak), \\\\ (ters bölü), \\{{ ve \\}} (süslü parantez)."
                    )
                sonuc.append(KACISLAR[satir[i + 1]])
                i += 2
                continue
            if h == "{":
                derinlik = 1
            sonuc.append(h)
            i += 1
        else:
            # { } içi: ham kopyala, içteki metinleri olduğu gibi atla
            if h == '"':
                j = i + 1
                while j < len(satir) and satir[j] != '"':
                    j += 2 if satir[j] == "\\" else 1
                sonuc.append(satir[i:j + 1])
                i = j + 1
                continue
            if h == "{":
                derinlik += 1
            elif h == "}":
                derinlik -= 1
            sonuc.append(h)
            i += 1
    raise LexerHatasi(f"Satır {satir_no}: Metin kapatılmamış, '\"' eksik.")


def kelimelere_ayir(kod):
    tokenlar = []
    satirlar = kod.split("\n")

    for satir_no, satir in enumerate(satirlar, start=1):
        i = 0
        while i < len(satir):
            harf = satir[i]
            sutun = i + 1

            # Boşluk veya tab → atla
            # (Süslü parantez kullandığımız için boşlukların anlamı yok!)
            if harf == " " or harf == "\t":
                i += 1

            # Yorum → satırın geri kalanını atla
            elif harf == "#":
                break

            # Rakam → bir SAYI oku (ör: 42) ya da ONDALIK sayı (ör: 3.14)
            elif harf.isdigit():
                bas = i
                while i < len(satir) and satir[i].isdigit():
                    i += 1
                # Arkasından "." ve bir rakam geliyorsa ondalık sayıdır
                if i + 1 < len(satir) and satir[i] == "." and satir[i + 1].isdigit():
                    i += 1
                    while i < len(satir) and satir[i].isdigit():
                        i += 1
                    tokenlar.append(Token("ONDALIK", float(satir[bas:i]), satir_no, sutun))
                else:
                    tokenlar.append(Token("SAYI", int(satir[bas:i]), satir_no, sutun))

            # Harf veya _ → bir İSİM ya da ANAHTAR KELİME oku
            elif harf.isalpha() or harf == "_":
                bas = i
                while i < len(satir) and (satir[i].isalnum() or satir[i] == "_"):
                    i += 1
                kelime = satir[bas:i]
                if kelime in ANAHTAR_KELIMELER:
                    etiket = ANAHTAR_KELIMELER[kelime]   # function → fn
                    tokenlar.append(Token(etiket, None, satir_no, sutun))
                else:
                    tokenlar.append(Token("İSİM", kelime, satir_no, sutun))

            # Tırnak → METİN oku (ör: "merhaba")
            elif harf == '"':
                i += 1  # açılış tırnağını geç
                deger, i = metin_oku(satir, i, satir_no)
                tokenlar.append(Token("METİN", deger, satir_no, sutun))

            # Diğer dillerden alışkanlıkla "==" veya "!=" yazılırsa
            # sadece "hata" demek yerine doğrusunu söyle.
            elif satir[i:i + 2] == "==":
                raise LexerHatasi(
                    f"Satır {satir_no}, sütun {sutun}: Bu dilde '==' yok.\n"
                    f"   Eşitlik için 'is' kullan:   x is 5"
                )
            elif satir[i:i + 2] == "!=":
                raise LexerHatasi(
                    f"Satır {satir_no}, sütun {sutun}: Bu dilde '!=' yok.\n"
                    f"   Eşit değil için 'is not' kullan:   x is not 5"
                )

            # İki karakterli işaret mi? (<=, -> ...)
            elif satir[i:i + 2] in IKI_KARAKTERLI:
                tokenlar.append(Token(satir[i:i + 2], None, satir_no, sutun))
                i += 2

            # Tek karakterli işaret mi? (+, {, , ...)
            elif harf in TEK_KARAKTERLI:
                tokenlar.append(Token(harf, None, satir_no, sutun))
                i += 1

            # Hiçbiri değilse → tanımadığımız bir karakter
            else:
                raise LexerHatasi(
                    f"Satır {satir_no}, sütun {sutun}: '{harf}' karakterini tanımıyorum."
                )

        # Satır bitti. Boş olmayan bir satırsa "satır sonu" işareti koy.
        # (Bir komutun nerede bittiğini parser bununla anlayacak.
        #  Bunu ileride ";" ile değiştirmeye karar verebiliriz.)
        if tokenlar and tokenlar[-1].tur != "YENİ_SATIR":
            tokenlar.append(Token("YENİ_SATIR", None, satir_no, len(satir) + 1))

    tokenlar.append(Token("SON", None, len(satirlar), 1))
    return tokenlar


# ---------------------------------------------------------------------
#  Bu dosya doğrudan çalıştırılırsa: verilen dosyayı token'lara ayırıp göster
#  Kullanım:  python derleyici\lexer.py ornekler\ilk.vash
# ---------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    dosya_adi = sys.argv[1]
    # "utf-8-sig": Windows'taki bazı editörler dosyanın en başına görünmez bir
    # işaret (BOM) koyar. "-sig" bu işareti varsa sessizce atlar.
    with open(dosya_adi, encoding="utf-8-sig") as f:
        kod = f.read()

    try:
        tokenlar = kelimelere_ayir(kod)
    except LexerHatasi as hata:
        print("HATA:", hata)
        sys.exit(1)

    # Her satırın token'larını kendi satırında göster
    simdiki_satir = None
    for t in tokenlar:
        if t.satir != simdiki_satir:
            simdiki_satir = t.satir
            print(f"\nsatır {t.satir:>2}: ", end="")
        print(t, end=" ")
    print()
