; старт скрипта
; "C:\Program Files\AutoHotkey\v2\AutoHotkey.exe" C:\Arduino\s4a.ahk

#Requires AutoHotkey v2.0
#SingleInstance force

Run '"C:\Program Files (x86)\S4A\S4A.exe" "C:\Program Files (x86)\S4A\S4A.image" C:\Arduino\auto_board.sb'
WinWait("S4A 1.6")
WinActivate("S4A 1.6")
Sleep 1000
; перевести програму у режим презентації
CoordMode("Mouse", "Window")
MouseMove(1265, 50)
Click()
; запустити програму
CoordMode("Mouse", "Window")
MouseMove(1230, 87)
Click()

8:: {
	; перевести програму у режим редагування
	CoordMode("Mouse", "Window")
	MouseMove(500, 230)
	Click()
	Sleep 300
	; зупинити програму
	MouseMove(1255, 87)
	Click()
	Sleep 300
	; клікнути на хрестик закриття програми
    MouseMove(1265, 20)
	Sleep 300
    Click()
	Sleep 300
	; клікнути на закриття діалогу
	MouseMove(615, 425)
	Click()
	Sleep 300
	; клікнути на закриття проекту
	MouseMove(615, 425)
	Click()
	ExitApp
}