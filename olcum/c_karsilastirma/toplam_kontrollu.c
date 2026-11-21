/* toplam.c ile aynı, ama Vash gibi her toplamada taşma kontrolü var */
#include <stdio.h>
#include <stdlib.h>
int main(void) {
    long long t = 0;
    for (long long i = 1; i <= 2000000000LL; i++) {
        if (__builtin_add_overflow(t, (i * 7) % 13, &t)) { puts("tasma"); exit(1); }
    }
    printf("%lld\n", t);
    return 0;
}
