# Vash, C ve C++ hız karşılaştırması: hepsini derler, her programı 5 kez çalıştırıp en kısa süreyi yazar.
#   powershell -File olc.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$vash = Join-Path $PSScriptRoot '..\..\vash.cmd'
$programlar = 'mandel', 'sirala', 'toplam', 'asal', 'toplam_paralel'
foreach ($p in $programlar) {
    & $vash build "$p.vash" | Out-Null
    if (Test-Path "$p.c") { clang -O2 "$p.c" -o "${p}_c.exe" 2>$null }
    if (Test-Path "$p.cpp") { clang++ -O2 -std=c++17 "$p.cpp" -o "${p}_cpp.exe" 2>$null }
}
function En-Kisa($exe) {
    $en = [double]::MaxValue
    $cikti = ''
    for ($i = 0; $i -lt 5; $i++) {
        $s = [System.Diagnostics.Stopwatch]::StartNew()
        $cikti = (& $exe | Out-String).Trim()
        $s.Stop()
        if ($s.Elapsed.TotalSeconds -lt $en) { $en = $s.Elapsed.TotalSeconds }
    }
    return @([math]::Round($en, 2), $cikti)
}
foreach ($p in $programlar) {
    $v = En-Kisa ".\$p.exe"
    $c = if (Test-Path "${p}_c.exe") { En-Kisa ".\${p}_c.exe" } else { @('-', '') }
    $cp = if (Test-Path "${p}_cpp.exe") { En-Kisa ".\${p}_cpp.exe" } else { @('-', '') }
    "{0,-16} Vash {1,6} sn   C {2,6} sn   C++ {3,6} sn   sonuç: {4} / {5} / {6}" -f $p, $v[0], $c[0], $cp[0], $v[1], $c[1], $cp[1]
}
