/** @odoo-module **/
// UI-07 `diag.js`: вкладка «Діагностика» — 16 циліндрів (пороги з паспорта `th`) і 22 допоміжні системи.
// Порт `buildDiag`/`renderDiag` (`b_sim.js:953–1011`); значення — зі `store`, відхилення `dev` рахує бекенд (R-03).

import { fmt, setCls, setText } from "./util";
import { CYL } from "./store";

export function makeDiag({ root, store, vpTxt }) {
    const S = store.S;
    const V = store.V;
    const th = () => store.th;
    const q = (s) => root.querySelector(s);
    let built = false;
    const cylRows = [];
    const auxRows = [];
    const run = () => S.rpm > 1200;

    /** [назва, стан()→[текст, клас], параметри()] — 22 системи (`b_sim.js:955`). */
    const AUX = [
        ["Маслосистема", () => (V.oilLvl < th().oil_min_pct + 5 ? ["Попередження", "warn"] : ["Норма", "ok"]), () => "картер " + fmt(V.oilLvl, 1) + " %, p " + fmt(V.pOil, 1) + " бар, t " + fmt(V.tOil, 0) + " °C, " + fmt(V.oilCons, 2) + " г/кВт·год"],
        ["Автодолив масла", () => (S.topup ? ["Працює", "warn"] : ["Очікування", ""]), () => "свіже " + fmt(V.oilFresh, 0) + " %, відпрацьоване " + fmt(V.oilWaste, 0) + " %"],
        ["Насос ВТ", () => (V.pHT.run ? ["Працює", "ok"] : ["Зупинено", ""]), () => fmt(V.pHT.f, 1) + " Гц, " + fmt(V.pHT.I, 1) + " А, p " + fmt(V.pExpHT, 2) + " бар"],
        ["Насос опалення", () => (V.pHe.run ? ["Працює", "ok"] : ["Зупинено", ""]), () => fmt(V.pHe.f, 1) + " Гц, " + fmt(V.pHe.I, 1) + " А, " + fmt(V.flow, 1) + " м³/год"],
        ["Насос НТ", () => (V.pLT.run ? ["Працює", "ok"] : ["Зупинено", ""]), () => fmt(V.pLT.f, 1) + " Гц, " + fmt(V.pLT.I, 1) + " А, " + fmt(V.tLTin, 0) + "/" + fmt(V.tLTout, 0) + " °C"],
        ["Змішувальний клапан зворотки", () => (V.cap < 0.995 ? ["Обмеження", "warn"] : V.tRet > th().ret_set_c - 4 ? ["Увага", "warn"] : ["Норма", "ok"]), () => "клапан " + fmt(V.mixPos, 0) + " %, зворотка " + fmt(V.tRet, 1) + " °C (уставка ≤ " + fmt(th().ret_set_c, 0) + ")"],
        ["Розширювальні баки", () => ["Норма", "ok"], () => "ВТ " + fmt(V.pExpHT, 2) + ", НТ " + fmt(V.pExpLT, 2) + ", опалення " + fmt(V.pExpH, 2) + " бар"],
        ["Градирня ВТ", () => (S.fan > 1 ? ["Працює", "ok"] : ["Очікування", ""]), () => fmt(V.fan, 0) + " %, " + fmt(V.qCooler, 0) + " кВт"],
        ["Градирня НТ", () => (S.fanLT > 1 ? ["Працює", "ok"] : ["Очікування", ""]), () => fmt(V.fanLT, 0) + " %, " + fmt(V.qLT, 0) + " кВт"],
        ["Турбокомпресор / інтеркулер", () => (S.rpm > 1200 ? ["Працює", "ok"] : ["Зупинено", ""]), () => fmt(V.tcRpm, 0) + " об/хв, p наддуву " + fmt(V.pBoost, 2) + " бар, t суміші " + fmt(V.tAirOut, 0) + " °C"],
        ["Каталізатор", () => (V.dpCat > 18 ? ["Увага", "warn"] : ["Норма", "ok"]), () => fmt(V.tE1, 0) + " → " + fmt(V.tCatOut, 0) + " °C, ΔP " + fmt(V.dpCat, 1) + " мбар"],
        ["Заслінка вихлопу", () => (V.bypass > 0.9 ? ["В обхід", "warn"] : V.bypass < 0.1 ? ["На ТО", "ok"] : ["Перехід", "warn"]), () => "привід " + fmt(V.bypass * 100, 0) + " %"],
        ["Аналіз викидів", () => (V.nox > th().nox_limit || V.co > th().co_limit ? ["Перевищення", "alarm"] : ["Норма", "ok"]), () => "NOx " + fmt(V.nox, 0) + "/" + fmt(th().nox_limit, 0) + ", CO " + fmt(V.co, 0) + "/" + fmt(th().co_limit, 0) + " мг/нм³"],
        ["Газова рампа, valve proving", () => (V.gasP < th().gas_min_bar ? ["Аварія", "alarm"] : vpTxt()), () => "p " + fmt(V.gasP, 2) + " бар, ΔP фільтра " + fmt(V.dpFilter, 0) + " мбар, YV1/YV2 " + (S.valves ? "відкр." : "закр.")],
        ["Повітряний фільтр", () => (V.airDp > 12 ? ["Увага", "warn"] : ["Норма", "ok"]), () => "ΔP " + fmt(V.airDp, 1) + " мбар (поріг 15)"],
        ["Вентиляція контейнера", () => (V.fanSup > 1 ? ["Працює", "ok"] : ["Очікування", ""]), () => "вент. " + fmt(V.fanSup, 0) + " %, жалюзі " + fmt(V.louver, 0) + " %, t " + fmt(V.tCont, 1) + " °C"],
        ["Газоаналізатор", () => (V.lel >= th().lel_alarm_pct ? ["Аварія", "alarm"] : V.lel >= th().lel_warn_pct ? ["Попередження", "warn"] : ["Норма", "ok"]), () => fmt(V.lel, 1) + " % НКПР (" + fmt(th().lel_warn_pct, 0) + " / " + fmt(th().lel_alarm_pct, 0) + " %)"],
        ["Пожежна сигналізація і гасіння", () => (S.fire ? ["Пожежа", "alarm"] : S.ext === "ready" ? ["Норма", "ok"] : ["Спрацювало", "warn"]), () => "балон " + fmt(S.extLevel, 0) + " %"],
        ["Контур аварійного стопу", () => (S.estopLoop ? ["Замкнений", "ok"] : ["Розімкнений", "alarm"]), () => "шафа, двері, зовнішня"],
        ["Захист ROCOF / вектор. зсув", () => (S.rocofFlag ? ["Спрацював", "alarm"] : ["Норма", "ok"]), () => "уставки df/dt 1,0 Гц/с, Δφ 12°"],
        ["Стартер, АКБ 24 В, ЗП", () => (V.batV < th().bat_min_v ? ["Попередження", "warn"] : ["Норма", "ok"]), () => "АКБ " + fmt(V.batV, 1) + " В, ЗП " + fmt(V.batI, 1) + " А, пусків " + fmt(S.starts, 0)],
        ["АРН, захисти генератора", () => (V.Ipct > 105 ? ["Увага", "warn"] : ["Норма", "ok"]), () => "збудження " + fmt(V.excI, 1) + " А, cos φ " + fmt(V.cos, 2) + ", I/Iном " + fmt(V.Ipct, 0) + " %"],
        ["Лічильники (TEDOM-1, тепло, газ)", () => ["Норма", "ok"], () => fmt(V.eTot, 0) + " кВт·год · " + fmt(V.hmTot, 1) + " Гкал · " + fmt(S.gasTotal, 0) + " м³"],
    ];

    function build() {
        const tb = q("#cyl-table tbody");
        tb.textContent = "";
        cylRows.length = 0;
        const n = store.cyl.length || CYL.length;
        for (let i = 0; i < n; i++) {
            const tr = document.createElement("tr");
            if (i === 8) {
                tr.className = "sep";
            }
            const cells = [];
            for (let k = 0; k < 7; k++) {
                const td = document.createElement("td");
                if (k > 0 && k < 6) {
                    td.className = "n";
                }
                tr.appendChild(td);
                cells.push(td);
            }
            cells[0].textContent = (store.cyl[i] && store.cyl[i].id) || CYL[i];
            cells[0].style.fontWeight = "600";
            tb.appendChild(tr);
            cylRows.push(cells);
        }
        const ab = q("#aux-table tbody");
        ab.textContent = "";
        auxRows.length = 0;
        AUX.forEach((a) => {
            const tr = document.createElement("tr");
            const c1 = document.createElement("td");
            c1.textContent = a[0];
            const c2 = document.createElement("td");
            const bd = document.createElement("span");
            c2.appendChild(bd);
            const c3 = document.createElement("td");
            c3.className = "wrapc";
            tr.append(c1, c2, c3);
            ab.appendChild(tr);
            auxRows.push({ bd, c3, a });
        });
        built = true;
    }

    function render() {
        if (!built) {
            build();
        }
        const t = th();
        const r_ = run();
        let maxDev = 0;
        let maxK = 0;
        let tmin = Infinity;
        let tmax = -Infinity;
        store.cyl.forEach((c, i) => {
            const r = cylRows[i];
            if (!r) {
                return;
            }
            const ad = Math.abs(c.dev);
            if (Number.isFinite(ad)) {
                maxDev = Math.max(maxDev, ad);
            }
            if (Number.isFinite(c.knock)) {
                maxK = Math.max(maxK, c.knock);
            }
            if (Number.isFinite(c.t)) {
                tmin = Math.min(tmin, c.t);
                tmax = Math.max(tmax, c.t);
            }
            const live = r_ && Number.isFinite(c.t);
            setText(r[1], live ? fmt(c.t, 0) : "—");
            const dc = ad > t.cyl_dev_alarm_k ? "alarm" : ad > t.cyl_dev_warn_k ? "warn" : "ok";
            setText(r[2], live && Number.isFinite(c.dev) ? (c.dev > 0 ? "+" : "") + fmt(c.dev, 0) : "—");
            setCls(r[2], "n " + (live && Number.isFinite(c.dev) ? dc : ""));
            const kc = c.knock >= t.knock_alarm ? "alarm" : c.knock >= t.knock_warn ? "warn" : "ok";
            setText(r[3], live ? fmt(c.knock, 0) : "—");
            setCls(r[3], "n " + (live ? kc : ""));
            setText(r[4], live ? fmt(c.kv, 1) : "—");
            setCls(r[4], "n " + (live && store.stateOf["cyl/" + c.id + "/kv"] === "warn" ? "warn" : ""));
            setText(r[5], live ? fmt(c.ms, 2) : "—");
            const pp = (c.plug / t.plug_interval_h) * 100;
            const pc = pp >= 95 ? "alarm" : pp >= 80 ? "warn" : "ok";
            setCls(r[6], Number.isFinite(pp) ? pc : "");
            setText(r[6], Number.isFinite(pp) ? (pp >= 95 ? "Замінити" : pp >= 80 ? "Зношується" : "Норма") + " · " + fmt(c.plug, 0) + " год (" + fmt(pp, 0) + " %)" : "—");
        });
        setText(
            q("#diag-sum"),
            r_ && Number.isFinite(V.cylAvg)
                ? "середня " + fmt(V.cylAvg, 0) + " °C · розкид " + fmt(tmax - tmin, 0) + " К · макс. Δ " + fmt(maxDev, 0) + " К · детонація до " + fmt(maxK, 0)
                : "двигун не працює: показники недоступні"
        );
        setText(
            q("#diag-note"),
            "Кількість циліндрів — допущення: " + fmt(store.unit.cylinders || 16, 0) + " (для 800 кВт ел. типовий V16). Відхилення понад " + fmt(t.cyl_dev_warn_k, 0) + " К — попередження, понад " + fmt(t.cyl_dev_alarm_k, 0) + " К — аварійне; детонація: попередження від " + fmt(t.knock_warn, 0) + ", аварія від " + fmt(t.knock_alarm, 0) + "."
        );
        let bad = 0;
        auxRows.forEach((o) => {
            const r = o.a[1]();
            setText(o.bd, r[0]);
            setCls(o.bd, "bdg " + (r[1] || ""));
            setText(o.c3, o.a[2]());
            if (r[1] === "warn" || r[1] === "alarm") {
                bad++;
            }
        });
        setText(q("#aux-sum"), bad ? "потребують уваги: " + bad : "усі системи в нормі");
    }
    return { render, build, count: () => AUX.length };
}
