from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class IcterpBulkEnroll(models.TransientModel):
    _name = "icterp.bulk.enroll"
    _description = "Enrol students in a course"

    offering_id = fields.Many2one("icterp.course.offering", required=True)
    student_ids = fields.Many2many("op.student", string="Students")
    result_note = fields.Text(readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        offering = self.env["icterp.course.offering"].browse(res.get("offering_id") or self.env.context.get("default_offering_id"))
        if offering and "student_ids" in fields_list:
            domain = [("course_id", "=", offering.course_id.id), ("state", "!=", "finished")]
            if offering.batch_id:
                domain.append(("batch_id", "=", offering.batch_id.id))
            students = self.env["op.student.course"].search(domain).mapped("student_id")
            students -= offering.enrollment_ids.filtered(lambda e: e.state in ("enrolled", "completed")).mapped("student_id")
            res["student_ids"] = [(6, 0, students.ids)]
        return res

    def action_enroll(self):
        self.ensure_one()
        Enr = self.env["icterp.enrollment"]
        done, problems = 0, []
        for student in self.student_ids:
            if self.offering_id.enrollment_ids.filtered(lambda e: e.student_id == student):
                continue
            try:
                with self.env.cr.savepoint():
                    Enr.create({"student_id": student.id, "offering_id": self.offering_id.id})
                done += 1
            except ValidationError as e:
                problems.append("%s: %s" % (student.name, e.args[0] if e.args else e))
        note = _("%s enrolled.", done)
        if problems:
            note += "\n" + _("Not enrolled:") + "\n" + "\n".join(problems)
        self.result_note = note
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}
