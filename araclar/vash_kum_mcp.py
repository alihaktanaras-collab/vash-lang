# Vash Kum Havuzu MCP sunucusu: yapay zekânın yazdığı Vash programlarını güvenle çalıştırır.
# Program sadece verilen izinleri kullanabilir (derleyici kesin denetler), dosyalara sadece verilen
# klasörde dokunabilir, süre dolunca durdurulur, başka program açamaz. Ek kütüphane gerekmez.
import json, os, shutil, subprocess, sys, tempfile

KOK = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
VASH = os.path.join(KOK, 'vash.cmd')
SPEC = os.path.join(KOK, 'VASH_SPEC.md')
EN_COK = 20000
IZINLER = ['files', 'net', 'system', 'screen', 'sound', 'time']

ACIKLAMA = ('Vash kodunu KUM HAVUZUNDA çalıştırır. Varsayılan: hiçbir izin yok (sadece hesap yapar ve yazdırır). '
            'izinler ile açıkça verilenler dışında hiçbir şey kullanılamaz: kod izin verilmeyen bir şey isterse DERLENMEZ. '
            '"files" verilirse dosyalara sadece "klasor" içinde dokunulabilir (dışarısı programı durdurur). '
            'Süre dolunca program durdurulur. Programın kendi C kodu (extern) yasaktır. '
            'Vash yazmadan önce vash_tarifi ile dilin tarifini oku. Sonuçta programın çıktısı, çıkış kodu ve kullandığı izinler döner.')

