#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
int main(void) {
    long long n = 50000000;
    long long *bilesik = calloc(n + 2, 8);
    long long sayi = 0;
    for (long long i = 2; i <= n; i++) {
        if (!bilesik[i]) {
            sayi++;
            for (long long j = i * i; j <= n; j += i) bilesik[j] = true;
        }
    }
    printf("%lld\n", sayi);
    return 0;
}
