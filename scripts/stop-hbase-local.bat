@echo off
setlocal
set PROJECT_DIR=C:\Users\pky45\.gemini\antigravity\scratch\urban-microclimate-hbase
set JAVA_HOME=C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot
set HADOOP_HOME=%PROJECT_DIR%\hadoop
set PATH=%HADOOP_HOME%\bin;%PATH%
set HBASE_HOME=%PROJECT_DIR%\hbase

echo Gracefully shutting down HBase cluster...
call "%HBASE_HOME%\bin\hbase.cmd" master stop --shutDownCluster

echo Stopping any active HBase REST gateway instances...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8085 ^| findstr LISTENING') do (
    echo Killing REST process PID %%a
    taskkill /F /PID %%a >nul 2>&1
)

echo HBase cluster and REST services stopped.
endlocal
