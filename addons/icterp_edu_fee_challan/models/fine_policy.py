from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class IcterpFinePolicy(models.Model):
    _name = "icterp.fine.policy"
    _description = "Late payment fine policy"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    grace_days = fields.Integer(default=0, help="Days after the due date before any fine applies.")
    method = fields.Selection([("per_day", "Amount per day late"), ("fixed", "One fixed amount")],
                              default="per_day", required=True)
    amount = fields.Float(required=True, help="Per day, or the fixed amount.")
    max_amount = fields.Float(string="Maximum fine", help="0 = no limit.")
    product_id = fields.Many2one("product.product", string="Fine product", required=True,
                                 default=lambda self: self.env.ref("icterp_edu_fee_challan.product_late_fine", raise_if_not_found=False),
                                 help="Used on the fine invoice; its income account receives the fines.")

    @api.constrains("amount", "max_amount", "grace_days")
    def _check(self):
        for p in self:
            if p.amount < 0 or p.max_amount < 0 or p.grace_days < 0:
                raise ValidationError(_("Fine amounts and grace days cannot be negative."))

    def fine_for(self, due_date, paid_date):
        """Fine owed when a challan due on `due_date` is paid on `paid_date`."""
        self.ensure_one()
        if not due_date or not paid_date:
            return 0.0
        late_days = (paid_date - (due_date + timedelta(days=self.grace_days))).days
        if late_days <= 0:
            return 0.0
        fine = self.amount * late_days if self.method == "per_day" else self.amount
        if self.max_amount:
            fine = min(fine, self.max_amount)
        return round(fine, 2)
