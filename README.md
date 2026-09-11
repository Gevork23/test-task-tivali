# Auth Signup — Pytest Automation

Набор автотестов на Python + pytest для проверки эндпоинта
`POST /api/Auth/signup` API **Fcle**.

## Описание проекта

Проект проверяет контракт эндпоинта `POST /api/Auth/signup`:

- успешную регистрацию с валидным e-mail (`200` + JSON-строка с полем
  `token`);
- валидацию формата e-mail (параметризовано, 9 кейсов);
- обязательность поля `email` (`409`);
- отклонение пустого тела запроса (`409`);
- отклонение тела с неправильным `Content-Type` (`415`/`409`);
- throttle повторной регистрации с тем же e-mail (`429`,
  `user.signup.resetTokenSent`);
- поддержку заявленного в Swagger `Content-Type: text/json`;
- приём необязательного поля `utm`.

Дополнительно проект фиксирует **два известных расхождения** между
Swagger-контрактом и фактическим поведением сервера (см. раздел
«Особенности API Fcle»). Эти кейсы помечены `@pytest.mark.xfail(strict=True)`
и в отчёте видны как `XFAIL` — они автоматически превратятся в
`XPASS` → `FAIL`, как только бэкенд будет исправлен.

Тесты **идемпотентны**: уникальные e-mail генерируются через
`uuid4 + Faker` перед каждым запуском, поэтому набор можно безопасно
перезапускать без коллизий на сервере.

## Особенности API Fcle (важно для ревьюера)

При разработке тестов были выявлены неочевидные детали контракта:

1. **Все ошибки валидации возвращают `409 Conflict`**, а не привычные
   `400/422`. Тело ответа — структурированный JSON:
   `{"error": {"code": "user.email.isInvalid", "message": "...", "values": "..."}}`.
2. **Успешный ответ — дважды закодированный JSON.** Строка ответа
   содержит внутри себя ещё одну JSON-строку:
   `"{\"email\":\"...\",\"lang\":\"en\",\"token\":\"...\"}"`.
   Разворачивается за два `json.loads` (см. helper `_parse_nested_json`).
3. **Повторная регистрация того же e-mail в коротком окне → `429`**
   с кодом `user.signup.resetTokenSent` (anti-enumeration).
   Тест `test_signup_with_duplicate_email_is_throttled` проверяет это
   **строго**: повторный `200` будет расценен как регрессия
   (возможность создать дубликат аккаунта).
4. **Регексп из Swagger**
   `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`
   допускает две точки подряд в домене, поэтому `user@example..com`
   **проходит** валидацию. Тест `test_signup_double_dot_domain_is_rejected`
   формулирует *желаемое* поведение (отказ) и помечен `xfail` до
   исправления регекспа.
5. **Swagger объявляет `additionalProperties: false`**, но ASP.NET Core
   по умолчанию игнорирует неизвестные JSON-поля. Тест
   `test_signup_with_unknown_field_is_rejected` фиксирует желаемый
   контракт и помечен `xfail` до ужесточения серверной валидации.

## Требования

- Python 3.10+
- Доступ в интернет к `https://automation.tivaliclub.com/fcle`

## Установка

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Runtime-зависимости
pip install -r requirements.txt

# + линтеры и форматтеры (опционально, но рекомендуется)
pip install -r requirements-dev.txt
```

## Запуск тестов

```bash
pytest tests/ -v
```

Ожидаемый результат — **16 passed, 2 xfailed**.

Запуск только позитивного сценария:

```bash
pytest tests/test_signup.py::TestAuthSignup::test_signup_with_valid_email_returns_token -v
```

Запуск без `xfail`-канареек (например, в «зелёном» CI-джобе,
где `xfail` не должен маскировать регрессии):

```bash
pytest tests/ -v -m "not xfail"
```

## Структура проекта

```
project/
├── tests/
│   ├── __init__.py       # маркер пакета тестов
│   ├── conftest.py       # фикстуры: session, base_url, unique_email, ...
│   └── test_signup.py    # тесты эндпоинта /api/Auth/signup
├── requirements.txt      # runtime-зависимости
├── requirements-dev.txt  # black / isort / flake8
├── pyproject.toml        # конфиги pytest, black, isort
├── .flake8               # конфиг flake8 (PEP 8: max-line-length = 79)
├── README.md
└── .gitignore
```

### Назначение файлов

| Файл | Назначение |
|------|------------|
| `tests/conftest.py` | Общие фикстуры: `base_url`, `api_session`, `faker_instance`, `unique_email`, `signup_url`, `valid_signup_payload`. |
| `tests/test_signup.py` | Класс `TestAuthSignup` с позитивными, негативными и канареечными кейсами. |
| `requirements.txt` | Минимальные зависимости для прогона тестов. |
| `requirements-dev.txt` | Дополнительно `black`, `isort`, `flake8` для локальной проверки стиля. |
| `pyproject.toml` | Настройки `pytest` (в т.ч. `xfail_strict = true`), `black` и `isort`. |
| `.flake8` | Правила flake8, согласованные с PEP 8 и black (`max-line-length = 79`). |

## Пример вывода

## Пример вывода

```
$ pytest tests/ -v
============================= test session starts =============================
platform linux -- Python 3.12.13, pytest-8.3.3, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: /home/user/test-task-tivali
configfile: pyproject.toml
plugins: Faker-30.1.0
collected 18 items

