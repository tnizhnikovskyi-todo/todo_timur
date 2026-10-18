// Складова артефакта (прототип) поверх ядра: адаптер з базою артефакта, приклад площадки, вбудовані діалоги каталогу й публікації.
// Входить лише в збірку прототипу (proto/src/main.js); модуль Odoo цих файлів не містить.
export { ArtifactAdapter, mapOf } from "./adapter_artifact.js";
export { registerArtifactDialogs, computeDiff } from "./dialogs.js";
export { SEED_REV, buildEmptySite, buildSample, fromProto, makeSnapshot } from "./sample.js";
export { createFiles, createStorage } from "./storage.js";
export { registerArtifactChecks } from "./checks_extra.js";
