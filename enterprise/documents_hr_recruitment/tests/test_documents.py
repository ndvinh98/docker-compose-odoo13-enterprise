# -*- coding: utf-8 -*-

from odoo.tests.common import tagged, TransactionCase, post_install

GIF = b"R0lGODdhAQABAIAAAP///////ywAAAAAAQABAAACAkQBADs="


@tagged('post_install', '-at_install')
class TestCaseDocumentsBridgeRecruitment(TransactionCase):

    def setUp(self):
        super(TestCaseDocumentsBridgeRecruitment, self).setUp()
        self.folder = self.env['documents.folder'].create({'name': 'folder_test'})
        self.company = self.env['res.company'].create({
            'name': 'test bridge recruitment',
            'recruitment_folder_id': self.folder.id,
            'documents_recruitment_settings': True,
        })

    def test_job_attachment(self):
        """
        Document is created from job attachment
        """
        job = self.env['hr.job'].create({
            'name': 'Cobble Dev :/',
            'company_id': self.company.id
        })
        attachment = self.env['ir.attachment'].create({
            'datas': GIF,
            'name': 'fileTextTwo.txt',
            'mimetype': 'text/plain',
            'res_model': job._name,
            'res_id': job.id
        })

        doc = self.env['documents.document'].search([('attachment_id', '=', attachment.id)])

        self.assertTrue(doc, "It should have created a document")
        self.assertEqual(doc.folder_id, self.folder, "It should be in the the correct folder")

    def test_applicant_attachment(self):
        """
        Document is created from applicant attachment
        """
        applicant = self.env['hr.applicant'].create({
            'name': 'Applicant',
            'company_id': self.company.id,
        })
        attachment = self.env['ir.attachment'].create({
            'datas': GIF,
            'name': 'fileTextTwo.txt',
            'mimetype': 'text/plain',
            'res_model': applicant._name,
            'res_id': applicant.id,
        })

        doc = self.env['documents.document'].search([('attachment_id', '=', attachment.id)])

        self.assertTrue(doc, "It should have created a document")
        self.assertEqual(doc.folder_id, self.folder, "It should be in the the correct folder")
