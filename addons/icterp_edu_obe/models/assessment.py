from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class IcterpAssessmentComponent(models.Model):
    _inherit = "icterp.assessment.component"

    subject_id = fields.Many2one(related="offering_id.subject_id")
    clo_id = fields.Many2one("icterp.obe.clo", string="CLO", domain="[('subject_id', '=', subject_id)]",
                             help="Use when the whole assessment measures one CLO. With questions, map each question instead.")


class IcterpAssessmentQuestion(models.Model):
    _inherit = "icterp.assessment.question"

    subject_id = fields.Many2one(related="component_id.offering_id.subject_id")
    clo_id = fields.Many2one("icterp.obe.clo", string="CLO", domain="[('subject_id', '=', subject_id)]")

    @api.constrains("clo_id")
    def _check_clo_subject(self):
        for q in self:
            if q.clo_id and q.clo_id.subject_id != q.component_id.offering_id.subject_id:
                raise ValidationError(_("%s belongs to another subject.", q.clo_id.display_name))


class IcterpCourseOffering(models.Model):
    _inherit = "icterp.course.offering"

    clo_attainment_ids = fields.One2many("icterp.obe.class.clo", "offering_id", string="CLO attainment")
    obe_computed_on = fields.Datetime(readonly=True)

    def action_compute_clo_attainment(self):
        self.env["icterp.obe.class.clo"]._compute_for(self)
        return True

    def action_print_clo_report(self):
        return self.env.ref("icterp_edu_obe.action_report_clo").report_action(self)
