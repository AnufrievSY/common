# common
Хранилище различных модулей, которые используются в проектах


# Запуск тестов
```bash
# Чистим старые результаты
Remove-Item -Recurse -Force allure-results
```
```bash
cp -r allure-report/history allure-results/history
pytest -v
allure generate allure-results -o allure-report 
allure serve allure-results
```