Option Explicit

Dim shell, fso, agentDir, pythonw, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

agentDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = agentDir & "\venv\Scripts\pythonw.exe"
If Not fso.FileExists(pythonw) Then
    WScript.Echo "Desktop agent virtual environment is missing. Run setup.bat first."
    WScript.Quit 1
End If

shell.CurrentDirectory = agentDir
command = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & agentDir & "\agent.py" & Chr(34)
shell.Run command, 0, False