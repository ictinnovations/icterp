from odoo import fields, models


class IcterpFeeChallan(models.Model):
    _inherit = "icterp.fee.challan"

    admission_id = fields.Many2one("op.admission", string="Admission application", index=True, readonly=True)

    def _on_paid(self):
        res = super()._on_paid()
        self.filtered("admission_id").mapped("admission_id")._on_admission_fee_paid()
        return res
