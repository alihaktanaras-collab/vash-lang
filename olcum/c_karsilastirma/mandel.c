#include <stdio.h>
int main(void) {
    long long boy = 2000, icerde = 0;
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
    printf("%lld\n", icerde);
    return 0;
}
