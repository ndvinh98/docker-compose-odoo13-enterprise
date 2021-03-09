# -*- coding: utf-8 -*-
{
    'name':"Map View",
    'summary':"Defines the map view for odoo enterprise",
    'description':"Allows the viewing of records on a map",
    'category': 'Hidden',
    'version':'1.0',
    'depends':['web', 'base_setup'],
    'data':[
        "views/assets.xml",
        "views/res_config_settings.xml",
        "views/res_partner.xml",
    ],
    'qweb':[
        "static/xml/templates.xml"
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
