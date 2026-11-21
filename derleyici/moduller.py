# =====================================================================
#  2½. İSTASYON: MODÜLLER (dosyaları birleştirme)
# =====================================================================
#
#  Bir program birden çok dosyadan oluşabilir:
#
#      # geometri.vash                     # ana.vash
#      fn alan(r: float) -> float {...}    import geometri
#                                          print(geometri.alan(2.0))
#
#  Bu istasyon:
#    1) "import geometri" görünce aynı klasördeki geometri.vash dosyasını bulur ve okur
#    2) geometri.vash'taki her şeyin adının önüne "geometri." ekler (alan → geometri.alan)
#       Böylece iki dosyada aynı adlı fonksiyon olsa da karışmaz.
#    3) ana dosyadaki "geometri.alan(...)" yazılarını da "geometri.alan" çağrısına çevirir
#    4) hepsini tek bir program gibi birleştirir; sonraki istasyonlar modül diye bir şey bilmez
#
#  Kurallar (TASARIM.md madde 36):
#    - Başka dosyadaki şeyler hep dosya adıyla kullanılır:  geometri.alan(...)
#    - Adı '_' ile başlayan şeyler gizlidir; sadece kendi dosyasında kullanılabilir
#    - İçe alınan dosyada sadece tanımlar olur (fn, type, enum, extern, global var, import);
#      içe almak hiçbir kodu gizlice çalıştıramaz
# =====================================================================

import difflib
import os

from lexer import kelimelere_ayir, LexerHatasi
from parser import (
    Parser, ParserHatasi, Program, Dugum, ImportKomutu, FonksiyonTanimi, TipTanimi, EnumTanimi,
    ExternBlok, DegiskenTanimi, Isim, Cagri, Atama, UseKomutu, TipAdi, Ozellik, MetotCagrisi,
    Metin, Parametre, AlanAtama,
)
from tipler import TipHatasi, IZINLER


def _hata(dugum, mesaj):
    yer = f"{dugum.dosya}, " if getattr(dugum, "dosya", None) else ""
    raise TipHatasi(f"{yer}Satır {dugum.satir}, sütun {dugum.sutun}: {mesaj}")


def _oneri(ad, adaylar):
    yakin = difflib.get_close_matches(ad, list(adaylar), n=1, cutoff=0.6)
    return f"\n   Bunu mu demek istedin: '{yakin[0]}'?" if yakin else ""


class Modul:
    """İçe alınan bir dosya ve içinde neler olduğu."""
    def __init__(self, ad, yol, program):
        self.ad = ad
        self.yol = yol
        self.program = program
        self.fonksiyonlar, self.tipler, self.enumlar, self.globaller = set(), set(), set(), set()
        self.importlar = []

    def hepsi(self):
        return self.fonksiyonlar | self.tipler | self.enumlar | self.globaller


def _dosya_isaretle(d, dosya):
    """Hata mesajları hangi dosyada olduğunu söyleyebilsin diye her düğüme dosya adını yaz."""
    if isinstance(d, (list, tuple)):
        for x in d:
            _dosya_isaretle(x, dosya)
        return
    if not isinstance(d, Dugum):
        return
    d.dosya = dosya
    for v in vars(d).values():
        if isinstance(v, (Dugum, list, tuple)):
            _dosya_isaretle(v, dosya)


def _ic_importlar(d, ust_seviye=True):
    """En dışarıda olmayan import'ları bul (import sadece dosyanın en dışında yazılabilir)."""
    if isinstance(d, (list, tuple)):
        for x in d:
            yield from _ic_importlar(x, ust_seviye)
        return
    if not isinstance(d, Dugum):
        return
    if isinstance(d, ImportKomutu) and not ust_seviye:
        yield d
    for v in vars(d).values():
        if isinstance(v, (Dugum, list, tuple)):
            yield from _ic_importlar(v, False)


