from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    icterp_home_enabled = fields.Boolean(string="Open Home after sign-in")
    icterp_home_welcome = fields.Char(
        string="Welcome message", config_parameter="icterp_home.welcome")
    icterp_home_show_more = fields.Boolean(string="Show apps that are not in a section")

    # Both switches default to on, so they are stored as explicit "True"/"False"
    # instead of the usual config_parameter booleans (which delete the key when off).
    @api.model
    def get_values(self):
        res = super().get_values()
        param = self.env["ir.config_parameter"].sudo()
        res["icterp_home_enabled"] = param.get_param("icterp_home.enabled", "True") != "False"
        res["icterp_home_show_more"] = param.get_param("icterp_home.show_more", "True") != "False"
        return res

    def set_values(self):
        super().set_values()
        param = self.env["ir.config_parameter"].sudo()
        was_enabled = param.get_param("icterp_home.enabled", "True") != "False"
        param.set_param("icterp_home.enabled", str(bool(self.icterp_home_enabled)))
        param.set_param("icterp_home.show_more", str(bool(self.icterp_home_show_more)))
        if self.icterp_home_enabled and not was_enabled:
            self.env["res.users"]._icterp_home_assign()
        elif not self.icterp_home_enabled and was_enabled:
            self.env["res.users"]._icterp_home_clear()

    def action_icterp_home_sections(self):
        self.env["icterp.home.section"]._icterp_sync_prefix_menus()
        return {
            "type": "ir.actions.act_window",
            "name": "Home page sections",
            "res_model": "icterp.home.section",
            "view_mode": "list,form",
            "context": {"active_test": False},
        }
