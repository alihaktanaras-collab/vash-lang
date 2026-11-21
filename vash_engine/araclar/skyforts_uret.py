# Sky Forts Mini için izometrik piksel sanat: uçan ada, binalar (3 seviye), inşaat iskelesi, ağaç, kaya,
# kaynak simgeleri, bulutlar ve sesler.   python vash_engine/araclar/skyforts_uret.py
import json, math, os, random, struct, wave, zlib

KOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ornekler', 'skyforts_mini')
RESIM = os.path.join(KOK, 'resimler')
SES = os.path.join(KOK, 'sesler')
os.makedirs(RESIM, exist_ok=True)
os.makedirs(SES, exist_ok=True)

def hx(s, a=255):
    s = s.lstrip('#')
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)

BOS = (0, 0, 0, 0)
KONTUR = hx('1a1c2c')

def png_yaz(ad, img):
    h, w = len(img), len(img[0])
    ham = b''.join(b'\x00' + b''.join(bytes(img[y][x]) for x in range(w)) for y in range(h))
    def parca(t, v):
        return struct.pack('>I', len(v)) + t + v + struct.pack('>I', zlib.crc32(t + v) & 0xffffffff)
    with open(os.path.join(RESIM, ad), 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + parca(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) +
                parca(b'IDAT', zlib.compress(ham, 9)) + parca(b'IEND', b''))

def tuval(w, h):
    return [[BOS for _ in range(w)] for _ in range(h)]

def nokta(img, x, y, c):
    x, y = int(x), int(y)
    if 0 <= y < len(img) and 0 <= x < len(img[0]):
        img[y][x] = c

def cokgen(img, pts, renk):
    """renk: sabit renk ya da f(x, y) -> renk"""
    ys = [p[1] for p in pts]
    for y in range(int(math.floor(min(ys))), int(math.ceil(max(ys))) + 1):
        yy = y + 0.5
        kes = []
        n = len(pts)
        for i in range(n):
            x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
            if (y1 <= yy < y2) or (y2 <= yy < y1):
                kes.append(x1 + (yy - y1) * (x2 - x1) / (y2 - y1))
        kes.sort()
        for i in range(0, len(kes) - 1, 2):
            for x in range(int(math.ceil(kes[i] - 0.5)), int(math.floor(kes[i + 1] - 0.5)) + 1):
                nokta(img, x, y, renk(x, y) if callable(renk) else renk)

def cizgi(img, x1, y1, x2, y2, c):
    n = int(max(abs(x2 - x1), abs(y2 - y1))) + 1
    for i in range(n + 1):
        t = i / max(n, 1)
        nokta(img, round(x1 + (x2 - x1) * t), round(y1 + (y2 - y1) * t), c)

def cerceve(img, renk=KONTUR):
    h, w = len(img), len(img[0])
    yeni = [r[:] for r in img]
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
    return [sum((k[y] for k in kareler), []) for y in range(len(kareler[0]))]

def koyu(c, k):
    return (max(0, int(c[0] * k)), max(0, int(c[1] * k)), max(0, int(c[2] * k)), c[3])

def acik(c, k):
    return (min(255, int(c[0] + (255 - c[0]) * k)), min(255, int(c[1] + (255 - c[1]) * k)), min(255, int(c[2] + (255 - c[2]) * k)), c[3])

# ---------------- izometrik geometri: karo 32x16 ----------------
HW, HH = 16, 8

def ayak_izi(tx, ty, w, d, yuk=0):
    """Ayak izinin köşeleri: üst, sağ, alt, sol (yukarı kaldırılmış)."""
    T = (tx, ty - yuk)
    R = (tx + w * HW, ty + w * HH - yuk)
    B = (tx + (w - d) * HW, ty + (w + d) * HH - yuk)
    L = (tx - d * HW, ty + d * HH - yuk)
    return T, R, B, L

