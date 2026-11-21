/* =====================================================================
 *  ÇALIŞMA ZAMANI KÜTÜPHANESİ (runtime)
 * =====================================================================
 *
 *  Dilimizde yazılan her program bu küçük kütüphaneyle birlikte derlenir.
 *  İçinde, işletim sistemiyle konuşması gereken birkaç temel iş var:
 *  ekrana yazmak, sayıyı metne çevirmek, hafızadan yer alıp geri vermek,
 *  hata olunca programı durdurmak.
 *
 *  Neden C ile yazıldı?
 *  Ekrana bir şey yazmak için Windows'la konuşmak gerekiyor. Bunu en kolay,
 *  her bilgisayarda zaten bulunan C kütüphanesi (printf, fputs...) yapar.
 *  Rust, Go ve Swift de başlangıçta C kütüphanesini böyle kullanır.
 *  İleride dilimiz güçlenince bu dosyayı da kendi dilimizle yazabiliriz.
 *
 *  Programın kendisi (senin yazdığın kod) bu dosyada DEĞİL; o, LLVM IR'dan
 *  doğrudan makine koduna çevriliyor. Burası sadece yardımcı fonksiyonlar.
 * ===================================================================== */

#include <errno.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <time.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <winsock2.h>      /* pencere (window) için yerel sunucu; windows.h'den önce gelmeli */
#include <windows.h>
#include <shellapi.h>
#include <winhttp.h>        /* http modülü: istemci */
#define SECURITY_WIN32
#include <security.h>       /* HTTPS sunucusu (TLS: Windows SChannel) */
#include <schannel.h>
#include <wincrypt.h>
#include <ncrypt.h>
#ifndef SOMAXCONN_HINT
#define SOMAXCONN_HINT(b) (-(b))   /* bekleyen bağlantı kuyruğunun boyu (Windows 8+) */
#endif
#endif

/* =====================================================================
 *  BELLEK: SAYAÇ (referans sayma)
 * =====================================================================
 *
 *  Hafızadan alınan her metnin hemen ÖNÜNDE 16 baytlık bir "başlık" durur:
 *
 *      [ sayaç: 2 | uzunluk: 7 ][ M e r h a b a \0 ]
 *                               ^
 *                               programın elindeki adres metnin başını gösterir;
 *                               başlık onun 16 bayt gerisinde
 *
 *  tut(m)   → sayacı 1 artır   ("bunu bir yer daha kullanıyor")
 *  birak(m) → sayacı 1 azalt; 0 olursa yeri hemen geri ver
 *
 *  Uzunluğu saklamak hız kazandırır: iki metni karşılaştırırken uzunlukları
 *  farklıysa harflere hiç bakmadan "eşit değil" deriz; birleştirirken de
 *  harfleri tek tek saymamız gerekmez.
 *
 *  Koddaki sabit metinlerin ("merhaba") sayacı -1'dir: "sonsuz, hiç temizleme".
 *  Bu kontrolleri derleyicimiz otomatik ekler; programcı hiçbir şey yazmaz.
 * ===================================================================== */

typedef struct { int64_t sayac; int64_t uzunluk; } Baslik;

#define BASLIK(m) (((Baslik *)(m)) - 1)
#define SAYAC(m) BASLIK(m)->sayac
#define UZUNLUK(m) BASLIK(m)->uzunluk

/* Bellek raporu için (DIL_BELLEK=1 ile çalıştırınca gösterilir) */
static int64_t toplam_ayrilan = 0;
static int64_t canli = 0;

/* ---------- MESAJ DİLİ ----------
 *  Çalışma hataları Türkçe ya da İngilizce: VASH_DIL=tr|en; yoksa Windows'un dili Türkçeyse Türkçe.
 *  Her mesaj iki dilde yazılır:  MESAJ("Türkçe", "English") */
static int dil_tr = 1;
#define MESAJ(tr, en) (dil_tr ? (tr) : (en))

static void hafiza_doldu(void) {
    fprintf(stderr, MESAJ("\nÇALIŞMA HATASI: Hafıza doldu.\n", "\nRUNTIME ERROR: Out of memory.\n"));
    exit(1);
}

/* ---------- ÇOK ÇEKİRDEK (parallel) ----------
 *  Değerlerin sayaçları normalde düz bir "+1 / -1" ile değişir (en hızlısı).
 *  parallel çalışırken aynı değeri birden çok çekirdek tutup bırakabilir; o sırada sayaçlar
 *  "bölünmez" (atomic) işlemlerle değişir. Böylece paralel olmayan programlar hiç yavaşlamaz. */
static void dili_belirle(void) {
    const char *d = getenv("VASH_DIL");
    if (d && (d[0] == 't' || d[0] == 'T')) dil_tr = 1;
    else if (d && (d[0] == 'e' || d[0] == 'E')) dil_tr = 0;
    else dil_tr = PRIMARYLANGID(GetUserDefaultUILanguage()) == LANG_TURKISH;
}

static LONG paralel_aktif = 0;               /* > 0: şu an paralel işler çalışıyor */
static LONG paralel_bolum = 0;               /* > 0: bir parallel bloğu/döngüsü çalışıyor (ana çekirdek de işçi gibi davranır) */
static _Thread_local int arka_plan_isi = 0;  /* bu iş parçacığı 'start' ile başlatılmış bir iş mi */
#define ISCI_MODU (paralel_bolum || arka_plan_isi)   /* kendi rafları ve arenasıyla mı çalışıyor */
#define SAYAC_ARTIR(x) do { if (paralel_aktif) __atomic_fetch_add(&(x), 1, __ATOMIC_RELAXED); else (x)++; } while (0)
static inline int64_t sayac_azalt(int64_t *x) {
    return paralel_aktif ? __atomic_sub_fetch(x, 1, __ATOMIC_ACQ_REL) : --(*x);
}
static CRITICAL_SECTION yaz_kilidi;           /* print'ler birbirine karışmasın */
static CRITICAL_SECTION arena_kilidi;         /* yeni arena parçası eklenirken */
static CRITICAL_SECTION toplama_kilidi;       /* parallel repeat toplamaları birleştirilirken */

/* ---------- Küçük parçalar için kendi deposu ----------
 *
 *  malloc (Windows'un hafıza dağıtıcısı) her boyutta işe yarayan genel bir
 *  sistem; bu yüzden küçük ve sık istekler için yavaş. Kısa metinler için
 *  kendi "raf sistemimizi" kuruyoruz:
 *
 *    - Boyutlar 16'nın katlarına yuvarlanır: 32, 48, 64 ... 128 bayt (her biri bir raf)
 *    - Geri verilen parça atılmaz, kendi boyutunun rafına konur
 *    - Yeni parça istenince önce o raftan alınır (sadece birkaç işlemci komutu)
 *    - Raf boşsa, 64 KB'lık büyük bir bloktan sırayla kesilir
 *
 *  Raftaki parçalar birbirine zincirle bağlıdır: her boş parçanın ilk 8 baytı
 *  bir sonraki boş parçanın adresini tutar.
 *  128 bayttan büyük istekler doğrudan malloc'a gider.
 *  (NOT: Şimdilik tek çekirdek içindir; çoklu çekirdek gelince güncellenecek.) */
#define KUCUK_SINIR 128
#define BLOK_BOYUTU (64 * 1024)

typedef struct {
    void *raflar[KUCUK_SINIR / 16 + 1];
    char *blok_bas, *blok_son;
} RafDurumu;
static RafDurumu raf_ana;                      /* paralel bir şey çalışmıyorken: düz, en hızlı yol */
static _Thread_local RafDurumu raf_cekirdek;   /* paralel çalışırken: her çekirdeğin kendi rafları */
#define RAF (ISCI_MODU ? &raf_cekirdek : &raf_ana)

static void *kucuk_al(size_t raf) {
    void *p = RAF->raflar[raf];
    if (p) {                                   /* rafta hazır parça var */
        RAF->raflar[raf] = *(void **)p;
        return p;
    }
    size_t boyut = raf * 16;
    if (!RAF->blok_bas || RAF->blok_bas + boyut > RAF->blok_son) {   /* yeni büyük blok */
        RAF->blok_bas = malloc(BLOK_BOYUTU);
        if (!RAF->blok_bas) hafiza_doldu();
        RAF->blok_son = RAF->blok_bas + BLOK_BOYUTU;
    }
    p = RAF->blok_bas;
    RAF->blok_bas += boyut;
    return p;
}

static void kucuk_ver(void *p, size_t raf) {
    *(void **)p = RAF->raflar[raf];                 /* rafın başına ekle */
    RAF->raflar[raf] = p;
}

/* ---------- ARENA: arena { } bloğu için "kare belleği" ----------
 *
 *  arena { ... } bloğunun içinde oluşan metin/liste/nesne/sözlükler 1 MB'lık büyük
 *  parçalardan SIRAYLA kesilir (yer aramak yok: sadece bir sayacı ilerletmek).
 *  İçlerinden biri bırakılınca yeri geri verilmez; blok bitince bütün parça tek
 *  hamlede boşaltılır ve bir sonraki blokta (ör. oyunun bir sonraki karesinde) yeniden kullanılır.
 *
 *  Güvenlik: bloktan DIŞARI kaçan değer (dışarıdaki bir değişkene, globale ya da dışarıdaki
 *  bir listeye konan) normal belleğe kopyalanır (kacir). Derleyici değişkenlere koyarken
 *  arena_kac'ı çağırır; listeye/nesneye/sözlüğe koyarken bu dosya kendisi kontrol eder.
 *  Böylece blok bittiğinde arenadaki hiçbir şeye dışarıdan bakılmıyor olur.
 *  (Liste/sözlük elemanlarının dizileri arenada değil, normal bellektedir; sadece başlıklar arenada.) */
#define ARENA_PARCA (1024 * 1024)
#define ARENA_EN_FAZLA_PARCA 256
#define ARENA_EN_DERIN 64
static char *arena_parcalar[ARENA_EN_FAZLA_PARCA * 4];   /* bütün çekirdeklerin parçaları (arena_mi için) */
static volatile LONG arena_parca_sayisi = 0;
typedef struct {                               /* bir çekirdeğin arena durumu */
    int aktif;                                 /* iç içe kaç arena bloğundayız */
    int kapali;                                /* > 0: arena açık olsa da normal bellekten al (kopyalarken) */
    int simdiki;                               /* şu an kesilen parça (-1: henüz yok) */
    int parca_sayim;
    size_t konum;                              /* o parçadaki ilk boş yer */
    int64_t canli;                             /* arenada olup henüz bırakılmamış değer sayısı */
    char *parcalar[ARENA_EN_FAZLA_PARCA];      /* bu çekirdeğin parçaları (sırayla) */
    struct { int parca; size_t konum; } isaretler[ARENA_EN_DERIN];
} ArenaDurumu;
static ArenaDurumu ca_ana = { 0, 0, -1, 0, 0, 0, {0}, {{0, 0}} };
static _Thread_local ArenaDurumu ca_cekirdek = { 0, 0, -1, 0, 0, 0, {0}, {{0, 0}} };
#define CA (ISCI_MODU ? &ca_cekirdek : &ca_ana)

static void *arena_al(size_t boyut) {
    boyut = (boyut + 15) & ~(size_t)15;
    if (boyut > ARENA_PARCA / 4) return NULL;               /* çok büyük: normal bellekten */
    if (CA->simdiki < 0 || CA->konum + boyut > ARENA_PARCA) {
        if (CA->simdiki + 1 >= CA->parca_sayim) {
            if (CA->parca_sayim >= ARENA_EN_FAZLA_PARCA) return NULL;
            char *yeni = malloc(ARENA_PARCA);
            if (!yeni) hafiza_doldu();
            EnterCriticalSection(&arena_kilidi);
            if (arena_parca_sayisi >= ARENA_EN_FAZLA_PARCA * 4) { LeaveCriticalSection(&arena_kilidi); free(yeni); return NULL; }
            arena_parcalar[arena_parca_sayisi] = yeni;
            InterlockedIncrement(&arena_parca_sayisi);
            LeaveCriticalSection(&arena_kilidi);
            CA->parcalar[CA->parca_sayim++] = yeni;
        }
        CA->simdiki++;
        CA->konum = 0;
    }
    void *p = CA->parcalar[CA->simdiki] + CA->konum;
    CA->konum += boyut;
    CA->canli++;
    return p;
}

/* Bu adres arenada mı? (parça sayısı çok az; birkaç karşılaştırma) */
static int arena_mi(const void *p) {
    const char *c = (const char *)p;
    int n = (int)arena_parca_sayisi;
    for (int i = 0; i < n; i++)
        if (c >= arena_parcalar[i] && c < arena_parcalar[i] + ARENA_PARCA) return 1;
    return 0;
}

/* Liste/nesne/sözlük başlıkları için yer al / geri ver */
static void *vash_al(size_t boyut) {
    if (CA->aktif && !CA->kapali) {
        void *p = arena_al(boyut);
        if (p) return p;
    }
    void *p = malloc(boyut);
    if (!p) hafiza_doldu();
    return p;
}

static void vash_ver(void *p) {
    if (arena_parca_sayisi && arena_mi(p)) { CA->canli--; return; }   /* arenadaysa: blok sonunda toplu boşalır */
    free(p);
}

static int64_t kacir(int64_t tur, int64_t v);   /* aşağıda: arenadaki bir değeri normal belleğe kopyala */

/* Arenadaki bir değer, arenada OLMAYAN bir kaba (liste/nesne/sözlük) konacaksa önce kopyalanır */
#define KAP_KONTROL(kap, tur, v) \
    if (CA->aktif && (tur) >= T_TEXT && (v) && !arena_mi(kap) && arena_mi((void *)(intptr_t)(v))) (v) = kacir((tur), (v))

void arena_baslat(void) {
    if (CA->aktif >= ARENA_EN_DERIN) {
        fflush(stdout);
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI: En fazla %d arena bloğu iç içe olabilir.\n", "\nRUNTIME ERROR: At most %d arena blocks can be nested inside each other.\n"), ARENA_EN_DERIN);
        exit(1);
    }
    CA->isaretler[CA->aktif].parca = CA->simdiki;
    CA->isaretler[CA->aktif].konum = CA->konum;
    CA->aktif++;
}

/* Harf önbelleği: metin[i] ve metin.length her seferinde metnin başından saymasın.
 * Türkçe harfler birden çok bayt olduğu için i. harfin yeri ancak saymakla bulunur;
 * en son bakılan uzun metni ve orada kalınan yeri hatırlarız (harf harf gezen döngüler hızlanır).
 * Sadece paralel bölüm dışında kullanılır; metin silinince ya da arena bitince unutulur. */
static struct {
    const char *m;          /* hangi metin (NULL: hiçbiri) */
    int64_t harf_sayisi;    /* -1: henüz sayılmadı */
    int64_t sira;           /* en son bulunan harfin sırası (0'dan) ... */
    const char *p;          /* ... ve yeri */
} harf_onbellek;
#define HARF_ONBELLEK_SINIRI 32                  /* bundan kısa metinlerde saymak zaten çok ucuz */
#define HARF_ONBELLEK_UNUT(x) do { if (harf_onbellek.m == (x)) harf_onbellek.m = NULL; } while (0)

void arena_bitir(void) {
    harf_onbellek.m = NULL;                          /* arenadaki metinlerin yeri yeniden kullanılacak */
    CA->aktif--;
    CA->simdiki = CA->isaretler[CA->aktif].parca;    /* bloğun başındaki yere geri dön: hepsi boşaldı */
    CA->konum = CA->isaretler[CA->aktif].konum;
    if (CA->aktif == 0 && !paralel_aktif && CA->canli != 0) {
        /* Derleyicide bir eksik: arenadan dışarı kopyalanmadan kaçan bir değer var */
        const char *rapor = getenv("DIL_BELLEK");
        if (rapor && rapor[0] == '1')
            fprintf(stderr, MESAJ("\n[bellek] UYARI: arena bloğundan kaçan %lld değer var\n", "\n[memory] WARNING: %lld values escaped from an arena block\n"), (long long)CA->canli);
        CA->canli = 0;
    }
}

/* uzunluk: harf sayısı (sondaki \0 hariç) */
static char *metin_ayir(size_t uzunluk) {
    size_t toplam = sizeof(Baslik) + uzunluk + 1;
    Baslik *b = NULL;
    if (CA->aktif && !CA->kapali && (b = arena_al(toplam)) != NULL) {
        /* arenadan alındı */
    } else if (toplam <= KUCUK_SINIR) {
        b = kucuk_al((toplam + 15) / 16);
    } else {
        b = malloc(toplam);
        if (!b) hafiza_doldu();
    }
    b->sayac = 1;
    b->uzunluk = (int64_t)uzunluk;
    SAYAC_ARTIR(toplam_ayrilan);
    SAYAC_ARTIR(canli);
    return (char *)(b + 1);
}

void tut(const char *m) {
    if (m && SAYAC(m) >= 0) {
        SAYAC_ARTIR(SAYAC(m));
    }
}

void birak(const char *m) {
    if (m && SAYAC(m) > 0) {
        if (sayac_azalt(&SAYAC(m)) == 0) {
            HARF_ONBELLEK_UNUT(m);
            size_t toplam = sizeof(Baslik) + (size_t)UZUNLUK(m) + 1;
            if (arena_parca_sayisi && arena_mi(BASLIK(m))) {
                CA->canli--;                         /* arenadaki yer blok sonunda toplu boşalır */
            } else if (toplam <= KUCUK_SINIR) {
                kucuk_ver(BASLIK(m), (toplam + 15) / 16);
            } else {
                free(BASLIK(m));
            }
            sayac_azalt(&canli);
        }
    }
}

/* İki metin eşit mi? Önce uzunluklara bak (çoğu zaman burada biter). */
int32_t metin_esit(const char *a, const char *b) {
    if (a == b) return 1;
    if (UZUNLUK(a) != UZUNLUK(b)) return 0;
    return memcmp(a, b, (size_t)UZUNLUK(a)) == 0;
}

static void bellek_raporu(void) {
    fflush(stdout);
    fprintf(stderr, MESAJ("\n[bellek] hafızadan %lld kez yer alındı, şu an hâlâ %lld tanesi geri verilmedi\n", "\n[memory] memory was reserved %lld times, %lld of them are still not given back\n"),
            (long long)toplam_ayrilan, (long long)canli);
}

static void saat_ve_rastgele_baslat(void);   /* dosyanın sonunda */

/* Program başlarken bir kere çağrılır. */
void calisma_baslat(void) {
#ifdef _WIN32
    /* Windows konsolu Türkçe karakterleri (ş, ğ, ı...) doğru göstersin */
    SetConsoleOutputCP(CP_UTF8);
#endif
    dili_belirle();
    InitializeCriticalSection(&yaz_kilidi);
    InitializeCriticalSection(&arena_kilidi);
    InitializeCriticalSection(&toplama_kilidi);
    saat_ve_rastgele_baslat();
    const char *rapor = getenv("DIL_BELLEK");
    if (rapor && rapor[0] == '1') {
        atexit(bellek_raporu);
    }
}

/* ---------- Ondalık sayıyı metne çevirme ----------
 * 3.5 → "3.5",  2.0 → "2.0" (sonuna .0 ekle ki tam sayıyla karışmasın),
 * 0.1 + 0.2 → "0.3" (15 basamak hassasiyet yeter, sondaki gürültüyü gizler) */
static void float_metne(double x, char *tampon, size_t boyut) {
    snprintf(tampon, boyut, "%.15g", x);
    if (!strpbrk(tampon, ".eEn")) {   /* nokta yoksa (ve inf/nan değilse) */
        strcat(tampon, ".0");
    }
}

/* ---------- print / write için ---------- */
static int int_yaziya(int64_t x, char *tampon);
void yaz_int(int64_t x)     { char t[24]; int_yaziya(x, t); fputs(t, stdout); }
void yaz_bool(int8_t x)     { fputs(x ? "true" : "false", stdout); }
void yaz_text(const char *s){ if (s) fwrite(s, 1, (size_t)UZUNLUK(s), stdout); }
void yaz_bosluk(void)       { putchar(' '); }
void yaz_satir(void)        { putchar('\n'); }
void yaz_float(double x) {
    char tampon[64];
    float_metne(x, tampon, sizeof tampon);
    fputs(tampon, stdout);
}

/* ---------- "Merhaba {isim}" için: değerleri metne çevir ve birleştir ----------
 * Bunların döndürdüğü metinler YENİ ve sayaçları 1: sahibi onları çağıran kod. */
/* Tam sayıyı hızlıca yazıya çevir (snprintf genel amaçlı olduğu için yavaş).
 * Rakamları sondan başa doğru üretir: 123 → '3', '2', '1' → ters çevir.
 * Döndürür: yazılan harf sayısı (sondaki \0 hariç). */
static int int_yaziya(int64_t x, char *tampon) {
    char ters[24];
    int n = 0;
    uint64_t u = x < 0 ? (uint64_t)0 - (uint64_t)x : (uint64_t)x;
    do {
        ters[n++] = (char)('0' + u % 10);
        u /= 10;
    } while (u);
    int i = 0;
    if (x < 0) tampon[i++] = '-';
    while (n) tampon[i++] = ters[--n];
    tampon[i] = '\0';
    return i;
}

char *metin_int(int64_t x) {
    char tampon[24];
    int n = int_yaziya(x, tampon);
    char *s = metin_ayir(n);
    memcpy(s, tampon, n + 1);
    return s;
}

/* "Sayı {i}" için: metin + tam sayıyı TEK seferde, tek bir yer alarak birleştir */
char *metin_birlestir_int(const char *a, int64_t x) {
    char tampon[24];
    int n = int_yaziya(x, tampon);
    size_t la = (size_t)UZUNLUK(a);
    char *s = metin_ayir(la + n);
    memcpy(s, a, la);
    memcpy(s + la, tampon, n + 1);
    return s;
}

char *metin_float(double x) {
    char tampon[64];
    float_metne(x, tampon, sizeof tampon);
    size_t n = strlen(tampon);
    char *s = metin_ayir(n);
    memcpy(s, tampon, n + 1);
    return s;
}

/* true / false sabit metinler: sayaçları -1 (hiç temizlenmez) */
static struct { int64_t sayac; int64_t uzunluk; char yazi[8]; }
    SABIT_TRUE = {-1, 4, "true"}, SABIT_FALSE = {-1, 5, "false"};
const char *metin_bool(int8_t x) { return x ? SABIT_TRUE.yazi : SABIT_FALSE.yazi; }

char *metin_birlestir(const char *a, const char *b) {
    size_t la = (size_t)UZUNLUK(a), lb = (size_t)UZUNLUK(b);
    char *s = metin_ayir(la + lb);
    memcpy(s, a, la);
    memcpy(s + la, b, lb + 1);
    return s;
}

/* =====================================================================
 *  LİSTELER
 * =====================================================================
 *
 *  Bir liste hafızada şöyle durur:
 *
 *      Liste { sayaç | uzunluk | kapasite | eleman türü | veri → [e1][e2][e3][  ][  ] }
 *                                                              ^ dolu     ^ boş yer (büyüme payı)
 *
 *  - Her eleman 8 bayttır (int, float, bool, metin adresi, liste adresi hepsi sığar).
 *  - kapasite dolunca veri alanı 2 katına büyütülür → add() çoğu zaman tek adım sürer.
 *  - Eleman türü, liste silinirken içindeki metinleri/listeleri de bırakmak ve
 *    print(liste) yaparken doğru yazmak için saklanır.
 *
 *  KOPYALA-YAZ (copy-on-write):
 *    var b = a      → kopyalanmaz, sadece sayaç 2 olur (ikisi aynı listeyi paylaşır)
 *    b.add(4)       → değiştirmeden önce liste_yazilabilir(b): sayaç 1 değilse,
 *                     b için GERÇEK bir kopya çıkarılır. a hiç etkilenmez.
 *  Böylece "her liste ayrı" kuralı korunur, ama gereksiz kopya hiç yapılmaz.
 * ===================================================================== */

enum { T_INT = 0, T_FLOAT = 1, T_BOOL = 2, T_TEXT = 3, T_LISTE = 4, T_NESNE = 5, T_SOZLUK = 6, T_BYTES = 7, T_KAPANIS = 8 };   /* T_KAPANIS: lambda / fonksiyon değeri */   /* T_BYTES: bytes (Liste yapısı, veri bayt bayt) */

typedef struct Nesne Nesne;
void nesne_birak(Nesne *o);
void nesne_yaz(Nesne *o);
typedef struct Sozluk Sozluk;
void sozluk_birak(Sozluk *s);
void sozluk_yaz(Sozluk *s);
static void eleman_yaz(int64_t tur, int64_t v);

