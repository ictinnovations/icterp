from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class IcterpGenerateChallans(models.TransientModel):
    _name = "icterp.generate.challans"
    _description = "Generate fee challans"

    student_ids = fields.Many2many("op.student", string="Students")
    batch_id = fields.Many2one("op.batch", help="Fill the student list with this batch.")
    fees_up_to = fields.Date(string="Fees dated up to", default=fields.Date.context_today, required=True,
                             help="Fee lines dated on or before this day are included.")
    issue_date = fields.Date(default=fields.Date.context_today, required=True)
    due_date = fields.Date(required=True, default=lambda self: fields.Date.context_today(self)
                           + timedelta(days=self.env.company.challan_validity_days or 15))
    issue_now = fields.Boolean(default=True, help="Post the invoices and mark the challans issued straight away.")
    result_note = fields.Text(readonly=True)

    @api.onchange("batch_id")
    def _onchange_batch(self):
        if self.batch_id:
            self.student_ids = self.env["op.student.course"].search([("batch_id", "=", self.batch_id.id)]).mapped("student_id")

    def action_generate(self):
        self.ensure_one()
        if not self.student_ids:
            raise UserError(_("Pick the students first."))
        Challan = self.env["icterp.fee.challan"]
        made, skipped = Challan, []
        for student in self.student_ids:
            # 1. fee lines not invoiced yet -> invoices (OpenEduCat, keeps scholarship discounts)
            fee_lines = self.env["op.student.fees.details"].search([
                ("student_id", "=", student.id), ("state", "=", "draft"), ("date", "<=", self.fees_up_to)])
            for line in fee_lines:
                line.get_invoice()
            # 2. every unpaid invoice of the student that is not already on an open challan
            invoices = self.env["op.student.fees.details"].search([
                ("student_id", "=", student.id), ("invoice_id", "!=", False)]).mapped("invoice_id")
            invoices = invoices.filtered(lambda i: i.state in ("draft", "posted") and i.payment_state not in ("paid", "in_payment", "reversed"))
            on_challan = Challan.search([("student_id", "=", student.id), ("state", "in", ["draft", "issued"])]).mapped("invoice_ids")
            invoices -= on_challan
            if not invoices:
                skipped.append(student.name)
                continue
            challan = Challan.create({"student_id": student.id, "invoice_ids": [(6, 0, invoices.ids)],
                                      "issue_date": self.issue_date, "due_date": self.due_date})
            if self.issue_now:
                challan.action_issue()
            made |= challan
        note = _("%s challan(s) created.", len(made))
        if skipped:
            note += "\n" + _("Nothing to bill for: %s", ", ".join(skipped))
        self.result_note = note
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}
