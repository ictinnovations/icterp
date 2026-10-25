"""Scholarships and waivers.

A scholarship is a percentage off chosen fee heads (empty = every head); a waiver is the same
thing at 100%. Approving a student's award applies the percentage to that student's fee lines
that are not invoiced yet and fall in the award's dates, through the fee line's discount, which
OpenEduCat already carries onto the invoice. Invoiced fees are not touched: credit notes stay a
deliberate accounting step.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class IcterpScholarship(models.Model):
    _name = "icterp.scholarship"
    _description = "Scholarship or waiver"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    kind = fields.Selection([("scholarship", "Scholarship"), ("waiver", "Fee waiver"), ("discount", "Discount")],
                            default="scholarship", required=True)
    percent = fields.Float(string="Percent off", required=True, default=50.0)
    product_ids = fields.Many2many("product.product", string="Fee heads", help="Leave empty to apply to every fee head.")
    criteria = fields.Text(help="Who qualifies, for the record (merit, need, sibling, Hafiz-e-Quran ...).")

    @api.onchange("kind")
    def _onchange_kind(self):
        if self.kind == "waiver":
            self.percent = 100.0

    @api.constrains("percent")
    def _check_percent(self):
        for s in self:
            if not 0 < s.percent <= 100:
                raise ValidationError(_("The percentage must be more than 0 and at most 100."))


class IcterpStudentScholarship(models.Model):
    _name = "icterp.student.scholarship"
    _description = "Scholarship awarded to a student"
    _inherit = ["mail.thread"]
    _order = "date_from desc, id desc"

    student_id = fields.Many2one("op.student", required=True, index=True, tracking=True)
    scholarship_id = fields.Many2one("icterp.scholarship", required=True, tracking=True)
    percent = fields.Float(related="scholarship_id.percent")
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(help="Leave empty for open-ended.")
    reason = fields.Text()
    state = fields.Selection([("draft", "Draft"), ("approved", "Approved"), ("cancelled", "Cancelled")],
                             default="draft", required=True, tracking=True)
    approved_by = fields.Many2one("res.users", readonly=True)
    fee_line_ids = fields.Many2many("op.student.fees.details", string="Fee lines discounted", readonly=True)

    def _eligible_fee_lines(self):
        self.ensure_one()
        domain = [("student_id", "=", self.student_id.id), ("state", "=", "draft"), ("date", ">=", self.date_from)]
        if self.date_to:
            domain.append(("date", "<=", self.date_to))
        lines = self.env["op.student.fees.details"].search(domain)
        heads = self.scholarship_id.product_ids
        if heads:
            lines = lines.filtered(lambda l: l.product_id in heads)
        return lines

    def action_approve(self):
        for award in self:
            if award.state != "draft":
                continue
            lines = award._eligible_fee_lines()
            for line in lines:
                # several awards on one fee line: keep the larger, they do not stack past 100%
                line.discount = max(line.discount or 0.0, award.percent)
            award.write({"state": "approved", "approved_by": self.env.user.id, "fee_line_ids": [(6, 0, lines.ids)]})
            award.message_post(body=_("Approved: %(pct)s%% off %(n)s fee line(s).", pct=award.percent, n=len(lines)))

    def action_cancel(self):
        for award in self:
            if award.state == "approved":
                for line in award.fee_line_ids.filtered(lambda l: l.state == "draft" and (l.discount or 0) == award.percent):
                    line.discount = 0.0
            award.state = "cancelled"
