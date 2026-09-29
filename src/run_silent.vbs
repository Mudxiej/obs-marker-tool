Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir

' Single-instance guard: exit if 127.0.0.1:8765 already answers.
Function ServerAlreadyRunning()
    On Error Resume Next
    Dim http
    Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
    If Err.Number <> 0 Then
        Err.Clear
        ServerAlreadyRunning = False
        Exit Function
    End If
    http.SetTimeouts 500, 500, 500, 1000
    http.Open "GET", "http://127.0.0.1:8765/api/status", False
    http.Send
    If Err.Number = 0 And http.Status = 200 Then
        ServerAlreadyRunning = True
    Else
        ServerAlreadyRunning = False
    End If
    Set http = Nothing
    Err.Clear
End Function

If ServerAlreadyRunning() Then
    Set fso = Nothing
    Set WshShell = Nothing
    WScript.Quit 0
End If

' Portable pythonw discovery (no hardcoded username):
' 1. %LOCALAPPDATA%\Programs\Python\Python3*\pythonw.exe (newest first)
' 2. pythonw.exe on PATH
' 3. py.exe launcher (py -3 -W)
Function FindPythonW()
    Dim localApp, folder, sub, best, bestNum, cur, re
    localApp = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\"
    best = ""
    bestNum = 0
    If fso.FolderExists(localApp) Then
        For Each folder In fso.GetFolder(localApp).SubFolders
            cur = 0
            ' Folder names look like Python314, Python313, ...
            If Left(folder.Name, 6) = "Python" Then
                On Error Resume Next
                cur = CInt(Mid(folder.Name, 7, 2)) * 100 + CInt(Mid(folder.Name, 9, 2))
                If Err.Number <> 0 Then cur = 0
                Err.Clear
                On Error GoTo 0
                If cur > bestNum And fso.FileExists(folder.Path & "\pythonw.exe") Then
                    bestNum = cur
                    best = folder.Path & "\pythonw.exe"
                End If
            End If
        Next
    End If
    If best <> "" Then
        FindPythonW = """" & best & """"
        Exit Function
    End If
    ' PATH fallback: let WScript resolve pythonw.exe
    FindPythonW = "pythonw"
End Function

pythonCmd = FindPythonW()
' Use py launcher as last resort if pythonw is missing from PATH.
If LCase(pythonCmd) = "pythonw" Then
    Dim sh, rc
    On Error Resume Next
    rc = WshShell.Run("cmd /c where pythonw > NUL 2>&1", 0, True)
    If rc <> 0 Then
        ' Try: py -3 -W <script> (py launcher ships with python.org installers)
        WshShell.Run "py -3 -W """ & scriptDir & "\server.py""", 0, False
        Set fso = Nothing
        Set WshShell = Nothing
        WScript.Quit 0
    End If
    On Error GoTo 0
End If

WshShell.Run pythonCmd & " """ & scriptDir & "\server.py""", 0, False

Set fso = Nothing
Set WshShell = Nothing
