from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class IcterpGradeScale(models.Model):
    _name = "icterp.grade.scale"
    _description = "Grade scale"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    line_ids = fields.One2many("icterp.grade.scale.line", "scale_id", string="Grades")

    def _grade_for(self, percent):
        """Letter, grade points and pass flag for a percentage (highest band whose minimum is met)."""
        self.ensure_one()
        for line in self.line_ids.sorted("min_percent", reverse=True):
            if percent + 1e-9 >= line.min_percent:
                return line
        return self.env["icterp.grade.scale.line"]


class IcterpGradeScaleLine(models.Model):
    _name = "icterp.grade.scale.line"
    _description = "Grade band"
    _order = "min_percent desc"

    scale_id = fields.Many2one("icterp.grade.scale", required=True, ondelete="cascade")
    letter = fields.Char(required=True)
    min_percent = fields.Float(string="From %", required=True)
    points = fields.Float(string="Grade points", required=True, digits=(4, 2))
    is_pass = fields.Boolean(default=True)

    @api.constrains("min_percent", "points")
    def _check_values(self):
        for line in self:
            if not 0 <= line.min_percent <= 100:
                raise ValidationError(_("A grade band must start between 0 and 100 percent."))
            if line.points < 0:
                raise ValidationError(_("Grade points cannot be negative."))
