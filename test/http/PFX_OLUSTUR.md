# pfx_sunucu.vash için deneme sertifikası

`deneme.pfx` gizli anahtar içerdiği için depoda yok. Denemeden önce bu klasörde PowerShell ile üret:

```powershell
$c = New-SelfSignedCertificate -DnsName localhost -CertStoreLocation Cert:\CurrentUser\My
Export-PfxCertificate -Cert $c -FilePath deneme.pfx -Password (ConvertTo-SecureString gizli123 -AsPlainText -Force)
Remove-Item "Cert:\CurrentUser\My\$($c.Thumbprint)"
```

(The test certificate is not in the repository because it contains a private key; create it with the commands above.)