typedef struct Liste {
    int64_t sayac;
    int64_t uzunluk;
    int64_t kapasite;
    int64_t tur;          /* elemanların türü (T_INT ...) */
    int64_t *veri;
} Liste;

void liste_birak(Liste *l);

/* [bool] listelerinde her eleman 1 bayt (C'deki gibi), diğerlerinde 8 bayt */
static inline size_t eleman_boyu(int64_t tur) { return tur == T_BOOL ? 1 : sizeof(int64_t); }
static inline int64_t veri_al(const Liste *l, int64_t i) {
    return l->tur == T_BOOL ? (int64_t)((const uint8_t *)l->veri)[i] : l->veri[i];
}
static inline void veri_koy(Liste *l, int64_t i, int64_t v) {
    if (l->tur == T_BOOL) ((uint8_t *)l->veri)[i] = (uint8_t)(v != 0);
    else l->veri[i] = v;
}
static Liste *bayt_kopya(Liste *l, int sahiplik_birak);
static void bayt_yaz(Liste *l);

Liste *liste_yeni(int64_t tur, int64_t kapasite) {
    Liste *l = vash_al(sizeof(Liste));
    l->sayac = 1;
    l->uzunluk = 0;
    l->kapasite = kapasite;
    l->tur = tur;
    l->veri = kapasite ? malloc(eleman_boyu(tur) * (size_t)kapasite) : NULL;
    if (kapasite && !l->veri) hafiza_doldu();
    SAYAC_ARTIR(toplam_ayrilan);
    SAYAC_ARTIR(canli);
    return l;
}

static void eleman_tut(int64_t tur, int64_t v) {
    if (tur == T_TEXT) tut((const char *)(intptr_t)v);
    else if (tur >= T_LISTE && v) SAYAC_ARTIR(*(int64_t *)(intptr_t)v);  /* liste/nesne/sözlük: ilk alan sayaç */
}

typedef struct Kapanis Kapanis;
void kapanis_birak(Kapanis *k);
static void eleman_birak(int64_t tur, int64_t v) {
    if (tur == T_TEXT) birak((const char *)(intptr_t)v);
    else if (tur == T_KAPANIS) kapanis_birak((Kapanis *)(intptr_t)v);
    else if (tur == T_LISTE) liste_birak((Liste *)(intptr_t)v);
    else if (tur == T_NESNE) nesne_birak((Nesne *)(intptr_t)v);
    else if (tur == T_SOZLUK) sozluk_birak((Sozluk *)(intptr_t)v);
}

void liste_tut(Liste *l) {
    if (l) SAYAC_ARTIR(l->sayac);
}

void liste_birak(Liste *l) {
    if (l && sayac_azalt(&l->sayac) == 0) {
        if (l->tur >= T_TEXT && l->tur != T_BYTES) {                 /* içindeki metinleri/listeleri de bırak */
            for (int64_t i = 0; i < l->uzunluk; i++) eleman_birak(l->tur, l->veri[i]);
        }
        free(l->veri);
        vash_ver(l);
        sayac_azalt(&canli);
    }
}

static void sinir_kontrolu(Liste *l, int64_t sira, int64_t satir) {
    if (sira >= 1 && sira <= l->uzunluk) return;
    fflush(stdout);
    if (sira == 0) {
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): Vash'ta listeler 1'den başlar; ilk eleman liste[1].\n", "\nRUNTIME ERROR (line %lld): In Vash, lists start at 1; the first element is list[1].\n"),
                (long long)satir);
    } else {
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): %lld elemanlı listenin %lld. elemanı yok.\n", "\nRUNTIME ERROR (line %lld): The list has %lld elements, so there is no element number %lld.\n"),
                (long long)satir, (long long)l->uzunluk, (long long)sira);
    }
    exit(1);
}

/* Derleyici eleman okumayı kendisi satır içine yazar; sınır dışıysa bunu çağırır */
void hata_sinir(Liste *l, int64_t sira, int64_t satir) {
    sinir_kontrolu(l, sira, satir);   /* hata mesajını yazıp programı durdurur */
    exit(1);
}

int64_t liste_al(Liste *l, int64_t sira, int64_t satir) {
    sinir_kontrolu(l, sira, satir);
    return veri_al(l, sira - 1);
}

/* Not: yeni değerin sahipliği listeye geçer (derleyici önceden tut() yapar) */
void liste_koy(Liste *l, int64_t sira, int64_t deger, int64_t satir) {
    sinir_kontrolu(l, sira, satir);
    KAP_KONTROL(l, l->tur, deger);
    int64_t eski = veri_al(l, sira - 1);
    veri_koy(l, sira - 1, deger);
    eleman_birak(l->tur, eski);
}

void liste_ekle(Liste *l, int64_t deger) {
    KAP_KONTROL(l, l->tur, deger);
    if (l->uzunluk == l->kapasite) {              /* yer kalmadı: 2 katına büyüt */
        int64_t yeni = l->kapasite ? l->kapasite * 2 : 4;
        int64_t *v = realloc(l->veri, eleman_boyu(l->tur) * (size_t)yeni);
        if (!v) hafiza_doldu();
        l->veri = v;
        l->kapasite = yeni;
    }
    veri_koy(l, l->uzunluk++, deger);
}

/* repeat N { liste.add(sabit) } kalıbı: N tane aynı değeri tek seferde ekle (sayı/bool listeleri) */
void liste_doldur(Liste *l, int64_t kac, int64_t deger) {
    if (kac <= 0) return;
    int64_t yeni = l->uzunluk + kac;
    if (yeni > l->kapasite) {
        int64_t kap = l->kapasite ? l->kapasite * 2 : 4;
        if (kap < yeni) kap = yeni;
        int64_t *v = realloc(l->veri, eleman_boyu(l->tur) * (size_t)kap);
        if (!v) hafiza_doldu();
        l->veri = v;
        l->kapasite = kap;
    }
    if (l->tur == T_BOOL) memset((uint8_t *)l->veri + l->uzunluk, deger != 0, (size_t)kac);
    else for (int64_t i = 0; i < kac; i++) l->veri[l->uzunluk + i] = deger;
    l->uzunluk = yeni;
}

void liste_sil(Liste *l, int64_t sira, int64_t satir) {
    sinir_kontrolu(l, sira, satir);
    eleman_birak(l->tur, veri_al(l, sira - 1));
    size_t b = eleman_boyu(l->tur);
    memmove((char *)l->veri + (sira - 1) * b, (char *)l->veri + sira * b, b * (size_t)(l->uzunluk - sira));
    l->uzunluk--;
}

int64_t liste_uzunluk(Liste *l) {
    return l->uzunluk;
}

/* liste.sort(): kararlı birleştirmeli sıralama (eşit elemanların sırası korunur).
   once(a, b) "a, b'den önce gelmeli mi?" sorusunu cevaplar. */
typedef int32_t (*Once)(int64_t, int64_t);
static int32_t once_int(int64_t a, int64_t b) { return a < b; }
static int32_t once_float(int64_t a, int64_t b) {
    double x, y;
    memcpy(&x, &a, sizeof x);
    memcpy(&y, &b, sizeof y);
    return x < y;
}
static int32_t once_text(int64_t a, int64_t b) {     /* harf kodlarına göre (UTF-8 bayt sırası = kod sırası) */
    const char *x = (const char *)(intptr_t)a, *y = (const char *)(intptr_t)b;
    int64_t n = UZUNLUK(x) < UZUNLUK(y) ? UZUNLUK(x) : UZUNLUK(y);
    int c = memcmp(x, y, (size_t)n);
    return c < 0 || (c == 0 && UZUNLUK(x) < UZUNLUK(y));
}
static int32_t once_bool(int64_t a, int64_t b) { return a == 0 && b != 0; }

static void sirala_parca(int64_t *v, int64_t *gecici, int64_t n, Once once) {
    if (n < 2) return;
    if (n <= 16) {                                    /* küçük parça: araya yerleştirme */
        for (int64_t i = 1; i < n; i++) {
            int64_t x = v[i], j = i;
            while (j > 0 && once(x, v[j - 1])) { v[j] = v[j - 1]; j--; }
            v[j] = x;
        }
        return;
    }
    int64_t m = n / 2;
    sirala_parca(v, gecici, m, once);
    sirala_parca(v + m, gecici, n - m, once);
    if (!once(v[m], v[m - 1])) return;                /* zaten sıralı */
    memcpy(gecici, v, sizeof(int64_t) * (size_t)m);
    int64_t i = 0, j = m, k = 0;
    while (i < m && j < n) v[k++] = once(v[j], gecici[i]) ? v[j++] : gecici[i++];
    while (i < m) v[k++] = gecici[i++];
}

void liste_sirala(Liste *l, Once once) {
    if (l->uzunluk < 2) return;
    if (l->tur == T_BOOL) {                           /* 1 baytlık elemanlar: geçici olarak 8 bayta açıp sırala */
        int64_t *g = malloc(sizeof(int64_t) * (size_t)l->uzunluk);
        if (!g) hafiza_doldu();
        for (int64_t i = 0; i < l->uzunluk; i++) g[i] = veri_al(l, i);
        int64_t *veri = l->veri;
        l->veri = g;
        l->tur = T_INT;
        liste_sirala(l, once);
        l->tur = T_BOOL;
        l->veri = veri;
        for (int64_t i = 0; i < l->uzunluk; i++) veri_koy(l, i, g[i]);
        free(g);
        return;
    }
    int64_t *gecici = malloc(sizeof(int64_t) * (size_t)(l->uzunluk / 2 + 1));
    if (!gecici) hafiza_doldu();
    sirala_parca(l->veri, gecici, l->uzunluk, once);
    free(gecici);
}

/* Taban sıralaması (radix, LSD, 16 bitlik 4 basamak): karşılaştırmasız, kararlı, O(n).
   Tam sayılarda işaret biti çevrilir; ondalıklarda negatiflerin bütün bitleri çevrilir (IEEE sırası);
   -0.0, +0.0 sayılır (birleştirmeli sıralamadaki gibi eşit kalsınlar). */
static inline uint64_t taban_anahtar(uint64_t u, int ondalik) {
    if (!ondalik) return u ^ 0x8000000000000000ULL;
    if (u == 0x8000000000000000ULL) u = 0;
    return (u >> 63) ? ~u : (u ^ 0x8000000000000000ULL);
}

static void taban_sirala(uint64_t *v, int64_t n, int ondalik) {
    uint64_t *g = malloc(sizeof(uint64_t) * (size_t)n);
    size_t *sayim = calloc(4 * 65536, sizeof(size_t));
    if (!g || !sayim) hafiza_doldu();
    for (int64_t i = 0; i < n; i++) {
        uint64_t k = taban_anahtar(v[i], ondalik);
        sayim[0 * 65536 + (k & 0xFFFF)]++;
        sayim[1 * 65536 + ((k >> 16) & 0xFFFF)]++;
        sayim[2 * 65536 + ((k >> 32) & 0xFFFF)]++;
        sayim[3 * 65536 + (k >> 48)]++;
    }
    uint64_t *kaynak = v, *hedef = g;
    for (int b = 0; b < 4; b++) {
        size_t *c = sayim + b * 65536;
        uint64_t ilk = (taban_anahtar(kaynak[0], ondalik) >> (16 * b)) & 0xFFFF;
        if (c[ilk] == (size_t)n) continue;            /* herkes aynı basamakta: bu tur boşuna */
        size_t top = 0;
        for (int d = 0; d < 65536; d++) { size_t x = c[d]; c[d] = top; top += x; }
        for (int64_t i = 0; i < n; i++) {
            uint64_t u = kaynak[i];
            hedef[c[(taban_anahtar(u, ondalik) >> (16 * b)) & 0xFFFF]++] = u;
        }
        uint64_t *t = kaynak; kaynak = hedef; hedef = t;
    }
    if (kaynak != v) memcpy(v, kaynak, sizeof(uint64_t) * (size_t)n);
    free(sayim);
    free(g);
}

void liste_sirala_dogal(Liste *l) {
    if ((l->tur == T_INT || l->tur == T_FLOAT) && l->uzunluk >= 4096) {
        taban_sirala((uint64_t *)l->veri, l->uzunluk, l->tur == T_FLOAT);
        return;
    }
    switch (l->tur) {
        case T_INT:   liste_sirala(l, once_int); break;
        case T_FLOAT: liste_sirala(l, once_float); break;
        case T_BOOL:  liste_sirala(l, once_bool); break;
        default:      liste_sirala(l, once_text); break;
    }
}

/* Değiştirmeden önce çağrılır: liste paylaşılıyorsa kendine ait bir kopya çıkar */
Liste *liste_yazilabilir(Liste *l) {
    if (l->sayac == 1) return l;                   /* tek sahibi biziz: doğrudan değiştir */
    if (l->tur == T_BYTES) return bayt_kopya(l, 1);
    CA->kapali++;                                /* kopya değişkenin kendisine ait: normal bellekte */
    Liste *y = liste_yeni(l->tur, l->uzunluk > 4 ? l->uzunluk : 4);
    CA->kapali--;
    memcpy(y->veri, l->veri, eleman_boyu(l->tur) * (size_t)l->uzunluk);
    y->uzunluk = l->uzunluk;
    if (l->tur >= T_TEXT) {
        for (int64_t i = 0; i < l->uzunluk; i++) eleman_tut(l->tur, l->veri[i]);
    }
    sayac_azalt(&l->sayac);                        /* eski liste artık bizi saymıyor */
    return y;
}

void liste_yaz(Liste *l) {
    if (l->tur == T_BYTES) { bayt_yaz(l); return; }
    putchar('[');
    for (int64_t i = 0; i < l->uzunluk; i++) {
        if (i > 0) fputs(", ", stdout);
        eleman_yaz(l->tur, veri_al(l, i));
    }
    putchar(']');
}

/* Bir liste/nesne/sözlük elemanını yazdır (metinler tırnak içinde) */
static void eleman_yaz(int64_t tur, int64_t v) {
    if (tur >= T_TEXT && v == 0) { fputs("none", stdout); return; }   /* yok olabilen (T?) alan/eleman */
    switch (tur) {
        case T_INT:    yaz_int(v); break;
        case T_FLOAT:  { double d; memcpy(&d, &v, sizeof d); yaz_float(d); break; }
        case T_BOOL:   yaz_bool((int8_t)v); break;
        case T_TEXT:   putchar('"'); yaz_text((const char *)(intptr_t)v); putchar('"'); break;
        case T_LISTE:  liste_yaz((Liste *)(intptr_t)v); break;
        case T_NESNE:  nesne_yaz((Nesne *)(intptr_t)v); break;
        case T_SOZLUK: sozluk_yaz((Sozluk *)(intptr_t)v); break;
        case T_KAPANIS: fputs("<fn>", stdout); break;
    }
}

/* =====================================================================
 *  NESNELER (kendi tipler: type Ogrenci { ... })
 * =====================================================================
 *
 *      Nesne { sayaç | tür bilgisi → { "Ogrenci", 2 alan, adlar, türler } | alan1 | alan2 | ... }
 *
 *  - Her alan 8 bayttır (liste elemanları gibi).
 *  - "Tür bilgisi" her tip için derleyicinin ürettiği sabit bir tablodur. Nesne silinirken
 *    hangi alanların metin/liste/nesne olduğunu (bırakılması gerektiğini) ve print(nesne)
 *    yaparken alanların adlarını buradan öğreniriz.
 *  - Listeler gibi KOPYALA-YAZ: var b = a → paylaşılır; b.ad = "x" → önce b kendi kopyasını alır.
 * ===================================================================== */

typedef struct TurBilgisi {
    const char *ad;
    int64_t alan_sayisi;
    const char **alan_adlari;
    const int64_t *alan_turleri;     /* T_INT ... T_NESNE */
    int64_t cesit;                   /* enum çeşitlerinde: kaçıncı çeşit (match bununla dallanır) */
} TurBilgisi;

struct Nesne {
    int64_t sayac;
    const TurBilgisi *tur;
    int64_t alanlar[];
};

Nesne *nesne_yeni(const TurBilgisi *tur) {
    Nesne *o = vash_al(sizeof(Nesne) + sizeof(int64_t) * (size_t)tur->alan_sayisi);
    o->sayac = 1;
    o->tur = tur;
    memset(o->alanlar, 0, sizeof(int64_t) * (size_t)tur->alan_sayisi);
    SAYAC_ARTIR(toplam_ayrilan);
    SAYAC_ARTIR(canli);
    return o;
}

void nesne_tut(Nesne *o) {
    if (o) SAYAC_ARTIR(o->sayac);
}

void nesne_birak(Nesne *o) {
    if (o && sayac_azalt(&o->sayac) == 0) {
        for (int64_t i = 0; i < o->tur->alan_sayisi; i++) {   /* metin/liste/nesne alanlarını bırak */
            eleman_birak(o->tur->alan_turleri[i], o->alanlar[i]);
        }
        vash_ver(o);
        sayac_azalt(&canli);
    }
}

/* Değiştirmeden önce çağrılır: nesne paylaşılıyorsa kendine ait bir kopya çıkar */
Nesne *nesne_yazilabilir(Nesne *o) {
    if (o->sayac == 1) return o;
    CA->kapali++;
    Nesne *y = nesne_yeni(o->tur);
    CA->kapali--;
    for (int64_t i = 0; i < o->tur->alan_sayisi; i++) {
        y->alanlar[i] = o->alanlar[i];
        eleman_tut(o->tur->alan_turleri[i], o->alanlar[i]);
    }
    sayac_azalt(&o->sayac);
    return y;
}

/* Alana yeni değer koy (sahipliği alana geçer), eskisini bırak */
void nesne_alan_koy(Nesne *o, int64_t sira, int64_t deger) {
    KAP_KONTROL(o, o->tur->alan_turleri[sira], deger);
    int64_t eski = o->alanlar[sira];
    o->alanlar[sira] = deger;
    eleman_birak(o->tur->alan_turleri[sira], eski);
}

void nesne_yaz(Nesne *o) {
    fputs(o->tur->ad, stdout);
    if (o->tur->alan_sayisi == 0) return;          /* alanı olmayan enum çeşidi: sadece adı (Nakit) */
    putchar('(');
    for (int64_t i = 0; i < o->tur->alan_sayisi; i++) {
        if (i > 0) fputs(", ", stdout);
        fputs(o->tur->alan_adlari[i], stdout);
        fputs(": ", stdout);
        eleman_yaz(o->tur->alan_turleri[i], o->alanlar[i]);
    }
    putchar(')');
}

/* =====================================================================
 *  SÖZLÜKLER: {"Ali": 90, "Ayşe": 85}
 * =====================================================================
 *
 *  İki parça:
 *    1) KAYITLAR: anahtarlar[] ve degerler[] eklendiği sırayla durur
 *       (keys() bu yüzden ekleme sırasını korur, Python gibi).
 *    2) TABLO: "bu anahtar hangi kayıtta?" sorusunu tek adımda cevaplayan
 *       hash tablosu. Anahtar bir sayıya (hash) çevrilir, o sayı tablodaki
 *       yeri gösterir. Yer doluysa bir sonrakine bakılır.
 *
 *  Silinen kayıt "silindi" diye işaretlenir; tablo büyütülürken temizlenir.
 *  Listeler gibi KOPYALA-YAZ ve sayaçlıdır.
 * ===================================================================== */

struct Sozluk {
    int64_t sayac;
    int64_t uzunluk;            /* canlı kayıt sayısı */
    int64_t anahtar_tur, deger_tur;
    int64_t kayit_sayisi;       /* kullanılan kayıt yeri (silinenler dahil) */
    int64_t kayit_kap;
    int64_t *anahtarlar, *degerler;
    unsigned char *silindi;
    int64_t *tablo;             /* kayıt numarası; -1 = boş */
    int64_t tablo_boy;          /* 2'nin kuvveti */
};

static uint64_t sozluk_hash(int64_t tur, int64_t k) {
    if (tur == T_TEXT) {                               /* FNV-1a */
        const unsigned char *p = (const unsigned char *)(intptr_t)k;
        uint64_t h = 1469598103934665603ULL;
        for (int64_t i = 0; i < UZUNLUK(p); i++) { h ^= p[i]; h *= 1099511628211ULL; }
        return h;
    }
    uint64_t x = (uint64_t)k;                          /* sayıları karıştır (splitmix) */
    x ^= x >> 33; x *= 0xff51afd7ed558ccdULL; x ^= x >> 33; x *= 0xc4ceb9fe1a85ec53ULL; x ^= x >> 33;
    return x;
}

static int sozluk_esit(int64_t tur, int64_t a, int64_t b) {
    if (tur == T_TEXT) return metin_esit((const char *)(intptr_t)a, (const char *)(intptr_t)b);
    return a == b;
}

Sozluk *sozluk_yeni(int64_t anahtar_tur, int64_t deger_tur) {
    Sozluk *s = vash_al(sizeof(Sozluk));
    memset(s, 0, sizeof(Sozluk));
    s->sayac = 1;
    s->anahtar_tur = anahtar_tur;
    s->deger_tur = deger_tur;
    SAYAC_ARTIR(toplam_ayrilan);
    SAYAC_ARTIR(canli);
    return s;
}

void sozluk_tut(Sozluk *s) { if (s) SAYAC_ARTIR(s->sayac); }

void sozluk_birak(Sozluk *s) {
    if (s && sayac_azalt(&s->sayac) == 0) {
        for (int64_t i = 0; i < s->kayit_sayisi; i++) {
            if (s->silindi[i]) continue;
            eleman_birak(s->anahtar_tur, s->anahtarlar[i]);
            eleman_birak(s->deger_tur, s->degerler[i]);
        }
        free(s->anahtarlar); free(s->degerler); free(s->silindi); free(s->tablo);
        vash_ver(s);
        sayac_azalt(&canli);
    }
}

int64_t sozluk_uzunluk(Sozluk *s) { return s->uzunluk; }

static int64_t sozluk_konum(Sozluk *s, int64_t k) {
    if (!s->tablo_boy) return -1;
    uint64_t maske = (uint64_t)s->tablo_boy - 1, i = sozluk_hash(s->anahtar_tur, k) & maske;
    for (;;) {
        int64_t kayit = s->tablo[i];
        if (kayit < 0) return -1;
        if (!s->silindi[kayit] && sozluk_esit(s->anahtar_tur, s->anahtarlar[kayit], k)) return kayit;
        i = (i + 1) & maske;
    }
}

static void sozluk_tabloya_koy(Sozluk *s, int64_t kayit) {
    uint64_t maske = (uint64_t)s->tablo_boy - 1, i = sozluk_hash(s->anahtar_tur, s->anahtarlar[kayit]) & maske;
    while (s->tablo[i] >= 0) i = (i + 1) & maske;
    s->tablo[i] = kayit;
}

/* Silinenleri at, gerekirse büyüt, tabloyu baştan kur */
static void sozluk_yeniden_kur(Sozluk *s, int64_t gereken) {
    int64_t n = 0;
    for (int64_t i = 0; i < s->kayit_sayisi; i++) {
        if (s->silindi[i]) continue;
        s->anahtarlar[n] = s->anahtarlar[i];
        s->degerler[n] = s->degerler[i];
        s->silindi[n] = 0;
        n++;
    }
    s->kayit_sayisi = n;
    int64_t kap = 8;
    while (kap < gereken) kap *= 2;
    if (kap != s->kayit_kap) {
        s->anahtarlar = realloc(s->anahtarlar, sizeof(int64_t) * (size_t)kap);
        s->degerler = realloc(s->degerler, sizeof(int64_t) * (size_t)kap);
        s->silindi = realloc(s->silindi, (size_t)kap);
        if (!s->anahtarlar || !s->degerler || !s->silindi) hafiza_doldu();
        s->kayit_kap = kap;
    }
    free(s->tablo);
    s->tablo_boy = kap * 2;                             /* tablo hep en az yarı boş */
    s->tablo = malloc(sizeof(int64_t) * (size_t)s->tablo_boy);
    if (!s->tablo) hafiza_doldu();
    memset(s->tablo, 0xff, sizeof(int64_t) * (size_t)s->tablo_boy);   /* hepsi -1 */
    for (int64_t i = 0; i < n; i++) sozluk_tabloya_koy(s, i);
}

