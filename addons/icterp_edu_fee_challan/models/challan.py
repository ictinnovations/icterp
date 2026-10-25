"""Fee challan: the bank deposit slip a student pays at a bank branch.

One challan per student bundles one or more fee invoices. Issuing it posts the invoices with
the challan's due date, so overdue reminders and ageing use the same date. The PDF prints three
copies (bank, institute, student) with the institute's bank accounts.

Paying: the bank stamps the challan, the accounts office confirms it (one by one or from the
bank's file). If it was paid after the due date plus the grace days, a fine invoice is created
from the fine policy, and one payment settles the fee invoices and the fine together.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class IcterpFeeChallan(models.Model):
    _name = "icterp.fee.challan"
    _description = "Fee challan"
    _inherit = ["mail.thread", "portal.mixin"]
    _order = "issue_date desc, id desc"

    name = fields.Char(string="Challan no.", required=True, copy=False, readonly=True, default=lambda self: _("New"), index=True)
    student_id = fields.Many2one("op.student", index=True, tracking=True,
                                 help="Empty for an applicant who is not a student yet (admission challan).")
    partner_id = fields.Many2one("res.partner", string="Payer", required=True, index=True,
                                 compute="_compute_partner", store=True, readonly=False, precompute=True)
    invoice_ids = fields.Many2many("account.move", string="Fee invoices", domain="[('move_type', '=', 'out_invoice')]")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
    issue_date = fields.Date(default=fields.Date.context_today, required=True)
    due_date = fields.Date(required=True, tracking=True)
    fine_policy_id = fields.Many2one("icterp.fine.policy", default=lambda self: self.env.company.challan_fine_policy_id)
    bank_ids = fields.Many2many("res.partner.bank", string="Pay at", default=lambda self: self.env.company.challan_bank_ids)
    amount = fields.Monetary(compute="_compute_amount", store=True, help="Total of the fee invoices.")
    fine_today = fields.Monetary(compute="_compute_fine_today", string="Fine if paid today")
    state = fields.Selection([("draft", "Draft"), ("issued", "Issued"), ("paid", "Paid"), ("cancelled", "Cancelled")],
                             default="draft", required=True, tracking=True, index=True)
    paid_date = fields.Date(tracking=True)
    paid_amount = fields.Monetary(tracking=True)
    fine_amount = fields.Monetary(string="Fine charged", readonly=True)
    fine_invoice_id = fields.Many2one("account.move", readonly=True)
    bank_reference = fields.Char(tracking=True)
    payment_ids = fields.Many2many("account.payment", string="Payments", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("icterp.fee.challan") or _("New")
        return super().create(vals_list)

    @api.depends("student_id")
    def _compute_partner(self):
        for c in self:
            if c.student_id:
                c.partner_id = c.student_id.partner_id

    def payer_name(self):
        return self.student_id.name or self.partner_id.name

    @api.depends("invoice_ids.amount_total", "invoice_ids.amount_residual", "state")
    def _compute_amount(self):
        for c in self:
            c.amount = sum(c.invoice_ids.mapped("amount_total"))

    def _compute_fine_today(self):
        today = fields.Date.context_today(self)
        for c in self:
            c.fine_today = c.fine_policy_id.fine_for(c.due_date, today) if c.fine_policy_id and c.state == "issued" else 0.0

    def _compute_access_url(self):
        super()._compute_access_url()
        for c in self:
            c.access_url = "/my/education/challan/%s" % c.id

    def fee_heads(self):
        """[(description, amount)] from the invoice lines, for the printed challan."""
        rows = []
        for line in self.invoice_ids.mapped("invoice_line_ids").filtered(lambda l: l.display_type in (False, "product")):
            rows.append((line.name or line.product_id.name, line.price_total))
        return rows

    # ------------------------------------------------------------------ workflow
    def action_issue(self):
        for c in self:
            if not c.invoice_ids:
                raise UserError(_("Challan %s has no fee invoices.", c.name))
            for inv in c.invoice_ids:
                if inv.partner_id != c.partner_id:
                    raise UserError(_("Invoice %s belongs to someone else.", inv.name))
                if inv.state == "draft":
                    inv.write({"invoice_date": c.issue_date, "invoice_date_due": c.due_date, "invoice_payment_term_id": False})
                    inv.action_post()
                    inv.invoice_date_due = c.due_date
                elif inv.state == "cancel":
                    raise UserError(_("Invoice %s is cancelled.", inv.name))
            c.state = "issued"
        return True

    def action_cancel(self):
        for c in self:
            if c.state == "paid":
                raise UserError(_("A paid challan cannot be cancelled. Reverse the payment in Accounting first."))
            c.state = "cancelled"

    def action_print(self):
        return self.env.ref("icterp_edu_fee_challan.action_report_challan").report_action(self)

    def _default_journal(self):
        bank = self.bank_ids[:1]
        journal = self.env["account.journal"].search([("type", "=", "bank"), ("bank_account_id", "=", bank.id)], limit=1) if bank else False
        return journal or self.env["account.journal"].search([("type", "=", "bank"), ("company_id", "=", self.company_id.id)], limit=1)

    def _create_fine_invoice(self, fine, paid_date):
        self.ensure_one()
        product = self.fine_policy_id.product_id
        inv = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": paid_date,
            "invoice_origin": self.name,
            "invoice_line_ids": [(0, 0, {"product_id": product.id, "name": _("Late payment fine, challan %s", self.name),
                                         "quantity": 1, "price_unit": fine, "tax_ids": [(6, 0, [])]})],
        })
        inv.action_post()
        return inv

    def confirm_payment(self, paid_date, amount=None, journal=None, reference=None):
        """Mark the challan paid on `paid_date`, adding the late fine if one applies.

        `amount` is what the bank received; it must cover the fees plus any fine.
        """
        self.ensure_one()
        if self.state != "issued":
            raise UserError(_("Challan %(name)s is %(state)s, not waiting for payment.", name=self.name, state=self.state))
        fine = self.fine_policy_id.fine_for(self.due_date, paid_date) if self.fine_policy_id else 0.0
        open_invoices = self.invoice_ids.filtered(lambda i: i.state == "posted" and i.payment_state not in ("paid", "in_payment", "reversed"))
        due = sum(open_invoices.mapped("amount_residual")) + fine
        if amount is None:
            amount = due
        if amount + 0.005 < due:
            raise UserError(_("Challan %(name)s needs %(due)s (fees plus %(fine)s fine) but %(amount)s was paid.",
                              name=self.name, due=due, fine=fine, amount=amount))
        moves = open_invoices
        if fine:
            self.fine_invoice_id = self._create_fine_invoice(fine, paid_date)
            moves |= self.fine_invoice_id
        payments = self.env["account.payment"]
        if moves:
            journal = journal or self._default_journal()
            if not journal:
                raise UserError(_("Create a bank journal in Accounting first."))
            wizard = self.env["account.payment.register"].with_context(active_model="account.move", active_ids=moves.ids).create({
                "payment_date": paid_date, "journal_id": journal.id, "amount": due, "group_payment": True,
                "communication": reference or self.name,
            })
            result = wizard._create_payments()
            payments = result if isinstance(result, models.BaseModel) else payments
        self.write({"state": "paid", "paid_date": paid_date, "paid_amount": amount, "fine_amount": fine,
                    "bank_reference": reference or False, "payment_ids": [(6, 0, payments.ids)]})
        self.message_post(body=_("Paid on %(date)s: %(amount)s%(fine)s.", date=paid_date, amount=amount,
                                 fine=(_(" including a fine of %s", fine) if fine else "")))
        self._on_paid()
        return True

    def _on_paid(self):
        """Hook: called once a challan is confirmed paid (admissions use it to confirm the seat)."""
        return True
