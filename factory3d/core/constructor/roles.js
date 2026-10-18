// Ролі й блокування редагування (SPEC §8.2, R-11): права — з API-03 `rights`, а не з перемикача. Менеджеру доступний режим
// «Переглянути як роль» (лише UI): сервер усе одно застосовує свої права.
import { ROLES, roleName } from "./data.js";
import { S } from "./state.js";
import { toast } from "./util.js";

/** Ефективна роль перегляду (для менеджера в режимі «Переглянути як»), інакше null. */
export const viewAs = () => (S.rights.is_manager && S.app.viewAs && S.app.viewAs !== "manager" ? S.app.viewAs : null);

export function canEditLayer(ly) {
    if (!ly || S.app.mode !== "edit") {
        return false;
    }
    const va = viewAs();
    if (va) {
        return (ly.edit_roles || []).includes(va);
    }
    if (S.rights.is_manager) {
        return true;
    }
    return ly.rid != null && (S.rights.editable_layer_ids || []).includes(ly.rid);
}
export const canManage = () => S.app.mode === "edit" && S.rights.is_manager && !viewAs();
export const canCatalog = () => {
    if (S.app.mode !== "edit") {
        return false;
    }
    const va = viewAs();
    return va ? va === "technologist" : !!(S.rights.is_manager || S.rights.can_edit_catalog);
};
export const canPublish = () => canManage() && !!S.rights.can_publish;

/** Ролі, що редагують шар (без менеджера): назви українською. */
export const layerRoleNames = (ly) =>
    (ly.edit_roles || []).filter((r) => r !== "manager").map(roleName);

export function lockHint(ly) {
    if (S.app.mode !== "edit") {
        return "Режим перегляду: правка вимкнена. Увімкніть «Редагування».";
    }
    const rs = layerRoleNames(ly);
    return `Шар «${ly.name}» редагує ${rs.length ? rs.join(", ") + " і Менеджер" : "Менеджер"}`;
}

export const toastLock = (ly) => toast(lockHint(ly), "warn");

/** Ролі поточного користувача (для підпису в шапці). */
export const myRoleNames = () => {
    const rs = S.rights.roles || [];
    return rs.length ? rs.map(roleName).join(", ") : "Без ролі";
};
export { ROLES };
