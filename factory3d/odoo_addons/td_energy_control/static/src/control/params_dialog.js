/** @odoo-module **/
// UI-18 ParamsDialog: форма параметров сценария по `scenarios[].schema` (API-16). «Зберегти» передаёт значения
// вызывающему (`onSave`), тот запускает prepare('scenario_params', …) → ConfirmDialog.

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"];

export class ParamsDialog extends Component {
    static template = "td_energy_control.ParamsDialog";
    static components = { Dialog };
    static props = {
        scenario: { type: Object },
        onSave: { type: Function },
        close: { type: Function },
    };

    setup() {
        const { params, schema } = this.props.scenario;
        const values = {};
        for (const spec of schema || []) {
            const value = (params || {})[spec.name];
            values[spec.name] = spec.type === "days" ? [...(value || [])] : value === undefined ? null : value;
        }
        this.weekdays = WEEKDAYS;
        this.state = useState({ values, errors: {} });
    }

    get schema() {
        return this.props.scenario.schema || [];
    }

    get title() {
        return `Параметри: ${this.props.scenario.title}`;
    }

    /** Підказка з межами: «100…2000 кВт». */
    hint(spec) {
        const unit = spec.unit ? ` ${spec.unit}` : "";
        if (spec.type === "days") {
            return "дні, у які починається вікно";
        }
        if (spec.min !== undefined && spec.max !== undefined) {
            return `${spec.min}…${spec.max}${unit}`;
        }
        return spec.unit || "";
    }

    isDayOn(name, day) {
        return this.state.values[name].includes(day);
    }

    toggleDay(name, day) {
        const days = this.state.values[name];
        const index = days.indexOf(day);
        if (index >= 0) {
            days.splice(index, 1);
        } else {
            days.push(day);
            days.sort((a, b) => a - b);
        }
    }

    /** Перевірка меж на клієнті (остаточна — на сервері, `ValidationError` у prepare). */
    validate() {
        const errors = {};
        for (const spec of this.schema) {
            const value = this.state.values[spec.name];
            if (spec.type === "float" || spec.type === "int") {
                if (value === null || value === "" || Number.isNaN(Number(value))) {
                    errors[spec.name] = "Вкажіть число";
                } else if (spec.type === "int" && !Number.isInteger(Number(value))) {
                    errors[spec.name] = "Потрібне ціле число";
                } else if (
                    (spec.min !== undefined && Number(value) < spec.min) ||
                    (spec.max !== undefined && Number(value) > spec.max)
                ) {
                    errors[spec.name] = `Поза межами ${this.hint(spec)}`;
                }
            } else if (spec.type === "days" && !this.state.values[spec.name].length) {
                errors[spec.name] = "Оберіть хоча б один день";
            } else if (spec.type === "time" && !value) {
                errors[spec.name] = "Вкажіть час";
            }
        }
        this.state.errors = errors;
        return !Object.keys(errors).length;
    }

    save() {
        if (!this.validate()) {
            return;
        }
        const out = {};
        for (const spec of this.schema) {
            const value = this.state.values[spec.name];
            out[spec.name] = spec.type === "float" || spec.type === "int" ? Number(value) : value;
        }
        this.props.close();
        this.props.onSave(out);
    }
}
