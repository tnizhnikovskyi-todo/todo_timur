# factory3d — 3D-модель меблевого підприємства

Процедурна сцена: уся геометрія будується скриптом із параметрів планування
(зони, ворота, верстати, маршрути). Змінили координати верстата чи кількість
стелажів у `plant/layout.py`, перезапустили, і всі формати перезібралися.

## Логіка планування (150 × 72 м, висота 9 м)

Потік наскрізний, із заходу на схід (I-подібний): сировина заходить через усю
західну стіну, готова продукція виходить через усю східну.

```
Приймання ─► Склади сировини ─► Лінії A–D ─► Сортування ─► Збирання ─► Пакування ─► Склад ГП ─► Відвантаження
(вся західна  плити (портал),     розкрій →      робот         лінія +     столи,        5 рядів     (вся східна
 стіна)       фурнітура, крайка,  крайка →                     6 вайм      термоусадка   стелажів     стіна)
              пакматеріали        присадка
                       └─► Нестинг ─► Дільниця фасадів МДФ (північ) ─► завіси ─► буфер комплектів ─┘
```

Чому так:

- **Приймання й відвантаження на всю ширину** — сім воріт із кожного боку, без
  перетину вхідного й вихідного потоків.
- **Склад плит упритул до розкрою** — колії порталу заходять над підйомними
  столами розкрійних центрів і нестингу, тож навантажувачі в зоні не потрібні.
- **Лінії A–D ідуть прямо на схід**: розкрій → крайкооблицювання → присадка,
  між верстатами рольганги. Усі лінії сходяться на сортувальному роботі, який
  видає деталі на збирання комплектами під замовлення.
- **Фасади окремим потоком**: нестинг ріже МДФ, фасади йдуть у закриту
  фарбувальну дільницю на півночі (вимога пожежної безпеки, своя витяжка крізь
  покрівлю, склад ЛФМ поруч), після завіс потрапляють у буфер комплектів.
- **Збирання → пакування → склад ГП → відвантаження** вишикувані поспіль.
- **Ремонтна дільниця впритул до ліній і збирання**, офіс за нею біля північної
  стіни — далі від шуму й навантажувачів. Компресорна й зарядна біля складу ГП.

Стани (верстат у роботі, простій, зупинено; комірка в нормі, нижче мінімуму,
порожня) задані для прикладу.

## Склад сцени

| Ділянка | Що стоїть |
|---|---|
| Приймання | 7 воріт, коридори розвантаження, стоси плит, палети фурнітури, крайка, вхідний контроль і карантин |
| Склад плит | портал над 98 стосами ДСП/МДФ/ХДФ, вакуумне захоплення |
| Склад фурнітури, крайки, пакматеріалів | 6 стелажів × 6 секцій × 4 яруси (144 комірки), 2 стелажі крайки, фанфолд-картон, плівка, порожні палети |
| Лінії A–D | 2 розкрійні центри, пакетний розкрій, форматно-розкрійний, вертикальна пила, 3 крайкооблицювальні (на A — лазерний агрегат і робот повернення), 4 ЧПК, прохідна присадка, шкантування, рольганги |
| Сортування | роботизована комірка: робот на лінійній колії між стелажами деталей |
| Фасади МДФ | нестинг, шліфування, автомат фарбування, кабіна клею, мембранно-вакуумний прес, фарбувальна камера, сушильна камера, УФ-лакування, встановлення завіс, склад ЛФМ |
| Збирання | автоматична лінія збирання корпусів, 6 ручних вайм, буфер комплектів (візки фурнітури й етажерки фасадів) |
| Пакування | 2 пакувальні столи з палетообмотувачами, розкрій гофрокартону, лінія термоусадки та обв'язки |
| Склад ГП | 5 рядів палетних стелажів × 18 прольотів × 4 яруси |
| Відвантаження | 7 воріт, коридори комплектування, машини |
| Освітлення | 314 LED-світильників по зонах за нормою, 3 щити освітлення, покажчики «Вихід» |
| Вентиляція й опалення | 25 дахових установок з рекуперацією, теплова мережа від котельні, припливна установка й тканинні повітроводи фасадів, витяжні вентилятори |
| Електропостачання | комірки 10 кВ, 2 сухі трансформатори по 1000 кВА, ГРЩ з 11 шаф, 4 розподільні шинопроводи з відгалуженнями до кожного верстата, кабельний лоток, АРМ енергетика |
| Інженерія | аспірація (магістраль між лініями B і C, гілка через фасадну дільницю до рукавного фільтра надворі), кільцева пневмомагістраль, компресорна, зарядна, спринклери, пожежні шафи; надворі котельня на відходах, силос стружки, брикетувальний прес, пожежні резервуари |
| Люди й транспорт | оператори біля працюючих верстатів, комірники, 7 навантажувачів, електротягач із візками, 6 фур |

Статичних «показових» маршрутів у сцені немає: маршрут показується лише для реального виробничого замовлення (вкладка «Виробництво») — нумеровані мітки по верстатах і лінія, по якій біжить точка.

## Реальне обладнання

Кожен верстат і вузол інженерії — конкретна модель виробника з опублікованими
параметрами. Паспорти лежать у `plant/equipment_specs.json` (виробник, модель,
параметри, габарити, посилання на джерела) і показуються в картці об'єкта
(«Паспорт обладнання») та у вкладці «Огляд» → «Парк обладнання». Габарити
процедурних моделей підігнано під паспортні в межах ±20 %, щоб не зламати
планування. Що варто знати:

- Портал STORETEQ P-500 має проліт до 16 м, тому він перекриває лише три ряди
  стосів біля пил; решта склад плит — буфер під навантажувач.
- Для фільтра NESTRO NKJ серійний максимум 32 000 м³/год; на всі верстати заводу
  знадобиться два таких фільтри або проєктна система (у моделі показано один).
- Цифри для обладнання Cefla (автомат фарбування, сушка, лакування, УФ-тунель)
  виробник не публікує — вони з оголошень дилерів про конкретні машини, це
  зазначено в паспорті. Якщо параметр не знайдено в джерелі, його немає в паспорті.

