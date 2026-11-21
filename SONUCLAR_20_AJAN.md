# 20 ajanın dil sıralaması (güncel Vash ile)

Her ajan yalnızca `DILLER.md` ve Vash kılavuzunu okudu, kod yazmadı ve beş dili 1'den 5'e sıraladı.
Aşağıda her görevin metni ve ajanın cevabı hiç değiştirilmeden yer alıyor.

**Özet:** Vash 20 görevin 10'unda 1., 6'sında 2., 2'sinde 3., 2'sinde 4. sırada. Ortalama sırası 1,8 (önceki deneyde 2,1).
1. sıradakiler: Vash 10 · Python 4 · C/C++ 3 · Java 2 · JavaScript 1.

| # | Görev | Vash | 1. sıradaki |
|---|---|---|---|
| 1 | Kelime sayma | 1 | Vash |
| 2 | Yapılacaklar listesi | 2 | Python |
| 3 | Hızlı asal sayma | 2 | C/C++ |
| 4 | Masaüstü hesap makinesi | 1 | Vash |
| 5 | CSV not raporu | 2 | Python |
| 6 | REST API sunucusu | 2 | JavaScript |
| 7 | Görüntü işleme | 1 | Vash |
| 8 | 2B aksiyon oyunu | 1 | Vash |
| 9 | Betik dili yorumlayıcısı | 1 | Vash |
| 10 | Anahtar-değer veritabanı | 3 | Java |
| 11 | Sohbet sunucusu | 4 | Java |
| 12 | N-cisim simülasyonu | 1 | Vash |
| 13 | Web tarayıcısı (crawler) | 1 | Vash |
| 14 | 10 GB günlük analizi | 1 | Vash |
| 15 | Fatura programı | 2 | Python |
| 16 | Ses işleme | 1 | Vash |
| 17 | Yapay sinir ağı | 1 | Vash |
| 18 | Dosya sıkıştırma | 2 | C/C++ |
| 19 | Satranç motoru | 3 | C/C++ |
| 20 | Dosya düzenleme otomasyonu | 4 | Python |

---

## Görev 1: Kelime sayma aracı
**İş:** Bir metin dosyasındaki en sık geçen 10 kelimeyi (büyük/küçük harf ayrımı yapmadan, noktalama işaretlerini atarak) kaç kez geçtikleriyle birlikte yazan bir komut satırı programı. Türkçe metinlerle de doğru çalışmalı.

SIRALAMA:
1. Vash — Belgelerde gereken her şeyin hazır olduğu açıkça yazıyor: Türkçe büyük/küçük harf çevirme (`lower("tr")`), Türkçe harfleri tanıyan düzenli ifade, sözlük, `sort(by: ...)` ile sıralama ve `args()` ile komut satırından bilgi alma; üstelik hatalar program çalışmadan yakalanıyor.
2. Python — Metin işleri, düzenli ifade, dosya okuma ve sözlük hazır geldiği için kod kısa ve hızlı yazılır, ama belgelerde Türkçe harf çevirme desteğinden söz edilmiyor ve hatalar ancak program çalışırken ortaya çıkıyor.
3. JavaScript (Node.js) — Metin işleri, düzenli ifade ve dosya okuma hazır, kod hızlı yazılır; ancak Türkçe desteğinden belgede söz edilmiyor ve tip hataları ancak çalışırken çıkıyor.
4. Java — Metin işleri ve düzenli ifade hazır, ama kod uzun ve törenli, bu makinede iki farklı sürüm karışık duruyor ve açılışı yavaş.
5. C / C++ — Metin işleri az ya da orta düzeyde, Türkçe harfleri doğru işlemek için hazır bir araç belirtilmemiş, bellek hatası riski var ve aynı iş için çok daha uzun kod gerekir.

## Görev 2: Yapılacaklar listesi
**İş:** Dosyaya kaydeden bir yapılacaklar listesi programı: iş ekle, listele, tamamlandı olarak işaretle, sil. Program kapanıp yeniden açılınca liste kaybolmamalı.

SIRALAMA:
1. Python — Dosya ve JSON işleri standart kütüphanede hazır, kod kısa ve okunaklı, hız bu iş için önemsiz olduğu için yavaşlığı sorun olmaz.
2. Vash — Dosya, JSON ve hatta masaüstü penceresi hazır, birçok hatayı (boş değer, ele alınmamış hata, izinsiz dosya erişimi) çalışmadan yakalar, ama çok genç olduğu ve örnek kod az olduğu için ikinci sırada.
3. JavaScript (Node.js) — JSON ve dosya işleri doğal ve kolay, ama tip hataları ancak çalışırken ortaya çıkar ve masaüstü arayüzü yok.
4. Java — Dosya işleri ve masaüstü penceresi var, ama hazır JSON/CSV yok, kod uzun ve törenli, bu bilgisayarda iki Java sürümü karışık.
5. C / C++ — Hazır JSON/CSV yok, metin işleri zayıf, bellek hatası riski yüksek ve bu kadar basit bir iş için kod gereksiz uzun olur.

