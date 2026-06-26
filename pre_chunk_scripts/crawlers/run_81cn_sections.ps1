param(
    [int]$MaxPagesPerSection = 1000,
    [int]$MaxDepth = 2,
    [int]$MinChars = 300,
    [double]$Delay = 1.0
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$crawler = Join-Path $PSScriptRoot "crawl_81cn_txt.py"
$sections = @("11", "12", "13", "14", "15")

foreach ($section in $sections) {
    Write-Host "== Crawl 81.cn section $section =="
    python $crawler `
        --section $section `
        --max-pages $MaxPagesPerSection `
        --max-depth $MaxDepth `
        --min-chars $MinChars `
        --delay $Delay
}
