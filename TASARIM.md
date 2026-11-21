# Vash — Dil Tasarım Belgesi

> Bu belge dilin "anayasası". Dile yeni bir özellik eklemeden önce burada beraber karar veriyoruz,
> sonra koda geçiyoruz.

## Ad: **Vash** · dosya uzantısı: **`.vash`**
- Kısa, her dilde kolay söylenir ("vaş"); tanınmış bir programlama diliyle çakışmıyor
- `.vsh` bilerek seçilmedi: oyun geliştirmede vertex shader dosyalarının uzantısı
- Komut: `vash run oyun.vash` (derle ve çalıştır), `vash build oyun.vash` (sadece .exe üret)

## 🧭 Büyük vizyon (bütün kararlar buna göre verilir)
**Kimlik:** Python kadar kolay, C++ kadar hızlı; **yan etkisi ve belleği güvenli** bir sistem dili.
İki amiral gemisi alanı:
1. **Yapay zekâ ajanlarına uygun dil (AI-native):** Yapay zekânın yazdığı kod neye dokunduğunu
   derlerken söylemek zorunda.
   - En güçlü imzamız `use` / `use change`. İleride dış dünyaya da genişler: `use files`, `use net`...
     Bir fonksiyon dosyaya ya da internete dokunuyorsa bu imzasından görünür, derleyici garanti eder.
   - Ajanlar kodu tek seferde doğru yazıp düzeltebilsin: net hata mesajları ("Bunu mu demek istedin?"),
     makinenin okuyabileceği hata çıktısı (`vash check --json`), tek sayfalık güncel dil özeti (`VASH_SPEC.md`).
2. **Vash Engine:** kod odaklı, saniyeler içinde derlenen, çöp toplayıcı takılması olmayan (sayaçlı bellek),
   144+ FPS'te kararlı, hafif bir 2B/3B oyun motoru. Unity gibi devasa bir editör değil.
   - Tekerleği yeniden icat etmeyiz: Raylib, Sokol, WebGPU/OpenGL, Box2D/Jolt, Dear ImGui gibi C
     kütüphaneleri `extern` ile bağlanıp **güvenli Vash kütüphanelerine** sarılır.

