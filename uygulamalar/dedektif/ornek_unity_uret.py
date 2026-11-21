# Vash Dedektif'in Unity röntgenini denemek için küçük bir örnek Unity projesi üretir: ornek_unity/GokAdasi
#   python uygulamalar/dedektif/ornek_unity_uret.py
# İçinde: sahne, prefab, materyal, script, resim ve sesler (birbirine GUID ile bağlı), bilerek kullanılmayan
# iki dosya, telefonu yoracak 4096 piksellik bir doku ve büyük bir WAV.
import hashlib, math, os, shutil, struct, wave, zlib

BURASI = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.join(BURASI, 'ornek_unity', 'GokAdasi')
SF = os.path.join(BURASI, '..', '..', 'vash_engine', 'ornekler', 'skyforts_mini', 'resimler')
SES = os.path.join(BURASI, '..', '..', 'vash_engine', 'ornekler', 'skyforts_mini', 'sesler')
if os.path.isdir(KOK):
    shutil.rmtree(KOK)

def guid(ad):
    return hashlib.md5(ad.encode()).hexdigest()

def yaz(yol, icerik, ikili=False):
    tam = os.path.join(KOK, yol)
    os.makedirs(os.path.dirname(tam), exist_ok=True)
    with open(tam, 'wb' if ikili else 'w', encoding=None if ikili else 'utf-8') as f:
        f.write(icerik)

def meta(yol, ek=''):
    yaz(yol + '.meta', f'fileFormatVersion: 2\nguid: {guid(yol)}\n{ek}')

def doku_meta(yol, en_buyuk=2048, sikistir=1):
    meta(yol, f'TextureImporter:\n  maxTextureSize: {en_buyuk}\n  textureCompression: {sikistir}\n')

