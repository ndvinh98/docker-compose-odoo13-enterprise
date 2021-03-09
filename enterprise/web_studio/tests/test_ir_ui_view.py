from odoo.tests.common import TransactionCase


class TestIrUiView(TransactionCase):
    def test_search_view_xml(self):
        self.env['ir.ui.view'].with_context(studio=1, check_field_names=False).create({
            'type': 'search',
            'model': 'res.partner',
            'name': 'web_studio.test_search_view_xml',
            'key': 'web_studio.test_search_view_xml',
            'arch': '''
                <search>
                    <searchpanel>
                        <field name="company_id" groups="base.group_multi_company"/>
                    </searchpanel>
                </search>
            ''',
        })
