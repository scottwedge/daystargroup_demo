#-*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Sunray Payroll Extend',
    'category': 'Human Resources',
    'sequence': 38,
    'website': 'https://mceesolutions.com',
    'depends': [
        'hr_payroll',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_payslip_view.xml',
        'views/hr_payroll_report.xml',
        'views/report_sunraypayslipdetails_templates.xml',
        'wizard/payroll_register_view.xml',
        'views/pfa_view.xml',
    ],
}
