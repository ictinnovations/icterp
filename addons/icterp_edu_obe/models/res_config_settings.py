from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    obe_student_threshold = fields.Float(string="Student attains a CLO/PLO at (%)", default=50.0,
                                         config_parameter="icterp_edu_obe.student_threshold")
    obe_class_threshold = fields.Float(string="Class attains a CLO when this % of students attain it", default=60.0,
                                       config_parameter="icterp_edu_obe.class_threshold")