/* s[k] = v. k ve v'nin sahipliği sözlüğe geçer (derleyici önceden tut() yapar). */
void sozluk_koy(Sozluk *s, int64_t k, int64_t v) {
    KAP_KONTROL(s, s->anahtar_tur, k);
    KAP_KONTROL(s, s->deger_tur, v);
    int64_t kayit = sozluk_konum(s, k);
    if (kayit >= 0) {                                   /* zaten var: değeri değiştir */
        eleman_birak(s->anahtar_tur, k);
        int64_t eski = s->degerler[kayit];
        s->degerler[kayit] = v;
        eleman_birak(s->deger_tur, eski);
        return;
    }
    if (s->kayit_sayisi >= s->kayit_kap) sozluk_yeniden_kur(s, (s->uzunluk + 1) * 2);
    kayit = s->kayit_sayisi++;
    s->anahtarlar[kayit] = k;
    s->degerler[kayit] = v;
    s->silindi[kayit] = 0;
    sozluk_tabloya_koy(s, kayit);
    s->uzunluk++;
}

static void sozluk_anahtar_yok(Sozluk *s, int64_t k, int64_t satir) {
    fflush(stdout);
    if (s->anahtar_tur == T_TEXT)
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): Sözlükte \"%s\" anahtarı yok.\n"
                        "   Olmayabilecekse şöyle oku:   sozluk.get(anahtar, else: yedek)\n",
                              "\nRUNTIME ERROR (line %lld): The dictionary has no key \"%s\".\n"
                              "   If the key may be missing, read it like this:   dict.get(key, else: fallback)\n"),
                (long long)satir, (const char *)(intptr_t)k);
    else
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): Sözlükte %lld anahtarı yok.\n"
                        "   Olmayabilecekse şöyle oku:   sozluk.get(anahtar, else: yedek)\n",
                              "\nRUNTIME ERROR (line %lld): The dictionary has no key %lld.\n"
                              "   If the key may be missing, read it like this:   dict.get(key, else: fallback)\n"),
                (long long)satir, (long long)k);
    exit(1);
}

/* s[k]: değeri döndürür (ödünç); yoksa hata */
int64_t sozluk_al(Sozluk *s, int64_t k, int64_t satir) {
    int64_t kayit = sozluk_konum(s, k);
    if (kayit < 0) sozluk_anahtar_yok(s, k, satir);
    return s->degerler[kayit];
}

/* s.get(k, else: ...) için: bulunursa *sonuc'a yaz, 1 döndür */
int32_t sozluk_bul(Sozluk *s, int64_t k, int64_t *sonuc) {
    int64_t kayit = sozluk_konum(s, k);
    if (kayit < 0) return 0;
    *sonuc = s->degerler[kayit];
    return 1;
}

int32_t sozluk_var_mi(Sozluk *s, int64_t k) { return sozluk_konum(s, k) >= 0; }

void sozluk_sil(Sozluk *s, int64_t k, int64_t satir) {
    int64_t kayit = sozluk_konum(s, k);
    if (kayit < 0) sozluk_anahtar_yok(s, k, satir);
    eleman_birak(s->anahtar_tur, s->anahtarlar[kayit]);
    eleman_birak(s->deger_tur, s->degerler[kayit]);
    s->silindi[kayit] = 1;
    s->uzunluk--;
}

static Liste *sozluk_sutun(Sozluk *s, int anahtar_mi) {
    int64_t tur = anahtar_mi ? s->anahtar_tur : s->deger_tur;
    Liste *l = liste_yeni(tur, s->uzunluk > 4 ? s->uzunluk : 4);
    for (int64_t i = 0; i < s->kayit_sayisi; i++) {
        if (s->silindi[i]) continue;
        int64_t v = anahtar_mi ? s->anahtarlar[i] : s->degerler[i];
        eleman_tut(tur, v);
        liste_ekle(l, v);
    }
    return l;
}

Liste *sozluk_anahtarlar(Sozluk *s) { return sozluk_sutun(s, 1); }
Liste *sozluk_degerler(Sozluk *s) { return sozluk_sutun(s, 0); }

/* Değiştirmeden önce: sözlük paylaşılıyorsa kendine ait bir kopya çıkar */
Sozluk *sozluk_yazilabilir(Sozluk *s) {
    if (s->sayac == 1) return s;
    CA->kapali++;
    Sozluk *y = sozluk_yeni(s->anahtar_tur, s->deger_tur);
    CA->kapali--;
    for (int64_t i = 0; i < s->kayit_sayisi; i++) {
        if (s->silindi[i]) continue;
        eleman_tut(s->anahtar_tur, s->anahtarlar[i]);
        eleman_tut(s->deger_tur, s->degerler[i]);
        sozluk_koy(y, s->anahtarlar[i], s->degerler[i]);
    }
    sayac_azalt(&s->sayac);
    return y;
}

/* Arenadaki bir değeri (içindekilerle birlikte) normal belleğe kopyala.
 * v'nin bir sahipliğini alır, normal bellekteki hâlinin bir sahipliğini döndürür.
 * Arenada değilse (ya da arena açık değilse) v'yi olduğu gibi döndürür. */
static int64_t kacir(int64_t tur, int64_t v) {
    if (!CA->aktif || tur < T_TEXT || !v || !arena_mi((void *)(intptr_t)v)) return v;
    CA->kapali++;
    int64_t y = v;
    if (tur == T_TEXT) {
        const char *m = (const char *)(intptr_t)v;
        char *n = metin_ayir((size_t)UZUNLUK(m));
        memcpy(n, m, (size_t)UZUNLUK(m) + 1);
        birak(m);
        y = (int64_t)(intptr_t)n;
    } else if (tur == T_LISTE) {
        Liste *l = (Liste *)(intptr_t)v;
        if (l->tur == T_BYTES) {                  /* bytes: baytları kopyala */
            Liste *n = bayt_kopya(l, 0);
            liste_birak(l);
            CA->kapali--;
            return (int64_t)(intptr_t)n;
        }
        Liste *n = liste_yeni(l->tur, l->uzunluk > 4 ? l->uzunluk : 4);
        for (int64_t i = 0; i < l->uzunluk; i++) {
            eleman_tut(l->tur, veri_al(l, i));
            veri_koy(n, i, kacir(l->tur, veri_al(l, i)));
        }
        n->uzunluk = l->uzunluk;
        liste_birak(l);
        y = (int64_t)(intptr_t)n;
    } else if (tur == T_NESNE) {
        Nesne *o = (Nesne *)(intptr_t)v;
        Nesne *n = nesne_yeni(o->tur);
        for (int64_t i = 0; i < o->tur->alan_sayisi; i++) {
            eleman_tut(o->tur->alan_turleri[i], o->alanlar[i]);
            n->alanlar[i] = kacir(o->tur->alan_turleri[i], o->alanlar[i]);
        }
        nesne_birak(o);
        y = (int64_t)(intptr_t)n;
    } else if (tur == T_SOZLUK) {
        Sozluk *s = (Sozluk *)(intptr_t)v;
        Sozluk *n = sozluk_yeni(s->anahtar_tur, s->deger_tur);
        for (int64_t i = 0; i < s->kayit_sayisi; i++) {
            if (s->silindi[i]) continue;
            eleman_tut(s->anahtar_tur, s->anahtarlar[i]);
            eleman_tut(s->deger_tur, s->degerler[i]);
            sozluk_koy(n, kacir(s->anahtar_tur, s->anahtarlar[i]), kacir(s->deger_tur, s->degerler[i]));
        }
        sozluk_birak(s);
        y = (int64_t)(intptr_t)n;
    }
    CA->kapali--;
    return y;
}

/* Derleyici çağırır: arena bloğunun içinden dışarıdaki bir değişkene (ya da globale) değer konurken */
void *arena_kac(void *v, int64_t tur) {
    return (void *)(intptr_t)kacir(tur, (int64_t)(intptr_t)v);
}

void sozluk_yaz(Sozluk *s) {
    putchar('{');
    int ilk = 1;
    for (int64_t i = 0; i < s->kayit_sayisi; i++) {
        if (s->silindi[i]) continue;
        if (!ilk) fputs(", ", stdout);
        eleman_yaz(s->anahtar_tur, s->anahtarlar[i]);
        fputs(": ", stdout);
        eleman_yaz(s->deger_tur, s->degerler[i]);
        ilk = 0;
    }
    putchar('}');
}

/* ---------- Çalışma hataları ----------
 * Program çalışırken olabilecek hatalar. Mesajı yazıp programı durdurur. */
void hata_sifira_bolme(int64_t satir) {
    fflush(stdout);
    fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): Sıfıra bölme yapılamaz.\n", "\nRUNTIME ERROR (line %lld): Cannot divide by zero.\n"), (long long)satir);
    exit(1);
}

void hata_tasma(int64_t satir) {
    fflush(stdout);
    fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): Sayı çok büyüdü (int en fazla 9.223.372.036.854.775.807 olabilir).\n", "\nRUNTIME ERROR (line %lld): Number too big (an int can be at most 9,223,372,036,854,775,807).\n"),
            (long long)satir);
    exit(1);
}

void hata_sifir_adim(int64_t satir) {
    fflush(stdout);
    fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): 'step' 0 oldu; sayaç hiç ilerlemez, döngü sonsuza kadar sürerdi.\n", "\nRUNTIME ERROR (line %lld): 'step' became 0; the counter would never move and the loop would run forever.\n"),
            (long long)satir);
    exit(1);
}

/* =====================================================================
 *  DIŞ DÜNYA: saat, rastgele sayı, klavye
 * ===================================================================== */

static double baslangic_saniye = 0.0;
static _Thread_local uint64_t rastgele_durum = 0;   /* her çekirdeğin kendi rastgele durumu */

static double simdi_saniye(void) {
#ifdef _WIN32
    LARGE_INTEGER frekans, sayac;
    QueryPerformanceFrequency(&frekans);           /* bilgisayarın en hassas saati */
    QueryPerformanceCounter(&sayac);
    return (double)sayac.QuadPart / (double)frekans.QuadPart;
#else
    return (double)clock() / CLOCKS_PER_SEC;
#endif
}

static void saat_ve_rastgele_baslat(void) {
    baslangic_saniye = simdi_saniye();
    /* Rastgele sayıların "tohumu": her çalıştırmada farklı olsun diye saatten alınır */
#ifdef _WIN32
    LARGE_INTEGER s;
    QueryPerformanceCounter(&s);
    rastgele_durum = (uint64_t)s.QuadPart ^ ((uint64_t)GetCurrentProcessId() << 32);
#else
    rastgele_durum = (uint64_t)clock();
#endif
}

/* time(): program başladığından beri geçen saniye */
double zaman(void) {
    return simdi_saniye() - baslangic_saniye;
}

/* splitmix64: hızlı ve kaliteli bir rastgele sayı üreteci.
 * (C'nin rand()'ı Windows'ta en fazla 32767 üretir ve kalitesi düşüktür.) */
static uint64_t rastgele_64(void) {
    uint64_t z = (rastgele_durum += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

/* random(a, b): a ile b arasında (ikisi de dahil) rastgele tam sayı.
 * "Modulo yanlılığı" olmasın diye adil olmayan aralıktaki sayılar atılır. */
int64_t rastgele(int64_t a, int64_t b, int64_t satir) {
    if (a > b) {
        fflush(stdout);
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): random(%lld to %lld): alt sınır üst sınırdan büyük olamaz.\n", "\nRUNTIME ERROR (line %lld): random(%lld to %lld): the lower limit cannot be bigger than the upper limit.\n"),
                (long long)satir, (long long)a, (long long)b);
        exit(1);
    }
    uint64_t aralik = (uint64_t)b - (uint64_t)a + 1;   /* 0 ise: bütün 64 bit */
    if (aralik == 0) return (int64_t)rastgele_64();
    uint64_t sinir = UINT64_MAX - (UINT64_MAX % aralik);
    uint64_t r;
    do { r = rastgele_64(); } while (r >= sinir);
    return (int64_t)((uint64_t)a + r % aralik);
}

/* Ekrana istemi yaz, klavyeden bir satır oku (sonundaki Enter hariç).
 * Girdi tamamen bittiyse (ör: dosyadan okunuyor ve dosya bitti) *bitti = 1 olur. */
static char *satir_oku(const char *istem, int *bitti) {
    *bitti = 0;
    if (istem) yaz_text(istem);
    fflush(stdout);
    size_t boy = 0, kap = 64;
    char *t = malloc(kap);
    if (!t) hafiza_doldu();
#ifdef _WIN32
    HANDLE giris = GetStdHandle(STD_INPUT_HANDLE);
    DWORD mod;
    if (GetConsoleMode(giris, &mod)) {
        /* Gerçek bir konsol: Türkçe harfler doğru gelsin diye "geniş karakter" olarak oku */
        wchar_t w[1024];
        DWORD okunan = 0;
        size_t wboy = 0;
        wchar_t *tum = NULL;
        for (;;) {
            if (!ReadConsoleW(giris, w, 1024, &okunan, NULL) || okunan == 0) {
                if (wboy == 0) *bitti = 1;
                break;
            }
            tum = realloc(tum, (wboy + okunan + 1) * sizeof(wchar_t));
            if (!tum) hafiza_doldu();
            memcpy(tum + wboy, w, okunan * sizeof(wchar_t));
            wboy += okunan;
            if (w[okunan - 1] == L'\n') break;
        }
        while (wboy && (tum[wboy - 1] == L'\n' || tum[wboy - 1] == L'\r')) wboy--;
        int gerek = wboy ? WideCharToMultiByte(CP_UTF8, 0, tum, (int)wboy, NULL, 0, NULL, NULL) : 0;
        char *s = metin_ayir((size_t)gerek);
        if (gerek) WideCharToMultiByte(CP_UTF8, 0, tum, (int)wboy, s, gerek, NULL, NULL);
        s[gerek] = '\0';
        free(tum);
        free(t);
        return s;
    }
#endif
    /* Dosyadan ya da başka bir programdan gelen girdi: düz oku */
    static int ilk_okuma = 1;
    int c;
    if (ilk_okuma) {
        /* Girdinin en başında görünmez bir UTF-8 işareti (BOM: EF BB BF) olabilir; atla */
        ilk_okuma = 0;
        c = getchar();
        if (c == 0xEF) {
            int c2 = getchar(), c3 = getchar();
            if (!(c2 == 0xBB && c3 == 0xBF)) {     /* BOM değilmiş: okunanları geri koy */
                if (c3 != EOF) ungetc(c3, stdin);
                if (c2 != EOF) ungetc(c2, stdin);
                ungetc(c, stdin);
            }
        } else if (c != EOF) {
            ungetc(c, stdin);
        }
    }
    while ((c = getchar()) != EOF && c != '\n') {
        if (boy + 1 >= kap) { kap *= 2; t = realloc(t, kap); if (!t) hafiza_doldu(); }
        t[boy++] = (char)c;
    }
    if (c == EOF && boy == 0) *bitti = 1;
    while (boy && t[boy - 1] == '\r') boy--;
    char *s = metin_ayir(boy);
    memcpy(s, t, boy);
    s[boy] = '\0';
    free(t);
    return s;
}

/* input("..."): metin oku */
char *oku_satir(const char *istem) {
    int bitti;
    return satir_oku(istem, &bitti);
}

/* ---------- Çevirmeyi "dene": başarılıysa 1 döndürür (hata vermez) ---------- */
static int tam_sayi_mi(const char *m, int64_t *sonuc) {
    const char *p = m;
    while (*p == ' ' || *p == '\t') p++;
    char *son;
    errno = 0;
    long long v = strtoll(p, &son, 10);
    while (*son == ' ' || *son == '\t') son++;
    if (son == p || *son != '\0' || errno == ERANGE) return 0;
    *sonuc = (int64_t)v;
    return 1;
}

static int ondalik_mi(const char *m, double *sonuc) {
    const char *p = m;
    while (*p == ' ' || *p == '\t') p++;
    char *son;
    double v = strtod(p, &son);
    while (*son == ' ' || *son == '\t') son++;
    if (son == p || *son != '\0') return 0;
    *sonuc = v;
    return 1;
}

int32_t metin_int_dene(const char *m, int64_t *sonuc)  { return tam_sayi_mi(m, sonuc); }
int32_t metin_float_dene(const char *m, double *sonuc) { return ondalik_mi(m, sonuc); }

static void girdi_bitti(const char *ne, int64_t satir) {
    fflush(stdout);
    fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): Girdi bitti; %s bekleniyordu.\n", "\nRUNTIME ERROR (line %lld): Input ended; %s was expected.\n"), (long long)satir, ne);
    exit(1);
}

/* var yas: int = input("Yaşın: ")  →  geçerli bir tam sayı gelene kadar tekrar sorar */
int64_t oku_int(const char *istem, int64_t satir) {
    for (;;) {
        int bitti;
        char *s = satir_oku(istem, &bitti);
        int64_t v;
        int tamam = tam_sayi_mi(s, &v);
        birak(s);
        if (tamam) return v;
        if (bitti) girdi_bitti(MESAJ("bir tam sayı", "an integer"), satir);
        fputs(MESAJ("  → Lütfen bir tam sayı gir (örn: 17)\n", "  → Please enter an integer (e.g. 17)\n"), stdout);
    }
}

/* var boy: float = input("Boyun: ")  →  geçerli bir sayı gelene kadar tekrar sorar */
double oku_float(const char *istem, int64_t satir) {
    for (;;) {
        int bitti;
        char *s = satir_oku(istem, &bitti);
        double v;
        int tamam = ondalik_mi(s, &v);
        birak(s);
        if (tamam) return v;
        if (bitti) girdi_bitti(MESAJ("bir sayı", "a number"), satir);
        fputs(MESAJ("  → Lütfen bir sayı gir (örn: 1.75)\n", "  → Please enter a number (e.g. 1.75)\n"), stdout);
    }
}

/* random(0.0 to 1.0) */
double rastgele_float(double a, double b, int64_t satir) {
    if (a > b) {
        fflush(stdout);
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): random(%g to %g): alt sınır üst sınırdan büyük olamaz.\n", "\nRUNTIME ERROR (line %lld): random(%g to %g): the lower limit cannot be bigger than the upper limit.\n"),
                (long long)satir, a, b);
        exit(1);
    }
    double u = (double)(rastgele_64() >> 11) * (1.0 / 9007199254740992.0);   /* [0, 1) */
    return a + (b - a) * u;
}

/* random(liste): rastgele bir eleman (8 baytlık kutu olarak) */
int64_t liste_rastgele(Liste *l, int64_t satir) {
    if (l->uzunluk == 0) {
        fflush(stdout);
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): random(liste): liste boş, seçilecek eleman yok.\n", "\nRUNTIME ERROR (line %lld): random(list): the list is empty, there is nothing to pick.\n"),
                (long long)satir);
        exit(1);
    }
    return veri_al(l, rastgele(0, l->uzunluk - 1, satir));
}

/* =====================================================================
 *  ÇEVİRME: int("42"), float("3.5")
 * ===================================================================== */

static void cevirme_hatasi(const char *m, const char *ne, int64_t satir) {
    fflush(stdout);
    fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): \"%s\" bir %s çevrilemez.\n", "\nRUNTIME ERROR (line %lld): \"%s\" cannot be turned into %s.\n"), (long long)satir, m, ne);
    exit(1);
}

int64_t metin_int_cevir(const char *m, int64_t satir) {
    const char *p = m;
    while (*p == ' ' || *p == '\t') p++;
    char *son;
    errno = 0;
    long long v = strtoll(p, &son, 10);
    while (*son == ' ' || *son == '\t') son++;
    if (son == p || *son != '\0') cevirme_hatasi(m, MESAJ("tam sayıya (int)", "an integer (int)"), satir);
    if (errno == ERANGE) cevirme_hatasi(m, MESAJ("int'e (çok büyük)", "an int (it is too big)"), satir);
    return (int64_t)v;
}

double metin_float_cevir(const char *m, int64_t satir) {
    const char *p = m;
    while (*p == ' ' || *p == '\t') p++;
    char *son;
    double v = strtod(p, &son);
    while (*son == ' ' || *son == '\t') son++;
    if (son == p || *son != '\0') cevirme_hatasi(m, MESAJ("ondalık sayıya (float)", "a decimal number (float)"), satir);
    return v;
}

/* int(3.7) → 3 (sıfıra doğru). Sığmayan ya da sayı olmayan değerler hata verir. */
int64_t float_int_cevir(double x, int64_t satir) {
    if (!(x > -9223372036854775808.0 && x < 9223372036854775808.0)) {
        fflush(stdout);
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): %g bir int'e sığmaz.\n", "\nRUNTIME ERROR (line %lld): %g does not fit in an int.\n"), (long long)satir, x);
        exit(1);
    }
    return (int64_t)x;
}

/* =====================================================================
 *  METİN İŞLERİ: length, contains, split, trim
 * ===================================================================== */

/* Harf sayısı: UTF-8'de Türkçe harfler 2 bayttır (ç = C3 A7).
 * "Devam baytları" (10xxxxxx) sayılmaz → her harf bir kere sayılır. */
int64_t metin_uzunluk(const char *m) {
    int onbellekli = !paralel_aktif && UZUNLUK(m) >= HARF_ONBELLEK_SINIRI;
    if (onbellekli && harf_onbellek.m == m && harf_onbellek.harf_sayisi >= 0) return harf_onbellek.harf_sayisi;
    int64_t n = 0;
    for (int64_t i = 0; i < UZUNLUK(m); i++) {
        if (((unsigned char)m[i] & 0xC0) != 0x80) n++;
    }
    if (onbellekli) {
        if (harf_onbellek.m != m) {
            harf_onbellek.m = m;
            harf_onbellek.sira = 0;
            harf_onbellek.p = m;
        }
        harf_onbellek.harf_sayisi = n;
    }
    return n;
}

int32_t metin_iceriyor(const char *m, const char *aranan) {
    return strstr(m, aranan) != NULL;
}

static char *metin_parca(const char *bas, size_t n) {
    char *s = metin_ayir(n);
    memcpy(s, bas, n);
    s[n] = '\0';
    return s;
}

Liste *metin_bol(const char *m, const char *ayirici, int64_t satir) {
    size_t la = (size_t)UZUNLUK(ayirici);
    if (la == 0) {
        fflush(stdout);
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): split(\"\"): boş bir ayırıcıyla bölünemez.\n", "\nRUNTIME ERROR (line %lld): split(\"\"): cannot split with an empty separator.\n"), (long long)satir);
        exit(1);
    }
    Liste *l = liste_yeni(T_TEXT, 4);
    const char *bas = m, *bul;
    while ((bul = strstr(bas, ayirici)) != NULL) {
        liste_ekle(l, (int64_t)(intptr_t)metin_parca(bas, (size_t)(bul - bas)));
        bas = bul + la;
    }
    liste_ekle(l, (int64_t)(intptr_t)metin_parca(bas, strlen(bas)));
    return l;
}

char *metin_kirp(const char *m) {
    const char *bas = m, *son = m + UZUNLUK(m);
    while (bas < son && (*bas == ' ' || *bas == '\t' || *bas == '\n' || *bas == '\r')) bas++;
    while (son > bas && (son[-1] == ' ' || son[-1] == '\t' || son[-1] == '\n' || son[-1] == '\r')) son--;
    return metin_parca(bas, (size_t)(son - bas));
}

/* ---------- Harf (UTF-8) yardımcıları ----------
 * UTF-8'de bir harf 1-4 bayttır: 'a' = 61, 'ç' = C3 A7, 'İ' = C4 B0.
 * Bir harfin ilk baytı "devam baytı" (10xxxxxx) değildir. */

static int devam_bayti(unsigned char b) { return (b & 0xC0) == 0x80; }

/* p'den itibaren sira harf ilerle (en fazla 'son'a kadar).
 * NOT: 'son' ayrıca verilir; p metnin ortasını gösterebilir ve orada başlık yoktur. */
static const char *harf_bul(const char *p, const char *son, int64_t sira) {
    while (p < son && sira > 0) {
        p++;
        while (p < son && devam_bayti((unsigned char)*p)) p++;
        sira--;
    }
    return p;
}

static void harf_sinir_hatasi(const char *m, int64_t sira, int64_t satir) {
    fflush(stdout);
    if (sira == 0) {
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): Vash'ta harfler 1'den başlar; ilk harf metin[1].\n", "\nRUNTIME ERROR (line %lld): In Vash, letters start at 1; the first letter is text[1].\n"),
                (long long)satir);
    } else {
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): %lld harfli metnin %lld. harfi yok.\n", "\nRUNTIME ERROR (line %lld): The text has %lld letters, so there is no letter number %lld.\n"),
                (long long)satir, (long long)metin_uzunluk(m), (long long)sira);
    }
    exit(1);
}

