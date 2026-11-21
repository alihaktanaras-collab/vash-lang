#include <cstdio>
#include <thread>
#include <vector>
int main() {
    const long long n = 2000000000LL;
    unsigned k = std::thread::hardware_concurrency();
    std::vector<long long> parca(k, 0);
    std::vector<std::thread> isler;
    for (unsigned w = 0; w < k; w++)
        isler.emplace_back([&, w] {
            long long bas = 1 + n * w / k, son = n * (w + 1) / k, t = 0;
            for (long long i = bas; i <= son; i++) t += (i * 7) % 13;
            parca[w] = t;
        });
    long long t = 0;
    for (unsigned w = 0; w < k; w++) { isler[w].join(); t += parca[w]; }
    std::printf("%lld\n", t);
}
