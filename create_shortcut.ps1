$WshShell = New-Object -ComObject WScript.Shell
$Desktop = [System.Environment]::GetFolderPath('Desktop')
$TargetVbs = Join-Path $PSScriptRoot "run_silent.vbs"
$IconPath = Join-Path $PSScriptRoot "assets\icon.ico"

$Shortcut = $WshShell.CreateShortcut("$Desktop\Qale.lnk")
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = "`"$TargetVbs`""
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.Description = "Qale - Developer Voice-to-Code Assistant"
$Shortcut.IconLocation = "$IconPath, 0"
$Shortcut.Save()

Write-Host "Qale desktop shortcut created successfully on your Desktop!"

