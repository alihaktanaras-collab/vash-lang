# =====================================================================
#  4. İSTASYON: LLVM IR ÜRETİCİ (Makine Diline Çevirici)
# =====================================================================
#
#  Görevi: Tipleri kontrol edilmiş ağacı LLVM IR'a çevirmek.
#  LLVM IR, makine koduna çok yakın ama işlemciden bağımsız bir "evrensel assembly".
#  Sonra LLVM (clang) bunu optimize edip gerçek makine koduna (.exe) çevirir.
#
#  Örnek:   var x = 2 + 3
#
#      %t1 = add i64 2, 3                ← topla, sonucu %t1 kutusuna koy
#      store i64 %t1, ptr @"g.x"         ← %t1'i x'in hafızadaki yerine yaz
#
#  LLVM IR'ın 3 temel fikri:
#
#  1. Her şeyin tipi açıkça yazılır:
#        i64    = 64 bitlik tam sayı      (bizim int)
#        double = 64 bitlik ondalık sayı  (bizim float)
#        i1     = 1 bitlik doğru/yanlış   (bizim bool)
#        ptr    = hafızada bir adres      (bizim text ve listeler)
#     Tip kontrolü (3. istasyon) bunları zaten bulduğu için burada tek yapmamız
#     gereken tabloya bakmak. Hızın sırrı bu: "bu sayı mı metin mi?" sorusu
#     program çalışırken hiç sorulmuyor.
#
#  2. Her işlemin sonucu YENİ bir kutuya (%t1, %t2, ...) konur. Bir kutuya
#     bir kere yazılır, bir daha değişmez. Değişebilen şeyler (değişkenler)
#     için hafızada yer ayrılır (alloca / global) ve load/store ile okunur/yazılır.
#
#  3. Kod "bloklara" bölünür. Her blok bir etiketle başlar ve bir atlamayla
#     (br, ret) biter. if ve döngüler bu atlamalarla yapılacak.
# =====================================================================

import struct

from parser import Dugum
from parser import (
    DegiskenTanimi, UseKomutu, Atama, FonksiyonTanimi, Donus, IfadeKomutu,
    Eger, TekrarSayi, TekrarSurece, TekrarSayac, Dur, Atla,
    Sayi, Ondalik, Mantiksal, Metin, Isim, IkiliIslem, TekliIslem, Cagri, Liste,
    Erisim, Ozellik, MetotCagrisi, ElemanAtama, WhenKomutu, TipTanimi, AlanAtama, Aralik, Olcum,
    Pencere, SozlukDegeri, EnumTanimi, MatchKomutu, Yok, YedekliDeger, ExternBlok,
)

# Programdaki kendi tiplerin adları (üretici başlarken doldurulur)
KULLANICI_TIPLERI = set()


def disaridan_erisilenler(program):
    """Ana programın hangi değişkenlerine fonksiyonlar erişiyor?
       = 'global var' olanlar + herhangi bir fonksiyonda 'use x' / 'use change x' ile çağrılanlar"""
    adlar = {k.ad for k in program.komutlar if isinstance(k, DegiskenTanimi) and k.global_mi}

    def tara(komutlar):
        for k in komutlar:
            if isinstance(k, UseKomutu) and not getattr(k, "izin", False):
                adlar.add(k.ad)
            for alt in ("govde", "degilse"):
                if getattr(k, alt, None):
                    tara(getattr(k, alt))

    for k in program.komutlar:
        if isinstance(k, FonksiyonTanimi):
            tara(k.govde)
        elif isinstance(k, TipTanimi):
            for m in k.metotlar:
                tara(m.govde)
        elif isinstance(k, WhenKomutu) and k.kuresel:
            adlar |= k.gereken_globaller        # küresel when gizli bir fonksiyon olacak
    return adlar


def temel(tip):
    """'Ogrenci?' → 'Ogrenci'  (yok olabilen değer, aynı adresin boş olabilen hâlidir)"""
    return tip[:-1] if tip and tip.endswith("?") and tip not in ("[?]", "{?}") else tip


def sayacli(tip):
    """Bu tipin değerleri hafızadan yer alıyor ve sayaçla mı yönetiliyor?"""
    tip = temel(tip)
    return tip == "text" or (tip or "").startswith(("[", "{")) or tip in KULLANICI_TIPLERI


def sozluk_mu(tip):
    return (tip or "").startswith("{")


def sozluk_parcalari(t):
    """"{text:[int]}" → ("text", "[int]")"""
    i = t.index(":")
    return t[1:i], t[i + 1:-1]


# Listede/nesnede her elemanın türü (calisma.c'deki T_INT, T_FLOAT ... ile aynı)
def eleman_turu(tip):
    tip = temel(tip)
    if tip in KULLANICI_TIPLERI:
        return 5                                  # T_NESNE
    if sozluk_mu(tip):
        return 6                                  # T_SOZLUK
    return {"int": 0, "float": 1, "bool": 2, "text": 3, "ptr": 0}.get(tip, 4)


# Bizim tiplerimiz → LLVM tipleri
def llvm_tipi(tip):
    if tip == "int":
        return "i64"
    if tip == "float":
        return "double"
    if tip == "bool":
        return "i1"
    if tip == "void":
        return "void"
    return "ptr"            # text ve listeler: hafızadaki bir adres


def sifir_degeri(tip):
    return {"i64": "0", "double": "0.0", "i1": "false", "ptr": "null"}[llvm_tipi(tip)]


def ondalik_yazisi(sayi):
    """LLVM ondalık sayıları kesin olsun diye 16'lık tabanda ister: 3.5 → 0x400C000000000000"""
    return "0x%016X" % struct.unpack(">Q", struct.pack(">d", sayi))[0]


# Çalışma zamanı kütüphanesindeki (calisma.c) fonksiyonlar
CALISMA_ZAMANI = """\
declare void @calisma_baslat()
declare void @yaz_int(i64)
declare void @yaz_float(double)
declare void @yaz_bool(i8)
declare void @yaz_text(ptr)
declare void @yaz_bosluk()
declare void @yaz_satir()
declare ptr @metin_int(i64)
declare ptr @metin_float(double)
declare ptr @metin_bool(i8)
declare ptr @metin_birlestir(ptr, ptr)
declare ptr @metin_birlestir_int(ptr, i64)
declare void @tut(ptr)
declare void @birak(ptr)
declare void @hata_sifira_bolme(i64) noreturn
declare void @hata_sifir_adim(i64) noreturn
declare void @hata_tasma(i64) noreturn
declare { i64, i1 } @llvm.sadd.with.overflow.i64(i64, i64)
declare { i64, i1 } @llvm.ssub.with.overflow.i64(i64, i64)
declare { i64, i1 } @llvm.smul.with.overflow.i64(i64, i64)
declare i32 @metin_esit(ptr, ptr)
declare void @hata_sinir(ptr, i64, i64) noreturn cold
declare ptr @liste_yeni(i64, i64)
declare void @liste_tut(ptr)
declare void @liste_birak(ptr)
declare i64 @liste_al(ptr, i64, i64)
declare void @liste_koy(ptr, i64, i64, i64)
declare void @liste_ekle(ptr, i64)
declare void @liste_doldur(ptr, i64, i64)
declare void @liste_sil(ptr, i64, i64)
declare i64 @liste_uzunluk(ptr)
declare ptr @liste_yazilabilir(ptr)
declare void @liste_yaz(ptr)
declare void @ui_baslat(ptr)
declare void @ui_metin(i64, ptr)
declare void @ui_deger(i64, ptr)
declare i64 @ui_bekle()
declare ptr @ui_olay_degeri()
declare void @ui_bitir()
declare ptr @metin_c_den(ptr)
declare i32 @metin_harf_turu(ptr, i32)
declare i64 @metin_kodu(ptr, i64)
declare ptr @harf_metni(i64, i64)
declare ptr @dosya_oku(ptr)
declare ptr @dosya_satirlar(ptr)
declare i32 @dosya_yaz(ptr, ptr, i32)
declare i32 @dosya_var_mi(ptr)
declare ptr @sozluk_yeni(i64, i64)
declare void @sozluk_tut(ptr)
declare void @sozluk_birak(ptr)
declare void @sozluk_koy(ptr, i64, i64)
declare i64 @sozluk_al(ptr, i64, i64)
declare i32 @sozluk_bul(ptr, i64, ptr)
declare i32 @sozluk_var_mi(ptr, i64)
declare void @sozluk_sil(ptr, i64, i64)
declare ptr @sozluk_anahtarlar(ptr)
declare ptr @sozluk_degerler(ptr)
declare ptr @sozluk_yazilabilir(ptr)
declare void @sozluk_yaz(ptr)
declare void @ui_liste_boy(i64, i64)
declare void @ui_metin_satir(i64, i64, ptr)
declare void @ui_satir_kirp(i64, i64)
declare i64 @ui_olay_satiri()
declare ptr @nesne_yeni(ptr)
declare void @nesne_tut(ptr)
declare void @nesne_birak(ptr)
declare ptr @nesne_yazilabilir(ptr)
declare void @nesne_alan_koy(ptr, i64, i64)
declare void @nesne_yaz(ptr)
declare ptr @oku_satir(ptr)
declare i64 @rastgele(i64, i64, i64)
declare double @zaman()
declare i64 @metin_int_cevir(ptr, i64)
declare double @metin_float_cevir(ptr, i64)
declare i64 @float_int_cevir(double, i64)
declare i64 @metin_uzunluk(ptr)
declare i32 @metin_iceriyor(ptr, ptr)
declare ptr @metin_bol(ptr, ptr, i64)
declare ptr @metin_kirp(ptr)
declare i64 @oku_int(ptr, i64)
declare double @oku_float(ptr, i64)
declare i32 @metin_int_dene(ptr, ptr)
declare i32 @metin_float_dene(ptr, ptr)
declare double @rastgele_float(double, double, i64)
declare i64 @liste_rastgele(ptr, i64)
declare ptr @metin_harf(ptr, i64, i64)
declare ptr @metin_parca_al(ptr, i64, i64, i64)
declare ptr @metin_buyuk(ptr, ptr, i64)
declare ptr @metin_kucuk(ptr, ptr, i64)
declare i32 @metin_basliyor(ptr, ptr)
declare i32 @metin_bitiyor(ptr, ptr)
declare ptr @metin_degistir(ptr, ptr, ptr, i64)
declare ptr @metin_bol_bosluk(ptr)
declare ptr @liste_birlestir(ptr, ptr)
"""


# Tam sayı taşması olunca ne olsun? (TASARIM.md madde 23)
#   "kontrol" : programı "sayı çok büyüdü" hatasıyla durdur (Swift gibi)  ← KARAR
#   "sar"     : sessizce başa sarar (eski davranış; sadece karşılaştırma için duruyor)
TASMA = "kontrol"


