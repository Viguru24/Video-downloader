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

$topForm = New-Object System.Windows.Forms.Form
$topForm.TopMost = $true
$topForm.ShowInTaskbar = $false
$topForm.WindowState = [System.Windows.Forms.FormWindowState]::Minimized
$topForm.Show()
$topForm.WindowState = [System.Windows.Forms.FormWindowState]::Normal
$topForm.BringToFront()
$topForm.Focus()

$result = $dialog.ShowDialog($topForm)
$topForm.Close()
$topForm.Dispose()

if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dialog.SelectedPath
}
