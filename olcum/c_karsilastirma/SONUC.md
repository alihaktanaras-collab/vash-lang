# Vash, C ve C++ hız karşılaştırması / speed comparison

C: `clang -O2`, C++: `clang++ -O2 -std=c++17` (clang 23), Vash: `vash build`. Üçü aynı anda ölçüldü: her program 5 kez çalıştı,
en kısa süre yazıldı (16 çekirdekli Windows 11; ölçüm sırasında arka planda başka programlar da açıktı, bu yüzden süreler
boş bir bilgisayardakinden uzun olabilir; karşılaştırma aynı koşulda). Üç dil de her programda aynı sonucu buldu.
Tekrar ölçmek için: `powershell -File olc.ps1`.

| Program | Ne yapıyor | Vash | C | C++ | Sonuç |
|---|---|---|---|---|---|
| mandel | 2000×2000 Mandelbrot (ondalıklı sayı hesabı) | **0,32 sn** | 0,55 sn | 0,56 sn | Vash ~%42 daha hızlı |
| sirala | 5 milyon sayıyı sıralama | 0,50 sn | 0,92 sn (`qsort`) | **0,24 sn** (`std::sort`) | Vash C'den %46 hızlı, C++ Vash'tan 2,1 kat hızlı |
| toplam | 2 milyar turluk tam sayı döngüsü | 2,81 sn | **2,47 sn** | 2,49 sn | C/C++ %14 önde (Vash her işlemde taşma kontrolü yapar) |
| asal | 50 milyona kadar eleme | 0,63 sn | 0,44 sn (1 bayt `bool`) | **0,26 sn** (`std::vector<bool>`, bit bit) | C 1,4 kat, C++ 2,4 kat önde |
| toplam_paralel | aynı toplam, bütün çekirdekler | 0,52 sn (`parallel repeat`) | — | **0,32 sn** (`std::thread`) | C++ 1,6 kat önde; Vash tek çekirdekli C'den 4,7 kat hızlı |

**Kısaca:** Vash, ondalıklı sayı hesabında C ve C++'tan hızlı. Tam sayı döngülerinde güvenlik kontrolleri yüzünden %10–15 geride.
C++'ın elle ayarlanmış kütüphaneleri (`std::sort`, bit bit `vector<bool>`) ve elle yazılmış iş parçacıkları hâlâ önde;
Vash'ın sıralaması ve `[bool]` listesi bu konuda geliştirilebilir. Vash'ta paralellik tek kelime (`parallel`), C++'ta
iş parçacıklarını elle bölmek gerekiyor.

**In short (EN):** Vash beats C and C++ on floating-point math, is 10–15% behind on integer loops (it checks every operation
for overflow), and is still behind C++'s tuned `std::sort`, bit-packed `std::vector<bool>` and hand-written threads.
Parallelism in Vash is one keyword (`parallel repeat`).

**Asal eleği notu:** Vash `[bool]` listelerinde her eleman 1 bayt (C'deki gibi). C++'ın `vector<bool>`'u her elemanı 1 bit
tutar, bu yüzden belleğe 8 kat daha az dokunur. C'de 8 baytlık eleman kullanılınca süre çok uzar (`asal8.c`).
