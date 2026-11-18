@echo off
setlocal
set PROJECT_DIR=C:\Users\pky45\.gemini\antigravity\scratch\urban-microclimate-hbase
set JAVA_HOME=C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot
set HADOOP_HOME=%PROJECT_DIR%\hadoop
set PATH=%HADOOP_HOME%\bin;%PATH%
set HBASE_HOME=%PROJECT_DIR%\hbase

echo Starting HBase Standalone Master and RegionServer...
start "HBase-Master" cmd /c "%HBASE_HOME%\bin\hbase.cmd master start"

powershell -Command "Start-Sleep -Seconds 10"

echo Starting HBase REST Gateway on port 8085...
start "HBase-REST" cmd /c "%HBASE_HOME%\bin\hbase.cmd rest start -p 8085"

echo HBase cluster and REST Gateway launched.
endlocal