def png(w, h, renk):
    satir = b'\x00' + bytes(renk) * w
    ham = zlib.compress(satir * h, 9)
    def p(t, v):
        return struct.pack('>I', len(v)) + t + v + struct.pack('>I', zlib.crc32(t + v) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + p(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + p(b'IDAT', ham) + p(b'IEND', b'')

def wav(saniye, frekans):
    import io
    b = io.BytesIO()
    with wave.open(b, 'wb') as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(44100)
        f.writeframes(b''.join(struct.pack('<hh', int(3000 * math.sin(i * frekans / 7000)), int(3000 * math.sin(i * frekans / 7100))) for i in range(int(44100 * saniye))))
    return b.getvalue()

# --- proje ayarları ---
yaz('ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 6000.0.30f1\nm_EditorVersionWithRevision: 6000.0.30f1 (demo)\n')
yaz('ProjectSettings/EditorBuildSettings.asset', f'%YAML 1.1\nEditorBuildSettings:\n  m_Scenes:\n  - enabled: 1\n    path: Assets/Sahneler/Ana.unity\n    guid: {guid("Assets/Sahneler/Ana.unity")}\n')
yaz('Packages/manifest.json', '{\n  "dependencies": {\n    "com.unity.ugui": "2.0.0"\n  }\n}\n')

# --- resimler ---
resimler = []
for ad in ['ada', 'komuta', 'maden', 'pompa', 'kristal', 'depo', 'jenerator', 'agaclar', 'simgeler']:
    yol = f'Assets/Resimler/{ad}.png'
    yaz(yol, open(os.path.join(SF, ad + '.png'), 'rb').read(), True)
    doku_meta(yol)
    resimler.append(yol)
yol = 'Assets/Resimler/Gokyuzu_4K.png'                      # telefonda çok büyük
yaz(yol, png(4096, 4096, (95, 165, 238, 255)), True)
doku_meta(yol, en_buyuk=8192, sikistir=0)
resimler.append(yol)
yol = 'Assets/Resimler/EskiLogo.png'                         # hiçbir yerde kullanılmıyor
yaz(yol, png(512, 512, (180, 60, 80, 255)) + bytes(300000), True)
doku_meta(yol)

# --- sesler ---
for ad in ['yerlestir', 'topla', 'bitti']:
    yol = f'Assets/Sesler/{ad}.wav'
    yaz(yol, open(os.path.join(SES, ad + '.wav'), 'rb').read(), True)
    meta(yol, 'AudioImporter:\n  compressionFormat: 1\n')
yol = 'Assets/Sesler/Muzik_Ana.wav'                          # büyük WAV
yaz(yol, wav(12, 3.0), True)
meta(yol, 'AudioImporter:\n  compressionFormat: 0\n')
yol = 'Assets/Sesler/deneme_muzik.wav'                       # hiçbir yerde kullanılmıyor
yaz(yol, wav(2, 5.0), True)
meta(yol)

# --- scriptler ---
scriptler = {
    'Assets/Scripts/Bina.cs': 'using UnityEngine;\n\npublic class Bina : MonoBehaviour\n{\n    public int seviye = 1;\n    public float uretim = 10f;\n\n    void Update()\n    {\n        // her saniye kaynak üret\n    }\n}\n',
    'Assets/Scripts/Kamera.cs': 'using UnityEngine;\n\npublic class Kamera : MonoBehaviour\n{\n    public float hiz = 5f;\n\n    void LateUpdate()\n    {\n        var y = Input.GetAxis("Vertical");\n        var x = Input.GetAxis("Horizontal");\n        transform.position += new Vector3(x, y, 0) * hiz * Time.deltaTime;\n    }\n}\n',
    'Assets/Scripts/Kaynaklar.cs': 'public static class Kaynaklar\n{\n    public static int metal = 400;\n    public static int yakit = 400;\n    public static int kristal = 30;\n\n    public static bool Harca(int m, int y, int k)\n    {\n        if (metal < m || yakit < y || kristal < k) return false;\n        metal -= m; yakit -= y; kristal -= k;\n        return true;\n    }\n}\n',
}
for yol, icerik in scriptler.items():
    yaz(yol, icerik)
    meta(yol, 'MonoImporter:\n  serializedVersion: 2\n')

# --- materyaller, prefablar, sahne (GUID ile birbirine bağlı) ---
def mat(ad, doku):
    yol = f'Assets/Materyaller/{ad}.mat'
    yaz(yol, f'%YAML 1.1\n--- !u!21 &2100000\nMaterial:\n  m_Name: {ad}\n  m_SavedProperties:\n    m_TexEnvs:\n    - _MainTex:\n        m_Texture: {{fileID: 2800000, guid: {guid(doku)}, type: 3}}\n')
    meta(yol)
    return yol
materyaller = [mat('Ada', 'Assets/Resimler/ada.png'), mat('Gokyuzu', 'Assets/Resimler/Gokyuzu_4K.png')]

def prefab(ad, doku):
    yol = f'Assets/Prefablar/{ad}.prefab'
    yaz(yol, f'%YAML 1.1\n--- !u!1 &100\nGameObject:\n  m_Name: {ad}\n--- !u!212 &200\nSpriteRenderer:\n  m_Sprite: {{fileID: 21300000, guid: {guid(doku)}, type: 3}}\n--- !u!114 &300\nMonoBehaviour:\n  m_Script: {{fileID: 11500000, guid: {guid("Assets/Scripts/Bina.cs")}, type: 3}}\n')
    meta(yol)
    return yol
prefablar = [prefab(ad.capitalize(), f'Assets/Resimler/{ad}.png') for ad in ['komuta', 'maden', 'pompa', 'kristal', 'depo', 'jenerator']]

sahne = '%YAML 1.1\n'
for i, p in enumerate(prefablar + materyaller + ['Assets/Resimler/agaclar.png', 'Assets/Resimler/simgeler.png', 'Assets/Scripts/Kamera.cs',
                                                  'Assets/Sesler/yerlestir.wav', 'Assets/Sesler/topla.wav', 'Assets/Sesler/bitti.wav', 'Assets/Sesler/Muzik_Ana.wav']):
    sahne += f'--- !u!1001 &{1000 + i}\nPrefabInstance:\n  m_SourcePrefab: {{fileID: 100100000, guid: {guid(p)}, type: 3}}\n'
yaz('Assets/Sahneler/Ana.unity', sahne)
meta('Assets/Sahneler/Ana.unity')
print('örnek Unity projesi:', KOK)
