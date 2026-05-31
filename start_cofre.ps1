param(
  [int]$Port = 5000,
  [string]$DbPath = "$PSScriptRoot\cofre.db"
)

$env:PORT = "$Port"
$env:COFRE_DB_PATH = $DbPath
python "$PSScriptRoot\server.py"
