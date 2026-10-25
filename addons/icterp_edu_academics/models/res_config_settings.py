from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    edu_warning_below = fields.Float(string="Warning below CGPA", default=2.2,
                                     config_parameter="icterp_edu_academics.warning_below")
    edu_probation_below = fields.Float(string="Probation below CGPA", default=2.0,
                                       config_parameter="icterp_edu_academics.probation_below")
    edu_suspension_after = fields.Integer(string="Suspension after consecutive probations", default=2,
                                          config_parameter="icterp_edu_academics.suspension_after")
