// Тексти й кроки турів (F19-02, F19-03): тур новачка (welcome, 13 кроків) і 11 тематичних (basic, rack, import, scratch, address, putaway,
// apply, find, labels, docs, team). Дані двомовні: пара `[українською, English]`. Крок: `sel` — селектор елемента для підсвічування
// (масив — перший, що є на сторінці; без елемента картка по центру), `kind` — `read` («прочитати») або `do` («дія» з кнопкою
// «Показати мені»), `act` — дія: {tab} вкладка лівої панелі, {mode} режим, {select} виділити об'єкт за префіксом, {rack} поставити
// стелаж, {levels} змінити число ярусів, {search} відкрити пошук, {tray}, {open} відкрити пункт меню «Ще», {variants}, {comments}.
// Тури, що змінюють дані (`mutates`), виконуються в «навчальній копії» (тимчасовому варіанті), у кінці — «Залишити зміни»/«Скасувати».
// Діалоги (модальні) тур не відкриває: у кроках лише вкладки, режими, вибір і підсвічування.
const P = (uk, en) => [uk, en];

const TAB = (tab) => `#ltabs button[data-tab="${tab}"]`;
const MENU = (key) => [`#menu-${key}`, "#menuMore summary", "#menuExtra"];

export const TOURS = [
    {
        id: "welcome",
        title: P("Тур новачка", "Beginner tour"),
        desc: P("13 кроків: план, рівні, виділення, мініатюра, перехід по коду, правка, каталог, перевірки, застосування, інструкція.", "13 steps: plan, levels, selection, minimap, go to code, editing, catalog, checks, applying, help."),
        steps: [
            { sel: "#vp", kind: "read", title: P("Сцена: 3D і «План»", "The scene: 3D and Plan"), text: P("Тут модель складу. Колесо — масштаб, права кнопка — панорама, ліва — обертання. Кнопки «3D» і «План» зверху перемикають вигляд.", "This is the warehouse model. Wheel — zoom, right button — pan, left — rotate. The “3D” and “Plan” buttons on top switch the view.") },
            { sel: "#s6Crumbs", kind: "read", title: P("Рівні: склад › зона › ряд › стелаж › ярус", "Levels: warehouse › zone › row › bay › tier"), text: P("Вибраний рівень ховає решту, а камера наїжджає на нього. «↓» заглиблює до виділеного, «↑» піднімає, «⟲» скидає.", "A chosen level hides the rest and the camera zooms in. “↓” drills down to the selection, “↑” goes up, “⟲” resets.") },
            { sel: TAB("layers"), kind: "do", act: { tab: "layers" }, title: P("Шари", "Layers"), text: P("Відкрийте вкладку «Шари»: у ній видимість, відмітка й правила редагування кожного шару.", "Open the “Layers” tab: visibility, elevation and edit rules of each layer."), },
            { sel: "#vp", kind: "do", act: { select: "*" }, title: P("Виділення", "Selection"), text: P("Клацніть по ряду чи місцю на сцені: праворуч з'являться властивості. «Клік виділяє» під рівнями вибирає: місце, стелаж, ряд або зону; повторний клік піднімає вибір вище.", "Click a row or a place on the scene: properties appear on the right. “Click selects” under the levels picks a place, bay, row or zone; a repeated click goes one level up.") },
            { sel: "#s6Mini", kind: "read", title: P("Мініатюра плану", "Minimap"), text: P("Червона рамка — те, що видно на екрані. Клацніть чи потягніть по мініатюрі, щоб перенести камеру.", "The red frame is what is on screen. Click or drag the minimap to move the camera.") },
            { sel: TAB("search"), kind: "do", act: { search: true }, title: P("Перехід по коду", "Go to a code"), text: P("Вкладка «Пошук»: введіть код або штрихкод місця — камера перейде до нього. Швидко: клавіша «/».", "The “Search” tab: type a place code or barcode and the camera goes there. Quick key: “/”.") },
            { sel: "#modeSeg", kind: "read", title: P("Перегляд і редагування", "View and edit"), text: P("«Редагування» вмикає правку об'єктів. Права визначає ваша роль; недоступні кнопки неактивні з підказкою.", "“Edit” turns on object editing. Your role defines your rights; unavailable buttons are disabled with a hint.") },
            { sel: TAB("catalog"), kind: "read", title: P("Каталог", "Catalog"), text: P("Каталог обладнання й типів місць: 50 типів, параметри, 3D-моделі. Звідси об'єкти потрапляють на сцену.", "The equipment and place-type catalog: 50 types, parameters, 3D models. Objects reach the scene from here.") },
            { sel: ["#checksBlock", "#rightBody"], kind: "read", title: P("Перевірки", "Checks"), text: P("Модель перевіряється під час правки: перетини, вихід за контур, проходи, висота, вага. Заборона блокує дію, попередження лише повідомляє.", "The model is checked while editing: overlaps, outside the outline, aisles, height, weight. A block stops the action, a warning only informs.") },
            { sel: "#draftChip", kind: "read", title: P("Чернетка", "Draft"), text: P("Зміни живуть у чернетці й зберігаються автоматично. Чип показує, скільки об'єктів змінено проти діючої версії.", "Changes live in the draft and are saved automatically. The chip shows how many objects differ from the active version.") },
            { sel: "#btnPublish", kind: "read", title: P("Застосування в Odoo", "Applying to Odoo"), text: P("«Опублікувати» показує план змін у Odoo; лише після підтвердження створюються й оновлюються локації. Публікує менеджер.", "“Publish” shows the plan of changes in Odoo; locations are created and updated only after confirmation. Done by a manager.") },
            { sel: "#btnHistory", kind: "read", title: P("Історія версій", "Version history"), text: P("Версії й контрольні точки: «Переглянути» порівняє схему з поточною, «Відновити» поверне чернетку (поточна збережеться окремо).", "Versions and checkpoints: “View” compares the plan with the current one, “Restore” returns the draft (the current one is saved separately).") },
            { sel: ["#menu-help", "#menu-lang", "#menuExtra"], kind: "read", title: P("Інструкція, тури, мова", "Help, tours, language"), text: P("Меню «Ще» містить «Інструкцію» (36 тем) і «Тури». Кнопка «UK/EN» перемикає мову інтерфейсу й підказок.", "The “More” menu holds “Help” (36 topics) and “Tours”. The “UK/EN” button switches the language of the interface and hints.") },
        ],
    },
    {
        id: "basic",
        title: P("Основи роботи", "The basics"),
        desc: P("Камера, виділення, скасування, збереження.", "Camera, selection, undo, saving."),
        steps: [
            { sel: "#vtools", kind: "read", title: P("Інструменти сцени", "Scene tools"), text: P("«3D»/«План», «Вписати», «Лінійка», «Підписи». Лінійка (клавіша M) міряє відстань між двома точками.", "“3D”/“Plan”, “Fit”, “Ruler”, “Labels”. The ruler (key M) measures the distance between two points.") },
            { sel: "#vp", kind: "do", act: { select: "*" }, title: P("Виділіть об'єкт", "Select an object"), text: P("Клацніть по об'єкту. Ctrl+клік додає до виділення, Shift+рамка в «Плані» виділяє кілька.", "Click an object. Ctrl+click adds to the selection, Shift+box in Plan selects several.") },
            { sel: "#modeSeg", kind: "do", act: { mode: "edit" }, title: P("Режим редагування", "Edit mode"), text: P("Увімкніть «Редагування»: тепер об'єкти можна переміщувати, повертати (Alt+R), видаляти (Del).", "Turn on “Edit”: now objects can be moved, rotated (Alt+R), deleted (Del).") },
            { sel: ".s3-undo, #btnUndo, #vtools", kind: "read", title: P("Скасування й повтор", "Undo and redo"), text: P("Ctrl+Z скасовує, Ctrl+Shift+Z чи Ctrl+Y повторює; історія спільна для всіх змін у цьому сеансі.", "Ctrl+Z undoes, Ctrl+Shift+Z or Ctrl+Y redoes; the history is shared by all changes in this session.") },
            { sel: ["#menu-saveAll", "#storeTag"], kind: "read", title: P("Збереження", "Saving"), text: P("Зміни зберігаються самі. Бірюзові позначки «не збережено» зникають після запису; «Зберегти все» робить це негайно.", "Changes are saved by themselves. Teal “unsaved” marks vanish after saving; “Save all” does it at once.") },
            { sel: "#vp", kind: "read", title: P("Гарячі клавіші", "Hotkeys"), text: P("Повний список — у меню «Ще → Гарячі клавіші».", "The full list is under “More → Hotkeys”.") },
        ],
    },
    {
        id: "rack",
        mutates: true,
        title: P("Стелаж: від порожнього місця до комірок", "A rack: from empty floor to cells"),
        desc: P("Тур змінює дані — у навчальній копії: поставити стелаж, змінити яруси, побачити комірки й перевірки.", "This tour changes data — in a training copy: place a rack, change tiers, see cells and checks."),
        steps: [
            { sel: "#modeSeg", kind: "do", act: { mode: "edit" }, title: P("Режим редагування", "Edit mode"), text: P("Для цього туру потрібне «Редагування».", "This tour needs “Edit”.") },
            { sel: TAB("slots"), kind: "do", act: { tab: "slots" }, title: P("Місця", "Places"), text: P("Вкладка «Місця» містить шаблони: палетний стелаж, полиці, консолі, місця на підлозі.", "The “Places” tab holds templates: pallet rack, shelves, cantilevers, floor spots.") },
            { sel: "#vp", kind: "do", act: { rack: true }, title: P("Поставте стелаж", "Place a rack"), text: P("Натисніть «Палетний стелаж» і клацніть на сцені. «Показати мені» ставить стелаж у центрі виду.", "Press “Pallet rack” and click the scene. “Show me” places a rack at the view centre.") },
            { sel: "#rightBody", kind: "read", title: P("Властивості ряду", "Row properties"), text: P("Праворуч — габарит, пролети, яруси, навантаження, префікс коду. Усе змінюється одразу на сцені.", "On the right — size, bays, tiers, load, code prefix. Everything changes on the scene at once.") },
            { sel: "#rightBody", kind: "do", act: { levels: 3 }, title: P("Змініть число ярусів", "Change the number of tiers"), text: P("Поставте «Ярусів» = 3. «Показати мені» робить це за вас.", "Set “Tiers” = 3. “Show me” does it for you.") },
            { sel: ["#cellsBox", "#rightBody"], kind: "read", title: P("Комірки й коди", "Cells and codes"), text: P("Кожне місце дає комірки з кодами за правилом адресації. У Odoo вони стануть локаціями після публікації.", "Each place gives cells with codes by the addressing rule. They become Odoo locations after publishing.") },
            { sel: ["#checksBlock", "#rightBody"], kind: "read", title: P("Перевірки", "Checks"), text: P("Перевірки одразу показують, чи вміщується стелаж у контур і чи не перетинає сусідів.", "Checks immediately show whether the rack fits the outline and does not overlap neighbours.") },
            { sel: "#draftChip", kind: "read", title: P("Лічильник чернетки", "Draft counter"), text: P("Чернетка змінена; опублікувати змінене можна лише з робочого варіанта, а не з навчальної копії.", "The draft is changed; changes can be published only from a working variant, not from a training copy.") },
        ],
    },
    {
        id: "import",
        title: P("Імпорт і експорт", "Import and export"),
        desc: P("Структура з Odoo, файли XLSX/CSV, експорт.", "Structure from Odoo, XLSX/CSV files, export."),
        steps: [
            { sel: MENU("importLocations"), kind: "do", act: { open: true }, title: P("«Імпорт локацій…»", "“Import locations…”"), text: P("Відкрийте «Ще» й оберіть «Імпорт локацій…»: джерело — файл XLSX/CSV або структура складу з Odoo.", "Open “More” and choose “Import locations…”: the source is an XLSX/CSV file or the warehouse structure from Odoo.") },
            { sel: MENU("parseCodes"), kind: "read", title: P("Розбір кодів", "Code parsing"), text: P("Коди з Odoo розкладаються за маскою на зону, ряд, секцію й ярус; нерозпізнані йдуть у лоток «Не розміщено».", "Odoo codes are split by a mask into zone, row, bay and tier; unrecognised ones go to the “Not placed” tray.") },
            { sel: TAB("tray"), kind: "read", title: P("Лоток «Не розміщено»", "The “Not placed” tray"), text: P("Звідти місця тягнуться на сцену або розкладаються автоматично.", "Places are dragged from there onto the scene or laid out automatically.") },
            { sel: MENU("exportLocations"), kind: "read", title: P("Експорт", "Export"), text: P("Експорт у CSV/XLSX «туди й назад»: файл можна виправити в Excel й імпортувати знову.", "Export to CSV/XLSX “there and back”: edit the file in Excel and import it again.") },
        ],
    },
    {
        id: "scratch",
        title: P("Склад «з нуля»", "A warehouse from scratch"),
        desc: P("Майстер: контур, колони, зони, перші ряди.", "The wizard: outline, columns, zones, first rows."),
        steps: [
            { sel: "#btnNewSite", kind: "read", title: P("Нова площадка", "A new site"), text: P("«Нова площадка» створює порожню площадку; майстер «З нуля» проведе через контур, колони, зони й перші ряди.", "“New site” creates an empty site; the “From scratch” wizard guides you through outline, columns, zones and first rows.") },
            { sel: [TAB("wizard"), "#menu-wizard", "#menuMore summary"], kind: "read", title: P("Майстер «З нуля»", "The “From scratch” wizard"), text: P("Кроки майстра зберігаються, тож можна припинити й повернутися пізніше.", "The wizard steps are saved, so you can stop and come back later.") },
            { sel: MENU("autolayout"), kind: "read", title: P("Авторозкладка", "Auto-layout"), text: P("Після зон запропонує розкласти стелажі за ширинами проходів і технікою.", "After the zones it proposes laying out racks by aisle widths and handling equipment.") },
        ],
    },
    {
        id: "address",
        title: P("Адресація кодів", "Code addressing"),
        desc: P("Як формуються коди комірок і локацій Odoo.", "How cell codes and Odoo locations are built."),
        steps: [
            { sel: "#vp", kind: "do", act: { select: null }, title: P("Властивості площадки", "Site properties"), text: P("Зніміть виділення (Esc): праворуч — властивості площадки, серед них «Адресація кодів».", "Clear the selection (Esc): the site properties are on the right, including “Code addressing”.") },
            { sel: ["#rightBody"], kind: "read", title: P("Маска коду", "The code mask"), text: P("Маска, напр. «{зона}-{ряд}-{секція}-{ярус}», задає імена комірок і штрихкоди локацій.", "A mask like “{zone}-{row}-{bay}-{tier}” sets cell names and location barcodes.") },
            { sel: ["#rightBody"], kind: "read", title: P("Перенумерація", "Renumbering"), text: P("Опубліковані коди за замовчуванням не змінюються; перенумерація всіх — лише менеджер, із попередженням про нові етикетки.", "Published codes stay by default; renumbering all is for a manager only, with a warning about new labels.") },
        ],
    },
    {
        id: "putaway",
        title: P("Правила розміщення", "Putaway rules"),
        desc: P("Куди Odoo кладе товар і що пополняти.", "Where Odoo puts goods and what to replenish."),
        steps: [
            { sel: MENU("rules"), kind: "do", act: { open: true }, title: P("Правила розміщення", "Putaway rules"), text: P("«Ще → Правила розміщення»: товар чи категорія → куди покласти; тут же min/max поповнення.", "“More → Putaway rules”: product or category → where to put; min/max replenishment too.") },
            { sel: ["#rightBody"], kind: "read", title: P("Місткість і категорії", "Capacity and categories"), text: P("Категорії зберігання й ємність комірки впливають на перевірку «чи вміститься».", "Storage categories and cell capacity feed the “does it fit” check.") },
            { sel: ["#btnPublish"], kind: "read", title: P("У Odoo — лише публікацією", "In Odoo — by publishing only"), text: P("Правила потрапляють в Odoo так само, як локації: план, підтвердження, одна транзакція з відкатом.", "Rules reach Odoo like locations: plan, confirmation, one transaction with rollback.") },
        ],
    },
    {
        id: "apply",
        title: P("Застосування в Odoo", "Applying to Odoo"),
        desc: P("План змін, підтвердження, журнал і відкат.", "Plan of changes, confirmation, log and rollback."),
        steps: [
            { sel: "#btnPublish", kind: "read", title: P("План", "The plan"), text: P("«Опублікувати» будує план: що створиться, перейменується, архівується; блокувальні проблеми видно одразу.", "“Publish” builds the plan: what will be created, renamed, archived; blocking issues show at once.") },
            { sel: "#s6Variants, #menu-variants", kind: "read", title: P("Лише активний варіант", "Only the active variant"), text: P("Застосовується завжди активний варіант; навчальна копія не публікується.", "The active variant is always the one applied; a training copy is never published.") },
            { sel: MENU("planLog"), kind: "read", title: P("Журнал і відкат", "Log and rollback"), text: P("«Журнал публікацій» показує операції; відкат можливий, поки створене не використано.", "The “Publication log” shows operations; rollback is possible while created records are unused.") },
            { sel: "#btnHistory", kind: "read", title: P("Версії", "Versions"), text: P("Кожне застосування — нова версія зі знімком; до неї можна повернути чернетку.", "Each applying is a new version with a snapshot; the draft can be returned to it.") },
        ],
    },
    {
        id: "find",
        title: P("Пошук і залишки", "Search and stock"),
        desc: P("Код, штрихкод, товар; теплові карти.", "Code, barcode, product; heat maps."),
        steps: [
            { sel: TAB("search"), kind: "do", act: { search: true }, title: P("Вкладка «Пошук»", "The “Search” tab"), text: P("Відкрийте «Пошук»: «Перейти до місця» за кодом або штрихкодом і «Де лежить» за товаром.", "Open “Search”: “Go to a place” by code or barcode and “Where is it” by product.") },
            { sel: ["#s3Goto", "#leftBody"], kind: "read", title: P("Перехід по коду", "Go to a code"), text: P("Введіть код (напр. PLT-01A) і Enter: камера наїде на місце, відкриється картка із залишками.", "Type a code (e.g. PLT-01A) and Enter: the camera zooms in and the card with stock opens.") },
            { sel: ["#s3Metric", ".s3-tools"], kind: "read", title: P("Показник", "Metric"), text: P("«Показник» фарбує комірки за заповненістю, віком запасу чи рухом; легенда показує кількість у класах.", "“Metric” paints cells by fill, stock age or movement; the legend shows counts per class.") },
        ],
    },
    {
        id: "labels",
        title: P("Етикетки", "Labels"),
        desc: P("Вибір комірок, розкладка аркуша, ZPL, PDF.", "Cell selection, sheet layout, ZPL, PDF."),
        steps: [
            { sel: MENU("labels"), kind: "do", act: { open: true }, title: P("«Етикетки…»", "“Labels…”"), text: P("Оберіть комірки (ряд, зона, виділення), вміст (код, штрихкод, QR) і розкладку аркуша.", "Choose cells (row, zone, selection), content (code, barcode, QR) and the sheet layout.") },
            { sel: ["#rightBody"], kind: "read", title: P("З картки ряду", "From the row card"), text: P("Блок «Етикетки» у властивостях ряду друкує його комірки одним кліком.", "The “Labels” block in the row properties prints its cells in one click.") },
            { sel: MENU("labels"), kind: "read", title: P("Формати", "Formats"), text: P("PDF формує сервер; ZPL, CSV і PNG — у браузері.", "The server builds PDF; ZPL, CSV and PNG are built in the browser.") },
        ],
    },
    {
        id: "docs",
        title: P("Документи", "Documents"),
        desc: P("Специфікація стелажів, план, експорт.", "Rack specification, plan, export."),
        steps: [
            { sel: ["#menu-spec", "#menu-planDoc", "#menuMore summary"], kind: "read", title: P("Документи", "Documents"), text: P("«Ще → Специфікація стелажів…» і «План (PDF, PNG)…»: документи будуються з поточної чернетки; таблиці відкриваються в Excel.", "“More → Rack specification…” and “Plan (PDF, PNG)…”: documents are built from the current draft; tables open in Excel.") },
            { sel: MENU("exportLocations"), kind: "read", title: P("Експорт таблиць", "Table export"), text: P("Той самий файл можна відкрити в Excel, виправити й імпортувати назад.", "The same file can be opened in Excel, fixed and imported back.") },
            { sel: ["#btnHistory"], kind: "read", title: P("Документ версії", "A version document"), text: P("Знімок версії можна завантажити й порівняти зі схемою.", "A version snapshot can be downloaded and compared with the plan.") },
        ],
    },
    {
        id: "team",
        title: P("Командна робота", "Teamwork"),
        desc: P("Варіанти, коментарі й задачі, блокування зон.", "Variants, comments and tasks, zone locks."),
        steps: [
            { sel: TAB("variants"), kind: "do", act: { variants: true }, title: P("Варіанти планування", "Layout variants"), text: P("Вкладка «Варіанти»: «Як є» і «Проєкт A/B…». «Створити з поточного» копіює чернетку; «Зробити активним» перемикає, не втрачаючи правок.", "The “Variants” tab: “As is” and “Project A/B…”. “Create from current” copies the draft; “Make active” switches without losing edits.") },
            { sel: ["#s6VarCmp", "#leftBody"], kind: "read", title: P("Порівняння", "Comparison"), text: P("Два варіанти поряд: місць, палетомісць, площа підлоги, об'єм, ємність, операції плану й різниця.", "Two variants side by side: places, pallet places, floor area, volume, capacity, plan operations and the difference.") },
            { sel: TAB("comments"), kind: "do", act: { comments: true }, title: P("Коментарі й задачі", "Comments and tasks"), text: P("Вкладка «Коментарі»: список із фільтрами; значки на сцені — синій нотатка, помаранчевий відкрита задача, сірий усе вирішено.", "The “Comments” tab: a list with filters; scene badges — blue a note, orange an open task, grey all resolved.") },
            { sel: ["#s6Comments", "#rightBody"], kind: "read", title: P("Додати коментар", "Add a comment"), text: P("Виділіть об'єкт і додайте нотатку або задачу «перевірити на місці». У Odoo задача з виконавцем стає його завданням.", "Select an object and add a note or a “check on site” task. In Odoo a task with an assignee becomes their activity.") },
            { sel: ["#s6LockList", "#rightBody"], kind: "read", title: P("Блокування зон", "Zone locks"), text: P("Вибір об'єкта в режимі редагування бере його зону на 5 хвилин. Червоний значок — зона зайнята іншим, зелений — вами.", "Selecting an object in edit mode takes its zone for 5 minutes. A red badge — the zone is held by someone else, green — by you.") },
        ],
    },
];

export const TOUR_BY_ID = Object.fromEntries(TOURS.map((tr) => [tr.id, tr]));
