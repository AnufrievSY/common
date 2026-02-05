# common
Хранилище различных модулей, которые используются в проектах


# Запуск тестов
```bash
# Чистим старые результаты
Remove-Item -Recurse -Force allure-results

# Запускаем тесты
pytest -v

# Открываем Allure
allure serve allure-results
```