tests/test_signup.py::TestAuthSignup::test_signup_with_valid_email_returns_token PASSED [  5%]
tests/test_signup.py::TestAuthSignup::test_signup_with_invalid_email_is_rejected[empty-string] PASSED [ 11%]
tests/test_signup.py::TestAuthSignup::test_signup_with_invalid_email_is_rejected[no-at-sign] PASSED [ 16%]
tests/test_signup.py::TestAuthSignup::test_signup_with_invalid_email_is_rejected[no-local-part] PASSED [ 22%]
tests/test_signup.py::TestAuthSignup::test_signup_with_invalid_email_is_rejected[empty-local-part] PASSED [ 27%]
tests/test_signup.py::TestAuthSignup::test_signup_with_invalid_email_is_rejected[empty-domain] PASSED [ 33%]
tests/test_signup.py::TestAuthSignup::test_signup_with_invalid_email_is_rejected[no-tld] PASSED [ 38%]
tests/test_signup.py::TestAuthSignup::test_signup_with_invalid_email_is_rejected[space-in-local-part] PASSED [ 44%]
tests/test_signup.py::TestAuthSignup::test_signup_with_invalid_email_is_rejected[double-at] PASSED [ 50%]
tests/test_signup.py::TestAuthSignup::test_signup_with_invalid_email_is_rejected[leading-dot-in-domain] PASSED [ 55%]
tests/test_signup.py::TestAuthSignup::test_signup_without_email_field_is_rejected PASSED [ 61%]
tests/test_signup.py::TestAuthSignup::test_signup_with_empty_body_is_rejected PASSED [ 66%]
tests/test_signup.py::TestAuthSignup::test_signup_with_malformed_body_is_rejected PASSED [ 72%]
tests/test_signup.py::TestAuthSignup::test_signup_with_duplicate_email_is_throttled PASSED [ 77%]
tests/test_signup.py::TestAuthSignup::test_signup_double_dot_domain_is_rejected XFAIL [ 83%]
tests/test_signup.py::TestAuthSignup::test_signup_with_utm_payload_succeeds PASSED [ 88%]
tests/test_signup.py::TestAuthSignup::test_signup_with_unknown_field_is_rejected XFAIL [ 94%]
tests/test_signup.py::TestAuthSignup::test_signup_with_text_json_content_type PASSED [100%]

=========================== short test summary info ===========================
XFAIL tests/test_signup.py::TestAuthSignup::test_signup_double_dot_domain_is_rejected - Server regex allows consecutive dots in the domain (user@example..com is accepted). Test asserts the desired behaviour; remove the marker once fixed.
XFAIL tests/test_signup.py::TestAuthSignup::test_signup_with_unknown_field_is_rejected - Swagger declares additionalProperties:false, but the server silently ignores unknown JSON fields. Test asserts the documented contract; remove the marker once the server enforces it.
======================== 16 passed, 2 xfailed in 2.83s ========================
```

## Идемпотентность

- Каждый тест, создающий пользователя, использует фикстуру
  `unique_email`, которая возвращает адрес вида
  `test_<uuid4-hex>@<faker-domain>`.
- `Faker.unique` гарантирует уникальность только **внутри одного
  pytest-процесса**, поэтому дополнительно подмешивается UUID4 —
  это защищает от коллизий между разными запусками и CI-джобами.
- Префикс `test_` упрощает поиск и очистку тестовых данных на бэкенде.

## Стиль кода

Проект следует строгому **PEP 8** (максимальная длина строки — **79**
символов) и принципам SOLID / KISS / DRY. Дополнительно используется
`black` и `isort` в режиме, совместимом с PEP 8.

Проверка стиля (ничего не меняет, только сообщает о нарушениях):

```bash
black --check .
isort --check .
flake8 .
```

Автоматическое форматирование:

```bash
black .
isort .
```