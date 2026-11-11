// Патерн кліпа (замінити на кліпи SALES §6 у clips.mjs). Правила: c.mark() — коли екран готовий; title()/pain() лише записують подію; hold() — пауза з рухом;
// zoom() до ключових цифр (на 1920 px дрібно); без «Новий» у кадрі (prototype.new_record_in_frame); жодного статичного кадру >2 с.
import { clip, title, hold, zoom, settle, goto } from './rec_lib.mjs';
export const PASS1 = [];            // кліпи, що змінюють дані
export const PASS2 = ['D_example']; // лише читання; кліпи дашборда — першими
export const CLIPS = {
    async D_example() {
        return clip('D_example', { role: 'manager', url: '/odoo' }, async (c) => {
            await settle(c.page, 700); c.mark();
            await title(c, 'Роль', 'Короткий титр — **вигода**');
            await hold(c, 2300);
        });
    },
};
