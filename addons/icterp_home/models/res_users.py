from odoo import api, models


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _icterp_home_action(self):
        return self.env.ref("icterp_home.action_home", raise_if_not_found=False)

    @api.model
    def _icterp_home_enabled(self):
        return self.env["ir.config_parameter"].sudo().get_param("icterp_home.enabled", "True") != "False"

    @api.model
    def _icterp_home_assign(self):
        """Point every internal user without a home action at the ICTERP home page."""
        action = self._icterp_home_action()
        if not action:
            return
        users = self.with_context(active_test=False).search(
            [("share", "=", False), ("action_id", "=", False)]
        )
        users.sudo().write({"action_id": action.id})

    @api.model
    def _icterp_home_clear(self):
        """Remove the home page as home action; users fall back to the first app."""
        action = self._icterp_home_action()
        if action:
            self.with_context(active_test=False).search(
                [("action_id", "=", action.id)]
            ).sudo().write({"action_id": False})

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        action = self._icterp_home_action()
        if action and self._icterp_home_enabled():
            users.filtered(lambda u: not u.share and not u.action_id).sudo().write(
                {"action_id": action.id}
            )
        return users
