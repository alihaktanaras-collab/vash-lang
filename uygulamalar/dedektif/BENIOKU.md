# Vash Dedektif

Vash ile yazılmış tek dosyalık (~2 MB) bir Windows uygulaması. `baslat.cmd` dosyasına çift tıkla.

## Disk sekmesi

- Bir sürücü ya da klasör seç, **Tara**'ya bas. Tarama bütün işlemci çekirdeklerine bölünür.
- **Ağaç haritası:** her kutu bir klasör, büyüklüğü kapladığı yer. Kutuya tıkla, içine gir; ↑ ile geri çık.
- **Büyük dosyalar:** 50 MB'tan büyükler, büyükten küçüğe. Tıkla: Dosya Gezgini'nde göster.
- **Unity:** taranan yerdeki Unity projeleri ve `Library` önbellekleri. **Çöpe taşı** klasörü Geri Dönüşüm Kutusu'na taşır
  (geri alınabilir); Unity projeyi bir sonraki açışta yeniden oluşturur.
- **Kopyalar:** aynı içerikli dosyalar (5 MB'tan büyük). Önce boyut, sonra dosyanın başı ve sonu,
  en son bütün içerik karşılaştırılır (çok çekirdekte).

## Unity projeleri sekmesi

Bilgisayardaki Unity projelerini kendisi bulur. Birine tıkla, röntgeni çekilir:
- Proje boyutu, varlık sayısı, script satırı
- Türlere göre boyut (resim, ses, model, ...)
- **Kullanılmıyor olabilir:** hiçbir sahne, prefab, materyal ya da ayar dosyasının kimliğiyle (GUID) anmadığı varlıklar.
  Kodla yüklenebilenler (Resources, StreamingAssets, Editor, Plugins, scriptler, shaderlar, ışık haritaları) sayılmaz.
  Yine de silmeden önce bak: kod içinden adıyla yüklenen bir şey olabilir.
- **Telefon uyarıları:** 2048 pikselden büyük dokular, sıkıştırılmamış büyük dokular, büyük WAV sesler, çok büyük modeller ve videolar.

## Ölçümler (bu bilgisayarda, 16 çekirdek)

| İş | Vash | Karşılaştırma |
|---|---|---|
| Kullanıcı klasörü: 854 bin dosya, 107 bin klasör | 20,9 sn (ilk), ~11 sn (sonraki) | Python `os.walk` + `os.stat`: 163,7 sn |
| Belgeler: 251 bin dosyada kopya arama (110 grup, 4,8 GB) | 0,6 sn (dosyalar bellekteyken) | ilk yöntem (tek çekirdek, yavaş iz): 96,6 sn |
| KorkuOyunu röntgeni (226 varlık) | 0,4–2,8 sn | |

## Dosyalar

- `dedektif.vash` uygulama · `tarama.vash` çok çekirdekli tarama ve kopyalar · `unity.vash` Unity röntgeni · `arayuz.vash` arayüz parçaları
- `hiz_olc.vash`, `kopya_olc.vash`, `unity_olc.vash`: penceresiz ölçüm programları
- Vash'a eklenenler: `std/fs.vash` (klasör okuma, parmak izi, çöpe taşıma, disk bilgisi, Gezgin'de gösterme)
