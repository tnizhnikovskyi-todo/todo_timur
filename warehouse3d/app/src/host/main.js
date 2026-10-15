// Хост «отдельное приложение»: грузит снимок Odoo, подключает хранилище (localStorage, ключи wh-app-*) и монтирует view.
import dataUrl from "../../../prototype/data.json?url";
import "../view/style.css";
import { createModel } from "../core/model.js";
import { createI18n } from "../i18n/index.js";
import { mountApp } from "../view/shell.js";
import { modKey } from "../view/util.js";

const PREFIX = "wh-app-";

// Хранилище по интерфейсу core/storage.js; доступ к localStorage всегда в try/catch (приватный режим, переполнение)
export function createLocalStorage(ls = globalThis.localStorage) {
  return {
    readonly: false,
    read(name) { try { const v = ls.getItem(PREFIX + name); return v == null ? null : JSON.parse(v); } catch (e) { return null; } },
    write(name, value) { try { ls.setItem(PREFIX + name, JSON.stringify(value)); return "local"; } catch (e) { return "fail"; } },
  };
}

async function start() {
  const root = document.getElementById("app");
  const storage = createLocalStorage();
  const saved = storage.read("lang");
  const i18n = createI18n(saved === "en" ? "en" : "uk", { mod: modKey() });
  try {
    const res = await fetch(dataUrl);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const model = createModel(data, storage, { words: () => ({ copy: i18n.t("word.copy"), newZone: i18n.t("word.newZone"), newType: i18n.t("word.newType") }) });
    mountApp(root, { model, i18n });
  } catch (e) {
    root.textContent = `${i18n.t("app.loadFail")}: ${e.message}`;
    console.error(e);
  }
}
start();