def prizma(img, tx, ty, w, d, h, ust, sol, sag, desen=True):
    T, R, B, L = ayak_izi(tx, ty, w, d)
    T2, R2, B2, L2 = ayak_izi(tx, ty, w, d, h)
    def sol_renk(x, y):
        return sol if not desen or (y % 4) else koyu(sol, 0.92)
    def sag_renk(x, y):
        return sag if not desen or (y % 4) else koyu(sag, 0.92)
    cokgen(img, [L, B, B2, L2], sol_renk)
    cokgen(img, [B, R, R2, B2], sag_renk)
    cokgen(img, [T2, R2, B2, L2], ust)
    # kenar parıltısı
    cizgi(img, L2[0], L2[1], B2[0], B2[1], acik(ust, 0.25))
    cizgi(img, B2[0], B2[1], R2[0], R2[1], acik(ust, 0.15))
    return T2, R2, B2, L2

def ice(tx, ty, w, d, pay):
    """Ayak izini 'pay' karo içeri al (ortalanmış): yeni tx, ty, w, d"""
    return tx + (pay - pay) * HW, ty + pay * 2 * HH, w - 2 * pay, d - 2 * pay

def piramit(img, tx, ty, w, d, h, tepe, sol, sag):
    T, R, B, L = ayak_izi(tx, ty, w, d, h)
    cx = (T[0] + B[0]) / 2
    cy = (T[1] + B[1]) / 2
    A = (cx, cy - tepe)
    cokgen(img, [L, B, A], sol)
    cokgen(img, [B, R, A], sag)
    cizgi(img, B[0], B[1], A[0], A[1], acik(sol, 0.3))

def yuz_pencere(img, kose, yon, u0, u1, v0, v1, renk):
    """Bir yan yüzde pencere: kose = yüzün alt sol noktası, yon = (dx, dy) birim karo yönü (sol yüz: +HW,+HH / sağ yüz: +HW,-HH)."""
    dx, dy = yon
    p1 = (kose[0] + dx * u0, kose[1] + dy * u0 - v0)
    p2 = (kose[0] + dx * u1, kose[1] + dy * u1 - v0)
    p3 = (kose[0] + dx * u1, kose[1] + dy * u1 - v1)
    p4 = (kose[0] + dx * u0, kose[1] + dy * u0 - v1)
    cokgen(img, [p1, p2, p3, p4], renk)

def silindir(img, cx, taban_y, r, h, govde, ust, serit=None):
    ry = r / 2
    for y in range(int(taban_y - h - ry), int(taban_y + ry) + 1):
        for x in range(int(cx - r), int(cx + r) + 1):
            dx = (x + 0.5 - cx) / r
            if abs(dx) > 1:
                continue
            alt = taban_y + ry * math.sqrt(max(0, 1 - dx * dx))
            ust_y = taban_y - h - ry * math.sqrt(max(0, 1 - dx * dx))
            if ust_y <= y + 0.5 <= alt:
                k = 1.08 - 0.45 * (dx + 1) / 2
                c = koyu(govde, k) if k < 1 else acik(govde, k - 1)
                if serit and int((alt - y) / 5) % 2 == 1:
                    c = koyu(serit, max(0.5, k))
                nokta(img, x, y, c)
    for y in range(int(taban_y - h - ry), int(taban_y - h + ry) + 1):
        for x in range(int(cx - r), int(cx + r) + 1):
            if ((x + 0.5 - cx) / r) ** 2 + ((y + 0.5 - (taban_y - h)) / ry) ** 2 <= 1:
                nokta(img, x, y, ust)

# ---------------- RENKLER ----------------
C = {k: hx(v) for k, v in dict(
    cim='5bbf4f', cim2='4fae47', cim_a='8fde5d', cim_k='2f8a3e', kenar='3d7a3a',
    toprak='a0663a', toprak2='8a5532', toprak_k='5e3a24', tas='7b8597', tas2='5d6575', tas_a='a8b2c2',
    tahta='b07a45', tahta2='8c5c33', tahta_k='6a4425', cati='c0444f', cati2='962f3c',
    mavi='3b5dc9', mavi2='29366f', mavi_a='5fa5ee', altin='ffcd75', altin2='ef9d47',
    metal='9aa6b8', metal2='6c7688', metal_k='4a5262', yakit='ef7d57', yakit2='c2502f',
    mor='b25ee0', mor2='7d3cb5', mor_a='e7b8ff', sari='ffe26b', sari2='e0a83a', beyaz='f4f4f4',
    cam='73eff7', cam2='41a6f6', yaprak='38b764', yaprak2='257179', yaprak_a='a7f070', govde='6a4425').items()}