class LLVMUretici:

    def __init__(self, kontrolcu):
        self.kontrolcu = kontrolcu      # 3. istasyonun bulduğu bilgiler
        KULLANICI_TIPLERI.clear()
        KULLANICI_TIPLERI.update(kontrolcu.tipler)
        KULLANICI_TIPLERI.update(kontrolcu.enumlar)     # enum değerleri de nesnedir
        self.tip_icinde = None          # şu an üretilen metodun tipi (TipBilgisi)
        self.ust = []                   # dosyanın en üstüne gidecekler (global değişkenler, metinler)
        self.metinler = {}              # aynı metni iki kere yazmamak için
        self.sayac = 0                  # %t1, %t2 ... için sayaç
        # Şu an yazılan fonksiyonun bilgileri:
        self.govde = []                 # komut satırları
        self.allocalar = []             # yerel değişkenlerin hafıza ayırma satırları
        self.kapsam = {}                # değişken adı → (adres, tip)
        self.donus_tipi = "void"

    # ---------- Küçük yardımcılar ----------
    def yeni(self):
        """Yeni bir sonuç kutusu adı: %t1, %t2, ..."""
        self.sayac += 1
        return f"%t{self.sayac}"

    def etiket(self, ad):
        self.sayac += 1
        return f"{ad}{self.sayac}"

    def yaz(self, satir):
        self.govde.append("  " + satir)

    def blok_baslat(self, etiket):
        self.govde.append(f"{etiket}:")
        self.simdiki_blok = etiket        # phi komutu için: şu an hangi bloktayız?

    def atla(self, etiket):
        """Başka bir bloğa atla. Atlamadan sonra gelen kod artık bu bloğa ait
        olamaz, bu yüzden ona (hiç çalışmayacak) yeni bir blok açılır."""
        self.yaz(f"br label %{etiket}")
        self.blok_baslat(self.etiket("olu"))

    def metin_sabiti(self, metin):
        """Bir metni programın içine sabit olarak göm, adresini döndür.
        Hafızadan alınan metinler gibi bunun da önünde bir sayaç var, ama değeri
        -1: "sonsuz, hiç temizleme". Böylece tut/birak her metne aynı şekilde uygulanabilir."""
        if metin in self.metinler:
            return self.metinler[metin]
        baytlar = metin.encode("utf-8") + b"\0"     # metnin sonunu gösteren 0 baytı
        kacisli = "".join(
            chr(b) if 32 <= b < 127 and b not in (34, 92) else f"\\{b:02X}" for b in baytlar
        )
        ad = f"@.metin.{len(self.metinler)}"
        tip = f"{{ i64, i64, [{len(baytlar)} x i8] }}"
        # Başlık: { sayaç = -1 (sonsuz), uzunluk } ve ardından harfler
        self.ust.append(f'{ad} = private unnamed_addr constant {tip} '
                        f'{{ i64 -1, i64 {len(baytlar) - 1}, [{len(baytlar)} x i8] c"{kacisli}" }}, align 16')
        # Programın kullandığı adres: başlığın 16 bayt ilerisi (metnin ilk harfi)
        adres = f"getelementptr inbounds ({tip}, ptr {ad}, i32 0, i32 2)"
        self.metinler[metin] = adres
        return adres

    # =================================================================
    #  BELLEK: SAYAÇ (tut / birak)
    # =================================================================
    #  Kural: her metin/liste değeri ya YENİ (sahibi biziz, işimiz bitince bırakmalıyız)
    #  ya da ÖDÜNÇ (bir değişkenden okundu, sahibi o değişken).
    #
    #    var a = "Sayı {i}"   → yeni metin, sahipliği doğrudan a'ya geçer
    #    var b = a            → a'dan ödünç; b de saklayacağı için tut(a): sayaç 2
    #    a = "x"              → a'nın eski metni birak: sayaç 1 (b hâlâ kullanıyor)
    #    fonksiyon bitince    → yerel değişkenlerdeki bütün metinler/listeler birak
    #  Listeler de aynı kurala uyar; sadece tut/birak yerine liste_tut/liste_birak çağrılır.
    def sahipli_mi(self, e):
        """Bu ifade YENİ bir metin/liste mi üretiyor (sahibi biz miyiz)?"""
        if not sayacli(getattr(e, "tip", None)):
            return False
        if getattr(e, "enum_olusturma", None):
            return True                                     # Odeme.Nakit: her seferinde yeni bir değer
        if isinstance(e, YedekliDeger):
            return True                                     # x else: y → sonuç her zaman sahiplenilir
        if isinstance(e, (Cagri, Liste, MetotCagrisi, SozlukDegeri)):
            return True                                     # fonksiyon sonucu, [1, 2, 3], Tip(...): yeni
        if isinstance(e, Metin):
            return any(tur == "ifade" for tur, _ in e.parcalar)      # "Sayı {i}" yeni oluşur
        if isinstance(e, Erisim):
            if e.liste.tip == "text":
                return True                                 # metin[1] her zaman yeni bir metin üretir
            return self.sahipli_mi(e.liste)                 # yeni bir listeden alındıysa (aşağıya bak)
        if isinstance(e, Ozellik):
            return self.sahipli_mi(e.nesne)                 # yeni bir nesnenin alanıysa
        return False                                        # değişkenden okuma, sabit metin: ödünç

    def tut(self, v, tip="text"):
        tip = temel(tip)
        if tip == "text":
            self.yaz(f"call void @tut(ptr {v})")
        elif tip in KULLANICI_TIPLERI:
            self.yaz(f"call void @nesne_tut(ptr {v})")
        elif sozluk_mu(tip):
            self.yaz(f"call void @sozluk_tut(ptr {v})")
        else:
            self.yaz(f"call void @liste_tut(ptr {v})")

    def birak(self, v, tip="text"):
        tip = temel(tip)
        if tip == "text":
            self.yaz(f"call void @birak(ptr {v})")
        elif tip in KULLANICI_TIPLERI:
            self.yaz(f"call void @nesne_birak(ptr {v})")
        elif sozluk_mu(tip):
            self.yaz(f"call void @sozluk_birak(ptr {v})")
        else:
            self.yaz(f"call void @liste_birak(ptr {v})")

    def gecici_birak(self, e, v):
        """Kullanılıp atılan yeni bir metni/listeyi bırak (ör: print("a {x}") sonrası)."""
        if self.sahipli_mi(e):
            self.birak(v, e.tip)

    def metin_sakla(self, adres, yeni, sahipli, tip="text"):
        """Bir metin/liste değişkenine yeni değer koy: yeniyi tut, eskiyi bırak."""
        if not sahipli:
            self.tut(yeni, tip)
        eski = self.yeni()
        self.yaz(f"{eski} = load ptr, ptr {adres}")
        self.yaz(f"store ptr {yeni}, ptr {adres}")
        self.birak(eski, tip)                              # (sıra önemli: x = x durumunda doğru çalışır)

    def yerelleri_birak(self):
        """Fonksiyondan çıkarken yerel metin/liste değişkenlerini bırak."""
        for adres, tip in self.metin_yerelleri:
            v = self.yeni()
            self.yaz(f"{v} = load ptr, ptr {adres}")
            self.birak(v, tip)

    # ---------- Liste elemanları: her eleman 8 baytlık bir "kutu" (i64) ----------
    def kutuya(self, v, tip):
        """Bir değeri listeye konacak 8 baytlık kutuya çevir."""
        if tip == "int":
            return v
        t = self.yeni()
        if tip == "float":
            self.yaz(f"{t} = bitcast double {v} to i64")
        elif tip == "bool":
            self.yaz(f"{t} = zext i1 {v} to i64")
        else:
            self.yaz(f"{t} = ptrtoint ptr {v} to i64")
        return t

    def kutudan(self, k, tip):
        """Listeden çıkan 8 baytlık kutuyu asıl değere çevir."""
        if tip == "int":
            return k
        t = self.yeni()
        if tip == "float":
            self.yaz(f"{t} = bitcast i64 {k} to double")
        elif tip == "bool":
            self.yaz(f"{t} = trunc i64 {k} to i1")
        else:
            self.yaz(f"{t} = inttoptr i64 {k} to ptr")
        return t

    def listeye_hazirla(self, e, eleman_tipi):
        """Listeye konacak değeri üret ve sahiplen (liste onu saklayacak)."""
        v = self.donustur(self.ifade(e), e.tip, eleman_tipi)
        if sayacli(eleman_tipi) and not self.sahipli_mi(e):
            self.tut(v, eleman_tipi)
        return self.kutuya(v, eleman_tipi)

    def yazilabilir_liste(self, ad):
        """Değiştirmeden önce: liste paylaşılıyorsa kopyasını al (kopyala-yaz)."""
        adres, _ = self.adres_bul(ad)
        p, p2 = self.yeni(), self.yeni()
        self.yaz(f"{p} = load ptr, ptr {adres}")
        self.yaz(f"{p2} = call ptr @liste_yazilabilir(ptr {p})")
        self.yaz(f"store ptr {p2}, ptr {adres}")
        return p2

    def tam_sayi_islem(self, komut, sol, sag, satir):
        """Tam sayılarla +, -, * işlemi. TASMA = "kontrol" ise taşmayı yakalar.
        Bonus: kontrol yapılınca LLVM, devam eden yolda sayının taşmadığını
        KESİN bilir; bu bilgiyle başka kontrolleri silip kodu hızlandırabilir."""
        if TASMA != "kontrol":
            t = self.yeni()
            self.yaz(f"{t} = {komut} i64 {sol}, {sag}")
            return t
        ad = {"add": "sadd", "sub": "ssub", "mul": "smul"}[komut]
        cift, t, tasti = self.yeni(), self.yeni(), self.yeni()
        self.yaz(f"{cift} = call {{ i64, i1 }} @llvm.{ad}.with.overflow.i64(i64 {sol}, i64 {sag})")
        self.yaz(f"{t} = extractvalue {{ i64, i1 }} {cift}, 0")
        self.yaz(f"{tasti} = extractvalue {{ i64, i1 }} {cift}, 1")
        hata_b, devam_b = self.etiket("tasma"), self.etiket("tasmadi")
        self.yaz(f"br i1 {tasti}, label %{hata_b}, label %{devam_b}")
        self.blok_baslat(hata_b)
        self.yaz(f"call void @hata_tasma(i64 {satir})")
        self.yaz("unreachable")
        self.blok_baslat(devam_b)
        return t

    def donustur(self, deger, kaynak, hedef):
        """int → float gerekiyorsa çevir (5 → 5.0)."""
        if kaynak == "int" and hedef == "float":
            t = self.yeni()
            self.yaz(f"{t} = sitofp i64 {deger} to double")
            return t
        return deger

    # =================================================================
    #  PROGRAM
    # =================================================================
    def uret(self, program):
        fonksiyon_kodlari = []

        # Ana programdaki değişkenlerden SADECE fonksiyonların gerçekten eriştikleri
        # ('use x' ile çağrılanlar ve 'global var' olanlar) global hafızaya konur.
        # Geri kalanlar main'in yerel değişkeni olur; LLVM onları işlemcinin hızlı
        # kutularında (yazmaçlarda) tutabilir. Bunu kesin bilebilmemizin sebebi Vash'ın
        # 'use' kuralı: bir fonksiyon dışarıdaki bir değişkene 'use' yazmadan dokunamaz.
        # (C++'ta her fonksiyon her globale gizlice dokunabildiği için bu yapılamaz.)
        self.gercek_globaller = disaridan_erisilenler(program)
        self.metin_globalleri = []
        for k in program.komutlar:
            if isinstance(k, DegiskenTanimi) and k.ad in self.gercek_globaller:
                tip = k.tip_sonuc
                self.ust.append(f'@"g.{k.ad}" = internal global {llvm_tipi(tip)} {sifir_degeri(tip)}')
                if sayacli(tip):
                    self.metin_globalleri.append((f'@"g.{k.ad}"', tip))

        # Küresel when'ler: her biri için durum değişkenleri ve "kim kimi izliyor" tablosu.
        # Bu tablo DERLEME sırasında kullanılır; program çalışırken hiçbir liste tutulmaz.
        self.kuresel_whenler = {}        # when düğümü → numarası
        self.izleyiciler = {}            # değişkenin adresi → onu izleyen küresel when numaraları
        for k in program.komutlar:
            if isinstance(k, WhenKomutu) and k.kuresel:
                n = len(self.kuresel_whenler)
                self.kuresel_whenler[id(k)] = n
                for durum in ("aktif", "onceki", "calisiyor"):
                    self.ust.append(f'@"when.{n}.{durum}" = internal global i1 false')
                for ad in k.izlenenler:
                    self.izleyiciler.setdefault(f'@"g.{ad}"', []).append(n)

        # extern: C fonksiyonlarını LLVM'e tanıt, hangi kütüphanelerin bağlanacağını not et
        self.extern_tanimlari()

        # Kendi tipler: her tip için çalışma zamanının kullanacağı "tür bilgisi" tablosu
        for bilgi in self.kontrolcu.tipler.values():
            self.tur_bilgisi_uret(bilgi)
        # Enum'lar: her çeşit kendi tablosuna sahip; tablodaki "çeşit numarası" ile match dallanır
        for bilgi in self.kontrolcu.enumlar.values():
            for sira, (cesit, alanlar) in enumerate(bilgi.cesitler.items()):
                self.tur_tablosu(f"{bilgi.ad}.{cesit}", cesit, list(alanlar.items()), sira)

        # Fonksiyonlar, metotlar, küresel when'ler
        for k in program.komutlar:
            if isinstance(k, FonksiyonTanimi):
                fonksiyon_kodlari.append(self.fonksiyon(k, self.kontrolcu.fonksiyonlar[k.ad]))
            elif isinstance(k, TipTanimi):
                bilgi = self.kontrolcu.tipler[k.ad]
                for m in k.metotlar:
                    fonksiyon_kodlari.append(self.fonksiyon(m, bilgi.metotlar[m.ad], bilgi))
            elif isinstance(k, WhenKomutu) and k.kuresel:
                fonksiyon_kodlari.append(self.kuresel_when_fonksiyonu(k))

        # Ana program → main fonksiyonu (her programın başladığı yer)
        self.fonksiyon_baslat("int", ana_program=True)
        self.yaz("call void @calisma_baslat()")
        for k in program.komutlar:
            if not isinstance(k, (FonksiyonTanimi, TipTanimi, EnumTanimi, ExternBlok)):
                self.komut(k)
        # Program biterken her şeyi düzgünce geri ver (bellek raporu 0 göstersin)
        self.yerelleri_birak()
        for adres, tip in self.metin_globalleri:
            v = self.yeni()
            self.yaz(f"{v} = load ptr, ptr {adres}")
            self.birak(v, tip)
        self.yaz("ret i32 0")
        ana = self.fonksiyon_bitir('define i32 @main() {')

        parcalar = [
            "; ===== Bu dosya derleyicimiz tarafından üretildi =====",
            "",
            "; --- Çalışma zamanı kütüphanesi (calisma.c) ---",
            CALISMA_ZAMANI,
            "; --- Global değişkenler ve metin sabitleri ---",
            *self.ust,
            "",
            *fonksiyon_kodlari,
            "; --- Ana program ---",
            ana,
            "; --- LLVM'e bellek ipuçları (liste başlığı ile elemanlar çakışmaz) ---",
            *self.TBAA_TANIMLARI,
        ]
        return "\n".join(parcalar) + "\n"

    def fonksiyon_baslat(self, donus_tipi, ana_program=False):
        self.govde = []
        self.allocalar = []
        self.kapsam = {}
        self.donus_tipi = donus_tipi
        self.ana_program = ana_program    # ana programdaki değişkenler global olur
        self.simdiki_blok = "giris"
        self.metin_yerelleri = []         # metin tutan yerel değişkenler (çıkarken bırakılacak)
        self.blok_derinligi = 0           # kaç { } bloğunun içindeyiz?
        self.donguler = []                # iç içe döngüler: (skip'in gideceği yer, stop'un gideceği yer)
        self.yerel_whenler = []           # şu an geçerli olan (blok içi) when'ler

    def fonksiyon_bitir(self, baslik):
        # Yerel değişken yerleri en başa (entry bloğuna) konur; LLVM böylece
        # onları hafıza yerine doğrudan işlemci yazmaçlarına (register) taşıyabilir.
        satirlar = [baslik, "giris:"] + self.allocalar + self.govde + ["}", ""]
        return "\n".join(satirlar)

    def fonksiyon(self, k, f, tip=None):
        """Bir fonksiyon ya da bir metot (tip verilmişse) üret.
        Metotlar, nesneyi gizli bir ilk parametre (%"self") olarak alan normal fonksiyonlardır."""
        self.fonksiyon_baslat(f.donus)
        self.tip_icinde = tip

        parametreler = [f'{llvm_tipi(t)} %"p.{a}"' for a, t in f.parametreler]
        if tip:
            parametreler.insert(0, 'ptr %"self"')
            ad = f'@"m.{tip.ad}.{k.ad}"'
        else:
            ad = f'@"f.{k.ad}"'
        baslik = f'define internal {llvm_tipi(f.donus)} {ad}({", ".join(parametreler)}) {{'

        # Parametreleri değiştirilebilir yerel değişkenlere kopyala
        for a, t in f.parametreler:
            adres = self.yerel_ayir(a, t)
            self.yaz(f'store {llvm_tipi(t)} %"p.{a}", ptr {adres}')
            if sayacli(t):
                self.tut(f'%"p.{a}"', t)       # ödünç gelen metni/listeyi sahiplen (çıkarken bırakılacak)

        for komut in k.govde:
            self.komut(komut)

        # Fonksiyonun sonu
        if f.donus == "void":
            self.yerelleri_birak()
            self.yaz("ret void")
        else:
            self.yaz("unreachable")       # buraya hiç gelinmez (return zorunlu)
        self.tip_icinde = None
        return self.fonksiyon_bitir(baslik)

    def tur_bilgisi_uret(self, bilgi):
        """Bir tip için çalışma zamanının okuyacağı sabit tablo:
           { tipin adı, alan sayısı, alan adları, alan türleri }
        Nesne silinirken hangi alanların bırakılacağı ve print(nesne) bundan öğrenilir."""
        self.tur_tablosu(bilgi.ad, bilgi.ad, [(alan, tip) for alan, (tip, _) in bilgi.alanlar.items()], 0)

    def tur_tablosu(self, t, gorunen_ad, alanlar, cesit):
        """{ ad, alan sayısı, alan adları, alan türleri, çeşit numarası }  (calisma.c: TurBilgisi)"""
        def c_metni(s, ad):
            b = s.encode("utf-8") + b"\0"
            k = "".join(chr(x) if 32 <= x < 127 and x not in (34, 92) else f"\\{x:02X}" for x in b)
            self.ust.append(f'{ad} = private unnamed_addr constant [{len(b)} x i8] c"{k}"')
        c_metni(gorunen_ad, f'@"tur.{t}.ad"')
        adlar, turler = [], []
        for i, (alan, tip) in enumerate(alanlar):
            c_metni(alan, f'@"tur.{t}.alan{i}"')
            adlar.append(f'ptr @"tur.{t}.alan{i}"')
            turler.append(f"i64 {eleman_turu(tip)}")
        n = len(adlar)
        self.ust.append(f'@"tur.{t}.adlar" = private constant [{n} x ptr] [{", ".join(adlar)}]')
        self.ust.append(f'@"tur.{t}.turler" = private constant [{n} x i64] [{", ".join(turler)}]')
        self.ust.append(f'@"tur.{t}" = private constant {{ ptr, i64, ptr, ptr, i64 }} '
                        f'{{ ptr @"tur.{t}.ad", i64 {n}, ptr @"tur.{t}.adlar", ptr @"tur.{t}.turler", i64 {cesit} }}')

    def alan_adresi(self, nesne, sira):
        """Nesnenin sira. alanının hafızadaki adresi (sayaç ve tür bilgisinden sonra, 8'er bayt)."""
        a = self.yeni()
        self.yaz(f"{a} = getelementptr inbounds i8, ptr {nesne}, i64 {16 + 8 * sira}")
        return a

    def yerel_ayir(self, ad, tip):
        """Fonksiyon içinde bir değişken için hafızada yer ayır."""
        self.sayac += 1
        adres = f'%"v.{ad}.{self.sayac}"'
        self.allocalar.append(f"  {adres} = alloca {llvm_tipi(tip)}")
        if sayacli(tip):
            # Metin/liste değişkenleri "boş" (null) başlar; birak(null) hiçbir şey yapmaz.
            # Böylece fonksiyondan çıkarken hepsini güvenle bırakabiliriz.
            self.allocalar.append(f"  store ptr null, ptr {adres}")
            self.metin_yerelleri.append((adres, tip))
        self.kapsam[ad] = (adres, tip)
        return adres

    def adres_bul(self, ad):
        """Bir değişkenin hafızadaki adresini bul."""
        if ad in self.kapsam:
            return self.kapsam[ad]
        # Metodun içinde bir alan adı: adresi, nesnenin içindeki yeri.
        # Böylece alanlar normal değişkenler gibi okunup yazılabilir.
        if self.tip_icinde and ad in self.tip_icinde.alanlar:
            sira = self.tip_icinde.alan_sirasi(ad)
            return (self.alan_adresi('%"self"', sira), self.tip_icinde.alanlar[ad][0])
        # Fonksiyon içinden okunan 'global var' ya da ana programın değişkeni
        d = self.kontrolcu.ana_kapsam.degiskenler[ad]
        return (f'@"g.{ad}"', d.tip)

    # =================================================================
    #  KOMUTLAR
    # =================================================================
    def komut(self, k):
        if isinstance(k, DegiskenTanimi):
            tip = k.tip_sonuc
            if self.ana_program and self.blok_derinligi == 0 and k.ad in self.gercek_globaller:
                adres = f'@"g.{k.ad}"'                 # bir fonksiyon erişiyor → global
                self.kapsam[k.ad] = (adres, tip)
            else:
                adres = self.yerel_ayir(k.ad, tip)    # fonksiyon içi → yerel
            deger = self.donustur(self.ifade(k.deger), k.deger.tip, tip)
            if sayacli(tip):
                self.metin_sakla(adres, deger, self.sahipli_mi(k.deger), tip)
            else:
                self.yaz(f"store {llvm_tipi(tip)} {deger}, ptr {adres}")

        elif isinstance(k, Atama):
            adres, tip = self.adres_bul(k.ad)
            deger = self.donustur(self.ifade(k.deger), k.deger.tip, tip)
            if sayacli(tip):
                self.metin_sakla(adres, deger, self.sahipli_mi(k.deger), tip)
            else:
                self.yaz(f"store {llvm_tipi(tip)} {deger}, ptr {adres}")
            self.degisti(adres)

        elif isinstance(k, ElemanAtama):          # liste[i] = x
            self.eleman_ata(k)

        elif isinstance(k, WhenKomutu):
            self.when_komutu(k)

        elif isinstance(k, Pencere):
            self.pencere(k)

        elif isinstance(k, MatchKomutu):
            self.match_komutu(k)

        elif isinstance(k, AlanAtama):            # nesne.alan = x
            kutu = self.listeye_hazirla(k.deger, k.alan_tipi)
            adres, _ = self.adres_bul(k.nesne.ad)
            p, p2 = self.yeni(), self.yeni()
            self.yaz(f"{p} = load ptr, ptr {adres}")
            self.yaz(f"{p2} = call ptr @nesne_yazilabilir(ptr {p})")      # kopyala-yaz
            self.yaz(f"store ptr {p2}, ptr {adres}")
            self.yaz(f"call void @nesne_alan_koy(ptr {p2}, i64 {k.alan_sirasi}, i64 {kutu})")
            self.degisti(adres)

        elif isinstance(k, UseKomutu):
            if getattr(k, "izin", False):          # use files: sadece derleyici için bir söz, kod üretmez
                return
            # Dışarıdaki değişkenin adresini bu fonksiyonda kullanılabilir yap
            self.kapsam[k.ad] = (f'@"g.{k.ad}"', k.tip)

        elif isinstance(k, Donus):
            if k.deger is None:
                self.yerelleri_birak()
                self.yaz("ret void")
            else:
                deger = self.donustur(self.ifade(k.deger), k.deger.tip, self.donus_tipi)
                if sayacli(self.donus_tipi) and not self.sahipli_mi(k.deger):
                    self.tut(deger, self.donus_tipi)   # döndürülen değer her zaman YENİ sayılır: önce sahiplen
                self.yerelleri_birak()    # sonra yerel değişkenleri bırak
                self.yaz(f"ret {llvm_tipi(self.donus_tipi)} {deger}")
            # return'den sonra yazılan kod hiç çalışmaz ama LLVM her bloğun
            # bir etiketle başlamasını ister: "ölü" bir blok aç.
            self.blok_baslat(self.etiket("olu"))

        elif isinstance(k, IfadeKomutu):
            v = self.ifade(k.ifade)
            self.gecici_birak(k.ifade, v)     # sonucu kullanılmayan yeni metin

        elif isinstance(k, Eger):
            self.eger(k)
        elif isinstance(k, TekrarSayi):
            self.tekrar_sayi(k)
        elif isinstance(k, TekrarSurece):
            self.tekrar_surece(k)
        elif isinstance(k, TekrarSayac):
            self.tekrar_sayac(k)
        elif isinstance(k, Dur):
            self.atla(self.donguler[-1][1])      # döngünün çıkışına atla
        elif isinstance(k, Atla):
            self.atla(self.donguler[-1][0])      # döngünün bir sonraki turuna atla

    # =================================================================
    #  PENCERE (window)
    # =================================================================
    #
    #   window "Sayaç" { label "Sayı: {sayi}"   button "Artır" { sayi = sayi + 1 } }
    #
    #   şuna dönüşür (kabaca):
    #
    #       ui_baslat(<sayfa>)              ← sunucuyu aç, pencereyi göster
    #     yenile:
    #       ui_metin(0, "Sayı: " + sayi)    ← her yazıyı yeniden hesapla (çalışma zamanı
    #       ui_metin(1, "Artır")               sadece DEĞİŞENLERİ pencereye yollar)
    #       olay = ui_bekle()               ← kullanıcı bir şey yapana kadar bekle
    #       switch olay:
    #         1  → sayi = sayi + 1; br yenile
    #         -1 → pencere kapandı: devam et
    #
    #   Yani "kendiliğinden güncellenme"nin sırrı: her olaydan sonra bütün yazılar yeniden
    #   hesaplanır, ama pencereye sadece farklı olanlar gider. Kod yazana hiçbir iş düşmez.
    def pencere(self, k):
        import html, json, os

        def tanim(ogeler):
            sonuc = []
            for o in ogeler:
                d = {"t": o.tur, "no": o.no}
                if o.tur in ("row", "list"):
                    d["c"] = tanim(o.cocuklar)
                if o.tur == "list":
                    d["secim"] = o.hedef is not None
                if o.tur == "textbox":
                    d["tip"] = o.hedef_tipi
                sonuc.append(d)
            return sonuc

        duzlestir = self.arayuz_duzlestir

        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pencere.html"), encoding="utf-8") as f:
            sablon = f.read()
        tanim_json = json.dumps(tanim(k.ogeler), ensure_ascii=False).replace("</", "<\\/")
        sayfa = sablon.replace("__BASLIK__", html.escape(k.baslik.deger)).replace("__TANIM__", tanim_json)
        self.yaz(f"call void @ui_baslat(ptr {self.metin_sabiti(sayfa)})")

        ogeler = list(duzlestir(k.ogeler))
        yenile, cikis, diger = self.etiket("pencere_yenile"), self.etiket("pencere_bitti"), self.etiket("pencere_diger")
        self.yaz(f"br label %{yenile}")
        self.blok_baslat(yenile)

        # 1) Ekrandaki her yazıyı ve bağlı her değeri hesapla
        for o in ogeler:
            if o.tur == "list":
                self.liste_yenile(o)
                continue
            t, yeni = self.degeri_metne_cevir(o.metin)
            self.yaz(f"call void @ui_metin(i64 {o.no}, ptr {t})")
            if yeni:
                self.birak(t)
            if o.hedef:
                adres, tip = self.adres_bul(o.hedef)
                v = self.yeni()
                self.yaz(f"{v} = load {llvm_tipi(tip)}, ptr {adres}")
                t, yeni = self.deger_metni(v, tip)
                self.yaz(f"call void @ui_deger(i64 {o.no}, ptr {t})")
                if yeni:
                    self.birak(t)

        # 2) Bir olay bekle ve hangi parçadan geldiğine göre dallan
        olay = self.yeni()
        self.yaz(f"{olay} = call i64 @ui_bekle()")
        dallar = []
        for o in ogeler:
            if o.tur == "list":
                if o.hedef:                                   # satıra tıklandı: seçim
                    dallar.append((o, None, self.etiket("olay_secim")))
                for b in self.arayuz_duzlestir(o.cocuklar):   # satırdaki bir düğmeye basıldı
                    if b.tur == "button":
                        dallar.append((b, o, self.etiket("olay_satir_button")))
            elif o.tur != "label":
                dallar.append((o, None, self.etiket(f"olay_{o.tur}")))
        secenekler = " ".join(f"i64 {o.no}, label %{e}" for o, _, e in dallar)
        self.yaz(f"switch i64 {olay}, label %{diger} [ {secenekler} ]")

        for o, liste, e in dallar:
            self.blok_baslat(e)
            if liste is not None:
                self.satir_olayi(liste, o)
            elif o.tur == "button":
                self.blok(o.govde)
            else:
                self.bagli_deger_al(o)                        # textbox, checkbox, list seçimi
            self.yaz(f"br label %{yenile}")

        self.blok_baslat(diger)                         # -1: pencere kapandı
        kapandi = self.yeni()
        self.yaz(f"{kapandi} = icmp slt i64 {olay}, 0")
        self.yaz(f"br i1 {kapandi}, label %{cikis}, label %{yenile}")
        self.blok_baslat(cikis)
        self.yaz("call void @ui_bitir()")

    @staticmethod
    def arayuz_duzlestir(ogeler):
        """row'ları aç: içindeki parçaları sırayla ver (list'in şablonuna girmeden)."""
        for o in ogeler:
            if o.tur == "row":
                yield from LLVMUretici.arayuz_duzlestir(o.cocuklar)
            else:
                yield o

    # ---------- list: her satır için şablon ----------
    #
    #   list urun, i in urunler { label "{i}. {urun}" }   şuna dönüşür:
    #
    #       l = urunler  (tut: döngü sırasında silinmesin)
    #       ui_liste_boy(no, l.length)
    #       repeat r from 1 to l.length {
    #           urun = l[r]; i = r
    #           ui_metin_satir(etiket_no, r, "{i}. {urun}")
    #       }
    #       ui_satir_kirp(etiket_no, l.length)     ← silinen satırların yazılarını unut
    def liste_al_ve_tut(self, o):
        l = self.ifade(o.kaynak)
        if not self.sahipli_mi(o.kaynak):
            self.tut(l, o.kaynak.tip)              # bu iş bitene kadar liste bizde kalsın
        return l

    def satir_baglan(self, o, l, r):
        """r. satırın elemanını ve sıra numarasını şablonun değişkenlerine koy."""
        tip = o.eleman_tipi
        v = self.kutudan(self.liste_eleman_oku(l, r, o.satir, tip), tip)
        if sayacli(tip):
            self.tut(v, tip)                       # satırın bloğu listeyi değiştirse de eleman yaşasın
        self.sayac += 1
        adres = f'%"satir.{o.eleman}.{self.sayac}"'
        self.allocalar.append(f"  {adres} = alloca {llvm_tipi(tip)}")
        self.yaz(f"store {llvm_tipi(tip)} {v}, ptr {adres}")
        self.kapsam[o.eleman] = (adres, tip)
        if o.sira_adi:
            self.sayac += 1
            s_adres = f'%"satir.{o.sira_adi}.{self.sayac}"'
            self.allocalar.append(f"  {s_adres} = alloca i64")
            self.yaz(f"store i64 {r}, ptr {s_adres}")
            self.kapsam[o.sira_adi] = (s_adres, "int")
        return v

    def satir_birak(self, o, v):
        if sayacli(o.eleman_tipi):
            self.birak(v, o.eleman_tipi)

    def liste_yenile(self, o):
        sablon = list(self.arayuz_duzlestir(o.cocuklar))
        l = self.liste_al_ve_tut(o)
        n = self.liste_uzunlugu(l)
        self.yaz(f"call void @ui_liste_boy(i64 {o.no}, i64 {n})")
        if o.hedef:
            adres, _ = self.adres_bul(o.hedef)
            v = self.yeni()
            self.yaz(f"{v} = load i64, ptr {adres}")
            t, _ = self.deger_metni(v, "int")
            self.yaz(f"call void @ui_deger(i64 {o.no}, ptr {t})")
            self.birak(t)

        self.sayac += 1
        r_yer = f'%"satir_no.{self.sayac}"'
        self.allocalar.append(f"  {r_yer} = alloca i64")
        self.yaz(f"store i64 1, ptr {r_yer}")
        kontrol, govde, son = self.etiket("satir_kontrol"), self.etiket("satir"), self.etiket("satir_son")
        self.yaz(f"br label %{kontrol}")
        self.blok_baslat(kontrol)
        r, c = self.yeni(), self.yeni()
        self.yaz(f"{r} = load i64, ptr {r_yer}")
        self.yaz(f"{c} = icmp sle i64 {r}, {n}")
        self.yaz(f"br i1 {c}, label %{govde}, label %{son}")
        self.blok_baslat(govde)
        onceki = dict(self.kapsam)
        v = self.satir_baglan(o, l, r)
        for b in sablon:
            t, yeni = self.degeri_metne_cevir(b.metin)
            self.yaz(f"call void @ui_metin_satir(i64 {b.no}, i64 {r}, ptr {t})")
            if yeni:
                self.birak(t)
        self.satir_birak(o, v)
        self.kapsam = onceki
        r2 = self.yeni()
        self.yaz(f"{r2} = add nsw i64 {r}, 1")
        self.yaz(f"store i64 {r2}, ptr {r_yer}")
        self.yaz(f"br label %{kontrol}")
        self.blok_baslat(son)
        for b in sablon:
            self.yaz(f"call void @ui_satir_kirp(i64 {b.no}, i64 {n})")
        self.birak(l, o.kaynak.tip)

    def satir_olayi(self, o, b):
        """Bir satırdaki düğmeye basıldı: o satırın elemanıyla düğmenin bloğunu çalıştır.
        Satır bu arada silinmişse (eski bir tıklama) hiçbir şey yapma."""
        r = self.yeni()
        self.yaz(f"{r} = call i64 @ui_olay_satiri()")
        l = self.liste_al_ve_tut(o)
        n = self.liste_uzunlugu(l)
        s0, var_mi = self.yeni(), self.yeni()
        self.yaz(f"{s0} = sub i64 {r}, 1")
        self.yaz(f"{var_mi} = icmp ult i64 {s0}, {n}")
        calis, bitti = self.etiket("satir_calis"), self.etiket("satir_bitti")
        self.yaz(f"br i1 {var_mi}, label %{calis}, label %{bitti}")
        self.blok_baslat(calis)
        onceki = dict(self.kapsam)
        v = self.satir_baglan(o, l, r)
        self.blok(b.govde)
        self.satir_birak(o, v)
        self.kapsam = onceki
        self.yaz(f"br label %{bitti}")
        self.blok_baslat(bitti)
        self.birak(l, o.kaynak.tip)

    def deger_metni(self, v, tip):
        """Bir değeri metne çevir. Döndürür: (metin, yeni_mi)"""
        if tip == "text":
            return v, False
        t = self.yeni()
        if tip == "int":
            self.yaz(f"{t} = call ptr @metin_int(i64 {v})")
            return t, True
        if tip == "float":
            self.yaz(f"{t} = call ptr @metin_float(double {v})")
            return t, True
        b = self.yeni()
        self.yaz(f"{b} = zext i1 {v} to i8")
        self.yaz(f"{t} = call ptr @metin_bool(i8 {b})")
        return t, False

    def bagli_deger_al(self, o):
        """textbox/checkbox'tan gelen yazıyı bağlı değişkenin tipine çevirip içine koy.
        Sayı kutusuna sayı olmayan bir şey yazıldıysa (ör: "12a"), değişken değişmez."""
        adres, tip = self.adres_bul(o.hedef)
        s = self.yeni()
        self.yaz(f"{s} = call ptr @ui_olay_degeri()")
        if tip == "text":
            self.metin_sakla(adres, s, True)
            self.degisti(adres)
            return
        if tip == "bool":
            c, b = self.yeni(), self.yeni()
            self.yaz(f"{c} = call i32 @metin_esit(ptr {s}, ptr {self.metin_sabiti('true')})")
            self.birak(s)
            self.yaz(f"{b} = icmp ne i32 {c}, 0")
            self.yaz(f"store i1 {b}, ptr {adres}")
            self.degisti(adres)
            return
        lt = llvm_tipi(tip)
        self.sayac += 1
        yer = f'%"kutu.{self.sayac}"'
        self.allocalar.append(f"  {yer} = alloca {lt}")
        ok, okb = self.yeni(), self.yeni()
        fonk = "metin_int_dene" if tip == "int" else "metin_float_dene"
        self.yaz(f"{ok} = call i32 @{fonk}(ptr {s}, ptr {yer})")
        self.birak(s)
        self.yaz(f"{okb} = icmp ne i32 {ok}, 0")
        oldu, olmadi = self.etiket("kutu_sayi"), self.etiket("kutu_sayi_degil")
        self.yaz(f"br i1 {okb}, label %{oldu}, label %{olmadi}")
        self.blok_baslat(oldu)
        v = self.yeni()
        self.yaz(f"{v} = load {lt}, ptr {yer}")
        self.yaz(f"store {lt} {v}, ptr {adres}")
        self.degisti(adres)
        self.yaz(f"br label %{olmadi}")
        self.blok_baslat(olmadi)

    def blok(self, komutlar):
        """Bir { } bloğunun komutlarını üret. Blokta oluşturulan değişkenler
        blok bitince unutulur (blok kapsamı)."""
        onceki_kapsam = dict(self.kapsam)
        onceki_when_sayisi = len(self.yerel_whenler)
        self.blok_derinligi += 1
        for komut in komutlar:
            self.komut(komut)
        self.blok_derinligi -= 1
        self.kapsam = onceki_kapsam
        del self.yerel_whenler[onceki_when_sayisi:]   # blokta yazılan when'ler blokla birlikte biter

    # =================================================================
    #  KARAR VERME: if / else
    # =================================================================
    #
    #   if x > 0 { A } else { B }        şuna dönüşür:
    #
    #       %k = icmp sgt i64 %x, 0
    #       br i1 %k, label %dogru, label %yanlis    ← şarta göre iki yoldan birine atla
    #     dogru:
    #       ...A...
    #       br label %son
    #     yanlis:
    #       ...B...
    #       br label %son
    #     son:                                        ← iki yol burada birleşir
    #
    def eger(self, k):
        kosul = self.ifade(k.kosul)
        dogru, yanlis, son = self.etiket("dogru"), self.etiket("yanlis"), self.etiket("ifson")
        self.yaz(f"br i1 {kosul}, label %{dogru}, label %{yanlis if k.degilse else son}")

        self.blok_baslat(dogru)
        self.blok(k.govde)
        self.yaz(f"br label %{son}")

        if k.degilse:
            self.blok_baslat(yanlis)
            self.blok(k.degilse)        # "else if" ise burada yeni bir Eger var
            self.yaz(f"br label %{son}")

        self.blok_baslat(son)

    # =================================================================
    #  DÖNGÜLER
    # =================================================================
    #  Bütün döngüler aynı kalıptadır:
    #
    #     kontrol:   şart doğru mu?  evet → govde'ye, hayır → cikis'a atla
    #     govde:     ...komutlar...
    #     ilerle:    (sayacı artır)  → kontrol'e geri atla      ← skip buraya atlar
    #     cikis:                                               ← stop buraya atlar
    #
    # ---- Döngüden önce bir kez "kendine ait yap" (Vash derleyicisindeki _tek_sahip_baslat ile aynı) ----
    @staticmethod
    def _dugum_cocuklari(d):
        for v in vars(d).values():
            if isinstance(v, Dugum):
                yield v
            elif isinstance(v, (list, tuple)):
                for x in v:
                    if isinstance(x, Dugum):
                        yield x

    def _eleman_yazilan_adlar(self, d, adlar):
        if type(d).__name__ == "ElemanAtama" and not getattr(d, "sozluk", False) and type(d.liste).__name__ == "Isim":
            t = getattr(d.liste, "tip", "") or ""
            if t.startswith("[") and not sayacli(t[1:-1]) and d.liste.ad not in adlar:
                adlar.append(d.liste.ad)
        for c in self._dugum_cocuklari(d):
            self._eleman_yazilan_adlar(c, adlar)
        return adlar

    def _sadece_eleman(self, d, ad):
        tur = type(d).__name__
        if tur == "Isim":
            return d.ad != ad
        if tur in ("Atama", "DegiskenTanimi") and d.ad == ad:
            return False
        if tur == "ElemanAtama" and type(d.liste).__name__ == "Isim" and d.liste.ad == ad:
            return self._sadece_eleman(d.sira, ad) and self._sadece_eleman(d.deger, ad)
        if tur == "Erisim" and type(d.liste).__name__ == "Isim" and d.liste.ad == ad:
            return self._sadece_eleman(d.sira, ad)
        if tur == "Ozellik" and d.ad == "length" and type(d.nesne).__name__ == "Isim" and d.nesne.ad == ad:
            return True
        return all(self._sadece_eleman(c, ad) for c in self._dugum_cocuklari(d))

    def _izleniyor_mu(self, adres):
        return adres in self.izleyiciler or any(adres in w["adresler"] for w in self.yerel_whenler)

    def _tek_sahip_baslat(self, dugumler):
        adlar = []
        for d in dugumler:
            self._eleman_yazilan_adlar(d, adlar)
        eklenen = []
        for ad in sorted(adlar):
            if ad not in self.kapsam:
                continue
            adres = self.kapsam[ad][0]
            if not adres.startswith("%") or adres in self.tek_sahipli or self._izleniyor_mu(adres):
                continue
            if not all(self._sadece_eleman(d, ad) for d in dugumler):
                continue
            p, p2 = self.yeni(), self.yeni()
            self.yaz(f"{p} = load ptr, ptr {adres}")
            self.yaz(f"{p2} = call ptr @liste_yazilabilir(ptr {p})")
            self.yaz(f"store ptr {p2}, ptr {adres}")
            self.tek_sahipli.append(adres)
            eklenen.append(adres)
        return eklenen

    def dongu_iskeleti(self, kontrol_uret, ilerle_uret, govde, kosul=None):
        if not hasattr(self, "tek_sahipli"):
            self.tek_sahipli = []
        tek_sahipler = self._tek_sahip_baslat(list(govde) + ([kosul] if kosul is not None else []))
        kontrol, govde_e, ilerle, cikis = (self.etiket("kontrol"), self.etiket("govde"),
                                          self.etiket("ilerle"), self.etiket("cikis"))
        self.yaz(f"br label %{kontrol}")

        self.blok_baslat(kontrol)
        sart = kontrol_uret()
        self.yaz(f"br i1 {sart}, label %{govde_e}, label %{cikis}")

        self.blok_baslat(govde_e)
        self.donguler.append((ilerle, cikis))
        self.blok(govde)
        self.donguler.pop()
        self.yaz(f"br label %{ilerle}")

        self.blok_baslat(ilerle)
        ilerle_uret(cikis)            # ilerletme, gerekirse doğrudan çıkışa da atlayabilir
        self.yaz(f"br label %{kontrol}")

        self.blok_baslat(cikis)
        self.tek_sahipli = [a for a in self.tek_sahipli if a not in tek_sahipler]

    def _doldurma_kalibi(self, k):
        """repeat N { l.add(sabit) } → (liste adı, değer) ya da None (Vash derleyicisindeki ile aynı)"""
        if len(k.govde) != 1 or type(k.govde[0]).__name__ != "IfadeKomutu":
            return None
        e = k.govde[0].ifade
        if type(e).__name__ != "MetotCagrisi" or e.ad != "add":
            return None
        if type(e.nesne).__name__ != "Isim" or len(e.argumanlar) != 1:
            return None
        a = e.argumanlar[0]
        tip = getattr(e.nesne, "tip", "")
        if tip == "[bool]" and type(a).__name__ == "Mantiksal":
            deger = "1" if a.deger in (True, "true") else "0"
        elif tip == "[int]" and type(a).__name__ == "Sayi":
            deger = str(a.deger)
        else:
            return None
        if e.nesne.ad not in self.kapsam or self._izleniyor_mu(self.kapsam[e.nesne.ad][0]):
            return None
        return e.nesne.ad, deger

    def tekrar_sayi(self, k):
        """repeat 3 { }  →  gizli bir sayaç 0'dan başlar, 3 olunca durur."""
        kac = self.ifade(k.sayi)
        kalip = self._doldurma_kalibi(k)
        if kalip:
            liste = self.yazilabilir_liste(kalip[0])
            self.yaz(f"call void @liste_doldur(ptr {liste}, i64 {kac}, i64 {kalip[1]})")
            return
        sayac = self.yerel_ayir(f"gizli_sayac{self.sayac}", "int")
        self.yaz(f"store i64 0, ptr {sayac}")

        def kontrol():
            v, s = self.yeni(), self.yeni()
            self.yaz(f"{v} = load i64, ptr {sayac}")
            self.yaz(f"{s} = icmp slt i64 {v}, {kac}")
            return s

        def ilerle(cikis):
            v, y = self.yeni(), self.yeni()
            self.yaz(f"{v} = load i64, ptr {sayac}")
            # sayac < kac olduğu için sayac + 1 asla taşmaz → "nsw" (taşmaz) etiketi
            self.yaz(f"{y} = add nsw i64 {v}, 1")
            self.yaz(f"store i64 {y}, ptr {sayac}")

        self.dongu_iskeleti(kontrol, ilerle, k.govde)

    def tekrar_surece(self, k):
        """repeat while kosul { }  →  her turdan önce şartı yeniden hesapla."""
        self.dongu_iskeleti(lambda: self.ifade(k.kosul), lambda cikis: None, k.govde, k.kosul)

    def tekrar_sayac(self, k):
        """repeat i from A to B step C { }"""
        bas = self.ifade(k.bas)
        son_deger = self.ifade(k.son)          # 'to' bir kere hesaplanır
        son = self.yerel_ayir(f"gizli_son{self.sayac}", "int")
        self.yaz(f"store i64 {son_deger}, ptr {son}")

        # Adım: yazılmadıysa 1. Sabit bir sayıysa yönü ve büyüklüğü derlerken biliriz.
        adim_buyuklugu = None
        if k.adim is None:
            adim, yon, adim_buyuklugu = "1", "ileri", 1
        elif isinstance(k.adim, Sayi) or (isinstance(k.adim, TekliIslem) and isinstance(k.adim.ifade, Sayi)):
            adim = self.ifade(k.adim)
            deger = k.adim.deger if isinstance(k.adim, Sayi) else -k.adim.ifade.deger
            yon = "ileri" if deger > 0 else "geri"
            adim_buyuklugu = abs(deger)
        else:                                   # adım bir değişken: yönü çalışırken anlaşılır
            adim_deger = self.ifade(k.adim)
            adim_yer = self.yerel_ayir(f"gizli_adim{self.sayac}", "int")
            self.yaz(f"store i64 {adim_deger}, ptr {adim_yer}")
            c = self.yeni()
            self.yaz(f"{c} = icmp eq i64 {adim_deger}, 0")
            hata_b, devam_b = self.etiket("adimsifir"), self.etiket("adimtamam")
            self.yaz(f"br i1 {c}, label %{hata_b}, label %{devam_b}")
            self.blok_baslat(hata_b)
            self.yaz(f"call void @hata_sifir_adim(i64 {k.satir})")
            self.yaz("unreachable")
            self.blok_baslat(devam_b)
            adim, yon = adim_yer, "calisirken"

        onceki_kapsam = dict(self.kapsam)
        i = self.yerel_ayir(k.ad, "int")
        self.yaz(f"store i64 {bas}, ptr {i}")

        def kontrol():
            v, s, sn = self.yeni(), self.yeni(), self.yeni()
            self.yaz(f"{v} = load i64, ptr {i}")
            self.yaz(f"{sn} = load i64, ptr {son}")
            if yon == "ileri":
                self.yaz(f"{s} = icmp sle i64 {v}, {sn}")       # i <= son
            elif yon == "geri":
                self.yaz(f"{s} = icmp sge i64 {v}, {sn}")       # i >= son
            else:
                a, ileri, ust, alt = self.yeni(), self.yeni(), self.yeni(), self.yeni()
                self.yaz(f"{a} = load i64, ptr {adim}")
                self.yaz(f"{ileri} = icmp sgt i64 {a}, 0")
                self.yaz(f"{ust} = icmp sle i64 {v}, {sn}")
                self.yaz(f"{alt} = icmp sge i64 {v}, {sn}")
                self.yaz(f"{s} = select i1 {ileri}, i1 {ust}, i1 {alt}")
            return s

        def ilerle(cikis):
            v = self.yeni()
            self.yaz(f"{v} = load i64, ptr {i}")
            if yon == "calisirken":
                a = self.yeni()
                self.yaz(f"{a} = load i64, ptr {adim}")
                y = self.tam_sayi_islem("add", v, a, k.satir)
            else:
                # TAŞMASIZ İLERLEME: Önce "kalan mesafe bir adımdan kısa mı?" diye bak.
                #   ileri:  kalan = son - i      geri:  kalan = i - son
                # Kısaysa döngü biter. Değilse i + adım kesinlikle 'son'u geçmez, yani
                # TAŞAMAZ → "nsw" (taşmaz) etiketiyle LLVM'e söylenir. Bu sayede:
                #   - her turdaki taşma kontrolü kalkar
                #   - LLVM döngüyü açabilir (unroll) ve liste sınır kontrollerini silebilir
                #   - "repeat i from 1 to <en büyük int>" son turda hata vermez
                sn, kalan, bitti = self.yeni(), self.yeni(), self.yeni()
                self.yaz(f"{sn} = load i64, ptr {son}")
                if yon == "ileri":
                    self.yaz(f"{kalan} = sub i64 {sn}, {v}")
                else:
                    self.yaz(f"{kalan} = sub i64 {v}, {sn}")
                # (i son'u geçmediği için kalan >= 0; işaretsiz karşılaştırma taşmaya karşı da güvenli)
                self.yaz(f"{bitti} = icmp ult i64 {kalan}, {adim_buyuklugu}")
                devam = self.etiket("artir")
                self.yaz(f"br i1 {bitti}, label %{cikis}, label %{devam}")
                self.blok_baslat(devam)
                y = self.yeni()
                komut = "add" if yon == "ileri" else "sub"
                self.yaz(f"{y} = {komut} nsw i64 {v}, {adim_buyuklugu}")
            self.yaz(f"store i64 {y}, ptr {i}")

        self.dongu_iskeleti(kontrol, ilerle, k.govde)
        self.kapsam = onceki_kapsam

    # =================================================================
    #  İFADELER: her biri, sonucunun bulunduğu kutuyu (ya da sabit değeri) döndürür
    # =================================================================
    def ifade(self, e):
        if isinstance(e, Sayi):
            return str(e.deger)
        if isinstance(e, Ondalik):
            return ondalik_yazisi(e.deger)
        if isinstance(e, Mantiksal):
            return "true" if e.deger else "false"
        if isinstance(e, Metin):
            return self.metin(e)
        if isinstance(e, Isim):
            adres, tip = self.adres_bul(e.ad)
            t = self.yeni()
            self.yaz(f"{t} = load {llvm_tipi(tip)}, ptr {adres}")
            return t
        if isinstance(e, TekliIslem):
            x = self.ifade(e.ifade)
            t = self.yeni()
            if e.isaret == "not":
                self.yaz(f"{t} = xor i1 {x}, true")      # true ↔ false
            elif e.tip == "float":
                self.yaz(f"{t} = fneg double {x}")
            else:
                return self.tam_sayi_islem("sub", "0", x, e.satir)
            return t
        if isinstance(e, IkiliIslem):
            return self.ikili_islem(e)
        if isinstance(e, Cagri):
            return self.cagri(e)
        if isinstance(e, Liste):
            return self.liste(e)
        if isinstance(e, SozlukDegeri):
            return self.sozluk_degeri(e)
        if isinstance(e, Yok):
            return "null"                           # yok = boş adres
        if isinstance(e, YedekliDeger):
            return self.yedekli_deger(e)
        if isinstance(e, Erisim):
            return self.erisim(e)
        if isinstance(e, Olcum):                    # measure { ... }
            bas, bit, t = self.yeni(), self.yeni(), self.yeni()
            self.yaz(f"{bas} = call double @zaman()")
            self.blok(e.govde)
            self.yaz(f"{bit} = call double @zaman()")
            self.yaz(f"{t} = fsub double {bit}, {bas}")
            return t
        if getattr(e, "enum_olusturma", None):     # Odeme.Kart(no: "1234", taksit: 3)
            return self.enum_olustur(e)
        if isinstance(e, Ozellik):
            if e.nesne.tip in KULLANICI_TIPLERI:    # nesne.alan
                return self.alan_oku(e)
            if e.nesne.tip == "text":               # metin.length (harf sayısı)
                m, t = self.ifade(e.nesne), self.yeni()
                self.yaz(f"{t} = call i64 @metin_uzunluk(ptr {m})")
                self.gecici_birak(e.nesne, m)
                return t
            l = self.ifade(e.nesne)                 # liste.length
            t = self.liste_uzunlugu(l)
            self.gecici_birak(e.nesne, l)
            return t
        if isinstance(e, MetotCagrisi):
            return self.metot_cagrisi(e)
        raise RuntimeError(f"Bunu üretmeyi bilmiyorum: {type(e).__name__}")

    # =================================================================
    #  HAZIR FONKSİYONLAR: input, random, time, int, float, text
    # =================================================================
    def hazir_fonksiyon(self, e):
        t = self.yeni()
        if e.ad == "input":
            istem = "null"
            if e.argumanlar:
                istem = self.ifade(e.argumanlar[0])
            # Beklenen tipe göre: int/float ise geçerli bir değer gelene kadar tekrar sorar
            if e.input_tipi == "int":
                self.yaz(f"{t} = call i64 @oku_int(ptr {istem}, i64 {e.satir})")
            elif e.input_tipi == "float":
                self.yaz(f"{t} = call double @oku_float(ptr {istem}, i64 {e.satir})")
            else:
                self.yaz(f"{t} = call ptr @oku_satir(ptr {istem})")      # yeni metin (sahibi biziz)
            if e.argumanlar:
                self.gecici_birak(e.argumanlar[0], istem)
            return t
        if e.ad == "random":
            a = e.argumanlar[0]
            if isinstance(a, Aralik):                   # random(1 to 6) / random(0.0 to 1.0)
                alt, ust = self.ifade(a.bas), self.ifade(a.son)
                if a.tip == "float":
                    alt = self.donustur(alt, a.bas.tip, "float")
                    ust = self.donustur(ust, a.son.tip, "float")
                    self.yaz(f"{t} = call double @rastgele_float(double {alt}, double {ust}, i64 {e.satir})")
                else:
                    self.yaz(f"{t} = call i64 @rastgele(i64 {alt}, i64 {ust}, i64 {e.satir})")
                return t
            l = self.ifade(a)                           # random(liste)
            self.yaz(f"{t} = call i64 @liste_rastgele(ptr {l}, i64 {e.satir})")
            v = self.kutudan(t, e.tip)
            if sayacli(e.tip):
                self.tut(v, e.tip)                      # çağrı sonucu her zaman "yeni" sayılır
            self.gecici_birak(a, l)
            return v
        if e.ad == "time":
            self.yaz(f"{t} = call double @zaman()")
            return t

        if e.ad in ("code", "char"):
            x = self.ifade(e.argumanlar[0])
            if e.ad == "code":
                self.yaz(f"{t} = call i64 @metin_kodu(ptr {x}, i64 {e.satir})")
            else:
                self.yaz(f"{t} = call ptr @harf_metni(i64 {x}, i64 {e.satir})")
            self.gecici_birak(e.argumanlar[0], x)
            return t

        if e.ad in ("read_file", "read_lines", "write_file", "append_file", "file_exists"):
            args = [self.ifade(a) for a in e.argumanlar]
            if e.ad == "read_file":                      # okunamazsa boş adres (none)
                self.yaz(f"{t} = call ptr @dosya_oku(ptr {args[0]})")
            elif e.ad == "read_lines":
                self.yaz(f"{t} = call ptr @dosya_satirlar(ptr {args[0]})")
            else:
                c = self.yeni()
                if e.ad == "file_exists":
                    self.yaz(f"{c} = call i32 @dosya_var_mi(ptr {args[0]})")
                else:
                    ekle = 1 if e.ad == "append_file" else 0
                    self.yaz(f"{c} = call i32 @dosya_yaz(ptr {args[0]}, ptr {args[1]}, i32 {ekle})")
                self.yaz(f"{t} = icmp ne i32 {c}, 0")
            for a, v in zip(e.argumanlar, args):
                self.gecici_birak(a, v)
            return t

        # Çevirme: int(x) / float(x) / text(x)
        x_dugum = e.argumanlar[0]
        kaynak = x_dugum.tip
        x = self.ifade(x_dugum)
        hedef = e.ad
        if kaynak == hedef:
            if hedef == "text" and not self.sahipli_mi(x_dugum):
                self.tut(x)                             # text(metin): sonuç her zaman "yeni" sayılır
            return x
        if e.yedek is not None:                         # int("abc", else: 0)
            return self.yedekli_cevirme(e, x_dugum, x)
        if hedef == "int":
            if kaynak == "text":
                self.yaz(f"{t} = call i64 @metin_int_cevir(ptr {x}, i64 {e.satir})")
                self.gecici_birak(x_dugum, x)
            elif kaynak == "float":
                self.yaz(f"{t} = call i64 @float_int_cevir(double {x}, i64 {e.satir})")
            else:                                       # bool → 0 / 1
                self.yaz(f"{t} = zext i1 {x} to i64")
            return t
        if hedef == "float":
            if kaynak == "text":
                self.yaz(f"{t} = call double @metin_float_cevir(ptr {x}, i64 {e.satir})")
                self.gecici_birak(x_dugum, x)
            else:
                self.yaz(f"{t} = sitofp i64 {x} to double")
            return t
        # hedef == "text"
        if kaynak == "int":
            self.yaz(f"{t} = call ptr @metin_int(i64 {x})")
        elif kaynak == "float":
            self.yaz(f"{t} = call ptr @metin_float(double {x})")
        else:
            b = self.yeni()
            self.yaz(f"{b} = zext i1 {x} to i8")
            self.yaz(f"{t} = call ptr @metin_bool(i8 {b})")
        return t

    def yedekli_cevirme(self, e, x_dugum, x):
        """int(metin, else: y): çevirmeyi DENE; olmazsa yedek değeri kullan.
           Yedek sadece gerektiğinde hesaplanır (phi ile iki yol birleşir)."""
        lt = llvm_tipi(e.ad)
        self.sayac += 1
        yer = f'%"cevir.{self.sayac}"'
        self.allocalar.append(f"  {yer} = alloca {lt}")
        ok, okb = self.yeni(), self.yeni()
        fonk = "metin_int_dene" if e.ad == "int" else "metin_float_dene"
        self.yaz(f"{ok} = call i32 @{fonk}(ptr {x}, ptr {yer})")
        self.gecici_birak(x_dugum, x)
        self.yaz(f"{okb} = icmp ne i32 {ok}, 0")
        basarili, yedek_b, son = self.etiket("cevrildi"), self.etiket("yedek"), self.etiket("cevirme_son")
        self.yaz(f"br i1 {okb}, label %{basarili}, label %{yedek_b}")
        self.blok_baslat(basarili)
        v = self.yeni()
        self.yaz(f"{v} = load {lt}, ptr {yer}")
        self.yaz(f"br label %{son}")
        self.blok_baslat(yedek_b)
        y = self.donustur(self.ifade(e.yedek), e.yedek.tip, e.ad)
        yedek_son = self.simdiki_blok
        self.yaz(f"br label %{son}")
        self.blok_baslat(son)
        t = self.yeni()
        self.yaz(f"{t} = phi {lt} [ {v}, %{basarili} ], [ {y}, %{yedek_son} ]")
        return t

    def metin_metodu(self, e):
        """metin.contains / starts_with / ends_with / split / trim / replace / upper / lower"""
        m = self.ifade(e.nesne)
        args = [self.ifade(a) for a in e.argumanlar]
        t = self.yeni()
        if e.ad in ("contains", "starts_with", "ends_with"):     # → bool
            fonk = {"contains": "metin_iceriyor", "starts_with": "metin_basliyor",
                    "ends_with": "metin_bitiyor"}[e.ad]
            c = self.yeni()
            self.yaz(f"{c} = call i32 @{fonk}(ptr {m}, ptr {args[0]})")
            self.yaz(f"{t} = icmp ne i32 {c}, 0")
        elif e.ad == "split":
            if args:
                self.yaz(f"{t} = call ptr @metin_bol(ptr {m}, ptr {args[0]}, i64 {e.satir})")
            else:
                self.yaz(f"{t} = call ptr @metin_bol_bosluk(ptr {m})")
        elif e.ad == "trim":
            self.yaz(f"{t} = call ptr @metin_kirp(ptr {m})")
        elif e.ad in ("is_digit", "is_letter", "is_space"):
            c = self.yeni()
            tur = {"is_digit": 0, "is_letter": 1, "is_space": 2}[e.ad]
            self.yaz(f"{c} = call i32 @metin_harf_turu(ptr {m}, i32 {tur})")
            self.yaz(f"{t} = icmp ne i32 {c}, 0")
        elif e.ad == "replace":
            self.yaz(f"{t} = call ptr @metin_degistir(ptr {m}, ptr {args[0]}, ptr {args[1]}, i64 {e.satir})")
        else:                                                    # upper / lower ("tr" isteğe bağlı)
            fonk = "metin_buyuk" if e.ad == "upper" else "metin_kucuk"
            dil = args[0] if args else "null"
            self.yaz(f"{t} = call ptr @{fonk}(ptr {m}, ptr {dil}, i64 {e.satir})")
        for a_dugum, a in zip(e.argumanlar, args):
            self.gecici_birak(a_dugum, a)
        self.gecici_birak(e.nesne, m)
        return t

    # =================================================================
    #  KENDİ TİPLER: oluşturma, alan okuma, metot çağırma
    # =================================================================
    def olusturma(self, e):
        """Ogrenci(ad: "Ali")  → nesne_yeni + her alana değerini (ya da varsayılanını) koy."""
        bilgi = self.kontrolcu.tipler[e.ad]
        o = self.yeni()
        self.yaz(f'{o} = call ptr @nesne_yeni(ptr @"tur.{e.ad}")')
        for i, (alan, (tip, alan_dugumu)) in enumerate(bilgi.alanlar.items()):
            deger = e.alan_degerleri.get(alan, alan_dugumu.varsayilan)
            kutu = self.listeye_hazirla(deger, tip)            # sahipliği alana geçer
            yer = self.alan_adresi(o, i)
            self.yaz(f"store i64 {kutu}, ptr {yer}")
        return o

    # =================================================================
    #  ENUM ve MATCH
    # =================================================================
    #  Bir enum değeri, alanları olan bir nesnedir; tür tablosunda "çeşit numarası" durur.
    #
    #   match o { Nakit { A }  Kart(no, taksit) { B } }    şuna dönüşür:
    #
    #       cesit = o.tur_tablosu.cesit
    #       switch cesit [ 0 → nakit, 1 → kart ]
    #     kart:
    #       no = o.alan[0]; taksit = o.alan[1]
    #       ...B...
    def enum_olustur(self, e):
        enum_ad, cesit = e.enum_olusturma
        alanlar = self.kontrolcu.enumlar[enum_ad].cesitler[cesit]
        o = self.yeni()
        self.yaz(f'{o} = call ptr @nesne_yeni(ptr @"tur.{enum_ad}.{cesit}")')
        for i, (alan, tip) in enumerate(alanlar.items()):
            kutu = self.listeye_hazirla(e.alan_degerleri[alan], tip)
            self.yaz(f"store i64 {kutu}, ptr {self.alan_adresi(o, i)}")
        return o

    def gizli_slot_bosalt(self, slot, tip):
        """Saklanan değeri bırak, yeri boşalt (return'de bir daha bırakılmasın)."""
        eski = self.yeni()
        self.yaz(f"{eski} = load ptr, ptr {slot}")
        self.yaz(f"store ptr null, ptr {slot}")
        self.birak(eski, tip)

    def match_komutu(self, k):
        bilgi = k.enum
        tip = bilgi.ad
        v = self.ifade(k.deger)
        # Değer, durumlar çalışırken yaşasın diye gizli bir yerel değişkende tutulur
        # (bir durumun içinde return olsa bile fonksiyon çıkarken düzgünce bırakılır).
        self.sayac += 1
        slot = self.yerel_ayir(f"match.{self.sayac}", tip)
        self.metin_sakla(slot, v, self.sahipli_mi(k.deger), tip)
        tb, cesit = self.yeni(), self.yeni()
        yer = self.yeni()
        self.yaz(f"{yer} = getelementptr inbounds i8, ptr {v}, i64 8")
        self.yaz(f"{tb} = load ptr, ptr {yer}")
        yer2 = self.yeni()
        self.yaz(f"{yer2} = getelementptr inbounds i8, ptr {tb}, i64 32")
        self.yaz(f"{cesit} = load i64, ptr {yer2}")
        son = self.etiket("match_son")
        diger = self.etiket("match_else") if k.degilse is not None else son
        dallar = [(d, self.etiket(f"durum_{d.cesit}")) for d in k.durumlar]
        secenekler = " ".join(f"i64 {bilgi.sira(d.cesit)}, label %{e}" for d, e in dallar)
        self.yaz(f"switch i64 {cesit}, label %{diger} [ {secenekler} ]")
        for d, e in dallar:
            self.blok_baslat(e)
            onceki = dict(self.kapsam)
            baglananlar = []
            for i, (ad, atip) in enumerate(zip(d.adlar, d.alan_tipleri)):
                kutu = self.yeni()
                self.yaz(f"{kutu} = load i64, ptr {self.alan_adresi(v, i)}")
                deger = self.kutudan(kutu, atip)
                aslot = self.yerel_ayir(ad, atip)
                if sayacli(atip):
                    self.metin_sakla(aslot, deger, False, atip)
                    baglananlar.append((aslot, atip))
                else:
                    self.yaz(f"store {llvm_tipi(atip)} {deger}, ptr {aslot}")
            self.blok(d.govde)
            for aslot, atip in baglananlar:
                self.gizli_slot_bosalt(aslot, atip)
            self.kapsam = onceki
            self.yaz(f"br label %{son}")
        if k.degilse is not None:
            self.blok_baslat(diger)
            self.blok(k.degilse)
            self.yaz(f"br label %{son}")
        self.blok_baslat(son)
        self.gizli_slot_bosalt(slot, tip)

    def alan_oku(self, e):
        """nesne.alan"""
        o = self.ifade(e.nesne)
        yer, kutu = self.alan_adresi(o, e.alan_sirasi), self.yeni()
        self.yaz(f"{kutu} = load i64, ptr {yer}")
        v = self.kutudan(kutu, e.tip)
        # Nesne geçiciyse (ör: Ogrenci(...).ad): önce alanı sahiplen, sonra nesneyi bırak
        if self.sahipli_mi(e.nesne):
            if sayacli(e.tip):
                self.tut(v, e.tip)
            self.birak(o, e.nesne.tip)
        return v

    def metot_arguman_listesi(self, f, argumanlar):
        """Argümanları üret; (LLVM yazısı, geçici bırakılacaklar) döndür."""
        parcalar, gecici = [], []
        for (p_ad, p_tip), a in zip(f.parametreler, argumanlar):
            v = self.donustur(self.ifade(a), a.tip, p_tip)
            parcalar.append(f"{llvm_tipi(p_tip)} {v}")
            gecici.append((a, v))
        return parcalar, gecici

    def metot_cagir(self, m, nesne, argumanlar):
        parcalar, gecici = self.metot_arguman_listesi(m, argumanlar)
        arg = ", ".join([f"ptr {nesne}"] + parcalar)
        t = None
        if m.donus == "void":
            self.yaz(f'call void @"m.{m.tip_adi}.{m.ad}"({arg})')
        else:
            t = self.yeni()
            self.yaz(f'{t} = call {llvm_tipi(m.donus)} @"m.{m.tip_adi}.{m.ad}"({arg})')
        for a, v in gecici:
            self.gecici_birak(a, v)
        return t

    def nesne_metodu(self, e):
        """nesne.metot(...)"""
        m = e.metot
        if m.degistirir:
            # Nesneyi değiştirecek: önce değişkenin kendine ait bir kopyası olduğundan emin ol
            adres, _ = self.adres_bul(e.nesne.ad)
            p, p2 = self.yeni(), self.yeni()
            self.yaz(f"{p} = load ptr, ptr {adres}")
            self.yaz(f"{p2} = call ptr @nesne_yazilabilir(ptr {p})")
            self.yaz(f"store ptr {p2}, ptr {adres}")
            t = self.metot_cagir(m, p2, e.argumanlar)
            self.degisti(adres)
            return t
        o = self.ifade(e.nesne)
        t = self.metot_cagir(m, o, e.argumanlar)
        self.gecici_birak(e.nesne, o)
        return t

    def metin(self, e):
        # Hiç değişken içermiyorsa: sabit metin (ödünç, hiç temizlenmez)
        if all(tur == "metin" for tur, _ in e.parcalar):
            return self.metin_sabiti(e.deger)
        # "Merhaba {ad}!" → parçaları tek tek metne çevirip birleştir.
        # Aradaki geçici metinler kullanılır kullanılmaz bırakılır.
        sonuc, sonuc_yeni = None, False
        for tur, parca in e.parcalar:
            # Hızlı yol: "...{sayı}" → metni ve sayıyı tek seferde birleştir
            # (sayı için ayrıca geçici bir metin oluşturmaya gerek yok)
            if sonuc is not None and tur == "ifade" and parca.tip == "int":
                v, t = self.ifade(parca), self.yeni()
                self.yaz(f"{t} = call ptr @metin_birlestir_int(ptr {sonuc}, i64 {v})")
                if sonuc_yeni:
                    self.birak(sonuc)
                sonuc, sonuc_yeni = t, True
                continue
            if tur == "metin":
                p, p_yeni = self.metin_sabiti(parca), False
            else:
                p, p_yeni = self.degeri_metne_cevir(parca)
            if sonuc is None:
                sonuc, sonuc_yeni = p, p_yeni
                continue
            t = self.yeni()
            self.yaz(f"{t} = call ptr @metin_birlestir(ptr {sonuc}, ptr {p})")
            if p_yeni:
                self.birak(p)
            if sonuc_yeni:
                self.birak(sonuc)
            sonuc, sonuc_yeni = t, True
        if not sonuc_yeni:
            self.tut(sonuc)        # ör: "{ad}" tek başına: kural gereği yeni sayılsın
        return sonuc

    def degeri_metne_cevir(self, ifade_dugumu):
        """{ } içindeki bir ifadeyi metne çevir. Döndürür: (değer, yeni_mi)"""
        tip = ifade_dugumu.tip
        v = self.ifade(ifade_dugumu)
        if tip == "text":
            return v, self.sahipli_mi(ifade_dugumu)   # değişkenden ödünç ya da yeni bir metin
        t = self.yeni()
        if tip == "int":
            self.yaz(f"{t} = call ptr @metin_int(i64 {v})")
            return t, True
        if tip == "float":
            self.yaz(f"{t} = call ptr @metin_float(double {v})")
            return t, True
        b = self.yeni()                      # bool: "true"/"false" sabit metinleri
        self.yaz(f"{b} = zext i1 {v} to i8")
        self.yaz(f"{t} = call ptr @metin_bool(i8 {b})")
        return t, False

    def sifir_kontrolu(self, bolen, tip, satir):
        """Bölen 0 ise programı anlaşılır bir hatayla durdur."""
        c = self.yeni()
        if tip == "float":
            self.yaz(f"{c} = fcmp oeq double {bolen}, 0.0")
        else:
            self.yaz(f"{c} = icmp eq i64 {bolen}, 0")
        hata_blok, devam_blok = self.etiket("sifir"), self.etiket("devam")
        self.yaz(f"br i1 {c}, label %{hata_blok}, label %{devam_blok}")
        self.blok_baslat(hata_blok)
        self.yaz(f"call void @hata_sifira_bolme(i64 {satir})")
        self.yaz("unreachable")
        self.blok_baslat(devam_blok)

    def kisa_devre(self, e):
        """a and b  /  a or b — "kısa devre":
           and: a yanlışsa sonuç zaten yanlış, b'ye HİÇ bakma.
           or:  a doğruysa sonuç zaten doğru, b'ye HİÇ bakma.
        Bu sayede  'x is not 0 and 10 // x > 1'  güvenle yazılabilir."""
        sol = self.ifade(e.sol)
        sol_blok = self.simdiki_blok
        sag_e, son = self.etiket("sag"), self.etiket("mantikson")
        if e.isaret == "and":
            self.yaz(f"br i1 {sol}, label %{sag_e}, label %{son}")
        else:
            self.yaz(f"br i1 {sol}, label %{son}, label %{sag_e}")
        self.blok_baslat(sag_e)
        sag = self.ifade(e.sag)
        sag_blok = self.simdiki_blok
        self.yaz(f"br label %{son}")
        self.blok_baslat(son)
        t = self.yeni()
        kisa = "false" if e.isaret == "and" else "true"
        # phi: "hangi yoldan geldiysen o değeri al"
        self.yaz(f"{t} = phi i1 [ {kisa}, %{sol_blok} ], [ {sag}, %{sag_blok} ]")
        return t

    def ikili_islem(self, e):
        if e.isaret in ("and", "or"):
            return self.kisa_devre(e)
        if e.isaret in ("is", "is not") and e.sol.tip == "ptr" and e.sag.tip == "ptr":   # iki tutamaç aynı mı?
            a, b, t = self.ifade(e.sol), self.ifade(e.sag), self.yeni()
            self.yaz(f"{t} = icmp {'eq' if e.isaret == 'is' else 'ne'} ptr {a}, {b}")
            return t
        if e.isaret in ("is", "is not") and "none" in (e.sol.tip, e.sag.tip):   # x is none
            taraf = e.sag if e.sol.tip == "none" else e.sol
            v, t = self.ifade(taraf), self.yeni()
            self.yaz(f"{t} = icmp {'eq' if e.isaret == 'is' else 'ne'} ptr {v}, null")
            self.gecici_birak(taraf, v)
            return t
        sol_tip, sag_tip = e.sol.tip, e.sag.tip
        sol = self.ifade(e.sol)
        sag = self.ifade(e.sag)
        op = e.isaret
        t = self.yeni()

        # Sayılarla işlemde biri float ise ikisi de float'a çevrilir
        ondalik = "float" in (sol_tip, sag_tip) or op == "/"
        if op in ("+", "-", "*", "/", "<", ">", "<=", ">=") or (op in ("is", "is not") and sol_tip in ("int", "float")):
            if ondalik:
                sol = self.donustur(sol, sol_tip, "float")
                sag = self.donustur(sag, sag_tip, "float")

        if op in ("+", "-", "*"):
            komut = {"+": "add", "-": "sub", "*": "mul"}[op]
            if ondalik:
                self.yaz(f"{t} = f{komut} double {sol}, {sag}")
                return t
            return self.tam_sayi_islem(komut, sol, sag, e.satir)

        if op == "/":
            self.sifir_kontrolu(sag, "float", e.satir)
            t = self.yeni()
            self.yaz(f"{t} = fdiv double {sol}, {sag}")
            return t

        if op in ("//", "%"):
            # Matematikteki gibi aşağı yuvarlayan bölme:  -7 // 2 = -4,  -7 % 2 = 1
            # İşlemcinin bölmesi sıfıra doğru yuvarlar (-3), bu yüzden düzeltiyoruz.
            self.sifir_kontrolu(sag, "int", e.satir)
            if TASMA == "kontrol":
                # Bölmede tek taşma durumu: en küçük sayı // -1 (sonuç int'e sığmaz)
                bir, iki, ikisi = self.yeni(), self.yeni(), self.yeni()
                self.yaz(f"{bir} = icmp eq i64 {sag}, -1")
                self.yaz(f"{iki} = icmp eq i64 {sol}, -9223372036854775808")
                self.yaz(f"{ikisi} = and i1 {bir}, {iki}")
                hata_b, devam_b = self.etiket("tasma"), self.etiket("tasmadi")
                self.yaz(f"br i1 {ikisi}, label %{hata_b}, label %{devam_b}")
                self.blok_baslat(hata_b)
                self.yaz(f"call void @hata_tasma(i64 {e.satir})")
                self.yaz("unreachable")
                self.blok_baslat(devam_b)
            b, k = self.yeni(), self.yeni()
            self.yaz(f"{b} = sdiv i64 {sol}, {sag}")
            self.yaz(f"{k} = srem i64 {sol}, {sag}")
            kalan_var, isaret_x, isaret_farkli, duzelt = self.yeni(), self.yeni(), self.yeni(), self.yeni()
            self.yaz(f"{kalan_var} = icmp ne i64 {k}, 0")
            self.yaz(f"{isaret_x} = xor i64 {k}, {sag}")
            self.yaz(f"{isaret_farkli} = icmp slt i64 {isaret_x}, 0")
            self.yaz(f"{duzelt} = and i1 {kalan_var}, {isaret_farkli}")
            t = self.yeni()
            if op == "//":
                d64 = self.yeni()
                self.yaz(f"{d64} = zext i1 {duzelt} to i64")
                self.yaz(f"{t} = sub i64 {b}, {d64}")
            else:
                kb = self.yeni()
                self.yaz(f"{kb} = add i64 {k}, {sag}")
                self.yaz(f"{t} = select i1 {duzelt}, i64 {kb}, i64 {k}")
            return t

        if op in ("<", ">", "<=", ">=", "is", "is not"):
            if sol_tip == "text":                     # metinleri karşılaştır
                c = self.yeni()
                self.yaz(f"{c} = call i32 @metin_esit(ptr {sol}, ptr {sag})")
                sart = "ne" if op == "is" else "eq"       # metin_esit: 1 = eşit, 0 = değil
                self.yaz(f"{t} = icmp {sart} i32 {c}, 0")
                self.gecici_birak(e.sol, sol)
                self.gecici_birak(e.sag, sag)
                return t
            if ondalik:
                sart = {"<": "olt", ">": "ogt", "<=": "ole", ">=": "oge", "is": "oeq", "is not": "une"}[op]
                self.yaz(f"{t} = fcmp {sart} double {sol}, {sag}")
            else:
                sart = {"<": "slt", ">": "sgt", "<=": "sle", ">=": "sge", "is": "eq", "is not": "ne"}[op]
                self.yaz(f"{t} = icmp {sart} {llvm_tipi(sol_tip)} {sol}, {sag}")
            return t

        raise RuntimeError(f"Bilinmeyen işlem: {op}")

    def cagri(self, e):
        if e.ad in ("print", "write"):
            for i, a in enumerate(e.argumanlar):
                if i > 0:
                    self.yaz("call void @yaz_bosluk()")
                self.yazdir(a)
            if e.ad == "print":
                self.yaz("call void @yaz_satir()")
            return None

        if e.ad in ("input", "random", "time", "int", "float", "text",
                    "read_file", "read_lines", "write_file", "append_file", "file_exists",
                    "code", "char"):
            return self.hazir_fonksiyon(e)
        if e.ad in KULLANICI_TIPLERI:                   # Ogrenci(ad: "Ali")
            return self.olusturma(e)
        if getattr(e, "metot", None):                   # metodun içinden aynı tipin metodu: kendi nesnesiyle
            return self.metot_cagir(e.metot, '%"self"', e.argumanlar)

        f = self.kontrolcu.fonksiyonlar[e.ad]
        if getattr(f, "extern", False):
            return self.c_cagrisi(e, f)
        argumanlar, gecici = [], []
        for (p_ad, p_tip), a in zip(f.parametreler, e.argumanlar):
            v = self.donustur(self.ifade(a), a.tip, p_tip)
            argumanlar.append(f"{llvm_tipi(p_tip)} {v}")
            gecici.append((a, v))
        arg_yazisi = ", ".join(argumanlar)
        t = None
        if f.donus == "void":
            self.yaz(f'call void @"f.{e.ad}"({arg_yazisi})')
        else:
            t = self.yeni()
            self.yaz(f'{t} = call {llvm_tipi(f.donus)} @"f.{e.ad}"({arg_yazisi})')
        for a, v in gecici:                 # fonksiyona verilen geçici yeni metinleri bırak
            self.gecici_birak(a, v)
        return t

    # =================================================================
    #  EXTERN: C fonksiyonlarını çağırmak
    # =================================================================
    def extern_tanimlari(self):
        import re
        from tipler import TipHatasi
        calisma_adlari = set(re.findall(r"@(\w+)\(", CALISMA_ZAMANI))
        tanitilanlar = {}                                  # aynı C fonksiyonu iki dosyada tanıtılabilir
        for f in self.kontrolcu.fonksiyonlar.values():
            if not getattr(f, "extern", False):
                continue
            if f.c_ad in calisma_adlari:
                raise TipHatasi(f"Satır {f.satir}: '{f.c_ad}' adı Vash'ın kendi içinde kullanılıyor; "
                                f"bu C fonksiyonu şimdilik tanıtılamaz.")
            imza = f"declare {f.c_donus} @{f.c_ad}({', '.join(f.c_parametreler)})"
            if f.c_ad in tanitilanlar:
                if tanitilanlar[f.c_ad] != imza:
                    raise TipHatasi(f"Satır {f.satir}: '{f.c_ad}' C fonksiyonu iki yerde farklı tiplerle tanıtılmış.")
                continue
            tanitilanlar[f.c_ad] = imza
            self.ust.append(imza)
        for k in self.kontrolcu.kutuphaneler:
            self.ust.append(f"; vash-kutuphane: {k}")      # derle.py bunu okuyup bağlar

    def c_cagrisi(self, e, f):
        """Vash değerlerini C'nin beklediği hâle çevir, çağır, sonucu Vash'a geri çevir."""
        argumanlar, gecici = [], []
        for (p_ad, p_tip), c_tip, a in zip(f.parametreler, f.c_parametreler, e.argumanlar):
            v = self.donustur(self.ifade(a), a.tip, p_tip)
            if c_tip == "i32":                       # Vash int (64 bit) → C int (32 bit)
                k = self.yeni()
                self.yaz(f"{k} = trunc i64 {v} to i32")
                v = k
            elif p_tip == "bool":                     # true/false → 1/0
                k = self.yeni()
                self.yaz(f"{k} = zext i1 {v} to i32")
                v = k
            argumanlar.append(f"{c_tip} {v}")
            gecici.append((a, v))
        cagri = f"call {f.c_donus} @{f.c_ad}({', '.join(argumanlar)})"
        if f.c_donus == "void":
            self.yaz(cagri)
            sonuc = None
        else:
            ham = self.yeni()
            self.yaz(f"{ham} = {cagri}")
            sonuc = ham
            if f.donus == "int" and f.c_donus == "i32":
                sonuc = self.yeni()
                self.yaz(f"{sonuc} = sext i32 {ham} to i64")
            elif f.donus == "bool":
                sonuc = self.yeni()
                self.yaz(f"{sonuc} = icmp ne i32 {ham}, 0")
            elif f.donus == "text":                   # C'nin metnini Vash metnine kopyala
                sonuc = self.yeni()
                self.yaz(f"{sonuc} = call ptr @metin_c_den(ptr {ham})")
        for a, v in gecici:
            self.gecici_birak(a, v)
        return sonuc

    def yazdir(self, a):
        # Değişkenli metni print içinde birleştirmeye gerek yok: parçaları sırayla yaz
        if isinstance(a, Metin) and any(tur == "ifade" for tur, _ in a.parcalar):
            for tur, parca in a.parcalar:
                if tur == "metin":
                    self.yaz(f"call void @yaz_text(ptr {self.metin_sabiti(parca)})")
                else:
                    v = self.ifade(parca)
                    self.deger_yaz(v, parca.tip)
                    self.gecici_birak(parca, v)
            return
        v = self.ifade(a)
        self.deger_yaz(v, a.tip)
        self.gecici_birak(a, v)

    def yedekli_deger(self, e):
        """x else: y  →  x boş değilse x, boşsa y  (sonuç sahiplenilmiş olarak döner)"""
        tip = e.tip
        v = self.ifade(e.deger)
        bos = self.yeni()
        self.yaz(f"{bos} = icmp eq ptr {v}, null")
        var_b, yok_b, son = self.etiket("deger_var"), self.etiket("deger_yok"), self.etiket("yedek_son")
        self.yaz(f"br i1 {bos}, label %{yok_b}, label %{var_b}")
        self.blok_baslat(var_b)
        if not self.sahipli_mi(e.deger):
            self.tut(v, tip)
        var_son = self.simdiki_blok
        self.yaz(f"br label %{son}")
        self.blok_baslat(yok_b)
        y = self.donustur(self.ifade(e.yedek), e.yedek.tip, tip)
        if not self.sahipli_mi(e.yedek):
            self.tut(y, tip)
        yok_son = self.simdiki_blok
        self.yaz(f"br label %{son}")
        self.blok_baslat(son)
        t = self.yeni()
        self.yaz(f"{t} = phi ptr [ {v}, %{var_son} ], [ {y}, %{yok_son} ]")
        return t

    def deger_yaz(self, v, tip):
        if tip == "none":
            self.yaz(f"call void @yaz_text(ptr {self.metin_sabiti('none')})")
            return
        if tip.endswith("?") and tip not in ("[?]", "{?}"):          # yok olabilir: önce bak
            bos = self.yeni()
            self.yaz(f"{bos} = icmp eq ptr {v}, null")
            yok_b, var_b, son = self.etiket("yaz_none"), self.etiket("yaz_deger"), self.etiket("yaz_son")
            self.yaz(f"br i1 {bos}, label %{yok_b}, label %{var_b}")
            self.blok_baslat(yok_b)
            self.yaz(f"call void @yaz_text(ptr {self.metin_sabiti('none')})")
            self.yaz(f"br label %{son}")
            self.blok_baslat(var_b)
            self.deger_yaz(v, tip[:-1])
            self.yaz(f"br label %{son}")
            self.blok_baslat(son)
            return
        if tip == "int":
            self.yaz(f"call void @yaz_int(i64 {v})")
        elif tip == "float":
            self.yaz(f"call void @yaz_float(double {v})")
        elif tip == "bool":
            b = self.yeni()
            self.yaz(f"{b} = zext i1 {v} to i8")
            self.yaz(f"call void @yaz_bool(i8 {b})")
        elif tip == "text":
            self.yaz(f"call void @yaz_text(ptr {v})")
        else:
            if tip in KULLANICI_TIPLERI:
                self.yaz(f"call void @nesne_yaz(ptr {v})")     # Ogrenci(ad: "Ali", ...)
            elif sozluk_mu(tip):
                self.yaz(f"call void @sozluk_yaz(ptr {v})")    # {"Ali": 90}
            else:
                self.yaz(f"call void @liste_yaz(ptr {v})")     # [1, 2, 3]

    # =================================================================
    #  LİSTELER
    # =================================================================
    def liste(self, e):
        """[a, b, c] → yeni bir liste oluştur, elemanları sırayla ekle."""
        eleman_tipi = e.tip[1:-1]
        l = self.yeni()
        self.yaz(f"{l} = call ptr @liste_yeni(i64 {eleman_turu(eleman_tipi)}, i64 {max(4, len(e.elemanlar))})")
        for x in e.elemanlar:
            kutu = self.listeye_hazirla(x, eleman_tipi)
            self.yaz(f"call void @liste_ekle(ptr {l}, i64 {kutu})")
        return l

    def erisim(self, e):
        """liste[i] → i. elemanı al (sınır kontrolü çalışma zamanında).
           metin[i] / metin[a to b] → harf / parça (Türkçe harfler bozulmadan)."""
        if e.liste.tip == "text":
            m, t = self.ifade(e.liste), self.yeni()
            if isinstance(e.sira, Aralik):
                a, b = self.ifade(e.sira.bas), self.ifade(e.sira.son)
                self.yaz(f"{t} = call ptr @metin_parca_al(ptr {m}, i64 {a}, i64 {b}, i64 {e.satir})")
            else:
                i = self.ifade(e.sira)
                self.yaz(f"{t} = call ptr @metin_harf(ptr {m}, i64 {i}, i64 {e.satir})")
            self.gecici_birak(e.liste, m)
            return t
        l = self.ifade(e.liste)
        sira = self.ifade(e.sira)
        if sozluk_mu(e.liste.tip):                 # sozluk["Ali"]: yoksa hata
            anahtar_tipi, _ = sozluk_parcalari(e.liste.tip)
            kutu = self.yeni()
            self.yaz(f"{kutu} = call i64 @sozluk_al(ptr {l}, i64 {self.kutuya(sira, anahtar_tipi)}, i64 {e.satir})")
            self.gecici_birak(e.sira, sira)
        else:
            kutu = self.liste_eleman_oku(l, sira, e.satir, e.tip)
        v = self.kutudan(kutu, e.tip)
        # Liste geçici (yeni) bir listeyse, ör: f()[1]: önce elemanı sahiplen, sonra listeyi bırak.
        # Böylece liste silinse bile eleman yaşamaya devam eder.
        if self.sahipli_mi(e.liste):
            if sayacli(e.tip):
                self.tut(v, e.tip)
            self.birak(l, e.liste.tip)
        return v

    # Liste yapısındaki alanların yeri (calisma.c'deki struct Liste ile aynı):
    #   0: sayaç   8: uzunluk   16: kapasite   24: tür   32: veri adresi
    #
    # !tbaa etiketleri (TBAA = "tipe dayalı takma ad analizi"): LLVM'e "liste başlığına yapılan
    # erişimler ile elemanlara yapılan erişimler ASLA aynı belleğe dokunmaz" diyoruz. Böylece
    # liste[i] = x yazıldıktan sonra LLVM uzunluğu ve veri adresini yeniden okumak zorunda kalmaz,
    # döngülerde bu okumaları döngünün dışına çıkarabilir.
    TBAA_BASLIK = "!tbaa !9002"
    TBAA_ELEMAN = "!tbaa !9004"
    TBAA_BAYT = "!tbaa !9007"            # [bool] elemanları (1 bayt): başlıkla karışmaz
    TBAA_TANIMLARI = [
        '!9000 = !{!"Vash TBAA"}',
        '!9001 = !{!"liste.baslik", !9000, i64 0}',
        '!9002 = !{!9001, !9001, i64 0}',
        '!9003 = !{!"liste.eleman", !9000, i64 0}',
        '!9004 = !{!9003, !9003, i64 0}',
        # Bir listenin uzunluğu 0 ile 2^60 arasındadır (her eleman 8 bayt; daha büyüğü belleğe sığmaz).
        # Bu bilgiyle LLVM, sınır kontrolünden geçen bir sıra numarasının küçük olduğunu anlar ve
        # o sayıyla yapılan hesaplardaki gereksiz taşma kontrollerini kendisi silebilir.
        '!9005 = !{i64 0, i64 1152921504606846976}',
        '!9006 = !{!"liste.bayt", !9000, i64 0}',
        '!9007 = !{!9006, !9006, i64 0}',
    ]

    def liste_alani(self, l, ofset, tip="i64"):
        """Liste başlığından bir alan oku (8: uzunluk, 32: veri adresi, 0: sayaç)."""
        yer, v = self.yeni(), self.yeni()
        self.yaz(f"{yer} = getelementptr inbounds i8, ptr {l}, i64 {ofset}")
        self.yaz(f"{v} = load {tip}, ptr {yer}, {self.TBAA_BASLIK}")
        return v

    def liste_uzunlugu(self, l):
        n = self.liste_alani(l, 8)
        self.govde[-1] += ", !range !9005"
        return n

    def sinir_kontrolu(self, l, sira, n, satir):
        """(sira - 1) < uzunluk mu? Değilse hata_sinir ile dur. Sıfırdan başlayan konumu döndür."""
        s0, uygun = self.yeni(), self.yeni()
        self.yaz(f"{s0} = sub i64 {sira}, 1")
        self.yaz(f"{uygun} = icmp ult i64 {s0}, {n}")
        tamam, disari = self.etiket("sinirda"), self.etiket("sinirdisi")
        self.yaz(f"br i1 {uygun}, label %{tamam}, label %{disari}")
        self.blok_baslat(disari)
        self.yaz(f"call void @hata_sinir(ptr {l}, i64 {sira}, i64 {satir})")
        self.yaz("unreachable")
        self.blok_baslat(tamam)
        return s0

    def eleman_ata(self, k):
        """liste[i] = x. Sayı/ondalık/bool listelerinde çağrı yapmadan, doğrudan IR:
             liste paylaşılmıyorsa (sayaç 1) olduğu yerde değiştir, paylaşılıyorsa önce kopyala;
             sonra sınır kontrolü ve tek bir 'store'.
           Metin/liste/nesne elemanlarında eski değeri bırakmak gerektiği için liste_koy çağrılır."""
        if getattr(k, "sozluk", False):            # sozluk["Ali"] = 90
            anahtar_tipi, deger_tipi = sozluk_parcalari(k.liste.tip)
            anahtar = self.listeye_hazirla(k.sira, anahtar_tipi)
            deger = self.listeye_hazirla(k.deger, deger_tipi)
            m = self.yazilabilir_sozluk(k.liste.ad)
            self.yaz(f"call void @sozluk_koy(ptr {m}, i64 {anahtar}, i64 {deger})")
            self.degisti(self.adres_bul(k.liste.ad)[0])
            return
        eleman_tipi = k.liste.tip[1:-1]
        kutu = self.listeye_hazirla(k.deger, eleman_tipi)
        sira = self.ifade(k.sira)
        adres, _ = self.adres_bul(k.liste.ad)
        if sayacli(eleman_tipi):
            liste = self.yazilabilir_liste(k.liste.ad)
            self.yaz(f"call void @liste_koy(ptr {liste}, i64 {sira}, i64 {kutu}, i64 {k.satir})")
        elif adres in getattr(self, "tek_sahipli", []):
            p = self.yeni()                       # döngüden önce kendine ait yapıldı: kontrol yok
            self.yaz(f"{p} = load ptr, ptr {adres}")
            n = self.liste_uzunlugu(p)
            veri = self.liste_alani(p, 32, "ptr")
            s0 = self.sinir_kontrolu(p, sira, n, k.satir)
            ey = self.yeni()
            if eleman_tipi == "bool":
                b8 = self.yeni()
                self.yaz(f"{ey} = getelementptr inbounds i8, ptr {veri}, i64 {s0}")
                self.yaz(f"{b8} = trunc i64 {kutu} to i8")
                self.yaz(f"store i8 {b8}, ptr {ey}, {self.TBAA_BAYT}")
            else:
                self.yaz(f"{ey} = getelementptr inbounds i64, ptr {veri}, i64 {s0}")
                self.yaz(f"store i64 {kutu}, ptr {ey}, {self.TBAA_ELEMAN}")
        else:
            p = self.yeni()
            self.yaz(f"{p} = load ptr, ptr {adres}")
            sayac, tek = self.liste_alani(p, 0), self.yeni()
            self.yaz(f"{tek} = icmp eq i64 {sayac}, 1")
            hizli, yavas, birles = self.etiket("tekSahip"), self.etiket("kopyala"), self.etiket("yazilabilir")
            self.yaz(f"br i1 {tek}, label %{hizli}, label %{yavas}")
            self.blok_baslat(yavas)
            p2 = self.yeni()
            self.yaz(f"{p2} = call ptr @liste_yazilabilir(ptr {p})")
            self.yaz(f"store ptr {p2}, ptr {adres}")
            self.yaz(f"br label %{birles}")
            self.blok_baslat(hizli)
            self.yaz(f"br label %{birles}")
            self.blok_baslat(birles)
            liste = self.yeni()
            self.yaz(f"{liste} = phi ptr [ {p}, %{hizli} ], [ {p2}, %{yavas} ]")
            n = self.liste_uzunlugu(liste)
            veri = self.liste_alani(liste, 32, "ptr")
            s0 = self.sinir_kontrolu(liste, sira, n, k.satir)
            ey = self.yeni()
            if eleman_tipi == "bool":            # [bool]: her eleman 1 bayt
                b8 = self.yeni()
                self.yaz(f"{ey} = getelementptr inbounds i8, ptr {veri}, i64 {s0}")
                self.yaz(f"{b8} = trunc i64 {kutu} to i8")
                self.yaz(f"store i8 {b8}, ptr {ey}, {self.TBAA_BAYT}")
            else:
                self.yaz(f"{ey} = getelementptr inbounds i64, ptr {veri}, i64 {s0}")
                self.yaz(f"store i64 {kutu}, ptr {ey}, {self.TBAA_ELEMAN}")
        self.degisti(adres)

    def liste_eleman_oku(self, l, sira, satir, tip=""):
        """liste[sira] → doğrudan IR olarak (fonksiyon çağrısı olmadan):
             sınırda mı?  (sira - 1) < uzunluk   (işaretsiz karşılaştırma: sira < 1'i de yakalar)
             evet → veri[sira - 1] oku      hayır → hata_sinir (hata mesajı, program durur)
        Çağrı olmadığı için LLVM döngülerde bu kontrolü çoğu zaman tamamen silebilir."""
        n = self.liste_uzunlugu(l)
        # Veri adresini kontrolden ÖNCE oku: koşulsuz bir okuma olduğu için LLVM onu
        # döngünün dışına taşıyabilir (koşulun arkasındaki okumaya dokunmaya cesaret edemez).
        veri = self.liste_alani(l, 32, "ptr")
        s0 = self.sinir_kontrolu(l, sira, n, satir)
        ey, kutu = self.yeni(), self.yeni()
        if tip == "bool":                          # [bool]: her eleman 1 bayt
            b8 = self.yeni()
            self.yaz(f"{ey} = getelementptr inbounds i8, ptr {veri}, i64 {s0}")
            self.yaz(f"{b8} = load i8, ptr {ey}, {self.TBAA_BAYT}")
            self.yaz(f"{kutu} = zext i8 {b8} to i64")
            return kutu
        self.yaz(f"{ey} = getelementptr inbounds i64, ptr {veri}, i64 {s0}")
        self.yaz(f"{kutu} = load i64, ptr {ey}, {self.TBAA_ELEMAN}")
        return kutu

    # =================================================================
    #  SÖZLÜKLER
    # =================================================================
    def sozluk_degeri(self, e):
        """{"Ali": 90, ...} → yeni bir sözlük oluştur, çiftleri sırayla koy."""
        anahtar_tipi, deger_tipi = sozluk_parcalari(e.tip)
        m = self.yeni()
        self.yaz(f"{m} = call ptr @sozluk_yeni(i64 {eleman_turu(anahtar_tipi)}, i64 {eleman_turu(deger_tipi)})")
        for a, d in zip(e.anahtarlar, e.degerler):
            ak = self.listeye_hazirla(a, anahtar_tipi)
            dk = self.listeye_hazirla(d, deger_tipi)
            self.yaz(f"call void @sozluk_koy(ptr {m}, i64 {ak}, i64 {dk})")
        return m

    def yazilabilir_sozluk(self, ad):
        """Değiştirmeden önce: sözlük paylaşılıyorsa kopyasını al (kopyala-yaz)."""
        adres, _ = self.adres_bul(ad)
        p, p2 = self.yeni(), self.yeni()
        self.yaz(f"{p} = load ptr, ptr {adres}")
        self.yaz(f"{p2} = call ptr @sozluk_yazilabilir(ptr {p})")
        self.yaz(f"store ptr {p2}, ptr {adres}")
        return p2

    def sozluk_metodu(self, e):
        """get(k, else: v) / has(k) / remove(k) / keys() / values()"""
        anahtar_tipi, deger_tipi = sozluk_parcalari(e.nesne.tip)
        if e.ad == "remove":
            k = self.ifade(e.argumanlar[0])
            m = self.yazilabilir_sozluk(e.nesne.ad)
            self.yaz(f"call void @sozluk_sil(ptr {m}, i64 {self.kutuya(k, anahtar_tipi)}, i64 {e.satir})")
            self.gecici_birak(e.argumanlar[0], k)
            self.degisti(self.adres_bul(e.nesne.ad)[0])
            return None
        m = self.ifade(e.nesne)
        t = self.yeni()
        if e.ad in ("keys", "values"):
            fonk = "sozluk_anahtarlar" if e.ad == "keys" else "sozluk_degerler"
            self.yaz(f"{t} = call ptr @{fonk}(ptr {m})")
        elif e.ad == "has":
            k = self.ifade(e.argumanlar[0])
            c = self.yeni()
            self.yaz(f"{c} = call i32 @sozluk_var_mi(ptr {m}, i64 {self.kutuya(k, anahtar_tipi)})")
            self.yaz(f"{t} = icmp ne i32 {c}, 0")
            self.gecici_birak(e.argumanlar[0], k)
        else:                                          # get(k, else: yedek)
            k = self.ifade(e.argumanlar[0])
            self.sayac += 1
            yer = f'%"sozluk_bul.{self.sayac}"'
            self.allocalar.append(f"  {yer} = alloca i64")
            c, cb = self.yeni(), self.yeni()
            self.yaz(f"{c} = call i32 @sozluk_bul(ptr {m}, i64 {self.kutuya(k, anahtar_tipi)}, ptr {yer})")
            self.gecici_birak(e.argumanlar[0], k)
            self.yaz(f"{cb} = icmp ne i32 {c}, 0")
            var_b, yok_b, son = self.etiket("anahtar_var"), self.etiket("anahtar_yok"), self.etiket("get_son")
            self.yaz(f"br i1 {cb}, label %{var_b}, label %{yok_b}")
            self.blok_baslat(var_b)
            kutu = self.yeni()
            self.yaz(f"{kutu} = load i64, ptr {yer}")
            v1 = self.kutudan(kutu, deger_tipi)
            if sayacli(deger_tipi):
                self.tut(v1, deger_tipi)              # sonuç her zaman "yeni" sayılır
            var_son = self.simdiki_blok
            self.yaz(f"br label %{son}")
            self.blok_baslat(yok_b)
            v2 = self.donustur(self.ifade(e.yedek), e.yedek.tip, deger_tipi)
            if sayacli(deger_tipi) and not self.sahipli_mi(e.yedek):
                self.tut(v2, deger_tipi)
            yok_son = self.simdiki_blok
            self.yaz(f"br label %{son}")
            self.blok_baslat(son)
            self.yaz(f"{t} = phi {llvm_tipi(deger_tipi)} [ {v1}, %{var_son} ], [ {v2}, %{yok_son} ]")
        self.gecici_birak(e.nesne, m)
        return t

    def metot_cagrisi(self, e):
        """liste.add(x)  /  liste.remove(i)  /  nesne.metot(...)  /  metin.split(...)"""
        if e.nesne.tip == "text":
            return self.metin_metodu(e)
        if e.ad == "join":                                   # liste.join(", ") → metin
            l, a, t = self.ifade(e.nesne), self.ifade(e.argumanlar[0]), self.yeni()
            self.yaz(f"{t} = call ptr @liste_birlestir(ptr {l}, ptr {a})")
            self.gecici_birak(e.argumanlar[0], a)
            self.gecici_birak(e.nesne, l)
            return t
        if getattr(e, "metot", None):
            return self.nesne_metodu(e)
        if sozluk_mu(e.nesne.tip):
            return self.sozluk_metodu(e)
        eleman_tipi = e.nesne.tip[1:-1]
        if e.ad == "add":
            kutu = self.listeye_hazirla(e.argumanlar[0], eleman_tipi)
            liste = self.yazilabilir_liste(e.nesne.ad)
            self.yaz(f"call void @liste_ekle(ptr {liste}, i64 {kutu})")
        else:
            sira = self.ifade(e.argumanlar[0])
            liste = self.yazilabilir_liste(e.nesne.ad)
            self.yaz(f"call void @liste_sil(ptr {liste}, i64 {sira}, i64 {e.satir})")
        self.degisti(self.adres_bul(e.nesne.ad)[0])
        return None

    # =================================================================
    #  WHEN
    # =================================================================
    #  when kosul { blok }  her when için gizli iki bilgi tutulur:
    #     onceki    : şart en son doğru muydu?
    #     calisiyor : blok şu an çalışıyor mu? (kendi kendini tetiklemesin)
    #  İzlenen bir değişken her değiştiğinde (derleyici bu yerleri biliyor):
    #     şart = kosul
    #     şart doğru VE önceden yanlış  →  bloğu çalıştır
    #     onceki = şart
    def degisti(self, adres):
        """Bir değişken değişti: onu izleyen when'leri kontrol et."""
        for n in self.izleyiciler.get(adres, []):
            self.yaz(f'call void @"when.{n}"()')
        for w in list(self.yerel_whenler):
            if adres in w["adresler"]:
                self.yerel_when_kontrol(w)

    def when_komutu(self, k):
        if id(k) in self.kuresel_whenler and self.ana_program and self.blok_derinligi == 0:
            n = self.kuresel_whenler[id(k)]
            if k.bekle:                          # when later: şu anki durumu "önceki" say
                c = self.ifade(k.kosul)
                self.yaz(f'store i1 {c}, ptr @"when.{n}.onceki"')
            self.yaz(f'store i1 true, ptr @"when.{n}.aktif"')
            if not k.bekle:                      # şart şimdiden doğruysa hemen çalışsın
                self.yaz(f'call void @"when.{n}"()')
            return
        # Blok içi when: izlediği değişkenlerin adresleri ve kendi "onceki" bilgisi
        self.sayac += 1
        onceki = self.yerel_ayir(f"when_onceki{self.sayac}", "bool")
        w = {"dugum": k, "onceki": onceki, "uretiliyor": False,
             "adresler": {self.adres_bul(ad)[0] for ad in k.izlenenler}}
        if k.bekle:
            c = self.ifade(k.kosul)
            self.yaz(f"store i1 {c}, ptr {onceki}")
        else:
            self.yaz(f"store i1 false, ptr {onceki}")
        self.yerel_whenler.append(w)
        if not k.bekle:
            self.yerel_when_kontrol(w)

    def yerel_when_kontrol(self, w):
        """Blok içi when'in kontrolünü değişikliğin yapıldığı yere yaz."""
        if w["uretiliyor"]:
            return                               # kendi bloğunun içindeyiz: tekrar tetikleme
        k = w["dugum"]
        c, o, ters, tetik = self.yeni(), self.yeni(), self.yeni(), self.yeni()
        c = self.ifade(k.kosul)
        self.yaz(f"{o} = load i1, ptr {w['onceki']}")
        self.yaz(f"{ters} = xor i1 {o}, true")
        self.yaz(f"{tetik} = and i1 {c}, {ters}")
        self.yaz(f"store i1 {c}, ptr {w['onceki']}")
        govde, devam = self.etiket("when_oldu"), self.etiket("when_devam")
        self.yaz(f"br i1 {tetik}, label %{govde}, label %{devam}")
        self.blok_baslat(govde)
        w["uretiliyor"] = True
        self.blok(k.govde)
        w["uretiliyor"] = False
        c2 = self.ifade(k.kosul)                 # blok değişkeni değiştirmiş olabilir: durumu güncelle
        self.yaz(f"store i1 {c2}, ptr {w['onceki']}")
        self.yaz(f"br label %{devam}")
        self.blok_baslat(devam)

    def kuresel_when_fonksiyonu(self, k):
        """Ana programdaki when → gizli bir fonksiyon. İzlenen değişken programın
        neresinde değişirse değişsin (fonksiyonlardaki 'use change' dahil) bu çağrılır."""
        n = self.kuresel_whenler[id(k)]
        self.fonksiyon_baslat("void")
        g = f'@"when.{n}'
        a, r, o, ters, tetik = self.yeni(), self.yeni(), self.yeni(), self.yeni(), self.yeni()
        son, d1, d2, govde = self.etiket("son"), self.etiket("aktif"), self.etiket("bos"), self.etiket("oldu")
        self.yaz(f'{a} = load i1, ptr {g}.aktif"')          # when satırına henüz gelinmediyse: bir şey yapma
        self.yaz(f"br i1 {a}, label %{d1}, label %{son}")
        self.blok_baslat(d1)
        self.yaz(f'{r} = load i1, ptr {g}.calisiyor"')      # zaten çalışıyorsa: tekrar tetikleme
        self.yaz(f"br i1 {r}, label %{son}, label %{d2}")
        self.blok_baslat(d2)
        c = self.ifade(k.kosul)
        self.yaz(f'{o} = load i1, ptr {g}.onceki"')
        self.yaz(f"{ters} = xor i1 {o}, true")
        self.yaz(f"{tetik} = and i1 {c}, {ters}")
        self.yaz(f'store i1 {c}, ptr {g}.onceki"')
        self.yaz(f"br i1 {tetik}, label %{govde}, label %{son}")
        self.blok_baslat(govde)
        self.yaz(f'store i1 true, ptr {g}.calisiyor"')
        self.blok(k.govde)
        self.yaz(f'store i1 false, ptr {g}.calisiyor"')
        c2 = self.ifade(k.kosul)
        self.yaz(f'store i1 {c2}, ptr {g}.onceki"')
        self.yaz(f"br label %{son}")
        self.blok_baslat(son)
        self.yerelleri_birak()
        self.yaz("ret void")
        return self.fonksiyon_bitir(f'define internal void @"when.{n}"() {{')


def llvm_ir_uret(program, kontrolcu):
    return LLVMUretici(kontrolcu).uret(program)
