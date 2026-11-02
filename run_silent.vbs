Set WshShell = CreateObject("WScript.Shell")
Set WshEnv = WshShell.Environment("PROCESS")
Set fso = CreateObject("Scripting.FileSystemObject")

WshEnv("PYTHONUTF8") = "1"
WshEnv("PYTHONIOENCODING") = "utf-8"

strScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strScriptDir

If fso.FileExists("C:\Python313\pythonw.exe") Then
    pythonwExe = "C:\Python313\pythonw.exe"
Else
    pythonwExe = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe")
End If

cmdArgs = ""
For i = 0 To WScript.Arguments.Count - 1
    cmdArgs = cmdArgs & " """ & WScript.Arguments(i) & """"
Next

WshShell.Run """" & pythonwExe & """ """ & strScriptDir & "\main.py""" & cmdArgs, 0, False
