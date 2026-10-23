' TaCZ 第一人称定位调参器 —— 无窗口启动
' 双击这个文件不会有任何黑框；出错时会弹一个对话框告诉你原因。
Option Explicit
Dim fso, sh, here, py, cand, i, list, args
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")
here = fso.GetParentFolderName(WScript.ScriptFullName)

list = Array( _
  sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python314\pythonw.exe", _
  sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python313\pythonw.exe", _
  sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\pythonw.exe", _
  sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python311\pythonw.exe", _
  sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python310\pythonw.exe", _
  "C:\Python314\pythonw.exe", "C:\Python313\pythonw.exe", "C:\Python312\pythonw.exe", _
  sh.ExpandEnvironmentStrings("%ProgramFiles%") & "\Python314\pythonw.exe", _
  sh.ExpandEnvironmentStrings("%ProgramFiles%") & "\Python313\pythonw.exe", _
  sh.ExpandEnvironmentStrings("%ProgramFiles%") & "\Python312\pythonw.exe")

py = ""
For i = 0 To UBound(list)
  If py = "" Then
    If fso.FileExists(list(i)) Then py = list(i)
  End If
Next

If py = "" Then
  ' 退一步：PATH 里找
  On Error Resume Next
  py = sh.ExpandEnvironmentStrings("%PYTHONW%")
  If py = "%PYTHONW%" Then py = ""
  On Error GoTo 0
End If

If py = "" Then
  MsgBox "没找到 Python。" & vbCrLf & vbCrLf & _
         "装一个 Python 3.8 以上的版本（安装时勾选 Add to PATH），" & vbCrLf & _
         "或者用记事本打开 启动.vbs，把 list 里第一条改成你自己的 pythonw.exe 路径。", _
         vbExclamation, "TaCZ 调参器"
  WScript.Quit 1
End If

sh.CurrentDirectory = here
sh.Run """" & py & """ """ & here & "\gui.py""", 0, False
