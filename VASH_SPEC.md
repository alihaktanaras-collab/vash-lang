# Vash — tek sayfalık dil tarifi (yapay zekâ ajanları ve hızlı öğrenenler için)

Vash: Python kadar kolay okunan, C++ hızında çalışan, yan etkisi ve belleği güvenli, derlenen bir dil.
Dosya uzantısı `.vash`. Anahtar kelimeler İngilizce. Hata mesajları İngilizce ya da Türkçe: `VASH_DIL=tr` (ya da `en`) ayarı; yoksa Windows Türkçeyse Türkçe. `check --json` ayar yoksa hep İngilizce.
Bu belgedeki her ` ```vash ` bloğu tek başına derlenen eksiksiz bir programdır (`python vashc/spec_dene.py` ile sınanır).

## 0. Çalıştırma ve kontrol
```text
vash run   dosya.vash          derle ve çalıştır
vash build dosya.vash          sadece .exe üret
vash check dosya.vash          sadece hataları kontrol et (hiçbir şey üretmez)
vash check --json dosya.vash   ajanlar için: hatayı JSON olarak verir (çıkış kodu: 0 = hatasız, 1 = hata)
vash kum [--izin files+net] [--klasor yol] [--sure 30] dosya.vash   kum havuzu (bkz. KUM_HAVUZU.md)
```
`--json` çıktısı (derleyici ilk hatada durur; `errors` en fazla 1 eleman içerir):
```text
{"ok": false, "file": "a.vash", "errors": [{"stage": "types", "file": "a.vash", "line": 2, "column": 7,
 "message": "'toplm' diye bir değişken yok.", "details": "Bunu mu demek istedin: 'toplam'?", "suggestion": "toplam"}]}
