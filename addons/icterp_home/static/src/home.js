import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

// Sections, welcome text and "More apps" come from Settings (icterp.home.section).
// The menu service only holds the apps this user may open, so access rights apply as usual.
export class IcterpHome extends Component {
    static template = "icterp_home.Home";
    static props = ["*"];

    setup() {
        this.menu = useService("menu");
        this.orm = useService("orm");
        this.state = useState({ query: "" });
        this.userName = user.name;
        const hour = new Date().getHours();
        this.greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
        onWillStart(async () => {
            this.config = await this.orm.call("icterp.home.section", "get_home_data", []);
        });
    }

    get welcome() {
        return this.config.welcome || "Pick an app to get started. You can come back here any time from Home in the app menu.";
    }

    get sections() {
        const q = this.state.query.trim().toLowerCase();
        const hidden = new Set(this.config.hidden_ids);
        const apps = this.menu
            .getApps()
            .filter((a) => !hidden.has(a.id))
            .filter((a) => !q || a.name.toLowerCase().includes(q));
        const byId = new Map(apps.map((a) => [a.id, a]));
        const used = new Set();
        const out = [];
        for (const s of this.config.sections) {
            const items = s.menu_ids.map((id) => byId.get(id)).filter((a) => a && !used.has(a.id));
            items.forEach((a) => used.add(a.id));
            if (items.length) {
                out.push({ key: `s${s.id}`, title: s.title, hint: s.hint, apps: items });
            }
        }
        if (this.config.show_more) {
            const rest = apps.filter((a) => !used.has(a.id));
            if (rest.length) {
                out.push({ key: "more", title: "More apps", hint: "", apps: rest });
            }
        }
        return out;
    }

    open(app) {
        this.menu.selectMenu(app);
    }

    onKeydown(ev) {
        if (ev.key === "Enter") {
            const first = this.sections[0]?.apps[0];
            if (first) {
                this.open(first);
            }
        }
    }
}

registry.category("actions").add("icterp_home", IcterpHome);
