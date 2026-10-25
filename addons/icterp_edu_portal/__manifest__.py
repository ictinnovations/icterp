{
    "name": "ICTERP Education: Student and Parent Portal",
    "summary": "Students and parents see timetable, attendance, results, assignments, fees and library loans in the portal",
    "description": "Adds an Education section to the ICTERP customer portal for students and parents. See README.md.",
    "version": "19.0.1.1.0",
    "category": "Education",
    "author": "ICT Innovations",
    "website": "https://icterp.com",
    "license": "LGPL-3",
    "depends": ["portal", "icterp_education"],
    "data": [
        "views/portal_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "icterp_edu_portal/static/src/scss/portal.scss",
        ],
    },
    "installable": True,
}
