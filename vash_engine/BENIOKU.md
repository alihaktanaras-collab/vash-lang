# Vash Engine

Vash diliyle yazılmış 2B oyun motoru ve düzenleyicisi. Düzenleyici 2 MB'lık tek bir program; çıkan oyunlar ~2 MB.

## Açmak

`baslat.cmd` dosyasına çift tıkla. İlk açılışta düzenleyici derlenir (birkaç saniye) ve örnek oyun "Altın Avcısı" açılır.
Başka bir oyun açmak için: `baslat.cmd yol\oyun.json`

## Düzenleyici

| Yer | Ne işe yarar |
|---|---|
| Sol | Sahnedeki nesneler. **Ekle** ile kutu, resim ya da yazı eklenir. En üstte **Sahne ayarları**. |
| Orta | Sahne. Nesneyi sürükle, sağ alt köşesinden boyutlandır. Tekerlek: yakınlaştır. Sağ tuş ya da boş yeri sürükle: kaydır. Shift: ızgaraya yapışmadan taşı. |
| Sağ | Seçili nesnenin ayarları ve **davranışları** (kod yazmadan: platform karakteri, düşman, toplanır, bitiş...). |
| Üst | **Oyna** (içeride oynatır), **Kodla çalıştır** (oyna.vash ile), **Dışa aktar** (.exe + güvenlik kartı), **Kaydet**. |

Kısayollar: Ctrl+S kaydet · Ctrl+Z geri al · Ctrl+Y yinele · Ctrl+D çoğalt · Delete sil · F5 oyna · Esc durdur.

## Zaman makinesi

Oynarken alttaki çubukla oyunu **geri sarabilirsin** (son 10 saniye). "Geri sar"ı basılı tut ya da çubuğu sürükle; P duraklatır.
Duraklatınca bir nesneye tıkla: o andaki konumu, hızı, yerde olup olmadığı sağda görünür. Hatayı bulup oradan devam edebilirsin.

## Güvenlik kartı

**Dışa aktar** oyunu `.exe` yapar, sonra Vash derleyicisi kodu inceler ve oyunun neler yapabildiğini gösterir
(ekran, ses, dosya, internet, komut çalıştırma). Kart oyunun yanına `GUVENLIK.txt` olarak da yazılır.
Bunu derleyici kodun kendisinden çıkarır; tahmin değildir. Kendi kodu olmayan oyunlar "sadece hazır davranışlar" diye işaretlenir.

## Claude ile oyun yapmak

Düzenleyici açıkken Claude Code (bu proje klasöründe) `vash-engine` MCP araçlarıyla düzenleyiciye bağlanır:
"başlangıca bir kurbağa düşman ekle", "üçüncü bölümü zorlaştır", "altınlara ses ekle" gibi istekleri
sahneyi okuyup değiştirerek yapar, ekran görüntüsüyle kontrol eder. Her değişiklik Ctrl+Z ile geri alınır.
Köprü sadece bu bilgisayara açıktır (127.0.0.1:7377).

## Kendi kodunla

Oyunun klasöründeki `oyna.vash` normal bir Vash programıdır:

```vash
import engine
import graphics

var g = engine.load("oyun.json") else: engine.Game()
engine.open(g, g.title)
g.prepare(g.folder)
repeat while graphics.is_open() {
    g.update(graphics.frame_time())
    if g.score >= 100 and g.message.length is 0 {
        g.say("100 altın!", 2.0)
    }
    g.show()
}
graphics.close_window()
```

## Sky Forts Mini

`ornekler/skyforts_mini/oyun.vash`: gökyüzündeki adanda izometrik üs kurma oyunu (kod ile yazılmış bir Vash oyunu).
Aşağıdaki karttan bina seç, adaya koy; inşaat bitince baloncuğa tıklayıp kaynak topla, binaları yükselt.
Tekerlek: yakınlaştır · sürükle: kaydır · sağ tık / Esc: vazgeç. Oyun kapalıyken de binalar üretir (kayit.json).

```powershell
cd vash_engine\ornekler\skyforts_mini; ..\..\..\vash.cmd build oyun.vash; .\oyun.exe
```

## Dosyalar

- `duzenleyici.vash` düzenleyici · `arayuz.vash` arayüz parçaları · `../std/engine.vash` motor
- `ornekler/platform/` örnek oyun (`oyun.json`, `resimler/`, `sesler/`, `oyna.vash`)
- `araclar/piksel_uret.py` örneğin piksel sanatını ve seslerini üretir · `araclar/seviye_uret.py` ilk bölümü üretir
- `araclar/vash_mcp.py` Claude köprüsü (MCP sunucusu)
