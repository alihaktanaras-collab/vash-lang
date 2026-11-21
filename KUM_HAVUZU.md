# Vash Kum Havuzu

Yapay zekânın (ya da herhangi birinin) yazdığı Vash programını **okumadan, güvenle** çalıştırmak için.

```powershell
vash kum program.vash                                   # hiçbir izin yok: sadece hesap yapar, ekrana yazar
vash kum --izin files --klasor C:\veri program.vash     # dosyalar sadece C:\veri içinde
vash kum --izin files+net --sure 60 program.vash        # birden çok izin + ile; süre saniye (varsayılan 30)
```

## Neyi garanti eder?

| Kural | Nasıl |
|---|---|
| Program sadece verilen izinleri kullanır | Derleyici programın kullandığı her izni kesin bilir (fonksiyonların `use` satırları, ana programdaki çağrılar, lambdalar, `start`, `parallel`, `window`). Fazlası varsa program **hiç derlenmez**. |
| Programın kendi C kodu olamaz | Kullanıcının dosyalarında `extern` yasak. Sadece Vash'ın hazır modülleri C'ye bağlanır. |
| Sahte modül olamaz | Kum havuzunda `json`, `http` gibi hazır modüller her zaman Vash'ın kendi klasöründen yüklenir; aynı adlı bir dosya koymak işe yaramaz. |
| Dosyalar klasörle sınırlı | `files` izniyle bile program sadece `--klasor` içinde okuyup yazar. `../`, tam yol (`C:/Windows/...`), ağ yolu, `dosya:gizli` gibi ek akışlar programı durdurur. Klasör verilmezse programın kendi klasörü. |
| Süre sınırı | Süre dolunca program (ve açabileceği her şey) durdurulur; çıkış kodu 124. |
| Başka program açamaz, belleği sınırlı | Program bir Windows "iş nesnesi" içinde çalışır: en fazla 1 süreç, en fazla 2 GB bellek. |

İzinler: `files` (dosya), `net` (internet), `system` (komut çalıştırma, sistem bilgisi), `screen` (pencere/grafik), `sound` (ses), `time` (saat).

## Claude ile

Bu klasörde açılan Claude Code oturumlarında `vash-kum` MCP aracı vardır (`.mcp.json`):

- `vash_calistir(kod, izinler, klasor, sure, argumanlar)`: kodu kum havuzunda çalıştırır; çıktı, çıkış kodu ve kullanılan izinler döner.
- `vash_denetle(kod, izinler)`: çalıştırmadan denetler, kullanılan izinleri söyler.
- `vash_tarifi()`: dilin tek sayfalık tarifi.

Örnek: "Şu klasördeki satış CSV'lerini topla" dediğinde Claude bir Vash programı yazar ve onu sadece `files` izniyle, sadece o klasöre dokunacak şekilde çalıştırır.

## Sınırlar (dürüstçe)

- Bu bir **dil düzeyi** kum havuzudur, sanal makine değil. Güvence, derleyicinin ve Vash çalışma kütüphanesinin doğruluğuna dayanır.
- Klasör sınırı Vash'ın dosya fonksiyonları içindir (`read_file`, `write_file`, `read_bytes`, ...). `screen` izni verilirse grafik modülü resim/ses dosyalarını kendi yükler; bu yüklemeler klasörle sınırlı değildir.
- Klasörün içinde önceden konmuş bir "bağlantı" (junction/symlink) varsa o başka yere çıkabilir; Vash programları bağlantı oluşturamaz.
- `net` izni verilirse program internetteki her adrese bağlanabilir (adres sınırı henüz yok).
- Denemeler: `test/kum/` (izinsiz dosya, gizli fonksiyonda internet, lambda/`start` ile gizleme, kendi C kodu, sahte modül, `../` ve tam yol ile kaçma, ek akış, sonsuz döngü).
