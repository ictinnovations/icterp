/** @odoo-module **/
import { registry } from "@web/core/registry";

// The web client falls back to "Odoo" when no title part is set. Give it ours.
registry.category("services").add("icterp_title", {
    dependencies: ["title"],
    start(env, { title }) {
        title.setParts({ brand: "ICTERP" });
    },
});
