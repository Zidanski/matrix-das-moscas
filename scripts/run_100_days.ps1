# Roda os 100 dias (50 normais + 50 com Fil em modo controle) de forma destacada, com log.
Set-Location C:\meuMundoNovo
uv run matrix simulate --days 50 --start 100 --seconds 60 --brain reduced --out runs/cem *>> runs/cem/log.txt
uv run matrix simulate --days 50 --start 150 --seconds 60 --brain reduced --control Fil --out runs/cem *>> runs/cem/log.txt
"FIM" | Out-File -Append runs/cem/log.txt
