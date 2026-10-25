from odoo import _, api, fields, models
from odoo.exceptions import UserError


class IcterpGradeChange(models.TransientModel):
    _name = "icterp.grade.change"
    _description = "Change a published grade"

    enrollment_id = fields.Many2one("icterp.enrollment", required=True)
    current_grade = fields.Char(related="enrollment_id.grade_letter")
    new_band_id = fields.Many2one("icterp.grade.scale.line", string="New grade", required=True,
                                  domain="[('scale_id', '=', scale_id)]")
    scale_id = fields.Many2one(related="enrollment_id.offering_id.grade_scale_id")
    reason = fields.Text(required=True)

    def action_apply(self):
        self.ensure_one()
        if not (self.env.su or self.env.user.has_group("openeducat_core.group_op_back_office_admin")):
            raise UserError(_("Only an education manager can change a grade."))
        enr = self.enrollment_id
        old = enr.grade_letter
        enr.with_context(icterp_grade_change=True).write({
            "grade_override": self.new_band_id.letter, "grade_override_points": self.new_band_id.points})
        enr.message_post(body=_("Grade changed from %(old)s to %(new)s by %(user)s. Reason: %(reason)s",
                                old=old or "-", new=self.new_band_id.letter, user=self.env.user.name, reason=self.reason))
        self.env["icterp.term.result"]._recompute_for(enr.student_id)
        return {"type": "ir.actions.act_window_close"}
