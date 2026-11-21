#include <stdio.h>
#include <stdlib.h>
static int kars(const void *a, const void *b) {
    long long x = *(const long long *)a, y = *(const long long *)b;
    return (x > y) - (x < y);
}
int main(void) {
    long long n = 5000000, x = 12345, s = 0;
    long long *l = malloc(sizeof(long long) * n);
    for (long long i = 0; i < n; i++) { x = (x * 1103515245 + 12345) % 2147483648LL; l[i] = x; }
    qsort(l, n, sizeof(long long), kars);
    for (long long i = 0; i < n; i += 1000) s += l[i] % 1000;
    printf("%lld\n", s);
    return 0;
}