class _AdDuzenleyici:
    """Bir dosyanın ağacını gezer:
       - içe aldığı modüllere yapılan 'geometri.alan(...)' erişimlerini 'geometri.alan' çağrısına çevirir
       - dosya bir modülse, kendi adlarının önüne 'modul.' ekler"""

    def __init__(self, kendi, gorunen):
        self.kendi = kendi                  # bu dosya bir modülse Modul, ana programsa None
        self.gorunen = gorunen              # içe aldığı modüller: ad → Modul

    def yeni_ad(self, ad):
        return f"{self.kendi.ad}.{ad}"

    def kopya_yer(self, yeni, eski):
        yeni.satir, yeni.sutun = eski.satir, eski.sutun
        if getattr(eski, "dosya", None):
            yeni.dosya = eski.dosya
        return yeni

    def modul_erisimi(self, d):
        """geometri.X  /  geometri.X(...)  → ne olduğuna göre yeni bir düğüm"""
        m = self.gorunen[d.nesne.ad]
        ad = d.ad
        if ad.startswith("_"):
            _hata(d, f"'{m.ad}.{ad}' gizli: adı '_' ile başlayan şeyler sadece kendi dosyasında ({m.ad}.vash) kullanılabilir.")
        if ad not in m.hepsi():
            _hata(d, f"'{m.ad}' modülünde '{ad}' diye bir şey yok." +
                  _oneri(ad, [a for a in m.hepsi() if not a.startswith("_")]))
        tam = f"{m.ad}.{ad}"
        if isinstance(d, MetotCagrisi):
            if ad in m.fonksiyonlar or ad in m.tipler:          # geometri.alan(...) / geometri.Nokta(x: ...)
                if getattr(d, "yedek", None) is not None:
                    _hata(d, f"'{tam}(...)' içinde 'else:' kullanılamaz.")
                return self.kopya_yer(Cagri(tam, self.gez(d.argumanlar),
                                            [(a, self.gez(v), t) for a, v, t in getattr(d, "isimli", [])]), d)
            ne = "bir değişken" if ad in m.globaller else "bir enum"
            _hata(d, f"'{tam}' {ne}; çağrılamaz.")
        # Ozellik: geometri.PI / geometri.Odeme (ardından .Kart(...) gelir)
        if ad in m.globaller or ad in m.enumlar:
            return self.kopya_yer(Isim(tam), d)
        if ad in m.fonksiyonlar:
            _hata(d, f"'{tam}' bir fonksiyon; çağırmak için parantez kullan:   {tam}(...)")
        _hata(d, f"'{tam}' bir tip; oluşturmak için alanlarıyla yaz:   {tam}(alan: ...)")

    def gez(self, d):
        if isinstance(d, list):
            return [self.gez(x) for x in d]
        if isinstance(d, tuple):
            return tuple(self.gez(x) for x in d)
        if not isinstance(d, Dugum):
            return d

        # Başka bir modüle erişim: geometri.alan(...) / geometri.PI
        if isinstance(d, (MetotCagrisi, Ozellik)) and isinstance(d.nesne, Isim) and d.nesne.ad in self.gorunen:
            return self.modul_erisimi(d)
        if isinstance(d, AlanAtama) and isinstance(d.nesne, Isim) and d.nesne.ad in self.gorunen:
            _hata(d, f"'{d.nesne.ad}.{d.alan}' başka bir dosyanın değişkeni; dışarıdan değiştirilemez.")

        # Modül adıyla aynı adda değişken olmasın (karışmasın)
        if isinstance(d, (DegiskenTanimi, Parametre)) and d.ad in self.gorunen:
            _hata(d, f"'{d.ad}' içe alınan bir modülün adı; değişkene başka bir ad ver.")
        if self.kendi and isinstance(d, (DegiskenTanimi, Parametre)) and not getattr(d, "_ust", False) \
                and d.ad in self.kendi.globaller:
            _hata(d, f"'{d.ad}' bu dosyanın global değişkeninin adı; yerel değişkene başka bir ad ver.")

        # Önce içindekileri gez
        for k, v in list(vars(d).items()):
            if isinstance(v, (Dugum, list, tuple)) and not k.startswith("_"):
                setattr(d, k, self.gez(v))

        # Metnin içindeki {…} kısımları tip kontrolünde okunur; o zaman da aynı düzeltme yapılsın
        if isinstance(d, Metin):
            d.yeniden_adlandir = self.gez

        # Başka modülün tipi: geometri.Nokta
        if isinstance(d, TipAdi) and "." in d.ad:
            mad, ad = d.ad.split(".", 1)
            if mad not in self.gorunen:
                _hata(d, f"'{mad}' diye içe alınmış bir modül yok. Önce:   import {mad}")
            m = self.gorunen[mad]
            if ad.startswith("_"):
                _hata(d, f"'{d.ad}' gizli: adı '_' ile başlayan şeyler sadece kendi dosyasında kullanılabilir.")
            if ad not in m.tipler and ad not in m.enumlar:
                _hata(d, f"'{mad}' modülünde '{ad}' diye bir tip yok." + _oneri(ad, m.tipler | m.enumlar))

        # Modülün kendi adları: alan → geometri.alan
        if self.kendi:
            k = self.kendi
            if isinstance(d, Cagri) and (d.ad in k.fonksiyonlar or d.ad in k.tipler):
                d.ad = self.yeni_ad(d.ad)
            elif isinstance(d, Isim) and (d.ad in k.globaller or d.ad in k.enumlar):
                d.ad = self.yeni_ad(d.ad)
            elif isinstance(d, Atama) and d.ad in k.globaller:
                d.ad = self.yeni_ad(d.ad)
            elif isinstance(d, TipAdi) and (d.ad in k.tipler or d.ad in k.enumlar):
                d.ad = self.yeni_ad(d.ad)
            elif isinstance(d, UseKomutu) and d.ad not in IZINLER:
                if d.ad not in k.globaller:
                    _hata(d, f"Modüldeki fonksiyonlar 'use' ile sadece kendi dosyalarının global değişkenlerini "
                             f"kullanabilir; '{d.ad}' {k.ad}.vash içinde yok.")
                d.ad = self.yeni_ad(d.ad)
        return d


