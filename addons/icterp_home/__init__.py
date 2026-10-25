from . import models


def _set_home_for_users(env):
    param = env["ir.config_parameter"].sudo()
    param.set_param("icterp_home.enabled", "True")
    param.set_param("icterp_home.show_more", "True")
    env["icterp.home.section"]._icterp_create_defaults()
    env["res.users"]._icterp_home_assign()


def _clear_home_for_users(env):
    env["res.users"]._icterp_home_clear()