```
`stage`: `lexer` · `parser` · `modules` · `types` · `codegen` · `file`. `file`: hatanın olduğu dosya (modüldeyse onun adı).
`suggestion` sadece "Bunu mu demek istedin" önerisi varsa bulunur. **Ajan için kural: düzelt → `vash check --json` → `ok: true` olana kadar tekrarla.**
Hatasızsa çıktıda programın (dolaylı olarak) kullandığı izinler ve C kütüphaneleri de olur:
`{"ok": true, ..., "permissions": ["files", "screen", "sound"], "c_libraries": ["raylib|graphics.vash"]}` (güvenlik kartı bunu kullanır).

## 1. Değişkenler, tipler, yazdırma
```vash
var x = 5                      # tip tahmin edilir: int
var y: float = 2               # int → float kendiliğinden çevrilir
var ad = "Ali"                 # text
var acik = true                # bool
var notlar: [int] = []         # boş liste: tip ŞART
x = x + 1                      # var olmadan: var olan değişkene yeni değer
print("Ad:", ad, "x:", x)      # virgüller arasına boşluk konur, sonra alt satır
write("aynı satırda ")         # alt satıra geçmez
print("Merhaba {ad}, {x * 2}") # metin içine her ifade yazılabilir
print(7 / 2, 7 // 2, 7 % 2, -7 // 2)   # 3.5 3 1 -4   (/ hep float; // ve % aşağı yuvarlar)
```
- Temel tipler: `int` (64 bit, taşarsa çalışma hatası), `float`, `bool`, `text`, `bytes` (ikili veri), `[T]` liste, `{K: V}` sözlük, kendi tipler, `T?`.
- Bir değişkenin tipi değişmez. Oluşturmadan kullanmak, aynı adla tekrar oluşturmak ve iç blokta dıştaki adı gölgelemek hatadır.
- Bir `{ }` bloğunda oluşturulan değişken blok bitince yok olur.
- Komutlar satır sonuyla biter; aynı satırda iki komut için `;`.

## 2. Karar, mantık, döngüler
```vash
var puan = 75
if puan >= 90 {
    print("A")
} else if puan >= 70 and puan is not 72 {
    print("B")
} else {
    print("C")
}
repeat 3 { write("x") }
print("")
repeat i from 1 to 5 { write("{i} ") }          # 5 dahil
repeat i from 10 to 1 step -2 { write("{i} ") } # geriye saymak için step -N şart
var n = 0
repeat while n < 10 {
    n = n + 1
    if n % 2 is 0 { skip }                      # continue
    if n > 7 { stop }                           # break
}
print(not (n is 8) or false)
```
- Eşitlik `is` / `is not` (**`==` ve `!=` yok**). Şart her zaman `bool` olmalı (`if x {}` sayıyla hata).
- `repeat i from 1 to 0` hiç çalışmaz (yön kendiliğinden dönmez). Sayaç döngü içinde değiştirilemez. `step 0` hata.
- Bit işlemleri (sadece `int`): `a & b`, `a | b`, `a ^ b`, `a << n`, `a >> n` (n 0–63 olmalı, yoksa çalışma hatası).
  Hepsi `+`/`-`'den zayıf, karşılaştırmadan güçlü: `x & 1 is 0` doğru çalışır. `bool` için `and`/`or` yazılır.

## 3. Fonksiyonlar ve `use` (yan etki güvenliği)
```vash
global var PI = 3.14159        # global: her fonksiyon OKUYABİLİR
var sayac = 0                  # ana program değişkeni: fonksiyonlar GÖREMEZ (use olmadan)

fn alan(r: float) -> float {   # parametre tipleri her zaman yazılır
    return PI * r * r
}

fn artir(kac: int) {
    use change sayac           # dışarıdakini değiştirmek için
    sayac = sayac + kac
}

fn goster() {
    use sayac                  # sadece okumak için
    print("sayaç:", sayac)
}

artir(2)
goster()
print(alan(2.0), kare(3))      # fonksiyonlar tanımlanmadan önce de çağrılabilir

fn kare(x: int) -> int {
    return x * x
}
```
- Fonksiyon sadece parametrelerini, kendi değişkenlerini, `global var`'ları ve `use` ile çağırdıklarını görür.
- Değer döndüren fonksiyon her yolda `return` etmeli. Fonksiyon parametre listesi **tek satırda** yazılır.

## 4. İzinler: dış dünyaya dokunan kod bunu söylemek zorunda
```vash
fn kaydet(yazi: text) -> bool {
    use files                  # yazılmazsa DERLEME HATASI
    return append_file("vash_spec_ornek.txt", "{yazi}\n")
}

fn rapor() {
    use files                  # kaydet'i çağırdığı için bu da yazmak zorunda (dolaylı da sayılır)
    if kaydet("bitti") {
        print("yazıldı")
    }
}

rapor()                        # ana program her şeye izinlidir
```
İzinler: `files`, `net`, `system`, `screen`, `sound`, `time`. Saf hesaplar izin istemez.

## 5. Listeler ve sözlükler (değer anlamı: kopya gibi davranır)
```vash
var meyveler = ["elma", "armut"]
meyveler.add("kiraz")          # sona ekle
meyveler[2] = "muz"            # 1'den başlar!
meyveler.remove(1)             # 1. elemanı sil
print(meyveler, meyveler.length, meyveler.join(", "))

var b = meyveler
b.add("nar")                   # meyveler DEĞİŞMEZ (kopyala-yaz)

var notlar = {"Ali": 90, "Ayşe": 85}     # {text: int}
notlar["Can"] = 70
print(notlar["Ali"], notlar.get("Veli", else: 0), notlar.has("Can"))
notlar.remove("Ayşe")
print(notlar.keys(), notlar.values(), notlar.length)   # keys eklenme sırasını korur
var bos: {text: [int]} = {}
print(bos.length)
```
- Listeler ve sözlükler `is` ile karşılaştırılamaz. Sınır dışı erişim çalışma hatası verir (`liste[0]` de).
- Sözlük anahtarı `text` ya da `int`. Olmayan anahtarı `s[k]` ile okumak çalışma hatası; `get(k, else: v)` güvenli.

İç içe değiştirme: bir değişkenin içindeki liste, sözlük ya da nesne doğrudan değiştirilebilir (sadece değişen parça kopyalanır).
```vash
type Ogrenci {
    ad: text
    notlar: [int] = []
}
var sinif = [Ogrenci(ad: "Ali"), Ogrenci(ad: "Can")]
sinif[1].notlar.add(90)                  # listedeki nesnenin listesine ekle
sinif[2].ad = "Can Demir"
var m: [[int]] = [[0, 0], [0, 0]]
m[2][1] = 5                              # matris
var gruplar: {text: [text]} = {"meyve": []}
gruplar["meyve"].add("elma")
print(sinif, m, gruplar)
```

## 6. Metinler
```vash
var s = "çiçek"
print(s.length, s[1], s[2 to 4])           # 5 ç içe   (Türkçe harfler tek harf sayılır)
print("istanbul".upper("tr"), "IŞIK".lower("tr"))
print(" a b ".trim(), "a,b".split(","), "bir  iki".split())
print(s.contains("çe"), s.starts_with("çi"), s.ends_with("k"), s.replace("ç", "c"))
print("7".is_digit(), "ş".is_letter(), " ".is_space(), code("A"), char(66))
print("Satır\tsekme \"tırnak\" \\ \{süslü\}")
var adlar = ["a", "b"]
print("Liste: {adlar.join(", ")}")         # { } içinde tırnaklı metin yazılabilir
```
- Metinler `+` ile **birleştirilmez**: `"{a}{b}"` ya da `[a, b].join("")` kullan.
- Metinler değiştirilemez (`trim()` yeni metin döndürür). `metin[i]` 1'den başlar, `a to b` iki ucu da dahil eder.
- Özel yazımlar: `\n` `\t` `\"` `\\` `\{` `\}`. (`\r` yok: `char(13)`.)

## 7. Hazır fonksiyonlar
```vash
var ad = input("Adın: ")                   # tip yoksa text
var yas: int = input("Yaşın: ")            # int istenince geçerli sayı gelene kadar sorar
var zar = random(1 to 6)                   # iki uç dahil
var oran = random(0.0 to 1.0)
var secim = random(["a", "b", "c"])
var sure = measure {
    var t = 0
    repeat i from 1 to 1000 { t = t + i }
}
print(ad, yas, zar, oran, secim, sure, time())
print(int("42"), int("abc", else: 0), int(3.7), float("2.5"), text(42))
var icerik = read_file("yok.txt") else: "(boş)"           # text?  okunamazsa none
var satirlar = read_lines("yok.txt") else: []              # [text]?
print(icerik, satirlar.length, file_exists("yok.txt"), write_file("vash_spec_ornek.txt", "x\n"))
```

## 8. Kendi tipler (`type`)
```vash
type Ogrenci {
    ad: text
    notlar: [int] = []                     # varsayılan değer

    fn ortalama() -> float {               # alanlar doğrudan adıyla (self yok); sadece okur
        if notlar.length is 0 {
            return 0.0
        }
        var toplam = 0
        repeat i from 1 to notlar.length { toplam = toplam + notlar[i] }
        return toplam / notlar.length
    }

    fn change not_ekle(n: int) {           # nesneyi değiştiren metot "change" ile işaretlenir
        notlar.add(n)
    }
}

var ali = Ogrenci(ad: "Ali")               # oluşturma HER ZAMAN alan adlarıyla
ali.not_ekle(90)
ali.ad = "Ali Can"
print(ali.ad, ali.ortalama(), ali)
var sinif: [Ogrenci] = [ali, Ogrenci(ad: "Ayşe", notlar: [80])]
print(sinif[2].ortalama())
```
- Nesneler de değer anlamlıdır: `var b = a` sonra `b.ad = "x"` → `a` değişmez. `is` ile karşılaştırılamaz.
- Bir tip kendi tipinde alan içeremez (ama `[Tip]` olabilir). Alan değiştirme ve `change` metot sadece doğrudan bir değişkenin üzerinde.

## 9. `enum` ve `match`
```vash
enum Sekil {
    Kare(kenar: float)
    Daire(r: float)
    Bos
}

fn alan(s: Sekil) -> float {
    match s {
        Kare(k) { return k * k }           # alanlara sırayla ad verilir (sadece okunur)
        Daire(r) { return 3.14 * r * r }
        Bos { return 0.0 }
    }
}

var sekiller = [Sekil.Kare(kenar: 2.0), Sekil.Bos, Sekil.Daire(r: 1.0)]
repeat i from 1 to sekiller.length {
    match sekiller[i] {
        Bos { print("boş") }
        else { print(alan(sekiller[i])) }  # geri kalanlar
    }
}
```
- Çeşit unutulur ve `else` yoksa derleme hatası. Enum alanlarına `s.kenar` ile erişilmez, sadece `match` ile.

## 10. Yok olabilen değer: `T?` ve `none`
```vash
type Kisi {
    ad: text
}

fn bul(ad: text) -> Kisi? {
    if ad is "Ali" {
        return Kisi(ad: "Ali")
    }
    return none
}

var k = bul("Veli")
if k is not none {
    print(k.ad)                            # kontrolden sonra güvenli
}
var ad = (bul("Can") else: Kisi(ad: "bilinmiyor")).ad
print(ad, k)                               # print none yazabilir

fn uzunluk(ad: text) -> int {
    var x = bul(ad)
    if x is none {
        return 0                           # erken çıkış: aşağıda x kesin var
    }
    return x.ad.length
}
print(uzunluk("Ali"))
```
- Kontrol edilmemiş kullanım **derleme hatası**. Sadece metin, liste, sözlük, kendi tip, enum için (`int?` yok).

## 11. `when`: şart yanlıştan doğruya döndüğü an bir kere çalışır
```vash
var can = 100
when can <= 0 {
    print("öldün")
    can = 100                              # kendini tekrar tetiklemez
}
when later can > 150 {                     # later: şart şu an doğru olsa da bekle
    print("çok güçlü")
}
fn hasar(n: int) {
    use change can
    can = can - n                          # when burada da çalışır
}
hasar(60)
hasar(60)
print(can)
```

## 12. Modüller
```text
# geometri.vash (aynı klasörde)        # ana.vash
global var PI = 3.14159                 import geometri
type Nokta { x: float  y: float }       var n = geometri.Nokta(x: 1.0, y: 2.0)
fn alan(r: float) -> float {...}        print(geometri.alan(2.0), geometri.PI)
fn _gizli() {...}                       # geometri._gizli() → HATA: '_' ile başlayan adlar gizli
```
- Hep dosya adıyla kullanılır. İçe alınan dosyada sadece tanım olur (fn, type, enum, extern, global var, import).
- Başka dosyanın değişkeni dışarıdan değiştirilemez. `import` sadece dosyanın en dışında.

## 13. C kütüphaneleri: `extern`
```vash
extern "msvcrt" {
    fn sqrt(x: float) -> float
    fn abs(x: i32) -> i32                  # i32: C'nin küçük tam sayısı (Vash'ta int gibi)
}
extern "msvcrt" needs files {              # dış dünyaya dokunanlar izin söyler
    fn fopen(ad: text, kip: text) -> ptr   # ptr: içine bakılmayan C tutamacı (none olabilir)
    fn fclose(f: ptr) -> i32
}
print(sqrt(2.0), abs(-5))
var f = fopen("vash_spec_ornek.txt", "a")
if f is not none {
    print(fclose(f))
}
```
Tipler: `int`, `i32`, `u8`, `float`, `f32`, `bool`, `text`, `ptr`. `fn _ad(...)` gizlidir ve C'deki adı `ad`'dır.

C yapıları da `extern` içinde tanımlanır ve Vash'ta normal tip gibi kullanılır (değer olarak C'ye gider/gelir):
```text
extern "raylib" needs screen {
    type Renk {
        r: u8
        g: u8
        b: u8
        a: u8 = 255
    }
    fn _ClearBackground(renk: Renk)
}
var mor = Renk(r: 200, g: 122, b: 255)
```
Hazır `graphics` modülü (Raylib): `import graphics` → `graphics.open_window(800, 600, "Oyun")`, `repeat while graphics.is_open() { graphics.begin_drawing(graphics.DARK_BLUE) ... graphics.end_drawing() }`,
`graphics.draw_circle / draw_rectangle / draw_text / key_down / mouse_position / frame_time / fps`. Örnek: `ornekler/parcaciklar.vash`.
- Pencere: `open_resizable_window`, `screen_width/height`, `set_title`, `set_min_size`, `maximize_window`, `set_exit_key(0)`, `elapsed()`.
- Şekiller: `draw_line`, `draw_triangle`, `draw_circle_outline`, `draw_rectangle_outline`, `draw_rounded(x, y, g, y, yarıçap, renk)`,
  `draw_rounded_outline`, `draw_gradient`, `clip_begin/clip_end` (sadece kutunun içi çizilir). Renk: `rgb`, `rgba`, `fade(renk, 0.5)`.
