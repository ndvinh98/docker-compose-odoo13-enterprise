# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Product Lifecycle Management (PLM)',
    'version': '1.0',
    'category': 'Manufacturing/PLM',
    'sequence': 50,
    'summary': """Manage engineering change orders on products, bills of material and routings""",
    'website': 'https://www.odoo.com/page/mrp-plm',
    'depends': ['mrp'],
    'description': """
Product Life Management
=======================

* Versioning of Bill of Materials and Routings
* Different approval flows possible depending on the type of change order

""",
    'data': [
        'security/mrp_plm.xml',
        'security/ir.model.access.csv',
        'data/mrp_data.xml',
        'views/mrp_bom_views.xml',
        'views/mrp_document_views.xml',
        'views/mrp_eco_templates.xml',
        'views/mrp_eco_views.xml',
        'views/product_views.xml',
        'views/mrp_routing_views.xml',
        'report/mrp_report_bom_structure.xml',
    ],
    'qweb': [
        'static/src/xml/mrp_plm_templates.xml'
    ],
    'demo': [],
    'application': True,
    'license': 'OEEL-1',
}
