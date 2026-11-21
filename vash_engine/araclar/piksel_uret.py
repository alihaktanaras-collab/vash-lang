# Platform örneği için piksel sanat resimleri (PNG) ve 8-bit sesleri (WAV) üretir.
# Ek kütüphane gerekmez:  python vash_engine/araclar/piksel_uret.py
import math, os, random, struct, wave, zlib

KOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ornekler', 'platform')
RESIM = os.path.join(KOK, 'resimler')
SES = os.path.join(KOK, 'sesler')
os.makedirs(RESIM, exist_ok=True)
os.makedirs(SES, exist_ok=True)

def hx(s, a=255):
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)

# Sweetie 16 paleti
P = {
    'k': hx('1a1c2c'), 'm': hx('5d275d'), 'r': hx('b13e53'), 'o': hx('ef7d57'),
    'y': hx('ffcd75'), 'l': hx('a7f070'), 'g': hx('38b764'), 't': hx('257179'),
    'n': hx('29366f'), 'b': hx('3b5dc9'), 'c': hx('41a6f6'), 'a': hx('73eff7'),
    'w': hx('f4f4f4'), 's': hx('94b0c2'), 'd': hx('566c86'), 'e': hx('333c57'),
    'p': hx('ffd6a5'),   # ten
    'h': hx('7a4a2a'),   # saç / kahverengi
    'u': hx('9a6236'),   # açık kahve (toprak)
    'v': hx('5a3a22'),   # koyu kahve
    '.': (0, 0, 0, 0),
}