# ---------------- UÇAN ADA ----------------
N = 14                                   # ızgara: 14 x 14 karo
ADA_PAY_UST = 6
ADA_GEN = 2 * N * HW + 8
ADA_YUK = N * 2 * HH + 150
OX = N * HW + 4                         # (0,0) karosunun üst köşesi
OY = ADA_PAY_UST
rnd = random.Random(11)
ada = tuval(ADA_GEN, ADA_YUK)

# alt kayalık: kenarlar boyunca aşağı sarkan uçurum
sol_alt = (OX - N * HW, OY + N * HH)        # sol köşe
alt = (OX, OY + 2 * N * HH)                 # alt köşe
sag_alt = (OX + N * HW, OY + N * HH)        # sağ köşe
def derinlik(x):
    t = (x - (OX - N * HW)) / (2 * N * HW)
    temel = 26 + 95 * math.sin(math.pi * t) ** 1.6
    return temel + 7 * math.sin(x * 0.21) + 4 * math.sin(x * 0.53 + 1) + rnd.uniform(-1.5, 1.5)
for x in range(int(OX - N * HW), int(OX + N * HW) + 1):
    if x <= OX:
        ust_y = sol_alt[1] + (x - sol_alt[0]) * 0.5
    else:
        ust_y = alt[1] - (x - OX) * 0.5
    d = derinlik(x)
    for y in range(int(ust_y) - 1, int(ust_y + d)):
        k = (y - ust_y) / max(d, 1)
        sag_mi = x > OX
        if k < 0.07:
            c = C['kenar']
        elif k < 0.42:
            c = C['toprak'] if not sag_mi else C['toprak2']
            if (y - int(ust_y)) % 9 == 0 and rnd.random() < 0.6:
                c = C['toprak_k']
            if rnd.random() < 0.05:
                c = C['toprak_k']
        else:
            c = C['tas'] if not sag_mi else C['tas2']
            if rnd.random() < 0.05:
                c = C['tas_a'] if not sag_mi else C['tas']
            elif int(y - ust_y) % 13 == 0 and rnd.random() < 0.7:
                c = koyu(c, 0.85)
            if k > 0.85:
                c = koyu(c, 0.8)
        nokta(ada, x, y, c)
    # sarkan kökler / sarmaşık
    if rnd.random() < 0.16:
        uz = rnd.randint(6, 18)
        for i in range(uz):
            nokta(ada, x, ust_y + 2 + i, C['cim_k'] if i < uz - 2 else C['cim_a'])

# üst yüzey: karo karo, hafif dama deseni
for gx in range(N):
    for gy in range(N):
        T, R, B, L = ayak_izi(OX + (gx - gy) * HW, OY + (gx + gy) * HH, 1, 1)
        taban = C['cim'] if (gx + gy) % 2 == 0 else C['cim2']
        def renk(x, y, taban=taban):
            r = rnd.random()
            if r < 0.06:
                return C['cim_a']
            if r < 0.10:
                return C['cim_k']
            return taban
        cokgen(ada, [T, R, B, L], renk)
# kenar parıltısı
cizgi(ada, OX - N * HW, OY + N * HH, OX, OY, C['cim_a'])
cizgi(ada, OX, OY, OX + N * HW, OY + N * HH, C['cim_a'])
ada = cerceve(ada)
png_yaz('ada.png', ada)

# ---------------- BİNALAR ----------------
# Her bina 3 seviye, yan yana; tuval: ayak izi + yükseklik
def bina_tuvali(w, d, maks_h):
    gen = (w + d) * HW + 6
    yuk = (w + d) * HH + maks_h + 8
    tx = d * HW + 3
    ty = maks_h + 4
    return gen, yuk, tx, ty