- Resim: `var r = graphics.load_texture("a.png")`, `texture_ok(r)`, `draw_texture(r, x, y)`,
  `draw_sprite(r, kx, ky, kg, ky, x, y, g, y, açı, aynala, renk)` (resmin bir parçası; döndür/aynala), `set_smooth(r, false)`, `unload_texture`.
- Yazı tipi (Türkçe harflerle): `var f = graphics.load_font("C:/Windows/Fonts/segoeui.ttf", 32)`, `draw_text_font(f, "Çığ", x, y, 32.0, renk)`, `text_width_font`.
- Ses (`sound` izni ister): `open_audio()`, `load_sound("a.wav")` + `play_sound`/`stop_sound`/`sound_playing`/`set_sound_volume`;
  müzik: `load_music` + `play_music` ve her karede `update_music(m)`.
- Kamera: `var k = graphics.camera(ox, oy, hx, hy, zoom)`, `camera_begin(k)` ... `camera_end()`, `screen_to_world`, `world_to_screen`.
- Giriş: `key_pressed`, `key_repeated`, `key_released`, `typed_char()` (→ text), `mouse_pressed(graphics.MOUSE_LEFT)`, `mouse_released`,
  `mouse_button_down`, `mouse_wheel`, `mouse_moved`, `set_cursor(graphics.CURSOR_HAND)`.
