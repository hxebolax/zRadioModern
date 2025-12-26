@echo off
setlocal EnableExtensions

title Subir primer contenido a GitHub - zRadioModern
echo ============================================================
echo   Subir primer contenido a GitHub (primer push)
echo   Repo: https://github.com/hxebolax/zRadioModern.git
echo ============================================================
echo.

REM ============================================================
REM CONFIGURACION
REM ============================================================
set "REPO_URL=https://github.com/hxebolax/zRadioModern.git"
set "BRANCH=main"
set "COMMIT_MSG=Primer commit: subida inicial"
echo Carpeta actual:
echo %CD%
echo.

REM ============================================================
REM COMPROBAR GIT
REM ============================================================
where git >nul 2>nul
if errorlevel 1 (
	echo [ERROR] Git no esta instalado o no esta en el PATH.
	echo Instala Git para Windows y reabre la consola.
	echo.
	pause
	exit /b 1
)

REM ============================================================
REM CREAR README SI NO EXISTE (EVITA COMMIT VACIO)
REM ============================================================
if not exist "README.md" (
	echo # zRadioModern>README.md
	echo.>>README.md
	echo Repositorio inicializado.>>README.md
)

REM ============================================================
REM INICIALIZAR REPO SI NO EXISTE .git
REM ============================================================
if not exist ".git" (
	echo [INFO] Inicializando repositorio git...
	git init
	if errorlevel 1 (
		echo [ERROR] Fallo al ejecutar: git init
		pause
		exit /b 1
	)
) else (
	echo [INFO] Repositorio git ya existe.
)

REM ============================================================
REM ASEGURAR RAMA MAIN
REM ============================================================
echo [INFO] Configurando rama %BRANCH%...
git branch -M "%BRANCH%"
if errorlevel 1 (
	echo [ERROR] Fallo al configurar la rama %BRANCH%.
	pause
	exit /b 1
)

REM ============================================================
REM CONFIGURAR REMOTO ORIGIN (CREAR O ACTUALIZAR)
REM ============================================================
git remote get-url origin >nul 2>nul
if errorlevel 1 (
	echo [INFO] Creando remoto origin...
	git remote add origin "%REPO_URL%"
	if errorlevel 1 (
		echo [ERROR] Fallo al agregar el remoto origin.
		pause
		exit /b 1
	)
) else (
	echo [INFO] Remoto origin ya existe. Actualizando URL por si acaso...
	git remote set-url origin "%REPO_URL%"
	if errorlevel 1 (
		echo [ERROR] Fallo al actualizar la URL del remoto origin.
		pause
		exit /b 1
	)
)

REM ============================================================
REM AÑADIR ARCHIVOS Y COMMIT
REM ============================================================
echo [INFO] Agregando archivos...
git add -A
if errorlevel 1 (
	echo [ERROR] Fallo al ejecutar: git add -A
	pause
	exit /b 1
)

echo [INFO] Creando commit...
git commit -m "%COMMIT_MSG%" >nul 2>nul
if errorlevel 1 (
	echo [WARN] No se pudo crear commit. Posibles causas:
	echo        - No hay cambios para commitear
	echo        - No tienes configurado user.name / user.email
	echo.
	echo [INFO] Si te falta configurar identidad, ejecuta:
	echo        git config --global user.name "TuNombre"
	echo        git config --global user.email "tu@email.com"
	echo.
)

REM ============================================================
REM PUSH INICIAL
REM ============================================================
echo [INFO] Subiendo a GitHub (push)...
git push -u origin "%BRANCH%"
if errorlevel 1 (
	echo.
	echo [ERROR] Fallo al subir (push).
	echo Posibles causas:
	echo  - No has iniciado sesion en GitHub (credenciales).
	echo  - GitHub requiere token (PAT) si usas HTTPS.
	echo  - No tienes permisos sobre el repositorio.
	echo.
	echo [TIP] Si te pide password en HTTPS, usa un TOKEN (PAT), no tu password.
	echo.
	pause
	exit /b 1
)

echo.
echo [OK] Subida inicial completada.
echo.
pause
exit /b 0