def komuta(sev):
    w = d = 3
    gen, yuk, tx, ty = bina_tuvali(w, d, 90)
    img = tuval(gen, yuk)
    taban_ust, taban_sol, taban_sag = [(C['tahta'], C['tahta2'], C['tahta_k']), (C['tas_a'], C['tas'], C['tas2']), (C['metal'], C['metal2'], C['metal_k'])][sev]
    prizma(img, tx, ty, w, d, 8, taban_ust, taban_sol, taban_sag)
    # gövde
    gtx, gty = tx, ty + 2 * HH * 0.5
    h = [26, 34, 42][sev]
    T2, R2, B2, L2 = prizma(img, tx, ty + HH, 2.5, 2.5, 8 + h, koyu(taban_ust, 0.95), taban_sol, taban_sag)
    # pencereler
    for i in range(3):
        yuz_pencere(img, ayak_izi(tx, ty + HH, 2.5, 2.5)[3], (HW, HH), 0.35 + i * 0.7, 0.65 + i * 0.7, 16, 24, C['cam'] if sev else C['altin'])
        yuz_pencere(img, ayak_izi(tx, ty + HH, 2.5, 2.5)[2], (HW, -HH), 0.35 + i * 0.7, 0.65 + i * 0.7, 16, 24, C['cam2'] if sev else C['altin2'])
    # kapı
    yuz_pencere(img, ayak_izi(tx, ty + HH, 2.5, 2.5)[3], (HW, HH), 0.95, 1.55, 8, 20, C['tahta_k'])
    # çatı
    cati = [(C['cati'], C['cati2']), (C['mavi'], C['mavi2']), (C['mavi_a'], C['mavi'])][sev]
    piramit(img, tx, ty + HH, 2.5, 2.5, 8 + h, [18, 22, 28][sev], cati[0], cati[1])
    # bayrak
    T, R, B, L = ayak_izi(tx, ty + HH, 2.5, 2.5, 8 + h)
    cx = (T[0] + B[0]) / 2
    tepe = (T[1] + B[1]) / 2 - [18, 22, 28][sev]
    cizgi(img, cx, tepe, cx, tepe - 14, C['tahta_k'])
    cokgen(img, [(cx + 1, tepe - 14), (cx + 9, tepe - 11), (cx + 1, tepe - 8)], C['altin'] if sev == 2 else C['cati'])
    if sev >= 1:   # köşe kuleleri
        for kx, ky in ((tx - 2.6 * HW, ty + 2.6 * HH + 6), (tx + 2.6 * HW, ty + 2.6 * HH + 6)):
            silindir(img, kx, ky, 5, 18 + 6 * sev, C['tas'] if sev == 1 else C['metal'], C['tas_a'] if sev == 1 else C['mavi_a'])
    return cerceve(img), (tx, ty)

def maden(sev):
    w = d = 2
    gen, yuk, tx, ty = bina_tuvali(w, d, 70)
    img = tuval(gen, yuk)
    prizma(img, tx, ty, w, d, 5, C['toprak'], C['toprak2'], C['toprak_k'])
    # yan bina
    prizma(img, tx, ty + HH, 1.2, 1.6, 5 + 14 + 4 * sev, C['tahta'] if sev == 0 else C['metal'], C['tahta2'] if sev == 0 else C['metal2'], C['tahta_k'] if sev == 0 else C['metal_k'])
    # sondaj kulesi
    kx, ky = tx + 0.9 * HW, ty + 1.6 * HH
    h = 30 + 8 * sev
    for s in (-5, 5):
        cizgi(img, kx + s, ky, kx, ky - h, C['metal_k'])
    for i in range(1, 5):
        y = ky - h * i / 5
        cizgi(img, kx - 5 * (1 - i / 5), y, kx + 5 * (1 - i / 5), y, C['metal2'])
    cokgen(img, [(kx - 3, ky - h - 2), (kx + 3, ky - h - 2), (kx + 3, ky - h + 3), (kx - 3, ky - h + 3)], C['cati'] if sev < 2 else C['altin'])
    # cevher yığını
    for i in range(10 + 4 * sev):
        px = tx + rnd.uniform(-0.8, 0.2) * HW
        py = ty + 2.6 * HH + rnd.uniform(-3, 3)
        cokgen(img, [(px, py - 3), (px + 3, py - 1), (px + 2, py + 2), (px - 2, py + 2), (px - 3, py - 1)], rnd.choice([C['metal'], C['metal2'], C['tas_a']]))
    return cerceve(img), (tx, ty)

