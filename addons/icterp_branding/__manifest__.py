{
    "name": "ICTERP Branding",
    "summary": "ICTERP name, colours, icons and wording in place of the Odoo branding",
    "version": "19.0.1.3.0",
    "license": "LGPL-3",
    "author": "ICT Innovations",
    "depends": ["web", "base_setup", "mail", "auth_signup"],
    "data": [
        "data/branding_data.xml",
        "views/templates.xml",
        "views/res_config_settings_views.xml",
        "views/ir_module_views.xml",
    ],
    "assets": {
        "web._assets_primary_variables": [
            ("prepend", "icterp_branding/static/src/scss/primary_variables.scss"),
        ],
        "web.assets_backend": [
            "icterp_branding/static/src/branding.js",
            "icterp_branding/static/src/scss/branding.scss",
            "icterp_branding/static/src/xml/res_config_edition.xml",
        ],
    },
    "installable": True,
}