ARACLAR = [
    {'name': 'vash_calistir', 'description': ACIKLAMA,
     'inputSchema': {'type': 'object', 'properties': {
         'kod': {'type': 'string', 'description': 'Vash programı'},
         'izinler': {'type': 'array', 'items': {'type': 'string', 'enum': IZINLER}, 'description': 'Verilen izinler (varsayılan: hiçbiri)'},
         'klasor': {'type': 'string', 'description': 'files izni varsa programın dokunabileceği tek klasör (tam yol). Verilmezse boş, geçici bir klasör.'},
         'sure': {'type': 'integer', 'description': 'Saniye cinsinden süre sınırı (varsayılan 30, en çok 600)'},
         'argumanlar': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Programın args() ile okuyacağı değerler'}},
         'required': ['kod']}},
    {'name': 'vash_denetle', 'description': 'Vash kodunu çalıştırmadan derleyiciyle denetler (kum havuzu kurallarıyla). Hatasızsa kodun kullandığı izinleri söyler.',
     'inputSchema': {'type': 'object', 'properties': {
         'kod': {'type': 'string'},
         'izinler': {'type': 'array', 'items': {'type': 'string', 'enum': IZINLER}}},
         'required': ['kod']}},
    {'name': 'vash_tarifi', 'description': 'Vash dilinin tek sayfalık tarifi (VASH_SPEC.md). Vash yazmadan önce oku.',
     'inputSchema': {'type': 'object', 'properties': {}}},
]

def _cmd(args):
    # cmd.exe boşluklu birden çok tırnaklı parçada karışır: /s /c "..." ile bütün komutu bir kat daha tırnağa al
    return 'cmd /s /c "' + subprocess.list2cmdline(args) + '"'

def _ortam(izinler):
    o = dict(os.environ)
    o['VASH_KUM'] = '1'
    o['VASH_KUM_IZIN'] = '+'.join(izinler)
    o['VASH_DIL'] = o.get('VASH_DIL', 'tr')
    return o

def _kisalt(t):
    return t if len(t) <= EN_COK else t[:EN_COK] + f'\n... ({len(t) - EN_COK} karakter daha kesildi)'

def _izinleri_dogrula(izinler):
    for i in izinler:
        if i not in IZINLER:
            raise ValueError(f"'{i}' diye bir izin yok. İzinler: {', '.join(IZINLER)}")

def denetle(kod, izinler):
    _izinleri_dogrula(izinler)
    gecici = tempfile.mkdtemp(prefix='vash_kum_')
    try:
        yol = os.path.join(gecici, 'program.vash')
        with open(yol, 'w', encoding='utf-8') as f:
            f.write(kod)
        r = subprocess.run(_cmd([VASH, 'check', '--json', yol]), capture_output=True, text=True,
                           encoding='utf-8', errors='replace', env=_ortam(izinler), timeout=120)
        return r.stdout.strip() or r.stderr.strip()
    finally:
        shutil.rmtree(gecici, ignore_errors=True)

def calistir(kod, izinler, klasor, sure, argumanlar):
    _izinleri_dogrula(izinler)
    sure = max(1, min(int(sure or 30), 600))
    gecici = tempfile.mkdtemp(prefix='vash_kum_')
    try:
        yol = os.path.join(gecici, 'program.vash')
        with open(yol, 'w', encoding='utf-8') as f:
            f.write(kod)
        alan = klasor or os.path.join(gecici, 'alan')
        if not klasor:
            os.makedirs(alan, exist_ok=True)
        if not os.path.isdir(alan):
            return f'Klasör yok: {alan}', True
        # önce denetle: izinleri öğren
        d = denetle(kod, izinler)
        try:
            dj = json.loads(d)
        except Exception:
            dj = None
        if not dj or not dj.get('ok'):
            return 'DERLENMEDİ (kum havuzu ya da kod hatası):\n' + d, True
        komut = [VASH, 'kum']
        if izinler:
            komut += ['--izin', '+'.join(izinler)]
        komut += ['--klasor', alan, '--sure', str(sure), yol] + list(argumanlar or [])
        r = subprocess.run(_cmd(komut), capture_output=True, text=True, encoding='utf-8', errors='replace',
                           env=_ortam(izinler), timeout=sure + 180)
        cikti = (r.stdout or '') + (('\n' + r.stderr) if r.stderr.strip() else '')
        ozet = f"\n---\nçıkış kodu: {r.returncode}   kullanılan izinler: {', '.join(dj.get('permissions', [])) or 'hiçbiri'}   klasör: {alan if klasor else '(geçici, silindi)'}"
        return _kisalt(cikti.strip()) + ozet, r.returncode != 0
    finally:
        shutil.rmtree(gecici, ignore_errors=True)

def arac(ad, a):
    if ad == 'vash_calistir':
        metin, hata = calistir(a['kod'], a.get('izinler') or [], a.get('klasor') or '', a.get('sure') or 30, a.get('argumanlar') or [])
        return {'content': [{'type': 'text', 'text': metin}], 'isError': hata}
    if ad == 'vash_denetle':
        return {'content': [{'type': 'text', 'text': denetle(a['kod'], a.get('izinler') or [])}]}
    if ad == 'vash_tarifi':
        with open(SPEC, encoding='utf-8') as f:
            return {'content': [{'type': 'text', 'text': f.read()}]}
    raise ValueError('Bilinmeyen araç: ' + str(ad))

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
        no = m.get('id')
        if no is None:
            continue
        yontem = m.get('method')
        try:
            if yontem == 'initialize':
                sonuc = {'protocolVersion': m.get('params', {}).get('protocolVersion', '2025-06-18'),
                         'capabilities': {'tools': {}}, 'serverInfo': {'name': 'vash-kum', 'version': '0.1.0'},
                         'instructions': 'Kod çalıştırman gerektiğinde (hesap, veri işleme, dosya analizi) Vash yaz ve vash_calistir ile kum havuzunda çalıştır. Sadece gereken izinleri ver; dosya gerekiyorsa klasörü kullanıcının verdiği klasörle sınırla.'}
            elif yontem == 'tools/list':
                sonuc = {'tools': ARACLAR}
            elif yontem == 'tools/call':
                p = m.get('params', {})
                try:
                    sonuc = arac(p.get('name'), p.get('arguments') or {})
                except Exception as e:
                    sonuc = {'content': [{'type': 'text', 'text': str(e)}], 'isError': True}
            elif yontem == 'ping':
                sonuc = {}
            else:
                gonder({'jsonrpc': '2.0', 'id': no, 'error': {'code': -32601, 'message': 'Bilinmeyen yöntem'}})
                continue
            gonder({'jsonrpc': '2.0', 'id': no, 'result': sonuc})
        except Exception as e:
            gonder({'jsonrpc': '2.0', 'id': no, 'error': {'code': -32603, 'message': str(e)}})

if __name__ == '__main__':
    main()