def png_yaz(ad, w, h, pikseller):
    satirlar = b''
    for y in range(h):
        satirlar += b'\x00' + b''.join(bytes(pikseller[y][x]) for x in range(w))
    def parca(tur, veri):
        return struct.pack('>I', len(veri)) + tur + veri + struct.pack('>I', zlib.crc32(tur + veri) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    with open(os.path.join(RESIM, ad), 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + parca(b'IHDR', ihdr) + parca(b'IDAT', zlib.compress(satirlar, 9)) + parca(b'IEND', b''))

def bos(w, h):
    return [[(0, 0, 0, 0) for _ in range(w)] for _ in range(h)]

def izgara(satirlar):
    return [[P[c] for c in s] for s in satirlar]

def cerceve_ekle(img, renk=P['k']):
    """Boş komşusu olan dolu piksellerin dışına 1 piksel koyu çizgi çizer."""
    h, w = len(img), len(img[0])
    yeni = [row[:] for row in img]
    for y in range(h):
        for x in range(w):
            if img[y][x][3] == 0:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and img[ny][nx][3] > 0 and img[ny][nx] != renk:
                        yeni[y][x] = renk
                        break
    return yeni

def yan_yana(kareler):
    h = len(kareler[0])
    return [sum((k[y] for k in kareler), []) for y in range(h)]

# ---------------- Karakter (16x16, 6 kare: dur, 4 koşu, zıpla) ----------------
UST = [
    "................",
    "................",
    "......rrrr......",
    ".....rrrrrr.....",
    ".....rrrrrrrrr..",
    ".....hhpppkp....",
    ".....hppppkp....",
    "......pppppp....",
    "......pppp......",
    ".....rrrrrr.....",
    "....prrrrrrp....",
    "....prrwwrrp....",
]
BACAK = {
    'dur': [
        ".....bbbbbb.....",
        ".....bb..bb.....",
        ".....hh..hh.....",
        "................",
    ],
    'adim1': [
        ".....bbbbbb.....",
        "....bb....bb....",
        "...hh......hh...",
        "................",
    ],
    'gec': [
        "......bbbb......",
        "......bbbb......",
        "......hhhh......",
        "................",
    ],
    'adim2': [
        ".....bbbbbb.....",
        ".....bb..bbb....",
        "....hh....hh....",
        "................",
    ],
    'zipla': [
        ".....bbbbbb.....",
        "....bb...bb.....",
        "...hh....hh.....",
        "................",
    ],
}

def karakter(bacak, yukari=0, kollar_yukari=False):
    ust = list(UST)
    if kollar_yukari:
        ust[9] = "...prrrrrrp....."
        ust[10] = "....rrrrrrr....."
        ust[11] = ".....rrwwrr....."
    satirlar = ust + BACAK[bacak]
    if yukari:
        satirlar = satirlar[yukari:] + ["................"] * yukari
    return cerceve_ekle(izgara(satirlar))

oyuncu = [karakter('dur'), karakter('adim1'), karakter('gec', 1), karakter('adim2'), karakter('gec', 1), karakter('zipla', 0, True)]
png_yaz('oyuncu.png', 16 * 6, 16, yan_yana(oyuncu))

# ---------------- Zemin (16x16, 2 kare: çimen üstü, toprak) ----------------
rnd = random.Random(7)
def toprak(img, bas):
    for y in range(bas, 16):
        for x in range(16):
            r = rnd.random()
            img[y][x] = P['u'] if r > 0.18 else P['v']
            if r > 0.97:
                img[y][x] = P['o']
    for _ in range(3):                      # taşlar
        x, y = rnd.randrange(1, 14), rnd.randrange(max(bas + 2, 5), 14)
        img[y][x] = P['s']; img[y][x + 1] = P['d']
    return img

ust = toprak(bos(16, 16), 4)
for x in range(16):
    for y in range(0, 4):
        ust[y][x] = P['g']
    ust[0][x] = P['l']
    if x % 3 == 0:
        ust[1][x] = P['l']
    if rnd.random() > 0.5:                   # sarkan çimen
        ust[4][x] = P['g']
        if rnd.random() > 0.6:
            ust[5][x] = P['t']
alt = toprak(bos(16, 16), 0)
png_yaz('zemin.png', 32, 16, yan_yana([ust, alt]))

# ---------------- Taş platform (16x16, 2 kare) ----------------
def tugla(ust_kat):
    img = bos(16, 16)
    for y in range(16):
        for x in range(16):
            img[y][x] = P['d']
    for y in range(16):
        kay = 0 if (y // 4) % 2 == 0 else 4
        for x in range(16):
            if y % 4 == 3 or (x + kay) % 8 == 7:
                img[y][x] = P['e']
            elif y % 4 == 0:
                img[y][x] = P['s']
    if ust_kat:
        for x in range(16):
            img[0][x] = P['w']; img[1][x] = P['s']
    return img
png_yaz('tas.png', 32, 16, yan_yana([tugla(True), tugla(False)]))

# ---------------- Altın (16x16, 6 kare: dönüyor) ----------------
def altin(gen):
    img = bos(16, 16)
    cx, cy, ry = 7.5, 7.5, 6.5
    rx = max(gen / 2.0, 0.6)
    for y in range(16):
        for x in range(16):
            d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if d <= 1.0:
                img[y][x] = P['y'] if d < 0.55 else P['o']
                if x < cx - rx * 0.3 and y < cy and d < 0.5:
                    img[y][x] = P['w']
    return cerceve_ekle(img, P['m'])
png_yaz('altin.png', 16 * 6, 16, yan_yana([altin(g) for g in (13, 10, 6, 2, 6, 10)]))

# ---------------- Sümük düşman (16x16, 3 kare) ----------------
def sumuk(bas):
    img = bos(16, 16)
    cx = 7.5
    ust = 5 + bas
    for y in range(ust, 16):
        for x in range(16):
            yy = (y - 15) / (15 - ust + 0.01)
            xx = (x - cx) / (7.0 + bas * 0.4)
            if xx * xx + yy * yy <= 1.0:
                img[y][x] = P['g']
                if yy < -0.55:
                    img[y][x] = P['l']
    gy = ust + 4
    for gx in (5, 10):
        if 0 <= gy < 16:
            img[gy][gx] = P['w']; img[gy][gx + 1 if gx == 5 else gx - 1] = P['w']
            img[gy + 1][gx] = P['k']
    if gy + 3 < 16:
        img[gy + 3][7] = P['t']; img[gy + 3][8] = P['t']
    img[ust + 1][4] = P['w']
    return cerceve_ekle(img, P['t'])
png_yaz('sumuk.png', 48, 16, yan_yana([sumuk(0), sumuk(1), sumuk(2)]))

# ---------------- Diken (16x16) ----------------
diken = bos(16, 16)
for t in range(4):
    for y in range(8, 16):
        yari = (y - 8) / 2.0
        for x in range(t * 4, t * 4 + 4):
            if abs(x - (t * 4 + 1.5)) <= yari + 0.01:
                diken[y][x] = P['s'] if x <= t * 4 + 1 else P['d']
    diken[8][t * 4 + 1] = P['w']
for x in range(16):
    diken[15][x] = P['e']
png_yaz('diken.png', 16, 9, cerceve_ekle(diken)[7:16])    # sadece dikenli alt kısım

# ---------------- Bayrak (16x32, 3 kare: dalgalanıyor) ----------------
def bayrak(faz):
    img = bos(16, 32)
    for y in range(2, 32):
        img[y][2] = P['s']; img[y][3] = P['d']
    img[1][2] = P['y']; img[1][3] = P['y']; img[0][2] = P['o']
    for x in range(4, 15):
        dal = int(round(math.sin((x - 4) * 0.7 + faz) * 1.2))
        for y in range(3, 11):
            yy = y + dal
            if 0 <= yy < 32:
                img[yy][x] = P['r'] if y < 7 else P['o']
                if y in (6, 7) and 7 <= x <= 10:
                    img[yy][x] = P['w']
    for y in range(28, 32):
        for x in range(0, 6):
            img[y][x] = P['d'] if y > 28 else P['s']
    return cerceve_ekle(img)
png_yaz('bayrak.png', 48, 32, yan_yana([bayrak(0.0), bayrak(2.1), bayrak(4.2)]))

# ---------------- Arka plan katmanları (yatayda dikişsiz) ----------------
def katman(w, h, yukseklik_fn, renk_fn):
    img = bos(w, h)
    for x in range(w):
        tepe = yukseklik_fn(x)
        for y in range(h):
            if y >= tepe:
                img[y][x] = renk_fn(x, y, tepe)
    return img

W = 240
def dag_y(x):
    a = 2 * math.pi * x / W
    return 18 + 14 * math.sin(a * 2 + 0.5) + 8 * math.sin(a * 5 + 1.3) + 3 * math.sin(a * 11)
def dag_renk(x, y, tepe):
    if y - tepe < 3 and tepe < 14:
        return P['w']
    golge = dag_y(x + 1) < tepe                 # sağa doğru inen yamaç gölgede
    if golge:
        return hx('8aa9cc') if not ((x + y) % 2 == 0 and y > 58) else hx('9db9d8')
    return hx('a9c6e3') if not ((x + y) % 2 == 0 and y > 58) else hx('9db9d8')
png_yaz('daglar.png', W, 70, katman(W, 70, dag_y, dag_renk))

def tepe_y(x):
    a = 2 * math.pi * x / W
    return 14 + 7 * math.sin(a * 3 + 2.0) + 4 * math.sin(a * 7)
def tepe_renk(x, y, tepe):
    if y - tepe < 2:
        return P['l']
    if y > 44 or (y > 38 and (x + y) % 2 == 0):
        return P['t']
    return P['g']
tepeler = katman(W, 60, tepe_y, tepe_renk)
for x0 in range(10, W, 37):                     # ağaçlar
    taban = int(tepe_y(x0)) + 1
    for y in range(taban - 9, taban):
        for x in range(x0 - 3, x0 + 4):
            if 0 <= y < 60 and abs(x - x0) <= (y - (taban - 9)) * 0.5 + 0.5:
                tepeler[y][x % W] = P['t'] if x >= x0 else P['g']
    for y in range(taban, min(taban + 2, 60)):
        tepeler[y][x0 % W] = P['v']
png_yaz('tepeler.png', W, 60, tepeler)

bulut = bos(W, 40)
rnd = random.Random(3)
for merkez in (30, 110, 185):
    for _ in range(6):
        cx = merkez + rnd.randint(-14, 14)
        cy = 22 + rnd.randint(-5, 4)
        r = rnd.randint(6, 10)
        for y in range(40):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    bulut[y][x % W] = P['w'] if y < cy + r * 0.4 else hx('cfe3ee')
png_yaz('bulutlar.png', W, 40, bulut)

# ---------------- 8-bit sesler ----------------
def wav_yaz(ad, ornekler, hz=22050):
    with wave.open(os.path.join(SES, ad), 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(hz)
        f.writeframes(b''.join(struct.pack('<h', max(-32767, min(32767, int(s * 32767)))) for s in ornekler))

def kare_dalga(frek, sure, ses=0.25, hz=22050, kayma=0.0):
    n = int(sure * hz)
    out = []
    faz = 0.0
    for i in range(n):
        f = frek + kayma * i / n
        faz += f / hz
        v = ses if (faz % 1.0) < 0.5 else -ses
        zarf = min(1.0, (n - i) / (0.02 * hz))
        out.append(v * zarf)
    return out

def gurultu(sure, ses=0.3, hz=22050):
    r = random.Random(1)
    n = int(sure * hz)
    return [r.uniform(-ses, ses) * (1 - i / n) ** 2 for i in range(n)]

wav_yaz('altin.wav', kare_dalga(988, 0.06) + kare_dalga(1319, 0.14))
wav_yaz('ezme.wav', [a + b for a, b in zip(kare_dalga(220, 0.12, 0.25, kayma=-140), gurultu(0.12, 0.2))])
wav_yaz('ah.wav', kare_dalga(440, 0.35, 0.22, kayma=-300))
wav_yaz('kazandin.wav', kare_dalga(523, 0.1) + kare_dalga(659, 0.1) + kare_dalga(784, 0.1) + kare_dalga(1047, 0.35))
print('tamam:', sorted(os.listdir(RESIM)), sorted(os.listdir(SES)))
