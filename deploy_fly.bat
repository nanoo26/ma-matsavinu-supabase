@echo off
setlocal

:: =========================================
::   Ma Matsavinu - Advanced Deploy Script
:: =========================================
echo ===============================================
echo   🚀 Ma Matsavinu - Advanced Fly.io Deployment
echo ===============================================
echo.

:: Generate timestamp for commit message
for /f "tokens=1-3 delims=/ " %%a in ("%date%") do (
    for /f "tokens=1-3 delims=:." %%x in ("%time%") do (
        set timestamp=%%c-%%b-%%a_%%x%%y%%z
    )
)

:: Check if there are changes to commit
echo 🔍 Checking for code changes...
git diff --quiet
if %errorlevel%==0 (
    echo ⚠ No changes detected. Skipping Git commit.
) else (
    echo 🔄 Adding and committing changes...
    git add .
    git commit -m "update %timestamp%"
)

echo.
echo 🚀 Deploying to Fly.io...
flyctl deploy
if %errorlevel% neq 0 (
    echo ❌ Deployment failed! Check the error above.
    pause
    exit /b 1
)

echo.
echo ✅ Deployment completed successfully!
echo.

:: Open website automatically
echo 🌐 Opening your app in browser...
start https://ma-matsavinu.fly.dev/

echo.
echo 📜 Showing live Fly.io logs (press CTRL+C to exit)
flyctl logs

echo.
pause
endlocal