/* metin[i] → tek harflik yeni bir metin */
/* m'nin sira. harfinin (0'dan) yeri: önbellekteki yerden ileri gider, sadece ASCII ise doğrudan */
static const char *harf_yeri(const char *m, int64_t sira) {
    const char *metin_sonu = m + UZUNLUK(m);
    if (paralel_aktif || UZUNLUK(m) < HARF_ONBELLEK_SINIRI) return harf_bul(m, metin_sonu, sira);
    if (harf_onbellek.m == m && harf_onbellek.harf_sayisi == UZUNLUK(m)) return m + sira;   /* hepsi tek baytlık */
    const char *p;
    if (harf_onbellek.m == m && sira >= harf_onbellek.sira) {
        p = harf_bul(harf_onbellek.p, metin_sonu, sira - harf_onbellek.sira);
    } else if (harf_onbellek.m == m && harf_onbellek.sira - sira < sira) {   /* geriye daha yakın */
        p = harf_onbellek.p;
        for (int64_t k = harf_onbellek.sira - sira; k > 0; k--) {
            p--;
            while (p > m && devam_bayti((unsigned char)*p)) p--;
        }
    } else {
        if (harf_onbellek.m != m) harf_onbellek.harf_sayisi = -1;
        p = harf_bul(m, metin_sonu, sira);
    }
    harf_onbellek.m = m;
    harf_onbellek.sira = sira;
    harf_onbellek.p = p;
    return p;
}

/* Tek baytlık (ASCII) harfler için hazır, hiç silinmeyen metinler: metin[i] çoğu zaman yeni yer ayırmaz */
static struct { Baslik b; char c[16]; } ascii_harfler[128];

static char *ascii_harf(unsigned char h) {
    if (ascii_harfler[h].b.sayac == 0) {             /* ilk kullanım: hazırla (sayaç -1 = sabit) */
        ascii_harfler[h].b.uzunluk = 1;
        ascii_harfler[h].c[0] = (char)h;
        ascii_harfler[h].b.sayac = -1;
    }
    return ascii_harfler[h].c;
}

char *metin_harf(const char *m, int64_t i, int64_t satir) {
    if (i < 1 || i > metin_uzunluk(m)) harf_sinir_hatasi(m, i, satir);
    const char *metin_sonu = m + UZUNLUK(m);
    const char *bas = harf_yeri(m, i - 1);
    if ((unsigned char)bas[0] < 0x80) return ascii_harf((unsigned char)bas[0]);
    const char *son = harf_bul(bas, metin_sonu, 1);
    return metin_parca(bas, (size_t)(son - bas));
}

/* metin[a to b] → a. harften b. harfe (ikisi de dahil). a > b ise boş metin. */
char *metin_parca_al(const char *m, int64_t a, int64_t b, int64_t satir) {
    int64_t n = metin_uzunluk(m);
    if (a > b) return metin_parca("", 0);
    if (a < 1 || a > n) harf_sinir_hatasi(m, a, satir);
    if (b > n) harf_sinir_hatasi(m, b, satir);
    const char *metin_sonu = m + UZUNLUK(m);
    const char *bas = harf_yeri(m, a - 1);
    const char *son = harf_bul(bas, metin_sonu, b - a + 1);
    return metin_parca(bas, (size_t)(son - bas));
}

/* Bir harfi çöz (UTF-8 → sayı); kaç bayt olduğunu *uzunluk'a yaz */
static uint32_t harf_coz(const unsigned char *p, int *uzunluk) {
    if (p[0] < 0x80) { *uzunluk = 1; return p[0]; }
    if ((p[0] & 0xE0) == 0xC0) { *uzunluk = 2; return ((p[0] & 0x1Fu) << 6) | (p[1] & 0x3Fu); }
    if ((p[0] & 0xF0) == 0xE0) { *uzunluk = 3; return ((p[0] & 0x0Fu) << 12) | ((p[1] & 0x3Fu) << 6) | (p[2] & 0x3Fu); }
    *uzunluk = 4;
    return ((p[0] & 0x07u) << 18) | ((p[1] & 0x3Fu) << 12) | ((p[2] & 0x3Fu) << 6) | (p[3] & 0x3Fu);
}

static int harf_yaz(uint32_t h, char *p) {
    if (h < 0x80) { p[0] = (char)h; return 1; }
    if (h < 0x800) { p[0] = (char)(0xC0 | (h >> 6)); p[1] = (char)(0x80 | (h & 0x3F)); return 2; }
    if (h < 0x10000) {
        p[0] = (char)(0xE0 | (h >> 12)); p[1] = (char)(0x80 | ((h >> 6) & 0x3F)); p[2] = (char)(0x80 | (h & 0x3F));
        return 3;
    }
    p[0] = (char)(0xF0 | (h >> 18)); p[1] = (char)(0x80 | ((h >> 12) & 0x3F));
    p[2] = (char)(0x80 | ((h >> 6) & 0x3F)); p[3] = (char)(0x80 | (h & 0x3F));
    return 4;
}

/* Derleyicinin hızlandırmaları: araya yeni metin oluşturmadan tek harfe bakmak.
 *   code(m[i])     → metin_harf_kodu(m, i)
 *   m[i] is x      → metin_harf_esit(m, i, x)        */
int64_t metin_harf_kodu(const char *m, int64_t i, int64_t satir) {
    if (i < 1 || i > metin_uzunluk(m)) harf_sinir_hatasi(m, i, satir);
    int n;
    return (int64_t)harf_coz((const unsigned char *)harf_yeri(m, i - 1), &n);
}

int32_t metin_harf_esit(const char *m, int64_t i, const char *x, int64_t satir) {
    if (i < 1 || i > metin_uzunluk(m)) harf_sinir_hatasi(m, i, satir);
    const char *bas = harf_yeri(m, i - 1);
    const char *son = harf_bul(bas, m + UZUNLUK(m), 1);
    return (son - bas) == UZUNLUK(x) && memcmp(bas, x, (size_t)(son - bas)) == 0;
}

/* Büyük/küçük harf: Latin harfleri (Türkçe dahil).
 * Türkçe kuralda:  i ↔ İ  ve  ı ↔ I     Evrensel kuralda:  i ↔ I  (ı → I, İ → i) */
static uint32_t harf_buyut(uint32_t h, int tr) {
    if (tr && h == 'i') return 0x130;                 /* i → İ */
    if (h == 0x131) return 'I';                       /* ı → I */
    if (h >= 'a' && h <= 'z') return h - 32;
    if (h >= 0xE0 && h <= 0xFE && h != 0xF7) return h - 0x20;   /* à..þ (ç ö ü dahil) */
    if (h == 0x11F || h == 0x15F) return h - 1;       /* ğ → Ğ, ş → Ş */
    return h;
}

static uint32_t harf_kucult(uint32_t h, int tr) {
    if (tr && h == 'I') return 0x131;                 /* I → ı */
    if (h == 0x130) return 'i';                       /* İ → i */
    if (h >= 'A' && h <= 'Z') return h + 32;
    if (h >= 0xC0 && h <= 0xDE && h != 0xD7) return h + 0x20;   /* À..Þ (Ç Ö Ü dahil) */
    if (h == 0x11E || h == 0x15E) return h + 1;       /* Ğ → ğ, Ş → ş */
    return h;
}

static int dil_turkce_mi(const char *dil, int64_t satir) {
    if (!dil || strcmp(dil, "en") == 0 || dil[0] == '\0') return 0;
    if (strcmp(dil, "tr") == 0) return 1;
    fflush(stdout);
    fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): Dil \"%s\" tanınmıyor; şimdilik \"tr\" ya da \"en\" olabilir.\n", "\nRUNTIME ERROR (line %lld): Language \"%s\" is not known; for now it can be \"tr\" or \"en\".\n"),
            (long long)satir, dil);
    exit(1);
}

static char *harfleri_cevir(const char *m, const char *dil, int64_t satir, int buyut) {
    int tr = dil_turkce_mi(dil, satir);
    size_t n = (size_t)UZUNLUK(m);
    char *gecici = malloc(n * 2 + 4);              /* bir harf en fazla 2 kat büyüyebilir (ı → I küçülür) */
    if (!gecici) hafiza_doldu();
    size_t j = 0;
    const unsigned char *p = (const unsigned char *)m, *son = p + n;
    while (p < son) {
        int u;
        uint32_t h = harf_coz(p, &u);
        h = buyut ? harf_buyut(h, tr) : harf_kucult(h, tr);
        j += (size_t)harf_yaz(h, gecici + j);
        p += u;
    }
    char *s = metin_parca(gecici, j);
    free(gecici);
    return s;
}

char *metin_buyuk(const char *m, const char *dil, int64_t satir) { return harfleri_cevir(m, dil, satir, 1); }
char *metin_kucuk(const char *m, const char *dil, int64_t satir) { return harfleri_cevir(m, dil, satir, 0); }

/* is_digit / is_letter / is_space: metnin BÜTÜN harfleri bu türden mi? (boş metin → false)
 * tur: 0 = rakam, 1 = harf (Türkçe ve diğer Latin harfleri, Yunan, Kiril, Çince...), 2 = boşluk */
static int harf_turunde(uint32_t h, int tur) {
    if (tur == 0) return h >= '0' && h <= '9';
    if (tur == 2) return h == ' ' || h == '\t' || h == '\n' || h == '\r';
    if ((h >= 'a' && h <= 'z') || (h >= 'A' && h <= 'Z')) return 1;
    if (h >= 0xC0 && h <= 0x24F) return h != 0xD7 && h != 0xF7;        /* Latin (ç ğ ı ö ş ü İ ...) */
    if (h >= 0x370 && h <= 0x52F) return h != 0x37E && h != 0x387;     /* Yunan, Kiril */
    if (h >= 0x5D0 && h <= 0x5EA) return 1;                             /* İbrani */
    if (h >= 0x620 && h <= 0x64A) return 1;                             /* Arap */
    if (h >= 0x3040 && h <= 0x30FF) return 1;                           /* Japon kana */
    if (h >= 0x4E00 && h <= 0x9FFF) return 1;                           /* Çince/Japonca/Korece */
    if (h >= 0xAC00 && h <= 0xD7A3) return 1;                           /* Korece */
    return 0;
}

int32_t metin_harf_turu(const char *m, int32_t tur) {
    const unsigned char *p = (const unsigned char *)m, *son = p + UZUNLUK(m);
    if (p == son) return 0;
    while (p < son) {
        int n;
        uint32_t h = harf_coz(p, &n);
        if (!harf_turunde(h, tur)) return 0;
        p += n;
    }
    return 1;
}

/* code("A") → 65: ilk harfin numarası */
int64_t metin_kodu(const char *m, int64_t satir) {
    if (UZUNLUK(m) == 0) {
        fflush(stdout);
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): code(\"\"): boş metnin harf numarası yok.\n", "\nRUNTIME ERROR (line %lld): code(\"\"): an empty text has no letter number.\n"), (long long)satir);
        exit(1);
    }
    int n;
    return (int64_t)harf_coz((const unsigned char *)m, &n);
}

/* char(65) → "A" */
char *harf_metni(int64_t h, int64_t satir) {
    if (h < 0 || h > 0x10FFFF || (h >= 0xD800 && h <= 0xDFFF)) {
        fflush(stdout);
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): char(%lld): böyle bir harf numarası yok "
                        "(0 ile 1114111 arasında olmalı).\n",
                              "\nRUNTIME ERROR (line %lld): char(%lld): there is no such letter number "
                              "(it must be between 0 and 1114111).\n"), (long long)satir, (long long)h);
        exit(1);
    }
    char t[4];
    int n = harf_yaz((uint32_t)h, t);
    return metin_parca(t, (size_t)n);
}

int32_t metin_basliyor(const char *m, const char *a) {
    return UZUNLUK(a) <= UZUNLUK(m) && memcmp(m, a, (size_t)UZUNLUK(a)) == 0;
}

int32_t metin_bitiyor(const char *m, const char *a) {
    return UZUNLUK(a) <= UZUNLUK(m) && memcmp(m + UZUNLUK(m) - UZUNLUK(a), a, (size_t)UZUNLUK(a)) == 0;
}

char *metin_degistir(const char *m, const char *eski, const char *yeni, int64_t satir) {
    size_t le = (size_t)UZUNLUK(eski), ly = (size_t)UZUNLUK(yeni);
    if (le == 0) {
        fflush(stdout);
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): replace(\"\", ...): boş bir parça değiştirilemez.\n", "\nRUNTIME ERROR (line %lld): replace(\"\", ...): an empty piece cannot be replaced.\n"),
                (long long)satir);
        exit(1);
    }
    size_t adet = 0;
    for (const char *p = m; (p = strstr(p, eski)) != NULL; p += le) adet++;
    size_t n = (size_t)UZUNLUK(m) - adet * le + adet * ly;
    char *s = metin_ayir(n);
    char *y = s;
    const char *p = m, *bul;
    while ((bul = strstr(p, eski)) != NULL) {
        memcpy(y, p, (size_t)(bul - p)); y += bul - p;
        memcpy(y, yeni, ly); y += ly;
        p = bul + le;
    }
    strcpy(y, p);
    return s;
}

/* split() ayraçsız: boşluklara göre kelimelere böl, boş parçaları atla */
Liste *metin_bol_bosluk(const char *m) {
    Liste *l = liste_yeni(T_TEXT, 4);
    const char *p = m;
    for (;;) {
        while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') p++;
        if (!*p) break;
        const char *bas = p;
        while (*p && *p != ' ' && *p != '\t' && *p != '\n' && *p != '\r') p++;
        liste_ekle(l, (int64_t)(intptr_t)metin_parca(bas, (size_t)(p - bas)));
    }
    return l;
}

/* extern: C fonksiyonunun döndürdüğü metni Vash metnine kopyala (C'ninki C'de kalır) */
char *metin_c_den(const char *c) {
    if (!c) c = "";
    return metin_parca(c, strlen(c));
}

/* liste.join(", "): elemanları metne çevirip aralarına ayırıcı koyarak birleştir */
char *liste_birlestir(Liste *l, const char *ayirici) {
    size_t la = (size_t)UZUNLUK(ayirici), kap = 64, n = 0;
    char *t = malloc(kap);
    if (!t) hafiza_doldu();
    for (int64_t i = 0; i < l->uzunluk; i++) {
        char tampon[64];
        const char *parca;
        size_t lp;
        int64_t v = veri_al(l, i);
        switch (l->tur) {
            case T_INT:   lp = (size_t)int_yaziya(v, tampon); parca = tampon; break;
            case T_FLOAT: { double d; memcpy(&d, &v, sizeof d); float_metne(d, tampon, sizeof tampon);
                            parca = tampon; lp = strlen(tampon); break; }
            case T_BOOL:  parca = v ? "true" : "false"; lp = strlen(parca); break;
            default:      parca = (const char *)(intptr_t)v; lp = (size_t)UZUNLUK(parca); break;
        }
        size_t gerek = n + lp + (i > 0 ? la : 0) + 1;
        if (gerek > kap) { while (kap < gerek) kap *= 2; t = realloc(t, kap); if (!t) hafiza_doldu(); }
        if (i > 0) { memcpy(t + n, ayirici, la); n += la; }
        memcpy(t + n, parca, lp); n += lp;
    }
    char *s = metin_parca(t, n);
    free(t);
    return s;
}

/* =====================================================================
 *  PENCERE (window): görsel arayüz
 * =====================================================================
 *
 *  Nasıl çalışır?
 *    1) Program bilgisayarın İÇİNDE küçük bir sunucu açar (127.0.0.1, dışarıdan erişilemez).
 *    2) Edge'i "uygulama modunda" (adres çubuğu olmadan) bu adrese açar:
 *       kullanıcı normal bir masaüstü penceresi görür.
 *    3) Pencerede bir düğmeye basılınca / kutuya yazılınca pencere bize bir "olay" gönderir.
 *       Vash kodu olayı işler, ekrandaki yazılar yeniden hesaplanır ve sadece
 *       DEĞİŞENLER pencereye geri gönderilir.
 *
 *  Program tek iş parçacıklıdır: bir olay işlenirken pencere cevabı bekler.
 *  Pencerenin görünümü (HTML/CSS/JS) derleyicideki pencere.html dosyasından gelir.
 *
 *  Test için:  VASH_PENCERE=yok  → Edge açılmaz, adres ekrana yazılır.
 *              VASH_PORT=8790    → sabit port kullan.
 * ===================================================================== */
#ifdef _WIN32

#define UI_EN_FAZLA 1024

static SOCKET ui_dinleyici = INVALID_SOCKET;
static SOCKET ui_bekleyen = INVALID_SOCKET;      /* cevabı, olay işlendikten sonra gönderilecek bağlantı */
static const char *ui_sayfa = NULL;
static size_t ui_sayfa_uzunluk = 0;
static char *ui_metinler[UI_EN_FAZLA], *ui_degerler[UI_EN_FAZLA];
static unsigned char ui_m_yeni[UI_EN_FAZLA], ui_d_yeni[UI_EN_FAZLA];
static char *ui_olay_deger = NULL;
static int64_t ui_olay_satir = 0;                /* olay bir list satırından geldiyse: kaçıncı satır */
static ULONGLONG ui_son_nabiz = 0, ui_baslangic = 0;

/* list: her listenin kaç satırı var, ve şablondaki her parçanın HER SATIRDAKİ yazısı */
static int64_t ui_boylar[UI_EN_FAZLA];
static unsigned char ui_b_var[UI_EN_FAZLA], ui_b_yeni[UI_EN_FAZLA];
typedef struct { char **v; unsigned char *yeni; int64_t kap; } Satirlar;
static Satirlar ui_satirlar[UI_EN_FAZLA];
static int ui_baglandi = 0;

/* --- büyüyen yazı tamponu --- */
typedef struct { char *p; size_t n, kap; } Tampon;

static void t_ekle(Tampon *t, const char *s, size_t n) {
    if (t->n + n + 1 > t->kap) {
        while (t->n + n + 1 > t->kap) t->kap = t->kap ? t->kap * 2 : 256;
        t->p = realloc(t->p, t->kap);
        if (!t->p) hafiza_doldu();
    }
    memcpy(t->p + t->n, s, n);
    t->n += n;
    t->p[t->n] = 0;
}

static void t_yaz(Tampon *t, const char *s) { t_ekle(t, s, strlen(s)); }

static void t_json_metin(Tampon *t, const char *s) {
    t_yaz(t, "\"");
    for (; *s; s++) {
        unsigned char c = (unsigned char)*s;
        if (c == '"') t_yaz(t, "\\\"");
        else if (c == '\\') t_yaz(t, "\\\\");
        else if (c == '\n') t_yaz(t, "\\n");
        else if (c < 0x20) { char k[8]; snprintf(k, sizeof k, "\\u%04x", c); t_yaz(t, k); }
        else t_ekle(t, (const char *)&c, 1);
    }
    t_yaz(t, "\"");
}

static void ui_hata(const char *mesaj) {
    fflush(stdout);
    fprintf(stderr, MESAJ("\nÇALIŞMA HATASI: Pencere açılamadı: %s\n", "\nRUNTIME ERROR: Could not open the window: %s\n"), mesaj);
    exit(1);
}

static void ui_gonder(SOCKET s, const char *tur, const char *govde, size_t n) {
    char baslik[256];
    int hn = snprintf(baslik, sizeof baslik,
                      "HTTP/1.1 200 OK\r\nContent-Type: %s\r\nContent-Length: %zu\r\n"
                      "Cache-Control: no-store\r\nConnection: close\r\n\r\n", tur, n);
    send(s, baslik, hn, 0);
    size_t gonderilen = 0;
    while (gonderilen < n) {
        int r = send(s, govde + gonderilen, (int)(n - gonderilen), 0);
        if (r <= 0) break;
        gonderilen += (size_t)r;
    }
    closesocket(s);
}

/* Değişen (ya da hepsi=1 ise bütün) yazıları/değerleri JSON olarak gönder:
     [[no, "n", "3"], ...]                 → listenin satır sayısı (önce bunlar: satırlar oluşsun)
     [[no, "m", "yazı"], [no, "d", "değer"], ...]
     [[no, "m", "yazı", satır], ...]       → bir list satırındaki parçanın yazısı */
static void ui_durum_gonder(SOCKET s, int hepsi) {
    Tampon t = {0};
    t_yaz(&t, "[");
    int ilk = 1;
    for (int i = 0; i < UI_EN_FAZLA; i++) {
        if (ui_b_var[i] && (hepsi || ui_b_yeni[i])) {
            char on[64];
            snprintf(on, sizeof on, "%s[%d,\"n\",\"%lld\"]", ilk ? "" : ",", i, (long long)ui_boylar[i]);
            t_yaz(&t, on);
            ilk = 0;
        }
        ui_b_yeni[i] = 0;
    }
    for (int i = 0; i < UI_EN_FAZLA; i++) {
        Satirlar *st = &ui_satirlar[i];
        for (int64_t r = 1; r < st->kap; r++) {
            if (st->v[r] && (hepsi || st->yeni[r])) {
                char on[64];
                snprintf(on, sizeof on, "%s[%d,\"m\",", ilk ? "" : ",", i);
                t_yaz(&t, on);
                t_json_metin(&t, st->v[r]);
                snprintf(on, sizeof on, ",%lld]", (long long)r);
                t_yaz(&t, on);
                ilk = 0;
            }
            if (r < st->kap) st->yeni[r] = 0;
        }
    }
    for (int i = 0; i < UI_EN_FAZLA; i++) {
        for (int tur = 0; tur < 2; tur++) {
            char *v = tur ? ui_degerler[i] : ui_metinler[i];
            unsigned char *yeni = tur ? &ui_d_yeni[i] : &ui_m_yeni[i];
            if (v && (hepsi || *yeni)) {
                char on[32];
                snprintf(on, sizeof on, "%s[%d,\"%c\",", ilk ? "" : ",", i, tur ? 'd' : 'm');
                t_yaz(&t, on);
                t_json_metin(&t, v);
                t_yaz(&t, "]");
                ilk = 0;
            }
            *yeni = 0;
        }
    }
    t_yaz(&t, "]");
    ui_gonder(s, "application/json; charset=utf-8", t.p, t.n);
    free(t.p);
}

static void ui_sakla(char **yer, unsigned char *yeni, const char *m) {
    if (*yer && strcmp(*yer, m) == 0) return;     /* aynıysa göndermeye gerek yok */
    free(*yer);
    *yer = strdup(m);
    *yeni = 1;
}

/* Vash kodu her olaydan sonra ekrandaki her yazıyı/değeri buraya verir; biz farkı buluruz. */
void ui_metin(int64_t no, const char *m) {
    if (no >= 0 && no < UI_EN_FAZLA) ui_sakla(&ui_metinler[no], &ui_m_yeni[no], m);
}

void ui_deger(int64_t no, const char *m) {
    if (no >= 0 && no < UI_EN_FAZLA) ui_sakla(&ui_degerler[no], &ui_d_yeni[no], m);
}

/* list: satır sayısı */
void ui_liste_boy(int64_t no, int64_t n) {
    if (no < 0 || no >= UI_EN_FAZLA) return;
    if (!ui_b_var[no] || ui_boylar[no] != n) {
        ui_boylar[no] = n;
        ui_b_var[no] = 1;
        ui_b_yeni[no] = 1;
    }
}

/* list şablonundaki bir parçanın r. satırdaki yazısı */
void ui_metin_satir(int64_t no, int64_t r, const char *m) {
    if (no < 0 || no >= UI_EN_FAZLA || r < 1) return;
    Satirlar *st = &ui_satirlar[no];
    if (r >= st->kap) {
        int64_t yeni_kap = st->kap ? st->kap : 8;
        while (yeni_kap <= r) yeni_kap *= 2;
        st->v = realloc(st->v, sizeof(char *) * (size_t)yeni_kap);
        st->yeni = realloc(st->yeni, (size_t)yeni_kap);
        if (!st->v || !st->yeni) hafiza_doldu();
        for (int64_t k = st->kap; k < yeni_kap; k++) { st->v[k] = NULL; st->yeni[k] = 0; }
        st->kap = yeni_kap;
    }
    ui_sakla(&st->v[r], &st->yeni[r], m);
}

/* Liste kısaldı: artık olmayan satırların yazılarını unut (geri gelirlerse yeniden gönderilsinler) */
void ui_satir_kirp(int64_t no, int64_t n) {
    if (no < 0 || no >= UI_EN_FAZLA) return;
    Satirlar *st = &ui_satirlar[no];
    for (int64_t r = n + 1; r < st->kap; r++) {
        free(st->v[r]);
        st->v[r] = NULL;
        st->yeni[r] = 0;
    }
}

