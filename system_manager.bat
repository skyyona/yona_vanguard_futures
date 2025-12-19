@echo off
setlocal enabledelayedexpansion

REM ###############################################################
REM #             YONA Vanguard Futures Application Launcher      #
REM ###############################################################

REM 현재 배치 파일이 있는 디렉토리 (프로젝트 루트)를 BASE_DIR 변수에 저장
SET "BASE_DIR=%~dp0"
if not "%BASE_DIR:~-1%"=="\" SET "BASE_DIR=%BASE_DIR%\"

echo ----------------------------------------------------
echo         YONA Vanguard Futures App Launcher
echo ----------------------------------------------------
echo.

REM 로깅 설정
SET "SM_LOG_DIR=%BASE_DIR%logs"
if not exist "%SM_LOG_DIR%" mkdir "%SM_LOG_DIR%"
SET "SM_LOG=%SM_LOG_DIR%\system_manager_launch.log"

echo [%DATE% %TIME%] 애플리케이션 실행 시작 > "%SM_LOG%"
echo [%DATE% %TIME%] 사용자: %USERNAME% on %COMPUTERNAME% >> "%SM_LOG%"
echo [%DATE% %TIME%] 기본 디렉토리: %BASE_DIR% >> "%SM_LOG%"
 
REM .env에서 APP_PORT를 읽어옵니다. 없으면 기본값 8200 사용
if exist "%BASE_DIR%.env" (
    for /f "usebackq tokens=1,2 delims== eol=#" %%a in ("%BASE_DIR%.env") do (
        if /i "%%a"=="APP_PORT" set "APP_PORT=%%b"
    )
)
if not defined APP_PORT set "APP_PORT=8200"
echo [%DATE% %TIME%] APP_PORT=%APP_PORT% >> "%SM_LOG%"

REM 필요한 디렉토리 생성
for %%d in (
    "backend\logs"
    "backtesting_backend\logs"
    "gui\logs"
) do (
    if not exist "%BASE_DIR%%%~d" (
        mkdir "%BASE_DIR%%%~d"
        if errorlevel 1 (
            echo [%DATE% %TIME%] 디렉토리 생성 실패: %%~d >> "%SM_LOG%"
        ) else (
            echo [%DATE% %TIME%] 디렉토리 생성됨: %%~d >> "%SM_LOG%"
        )
    )
)

REM ----------------------------------------------
REM # 1. Live Trading Backend 실행
REM ----------------------------------------------
echo [%DATE% %TIME%] 실거래 백엔드 시작 중... >> "%SM_LOG%"
netstat -ano | findstr ":%APP_PORT%" >nul
if %errorlevel%==0 (
    echo [%DATE% %TIME%] %APP_PORT% 포트가 이미 사용 중입니다. >> "%SM_LOG%"
    echo.
    echo 경고: %APP_PORT% 포트가 이미 사용 중입니다. 실거래 백엔드를 시작할 수 없습니다.
) else (
    if exist "%BASE_DIR%backend\app_main.py" (
        echo [%DATE% %TIME%] 실거래 백엔드 시작 중... >> "%SM_LOG%"
        start "Live Backend" cmd /k "cd /d "%BASE_DIR%backend" && call "%BASE_DIR%.venv_new\Scripts\activate.bat" && python -m uvicorn app_main:app --host 0.0.0.0 --port %APP_PORT% --reload --log-level info"
    ) else (
        echo [%DATE% %TIME%] 오류: backend 디렉토리에서 app_main.py를 찾을 수 없습니다. >> "%SM_LOG%"
        echo 오류: backend 디렉토리에서 app_main.py를 찾을 수 없습니다.
    )
)