| Обладнання в моделі | Виробник і модель | Ключові параметри | Джерело |
|---|---|---|---|
| SAW-1, SAW-2 | HOMAG SAWTEQ S-310 з підйомним столом (S-310/43/22) | Довжина різу: 4300 мм (ряд 3200 / 3800 / 4300 / 5600); Ширина підйомного столу: 2200 мм; Виліт пилки: 80 мм (опція 95 мм) | [1](https://www.homag.com/en/product-detail/machines/panel-dividing-cutting/panel-dividing-saws/panel-dividing-saw-sawteq-s-310-with-lifting-table) [2](https://www.homag.com/fileadmin/product/paneldividing/brochures/sawteq-s-300/panel-dividing-saw-sawteq-s-300-en.pdf) |
| SAW-3 | HOMAG SAWTEQ S-510 з підйомним столом (S-510/43/22) | Довжина різу: 4300 мм (ряд 3200–6500); Виліт пилки (висота пакета): 150 мм (опція 170 мм); Ширина підйомного столу: 2200 мм | [1](https://www.homag.com/en/product-detail/machines/panel-dividing-cutting/panel-dividing-saws/panel-dividing-saw-sawteq-s-510-with-lifting-table) [2](https://www.homag.com/fileadmin/product/paneldividing/brochures/sawteq-s-500/panel-dividing-saw-sawteq-s-500-en.pdf) |
| SLIDE-1 | Altendorf F 45 | Макс. висота пропилу: 204 мм; Виліт пилки: 154 мм (пилка Ø450); Макс. діаметр пилки: 450 мм | [1](https://www.altendorf.com/en/machines/altendorf-f-45/) |
| VSAW-1 | Striebig EVOLUTION 4224 | Довжина різу: 3300 мм; Висота різу (вертикальний): 2240 мм; Висота різу (горизонтальний): 2100 мм | [1](https://www.striebig.com/en/vertical-saws/evolution) [2](https://www.striebig.com/07_downloads/produktinformationen/datenblaetter/en/datasheet-striebig-evolution-en.pdf) |
| NEST-1 | HOMAG CENTATEQ N-510 /32/22, автоматизація Concept 2H+ | Робоча зона X × Y: 3180 × 2160 мм; Макс. товщина заготовки: 260 мм; Товщина плит для автозавантаження: 6–60 мм | [1](https://www.homag.com/en/product-detail/machines/cnc-machining-centers/cnc-gantry-processing-center-centateq-n-510) [2](https://www.homag.com/fileadmin/product/cnc/brochures/centateq-n-510/cnc-processing-center-nesting-centateq-n-510-en.pdf) |
| GANTRY-1 | HOMAG STORETEQ P-500, вакуумна траверса ST71 X | Ширина прольоту: 5000 мм базово, до 16000 мм; Довжина шляху: 10000 мм базово, до 100000 мм; Швидкість моста: 60 м/хв, до 130 м/хв | [1](https://www.homag.com/en/product-detail/machines/storage-systems/storage-system-storeteq-p-300-p-500) [2](https://www.homag.com/fileadmin/product/automation/brochures/storeteq-p-300-500/storage-systems-storeteq-p-300-500-en.pdf) |
| EDGE-1 | HOMAG EDGETEQ S-500 (airTec, серія 2480–2484) | Швидкість подачі: 16–20 м/хв (опції 25, 30, 35 м/хв); Товщина кромки (рулон): 0,3–3 мм; Товщина кромки (смуги/масив): 0,4–12 (20) мм | [1](https://www.homag.com/fileadmin/product/edge/brochures/edgeteq-s-500-s-500-profiline/Edge-banding-machines-edgeteq-s-500-s-500-profiline-en.pdf) [2](https://wtp.hoechsmann.com/en/lexikon/36866/homag_edgeteq_s-500) |
| EDGE-2, EDGE-3 | HOMAG EDGETEQ S-380 Model 1660 HF | Швидкість подачі: 8–18 м/хв (опція 20 м/хв); Товщина кромки (рулон): 0,3–3 мм; Товщина кромки (смуги/масив): 0,4–15 мм | [1](https://www.homag.com/fileadmin/product/edge/brochures/edgeteq-s-380-s-380-profiline/Edge-banding-machines-edgeteq-s-380-s-380-profiline-en.pdf) |
| CNC-1, CNC-2, CNC-3, CNC-4 | HOMAG CENTATEQ P-110 /31 | Робоче поле X (одиночна / маятникова): 3100 / 1000 мм; Робоче поле Y (Ø25 мм): 1550 мм; Висота заготовки Z: 240 мм | [1](https://www.homag.com/fileadmin/product/cnc/brochures/cnc-processing-centers-centateq-p-110-en.pdf) [2](https://www.homag.com/en/product-detail/machines/cnc-machining-centers/cnc-processing-center-centateq-p-110) |
| BORE-1 | HOMAG DRILLTEQ H-600 (конфігурація 0037) | Розмір заготовки: 2500 × 1300 мм (робочий 2500 × 1000 мм); Товщина заготовки: до 80 мм; Швидкість осей X/Y/Z: 138 / 80 / 50 м/хв | [1](https://www.homag.com/fileadmin/product/cnc/brochures/drillteq-h-600/centres-d-usinage-drillteq-h-600-fr.pdf) [2](https://www.homag.com/en/product-detail/machines/cnc-drilling-and-routing-machining-centers/cnc-processing-center-drillteq-h-600) |
| DOWEL-1 | HOMAG DRILLTEQ D-510 (2500 мм) | Довжина заготовки: 20–2500 мм; Ширина заготовки: 20–800 мм; Товщина заготовки: 10–80 мм | [1](https://www.homag.com/fileadmin/product/cnc/brochures/cnc-drilling-dowel-inserting-machine-DRILLTEQ-D-510-en.pdf) [2](https://www.homag.com/en/product-detail/machines/cnc-drilling-and-dowel-inserting-machines/cnc-drilling-and-dowel-inserting-machine-drillteq-d-510) |
| HINGE-1 | Blum MINIPRESS P (M53.2000EU) | Потужність двигуна: 1,1 кВт; Тиск повітря: 5–7 бар; Витрата повітря: 1,5 л/цикл | [1](https://xcart.wurthlac.com/skin/common_files/files/specs/BM53.2004US-Blum_Minipress-P-Product_Details.pdf) [2](https://publications.blum.com/2024/catalogue/en/631/) |
| SORT-1 | HOMAG SORTBOT R-300 | Стелажі: до 16 по колу, до 3 рівнів; Комірки на рівень: 16 (товщина 16–19 мм) / 14 (19–25 мм); Довжина заготовки: 240–2800 мм | [1](https://www.homag.com/en/product-detail/machines/automation/robot-solutions-for-the-furniture-industry/robot-sorting-cell-sortbot-r-300) [2](https://wtp.hoechsmann.com/en/lexikon/pdf/hom_sortbot_r-300_2023_en.pdf) |
| SAND-1 | SCM (DMC) dmc sd 60 135, 2 агрегати | Робоча ширина: 1350 мм; Товщина заготовки: 4–170 мм; Шліфувальна стрічка: 1370 × 2150 мм | [1](https://wtp.hoechsmann.com/es/lexikon/pdf/scm_dmc_sd_2017_en.pdf) |
| PRESS-1 | Orma AIR SYSTEM ECO 30/14 | Розмір плит: 2840 × 1340 мм; Макс. панель з 3D-облицюванням ПВХ: 2740 × 1240 мм; Висота робочої камери: 60 мм (опція 180 мм) | [1](https://wtp.hoechsmann.com/cz/lexikon/pdf/orm_airsystem_cvm_vacuum_2021_en_ru_fr_it_es.pdf) |
| GLUE-1 | Ardesia AMBER 3 (суха фільтрація) + поворотний візок Criart CBC/9 | Робоча ширина: 3000 мм; Загальна ширина × висота: 3450 × 3250 мм; Фільтрація: інерційні картонні фільтри + Paint Stop | [1](https://www.makxilia.biz/en/product/woodworking-machinery/painting-booths/dry-painting-booth/dry-painting-booth-mod-amber-3-mm-3000x3250-as-per-e-c-rules/) [2](https://www.makxilia.biz/en/product/woodworking-machinery/painting-booths/racks-carriages-etc/different-carriages/zinc-plated-adjustable-rotating-trolley-art-cbc9/) |
| SPRAY-1 | Ardesia DOUBLE 4 (подвійна водяна завіса) | Робоча ширина: 4000 мм; Загальна ширина × висота: 4450 × 3300 мм; Фільтрація: подвійна водяна завіса + небулайзери + Paint Stop | [1](https://www.makxilia.biz/en/product/woodworking-machinery/painting-booths/water-curtain-painting-booths/water-painting-booth-mod-double-4-as-per-e-c-rules-mm-4000x3300/) |
| AUTOSPRAY-1 | Cefla Finishing EASY 2000 DUO D | Робоча ширина: 1300 мм; Швидкість подачі: 2–8 м/хв; Пістолети: 4 (Kremlin AVX, Airmix), 2 контури фарби | [1](https://www.machineseeker.com/cefla-easy+duo/i-22608062) [2](https://www.ceflafinishing.com/en/products/easy-spraying-machines) |
| DRY-1 | Cefla Finishing вертикальна двозонна сушка до лінії EASY 2000 (наступник — Omnidry) | Тип: вертикальна двозонна платформна, тепле повітря; Довжина платформи: 3500 мм; Вентилятори зони випаровування: 2 × 8000 м³/год | [1](https://www.machineseeker.com/cefla-easy+2000/i-22555187) [2](https://www.ceflafinishing.com/en/products/omnidry-vertical-oven) |
| UV-1 | Cefla Finishing (Sorbini) Smartcoater MF-EVO + УФ-сушка UV-R/3 | Робоча ширина: 1300 мм; Товщина заготовки: 3–80 мм; Швидкість подачі: 5–20 м/хв | [1](https://www.werktuigen.com/cefla+%28by+sorbini%29-smartcoater+mf-evo/wt-596-1289) [2](https://www.ceflafinishing.com/en/products/smartcoater-pro) |
| ASMLINE-1 | HOMAG CABTEQ T-200 | Довжина корпусу: 250–2500 мм (опція 3100 мм); Глибина корпусу: 120–800 мм (опція 1000 мм); Висота корпусу: 220–1320 мм | [1](https://www.homag.com/en/product-detail/machines/case-clamps/electric-throughfeed-case-clamp-cabteq-t-200) [2](https://wtp.hoechsmann.com/fr/lexikon/pdf/hom_cabteqs_-200_-250_cabeteqt_-200_-250_2023_en.pdf) |
| BOX-1 | Panotec Nextmode 2.5 (поточний наступник — Nextpro 2.5) | Робоча ширина фанфолду: 2500 мм; Мін. довжина обробки: 480 мм; Товщина картону: 2–7 мм | [1](https://wtp.hoechsmann.com/en/lexikon/pdf/pnt_nextmode_25_en.pdf) [2](https://panotec.com/en/products/nextpro/) |
| PACK-1, PACK-2 | Robopac Rotoplat 508 PDS | Діаметр столу: 1650 або 1800 мм; Швидкість столу: 5–12 об/хв; Макс. маса вантажу: 2000 / 2500 кг | [1](https://pack-trade.com/en/nproduct/palletayzer_robopac_rotoplat_508_pds_hqyvw) |
| PACKLINE-1 | Smipack FP8000CS (L-зварювач) + T652 (тунель) | L-зварювач — рамка: 840 × 710 мм; L-зварювач — висота пакета: до 250 мм; L-зварювач — продуктивність: до 2700 пакетів/год | [1](https://www.smipack.it/products/4/1029/semi-automatic-and-automatic-l-sealers-with-shrink-tunnel?lang=en) [2](https://www.smipack.it/products/4/1043/semi-automatic-and-automatic-l-sealers-with-shrink-tunnel?lang=en) |
| COMPRESSOR | Atlas Copco GA 37 VSD+ FF (×2) + ресивер LV911 900 л | Продуктивність FAD при 7 бар: 14,8–115,0 л/с (0,89–6,9 м³/хв); Макс. тиск: 13 бар; Двигун: 37 кВт (IPM), VSD | [1](https://storage.mtender.gov.md/get/6de37aeb-d954-4d2f-99c9-97a33c8dc183-1649407528882) [2](https://shopct.atlascopco.com/en-GB/products/8101018078/lv911-ce-vessel-900l-11b) |
| DUST-1 | NESTRO Lufttechnik Kompakt-JET-Filter NKJ (32 000 м³/год) | Витрата повітря: 13000–32000 м³/год (4 класи); Площа фільтрування: 81–210 м²; Макс. розрідження: 3800 Па | [1](https://www.nestro.com/de/loesungen/filtersysteme/kompakt_jet_filters/) |
| BOILER | Kalvis K-500M (серія M, шнекова подача) | Теплова потужність: 495 кВт; ККД: 82 % (паливо 35 % вологості); Паливо: тирса, тріска ≤50 мм, деревні відходи, брикети | [1](https://www.kalvis.lt/en/produktas/m-series-boilers-with-volcanic-fuel-supply/) |
| TUGGER-1 | Jungheinrich EZS 350 | Буксирувана маса: 5000 кг; Тягове зусилля: 1000 / 3700 Н; Швидкість з вантажем / без: 8 / 12,5 км/год | [1](https://www.jungheinrich.co.uk/products/new-forklifts/tow-tractors/ezs-350-108324) [2](https://media-live2.prod.scw.jungheinrichcloud.com/resource/blob/2498314/0709eaf0434ec15d22518e83e2a5e74d/ezs-3-2026-specsheet-en-2026-07-pdf-data.pdf) |
| ASM-1, ASM-2, ASM-3, ASM-4, ASM-5, ASM-6 | HOMAG CABTEQ S-250 | Довжина корпусу: 150–2500 мм (опція 3000 мм); Глибина корпусу: 250–700 мм (опція 900 мм); Висота корпусу: 150–1400 мм | [1](https://www.homag.com/en/product-detail/machines/case-clamps/stationary-case-clamp-cabteq-s-250) [2](https://wtp.hoechsmann.com/fr/lexikon/pdf/hom_cabteqs_-200_-250_cabeteqt_-200_-250_2023_en.pdf) |
| FL-1, FL-2, FL-3, FL-4, FL-5, FL-C1, FL-C2 | Jungheinrich EFG 216 | Вантажопідйомність: 1600 кг (центр ваги 500 мм); Висота підйому: 3300 мм стандарт, варіанти 2900–7000 мм; Акумулятор: 48 В / 500 А·год | [1](https://www.jungheinrich.co.uk/products/new-forklifts/forklifts/jungheinrich-electric-forklifts/efg-214-220-2499396) [2](https://media-live2.prod.scw.jungheinrichcloud.com/resource/blob/2584562/7208cbf746b0706c81339af57c697f71/efg-2-2026-specsheet-en-2026-10-pdf-data.pdf) |
| EDGE-1 (у складі) | KUKA KR 120 R2700-2 (KR QUANTEC) | Номінальне навантаження: 120 кг; Максимальне навантаження: 167 кг (при центрі мас 0 мм); Максимальний виліт: 2701 мм | [1](https://www.kuka.com/en-de/products/robotics-systems/industrial-robots/kr-quantec) [2](https://k2tool.ru/downloads/733-broshjura-promyshlennogo-robota-kuka-kr-quantec-kr-120-r2700-2) |
| SPRAY-1 (у складі) | Wagner Cobra 40-10 | Співвідношення тисків: 40:1; Макс. тиск: 250 бар; Об'єм за подвійний хід: 10 см³ | [1](https://spraydirect.co.uk/acatalog/Cobra-Brochure.pdf) |
| PACKLINE-1 (у складі) | Mosca SoniXs MS-6 | Продуктивність: до 52 обв'язок/хв (арка 550 × 500 мм); Розміри арки: від 450 × 400 до 1650 × 1800 мм (13 варіантів); Стрічка PP: 5–15 мм, 0,40–0,90 мм | [1](https://www.mosca.com/en/Produkte/Umreifungsmaschinen/Umreifungsmaschinen/productdetail/sonixs-ms-6-728) [2](https://www.mosca.com/en/product/datasheet/sonixs-ms-6-728/660) |
| UV-1 (у складі) | Cefla Finishing UV-R / 3 | Робоча ширина: 1300 мм; Лампи: 3 верхні, до 120 Вт/см; Швидкість подачі: ≈1,25–21,25 м/хв | [1](https://www.used-machines.com/cefla-uv-r+%2F+3/gm-209-18902) [2](https://www.ceflafinishing.com/en/products/uv-r-uv-oven) |
| BOILER (у складі) | Schuko Compacto CT 2500 75/160 | Продуктивність: 150–200 кг/год; Діаметр брикета: 75 мм; Двигун: 15 кВт | [1](https://www.schuko.de/en/products-systems/briquetting-presses) [2](https://www.schuko.de/fileadmin/content/PDFs/WG_12/Brikettierpressen/briquetting-presses-Compacto-GB.pdf) |

## Електропостачання

Шар «Електропостачання» і вкладка «Енергія» в переглядачі. Електрощитова — у
куті складу ГП біля північної стіни, за сітчастим огородженням (зона `Z-ELEC`).

```
ввід 10 кВ → RM6-1 (комірки 10 кВ) → T1, T2 (сухі, 2 × 1000 кВА) → ГРЩ 0,4 кВ (дві секції + секційний вимикач QS)
   секція 1: QF-3 → ШР-3 фасади · QF-2 → ШР-2 лінії C–D, нестинг, портал · QF-C1 → кабелі: компресорна, аспірація, котельня
   секція 2: QF-1 → ШР-1 лінії A–B, сортування · QF-4 → ШР-4 збирання й пакування · QF-C2 → кабелі: зарядна, освітлення, офіс, вентиляція
   PFC-1, PFC-2 — компенсація реактивної потужності на кожній секції
```

- Чотири розподільні шинопроводи однакові — Canalis KSA 630 А (менших номіналів
  у цьому ряду немає); запас лишається під нові верстати.
- Шинопроводи висять на 6,2 м (під аспірацією й світильниками), спільною трасою
  йдуть від ГРЩ на південь уздовж складу ГП, далі кожен над своєю дільницею.
  Від них відгалужувальні коробки з автоматами й кабелі зверху до кожного верстата.
- Кабельний лоток іде вздовж північної стіни до щитів компресорної й зарядної,
  через стіну — до щита аспірації та котельні надворі.
- Трансформатори взято з резервом N-1: якщо один вимкнуть, секційний вимикач
  замкнеться і другий понесе все навантаження (зараз ≈ 578 кВА з 1000).

Навантаження рахує `plant/energy.py` для 3D-сцени й даних однаково:
встановлена потужність 1 005 кВт, зараз ≈ 561 кВт, cos φ 0.90 → 0.97 з компенсацією.
Потужність підключення верстата береться з паспорта (`connected_kw`), якщо виробник
або дилер її публікує — знайдено для 17 моделей. Для решти в паспорті
записано, чому цифри немає, а в розрахунку стоїть оцінка за аналогами
(у переглядачі позначена «оцінка» і зірочкою). Поточна потужність — за станом
верстата: у роботі, простій (підігрів клею, вакуум) чи зупинка. Тариф у
вкладці умовний.

| Обладнання в моделі | Виробник і модель | Ключові параметри | Джерело |
|---|---|---|---|
| RM6-1 | Schneider Electric RM6 NE-QIQI 24 кВ (моноблок РУ 10 кВ: 2 лінійні вимикачі навантаження I + 2 трансформаторні запобіжники-вимикачі Q) | Номінальна напруга: 12 / 17,5 / 24 кВ (для мережі 10 кВ); Номінальний струм збірних шин: 630 А (або 400 А); Функція I (лінійний вимикач навантаження): 630 А; Ik 20 кА 1 або 3 с (виконання 24 кВ / 630 А) | [1](https://www.more-energy.com.mx/wp-content/uploads/2017/09/AMTED398032EN_web.pdf) [2](https://www.se.com/eg/en/product/RM63NIQI24D2SMEGY/rm6-3-functions-iqi-non-extensible-24-kv-cubicle/) |
| T1, T2 | Schneider Electric Trihal 1000 кВА 10/0,4 кВ, Dyn11, у кожусі IP31 (2 шт.) | Номінальна потужність: 1000 кВА (природне повітряне охолодження AN; +40 % з примусовим AF); Напруга: ВН 10 кВ (клас ізоляції 12 кВ) / НН 400 В (до 433 В); Схема і група з'єднань: Dyn (трикутник / зірка з виведеною нейтраллю), напр. Dyn11 | [1](https://zenex.home.pl/pub/katalogi/schneider/3_aparatura_sn/3_1_transformatory/3_1_1_transformator_zywiczny_resilglas/pdf/katalogi_i_ulotki/trihal_standard_losses_nrjed311119en.pdf) [2](http://www.trinetgrup.ro/cat_schneider/pdf/Trihal.pdf) |
| T1 → Q1, T2 → Q2 | Schneider Electric Canalis KTA 1600 А (алюміній), напр. KTA1600ED4403 | Номінальний струм Ie: 1600 А при 35 °C (97 % при 40 °C); Матеріал провідників: алюміній; Полярність: 3L + N + PE | [1](https://www.se.com/ua/uk/product/download-pdf/KTA1600ED4403) [2](https://electrika.com/catalogues/schneider-electric/schneider-electric--miscellaneous/schneider-electric-miscellaneous/kgkhkvkt/kta1600ed4403/part/352251) |
| QF-1, QF-2, QF-3, QF-4, QF-C1, QF-C2, SWB-1 | Schneider Electric PrismaSeT P (Prisma Plus System P), шафи IP31/IP55 до 4000 А | Номінальний струм: до 4000 А; Струм короткочасної стійкості Icw: 100 кА (дійсне) / 1 с; Ударний струм Ipk: 220 кА | [1](https://www.linkpano.com.tr/en/prismaset-p.html) [2](http://www.ncei-sa.com/wp-content/uploads/2017/10/11-PRISMA-P.pdf) |
| Q1, Q2, QS, SWB-1 | Schneider Electric MasterPact MTZ2 16 H1, 3P, висувний (LV848273) + MicroLogic 5.0 X | Номінальний струм In: 1600 А при 40 °C (номінали датчика 800–1600 А); Гранична відключаюча здатність Icu: 66 кА при 220/415 В і 440 В; Робоча відключаюча здатність Ics: 66 кА (100 % Icu) | [1](https://www.se.com/ua/uk/product/LV848273/) [2](https://www.se.com/ua/uk/product/download-pdf/LV848273) |
| PFC-1, PFC-2 | Schneider Electric PowerLogic VarSet 350 квар, з антирезонансними дроселями 3,8 (190 Гц), верхній ввід, з автоматом (VLVAF5P03517AK) — по одній на секцію шин | Номінальна реактивна потужність: 350 квар при 400/415 В, 50 Гц; Ступені: 50 + 3 × 100 квар (крок 50 квар); Контролер: PowerLogic PFC VPL6 (VarPlus Logic) | [1](https://www.se.com/ua/uk/product/download-pdf/VLVAF5P03517AK) [2](https://www.voltimum.co.uk/products/schneider-electric/energy-management-controller/varset-capacitor-bank-auto-350kvar-dr38-top-entry-400v-50hz-cb-vlvaf5p03517ak) |
| BW-1, BW-2, BW-3, BW-4 | Schneider Electric Canalis KSA 630 А, розподільна секція 3 м з 6 відгалуженнями (KSA630ED4306) | Номінальний струм Ie: 630 А при 35 °C (ряд KSA 500…1000 А); Матеріал провідників: алюміній; Полярність: 3L + N + PE (4 полюси) | [1](https://www.se.com/ua/uk/product/download-pdf/KSA630ED4306) |
| BW-1, BW-2, BW-3, BW-4 | Schneider Electric Canalis KSB160DC4 — відгалужувач 160 А під ComPacT NSX100/160 (ряд KSB…DC4 до 400 А) | Номінальний струм: 160 А при 35 °C (ряд: 160 / 250 / 400 А — KSB160DC4 / KSB250DC4 / KSB400DC4); Апарат захисту: ComPacT NSX100 або NSX160 (замовляється окремо); Сумісність: шинопроводи Canalis KS і KT | [1](https://www.se.com/ua/uk/product/download-pdf/KSB160DC4) [2](https://www.electrika.com/catalogues/Schneider-Electric-Busbar-Trunking/Part-Number-Reference/KSB250DC4/Tap-off-unit-250A-Compact-NS/miscellaneous/ksb400dc4/part/125036) |
| EMS-1, Q1, Q2, QF-1, QF-2, QF-3, QF-4, QF-C1, QF-C2, SWB-1 | Schneider Electric PowerLogic PM5560 (METSEPM5560) | Клас точності: 0,2S (активна енергія, IEC 62053-22); реактивна ±1 %; Вимірювані величини: струм, напруга, частота, P, Q, S, cos φ, енергія, багатотарифний облік; Якість електроенергії: гармоніки до 63-ї | [1](https://www.se.com/ua/uk/product/download-pdf/METSEPM5560) |

## Освітлення

Шар «Освітлення». 314 світильників Signify CoreLine Highbay Gen5 (20 500 лм, 126 Вт,
IP65, DALI-2) на 7,6 м, над мостом портального складу — впритул до ферм. Кількість у
кожній зоні — з розрахунку освітленості методом коефіцієнта використання
(E = N · Φ · UF · MF / A, UF 0,7, MF 0,8) під норму EN 12464-1 для виду робіт; у
стелажних зонах світильники стоять над проходами. Розстановка оминає аспірацію,
витяжні труби, установки вентиляції й колони (`plant/lighting.py`). Три щити
освітлення живляться з кабельного лотка; керування — DALI-маршрутизатори з
датчиками присутності й денного світла, у складах світло зараз приглушене.
Режим «Освітленість відносно норми» фарбує зони.

| Зона | Вид робіт | Норма, лк | Світильників | Розрахунок, лк |
|---|---|---|---|---|
| Приймання | пакування й відвантаження | 300 | 24 | 304 |
| Склад плит | складування | 100 | 12 | 115 |
| Склад фурнітури | стелажні проходи з персоналом | 150 | 5 | 164 |
| Склад крайки | стелажні проходи з персоналом | 150 | 3 | 205 |
| Пакувальні матеріали | складування | 100 | 2 | 161 |
| Розкрій | верстатна обробка деревини | 500 | 27 | 509 |
| Крайкооблицювання | верстатна обробка деревини | 500 | 27 | 549 |
| Присадка | верстатна обробка деревини | 500 | 27 | 549 |
| Сортування деталей | збирання, верстакові роботи | 300 | 12 | 314 |
| Дільниця фасадів МДФ | фарбування, оздоблення | 750 | 91 | 846 |
| Збирання | збирання, верстакові роботи | 300 | 15 | 345 |
| Буфер комплектів | стелажні проходи з персоналом | 150 | 4 | 171 |
| Ремонтна дільниця | збирання, верстакові роботи | 300 | 4 | 366 |
| Пакування | пакування й відвантаження | 300 | 12 | 360 |
| Вихід з пакування | складування | 100 | 3 | 116 |
| Компресорна | компресорна | 200 | 2 | 360 |
| Зарядна станція | заряджання акумуляторів | 200 | 2 | 360 |
| Склад готової продукції | стелажні проходи з персоналом | 150 | 12 | 165 |
| Електрощитова | електрощитова | 200 | 4 | 387 |
| Відвантаження | пакування й відвантаження | 300 | 26 | 315 |

Номери таблиць EN 12464-1:2021 перераховано з публічних таблиць редакції 2011 (значення
лк ті самі); для шліфування, компресорної й зарядної окремого рядка в стандарті немає —
узято найближчий, це зазначено в `plant/lux_norms.json`.

## Вентиляція й опалення

Шар «Вентиляція й опалення» (`plant/ventilation.py`):

- 25 дахових установок Hoval RoofVent RH-9C — приплив і витяжка з рекуперацією
  тепла та водяним нагрівачем. Одна обслуговує до ~800 м², тобто на цех вистачило б
  ~14; взято 25, щоб мати ≈ 2 обміни повітря на годину в цеху з пилом і клеями.
  Місця підібрано так, щоб корпус під покрівлею не зачіпав аспірацію, шинопроводи,
  міст порталу, стелажі й спринклери.
- Теплова мережа від котельні: подача над зворотком, магістраль уздовж будівлі,
  відгалуження до кожної установки. Спринклери й пневмокільце підняті над нею.
- Дільниця фасадів — окрема припливна установка VTS VENTUS на даху і два тканинні
  повітроводи Prihoda над камерами: подає стільки, скільки витягують фарбування й
  сушка.
- Електрощитова й компресорна — настінні вентилятори VENTS OV 4E 500 за
  термостатом; зарядна — вибухозахищений вентилятор і дефлектор на даху (водень).

Зараз (+9 °C надворі) установки подають ≈ 174 800 м³/год і беруть
≈ 322 кВт тепла — 65 % котла. Що варто знати:

- Котельня — два котли Kalvis K-500M каскадом (2 × 495 кВт). Оцінка зимового
  навантаження при −15 °C (`heat_balance()` у `plant/ventilation.py`): огородження
  ≈ 189 кВт, інфільтрація ≈ 109, дахові установки після рекуперації ≈ 247, приплив
  фасадів ≈ 208 — разом ≈ 753 кВт, запас двох котлів ≈ 30 %. Це оцінка з
  припущеними U-коефіцієнтами, не проєктний розрахунок; внутрішні теплонадходження
  від верстатів не враховано.
- Зарядна — вибухозахищений вентилятор Systemair EX 140A-4 (II 2G Ex db eb h IIB+H2 T4 Gb,
  до 644 м³/год). Потрібна витрата за EN IEC 62485-3: Q = 0,055 · n · Igas =
  0,055 · 24 · 40 А = 52,8 м³/год на батарею, 158 м³/год на три (Igas — 40 % струму
  зарядного 100 А, бо виробник зарядного його не публікує). Маркування IIB+H2, а не
  повне IIC — саме для водню; прийнятність підтверджує той, хто класифікує зони.
- Для VTS VENTUS VVS180 виробник не публікує витрату й потужність для конкретного
  виконання — у розрахунку стоїть оцінка; для витяжки фарбування потрібне Ex-виконання.

| Обладнання в моделі | Виробник і модель | Ключові параметри | Джерело |
|---|---|---|---|
| LT-* | Signify (Philips) CoreLine Highbay Gen5 BY121P G5 LED200S/840 PSD WB (код 911401629908) | Світловий потік: 20 500 лм; Потужність: 126 Вт; Світловіддача: 163 лм/Вт | [1](https://www.signify.com/en-gb/prof/indoor-luminaires/high-bay-and-low-bay/high-bay/philips-coreline-highbay-gen5/911401629908_EU/product) |
| LT-HW, LT-EDGE, LT-FG | Signify (Philips) CoreLine Highbay Gen5 BY121P G5 LED200S/840 PSD NB (код 911401629808) | Світловий потік: 20 500 лм; Потужність: 126 Вт; Світловіддача: 163 лм/Вт | [1](https://www.signify.com/en-gb/prof/indoor-luminaires/high-bay-and-low-bay/high-bay/philips-coreline-highbay-gen5/911401629808_EU/product) [2](https://www.signify.com/en-gb/prof/indoor-luminaires/high-bay-and-low-bay/high-bay/philips-coreline-highbay-gen5/911401629708_EU/product) |
| EMERGENCY | Zemper Spazio High Bay LUE4700LX (біла RAL9003) | Світловий потік в аварійному режимі: 680 лм (LUE4700LX), 600 лм (чорна версія LUE4700LXN); Автономність: 1 год; Акумулятор: LiFePO₄ 6,4 В, 1,5 А·год; час заряду 24 год | [1](https://zemper.com/en/producto/spazio-high-bay/) [2](https://www.teknoware.com/emergency-lighting/product/twt3756wk/) |
| LP-1…LP-3 | Helvar Imagine 950 DALI-2 Router (4 лінії DALI) + високоповісний мультисенсор 322 | Лінії DALI: 4 (DALI-2 multi-master application controller); Кількість пристроїв: 512 (128 на лінію: 64 світильники/сервіси + 63 датчики/контроли DALI-2); Струм живлення шини DALI: 4 × 240 мА (гарантовано), 4 × 250 мА (макс.) | [1](https://helvar.com/product/950-dali-2-multi-master-application-controller/) [2](https://lenalighting.com/images/IoT%20komonenty/Karty%20katalogowe/W03021%20Router%20DALI-2%204%20magistrale%20HEL%20IMAGINE%20950%20IoT%20Karta%20katalogowa%20EN.pdf) |
| RV-01…RV-25 | Hoval RoofVent RH-9C (типорозмір 9, водяний нагрівач тип C) | Номінальна витрата повітря: 8000 м³/год (мін. 5000 м³/год); Площа обслуговування однією установкою: 797 м²; Ефективність рекуперації (пластинчастий теплообмінник): 78 % суха / 90 % волога | [1](https://d24wsxjsjg3bg4.cloudfront.net/PRODUCTS/VENTILATION/RoofVent/RoofVent-RC/BA_RoofVent_4214745_v06_en_2024-01-29-124839_rsiq.pdf) [2](https://hoval.com.ua/wp-content/uploads/2023/06/BA_RoofVent_4214745_v05_en.pdf) |
| AHU-1 | VTS Group VENTUS VVS180 (припливно-витяжний секційний агрегат) | Рекомендований діапазон витрати: мін. 8640 м³/год; макс. 18 540 м³/год (з охолоджувачем), 23 400 м³/год (з нагрівачем), 30 600 м³/год (фільтр), 32 400 м³/год (вентилятор); Номінальна витрата: у брошурі не наведено (null) — визначається підбором у програмі виробника; Висота корпусу (один ярус): 1387 мм (внутрішня 1197 мм) | [1](https://vtsgroup.com/files/document-files/3893/IN_Brochure_VENTUS%20VVS,SVS.pdf) |
| AHU-1 (у складі) | Prihoda Текстильний повітророзподільник Prihoda Premium NMI (неповітропроникна тканина), круглий переріз | Матеріал: 100 % поліестер (PES) з вплетеною вуглецевою ниткою (антистатик); Клас реакції на вогонь: B-s1,d0 за EN 13501-1 (протокол класифікації PK-22-213, NMR/NMI/PMI); Поверхнева маса тканини NMI: 200–320 г/м² | [1](https://www.prihoda.com/wp-content/uploads/2022/02/TD-EN.pdf) [2](https://www.eboss.co.nz/assets/literature/287/31528/fabric-ducting-technical-data-usa-prihoda.pdf) |
| EF-ELEC, EF-CMP | VENTS (Вентс, Україна) OV 4E 500 (осьовий настінний вентилятор, код 1009611) | Максимальна витрата: 7060 м³/год; Споживана потужність: 420 Вт; Живлення / струм: 230 В, 50 Гц; 1,95 А | [1](https://www.emas.cz/var/files/255516-elveve0571928.pdf) [2](https://www.onninen.fi/en/vents-axial-fan-ov-4e-500/p/ASM981) |
| EF-CHG | Systemair EX 140A-4 (арт. SA135277), 3~ 400 В, вибухозахищений канальний відцентровий вентилятор | Маркування ATEX: II 2G Ex db eb h IIB+H2 T4 Gb, сертифікат Presafe 16 ATEX 8598 X; Група газів: IIB+H2: гази IIA та IIB, а також водень (H2, газ групи IIC). Це не повний IIC: ацетилен і CS2 не покриваються, для зарядної кімнати вони не потрібні; Зона / категорія / температурний клас: зони 1 і 2, категорія 2G, EPL Gb; T4 (поверхня ≤135 °C). Водень має клас T1, тож T4 підходить із запасом | [1](https://www.zvei.org/fileadmin/user_upload/Verband/Fachverbaende/Batterien/Merkblaetter/Industriebatterien/14e-Leaflet-Ventilation_of_battery_charging_rooms_for_lead_traction_batteries_01.pdf) [2](https://www.agroarbo.nl/bijlage-voorbeeldberekening-van-de-benodigde-hoeveelheid-ventilatie) |

## Дані Odoo (поки демо)

Переглядач показує сцену так, ніби підключена Odoo 19. Дані генерує
`plant/odoo_demo.py` (без Blender: `python -m plant.odoo_demo dist/odoo_demo.json`)
за тими самими правилами наповнення, що й 3D-сцена, тому стан у моделі та в
«Odoo» збігається. Ключі — коди об'єктів сцени (`FUR-R1-S02-L3`, `CNC-2`,
`DOCK-E2`…), структура повторює моделі Odoo:

| Що | Модель Odoo | Де видно в переглядачі |
|---|---|---|
| Залишки по комірках, стосах, полицях, палетах: товар, кількість, партія, упаковка, резерв | `stock.location`, `stock.quant`, `stock.lot`, `stock.quant.package` | клік по місцю зберігання; вкладка «Склад» — пошук товару підсвічує всі місця з кількостями; режим «Заповненість складу» |
| Правила поповнення і закупівлі для комірок нижче мінімуму | `stock.warehouse.orderpoint`, `purchase.order` | картка комірки, «Огляд» |
| Виробничі замовлення і робочі завдання за маршрутами ліній A–D та фасадів | `mrp.production`, `mrp.workorder` | вкладка «Виробництво»: маршрут замовлення нумерованими мітками й лінією в 3D, компоненти й де вони лежать |
| Робочі центри: стан, OEE, втрати часу, поточне завдання, черга | `mrp.workcenter`, `mrp.workcenter.productivity` | клік по верстату; режим «OEE верстатів»; причини простоїв |
| Приймання, відвантаження, комплектація компонентів, розміщення ГП | `stock.picking` | вкладка «Логістика»: ворота, машина, ячейки відбору / розміщення в 3D |
| Замовлення клієнтів | `sale.order` | джерело виробничих замовлень і відвантажень |
| Вхідний контроль | `quality.check` | карантин у зоні приймання, «Огляд» |
| Заявки на ремонт, обладнання (навантажувачі, компресор, аспірація, портал) | `maintenance.request`, `maintenance.equipment` | картки верстатів і обладнання |
| Працівники на дільницях | `hr.employee` | клік по людині |
| Енергоспоживання: лічильники на вводах і фідерах, потужність по верстатах, кВт·год на замовлення | у стандартній Odoo немає — дані з лічильників PowerLogic по Modbus TCP через Odoo IoT або окремий модуль | вкладка «Енергія», картки верстатів, шаф ГРЩ, шинопроводів, трансформаторів; режим «Споживання електроенергії»; кВт·год у картці замовлення |

Поки сторінка відкрита, завдання в роботі просуваються — імітація живого
підключення. Для справжньої бази досить віддати JSON того самого формату
(скриптом через XML-RPC або контролером Odoo) як `odoo_demo.json`; переглядач
міняти не треба.

## Файли

| Файл | Для чого |
|---|---|
| `dist/factory.glb` | Веб, Blender, Unity/Unreal. В об'єктів є властивості `code`, `kind`, `label`, `desc` (glTF extras) |
| `dist/factory.usdz` | Перегляд на iPhone/iPad/Mac (Quick Look, AR). Вісь Y угору, метри |
| `dist/factory.blend` | Вихідна сцена: окрема колекція на кожен шар |
| `dist/index.html` | Переглядач (three.js): види, шари, клік по об'єкту, підписи, маршрути замовлень. Вантажить `factory.glb` і `odoo_demo.json` поруч |
| `dist/factory_viewer.html` | Той самий переглядач одним файлом, модель вбудована. Відкривається подвійним кліком, потрібен лише інтернет для three.js із CDN |
| `dist/odoo_demo.json` | Демо-дані «як із Odoo», вбудовані й в однофайловий переглядач |
| `dist/factory_web.glb` | Квантована копія моделі (KHR_mesh_quantization) — саме вона вбудована в однофайловий переглядач |

## Код

| Модуль | Що в ньому |
|---|---|
| `build_scene.py` | точка входу: збирання сцени, експорт, вбудовування в переглядач |
| `plant/layout.py` | планування: габарити, зони, ворота, верстати (координати, поворот, статус), маршрути |
| `plant/geom.py` | матеріали, збирач мешів, спільні меші, типові вузли (палети, пульти, огорожі, роботи, люди, навантажувачі) |
| `plant/machines.py` | процедурні моделі 24 типів верстатів |
| `plant/site.py` | будівля, склади, інженерія, люди, транспорт, маршрути |
| `plant/odoo_demo.py` | демо-дані у форматі моделей Odoo 19 |
| `plant/equipment.py`, `plant/equipment_specs.json` | паспорти реального обладнання і прив'язка до об'єктів сцени |
| `plant/lighting.py`, `plant/ventilation.py`, `plant/lux_norms.json` | розстановка світильників за нормою, вентиляція й теплова мережа, норми освітленості |
| `plant/energy.py` | схема електропостачання (ГРЩ, траси шинопроводів, відгалуження), розрахунок навантажень і дані лічильників |
| `viewer/index.html` | переглядач |

Однакові об'єкти (верстати одного типу, стелажі, палети, комірки) посилаються
на спільний меш, тож у glTF він зберігається один раз.

## Збирання

```bash
python3 -m venv .venv && .venv/bin/pip install bpy   # Blender як Python-модуль (Python 3.13)
.venv/bin/python build_scene.py dist
```

Для квантованої копії потрібен Node.js (`npx @gltf-transform/cli`). Без нього
в однофайловий переглядач вбудовується повний GLB.

Лише перевбудувати однофайловий переглядач після правок у `viewer/index.html`:

```bash
.venv/bin/python build_scene.py --embed dist/factory_web.glb dist
```

## Переглядач

`index.html` треба відкривати через веб-сервер (`cd dist && python3 -m http.server 8000`),
`factory_viewer.html` — просто подвійним кліком.

Керування: ліва кнопка миші обертає, права зсуває, коліщатко змінює масштаб.
Клік вибирає об'єкт, подвійний клік наближає. Клавіші 1–9 і 0 перемикають
види, Esc знімає вибір.