def pompa(sev):
    w = d = 2
    gen, yuk, tx, ty = bina_tuvali(w, d, 70)
    img = tuval(gen, yuk)
    prizma(img, tx, ty, w, d, 5, C['tas'], C['tas2'], C['metal_k'])
    cx, cy = tx + 0.0 * HW, ty + 2 * HH + 2
    silindir(img, cx - 6, cy + 2, 10, 22 + 6 * sev, C['yakit'], acik(C['yakit'], 0.3), C['yakit2'] if sev >= 1 else None)
    if sev >= 1:
        silindir(img, cx + 11, cy + 6, 7, 16 + 6 * sev, C['yakit2'], C['yakit'])
    # boru
    cizgi(img, cx + 3, cy - 10, cx + 16, cy - 4, C['metal_k'])
    cizgi(img, cx + 3, cy - 11, cx + 16, cy - 5, C['metal'])
    # alev
    if sev == 2:
        cokgen(img, [(cx - 6, cy - 46), (cx - 3, cy - 38), (cx - 9, cy - 38)], C['sari'])
    return cerceve(img), (tx, ty)

def kristal(sev):
    w = d = 2
    gen, yuk, tx, ty = bina_tuvali(w, d, 80)
    img = tuval(gen, yuk)
    prizma(img, tx, ty, w, d, 6, C['tas_a'], C['tas'], C['tas2'])
    prizma(img, tx, ty + HH * 0.6, 1.4, 1.4, 10, C['mor2'], C['tas2'], C['metal_k'])
    cx, cy = tx, ty + 2 * HH - 4
    for i, (ox, h, r) in enumerate([(0, 30 + 8 * sev, 7), (-9, 16 + 4 * sev, 4), (9, 18 + 4 * sev, 4)][: 1 + min(2, sev + 1)]):
        tepe = (cx + ox, cy - h)
        cokgen(img, [(cx + ox - r, cy - h * 0.3), tepe, (cx + ox, cy)], C['mor_a'])
        cokgen(img, [(cx + ox, cy), tepe, (cx + ox + r, cy - h * 0.3)], C['mor'])
        cizgi(img, cx + ox, cy, tepe[0], tepe[1], C['beyaz'])
    return cerceve(img), (tx, ty)

def depo(sev):
    w = d = 2
    gen, yuk, tx, ty = bina_tuvali(w, d, 60)
    img = tuval(gen, yuk)
    renk = [(C['tahta'], C['tahta2'], C['tahta_k']), (C['tas_a'], C['tas'], C['tas2']), (C['metal'], C['metal2'], C['metal_k'])][sev]
    h = 18 + 5 * sev
    prizma(img, tx, ty + 2, 1.8, 1.8, h, renk[0], renk[1], renk[2])
    # yuvarlak çatı yerine eğimli çatı
    piramit(img, tx, ty + 2, 1.8, 1.8, h, 10, C['cati'] if sev < 2 else C['mavi'], C['cati2'] if sev < 2 else C['mavi2'])
    yuz_pencere(img, ayak_izi(tx, ty + 2, 1.8, 1.8)[3], (HW, HH), 0.5, 1.3, 2, 14, C['tahta_k'])
    # kasalar
    for i in range(2 + sev):
        bx = tx + 0.9 * HW + i * 5
        by = ty + 3.2 * HH - i * 2
        prizma(img, bx, by - 6, 0.35, 0.35, 6, C['tahta'], C['tahta2'], C['tahta_k'], False)
    return cerceve(img), (tx, ty)

def jenerator(sev):
    w = d = 2
    gen, yuk, tx, ty = bina_tuvali(w, d, 70)
    img = tuval(gen, yuk)
    prizma(img, tx, ty, w, d, 5, C['metal'], C['metal2'], C['metal_k'])
    prizma(img, tx, ty + HH * 0.7, 1.3, 1.3, 16 + 4 * sev, C['metal_k'], C['metal2'], C['mavi2'])
    cx, cy = tx, ty + 2 * HH - 2
    # bobin
    for i in range(3 + sev):
        y = cy - 22 - 4 * sev - i * 4
        cokgen(img, [(cx - 6 + i, y), (cx + 6 - i, y), (cx + 6 - i, y + 2), (cx - 6 + i, y + 2)], C['altin'] if i % 2 == 0 else C['altin2'])
    # şimşek
    y0 = cy - 36 - 8 * sev
    cokgen(img, [(cx + 1, y0 - 10), (cx - 4, y0), (cx, y0), (cx - 2, y0 + 8), (cx + 4, y0 - 2), (cx, y0 - 2)], C['sari'])
    return cerceve(img), (tx, ty)

