#include <cstdio>
#include <vector>
int main() {
    long long n = 50000000, sayi = 0;
    std::vector<bool> bilesik(n + 2, false);
    for (long long i = 2; i <= n; i++) {
        if (!bilesik[i]) {
            sayi++;
            for (long long j = i * i; j <= n; j += i) bilesik[j] = true;
        }
    }
    std::printf("%lld\n", sayi);
}
