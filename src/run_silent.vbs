Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir

pythonPath = "C:\Users\mudxiej\AppData\Local\Programs\Python\Python314\pythonw.exe"
If fso.FileExists(pythonPath) Then
    WshShell.Run """" & pythonPath & """ """ & scriptDir & "\server.py""", 0, False
Else
    WshShell.Run "pythonw """ & scriptDir & "\server.py""", 0, False
End If

Set fso = Nothing
Set WshShell = Nothing