**Yol haritası:** `extern` (C'yi çağırma) → modüller (`import`) → derleyiciyi Vash'la yazma (self-hosting) →
oyun motoru ihtiyaçları (her kare için hızlı bellek alanı / arena, paralel çalıştırma kolaylıkları,
ilk grafik penceresi ve ImGui).

## Hedef
- **Genel amaçlı** bir dil: hesaplama, veri işleme, araçlar, uygulamalar, oyunlar... (belli bir alana özel değil;
  amiral gemisi alanları yukarıdaki vizyonda)
- **Python kadar kolay** yazılsın
- **C++ kadar hızlı** çalışsın → gerçek makine koduna (`.exe`) derlenir (LLVM ile, Rust'ın yöntemi)
- Derleyici önce Python'da yazılacak, ileride **dilin kendisiyle** yeniden yazılacak (self-hosting)

## Felsefe: Ne zaman farklı olalım?
> **Diğer dillerin iyi yaptığı yerde aynı kalırız. Herkesi zorlayan yerlerde farklı oluruz.**

Sırf farklı olsun diye bir şeyi değiştirmeyiz. Bir özellik tasarlarken şunu soruyoruz:
*"Diğer dillerde yeni başlayanların burada takıldığı bir tuzak var mı?"* Varsa onu çözüyoruz.

---

## ✅ Verilen kararlar

### 1. Anahtar kelimeler İngilizce

### 2. Bloklar süslü parantezle `{ }`
```
fn selam() {
    print("merhaba")
}
```

### 3. Değişkenler: `var` ile oluşturulur
`var` = `variable` (ikisi de aynı)

```
var x = 5                # yeni değişken, tipi tahmin edilir (int)
var y: int = 5           # yeni değişken, tipi açıkça yazılmış
var liste: [int] = []    # boş liste: tip burada şart, çünkü tahmin edilemez

x = 10                   # var OLMADAN yazınca: var olan değişkenin değerini değiştir
```

- **Oluşturmadan kullanmak hatadır.** Böylece yazım hataları yakalanır:
  ```
  var toplam = 0
  topalm = 5         ← HATA: "topalm" diye bir değişken yok
  ```

### 4. Tipler: derleyici tahmin eder, istenirse yazılır
- Tip yazmak **isteğe bağlıdır**: `var x = 5` de `var x: int = 5` de geçerli
- Derleyicinin tahmin edemediği yerde (ör. boş liste) tip yazmak **zorunludur**
- Fonksiyon parametrelerinde tip **her zaman** yazılır
- **Bir değişkenin tipi bir kere belirlenir, sonra değişmez.** Farklı tipte değer vermek **derleme hatasıdır**:
  ```
  var x = 5
  x = "merhaba"     ← HATA: x bir int, metin verilemez
  ```
- Tip isimleri için 13. maddeye bak

### 5. Fonksiyonlar: `fn` = `function`
```
fn topla(a: int, b: int) -> int {
    return a + b
}
```

### 6. Eş anlamlı kelimeler
Bazı kelimelerin uzun ve kısa hali var, ikisi de çalışır:

| Kısa | Uzun |
|---|---|
| `var` | `variable` |
| `fn` | `function` |
| `int` | `integer` |

Her kelimenin kısa hali **olmak zorunda değil**. Tek harfli kısaltmalar kullanılmaz (okuması zor).

### 7. Eşitlik karşılaştırması: `is` / `is not`
```
if x is 5 { }
if isim is not "Ali" { }
```
- `==` ve `!=` **yoktur**. Böylece `=` (değer ver) ile "eşit mi?" sorusu asla karışmaz.
- Büyük/küçük karşılaştırmaları normal kalır: `<` `>` `<=` `>=`

### 8. Hata mesajları: Türkçe ve İngilizce
- Varsayılan dil Türkçe, istenirse İngilizce
- Her hata mesajı şunları söyler: **nerede** (satır ve sütun), **ne oldu** ve mümkünse **nasıl düzelir**
  ```
  HATA (satır 4): "topalm" diye bir değişken yok.
     topalm = 5
     ^^^^^^
     Bunu mu demek istedin: "toplam"?
  ```

### 9. Ekrana yazdırma: `print` ve `write`
| Komut | Ne yapar |
|---|---|
| `print(...)` | Yazar ve **alt satıra geçer** |
| `write(...)` | Yazar, **aynı satırda kalır** |

```
print("Merhaba")                 # Merhaba ⏎
write("Adın: ")                  # Adın: _   (imleç aynı satırda)

print("Yaş:", yas, "Boy:", boy)  # Yaş: 17 Boy: 180   ← virgülle ayrılanlar arasına boşluk konur
print("Yaş: {yas} Boy: {boy}")   # Yaş: 17 Boy: 180   ← aynısı, metin içine yazarak
```
- Parantez **zorunlu**: `print` normal bir fonksiyon gibi çağrılır, ayrı bir kuralı yoktur
- `print` ve `write` anahtar kelime **değildir**; dilin hazır gelen (yerleşik) fonksiyonlarıdır

### 10. Komut sonu: satır sonu, istenirse `;`
```
var x = 5
var y = 10; var z = 3     # aynı satırda iki komut
```

### 11. Fonksiyondan değer döndürme: `return`
```
fn kare(x: int) -> int {
    return x * x
}
```

### 12. İşlem önceliği: matematikteki gibi
Önce parantez, sonra `*` `/` `%`, sonra `+` `-`, en son karşılaştırma (`is`, `<`, `>` ...).
`2 + 3 * 4` → `14`

### 13. Temel tipler
| Tip | Ne tutar | Örnek değer |
|---|---|---|
| `int` (= `integer`) | Tam sayı | `42`, `-7` |
| `float` | Ondalıklı sayı | `3.14`, `0.5` |
| `text` | Metin | `"merhaba"` |
| `bool` | Doğru / yanlış | `true`, `false` |
| `[tip]` | Liste | `[1, 2, 3]` → `[int]` |

- `int` ile `float` birlikte kullanılabilir, sonuç `float` olur: `2 + 0.5` → `2.5`
- Metinler `+` ile birleştirilmez (tuzak!), metin içine yazılır: `"Merhaba {isim}"`

### 14. Bölme: `/` her zaman tam sonuç verir
```
7 / 2     # 3.5   (sonuç her zaman float)
7 // 2    # 3     (tam sayı bölmesi)
7 % 2     # 1     (kalan)
```

### 15. Kapsam: fonksiyonlar dışarıyı göremez (açıkça istenmedikçe)
Bir fonksiyon sadece **parametrelerini** ve **kendi içinde oluşturduğu** değişkenleri görür.
Dışarıdaki bir değişkeni kullanmak için onu `use` ile çağırır:

```
var vergi = 18
var sayac = 0

fn fiyat(x: int) -> int {
    use vergi                 # dışarıdan çağır → SADECE OKUNABİLİR
    return x + vergi
}

fn artir() {
    use change sayac          # dışarıdan çağır → DEĞİŞTİRİLEBİLİR
    sayac = sayac + 1
}
```

**`global` değişkenler** her fonksiyondan `use` yazmadan **okunabilir**. Değiştirmek için yine `use change` gerekir:
```
global var PI = 3.14159

fn alan(r: float) -> float {
    return PI * r * r         # use gerekmez
}
```
- `global var` sadece en dış seviyede (fonksiyon dışında) yazılabilir
- `change` bağlamsal kelimedir: sadece `use`'dan sonra özel anlam taşır
- **Neden?** Bir fonksiyona bakınca neye bağlı olduğu hemen görülür. Dışarıdaki bir değeri kimin
  değiştirdiği her zaman `use change` satırından bulunur. (Benzerleri: PHP `global`, C++ lambda yakalama listesi)

### 16b. Çalışma zamanı davranışları (4. istasyonda belirlendi)
- `//` ve `%` matematikteki gibi **aşağı** yuvarlar: `-7 // 2` → `-4`, `-7 % 2` → `1` (Python gibi; C++ `-3` verir)
- Ondalık sayılar her zaman noktalı yazılır: `2.0` (tam sayıyla karışmasın), `0.1 + 0.2` → `0.3`
- **Sıfıra bölme** programı çökertmez, anlaşılır bir mesajla durdurur:
  `ÇALIŞMA HATASI (satır 14): Sıfıra bölme yapılamaz.`

### 16. Fonksiyonların sırası serbest
Bir fonksiyon, dosyada tanımlandığı yerden **önce** de çağrılabilir (Rust, Go, Swift gibi).

### 17. Karar verme: `if` / `else if` / `else`
```
if puan >= 90 {
    print("A")
} else if puan >= 70 {
    print("B")
} else {
    print("C")
}
```
- Şart **mutlaka bool** olmalı. `if x { }` (x bir sayıyken) hatadır; ne sorulduğu açıkça yazılır: `if x is not 0 { }`
  (Python'da `if x:` sayıyı gizlice doğru/yanlışa çevirir; bu bir tuzak.)
- Diğer dillerden gelenler için yardım: `elif` yazılırsa "`else if` kullan" denir

### 18. Mantık: `and` / `or` / `not`
```
if yas >= 13 and yas <= 19 { print("genç") }
if not bitti { devam() }
```
- Öncelik: `not` > `and` > `or` (matematikteki çarpma/toplama gibi)
- `and` ve `or` kısa devre yapar: `a and b` yazınca a yanlışsa b'ye hiç bakılmaz

### 19. Döngüler: hepsi `repeat` ile başlar
| Yazılış | Ne yapar |
|---|---|
| `repeat 3 { }` | 3 kere tekrarla |
| `repeat while can > 0 { }` | Şart doğru olduğu sürece tekrarla |
| `repeat i from 1 to 10 { }` | i'yi 1'den 10'a kadar say (10 **dahil**) |
| `repeat i from 1 to 10 step 2 { }` | 2'şer say: 1 3 5 7 9 |
| `repeat i from 10 to 1 step -1 { }` | Geriye say: 10 9 ... 1 |

- **Yön asla kendiliğinden değişmez.** `repeat i from 1 to 0` hiç çalışmaz (geriye saymak için `step -1` şart).
  Böylece `repeat i from 1 to kisi_sayisi` kişi yokken yanlışlıkla çalışmaz.
- `from`, `to`, `step` bağlamsal kelimelerdir: sadece `repeat` içinde özel anlam taşır (`var step = 5` yazılabilir)
- Sayaç (`i`) döngünün içinde **değiştirilemez**, sadece okunur
- `step 0` hatadır (sonsuz döngü olurdu)

### 20. Döngüyü kontrol etme: `stop` / `skip`
| Komut | Ne yapar | Diğer dillerde |
|---|---|---|
| `stop` | Döngüden tamamen çık | `break` |
| `skip` | Bu turu atla, sıradakine geç | `continue` |

Diğer dillerden gelenler `while`, `for`, `break`, `continue` yazarsa derleyici doğrusunu söyler.

### 21. Blok kapsamı
Bir `{ }` bloğunun içinde oluşturulan değişken sadece o blokta geçerlidir:
```
if x > 0 {
    var mesaj = "pozitif"
}
print(mesaj)     ← HATA: mesaj sadece if bloğunun içinde vardı
```
- Aynı fonksiyonda, dışarıda zaten olan bir adla içeride yeni değişken oluşturulamaz (karışıklığı önler)

### 22. Bellek yönetimi: sayaç (referans sayma, Swift gibi)
Hafızadan yer alan her şeyin (metin, liste, ileride kendi tipler) bir **sayacı** vardır:
"bu şeyi kaç yer kullanıyor?" Son kullanan bırakınca yer **hemen** geri verilir.
```
var a = "Sayı {x}"     # yeni metin, sayacı 1
a = "başka"            # eski metnin sayacı 0 → hemen temizlendi
```
- Programcı **hiçbir şey yazmaz** (Python kadar kolay)
- Çöpçü yok → oyunlarda **takılma yok**
- Sayılar (`int`, `float`, `bool`) sayaçsızdır, hafızadan ayrıca yer almaz → sayı ağırlıklı kod C++ ile aynı hızda
- Koddaki sabit metinler (`"merhaba"`) hiç temizlenmez (sayacı "sonsuz")
- **Neden?** Çöpçü (Python/C#/Go) oyunlarda takılma yapar; elle temizlik (C++) hata kaynağıdır;
  sahiplik (Rust) öğrenmesi çok zordur. Sayaç, "kolay + hızlı + takılmasız" hedefine en uygun yol.
- ⚠️ Bilinen zayıf nokta: iki şey birbirini gösterirse sayaç sıfırlanmaz. Kendi tipler gelince çözülecek.
- Hız hedefi: C++ ile yan yana ölçülür, yavaş kalan yer derleyici hileleriyle düzeltilir.
- **Kısa metin hızlandırması:** Metnin başlığında uzunluk da saklanıyor (karşılaştırma ve birleştirme
  harf saymadan yapılıyor); 128 bayttan küçük parçalar için kendi "raf" depomuz var (malloc yerine).
- **Ölçümler** (aynı anda, dönüşümlü; mutlak süreler bilgisayarın o anki durumuna göre değişir, oranlara bakılmalı):
  | Test | Bizim dil | C++ | Not |
  |---|---|---|---|
  | 3 milyon kez `"Sayı {i}"` oluşturmak | ~85 ms | ~120 ms | önce 1.5 kat yavaştık, şimdi ~1.4 kat hızlıyız |
  | Uzun metni 5 milyon kez kopyalamak | 37 ms | 1032 ms (düz yazım) / 27 ms (usta yazımı) | sayaç kopyalamaz, sadece sayar |
  Bellek: sayaçsız 185 MB → sayaçlı 4 MB.
- Bellek raporu: programı `DIL_BELLEK=1` ortam değişkeniyle çalıştırınca, bitişte kaç yer alındığını
  ve kaçının geri verilmediğini yazar.

### 23. Tam sayı taşması: hata ver (Swift gibi)
`int` en fazla 9.223.372.036.854.775.807 tutabilir. Bir işlemin sonucu buna sığmazsa program durur:
```
ÇALIŞMA HATASI (satır 5): Sayı çok büyüdü (int en fazla 9.223.372.036.854.775.807 olabilir).
```
- `+`, `-`, `*`, eksi işareti, `//` ve `%` (en küçük sayı `// -1`) ve döngü sayacının ilerlemesi kontrol edilir
- **Neden?** Sessizce başa sarmak yanlış sonuç verir ve kimse fark etmez (tuzak). C++'taki gibi "tanımsız"
  bırakmak daha da tehlikeli. Hata vermek hem güvenli hem de **hızlı**: kontrol, LLVM'e "sayı taşmadı" bilgisini
  verdiği için başka kontrolleri siliyor. Asal sayı testinde: başa sarma 215-223 ms, hata verme 184-185 ms, C++ 184-191 ms.
- Döngü sayacı taşmaz: "kalan mesafe bir adımdan kısaysa bitir, değilse ilerle" kuralıyla ilerler.
  Böylece `repeat i from 1 to <en büyük int>` de doğru çalışır ve her turda kontrol gerekmez (hız).

### 24. Listeler
```
var meyveler = ["elma", "armut", "kiraz"]    # tip tahmin: [text]
var notlar: [int] = []                       # boş liste: tip şart

print(meyveler[1])          # elma   ← 1'den başlar
meyveler[2] = "muz"         # elemanı değiştir
meyveler.add("çilek")       # sona ekle
meyveler.remove(1)          # 1. elemanı sil
print(meyveler.length)      # eleman sayısı
print(meyveler)             # ["muz", "kiraz", "çilek"]

repeat i from 1 to meyveler.length {
    print(meyveler[i])
}
```
- **1'den başlar** (Lua, Julia gibi): insanların saydığı gibi ve `repeat i from 1 to` ile uyumlu
- **Her liste ayrıdır** (Swift gibi, "değer anlamı"): `var b = a` sonra `b.add(4)` → a **değişmez**.
  Arka planda hemen kopyalanmaz; ikisi aynı listeyi paylaşır, biri değişmeye kalkınca o an kopyalanır
  ("kopyala-yaz", copy-on-write). Sayaç sayesinde bunu anlamak tek bir karşılaştırma: sayaç 1 mi?
  (Python'daki "b'yi değiştirdim a da değişti" tuzağı yok.)
- Fonksiyona verilen liste de kopya gibi davranır: fonksiyon içinde değiştirmek çağıranı etkilemez
- **Sınır dışı hata verir:** `3 elemanlı listenin 10. elemanı yok (satır 5)`; `liste[0]` için ayrıca
  "listeler 1'den başlar" denir
- Liste işleri nokta ile yazılır: `liste.add(x)`, `liste.remove(i)`, `liste.length`
  (ileride kendi tiplerin de aynı şekilde: `oyuncu.hareket()`)
- Şimdilik: `add`/`remove`/`liste[i] = x` sadece bir değişkenin üzerinde yapılabilir (`a[1].add(x)` henüz yok);
  listeler `is` ile karşılaştırılamaz
- **Ölçüm** (10 milyon eleman ekle + 5 kez topla), iyileştirmeden sonra:
  Vash 166-176 ms, C++ 162-187 ms (`v[i]` ve `v.at(i)`), Python ~9150 ms → **C++ ile aynı, Python'dan ~50 kat hızlı.**
  İlk hali ~1.4 kat yavaştı. Makine koduna bakınca bulunan sebepler ve çözümleri:
  1. Döngü sayacının her turdaki taşma kontrolü → "taşmasız ilerleme" (madde 19'a bak)
  2. Sınır kontrolü fonksiyon çağrısıydı, LLVM gömmedi → derleyici kontrolü doğrudan IR olarak yazıyor;
     LLVM bu sayede `repeat i from 1 to liste.length` döngülerinde kontrolü tamamen siliyor
  3. Ana programın değişkenleri global olduğu için her turda hafızaya yazılıyordu → madde 25
  ("add'deki kopyala-yaz kontrolü sebep" tahmini yanlış çıktı: doldurma aşaması zaten C++ ile eşitti.)

### 25. Hangi değişken gerçekten global? (`use` kuralının hız kazancı)
Ana programdaki bir değişken sadece bir fonksiyon onu `use` ile çağırıyorsa ya da `global var` ise
hafızada global olarak durur. Geri kalanlar main'in yerel değişkenidir; LLVM onları işlemcinin hızlı kutularında
(yazmaçlarda) tutar. Derleyici bunu `use` satırlarından **kesin olarak** bilir. C++'ta her fonksiyon her globale
gizlice dokunabildiği için C++ derleyicisi bunu yapamaz.

### 26. `when` — senin fikrin
Bir şart **yanlıştan doğruya döndüğü an** bloğu bir kere çalıştırır:
```
var can = 100
when can <= 0 {
    print("Öldün, yeniden doğuyorsun")
    can = 100                 # izlediği değişkeni değiştirebilir (sonsuz döngüye karşı korumalı)
}
fn hasar_al(n: int) {
    use change can
    can = can - n             # when burada da çalışır
}
```
- **Ne zaman?** Değişken değiştiği satırdan hemen sonra, bir sonraki satıra geçmeden
- **Şart en baştan doğruysa** when hemen bir kere çalışır. Beklemesi istenirse: `when later can <= 0 { }`
  (`later` bağlamsal kelime: sadece `when`'den hemen sonra özel; `when later is 5` gibi yazılırsa
  `later` bir değişken adı sayılır)
- **Nerede?** Ana programda yazılan when program boyunca geçerlidir ve fonksiyonlardaki `use change`
  değişikliklerinde de çalışır. Fonksiyonun ya da bir bloğun içinde yazılan when o blok bitene kadar geçerlidir
  ve o bloğun içindeki değişiklikleri izler.
- Bir when kendi bloğunun içinden tekrar tetiklenemez (sonsuz döngü olmaz)
- when bloğunda `return`, `stop`, `skip` kullanılamaz; döngü sayaçları izlenemez
- **Nasıl hızlı?** Derleyici `use` kuralı sayesinde izlenen değişkenin değiştiği her satırı program çalışmadan bilir;
  kontrol sadece oralara eklenir. Değişmeyen yerlerde maliyet sıfır; "kim kimi izliyor" listesi tutulmaz.
- Şimdilik bilinen sınır: fonksiyon içindeki bir when, başka bir fonksiyonun `use change` ile yaptığı
  değişikliği görmez (sadece kendi bloğundaki değişiklikleri izler)

### 27. Kendi tipler: `type`
```
type Ogrenci {
    ad: text
    notlar: [int] = []          # varsayılan değer (yazılmazsa bu kullanılır)

    fn ortalama() -> float {     # sadece okur
        var toplam = 0
        repeat i from 1 to notlar.length { toplam = toplam + notlar[i] }
        return toplam / notlar.length
    }
    fn change not_ekle(n: int) { # nesneyi değiştirir → "change" ile işaretli
        notlar.add(n)
    }
}

var ali = Ogrenci(ad: "Ali")    # alan adlarıyla oluşturulur
ali.not_ekle(90)
ali.ad = "Ali Can"               # alan değiştirme
print(ali.ad, ali.ortalama())
print(ali)                       # Ogrenci(ad: "Ali Can", notlar: [90])
```
- **Oluşturma alan adlarıyla:** `Tip(alan: değer, ...)`; varsayılan değeri olan alanlar yazılmayabilir.
  Hangi değerin nereye gittiği hep okunur, sıra karışıklığı olmaz.
- **Her değer ayrıdır** (listeler gibi): `var b = a` sonra `b.ad = "x"` → `a` değişmez (kopyala-yaz).
  Bu sayede "birbirini gösterme" (A → B → A) kurulamaz → sayacın sızıntı zayıflığı tiplerde ortaya çıkmaz.
- **Metotlarda alanlar doğrudan adıyla** kullanılır (`self` yazmak gerekmez). Aynı tipin diğer metotları da adıyla çağrılır.
- **Nesneyi değiştiren metot `fn change ...` ile işaretlenir** (`use change` fikrinin devamı; Swift'te `mutating`).
  İşaretsiz metot alanları sadece okuyabilir. `change` metot sadece değiştirilebilir bir değişkenin üzerinde çağrılır.
  Bu bilgi ileride `parallel` ve `when` için de kullanılır.
- `when` tiplerle çalışır: `when hesap.bakiye < 0 { }` → `hesap.bakiye = ...` ya da `hesap.para_cek(...)` sonrası kontrol edilir
- Metotlar da fonksiyonlar gibi dışarıyı göremez (gerekirse `use`)
- Şimdilik: alan değiştirme ve `change` metot çağrısı doğrudan bir değişkenin üzerinde yapılır (`a.b.c = x` henüz yok);
  nesneler `is` ile karşılaştırılamaz; bir tip kendi tipinde bir alan içeremez (ama `[Tip]` listesi olabilir)

### 28. Dış dünya ve metinler: hazır fonksiyonlar
Her biri diğer dillerdeki bilinen bir tuzağı çözecek şekilde tasarlandı:

**`input` — tipe göre otomatik, yanlış girişte çökmez** (Vash'a özgü)
```
var ad = input("Adın: ")              # tip yoksa: metin
var yas: int = input("Yaşın: ")       # int bekleniyor → sayı ister
#   Yaşın: on yedi
#     → Lütfen bir tam sayı gir (örn: 17)
#   Yaşın: 17
```
Vash değişkenin tipini program çalışmadan bildiği için `input` neyin istendiğini kendisi anlar (atama, fonksiyon
parametresi, return... her yerde). Python'da aynı güvenli davranış için döngü + try/except ile 8-10 satır gerekir;
`int(input())` ise yanlış girişte programı çökertir.

**`random` — sınırlar okunduğu gibi**
```
random(1 to 6)                        # zar: 1..6, ikisi de dahil (repeat'teki "to" ile aynı)
random(0.0 to 1.0)                    # ondalık
random(renkler)                       # listeden rastgele bir eleman
```
(Python'da `randint(1,6)` 6'yı dahil eder ama `randrange(1,6)` etmez; C'de `rand() % 6` adil değildir.)
Kaliteli ve adil bir üreteç (splitmix64) kullanılır.

**`measure` — bir bloğun süresini tek satırda ölçer** (Vash'a özgü)
```
var sure = measure {
    asallari_say(1000000)
}
print("Sürdü:", sure, "saniye")
```
Başlangıç/bitiş değişkeni yok, unutma yok; bilgisayarın en hassas saatini kullanır. `time()` da vardır
(program başladığından beri geçen saniye).

**Çevirme — sessizce yanlış sayı yok, istenirse yedek değer**
```
int("42")                 # 42
int("abc", else: 0)       # 0   (çevrilemezse yedek)
int("abc")                # ÇALIŞMA HATASI (satır 3): "abc" bir tam sayıya (int) çevrilemez.
float("3.5")   text(42)   int(3.7) → 3
```
(JavaScript'te `parseInt("12abc")` sessizce 12, C'de `atoi("abc")` sessizce 0 verir.)

| Yazılış | Ne yapar |
|---|---|
| `int(x)` / `int(x, else: y)` | Metni/ondalığı tam sayıya çevirir (`int(3.7)` → 3) |
| `float(x)` / `float(x, else: y)` | Metni/tam sayıyı ondalığa çevirir |
| `text(x)` | Sayıyı/bool'u metne çevirir |
| `time()` | Program başladığından beri geçen saniye |

### 29. Metinler: beraber belirlenen farklar
**Metin içinde her türlü ifade:**
```
print("{ad}, adın {ad.length} harf")
print("Toplam: {fiyat * adet} TL — ilk not: {notlar[1]}")
```
(Şimdilik `{ }` içinde tırnaklı bir metin yazılamaz: `"{x.split(",")}"` olmaz, önce bir değişkene alınır.)

**Harfler ve parçalar 1'den başlar, `to` iki sınırı da dahil eder, Türkçe harfler bozulmaz:**
```
var s = "çiçek"
s[1]          # "ç"
s[2 to 4]     # "içe"
```
(Go'da `"çiçek"[0]` bozuk bir bayt verir; Rust metne sırayla erişime hiç izin vermez; Python'da `s[1:4]`'te 4 dahil değildir.)

**Büyük/küçük harf, dil seçilebilir:**
```
"istanbul".upper()        # ISTANBUL   (evrensel kural)
"istanbul".upper("tr")    # İSTANBUL   (Türkçe kural)
"IŞIK".lower("tr")        # ışık
```
(Neredeyse bütün dillerde `"istanbul".upper()` "ISTANBUL", `"IŞIK".lower()` "işik" verir; Türkçe kural yoktur
ya da çok uzun yazılır.) Şimdilik Latin harfleri (Türkçe dahil) çevrilir; diğer alfabeler aynen kalır.

| Yazılış | Ne yapar |
|---|---|
| `metin.length` | Harf sayısı (**Türkçe harfler dahil doğru sayılır**: `"çiçek".length` → 5; C/Go/Rust'ta 7 çıkar) |
| `metin[i]` / `metin[a to b]` | Harf / parça |
| `metin.contains("x")` | İçinde geçiyor mu? → bool |
| `metin.starts_with("x")` / `ends_with("x")` | Böyle mi başlıyor / bitiyor? |
| `metin.split(",")` | Parçalara böler → `[text]` |
| `metin.split()` | Kelimelere böler, fazla boşlukları atar |
| `metin.trim()` | Baştaki ve sondaki boşlukları atar |
| `metin.replace("a", "b")` | Her geçtiği yeri değiştirir |
| `metin.upper()` / `lower()` (`"tr"` ile Türkçe) | Büyük / küçük harf |
| `liste.join(", ")` | Listeyi metne birleştirir (**sayı listeleri de olur**). Python'da ters yazılır: `", ".join(liste)` |

- `random(5 to 1)` (alt sınır üstten büyük) ve boş listeden `random` hata verir
- Bu adlar hazır fonksiyon olduğu için aynı adla değişken ya da fonksiyon oluşturulamaz (`print` gibi)
- Metinler değiştirilemez: `trim()` yeni bir metin döndürür, eskisi aynen kalır
- Metinlerde özel yazımlar: `\n` (yeni satır), `\t` (sekme), `\"` (tırnak), `\\` (ters bölü), `\{` `\}` (süslü parantez)
- `{ }` içinde tırnaklı metin yazılabilir: `"Liste: {adlar.join(", ")}"`

### 30. Görsel arayüz: `window` (beraber karar verildi)
**Yol:** Web görünümlü masaüstü penceresi (VS Code ve Discord gibi). Program kendi içinde yerel bir
sunucu açar (sadece bu bilgisayardan erişilebilir). Edge'i adres çubuğu olmadan "uygulama modunda" açar.

```
var sayi = 0
var ad = ""
var onay = false

window "Sayaç" {
    label "Merhaba {ad}! Sayı: {sayi}"        # sayi/ad değişince KENDİLİĞİNDEN güncellenir
    textbox "Adın" -> ad                      # iki yönlü bağ
    checkbox "Kabul ediyorum" -> onay
    row {                                     # yan yana diz
        button "Artır" { sayi = sayi + 1 }
        button "Sıfırla" { sayi = 0 }
    }
}
print("Pencere kapandı")                       # pencere kapanınca program buradan devam eder
```

| Karar | Seçilen |
|---|---|
| Yazılış | **Blok yapısı**: ekranın şekli koddan görünür |
| Güncelleme | **Kendiliğinden**: ekranı güncelleyen kod hiç yazılmaz |
| Giriş kutuları | **İki yönlü bağ** `->`: tipe göre kutu (int/float → sayı, text → yazı, bool → checkbox) |

**Parçalar:** `label <yazı>`, `button <yazı> { ... }`, `textbox <yazı> -> değişken`,
`checkbox <yazı> -> değişken`, `row { ... }`. Yazı yerine her türlü ifade yazılabilir:
`label sepet_yazisi(adlar)`, `label "Toplam: {toplam(fiyatlar)} TL"`.

**Nasıl kendiliğinden güncelleniyor?** Her olaydan (düğme, kutuya yazma) sonra ekrandaki bütün yazılar
yeniden hesaplanır. Çalışma zamanı bunları bir öncekiyle karşılaştırır ve pencereye **sadece değişenleri**
gönderir. Programcı hiçbir şey yazmaz.

**Kurallar:**
- `window` şimdilik sadece ana programın en dışında olabilir ve programda tek pencere olabilir.
- Düğmenin bloğu ana programın bir parçası gibi çalışır: değişkenleri görür ve değiştirir; `when`'ler tetiklenir.
- Sayı kutusuna sayı olmayan bir şey yazılırsa (ör. `12a`) değişken değişmez.
- Pencere kapanınca program `window` bloğundan sonrasına devam eder. Yeniden yüklemek (F5) programı kapatmaz.
- Kullanıcı hızlı yazarken eski bir cevap kutunun üzerine yazmaz (her kutunun sürüm numarası var).

#### Liste görünümü: `list` (beraber karar verildi: şablonlu + `->` ile seçim)
```
var sepet: [Kalem] = []
var secili = 0                                  # 0 = seçim yok

list kalem, i in sepet -> secili {              # her eleman için bir satır
    label "{i}. {kalem.ad}"                     # satırın şablonu
    label "{kalem.tutar()} TL"
    button "Sil" { sepet.remove(i) }            # düğme, kendi satırının elemanıyla çalışır
}
```
- `list eleman[, sıra] in liste [-> secili] { şablon }`. Sıra numarasının adı (`i`) isteğe bağlı.
- Liste değişince satırlar **kendiliğinden** eklenir/silinir/güncellenir.
- Satıra tıklayınca seçilir; seçilen sıra `->` ile bir int değişkene iki yönlü bağlıdır (programdan `secili = 0` yazınca seçim kalkar).
- `kalem` ve `i` sadece okunur. Listeyi değiştirmek için listenin kendisi kullanılır (`sepet.remove(i)`, `sepet[i] = ...`).
- Şablona şimdilik `label`, `button`, `row` konabilir (textbox/checkbox/iç içe list yok).
- Satırdaki düğmeye basıldığında o satır bu arada silinmişse (eski bir tıklama), düğme hiçbir şey yapmaz.

**Henüz yok:** tablo (sütun başlıklı), birden çok pencere, resim, renk ve stil seçimi, menüler,
zamanlayıcı (her saniye güncelleme), fonksiyon içinde pencere.

### 31. Sözlükler (beraber karar verildi: süslü parantez)
```
var notlar = {"Ali": 90, "Ayşe": 85}        # tip: {text: int}
var bos: {text: int} = {}                   # boşsa tip yazılır
notlar["Zeynep"] = 70                       # ekle / değiştir
print(notlar["Ali"])                        # yoksa ÇALIŞMA HATASI (anahtar yok)
print(notlar.get("Can", else: 0))           # yoksa yedek
notlar.has("Ayşe")   notlar.remove("Ali")   notlar.length   notlar.keys()   notlar.values()
```
- Anahtar şimdilik `text` ya da `int`; değer her şey olabilir (liste, sözlük, kendi tip...).
- `keys()` **eklenme sırasını korur** (Python gibi). Hash tablosu: okuma/yazma tek adım.
- Listeler gibi **her değer ayrı** (kopyala-yaz) ve sayaçlı.
- Listeler, sözlükler ve fonksiyon çağrıları artık **birden çok satıra** yazılabilir.

### 32. `enum` ve `match` (beraber karar verildi)
```
enum Odeme {
    Nakit
    Kart(no: text, taksit: int)
    Havale(iban: text)
}
var o = Odeme.Kart(no: "1234", taksit: 3)
match o {
    Nakit { ... }
    Kart(no, taksit) { ... }                  # alanlara ad verilir (sadece okunur)
    else { ... }                              # geri kalan çeşitler (isteğe bağlı)
}
```
- Bir çeşit unutulursa ve `else` yoksa **derlerken hata** (hangi çeşitlerin eksik olduğu yazılır).
- Enum kendine işaret edebilir: `Topla(sol: Hesap, sag: Hesap)` → ağaçlar (derleyicinin düğümleri böyle olacak).
- Her durumu `return` ile biten bir match, fonksiyonun "her yolda döner" kuralını karşılar.
- Alanlara `o.no` diye erişilmez; `match` ile okunur. Enum'lar `is` ile karşılaştırılmaz.

### 33. Yok olabilen değer: `T?` ve `none` (beraber karar verildi: kontrol zorunlu)
```
fn bul(ad: text) -> Ogrenci? { ... return none }
var o = bul("Ali")
print(o.ad)                     # DERLEME HATASI: 'o' yok olabilir, önce kontrol et
if o is not none { print(o.ad) }        # burada güvenli
if o is none { return }                 # erken çıkış: bu satırdan sonra o kesin var
repeat while o is not none { ... }      # döngüde de
var ad = (bul("Can") else: bilinmeyen).ad      # yedekle oku
```
- "Null hatası" çalışırken **hiç** olmaz; derleyici kontrol edilmemiş kullanımı yakalar.
- Kontrolden sonra değişkene yeniden none olabilecek bir değer atanırsa kontrol düşer (tekrar gerekir).
- Şimdilik metin, liste, sözlük, kendi tipler ve enum'lar için (bellekte adres olanlar; "yok" = boş adres,
  ek maliyet sıfır). `int?` / `float?` / `bool?` henüz yok.
- `print` yok olabilen değeri yazabilir (`none` yazar).

### 34. C kütüphanelerini kullanmak: `extern` (beraber karar verildi: kütüphane bloğu, normal çağrı)
```
extern "msvcrt" {
    fn sqrt(x: float) -> float
    fn fopen(ad: text, kip: text) -> ptr
    fn fputs(yazi: text, dosya: ptr) -> i32
}
print(sqrt(16.0))                    # Vash fonksiyonu gibi çağrılır
```
- Tırnak içindeki ad, fonksiyonun bulunduğu kütüphane (`msvcrt` C'nin temeli, `kernel32`/`user32` Windows'unki...).
- Kullanılabilen tipler: `int`, `float`, `bool`, `text`, ayrıca sadece burada anlamlı iki tip:
  `i32` (C'nin küçük tam sayısı; Vash'ta normal int gibi görünür) ve `ptr` (C'nin verdiği bir "tutamaç",
  ör. açık bir dosya; içine bakılmaz, saklanır ve geri verilir; `none` olabilir).
- C'den gelen metin Vash metnine kopyalanır.
- C kodu Vash'ın korumalarının dışında çalışır; yanlış kullanılırsa program kapanabilir.
- Kütüphane ya da fonksiyon bulunamazsa derlerken anlaşılır bir hata verilir.
- **Henüz yok:** C'nin bir "kaba" yazmasını isteyen fonksiyonlar (ör. dosyadan okuma). Bunun için
  Vash'a bayt kabı eklenmesi gerekecek.

### 35. İzinler: kod dış dünyanın neresine dokunuyor? (beraber karar verildi: şimdi, sabit liste)
```
extern "msvcrt" needs files {                 # bu C fonksiyonları dosyalara dokunuyor
    fn fopen(ad: text, kip: text) -> ptr
}
fn kaydet(not: text) {
    use files                                 # yazmazsan DERLEME HATASI
    var f = fopen("notlar.txt", "a")
}
fn rapor() {
    use files                                 # kaydet'i çağırdığı için bu da yazmak zorunda
    kaydet("bitti")
}
```
- İzinler sabit bir liste: `files` (dosya), `net` (internet), `system` (program çalıştırma, sistem bilgisi),
  `screen` (pencere/grafik), `sound` (ses), `time` (saat, bekleme). Saf hesaplar (ör. `sqrt`) izin istemez.
- **Dolaylı çağrılar da sayılır:** A, dosyaya dokunan B'yi çağırıyorsa A da `use files` yazar. Böylece
  bir fonksiyonun başındaki `use` satırları, onun (ve çağırdığı her şeyin) dokunabileceği her yeri gösterir.
- **Ana program her şeye izinlidir** (programın sahibi odur). Pencere düğmeleri ve ana programdaki `when`'ler de.
- Neden: yapay zekânın (ya da bir kütüphanenin) yazdığı kod, neye dokunduğunu gizleyemez; derleyici garanti eder.
- **Henüz açık:** bir fonksiyonun içinden tetiklenen küresel `when`'in izinleri ayrıca kontrol edilmiyor.

### 36. Modüller: kodu birden çok dosyaya bölmek (beraber karar verildi)
```
# geometri.vash                              # ana.vash
global var PI = 3.14159                      import geometri
type Nokta { x: float   y: float }
fn alan(r: float) -> float { ... }           print(geometri.alan(2.0))
fn _kare(x: float) -> float { ... }          var n = geometri.Nokta(x: 1.0, y: 2.0)
                                             var d = geometri.Sekil.Daire(...)
```
- `import geometri` → aynı klasördeki `geometri.vash`. Sadece dosyanın en dışında yazılır.
- **Hep dosya adıyla kullanılır:** `geometri.alan(...)`, `geometri.Nokta`, `geometri.PI`. Neyin nereden geldiği
  her zaman görünür; iki dosyada aynı ad olsa da karışmaz.
- **`_` ile başlayan adlar gizlidir:** sadece kendi dosyasında kullanılabilir. extern'de de geçerli:
  `fn _sqrt(...)` gizlidir ve C'deki adı `sqrt`'tir (C adı gerçekten `_` ile başlıyorsa iki tane yazılır: `__getch`).
  Böylece bir kütüphane ham C fonksiyonlarını gizleyip sadece güvenli Vash fonksiyonlarını gösterebilir.
- **İçe alınan dosyada sadece tanımlar olur:** fn, type, enum, extern, global var, import. print/var/if gibi
  çalışan kod olamaz → içe almak hiçbir şeyi gizlice çalıştıramaz.
- Başka bir dosyanın değişkeni dışarıdan değiştirilemez (`geometri.PI = 3` hata).
- Modüller birbirini içe alabilir; izinler (`use files`) dosyalar arasında da geçerli.
- Hata başka dosyadaysa mesaj dosyanın adıyla başlar: `geometri.vash, Satır 5: ...`
- **Henüz yok:** alt klasörler (`import oyun.grafik`), standart kütüphane klasörü, bir şeyi kısa adıyla çekmek.

### 37. Dosyalar (beraber karar verildi: hazır fonksiyonlar, sorun olursa none)
```
var metin = read_file("notlar.txt")         # text?   okunamazsa none
var satirlar = read_lines("liste.txt")      # [text]? okunamazsa none
write_file("sonuc.txt", "Merhaba\n")        # bool: oldu mu?
append_file("gunluk.txt", "yeni satır\n")   # bool: sonuna ekler
file_exists("ayar.txt")                     # bool
```
- Fonksiyon içinde kullanılınca `use files` izni gerekir (ana program her şeye izinli).
- Okunamayan dosya `none` döner; Vash kontrol etmeyi unutturmaz. Kısa yol: `read_file("x.txt") else: ""`.
- Türkçe harfli dosya adları çalışır (`öğrenci_notları.txt`).
- Okurken baştaki görünmez BOM işareti atılır, Windows satır sonları (`\r\n`) `\n` yapılır.
- Bayt kabı (C'nin dosya fonksiyonlarıyla alt seviye çalışmak) ileride, çalışma zamanını Vash'a taşırken eklenecek.
- **Açık soru:** `time()`, `random` ve `measure` da dış dünyaya dokunuyor (saat). Bunlar da `use time` istemeli mi?

### 38. Harflerle çalışmak (beraber karar verildi: metin işleri + code/char)
```
"7".is_digit()      # true   bütün harfleri rakam mı?
"ç".is_letter()     # true   bütün harfleri harf mi? (Türkçe, Yunan, Kiril, Çince... dahil)
" ".is_space()      # true   bütün harfleri boşluk mu?
code("A")           # 65     harfin numarası
char(65)            # "A"    numaradan harf
```
- Boş metin için `is_...` hep `false` döner. `code("")` ve geçersiz bir `char(...)` çalışma hatası verir.

### 39. Ajanlar için: `vash check --json` ve `VASH_SPEC.md`
```
vash check dosya.vash          # sadece kontrol (hiçbir şey üretmez)
vash check --json dosya.vash   # {"ok": false, "errors": [{"stage", "file", "line", "column", "message", "details", "suggestion"}]}
```
- Çıkış kodu: 0 = hatasız, 1 = hata. Derleyici ilk hatada durduğu için `errors` en fazla 1 eleman içerir.
- JSON alan adları İngilizce (ajanların ve ileride VS Code eklentisinin standart beklediği biçim); mesajlar Türkçe.
- `VASH_SPEC.md`: dilin tek sayfalık tarifi. İçindeki her `vash` örneği `python vashc/spec_dene.py` ile derlenerek sınanır;
  dil değişince belge eskimez.

### 40. Bellek: `arena { }` bloğu (beraber karar verildi: blok, dışarı kaçan otomatik kopyalanır)
```
repeat kare from 1 to 1000 {
    arena {                              # bu bloktaki geçici her şey blok bitince tek hamlede silinir
        var parcalar = hesapla(kare)     # bloğun içinde kalan: arenada
        sonuc = "kare {kare}"            # dışarıdaki değişkene giden: kendiliğinden kopyalanır
    }
}
```
- Bloğun içinde oluşan metin/liste/nesne/sözlükler büyük bir bellek parçasından **sırayla kesilir** (yer aramak yok),
  tek tek geri verilmez; blok bitince parça toplu boşalır ve sonraki blokta yeniden kullanılır. Oyun karesi için ideal.
- **Güvenli:** dışarıdaki bir değişkene, globale, dışarıdaki bir listeye/sözlüğe/nesneye konan değer normal belleğe
  kopyalanır. Programcının bir şey yapması gerekmez, yanlış kullanmak mümkün değil.
- Bloğun içinde `return` ve dışarıdaki bir döngüye `stop`/`skip` yazılamaz. İç içe arena olabilir.
- `arena` bağlamsal kelime: `arena {` ile başlamıyorsa değişken adı olabilir.
- Ölçüm (her karede 200 nesne + metinler, 2000 kare): arena ile ~159 ms, arenasız ~201 ms (~%20 hızlı).
- Test: `python test/arena/arena_dene.py` (her program arenalı ve arenasız çalıştırılıp çıktılar ve bellek karşılaştırılır).
- Not: liste/sözlük elemanlarının dizileri hâlâ normal bellekte (sadece başlıkları arenada); ileride onlar da taşınabilir.

### 41. `weak` (zayıf referans): şimdilik yok (beraber karar verildi)
Vash'ta nesneler kopya gibi davrandığı için iki nesne birbirini tutamaz, sayaç sızıntısı oluşmaz; `weak`'e gerek yok.
Oyunda nesneler birbirini **numarayla** gösterir (ör. `hedef_no: int`), büyük oyun motorlarındaki gibi.
İleride "paylaşılan nesne" türü eklenirse `weak` o zaman tekrar konuşulur.

### 42. Yeni özellikler sadece Vash derleyicisine eklenir (beraber karar verildi)
Python derleyicisi (`derleyici/`) olduğu gibi kalır; sadece Vash derleyicisinin ilk kopyasını üretmek için kullanılır.
İlk yeni özellik `arena` (madde 40). Python'la karşılaştırma testleri, yeni özellik kullanmayan programlar için geçerli.
Atölyenin içeriden görünüm sekmeleri (Python) yeni özellikli programlarda boş kalabilir; derleme/çalıştırma etkilenmez.

### 43. Çok çekirdek: `parallel` (beraber karar verildi: iki biçim, turlar sadece kendi sırasına yazar)
```
parallel {                                   # her komut ayrı bir çekirdekte, aynı anda
    var a = fizik_hesapla()                  # 'var' ile oluşan bloktan sonra da kullanılır
    var b = yapay_zeka_guncelle()
}
parallel repeat i from 1 to dusmanlar.length {   # turlar çekirdeklere bölünür
    dusmanlar[i] = guncelle(dusmanlar[i])        # her tur SADECE kendi sırasına yazar
}
```
- **Veri yarışı derleme hatasıdır.** Derleyici her işin okuduğu/değiştirdiği değişkenleri bulur; çağrılan fonksiyonların
  (ve onların çağırdıklarının, sonuna kadar) `use` / `use change` bilgisi de sayılır. Kurallar:
  - `parallel { }`: bir değişkeni bir iş değiştiriyorsa başka hiçbir iş ona dokunamaz.
  - `parallel repeat`: turlar dışarıdaki hiçbir değişkeni değiştiremez; tek istisna bir listenin kendi elemanı `l[i] = ...`.
    O liste turda sadece `l[i]` (ve `l.length`) olarak okunabilir. Değiştiren fonksiyon çağrılamaz. Okumak serbest.
  - İçinde `return` yok; dışarıdaki döngüye `stop`/`skip` yok; `parallel repeat` içinde `stop`/`skip` yok, `step` yok (şimdilik).
  - Bir `when`'in izlediği değişken paralel bölümde değiştirilemez.
  Rust bu güvenliği zor sahiplik kurallarıyla sağlıyor; Vash basit `use` kuralıyla.
- `parallel` bağlamsal kelime (değişken adı olabilir). `print` satırları birbirine karışmaz.
- **Nasıl çalışıyor:** her iş ayrı bir fonksiyona çevrilir; kullandığı dışarıdaki değişkenlerin adresleri küçük bir diziyle verilir.
  Çalışma zamanında **kalıcı bir işçi takımı** var (çekirdek sayısı kadar, bir kere oluşturulur, sonra iş bekler).
  Paralel çalışırken sayaçlar "bölünmez" (atomic) işlemlerle değişir ve her çekirdek kendi raflarını/arenasını kullanır;
  paralel bir şey çalışmıyorken her şey eskisi gibi düz ve hızlıdır.
- **Ölçümler (16 çekirdek):** asal sayı sayma paralel 24–28 ms, sırayla 131–136 ms (~5 kat). Bir `parallel` çağrısının
  kendi maliyeti ~28 mikrosaniye (oyun karesinde rahatça kullanılır). Paralel kullanmayan programlar yavaşlamadı
  (ölçüldü: önce %5–13 yavaşlama görüldü, çekirdeğe özel belleğe her erişimin maliyetinden; "iki mod" ile giderildi).
- Test: `vash run test/paralel/dogruluk.vash` (20 tur × 20.000 eleman, ortak metinler; sonuç ve bellek kontrolü),
  `test/paralel/kare_maliyeti.vash`.
- **Henüz yok:** `step`'li paralel döngü (toplama madde 47'de yapıldı), paralel içinde paralel
  (şimdilik içteki sırayla çalışır).

### 44. Modüller başka dosyanın adlarını göremez (hata düzeltmesi)
Bir modülün içindeki kod sadece kendi adlarını ve içe aldığı modülleri görür; ana dosyanın fonksiyonlarını göremez,
çağıramaz. (Eskiden ana dosyada `kontrol` adlı bir fonksiyon, bir modülün içinde `kontrol` adlı değişkeni engelliyordu.)
Not: Bu düzeltme Vash derleyicisinde; Python derleyicisi dondurulduğu için `vashc/` içindeki derleyici kodu (Python'la ilk
kopyası üretildiği için) hâlâ bu çakışmadan kaçınacak şekilde yazılmalı.

### 45. C yapıları ve grafik (beraber karar verildi: extern'de yapı + sade bir `grafik` modülü)
```
extern "raylib" needs screen {
    type Renk {                      # C'nin yapısı: alanların C'deki tipleri yazılır
        r: u8
        g: u8
        b: u8
        a: u8 = 255
    }
    fn _DrawCircle(x: i32, y: i32, yaricap: f32, renk: Renk)
    fn _GetMousePosition() -> Konum  # yapı dönen fonksiyon
}
var kirmizi = Renk(r: 230, g: 41, b: 55)     # Vash'ta normal bir tip gibi
```
- `extern` içinde `type` ile **C yapısı** tanımlanır; Vash'ta normal tip gibi oluşturulur, yazdırılır, saklanır.
  Alanlar: `int` (8 bayt), `i32`, `u8` (bayt), `bool` (1 bayt), `float` (8 bayt), `f32` (C'nin 4 baytlık float'ı).
  Metot olamaz. C fonksiyonlarına değer olarak verilir/alınır: derleyici C'nin bellek düzenine (hizalama dahil)
  çevirir; Windows kuralına göre 1/2/4/8 baytlık yapılar yazmaçta, daha büyükleri adresle gider/gelir.
- Yeni C tipleri (sadece `extern`'de, Vash'ta `int`/`float` görünür): `u8` (0–255) ve `f32`.
- Kütüphane `kutuphaneler/<ad>/lib/lib<ad>.a` olarak duruyorsa `vash` onu kendisi bulup bağlar.
- **`grafik` modülü** (`ornekler/grafik.vash`, altında Raylib 6.2): `grafik.pencere(g, y, "başlık")`, `grafik.acik()`,
  `grafik.ciz_basla(renk)` / `ciz_bitir()`, `daire`, `dikdortgen`, `yazi`, `yazi_genisligi`, `kare_suresi`, `fps`,
  `tus_basili(grafik.TUS_SAG)`, `fare()`, `fare_basili()`, `ekran_goruntusu(dosya)`, `kapat()`, hazır renkler
  (`grafik.SARI`, `KOYU_MAVI`...). Ham Raylib fonksiyonları `_` ile gizli.
- Örnekler: `ornekler/grafik_dene.vash` (90 kare çizip kapanır, ekran görüntüsü alır), `ornekler/parcaciklar.vash`
  (20.000 parçacık `parallel repeat` ile hareket eder, çizim `arena` içinde; ok tuşlarıyla oynanır): **~57–60 FPS**.
  Not: Raylib küçük daireleri 36 üçgenle çiziyor; 20.000 dairede 33 FPS'e düşüyordu, küçük karelerle (2 üçgen) 60.
- Raylib'in varsayılan yazı tipinde Türkçe harfler (ç, ş, ı...) yok; pencere yazılarında şimdilik görünmez.
- `vash run` artık programı tam yoluyla başlatıyor (Windows bazı ortamlarda bulunduğu klasöre bakmıyor).
- **Henüz yok:** 3B çizim, resim/ses yükleme, Türkçe yazı tipi, standart kütüphane klasörü (`grafik.vash` şimdilik
  `ornekler/` içinde; kullanan dosyanın yanında olmalı).

### 46. Standart kütüphane ve hazır araçlar (beraber karar verildi: İngilizce adlar)
- Hazır modüller `std/` klasöründe; `import csv` önce dosyanın yanına, sonra `std/`'ye bakar.
- `args()`: komut satırından verilenler (`[text]`, program adı hariç).
- `liste.sort()` (int/float/text/bool) ve `liste.sort(by: once_mi)`; kararlı (eşitlerin sırası korunur) birleştirmeli sıralama.
- Düzenli ifadeler metnin işleri olarak: `matches` (metnin tamamı), `find` (→ `text?`), `find_all`, `replace_pattern`.
  Motor Vash ile yazıldı (`std/regex.vash`, Pike VM: kötü desenlerde bile donmaz). Yazıyla verilen desen bir kere çözülür.
- `csv` (`parse`, `parse_records`, `stringify`; tırnaklı hücreler) ve `json` (`parse`, `stringify`, `pretty`, `get`, `at`, `as_*`).
- `grafik` → `graphics` (İngilizce adlar: `open_window`, `begin_drawing`, `draw_circle` ...).

### 47. Paralel döngüde toplama (beraber karar verildi: kendiliğinden)
- `parallel repeat` içinde `toplam = toplam + x` (ayrıca `-`, `*`, `x + toplam`) ve dizide `sayilar[k] = sayilar[k] + 1`
  kendiliğinden çekirdeklere bölünür: her çekirdek kendi ara sonucunu (0 ya da 1'den başlayarak) tutar, döngü bitince
  ara sonuçlar sırayla asıl değişkene eklenir. Programcı hiçbir şey yazmaz.
- Kurallar (derleyici kontrol eder): toplanan değişken döngüde başka yerde okunamaz/yazılamaz; aynı değişken hem `+` hem `*`
  ile birleştirilemez; çağrılan fonksiyonlar onu okuyamaz; `when`'in izlediği değişken toplanamaz.
- Tam sayılarda birleştirirken de taşma kontrol edilir. Ondalıklı sayılarda toplama sırası değiştiği için son basamak farklı olabilir.
- Ölçüm: 2 milyar turluk toplam tek çekirdekte 0,97 sn, `parallel repeat` ile 0,32 sn (16 çekirdek, ~3 kat).
- Test: `test/paralel_toplama/`.

### 48. İkili veriler: `bytes` (beraber karar verildi: yeni tip, read_bytes / write_bytes)
- Yeni tip `bytes`: her bayt 1 yer kaplar (C kadar az bellek). Değer anlamlı ve kopyala-yazlı (listeler gibi).
- `read_bytes(yol) -> bytes?`, `write_bytes(yol, b) -> bool` (`use files` ister), `bytes(n)` (n sıfır bayt),
  `b[i]` (0–255, 1'den başlar), `b[i] = x` (0–255 dışı çalışma hatası), `b.length`, `b.add(x)`, `b[a to b]`,
  `"yazı".to_bytes()`, `b.to_text()` (geçersiz UTF-8 baytları `?` olur),
  `b.get_int(sira, boyut)` / `b.add_int(sayi, boyut)`: 1/2/4/8 baytlık sayılar, küçük uçtan (dosyaların çoğu böyle).
- Çalışma zamanında liste yapısını kullanır (tür = bytes, veri bayt bayt), böylece sayaç, kopyala-yaz, arena ve
  listelerin/nesnelerin içinde durmak ek iş gerektirmedi. `is` ile karşılaştırılamaz, `parallel repeat`'te yazılamaz.
- Test: `test/bytes/`.

### 49. İç içe değiştirme (`a[i].b = x`, `m[i][j] = x`, `s["k"].add(x)`)
- Bir değişkenin içindeki liste, sözlük ya da nesne doğrudan değiştirilebilir: eleman atama, alan atama, `add/remove/sort`,
  `change` metotlar, `bytes` işleri. Değer anlamı korunur: `var eski = a` yapıldıysa `eski` değişmez.
- Nasıl: yolun her adımında kap "kendine ait" yapılır; sadece başkasıyla paylaşılan parça kopyalanır.
  1000×1000 matrise `b[i][j] = x` yazmak hiç kopya yapmadan çalışır.
- Kural: kökte bir değişken olmalı ve o değişken değiştirilebilir olmalı (`use change`, sayaç değil ...).
  Geçici bir değerin ya da `a[2 to 4]` parçasının içi değiştirilemez. `parallel repeat`'te iç içe yazma şimdilik yok.
- Test: `test/ic_ice/`.

### 50. C ile hız karşılaştırması
- `olcum/c_karsilastirma/` (sonuçlar `SONUC.md`): Mandelbrot (%40) ve sıralamada (%45) Vash daha hızlı, 2 milyar turluk döngüde
  C %13 önde (taşma kontrolleri), `[bool]` ile asal eleğinde C %32 önde (0,33 sn / 0,25 sn).

### 51. `[bool]` listelerinde her eleman 1 bayt
- Önceden bütün listeler her elemana 8 bayt ayırıyordu; `[bool]` artık C'deki gibi 1 bayt kullanıyor (8 kat az bellek).
  Dilde hiçbir şey değişmedi, sadece bellekteki düzen. Asal eleği 1,14 sn → 0,35 sn (aynı ölçümde C 0,26 sn).
- Derleyici liste tipini bildiği için okuma/yazmayı doğrudan 1 baytlık yere yapar; çalışma kütüphanesinde `veri_al` / `veri_koy`.
- Derleyici kendini ilk kez Python derleyicisiyle kurduğu (ve kendisi `[bool]` kullandığı) için aynı değişiklik
  `derleyici/llvm_uretici.py`'ye de yapıldı (yeni özellik değil, ortak bellek düzeni).
- Test: `test/bool_liste/`.

### 52. HTTP: istemci ve sunucu (beraber karar verildi: sunucu döngüyle)
- `std/http.vash` (Vash ile yazıldı) + çalışma kütüphanesinde WinHTTP (istemci) ve Winsock (sunucu).
- İstemci: `http.get(url)`, `http.post(url, govde, tip)`, `http.request(yontem, url, govde, basliklar)` → `Response?`
  (`status`, `body`, `headers`); olmazsa none, nedeni `http.error()`. HTTPS dahil.
- Sunucu döngüyle: `var sunucu = http.listen(8080)`, `var istek = sunucu.next()`, `istek.reply(200, govde)`.
  Bağlantılar arka planda (her biri ayrı iş parçacığında, sadece C belleğiyle) kabul edilip okunur ve sıraya girer;
  istekler ana programda sırayla işlenir → ana programın değişkenleri `use change` olmadan, veri yarışı olmadan kullanılır.
- İstek ve sunucular numarayla tutulur: aynı isteğe iki kez cevap vermek programı bozamaz (ikincisi false döner).
- Gövde `{`/`[` ile başlıyorsa Content-Type kendiliğinden JSON olur. kalıcı bağlantı: madde 54.
- Ölçüm: tek tek isteklerde istek başına ~0,2–0,5 ms; 500 istemci aynı anda: 500/500 başarılı (Python'un hazır sunucusuyla aynı sürede).
- Test: `test/http/` (sunucu.vash + istemci.vash, tek_program.vash).

### 53. Arka planda iş: `start` / `wait` (beraber karar verildi: sadece sonuç döndürür, tip task[T])
- `var gorev = start f(a, b)` → iş hemen ayrı bir iş parçacığında başlar; `gorev.wait()` bitmesini bekler ve sonucu verir; `gorev.done()`.
- Tip `task[T]` (yazmak çoğu zaman gerekmez): `var isler: [task[text]] = []`. Değer döndürmeyen iş: `task[]` (beraber karar verildi).
- Güvenlik (derleme hatası): başlatılan fonksiyon (çağırdıklarıyla) dışarıdaki bir değişkeni değiştiremez ve programda
  değişen bir değişkeni okuyamaz; değerleri parametreyle alır (iş kendi kopyasıyla çalışır), sonucunu döndürür.
  Sadece Vash fonksiyonları başlatılabilir (hazır işler, metotlar, C fonksiyonları değil). `arena` içinde yazılamaz.
- Çalışma zamanında iş numarayla tutulur; ikinci `wait` anlaşılır bir çalışma hatası verir.
- İş çalışırken sayaçlar bölünmez işlemlerle değişir; işin kendi rafları/arenası olur. Bunun için "paralel mi" bayrağı ikiye
  ayrıldı: sayaçlar için genel (`paralel_aktif`), raf/arena için iş parçacığının kendi bayrağı (`arka_plan_isi`),
  böylece ana program bir iş çalışırken de kendi hızlı yolunda ve `parallel` bloklarını kullanabilir.
- `start` bir anahtar kelime değil: sadece `start ad(` ya da `start modul.ad(` biçiminde iş başlatır (`start` değişken adı olabilir).
- Test: `test/arka_plan/`.

### 54. Kalıcı bağlantı (keep-alive) ve HTTPS sunucusu (beraber karar verildi: listen_secure)
- Bağlantı cevaptan sonra açık kalır (HTTP/1.1'de istemci `Connection: close` demedikçe); yeni bir okuyucu aynı bağlantıdan
  sıradaki isteği bekler, 15 sn ses gelmezse kapatır. Küçük paketler beklemeden gider (TCP_NODELAY).
  Ölçüm: tek bağlantıdan 1000 istek 0,09 sn; her biri yeni bağlantıyla 0,29 sn.
- `http.listen_secure(8443, "sertifika.pfx", "parola")`: TLS Windows SChannel ile (ek kütüphane yok). Sertifika `""` ise deneme
  için `localhost` adına kendi imzalı sertifika üretilir. Windows, HTTPS anahtarının kullanıcının anahtar deposunda durmasını
  istediği için anahtar program çalışırken oraya konur, program biterken silinir (bilgisayarda iz kalmaz; denendi).
- Denendi: deneme sertifikası ve .pfx dosyası (TLS 1.2), yanlış parola anlaşılır hata verir. Test: `test/http/guvenli.vash`, `pfx_sunucu.vash`.

### 55. İşler arasında mesajlaşma: `channel[T]` (beraber karar verildi: channel, receive → T?)
- `var kanal = channel[text]()` · `kanal.send(x)` · `kanal.receive()` (gelene kadar bekler) · `kanal.try_receive()` (beklemez) · `kanal.close()`.
- Kanal kapanıp boşalınca `receive()` none döner (`T?`). `int?` olmadığı için sayı/bool kanallarında yedek değer şart:
  `kanal.receive(else: -1)` (`int("...", else: 0)` ve `get(k, else: v)` ile aynı kalıp).
- Mesaj değer olarak gider (kopya gibi; arenadaysa normal belleğe kopyalanır), sıra korunur. Kanal numarayla tutulur;
  `start`'a parametre olarak verilir. Kapalı kanala `send` çalışma hatası.
- Test: `test/kanal/` (üretici-tüketici, işçi hattı, 4 işçinin aynı kanaldan iş alması).

### 56. Gerçek internet denemesi
- `test/internet/internet.vash`: example.com, httpbin.org, google.com (HTTPS ve HTTP), olmayan alan adı (anlaşılır hata),
  Türkçe harfli JSON POST. Hepsi doğru; 5 istek `start` ile aynı anda.

### 57. Hata mesajları iki dilde (beraber karar verildi: ikisi, varsayılan İngilizce)
- Her mesaj iki dilde yazılır: derleyicide `dil.sec("Türkçe", "English")` (`vashc/dil.vash`), çalışma kütüphanesinde
  `MESAJ("Türkçe", "English")`, std modüllerinde kendi küçük yardımcıları, `vash.cmd`'de `if`.
- Dil seçimi: `VASH_DIL=tr|en` ortam değişkeni; yoksa Windows'un arayüz dili Türkçeyse Türkçe, değilse İngilizce.
  `check --json` (ajanlar için) ayar yoksa hep İngilizce. Derlenen programların çalışma hataları da aynı kurala uyar.
- Türkçe metinler birebir korundu: karşılaştırma testleri eski (Python) derleyicinin Türkçe çıktısıyla aynı (derleyici
  ayar verilmezse Türkçe başlar; `vash.vash` dili başta seçer). `--json` iki dildeki "Satır/Line", "sütun/column",
  "Bunu mu demek istedin/Did you mean" biçimlerini de anlar; atölye (`arayuz/sunucu.py`) de.
- Yaklaşık 460 mesaj çevrildi (tipler 313, parser 88, moduller 20, lexer 5, vash 12, uretici 3, oneri 1, calisma.c 67, regex 1).
- Yan bulgu: `vashc/vash.vash`'ın 41 satırında Türkçe harfler iki kez kodlanmıştı ("hazÄ±r"); düzeltildi
  (derleyicinin "✓ ... hazır" ve bazı hata mesajları ekranda bozuk çıkıyordu).

### 58. Hata yakalama (beraber karar verildi: kontrollü hatalar, her çağrıda try, do/catch, hata = metin)
- `fn f(...) -> T fails { ... fail "mesaj" ... }`. Hata verebilen çağrı ya `try f(...)` (hata yukarı ya da en yakın
  `do { } catch hata { }`'e gider) ya da `f(...) else: yedek` ile yazılır; ikisi de yoksa DERLEME hatası.
- `try` ile gelen hata yakalanmıyorsa fonksiyon `fails` olmalı (derleme hatası); ana programda yakalanmazsa program
  "yakalanmayan hata" mesajıyla durur. `parallel`, `arena`, `when` bloklarının ve lambda'ların dışına hata iletilemez.
- Metotlar da `fails` olabilir (`fn change cek(m: int) fails`). `fails` fonksiyon şimdilik `start` ile başlatılamaz, değer olarak verilemez.
- Nasıl: hata iş parçacığına özel bir yerde bekler (`hata_koy`/`hata_al`); hata verebilen her çağrıdan sonra bakılır.
  Bloklar değişkenlerini fonksiyon sonunda bıraktığı için catch'e atlamak basit bir atlamadır. Normal yolda bellek sızıntısı yok.
- Test: `test/hata/`.

### 59. Generic (beraber karar verildi: köşeli parantez)
- `fn ilk[T](l: [T]) -> T`, birden çok: `fn ciftle[A, B](...)`. `type Kutu[T] { deger: T }`, kullanım `Kutu[int]`.
- Tipler çağrıdaki değerlerden (ya da beklenen tipten: `var y: Yigin[text] = Yigin()`) anlaşılır.
- Her kullanılan tip için ayrı bir kopya üretilir (`ilk[int]`, `Kutu[text]`): hız normal fonksiyonla aynı. Kopyada çıkan hata
  hangi tip için olduğunu söyler. Generic tiplerin metotları, `fails`'i ve iç içe kullanımı (`fn takas[A, B](c: Cift[A, B]) -> Cift[B, A]`) çalışır.
- Test: `test/generic/`.

### 60. Lambda ve fonksiyon değerleri (beraber karar verildi: fn(a, b) => ifade)
- `fn(a, b) => a + b`, blok: `fn(x: int) -> int { ... }`. Fonksiyon tipi `fn(int, int) -> int`. Adı olan fonksiyon da değer: `uygula(l, kare)`.
- Parametre tipleri beklenen yerden anlaşılır (`liste.sort(by: fn(a, b) => a < b)`); anlaşılamazsa yazılır.
- Dışarıdaki değerlerin KOPYASI yakalanır (sonradan değişse de lambda eski değeri görür); lambda dışarıdakini değiştiremez,
  içinde `use` yazılmaz; izinleri oluşturulduğu yerin izinleridir.
- Çalışma zamanında "kapanış": { sayaç, kod adresi, yakalanan değerler } (`T_KAPANIS`), listelerde/değişkenlerde durabilir.
- Liste işleri (beraber karar: önerilenler): `map`, `filter`, `any`, `all`, `count`, `find` (→ `T?`, sayılarda `else:`), `sort(by: lambda)`.
- Test: `test/lambda/`.

### 61. Bit işlemleri (beraber karar verildi: işaretlerle)
- `& | ^ << >>` sadece `int` ile. Öncelik: `|` < `^` < `&` < `<< >>` < `+ -` (hepsi karşılaştırmadan güçlü).
- Kaydırma 0–63 dışında çalışma hatası (C'deki gibi belirsiz sonuç yok). `bool` ile `&`/`|` hata verir, `and`/`or` önerilir.

### 62. `math` modülü
- C'nin matematik fonksiyonları (msvcrt), `PI/TAU/E`, `clamp/lerp/sign/round`, ve 2B vektör tipi `Vec2` (metotlarıyla).

### 63. Grafik: resim, Türkçe yazı tipi, ses, kamera, arayüz şekilleri
- `graphics` modülü büyüdü: resim (`Texture`), yazı tipi (`Font`, Türkçe harfler `LoadCodepoints` ile yüklenir), ses/müzik (`Sound`, `Music`),
  `Camera2D`, yuvarlak köşeli kutu, kırpma (scissor), geçişli renk, daha çok tuş/fare fonksiyonu, imleç şekli.
- C yapıları düz yazıldı: C'deki iç içe yapılar (Font içindeki Texture, Sound içindeki AudioStream) tek tek alanlara açıldı; gerekirse `padding` alanı eklendi.
- Derleyici: `extern` fonksiyonuna `bytes` verilebilir (verinin adresi gider), C yapısında `ptr` alanı olabilir.
- Hata düzeltmesi: modülde bir parametre aynı dosyadaki bir fonksiyonla aynı adı taşıyınca (ör. `fps`) fonksiyon sanılıyordu; artık yerel değişken seçilir.
- Test: `test/motor_eksik/grafik_yeni.vash` (kendi ürettiği BMP ve WAV'ı yükler, Türkçe yazar, ekran görüntüsü alır).
- Ses fonksiyonları ayrı `sound` iznine alındı (güvenlik kartı ekranı ve sesi ayrı gösterebilsin diye).

### 64. Vash Engine 2D ilk sürüm (beraber karar verildi: üç bölümlü, koyu, Vash ile; davranışlar hem hazır hem kodla)
- `std/engine.vash`: sahne (`Game`), nesne (`Thing`), hazır davranışlar, eksen eksen çarpışma, parçacıklar, paralaks katmanlar,
  ekran sarsıntısı, kamera, JSON kaydet/yükle. Oyun değer anlamlı: `var kopya = oyun` tam bir kopya (oyna/durdur, geri al bedava).
- `vash_engine/duzenleyici.vash`: düzenleyici (sürükle-bırak, boyutlandırma, ızgara, yakınlaştırma, geri al/yinele, davranış kartları,
  renk seçici, resim önizleme, sahne ayarları, içeride oynatma). `vash_engine/arayuz.vash`: anlık (her kare çizilen) arayüz parçaları.
- Örnek oyun "Altın Avcısı" (`vash_engine/ornekler/platform`): piksel sanat görseller ve 8-bit sesler `araclar/piksel_uret.py` ile üretildi.
- Kodla davranış: oyunun `oyna.vash` dosyası normal bir Vash programı; "Kodla çalıştır" onu çalıştırır, "Dışa aktar" .exe yapar.

### 65. Zaman makinesi (geri sarma)
- Oynarken son 10 saniyenin her karesi saklanır (oyun değer anlamlı olduğu için bir kare = oyunun kopyası; değişmeyen parçalar paylaşılır).
- "Geri sar" basılı tutulur ya da zaman çubuğu sürüklenir; duraklatınca bir nesneye tıklayıp o anki değerleri (konum, hız, yerde mi) görülür.
- Geri sarılan andan devam edilince "gelecek" silinir, oyun oradan sürer.

### 66. Güvenlik kartı
- `vash check --json` hatasız programın kullandığı izinleri (`permissions`) ve C kütüphanelerini (`c_libraries`) söyler:
  ana programın her izni var ama ne kullandığı not edilir (çağrılan fonksiyonların izinleri + dosya fonksiyonları).
- "Dışa aktar" sonrası düzenleyici kartı gösterir ve oyunun yanına `GUVENLIK.txt` yazar. Kendi kodu olmayan oyun "sadece hazır davranışlar" diye işaretlenir;
  Vash'ın kendi modülleri dışındaki C kütüphaneleri (ya da oyun klasöründe std modülüyle aynı adlı dosya) sarıyla uyarılır.

### 67. Claude köprüsü (beraber karar verildi: ücretli API yok, bu oturumla MCP üzerinden)
- Düzenleyici `http.listen_local(7377)` ile sadece bu bilgisayara açık bir kapı açar: `/sahne` (oku/yaz), `/ekran`, `/durum`, `/mesaj`, `/sec`, `/oyna`, `/durdur`, `/kaydet`.
- `vash_engine/araclar/vash_mcp.py`: ek kütüphanesiz MCP sunucusu; Claude Code `.mcp.json` ile başlatır. Araçlar: sahne_oku, sahne_yaz,
  ekran_goruntusu, durum, mesaj_goster, sec, oyna, durdur, kaydet, vash_kontrol, vash_tarifi, oyun_kodu_yaz.
- Claude'un her değişikliği düzenleyicide Ctrl+Z ile geri alınabilir. Yeni: `http.listen_local` (calisma.c'de `vash_yerel_sunucu_ac`).


### 68. Sky Forts Mini (beraber karar verildi: izometrik, ilk sürüm sadece üs kurma)
- Yapımcı Claude'un önerisiyle örnek oyun: gökyüzündeki uçan adada izometrik üs kurma (`vash_engine/ornekler/skyforts_mini/oyun.vash`).
- 6 bina × 3 seviye (piksel sanat `araclar/skyforts_uret.py` ile üretilir), metal/yakıt/kristal üretimi ve toplama, depo sınırı, enerji,
  2 inşaatçı, inşaat/yükseltme süreleri, Komuta Merkezi seviyesine bağlı sınırlar, taşıma, ağaç kaldırma, 5 sn'de bir otomatik kayıt.
- Üretim gerçek saate göre hesaplanır (Windows saati, `extern kernel32 needs time`): oyun kapalıyken de üretir, bina kapasitesine kadar.
- Yeni `std/iso.vash`: izometrik ızgara hesapları ve karo çizimi. `--dene` mantığı otomatik sınar, `--demo` hazır üsle açar.
- Sonraki adım (karar bekliyor): savaş, ve Vash'ı Unity'de kullanmak (Vash → C# çevirici ya da DLL).

### 69. Kum havuzu (beraber karar verildi: Claude da kullanıcı da; varsayılan izin yok; 30 sn)
- Vash'ın parladığı yer: yapay zekânın yazdığı programı okumadan güvenle çalıştırmak. `vash kum [--izin a+b] [--klasor k] [--sure s] dosya.vash`.
- Derleyici: kum modunda (`VASH_KUM=1`) izin verilmeyen `use` satırı, ana programdaki izinli çağrı (lambda, `start`, `parallel`,
  `window` dahil) ve kullanıcı dosyasındaki `extern` derleme hatasıdır. Hazır modüller her zaman std klasöründen yüklenir (sahte modül olmaz).
- Çalışma kütüphanesi: `VASH_KUM_KLASOR` varsa dosya fonksiyonları yolu tam yola çevirip klasör dışını reddeder (program durur, çıkış 3).
  `vash_kum_calistir`: program bir Job nesnesinde (1 süreç, 2 GB), süre dolunca durdurulur (çıkış 124).
- `araclar/vash_kum_mcp.py` (`vash-kum`): `vash_calistir`, `vash_denetle`, `vash_tarifi`. Ayrıntı: `KUM_HAVUZU.md`, denemeler `test/kum/`.

### 70. Vash Dedektif (beraber karar verildi: disk dedektifi + Unity röntgeni, pencereli)
- "Kendini belli eden" ilk gerçek uygulama: `uygulamalar/dedektif/`. Disk: çok çekirdekli tarama (iş kanalından iş alan işçiler),
  ağaç haritası (squarified), büyük dosyalar, Unity Library temizliği (Geri Dönüşüm Kutusu'na, onaylı), kopyalar (boyut → baş+son izi → tam iz).
  Unity: varlık türleri, GUID referanslarıyla kullanılmayan varlıklar, telefon uyarıları (doku boyu PNG/PSD/TGA başlığından), script satırları.
- Yeni `std/fs.vash` ve calisma.c'de `vash_klasor_oku` (FindFirstFileExW, büyük getirme), `vash_dosya_ozeti(_hizli)`, `vash_cope_tasi`,
  `vash_disk_bilgi`, `vash_suruculer`, `vash_gezginde_ac` (sadece var olan yollar, explorer üzerinden; komut çalıştırmaz), `vash_dosya_basi`.
  Hepsi kum havuzu klasör sınırına uyar. Dönen yazılar iş parçacığına özel tamponda.
- Ölçüm: 854 bin dosya 20,9 sn (Python os.walk+stat 163,7 sn). Kopya arama 96,6 sn → 0,6 sn (iki adım + çok çekirdek + 8 baytlık iz).

### 71. Hızlandırmalar (C++ ile yarış)
- **Taban sıralaması:** `[int]`/`[float]` listelerinin `sort()`'u 4096 elemandan büyükse radix sort (16 bitlik 4 basamak, kararlı;
  boş basamak turları atlanır; -0.0 = +0.0). 5 milyon sayı: 0,50 → 0,17 sn (`std::sort` 0,26).
- **Paralel sınır bilgisi:** sınırları sabit `parallel repeat`'te iş fonksiyonuna `llvm.assume(bas >= A)`, `llvm.assume(son <= B)`.
  Sayaçla yapılan hesaplardaki taşma kontrolleri silinir: 0,52 → 0,27 sn (`std::thread` 0,32).
- **Döngü öncesi paylaşım kontrolü:** döngüde bir yerel sayı/bool listesine sadece `l[i] = x`, `l[i]`, `l.length` ile dokunuluyorsa
  (başka yere verilmiyor, `add` yok, lambda yok, `when` izlemiyor, paralel paylaşılan değil) `liste_yazilabilir` döngüden önce bir kez
  çağrılır, içeride kontrol yoktur. İki derleyicide aynı (karşılaştırma testleri için; adlar kod sırasına göre sıralanır).
- **Doldurma kalıbı:** `repeat N { l.add(sabit) }` (l yerel `[bool]`/`[int]`, sabit true/false/sayı) → `liste_doldur` (memset).
- **TBAA:** `[bool]` ve `bytes` elemanlarına ayrı etiket (`liste.bayt`): 1 baytlık yazmalar liste başlığını değiştirmiş sayılmaz.
- Bilerek yapılmayanlar: bit bit `[bool]` (paralel yazmalarda veri yarışı olurdu), tam sayı taşma kontrolünü kaldırmak (güvence).
- Test: `test/hizlandirma/hizlandirma.vash`.
## 🛠️ Vash'ı Vash'la yazmak (self-hosting) — ilerleme
Derleyicinin Vash'la yazılmış hâli `vashc/` klasöründe. Her parça, Python'daki karşılığıyla
**birebir aynı sonucu** verdiği kontrol edilerek eklendi (`python vashc/karsilastir_*.py`).

| Parça | Durum |
|---|---|
| 1. Kelimelere ayırıcı (`vashc/lexer.vash`) | ✅ 36/36 dosyada birebir aynı (8.219 token); Python'dan ~2 kat hızlı |
| 2. Ağaç kurucu (`vashc/parser.vash`) | ✅ 48/48 dosyada birebir aynı ağaç (10.164 düğüm, 22 zor/hatalı durum dahil); ~3 kat hızlı |
| 3a. Tip kontrolü, 1. bölüm (`vashc/tipler.vash`): değişkenler, hesaplar, if, döngüler, fonksiyonlar, listeler, sözlükler, metinler, none, hazır fonksiyonlar, izinler | ✅ 42/42 dosyada birebir aynı (25 hatalı kod dahil, "Bunu mu demek istedin?" önerileri de aynı) |
| 3b. Tip kontrolü, 2. bölüm: type, enum/match, when, window, extern | ✅ 72/72 dosyada birebir aynı (örnekler + 53 zor durum) |
| 3c. import: birden çok dosyayı birleştirme (`vashc/moduller.vash`) | ✅ 105/105 dosyada birebir aynı (20 çok dosyalı durum dahil; `vashc/` içindeki derleyici dosyalarının kendisi de) |
| 4. Makine dili üretici, LLVM IR (`vashc/uretici.vash`) | ✅ 107/107 dosyada birebir aynı IR (302.383 satır; `python vashc/karsilastir_uretici.py`) |
| 5. **Kendini derleme** (`python vashc/kendini_derle.py`) | ✅ Vash derleyicisi kendi kaynağını derliyor; 2. ve 3. kuşak birebir aynı IR üretiyor, 3. kuşak da 107/107 testi geçiyor. Python'dan ~2,4 kat hızlı (kendi ~8.000 satırlık kaynağını 0,12 sn'de çeviriyor) |

| 6. **`vash` komutu Vash derleyicisinde** (`vashc/vash.vash`) | ✅ `vash run/build/ir` artık Vash'la yazılmış derleyiciyi kullanıyor; clang'ı çağırma, kütüphane bağlama ve hata mesajları da Vash'ta |

**Durum:** Vash artık kendi kendini derleyebiliyor ve `vash` komutu Vash derleyicisiyle çalışıyor.
- İlk kullanımda `vashc\vash.exe` yoksa Python'daki derleyici onu **bir kere** üretir; sonra Python kullanılmaz.
- `vash yenile`: `vashc/` içindeki derleyici kodu değiştiyse `vash.exe`'yi yeniden üretir.
- `vash py run x.vash`: eski (Python) derleyiciyle çalıştırır (karşılaştırma için).
- Komut satırı bilgileri (`run`, dosya adı) şimdilik `vash.cmd`'den ortam değişkenleriyle geliyor; Vash'ta henüz
  "programa verilen argümanları okuma" özelliği yok (ileride tasarlanabilir).
- Atölye (`arayuz/`) de derlemeyi ve çalıştırmayı Vash derleyicisiyle yapıyor. "Kelimeler / Ağaç / Tipler" sekmelerindeki
  içeriden görünümü ise hâlâ Python istasyonları çiziyor (sadece göstermek için; iki derleyici aynı sonucu veriyor).
- Bilinen eksik: `calisma.c` değişirse `derleyici\calisma_lto.o` silinmeli (Vash'ta dosya tarihini okuma yok).

Ağaç Vash'ta **tek bir düğüm tipiyle** tutuluyor (Python'da 45 sınıf var):
`Dugum { tur, deger, ek, cocuklar: [Dugum], satir, sutun }`. Boş yer için `"Bos"`, liste için `"[]"` düğümü.
Hata olunca ilk mesaj not edilir ve okuma dosyanın sonuna atılır (Vash'ta "fırlatma" yok).

---

## 💡 Kabul edilen fikirler (ilgili özellik tasarlanırken detaylandırılacak)
- `"Merhaba {isim}"`: metnin içine değişken yazmak ✅ (yapıldı)
- **`when`** → ✅ yapıldı, madde 26. (Benzerleri: Svelte `$:`, Swift `didSet`, Godot/Unity sinyalleri, Verilog `always @`.)
- **`parallel` — otomatik çok çekirdek** → ✅ yapıldı, madde 43. (İlk taslak aşağıda.)
  ```
  parallel {
      fizik_hesapla()
      yapay_zeka_guncelle()
  }
  parallel repeat i from 1 to dusmanlar.length { dusman_guncelle(i) }
  ```
  Derleyici `use`/`use change` bilgisiyle veri yarışını **program çalışmadan** yakalar. Kural: bir bloktaki
  işlerden en fazla biri bir değişkeni değiştirebilir; değiştiriyorsa diğerleri onu okuyamaz (dolaylı
  çağrılar dahil). Rust bu güvenliği zor sahiplik kurallarıyla sağlıyor; Vash basit `use` kuralıyla.
  Gerekenler: atomik sayaç, her çekirdeğe ayrı raf, `print` sırası. Ad `split` değil, çünkü `split`
  çoğu dilde "metni böl" demek.

---

## 📜 Değiştirilen kararlar (neden değiştiğini unutmamak için)
- ~~`var n, x = 5` / `var s, x int`~~ → `var x = 5` / `var x: int = 5`
  **Neden:** En sık yapılan iş en uzun yazılış olmuştu. Virgül "iki değişken" gibi okunuyordu.
  Ayrı satırda tip vermek ya gereksizdi ya da hata veriyordu. Boş liste gibi durumlarda da tip verilemiyordu.

---

## ❓ Henüz karar verilmeyenler (sırası gelince konuşacağız)
- Listelerin üzerinde dönmek: `repeat x in liste { }` (listeler tasarlanınca)
- `"{...}"` içine sadece değişken adı mı, yoksa işlem de (`"{x + 1}"`) yazılabilir mi?
- `use` ile çağrılan değişken, fonksiyon ondan önce çalıştırılırsa ne olur? (nadir bir durum, ileride)
- Yorum satırı (şimdilik `#`)
- Değer vermeden değişken oluşturulabilir mi? (`var x: int`)