int64_t ui_olay_satiri(void) { return ui_olay_satir; }

void ui_baslat(const char *sayfa) {
    WSADATA w;
    if (WSAStartup(MAKEWORD(2, 2), &w) != 0) ui_hata(MESAJ("ağ başlatılamadı", "could not start the network"));
    ui_sayfa = sayfa;
    ui_sayfa_uzunluk = (size_t)UZUNLUK(sayfa);

    ui_dinleyici = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (ui_dinleyici == INVALID_SOCKET) ui_hata(MESAJ("soket açılamadı", "could not open a socket"));
    struct sockaddr_in a = {0};
    a.sin_family = AF_INET;
    a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);                 /* sadece bu bilgisayar */
    const char *port = getenv("VASH_PORT");
    a.sin_port = htons(port ? (u_short)atoi(port) : 0);          /* 0: boş bir port seç */
    if (bind(ui_dinleyici, (struct sockaddr *)&a, sizeof a) != 0) ui_hata(MESAJ("port kullanılamadı", "the port could not be used"));
    listen(ui_dinleyici, 16);
    int boy = sizeof a;
    getsockname(ui_dinleyici, (struct sockaddr *)&a, &boy);

    char adres[64];
    snprintf(adres, sizeof adres, "http://127.0.0.1:%d/", ntohs(a.sin_port));
    const char *pencere = getenv("VASH_PENCERE");
    if (pencere && strcmp(pencere, "yok") == 0) {
        fprintf(stderr, MESAJ("[pencere] %s\n", "[window] %s\n"), adres);
    } else {
        char arg[160];
        snprintf(arg, sizeof arg, "--app=%s --window-size=520,680", adres);
        /* Edge uygulama modu: adres çubuğu olmayan, normal görünümlü bir pencere */
        if ((INT_PTR)ShellExecuteA(NULL, "open", "msedge.exe", arg, NULL, SW_SHOWNORMAL) <= 32) {
            ShellExecuteA(NULL, "open", adres, NULL, NULL, SW_SHOWNORMAL);   /* olmazsa varsayılan tarayıcı */
        }
    }
    fflush(stdout);
    fflush(stderr);
    ui_baslangic = GetTickCount64();
}

/* Bir isteği oku: "GET / ..." ya da "POST /olay ...\r\n\r\n<gövde>" */
static int ui_istek_oku(SOCKET s, char **istek, char **govde) {
    Tampon t = {0};
    size_t gerek = 0;
    for (;;) {
        fd_set f;
        FD_ZERO(&f);
        FD_SET(s, &f);
        struct timeval z = {3, 0};
        if (select(0, &f, NULL, NULL, &z) <= 0) break;            /* boş bağlantı: bırak */
        char k[4096];
        int r = recv(s, k, sizeof k, 0);
        if (r <= 0) break;
        t_ekle(&t, k, (size_t)r);
        char *son = strstr(t.p, "\r\n\r\n");
        if (son && !gerek) {
            size_t uz = 0;
            char *cl = strstr(t.p, "Content-Length:");
            if (!cl) cl = strstr(t.p, "content-length:");
            if (cl && cl < son) uz = (size_t)strtoull(cl + 15, NULL, 10);
            gerek = (size_t)(son + 4 - t.p) + uz;
        }
        if (gerek && t.n >= gerek) {
            *istek = t.p;
            *govde = strstr(t.p, "\r\n\r\n") + 4;
            return 1;
        }
    }
    free(t.p);
    return 0;
}

/* Bir sonraki olayı bekle. Dönüş: olayın geldiği parçanın numarası, pencere kapandıysa -1. */
int64_t ui_bekle(void) {
    if (ui_bekleyen != INVALID_SOCKET) {            /* önceki olayın cevabı: değişen yazılar */
        ui_durum_gonder(ui_bekleyen, 0);
        ui_bekleyen = INVALID_SOCKET;
    }
    static ULONGLONG kapanis = 0;    /* "kapandım" sinyalinin geldiği an (0: gelmedi) */
    for (;;) {
        fd_set f;
        FD_ZERO(&f);
        FD_SET(ui_dinleyici, &f);
        struct timeval z = {0, 250000};
        int r = select(0, &f, NULL, NULL, &z);
        ULONGLONG simdi = GetTickCount64();
        /* Sayfa "kapandım" dedi ve 1.5 saniyede yeniden bağlanmadı → pencere gerçekten kapandı.
           (Yeniden yükleme de "kapandım" der ama hemen tekrar bağlanır; o zaman program sürer.) */
        if (kapanis && simdi - kapanis > 1500) { kapanis = 0; return -1; }
        if (r <= 0) {
            if (ui_baglandi && simdi - ui_son_nabiz > 8000) return -1;      /* pencereden ses gelmiyor */
            if (!ui_baglandi && simdi - ui_baslangic > 60000) ui_hata(MESAJ("pencere 60 saniyede bağlanmadı", "the window did not connect within 60 seconds"));
            continue;
        }
        SOCKET s = accept(ui_dinleyici, NULL, NULL);
        if (s == INVALID_SOCKET) continue;
        char *istek, *govde;
        if (!ui_istek_oku(s, &istek, &govde)) { closesocket(s); continue; }

        if (strncmp(istek, "GET / ", 6) == 0) {
            kapanis = 0;                                   /* sayfa yeniden açılıyor */
            ui_gonder(s, "text/html; charset=utf-8", ui_sayfa, ui_sayfa_uzunluk);
        } else if (strncmp(istek, "POST /nabiz ", 12) == 0) {
            ui_son_nabiz = simdi;
            ui_gonder(s, "application/json", "[]", 2);
        } else if (strncmp(istek, "POST /kapat ", 12) == 0) {
            kapanis = simdi;
            ui_gonder(s, "application/json", "[]", 2);
        } else if (strncmp(istek, "POST /olay ", 11) == 0) {
            kapanis = 0;
            ui_baglandi = 1;
            ui_son_nabiz = simdi;
            char *son;
            long no = strtol(govde, &son, 10);             /* "no satır\ndeğer" */
            ui_olay_satir = strtoll(son, NULL, 10);         /* list satırı değilse 0 */
            char *deger = strchr(govde, '\n');
            deger = deger ? deger + 1 : "";
            if (no < 0 || no >= UI_EN_FAZLA) {      /* -1: sayfa yeni açıldı, her şeyi gönder */
                ui_durum_gonder(s, 1);
            } else {
                free(ui_olay_deger);
                ui_olay_deger = strdup(deger);
                if (ui_degerler[no]) {               /* kullanıcının yazdığını ona geri yollama */
                    free(ui_degerler[no]);
                    ui_degerler[no] = strdup(deger);
                    ui_d_yeni[no] = 0;
                }
                ui_bekleyen = s;
                free(istek);
                return no;
            }
        } else {
            static const char yok[] = "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
            send(s, yok, (int)sizeof yok - 1, 0);
            closesocket(s);
        }
        free(istek);
    }
}

/* Son olayla gelen değer (kutuya yazılan yazı; onay kutusu için "true"/"false") */
char *ui_olay_degeri(void) {
    const char *d = ui_olay_deger ? ui_olay_deger : "";
    return metin_parca(d, strlen(d));
}

void ui_bitir(void) {
    if (ui_bekleyen != INVALID_SOCKET) { ui_durum_gonder(ui_bekleyen, 0); ui_bekleyen = INVALID_SOCKET; }
    if (ui_dinleyici != INVALID_SOCKET) { closesocket(ui_dinleyici); ui_dinleyici = INVALID_SOCKET; }
    for (int i = 0; i < UI_EN_FAZLA; i++) {
        free(ui_metinler[i]);
        free(ui_degerler[i]);
        ui_metinler[i] = ui_degerler[i] = NULL;
        Satirlar *st = &ui_satirlar[i];
        for (int64_t r = 0; r < st->kap; r++) free(st->v[r]);
        free(st->v);
        free(st->yeni);
        st->v = NULL; st->yeni = NULL; st->kap = 0;
        ui_b_var[i] = 0;
    }
    free(ui_olay_deger);
    ui_olay_deger = NULL;
    WSACleanup();
}
#endif


/* =====================================================================
 *  DOSYALAR: read_file, read_lines, write_file, append_file, file_exists
 * =====================================================================
 *  Windows'ta Türkçe harfli dosya adları (öğrenci.txt) için adı Windows'un
 *  kendi harf düzenine (UTF-16) çevirip _wfopen ile açıyoruz.
 *  Okurken: baştaki BOM işareti atılır, satır sonları "\r\n" → "\n" yapılır. */

#ifdef _WIN32
/* =====================================================================
 *  KUM HAVUZU: VASH_KUM_KLASOR ortam değişkeni varsa, program dosyalara
 *  sadece o klasörün (ve alt klasörlerinin) içinde dokunabilir.
 *  Yol önce Windows'un tam yoluna çevrilir (.. ve göreli yollar çözülür),
 *  sonra klasörle başlıyor mu diye bakılır. Dışarıdaysa program durur.
 * ===================================================================== */
#define KUM_UZUNLUK 4096
static int kum_durumu = -1;                     /* -1 bakılmadı, 0 yok, 1 var, 2 bozuk (her şey yasak) */
static wchar_t kum_kok[KUM_UZUNLUK];

static void kum_yolu_denetle(const char *yol, const wchar_t *w) {
    if (kum_durumu < 0) {
        static wchar_t ham[KUM_UZUNLUK];
        DWORD n = GetEnvironmentVariableW(L"VASH_KUM_KLASOR", ham, KUM_UZUNLUK);
        if (n == 0) kum_durumu = 0;
        else if (n >= KUM_UZUNLUK) kum_durumu = 2;
        else {
            DWORD m = GetFullPathNameW(ham, KUM_UZUNLUK, kum_kok, NULL);
            if (m == 0 || m >= KUM_UZUNLUK) kum_durumu = 2;
            else {
                size_t L = wcslen(kum_kok);
                while (L > 3 && (kum_kok[L - 1] == L'\\' || kum_kok[L - 1] == L'/')) kum_kok[--L] = 0;
                kum_durumu = 1;
            }
        }
    }
    if (kum_durumu == 0) return;
    int izinli = 0;
    if (kum_durumu == 1) {
        static wchar_t tam[KUM_UZUNLUK];
        DWORD m = GetFullPathNameW(w, KUM_UZUNLUK, tam, NULL);
        size_t L = wcslen(kum_kok);
        if (m > 0 && m < KUM_UZUNLUK && _wcsnicmp(tam, kum_kok, L) == 0 && (tam[L] == L'\\' || tam[L] == 0)) izinli = 1;
        if (izinli && wcschr(tam + 2, L':')) izinli = 0;         /* "dosya:gizli" gibi ek akışlar */
        if (izinli && wcsncmp(tam, L"\\\\", 2) == 0) izinli = 0;  /* \\?\ ve ağ yolları */
    }
    if (!izinli) {
        fflush(stdout);
        fprintf(stderr, MESAJ("\nKUM HAVUZU: '%s' izin verilen klasörün dışında; program durduruldu.\n", "\nSANDBOX: '%s' is outside the allowed folder; the program was stopped.\n"), yol);
        exit(3);
    }
}

static wchar_t *kum_genis(const char *m) {
    int n = MultiByteToWideChar(CP_UTF8, 0, m, -1, NULL, 0);
    if (n <= 0) return NULL;
    wchar_t *w = malloc(sizeof(wchar_t) * (size_t)n);
    if (!w) hafiza_doldu();
    MultiByteToWideChar(CP_UTF8, 0, m, -1, w, n);
    return w;
}

/* Komutu çalıştır: dosyalar 'klasor' ile sınırlı, 'ms' dolunca program (ve açtığı her şey) durdurulur.
   Dönüş: çıkış kodu; süre dolduysa -2; başlatılamadıysa -1. */
int64_t vash_kum_calistir(const char *komut, const char *klasor, int64_t ms) {
    wchar_t *wk = kum_genis(komut);
    wchar_t *wd = (klasor && klasor[0]) ? kum_genis(klasor) : NULL;
    if (!wk) return -1;
    HANDLE is = CreateJobObjectW(NULL, NULL);
    if (is) {
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION li;
        memset(&li, 0, sizeof li);
        li.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_ACTIVE_PROCESS | JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION;
        li.BasicLimitInformation.ActiveProcessLimit = 1;          /* başka program açamaz */
        li.ProcessMemoryLimit = (SIZE_T)2048 * 1024 * 1024;       /* en çok 2 GB bellek */
        SetInformationJobObject(is, JobObjectExtendedLimitInformation, &li, sizeof li);
    }
    SetEnvironmentVariableW(L"VASH_KUM_KLASOR", wd ? wd : L".");
    STARTUPINFOW si;
    memset(&si, 0, sizeof si);
    si.cb = sizeof si;
    PROCESS_INFORMATION pi;
    memset(&pi, 0, sizeof pi);
    BOOL oldu = CreateProcessW(NULL, wk, NULL, NULL, TRUE, CREATE_SUSPENDED, NULL, wd, &si, &pi);
    SetEnvironmentVariableW(L"VASH_KUM_KLASOR", NULL);
    free(wk);
    if (wd) free(wd);
    if (!oldu) {
        if (is) CloseHandle(is);
        return -1;
    }
    if (is && !AssignProcessToJobObject(is, pi.hProcess)) {
        TerminateProcess(pi.hProcess, 1);
        CloseHandle(pi.hThread);
        CloseHandle(pi.hProcess);
        CloseHandle(is);
        return -1;
    }
    ResumeThread(pi.hThread);
    DWORD r = WaitForSingleObject(pi.hProcess, ms > 0 ? (DWORD)ms : INFINITE);
    int64_t kod;
    if (r == WAIT_TIMEOUT) {
        if (is) TerminateJobObject(is, 124); else TerminateProcess(pi.hProcess, 124);
        WaitForSingleObject(pi.hProcess, 5000);
        kod = -2;
    } else {
        DWORD c = 1;
        GetExitCodeProcess(pi.hProcess, &c);
        kod = (int64_t)c;
    }
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    if (is) CloseHandle(is);
    return kod;
}
#endif

static FILE *dosya_ac(const char *yol, const wchar_t *kip) {
#ifdef _WIN32
    int n = MultiByteToWideChar(CP_UTF8, 0, yol, -1, NULL, 0);
    if (n <= 0) return NULL;
    wchar_t *w = malloc(sizeof(wchar_t) * (size_t)n);
    if (!w) hafiza_doldu();
    MultiByteToWideChar(CP_UTF8, 0, yol, -1, w, n);
    kum_yolu_denetle(yol, w);
    FILE *f = _wfopen(w, kip);
    free(w);
    return f;
#else
    char k[8];
    wcstombs(k, kip, sizeof k);
    return fopen(yol, k);
#endif
}

/* Bütün dosyayı oku; okunamazsa NULL (Vash'ta none) */
char *dosya_oku(const char *yol) {
    FILE *f = dosya_ac(yol, L"rb");
    if (!f) return NULL;
    size_t kap = 4096, n = 0;
    char *p = malloc(kap);
    if (!p) hafiza_doldu();
    for (;;) {
        if (n == kap) {
            kap *= 2;
            p = realloc(p, kap);
            if (!p) hafiza_doldu();
        }
        size_t r = fread(p + n, 1, kap - n, f);
        if (r == 0) break;
        n += r;
    }
    int hata_var = ferror(f);
    fclose(f);
    if (hata_var) { free(p); return NULL; }
    size_t bas = (n >= 3 && (unsigned char)p[0] == 0xEF && (unsigned char)p[1] == 0xBB && (unsigned char)p[2] == 0xBF) ? 3 : 0;
    size_t y = 0;                                    /* \r\n → \n */
    for (size_t i = bas; i < n; i++) {
        if (p[i] == '\r' && i + 1 < n && p[i + 1] == '\n') continue;
        p[y++] = p[i];
    }
    char *m = metin_parca(p, y);
    free(p);
    return m;
}

/* Dosyayı satır satır oku → [text]; okunamazsa NULL */
Liste *dosya_satirlar(const char *yol) {
    char *m = dosya_oku(yol);
    if (!m) return NULL;
    Liste *l = liste_yeni(T_TEXT, 8);
    const char *bas = m, *son = m + UZUNLUK(m);
    while (bas < son) {
        const char *s = memchr(bas, '\n', (size_t)(son - bas));
        const char *bitis = s ? s : son;
        liste_ekle(l, (int64_t)(intptr_t)metin_parca(bas, (size_t)(bitis - bas)));
        if (!s) break;
        bas = s + 1;
    }
    birak(m);
    return l;
}

/* Dosyaya yaz (ekle=1 ise sonuna ekle); oldu mu? */
int32_t dosya_yaz(const char *yol, const char *m, int32_t ekle) {
    FILE *f = dosya_ac(yol, ekle ? L"ab" : L"wb");
    if (!f) return 0;
    size_t n = (size_t)UZUNLUK(m);
    int tamam = fwrite(m, 1, n, f) == n;
    if (fclose(f) != 0) tamam = 0;
    return tamam;
}

int32_t dosya_var_mi(const char *yol) {
#ifdef _WIN32
    int n = MultiByteToWideChar(CP_UTF8, 0, yol, -1, NULL, 0);
    if (n <= 0) return 0;
    wchar_t *w = malloc(sizeof(wchar_t) * (size_t)n);
    if (!w) hafiza_doldu();
    MultiByteToWideChar(CP_UTF8, 0, yol, -1, w, n);
    kum_yolu_denetle(yol, w);
    DWORD a = GetFileAttributesW(w);
    free(w);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
#else
    FILE *f = fopen(yol, "rb");
    if (f) fclose(f);
    return f != NULL;
#endif
}

/* =====================================================================
 *  PARALLEL: işleri çekirdeklere dağıtmak
 * =====================================================================
 *  Derleyici her paralel işi ayrı bir fonksiyona çevirir: is(ortam, bas, son).
 *  "ortam", işin kullandığı dışarıdaki değişkenlerin adreslerini tutan küçük bir dizidir.
 *    parallel repeat i from a to b { }  →  paralel_repeat: a..b aralığı çekirdek sayısı kadar parçaya bölünür
 *    parallel { is1  is2  is3 }         →  paralel_isler: her iş ayrı bir çekirdekte
 *  Ana çekirdek de boş durmaz, ilk parçayı kendisi çalıştırır; sonra hepsinin bitmesini bekler.
 *  (Derleyici, aynı anda çalışan işlerin aynı değişkene dokunmadığını program çalışmadan kontrol eder.) */
typedef void (*VashIs)(void *ortam, int64_t bas, int64_t son);

typedef struct {
    VashIs is;
    void *ortam;
    int64_t bas, son;
    uint64_t tohum;
} IsParcasi;

/* Kalıcı işçi takımı: işçiler bir kere oluşturulur, sonra iş bekler (her parallel'de yeniden oluşturmak yavaş olurdu,
 * ayrıca her işçinin kendi rafları kalıcı olur ve yeniden kullanılır). */
typedef struct {
    HANDLE basla;                 /* "iş var" işareti */
    IsParcasi *is;
} Isci;
static Isci isciler[64];
static int isci_sayisi = 0;
static volatile LONG kalan_is = 0;
static HANDLE bitti_olayi;

static DWORD WINAPI isci_dongusu(LPVOID p) {
    Isci *x = (Isci *)p;
    for (;;) {
        WaitForSingleObject(x->basla, INFINITE);
        IsParcasi *j = x->is;
        rastgele_durum = j->tohum;                  /* her çekirdeğin rastgele sayıları farklı olsun */
        j->is(j->ortam, j->bas, j->son);
        if (InterlockedDecrement(&kalan_is) == 0) SetEvent(bitti_olayi);
    }
    return 0;
}

static int cekirdek_sayisi(void) {
    static int n = 0;
    if (!n) {
        n = (int)GetActiveProcessorCount(ALL_PROCESSOR_GROUPS);
        if (n < 1) n = 1;
        if (n > 64) n = 64;
    }
    return n;
}

static void takimi_kur(void) {
    if (isci_sayisi) return;
    bitti_olayi = CreateEventW(NULL, FALSE, FALSE, NULL);
    for (int i = 0; i < cekirdek_sayisi() - 1; i++) {
        isciler[i].basla = CreateEventW(NULL, FALSE, FALSE, NULL);
        HANDLE h = CreateThread(NULL, 0, isci_dongusu, &isciler[i], 0, NULL);
        if (!h || !isciler[i].basla) {
            fflush(stdout);
            fprintf(stderr, MESAJ("\nÇALIŞMA HATASI: Çekirdek işçileri başlatılamadı.\n", "\nRUNTIME ERROR: Could not start the workers for the processor cores.\n"));
            exit(1);
        }
        CloseHandle(h);
        isci_sayisi++;
    }
}

static void parcalari_calistir(IsParcasi *parcalar, int n) {
    if (ISCI_MODU) {                                /* paralelin içinde paralel (ya da arka plan işi): sırayla yap */
        for (int i = 0; i < n; i++) parcalar[i].is(parcalar[i].ortam, parcalar[i].bas, parcalar[i].son);
        return;
    }
    takimi_kur();
    if (n > isci_sayisi + 1) n = isci_sayisi + 1;   /* (çağıranlar n'i zaten buna göre böler) */
    for (int i = 0; i < n; i++) parcalar[i].tohum = rastgele_64() ^ ((uint64_t)(i + 1) * 0xD1B54A32D192ED03ULL);
    InterlockedIncrement(&paralel_aktif);           /* artık sayaçlar bölünmez işlemlerle değişir */
    InterlockedIncrement(&paralel_bolum);
    kalan_is = n - 1;
    for (int i = 1; i < n; i++) {
        isciler[i - 1].is = &parcalar[i];
        SetEvent(isciler[i - 1].basla);
    }
    parcalar[0].is(parcalar[0].ortam, parcalar[0].bas, parcalar[0].son);   /* ilk parçayı bu çekirdek yapar */
    if (n > 1) WaitForSingleObject(bitti_olayi, INFINITE);
    InterlockedDecrement(&paralel_bolum);
    InterlockedDecrement(&paralel_aktif);
}

/* parallel repeat i from bas to son { ... } */
void paralel_repeat(VashIs is, void *ortam, int64_t bas, int64_t son) {
    if (son < bas) return;
    uint64_t toplam = (uint64_t)son - (uint64_t)bas + 1;
    int n = cekirdek_sayisi();
    if (toplam < (uint64_t)n) n = (int)toplam;
    if (n <= 1) { is(ortam, bas, son); return; }      /* tek tur: paralele gerek yok */
    IsParcasi parcalar[64];
    uint64_t parca = toplam / (uint64_t)n, artan = toplam % (uint64_t)n;
    int64_t b = bas;
    for (int i = 0; i < n; i++) {
        uint64_t boy = parca + ((uint64_t)i < artan ? 1 : 0);
        parcalar[i].is = is;
        parcalar[i].ortam = ortam;
        parcalar[i].bas = b;
        parcalar[i].son = (int64_t)((uint64_t)b + boy - 1);
        b = (int64_t)((uint64_t)b + boy);
    }
    parcalari_calistir(parcalar, n);
}

/* parallel { is1  is2 ... }: her iş ayrı bir çekirdekte (çekirdekten fazla iş varsa gruplar hâlinde) */
void paralel_isler(VashIs *isler, void *ortam, int64_t n) {
    int64_t grup = cekirdek_sayisi();
    for (int64_t ilk = 0; ilk < n; ilk += grup) {
        int k = (int)((n - ilk) < grup ? (n - ilk) : grup);
        IsParcasi parcalar[64];
        for (int i = 0; i < k; i++) {
            parcalar[i].is = isler[ilk + i];
            parcalar[i].ortam = ortam;
            parcalar[i].bas = 0;
            parcalar[i].son = 0;
        }
        parcalari_calistir(parcalar, k);
    }
}

/* args(): programa komut satırından verilen bilgiler (program adı hariç), Türkçe harfler dahil */
Liste *vash_args(void) {
    int n = 0;
    wchar_t **w = CommandLineToArgvW(GetCommandLineW(), &n);
    Liste *l = liste_yeni(T_TEXT, n > 4 ? n : 4);
    for (int i = 1; w && i < n; i++) {
        int boy = WideCharToMultiByte(CP_UTF8, 0, w[i], -1, NULL, 0, NULL, NULL);
        char *gecici = malloc((size_t)boy);
        if (!gecici) hafiza_doldu();
        WideCharToMultiByte(CP_UTF8, 0, w[i], -1, gecici, boy, NULL, NULL);
        liste_ekle(l, (int64_t)(intptr_t)metin_c_den(gecici));
        free(gecici);
    }
    if (w) LocalFree(w);
    return l;
}

