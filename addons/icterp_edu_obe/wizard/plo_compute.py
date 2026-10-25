from odoo import _, fields, models


class IcterpObePloCompute(models.TransientModel):
    _name = "icterp.obe.plo.compute"
    _description = "Compute PLO attainment"

    course_id = fields.Many2one("op.course", string="Programme", required=True)
    term_id = fields.Many2one("op.academic.term", string="Only courses of term", help="Empty = every term.")
    result_note = fields.Text(readonly=True)

    def action_compute(self):
        self.ensure_one()
        domain = [("course_id", "=", self.course_id.id)]
        if self.term_id:
            domain.append(("term_id", "=", self.term_id.id))
        offerings = self.env["icterp.course.offering"].search(domain)
        self.env["icterp.obe.class.clo"]._compute_for(offerings)
        students = offerings.mapped("enrollment_ids").filtered(lambda e: e.state in ("enrolled", "completed")).mapped("student_id")
        self.env["icterp.obe.student.plo"]._compute_for(students)
        attained = self.env["icterp.obe.student.plo"].search_count([("student_id", "in", students.ids), ("attained", "=", True)])
        total = self.env["icterp.obe.student.plo"].search_count([("student_id", "in", students.ids)])
        self.result_note = _("%(o)s courses and %(s)s students processed. %(a)s of %(t)s student PLO results attained.",
                             o=len(offerings), s=len(students), a=attained, t=total)
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}
