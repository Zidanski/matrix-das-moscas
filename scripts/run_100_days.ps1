# Roda os 100 dias (50 normais + 50 com Fil em modo controle) de forma destacada, com log.
# Os dois lotes correm em paralelo (12 processos); FIM so e escrito quando os dois terminam.
Set-Location C:\meuMundoNovo
$a = Start-Process -FilePath "uv" -ArgumentList "run matrix simulate --days 50 --start 100 --seconds 60 --brain reduced --out runs/cem" -NoNewWindow -PassThru -RedirectStandardOutput runs/cem/log_normal.txt -RedirectStandardError runs/cem/err_normal.txt
$b = Start-Process -FilePath "uv" -ArgumentList "run matrix simulate --days 50 --start 150 --seconds 60 --brain reduced --control Fil --out runs/cem" -NoNewWindow -PassThru -RedirectStandardOutput runs/cem/log_controle.txt -RedirectStandardError runs/cem/err_controle.txt
Wait-Process -Id $a.Id, $b.Id
"FIM $(Get-Date)" | Out-File -Append -Encoding utf8 runs/cem/log.txt