/* print / write paralel çalışırken satırlar birbirine karışmasın */
void yaz_kilitle(void) { if (paralel_aktif) EnterCriticalSection(&yaz_kilidi); }
void yaz_ac(void)      { if (paralel_aktif) LeaveCriticalSection(&yaz_kilidi); }

/* parallel repeat'te toplama (toplam = toplam + x, sayilar[k] = sayilar[k] + 1):
 * her çekirdek kendi ara sonucunu tutar, döngü bitince ara sonuçlar burada asıl değişkene eklenir (aynı anda tek çekirdek). */
void toplama_kilitle(void) { EnterCriticalSection(&toplama_kilidi); }
void toplama_ac(void)      { LeaveCriticalSection(&toplama_kilidi); }

/* asıl listeyle aynı uzunlukta, her elemanı başlangıç değeri (0 ya da 1) olan bir ara liste */
Liste *liste_toplama_parcasi(Liste *ornek, int64_t kimlik) {
    int64_t n = ornek ? ornek->uzunluk : 0;
    Liste *l = liste_yeni(ornek ? ornek->tur : T_INT, n > 4 ? n : 4);
    for (int64_t i = 0; i < n; i++) veri_koy(l, i, kimlik);
    l->uzunluk = n;
    return l;
}

/* islem: 0 = topla, 1 = çarp */
void liste_toplama_birlestir(Liste *hedef, Liste *parca, int64_t islem, int64_t satir) {
    if (!hedef || !parca) return;
    EnterCriticalSection(&toplama_kilidi);
    int64_t n = hedef->uzunluk < parca->uzunluk ? hedef->uzunluk : parca->uzunluk;
    if (hedef->tur == T_FLOAT) {
        for (int64_t i = 0; i < n; i++) {
            double a, b;
            memcpy(&a, &hedef->veri[i], sizeof a);
            memcpy(&b, &parca->veri[i], sizeof b);
            a = islem ? a * b : a + b;
            memcpy(&hedef->veri[i], &a, sizeof a);
        }
    } else {
        for (int64_t i = 0; i < n; i++) {
            int64_t r;
            int tasti = islem ? __builtin_mul_overflow(hedef->veri[i], parca->veri[i], &r)
                              : __builtin_add_overflow(hedef->veri[i], parca->veri[i], &r);
            if (tasti) hata_tasma(satir);
            hedef->veri[i] = r;
        }
    }
    LeaveCriticalSection(&toplama_kilidi);
}

/* ====================================================================
 *  bytes: ikili veriler (resim, ses, zip ...)
 *  Liste yapısını kullanır (sayaç, uzunluk, kapasite, tur = T_BYTES), ama veri bayt bayt durur.
 *  Böylece sayaç, kopyala-yaz ve listelerin içinde durmak listelerle aynı şekilde çalışır.
 * ==================================================================== */
static Liste *bayt_bos(int64_t kapasite) {
    Liste *l = liste_yeni(T_BYTES, 0);
    if (kapasite < 16) kapasite = 16;
    l->veri = malloc((size_t)kapasite);
    if (!l->veri) hafiza_doldu();
    l->kapasite = kapasite;
    return l;
}

static void bayt_yer_ac(Liste *l, int64_t gereken) {
    if (gereken <= l->kapasite) return;
    int64_t yeni = l->kapasite ? l->kapasite * 2 : 16;
    if (yeni < gereken) yeni = gereken;
    void *v = realloc(l->veri, (size_t)yeni);
    if (!v) hafiza_doldu();
    l->veri = v;
    l->kapasite = yeni;
}

/* Bayt dizisinin kendine ait kopyası (sahiplik_birak: eskinin sayacından bizi düş) */
static Liste *bayt_kopya(Liste *l, int sahiplik_birak) {
    CA->kapali++;                                    /* kopya değişkenin kendisine ait: normal bellekte */
    Liste *y = bayt_bos(l->uzunluk);
    CA->kapali--;
    memcpy(y->veri, l->veri, (size_t)l->uzunluk);
    y->uzunluk = l->uzunluk;
    if (sahiplik_birak) sayac_azalt(&l->sayac);
    return y;
}

static void bayt_yaz(Liste *l) {                     /* bytes[72, 101, 108] (uzunsa ilk 32'si) */
    fputs("bytes[", stdout);
    int64_t n = l->uzunluk > 32 ? 32 : l->uzunluk;
    const uint8_t *v = (const uint8_t *)l->veri;
    for (int64_t i = 0; i < n; i++) {
        if (i > 0) fputs(", ", stdout);
        printf("%u", (unsigned)v[i]);
    }
    if (l->uzunluk > n) printf(MESAJ(", ... (toplam %lld bayt)", ", ... (%lld bytes in total)"), (long long)l->uzunluk);
    putchar(']');
}

static void bayt_hatasi(int64_t satir, const char *mesaj, ...) {
    fflush(stdout);
    fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): ", "\nRUNTIME ERROR (line %lld): "), (long long)satir);
    va_list ap;
    va_start(ap, mesaj);
    vfprintf(stderr, mesaj, ap);
    va_end(ap);
    fputc('\n', stderr);
    exit(1);
}

Liste *bayt_yeni(int64_t n, int64_t satir) {
    if (n < 0) bayt_hatasi(satir, MESAJ("bytes(%lld): bayt sayısı eksi olamaz.", "bytes(%lld): the number of bytes cannot be negative."), (long long)n);
    Liste *l = bayt_bos(n);
    memset(l->veri, 0, (size_t)n);
    l->uzunluk = n;
    return l;
}

static void bayt_degeri_kontrol(int64_t x, int64_t satir) {
    if (x < 0 || x > 255)
        bayt_hatasi(satir, MESAJ("Bir bayt 0 ile 255 arasında olmalı, %lld konamaz.", "A byte must be between 0 and 255; %lld cannot be stored."), (long long)x, 0);
}

static void bayt_sira_kontrol(Liste *l, int64_t sira, int64_t satir) {
    if (sira >= 1 && sira <= l->uzunluk) return;
    if (sira == 0) bayt_hatasi(satir, MESAJ("Vash'ta sıralar 1'den başlar; ilk bayt veri[1].", "In Vash, positions start at 1; the first byte is data[1]."), 0, 0);
    bayt_hatasi(satir, MESAJ("%lld baytlık dizinin %lld. baytı yok.", "The byte list has %lld bytes, so there is no byte number %lld."), (long long)l->uzunluk, (long long)sira);
}

void bayt_koy(Liste *l, int64_t sira, int64_t x, int64_t satir) {
    bayt_sira_kontrol(l, sira, satir);
    bayt_degeri_kontrol(x, satir);
    ((uint8_t *)l->veri)[sira - 1] = (uint8_t)x;
}

void bayt_ekle(Liste *l, int64_t x, int64_t satir) {
    bayt_degeri_kontrol(x, satir);
    bayt_yer_ac(l, l->uzunluk + 1);
    ((uint8_t *)l->veri)[l->uzunluk++] = (uint8_t)x;
}

/* veri[a to b]: iki uç dahil */
Liste *bayt_parca(Liste *l, int64_t a, int64_t b, int64_t satir) {
    if (a < 1 || b > l->uzunluk || a > b + 1)
        bayt_hatasi(satir, MESAJ("%lld baytlık diziden bu parça alınamaz (a to b: 1 ≤ a, b ≤ uzunluk).", "Cannot take this piece from a byte list of %lld bytes (a to b: 1 ≤ a, b ≤ length)."), (long long)l->uzunluk, 0);
    int64_t n = b - a + 1;
    Liste *y = bayt_bos(n);
    memcpy(y->veri, (uint8_t *)l->veri + (a - 1), (size_t)n);
    y->uzunluk = n;
    return y;
}

static void bayt_boyut_kontrol(int64_t boyut, int64_t satir) {
    if (boyut != 1 && boyut != 2 && boyut != 4 && boyut != 8)
        bayt_hatasi(satir, MESAJ("Sayının boyutu 1, 2, 4 ya da 8 bayt olabilir, %lld olamaz.", "A number's size can be 1, 2, 4 or 8 bytes, not %lld."), (long long)boyut, 0);
}

/* sira'dan başlayan boyut baytlık sayı (küçük uçtan: çoğu dosya böyle). 1, 2, 4: işaretsiz; 8: int'in kendisi */
int64_t bayt_sayi_al(Liste *l, int64_t sira, int64_t boyut, int64_t satir) {
    bayt_boyut_kontrol(boyut, satir);
    if (sira < 1 || sira + boyut - 1 > l->uzunluk)
        bayt_hatasi(satir, MESAJ("%lld baytlık dizide %lld. bayttan başlayan sayı sığmıyor.", "In a byte list of %lld bytes, a number starting at byte %lld does not fit."), (long long)l->uzunluk, (long long)sira);
    const uint8_t *p = (const uint8_t *)l->veri + (sira - 1);
    uint64_t x = 0;
    for (int64_t i = boyut - 1; i >= 0; i--) x = (x << 8) | p[i];
    return (int64_t)x;
}

/* sayıyı boyut bayt olarak sona ekle (küçük uçtan); eksi sayılar da yazılabilir */
void bayt_sayi_ekle(Liste *l, int64_t x, int64_t boyut, int64_t satir) {
    bayt_boyut_kontrol(boyut, satir);
    if (boyut < 8) {
        int64_t ust = ((int64_t)1 << (8 * boyut)) - 1, alt = -((int64_t)1 << (8 * boyut - 1));
        if (x < alt || x > ust)
            bayt_hatasi(satir, MESAJ("%lld sayısı %lld bayta sığmıyor.", "The number %lld does not fit in %lld bytes."), (long long)x, (long long)boyut);
    }
    bayt_yer_ac(l, l->uzunluk + boyut);
    uint8_t *p = (uint8_t *)l->veri + l->uzunluk;
    uint64_t u = (uint64_t)x;
    for (int64_t i = 0; i < boyut; i++) { p[i] = (uint8_t)(u & 0xFF); u >>= 8; }
    l->uzunluk += boyut;
}

/* "yazı".to_bytes(): metnin UTF-8 baytları */
Liste *metin_bayta(const char *m) {
    int64_t n = UZUNLUK(m);
    Liste *l = bayt_bos(n);
    memcpy(l->veri, m, (size_t)n);
    l->uzunluk = n;
    return l;
}

/* veri.to_text(): baytları metin olarak oku (geçersiz UTF-8 baytları '?' olur) */
char *bayt_metne(Liste *l) {
    const uint8_t *v = (const uint8_t *)l->veri;
    int64_t n = l->uzunluk, i = 0;
    char *gecici = malloc((size_t)n + 1);
    if (!gecici) hafiza_doldu();
    int64_t y = 0;
    while (i < n) {
        uint8_t c = v[i];
        int boy = c < 0x80 ? 1 : (c >> 5) == 6 ? 2 : (c >> 4) == 14 ? 3 : (c >> 3) == 30 ? 4 : 0;
        int gecerli = boy > 0 && i + boy <= n;
        for (int k = 1; gecerli && k < boy; k++) if ((v[i + k] & 0xC0) != 0x80) gecerli = 0;
        if (!gecerli) { gecici[y++] = '?'; i++; continue; }
        for (int k = 0; k < boy; k++) gecici[y++] = (char)v[i + k];
        i += boy;
    }
    char *m = metin_parca(gecici, (size_t)y);
    free(gecici);
    return m;
}

#ifdef _WIN32
/* =====================================================================
 *  KLASÖRLER (std/fs.vash): klasör okuma, dosya parmak izi, çöpe taşıma, disk bilgisi
 *  Dönen yazılar iş parçacığına özel bir tamponda; Vash hemen kopyalar.
 * ===================================================================== */
static _Thread_local char *fs_tampon = NULL;
static _Thread_local size_t fs_kap = 0;

static void fs_yer(size_t n) {
    if (n <= fs_kap) return;
    size_t yeni = fs_kap ? fs_kap : 65536;
    while (yeni < n) yeni *= 2;
    char *p = realloc(fs_tampon, yeni);
    if (!p) hafiza_doldu();
    fs_tampon = p;
    fs_kap = yeni;
}

/* Klasördeki her şey, satır başına:  tür \t bayt \t değişme_zamanı(unix sn) \t ad
   tür: D klasör, F dosya, L bağlantı (junction/symlink; içine girilmemeli). Okunamazsa "". */
const char *vash_klasor_oku(const char *yol) {
    wchar_t *w = kum_genis(yol);
    fs_yer(1);
    fs_tampon[0] = 0;
    if (!w) return fs_tampon;
    kum_yolu_denetle(yol, w);
    size_t L = wcslen(w);
    wchar_t *desen = malloc(sizeof(wchar_t) * (L + 3));
    if (!desen) hafiza_doldu();
    wcscpy(desen, w);
    if (L > 0 && desen[L - 1] != L'\\' && desen[L - 1] != L'/') wcscat(desen, L"\\");
    wcscat(desen, L"*");
    free(w);
    WIN32_FIND_DATAW f;
    HANDLE h = FindFirstFileExW(desen, FindExInfoBasic, &f, FindExSearchNameMatch, NULL, FIND_FIRST_EX_LARGE_FETCH);
    free(desen);
    if (h == INVALID_HANDLE_VALUE) return fs_tampon;
    size_t n = 0;
    char ad[1100];
    do {
        if (f.cFileName[0] == L'.' && (f.cFileName[1] == 0 || (f.cFileName[1] == L'.' && f.cFileName[2] == 0))) continue;
        int m = WideCharToMultiByte(CP_UTF8, 0, f.cFileName, -1, ad, (int)sizeof ad, NULL, NULL);
        if (m <= 0) continue;
        char tur = (f.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) ? 'L' : ((f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) ? 'D' : 'F');
        unsigned long long bayt = ((unsigned long long)f.nFileSizeHigh << 32) | f.nFileSizeLow;
        unsigned long long ft = ((unsigned long long)f.ftLastWriteTime.dwHighDateTime << 32) | f.ftLastWriteTime.dwLowDateTime;
        long long zaman = ft ? (long long)(ft / 10000000ULL) - 11644473600LL : 0;
        fs_yer(n + (size_t)m + 64);
        n += (size_t)sprintf(fs_tampon + n, "%c\t%llu\t%lld\t%s\n", tur, bayt, zaman, ad);
    } while (FindNextFileW(h, &f));
    FindClose(h);
    return fs_tampon;
}

static inline uint64_t iz_karistir(uint64_t h, uint64_t w) {
    h ^= w * 0x9E3779B97F4A7C15ULL;
    h = (h << 31) | (h >> 33);
    return h * 0xC2B2AE3D27D4EB4FULL;
}

static uint64_t iz_blok(uint64_t h, const unsigned char *b, size_t r) {
    size_t i = 0;
    for (; i + 8 <= r; i += 8) {
        uint64_t w;
        memcpy(&w, b + i, 8);
        h = iz_karistir(h, w);
    }
    uint64_t son = 0;
    for (size_t k = 0; i < r; i++, k++) son |= (uint64_t)b[i] << (8 * k);
    return iz_karistir(h, son ^ (uint64_t)r);
}

/* Dosyanın bütün içeriğinden 64 bitlik parmak izi, 16 onaltılık harf; okunamazsa "" */
const char *vash_dosya_ozeti(const char *yol) {
    fs_yer(32);
    fs_tampon[0] = 0;
    FILE *d = dosya_ac(yol, L"rb");
    if (!d) return fs_tampon;
    static _Thread_local unsigned char *blok = NULL;
    if (!blok) { blok = malloc(1 << 20); if (!blok) hafiza_doldu(); }
    uint64_t h = 0x243F6A8885A308D3ULL;
    size_t r;
    while ((r = fread(blok, 1, 1 << 20, d)) > 0) h = iz_blok(h, blok, r);
    fclose(d);
    sprintf(fs_tampon, "%016llx", (unsigned long long)h);
    return fs_tampon;
}

/* Hızlı ön iz: sadece ilk ve son 64 KB (aynı boyutlu dosyaları çabucak ayırmak için) */
const char *vash_dosya_ozeti_hizli(const char *yol) {
    fs_yer(32);
    fs_tampon[0] = 0;
    FILE *d = dosya_ac(yol, L"rb");
    if (!d) return fs_tampon;
    static _Thread_local unsigned char *blok = NULL;
    if (!blok) { blok = malloc(65536); if (!blok) hafiza_doldu(); }
    uint64_t h = 0x13198A2E03707344ULL;
    size_t r = fread(blok, 1, 65536, d);
    h = iz_blok(h, blok, r);
    if (_fseeki64(d, -65536, SEEK_END) == 0) {
        r = fread(blok, 1, 65536, d);
        h = iz_blok(h, blok, r);
    }
    fclose(d);
    sprintf(fs_tampon, "%016llx", (unsigned long long)h);
    return fs_tampon;
}

/* Dosyayı ya da klasörü Geri Dönüşüm Kutusu'na taşı (geri alınabilir). Oldu mu? */
int32_t vash_cope_tasi(const char *yol) {
    wchar_t *w = kum_genis(yol);
    if (!w) return 0;
    kum_yolu_denetle(yol, w);
    wchar_t tam[KUM_UZUNLUK + 2];
    DWORD m = GetFullPathNameW(w, KUM_UZUNLUK, tam, NULL);
    free(w);
    if (m == 0 || m >= KUM_UZUNLUK) return 0;
    if (m <= 3) return 0;                               /* bir sürücünün kökü (C:\) asla */
    tam[m] = 0;
    tam[m + 1] = 0;                                     /* çift sıfırla biten liste */
    SHFILEOPSTRUCTW op;
    memset(&op, 0, sizeof op);
    op.wFunc = FO_DELETE;
    op.pFrom = tam;
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI;
    return SHFileOperationW(&op) == 0 && !op.fAnyOperationsAborted;
}

/* Sürücü bilgisi: "toplam_bayt \t boş_bayt"; okunamazsa "" */
const char *vash_disk_bilgi(const char *kok) {
    fs_yer(64);
    fs_tampon[0] = 0;
    wchar_t *w = kum_genis(kok);
    if (!w) return fs_tampon;
    ULARGE_INTEGER bos, toplam, toplam_bos;
    if (GetDiskFreeSpaceExW(w, &bos, &toplam, &toplam_bos)) sprintf(fs_tampon, "%llu\t%llu", (unsigned long long)toplam.QuadPart, (unsigned long long)toplam_bos.QuadPart);
    free(w);
    return fs_tampon;
}

/* Sürücüler: "C:\\\nD:\\\n" */
const char *vash_suruculer(void) {
    fs_yer(128);
    DWORD maske = GetLogicalDrives();
    size_t n = 0;
    for (int i = 0; i < 26; i++) {
        if (maske & (1u << i)) {
            wchar_t k[4] = { (wchar_t)(L'A' + i), L':', L'\\', 0 };
            UINT t = GetDriveTypeW(k);
            if (t == DRIVE_FIXED || t == DRIVE_REMOVABLE) n += (size_t)sprintf(fs_tampon + n, "%c:\\\n", 'A' + i);
        }
    }
    fs_tampon[n] = 0;
    return fs_tampon;
}

/* Dosya Gezgini'nde göster: klasörse açar, dosyaysa seçili gösterir. Sadece var olan yollar; hiçbir şey çalıştırılmaz. */
void vash_gezginde_ac(const char *yol) {
    wchar_t *w = kum_genis(yol);
    if (!w) return;
    kum_yolu_denetle(yol, w);
    wchar_t tam[KUM_UZUNLUK];
    DWORD m = GetFullPathNameW(w, KUM_UZUNLUK, tam, NULL);
    free(w);
    if (m == 0 || m >= KUM_UZUNLUK) return;
    DWORD a = GetFileAttributesW(tam);
    if (a == INVALID_FILE_ATTRIBUTES) return;
    wchar_t arg[KUM_UZUNLUK + 16];
    if (a & FILE_ATTRIBUTE_DIRECTORY) swprintf(arg, KUM_UZUNLUK + 16, L"\"%ls\"", tam);
    else swprintf(arg, KUM_UZUNLUK + 16, L"/select,\"%ls\"", tam);
    ShellExecuteW(NULL, L"open", L"explorer.exe", arg, NULL, SW_SHOWNORMAL);
}

/* Dosyanın ilk n baytını tampona oku; okunan bayt sayısı (okunamazsa 0) */
int64_t vash_dosya_basi(const char *yol, uint8_t *tampon, int64_t n) {
    FILE *f = dosya_ac(yol, L"rb");
    if (!f) return 0;
    size_t r = fread(tampon, 1, (size_t)n, f);
    fclose(f);
    return (int64_t)r;
}

/* İşlemci çekirdeği sayısı */
int64_t vash_cekirdek(void) {
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    return (int64_t)si.dwNumberOfProcessors;
}
#endif

/* read_bytes: bütün dosya, olduğu gibi (okunamazsa NULL → none) */
Liste *dosya_bayt_oku(const char *yol) {
    FILE *f = dosya_ac(yol, L"rb");
    if (!f) return NULL;
    Liste *l = bayt_bos(4096);
    for (;;) {
        bayt_yer_ac(l, l->uzunluk + 65536);
        size_t r = fread((uint8_t *)l->veri + l->uzunluk, 1, (size_t)(l->kapasite - l->uzunluk), f);
        if (r == 0) break;
        l->uzunluk += (int64_t)r;
    }
    int hata_var = ferror(f);
    fclose(f);
    if (hata_var) { liste_birak(l); return NULL; }
    return l;
}

/* write_bytes: dosyaya olduğu gibi yaz; oldu mu? */
int32_t dosya_bayt_yaz(const char *yol, Liste *l) {
    FILE *f = dosya_ac(yol, L"wb");
    if (!f) return 0;
    size_t n = (size_t)l->uzunluk;
    int tamam = fwrite(l->veri, 1, n, f) == n;
    if (fclose(f) != 0) tamam = 0;
    return tamam;
}

/* İç içe değiştirme için: s[k] değerinin durduğu yerin adresi (anahtar yoksa çalışma hatası) */
int64_t *sozluk_yer(Sozluk *s, int64_t k, int64_t satir) {
    int64_t kayit = sozluk_konum(s, k);
    if (kayit < 0) sozluk_anahtar_yok(s, k, satir);
    return &s->degerler[kayit];
}

/* ====================================================================
 *  HTTP (std/http.vash bunları extern ile çağırır)
 *  Arka plandaki iş parçacıkları sadece C belleğiyle çalışır, Vash değerlerine dokunmaz.
 *  İstekler ve sunucular numarayla tutulur: aynı isteğe iki kez cevap vermek programı bozamaz.
 * ==================================================================== */

static void tampon_ekle(Tampon *t, const char *s, size_t n) {
    if (t->n + n + 1 > t->kap) {
        size_t yeni = t->kap ? t->kap * 2 : 1024;
        while (yeni < t->n + n + 1) yeni *= 2;
        char *p = realloc(t->p, yeni);
        if (!p) hafiza_doldu();
        t->p = p;
        t->kap = yeni;
    }
    if (n) memcpy(t->p + t->n, s, n);
    t->n += n;
    t->p[t->n] = 0;
}

static wchar_t *genis(const char *s) {
    int n = MultiByteToWideChar(CP_UTF8, 0, s, -1, NULL, 0);
    wchar_t *w = malloc(sizeof(wchar_t) * (size_t)(n > 0 ? n : 1));
    if (!w) hafiza_doldu();
    if (n > 0) MultiByteToWideChar(CP_UTF8, 0, s, -1, w, n); else w[0] = 0;
    return w;
}

static char *dar(const wchar_t *w, int uzunluk) {
    int n = uzunluk > 0 ? WideCharToMultiByte(CP_UTF8, 0, w, uzunluk, NULL, 0, NULL, NULL) : 0;
    char *s = malloc((size_t)n + 1);
    if (!s) hafiza_doldu();
    if (n > 0) WideCharToMultiByte(CP_UTF8, 0, w, uzunluk, s, n, NULL, NULL);
    s[n] = 0;
    return s;
}

static CRITICAL_SECTION http_kilidi;
static volatile LONG http_kilidi_hazir = 0;
static void http_kilit_hazirla(void) {
    if (InterlockedCompareExchange(&http_kilidi_hazir, 1, 0) == 0) InitializeCriticalSection(&http_kilidi);
}
static __thread const char *http_son_hata = "";
const char *vash_http_hata(void) { return http_son_hata; }