- `extern` içinde `bytes` değer olarak verilebilir (C verinin adresini alır); C yapısının alanı `ptr` olabilir.

Hazır `engine` modülü (Vash Engine 2D): `engine.run("oyun.json")` sahneyi kendi penceresinde oynatır. Kendi kodunla:
`var g = engine.load("oyun.json") else: engine.Game()`, `engine.open(g, g.title)`, `g.prepare(g.folder)`, her karede `g.update(graphics.frame_time())` ve `g.show()`.
Nesneler `g.things` (`g.find("Oyuncu")` → sıra), hazır davranışlar `platformer, topdown, gravity, patrol, enemy, danger, collect, goal, float, camera`;
`g.say("mesaj", 2.0)`, `g.score`, `engine.save(g, "oyun.json")`. Düzenleyici: `vash_engine/` (bkz. `vash_engine/BENIOKU.md`).

Hazır `fs` modülü (dosya sistemi, `use files`): `fs.list(yol)` → `[fs.Entry]` (`name`, `is_dir`, `is_link`, `size`, `modified`),
`fs.hash(yol)` / `fs.quick_hash(yol)` (içerik parmak izi), `fs.read_head(yol, n)` → `bytes`, `fs.trash(yol)` (Geri Dönüşüm Kutusu'na),
`fs.drives()`, `fs.disk_size(k)`, `fs.disk_free(k)`, `fs.reveal(yol)` (Gezgin'de göster), `fs.cores()`, `fs.join/name/parent/extension`, `fs.size_text(n)`.

Hazır `iso` modülü (izometrik ızgara): `var g = iso.Grid(origin_x: 228.0, origin_y: 6.0, tile_w: 32.0, tile_h: 16.0, size: 14)`,
`g.tile_to_world(x, y)` (karonun üst köşesi), `g.world_to_tile(wx, wy)` (→ `iso.Tile`, dışarıdaysa x = -1), `iso.draw_tile`, `iso.draw_area`, `iso.draw_area_outline`.

Hazır `math` modülü: `math.sqrt/sin/cos/tan/atan2/pow/exp/log/floor/ceil/round/abs/min/max/clamp/lerp/sign/radians/degrees`,
`math.PI`, `math.TAU`; tam sayı için `abs_int/min_int/max_int/clamp_int`. 2B vektör: `var v = math.vec2(3.0, 4.0)` →
`v.length()`, `v.normalized()`, `v.add(b)`, `v.sub(b)`, `v.scale(2.0)`, `v.dot(b)`, `v.distance(b)`, `v.rotated(açı)`, `v.lerp_to(b, t)`, `math.from_angle(a)`.

## 14. Pencere (masaüstü arayüz)
```vash
var sayi = 0
var ad = ""
var liste = ["elma", "armut"]
var secili = 0
window "Sayaç" {
    label "Merhaba {ad}! Sayı: {sayi}"     # değişince kendiliğinden güncellenir
    textbox "Adın" -> ad                   # iki yönlü bağ
    row {
        button "Artır" { sayi = sayi + 1 }
        button "Ekle" { liste.add(ad) }
    }
    list meyve, i in liste -> secili {     # her eleman için bir satır
        label "{i}. {meyve}"
        button "Sil" { liste.remove(i) }
    }
}
print("pencere kapandı")
```
Parçalar: `label`, `button {}`, `textbox -> v`, `checkbox -> bool`, `row {}`, `list e[, i] in l [-> secili] {}`.
Sadece ana programın en dışında, tek pencere.

## 15. Bellek: `arena { }` (oyun karesi gibi tekrar eden işler için)
```vash
type Parca {
    x: float
    ad: text
}

var sonuc = ""
var kayitlar: [text] = []
repeat kare from 1 to 100 {
    arena {                                    # bloktaki geçici her şey blok bitince tek hamlede silinir
        var parcalar: [Parca] = []
        repeat i from 1 to 50 {
            parcalar.add(Parca(x: i * 1.5, ad: "parça {i}"))
        }
        sonuc = "kare {kare}: {parcalar.length} parça"   # dışarı giden değer kendiliğinden kopyalanır
        kayitlar.add(parcalar[1].ad)                     # dışarıdaki listeye konan da
    }
}
print(sonuc, kayitlar.length)
```
- Programcı hiçbir şey kopyalamaz; yanlış kullanmak mümkün değil. Sonuç arenasız yazılmışıyla aynıdır, sadece daha hızlı.
- Bloğun içinde `return` ve dışarıdaki döngüye `stop`/`skip` yazılamaz. İç içe olabilir.

## 16. Çok çekirdek: `parallel`
```vash
fn kare_toplami(bas: int, son: int) -> int {
    var t = 0
    repeat i from bas to son { t = t + i * i }
    return t
}

parallel {                                     # her komut ayrı bir çekirdekte, aynı anda
    var a = kare_toplami(1, 100000)            # 'var' ile oluşan bloktan sonra da kullanılır
    var b = kare_toplami(100001, 200000)
}
print(a + b)

var hizlar = [1.0, 2.0, 3.0]
var konumlar = [0.0, 0.0, 0.0]
parallel repeat i from 1 to konumlar.length {  # turlar çekirdeklere bölünür
    konumlar[i] = konumlar[i] + hizlar[i] * 0.5    # her tur SADECE kendi sırasına yazar
}
print(konumlar)

var toplam = 0
var sayaclar: [int] = [0, 0, 0]
parallel repeat i from 1 to 1000 {             # toplama: her çekirdek kendi ara toplamını tutar, sonunda birleşir
    toplam = toplam + i * i
    sayaclar[i % 3 + 1] = sayaclar[i % 3 + 1] + 1
}
print(toplam, sayaclar)
```
- **Aynı değişkene aynı anda dokunmak derleme hatasıdır** (çağrılan fonksiyonların `use change`'leri de, sonuna kadar sayılır).
- `parallel { }`: bir işin değiştirdiğine başka iş dokunamaz. `parallel repeat`: dışarıda sadece `liste[i] = ...` değişebilir;
  o liste turda sadece `liste[i]` / `liste.length` olarak okunur; değiştiren fonksiyon çağrılamaz; `step`, `stop`, `skip` yok.
- İçlerinde `return` yok. `when`'in izlediği değişken paralelde değiştirilemez.

## 16b. Hazır araçlar: argümanlar, sıralama, desenler, CSV, JSON, baytlar
```vash
import csv
import json

var bilgiler = args()                          # komut satırından verilenler (program adı hariç)
var sayilar = [5, 2, 9]
sayilar.sort()                                 # int/float/text/bool kendiliğinden sıralanır
var adlar = ["Zeynep", "Al", "Can"]
adlar.sort(by: kisa_once)                      # ya da "önce mi?" fonksiyonuyla
print(bilgiler.length, sayilar, adlar)

fn kisa_once(a: text, b: text) -> bool {
    return a.length < b.length
}

var satir = "sipariş 42: 3 adet, 120 TL"      # düzenli ifadeler (regex), metnin işleri olarak (matches: metnin TAMAMI uyuyor mu?)
print("42".matches("\\d+"), satir.find("\\d+") else: "yok", satir.find_all("\\d+"), satir.replace_pattern("\\d+", "#"))

var tablo = csv.parse("ad,yas\nAli,30\n\"Can, Jr\",25")         # [[text]]; tırnaklı hücreler dahil
var kayitlar = csv.parse_records("ad,yas\nAli,30")               # [{text: text}]
print(tablo[3][1], kayitlar[1]["yas"], csv.stringify(tablo).length)

var veri = json.parse("\{\"ad\": \"Ali\", \"notlar\": [90, 75]\}") else: json.null()
print(json.as_text(json.get(veri, "ad"), ""), json.as_int(json.at(json.get(veri, "notlar"), 2), 0))
print(json.stringify(json.object({"tamam": json.boolean(true)})))

var b = "PNG".to_bytes()                       # bytes: ikili veri (her bayt 0–255)
b.add(0)
b.add_int(1000, 2)                             # 2 baytlık sayı (küçük uçtan)
print(b, b.length, b[1], b.get_int(5, 2), b[1 to 3].to_text(), bytes(3))
```
- `bytes`: `read_bytes(yol) -> bytes?`, `write_bytes(yol, b) -> bool` (`use files` ister), `bytes(n)`, `b[i]`, `b[i] = x`, `b[a to b]`,
  `b.add(x)`, `b.add_int(sayi, boyut)` ve `b.get_int(sira, boyut)` (boyut 1/2/4/8; 1–4 işaretsiz okunur), `metin.to_bytes()`, `b.to_text()`.
- JSON değerleri `json.Json` enum'udur: `Null`, `Bool(value)`, `Number(value)`, `String(value)`, `Array(items)`, `Object(fields)`; `match` ile de açılabilir.

## 16c. Arka planda iş (`start` / `wait`) ve HTTP
```vash
import http

fn indir(adres: text) -> text {                # başlatılan fonksiyon sadece kendisine verilenle çalışır
    use net
    var c = http.get(adres)                    # http.Response? (olmazsa none; nedeni: http.error())
    if c is none {
        return "olmadı: {http.error()}"
    }
    return "{c.status}: {c.body.length} harf"
}

var isler: [task[text]] = []                   # task[T]: T döndüren arka plan işi (değer döndürmeyen: task[])
isler.add(start indir("http://127.0.0.1:1/a")) # iş hemen başlar, program devam eder
isler.add(start indir("http://127.0.0.1:1/b"))
repeat i from 1 to isler.length {
    print(isler[i].wait())                     # bitmesini bekle, sonucu al (her iş bir kez); .done(): bitti mi?
}

fn sunucu_ac() {
    use net
    var sunucu = http.listen(8080) else: http.Server(id: 0, port: 0)
    var calisiyor = sunucu.id is not 0
    repeat while calisiyor {
        var istek = sunucu.next()              # sıradaki istek; bağlantılar arka planda aynı anda kabul edilir
        if istek.method is "GET" and istek.path is "/selam" {
            istek.reply(200, "merhaba {istek.param("ad")}")        # ?ad=Ali
        } else if istek.path is "/kapat" {
            istek.reply(200, "\{\"durum\": \"kapandı\"\}")          # { ya da [ ile başlıyorsa JSON gider
            calisiyor = false
        } else {
            istek.reply_with(404, "yok", {"X-Neden": "bilinmiyor"})
        }
    }
}
```
- `start f(...)`: sadece kendi (ya da modüldeki) fonksiyonlar. Başlatılan fonksiyon (çağırdıklarıyla birlikte) dışarıdaki bir değişkeni
  değiştiremez, programda değişen bir değişkeni okuyamaz (derleme hatası); değerleri parametreyle alır, sonucunu döndürür.
  Dosya ve ağ kullanabilir. `arena { }` içinde `start` yazılamaz. Aynı işi iki kez `wait` etmek çalışma hatasıdır.
- `http`: `get(url)`, `post(url, govde, tip)`, `request(yontem, url, govde, basliklar)` → `Response?` (`status`, `body`, `headers`: adlar küçük harf).
  `listen(port)` → `Server?`; `sunucu.next()`, `sunucu.next_within(ms)` → `Request?`, `sunucu.close()`.
  `Request`: `method`, `path`, `query`, `body`, `headers`, `param(ad)`, `parts()` (`/urunler/5` → `["urunler", "5"]`),
  `reply(durum, govde)`, `reply_with(durum, govde, basliklar)`. Hepsi `use net` ister. İstekler sırayla işlenir (veri yarışı olmaz).
- Sadece bu bilgisayardan bağlanılabilen sunucu: `http.listen_local(7377)` (127.0.0.1; ağdaki başka cihazlar ulaşamaz).
- HTTPS sunucusu: `http.listen_secure(8443, "sertifika.pfx", "parola")` (sertifika `""` ise deneme için kendi imzalı sertifika üretilir).
  Bağlantılar açık kalır (keep-alive; istemci `Connection: close` demedikçe).

İşler arasında mesajlaşma: `channel[T]` (mesaj kopya gibi gider, sıra korunur):
```vash
fn uret(kanal: channel[text], kac: int) {
    repeat i from 1 to kac {
        kanal.send("parça {i}")               # gönder
    }
    kanal.close()                              # bitti: bekleyen receive'lar none alır
}

var kanal = channel[text]()                    # yeni kanal
var uretim = start uret(kanal, 3)
var m = kanal.receive()                        # sıradakini al (gelene kadar bekler); kapalı ve boşsa none
repeat while m is not none {
    print(m)
    m = kanal.receive()
}
uretim.wait()
var sayilar = channel[int]()
sayilar.send(7)
print(sayilar.try_receive(else: -1), sayilar.try_receive(else: -1))   # try_receive: beklemez
```
- `receive()` / `try_receive()` → `T?`; `int`/`float`/`bool` kanallarında `int?` olmadığı için yedek şart: `receive(else: -1)`.
- Kanal `start`'a parametre olarak verilir. Kapalı kanala `send` çalışma hatası.

## 16d. Hata yakalama, generic, lambda
```vash
fn bol(a: int, b: int) -> int fails {          # fails: hata verebilir
    if b is 0 {
        fail "sıfıra bölünemez"                # hata ver (mesaj: text)
    }
    return a // b
}

fn ortalama(l: [int]) -> int fails {
    var t = 0
    repeat i from 1 to l.length { t = t + l[i] }
    return try bol(t, l.length)                # try: hata olursa yukarı iletir (ya da en yakın catch'e)
}

print(bol(10, 0) else: -1)                     # else: hata olursa yedek değer
do {
    print(try ortalama([2, 4]))
    print(try ortalama([]))
} catch hata {                                 # hata: text
    print("olmadı: {hata}")
}

fn ilk[T](l: [T]) -> T {                       # generic fonksiyon: her tip için ayrı kopya üretilir
    return l[1]
}
type Kutu[T] {                                 # generic tip
    deger: T
    fn al() -> T { return deger }
}
var k = Kutu(deger: "elma")                    # Kutu[text] (tip değerden anlaşılır)
var y: Kutu[int] = Kutu(deger: 5)
print(ilk([7, 8]), ilk(["a"]), k.al(), y.al())

fn uygula(l: [int], f: fn(int) -> int) -> [int] {      # fonksiyon tipi: fn(int) -> int
    var s: [int] = []
    repeat i from 1 to l.length { s.add(f(l[i])) }
    return s
}
var carpan = 3
var carp = fn(x: int) => x * carpan            # lambda; carpan'ın KOPYASI yakalanır
print(uygula([1, 2], carp), uygula([1, 2], fn(x) => x + 1))   # tip beklenen yerden anlaşılır
var sayilar = [5, 3, 8, 1]
print(sayilar.map(fn(x) => x * 2), sayilar.filter(fn(x) => x > 2), sayilar.count(fn(x) => x > 4))
print(sayilar.any(fn(x) => x > 7), sayilar.all(fn(x) => x > 0), sayilar.find(fn(x) => x > 6, else: 0))
sayilar.sort(by: fn(a, b) => a > b)
var blok = fn(x: int) -> text {                # blok lambda
    if x > 4 { return "büyük" }
    return "küçük"
}
print(sayilar, blok(9))
```
- Hata verebilen çağrı ya `try` ya da `else:` ile yazılmalı (derleme hatası). `try` ile gelen hata önce aynı fonksiyondaki `do`/`catch`'e
  gider; yakalanmazsa fonksiyon `fails` olmalı; ana programda yakalanmazsa program anlaşılır mesajla durur.
  `parallel`, `arena`, `when` ve lambda dışına hata iletilemez (içeride yakala). `fails` fonksiyon `start` ile başlatılamaz.
- Generic: tipler çağrıdaki değerlerden anlaşılır; anlaşılamazsa (boş liste) tipi yazılan bir değişken ver. `Kutu` tek başına tip değildir, `Kutu[int]`.
- Lambda: `fn(a, b) => ifade` ya da `fn(a: int) -> int { ... }`. Dışarıdaki değerlerin kopyasıyla çalışır, dışarıdakini değiştiremez,
  içinde `use` yazılmaz. Adı olan fonksiyon da değer olarak verilebilir (`uygula(l, kare)`). Değer döndürmeyen iş tipi: `task[]`.
- Liste işleri: `map`, `filter`, `any`, `all`, `count`, `find` (→ `T?`; sayılarda `else:` şart), `sort(by: lambda)`.

## 17. Diğer dillerden gelenlerin yaptığı hatalar
| Yanlış (başka dil) | Doğru (Vash) |
|---|---|
| `x == 5`, `x != 5` | `x is 5`, `x is not 5` |
| `for i in range(10)`, `for (...)` | `repeat i from 1 to 10 { }` |
| `while x { }` | `repeat while x { }` |
| `break`, `continue` | `stop`, `skip` |
| `elif` | `else if` |
| `x += 1` | `x = x + 1` |
| `"a" + b` | `"a{b}"` |
| `liste[0]` (ilk eleman) | `liste[1]` |
| `s[1:4]` (Python dilimi) | `s[2 to 4]` (metinlerde ve baytlarda) |
| `len(x)`, `x.size()` | `x.length` |
| `x.append(y)`, `x.push(y)` | `x.add(y)` |
| `null`, `nil`, `None` | `none` (sadece `T?` tiplerde) |
| `Ogrenci("Ali")` | `Ogrenci(ad: "Ali")` |
| `self.ad` | `ad` (metodun içinde) |
| `int x = 5`, `let x = 5` | `var x = 5` |
| `def f(x):`, `function f(x) {` | `fn f(x: int) -> int { }` |
| fonksiyondan dışarıdaki değişkeni kullanmak | `use x` / `use change x` |
| `try { } catch (e) { }`, `throw` | `do { try f() } catch hata { }`, `fail "mesaj"`, `f() else: yedek` |
| `x => x * 2`, `lambda x: x * 2` | `fn(x) => x * 2` |
| `List<int>`, `def f<T>` | `[int]`, `fn f[T](...)`, `Kutu[int]` |
| `", ".join(liste)` | `liste.join(", ")` |

## 18. Henüz olmayanlar (yazma; derleyici hata verir)
- Arayüz (trait), tuple, `weak`, generic enum, `fails` lambda, açık tip argümanı (`ilk[int](...)`).
- `+=`, `++`, metin `+`, liste dilimi (`l[2 to 4]` sadece metinde ve baytlarda), `in` operatörü (yerine `contains` / `has`).
- `int?` / `float?` / `bool?`; `is` ile liste/sözlük/nesne/enum karşılaştırma.
- Birden çok satıra bölünmüş fonksiyon parametre listesi (çağrı argümanları, listeler, sözlükler bölünebilir).
- Kilit (`lock`), alt klasör modülleri, birden çok pencere. `parallel repeat` içinde iç içe yazma (`l[i].x = ...`).
