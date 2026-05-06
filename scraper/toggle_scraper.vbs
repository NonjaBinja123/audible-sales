Dim fso, flagFile
Set fso = CreateObject("Scripting.FileSystemObject")
flagFile = "C:\Projects\AudibleTool\scraper\scraper.disabled"

If fso.FileExists(flagFile) Then
    fso.DeleteFile flagFile
    MsgBox "Scraper enabled. It will run at the next scheduled time.", vbInformation, "Audible Scraper"
Else
    fso.CreateTextFile(flagFile).Close
    MsgBox "Scraper disabled. The scheduled task will still fire but exit immediately.", vbInformation, "Audible Scraper"
End If
