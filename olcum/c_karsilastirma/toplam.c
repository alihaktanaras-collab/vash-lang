#include <stdio.h>
int main(void) {
    long long t = 0;
    for (long long i = 1; i <= 2000000000LL; i++) t += (i * 7) % 13;
    printf("%lld\n", t);
    return 0;
}
