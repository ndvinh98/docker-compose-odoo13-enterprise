# -*- coding: utf-8 -*-


from odoo.tests import common


class TestImportExport(common.TransactionCase):

    # Simple import / export test
    def test_import_export_general(self):
        test_analytic_lines = [
            {
                "id": "__import__.admin1433780253119_aal1",
                "date": "2015-06-08",
                "project_id": "__import__.admin1433780253119_project1",
                "task_id": "__import__.admin1433780253119_task1",
                "desc": "description",
                "unit_amount": "2.00",
                "write_date": "2015-06-08 16:17:59",
                "to_sync": True,
                "sync_problem": False,
                "sheet_state": "open",
            },
        ]
        test_tasks = [
            {
                "name": "task",
                "id": "__import__.admin1433780253119_task1",
                "project_id": "__import__.admin1433780253119_project1",
                "to_sync": True,
                "sync_problem": False,
            }
        ]
        test_projects = [{
            "name": "project",
            "id": "__import__.admin1433780253119_project1",
            "to_sync": True,
            "sync_problem": False,
        }]

        user_admin = self.env.ref('base.user_admin')

        AAL = self.env['account.analytic.line'].with_user(user_admin)

        context = {'lang': "en_US", 'tz': "Europe/Brussels", 'uid': user_admin.id}

        AAL.with_context(context).import_ui_data(test_analytic_lines, test_tasks, test_projects)

        AAL.with_context(context).export_data_for_ui()

        for line in test_analytic_lines:
            line_ext_id = line["id"]
            aal = self.env["ir.model.data"].xmlid_to_object(line_ext_id)
            self.assertEqual(line["desc"], aal.name)
            self.assertEqual(line["date"], str(aal.date))
            self.assertEqual(float(line["unit_amount"]), aal.unit_amount)

    # Creates a timesheet_sheet and sets it in a confirmed state.
    # Then exports data and makes sure that the analytic lines of the sheet are exported with sheet_state closed
    def test_closed_sheet_sync(self):

        test_projects = [
            {
                "name": "project",
                "id": "__import__.admin1433780253119_project1",
                "to_sync": True,
                "sync_problem": False,
            }
        ]

        context = {'lang': "en_US", 'tz': "Europe/Brussels", 'uid': 1}
        AAL = self.env['account.analytic.line']
        AAL.with_context(context).import_ui_data([], [], test_projects)

        project = self.env["ir.model.data"].xmlid_to_object(test_projects[0]['id'])

        AAL = self.env['account.analytic.line']
        aal = AAL.with_context(context).create({
            'project_id': project.id,
            'user_id': 1,
            'name': 'activity description',
        })

        # This test can be removed when the format of `export_data_for_ui` will change. Indeed, sheet
        # state is not supported anymore (since removal of hr_timesheet_sheet module, in saas-17).
        # The `export_data_for_ui` return the sheet state 'open' as an harcoded value, to not change
        # returned format values, since it has to be compatible cross version for the sake of the
        # mobile timesheet app.
        exported_data = AAL.with_context(context).export_data_for_ui()
        for exported_aal in exported_data['aals']['datas']:
            if self.env["ir.model.data"].xmlid_to_res_id(exported_aal[0]) == aal.id:
                self.assertEqual(exported_aal[8], 'open')
