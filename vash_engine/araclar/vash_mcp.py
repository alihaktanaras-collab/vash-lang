# Vash Engine MCP sunucusu: Claude Code'un açık düzenleyiciyle konuşmasını sağlar.
# Düzenleyici 127.0.0.1:7377'de (sadece bu bilgisayar) dinler; bu sunucu araçları ona iletir.
# Ek kütüphane gerekmez. Claude Code bunu .mcp.json ile başlatır.
import base64, json, os, subprocess, sys, tempfile, urllib.request, urllib.error

ADRES = 'http://127.0.0.1:7377'
KOK = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
VASH = os.path.join(KOK, 'vash.cmd')
SPEC = os.path.join(KOK, 'VASH_SPEC.md')

def istek(yol, govde=None):
    veri = None if govde is None else govde.encode('utf-8')
    r = urllib.request.Request(ADRES + yol, data=veri, method='POST' if govde is not None else 'GET')
    try:
        with urllib.request.urlopen(r, timeout=15) as c:
            return c.read().decode('utf-8')
    except urllib.error.HTTPError as h:
        return f'HATA {h.code}: ' + h.read().decode('utf-8', 'replace')
    except Exception as e:
        raise RuntimeError('Düzenleyiciye bağlanılamadı. Vash Engine düzenleyicisi açık mı? (' + str(e) + ')')

DAVRANISLAR = '''Davranışlar (behaviors[].kind; alanlar: speed, power, value, sound):
- platformer: oyuncu; ok tuşları/A-D ile yürür (speed), Boşluk/W/Yukarı ile zıplar (power)
- topdown: dört yöne yürür (speed)
- gravity: düşer, katı (solid) nesnelere konar
- patrol: sağa sola yürür (speed), duvarda ve kenarda döner
- enemy: değerse oyuncu baştan başlar (value: vurma sesi), üstüne basılınca ezilir (power: puan, sound: ezilme sesi)
- danger: değince oyuncu baştan başlar (sound)
- collect: oyuncu alınca puan + power (sound)
- goal: oyuncu değince oyun biter, value mesajı gösterilir (sound)
- float: aşağı yukarı süzülür (speed, power = yükseklik)
- camera: kamera bunu izler (yoksa oyuncuyu)
Nesne (things[]): name, kind (box|image|text), x, y, width, height, color ("#rrggbb"), image ("resimler/x.png"),
frames (resimde yan yana kare sayısı), frame_speed, tiled (zemin gibi tekrarla; 1. kare üst sıra, 2. kare alt sıralar),
label ({score} puanı gösterir), text_size, on_screen (ekranda sabit yazı), layer (büyük önde), solid, hidden, behaviors.
Oyun: title, view_width/height, world_width/height, sky_top, sky_bottom, gravity, pixel_scale (resim pikseli kaç ekran pikseli), layers[] (image, speed 0..1, y).
Bir karo = 16 piksel x pixel_scale (genelde 48). Platform karakteri resmi: 1. kare durma, ortadakiler koşma, son kare zıplama.'''

ARACLAR = [
    {'name': 'sahne_oku', 'description': 'Açık düzenleyicideki sahnenin tamamını JSON olarak verir. ' + DAVRANISLAR,
     'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'sahne_yaz', 'description': 'Sahnenin TAMAMINI verilen JSON ile değiştirir (sahne_oku ile alıp düzenleyerek gönder). Düzenleyicide Ctrl+Z ile geri alınabilir.',
     'inputSchema': {'type': 'object', 'properties': {'sahne': {'type': 'string', 'description': 'Sahnenin tam JSON metni'}}, 'required': ['sahne']}},
    {'name': 'ekran_goruntusu', 'description': 'Düzenleyicinin şu anki görüntüsünü resim olarak verir.',
     'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'durum', 'description': 'Açık proje: dosya, klasör, seçili nesne, oynuyor mu, kullanılabilir resim ve ses dosyaları.',
     'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'mesaj_goster', 'description': 'Düzenleyicinin alt çubuğunda kısa bir mesaj gösterir (ne yaptığını söylemek için).',
     'inputSchema': {'type': 'object', 'properties': {'metin': {'type': 'string'}}, 'required': ['metin']}},
    {'name': 'sec', 'description': 'Adı verilen nesneyi düzenleyicide seçer.',
     'inputSchema': {'type': 'object', 'properties': {'ad': {'type': 'string'}}, 'required': ['ad']}},
    {'name': 'oyna', 'description': 'Oyunu düzenleyicinin içinde başlatır (durdur ile durur).',
     'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'durdur', 'description': 'Oynayan oyunu durdurur.', 'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'kaydet', 'description': 'Sahneyi dosyasına kaydeder.', 'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'vash_kontrol', 'description': 'Vash kodunu derleyiciyle denetler (çalıştırmaz). Hata varsa satır ve açıklamasını verir. Kod yazmadan önce vash_tarifi ile dili öğren.',
     'inputSchema': {'type': 'object', 'properties': {'kod': {'type': 'string'}}, 'required': ['kod']}},
    {'name': 'vash_tarifi', 'description': 'Vash dilinin tek sayfalık tarifi (VASH_SPEC.md).', 'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'oyun_kodu_yaz', 'description': 'Projenin oyna.vash dosyasını yazar (önce derleyiciyle denetler; hata varsa yazmaz). Oyuna kendi Vash kodunu eklemek için. engine modülü: engine.load, engine.open, game.prepare, game.update, game.find, game.things[i], game.say, game.show.',
     'inputSchema': {'type': 'object', 'properties': {'kod': {'type': 'string'}}, 'required': ['kod']}},
]

