# Установка и работа с Claude Code на своём компьютере

Пошаговая инструкция: от чистой машины до первого отчёта о трендах. Подходит для
Windows, macOS и Linux.

## 1. Что понадобится

| Что | Зачем | Где взять |
|---|---|---|
| Python 3.11+ | код проекта | python.org (Windows: при установке отметьте «Add python.exe to PATH») |
| Git | получить репозиторий | git-scm.com |
| Claude Code | Claude работает с проектом на вашей машине | code.claude.com — терминал (CLI), десктоп-приложение или расширение VS Code |
| Отдельный аккаунт TikTok | под ним будет смотреть браузер | рекомендуется не основной: автоматический сбор нарушает правила TikTok, аккаунт могут ограничить |

Проверка: `python --version` (или `python3 --version` на macOS) показывает 3.11 или новее.

## 2. Установка проекта

```bash
git clone https://github.com/j09822475-dev/ytcode.git
cd ytcode
git checkout claude/tiktok-trends-channel-bjoxlv   # пока код не влит в основную ветку
```

Виртуальное окружение и зависимости:

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1      # если ругается на политику: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -e ".[dev]"
playwright install chromium
```

Вместо скачанного Chromium можно использовать установленный Google Chrome: в
`trendbot.toml` укажите `browser_channel = "chrome"` (тогда `playwright install` не нужен).

Проверка установки:
```bash
pytest
```
Должно быть `11 passed`.

## 3. Настройка под свою нишу

```bash
cp trendbot.example.toml trendbot.toml      # Windows: copy trendbot.example.toml trendbot.toml
```

Откройте `trendbot.toml` и заполните:
- `niche` — о чём канал;
- `keywords` — 2–5 поисковых запросов, по которым люди ищут такие ролики;
- `hashtags` — 2–5 хэштегов ниши (без `#`).

Остальное можно не трогать. Этот шаг может сделать и Claude — просто скажите ему нишу.

## 4. Запуск Claude Code

Всегда запускайте Claude Code **из папки проекта** и **с активированным venv** — иначе он
не найдёт команду `trendbot`:

```bash
cd ytcode
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
claude
```

(В десктоп-приложении или VS Code — откройте папку `ytcode`; если `trendbot` не находится,
попросите Claude «активируй .venv и установи проект».)

Claude автоматически прочитает `CLAUDE.md` — там правила проекта, архитектура и порядок
работы. Разрешения на запуск `trendbot` и `pytest` без лишних вопросов уже заданы в
`.claude/settings.json`.

## 5. Первый вход в TikTok

Напишите Claude: «войди в TikTok» — или сами выполните:
```bash
trendbot login
```
Откроется окно браузера со страницей входа. **Войдите сами** (логин, пароль, коды
вводите только вы). Команда заметит вход и закроется. Сессия сохранится в
`data/browser-profile` — повторять вход нужно, только если TikTok вас разлогинит.

## 6. Использование

Главное — просто писать Claude обычными словами:

| Что написать Claude | Что будет |
|---|---|
| `/find-trends` или «найди тренды» | сбор (несколько минут, окно браузера листает TikTok), отчёт, разбор кадров, 5 идей роликов → `data/reports/<дата>/analysis.md` |
| «разбери последний отчёт ещё раз, сделай упор на звуки» | новый разбор без повторного сбора |
| «добавь в ключевые слова …» | правка `trendbot.toml` |
| «сравни с прошлым запуском» | что выросло, что затухло |

Пока идёт сбор:
- **не закрывайте окно браузера** и не сворачивайте его надолго;
- если TikTok показал **капчу** — пройдите её в окне, сбор продолжится сам;
- компьютер не должен уходить в сон.

Запускайте сбор 1–3 раза в день: «прирост роликов/час» в отчёте считается между
запусками — он и показывает, что тренд растёт прямо сейчас.

Без Claude всё тоже работает:
```bash
trendbot run                 # сбор + отчёт с кадрами
trendbot collect --feed 20   # только сбор, 20 роликов ленты
trendbot report --frames     # только отчёт
```

## 7. Разработка вместе с Claude

Примеры задач:
- «добавь создание видео по идее из analysis.md»;
- «сбор перестал находить ролики — разберись» (Claude попросит короткий отладочный запуск
  с сохранением сырых ответов сайта и починит парсер по ним — порядок в `CLAUDE.md`);
- «добавь в отчёт график роста звуков».

Как принято работать:
1. Claude меняет код и **прогоняет `pytest`** — все тесты должны быть зелёными.
2. Сквозной тест работает с локальным макетом сайта, к настоящему TikTok не ходит.
   Проверку на живом сайте Claude делает только с вашего согласия и маленьким объёмом.
3. Коммит — после зелёных тестов. Попросите: «закоммить и запушь».

## 8. Частые проблемы

| Симптом | Решение |
|---|---|
| `trendbot: command not found` | не активирован venv: `source .venv/bin/activate` (Windows: `.venv\Scripts\Activate.ps1`) |
| `Executable doesn't exist … playwright install` | `playwright install chromium` или `browser_channel = "chrome"` |
| `tomllib` / синтаксическая ошибка при запуске | Python старше 3.11 — обновите |
| В отчёте 0 роликов | проверьте, что вход выполнен (`trendbot login`); если да — сайт изменился, попросите Claude разобраться |
| Капча на каждом шаге | сделайте перерыв на несколько часов, уменьшите `feed_videos`; не запускайте сбор слишком часто |
| Хочу начать заново | удалите `data/trendbot.sqlite` (история трендов) или всю `data/` (включая вход) |

## Что где лежит

```
trendbot.toml            ваши настройки (не в git)
data/                    ваши данные (не в git)
  browser-profile/       профиль браузера с входом в TikTok — никому не передавайте
  trendbot.sqlite        собранная статистика
  reports/<дата>/        report.md, trends.json, frames/, analysis.md
CLAUDE.md                инструкции для Claude
.claude/skills/find-trends/SKILL.md   порядок поиска и разбора трендов
.claude/settings.json    разрешения Claude Code для проекта
```
