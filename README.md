# common
Хранилище различных модулей, которые используются в проектах

# Установка
```powershell
$RepoUrl = "https://github.com/AnufrievSY/common.git"
$ProjectRoot = Get-Location
$TmpDir = Join-Path $env:TEMP ("common_tmp_" + [guid]::NewGuid())

Write-Host "Клонирование во временную папку: $TmpDir"
git clone --depth 1 $RepoUrl $TmpDir

Set-Location $TmpDir
python -m pip install --upgrade pip
Get-ChildItem -Filter "requirements*.txt" | ForEach-Object {
    Write-Host "Установка зависимостей"
    python -m pip install -r $_.FullName
}

Set-Location $ProjectRoot
Get-ChildItem $TmpDir -Directory | Where-Object { $_.Name -ne ".git" } | ForEach-Object {
    $TargetDir = Join-Path $ProjectRoot $_.Name
    if (-not (Test-Path $TargetDir)) {
        Write-Host "Создание папки $TargetDir"
        New-Item -ItemType Directory -Path $TargetDir | Out-Null
    }
    Write-Host "Копирование файлов в $TargetDir"
    Copy-Item -Path (Join-Path $_.FullName "*") -Destination $TargetDir -Recurse -Force
}

Write-Host "Очистка временного хранилища"
Remove-Item -Recurse -Force $TmpDir

Write-Host "Готово."
```

# Тесты
### Запуск
```bash
pytest -vv
```

### Просмотр отчета Allure
```bash
allure serve tests/reports/allure/results
```

### Просмотр отчета покрытия
```bash
 .\\tests\reports\coverage\html\index.html
```