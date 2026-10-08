# Задание для агента: поднять Docker-стенд «Генератори» (td_genset) у заказчика

Ты работаешь на компьютере заказчика (Windows, macOS или Linux с Docker Desktop). Цель: поднять стенд модуля Odoo 18
«Генератори» с эмулятором ретранслятора, убедиться, что он работает, показать заказчику карточку генератора «Стенд»
и прогнать с ним три сценария. Описание для человека — `smartgen/docker/README.md`: прочитай его целиком перед
началом, в нём таблица всех сценариев и типовых проблем.

## Чего не делать

- **Не менять код модуля** (`smartgen/td_genset/**`) и эмулятора (`smartgen/tools/**`). Файлы стенда
  (`smartgen/docker/**`) менять только для обхода проблем окружения из раздела 7 (порт, `platform`) и сразу
  говорить об этом заказчику.
- **Не подключать стенд к настоящему ретранслятору** без явной просьбы заказчика. Адрес и токен настоящего
  ретранслятора не искать, не подбирать и не записывать в файлы.
- **Никогда не включать «Дозволити команди»** у генератора, который опрашивает настоящий ретранслятор, не создавать
  ему расписание и не отправлять `POST /commands` на настоящий ретранслятор: он управляет реальным генератором в
  офисе. Если заказчик сам просит подключить настоящий ретранслятор — только чтение, строго по разделу README
  «Переключить стенд на настоящий ретранслятор».
- Не открывать порты стенда в сеть (`0.0.0.0`), не менять учебные пароли на настоящие, не делать `git commit` /
  `git push`.
- `docker compose down -v` удаляет базу стенда — только с согласия заказчика (или если первая установка сломалась и
  заказчик согласен начать заново).

## 1. Проверить окружение

```bash
docker version           # должны ответить и Client, и Server; Server молчит — запустить Docker Desktop, подождать «Engine running»
docker compose version   # v2… или новее (команда «docker compose» через пробел)
git --version
```

Порты 8069 и 8081 свободны (вывод должен быть пустым):

- macOS / Linux: `lsof -nP -iTCP:8069 -sTCP:LISTEN; lsof -nP -iTCP:8081 -sTCP:LISTEN`
- Windows PowerShell: `Get-NetTCPConnection -State Listen -LocalPort 8069,8081 -ErrorAction SilentlyContinue`

Память Docker: `docker info --format "{{.MemTotal}}"` — не меньше 4000000000 (байт). Меньше — попросить заказчика
увеличить: Docker Desktop → Settings → Resources → Memory.

## 2. Склонировать и запустить

```bash
git clone -b claude/dreamy-ramanujan-p2wlej https://github.com/tnizhnikovskyi-todo/todo_timur.git
cd todo_timur/smartgen/docker
git ls-files --eol entrypoint.sh   # в колонке рабочей копии должно быть w/lf (на Windows — обязательно проверить)
docker compose up -d
```

Клон уже есть — `git -C <папка клона> switch claude/dreamy-ramanujan-p2wlej && git -C <папка клона> pull`.
Клонировать в папку пользователя (Docker Desktop по умолчанию даёт контейнерам доступ к ней).

## 3. Дождаться готовности

Первый старт: загрузка образов (2–10 мин) и установка модуля с настройкой (3–5 мин). Следить:

```bash
docker compose logs -f odoo
```

Готово, когда после строки `[stand] Запуск Odoo: http://localhost:8069 …` появились
`HTTP service (werkzeug) running on …:8069` и `Modules loaded.` Строка `Modules loaded.` бывает и раньше, во время
установки, — важна та, что после `[stand] Запуск Odoo`. Сообщения вида `<string>:38: (ERROR/3) Unexpected
indentation.` во время установки безвредны (так Odoo обрабатывает описания своих стандартных модулей).