/* ---------- İstemci: tek istek, cevap gelene kadar bekler ---------- */
typedef struct { int32_t durum; Tampon govde; char *basliklar; } HttpCevap;
static HttpCevap *cevaplar[4096];

/* olmazsa 0 (nedeni: vash_http_hata), olursa cevabın numarası */
int64_t vash_http_istek(const char *yontem, const char *url, const char *govde, const char *basliklar) {
    http_kilit_hazirla();
    http_son_hata = "";
    wchar_t *wurl = genis(url);
    URL_COMPONENTS uc;
    memset(&uc, 0, sizeof uc);
    uc.dwStructSize = sizeof uc;
    static __thread wchar_t sunucu[256], yol[4096], ek[4096], tam_yol[8192];
    uc.lpszHostName = sunucu; uc.dwHostNameLength = 256;
    uc.lpszUrlPath = yol; uc.dwUrlPathLength = 4096;
    uc.lpszExtraInfo = ek; uc.dwExtraInfoLength = 4096;
    if (!WinHttpCrackUrl(wurl, 0, 0, &uc)) { free(wurl); http_son_hata = MESAJ("adres (URL) anlaşılamadı; http:// ya da https:// ile başlamalı", "could not understand the address (URL); it must start with http:// or https://"); return 0; }
    free(wurl);
    _snwprintf(tam_yol, 8192, L"%ls%ls", uc.dwUrlPathLength ? yol : L"/", ek);
    tam_yol[8191] = 0;
    HINTERNET oturum = WinHttpOpen(L"Vash/0.1", WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY, WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!oturum) oturum = WinHttpOpen(L"Vash/0.1", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!oturum) { http_son_hata = MESAJ("ağ kullanılamıyor", "the network cannot be used"); return 0; }
    HINTERNET bag = WinHttpConnect(oturum, sunucu, uc.nPort, 0);
    wchar_t *wyontem = genis(yontem);
    HINTERNET ist = bag ? WinHttpOpenRequest(bag, wyontem, tam_yol, NULL, WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES,
                                             uc.nScheme == INTERNET_SCHEME_HTTPS ? WINHTTP_FLAG_SECURE : 0) : NULL;
    free(wyontem);
    int64_t no = 0;
    if (ist) {
        wchar_t *wbas = genis(basliklar);
        DWORD govde_boy = (DWORD)strlen(govde);
        BOOL tamam = WinHttpSendRequest(ist, wbas[0] ? wbas : WINHTTP_NO_ADDITIONAL_HEADERS, wbas[0] ? (DWORD)-1L : 0,
                                        (LPVOID)govde, govde_boy, govde_boy, 0)
                     && WinHttpReceiveResponse(ist, NULL);
        free(wbas);
        if (tamam) {
            HttpCevap *c = calloc(1, sizeof *c);
            if (!c) hafiza_doldu();
            DWORD durum = 0, boy = sizeof durum;
            WinHttpQueryHeaders(ist, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER, WINHTTP_HEADER_NAME_BY_INDEX, &durum, &boy, WINHTTP_NO_HEADER_INDEX);
            c->durum = (int32_t)durum;
            DWORD bb = 0;
            WinHttpQueryHeaders(ist, WINHTTP_QUERY_RAW_HEADERS_CRLF, WINHTTP_HEADER_NAME_BY_INDEX, NULL, &bb, WINHTTP_NO_HEADER_INDEX);
            wchar_t *wb = malloc(bb + 2);
            if (wb && WinHttpQueryHeaders(ist, WINHTTP_QUERY_RAW_HEADERS_CRLF, WINHTTP_HEADER_NAME_BY_INDEX, wb, &bb, WINHTTP_NO_HEADER_INDEX))
                c->basliklar = dar(wb, (int)(bb / sizeof(wchar_t)));
            else c->basliklar = dar(L"", 0);
            free(wb);
            tampon_ekle(&c->govde, "", 0);
            for (;;) {
                DWORD var = 0, okunan = 0;
                if (!WinHttpQueryDataAvailable(ist, &var) || var == 0) break;
                char *parca = malloc(var);
                if (!parca) hafiza_doldu();
                if (WinHttpReadData(ist, parca, var, &okunan)) tampon_ekle(&c->govde, parca, okunan);
                free(parca);
                if (okunan == 0) break;
            }
            EnterCriticalSection(&http_kilidi);
            for (int i = 1; i < 4096; i++) if (!cevaplar[i]) { cevaplar[i] = c; no = i; break; }
            LeaveCriticalSection(&http_kilidi);
            if (!no) { free(c->govde.p); free(c->basliklar); free(c); http_son_hata = MESAJ("çok fazla açık cevap", "too many open responses"); }
        } else {
            http_son_hata = MESAJ("sunucuya ulaşılamadı ya da cevap gelmedi", "could not reach the server, or no answer came");
        }
        WinHttpCloseHandle(ist);
    } else {
        http_son_hata = MESAJ("sunucuya bağlanılamadı", "could not connect to the server");
    }
    if (bag) WinHttpCloseHandle(bag);
    WinHttpCloseHandle(oturum);
    return no;
}

static HttpCevap *cevap_bul(int64_t no) { return (no > 0 && no < 4096) ? cevaplar[no] : NULL; }
int64_t vash_http_durum(int64_t no) { HttpCevap *c = cevap_bul(no); return c ? c->durum : 0; }
const char *vash_http_govde(int64_t no) { HttpCevap *c = cevap_bul(no); return c && c->govde.p ? c->govde.p : ""; }
const char *vash_http_basliklar(int64_t no) { HttpCevap *c = cevap_bul(no); return c ? c->basliklar : ""; }
void vash_http_birak(int64_t no) {
    http_kilit_hazirla();
    EnterCriticalSection(&http_kilidi);
    HttpCevap *c = cevap_bul(no);
    if (c) cevaplar[no] = NULL;
    LeaveCriticalSection(&http_kilidi);
    if (c) { free(c->govde.p); free(c->basliklar); free(c); }
}

/* ---------- Sunucu: bağlantılar arka planda kabul edilir, istekler sıraya girer ----------
 *  Her bağlantı (düz ya da TLS/HTTPS) bir Baglanti'dır. Okuyan iş parçacığı isteği okuyup sıraya koyar;
 *  ana program cevap verince bağlantı açık kalacaksa (keep-alive) yeni bir okuyucu aynı bağlantıyı bekler. */
typedef struct {
    SOCKET k;
    int tls;
    CtxtHandle ctx;
    int ctx_var;
    SecPkgContext_StreamSizes boy;
    Tampon sifreli;                 /* gelmiş ama henüz çözülmemiş şifreli baytlar */
    Tampon artan;                   /* çözülmüş ama henüz kullanılmamış düz baytlar (bir sonraki isteğin başı) */
} Baglanti;

typedef struct HttpSunucu HttpSunucu;

typedef struct HttpIstek {
    Baglanti *b;
    HttpSunucu *sunucu;
    int kalici;                     /* cevaptan sonra bağlantı açık kalsın mı (keep-alive) */
    char *yontem, *yol, *sorgu, *basliklar;
    Tampon govde;
    struct HttpIstek *sonraki;
} HttpIstek;

struct HttpSunucu {
    SOCKET dinleyen;
    int tls;
    CredHandle kimlik;              /* HTTPS: sunucunun sertifikası */
    HttpIstek *ilk, *son;           /* bekleyen istekler (sıra) */
    CRITICAL_SECTION kilit;
    CONDITION_VARIABLE geldi;
    volatile LONG kapali;
};

static HttpSunucu *sunucular[64];
static HttpIstek *istekler[65536];        /* cevap bekleyen istekler (numarayla) */
static int64_t istek_sirasi = 0;

typedef struct { HttpSunucu *s; Baglanti *b; int yeni; } BaglantiIsi;

static void baglanti_kapat(Baglanti *b) {
    if (!b) return;
    if (b->ctx_var) DeleteSecurityContext(&b->ctx);
    closesocket(b->k);
    free(b->sifreli.p);
    free(b->artan.p);
    free(b);
}

static void istek_sil(HttpIstek *r) {
    free(r->yontem); free(r->yol); free(r->sorgu); free(r->basliklar); free(r->govde.p); free(r);
}

static int soket_gonder(SOCKET k, const char *p, size_t n) {
    size_t g = 0;
    while (g < n) {
        int r = send(k, p + g, (int)(n - g), 0);
        if (r <= 0) return 0;
        g += (size_t)r;
    }
    return 1;
}

static void tampon_bastan_at(Tampon *t, size_t n) {
    if (n >= t->n) { t->n = 0; if (t->p) t->p[0] = 0; return; }
    memmove(t->p, t->p + n, t->n - n);
    t->n -= n;
    t->p[t->n] = 0;
}

/* TLS el sıkışması (sunucu tarafı); olursa 1 */
static int tls_el_sikis(HttpSunucu *s, Baglanti *b) {
    int ilk = 1;
    for (;;) {
        if (b->sifreli.n == 0 || !ilk) {
            char parca[16384];
            int r = recv(b->k, parca, sizeof parca, 0);
            if (r <= 0) return 0;
            tampon_ekle(&b->sifreli, parca, (size_t)r);
        }
        SecBuffer gir[2] = { { (unsigned long)b->sifreli.n, SECBUFFER_TOKEN, b->sifreli.p }, { 0, SECBUFFER_EMPTY, NULL } };
        SecBufferDesc gir_d = { SECBUFFER_VERSION, 2, gir };
        SecBuffer cik[1] = { { 0, SECBUFFER_TOKEN, NULL } };
        SecBufferDesc cik_d = { SECBUFFER_VERSION, 1, cik };
        unsigned long ozellik = 0;
        SECURITY_STATUS d = AcceptSecurityContext(&s->kimlik, b->ctx_var ? &b->ctx : NULL, &gir_d,
            ASC_REQ_SEQUENCE_DETECT | ASC_REQ_REPLAY_DETECT | ASC_REQ_CONFIDENTIALITY | ASC_REQ_STREAM | ASC_REQ_ALLOCATE_MEMORY | ASC_REQ_EXTENDED_ERROR,
            0, &b->ctx, &cik_d, &ozellik, NULL);
        if (d == SEC_E_INCOMPLETE_MESSAGE) { ilk = 0; continue; }
        if (d == SEC_E_OK || d == SEC_I_CONTINUE_NEEDED || (FAILED(d) && (ozellik & ASC_RET_EXTENDED_ERROR))) b->ctx_var = 1;
        if (cik[0].cbBuffer && cik[0].pvBuffer) {
            int tamam = soket_gonder(b->k, cik[0].pvBuffer, cik[0].cbBuffer);
            FreeContextBuffer(cik[0].pvBuffer);
            if (!tamam) return 0;
        }
        if (d != SEC_E_OK && d != SEC_I_CONTINUE_NEEDED) return 0;
        if (gir[1].BufferType == SECBUFFER_EXTRA && gir[1].cbBuffer > 0)
            tampon_bastan_at(&b->sifreli, b->sifreli.n - gir[1].cbBuffer);
        else
            b->sifreli.n = 0;
        if (d == SEC_E_OK) {
            return QueryContextAttributesW(&b->ctx, SECPKG_ATTR_STREAM_SIZES, &b->boy) == SEC_E_OK;
        }
        ilk = b->sifreli.n == 0;
    }
}

/* Bağlantıdan biraz düz bayt oku, hedefe ekle. >0: okundu, 0: bağlantı kapandı, <0: hata */
static int bag_oku(Baglanti *b, Tampon *hedef) {
    if (b->artan.n > 0) {                                       /* önceki okumadan kalan */
        int n = (int)b->artan.n;
        tampon_ekle(hedef, b->artan.p, b->artan.n);
        b->artan.n = 0;
        return n;
    }
    if (!b->tls) {
        char parca[8192];
        int r = recv(b->k, parca, sizeof parca, 0);
        if (r > 0) tampon_ekle(hedef, parca, (size_t)r);
        return r;
    }
    for (;;) {
        if (b->sifreli.n > 0) {
            SecBuffer t[4] = { { (unsigned long)b->sifreli.n, SECBUFFER_DATA, b->sifreli.p }, { 0, SECBUFFER_EMPTY, NULL },
                               { 0, SECBUFFER_EMPTY, NULL }, { 0, SECBUFFER_EMPTY, NULL } };
            SecBufferDesc td = { SECBUFFER_VERSION, 4, t };
            SECURITY_STATUS d = DecryptMessage(&b->ctx, &td, 0, NULL);
            if (d == SEC_E_OK) {
                int n = 0;
                Tampon ek = {0};
                for (int i = 0; i < 4; i++) {
                    if (t[i].BufferType == SECBUFFER_DATA && t[i].cbBuffer) { tampon_ekle(hedef, t[i].pvBuffer, t[i].cbBuffer); n += (int)t[i].cbBuffer; }
                    if (t[i].BufferType == SECBUFFER_EXTRA && t[i].cbBuffer) tampon_ekle(&ek, t[i].pvBuffer, t[i].cbBuffer);
                }
                b->sifreli.n = 0;
                if (ek.n) tampon_ekle(&b->sifreli, ek.p, ek.n);
                free(ek.p);
                if (n > 0) return n;
                continue;
            }
            if (d == SEC_I_CONTEXT_EXPIRED) return 0;
            if (d != SEC_E_INCOMPLETE_MESSAGE) return -1;
        }
        char parca[16384];
        int r = recv(b->k, parca, sizeof parca, 0);
        if (r <= 0) return r;
        tampon_ekle(&b->sifreli, parca, (size_t)r);
    }
}

static int bag_yaz(Baglanti *b, const char *p, size_t n) {
    if (!b->tls) return soket_gonder(b->k, p, n);
    size_t en_fazla = b->boy.cbMaximumMessage;
    char *paket = malloc(b->boy.cbHeader + en_fazla + b->boy.cbTrailer);
    if (!paket) hafiza_doldu();
    int tamam = 1;
    for (size_t g = 0; g < n && tamam; ) {
        size_t parca = n - g < en_fazla ? n - g : en_fazla;
        memcpy(paket + b->boy.cbHeader, p + g, parca);
        SecBuffer t[4] = { { b->boy.cbHeader, SECBUFFER_STREAM_HEADER, paket },
                           { (unsigned long)parca, SECBUFFER_DATA, paket + b->boy.cbHeader },
                           { b->boy.cbTrailer, SECBUFFER_STREAM_TRAILER, paket + b->boy.cbHeader + parca },
                           { 0, SECBUFFER_EMPTY, NULL } };
        SecBufferDesc td = { SECBUFFER_VERSION, 4, t };
        if (EncryptMessage(&b->ctx, 0, &td, 0) != SEC_E_OK) { tamam = 0; break; }
        tamam = soket_gonder(b->k, paket, t[0].cbBuffer + t[1].cbBuffer + t[2].cbBuffer);
        g += parca;
    }
    free(paket);
    return tamam;
}

static char *kopya_parca(const char *b, size_t n) {
    char *s = malloc(n + 1);
    if (!s) hafiza_doldu();
    memcpy(s, b, n);
    s[n] = 0;
    return s;
}

/* Bir bağlantıdan bir istek oku (başlık + Content-Length kadar gövde), sıraya koy */
static DWORD WINAPI baglanti_isle(LPVOID p) {
    BaglantiIsi *is = p;
    HttpSunucu *s = is->s;
    Baglanti *b = is->b;
    int yeni = is->yeni;
    free(is);
    if (yeni) {
        DWORD sure = 15000;                          /* 15 sn ses gelmezse bağlantıyı bırak */
        setsockopt(b->k, SOL_SOCKET, SO_RCVTIMEO, (const char *)&sure, sizeof sure);
        if (b->tls && !tls_el_sikis(s, b)) { baglanti_kapat(b); return 0; }
    }
    Tampon t = {0};
    char *bitis = NULL;
    while (!(t.p && (bitis = strstr(t.p, "\r\n\r\n")))) {
        if (t.n > (1 << 20) || bag_oku(b, &t) <= 0) { baglanti_kapat(b); free(t.p); return 0; }
    }
    size_t baslik_boyu = (size_t)(bitis - t.p) + 4;
    long long uzunluk = 0;
    int kapat_dedi = 0, acik_dedi = 0;
    for (char *c = t.p; c < bitis; c++) {
        if (c == t.p || c[-1] == '\n') {
            if (_strnicmp(c, "content-length:", 15) == 0) uzunluk = atoll(c + 15);
            if (_strnicmp(c, "connection:", 11) == 0) {
                const char *v = c + 11;
                while (*v == ' ') v++;
                if (_strnicmp(v, "close", 5) == 0) kapat_dedi = 1;
                if (_strnicmp(v, "keep-alive", 10) == 0) acik_dedi = 1;
            }
        }
    }
    if (uzunluk < 0 || uzunluk > (64LL << 20)) { baglanti_kapat(b); free(t.p); return 0; }
    while ((long long)(t.n - baslik_boyu) < uzunluk) {
        if (bag_oku(b, &t) <= 0) { baglanti_kapat(b); free(t.p); return 0; }
    }
    HttpIstek *r = calloc(1, sizeof *r);
    if (!r) hafiza_doldu();
    r->b = b;
    r->sunucu = s;
    char *satir_sonu = strstr(t.p, "\r\n");
    char *b1 = memchr(t.p, ' ', (size_t)(satir_sonu - t.p));
    if (!b1) b1 = satir_sonu;
    char *hedef = b1 < satir_sonu ? b1 + 1 : b1;
    char *b2 = memchr(hedef, ' ', (size_t)(satir_sonu - hedef));
    if (!b2) b2 = satir_sonu;
    int http10 = b2 < satir_sonu && strncmp(b2 + 1, "HTTP/1.0", 8) == 0;
    r->kalici = http10 ? acik_dedi : !kapat_dedi;     /* HTTP/1.1'de bağlantı açık kalır (istemci kapat demedikçe) */
    r->yontem = kopya_parca(t.p, (size_t)(b1 - t.p));
    char *soru = memchr(hedef, '?', (size_t)(b2 - hedef));
    r->yol = kopya_parca(hedef, (size_t)((soru ? soru : b2) - hedef));
    r->sorgu = soru ? kopya_parca(soru + 1, (size_t)(b2 - soru - 1)) : kopya_parca("", 0);
    Tampon bas = {0};                                /* başlıklar: "Ad: değer\n" satırları */
    tampon_ekle(&bas, "", 0);
    for (char *c = satir_sonu + 2; c < bitis; ) {
        char *s2 = strstr(c, "\r\n");
        if (!s2 || s2 > bitis) s2 = bitis;
        tampon_ekle(&bas, c, (size_t)(s2 - c));
        tampon_ekle(&bas, "\n", 1);
        c = s2 + 2;
    }
    r->basliklar = bas.p;
    tampon_ekle(&r->govde, "", 0);
    tampon_ekle(&r->govde, t.p + baslik_boyu, (size_t)uzunluk);
    size_t kullanilan = baslik_boyu + (size_t)uzunluk;
    if (t.n > kullanilan) tampon_ekle(&b->artan, t.p + kullanilan, t.n - kullanilan);   /* arka arkaya gelen istek */
    free(t.p);
    EnterCriticalSection(&s->kilit);
    if (s->son) s->son->sonraki = r; else s->ilk = r;
    s->son = r;
    LeaveCriticalSection(&s->kilit);
    WakeConditionVariable(&s->geldi);
    return 0;
}

static void okuyucu_baslat(HttpSunucu *s, Baglanti *b, int yeni) {
    BaglantiIsi *is = malloc(sizeof *is);
    if (!is) hafiza_doldu();
    is->s = s;
    is->b = b;
    is->yeni = yeni;
    HANDLE h = CreateThread(NULL, 256 * 1024, baglanti_isle, is, STACK_SIZE_PARAM_IS_A_RESERVATION, NULL);
    if (h) CloseHandle(h); else { baglanti_kapat(b); free(is); }
}

static DWORD WINAPI kabul_dongusu(LPVOID p) {
    HttpSunucu *s = p;
    while (!s->kapali) {
        SOCKET k = accept(s->dinleyen, NULL, NULL);
        if (k == INVALID_SOCKET) { if (s->kapali) break; Sleep(1); continue; }
        Baglanti *b = calloc(1, sizeof *b);
        if (!b) hafiza_doldu();
        b->k = k;
        BOOL hemen = TRUE;                           /* küçük cevaplar beklemeden gitsin (Nagle kapalı) */
        setsockopt(k, IPPROTO_TCP, TCP_NODELAY, (const char *)&hemen, sizeof hemen);
        b->tls = s->tls;
        okuyucu_baslat(s, b, 1);
    }
    return 0;
}

/* ---------- HTTPS: sertifika ---------- */
/* HTTPS anahtarı program çalışırken kullanıcının anahtar deposunda durmalı (Windows böyle istiyor);
 * program biterken silinir, bilgisayarda iz kalmaz. */
#ifndef PKCS12_ALWAYS_CNG_KSP
#define PKCS12_ALWAYS_CNG_KSP 0x00000200
#endif
static wchar_t silinecek_anahtarlar[16][260];
static int silinecek_sayisi = 0;
static void anahtarlari_sil(void) {
    NCRYPT_PROV_HANDLE saglayici = 0;
    if (NCryptOpenStorageProvider(&saglayici, MS_KEY_STORAGE_PROVIDER, 0) != ERROR_SUCCESS) return;
    for (int i = 0; i < silinecek_sayisi; i++) {
        NCRYPT_KEY_HANDLE anahtar = 0;
        if (NCryptOpenKey(saglayici, &anahtar, silinecek_anahtarlar[i], 0, 0) == ERROR_SUCCESS) NCryptDeleteKey(anahtar, 0);
    }
    silinecek_sayisi = 0;
    NCryptFreeObject(saglayici);
}
static void anahtari_sonra_sil(const wchar_t *ad) {
    if (silinecek_sayisi == 0) atexit(anahtarlari_sil);
    if (silinecek_sayisi < 16) {
        wcsncpy(silinecek_anahtarlar[silinecek_sayisi], ad, 259);
        silinecek_anahtarlar[silinecek_sayisi++][259] = 0;
    }
}

static PCCERT_CONTEXT pfx_sertifikasi(const char *yol, const char *parola) {
    FILE *f = dosya_ac(yol, L"rb");
    if (!f) { http_son_hata = MESAJ("sertifika dosyası açılamadı", "could not open the certificate file"); return NULL; }
    Tampon t = {0};
    char parca[8192];
    size_t r;
    while ((r = fread(parca, 1, sizeof parca, f)) > 0) tampon_ekle(&t, parca, r);
    fclose(f);
    CRYPT_DATA_BLOB blob = { (DWORD)t.n, (BYTE *)t.p };
    wchar_t *wp = genis(parola);
    HCERTSTORE depo = PFXImportCertStore(&blob, wp, CRYPT_USER_KEYSET | PKCS12_ALWAYS_CNG_KSP);
    free(wp);
    free(t.p);
    if (!depo) { http_son_hata = MESAJ("sertifika okunamadı (parola yanlış ya da dosya .pfx değil)", "could not read the certificate (wrong password, or the file is not .pfx)"); return NULL; }
    PCCERT_CONTEXT c = NULL, bulunan = NULL;
    while ((c = CertEnumCertificatesInStore(depo, c)) != NULL) {
        DWORD boy = 0;
        if (CertGetCertificateContextProperty(c, CERT_KEY_PROV_INFO_PROP_ID, NULL, &boy) ||
            CertGetCertificateContextProperty(c, CERT_NCRYPT_KEY_HANDLE_PROP_ID, NULL, &boy) ||
            CertGetCertificateContextProperty(c, CERT_KEY_CONTEXT_PROP_ID, NULL, &boy)) {
            bulunan = CertDuplicateCertificateContext(c);
            DWORD b2 = 0;
            CertGetCertificateContextProperty(c, CERT_KEY_PROV_INFO_PROP_ID, NULL, &b2);
            CRYPT_KEY_PROV_INFO *bilgi = b2 ? malloc(b2) : NULL;
            if (bilgi && CertGetCertificateContextProperty(c, CERT_KEY_PROV_INFO_PROP_ID, bilgi, &b2) && bilgi->pwszContainerName)
                anahtari_sonra_sil(bilgi->pwszContainerName);
            free(bilgi);
            CertFreeCertificateContext(c);
            break;
        }
    }
    if (!bulunan) http_son_hata = MESAJ("sertifika dosyasında gizli anahtarlı bir sertifika yok", "the certificate file has no certificate with a private key");
    return bulunan;
}

