import uuid
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class OpAdmission(models.Model):
    _inherit = "op.admission"

    matric_obtained = fields.Float(string="Matric marks")
    matric_total = fields.Float(string="Matric out of", default=1100)
    inter_obtained = fields.Float(string="Intermediate marks")
    inter_total = fields.Float(string="Intermediate out of", default=1100)
    board_name = fields.Char(string="Board / university")
    passing_year = fields.Char()
    hafiz = fields.Boolean(string="Hafiz-e-Quran")
    applied_online = fields.Boolean(readonly=True)
    access_token = fields.Char(copy=False, readonly=True, default=lambda self: uuid.uuid4().hex)

    entry_test_id = fields.Many2one("icterp.entry.test", string="Entry test", copy=False)
    test_roll_no = fields.Char(string="Test roll no.", copy=False, readonly=True)
    test_room_id = fields.Many2one("op.classroom", string="Test room", copy=False)
    test_marks = fields.Float(copy=False)
    test_taken = fields.Boolean(copy=False, help="Set when test marks are entered (0 = sat the test and scored 0, or absent).")
    interview_marks = fields.Float(string="Interview (out of 100)", copy=False)

    matric_percent = fields.Float(compute="_compute_aggregate", store=True, digits=(5, 2))
    inter_percent = fields.Float(compute="_compute_aggregate", store=True, digits=(5, 2))
    test_percent = fields.Float(compute="_compute_aggregate", store=True, digits=(5, 2))
    aggregate = fields.Float(compute="_compute_aggregate", store=True, digits=(5, 3))
    merit_rank = fields.Integer(copy=False, readonly=True)
    merit_status = fields.Selection([("pending", "Not ranked yet"), ("selected", "Selected"), ("waiting", "Waiting list"),
                                     ("not_selected", "Not selected")], default="pending", copy=False, readonly=True, tracking=True)
    offer_sent_on = fields.Date(copy=False, readonly=True)
    offer_expires_on = fields.Date(copy=False)
    admission_challan_id = fields.Many2one("icterp.fee.challan", copy=False, readonly=True)

    @api.depends("matric_obtained", "matric_total", "inter_obtained", "inter_total", "test_marks", "interview_marks",
                 "hafiz", "entry_test_id.total_marks", "register_id.weight_matric", "register_id.weight_inter",
                 "register_id.weight_test", "register_id.weight_interview", "register_id.hafiz_bonus")
    def _compute_aggregate(self):
        for a in self:
            reg = a.register_id
            a.matric_percent = 100.0 * a.matric_obtained / a.matric_total if a.matric_total else 0.0
            a.inter_percent = 100.0 * a.inter_obtained / a.inter_total if a.inter_total else 0.0
            total = a.entry_test_id.total_marks or 100.0
            a.test_percent = 100.0 * (a.test_marks or 0.0) / total if total else 0.0
            parts = [(reg.weight_matric, a.matric_percent), (reg.weight_inter, a.inter_percent),
                     (reg.weight_test, a.test_percent), (reg.weight_interview, a.interview_marks or 0.0)]
            weight = sum(w for w, _p in parts if w)
            agg = sum(w * p for w, p in parts if w) / weight if weight else 0.0
            if a.hafiz and reg.hafiz_bonus:
                agg += reg.hafiz_bonus
            a.aggregate = round(agg, 3)

    @api.constrains("matric_obtained", "matric_total", "inter_obtained", "inter_total", "test_marks", "interview_marks")
    def _check_marks(self):
        for a in self:
            if a.matric_obtained < 0 or (a.matric_total and a.matric_obtained > a.matric_total):
                raise ValidationError(_("Matric marks must be between 0 and %s.", a.matric_total))
            if a.inter_obtained < 0 or (a.inter_total and a.inter_obtained > a.inter_total):
                raise ValidationError(_("Intermediate marks must be between 0 and %s.", a.inter_total))
            total = a.entry_test_id.total_marks or 100.0
            if a.test_marks and not 0 <= a.test_marks <= total:
                raise ValidationError(_("Test marks must be between 0 and %s.", total))
            if a.interview_marks and not 0 <= a.interview_marks <= 100:
                raise ValidationError(_("Interview marks are out of 100."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "test_marks" in vals and vals.get("test_marks") is not False:
                vals["test_taken"] = True
        return super().create(vals_list)

    def write(self, vals):
        if "test_marks" in vals and vals.get("test_marks") is not False:
            vals = dict(vals, test_taken=True)
        return super().write(vals)

    # ------------------------------------------------------------------ offer
    def _ensure_partner(self):
        self.ensure_one()
        if not self.partner_id:
            self.partner_id = self.env["res.partner"].create({
                "name": self.name, "email": self.email, "phone": self.phone or self.mobile,
                "street": self.street, "city": self.city, "country_id": self.country_id.id})
        return self.partner_id

    def _fee_product(self):
        self.ensure_one()
        reg = self.register_id
        line = reg.admission_fees_line_ids.filtered(lambda l: l.course_id == self.course_id)[:1]
        product = line.course_fees_product_id or reg.product_id
        if not product:
            product = self.env.ref("icterp_edu_admission.product_admission_fee")
        return product

    def _create_admission_challan(self):
        self.ensure_one()
        partner = self._ensure_partner()
        product = self._fee_product()
        price = self.register_id.admission_fee or product.lst_price
        if price <= 0:
            return self.env["icterp.fee.challan"]
        inv = self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": partner.id, "invoice_origin": self.application_number,
            "invoice_line_ids": [(0, 0, {"product_id": product.id, "name": _("Admission fee, %s", self.register_id.name),
                                         "quantity": 1, "price_unit": price})],
        })
        challan = self.env["icterp.fee.challan"].create({
            "partner_id": partner.id, "admission_id": self.id, "invoice_ids": [(6, 0, inv.ids)],
            "issue_date": fields.Date.context_today(self), "due_date": self.offer_expires_on})
        challan.action_issue()
        return challan

    def action_send_offer(self):
        template = self.env.ref("icterp_edu_admission.mail_template_offer_letter")
        for a in self:
            if a.merit_status != "selected":
                raise UserError(_("%s is not on the selected list.", a.name))
            today = fields.Date.context_today(a)
            a.write({"offer_sent_on": today, "offer_expires_on": today + timedelta(days=a.register_id.offer_valid_days or 7)})
            a.admission_challan_id = a._create_admission_challan()
            template.send_mail(a.id, force_send=False)
            a.message_post(body=_("Offer letter sent; pay by %s.", a.offer_expires_on))
        return True

    def _on_admission_fee_paid(self):
        for a in self.filtered(lambda r: r.state in ("submit", "confirm")):
            a.state = "admission"
            a.message_post(body=_("Admission fee paid: seat confirmed. Enrol the student to create the student record."))
            a.activity_schedule("mail.mail_activity_data_todo", summary=_("Enrol the student"), user_id=a.create_uid.id or self.env.uid)

    def status_url(self):
        self.ensure_one()
        return "/admission/status/%s/%s" % (self.id, self.access_token)
