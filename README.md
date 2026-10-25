# ICTERP Community for Odoo 19

ICTERP is open source ERP built on [Odoo Community 19](https://github.com/odoo/odoo). This repository holds the ICTERP Community modules: branding, the app home page, the education suite (from admissions to GPA, fee challans, date sheets and OBE) and payroll. Calling, campaigns and live chat come from our ICTContact and ICTDesk products, which connect to ICTERP Enterprise.

Everything here is released under the LGPL-3, the same licence as Odoo Community.

Website and user guides: [icterp.com](https://icterp.com) | Built by [ICT Innovations](https://www.ictinnovations.com), maintained by Tahir Almas

## Built for Odoo 19 Community

| | |
|---|---|
| Odoo | 19.0 Community edition (tested on the official `odoo:19.0` image) |
| Python | 3.10 or newer, as Odoo 19 requires |
| PostgreSQL | 13 or newer (tested on 16) |
| Licence | LGPL-3, like Odoo Community |
| Odoo Enterprise | Not needed and not used. ICTERP contains no Enterprise code |

This branch targets Odoo 19. We move ICTERP to each new Odoo Community version once a year.

## Why ICTERP instead of plain Odoo Community

Odoo Community is an excellent base, but several things people expect from an ERP are only in the paid Enterprise edition. ICTERP fills those gaps with open source modules.

| | Odoo 19 Community | ICTERP Community |
|---|---|---|
| App home page after sign-in | No (Enterprise only) | Yes: grouped app tiles, configurable from Settings |
| Payroll | No (Enterprise only) | Yes: salary structures, payslips and batches (OCA Payroll) |
| Your own name and look | Odoo branding, links to odoo.com | ICTERP name, icons, colours and emails; odoo.com links and upsells removed |
| School, college and university management | No | Yes: students, admissions, timetable, attendance, exams, fees and library |
| Student and parent portal | No | Yes: timetable, attendance, results, assignments, fees and challans |
| University registration, GPA, CGPA and transcripts | No | Yes |
| Bank fee challans, fines and scholarships | No | Yes, with bank file import |
| Exam date sheets, seating plans and invigilation | No | Yes, with clash checks |
| Online admissions with entry tests and merit lists | No | Yes, with offer letters and admission fee challans |
| Outcome based education (PEO, PLO, CLO) | No | Yes, with attainment reports for accreditation |
| Third-party usage reporting | n/a | OpenEduCat's daily usage report is switched off |

Calling from the CRM (Odoo's VoIP app is Enterprise only) and website chat history are available as ICTERP Enterprise add-ons through ICTContact and ICTDesk.

## Modules

| Area | Module | What it does |
|---|---|---|
| Core | `icterp_branding` | ICTERP name, colours, icons and wording in place of the Odoo branding |
| Core | `icterp_home` | App home page with grouped tiles, opened after sign-in |
| Core | `icterp_website` | Keeps the ICTERP sign-in page and removes the Odoo generator tag when the Website app is installed |
| Education | `icterp_education` | School, college and university management for ICTERP: students, admissions, timetable, attendance, exams, fees and library |
| Education | `icterp_edu_portal` | Students and parents see timetable, attendance, results, assignments, fees and library loans in the portal |
| Education | `icterp_edu_academics` | Course offerings per term, student course registration (enrol, drop, withdraw), assessment marks, GPA/CGPA, academic standing and transcripts |
| Education | `icterp_edu_fee_challan` | Bank fee challans (3 copies), payment confirmation and bank-file import, late payment fines, scholarships and waivers |
| Education | `icterp_edu_datesheet` | Exam date sheets per term, clash checks, seating plans that mix subjects, invigilator duties and student exam slips |
| Education | `icterp_edu_admission` | Online application form, entry test roll numbers and admit cards, weighted merit lists, offer letters and admission fee challans |
| Education | `icterp_edu_obe` | PEOs, PLOs and CLOs with Bloom levels, assessments and questions mapped to CLOs, CLO and PLO attainment for HEC/PEC accreditation |
| HR | `icterp_payroll` | Salary structures, payslips and payslip batches for ICTERP (OCA Payroll, LGPL-3) |

## Community and Enterprise

Every module in this repository is open source and free to use. Enterprise adds our communication products, their connectors, ICT Billing and our team.

| | Community | Enterprise |
|---|---|---|
| ICTERP Community modules in this repository | Yes | Yes |
| Calling, campaigns and AI voice agent workflows | | ICTContact / ICTCRM add-on with its own licence |
| Website live chat history on contacts and leads | | ICTDesk add-on |
| ICT Billing to manage and bill your own customers | | Included |
| White label set up for you and kept working through upgrades | | Included |
| Setup, support, ICT Monitor and the yearly Odoo upgrade | GitHub issues | Included |

Prices and packages: [icterp.com/packages](https://icterp.com/packages/)

## Quick start (Docker)

```bash
git clone https://github.com/ictinnovations/icterp.git && cd icterp
bash tools/vendor-openeducat.sh addons-vendor/openeducat    # only if you want the education apps
bash tools/fetch-oca-payroll.sh addons-vendor/payroll         # only if you want payroll
mkdir -p addons-vendor/openeducat addons-vendor/payroll     # empty folders are fine
cp .env.example .env            # set a database password
cp config/odoo.conf.example config/odoo.conf   # use the same password as db_password
docker compose up -d
```

Open http://localhost:8069, create a database, then install **ICTERP Branding** and **ICTERP Home** from Apps, followed by any other module you need.

## Running the tests

```bash
docker compose run --rm odoo odoo -c /etc/odoo/odoo.conf -d icterp_test \
  -i icterp_branding,icterp_home --test-enable --stop-after-init
```

Swap in the modules you changed.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Credits

ICTERP stands on the work of these open source projects:

- [Odoo Community](https://github.com/odoo/odoo) by Odoo S.A., LGPL-3. The core ERP platform and its business apps.
- [OpenEduCat Community](https://github.com/openeducat/openeducat_erp) by OpenEduCat Inc., LGPL-3. The base of the education apps.
- [OCA Payroll](https://github.com/OCA/payroll) by the Odoo Community Association, LGPL-3. The payroll engine behind ICTERP Payroll.

Our modules extend these projects. Odoo Community and OCA Payroll are used unchanged. The OpenEduCat fetch script swaps the app icons and display names and turns off its usage reporting; its copyright headers and licence files stay exactly as they are.

## Licence

LGPL-3.0. See [COPYING.LESSER](COPYING.LESSER) and [COPYING](COPYING). OpenEduCat Community and OCA Payroll are fetched from their own repositories under their own LGPL-3 licences and are not bundled here.

ICTERP is built and supported by [ICT Innovations](https://www.ictinnovations.com) and maintained by Tahir Almas. More of our open source work: [ictinnovations.com/projects](https://ictinnovations.com/projects/). Odoo is a trademark of Odoo S.A.; ICTERP is not affiliated with Odoo S.A.
