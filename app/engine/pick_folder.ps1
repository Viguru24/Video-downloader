param (
    [string]$InitialPath = ""
)

Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "Select OmniDownloader Default Save Folder"
$dialog.ShowNewFolderButton = $true

if ($InitialPath -and (Test-Path $InitialPath)) {
    $dialog.SelectedPath = $InitialPath
}

$form = New-Object System.Windows.Forms.Form
$form.TopMost = $true
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen

$result = $dialog.ShowDialog($form)
if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dialog.SelectedPath
}
