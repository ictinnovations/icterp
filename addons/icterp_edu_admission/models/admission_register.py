"""Admission register (one intake, e.g. "BSCS Fall 2026") with merit rules.

Aggregate (out of 100) = weighted average of the percentages that have a weight:
  matric %, intermediate %, entry test %, interview %
plus the Hafiz-e-Quran bonus for applicants who are Hafiz. Weights are relative, they need not
total 100. The merit list ranks applicants by aggregate, then test %, then intermediate %:
the first `max_count` (seats) are selected, the next `waiting_count` go on the waiting list.
"""
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

ACTIVE_STATES = ("submit", "confirm", "admission")


class OpAdmissionRegister(models.Model):
    _inherit = "op.admission.register"

    online = fields.Boolean(string="Open for online applications",
                            help="Shown on the website's admissions page while the dates are open.")
    weight_matric = fields.Float(string="Matric weight", default=10)
    weight_inter = fields.Float(string="Intermediate weight", default=40)
    weight_test = fields.Float(string="Entry test weight", default=50)
    weight_interview = fields.Float(string="Interview weight", default=0)
    hafiz_bonus = fields.Float(string="Hafiz-e-Quran bonus", default=0,
                               help="Added to the aggregate of applicants who are Hafiz-e-Quran.")
    test_required = fields.Boolean(default=True)
    waiting_count = fields.Integer(string="Waiting list size", default=10)
    offer_valid_days = fields.Integer(default=7, help="Days to pay the admission challan after the offer.")
    admission_fee = fields.Float(help="Admission fee on the offer challan. 0 = use the register's product price.")
    entry_test_ids = fields.One2many("icterp.entry.test", "register_id", string="Entry tests")
    merit_generated_on = fields.Datetime(readonly=True)

    def _applicants(self):
        self.ensure_one()
        return self.env["op.admission"].search([("register_id", "=", self.id), ("state", "in", list(ACTIVE_STATES))])

    def action_generate_merit(self):
        for reg in self:
            applicants = reg._applicants()
            missing = applicants.filtered(lambda a: reg.test_required and reg.weight_test and not a.test_taken)
            ranked = (applicants - missing).sorted(
                lambda a: (-a.aggregate, -(a.test_percent or 0), -(a.inter_percent or 0), a.id))
            seats = reg.max_count or len(ranked)
            for i, a in enumerate(ranked, start=1):
                status = "selected" if i <= seats else ("waiting" if i <= seats + reg.waiting_count else "not_selected")
                a.write({"merit_rank": i, "merit_status": status})
            missing.write({"merit_rank": 0, "merit_status": "pending"})
            reg.merit_generated_on = fields.Datetime.now()
            reg.message_post(body=_("Merit list: %(n)s ranked, %(sel)s selected, %(wait)s waiting, %(miss)s without test marks.",
                                    n=len(ranked), sel=min(seats, len(ranked)),
                                    wait=len(ranked.filtered(lambda a: a.merit_status == "waiting")), miss=len(missing)))
        return True

    def action_send_offers(self):
        for reg in self:
            todo = reg._applicants().filtered(lambda a: a.merit_status == "selected" and not a.offer_sent_on)
            if not todo:
                raise UserError(_("No selected applicant is waiting for an offer. Generate the merit list first."))
            todo.action_send_offer()
        return True

    def action_open_merit_list(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Merit list"), "res_model": "op.admission",
            "view_mode": "list,form", "views": [(self.env.ref("icterp_edu_admission.admission_merit_view_list").id, "list"), (False, "form")],
            "domain": [("register_id", "=", self.id), ("state", "in", list(ACTIVE_STATES))],
            "context": {"search_default_ranked": 1},
        }
