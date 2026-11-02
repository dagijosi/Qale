Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

strDesktop = WshShell.SpecialFolders("Desktop")
strScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

Set oLink = WshShell.CreateShortcut(strDesktop & "\Qale.lnk")
oLink.TargetPath = "wscript.exe"
oLink.Arguments = """" & strScriptDir & "\run_silent.vbs"""
oLink.WorkingDirectory = strScriptDir
oLink.Description = "Qale - Developer Voice-to-Code Assistant"
oLink.IconLocation = strScriptDir & "\assets\icon.ico, 0"
oLink.Save

WScript.Echo "Qale desktop shortcut created successfully on your Desktop!"
