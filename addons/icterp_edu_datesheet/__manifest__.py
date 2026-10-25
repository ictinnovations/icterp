{
    "name": "ICTERP Education: Date Sheets, Seating Plans and Invigilation",
    "summary": "Exam date sheets per term, clash checks, seating plans that mix subjects, invigilator duties and student exam slips",
    "description": "Exam scheduling for ICTERP Education. See README.md.",
    "version": "19.0.1.0.0",
    "category": "Education",
    "author": "ICT Innovations",
    "website": "https://icterp.com",
    "license": "LGPL-3",
    "depends": ["icterp_edu_academics", "openeducat_classroom"],
    "data": [
        "security/ir.model.access.csv",
        "report/datesheet_reports.xml",
        "views/exam_schedule_views.xml",
        "views/portal_templates.xml",
        "views/menus.xml",
    ],
    "installable": True,
}
