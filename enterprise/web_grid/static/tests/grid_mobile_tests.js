odoo.define('web_grid.grid_mobile_tests', function (require) {
"use strict";

let GridView = require('web_grid.GridView');
let testUtils = require('web.test_utils');

let createView = testUtils.createView;

QUnit.module('Views', {
    beforeEach: function () {
        this.data = {
            'analytic.line': {
                fields: {
                    project_id: {string: "Project", type: "many2one", relation: "project"},
                    task_id: {string: "Task", type: "many2one", relation: "task"},
                    date: {string: "Date", type: "date"},
                    unit_amount: {string: "Unit Amount", type: "float"},
                },
                records: [
                    {id: 1, project_id: 31, date: "2017-01-24", unit_amount: 2.5},
                    {id: 2, project_id: 31, task_id: 1, date: "2017-01-25", unit_amount: 2},
                    {id: 3, project_id: 31, task_id: 1, date: "2017-01-25", unit_amount: 5.5},
                    {id: 4, project_id: 31, task_id: 1, date: "2017-01-30", unit_amount: 10},
                    {id: 5, project_id: 142, task_id: 12, date: "2017-01-31", unit_amount: 3.5},
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
        this.arch = `
            <grid string="Timesheet" adjustment="object" adjust_name="adjust_grid">
                <field name="project_id" type="row"/>
                <field name="task_id" type="row"/>
                <field name="date" type="col">
                    <range name="week" string="Week" span="week" step="day"/>
                </field>
                <field name="unit_amount" type="measure" widget="float_time"/>
            </grid>
        `;
    }
}, function () {
    QUnit.module('GridView Mobile');

    QUnit.test('basic grid view, range button in mobile', async function (assert) {
        assert.expect(5);
        let countCallRPC = 0;
        let grid = await createView({
            View: GridView,
            model: 'analytic.line',
            data: this.data,
            arch: this.arch,
            currentDate: "2017-01-25",
            mockRPC: function (route, args) {
                if (args.method === 'read_grid') {
                    if (countCallRPC === 0) {
                        assert.equal(args.kwargs.range.span, 'day', "range should be day");
                    } else if (countCallRPC === 1) {
                        assert.equal(args.kwargs.range.span, 'week', "range should be month");
                    }
                }
                countCallRPC++;
                return this._super.apply(this, arguments);
            },
        });

        await testUtils.nextTick();
        assert.equal(grid.$('table').length, 1, "should have rendered one table");

        let btnCal = grid.$buttons.find('.btn-group.o_grid_range > button.btn.fa-calendar');
        assert.equal(btnCal.length, 1, "should have a calendar button for range");
        await testUtils.dom.click(btnCal);

        // Day range should be automatically added.
        let btnRange = grid.$buttons.find('.btn-group.o_grid_range button.grid_arrow_range');
        assert.equal(btnRange.length, 2, "should have two range buttons (Day and Week)");

        await testUtils.dom.click(grid.$buttons.find('button[data-name=week]'));

        grid.destroy();
    });
});
});
