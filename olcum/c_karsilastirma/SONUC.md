# Vash, C ve C++ hız karşılaştırması / speed comparison

C: `clang -O2`, C++: `clang++ -O2 -std=c++17` (clang 23), Vash: `vash build`. Üçü aynı anda ölçüldü: her program 5 kez çalıştı,
en kısa süre alındı; bu da 3 kez tekrarlandı ve ortancası yazıldı (16 çekirdekli Windows 11, clang 23). Üç ölçüm arasındaki fark ±0,02 sn.
Üç dil de her programda aynı sonucu buldu. Tekrar ölçmek için: `powershell -File olc.ps1`.

| Program | Ne yapıyor | Vash | C | C++ | Sonuç |
|---|---|---|---|---|---|
| mandel | 2000×2000 Mandelbrot (ondalıklı sayı hesabı) | **0,33 sn** | 0,55 sn | 0,55 sn | Vash %40 daha hızlı |
| sirala | 5 milyon sayıyı sıralama | **0,15 sn** | 0,92 sn (`qsort`) | 0,23 sn (`std::sort`) | Vash C'den 6,1 kat, C++'tan 1,5 kat hızlı |
| toplam | 2 milyar turluk tam sayı döngüsü | 2,85 sn | 2,48 sn | **2,46 sn** | C/C++ %14 önde (Vash her işlemde taşma kontrolü yapar) |
| asal | 50 milyona kadar eleme | 0,46 sn | 0,44 sn (1 bayt `bool`) | **0,26 sn** (`std::vector<bool>`, bit bit) | C %5 önde; C++ 1,8 kat önde |
| toplam_paralel | aynı toplam, bütün çekirdekler | **0,28 sn** (`parallel repeat`) | — | 0,32 sn (`std::thread`) | Vash %13 daha hızlı; tek satırla |

**Bu sürümde ne değişti (önceki ölçüme göre):**

| | önce | şimdi | neden |
|---|---|---|---|
| sirala | 0,50 sn | 0,15 sn | Tam sayı ve ondalık listeleri artık **taban sıralamasıyla** (radix sort, karşılaştırmasız) sıralanıyor. |
| toplam_paralel | 0,52 sn | 0,28 sn | Sınırları sabit olan `parallel repeat`'te her çekirdeğe "senin parçan bu aralıkta" bilgisi veriliyor; LLVM gereksiz taşma kontrollerini siliyor. |
| asal | 0,63 sn | 0,46 sn | `repeat N { liste.add(sabit) }` kalıbı tek seferde dolduruluyor; döngüde sadece okunup yazılan yerel listelerin paylaşım kontrolü döngüden önce bir kez yapılıyor. |

**C++'ın önde olduğu iki yer:**
- **toplam:** Vash her tam sayı toplamasında taşmayı kontrol eder (taşarsa sessizce yanlış sonuç vermek yerine hata verir). Fark bu güvencenin bedeli.
  Aynı kontrolü C'ye elle ekleyince (`__builtin_add_overflow`, [toplam_kontrollu.c](toplam_kontrollu.c)) C de 2,81 sn sürüyor: farkın tamamı bu.
- **asal:** C++'ın `vector<bool>`'u her değeri tek **bit** tutar (8 kat az bellek). Vash bunu bilerek yapmaz: iki çekirdek aynı bayttaki
  komşu bitlere aynı anda yazarsa biri kaybolur; Vash'ın "paralel kodda veri yarışı olmaz" güvencesi bozulurdu.
  Vash'ın sınır ve taşma kontrollerinin burada maliyeti yok: aynı kontrollerle yazılmış C de 0,45 sn.

**In short (EN):** Vash now beats C++ on floating point (Mandelbrot), sorting (radix sort for numeric lists) and parallel loops,
and is close to C on the prime sieve. C++ stays ahead where Vash pays for safety: integer overflow checks on every addition,
and 1-byte (not bit-packed) booleans so that parallel writes can never race.
