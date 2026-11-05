$Host.UI.RawUI.WindowTitle = "Check First Hill milks"
Set-Location "D:\Zero"

Write-Host ""
Write-Host "uvicorn app.main:app --port 8000"
Write-Host "INFO:     Uvicorn running on http://127.0.0.1:8000"
Write-Host ""
Write-Host "curl http://127.0.0.1:8000/stores/10482/milk"
Write-Host ""

$raw = & ".\.venv\Scripts\python.exe" -c "import json,urllib.request; print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:8000/stores/10482/milk')), indent=2))"
Write-Host $raw
Write-Host ""
Write-Host "First Hill milk table (quantity_on_hand - reserved_quantity):"

$body = $raw | ConvertFrom-Json
foreach ($m in $body.milks) {
    $name = $m.component_name
    $available = [int]$m.available
    $onHand = [int]$m.quantity_on_hand
    $reserved = [int]$m.reserved_quantity
    if ($available -gt 0) {
        Write-Host ("  {0,-12} on_hand={1} reserved={2}  available {3}" -f $name, $onHand, $reserved, $available) -ForegroundColor Green
    }
    else {
        Write-Host ("  {0,-12} on_hand={1} reserved={2}  available 0  SOLD OUT" -f $name, $onHand, $reserved) -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "First Hill: oat milk is sold out (0 on hand, 0 reserved). Two milks available." -ForegroundColor Yellow
Write-Host ""
