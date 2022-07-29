# -*- coding: utf-8 -*-

{
    'name': 'Settlement & Gratuity UAE',
    'version': '15.0',
    'category': 'HR',
    'summary': 'HR Management',
    'description': """
                    final settlement,
                    gratuity,
                    """,
    'author': 'TecbotErp',
    'website': "https://techboterp.com",
    'company': 'TechbotErp',

    'depends': ['base', 'hr_payroll', 'hr_contract', 'hr_holidays', 'account'],
    'data': [
        'data/data.xml',
        'security/ir.model.access.csv',
        'views/settlement_type.xml',
        'views/hr_settlement_view.xml',

    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}

