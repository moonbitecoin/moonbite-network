Set oWS = WScript.CreateObject("WScript.Shell")
strDesktop = oWS.SpecialFolders("Desktop")

Set oLink = oWS.CreateShortcut(strDesktop & "\MoonBite GUI.lnk")
oLink.TargetPath = "C:\Users\usman\Desktop\MoonBite\LAUNCH_GUI.bat"
oLink.WorkingDirectory = "C:\Users\usman\Desktop\MoonBite"
oLink.Description = "MoonBite Desktop GUI - Click to launch"
oLink.IconLocation = "C:\Windows\System32\cmd.exe,0"
oLink.Save

MsgBox "Shortcut created: MoonBite GUI.lnk on Desktop", 0, "Success"
