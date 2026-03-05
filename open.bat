@echo off
REM Always start in the folder where this batch file is located
cd /d "%~dp0"

REM Step 1: Check if Miniforge is installed
IF NOT EXIST "%USERPROFILE%\miniforge3" (
    echo Miniforge not found. Installing...
    curl -L -o Miniforge3-Windows-x86_64.exe https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe
    start /wait "" Miniforge3-Windows-x86_64.exe /InstallationType=JustMe /AddToPath=1 /RegisterPython=1 /S /D=%USERPROFILE%\miniforge3
) ELSE (
    echo Miniforge already installed. Skipping installation.
)

REM Step 2: Initialize Conda
call "%USERPROFILE%\miniforge3\Scripts\activate.bat"

REM Step 3: Check if environment "dv" exists
conda env list | findstr /C:"dv" >nul
IF ERRORLEVEL 1 (
    echo Environment dv not found. Creating...
    conda create -y -n dv python
) ELSE (
    echo Environment dv already exists. Skipping creation.
)

REM Step 4: Activate environment
call conda activate dv

REM Step 5: Install requirements.txt if present
IF EXIST requirements.txt (
    echo Installing requirements...
    pip install -r requirements.txt
) ELSE (
    echo No requirements.txt found in %~dp0
)

REM Step 6: Run Streamlit app
IF EXIST app.py (
    echo Launching Streamlit app...
    streamlit run app.py
) ELSE (
    echo app.py not found in %~dp0
)

pause