def iskele(w):
    gen, yuk, tx, ty = bina_tuvali(w, w, 50)
    img = tuval(gen, yuk)
    prizma(img, tx, ty, w, w, 4, C['toprak'], C['toprak2'], C['toprak_k'])
    T, R, B, L = ayak_izi(tx, ty + 4, w, w)
    for p in (T, R, B, L):
        cizgi(img, p[0], p[1] - 4, p[0], p[1] - 34, C['tahta'])
    for yuk_ in (14, 28):
        for a, b in ((L, B), (B, R)):
            cizgi(img, a[0], a[1] - 4 - yuk_, b[0], b[1] - 4 - yuk_, C['tahta2'])
    cizgi(img, L[0], L[1] - 4, B[0], B[1] - 30, C['tahta_k'])
    cizgi(img, B[0], B[1] - 4, R[0], R[1] - 30, C['tahta_k'])
    # tuğla yığını
    prizma(img, B[0] - 4, B[1] - 14, 0.5, 0.5, 6, C['cati'], C['cati2'], C['toprak_k'], False)
    return cerceve(img), (tx, ty)

BINALAR = {'komuta': (komuta, 3), 'maden': (maden, 2), 'pompa': (pompa, 2), 'kristal': (kristal, 2), 'depo': (depo, 2), 'jenerator': (jenerator, 2)}
bilgi = {}
for ad, (fn, ayak) in BINALAR.items():
    kareler = []
    capa = None
    for sev in range(3):
        rnd.seed(hash((ad, sev)) & 0xffff)
        img, capa = fn(sev)
        kareler.append(img)
    png_yaz(f'{ad}.png', yan_yana(kareler))
    bilgi[ad] = {'frame_width': len(kareler[0][0]), 'height': len(kareler[0]), 'anchor_x': capa[0], 'anchor_y': capa[1], 'size': ayak}
for w in (2, 3):
    img, capa = iskele(w)
    png_yaz(f'iskele{w}.png', img)
    bilgi[f'iskele{w}'] = {'frame_width': len(img[0]), 'height': len(img), 'anchor_x': capa[0], 'anchor_y': capa[1], 'size': w}

# ---------------- süs: ağaç, kaya ----------------
def agac(tur):
    img = tuval(24, 40)
    cx = 12
    cizgi(img, cx, 36, cx, 28, C['govde'])
    cizgi(img, cx + 1, 36, cx + 1, 28, C['tahta_k'])
    for i, (y, r) in enumerate([(28, 10), (21, 8), (14, 6)] if tur == 0 else [(26, 9), (18, 9)]):
        if tur == 0:
            cokgen(img, [(cx - r, y), (cx, y - 11), (cx + r + 1, y)], lambda x, yy: C['yaprak'] if x <= cx else C['yaprak2'])
        else:
            for yy in range(y - r, y + r):
                for x in range(cx - r, cx + r + 1):
                    if (x - cx) ** 2 + (yy - y) ** 2 <= r * r:
                        nokta(img, x, yy, C['yaprak_a'] if (x - cx) + (yy - y) < -r * 0.6 else (C['yaprak'] if x <= cx + 2 else C['yaprak2']))
    return cerceve(img)
png_yaz('agaclar.png', yan_yana([agac(0), agac(1)]))

kaya = tuval(20, 14)
cokgen(kaya, [(2, 12), (5, 4), (11, 2), (17, 6), (18, 12)], lambda x, y: C['tas_a'] if x + y < 14 else (C['tas'] if x < 12 else C['tas2']))
png_yaz('kaya.png', cerceve(kaya))

