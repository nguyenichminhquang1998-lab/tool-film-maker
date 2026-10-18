@echo off
rem Bat tay: ghi dien nang cua may nay. Dong cua so nay de dung. Khong tu chay theo lich.
title Ghi dien nang (dong cua so de dung)
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -I "%~dp0dien-nang.py" chay
pause
