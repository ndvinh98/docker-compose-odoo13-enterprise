# -*- coding: utf-8 -*-

import base64
from odoo.tests.common import HttpCase, tagged, SavepointCase, TransactionCase, post_install

GIF = b"R0lGODdhAQABAIAAAP///////ywAAAAAAQABAAACAkQBADs="
TEXT = base64.b64encode(bytes("workflow bridge product", 'utf-8'))


@tagged('post_install', '-at_install')
class TestCaseDocumentsBridgeProduct(TransactionCase):
    
    def setUp(self):
        super(TestCaseDocumentsBridgeProduct, self).setUp()
        self.folder_test = self.env['documents.folder'].create({'name': 'folder_test'})
        self.company_test = self.env['res.company'].create({
            'name': 'test bridge products',
            'product_folder': self.folder_test.id,
            'documents_product_settings': False
        })
        self.template_test = self.env['product.template'].create({
            'name': 'template_test',
            'company_id': self.company_test.id
        })
        self.product_test = self.template_test.product_variant_id
        self.attachment_txt_two = self.env['ir.attachment'].create({
            'datas': TEXT,
            'name': 'fileTextTwo.txt',
            'mimetype': 'text/plain',
        })
        self.attachment_gif_two = self.env['ir.attachment'].create({
            'datas': GIF,
            'name': 'fileTwoGif.gif',
            'mimetype': 'image/gif',
        })

    def test_bridge_folder_product_settings_on_write(self):
        """
        Makes sure the settings apply their values when a document is assigned a res_model, res_id.
        """
        self.company_test.write({'documents_product_settings': True})
        
        self.attachment_gif_two.write({
            'res_model': 'product.product',
            'res_id': self.product_test.id
        })
        self.attachment_txt_two.write({
            'res_model': 'product.template',
            'res_id': self.template_test.id
        })

        txt_doc = self.env['documents.document'].search([('attachment_id', '=', self.attachment_txt_two.id)])
        gif_doc = self.env['documents.document'].search([('attachment_id', '=', self.attachment_gif_two.id)])

        self.assertEqual(txt_doc.folder_id, self.folder_test, 'the text two document should have a folder')
        self.assertEqual(gif_doc.folder_id, self.folder_test, 'the gif two document should have a folder')

    def test_bridge_folder_product_settings_default_company(self):
        """
        Makes sure the settings apply their values when a document is assigned a res_model, res_id but when
        the product/template doesn't have a company_id.
        """
        company_test = self.env['res.company'].create({
            'name': 'test bridge products two',
            'product_folder': self.folder_test.id,
            'documents_product_settings': True,
        })
        test_user = self.env['res.users'].create({
            'name': "documents test documents user",
            'login': "dtdu",
            'email': "dtdu@yourcompany.com",
            # group_system is used as it is required to write on product.product and product.template
            'groups_id': [(6, 0, [self.ref('documents.group_documents_user'), self.ref('base.group_system')])],
            'company_ids': [(6, 0, [company_test.id])],
            'company_id': company_test.id,
        })
        template_test = self.env['product.template'].create({
            'name': 'template_test',
        })
        self.attachment_txt_two.with_user(test_user).write({
            'res_model': 'product.template',
            'res_id': template_test.id,
        })
        txt_doc = self.env['documents.document'].search([('attachment_id', '=', self.attachment_txt_two.id)])
        self.assertEqual(txt_doc.folder_id, self.folder_test, 'the text two document should have a folder')

        product_test = self.env['product.product'].create({
            'name': 'product_test',
        })
        self.attachment_gif_two.with_user(test_user).write({
            'res_model': 'product.product',
            'res_id': product_test.id,
        })
        gif_doc = self.env['documents.document'].search([('attachment_id', '=', self.attachment_gif_two.id)])
        self.assertEqual(gif_doc.folder_id, self.folder_test, 'the gif two document should have a folder')

    def test_default_res_id_model(self):
        """
        Test default res_id and res_model from context are used for document creation.
        """
        self.company_test.write({'documents_product_settings': True})

        attachment = self.env['ir.attachment'].with_context(
            default_res_id=self.product_test.id,
            default_res_model=self.product_test._name,
        ).create({
            'datas': GIF,
            'name': 'fileTwoGif.gif',
            'mimetype': 'image/gif',
        })
        document = self.env['documents.document'].search([('attachment_id', '=', attachment.id)])
        self.assertTrue(document, "It should have created a document from default values")

    def test_create_product_from_workflow(self):

        document_gif = self.env['documents.document'].create({
            'datas': GIF,
            'name': 'file.gif',
            'mimetype': 'image/gif',
            'folder_id': self.folder_test.id,
        })

        workflow_rule = self.env['documents.workflow.rule'].create({
            'domain_folder_id': self.folder_test.id,
            'name': 'workflow product',
            'create_model': 'product.template',
        })

        action = workflow_rule.apply_actions([document_gif.id])
        new_product = self.env['product.template'].browse([action['res_id']])

        self.assertEqual(document_gif.res_model, 'product.template')
        self.assertEqual(document_gif.res_id, new_product.id)
        self.assertEqual(new_product.image_1920, document_gif.datas)
