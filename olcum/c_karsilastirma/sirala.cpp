#include <algorithm>
#include <cstdio>
#include <vector>
int main() {
    long long n = 5000000, x = 12345, s = 0;
    std::vector<long long> l(n);
    for (long long i = 0; i < n; i++) { x = (x * 1103515245 + 12345) % 2147483648LL; l[i] = x; }
    std::sort(l.begin(), l.end());
    for (long long i = 0; i < n; i += 1000) s += l[i] % 1000;
    std::printf("%lld\n", s);
}
