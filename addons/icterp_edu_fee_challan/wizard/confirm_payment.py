from odoo import api, fields, models


class IcterpChallanConfirmPayment(models.TransientModel):
    _name = "icterp.challan.confirm.payment"
    _description = "Confirm a challan was paid"

    challan_id = fields.Many2one("icterp.fee.challan", required=True)
    currency_id = fields.Many2one(related="challan_id.currency_id")
    paid_date = fields.Date(required=True, default=fields.Date.context_today)
    journal_id = fields.Many2one("account.journal", domain="[('type', 'in', ['bank', 'cash'])]")
    reference = fields.Char(string="Bank reference / scroll no.")
    fine = fields.Monetary(compute="_compute_due", string="Late fine")
    due = fields.Monetary(compute="_compute_due", string="Total to receive")
    amount = fields.Monetary(string="Amount received")

    @api.depends("challan_id", "paid_date")
    def _compute_due(self):
        for w in self:
            c = w.challan_id
            w.fine = c.fine_policy_id.fine_for(c.due_date, w.paid_date) if c.fine_policy_id else 0.0
            open_inv = c.invoice_ids.filtered(lambda i: i.state == "posted" and i.payment_state not in ("paid", "in_payment", "reversed"))
            w.due = sum(open_inv.mapped("amount_residual")) + w.fine

    @api.onchange("due")
    def _onchange_due(self):
        self.amount = self.due

    def action_confirm(self):
        self.ensure_one()
        self.challan_id.confirm_payment(self.paid_date, amount=self.amount or self.due,
                                        journal=self.journal_id or None, reference=self.reference)
        return {"type": "ir.actions.act_window_close"}