/* Deneme için: localhost adına, 1 yıllık, kendi kendine imzalı sertifika (tarayıcılar "güvenilmez" der) */
static PCCERT_CONTEXT deneme_sertifikasi(void) {
    NCRYPT_PROV_HANDLE saglayici = 0;
    NCRYPT_KEY_HANDLE anahtar = 0;
    if (NCryptOpenStorageProvider(&saglayici, MS_KEY_STORAGE_PROVIDER, 0) != ERROR_SUCCESS) return NULL;
    wchar_t ad[64];
    _snwprintf(ad, 64, L"Vash-deneme-%lu", (unsigned long)GetCurrentProcessId());
    if (NCryptCreatePersistedKey(saglayici, &anahtar, BCRYPT_RSA_ALGORITHM, ad, 0, NCRYPT_OVERWRITE_KEY_FLAG) != ERROR_SUCCESS) {
        NCryptFreeObject(saglayici);
        return NULL;
    }
    DWORD uzunluk = 2048;
    NCryptSetProperty(anahtar, NCRYPT_LENGTH_PROPERTY, (PBYTE)&uzunluk, sizeof uzunluk, 0);
    if (NCryptFinalizeKey(anahtar, 0) != ERROR_SUCCESS) { NCryptFreeObject(anahtar); NCryptFreeObject(saglayici); return NULL; }
    BYTE ad_bayt[256];
    DWORD ad_boy = sizeof ad_bayt;
    CertStrToNameW(X509_ASN_ENCODING, L"CN=localhost", CERT_X500_NAME_STR, NULL, ad_bayt, &ad_boy, NULL);
    CERT_NAME_BLOB konu = { ad_boy, ad_bayt };
    CRYPT_KEY_PROV_INFO bilgi;
    memset(&bilgi, 0, sizeof bilgi);
    bilgi.pwszContainerName = ad;
    bilgi.pwszProvName = (LPWSTR)MS_KEY_STORAGE_PROVIDER;
    bilgi.dwKeySpec = 0;
    CRYPT_ALGORITHM_IDENTIFIER imza = { (LPSTR)szOID_RSA_SHA256RSA, { 0, NULL } };
    SYSTEMTIME bitis;
    GetSystemTime(&bitis);
    bitis.wYear += 1;
    PCCERT_CONTEXT c = CertCreateSelfSignCertificate(anahtar, &konu, 0, &bilgi, &imza, NULL, &bitis, NULL);
    NCryptFreeObject(anahtar);
    NCryptFreeObject(saglayici);
    return c;
}


static int sunucu_sadece_yerel = 0;   /* 1: sadece bu bilgisayardan bağlanılabilir */

static int64_t sunucu_kur(int64_t port, int tls, const char *sertifika, const char *parola) {
    http_kilit_hazirla();
    http_son_hata = "";
    WSADATA w;
    if (WSAStartup(MAKEWORD(2, 2), &w) != 0) { http_son_hata = MESAJ("ağ başlatılamadı", "could not start the network"); return 0; }
    CredHandle kimlik;
    memset(&kimlik, 0, sizeof kimlik);
    if (tls) {
        PCCERT_CONTEXT c;
        if (sertifika[0]) {
            c = pfx_sertifikasi(sertifika, parola);
        } else {
            c = deneme_sertifikasi();
            if (c) {
                wchar_t ad[64];
                _snwprintf(ad, 64, L"Vash-deneme-%lu", (unsigned long)GetCurrentProcessId());
                anahtari_sonra_sil(ad);
            } else {
                http_son_hata = MESAJ("deneme sertifikası üretilemedi", "could not create a test certificate");
            }
        }
        if (!c) return 0;
        SCHANNEL_CRED sc;
        memset(&sc, 0, sizeof sc);
        sc.dwVersion = SCHANNEL_CRED_VERSION;
        sc.cCreds = 1;
        sc.paCred = &c;
        SECURITY_STATUS d = AcquireCredentialsHandleW(NULL, (LPWSTR)UNISP_NAME_W, SECPKG_CRED_INBOUND, NULL, &sc, NULL, NULL, &kimlik, NULL);
        CertFreeCertificateContext(c);
        if (d != SEC_E_OK) { http_son_hata = MESAJ("sertifika HTTPS için kullanılamadı", "the certificate could not be used for HTTPS"); return 0; }
    }
    SOCKET dn = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (dn == INVALID_SOCKET) { http_son_hata = MESAJ("soket açılamadı", "could not open a socket"); return 0; }
    struct sockaddr_in a;
    memset(&a, 0, sizeof a);
    a.sin_family = AF_INET;
    a.sin_addr.s_addr = htonl(sunucu_sadece_yerel ? INADDR_LOOPBACK : INADDR_ANY);
    a.sin_port = htons((u_short)port);
    if (bind(dn, (struct sockaddr *)&a, sizeof a) != 0 || listen(dn, SOMAXCONN_HINT(4096)) != 0) {
        closesocket(dn);
        if (tls) FreeCredentialsHandle(&kimlik);
        http_son_hata = MESAJ("bu port kullanılamıyor (başka bir program kullanıyor olabilir)", "this port cannot be used (another program may be using it)");
        return 0;
    }
    HttpSunucu *s = calloc(1, sizeof *s);
    if (!s) hafiza_doldu();
    s->dinleyen = dn;
    s->tls = tls;
    s->kimlik = kimlik;
    InitializeCriticalSection(&s->kilit);
    InitializeConditionVariable(&s->geldi);
    int64_t no = 0;
    EnterCriticalSection(&http_kilidi);
    for (int i = 1; i < 64; i++) if (!sunucular[i]) { sunucular[i] = s; no = i; break; }
    LeaveCriticalSection(&http_kilidi);
    if (!no) { closesocket(dn); free(s); http_son_hata = MESAJ("çok fazla sunucu", "too many servers"); return 0; }
    HANDLE h = CreateThread(NULL, 0, kabul_dongusu, s, 0, NULL);
    if (h) CloseHandle(h);
    return no;
}

/* port'u dinlemeye başla; olmazsa 0 */
int64_t vash_sunucu_ac(int64_t port) { return sunucu_kur(port, 0, "", ""); }

/* sadece bu bilgisayardan (127.0.0.1) bağlanılabilen sunucu */
int64_t vash_yerel_sunucu_ac(int64_t port) {
    sunucu_sadece_yerel = 1;
    int64_t no = sunucu_kur(port, 0, "", "");
    sunucu_sadece_yerel = 0;
    return no;
}

/* HTTPS: sertifika "" ise deneme sertifikası üretilir */
int64_t vash_guvenli_sunucu_ac(int64_t port, const char *sertifika, const char *parola) {
    return sunucu_kur(port, 1, sertifika, parola);
}

/* Sıradaki isteği bekle (ms < 0: sonsuza kadar). Gelmezse 0, gelirse isteğin numarası. */
int64_t vash_sunucu_bekle(int64_t sno, int64_t ms) {
    HttpSunucu *s = (sno > 0 && sno < 64) ? sunucular[sno] : NULL;
    if (!s) return 0;
    EnterCriticalSection(&s->kilit);
    while (!s->ilk) {
        if (!SleepConditionVariableCS(&s->geldi, &s->kilit, ms < 0 ? INFINITE : (DWORD)ms)) break;
    }
    HttpIstek *r = s->ilk;
    if (r) { s->ilk = r->sonraki; if (!s->ilk) s->son = NULL; }
    LeaveCriticalSection(&s->kilit);
    if (!r) return 0;
    int64_t no = 0;
    EnterCriticalSection(&http_kilidi);
    for (int64_t i = 0; i < 65535 && !no; i++) {
        istek_sirasi = istek_sirasi % 65535 + 1;
        if (!istekler[istek_sirasi]) { istekler[istek_sirasi] = r; no = istek_sirasi; }
    }
    LeaveCriticalSection(&http_kilidi);
    if (!no) { baglanti_kapat(r->b); istek_sil(r); }
    return no;
}

static HttpIstek *istek_bul(int64_t no) { return (no > 0 && no < 65536) ? istekler[no] : NULL; }
const char *vash_istek_yontem(int64_t no) { HttpIstek *r = istek_bul(no); return r ? r->yontem : ""; }
const char *vash_istek_yol(int64_t no) { HttpIstek *r = istek_bul(no); return r ? r->yol : ""; }
const char *vash_istek_sorgu(int64_t no) { HttpIstek *r = istek_bul(no); return r ? r->sorgu : ""; }
const char *vash_istek_basliklar(int64_t no) { HttpIstek *r = istek_bul(no); return r ? r->basliklar : ""; }
const char *vash_istek_govde(int64_t no) { HttpIstek *r = istek_bul(no); return r ? r->govde.p : ""; }

static const char *durum_adi(int64_t d) {
    switch (d) {
        case 200: return "OK"; case 201: return "Created"; case 204: return "No Content";
        case 301: return "Moved Permanently"; case 302: return "Found"; case 304: return "Not Modified";
        case 400: return "Bad Request"; case 401: return "Unauthorized"; case 403: return "Forbidden";
        case 404: return "Not Found"; case 405: return "Method Not Allowed"; case 409: return "Conflict";
        case 422: return "Unprocessable Entity"; case 500: return "Internal Server Error"; case 503: return "Service Unavailable";
        default: return "Status";
    }
}

/* Cevabı gönder. Bağlantı açık kalacaksa yeni bir okuyucu aynı bağlantıdan sıradaki isteği bekler.
 * Bu istek zaten cevaplandıysa bir şey yapmaz (0 döner). */
int32_t vash_istek_cevapla(int64_t no, int64_t durum, const char *govde, const char *basliklar) {
    http_kilit_hazirla();
    EnterCriticalSection(&http_kilidi);
    HttpIstek *r = istek_bul(no);
    if (r) istekler[no] = NULL;
    LeaveCriticalSection(&http_kilidi);
    if (!r) return 0;
    HttpSunucu *s = r->sunucu;
    int kalici = r->kalici && !s->kapali;
    size_t n = strlen(govde);
    Tampon t = {0};
    char bas[256];
    snprintf(bas, sizeof bas, "HTTP/1.1 %lld %s\r\nContent-Length: %llu\r\nConnection: %s\r\n",
             (long long)durum, durum_adi(durum), (unsigned long long)n, kalici ? "keep-alive" : "close");
    tampon_ekle(&t, bas, strlen(bas));
    tampon_ekle(&t, basliklar, strlen(basliklar));
    tampon_ekle(&t, "\r\n", 2);
    tampon_ekle(&t, govde, n);
    int tamam = bag_yaz(r->b, t.p, t.n);
    free(t.p);
    Baglanti *b = r->b;
    istek_sil(r);
    if (tamam && kalici) {
        okuyucu_baslat(s, b, 0);                     /* aynı bağlantıdan sıradaki istek */
    } else {
        shutdown(b->k, SD_SEND);
        baglanti_kapat(b);
    }
    return tamam;
}

void vash_sunucu_kapat(int64_t sno) {
    HttpSunucu *s = (sno > 0 && sno < 64) ? sunucular[sno] : NULL;
    if (!s) return;
    s->kapali = 1;
    closesocket(s->dinleyen);
}
/* ====================================================================
 *  start / wait: arka planda iş
 *  var gorev = start indir(url)  → işin numarası (iş hemen ayrı bir iş parçacığında başlar)
 *  var sonuc = gorev.wait()      → bitmesini bekle, sonucu al (her iş bir kez beklenir)
 *  Derleyici, başlatılan fonksiyonun dışarıdaki değişkenlere dokunmadığını önceden kontrol eder.
 *  İş çalışırken sayaçlar bölünmez işlemlerle değişir (paralel_aktif); iş kendi rafları ve arenasıyla çalışır.
 * ==================================================================== */
typedef void (*VashGorevIsi)(void *veri, int64_t *sonuc);
typedef struct {
    VashGorevIsi is;
    void *veri;
    int64_t sonuc;
    HANDLE ip;
    uint64_t tohum;
} Gorev;

#define GOREV_EN_FAZLA 65536
static Gorev *gorevler[GOREV_EN_FAZLA];
static int64_t gorev_sirasi = 0;
static CRITICAL_SECTION gorev_kilidi;
static volatile LONG gorev_kilidi_hazir = 0;

static DWORD WINAPI gorev_calistir(LPVOID p) {
    Gorev *g = p;
    arka_plan_isi = 1;
    rastgele_durum = g->tohum;
    g->is(g->veri, &g->sonuc);
    InterlockedDecrement(&paralel_aktif);           /* bu iş bitti: (başka iş yoksa) sayaçlar yine düz yoldan */
    return 0;
}

int64_t gorev_baslat(VashGorevIsi is, void *veri) {
    if (InterlockedCompareExchange(&gorev_kilidi_hazir, 1, 0) == 0) InitializeCriticalSection(&gorev_kilidi);
    Gorev *g = calloc(1, sizeof *g);
    if (!g) hafiza_doldu();
    g->is = is;
    g->veri = veri;
    g->tohum = rastgele_64();
    int64_t no = 0;
    EnterCriticalSection(&gorev_kilidi);
    for (int64_t i = 0; i < GOREV_EN_FAZLA - 1 && !no; i++) {
        gorev_sirasi = gorev_sirasi % (GOREV_EN_FAZLA - 1) + 1;
        if (!gorevler[gorev_sirasi]) { gorevler[gorev_sirasi] = g; no = gorev_sirasi; }
    }
    LeaveCriticalSection(&gorev_kilidi);
    if (!no) {
        fflush(stdout);
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI: Aynı anda çok fazla arka plan işi var (beklenmemiş %d iş).\n", "\nRUNTIME ERROR: Too many background tasks at the same time (%d tasks not yet waited for).\n"), GOREV_EN_FAZLA - 1);
        exit(1);
    }
    InterlockedIncrement(&paralel_aktif);           /* iş başlamadan önce: sayaçlar artık bölünmez işlemlerle */
    g->ip = CreateThread(NULL, 64 * 1024 * 1024, gorev_calistir, g, STACK_SIZE_PARAM_IS_A_RESERVATION, NULL);
    if (!g->ip) {
        fflush(stdout);
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI: Arka plan işi başlatılamadı.\n", "\nRUNTIME ERROR: Could not start the background task.\n"));
        exit(1);
    }
    return no;
}

/* İşin bitmesini bekle, sonucunu (sahipliğiyle) döndür */
int64_t gorev_bekle(int64_t no, int64_t satir) {
    Gorev *g = NULL;
    if (gorev_kilidi_hazir) {
        EnterCriticalSection(&gorev_kilidi);
        if (no > 0 && no < GOREV_EN_FAZLA) { g = gorevler[no]; gorevler[no] = NULL; }
        LeaveCriticalSection(&gorev_kilidi);
    }
    if (!g) {
        fflush(stdout);
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): Bu iş zaten beklenmiş; her iş bir kez beklenir (wait).\n", "\nRUNTIME ERROR (line %lld): This task was already waited for; each task can be waited for only once (wait).\n"), (long long)satir);
        exit(1);
    }
    WaitForSingleObject(g->ip, INFINITE);
    CloseHandle(g->ip);
    int64_t s = g->sonuc;
    free(g);
    return s;
}

/* İş bitti mi? (beklemeden bakmak için) */
int32_t gorev_bitti_mi(int64_t no) {
    Gorev *g = NULL;
    if (gorev_kilidi_hazir) {
        EnterCriticalSection(&gorev_kilidi);
        if (no > 0 && no < GOREV_EN_FAZLA) g = gorevler[no];
        if (g && WaitForSingleObject(g->ip, 0) != WAIT_OBJECT_0) g = (Gorev *)1;
        else g = NULL;
        LeaveCriticalSection(&gorev_kilidi);
    }
    return g == NULL;
}

/* ====================================================================
 *  channel: işler arasında mesajlaşma
 *  var kanal = channel[text]()  ·  kanal.send(x)  ·  kanal.receive() (gelene kadar bekler)  ·  kanal.close()
 *  Mesajlar değer olarak gider (kopya gibi davranır); sıra korunur. Kanal numarayla tutulur (i64).
 * ==================================================================== */
typedef struct {
    int64_t *veri;                  /* halka biçiminde sıra */
    int64_t bas, n, kap;
    int64_t tur;                    /* mesajların türü (T_INT ...) */
    int kapali;
    CRITICAL_SECTION kilit;
    CONDITION_VARIABLE geldi;
} Kanal;

#define KANAL_EN_FAZLA 65536
static Kanal *kanallar[KANAL_EN_FAZLA];
static int64_t kanal_sayisi = 0;
static CRITICAL_SECTION kanal_kilidi;
static volatile LONG kanal_kilidi_hazir = 0;

int64_t kanal_yeni(int64_t tur) {
    if (InterlockedCompareExchange(&kanal_kilidi_hazir, 1, 0) == 0) InitializeCriticalSection(&kanal_kilidi);
    Kanal *k = calloc(1, sizeof *k);
    if (!k) hafiza_doldu();
    k->tur = tur;
    InitializeCriticalSection(&k->kilit);
    InitializeConditionVariable(&k->geldi);
    EnterCriticalSection(&kanal_kilidi);
    int64_t no = ++kanal_sayisi;
    if (no < KANAL_EN_FAZLA) kanallar[no] = k;
    LeaveCriticalSection(&kanal_kilidi);
    if (no >= KANAL_EN_FAZLA) {
        fflush(stdout);
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI: Çok fazla kanal oluşturuldu (en fazla %d).\n", "\nRUNTIME ERROR: Too many channels were created (at most %d).\n"), KANAL_EN_FAZLA - 1);
        exit(1);
    }
    return no;
}

static Kanal *kanal_bul(int64_t no) { return (no > 0 && no < KANAL_EN_FAZLA) ? kanallar[no] : NULL; }

/* Mesajı kanala koy (sahipliği kanala geçer) */
void kanal_gonder(int64_t no, int64_t kutu, int64_t satir) {
    Kanal *k = kanal_bul(no);
    if (!k) return;
    kutu = kacir(k->tur, kutu);                     /* arenadaysa normal belleğe: alan kişi arenayı görmez */
    EnterCriticalSection(&k->kilit);
    if (k->kapali) {
        LeaveCriticalSection(&k->kilit);
        fflush(stdout);
        fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): Kapatılmış bir kanala mesaj gönderilemez (send, close'dan sonra).\n", "\nRUNTIME ERROR (line %lld): Cannot send a message to a closed channel (send after close).\n"), (long long)satir);
        exit(1);
    }
    if (k->n == k->kap) {                           /* yer kalmadı: 2 katına büyüt, sırayı düzelt */
        int64_t yeni = k->kap ? k->kap * 2 : 16;
        int64_t *v = malloc(sizeof(int64_t) * (size_t)yeni);
        if (!v) hafiza_doldu();
        for (int64_t i = 0; i < k->n; i++) v[i] = k->veri[(k->bas + i) % k->kap];
        free(k->veri);
        k->veri = v;
        k->kap = yeni;
        k->bas = 0;
    }
    k->veri[(k->bas + k->n) % k->kap] = kutu;
    k->n++;
    LeaveCriticalSection(&k->kilit);
    WakeConditionVariable(&k->geldi);
}

/* Sıradaki mesajı al. bekle: gelene kadar bekle. Mesaj varsa 1 (sonuc'a yazılır, sahipliğiyle);
 * kanal kapanmış ve boşsa (ya da beklemeden bakıldı ve boşsa) 0 ve sonuc = 0 */
int32_t kanal_al(int64_t no, int32_t bekle, int64_t *sonuc) {
    *sonuc = 0;
    Kanal *k = kanal_bul(no);
    if (!k) return 0;
    EnterCriticalSection(&k->kilit);
    while (bekle && k->n == 0 && !k->kapali) SleepConditionVariableCS(&k->geldi, &k->kilit, INFINITE);
    int32_t var = k->n > 0;
    if (var) {
        *sonuc = k->veri[k->bas];
        k->bas = (k->bas + 1) % k->kap;
        k->n--;
    }
    LeaveCriticalSection(&k->kilit);
    return var;
}

/* Kanalı kapat: bekleyenler uyanır; kalan mesajlar yine okunabilir, sonra receive() none döner */
void kanal_kapat(int64_t no) {
    Kanal *k = kanal_bul(no);
    if (!k) return;
    EnterCriticalSection(&k->kilit);
    k->kapali = 1;
    LeaveCriticalSection(&k->kilit);
    WakeAllConditionVariable(&k->geldi);
}

/* ====================================================================
 *  Hatalar: fail / try / do-catch
 *  fail "mesaj" → hata bu iş parçacığına özel yerde bekler; çağıran try / else: / catch ile alır.
 * ==================================================================== */
static _Thread_local char *bekleyen_hata = NULL;

/* Hatayı koy (mesajın sahipliğini alır) */
void hata_koy(char *m) {
    if (bekleyen_hata) birak(bekleyen_hata);
    bekleyen_hata = m;
}

/* Bekleyen hatayı al ve temizle (sahipliği verir); hata yoksa NULL */
char *hata_al(void) {
    char *m = bekleyen_hata;
    bekleyen_hata = NULL;
    return m;
}

/* Ana programda yakalanmayan hata: programı anlaşılır bir mesajla durdur */
void hata_yakalanmadi(char *m, int64_t satir) {
    fflush(stdout);
    fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): Yakalanmayan hata: %s\n", "\nRUNTIME ERROR (line %lld): Uncaught error: %s\n"),
            (long long)satir, m ? m : "");
    exit(1);
}

/* ====================================================================
 *  Lambda / fonksiyon değeri ("kapanış"): kodun adresi + yakalanan değerlerin kopyaları
 *  { sayaç, fonksiyon, n, [tür, değer] x n }   — kod: fonksiyon(kapanis, değerler...)
 * ==================================================================== */
struct Kapanis {
    int64_t sayac;
    void *fn;
    int64_t n;
    int64_t d[];                    /* çiftler: tür, değer */
};

Kapanis *kapanis_yeni(void *fn, int64_t n) {
    Kapanis *k = malloc(sizeof(Kapanis) + sizeof(int64_t) * 2 * (size_t)n);
    if (!k) hafiza_doldu();
    k->sayac = 1;
    k->fn = fn;
    k->n = n;
    memset(k->d, 0, sizeof(int64_t) * 2 * (size_t)n);
    SAYAC_ARTIR(toplam_ayrilan);
    SAYAC_ARTIR(canli);
    return k;
}

/* i. yakalanan değeri koy (sahipliği kapanışa geçer) */
void kapanis_koy(Kapanis *k, int64_t i, int64_t tur, int64_t v) {
    k->d[2 * i] = tur;
    k->d[2 * i + 1] = v;
}

int64_t kapanis_al(Kapanis *k, int64_t i) { return k->d[2 * i + 1]; }

void kapanis_tut(Kapanis *k) { if (k) SAYAC_ARTIR(k->sayac); }

void kapanis_birak(Kapanis *k) {
    if (k && sayac_azalt(&k->sayac) == 0) {
        for (int64_t i = 0; i < k->n; i++) eleman_birak(k->d[2 * i], k->d[2 * i + 1]);
        free(k);
        sayac_azalt(&canli);
    }
}

/* liste.sort(by: kapanış): karşılaştırma bir kapanışla yapılır (iç içe sıralamaya karşı önceki hâli saklanır) */
typedef int32_t (*OnceK)(void *k, int64_t a, int64_t b);
static _Thread_local OnceK sirala_k_fn = NULL;
static _Thread_local void *sirala_k_kapanis = NULL;
static int32_t once_kapanis(int64_t a, int64_t b) { return sirala_k_fn(sirala_k_kapanis, a, b); }
void liste_sirala_k(Liste *l, OnceK f, void *k) {
    OnceK onceki_f = sirala_k_fn;
    void *onceki_k = sirala_k_kapanis;
    sirala_k_fn = f;
    sirala_k_kapanis = k;
    liste_sirala(l, once_kapanis);
    sirala_k_fn = onceki_f;
    sirala_k_kapanis = onceki_k;
}

/* a << n / a >> n: n 0..63 arasında olmalı */
void hata_kaydirma(int64_t n, int64_t satir) {
    fflush(stdout);
    fprintf(stderr, MESAJ("\nÇALIŞMA HATASI (satır %lld): Kaydırma miktarı 0 ile 63 arasında olmalı, burada %lld var.\n",
                          "\nRUNTIME ERROR (line %lld): The shift amount must be between 0 and 63, but here it is %lld.\n"),
            (long long)satir, (long long)n);
    exit(1);
}
