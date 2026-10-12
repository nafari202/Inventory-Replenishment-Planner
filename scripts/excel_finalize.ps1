# Open the workbook in Excel, recalculate every formula, and save, so the file opens with values filled in
# (openpyxl writes formulas but cannot calculate them). Run after run_pipeline.py.
param([string]$Path = (Join-Path $PSScriptRoot "..\outputs\Inventory_Replenishment_Planner.xlsx"))
$full = (Resolve-Path $Path).Path
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
try {
    $wb = $xl.Workbooks.Open($full)
    $xl.CalculateFull()
    $wb.Worksheets.Item(1).Activate()
    $wb.Save()
    $wb.Close($false)
    Write-Output "Recalculated and saved $full"
} finally {
    $xl.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
}
