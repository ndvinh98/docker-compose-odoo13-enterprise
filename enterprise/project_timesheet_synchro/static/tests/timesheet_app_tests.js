odoo.define('project_timesheet_synchro.timesheet_app_tests', function (require) {
    "use strict";
    var TimeSheetUI = require('project_timeshee.ui');
    var concurrency = require('web.concurrency');
    var ServiceProviderMixin = require('web.ServiceProviderMixin');
    var testUtils = require('web.test_utils');

    QUnit.module('project_timesheet_synchro', {
        beforeEach: function () {
            this.data = {
                projects: {
                    fields: {
                        name: {string: "Project Name", type: "char" },
                        use_tasks: {string: "Use Tasks", type: "boolean" },
                        allow_timesheets: {string: "Allow Timesheets", type: "boolean" },
                    },
                    records: [{
                        id: "1",
                        name: "Project 1",
                        use_tasks: true,
                        allow_timesheets: true
                    }, {
                        id: "2",
                        name: "Project 2",
                        use_tasks: true,
                        allow_timesheets: true
                    }, ]
                },
                tasks: {
                    fields: {
                        name: {string: "Task Title", type: "char" },
                        sequence: {string: "sequence", type: "integer" },
                        kanban_state: {string: "State", type: "selection", selection: [["abc", "ABC"],["def", "DEF"],["ghi", "GHI"]] },
                        project_id: {string: "Project", type: 'many2one', relation: 'project.project' },
                    },
                    records: [{
                        id: "1",
                        name: "task1",
                        project_id: "1",
                        sequence: "1",
                        kanban_state: "abc"
                    }, {
                        id: "2",
                        name: "task2",
                        project_id: "2",
                        sequence: "2",
                        kanban_state: "abc"
                    }, ]
                },
                account_analytic_lines: {
                    fields: {
                        project_id: {string: "Project",type: "many2one" },
                        task_id: {string: "Task", type: "many2one" },
                        date: {string: "Date", type: "date" },
                        unit_amount: {string: "Time Spent", type: "float" },
                        name: {string: "Descriprion", type: "char" },
                    },
                    records: [{
                        id: "1",
                        project_id: "1",
                        task_id: "1",
                        date: "2017-08-21",
                        unit_amount: "03.50",
                        desc: "Test"
                    }, {
                        id: "2",
                        project_id: "1",
                        task_id: "2",
                        date: "2017-08-18",
                        unit_amount: "03.50",
                        desc: "Test"
                    }, {
                        id: "3",
                        project_id: "2",
                        task_id: "2",
                        date: "2017-08-15",
                        unit_amount: "03.50",
                        desc: "Test"
                    }, ]
                },
            };

            // Patch timesheetUI so that it is no longer a service provider.
            testUtils.mock.patch(TimeSheetUI, {
                /**
                 * @override
                 */
                init: function () {
                    var originalServiceProviderMixinInit = ServiceProviderMixin.init;
                    ServiceProviderMixin.init = function () {};
                    this._super.apply(this, arguments);
                    ServiceProviderMixin.init = originalServiceProviderMixinInit;
                },
            });
        },
        afterEach: function () {
            testUtils.mock.unpatch(TimeSheetUI);
        }
    }, function () {

        QUnit.module('TimeSheetUI');

        QUnit.test('timesheet_app_tests', async function (assert) {
            assert.expect(6);
            var projectTimesheet = new TimeSheetUI();
            projectTimesheet.data = {};
            await projectTimesheet.appendTo($('#qunit-fixture'));

            projectTimesheet.data.projects = this.data.projects.records; // projects
            projectTimesheet.data.tasks = this.data.tasks.records; // tasks
            projectTimesheet.data.account_analytic_lines = this.data.account_analytic_lines.records; // timesheets
            projectTimesheet.activities_screen.make_activities_list();
            await testUtils.nextTick();

            /*Start & Stop Timer*/
            projectTimesheet.activities_screen.start_timer();
            await concurrency.delay(0);
            projectTimesheet.activities_screen.stop_timer();
            await testUtils.nextTick();

            // select project
            projectTimesheet.$('.pt_activity_project').select2("open");
            $('.select2-results li div').first().trigger('mouseup');

            // select task
            projectTimesheet.$('.pt_activity_task').select2("open");
            $('.select2-results li div').first().trigger('mouseup');

            $('.pt_activity_duration').val("0.25"); // set time spent
            $('.pt_activity_duration').trigger('change');

            $('textarea.pt_description').val("Test"); // set description
            $('textarea.pt_description').trigger('change');

            projectTimesheet.edit_activity_screen.save_changes(); // save record
            await testUtils.nextTick();

            assert.strictEqual($('.pt_project').first().text(), "Project 1", "Should contain project named 'Project 1'");
            assert.strictEqual($('.pt_task').first().text().trim(), "task1", "Should contain task named 'task 1'");
            assert.strictEqual($('.pt_duration_time').first().text().trim(), "00:15", "time spent should be 00:15");
            await testUtils.dom.click($('.pt_quick_subtract_time'));
            assert.strictEqual($('.pt_duration_time').first().text().trim(), "00:00", "time spent should now be 00:00");
            await testUtils.dom.click($('.pt_quick_subtract_time'));
            assert.strictEqual($('.pt_deletion_from_list_modal').length, 1, "Should open a modal with delete button");
            await testUtils.dom.click($('.pt_delete_activity'));
            assert.strictEqual($('.pt_activities_list tr').length, 0, "Should display 0 timesheet");
            projectTimesheet.reset_app();
            projectTimesheet.destroy();
        });
    });
});