# ---------------- kaynak simgeleri (12x12) ----------------
def simge(tur):
    img = tuval(12, 12)
    if tur == 'metal':
        cokgen(img, [(1, 6), (5, 3), (11, 5), (11, 8), (7, 11), (1, 9)], lambda x, y: C['metal'] if y < 7 else C['metal2'])
        cizgi(img, 2, 6, 6, 4, C['beyaz'])
    elif tur == 'yakit':
        for y in range(12):
            for x in range(12):
                d = ((x - 5.5) / 4.5) ** 2 + ((y - 7.5) / 4) ** 2
                if d <= 1 or (y < 7 and abs(x - 5.5) <= (y - 0.5) * 0.7):
                    nokta(img, x, y, C['yakit'] if x < 6 else C['yakit2'])
        nokta(img, 4, 6, C['beyaz'])
    elif tur == 'kristal':
        cokgen(img, [(6, 0), (11, 5), (6, 12), (1, 5)], lambda x, y: C['mor_a'] if x < 6 else C['mor'])
        cizgi(img, 6, 1, 6, 11, C['beyaz'])
    elif tur == 'enerji':
        cokgen(img, [(7, 0), (2, 7), (6, 7), (4, 12), (10, 4), (6, 4)], C['sari'])
    return cerceve(img)
png_yaz('simgeler.png', yan_yana([simge(t) for t in ('metal', 'yakit', 'kristal', 'enerji')]))

# ---------------- bulutlar ve uzak adalar ----------------
W = 320
bulut = tuval(W, 60)
rnd.seed(5)
for merkez in (40, 150, 260):
    for _ in range(7):
        cx = merkez + rnd.randint(-22, 22); cy = 34 + rnd.randint(-6, 5); r = rnd.randint(7, 13)
        for y in range(60):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    bulut[y][x % W] = C['beyaz'] if y < cy + r * 0.3 else hx('d6e7f2')
png_yaz('bulutlar.png', bulut)

uzak = tuval(W, 50)
for merkez, gen in ((60, 34), (210, 22)):
    for x in range(merkez - gen, merkez + gen):
        t = (x - merkez) / gen
        ust = 20 - 3 * math.cos(t * 3)
        alt_ = 20 + 18 * (1 - t * t) ** 1.5
        for y in range(int(ust), int(alt_)):
            nokta(uzak, x, y, hx('8fb3d9') if y < ust + 3 else hx('a9c4e3'))
png_yaz('uzak_adalar.png', uzak)

with open(os.path.join(KOK, 'resimler', 'bilgi.json'), 'w', encoding='utf-8') as f:
    json.dump({'tile_w': 32, 'tile_h': 16, 'grid': N, 'island_origin_x': OX, 'island_origin_y': OY, 'buildings': bilgi}, f, indent=1)

# ---------------- sesler ----------------
def wav_yaz(ad, ornekler, hz=22050):
    with wave.open(os.path.join(SES, ad), 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(hz)
        f.writeframes(b''.join(struct.pack('<h', max(-32767, min(32767, int(s * 32767)))) for s in ornekler))

def ton(frek, sure, ses=0.22, hz=22050, dalga='kare', kayma=0.0):
    n = int(sure * hz); out = []; faz = 0.0
    for i in range(n):
        faz += (frek + kayma * i / n) / hz
        v = (1 if (faz % 1) < 0.5 else -1) if dalga == 'kare' else math.sin(2 * math.pi * faz)
        out.append(v * ses * min(1.0, (n - i) / (0.03 * hz)) * min(1.0, i / (0.004 * hz)))
    return out

wav_yaz('yerlestir.wav', ton(180, 0.05, 0.3, kayma=-60) + ton(120, 0.06, 0.25))
wav_yaz('topla.wav', ton(880, 0.05, dalga='sin', ses=0.3) + ton(1175, 0.09, dalga='sin', ses=0.3))
wav_yaz('bitti.wav', ton(523, 0.08) + ton(659, 0.08) + ton(784, 0.08) + ton(1047, 0.25))
wav_yaz('tik.wav', ton(1400, 0.02, 0.15, dalga='sin'))
wav_yaz('hata.wav', ton(200, 0.15, 0.2, kayma=-60))
print('tamam:', sorted(os.listdir(RESIM)))
