param(
    [string]$InputPath = 'D:\NexentFile\赛题3申请表.docx',
    [string]$OutputPath = 'D:\NexentFile\outputs\apply_form\filled.pdf'
)

$ErrorActionPreference = 'Stop'
$formWord = New-Object -ComObject Word.Application
$formWord.Visible = $false
$formWord.DisplayAlerts = 0
try {
    $formDocument = $formWord.Documents.Open($InputPath, $false, $true)
    $formDocument.Repaginate()
    Write-Output ('Pages=' + $formDocument.ComputeStatistics(2))
    $formDocument.ExportAsFixedFormat($OutputPath, 17)
    $formDocument.Close(0)
} finally {
    $formWord.Quit()
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($formWord) | Out-Null
}
