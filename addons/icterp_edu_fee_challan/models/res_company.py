from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    challan_bank_ids = fields.Many2many("res.partner.bank", "icterp_company_challan_bank_rel", "company_id", "bank_id",
                                        string="Challan bank accounts", help="Printed on every challan.")
    challan_fine_policy_id = fields.Many2one("icterp.fine.policy", string="Default fine policy")
    challan_validity_days = fields.Integer(string="Days to pay", default=15, help="Due date = issue date + this many days.")
    challan_instructions = fields.Text(string="Challan instructions",
                                       default="Pay at any branch of the banks listed. Keep the student copy as your receipt.")
