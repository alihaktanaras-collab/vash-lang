# Platform örneğinin ilk bölümünü (oyun.json) üretir. Sonrası düzenleyiciyle değiştirilebilir.
import json, os

KOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ornekler', 'platform')
T = 48                      # bir karo: 16 piksel x 3
ZEMIN_Y = 540 - 2 * T       # zeminin üstü

nesneler = []
def ekle(**k):
    temel = dict(kind='image', x=0, y=0, width=T, height=T, color='#ffffff', image='', frames=1, frame_speed=8,
                 tiled=False, label='', text_size=28, on_screen=False, layer=0, solid=False, hidden=False, behaviors=[])
    temel.update(k)
    nesneler.append(temel)

def davranis(kind, speed=0, power=0, value='', sound=''):
    return dict(kind=kind, speed=speed, power=power, value=value, sound=sound)

# Zemin parçaları (karo sütunu, genişlik) — aralarında çukurlar var
for i, (bas, gen) in enumerate([(0, 18), (21, 10), (34, 6), (43, 14), (60, 20)]):
    ekle(name=f'Zemin {i + 1}', x=bas * T, y=ZEMIN_Y, width=gen * T, height=2 * T + 60,
         image='resimler/zemin.png', frames=2, tiled=True, solid=True)

# Taş platformlar (karo sütunu, karo satırı yukarıdan, genişlik)
for i, (sx, sy, gen) in enumerate([(7, 6, 3), (12, 4, 4), (18, 6, 3), (25, 5, 3), (31, 3, 2), (36, 5, 3), (47, 6, 4), (52, 4, 3), (64, 6, 3), (69, 4, 3)]):
    ekle(name=f'Platform {i + 1}', x=sx * T, y=sy * T + 12, width=gen * T, height=T,
         image='resimler/tas.png', frames=2, tiled=True, solid=True)

# Altınlar
altin_yerleri = [(4, 8), (5, 8), (6, 8), (8, 5), (13, 3), (14, 3), (15, 3), (19, 5), (22, 8), (23, 8), (24, 8),
                 (26, 4), (31, 2), (32, 2), (37, 4), (38, 4), (44, 8), (45, 8), (48, 5), (49, 5), (53, 3), (54, 3),
                 (58, 6), (62, 8), (65, 5), (70, 3), (71, 3), (74, 8), (75, 8)]
for i, (sx, sy) in enumerate(altin_yerleri):
    ekle(name=f'Altın {i + 1}', x=sx * T + 6, y=sy * T + 18, width=36, height=36, image='resimler/altin.png',
         frames=6, frame_speed=10, layer=2,
         behaviors=[davranis('collect', power=10, sound='sesler/altin.wav'), davranis('float', speed=3, power=5)])

# Sümükler (düşman)
for i, sx in enumerate([10, 25, 46, 55, 66, 72]):
    ekle(name=f'Sümük {i + 1}', x=sx * T, y=ZEMIN_Y - T, image='resimler/sumuk.png', frames=3, frame_speed=5, layer=3,
         behaviors=[davranis('gravity'), davranis('patrol', speed=70), davranis('enemy', power=50, value='sesler/ah.wav', sound='sesler/ezme.wav')])

# Dikenler
for i, (sx, gen) in enumerate([(16, 2), (39, 1), (50, 2), (63, 1)]):
    ekle(name=f'Diken {i + 1}', x=sx * T, y=ZEMIN_Y - 27, width=gen * T, height=27, image='resimler/diken.png',
         tiled=True, layer=1, behaviors=[davranis('danger', sound='sesler/ah.wav')])

# Bitiş bayrağı
ekle(name='Bayrak', x=77 * T, y=ZEMIN_Y - 2 * T, width=T, height=2 * T, image='resimler/bayrak.png', frames=3,
     frame_speed=6, layer=1, behaviors=[davranis('goal', value='Tebrikler, bitirdin!', sound='sesler/kazandin.wav')])

# Oyuncu
ekle(name='Oyuncu', x=2 * T, y=ZEMIN_Y - T, image='resimler/oyuncu.png', frames=6, frame_speed=12, layer=5,
     behaviors=[davranis('platformer', speed=270, power=660)])

# Ekranda duran yazılar
ekle(name='Puan yazısı', kind='text', x=24, y=14, width=240, height=40, label='Altın: {score}', text_size=34,
     color='#ffe9a8', on_screen=True, layer=10)
ekle(name='İpucu', kind='text', x=24, y=500, width=420, height=28, label='← → yürü   ·   Boşluk zıpla   ·   Düşmanların üstüne bas',
     text_size=20, color='#ffffff', on_screen=True, layer=10)

oyun = dict(title='Altın Avcısı', view_width=960, view_height=540, world_width=80 * T, world_height=540,
            sky_top='#3b8fd9', sky_bottom='#bfe9ff', gravity=1700, pixel_scale=3,
            layers=[dict(image='resimler/bulutlar.png', speed=0.12, y=30),
                    dict(image='resimler/daglar.png', speed=0.25, y=330),
                    dict(image='resimler/tepeler.png', speed=0.5, y=372)],
            things=nesneler)
with open(os.path.join(KOK, 'oyun.json'), 'w', encoding='utf-8') as f:
    json.dump(oyun, f, ensure_ascii=False, indent=2)
print('nesne sayısı:', len(nesneler))
