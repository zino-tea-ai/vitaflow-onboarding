@echo off
chcp 65001 >nul
echo ============================================
echo 🔒 Cursor Project 一键备份
echo ============================================
echo.

cd /d "C:\Users\WIN\Desktop\Cursor Project"

echo [1/3] Git 提交...
echo --------------------------------------------
git add -A
git commit -m "Auto backup - %date% %time:~0,8%"
echo.

echo [2/3] 推送到 GitHub...
echo --------------------------------------------
git push github changes:main
echo.

echo [3/3] 本地备份...
echo --------------------------------------------
python backup.py
echo.

echo ============================================
echo ✅ 所有备份任务完成!
echo ============================================
echo.
pause
