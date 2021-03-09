# -*- coding: utf-8 -*-

import base64
from odoo.tests.common import HttpCase, tagged, SavepointCase, TransactionCase

GIF = b"R0lGODdhAQABAIAAAP///////ywAAAAAAQABAAACAkQBADs="
TEXT = base64.b64encode(bytes("workflow bridge project", 'utf-8'))


class TestCaseDocumentsBridgeProject(TransactionCase):

    def setUp(self):
        super(TestCaseDocumentsBridgeProject, self).setUp()
        self.folder_a = self.env['documents.folder'].create({
            'name': 'folder A',
        })
        self.folder_a_a = self.env['documents.folder'].create({
            'name': 'folder A - A',
            'parent_folder_id': self.folder_a.id,
        })
        self.attachment_txt = self.env['documents.document'].create({
            'datas': TEXT,
            'name': 'file.txt',
            'mimetype': 'text/plain',
            'folder_id': self.folder_a_a.id,
        })
        self.workflow_rule_task = self.env['documents.workflow.rule'].create({
            'domain_folder_id': self.folder_a.id,
            'name': 'workflow rule create task on f_a',
            'create_model': 'project.task',
        })

    def test_bridge_folder_workflow(self):
        """
        tests the create new business model (project).

        """
        self.assertEqual(self.attachment_txt.res_model, 'documents.document', "failed at default res model")
        self.workflow_rule_task.apply_actions([self.attachment_txt.id])

        self.assertEqual(self.attachment_txt.res_model, 'project.task', "failed at workflow_bridge_documents_project"
                                                                        " new res_model")
        task = self.env['project.task'].search([('id', '=', self.attachment_txt.res_id)])
        self.assertTrue(task.exists(), 'failed at workflow_bridge_documents_project task')
        self.assertEqual(self.attachment_txt.res_id, task.id, "failed at workflow_bridge_documents_project res_id")

    def test_bridge_project_project_settings_on_write(self):
        """
        Makes sure the settings apply their values when an document is assigned a res_model, res_id
        """
        folder_test = self.env['documents.folder'].create({'name': 'folder_test'})

        company_test = self.env['res.company'].create({
            'name': 'test bridge projects',
            'project_folder': folder_test.id,
            'documents_project_settings': False
        })
        task_test = self.env['project.task'].create({
            'name': 'task_test',
            'company_id': company_test.id
        })
        project_test = self.env['project.project'].create({
            'name': 'project_test',
            'company_id': company_test.id
        })
        attachment_txt_test = self.env['ir.attachment'].create({
            'datas': TEXT,
            'name': 'fileText_test.txt',
            'mimetype': 'text/plain',
        })
        attachment_gif_test = self.env['ir.attachment'].create({
            'datas': GIF,
            'name': 'fileText_test.txt',
            'mimetype': 'text/plain',
        })

        company_test.write({'documents_project_settings': True})

        attachment_txt_test.write({
            'res_model': 'project.project',
            'res_id': project_test.id
        })
        attachment_gif_test.write({
            'res_model': 'project.task',
            'res_id': task_test.id
        })

        txt_doc = self.env['documents.document'].search([('attachment_id', '=', attachment_txt_test.id)])
        gif_doc = self.env['documents.document'].search([('attachment_id', '=', attachment_gif_test.id)])

        self.assertEqual(txt_doc.folder_id, folder_test, 'the text test document have a folder')
        self.assertEqual(gif_doc.folder_id, folder_test, 'the gif test document have a folder')

