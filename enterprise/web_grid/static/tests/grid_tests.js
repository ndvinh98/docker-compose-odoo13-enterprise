odoo.define('web_grid.grid_tests', function (require) {
"use strict";

var concurrency = require('web.concurrency');
var GridView = require('web_grid.GridView');
var testUtils = require('web.test_utils');

var createView = testUtils.createView;
var createActionManager = testUtils.createActionManager;

QUnit.module('Views', {
    beforeEach: function () {
        this.data = {
            'analytic.line': {
                fields: {
                    project_id: {string: "Project", type: "many2one", relation: "project"},
                    task_id: {string: "Task", type: "many2one", relation: "task"},
                    date: {string: "Date", type: "date"},
                    unit_amount: {string: "Unit Amount", type: "float"},
                    name: {string: "Description", type: "char"},
                },
                records: [
                    {id: 1, project_id: 31, date: "2017-01-24", unit_amount: 2.5, name: "ABC"},
                    {id: 2, project_id: 31, task_id: 1, date: "2017-01-25", unit_amount: 2, name: "ADE"},
                    {id: 3, project_id: 31, task_id: 1, date: "2017-01-25", unit_amount: 5.5, name: "AFG"},
                    {id: 4, project_id: 31, task_id: 1, date: "2017-01-30", unit_amount: 10, name: "ACD"},
                    {id: 5, project_id: 142, task_id: 12, date: "2017-01-31", unit_amount: 3.5, name: "ADE"},
                ]
            },
            project: {
                fields: {
                    name: {string: "Project Name", type: "char"}
                },
                records: [
                    {id: 31, display_name: "P1"},
                    {id: 142, display_name: "Webocalypse Now"},
                ]
            },
            task: {
                fields: {
                    name: {string: "Task Name", type: "char"},
                    project_id: {string: "Project", type: "many2one", relation: "project"},
                },
                records: [
                    {id: 1, display_name: "BS task", project_id: 31},
                    {id: 12, display_name: "Another BS task", project_id: 142},
                    {id: 54, display_name: "yet another task", project_id: 142},
                ]
            },
        };
        this.arch = '<grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">' +
                    '<field name="project_id" type="row"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                        '<range name="month" string="Month" span="month" step="day" invisible="context.get(\'hide_second_button\')"/>' +
                        '<range name="year" string="Year" span="year" step="month"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_time"/>' +
                    '<button string="Action" type="action" name="action_name"/>' +
                    '<empty>' +
                        '<p class="o_view_nocontent_smiling_face">' +
                            'Add projects and tasks' +
                        '</p>' +
                        '<p>you will be able to register your working hours on the given task</p>' +
                        '<p><a href="some-link"><img src="some-image" alt="alt text"/></a></p>' +
                    '</empty>' +
                '</grid>';
        this.archs = {
            'analytic.line,23,form': '<form string="Add a line"><group><group>' +
                                  '<field name="project_id"/>' +
                                  '<field name="task_id"/>' +
                                  '<field name="date"/>' +
                                  '<field name="unit_amount" string="Time spent"/>' +
                                '</group></group></form>',
        };
    }
}, function () {
    QUnit.module('GridView');

    QUnit.test('basic grid view', async function (assert) {
        assert.expect(17);

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: this.arch,
            currentDate: "2017-01-25",
            mockRPC: function (route) {
                if (route === 'some-image') {
                    return Promise.resolve();
                }
                return this._super.apply(this, arguments);
            },
        });

        await testUtils.nextTick();

        assert.ok(grid.$('table').length, "should have rendered a table");
        assert.containsN(grid, 'div.o_grid_cell_container', 14,
            "should have 14 cells");
        assert.strictEqual(grid.$('div.o_grid_input:contains(02:30)').length, 1,
            "should have correctly parsed a float_time");

        var cell = grid.$('div.o_grid_input:contains(02:30)').get(0);
        cell.focus();
        cell.click();
        cell.blur();
        await testUtils.nextTick();

        assert.strictEqual(grid.$('div.o_grid_input:contains(00:00)').length, 12,
            "should have correctly parsed another float_time");

        assert.ok(grid.$buttons.find('button.grid_arrow_previous').is(':visible'),
            "previous button should be visible");
        assert.hasClass(grid.$buttons.find('button.grid_arrow_range[data-name="week"]'),'active',
            "current range is shown as active");

        assert.strictEqual(grid.$('tfoot td:contains(02:30)').length, 1, "should display total in a column");
        assert.strictEqual(grid.$('tfoot td:contains(00:00)').length, 5, "should display totals, even if 0");

        await testUtils.dom.click(grid.$buttons.find('button.grid_arrow_next'));
        assert.ok(grid.$('div.o_grid_cell_container').length, "should not have any cells");
        assert.ok(grid.$('th div:contains(P1)').length,
            "should have rendered a cell with project name");
        assert.ok(grid.$('th div:contains(BS task)').length,
            "should have rendered a cell with task name");
        assert.notOk(grid.$('.o_grid_nocontent_container p:contains(Add projects and tasks)').length,
            "should not have rendered a no content helper");

        assert.notOk(grid.$('td.o_grid_current').length, "should not have any cell marked current");
        await testUtils.dom.click(grid.$buttons.find('button.grid_arrow_next'));
        // await testUtils.nextTick();

        assert.ok(grid.$('.o_grid_nocontent_container p:contains(Add projects and tasks)').length,
            "should have rendered a no content helper");
        assert.containsOnce(grid, '.o_grid_nocontent_container p a img',
            "should have rendered a no content helper with an image in a link");

        assert.notOk(grid.$('div.o_grid_cell_container').length, "should not have any cell");

        var emptyTd = 0;
        grid.$('tfoot td').each(function () {
            if ($(this).text() === '') {
                emptyTd++;
            }
        });
        assert.strictEqual(emptyTd, 8, "8 totals cells should be empty");
        grid.destroy();
    });

    QUnit.test('basic grouped grid view', async function (assert) {
        assert.expect(33);
        var nbReadGridDomain = 0;
        var nbReadGroup = 0;
        var nbReadGrid = 0;

        this.data['analytic.line'].records.push([
            {id: 6, project_id: 142, task_id: 12, date: "2017-01-31", unit_amount: 3.5},
        ]);

        this.arch = '<grid string="Timesheet By Project" adjustment="object" adjust_name="adjust_grid">' +
                '<field name="project_id" type="row" section="1"/>' +
                '<field name="task_id" type="row"/>' +
                '<field name="date" type="col">' +
                    '<range name="week" string="Week" span="week" step="day"/>' +
                    '<range name="month" string="Month" span="month" step="day"/>' +
                '</field>'+
                '<field name="unit_amount" type="measure" widget="float_time"/>' +
                '<empty>' +
                    '<p class="o_view_nocontent_smiling_face">' +
                        'Click to add projects and tasks' +
                    '</p>' +
                    '<p>you will be able to register your working hours on the given task</p>' +
                    '<p><a href="some-link"><img src="some-image" alt="alt text"/></a></p>' +
                '</empty>' +
            '</grid>';

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: this.arch,
            currentDate: "2017-01-25",
            mockRPC: function (route, args) {
                if (route === 'some-image') {
                    return Promise.resolve();
                } else if (args.method === 'read_grid_domain') {
                    nbReadGridDomain++;
                } else if (args.method === 'read_group') {
                    assert.strictEqual(args.kwargs.groupby.length, 1,
                        "should read group on the section (project_id)");
                    assert.strictEqual(args.kwargs.groupby[0], 'project_id',
                        "should read group on the section (project_id)");
                    nbReadGroup++;
                } else if (args.method === 'read_grid') {
                    nbReadGrid++;
                }
                return this._super.apply(this, arguments);
            },
        });
        await testUtils.nextTick();
        assert.ok(grid.$('table').length, "should have rendered a table");
        assert.strictEqual(nbReadGridDomain, 1, "should have read the grid domain");
        assert.strictEqual(nbReadGridDomain, 1, "should have read group");
        assert.strictEqual(nbReadGrid, 2, "should have read one grid by group");
        assert.containsN(grid, '.o_grid_section', 2, "should have one section by project");

        // first section
        assert.strictEqual(grid.$('.o_grid_section:eq(0) th:contains(P1)').length, 1,
            "first section should be for project P1");
        assert.strictEqual(grid.$('.o_grid_section:eq(0) div.o_grid_cell_container').length, 14,
            "first section should have 14 cells");
        assert.strictEqual(grid.$('.o_grid_section:eq(0) th:contains(Unknown)').length, 1,
            "first section should have a row without task");
        assert.strictEqual(grid.$('.o_grid_section:eq(0) th:contains(BS task)').length, 1,
            "first section should have a row for BS task");

        assert.strictEqual(grid.$('.o_grid_section:eq(0) tr:eq(2) div.o_grid_input:contains(02:30)').length, 1,
            "should have correctly parsed a float_time for cell without task");
        assert.strictEqual(grid.$('.o_grid_section:eq(0) div.o_grid_input:contains(00:00)').length, 12,
            "should have correctly parsed another float_time");

        // second section
        assert.strictEqual(grid.$('.o_grid_section:eq(1) th:contains(Webocalypse Now)').length, 1,
            "second section should be for project Webocalypse Now");
        assert.strictEqual(grid.$('.o_grid_section:eq(1) th:contains(Another BS task)').length, 0,
            "first section should be empty");
        assert.strictEqual(grid.$('.o_grid_section:eq(1) div.o_grid_cell_container').length, 0,
            "second section should be empty");

        assert.ok(grid.$buttons.find('button.grid_arrow_previous').is(':visible'),
            "previous button should be visible");
        assert.hasClass(grid.$buttons.find('button.grid_arrow_range[data-name="week"]'),'active',
            "current range is shown as active");

        assert.strictEqual(grid.$('tfoot td:contains(02:30)').length, 1, "should display total in a column");
        assert.strictEqual(grid.$('tfoot td:contains(00:00)').length, 5, "should display totals, even if 0");

        await testUtils.dom.click(grid.$buttons.find('button.grid_arrow_next'));

        assert.strictEqual(nbReadGridDomain, 2, "should have read the grid domain again");
        assert.strictEqual(nbReadGridDomain, 2, "should have read group again");
        assert.strictEqual(nbReadGrid, 4, "should have read one grid by group again");

        assert.ok(grid.$('div.o_grid_cell_container').length, "should not have any cells");
        assert.ok(grid.$('th:contains(P1)').length,
            "should have rendered a cell with project name");
        assert.ok(grid.$('th div:contains(BS task)').length,
            "should have rendered a cell with task name");
        assert.strictEqual(grid.$('.o_grid_section:eq(1) th:contains(Another BS task)').length, 1,
            "first section should have a row for Another BS task");
        assert.strictEqual(grid.$('.o_grid_section:eq(1) div.o_grid_cell_container').length, 7,
            "second section should have 7 cells");
        await testUtils.dom.click(grid.$buttons.find('button.grid_arrow_next'));

        assert.containsNone(grid, '.o_grid_nocontent_container',
            "should not have rendered a no content helper in grouped");
        grid.destroy();
    });

    QUnit.test('grouped grid view with no data', async function (assert) {
        assert.expect(4);

        this.data['analytic.line'].records = [];

        this.arch = '<grid string="Timesheet By Project" adjustment="object" adjust_name="adjust_grid">' +
                '<field name="project_id" type="row" section="1"/>' +
                '<field name="task_id" type="row"/>' +
                '<field name="date" type="col">' +
                    '<range name="week" string="Week" span="week" step="day"/>' +
                    '<range name="month" string="Month" span="month" step="day"/>' +
                '</field>' +
                '<field name="unit_amount" type="measure" widget="float_time"/>' +
            '</grid>';

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: this.arch,
            currentDate: "2017-01-25",
        });

        assert.isVisible(grid.$('.o_control_panel .grid_arrow_previous'));
        assert.isVisible(grid.$('.o_control_panel .grid_arrow_next'));
        assert.containsOnce(grid, '.o_view_grid .o_grid_section');
        assert.containsN(grid, '.o_view_grid thead th', 9); // title + 7 days + total

        grid.destroy();
    });

    QUnit.test('load and reload a grid view with favorite search', async function (assert) {
        assert.expect(4);

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: '<grid string="Timesheet By Project">' +
                    '<field name="project_id" type="row" section="1"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_time"/>' +
                '</grid>',
            groupBy: ["task_id", "project_id"], // user-set default search view
            currentDate: "2017-01-25",
        });

        assert.strictEqual(grid.$('tr:eq(2) th').text(), 'BS taskP1',
            "GroupBy should have been taken into account when loading the view."
        );
        assert.strictEqual(grid.$('tr:eq(3) th').text(), 'UnknownP1',
            "GroupBy should have been taken into account when loading the view."
        );

        await testUtils.dom.click(grid.$buttons.find('.grid_arrow_next'));

        assert.strictEqual(grid.$('tr:eq(2) th').text(), 'Another BS taskWebocalypse Now',
            "GroupBy should have been kept when clicking the pager."
        );
        assert.strictEqual(grid.$('tr:eq(3) th').text(), 'BS taskP1',
            "GroupBy should have been kept when clicking the pager."
        );

        grid.destroy();
    });

    QUnit.test('groupBy a string is supported', async function (assert) {
        // groupBy could be a single "field" instead of an Array of strings
        assert.expect(4);

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: '<grid string="Timesheet By Project">' +
                    '<field name="project_id" type="row" section="1"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_time"/>' +
                '</grid>',
            groupBy: "task_id",
            currentDate: "2017-01-25",
        });

        assert.strictEqual(grid.$('tr:eq(2) th').text(), 'BS task',
            "GroupBy should have been taken into account when loading the view."
        );
        assert.strictEqual(grid.$('tr:eq(3) th').text(), 'Unknown',
            "GroupBy should have been taken into account when loading the view."
        );

        await testUtils.dom.click(grid.$buttons.find('.grid_arrow_next'));

        assert.strictEqual(grid.$('tr:eq(2) th').text(), 'Another BS task',
            "GroupBy should have been kept when clicking the pager."
        );
        assert.strictEqual(grid.$('tr:eq(3) th').text(), 'BS task',
            "GroupBy should have been kept when clicking the pager."
        );

        grid.destroy();
    });

    QUnit.test('groupBy a date with groupby function', async function (assert) {
        assert.expect(1);

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: '<grid string="Timesheet By Project">' +
                    '<field name="project_id" type="row" section="1"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_time"/>' +
                '</grid>',
            groupBy: "date:month",
            currentDate: "2017-01-25",
        });

        assert.strictEqual(grid.$('tbody tr:first th').text(), 'January 2017',
            "groupBy should have been taken into account when loading the view"
        );

        grid.destroy();
    });

    QUnit.test('Removing groupBy defaults to initial groupings', async function (assert) {
        assert.expect(6);

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: '<grid string="Timesheet By Project">' +
                    '<field name="project_id" type="row" section="1"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_time"/>' +
                '</grid>',
            groupBy: ["task_id", "project_id"],
            currentDate: "2017-01-25",
        });

        assert.strictEqual(grid.$('tr:eq(2) th').text(), 'BS taskP1',
            "GroupBy should have been taken into account when loading the view."
        );
        assert.strictEqual(grid.$('tr:eq(3) th').text(), 'UnknownP1',
            "GroupBy should have been taken into account when loading the view."
        );

        await grid.update({groupBy: []});

        assert.strictEqual(grid.$('tr:eq(2) th').text(), 'P1',
            "Should be grouped by default (Project > Task)."
        );
        assert.strictEqual(grid.$('tr:eq(3) th').text(), 'BS task',
            "Should be grouped by default (Project > Task)."
        );
        assert.strictEqual(grid.$('tr:eq(4) th').text(), 'Unknown',
            "Should be grouped by default (Project > Task)."
        );
        assert.strictEqual(grid.$('tr:eq(5) th').text(), 'Webocalypse Now',
            "Should be grouped by default (Project > Task)."
        );

        grid.destroy();
    });

    QUnit.test('DOM keys are unique', async function (assert) {
        /*Snabbdom, the virtual dom libraries, use keys to distinguish similar
        elements (typically grid rows).
        If these keys are not unique, and there are rows that are repeated,
        the library might crash upon comparing the elements to refresh.
        */

        assert.expect(8);

        var line_records = [
                {id: 12, project_id: 142, date: "2017-01-17", unit_amount: 0},
                {id: 1, project_id: 31, date: "2017-01-24", unit_amount: 2.5},
                {id: 3, project_id: 143, date: "2017-01-25", unit_amount: 5.5},
                {id: 2, project_id: 33, date: "2017-01-25", unit_amount: 2},
                {id: 4, project_id: 143, date: "2017-01-18", unit_amount: 0},
                {id: 5, project_id: 142, date: "2017-01-18", unit_amount: 0},
                {id: 10, project_id: 31, date: "2017-01-18", unit_amount: 0},
                {id: 22, project_id: 33, date: "2017-01-19", unit_amount: 0},
                {id: 21, project_id: 99, date: "2017-01-19", unit_amount: 0},
        ];
        var project_records = [
                {id: 31, display_name: "Rem"},
                {id: 33, display_name: "Rer"},
                {id: 142, display_name: "Sas"},
                {id: 143, display_name: "Sassy"},
                {id: 99, display_name: "Sar"},
        ];
        this.data.project.records = project_records;
        this.data['analytic.line'].records = line_records;

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: this.arch,
            currentDate: "2017-01-25",
        });
        await testUtils.nextTick();
        assert.strictEqual(grid.$('tbody th:first').text(), "RerUnknown", "Should be equal.");
        assert.strictEqual(grid.$('tbody th:eq(1)').text(), "SassyUnknown", "Should be equal.");
        assert.strictEqual(grid.$('tbody th:eq(2)').text(), "RemUnknown", "Should be equal.");

        await testUtils.dom.click(grid.$buttons.find('button.grid_arrow_previous'));
        assert.strictEqual(grid.$('tbody th:first').text(), "SarUnknown", "Should be equal.");
        assert.strictEqual(grid.$('tbody th:eq(1)').text(), "RerUnknown", "Should be equal.");
        assert.strictEqual(grid.$('tbody th:eq(2)').text(), "RemUnknown", "Should be equal.");
        assert.strictEqual(grid.$('tbody th:eq(3)').text(), "SassyUnknown", "Should be equal.");
        assert.strictEqual(grid.$('tbody th:eq(4)').text(), "SasUnknown", "Should be equal.");

        grid.destroy();
    });

    QUnit.test('group by non-relational field', async function (assert) {
        assert.expect(1);

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: this.arch,
            currentDate: "2017-01-25",
        });

        await grid.update({groupBy: ["date"]});
        assert.strictEqual(grid.$('tbody th:first').text(),
                           "January 2017",
                           "Should be equal.");
        grid.destroy();
    });

    QUnit.test('create analytic lines', async function (assert) {
        assert.expect(7);
        this.data['analytic.line'].fields.date.default = "2017-02-25";

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: '<grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">' +
                    '<field name="project_id" type="row"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                        '<range name="month" string="Month" span="month" step="day"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_time"/>' +
                '</grid>',
            currentDate: "2017-02-25",
            viewOptions: {
                action: {
                    views: [{viewID: 23, type: 'form'}],
                },
            },
            archs: this.archs,
            mockRPC: function (route, args) {
                if (args.method === 'create') {
                    assert.strictEqual(args.args[0].date, "2017-02-25",
                        "default date should be current day");
                }
                return this._super(route, args);
            },
        });

        assert.containsNone(grid, '.o_grid_nocontent_container',
            "should not have rendered a no content helper");

        assert.containsNone(grid, 'div.o_grid_cell_container', "should not have any cells");
        assert.notOk($('.modal').length, "should not have any modal open");
        await testUtils.dom.click(grid.$buttons.find('.o_grid_button_add'));

        assert.ok($('.modal').length, "should have opened a modal");

        // input a project and a task
        await testUtils.fields.many2one.clickOpenDropdown('project_id');
        await testUtils.fields.many2one.clickHighlightedItem('project_id');
        await testUtils.fields.many2one.clickOpenDropdown('task_id');
        await testUtils.fields.many2one.clickHighlightedItem('task_id');

        // input unit_amount
        await testUtils.fields.editInput($('.modal input').eq(3), "4");

        // save
        await testUtils.dom.click($('.modal .modal-footer button.btn-primary'));

        assert.containsN(grid, 'div.o_grid_cell_container', 7,
            "should have 7 cell containers (1 for each day)");

        assert.strictEqual(grid.$('td.o_grid_total:contains(4:00)').length, 1,
            "should have a total of 4:00");

        grid.destroy();
    });

    QUnit.test('create analytic lines on grouped grid view', async function (assert) {
        assert.expect(4);
        this.data['analytic.line'].fields.date.default = "2017-02-25";

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: '<grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">' +
                    '<field name="project_id" type="row"  section="1"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                        '<range name="month" string="Month" span="month" step="day"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_time"/>' +
                '</grid>',
            currentDate: "2017-02-25",
            viewOptions: {
                action: {
                    views: [{viewID: 23, type: 'form'}],
                },
            },
            domain: [['date', '>', '2014-09-09']],
            archs: this.archs,
            mockRPC: function (route, args) {
                if (args.method === 'read_group') {
                    assert.deepEqual(args.kwargs.domain[3], ['date', '>', '2014-09-09'],
                        "the action domain should always be given");
                }
                if (args.method === 'create') {
                    assert.strictEqual(args.args[0].date, "2017-02-25",
                        "default date should be current day");
                }
                return this._super(route, args);
            },
        });

        await testUtils.dom.click(grid.$buttons.find('.o_grid_button_add'));
        assert.ok($('.modal').length, "should have opened a modal");
        // input a project and a task
        await testUtils.fields.many2one.clickOpenDropdown('project_id');
        await testUtils.fields.many2one.clickHighlightedItem('project_id');
        await testUtils.fields.many2one.clickOpenDropdown('task_id');
        await testUtils.fields.many2one.clickHighlightedItem('task_id');
        // input unit_amount
        await testUtils.fields.editInput($('.modal input').eq(3), "4");
        // save
        await testUtils.dom.click($('.modal .modal-footer button.btn-primary'));

        grid.destroy();
    });

    QUnit.test('switching active range', async function (assert) {
        assert.expect(6);
        var done = assert.async();
        this.data['analytic.line'].fields.date.default = "2017-02-25";

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: '<grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">' +
                    '<field name="project_id" type="row"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                        '<range name="month" string="Month" span="month" step="day"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_time"/>' +
                '</grid>',
            currentDate: "2017-02-25",
        });

        return concurrency.delay(0).then(function () {
            assert.strictEqual(grid.$('thead th:not(.o_grid_title_header)').length, 8,
                "should have 8 columns (1 for each day + 1 for total)");
            assert.hasClass(grid.$buttons.find('button.grid_arrow_range[data-name="week"]'),'active',
                "current range is shown as active");
            assert.doesNotHaveClass(grid.$buttons.find('button.grid_arrow_range[data-name="month"]'), 'active',
                "month range is not active");

            testUtils.dom.click(grid.$buttons.find('button[data-name=month]'));

            return concurrency.delay(0);
        }).then(function () {

            assert.strictEqual(grid.$('thead th:not(.o_grid_title_header)').length, 29,
                "should have 29 columns (1 for each day + 1 for total)");
            assert.hasClass(grid.$buttons.find('button.grid_arrow_range[data-name="month"]'),'active',
                "month range is shown as active");
            assert.doesNotHaveClass(grid.$buttons.find('button.grid_arrow_range[data-name="week"]'), 'active',
                "week range is not active");

            grid.destroy();
            done();
        });
    });

    QUnit.test('clicking on the info icon on a cell triggers a do_action', async function (assert) {
        assert.expect(5);

        var domain;

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: this.arch,
            currentDate: "2017-01-25",
            mockRPC: function () {
                return this._super.apply(this, arguments).then(function (result) {
                    domain = result.grid[0][2].domain;
                    return result;
                });
            }
        });

        assert.containsN(grid, 'i.o_grid_cell_information', 14,
            "should have 14 icons to open cell info");

        testUtils.mock.intercept(grid, 'do_action', function (event) {
            var action = event.data.action;

            assert.deepEqual(action.domain, domain, "should trigger a do_action with correct values");
            assert.strictEqual(action.name, "P1: BS task",
                "should have correct action name");
            assert.strictEqual(action.context.default_project_id, 31, "should pass project_id in context when click on info icon on cell");
            assert.strictEqual(action.context.default_task_id, 1 , "should pass task_id in context when click on info icon on cell");
        });
        await testUtils.dom.click(grid.$('i.o_grid_cell_information').eq(2));

        grid.destroy();
    });

    QUnit.test('editing a value', async function (assert) {
        assert.expect(13);

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: this.arch,
            currentDate: "2017-01-25",
            viewOptions: {
                context: {some_value: 2},
            },
            mockRPC: function (route, args) {
                if (args.method === 'search') {
                    return Promise.resolve([1, 2, 3, 4, 5]);
                }
                if (args.method === 'adjust_grid') {
                    assert.strictEqual(args.model, 'analytic.line',
                        'should call with correct model in env');
                    assert.deepEqual(args.kwargs.context, {some_value: 2},
                        'should call with correct context');
                    assert.strictEqual(args.args[0].length, 0,
                        'should call method with no specific res ids');

                }
                return this._super.apply(this, arguments);
            },
            intercepts: {
                execute_action: function (event) {
                    assert.strictEqual(event.data.env.model, 'analytic.line',
                        'should call with correct model in env');
                    assert.deepEqual(event.data.env.context, {some_value: 2},
                        'should call with correct context in env');
                    assert.deepEqual(event.data.env.resIDs, [1, 2, 3, 4, 5],
                        'should call with correct resIDs in env');
                },
            },
        });

        var $input = grid.$('.o_grid_cell_container:eq(0) div.o_grid_input');

        assert.doesNotHaveClass($input, 'o_has_error',
            "input should not show any error at start");
        await testUtils.dom.click($input);
        $input.focus();
        var selection = window.getSelection();
        assert.strictEqual($(selection.focusNode).closest(".o_grid_input")[0], $input[0],
            "the text in the cell is focused");
        assert.strictEqual(selection.anchorOffset, 0,
            "selection starts at index 0");
        /**
         * The next assertion is browser dependent. Indeed Firefox and
         * Chrome implement two working `window.getSelection` but with
         * different return results.
         *
         * On Chrome, selecting the whole content of a node with an unique
         * text node thanks to the `Range.selectNodeContents` function
         * creates a Range element whose reference is the text node and the
         * selection end value is the text node length.
         * On Firefox, doing the same operation creates a Range element
         * whose reference is the parent node and the selection end value
         * is 1 (saying that one whole text node is selected).
         *
         * Note that the test could just check that the selection end is
         * greater than 1 (checking that something is selected), but this
         * problem was worth mentioning and the test is maybe more correct
         * and explicit this way.
         *
         * TODO(?) use mock getSelection (there are some support code somewhere)
         */
        assert.strictEqual(selection.focusOffset, selection.focusNode === $input[0] ? 1 : 5,
            "selection ends at the text end (so the 00:00 text is selected)");

        $input.text('abc');
        $input.focusout();
        await testUtils.nextTick();
        assert.hasClass($input,'o_has_error',
            "input should be formatted to show that there was an error");

        $input.text('8.5');
        $input.focusout();
        await testUtils.nextTick();

        assert.doesNotHaveClass($input, 'o_has_error',
            "input should not be formatted like there is an error");

        assert.strictEqual($input.text(), "08:30",
            "text should have been properly parsed/formatted");

        await testUtils.dom.click(grid.$buttons.find('button:contains("Action")'));

        grid.destroy();
    });

    QUnit.test('basic grid view, hide range button', async function (assert) {
        assert.expect(3);
        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: this.arch,
            currentDate: "2017-01-25",
            action: {
                views: [{viewID: 23, type: 'form'}],
            },
            context: {'hide_second_button': true}
        });

        assert.containsN(grid.$buttons, 'button.grid_arrow_range', 2, "should have only one range button displayed");
        assert.containsOnce(grid.$buttons, "button[data-name='week']", "should have week button displayed");
        assert.containsOnce(grid.$buttons, "button[data-name='year']", "should have year button displayed");

        grid.destroy();
    });

    QUnit.test('grid view with type="readonly" field', async function (assert) {
        assert.expect(4);
        var done = assert.async();
        this.data['analytic.line'].fields.validated = {string: "Validation", type: "boolean"};
        this.data['analytic.line'].records.push({id: 8, project_id: 142, task_id: 54, date: "2017-01-25", unit_amount: 4, employee_id: 101, validated: true});
        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: '<grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">' +
                    '<field name="validated" type="readonly"/>' +
                    '<field name="project_id" type="row"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                        '<range name="month" string="Month" span="month" step="day"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_time"/>' +
                '</grid>',
            currentDate: "2017-01-25",
        });
        return concurrency.delay(0).then(function () {
            assert.strictEqual(grid.$('.o_grid_cell_container:not(.o_grid_cell_empty)').length, 3,
                "should have 3 columns which has timesheet value");
            assert.strictEqual(grid.$('.o_grid_cell_container:not(.o_grid_cell_readonly, .o_grid_cell_empty)').length, 2,
                "should have 2 cells which are not readonly");
            assert.strictEqual(grid.$('.o_grid_cell_readonly').length, 1,
                "should have 1 cell which is readonly");
            assert.doesNotHaveClass(grid.$('.o_grid_cell_readonly div'), 'o_grid_input',
                "should not have o_grid_input class on readonly cell");
            grid.destroy();
            done();
        });
    });

    QUnit.test('grid_anchor is properly transferred in context', async function (assert) {
        assert.expect(1);

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: '<grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">' +
                    '<field name="project_id" type="row"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                        '<range name="month" string="Month" span="month" step="day" invisible="context.get(\'hide_second_button\')"/>' +
                        '<range name="year" string="Year" span="year" step="month"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_time"/>' +
                '</grid>',
            currentDate: "2017-01-31",
            mockRPC: function (route, args) {
                if (args.method === 'adjust_grid') {
                    assert.strictEqual(args.kwargs.context.grid_anchor, '2017-01-24',
                        "proper grid_anchor is sent to server");
                }
                return this._super.apply(this, arguments);
            },
        });

        // go back to previous week, to be able to check if grid_anchor is
        // properly updated and sent to the server
        await testUtils.dom.click(grid.$buttons.find('.grid_arrow_previous'));
        grid.$('.o_grid_input').first().text('2').focusout();
        await testUtils.nextTick();

        grid.destroy();
    });

    QUnit.test('grid_anchor stays when navigating', async function (assert) {
        assert.expect(3);

        // create an action manager to test the interactions with the search view
        var actionManager = await createActionManager({
            data: this.data,
            archs: {
                'analytic.line,false,grid': '<grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">' +
                    '<field name="project_id" type="row"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                        '<range name="month" string="Month" span="month" step="day"/>' +
                        '<range name="year" string="Year" span="year" step="month"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_time"/>' +
                '</grid>',
                'analytic.line,false,search': '<search>' +
                        '<filter name="filter_test" help="Project 31" domain="[(\'project_id\', \'=\', 31)]"/>' +
                '</search>',
            },
        });

        await actionManager.doAction({
            res_model: 'analytic.line',
            type: 'ir.actions.act_window',
            views: [[false, 'grid']],
            context: {
                'search_default_filter_test': 1,
                'grid_anchor': '2017-01-31',
            },
        });

        // check first column header
        assert.strictEqual(actionManager.$('.o_view_grid th:eq(2)').text(), "Tue,Jan 31", "The first day of the span should be the 31st of January");

        // move to previous week, and check first column header
        await testUtils.dom.click(actionManager.$('.o_control_panel .grid_arrow_previous'));
        assert.strictEqual(actionManager.$('.o_view_grid th:eq(2)').text(), "Tue,Jan 24", "The first day of the span should be the 24st of January, as we check the previous week");

        // remove the filter in the searchview
        await testUtils.dom.click($('.o_control_panel .o_searchview .o_facet_remove'));

        // recheck first column header
        assert.strictEqual(actionManager.$('.o_view_grid th:eq(2)').text(), "Tue,Jan 24", "The first day of the span should STILL be the 24st of January, even we resetting search");

        actionManager.destroy();
    });

    QUnit.test('grid view grouped by char field, and switch range', async function (assert) {
        assert.expect(3);

        this.data['analytic.line'].records = this.data['analytic.line'].records.concat([
            {id: 6, project_id: 31, task_id: 12, date: "2017-01-30", unit_amount: 2, name: "ADE"},
            {id: 7, project_id: 31, task_id: 54, date: "2017-01-25", unit_amount: 5.5, name: "AFG"},
        ]);
        const grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: `
                <grid adjustment="object" adjust_name="adjust_grid">
                    <field name="project_id" type="row" section="1"/>
                    <field name="task_id" type="row"/>
                    <field name="date" type="col">
                        <range name="week" string="Week" span="week" step="day"/>
                        <range name="month" string="Month" span="month" step="day"/>
                    </field>
                    <field name="unit_amount" type="measure" widget="float_time"/>
                </grid>`,
            currentDate: "2017-01-25",
            groupBy: ['project_id', 'task_id', 'name'],
            domain: [['project_id', '=', 31]],
        });

        assert.containsN(grid, '.o_grid_section > tr', 5);
        await testUtils.dom.click(grid.$('.o_control_panel .grid_arrow_next'));
        assert.containsN(grid, '.o_grid_section > tr', 3);
        await testUtils.dom.click(grid.$('.o_control_panel .grid_arrow_previous'));
        assert.containsN(grid, '.o_grid_section > tr', 5);

        grid.destroy();
    });

    QUnit.module('GridViewWidgets');

    QUnit.test('float_toggle widget', async function (assert) {
        assert.expect(13);

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: '<grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">' +
                    '<field name="project_id" type="row" section="1"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                        '<range name="month" string="Month" span="month" step="day"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_toggle" options="{\'factor\': 0.125, \'range\': [0.0, 0.5, 1.0]}"/>' +
                '</grid>',
            currentDate: "2017-01-31",
            mockRPC: function (route, args) {
                if (args.method === 'adjust_grid') {
                    if (args.args[3] == '2017-02-01/2017-02-02') { // use case "clicking on empty cell button"
                        assert.strictEqual(args.args[5], 8, "saving 1.00 on float_toggle button will register 8 in database (1 / 0.125)");
                    }
                    if (args.args[3] == '2017-01-30/2017-01-31') { // use case "clicking on non empty cell button"
                        assert.strictEqual(args.args[5], -10, "saving 0.00 on float_toggle button will send a negative delta of 1.25 / 0.125");
                    }
                }
                return this._super.apply(this, arguments);
            },
        });

        // first section
        assert.strictEqual(grid.$('.o_grid_section:eq(0) button.o_grid_float_toggle').length, 7,
            "first section should be for project P1");
        assert.strictEqual(grid.$('.o_grid_section:eq(0) button.o_grid_float_toggle:contains(1.25)').length, 1,
            "one button contains the value 1.25 (timesheet line #4)");
        assert.strictEqual(grid.$('.o_grid_section:eq(0) button.o_grid_float_toggle:contains(0.00)').length, 6,
            "Other button are filled with 0.00");
        assert.strictEqual(grid.$('.o_grid_section:eq(0) .o_grid_cell_container[data-path="0.grid.0.0"] button').text(), '1.25',
            "the second cell of the second section is the timesheet #4");

        // second section
        assert.strictEqual(grid.$('.o_grid_section:eq(1) button.o_grid_float_toggle').length, 7,
            "first section should be for project Webocalypse Now");
        assert.strictEqual(grid.$('.o_grid_section:eq(1) button.o_grid_float_toggle:contains(0.44)').length, 1,
            "one button contains the value 1.25 (timesheet line #5)");
        assert.strictEqual(grid.$('.o_grid_section:eq(1) button.o_grid_float_toggle:contains(0.00)').length, 6,
            "Other button are filled with 0.00");
        assert.strictEqual(grid.$('.o_grid_section:eq(1) .o_grid_cell_container[data-path="1.grid.0.1"] button').text(), '0.44',
            "the second cell of the second section is the timesheet #5");

        // clicking on empty cell button
        var $button = grid.$('.o_grid_section:eq(1) .o_grid_cell_container[data-path="1.grid.0.2"] button');
        $button.focus();
        await testUtils.nextTick();

        await testUtils.dom.click($button);
        assert.strictEqual(grid.$('.o_grid_section:eq(1) .o_grid_cell_container[data-path="1.grid.0.2"] button').text(), '0.50',
            "0.5 is the next value since 0.0 was the closest value in the range");

        await testUtils.dom.click($button);
        assert.strictEqual(grid.$('.o_grid_section:eq(1) .o_grid_cell_container[data-path="1.grid.0.2"] button').text(), '1.00',
            "0.5 becomes 1.0 as it is the next value in the range");

        $button.blur(); // will trigger the adjustment RPC call
        await testUtils.nextTick();

        // clicking on non empty cell button (1.25)
        var $button = grid.$('.o_grid_section:eq(0) .o_grid_cell_container[data-path="0.grid.0.0"] button');
        $button.focus();
        await testUtils.nextTick();

        await testUtils.dom.click($button);
        assert.strictEqual(grid.$('.o_grid_section:eq(0) .o_grid_cell_container[data-path="0.grid.0.0"] button').text(), '0.00',
            "1.25 is starting value, the closest in the range is 1.00, so the next will be 0.00");

        $button.blur(); // will trigger the adjustment RPC call
        await testUtils.nextTick();
        grid.destroy();
    });

    QUnit.test('button context not polluted by previous click', async function (assert) {
        assert.expect(4);

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: this.arch,
            currentDate: "2017-01-31",
            mockRPC: function (route, args) {
                if (route === 'some-image') {
                    return Promise.resolve();
                }
                if (args.method === 'search') {
                    return Promise.resolve([1, 2, 3, 4, 5]);
                }
                return this._super.apply(this, arguments);
            },
            intercepts: {
                execute_action: function (event) {
                    if (event.data.action_data.name === 'action_name') {
                        assert.step(event.data.action_data.context.grid_anchor);
                    }
                },
            },
        });
        await testUtils.nextTick();
        testUtils.dom.click(grid.$buttons.find('.grid_arrow_previous'));

        // check that first button click does not affect that button
        // context for subsequent clicks on it
        await testUtils.dom.click(grid.$buttons.find('button:contains("Action")'));
        assert.verifySteps(['2017-01-24'],
            'first button click get current grid anchor date');
        testUtils.dom.click(grid.$buttons.find('.grid_arrow_previous'));
        await testUtils.dom.click(grid.$buttons.find('button:contains("Action")'));
        assert.verifySteps(['2017-01-17'],
            'second button click get current grid anchor date');

        grid.destroy();
    });

    QUnit.test('grid view in day range ', async function (assert) {
        assert.expect(14);
        var nbReadGrid = 0;
        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: `
                <grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">
                    <field name="project_id" type="row"/>
                    <field name="task_id" type="row"/>
                    <field name="date" type="col">
                        <range name="day" string="Day" span="day" step="day"/>
                    </field>
                    <field name="unit_amount" type="measure" widget="float_time"/>
                </grid>
            `,
            currentDate: "2017-01-30",
            mockRPC: function (route, args) {
                if (args.method === 'read_grid') {
                    nbReadGrid++;
                }
                return this._super.apply(this, arguments);
            },
        });
        assert.ok(grid.$('table').length, "Table rendered properly.");
        assert.strictEqual(nbReadGrid, 1, "should have read one grid by group")
        assert.containsOnce(grid, 'thead th:not(.o_grid_title_header)', "Single Day column should be shown");
        var grid_anchor = grid.$('thead tr').text().split(',\n').join().replace(/\s/g, '');
        assert.equal(grid_anchor, "Mon,Jan30", "grid should start with grid_anchor date as the default date.");

        await testUtils.dom.click(grid.$buttons.find('button.grid_arrow_next'));

        grid_anchor = grid.$('thead tr').text().split(',\n').join().replace(/\s/g, '');
        assert.equal(grid_anchor, 'Tue,Jan31', "Date should be of next day.");
        assert.strictEqual(nbReadGrid, 2, "should have read one grid by group")
        assert.containsOnce(grid, 'thead th:not(.o_grid_title_header)', "Single Day column should be shown");

        await testUtils.dom.click(grid.$buttons.find('button.grid_arrow_previous'));

        grid_anchor = grid.$('thead tr').text().split(',\n').join().replace(/\s/g, '');
        assert.equal(grid_anchor, "Mon,Jan30", "Date should be today's date.");
        assert.strictEqual(nbReadGrid, 3, "should have read one grid by group")
        assert.containsOnce(grid, 'thead th:not(.o_grid_title_header)', "Single Day column should be shown");

        await testUtils.dom.click(grid.$buttons.find('button.grid_arrow_previous'));

        grid_anchor = grid.$('thead tr').text().split(',\n').join().replace(/\s/g, '');
        assert.equal(grid_anchor, 'Sun,Jan29', "Date should be of 29th Jan.");
        assert.strictEqual(nbReadGrid, 4, "should have read four read grid");

        await testUtils.dom.click(grid.$buttons.find('button.grid_arrow_next'));

        grid_anchor = grid.$('thead tr').text().split(',\n').join().replace(/\s/g, '');
        assert.equal(grid_anchor, 'Mon,Jan30', "Date should be of 30th Jan.");
        assert.strictEqual(nbReadGrid, 5, "should have five read grid");
        grid.destroy();
    });

    QUnit.test('basic grouped grid view in day range', async function (assert) {
        assert.expect(19);
        var nbReadGroup = 0;

        this.arch = `
            <grid string="Timesheet By Project" adjustment="object" adjust_name="adjust_grid">
                <field name="project_id" type="row" section="1"/>
                <field name="task_id" type="row"/>
                <field name="date" type="col">
                    <range name="day" string="Day" span="day" step="day"/>
                </field>
                <field name="unit_amount" type="measure" widget="float_time"/>
            </grid>
        `;

        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: this.arch,
            currentDate: "2017-01-25",
            mockRPC: function (route, args) {
                if (args.method === 'read_group') {
                    assert.strictEqual(args.kwargs.groupby.length, 1,
                        "should read group on the section (project_id)");
                    assert.strictEqual(args.kwargs.groupby[0], 'project_id',
                        "should read group on the section (project_id)");
                    nbReadGroup++;
                }
                return this._super.apply(this, arguments);
            },
        });

        assert.ok(grid.$('table').length, "should have rendered a table");
        assert.strictEqual(nbReadGroup, 1, "should have one read_grid by group")
        assert.containsOnce(grid, 'thead th:not(.o_grid_title_header)', "Single Day column should be shown");
        assert.containsN(grid, '.o_grid_section', 2, "should have one section by project");

        // first section
        assert.containsOnce(grid, '.o_grid_section:eq(0) th:contains(P1)',
            "first section should be for project P1");
        assert.containsN(grid, '.o_grid_section:eq(0) div.o_grid_cell_container', 1,
            "first section should have 1 cells");
        assert.containsNone(grid, '.o_grid_section:eq(0) th:contains(Unknown)',
            "first section should'nt have a row without task");
        assert.containsOnce(grid, '.o_grid_section:eq(0) th:contains(BS task)',
            "first section should have a row for BS task");

        var grid_anchor = grid.$('thead tr').text().split(',\n').join().replace(/\s/g, '');
        assert.equal(grid_anchor, "Wed,Jan25", "grid should start with grid_anchor date as the default date.");

        await testUtils.dom.click(grid.$buttons.find('button.grid_arrow_next'));

        var next_date = grid.$('thead tr').text().split(',\n').join().replace(/\s/g, '');
        assert.equal(next_date, 'Thu,Jan26', "Date should be of next day.");
        assert.containsOnce(grid, 'thead th:not(.o_grid_title_header)', "Single Day column should be shown");

        await testUtils.dom.click(grid.$buttons.find('button.grid_arrow_previous'));

        var previous_date = grid.$('thead tr').text().split(',\n').join().replace(/\s/g, '');
        assert.equal(previous_date, "Wed,Jan25", "Date should be today's date.");
        assert.containsOnce(grid, 'thead th:not(.o_grid_title_header)', "Single Day column should be shown");
        grid.destroy();
    });

    QUnit.test('work well with selection fields', async function (assert) {
        assert.expect(1);

        this.data['analytic.line'].fields.foo = {
            type: "selection",
            selection: [['a', 'A'], ['b', 'B']]
        };
        this.data['analytic.line'].records.forEach(function (record) {
            record.foo = "a";
        });

        this.arch = '<grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">' +
            '<field name="project_id" type="row"/>' +
            '<field name="foo" type="row"/>' +
            '<field name="date" type="col">' +
                '<range name="week" string="Week" span="week" step="day"/>' +
                '<range name="month" string="Month" span="month" step="day" invisible="context.get(\'hide_second_button\')"/>' +
                '<range name="year" string="Year" span="year" step="month"/>' +
            '</field>'+
            '<field name="unit_amount" type="measure" widget="float_time"/>' +
        '</grid>';


        var grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: this.arch,
            currentDate: "2017-01-25",
            mockRPC: function (route) {
                if (route === 'some-image') {
                    return Promise.resolve();
                }
                return this._super.apply(this, arguments);
            },
            debug: true,
        });

        await testUtils.nextTick();
        assert.strictEqual(grid.$('th div').first()[0].innerHTML, `<div title="P1" class="">P1</div><div title="A" class="">A</div>`,
            "should render properly selection value");
        grid.destroy();
    });

    QUnit.test('button disabled after blur', async function (assert) {
        /*
         * OPW 2121906
         * We disable the button and enable it only when the RPC call is done.
         * Without this limitation, stressing the view can cause concurrency issues.
         */

        assert.expect(3);
        const def = testUtils.makeTestPromise();
        let rpcCalled = false;

        const grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: '<grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">' +
                    '<field name="project_id" type="row" section="1"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                        '<range name="month" string="Month" span="month" step="day"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_toggle" options="{\'factor\': 0.125, \'range\': [0.0, 0.5, 1.0]}"/>' +
                '</grid>',
            currentDate: "2017-01-31",
            async mockRPC (route, args) {
                if (args.method === 'adjust_grid') {
                    rpcCalled = true;
                    await def;
                }
                return this._super.apply(this, arguments);
            },
        });

        const $button = grid.$('.o_grid_section:eq(1) .o_grid_cell_container[data-path="1.grid.0.0"] button');
        $button.focus();
        testUtils.dom.click($button);
        $button.blur();
        await testUtils.nextTick();

        assert.ok(rpcCalled, 'The RPC should be called');
        assert.ok($button.is(':disabled'), 'the button is disabled while the RPC call is not done');

        def.resolve();
        await testUtils.nextTick();

        assert.notOk($button.is(':disabled'), 'the button is enabled when the RPC call is done');
        grid.destroy();
    });

    QUnit.test('each button\'s value is correct after RPC call', async function (assert) {
        /*
         * OPW 2121906
         * We disable the button and enable it only when the RPC call is done.
         * Without this limitation, stressing the view can cause concurrency issues.
         */
        assert.expect(3);
        const def = testUtils.makeTestPromise();
        let rpcCalled = false;

        const grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: '<grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">' +
                    '<field name="project_id" type="row" section="1"/>' +
                    '<field name="task_id" type="row"/>' +
                    '<field name="date" type="col">' +
                        '<range name="week" string="Week" span="week" step="day"/>' +
                        '<range name="month" string="Month" span="month" step="day"/>' +
                    '</field>'+
                    '<field name="unit_amount" type="measure" widget="float_toggle" options="{\'factor\': 0.125, \'range\': [0.0, 0.5, 1.0]}"/>' +
                '</grid>',
            currentDate: "2017-01-31",
            async mockRPC (route, args) {
                if (args.method === 'adjust_grid') {
                    rpcCalled = true;
                    await def;
                }
                return this._super.apply(this, arguments);
            },
        });

        var $button1 = grid.$('.o_grid_section:eq(1) .o_grid_cell_container[data-path="1.grid.0.0"] button');
        var $button2 = grid.$('.o_grid_section:eq(1) .o_grid_cell_container[data-path="1.grid.0.2"] button');

        $button1.focus();
        $button1.click();
        $button1.blur();
        await testUtils.nextTick();
        assert.ok(rpcCalled, 'The RPC should be called');

        $button2.click();
        def.resolve();
        await testUtils.nextTick();

        assert.strictEqual($button1.text(), '0.50');
        assert.strictEqual($button2.text(), '0.50');
        grid.destroy();
    });
});
});