REM ----------------------------------------------
REM # 2. Backtesting Backend 실행
REM ----------------------------------------------
echo [%DATE% %TIME%] 백테스팅 백엔드 시작 중... >> "%SM_LOG%"
if exist "%BASE_DIR%backtesting_backend\app_main.py" (
    echo [%DATE% %TIME%] 백테스팅 백엔드 시작 중... >> "%SM_LOG%"
    REM 프로젝트 루트에서 모듈 경로를 사용해 uvicorn 실행 (패키지 인식 보장)
    REM 포트 사용 여부와 상관없이 항상 프롬프트를 띄워 사용자에게 상태를 보여준다.
    start "Backtesting Backend" cmd /k "cd /d "%BASE_DIR%" && call "%BASE_DIR%.venv_backtest\Scripts\activate.bat" && python -m uvicorn backtesting_backend.app_main:app --host 0.0.0.0 --port 8001 --log-level info"
) else (
    echo [%DATE% %TIME%] 오류: backtesting_backend 디렉토리에서 app_main.py를 찾을 수 없습니다. >> "%SM_LOG%"
    echo 오류: backtesting_backend 디렉토리에서 app_main.py를 찾을 수 없습니다.
)

REM ----------------------------------------------
REM # 3. Engine Backend 실행
REM ----------------------------------------------
echo [%DATE% %TIME%] 엔진 백엔드 시작 중... >> "%SM_LOG%"
netstat -ano | findstr ":8202" >nul
if %errorlevel%==0 (
    echo [%DATE% %TIME%] 8202 포트가 이미 사용 중입니다. >> "%SM_LOG%"
    echo.
    echo 경고: 8202 포트가 이미 사용 중입니다. 엔진 백엔드를 시작할 수 없습니다.
) else (
    if exist "%BASE_DIR%engine_backend\app_main.py" (
        echo [%DATE% %TIME%] 엔진 백엔드 시작 중... >> "%SM_LOG%"
        REM 엔진 전용 가상환경에서 signal-logger 래퍼를 통해 uvicorn 실행
        start "Engine Backend" cmd /k "cd /d "%BASE_DIR%" && call "%BASE_DIR%engine_backend\.venv\Scripts\activate.bat" && python run_engine_backend_with_signal_logger.py --port 8202"
    ) else (
        echo [%DATE% %TIME%] 오류: engine_backend 디렉토리에서 app_main.py를 찾을 수 없습니다. >> "%SM_LOG%"
        echo 오류: engine_backend 디렉토리에서 app_main.py를 찾을 수 없습니다.
    )
)

REM ----------------------------------------------
REM # 4. GUI/Frontend 실행
REM ----------------------------------------------
echo [%DATE% %TIME%] GUI/프론트엔드 시작 중... >> "%SM_LOG%"
if exist "%BASE_DIR%gui\main.py" (
    echo [%DATE% %TIME%] GUI 시작 중... >> "%SM_LOG%"
    start "GUI" cmd /k "cd /d "%BASE_DIR%gui" && call "%BASE_DIR%.venv_new\Scripts\activate.bat" && python main.py"
) else (
    echo [%DATE% %TIME%] %BASE_DIR%gui\main.py에서 GUI를 찾을 수 없습니다. - GUI 시작을 건너뜁니다. >> "%SM_LOG%"
    echo 경고: %BASE_DIR%gui\main.py에서 GUI를 찾을 수 없습니다.
)

echo.
echo ====================================================
echo    YONA Vanguard Futures - 실행 완료
echo ====================================================
echo.
echo 웹 브라우저에서 다음 주소를 확인하세요:
echo - 실거래 백엔드:      http://localhost:%APP_PORT%
echo - 백테스팅 백엔드:    http://localhost:8001
echo.
echo 로그 파일 위치:
echo - 시스템 로그:        %SM_LOG%
echo - 실거래 백엔드:      %BASE_DIR%backend\logs\uvicorn_8000.log
echo - 백테스팅 백엔드:    %BASE_DIR%backtesting_backend\logs\uvicorn_8001.log
echo - GUI:               %BASE_DIR%gui\logs\gui.log
echo.
echo 모든 서비스가 실행된 후 이 창을 닫을 수 있습니다.
echo ====================================================
echo.

pause
endlocal