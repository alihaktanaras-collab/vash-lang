#include <cstdio>
#include <complex>
int main() {
    const long long boy = 2000;
    long long icerde = 0;
    for (long long y = 0; y < boy; y++)
        for (long long x = 0; x < boy; x++) {
            double cr = 3.0 * x / boy - 2.0, ci = 2.0 * y / boy - 1.0, zr = 0, zi = 0;
            long long k = 0;
            while (k < 100 && zr * zr + zi * zi <= 4.0) {
                double t = zr * zr - zi * zi + cr;
                zi = 2.0 * zr * zi + ci;
                zr = t;
                k++;
            }
            if (k == 100) icerde++;
        }
    std::printf("%lld\n", icerde);
}