def kontrol(kod, klasor=None):
    k = klasor or tempfile.mkdtemp()
    yol = os.path.join(k, '_vash_mcp_kontrol.vash')
    with open(yol, 'w', encoding='utf-8') as f:
        f.write(kod)
    try:
        r = subprocess.run(['cmd', '/c', VASH, 'check', '--json', yol], capture_output=True, text=True, encoding='utf-8', timeout=120)
        return r.stdout.strip() or r.stderr.strip()
    finally:
        os.remove(yol)

def calistir(ad, a):
    if ad == 'sahne_oku':
        return [{'type': 'text', 'text': istek('/sahne')}]
    if ad == 'sahne_yaz':
        return [{'type': 'text', 'text': istek('/sahne', a['sahne'])}]
    if ad == 'ekran_goruntusu':
        yol = istek('/ekran')
        if yol.startswith('HATA'):
            return [{'type': 'text', 'text': yol}]
        with open(yol, 'rb') as f:
            return [{'type': 'image', 'data': base64.b64encode(f.read()).decode(), 'mimeType': 'image/png'}]
    if ad == 'durum':
        return [{'type': 'text', 'text': istek('/durum')}]
    if ad == 'mesaj_goster':
        return [{'type': 'text', 'text': istek('/mesaj', a['metin'])}]
    if ad == 'sec':
        return [{'type': 'text', 'text': istek('/sec', a['ad'])}]
    if ad in ('oyna', 'durdur', 'kaydet'):
        return [{'type': 'text', 'text': istek('/' + ad, '')}]
    if ad == 'vash_kontrol':
        return [{'type': 'text', 'text': kontrol(a['kod'])}]
    if ad == 'vash_tarifi':
        with open(SPEC, encoding='utf-8') as f:
            return [{'type': 'text', 'text': f.read()}]
    if ad == 'oyun_kodu_yaz':
        d = json.loads(istek('/durum'))
        klasor = d['folder']
        sonuc = kontrol(a['kod'], klasor)
        if '"ok": true' not in sonuc:
            return [{'type': 'text', 'text': 'Yazılmadı, kodda hata var: ' + sonuc}]
        with open(os.path.join(klasor, 'oyna.vash'), 'w', encoding='utf-8') as f:
            f.write(a['kod'])
        return [{'type': 'text', 'text': 'oyna.vash yazıldı. ' + sonuc}]
    raise RuntimeError('Bilinmeyen araç: ' + ad)

def gonder(m):
    sys.stdout.write(json.dumps(m, ensure_ascii=False) + '\n')
    sys.stdout.flush()

def main():
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    for satir in sys.stdin:
        satir = satir.strip()
        if not satir:
            continue
        try:
            m = json.loads(satir)
        except Exception:
            continue
        yontem = m.get('method')
        no = m.get('id')
        if no is None:
            continue                      # bildirim (ör. notifications/initialized)
        try:
            if yontem == 'initialize':
                surum = m.get('params', {}).get('protocolVersion', '2025-06-18')
                sonuc = {'protocolVersion': surum, 'capabilities': {'tools': {}},
                         'serverInfo': {'name': 'vash-engine', 'version': '0.1.0'},
                         'instructions': 'Vash Engine düzenleyicisine bağlanır: sahneyi oku/değiştir, ekran görüntüsü al, oyunu oynat. Önce durum ve sahne_oku ile bak; değiştirdikten sonra ekran_goruntusu ile sonucu kontrol et.'}
            elif yontem == 'tools/list':
                sonuc = {'tools': ARACLAR}
            elif yontem == 'tools/call':
                p = m.get('params', {})
                try:
                    sonuc = {'content': calistir(p.get('name'), p.get('arguments') or {})}
                except Exception as e:
                    sonuc = {'content': [{'type': 'text', 'text': str(e)}], 'isError': True}
            elif yontem == 'ping':
                sonuc = {}
            else:
                gonder({'jsonrpc': '2.0', 'id': no, 'error': {'code': -32601, 'message': 'Bilinmeyen yöntem: ' + str(yontem)}})
                continue
            gonder({'jsonrpc': '2.0', 'id': no, 'result': sonuc})
        except Exception as e:
            gonder({'jsonrpc': '2.0', 'id': no, 'error': {'code': -32603, 'message': str(e)}})

if __name__ == '__main__':
    main()
