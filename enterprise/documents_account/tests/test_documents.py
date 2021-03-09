# -*- coding: utf-8 -*-

import base64
from odoo.tests.common import HttpCase, tagged, SavepointCase, TransactionCase, post_install

GIF = b"R0lGODdhAQABAIAAAP///////ywAAAAAAQABAAACAkQBADs="
TEXT = base64.b64encode(bytes("workflow bridge account", 'utf-8'))


@tagged('post_install', '-at_install', 'test_document_bridge')
class TestCaseDocumentsBridgeAccount(TransactionCase):

    def setUp(self):
        super(TestCaseDocumentsBridgeAccount, self).setUp()
        self.folder_a = self.env['documents.folder'].create({
            'name': 'folder A',
        })
        self.folder_a_a = self.env['documents.folder'].create({
            'name': 'folder A - A',
            'parent_folder_id': self.folder_a.id,
        })
        self.document_txt = self.env['documents.document'].create({
            'datas': TEXT,
            'name': 'file.txt',
            'mimetype': 'text/plain',
            'folder_id': self.folder_a_a.id,
        })
        self.document_gif = self.env['documents.document'].create({
            'datas': GIF,
            'name': 'file.gif',
            'mimetype': 'image/gif',
            'folder_id': self.folder_a.id,
        })

        self.workflow_rule_vendor_bill = self.env['documents.workflow.rule'].create({
            'domain_folder_id': self.folder_a.id,
            'name': 'workflow rule create vendor bill on f_a',
            'create_model': 'account.move.in_invoice',
        })

    def test_bridge_folder_workflow(self):
        """
        tests the create new business model (vendor bill & credit note).

        """
        self.assertEqual(self.document_txt.res_model, 'documents.document', "failed at default res model")
        multi_return = self.workflow_rule_vendor_bill.apply_actions([self.document_txt.id, self.document_gif.id])
        self.assertEqual(multi_return.get('type'), 'ir.actions.act_window',
                         'failed at invoice workflow return value type')
        self.assertEqual(multi_return.get('res_model'), 'account.move',
                         'failed at invoice workflow return value res model')

        self.assertEqual(self.document_txt.res_model, 'account.move', "failed at workflow_bridge_dms_account"
                                                                           " new res_model")
        vendor_bill_txt = self.env['account.move'].search([('id', '=', self.document_txt.res_id)])
        self.assertTrue(vendor_bill_txt.exists(), 'failed at workflow_bridge_dms_account vendor_bill')
        self.assertEqual(self.document_txt.res_id, vendor_bill_txt.id, "failed at workflow_bridge_dms_account res_id")
        self.assertEqual(vendor_bill_txt.type, 'in_invoice', "failed at workflow_bridge_dms_account vendor_bill type")
        vendor_bill_gif = self.env['account.move'].search([('id', '=', self.document_gif.res_id)])
        self.assertEqual(self.document_gif.res_id, vendor_bill_gif.id, "failed at workflow_bridge_dms_account res_id")

        single_return = self.workflow_rule_vendor_bill.apply_actions([self.document_txt.id])
        self.assertEqual(single_return.get('res_model'), 'account.move',
                         'failed at invoice res_model action from workflow create model')
        invoice = self.env[single_return['res_model']].browse(single_return.get('res_id'))
        attachments = self.env['ir.attachment'].search([('res_model', '=', 'account.move'), ('res_id', '=', invoice.id)])
        self.assertEqual(len(attachments), 1, 'there should only be one ir attachment matching')

    def test_bridge_account_account_settings_on_write(self):
        """
        Makes sure the settings apply their values when an ir_attachment is set as message_main_attachment_id
        on invoices.
        """
        folder_test = self.env['documents.folder'].create({'name': 'folder_test'})
        self.env.user.company_id.documents_account_settings = True

        for invoice_type in ['in_invoice', 'out_invoice', 'in_refund', 'out_refund']:
            invoice_test = self.env['account.move'].with_context(default_type=invoice_type).create({
                'name': 'invoice_test',
                'type': invoice_type,
            })
            setting = self.env['documents.account.folder.setting'].create({
                'folder_id': folder_test.id,
                'journal_id': invoice_test.journal_id.id,
            })
            attachment_txt_test = self.env['ir.attachment'].create({
                'datas': TEXT,
                'name': 'fileText_test.txt',
                'mimetype': 'text/plain',
                'res_model': 'account.move',
                'res_id': invoice_test.id
            })
            attachment_txt_alternative_test = self.env['ir.attachment'].create({
                'datas': TEXT,
                'name': 'fileText_test_alternative.txt',
                'mimetype': 'text/plain',
                'res_model': 'account.move',
                'res_id': invoice_test.id
            })
            attachment_txt_main_attachment_test = self.env['ir.attachment'].create({
                'datas': TEXT,
                'name': 'fileText_main_attachment.txt',
                'mimetype': 'text/plain',
                'res_model': 'account.move',
                'res_id': invoice_test.id
            })

            invoice_test.write({'message_main_attachment_id': attachment_txt_test.id})
            txt_doc = self.env['documents.document'].search([('attachment_id', '=', attachment_txt_test.id)])
            self.assertEqual(txt_doc.folder_id, folder_test, 'the text test document have a folder')
            invoice_test.write({'message_main_attachment_id': attachment_txt_alternative_test.id})
            self.assertEqual(txt_doc.attachment_id.id, attachment_txt_alternative_test.id,
                             "the attachment of the document should have swapped")
            attachment_txt_main_attachment_test.register_as_main_attachment()
            self.assertEqual(txt_doc.attachment_id.id, attachment_txt_main_attachment_test.id,
                             "the attachment of the document should have swapped")
            # deleting the setting to prevent duplicate settings.
            setting.unlink()

    def test_reconciliation_request(self):
        account_type_test = self.env['account.account.type'].create({'name': 'account type test', 'type': 'other', 'internal_group': 'asset'})
        account_test = self.env['account.account'].create(
            {'name': 'Receivable', 'code': '0000222', 'user_type_id': account_type_test.id, 'reconcile': True})
        journal_test = self.env['account.journal'].create({'name': 'journal test', 'type': 'bank', 'code': 'BNK67'})
        account_move_test = self.env['account.move'].create(
            {'name': 'account move test', 'state': 'draft', 'journal_id': journal_test.id})
        account_move_line_test = self.env['account.move.line'].create({
            'name': 'account move line test',
            'move_id': account_move_test.id,
            'account_id': account_test.id,
        })
        account_move_test.post()

        document_test = self.env['documents.document'].create({
            'name': 'test reconciliation workflow',
            'folder_id': self.folder_a.id,
            'res_model': 'account.move.line',
            'res_id': account_move_line_test.id,
            'datas': TEXT,
        })

        action = self.workflow_rule_vendor_bill.apply_actions([document_test.id])
        self.assertEqual(action['res_model'], 'account.move', 'a new invoice should be generated')
        invoice = self.env['account.move'].browse(action['res_id'])
        self.assertEqual(invoice.document_request_line_id.id, account_move_line_test.id,
                         'the new invoice should store the ID of the move line on which its document was attached')
