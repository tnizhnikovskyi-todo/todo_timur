// English dictionary. Same keys as uk.js (checked by test/i18n.test.js).
const plural = (one, other) => ({ one, other });

export default {
  "app.title": "Warehouse Builder",
  "app.loadFail": "Could not load the warehouse data",
  "common.close": "Close",
  "lang.label": "Interface language",
  "top.edit": "✎ Edit",
  "top.done": "Done",

  "plan.viewLabel": "Plan view",
  "plan.svgLabel": "Top view of the warehouse: Odoo locations in hierarchy, colored by fill level",
  "plan.canvasLabel": "3D model of the warehouse",
  "plan.focusOnly": "Show this level only",
  "plan.up": "Level up",
  "plan.zoomIn": "Zoom in",
  "plan.zoomOut": "Zoom out",
  "plan.fit": "Fit the level",
  "plan.loading3d": "Building the 3D model…",
  "plan.fail3d": "Could not build the 3D model. Check that the browser supports WebGL and switch the view again.",
  "lvl.bar": "Location level",
  "lvl.level": "Level {n}",
  "lvl.below": "Level below",
  "lvl.belowOption": "level below…",
  "pick.label": "Click selects",
  "pick.aria": "What a click selects",
  "pick.place": "Place",
  "pick.bay": "Bay",
  "pick.rack": "Row",
  "pick.zone": "Zone",
  "legend.ok": "30% or more",
  "legend.warn": "below 30% · below minimum",
  "legend.bad": "empty",
  "legend.idle": "zone without capacity",
  "legend.new": "new · model only",
  "legend.pend": "not saved",
  "status.hintEdit": "Click — select · {mod}+click — several · drag — move · Shift+drag — marquee · R — rotate row · {mod}+C / {mod}+V — copy / paste · {mod}+D — duplicate · {mod}+Z — undo",
  "status.hint2d": "Click — select (again — level up) · wheel — zoom",
  "status.hint3d": "Click — select (again — level up) · left button — orbit · right button — pan",
  "status.local": "Saved changes are kept in this browser only",
  "status.ro": "View only: the model cannot be saved",
  "status.odoo": "The project is stored in the Odoo database",
  "status.zoneBusy": "{zone} is being edited by {by} until {until}",
  "tip.new": "new place · model only",
  "tip.newPend": "new place · not saved",
  "tip.more": "+ {n} more",
  "tip.empty": "empty",
  "tip.filled": "filled {pct}",
  "tip.low": "below minimum",

  "bar.editing": "Edit mode",
  "bar.hasPending": "The model has unsaved changes",
  "bar.pending": "not saved: {n}",
  "bar.allSaved": "all saved",
  "bar.stats": "places added to the model: {added}, removed: {removed}",
  "bar.saveAll": "Save all",
  "bar.discardAll": "Discard all",
  "bar.undoTitle": "Undo the last unsaved change ({mod}+Z)",
  "bar.undoLabel": "Undo the last unsaved change",
  "bar.types": "Place types",
  "bar.reset": "Reset to Odoo data",

  "n.positions": plural("{n} item", "{n} items"),
  "n.places": plural("{n} place", "{n} places"),
  "n.changes": plural("{n} change", "{n} changes"),
  "n.change": "Change",
  "n.saved": "Saved: {what} · {cnt}",
  "n.savedLocal": "Stored in this browser",
  "n.savedShared": "The model is updated for everyone who opens the page",
  "n.saveFail": "Could not save: {what}",
  "n.saveStale": "The project was changed by another user",
  "n.saveStaleSub": "Your changes are not saved in Odoo. Reload the page to see the current state.",
  "n.zoneLocked": "{zone} is being edited by {by} (until {until}): changes in this zone are blocked",
  "n.discarded": "Unsaved changes discarded: {n}",
  "n.nothingUndo": "Nothing to undo",
  "n.nothingUndoSub": "Only unsaved changes can be undone",
  "n.undone": "Undone: {label}",
  "n.undoneSub": "{mod}+Shift+Z — redo",
  "n.redone": "Redone: {label}",
  "n.nothingRedo": "Nothing to redo",
  "n.nothingSel": "Nothing selected",
  "n.nothingSelSub": "Select an object in the model, then press {mod}+C",
  "n.copied": "Copied: {names}",
  "n.copiedSub": "{mod}+V — paste into the selected place or next to the original",
  "n.clipEmpty": "Clipboard is empty",
  "n.clipEmptySub": "First select an object and press {mod}+C",
  "what.sel": "selection ({n})",
  "what.all": "all changes",
  "what.types": "place types",

  "node.rack": "Row",
  "node.bay": "Bay",
  "node.level": "Level",
  "node.bayleaf": "Stack",
  "form.shelf": "Shelf bay",
  "form.rolls": "Roll rack",
  "form.pallet": "Pallet rack",
  "form.stack": "Floor stack",
  "form.zone": "Floor place",
  "kind.stack": "Board stack",
  "kind.bin": "Hardware bin",
  "kind.shelf": "Shelf",
  "kind.pallet_cell": "Pallet place",
  "kind.kit": "Production kit",
  "kind.area": "Zone",
  "kind.place": "Place",
  "type.FUR": "Hardware shelves",
  "type.EB": "Edge-band rack",
  "type.FG": "Finished goods pallet rack",
  "type.RCK": "Cell rack",
  "type.PLT": "Board stack",
  "type.PAL": "Pallet place",
  "type.CART": "Cart",
  "type.DOCK": "Unloading gate",
  "type.BIG": "Large zone",
  "type.ZONE": "Floor zone",
  "word.copy": "copy",
  "word.newZone": "New zone",
  "word.newType": "New type",
  "unit.m": "m",
  "tag.pend": "not saved",
  "tag.new": "new",
  "tag.fromOdoo": "from Odoo",

  "op.rack": "Added row {name}: {type}, {nb} bays × {nl} levels",
  "op.rackStack": "Added row {name}: {type}, {nb} stacks",
  "op.zone": "Added {type}: {codes}",
  "op.group": "Added zone “{name}”",
  "op.bay": "Added bay {names} × {nl} levels",
  "op.bayStack": "Added stack {names}",
  "op.level": "Added level {name}",
  "op.settp": "Row type: {type}",
  "op.move": "Moved {ref}",
  "op.moveMany": "Moved together: {refs}",
  "op.rotMany": "Rotated by 90°: {refs}",
  "op.rotBack": "{ref}: rotated back",
  "op.rot": "{ref}: rotated by 90°",
  "op.pair": "{a} → {b}",
  "op.dup": "Copied: {pairs}",
  "op.dupN": "Copied: {pairs} ({places})",
  "op.paste": "Pasted into {to}: {pairs}",
  "op.pasteN": "Pasted into {to}: {pairs} ({places})",
  "op.props": "Properties of {ref}: {what}",
  "op.rotTo": "{ref}: rotation {deg}°",
  "op.mass": "Added rows {names}: {type}, {nr} × {nb} × {nl} ({places})",
  "op.grid": "Grid of places {ref}: {nx} × {ny} ({places})",
  "op.align": "Aligned “{mode}”: {refs}",
  "op.distribute": "Distributed {axis}: {refs}",
  "op.groupSel": "Grouped into “{name}”: {refs}",
  "op.ungroup": "Ungrouped {ref}",
  "n.groupParents": "Only objects of one zone can be grouped",
  "n.groupParentsSub": "Select rows or floor places that stand in the same zone",
  "prop.name": "name",
  "prop.pos": "position",
  "prop.rot": "rotation",
  "prop.size": "size",
  "prop.sections": "bays and levels",
  "props.title": "Properties",
  "props.x": "X, m",
  "props.y": "Y, m",
  "props.rot": "Rotation",
  "props.w": "Width, m",
  "props.d": "Depth, m",
  "props.h": "Height, m",
  "props.wMin": "Zone width, m",
  "props.dMin": "Zone depth, m",
  "props.bays": "Bays",
  "props.noteLeaf": "X, Y are measured from the corner of the zone the place stands in. Width and depth are the place's own (before rotation); 90° and 270° swap them. Only changed fields are applied.",
  "props.noteRack": "X, Y are measured from the zone corner. Rotation 180° and 270° puts the bays in reverse order. Bays and levels: extra ones are removed (last bays, top levels), missing ones are added.",
  "props.noteZone": "X, Y are measured from the parent zone corner. A zone cannot be smaller than its contents.",
  "mass.title": "Mass create",
  "mass.rows": "Rows",
  "mass.bays": "Bays",
  "mass.gap": "Aisle between rows, m",
  "mass.orient": "Orientation",
  "mass.orientH": "along X",
  "mass.orientV": "along Y (rotated 90°)",
  "mass.sum": "Will create: {nr} rows, {nb} bays per row, {nl} levels; {places} in total; block {w} × {d} m. “Show” displays them in the model.",
  "mass.sumStack": "Will create: {nr} rows, {nb} stacks per row; {places} in total; block {w} × {d} m. “Show” displays them in the model.",
  "grid.title": "Grid array",
  "grid.nx": "Along X, pcs",
  "grid.ny": "Along Y, pcs",
  "grid.sx": "Step X, m",
  "grid.sy": "Step Y, m",
  "grid.note": "Copies stand in the same zone and get the next free codes; the step is the distance from the start of one place to the start of the next.",
  "align.title": "Align and distribute",
  "align.left": "Left",
  "align.right": "Right",
  "align.top": "Top",
  "align.bottom": "Bottom",
  "align.cx": "Center X",
  "align.cy": "Center Y",
  "align.distx": "Distribute along X",
  "align.disty": "Distribute along Y",
  "align.mx": "along X",
  "align.my": "along Y",
  "group.title": "Grouping",
  "group.group": "Group",
  "group.ungroup": "Ungroup",
  "group.ungroupTitle": "Return the zone contents to its parent zone; the zone disappears",
  "group.note": "The selected objects of one zone move into a new zone with this name. Place codes do not change.",
  "op.unpos": "{ref}: automatic position",
  "op.del": "Removed {ref}",
  "op.delN": "Removed {ref} ({places})",
  "op.delMany": "Removed: {refs}",
  "op.delManyN": "Removed: {refs} ({places})",
  "op.reset": "All model changes reset to Odoo data",
  "op.types": "Place types changed",

  "form.show": "Show",
  "form.save": "Save",
  "form.placeType": "Place type",
  "form.stacks": "Stacks",
  "form.bays": "Bays",
  "form.levels": "Levels",
  "form.count": "Count",
  "form.name": "Name",

  "side.selectLevel": "Select this level",
  "side.selectLevelTitle": "Select level",
  "side.fill": "Fill level",
  "side.rule": "Replenishment rule",
  "side.minmax": "min {min} · max {max}",
  "side.empty": "Empty",
  "side.low": "Below minimum",
  "side.stock": "Stock",
  "side.reserved": "reserved {n}",
  "side.noStock": "Empty.",
  "side.draftNote": "New place: it exists only in the 3D model, not in Odoo yet.",
  "side.unselect": "Clear selection",
  "side.selected": "Selected",
  "side.whole": "Whole warehouse",
  "side.shown": "Level shown",
  "side.fillPct": "fill level {pct}",
  "side.below": "Level below · {n}",
  "side.selectShort": "Select",
  "side.lowN": "{n} min",
  "side.lowList": "Below minimum · {n}",
  "side.min": "min {min}",
  "side.stockOf": "Stock of place {code}",
  "side.editMulti": "Model editing · several selected",
  "side.selectedN": plural("{n} object selected", "{n} objects selected"),
  "side.dragAll": "drag any selected object in the model — they move together: {names}",
  "side.noDrag": "these objects cannot be dragged (rows, floor places and zones inside the visible level can)",
  "side.dupAll": "Duplicate all",
  "side.copy": "Copy",
  "side.rotRacks": "Rotate rows",
  "side.rotRack": "Rotate row",
  "side.delAll": "Remove all · {places}",
  "side.saveSel": "Save selection",
  "side.pending": "Not saved · {n}",
  "side.discard": "Discard",
  "side.selectedHead": "Selected · {n}",
  "side.onlyThis": "Select only this one",
  "side.unpickLabel": "Remove {name} from the selection",
  "side.unpick": "Remove from the selection",
  "side.noteMulti": "{mod}+click in the model adds an object to the selection or removes it. {mod}+C / {mod}+V — copy and paste, {mod}+Z — undo the last unsaved change, {mod}+Shift+Z — redo.",
  "side.edit": "Model editing",
  "side.dup": "Duplicate {name}",
  "side.paste": "Paste {names}",
  "side.del": "Remove {name}",
  "side.saveAll": "Save all",
  "side.saveObj": "Save {name}",
  "side.levelH": "level {h} m",
  "side.addRack": "Add a row",
  "side.addZone": "Add a floor place",
  "side.addGroup": "Add a zone",
  "side.position": "Position",
  "side.overlap": "Overlaps with: {names}. Drag the row to a free spot.",
  "side.manual": "Placed by hand",
  "side.auto": "Automatic",
  "side.rotated": "rotated by 90°",
  "side.offset": "{x}; {y} m from the corner of “{parent}”.",
  "side.dragHintUp": "To drag the row, select a level above it.",
  "side.dragHint": "Drag the row with the mouse in the model.",
  "side.rot90": "Rotate by 90°",
  "side.unpos": "Automatic position",
  "side.rackType": "Row type",
  "side.addStack": "Add a stack",
  "side.addBay": "Add a bay",
  "side.addLevel": "Add a level on top",
  "side.inside": "Inside · {n}",
  "side.delLabel": "Remove {name}",
  "side.delTitle": "Remove from the model (until saved it is only a preview)",
  "side.noteEdit": "“Show” previews the change in the model, but it is not saved yet (teal). “Save” writes the changes of this object. “Duplicate” ({mod}+D) creates a copy next to the selected object with empty places; {mod}+C / {mod}+V — copy and paste elsewhere; {mod}+click — select several objects and drag them together; {mod}+Z — undo the last unsaved change. Nothing changes in Odoo.",

  "types.title": "Storage place types",
  "types.intro": "Size of one section in meters. A change is visible at once on all places of this type and is saved with the “Save types” button.",
  "types.code": "Code",
  "types.name": "Name",
  "types.form": "Construction",
  "types.w": "Width",
  "types.d": "Depth",
  "types.lh": "Level height",
  "types.lv": "Levels",
  "types.lvLabel": "Levels in a new bay",
  "types.places": "Places",
  "types.new": "+ New type",
  "types.unsaved": "There are unsaved type changes",
  "types.allSaved": "All saved",
  "types.discard": "Discard changes",
  "types.save": "Save types",
  "types.inUse": "The type is in use or built in",
  "types.remove": "Delete type",

  "top.warehouse": "Warehouse",
  "node.cell": "Cell",
  "depth.level": "Level",
  "depth.cell": "Cell",
  "depth.inherit": "as in the warehouse",
  "n.projectBroken": "The project could not be read, a copy was saved, the demo project is open",
  "n.projectBrokenNoCopy": "The project could not be read and no copy could be saved, the demo project is open (the old data is untouched)",
  "op.depth": "{ref}: location depth — {depth}",
  "op.cells": "{ref}: cells per level — {n}",
  "form.cells": "Cells per level",
  "side.depthTitle": "Location depth",
  "side.depthWh": "The last level that becomes an Odoo location. Applies to the whole warehouse; a zone can override it.",
  "side.depthZone": "The last level that becomes an Odoo location in this zone.",
  "side.cellsTitle": "Cells per level",
  "side.cellsOn": "The level is split into cells: each is a separate place with the code “level code”-1…N.",
  "side.cellsOff": "The level stays one place: cells appear when the location depth is “Cell” (for the warehouse or a zone).",
  "side.cellOf": "A cell of a level. Change the number of cells in the field below.",
  "help.button": "Help",
  "help.title": "How to work with the 3D warehouse model",
  "help.toc": "Contents",
  "help.back": "Back to the model",
  "help.start.title": "What this is",
  "help.start.html": `
    <p><b>Warehouse Builder</b> is a model of the warehouse built from Odoo storage locations (database snapshot of {date}). Every row, bay, level and floor place in the model is an Odoo location or a new place you added in the model.</p>
    <p>Everything you change in the model concerns <b>the model only</b>: nothing is created or deleted in Odoo. The Odoo data is a snapshot and is not updated in real time.</p>
    <p>The top bar has the warehouse name, the <b>warehouse switch</b>, the <b>2D / 3D</b> switch, the <b>“✎ Edit”</b> button, this <b>“Help”</b> and the <b>UK / EN</b> language switch — your choice of language is remembered in the browser.</p>`,
  "help.view.title": "Viewing the model",
  "help.view.html": `
    <ul>
      <li><b>2D / 3D</b> — the switch in the top bar: a plan view from above or a volumetric model.</li>
      <li><b>Level</b> — the lists above the model (WH › zone › row › bay › level). Pick a level — the rest is hidden and the camera moves closer. The labels in the model and the “Show this level only” button in the right panel do the same. <b>↑</b> — level up, <b>⟲</b> — fit the level, <b>+ / −</b> — zoom.</li>
      <li><b>Mouse in 3D</b>: left button — orbit, right button — pan, wheel — zoom. <b>In 2D</b>: drag — pan the plan, wheel — zoom.</li>
      <li>Hover over a place — a tooltip shows the code, product and fill level.</li>
      <li>The color of a place shows its fill level:</li>
    </ul>`,
  "help.select.title": "Selection",
  "help.select.html": `
    <ul>
      <li><b>Click</b> on the model selects and highlights an object without hiding anything. What exactly is selected is set by the switch <b>“Click selects: Place / Bay / Row / Zone”</b>.</li>
      <li><b>Clicking again</b> on the selected object selects the level above (level → bay → row → zone).</li>
      <li>The right panel shows the chain of levels (click on it to select that level), what is inside, and the buttons “Show this level only” and “Clear selection”. <kbd>Esc</kbd> clears the selection in edit mode.</li>
    </ul>`,
  "help.edit.title": "Editing",
  "help.edit.html": `
    <p>The <b>“✎ Edit”</b> button turns edit mode on, <b>“Done”</b> turns it off. Select an object — the right panel shows the actions for it:</p>
    <table class="hl-t"><thead><tr><th class="first">Selected</th><th>What you can do</th></tr></thead><tbody>
      <tr><td class="first">Warehouse or zone</td><td>“Add a row” (place type, number of bays and levels), “Add a floor place”, “Add a zone”</td></tr>
      <tr><td class="first">Row</td><td>change the row type, “Add a bay” (for boards — “Add a stack”), rotate, put back to the automatic position</td></tr>
      <tr><td class="first">Bay</td><td>“Add a level on top”</td></tr>
      <tr><td class="first">Level or cell</td><td>“Cells per level” — split a level into cells (see “Warehouses, cells and the project”)</td></tr>
      <tr><td class="first">Anything</td><td>“⧉ Duplicate”, “Copy”, “Remove” (together with everything inside); × in the “Inside” list removes one nested object</td></tr>
    </tbody></table>
    <p><b>Place types</b> (the button above the model in edit mode) is the catalog of constructions: code, name, kind (shelf bay, roll rack, pallet rack, floor stack, floor place), width, depth, level height, levels in a new bay. Changing a size rebuilds all places of this type at once; you can add your own type. It is saved with the “Save types” button in the window.</p>
    <p>New places get codes modeled on their neighbors (<span class="code">FUR-R7-S01-L1</span>) and are shown in blue.</p>`,
  "help.move.title": "Moving and rotating",
  "help.move.html": `
    <ul>
      <li><b>Drag</b> a row or a floor place with the mouse (in 2D and 3D). A zone can be dragged if you select it first. You can drag what stands inside the visible level: to move a row, open its zone, not the row itself.</li>
      <li>The zone grows to fit the object. If a row overlaps a neighbor, the panel shows a warning.</li>
      <li><b>“Automatic position”</b> in the row panel puts the row back to where the layout places it.</li>
      <li><kbd>R</kbd> or <b>“⟳ Rotate by 90°”</b> rotates a row: bays go in depth instead of along. Once more — rotate back. Other angles (180° and 270°) and exact coordinates are in “Properties” (see “Editing tools”).</li>
    </ul>`,
  "help.multi.title": "Several objects at once",
  "help.multi.html": `
    <ul>
      <li><kbd>{mod}</kbd>+<kbd>click</kbd> in the model adds an object to the selection, another <kbd>{mod}</kbd>+<kbd>click</kbd> removes it. All selected objects are highlighted together.</li>
      <li>Drag <b>any selected object</b> — everything selected moves, keeping the relative layout. A selected level or bay drags its row.</li>
      <li><kbd>R</kbd> rotates all selected rows. Marquee selection (<kbd>Shift</kbd> + drag), align, distribute and grouping are described in “Editing tools”.</li>
      <li>The “N objects selected” panel: the list (× removes from the selection), “Duplicate all”, “Copy”, “Rotate rows”, “Remove all”, “Save selection”, “Clear selection”.</li>
    </ul>`,
  "help.tools.title": "Editing tools",
  "help.tools.html": `
    <ul>
      <li><b>Properties</b> (panel of a row, zone or floor place): name, <b>X and Y</b> in meters from the parent zone corner, <b>rotation</b> 0 / 90 / 180 / 270°, width, depth and height, and for a row the <b>number of bays and levels</b>. Only changed fields are applied — through “Show” / “Save”, undone with {mod}+Z. Rotation 90° and 270° swaps width and depth; 180° and 270° put the bays in reverse order.</li>
      <li><b>Mass create</b> (zone panel): type, rows × bays × levels, aisle between rows (m) and orientation (along X or Y). Under the form there is a summary: how many places and what block you get; “Show” draws the rows in the model before saving. Rows are placed below the existing contents of the zone.</li>
      <li><b>Grid array</b> (floor place panel): N × M copies with the step along X and Y (start to start), new codes are the next free ones.</li>
      <li><b>Marquee selection</b> in 2D: hold <kbd>Shift</kbd> and drag — objects that fall entirely inside the frame are selected; what exactly (place, bay, row, zone) is decided by the “Click selects” switch. <kbd>Shift</kbd>+<kbd>{mod}</kbd> adds to the selection. Without <kbd>Shift</kbd> the mouse still drags an object or pans.</li>
      <li><b>Align</b> (the “N objects selected” panel): by left, right, top, bottom edge and by center X / Y; <b>distribute</b> with equal gaps along X or Y (three objects or more, the outer ones stay in place).</li>
      <li><b>Grouping:</b> “Group” moves the selected objects of one zone into a new zone with the given name (positions are kept); “Ungroup” in the panel of such a zone returns the contents to the parent zone and the zone disappears. Place codes do not change. Everything is undone with {mod}+Z.</li>
    </ul>`,
  "help.copy.title": "Copying",
  "help.copy.html": `
    <ul>
      <li><b>“⧉ Duplicate”</b> or <kbd>{mod}</kbd>+<kbd>D</kbd> — a copy of the selection next to it: a level — as a new level on top, a bay — at the end of the row, a row — with the next number (R3 → R7), a floor place — with the next free code (KIT-01 → KIT-13), a zone — “name copy”. A row placed by hand is copied next to it onto a free spot.</li>
      <li><kbd>{mod}</kbd>+<kbd>C</kbd> — remember the selection, <kbd>{mod}</kbd>+<kbd>V</kbd> — paste a copy. Where it goes: into the selected object if it fits — a level into a bay, a bay into a row of the same construction, a row, a floor place or a zone into a zone; otherwise into the nearest suitable level above; otherwise next to the original. The <b>“Paste … → where”</b> button in the panel shows where the copy will land.</li>
      <li>The copy has the same structure and types, but its places are new and empty. After copying, the copy itself is selected — you can drag or rotate it right away.</li>
    </ul>`,
  "help.save.title": "Saving and undoing",
  "help.save.html": `
    <ul>
      <li>Every change is first only <b>shown</b> in the model in teal — “not saved”. Forms have two buttons: <b>“Show”</b> (see the result; showing the same form again replaces the previous preview) and <b>“Save”</b>.</li>
      <li>Unsaved changes are collected per object where they were made. The object panel lists them with the buttons <b>“Save &lt;object&gt;”</b> / “Discard”. Above the model there are “Save all”, “Discard all” and ↶.</li>
      <li><kbd>{mod}</kbd>+<kbd>Z</kbd> or ↶ — undo the last unsaved change, <kbd>{mod}</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd> or <kbd>{mod}</kbd>+<kbd>Y</kbd> — redo it. Saved changes cannot be undone this way.</li>
      <li>After saving, a notification “Saved: … · N changes” appears in the top right corner.</li>
      <li>Both the saved model and unsaved changes live in the project in this browser (localStorage) and survive a reload; they will not be there in another browser or on another computer. More in “Warehouses, cells and the project”.</li>
      <li><b>“Reset to Odoo data”</b> removes all model changes (it is an unsaved change itself — you still have to save it, or you can discard it).</li>
    </ul>`,
  "help.project.title": "Warehouses, cells and the project",
  "help.project.html": `
    <ul>
      <li>The <b>warehouse switch</b> in the top bar: a project holds several warehouses (the demo has WH from the Odoo snapshot and a synthetic WH2). Each has its own plan, its own saved and unsaved changes and its own place types; unsaved changes are kept when you switch.</li>
      <li><b>Location depth</b> (edit mode, warehouse or zone panel) is the last level that becomes an Odoo location: <b>“Level”</b> (default) or <b>“Cell”</b>. A zone can have its own value or “as in the warehouse”. It goes through “Show” / “Save” like other changes and is undone with {mod}+Z.</li>
      <li><b>Cells per level</b> (level panel, 1–12) goes through “Show” / “Save” like other changes. With depth “Cell” and more than one cell the level stops being a place: separate places with codes <span class="code">&lt;level code&gt;-1…N</span> replace it, and in 2D and 3D the level is split into N parts. With depth “Level” the number is remembered but the level stays one place.</li>
      <li><b>Where the project is stored:</b> in this browser (localStorage, key <span class="code">wh-app-project-&lt;id&gt;</span>) — both warehouses, saved and unsaved changes, location depth. If a project cannot be read, its raw record is kept under the key <span class="code">wh-app-project-&lt;id&gt;.broken-&lt;time&gt;</span> and a new demo project opens with a message — nothing is overwritten. Changes from older versions (keys <span class="code">wh-app-edit</span>, <span class="code">wh-app-pending</span> and the prototype’s <span class="code">wh-model-*</span>) were moved into warehouse WH on first start; the old keys stay as a copy.</li>
    </ul>`,
  "help.odoo.title": "Working from Odoo",
  "help.odoo.html": `
    <ul>
      <li><b>Where to open it.</b> In Odoo: <b>Inventory → Configuration → Конструктор складу</b> (the module menu is in Ukrainian; it needs the "Конструктор: перегляд" group). The app opens from your Odoo database address; no separate sign-in — your Odoo account is used. Outside Odoo (an opened file or a site) the app keeps the project in the browser, as described above.</li>
      <li><b>Where projects are stored.</b> In the Odoo database, not in the browser: the "Warehouse constructor" module (<span class="code">wh_constructor</span>) keeps projects, their versions and zone locks. There is one project for everyone with access to the company; project warehouses are linked to Odoo warehouses by code.</li>
      <li><b>Versions.</b> Every "Save" creates a new project version (the last 50 are kept); unsaved ("teal") changes are also stored in the project but create no versions. If someone saved the project while you were editing, your save is rejected with "The project was changed by another user" — reload the page to see the current state. Restoring an old version is done in the module (a versions menu in the app will come later).</li>
      <li><b>Rights</b> are Odoo groups. "Конструктор: перегляд" (view) — look only (nothing can be saved; the status line says "View only"). "Конструктор: проєктування" (design, includes view) — create and change projects, lock zones. "Конструктор: застосування в Odoo" (apply, includes design) — apply changes to Odoo locations (coming in a later stage). An administrator assigns the groups on the user form.</li>
      <li><b>Zone locks.</b> When you select an object in edit mode, the zone it belongs to is locked for you for 5 minutes; while the page stays open the lock is renewed automatically, and it is released when you leave edit mode. If another user is already editing the zone, you get "Zone is being edited by …": changes in it are blocked, other zones stay available. A lock expires by itself if the person closes the page or loses the connection.</li>
    </ul>`,
  "help.keys.title": "Hotkeys",
  "help.keys.html": `
    <p class="mut">They work in edit mode when the cursor is not in an input field; the Ukrainian keyboard layout works too. On Mac use ⌘ instead of Ctrl.</p>
    <table class="hl-t"><tbody>
      <tr><td class="first"><kbd>{mod}</kbd>+<kbd>click</kbd></td><td>add to / remove from the selection</td></tr>
      <tr><td class="first"><kbd>Shift</kbd>+drag (2D)</td><td>marquee select; with <kbd>{mod}</kbd> — add to the selection</td></tr>
      <tr><td class="first"><kbd>{mod}</kbd>+<kbd>C</kbd></td><td>copy the selection</td></tr>
      <tr><td class="first"><kbd>{mod}</kbd>+<kbd>V</kbd></td><td>paste the copied objects</td></tr>
      <tr><td class="first"><kbd>{mod}</kbd>+<kbd>D</kbd></td><td>duplicate the selection next to it</td></tr>
      <tr><td class="first"><kbd>{mod}</kbd>+<kbd>Z</kbd></td><td>undo the last unsaved change</td></tr>
      <tr><td class="first"><kbd>{mod}</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd> · <kbd>{mod}</kbd>+<kbd>Y</kbd></td><td>redo an undone change</td></tr>
      <tr><td class="first"><kbd>R</kbd></td><td>rotate the selected rows by 90°</td></tr>
      <tr><td class="first"><kbd>Esc</kbd></td><td>clear the selection (it also closes the place types window)</td></tr>
    </tbody></table>`,
};
