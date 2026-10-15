// Хост «отдельное приложение»: грузит снимок Odoo, открывает проект из хранилища (localStorage, ключи wh-app-*) и монтирует view.
import dataUrl from "../../../prototype/data.json?url";
import "../view/style.css";
import { createModel } from "../core/model.js";
import { openProject } from "../core/project.js";
import { DEMO_REFS, demoBase2, demoProject } from "../core/demo.js";
import { createI18n } from "../i18n/index.js";
import { mountApp } from "../view/shell.js";
import { modKey } from "../view/util.js";
import { createLocalStorage } from "./storage.js";

async function start() {
  const root = document.getElementById("app");
  const storage = createLocalStorage();
  const saved = storage.read("lang");
  const i18n = createI18n(saved === "en" ? "en" : "uk", { mod: modKey() });
  try {
    const res = await fetch(dataUrl);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const bases = { [DEMO_REFS.main]: data, [DEMO_REFS.second]: demoBase2(data.meta) };
    const project = await openProject(storage, { bases, now: data.meta.pulled_at, demo: demoProject });
    const model = createModel(project, storage, { bases, words: () => ({ copy: i18n.t("word.copy"), newZone: i18n.t("word.newZone"), newType: i18n.t("word.newType") }) });
    mountApp(root, { model, i18n });
  } catch (e) {
    root.textContent = `${i18n.t("app.loadFail")}: ${e.message}`;
    console.error(e);
  }
}
start();