## Görev 3: Hızlı asal sayma
**İş:** 1'den 50.000.000'a kadar (dahil) kaç tane asal sayı olduğunu olabildiğince hızlı sayan bir program; çalışma süresini de ölçüp yazmalı.

SIRALAMA:
1. C / C++ — Belgeye göre en hızlı dil bu; Vash'ın bile tam sayı döngüsünde ve `[bool]` listesiyle elemede (asal bulmanın tam bu işi) C'den %13–32 yavaş kaldığı yazıyor, 16 çekirdeği de iş parçacıklarıyla kullanabiliyor.
2. Vash — Makine koduna derlenip C'ye yakın hızda çalışıyor, `parallel repeat` ve `measure { }` ile 16 çekirdeğe bölmek ve süreyi ölçmek kolay ve güvenli, ama her işlemde taşma ve sınır kontrolü yaptığı için bu işte C'nin biraz gerisinde kalıyor.
3. Java — JIT (çalışırken makine koduna çevirme) sayesinde hızı yüksek ve iş parçacıkları güçlü, ama açılış süresi ve bellek kullanımı yüksek, bu makinede de iki sürüm karışık duruyor.
4. JavaScript (Node.js) — JIT ile orta–yüksek hızda, ama yoğun sayı hesabında derlenen dillerden yavaş ve paralel hesap (worker_threads) zahmetli.
5. Python — Yorumlanarak çalıştığı için yoğun döngülerde onlarca kat yavaş, GIL yüzünden iş parçacıkları aynı anda hesap yapamıyor ve hızlandırıcı ek paket de kurulu değil.

## Görev 4: Masaüstü hesap makinesi
**İş:** Küçük bir masaüstü hesap makinesi penceresi: iki sayı girilebilsin, dört işlem için düğmeler olsun, sonuç pencerede görünsün.

SIRALAMA:
1. Vash — Kılavuzdaki yerleşik `window` bloğu bu işin istediği her şeyi hazır veriyor: sayı girmek için `textbox`, işlemler için `button`, sonucu göstermek için kendiliğinden güncellenen `label`; yazıyı sayıya çevirmek de kolay (`float("2.5")`), bu yüzden en kısa kod bununla yazılır.
2. Python — Standart kütüphanedeki tkinter ile ek paket kurmadan masaüstü penceresi yapılabiliyor ve kod kısa ve okunaklı oluyor.
3. Java — Swing ile pencere yapılabiliyor ama kod uzun ve törenli; üstelik bu makinede iki Java sürümü var, hangisinin çalıştığına dikkat etmek gerekiyor.
4. C / C++ — Pencere için sadece düşük seviyeli Win32 API var; basit bir hesap makinesi için bile çok uzun kod ve bellek hatası riski demek.
5. JavaScript (Node.js) — Yerleşik masaüstü penceresi yok ve paket kurmak için internet gerekiyor, yani bu iş bu makinede bununla neredeyse yapılamaz.

## Görev 5: CSV not raporu
**İş:** Bir CSV dosyasındaki öğrenci notlarından (sütunlar: ad, ders, not) her öğrencinin ortalamasını ve sınıf ortalamasını gösteren bir rapor üreten program.

SIRALAMA:
1. Python — CSV okuma standart kütüphanede hazır geliyor, kod kısa ve okunaklı oluyor, dil olgun; bu küçük işte yavaş olması önemli değil.
2. Vash — Hazır `csv` modülü (`csv.parse_records`) ve sözlüklerle iş kolayca yapılıyor, hatalar da program çalışmadan yakalanıyor; ama dil çok yeni ve örnek kod az.
3. JavaScript (Node.js) — Hızlı yazılıyor ve metin işleri güçlü, ama hazır CSV aracı yok (ayırmak elle yapılmalı) ve tip hataları ancak program çalışırken çıkıyor.
4. Java — Metin ve dosya araçları sağlam, ama CSV aracı yok, kod uzun ve törenli, bu bilgisayarda iki Java sürümü karışık.
5. C / C++ — CSV aracı yok, metin işleri zayıf ve kod uzun; çok yüksek hızı bu küçük işte işe yaramıyor, bellek hatası riski de cabası.

## Görev 6: REST API sunucusu
**İş:** Bir ürün kataloğu için HTTP üzerinden çalışan bir REST API sunucusu: ürün ekleme, listeleme, arama, güncelleme ve silme (istek ve cevaplar JSON). Aynı anda yüzlerce istemciye cevap verebilmeli; veriler diske kaydedilmeli ve sunucu yeniden başlayınca geri yüklenmeli; hatalı isteklere anlamlı hata kodları ve mesajları dönmeli.