def modulleri_bagla(ana, klasor):
    """Ana programın import'larını bul, modülleri oku, adlarını düzelt, hepsini tek programda birleştir."""
    for imp in _ic_importlar(ana.komutlar):
        _hata(imp, "'import' sadece dosyanın en dışında yazılabilir (fonksiyonların ve blokların dışında).")
    ana_importlar = [k for k in ana.komutlar if isinstance(k, ImportKomutu)]
    if not ana_importlar:
        return ana

    moduller, sira = {}, []

    def yukle(imp):
        ad = imp.ad
        if ad in moduller:
            return moduller[ad]
        yol = os.path.join(klasor, ad + ".vash")
        if not os.path.exists(yol):
            _hata(imp, f"'{ad}' modülü bulunamadı: {ad}.vash dosyası aynı klasörde olmalı.")
        with open(yol, encoding="utf-8-sig") as f:
            kod = f.read()
        dosya = f"{ad}.vash"
        try:
            program = Parser(kelimelere_ayir(kod)).program()
        except (LexerHatasi, ParserHatasi) as h:
            raise TipHatasi(f"{dosya}, {h}")
        _dosya_isaretle(program, dosya)
        m = Modul(ad, yol, program)
        moduller[ad] = m                            # birbirini içe alan dosyalar sonsuz döngüye girmesin

        for k in program.komutlar:
            if isinstance(k, FonksiyonTanimi):
                m.fonksiyonlar.add(k.ad)
            elif isinstance(k, ExternBlok):
                m.fonksiyonlar.update(f.ad for f in k.fonksiyonlar)
            elif isinstance(k, TipTanimi):
                m.tipler.add(k.ad)
            elif isinstance(k, EnumTanimi):
                m.enumlar.add(k.ad)
            elif isinstance(k, DegiskenTanimi) and k.global_mi:
                m.globaller.add(k.ad)
                k._ust = True
            elif isinstance(k, ImportKomutu):
                m.importlar.append(k)
            else:
                _hata(k, f"{dosya} içe alınan bir modül; içinde sadece tanımlar olabilir "
                         f"(fn, type, enum, extern, global var, import).\n"
                         f"   Çalışan kod (print, var, if, repeat...) ana programda olmalı.")
        for imp2 in _ic_importlar(program.komutlar):
            _hata(imp2, "'import' sadece dosyanın en dışında yazılabilir.")
        for imp2 in m.importlar:
            yukle(imp2)
        sira.append(m)
        return m

    for imp in ana_importlar:
        yukle(imp)

    # Adları düzelt: önce modüller (kendi adları + içe aldıkları), sonra ana program
    for m in sira:
        gorunen = {i.ad: moduller[i.ad] for i in m.importlar}
        for k in m.program.komutlar:            # tanımların kendi adları: alan → geometri.alan
            if isinstance(k, (FonksiyonTanimi, TipTanimi, EnumTanimi, DegiskenTanimi)):
                k.ad = f"{m.ad}.{k.ad}"
            elif isinstance(k, ExternBlok):
                for f in k.fonksiyonlar:
                    f.c_ad = getattr(f, "c_ad", f.ad)     # C'deki gerçek adı sakla
                    f.ad = f"{m.ad}.{f.ad}"
        m.program.komutlar = _AdDuzenleyici(m, gorunen).gez(m.program.komutlar)
    gorunen = {i.ad: moduller[i.ad] for i in ana_importlar}
    ana.komutlar = _AdDuzenleyici(None, gorunen).gez(ana.komutlar)

    # Birleştir: modüllerin tanımları + modüllerin global değişkenleri + ana program
    tanimlar, globaller = [], []
    for m in sira:
        for k in m.program.komutlar:
            if isinstance(k, ImportKomutu):
                continue
            (globaller if isinstance(k, DegiskenTanimi) else tanimlar).append(k)
    return Program(tanimlar + globaller + [k for k in ana.komutlar if not isinstance(k, ImportKomutu)])