Без лога — опрашивать раз в 10–20 с, пока не будет `200` (до 15 мин):

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8069/web/login
```

PowerShell: `(Invoke-WebRequest http://localhost:8069/web/login -UseBasicParsing).StatusCode`.
Или одной командой: `docker compose up -d --wait --wait-timeout 1200` — вернётся, когда все сервисы станут healthy.

## 4. Проверить, что стенд работает

| Проверка | Команда | Ожидается |
|---|---|---|
| Сервисы | `docker compose ps` | `db`, `relay`, `odoo` — running, `(healthy)` |
| Страница входа | `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8069/web/login` | `200` |
| Модуль установлен | `docker compose exec db psql -U odoo -d genset -Atc "select state from ir_module_module where name = 'td_genset'"` | `installed` |
| Стенд настроен | `docker compose logs odoo` — строки `[seed]` (PowerShell: `docker compose logs odoo \| Select-String '\[seed\]'`) | от `[seed] база genset: настройка стенда` до `[seed] готово…`, без `ОШИБКА` |
| Данные идут (через 1–2 мин после старта Odoo) | `docker compose exec db psql -U odoo -d genset -Atc "select link_state, controller_mode, (select count(*) from td_genset_reading) from td_genset"` | `online\|auto\|<больше 0>` |
| Эмулятор | `curl -s -H "Authorization: Bearer dev-token-0123456789abcdefghij" http://localhost:8081/api/v1/status` | JSON: `"version": "1.1.1"`, в `devices` — `"online": true` |

## 5. Показать заказчику

1. http://localhost:8069 → `admin` / `admin` → **Генератори → Генератор** → карточка «Стенд».
2. Показать: шапку «Онлайн · N с тому»; пульт (режим «Авто», стан «Очікування»); мережу, паливо 95 % (≈ 138 L),
   АКБ 27,8 V, мотогодини 34 год 51 хв, 39 пусків, 253 kWh; «Наступна подія» розкладу (пн–пт 08:45 «Авто», 18:30
   «Ручний» + «Стоп»); смарт-кнопки «Показання», «Тривоги», «Команди», «До ТО, мотогодин»; вкладки и чатер.
3. Объяснить тревогу «Термін ТО: перше 30 год…» и заявку «ТО-1 після обкатки» — штатная работа модуля (у эмулятора
   34 мотогодини, первое ТО — на 30).
4. Роли: окно инкогнито → `qa_s` / `qa_s` — кнопки пульта недоступны (пульт — только тех. адміністратору), есть
   «Робота поза графіком»; изменения видны в обоих окнах без F5.
5. Кнопка «Оновити дані» — забрать данные сразу, не дожидаясь минутного опроса.

## 6. Три сценария с заказчиком

Перед сценариями режим генератора — «Авто» (на карточке; или в ответе `GET /_sim` → `devices[0].mode` = `auto`).
Если «Ручний» или «Стоп» (в будни после 18:30 так делает расписание) — `admin` → пульт «Авто» → подтвердить, дождаться
в «Команди» статуса «Підтверджено».

Функция для запросов к эмулятору — bash / zsh:

```bash
sim() { curl -s -X POST http://localhost:8081/_sim -H "Authorization: Bearer dev-token-0123456789abcdefghij" -H 'Content-Type: application/json' -d "$1" -o /dev/null -w '%{http_code}\n'; }
```

PowerShell:

```powershell
function sim($json) { Invoke-RestMethod -Method Post -Uri http://localhost:8081/_sim -Headers @{ Authorization = 'Bearer dev-token-0123456789abcdefghij' } -ContentType 'application/json' -Body $json | Out-Null; 'OK' }
```

После каждого запроса — «Оновити дані» на карточке (или подождать до минуты). Ответ `200` / `OK` — эмулятор принял.

### Сценарий 1. Пропала сеть — генератор запустился сам

`sim '{"mains_normal": false}'`. Через 10–60 с: «Мережа: немає», етап «Пуск», затем «Робота» (генератор под
нагрузкой примерно через 45 с), живлення від генератора; события «Відключення мережі» и «Робота генератора»; в
чатере «Зникла мережа о HH:MM.» и «Генератор запущено о HH:MM: Зникла мережа · режим Авто.».

Вернуть: `sim '{"mains_normal": true}'` → примерно через минуту генератор остановлен; в чатере «Мережа повернулася:
Генератор підхопив за N с (без мережі N хв).» и «Генератор зупинено о HH:MM: Пуск з 1-ї спроби, навантаження
прийнято; мережа повернулася.».

Проверка в базе: `docker compose exec db psql -U odoo -d genset -Atc "select genset_status, mains_ok, feed_source from td_genset"` —
во время сценария `9|f|genset`, после — `0|t|mains`.

### Сценарий 2. Пропала связь с модулем

`sim '{"link": false, "advance": 600}'` — «модуль молчит уже 10 минут». После «Оновити дані»: «Немає зв'язку»,
событие «Зв'язок», команды пульта недоступны; примерно через 3 мин — критическая тревога «Немає зв'язку з модулем»
(смарт-кнопка «Тривоги»). Уведомления рассылает задача cron раз в минуту: чтобы показать уведомление у `qa_s`
во «Входящих», не возвращайте связь раньше чем через минуту после тревоги.

Вернуть: `sim '{"link": true, "clock_offset": 0}'` → «Онлайн», в чатере «Зв'язок відновлено після N хв без даних.»,
тревога снята.

### Сценарий 3. Уровень топлива упал без работы двигателя (возможный слив)

`sim '{"fuel_level": 40}'` → событие «Падіння рівня палива», критическая тревога «Рівень палива впав на 80 L без
роботи двигуна» (≈ 138 → 58 L), в течение минуты — уведомление `qa_s`.

Вернуть: `sim '{"fuel_level": 95}'` → событие «Заправка», в чатере «Рівень палива зріс: +80 L (58 → 138 L).».
Тревогу о падении принять: `qa_s` или `admin` → «Тривоги» → «Прийняв».

Остальные сценарии (`no_exec`, `cloud_press`, `reset`, низкий уровень топлива) — таблица в README, раздел «Сценарии
через эмулятор».

## 7. Ошибки и что делать

| Ошибка | Действие |
|---|---|
| `Cannot connect to the Docker daemon`, `error during connect` | Запустить Docker Desktop, дождаться «Engine running», повторить |
| Образ не скачивается: `TLS handshake timeout`, `i/o timeout`, `toomanyrequests`, `pull access denied` | Проверить интернет и прокси (Docker Desktop → Settings → Resources → Proxies); `docker login`; повторить `docker compose pull`, затем `docker compose up -d`. Нужны только официальные образы `postgres:16`, `python:3.12-slim`, `odoo:18.0` — другие не подставлять |
| `no matching manifest for linux/arm64/v8` | В `docker-compose.yml` у `odoo` раскомментировать `platform: linux/amd64`, `docker compose up -d`; сказать заказчику |
| `port is already allocated`, `address already in use` | Найти процесс (шаг 1). Если его нельзя остановить — в `docker-compose.yml` поменять левую часть порта (`"127.0.0.1:18069:8069"`, `"127.0.0.1:18081:8081"`), `docker compose up -d`, дальше пользоваться новыми портами; сказать заказчику |
| В логе odoo `$'\r': command not found` или `invalid option name` | CRLF в `entrypoint.sh` (`git ls-files --eol entrypoint.sh` покажет `w/crlf`). Пересоздать файл из git: `rm entrypoint.sh` (PowerShell: `Remove-Item entrypoint.sh`), `git checkout -- entrypoint.sh`, затем `docker compose up -d --force-recreate odoo` |
| `Mounts denied`, `path … is not shared` | Клонировать в папку пользователя или добавить путь в Docker Desktop → Settings → Resources → File sharing |
| В логе `[stand] база genset: ready` при первом показе | Не ошибка: стенд уже запускался, тома сохранились, установка пропущена. Начать с нуля — только с согласия заказчика: `docker compose down -v && docker compose up -d` |
| Установка прервалась (`[stand] база genset: not_installed` / `empty`, Traceback при установке) | `docker compose restart odoo` — entrypoint доустановит модуль. Повторяется — показать заказчику Traceback (`docker compose logs --tail=200 odoo`) и с его согласия `docker compose down -v && docker compose up -d` |
| odoo перезапускается по кругу | `docker compose logs --tail=200 odoo`, найти Traceback; при нехватке памяти — Docker Desktop → Resources → Memory ≥ 4 ГБ |
| Нет данных на карточке дольше 3 мин | `docker compose logs --tail=50 relay` — раз в минуту запросы Odoo `GET /api/v1/status` и `/readings`; адрес: `docker compose exec db psql -U odoo -d genset -Atc "select value from ir_config_parameter where key = 'td_genset.relay_url'"` → `http://relay:8081/api/v1`; на карточке `admin` → «Перевірити зв'язок» |
| `/_sim` отвечает `401` | Нет заголовка `Authorization: Bearer dev-token-0123456789abcdefghij` |
| `/_sim` отвечает `400 unknown _sim keys` | Опечатка в ключе; список ключей — в ответе (`known`) и в начале `smartgen/tools/fake_relay.py` |

## 8. Завершение

Сообщить заказчику: адрес http://localhost:8069, логины (`admin`, `qa_s`, `qa_a`, `qa_t`, пароль = логин), что
показано и проверено; что стенд работает в фоне и запускается вместе с Docker Desktop; как остановить
(`docker compose stop`) и удалить вместе с базой (`docker compose down -v`). Без просьбы заказчика стенд не удалять.
