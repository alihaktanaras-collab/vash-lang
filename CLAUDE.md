# Vash projesi — çalışma kuralları

## 1. DİL: HER ŞEY TÜRKÇE (en önemli kural)
Kullanıcıya görünen her yazı Türkçe olmalı. İstisna yok:
- ara açıklamalar ("şimdi şunu deniyorum...") ve kapanış mesajı
- sonraki adım kutusu (wrap_up özeti, sorusu, buton yazıları)
- görev listesi adımları, sorular ve seçenekleri
- uzun bir işin sonunda ya da konuşma özetlendikten sonra da

Bu kural üç kez çiğnendi; kullanıcı haklı olarak çok rahatsız oldu. Her mesajı göndermeden önce dilini kontrol et.

## 2. Çok basit anlat
Kullanıcı terim bilmiyor. Her şeyi günlük dille, kısa ve sade anlat; teknik terim gerekirse ne demek olduğunu söyle.

## 3. Kararları birlikte al
Dilin söz dizimi ya da yeni bir özellikle ilgili her kararı kullanıcıya sor (basit seçeneklerle, önerilen seçenek ilk sırada).

## Proje hakkında
- `VASH_SPEC.md`: dilin tek sayfalık tarifi — Vash kodu yazmadan önce oku. Dil değişince güncelle ve `python vashc/spec_dene.py` ile sına.
- Vash kodu yazınca: `vash check --json dosya.vash` → `ok: true` olana kadar düzelt.
- `TASARIM.md`: dilin bütün kararları ve ilerleme tablosu
- `derleyici/`: Python'daki ilk derleyici · `vashc/`: Vash ile yazılmış derleyici (kendini derleyebiliyor)
- `vash run/build/ir dosya.vash`: Vash derleyicisiyle çalışır · `vash py ...`: eski Python derleyicisi
- `arayuz/`: tarayıcıdaki atölye (`python arayuz/sunucu.py`) — derleyici değişince yeniden başlat
- Karşılaştırma testleri: `python vashc/karsilastir_*.py`, `python vashc/kendini_derle.py`
- Hata mesajları iki dilde: derleyicide `dil.sec("Türkçe", "English")` (vashc/dil.vash), çalışma kütüphanesinde `MESAJ("Türkçe", "English")` (calisma.c). Yeni mesaj yazarken ikisini de yaz; Türkçe metni değiştirme (karşılaştırma testleri eski derleyicinin Türkçe çıktısıyla karşılaştırır). Dil: `VASH_DIL=tr|en`, yoksa Windows'un dili; `check --json` ayar yoksa İngilizce.