SIRALAMA:
1. JavaScript (Node.js) — HTTP sunucusu ve JSON hazır geliyor, Node.js de web işleri için doğal bir araç; tek iş parçacığıyla çalışsa da bu iş zaten çoğunlukla ağ ve dosya beklemesi, o yüzden yüzlerce istemciye rahatça yetişir.
2. Vash — HTTP sunucusu (bağlantıları aynı anda kabul ediyor), JSON ve dosya araçları hazır geliyor, çok da hızlı; ama istekleri tek tek sırayla işliyor ve dil çok genç, örnek kod az.
3. Python — standart kütüphanesinde HTTP, JSON ve dosya araçları var, kod kısa olur; ama yavaş ve gerçek paralel çalışma zahmetli olduğundan yoğun yükte geride kalır.
4. Java — HTTP ve eşzamanlılık araçları güçlü; ama hazır JSON aracı yok, istekleri ve cevapları çözecek kodu elle yazmak gerekir, kod da uzun olur.
5. C / C++ — HTTP de JSON da yok, sadece düşük seviyeli soket var; her şeyi sıfırdan yazmak gerekir, bellek hatası riski de yüksek.

## Görev 7: Görüntü işleme aracı
**İş:** 8000×6000 piksellik fotoğrafları (BMP ya da PPM biçiminde) okuyup Gauss bulanıklaştırma, Sobel kenar bulma ve histogram eşitleme uygulayan, sonucu yeni bir dosyaya yazan bir komut satırı aracı. Hangi filtrelerin uygulanacağı komut satırından seçilmeli. Bütün işlemci çekirdeklerini kullanıp olabildiğince hızlı çalışmalı.

