<p align="center"><img src="logo/vash_logo.svg" width="120" alt="Vash logosu"></p>

<h1 align="center">Vash</h1>

<p align="center"><b>Python kadar kolay, C kadar hızlı, baştan güvenli.</b><br>
Kendini derleyen, makine koduna çevrilen genel amaçlı bir dil; yanında 2B oyun motoru, yapay zekânın yazdığı kod için kum havuzu
ve onunla yazılmış gerçek uygulamalar.</p>

<p align="center"><a href="README.md">English</a> · <a href="VASH_SPEC.md">Dil tarifi</a> · <a href="KUM_HAVUZU.md">Kum havuzu</a> · <a href="vash_engine/BENIOKU.md">Vash Engine</a> · <a href="TASARIM.md">Tasarım kararları</a></p>

> **Durum: deneysel.** Şimdilik sadece Windows. Derleyici kendini derliyor ve testlerini geçiyor,
> ama dil ve standart kütüphane hâlâ değişebilir.

Örnek kod için [İngilizce sayfaya](README.md) ya da [docs/ornek.vash](docs/ornek.vash) dosyasına bak.

## Neden Vash

- **Okunaklı.** Python'a benzer, süslü parantezli yazım; `==` yerine `is`; her nesne alan adlarıyla kurulur; `null` sürprizi yok (`T?` ve `else:`).
- **Hızlı.** LLVM ile makine koduna derlenir. `parallel repeat` tek kelimeyle bütün çekirdekleri kullanır. C ve C++ ile aynı anda ölçüldü
  (clang 23, `-O2`, 5 denemenin en iyisi; [ayrıntı](olcum/c_karsilastirma/SONUC.md)):

  | Program | Vash | C | C++ |
  |---|---|---|---|
  | Mandelbrot 2000×2000 (ondalıklı hesap) | **0,35 sn** | 0,59 sn | 0,59 sn |
  | 5 milyon sayıyı sıralama | **0,17 sn** | 0,98 sn (`qsort`) | 0,26 sn (`std::sort`) |
  | 2 milyar turluk tam sayı döngüsü | 2,84 sn | 2,49 sn | **2,47 sn** |
  | 50 milyona kadar asal eleği | 0,47 sn | 0,44 sn | **0,27 sn** (bit bit `vector<bool>`) |
  | Aynı döngü 16 çekirdekte | **0,27 sn** (`parallel repeat`) | — | 0,32 sn (`std::thread`) |

  C++'ın önde olduğu yerlerde Vash güvenlik bedeli ödüyor: her tam sayı toplamasında taşmayı kontrol ediyor ve paralel
  yazmalar asla çakışmasın diye her `bool`'u bir bayt tutuyor.
- **Güvenli.** Değerler kopya gibi davranır (değişince kopyalanır, takma ad hatası olmaz); tam sayı taşması ve liste dışına çıkma
  çalışma hatasıdır; çöp toplayıcı duraklaması yoktur (referans sayımı ve `arena { }` blokları).
- **İzinler dilin içinde.** Dosyaya, internete, ekrana dokunan ya da komut çalıştıran fonksiyon bunu yazmak zorundadır
  (`use files`, `use net`...). Derleyici bir programın neler yapabildiğini kesin bilir.
- **Yapay zekâ için.** `vash check --json` hataları ve programın kullandığı izinleri makinenin okuyacağı biçimde verir; dilin tamamı
  tek sayfadır ([VASH_SPEC.md](VASH_SPEC.md)). 20 ajanlık denemede modeller Vash'ı verilen diller arasında ilk sıraya koydu.
- **Kendini derliyor.** [`vashc/`](vashc) klasöründeki derleyici Vash ile yazıldı ve kendini derliyor; 2. ve 3. aşama çıktıları birebir aynı.
- **İki dilli.** Hata mesajları Türkçe ya da İngilizce (`VASH_DIL=tr|en`; yoksa Windows'un dili).

## İçinde neler var

| | |
|---|---|
| **Standart kütüphane** (`std/`) | `http` (istemci + HTTP/HTTPS sunucu), `json`, `csv`, `regex`, `fs`, `math` (+ `Vec2`), `graphics` (raylib: resim, Türkçe yazı tipi, ses, kamera), `iso`, `engine` |
| **Eşzamanlılık** | `parallel repeat`, `start f()` / `.wait()` işleri, tipli `channel[T]` |
| **Kum havuzu** | `vash kum`, güvenilmeyen (örneğin yapay zekânın yazdığı) kodu sadece verdiğin izinlerle, dosyaları tek klasörle sınırlı, süre sınırlı ve başka program açamadan çalıştırır. Bkz. [KUM_HAVUZU.md](KUM_HAVUZU.md). |
| **Vash Engine** | Vash ile yazılmış 2B motor ve düzenleyici: hazır davranışlar, zaman makinesi (son 10 saniyeyi geri sar), dışa aktarılan oyun için güvenlik kartı, Claude (MCP) köprüsü. |
| **Vash Dedektif** | Disk analizi + Unity proje röntgeni: 850 bin dosya ~11–21 sn (Python `os.walk`: 164 sn), kopya bulma, Unity `Library` temizliği, kullanılmayan varlıklar. |

## Kurulum (Windows 10/11)

1. LLVM (clang) ve Python 3.10+ kur:
   ```powershell
   winget install LLVM.LLVM Python.Python.3.12
   ```
2. Depoyu indir, klasörünü `PATH`'e ekle (ya da `vash.cmd`'yi tam yoluyla çağır).
3. İlk komut derleyiciyi bir kez hazırlar (`derleyici/` klasöründeki küçük Python derleyicisiyle):
   ```powershell
   vash run ornekler\ilk.vash
   ```

## Komutlar

```text
vash run   dosya.vash        derle ve çalıştır
vash build dosya.vash        dosya.exe üret
vash check dosya.vash        sadece denetle (--json: ajanlar için, hatalar + izinler)
vash kum [--izin files+net] [--klasor klasor] [--sure 30] dosya.vash   kum havuzunda çalıştır
vash yenile                  vashc/ değişince derleyiciyi yeniden üret
```

## Testler

```powershell
python vashc\kendini_derle.py          # kendini derleme: 2. aşama == 3. aşama
python vashc\karsilastir_uretici.py    # Vash derleyicisi ile Python derleyicisi, 110 program
python vashc\spec_dene.py              # tarifteki her örnek derleniyor
```

## Lisans

MIT, bkz. [LICENSE](LICENSE). `kutuphaneler/raylib` içindeki raylib zlib lisanslıdır.
