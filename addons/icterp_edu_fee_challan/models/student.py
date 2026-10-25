from odoo import fields, models


class OpStudent(models.Model):
    _inherit = "op.student"

    challan_ids = fields.One2many("icterp.fee.challan", "student_id", string="Challans")
    scholarship_ids = fields.One2many("icterp.student.scholarship", "student_id", string="Scholarships")
    challan_count = fields.Integer(compute="_compute_challan_count")

    def _compute_challan_count(self):
        for s in self:
            s.challan_count = len(s.challan_ids)

    def action_open_challans(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("icterp_edu_fee_challan.challan_action")
        action["domain"] = [("student_id", "=", self.id)]
        action["context"] = {"default_student_id": self.id}
        return action

    def _unpaid_overdue_challans(self):
        """Issued challans past their due date (used to hold exam slips, if that module is installed)."""
        today = fields.Date.context_today(self)
        return self.challan_ids.filtered(lambda c: c.state == "issued" and c.due_date and c.due_date < today)