SIRALAMA:
1. Vash — C/C++ seviyesinde hızlı makine koduna derleniyor, `bytes` ile ikili dosya okuma/yazma, `args()` ile komut satırı, `parallel repeat` ile satırları çekirdeklere kolayca bölme ve histogram toplamayı kendiliğinden paralel yapma sunuyor, veri yarışlarını da derlerken yakalıyor; tek bedeli tam sayı döngülerinde %13–32 yavaşlık ve dilin genç olması.
2. C / C++ — en yüksek hızı ve bellek üzerinde tam kontrolü veriyor, `std::thread` ile 16 çekirdeğin hepsi kullanılabilir, ama veri yarışları ve bellek hataları derleyici tarafından yakalanmıyor, kod da uzun oluyor.
3. Java — JIT sayesinde hızlı ve eşzamanlılık kütüphanesi güçlü, ama çöp toplayıcı, yüksek bellek kullanımı (yaklaşık 144 MB'lık görüntüler için) ve makinedeki karışık JDK sürümleri onu geride bırakıyor.
4. JavaScript (Node.js) — ikili dosya desteği var ama yoğun sayı hesabında derlenen dillerden yavaş, worker_threads ile paralel çalışma da zahmetli (veri mesajla taşınıyor).
5. Python — sadece standart kütüphane kurulu (hızlandırıcı paket yok), yoğun döngülerde onlarca kat yavaş, GIL yüzünden iş parçacıkları aynı anda hesap yapamıyor; 48 milyon piksel için en uygunsuz seçenek.

## Görev 8: 2B aksiyon oyunu
**İş:** Gerçek zamanlı bir 2B aksiyon oyunu: klavyeyle yönetilen oyuncu, ekranda aynı anda binlerce düşman ve mermi, çarpışma algılama, basit fizik (yerçekimi, sekme), skor ve can göstergesi. Bölümlerin düzeni bir JSON dosyasından yüklenmeli. Saniyede 60 kare akıcı çalışmalı.

SIRALAMA:
1. Vash — C/C++ hızında çalışıyor, Raylib tabanlı `graphics` modülü (pencere, çizim, `key_down`, `fps`) ve `json` modülü hazır geliyor; çöp toplayıcı olmadığı için oyun sırasında takılma da olmuyor.
2. C / C++ — En yüksek hızı veriyor ve Raylib 6.2 kurulu, ama JSON için hazır araç yok ve bellek hataları riski var.
3. Java — Java2D ile 2B çizim ve Swing ile klavye kullanımı hazır, hızı yeterli; ama JSON için hazır araç yok ve çöp toplayıcının kısa duraklamaları akıcılığı bozabilir.
4. Python — JSON ve tkinter canvas hazır, ama yavaş olduğu için binlerce düşman ve mermiyi saniyede 60 kare çizip çarpışmalarını hesaplayamaz.
5. JavaScript (Node.js) — JSON doğal olarak destekleniyor, ama hazır pencere ya da grafik aracı yok ve internet olmadığı için bunlar paketle de eklenemeyebilir; yani oyun ekrana hiç çizilemez.

## Görev 9: Betik dili yorumlayıcısı
**İş:** Küçük bir betik dili için yorumlayıcı: değişkenler, sayılar ve metinler, if/while, fonksiyonlar (özyineleme dahil), listeler. Sözdizimi ve çalışma hatalarında satır ve sütun numarasıyla anlaşılır hata mesajı vermeli. Bu dilde yazılmış fib(30) gibi özyinelemeli bir betiği makul sürede çalıştırabilmeli.

SIRALAMA:
1. Vash — Kılavuza göre `enum` + `match` sözdizimi ağacını kurmaya ve gezmeye çok uygun, C seviyesinde hızı fib(30)'u rahatça çalıştırır, sözlükleri, hata yakalamayı (`fails`/`try`) ve listeleri hazır sunar, birçok hatayı da program çalışmadan yakalar (riski: dil çok genç ve örnek kod az).
2. JavaScript (Node.js) — Kısa ve hızlı yazılır, dinamik nesneler ve kapanışlar yorumlayıcı yazmayı kolaylaştırır, JIT sayesinde de fib(30) makul sürede biter; ama tip hataları ancak çalışırken ortaya çıkar.
3. Java — Hızlıdır, tipleri sıkıdır, standart kütüphanesi geniştir ve olgundur; ama kod uzun ve törenlidir, bu makinede de iki Java sürümü karışık kurulu.
4. C / C++ — En yüksek hızı verir; ama bir yorumlayıcıdaki ağaç ve metin işlerinde bellek hatası ve tanımsız davranış riski yüksektir, kod da uzar.
5. Python — En kısa ve okunaklı kodu verir; ama yavaş olduğu için Python'da yazılmış bir yorumlayıcının içinde fib(30) çalıştırmak (yaklaşık 1,3 milyon çağrı) "makul süre" şartını büyük olasılıkla karşılamaz.

## Görev 10: Anahtar-değer veritabanı
**İş:** Bir anahtar-değer veritabanı motoru: diskte milyonlarca kayıt tutabilmeli; hızlı arama için indeks ve anahtar aralığı sorguları olmalı; elektrik kesilse bile veri kaybolmaması için önce günlüğe yazma (write-ahead log) ve açılışta kurtarma yapmalı; aynı anda okuma yapan birden fazla istemciyi desteklemeli.

SIRALAMA:
1. Java — Hızlı, olgun ve kararlı; zengin eşzamanlılık kütüphanesi birçok okuyucunun ortak indeksi aynı anda okumasını kolaylaştırıyor, geniş standart kütüphanesi de ikili dosya işlerini, otomatik bellek yönetimini ve sıkı tip denetimini bir arada sunuyor.
2. C / C++ — En yüksek hızı ve diske yazma, senkronlama ve bellek üzerinde tam kontrolü veriyor, ama bellek hataları ve veri yarışları derlerken yakalanmadığı için bu kadar kritik bir motorda risk yüksek.
3. Vash — C hızında ve güvenli bir dil, ama belgelere göre dosyalar bütün halinde okunup yazılıyor (dosyanın ortasına atlamak için C fonksiyonları gerekiyor), kilit yok, arka plandaki işler değişen ortak veriyi okuyamıyor; bu da birçok okuyucunun aynı indeksi paylaşmasını zorlaştırıyor, üstelik dil çok genç.
4. JavaScript (Node.js) — İkili dosya araçları ve makul hızı var, ama ana kod tek iş parçacığında çalışıyor ve işçiler arasında veri ancak mesajla taşınıyor; bu yüzden ortak indeksi aynı anda birçok okuyucuya açmak zahmetli, tip hataları da ancak çalışırken çıkıyor.
5. Python — Milyonlarca kayıt ve sık indeks işlemi için yavaş; GIL yüzünden iş parçacıkları aynı anda hesap yapamıyor, hatalar da çoğunlukla çalışırken ortaya çıkıyor.

## Görev 11: Sohbet sunucusu (yeni)
**İş:** Çok kullanıcılı bir sohbet sunucusu: kullanıcılar HTTP üzerinden sohbet odalarına mesaj gönderir ve yeni mesajları alır; aynı anda yüzlerce kullanıcı bağlı olabilir; mesaj geçmişi diske kaydedilmeli; bozuk ya da kötü niyetli isteklerde sunucu asla çökmemeli ve uzun süre kesintisiz çalışmalı.

SIRALAMA:
1. Java — Hazır HTTP ve zengin eşzamanlılık araçları sayesinde yüzlerce bağlantıyı aynı anda taşır, bir istekte çıkan hata (istisna) sadece o isteği bozar, sunucuyu durdurmaz; ayrıca olgun ve kararlı olduğu için uzun süre kesintisiz çalışmaya en uygun olanı (JSON'un hazır olmaması küçük bir eksik).
2. JavaScript (Node.js) — HTTP ve JSON için en doğal dil, tek iş parçacıklı olay döngüsü yüzlerce açık bağlantıyı ve "yeni mesaj gelene kadar bekle" isteklerini kolayca taşır; ama tip hataları ancak çalışırken ortaya çıkar ve yakalanmayan bir hata bütün süreci düşürebilir.
3. Python — Standart kütüphanede HTTP, JSON ve dosya araçları hazır, istek hataları kolayca yakalanır; ama yavaş, GIL yüzünden gerçek paralellik yok ve hatalar çalışırken ortaya çıkıyor.
4. Vash — HTTP/HTTPS sunucusu, JSON ve derlerken yakalanan birçok hata çok çekici; ama istekler tek sırada işleniyor, dizi sınırı ya da sayı taşması gibi hatalar bütün programı durduruyor (bu da "asla çökmemeli" şartına ters), gerçek tarih/saat yok ve dil çok genç.
5. C / C++ — Sadece düşük seviye soket var (HTTP ve JSON elle yazılmalı), bellek hataları ve tanımsız davranış kötü niyetli isteklere karşı en büyük çökme ve güvenlik riskini taşıyor.

## Görev 12: N-cisim fizik simülasyonu (yeni)
**İş:** Bir kütleçekim (N-cisim) simülasyonu: 1 milyon parçacık; her adımda parçacıklara etkiyen kuvvetleri yaklaşık bir yöntemle (ızgara/ağaç) hesaplayıp hız ve konumları günceller; 1000 adım çalışır ve her 100 adımda bütün parçacıkların konumlarını bir dosyaya yazar. Bütün işlemci çekirdeklerini kullanmalı ve sayısal sonuçlar güvenilir olmalı.

SIRALAMA:
1. Vash — Belgelere göre C/C++ hızında çalışıyor, ondalıklı sayı hesabında C'den bile hızlı; `parallel repeat` ve paralel toplama (ızgaraya kütle yığmak için `liste[k] = liste[k] + x` biçimi) bütün çekirdekleri kolayca kullanıyor; aynı veriye aynı anda yazma hatalarını (veri yarışlarını), dizi sınırı aşımını ve sayı taşmasını yakalıyor, bu da sonuçları güvenilir kılıyor.
2. C / C++ — En yüksek hız ve tam bellek denetimi sunuyor, ama aynı veriye aynı anda yazma hatalarını, sınır aşımını ve tanımsız davranışı (sonucu önceden kestirilemeyen hataları) derleyici yakalamıyor; bu da sayısal güvenilirliği bütünüyle programcıya bırakıyor.
3. Java — Yüksek hızı, zengin eşzamanlılık kütüphanesi ve dizi sınırı kontrolü var, ama veri yarışlarını derleyici yakalamıyor, tam sayı taşması sessizce başa sarıyor, açılış süresi ile bellek kullanımı yüksek, makinede de iki sürüm karışık duruyor.
4. JavaScript (Node.js) — Yoğun sayı hesabında derlenen dillerden yavaş; paralellik verinin mesajla taşındığı worker_threads ile zahmetli; sınır dışı erişim sessizce `undefined` döndürdüğü için hatalar gizli kalabilir.
5. Python — Yalnızca standart kütüphane kurulu (sayısal hesap paketi yok); yoğun döngülerde onlarca kat yavaş; GIL (iş parçacıklarının aynı anda hesap yapmasını engelleyen kilit) yüzünden paralellik ancak ayrı süreçlerle mümkün; 1 milyon parçacıkla 1000 adım bu koşullarda pratik değil.

## Görev 13: Web tarayıcısı / crawler (yeni)
**İş:** Verilen bir başlangıç adresinden başlayıp aynı sitedeki sayfaları gezen bir web tarayıcısı (crawler): en fazla 2000 sayfa, aynı anda 20 sayfa indirme, her sayfanın HTML'inden başlığı ve bağlantıları çıkarma, aynı sayfayı iki kez indirmeme, sonuçları bir JSON dosyasına yazma, ulaşılamayan sayfaları hata nedeniyle raporlama.

SIRALAMA:
1. Vash — Belgeye göre gereken her şey hazır geliyor: HTTPS destekli `http.get` ve hata nedenini veren `http.error()`, `start`/`channel` ile 20 işçi kurmak, düzenli ifadeyle bağlantı çıkarmak ve `json` modülü; üstelik işçiler arasında aynı veriye aynı anda dokunma hataları (veri yarışları) program çalışmadan yakalanıyor.
2. Python — Standart kütüphanesinde HTTP, JSON ve düzenli ifade araçları var ve kod kısa yazılıyor; GIL yalnızca aynı anda hesap yapmayı engellediği, ağdan cevap beklemeyi engellemediği için iş parçacıkları 20 indirme için yeterli olur.
3. JavaScript (Node.js) — JSON ve web işleri için doğal ve HTTP desteği hazır, fakat tip hataları ancak program çalışırken ortaya çıkıyor ve kurulu bir paket olmadığı için HTML'i sadece düzenli ifadeyle ayrıştırmak gerekecek.
4. Java — HTTP desteği ve güçlü eşzamanlılık araçları var, fakat hazır JSON aracı yok, kod uzun oluyor ve bu makinede iki Java sürümü birbirine karışmış durumda.
5. C / C++ — Ağ için sadece düşük seviyeli soket var; hazır HTTP, HTTPS ve JSON araçları yok ve bellek hatası riski yüksek; bu iş için en zahmetli seçenek.

## Görev 14: 10 GB günlük (log) analizi (yeni)
**İş:** 10 GB'lık bir web sunucusu günlük (log) dosyasını analiz eden bir araç: satırları düzenli ifadelerle ayrıştırır; saat başına istek sayısını, en çok hata veren 20 adresi, yanıt sürelerinin ortalamasını ve yüzde 95'lik değerini çıkarır. Dosya belleğe sığmayabilir; olabildiğince hızlı ve çok çekirdekli çalışmalı.

SIRALAMA:
1. Vash — Belgeye göre C/C++ kadar hızlı, düzenli ifadeleri hazır ve kilitlenmeyen bir motorla çalıştırıyor, `parallel repeat` ile sayımları kendiliğinden çekirdeklere bölüyor ve veri yarışlarını program çalışmadan yakalıyor; büyük dosyayı parça parça okumak gerekirse C kütüphanelerini (ör. `fopen`) doğrudan çağırabiliyor, ancak dil çok genç ve tarih/saat desteği sadece geçen süreyle sınırlı.
2. C / C++ — En yüksek hızı ve tam bellek denetimini veriyor; C++'ta düzenli ifade ve iş parçacıkları var, ama veri yarışları ve bellek hataları programcıya kalıyor ve aynı iş için kod uzun.
3. Java — Hızı yüksek, düzenli ifade ve zengin çok çekirdek araçları hazır, ama JVM'in açılışı ve bellek kullanımı yüksek, bu makinede de iki sürüm karışık.
4. JavaScript (Node.js) — Düzenli ifade ve dosya araçları var, ama yoğun hesapta derlenen dillerden yavaş ve worker_threads ile paralel çalıştırmak zahmetli (veri işçiler arasında mesajla taşınıyor).
5. Python — Kodu en kısa olurdu, ama 10 GB veride çok yavaş kalır ve GIL yüzünden gerçek paralellik ancak ayrı süreçlerle (multiprocessing) zahmetli biçimde sağlanır.

## Görev 15: Fatura takip programı (yeni)
**İş:** Küçük bir işletme için masaüstü fatura takip programı: pencerede fatura ekleme, düzenleme ve silme; müşteriye göre listeleme; aylık toplam ve KDV hesabı; CSV'ye dışa aktarma; program kapanınca veriler kaybolmamalı. Kullanıcı programcı değil, arayüz basit ve anlaşılır olmalı; para hesaplarında hata olmamalı.

SIRALAMA:
1. Python — Belgelere göre bu işin her parçası hazır geliyor: tkinter ile pencere, CSV, JSON ve tarih/saat; tam sayılar da taşmadığı için para tutarı kuruş olarak tutulursa hesap hatasız olur. Hız yavaş ama küçük bir fatura programı için sorun değil.
2. Vash — Yerleşik pencere, CSV ve JSON var; hataların çoğunu program çalışmadan yakalıyor ve taşmada durduruyor, bu da para hesabı için iyi. Ama tarih/saat aracı yok (aylık toplam için tarihi elle ayırmak gerekir), pencerede az parça var ve tek pencere açılabiliyor, dil de çok genç.
3. Java — Swing ile olgun bir masaüstü arayüzü ve tarih/saat desteği var. Ama hazır CSV ve JSON yok, kod uzun, ayrıca bu makinede iki Java sürümü karışık duruyor.
4. C / C++ — Pencere sadece düşük seviyeli Win32 ile yapılabiliyor, CSV ve JSON yok, bellek hatası riski de yüksek. Bu kadar basit bir program için gereksiz zahmet ve risk.
5. JavaScript (Node.js) — Masaüstü pencere desteği hiç yok, eklemek için internetten paket kurmak gerekiyor; tip hataları da ancak program çalışırken ortaya çıkıyor.

## Görev 16: Ses işleme aracı (yeni)
**İş:** WAV ses dosyalarını okuyup ses seviyesini normalleştiren, yankı (eko) efekti ekleyen ve sonucu yeni bir WAV dosyasına yazan bir komut satırı aracı. İkili dosya biçimini (başlık, 16 bitlik örnekler) doğru okuyup yazmalı; 1 saatlik kayıtları birkaç saniyede işleyebilmeli.

SIRALAMA:
1. Vash — Belgelere göre C/C++ hızında çalışıyor, ikili dosya okuma/yazma (`bytes`, `get_int`/`add_int`, `read_bytes`/`write_bytes`) ve komut satırı argümanları (`args()`) hazır, `parallel repeat` ile çok çekirdek kolay; dizi sınırı ve taşma hataları da anlaşılır mesajla yakalandığı için kısa ve güvenli kodla 1 saatlik kayıt birkaç saniyede işlenebilir.
2. C / C++ — En yüksek hızı ve ikili veri üzerinde tam kontrolü veriyor, ancak bellek hataları, dizi sınırı aşımı ve tanımsız davranış riski derleyici tarafından yakalanmadığı için örnek işleme kodu hataya daha açık ve daha uzun.
3. Java — Hızı yüksek, ikili dosya araçları ve sıkı tipleri var, fakat JVM açılış süresi, bellek kullanımı, uzun kod ve bu makinede iki sürümün karışık olması onu öndekilerin gerisine düşürüyor.
4. JavaScript (Node.js) — İkili dosya araçları var ve hızı orta–yüksek, ama yoğun sayı hesabında derlenen dillerden yavaş, tip hataları ancak çalışırken çıkıyor ve paralel hesap zahmetli.
5. Python — İkili dosya araçları ve kısa kod avantajına rağmen yalnızca standart kütüphane kurulu olduğundan, saatlik kayıttaki milyonlarca örneği tek tek dolaşan döngüler onlarca kat yavaş kalır ve GIL yüzünden gerçek paralellik zahmetli.

## Görev 17: Yapay sinir ağı (yeni)
**İş:** Hazır makine öğrenmesi kütüphanesi kullanmadan, sıfırdan küçük bir yapay sinir ağı: CSV dosyasından 60.000 el yazısı rakam görüntüsünü (her biri 784 piksel) okuyup ileri ve geri yayılımla birkaç tur eğitir, test verisinde doğruluğu raporlar. Matris işlemleri yoğun; eğitim olabildiğince hızlı ve çok çekirdekli olmalı.

SIRALAMA:
1. Vash — Belgelere göre C ile aynı hızda, ondalıklı (virgüllü sayı) hesapta C'den bile hızlı; `parallel repeat` ile matris döngüleri kolayca çekirdeklere bölünüyor, veri yarışları (iki işin aynı veriye aynı anda yazması) derlerken yakalanıyor ve hazır `csv` modülü var.
2. C / C++ — En yüksek hıza ve 16 çekirdeği tam kontrol etme imkânına sahip, ama CSV okuyucusu yok, iş parçacıklarını ve bellek hatalarını programcı kendisi yönetmek zorunda.
3. Java — JIT ile hızlı çalışıyor ve güçlü bir eşzamanlılık (aynı anda çalışma) kütüphanesi var, ama CSV aracı yok, kod uzun ve bu makinede iki JDK sürümü karışık.
4. JavaScript (Node.js) — Yoğun sayı hesabında derlenen dillerden yavaş, paralel hesap için worker_threads'e (ayrı işçilere) veriyi mesajla taşımak gerekiyor ve CSV aracı yok.
5. Python — Ek paket olmadan (NumPy yokken) hızı düşük; GIL kilidi yüzünden iş parçacıkları aynı anda hesap yapamıyor, bu yüzden yoğun matris işi için en kötü seçenek.

## Görev 18: Dosya sıkıştırma aracı (yeni)
**İş:** Bir dosya sıkıştırma aracı: herhangi bir dosyayı (metin ya da ikili) Huffman kodlamasıyla sıkıştıran ve geri açan, açılan dosyanın birebir aynı olduğunu doğrulayan bir komut satırı programı. Bit düzeyinde ikili okuma ve yazma gerekir; yüzlerce MB'lık dosyalarda hızlı olmalı.

SIRALAMA:
1. C / C++ — Bu iş en çok ham hız ve bit düzeyinde tam kontrol istiyor; belgeye göre "çok yüksek" hız, ikili dosya araçları ve belleğe tam hâkimiyet sunan tek dil bu, bellek hatası riski ise bu kadar küçük ve iyi bilinen bir programda yönetilebilir.
2. Vash — C ile aynı düzeyde hızlı, `bytes` tipi ve `read_bytes`/`write_bytes` hazır, bayt sayımı `parallel repeat` ile kendiliğinden çekirdeklere bölünüyor; ama kılavuzda bit işlemleri (kaydırma, ve/veya) hiç geçmediği için bitleri çarpma, bölme ve kalanla işlemek gerekecek, ayrıca dil çok genç.
3. Java — JIT sayesinde hızı yüksek, ikili dosya desteği ve olgun kütüphanesi var; ama kod uzun, açılışı yavaş, bellek kullanımı yüksek ve bu makinede iki sürüm karışık.
4. JavaScript (Node.js) — İkili dosya okuma/yazma var ama hızı "orta–yüksek", yoğun sayı ve bit hesabında derlenen dillerden yavaş, paralel hesap da zahmetli.
5. Python — İkili dosya desteği olsa da yoğun döngülerde onlarca kat yavaş, bu da yüzlerce MB'lık dosyayı bit bit işlerken hız şartını karşılamasını imkânsıza yakın kılıyor.

## Görev 19: Satranç motoru (yeni)
**İş:** Bir satranç motoru: bütün kurallarla geçerli hamle üretimi (rok, geçerken alma, terfi, şah çekme kontrolü), alfa-beta budamalı arama ve bir değerlendirme fonksiyonu; verilen bir pozisyonda belirli bir süre içinde en iyi hamleyi bulmalı. Saniyede olabildiğince çok pozisyon inceleyebilmeli ve aramayı birden çok çekirdeğe yayabilmeli.

SIRALAMA:
1. C / C++ — En yüksek hızı verir, bit tahtası ve Zobrist anahtarı için gereken bit işlemleri ve taşınca başa saran sayılar var, ayrıca `std::thread` ile ortak bir hamle önbelleğini (daha önce bakılan pozisyonların tablosu) bütün çekirdekler aynı anda kullanabilir; belleği elle yönetmenin riski bu iş için kabul edilebilir.
2. Java — JIT ile hızı yüksek, zengin iş parçacığı kütüphanesiyle aramayı çekirdeklere yaymak ve ortak önbelleği paylaşmak kolay, taşan sayıların sessizce başa sarması da karma (hash) hesabına uyar; yalnız C/C++'tan biraz yavaş ve bu makinede iki Java sürümü karışık.
3. Vash — Hızı C/C++ seviyesinde ve `parallel repeat` ile kök hamleleri güvenle çekirdeklere bölebilir, ama kılavuzda bit işlemleri yok, taşan sayı programı durdurur (Zobrist karması yazılamaz) ve kilit ya da paylaşılan değişebilir veri olmadığı için çekirdekler ortak önbellek kullanamaz.
4. JavaScript (Node.js) — JIT sayesinde orta–yüksek hızda ve 32 bitlik bit işlemleri var, ama worker_threads arasında veri mesajla taşındığı için paralel arama zahmetli ve yoğun sayı hesabında derlenen dillerden yavaş.
5. Python — Saniyede incelenen pozisyon sayısı en önemli ölçüt, Python ise yoğun döngülerde onlarca kat yavaş ve GIL yüzünden çekirdeklere ancak ayrı süreçlerle (multiprocessing) yayılabiliyor.

## Görev 20: Dosya düzenleme otomasyonu (yeni)
**İş:** Bir klasörü izleyen dosya düzenleme aracı: klasöre yeni gelen fotoğraf, belge ve müzik dosyalarını türüne ve tarihine göre alt klasörlere taşır; aynı adlı dosyalarda çakışmayı çözer; yaptığı her işi bir günlük dosyasına yazar; kurallarını bir ayar dosyasından (JSON) okur. Sürekli arka planda çalışır.

SIRALAMA:
1. Python — Belgeye göre bu işin bütün parçaları (dosya işleri, JSON, tarih/saat, metin işleri) standart kütüphanede hazır ve kod kısa yazılıyor; işin çoğu dosya beklemek olduğu için yavaşlığı burada sorun değil.
2. JavaScript (Node.js) — Dosya, JSON, tarih/saat ve arka planda sürekli çalışma rahat, ama tip hataları ancak program çalışırken ortaya çıkıyor ve ek paket kurmak için internet gerekiyor.
3. Java — Dosya, tarih/saat ve uzun süre çalışma için olgun araçları var, ama hazır JSON desteği olmadığı için ayar dosyasını okuyan kısmı elle yazmak gerekiyor ve kod uzun oluyor.
4. Vash — JSON ve güvenli kod yazma iyi, ama tarih/saat olarak sadece geçen süreyi ölçebiliyor ve kılavuzda klasördeki dosyaları listeleme, taşıma, klasör açma ya da dosyanın tarihini okuma yok, bunların hepsi C kütüphanelerine elle bağlanarak (`extern`) yapılmak zorunda.
5. C / C++ — JSON yok, tarih/saat araçları temel düzeyde, bellek hatası riski var ve aynı iş için yazılacak kod çok uzun; bu işte çok yüksek hıza da ihtiyaç yok.
