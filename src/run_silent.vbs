Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir

' Single-instance guard: exit if a healthy server already answers.
' Reads port.txt (written by the server on bind), then 8765, so a server
' on a fallback port is still reused instead of launching a second copy.
Function ProbeStatus(portNum)
    On Error Resume Next
    Dim http
    Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
    If Err.Number <> 0 Then
        Err.Clear
        ProbeStatus = False
        Exit Function
    End If
    http.SetTimeouts 300, 300, 300, 500
    http.Open "GET", "http://127.0.0.1:" & CStr(portNum) & "/api/status", False
    http.Send
    If Err.Number = 0 And http.Status = 200 Then
        ProbeStatus = True
    Else
        ProbeStatus = False
    End If
    Set http = Nothing
    Err.Clear
End Function

Function ServerAlreadyRunning()
    ' 1. Bound port from the previous launch, if the file exists.
    Dim portFile, ts, saved
    portFile = scriptDir & "\port.txt"
    If fso.FileExists(portFile) Then
        On Error Resume Next
        Set ts = fso.OpenTextFile(portFile, 1, False)
        If Err.Number = 0 Then
            saved = Trim(ts.ReadAll())
            ts.Close
            If saved <> "" And IsNumeric(saved) Then
                If ProbeStatus(CInt(saved)) Then
                    ServerAlreadyRunning = True
                    Exit Function
                End If
            End If
        End If
        Err.Clear
        On Error GoTo 0
    End If
    ' 2. Default port fast path.
    If ProbeStatus(8765) Then
        ServerAlreadyRunning = True
    Else
        ServerAlreadyRunning = False
    End If
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
    Dim localApp, folder, best, bestNum, cur
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
