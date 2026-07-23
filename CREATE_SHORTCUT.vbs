Set oWS = WScript.CreateObject("WScript.Shell")
strDesktop = oWS.SpecialFolders("Desktop")

Set oLink = oWS.CreateShortcut(strDesktop & "\MyCoin GUI.lnk")
oLink.TargetPath = oWS.ExpandEnvironmentStrings("%USERPROFILE%\Desktop\BigCoinBB\LAUNCH_GUI.bat")
oLink.WorkingDirectory = oWS.ExpandEnvironmentStrings("%USERPROFILE%\Desktop\BigCoinBB")
oLink.Description = "MyCoin Desktop GUI - Click to launch"
oLink.IconLocation = "C:\Windows\System32\cmd.exe,0"
oLink.Save

MsgBox "Shortcut created: MyCoin GUI.lnk on Desktop", 0, "Success"
