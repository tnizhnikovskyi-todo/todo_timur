#!/usr/bin/env node
// Збірка ядра конструктора (CD-29, MERGE.md §4.1): ОДНІ Й ТІ САМІ файли factory3d/core/constructor/* → модуль Odoo і прототип.
// Запускається РОЗРОБНИКОМ, не сервером; результат для модуля комітиться (як static/lib/f3d-loaders).
//
//   node tools/build_core.mjs module [--check]
//       core/constructor/index.js → odoo_addons/td_constructor/static/lib/f3d-core/constructor.esm.js (ESM, без three.js:
//       three передає хост). Оновлює CORE_BUILD у static/src/editor/core_loader.js (скидання кешу браузера). --check — лише
//       перевірити, що закомічена збірка свіжа (код виходу 1, якщо ні).
//   node tools/build_core.mjs proto --out <файл.js>
//       build/constructor/proto/src/main.js (хост прототипу + core/constructor/artifact/*) → IIFE для вставки в HTML
//       (його викликає build/constructor/proto/build.py).
//
// esbuild: `--esbuild-dir <каталог з node_modules/esbuild>` або змінна ESBUILD_DIR; без них — `npm install esbuild` у тимчасовий
// каталог (потрібен доступ до npm-реєстру). Файли core/ імпортують лише один одного (перевіряє tools/test_core.mjs).
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(here, "..");
export const PATHS = {
    coreEntry: join(ROOT, "core/constructor/index.js"),
    moduleOut: join(ROOT, "odoo_addons/td_constructor/static/lib/f3d-core/constructor.esm.js"),
    loaderFile: join(ROOT, "odoo_addons/td_constructor/static/src/editor/core_loader.js"),
    protoEntry: join(ROOT, "build/constructor/proto/src/main.js"),
};
const BANNER = "// Згенеровано tools/build_core.mjs з factory3d/core/constructor/*. НЕ правити вручну: правте core/ і запустіть збірку.\n";

const run = (cmd, args, cwd) => execFileSync(cmd, args, { cwd, stdio: ["ignore", "pipe", "inherit"] }).toString();

export async function loadEsbuild(argv = []) {
    const i = argv.indexOf("--esbuild-dir");
    let dir = i >= 0 ? resolve(argv[i + 1]) : process.env.ESBUILD_DIR;
    if (!dir) {
        const work = mkdtempSync(join(tmpdir(), "f3d-core-"));
        dir = join(work, "esb");
        mkdirSync(dir, { recursive: true });
        run("npm", ["init", "-y"], dir);
        run("npm", ["install", "esbuild"], dir);
    }
    return createRequire(join(dir, "noop.js"))("esbuild");
}

async function bundle(esbuild, o) {
    const res = await esbuild.build({
        entryPoints: [o.entry],
        bundle: true,
        write: false,
        format: o.format,
        target: "es2022",
        charset: "utf8",
        legalComments: "none",
        loader: { ".json": "json" },
        minify: !!o.minify,
        logLevel: "warning",
        ...(o.globalName ? { globalName: o.globalName } : {}),
    });
    return res.outputFiles[0].text;
}

export async function buildModule(esbuild) {
    const code = BANNER + (await bundle(esbuild, { entry: PATHS.coreEntry, format: "esm" }));
    const hash = createHash("sha256").update(code).digest("hex").slice(0, 10);
    return { code, hash };
}

const loaderWithHash = (src, hash) => src.replace(/export const CORE_BUILD = "[^"]*";/, `export const CORE_BUILD = "${hash}";`);

async function main() {
    const argv = process.argv.slice(2);
    const target = argv[0];
    const esbuild = await loadEsbuild(argv);
    if (target === "module") {
        const { code, hash } = await buildModule(esbuild);
        const loaderSrc = readFileSync(PATHS.loaderFile, "utf8");
        if (argv.includes("--check")) {
            const same = existsSync(PATHS.moduleOut) && readFileSync(PATHS.moduleOut, "utf8") === code && loaderSrc === loaderWithHash(loaderSrc, hash);
            console.log(same ? "constructor.esm.js свіжий" : "constructor.esm.js ЗАСТАРІВ: запустіть node tools/build_core.mjs module");
            process.exit(same ? 0 : 1);
        }
        mkdirSync(dirname(PATHS.moduleOut), { recursive: true });
        writeFileSync(PATHS.moduleOut, code);
        writeFileSync(PATHS.loaderFile, loaderWithHash(loaderSrc, hash));
        console.log(`${PATHS.moduleOut} · ${(code.length / 1024).toFixed(0)} КБ · build ${hash}`);
    } else if (target === "proto") {
        const i = argv.indexOf("--out");
        if (i < 0) {
            throw new Error("proto: потрібен --out <файл.js>");
        }
        const minify = argv.includes("--minify");
        const code = await bundle(esbuild, { entry: PATHS.protoEntry, format: "iife", minify });
        writeFileSync(resolve(argv[i + 1]), code);
        console.log(`proto: ${(code.length / 1024).toFixed(0)} КБ${minify ? " (minify)" : ""}`);
    } else {
        console.error("Використання: node tools/build_core.mjs module [--check] | proto --out <файл.js> [--minify]");
        process.exit(2);
    }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
    main().catch((e) => {
        console.error(e);
        process.exit(1);
    });
}
