{
    "name": "ICTERP Home",
    "summary": "App home page with grouped tiles, opened after sign-in",
    "version": "19.0.1.0.1",
    "license": "LGPL-3",
    "author": "ICT Innovations",
    "depends": ["web", "base_setup", "icterp_branding"],
    "data": [
        "security/ir.model.access.csv",
        "data/home_data.xml",
        "views/home_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "icterp_home/static/src/home.js",
            "icterp_home/static/src/home.xml",
            "icterp_home/static/src/home.scss",
        ],
    },
    "post_init_hook": "_set_home_for_users",
    "uninstall_hook": "_clear_home_for_users",
    "installable": True,
}
