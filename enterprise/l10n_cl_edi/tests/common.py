# -*- coding: utf-8 -*-
import base64
import logging

from odoo.addons.account.tests.account_test_xml import AccountTestEdiCommon

from odoo import fields
from odoo.tests import tagged
from odoo.tools import misc, os, relativedelta

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestL10nClEdiCommon(AccountTestEdiCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref='l10n_cl.cl_chart_template'):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.company_data['company'].write({
            'country_id': cls.env.ref('base.cl').id,
            'currency_id': cls.env.ref('base.CLP').id,
            'name': 'Blanco Martin & Asociados EIRL',
            'street': 'Apoquindo 6410',
            'city': 'Les Condes',
            'phone': '+1 (650) 691-3277 ',
            'l10n_cl_dte_service_provider': 'SIITEST',
            'l10n_cl_dte_resolution_number': 0,
            'l10n_cl_dte_resolution_date': '2019-10-20',
            'l10n_cl_dte_email': 'info@bmya.cl',
            'l10n_cl_sii_regional_office': 'ur_SaC',
            'l10n_cl_company_activity_ids': [(6, 0, [cls.env.ref('l10n_cl_edi.eco_new_acti_620200').id])],
        })
        cls.company_data['company'].partner_id.write({
            'l10n_cl_sii_taxpayer_type': '1',
            'vat': 'CL762012243',
            'l10n_cl_activity_description': 'activity_test',
        })
        cls.certificate = cls.env['l10n_cl.certificate'].sudo().create({
            'signature_filename': 'Test',
            'subject_serial_number': '23841194-7',
            'signature_pass_phrase': 'asadadad',
            'private_key': misc.file_open(os.path.join('l10n_cl_edi', 'tests', 'private_key_test.key')).read(),
            'certificate': misc.file_open(os.path.join('l10n_cl_edi', 'tests', 'cert_test.cert')).read(),
            'cert_expiration': fields.Datetime.now() + relativedelta(years=1),
            'company_id': cls.company_data['company'].id
        })
        cls.company_data['company'].write({
            'l10n_cl_certificate_ids': [(4, cls.certificate.id)]
        })

        cls.partner_sii = cls.env['res.partner'].create({
            'name': 'Partner SII',
            'is_company': 1,
            'city': 'Pudahuel',
            'country_id': cls.env.ref('base.cl').id,
            'street': 'Puerto Test 102',
            'phone': '+562 0000 0000',
            'website': 'http://www.partner_sii.cl',
            'company_id': cls.company_data['company'].id,
            'l10n_cl_dte_email': 'partner@sii.cl',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_cl.it_RUT').id,
            'l10n_cl_sii_taxpayer_type': '1',
            'l10n_cl_activity_description': 'activity_test',
            'vat': '76086428-5',
        })

        cls.partner_anonimo = cls.env['res.partner'].create({
            'name': 'Consumidor Final Anonimo',
            'l10n_cl_sii_taxpayer_type': '3',
            'street': '',
            'street2': '',
            'country_id': cls.env.ref('base.cl').id,
            'vat': '66666666-6',
        })
        cls.sale_journal = cls.env['account.journal'].create({
            'name': 'Sale Journal Test',
            'type': 'sale',
            'code': 'INV',
            'l10n_cl_point_of_sale_type': 'online',
            'l10n_latam_use_documents': True,
            'currency_id': cls.env.ref('base.CLP').id,
        })

        cls.sequence_34 = cls.sale_journal.l10n_cl_sequence_ids.filtered(
            lambda r: r.l10n_latam_document_type_id.code == '34')
        caf34_file = misc.file_open(os.path.join(
            'l10n_cl_edi', 'tests', 'folios', 'folio_sii_doc_34.xml')).read()
        caf34_file = base64.b64encode(caf34_file.encode('utf-8'))
        cls.caf_factura_afecta = cls.env['l10n_cl.dte.caf'].sudo().create({
            'filename': 'FoliosSII7620122434221201910221946.xml',
            'caf_file': caf34_file,
            'issued_date': '2019-10-22',
            'start_nb': 1,
            'final_nb': 100,
            'sequence_id': cls.sequence_34.id,
            'status': 'in_use',
        })

        cls.sequence_33 = cls.sale_journal.l10n_cl_sequence_ids.filtered(
            lambda r: r.l10n_latam_document_type_id.code == '33')
        caf33_file = misc.file_open(os.path.join(
            'l10n_cl_edi', 'tests', 'folios', 'folio_sii_doc_33.xml')).read()
        caf33_file = base64.b64encode(caf33_file.encode('utf-8'))
        cls.caf_33 = cls.env['l10n_cl.dte.caf'].sudo().create({
            'filename': 'FoliosSII7620122433321201910221946.xml',
            'caf_file': caf33_file,
            'issued_date': '2019-10-22',
            'start_nb': 1,
            'final_nb': 100,
            'sequence_id': cls.sequence_33.id,
            'status': 'in_use',
        })

        cls.sequence_39 = cls.sale_journal.l10n_cl_sequence_ids.filtered(
            lambda r: r.l10n_latam_document_type_id.code == '39')
        caf39_file = misc.file_open(os.path.join(
            'l10n_cl_edi', 'tests', 'folios', 'folio_sii_doc_39.xml')).read()
        caf39_file = base64.b64encode(caf39_file.encode('utf-8'))
        cls.caf_39 = cls.env['l10n_cl.dte.caf'].sudo().create({
            'filename': 'FoliosSII7620122433921201910221946.xml',
            'caf_file': caf39_file,
            'issued_date': '2019-10-22',
            'start_nb': 1,
            'final_nb': 100,
            'sequence_id': cls.sequence_39.id,
            'status': 'in_use',
        })

        cls.sequence_56 = cls.sale_journal.l10n_cl_sequence_ids.filtered(
            lambda r: r.l10n_latam_document_type_id.code == '56')
        cls.sequence_56.write({
            'number_next': 122,
        })
        caf56_file = misc.file_open(os.path.join(
            'l10n_cl_edi', 'tests', 'folios', 'folio_sii_doc_56.xml')).read()
        caf56_file = base64.b64encode(caf56_file.encode('utf-8'))
        cls.caf_56 = cls.env['l10n_cl.dte.caf'].sudo().create({
            'filename': 'FoliosSII7620122435621201910221946.xml',
            'caf_file': caf56_file,
            'issued_date': '2019-10-22',
            'start_nb': 122,
            'final_nb': 200,
            'sequence_id': cls.sequence_56.id,
            'status': 'in_use',
        })

        l10n_latam_document_type_110 = cls.env.ref('l10n_cl.dc_fe_dte')
        l10n_latam_document_type_110.write({'active': True})
        sequence_110 = cls.env['ir.sequence'].create({
            'name': 'Sequence 110',
            'padding': 6,
            'implementation': 'no_gap',
            'l10n_latam_document_type_id': l10n_latam_document_type_110.id,
            'number_next': 1,
            'prefix': None
        })
        cls.sale_journal.write({'l10n_cl_sequence_ids': [(4, sequence_110.id)]})
        cls.sequence_110 = cls.sale_journal.l10n_cl_sequence_ids.filtered(
            lambda r: r.l10n_latam_document_type_id.code == '110')
        caf110_file = misc.file_open(os.path.join(
            'l10n_cl_edi', 'tests', 'folios', 'folio_sii_doc_110.xml')).read()
        caf110_file = base64.b64encode(caf110_file.encode('utf-8'))
        cls.caf_110 = cls.env['l10n_cl.dte.caf'].sudo().create({
            'filename': 'FoliosSII76201224311021201910221946.xml',
            'caf_file': caf110_file,
            'issued_date': '2019-10-22',
            'start_nb': 1,
            'final_nb': 100,
            'sequence_id': cls.sequence_110.id,
            'status': 'in_use',
        })

    def xml_serializer(self, dte):
        return dte.encode()
