odoo.define('web_gantt.tests', function (require) {
'use strict';

var GanttView = require('web_gantt.GanttView');
var GanttRenderer = require('web_gantt.GanttRenderer');
var GanttRow = require('web_gantt.GanttRow');
var testUtils = require('web.test_utils');


var initialDate = new Date(2018, 11, 20, 8, 0, 0);
initialDate = new Date(initialDate.getTime() - initialDate.getTimezoneOffset() * 60 * 1000);

var createView = testUtils.createView;

// The gantt view uses momentjs for all time computation, which bypasses
// tzOffset, making it hard to test. We had two solutions to test this:
//
// 1. Change everywhere in gantt where we use momentjs to manual
//    manipulations using tzOffset so that we can manipulate it tests.
//    Pros:
//      - Consistent with other mechanisms in Odoo.
//      - Full coverage of the behavior since we can manipulate in tests
//    Cons:
//      - We need to change nearly everything everywhere in gantt
//      - The code works, it is sad to have to change it, risking to
//        introduce new bugs, just to be able to test this.
//      - Just applying the tzOffset to the date is not as easy as it
//        sounds. Moment is smart. It offsets the date with the offset
//        that you would locally have AT THAT DATE. Meaning that it
//        sometimes offsets of 1 hour or 2 hour in the same locale
//        depending as if the particular datetime we are offseting would
//        be in DST or not at that time. We would have to handle all
//        the DST conversion shenanigans manually to be correct.
//
// 2. Use the same computation path as the production code to compute
//    the expected value.
//    Pros:
//      - Very easy to implement
//      - Momentjs is smart, see last Con above. It does all the heavy
//        lifting for us and it is a well known, stable and maintained
//        library, so we can trust it on these matters.
//    Cons:
//      - The test relies on the behavior of Momentjs. If the library
//        has a bug, the gantt view will have an issue that this test
//        will never be able to see.
//
// Considering the Cons of the first option are tremendous and the one
// of the second option is offest by the fact that we consider Momentjs
// to be a trustworthy library, we chose option 2. It was required in
// only a few test but we think it was still interesting to mention it.

function getPillItemWidth($el) {
    return $el.attr('style').split('width: ')[1].split(';')[0];
}

QUnit.module('Views', {
    beforeEach: function () {
        this.data = {
            tasks: {
                fields: {
                    id: {string: 'ID', type: 'integer'},
                    name: {string: 'Name', type: 'char'},
                    start: {string: 'Start Date', type: 'datetime'},
                    stop: {string: 'Stop Date', type: 'datetime'},
                    progress: {string: "progress", type: "integer"},
                    time: {string: "Time", type: "float"},
                    stage: {string: 'Stage', type: 'selection', selection: [['todo', 'To Do'], ['in_progress', 'In Progress'], ['done', 'Done'], ['cancel', 'Cancelled']]},
                    project_id: {string: 'Project', type: 'many2one', relation: 'projects'},
                    user_id: {string: 'Assign To', type: 'many2one', relation: 'users'},
                    active: {string: "active", type: "boolean", default: true},
                    color: {string: 'Color', type: 'integer'},
                    progress: {string: 'Progress', type: 'integer'},
                    exclude: {string: 'Excluded from Consolidation', type: 'boolean'},
                    stage_id: {string: "Stage", type: "many2one", relation: 'stage'}
                },
                records: [
                    { id: 1, name: 'Task 1', start: '2018-11-30 18:30:00', stop: '2018-12-31 18:29:59', stage: 'todo', stage_id: 1, project_id: 1, user_id: 1, color: 0, progress: 0},
                    { id: 2, name: 'Task 2', start: '2018-12-17 11:30:00', stop: '2018-12-22 06:29:59', stage: 'done', stage_id: 4, project_id: 1, user_id: 2, color: 2, progress: 30},
                    { id: 3, name: 'Task 3', start: '2018-12-27 06:30:00', stop: '2019-01-03 06:29:59', stage: 'cancel', stage_id: 3, project_id: 1, user_id: 2, color: 10, progress: 60},
                    { id: 4, name: 'Task 4', start: '2018-12-19 18:30:00', stop: '2018-12-20 06:29:59', stage: 'in_progress', stage_id: 3, project_id: 1, user_id: 1, color: 1, progress: false, exclude: 0},
                    { id: 5, name: 'Task 5', start: '2018-11-08 01:53:10', stop: '2018-12-04 02:34:34', stage: 'done', stage_id: 2, project_id: 2, user_id: 1, color: 2, progress: 100, exclude: 1},
                    { id: 6, name: 'Task 6', start: '2018-11-19 23:00:00', stop: '2018-11-20 04:21:01', stage: 'in_progress', stage_id: 4, project_id: 2, user_id: 1, color: 1, progress: 0},
                    { id: 7, name: 'Task 7', start: '2018-12-20 06:30:12', stop: '2018-12-20 18:29:59', stage: 'cancel', stage_id: 1, project_id: 2, user_id: 2, color: 10, progress: 80},
                ],
            },
            projects: {
                fields: {
                    id: {string: 'ID', type: 'integer'},
                    name: {string: 'Name', type: 'char'},
                },
                records: [
                    {id: 1, name: 'Project 1'},
                    {id: 2, name: 'Project 2'},
                ],
            },
            users: {
                fields: {
                    id: {string: 'ID', type: 'integer'},
                    name: {string: 'Name', type: 'char'},
                },
                records: [
                    {id: 1, name: 'User 1'},
                    {id: 2, name: 'User 2'},
                ],
            },
            stage: {
                fields: {
                    name: {string: "Name", type: "char"},
                    sequence: {string: "Sequence", type: "integer"}
                },
                records: [{
                    id: 1,
                    name: "in_progress",
                    sequence: 2,
                }, {
                    id: 3,
                    name: "cancel",
                    sequence: 4,
                }, {
                    id: 2,
                    name: "todo",
                    sequence: 1,
                }, {
                    id: 4,
                    name: "done",
                    sequence: 3,
                }]
            },
        };
    },
}, function () {
    QUnit.module('GanttView');

    // BASIC TESTS

    QUnit.test('empty ungrouped gantt rendering', async function (assert) {
        assert.expect(3);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            domain: [['id', '=', 0]],
        });

        assert.containsOnce(gantt, '.o_gantt_header_container',
            'should have a header');
        assert.containsN(gantt, '.o_gantt_header_container .o_gantt_header_scale .o_gantt_header_cell', 31,
            'should have a 31 slots for month view');
        assert.containsOnce(gantt, '.o_gantt_row_container .o_gantt_row',
            'should have a 1 row');

        gantt.destroy();
    });

    QUnit.test('ungrouped gantt rendering', async function (assert) {
        assert.expect(20);

        // This is one of the few tests which have dynamic assertions, see
        // our justification for it in the comment at the top of this file

        var task2 = this.data.tasks.records[1];
        var startDateUTCString = task2.start;
        var startDateUTC = moment.utc(startDateUTCString);
        var startDateLocalString = startDateUTC.local().format('DD MMM, hh:mm A');

        var stopDateUTCString = task2.stop;
        var stopDateUTC = moment.utc(stopDateUTCString);
        var stopDateLocalString = stopDateUTC.local().format('DD MMM, hh:mm A');

        var POPOVER_DELAY = GanttRow.prototype.POPOVER_DELAY;
        GanttRow.prototype.POPOVER_DELAY = 0;

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            mockRPC: function (route, args) {
                if (route === '/web/dataset/search_read') {
                    assert.strictEqual(args.model, 'tasks',
                        "should read on the correct model");
                } else if (route === '/web/dataset/call_kw/tasks/read_group') {
                    throw Error("Should not call read_group when no groupby !");
                }
                return this._super.apply(this, arguments);
            },
            session: {
                getTZOffset: function () {
                    return 60;
                },
            },
        });

        assert.containsOnce(gantt, '.o_gantt_header_container',
            'should have a header');
        assert.hasClass(gantt.$buttons.find('.o_gantt_button_scale[data-value=month]'), 'active',
            'month view should be activated by default');
        assert.notOk(gantt.$buttons.find('.o_gantt_button_expand_rows').is(':visible'),
            "the expand button should be invisible (only displayed if useful)");
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), 'December 2018',
            'should contain "December 2018" in header');
        assert.containsN(gantt, '.o_gantt_header_container .o_gantt_header_scale .o_gantt_header_cell', 31,
            'should have a 31 slots for month view');
        assert.containsOnce(gantt, '.o_gantt_row_container .o_gantt_row',
            'should have a 1 row');
        assert.containsNone(gantt, '.o_gantt_row_container .o_gantt_row .o_gantt_row_sidebar',
            'should not have a sidebar');
        assert.containsN(gantt, '.o_gantt_pill_wrapper', 6,
            'should have a 6 pills');

        // verify that the level offset is correctly applied (add 1px gap border compensation for each level)
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_cell[data-date="2018-12-01 00:00:00"] .o_gantt_pill_wrapper:contains(Task 1)').css('margin-top'), '0px',
            'task 1 should be in first level');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_cell[data-date="2018-12-01 00:00:00"] .o_gantt_pill_wrapper:contains(Task 5)').css('margin-top'), GanttRow.prototype.LEVEL_TOP_OFFSET + 1 +'px',
            'task 5 should be in second level');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_cell[data-date="2018-12-17 00:00:00"] .o_gantt_pill_wrapper:contains(Task 2)').css('margin-top'), GanttRow.prototype.LEVEL_TOP_OFFSET + 1 +'px',
            'task 2 should be in second level');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_cell[data-date="2018-12-20 00:00:00"] .o_gantt_pill_wrapper:contains(Task 4)').css('margin-top'), 2 * GanttRow.prototype.LEVEL_TOP_OFFSET + 2 +'px',
            'task 4 should be in third level');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_cell[data-date="2018-12-20 00:00:00"] .o_gantt_pill_wrapper:contains(Task 7)').css('margin-top'), 2 * GanttRow.prototype.LEVEL_TOP_OFFSET + 2 +'px',
            'task 7 should be in third level');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_cell[data-date="2018-12-27 00:00:00"] .o_gantt_pill_wrapper:contains(Task 3)').css('margin-top'), GanttRow.prototype.LEVEL_TOP_OFFSET + 1 +'px',
            'task 3 should be in second level');

        // test popover and local timezone
        assert.containsNone(gantt, 'div.popover', 'should not have a popover');
        gantt.$('.o_gantt_pill:contains("Task 2")').trigger('mouseenter');
        await testUtils.nextTick();
        assert.containsOnce($, 'div.popover', 'should have a popover');

        assert.strictEqual($('div.popover .flex-column span:nth-child(2)').text(), startDateLocalString,
            'popover should display start date of task 2 in local time');
        assert.strictEqual($('div.popover .flex-column span:nth-child(3)').text(), stopDateLocalString,
            'popover should display start date of task 2 in local time');

        gantt.destroy();
        assert.containsNone(gantt, 'div.popover', 'should not have a popover anymore');
        GanttRow.prototype.POPOVER_DELAY = POPOVER_DELAY;
    });

    QUnit.test('ordered gantt view', async function (assert) {
        assert.expect(1);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" progress="progress"></gantt>',
            groupBy: ['stage_id'],
            viewOptions: {
                initialDate: initialDate,
            },
        })

        assert.strictEqual(gantt.$('.o_gantt_row_title').text().replace(/\s/g, ''),
            "todoin_progressdonecancel");

        gantt.destroy();
    });

    QUnit.test('empty single-level grouped gantt rendering', async function (assert) {
        assert.expect(3);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['project_id'],
            domain: [['id', '=', 0]],
        });

        assert.containsOnce(gantt, '.o_gantt_header_container',
            'should have a header');
        assert.containsN(gantt, '.o_gantt_header_container .o_gantt_header_scale .o_gantt_header_cell', 31,
            'should have a 31 slots for month view');
        assert.containsOnce(gantt, '.o_gantt_row_container .o_gantt_row',
            'should have a 1 row');

        gantt.destroy();
    });

    QUnit.test('single-level grouped gantt rendering', async function (assert) {
        assert.expect(12);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt string="Tasks" date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['project_id'],
        });

        assert.containsOnce(gantt, '.o_gantt_header_container',
            'should have a header');
        assert.hasClass(gantt.$buttons.find('.o_gantt_button_scale[data-value=month]'), 'active',
            'month view should by default activated');
        assert.notOk(gantt.$buttons.find('.o_gantt_button_expand_rows').is(':visible'),
            "the expand button should be invisible (only displayed if useful)");
        assert.strictEqual(gantt.$('.o_gantt_header_container > .o_gantt_row_sidebar').text().trim(), 'Tasks',
            'should contain "Tasks" in header sidebar');
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), 'December 2018',
            'should contain "December 2018" in header');
        assert.containsN(gantt, '.o_gantt_header_container .o_gantt_header_scale .o_gantt_header_cell', 31,
            'should have a 31 slots for month view');
        assert.containsN(gantt, '.o_gantt_row_container .o_gantt_row', 2,
            'should have a 2 rows');
        assert.containsOnce(gantt, '.o_gantt_row_container .o_gantt_row:nth-child(2) .o_gantt_row_sidebar',
            'should have a sidebar');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_row:nth-child(2) .o_gantt_row_title').text().trim(), 'Project 1',
            'should contain "Project 1" in sidebar title');
        assert.containsN(gantt, '.o_gantt_row_container .o_gantt_row:nth-child(2) .o_gantt_pill_wrapper', 4,
            'should have a 4 pills in first row');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_row:last-child .o_gantt_row_title').text().trim(), 'Project 2',
            'should contain "Project 2" in sidebar title');
        assert.containsN(gantt, '.o_gantt_row_container .o_gantt_row:last-child .o_gantt_pill_wrapper', 2,
            'should have a 2 pills in first row');

        gantt.destroy();
    });

    QUnit.test('single-level grouped gantt rendering with group_expand', async function (assert) {
        assert.expect(12);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt string="Tasks" date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['project_id'],
            mockRPC: function (route) {
                if (route === '/web/dataset/call_kw/tasks/read_group') {
                    return Promise.resolve([
                        { project_id: [20, "Unused Project 1"], project_id_count: 0 },
                        { project_id: [50, "Unused Project 2"], project_id_count: 0 },
                        { project_id: [2, "Project 2"], project_id_count: 2 },
                        { project_id: [30, "Unused Project 3"], project_id_count: 0 },
                        { project_id: [1, "Project 1"], project_id_count: 4 }
                    ]);
                }
                return this._super.apply(this, arguments);
            },
        });

        assert.containsOnce(gantt, '.o_gantt_header_container',
            'should have a header');
        assert.hasClass(gantt.$buttons.find('.o_gantt_button_scale[data-value=month]'), 'active',
            'month view should by default activated');
        assert.notOk(gantt.$buttons.find('.o_gantt_button_expand_rows').is(':visible'),
            "the expand button should be invisible (only displayed if useful)");
        assert.strictEqual(gantt.$('.o_gantt_header_container > .o_gantt_row_sidebar').text().trim(), 'Tasks',
            'should contain "Tasks" in header sidebar');
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), 'December 2018',
            'should contain "December 2018" in header');
        assert.containsN(gantt, '.o_gantt_header_container .o_gantt_header_scale .o_gantt_header_cell', 31,
            'should have a 31 slots for month view');
        assert.containsN(gantt, '.o_gantt_row_container .o_gantt_row', 5,
            'should have a 5 rows');
        assert.containsOnce(gantt, '.o_gantt_row_container .o_gantt_row:nth-child(2) .o_gantt_row_sidebar',
            'should have a sidebar');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_row:nth-child(2) .o_gantt_row_title').text().trim(), 'Unused Project 1',
            'should contain "Unused Project" in sidebar title');
        assert.containsN(gantt, '.o_gantt_row_container .o_gantt_row:nth-child(2) .o_gantt_pill_wrapper', 0,
            'should have 0 pills in first row');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_row:last-child .o_gantt_row_title').text().trim(), 'Project 1',
            'should contain "Project 1" in sidebar title');
        assert.containsN(gantt, '.o_gantt_row_container .o_gantt_row:not(.o_gantt_total_row):last-child .o_gantt_pill_wrapper', 4,
            'should have 4 pills in last row');

        gantt.destroy();
    });

    QUnit.test('multi-level grouped gantt rendering', async function (assert) {
        assert.expect(31);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt string="Tasks" date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['user_id', 'project_id', 'stage'],
        });

        assert.containsOnce(gantt, '.o_gantt_header_container',
            'should have a header');
        assert.hasClass(gantt.$buttons.find('.o_gantt_button_scale[data-value=month]'), 'active',
            'month view should by default activated');
        assert.ok(gantt.$buttons.find('.o_gantt_button_expand_rows').is(':visible'),
            "there should be an expand button");
        assert.strictEqual(gantt.$('.o_gantt_header_container > .o_gantt_row_sidebar').text().trim(), 'Tasks',
            'should contain "Tasks" in header sidebar');
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), 'December 2018',
            'should contain "December 2018" in header');
        assert.containsN(gantt, '.o_gantt_header_container .o_gantt_header_scale .o_gantt_header_cell', 31,
            'should have a 31 slots for month view');
        assert.containsN(gantt, '.o_gantt_row_container .o_gantt_row', 12,
            'should have a 12 rows');
        assert.containsN(gantt, '.o_gantt_row_container .o_gantt_row_group.open', 6,
            'should have a 6 opened groups');
        assert.containsN(gantt, '.o_gantt_row_container .o_gantt_row:not(.o_gantt_row_group)', 6,
            'should have a 6 rows');
        assert.containsOnce(gantt, '.o_gantt_row_container .o_gantt_row:first .o_gantt_row_sidebar',
            'should have a sidebar');

        // Check grouped rows
        assert.hasClass(gantt.$('.o_gantt_row_container .o_gantt_row:first'), 'o_gantt_row_group',
            '1st row should be a group');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_row:first .o_gantt_row_title').text().trim(), 'User 1',
            '1st row title should be "User 1"');

        assert.hasClass(gantt.$('.o_gantt_row_container .o_gantt_row:nth(1)'), 'o_gantt_row_group',
            '2nd row should be a group');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_row:nth(1) .o_gantt_row_title').text().trim(), 'Project 1',
            '2nd row title should be "Project 1"');

        assert.hasClass(gantt.$('.o_gantt_row_container .o_gantt_row:nth(4)'), 'o_gantt_row_group',
            '5th row should be a group');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_row:nth(4) .o_gantt_row_title').text().trim(), 'Project 2',
            '5th row title should be "Project 2"');

        assert.hasClass(gantt.$('.o_gantt_row_container .o_gantt_row:nth(6)'), 'o_gantt_row_group',
            '7th row should be a group');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_row:nth(6) .o_gantt_row_title').text().trim(), 'User 2',
            '7th row title should be "User 2"');

        assert.hasClass(gantt.$('.o_gantt_row_container .o_gantt_row:nth(7)'), 'o_gantt_row_group',
            '8th row should be a group');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_row:nth(7) .o_gantt_row_title').text().trim(), 'Project 1',
            '8th row title should be "Project 1"');

        assert.hasClass(gantt.$('.o_gantt_row_container .o_gantt_row:nth(10)'), 'o_gantt_row_group',
            '11th row should be a group');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_row:nth(10) .o_gantt_row_title').text().trim(), 'Project 2',
            '11th row title should be "Project 2"');

        // group row count and greyscale
        assert.strictEqual(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_consolidated_pill_title').text().replace(/\s+/g, ''), "2121",
            "the count should be correctly computed");

        assert.strictEqual(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_pill:eq(0)').css('background-color'), "rgb(0, 160, 157)",
            "the 1st group pill should have the correct grey scale)");
        assert.strictEqual(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_pill:eq(1)').css('background-color'), "rgb(0, 160, 157)",
            "the 2nd group pill should have the correct grey scale)");
        assert.strictEqual(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_pill:eq(2)').css('background-color'), "rgb(0, 160, 157)",
            "the 3rd group pill should have the correct grey scale");
        assert.strictEqual(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_pill:eq(3)').css('background-color'), "rgb(0, 160, 157)",
            "the 4th group pill should have the correct grey scale");

        assert.strictEqual(getPillItemWidth(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_pill_wrapper:eq(0)')), "calc(300% + 2px)",
            "the 1st group pill should have the correct width (1 to 3 dec)");
        assert.strictEqual(getPillItemWidth(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_pill_wrapper:eq(1)')), "calc(1600% + 15px)",
            "the 2nd group pill should have the correct width (4 to 19 dec)");
        assert.strictEqual(getPillItemWidth(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_pill_wrapper:eq(2)')), "50%",
            "the 3rd group pill should have the correct width (20 morning dec");
        assert.strictEqual(getPillItemWidth(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_pill_wrapper:eq(3)')), "calc(1150% + 10px)",
            "the 4th group pill should have the correct width (20 afternoon to 31 dec");

        gantt.destroy();
    });

    QUnit.test('full precision gantt rendering', async function(assert) {
        assert.expect(1);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" default_scale="week" date_stop="stop" '
                    + 'precision="{\'day\': \'hour:full\', \'week\':'
                    + ' \'day:full\', \'month\': \'day:full\'}" />',
            viewOptions: {
                initialDate: new Date(2018, 10, 15, 8, 0, 0),
            },
            groupBy: ['user_id', 'project_id']
        });

        assert.strictEqual(getPillItemWidth(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_pill_wrapper:eq(0)')), "calc(700% + 6px)",
            "the group pill should have the correct width (7 days)");

        gantt.destroy();
    });

    QUnit.test('gantt rendering, thumbnails', async function (assert) {
        assert.expect(2);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt string="Tasks" date_start="start" date_stop="stop" thumbnails="{\'user_id\': \'image\'}" />',
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['user_id'],
            mockRPC: function (route, args) {
                console.log(route)
                if (route.endsWith('search_read')) {
                    return Promise.resolve({
                        records: [
                            {
                                display_name: "Task 1",
                                id: 1,
                                start: "2018-11-30 18:30:00",
                                stop: "2018-12-31 18:29:59",
                                user_id: [1, "User 2"],
                            },{
                                display_name: "FALSE",
                                id: 1,
                                start: "2018-12-01 18:30:00",
                                stop: "2018-12-02 18:29:59",
                                user_id: false,
                            }
                        ]
                    })
                }
                if(route.endsWith('read_group')) {
                    return Promise.resolve([
                        {
                            user_id: [1, "User 1"],
                            user_id_count: 3,
                            __domain: [
                                ["user_id", "=", 1],
                                ["start", "<=", "2018-12-31 23:59:59"],
                                ["stop", ">=", "2018-12-01 00:00:00"],
                            ]
                        },{
                            user_id: false,
                            user_id_count: 3,
                            __domain: [
                                ["user_id", "=", false],
                                ["start", "<=", "2018-12-31 23:59:59"],
                                ["stop", ">=", "2018-12-01 00:00:00"],
                            ]
                        }
                    ])
                }
                return this._super.apply(this, arguments);
            }
        });


        assert.containsN(gantt, '.o_gantt_row_thumbnail', 1, 'There should be a thumbnail per row where user_id is defined');

        assert.ok(gantt.$('.o_gantt_row_thumbnail:nth(0)')[0].dataset.src.endsWith('web/image?model=users&id=1&field=image'));

        gantt.destroy();
    });

    QUnit.test('scale switching', async function (assert) {
        assert.expect(17);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
        });

        // default (month)
        assert.hasClass(gantt.$buttons.find('.o_gantt_button_scale[data-value=month]'), 'active',
            'month view should be activated by default');

        // switch to day view
        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_scale[data-value=day]'));
        assert.hasClass(gantt.$buttons.find('.o_gantt_button_scale[data-value=day]'), 'active',
            'day view should be activated');
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), '20 December 2018',
            'should contain "20 December 2018" in header');
        assert.containsN(gantt, '.o_gantt_header_container .o_gantt_header_scale .o_gantt_header_cell', 24,
            'should have a 24 slots for day view');
        assert.containsN(gantt, '.o_gantt_pill_wrapper', 4,
            'should have a 4 pills');

        // switch to week view
        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_scale[data-value=week]'));
        assert.hasClass(gantt.$buttons.find('.o_gantt_button_scale[data-value=week]'), 'active',
            'week view should be activated');
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), '16 December 2018 - 22 December 2018',
            'should contain "16 December 2018 - 22 December 2018" in header');
        assert.containsN(gantt, '.o_gantt_header_container .o_gantt_header_scale .o_gantt_header_cell', 7,
            'should have a 7 slots for week view');
        assert.containsN(gantt, '.o_gantt_pill_wrapper', 4,
            'should have a 4 pills');

        // switch to month view
        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_scale[data-value=month]'));
        assert.hasClass(gantt.$buttons.find('.o_gantt_button_scale[data-value=month]'), 'active',
            'month view should be activated');
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), 'December 2018',
            'should contain "December 2018" in header');
        assert.containsN(gantt, '.o_gantt_header_container .o_gantt_header_scale .o_gantt_header_cell', 31,
            'should have a 31 slots for month view');
        assert.containsN(gantt, '.o_gantt_pill_wrapper', 6,
            'should have a 6 pills');

        // switch to year view
        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_scale[data-value=year]'));
        assert.hasClass(gantt.$buttons.find('.o_gantt_button_scale[data-value=year]'), 'active',
            'year view should be activated');
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), '2018',
            'should contain "2018" in header');
        assert.containsN(gantt, '.o_gantt_header_container .o_gantt_header_scale .o_gantt_header_cell', 12,
            'should have a 12 slots for year view');
        assert.containsN(gantt, '.o_gantt_pill_wrapper', 7,
            'should have a 7 pills');

        gantt.destroy();
    });

    QUnit.test('today is highlighted', async function (assert) {
        assert.expect(2);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
        });

        var dayOfMonth = moment().date();
        assert.containsOnce(gantt, '.o_gantt_header_cell.o_gantt_today',
            "there should be an highlighted day");
        assert.strictEqual(parseInt(gantt.$('.o_gantt_header_cell.o_gantt_today').text(), 10), dayOfMonth,
            'the highlighted day should be today');

        gantt.destroy();
    });

    // BEHAVIORAL TESTS

    QUnit.test('date navigation with timezone (1h)', async function (assert) {
        assert.expect(32);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            mockRPC: function (route, args) {
                if (route === '/web/dataset/search_read') {
                    assert.step(args.domain.toString());
                }
                return this._super.apply(this, arguments);
            },
            session: {
                getTZOffset: function () {
                    return 60;
                },
            },
        });
        assert.verifySteps(["start,<=,2018-12-31 22:59:59,stop,>=,2018-11-30 23:00:00"]);

        // month navigation
        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_prev'));
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), 'November 2018',
            'should contain "November 2018" in header');
        assert.verifySteps(["start,<=,2018-11-30 22:59:59,stop,>=,2018-10-31 23:00:00"]);

        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_next'));
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), 'December 2018',
            'should contain "December 2018" in header');
        assert.verifySteps(["start,<=,2018-12-31 22:59:59,stop,>=,2018-11-30 23:00:00"]);

        // switch to day view and check day navigation
        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_scale[data-value=day]'));
        assert.verifySteps(["start,<=,2018-12-20 22:59:59,stop,>=,2018-12-19 23:00:00"]);

        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_prev'));
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), '19 December 2018',
            'should contain "19 December 2018" in header');
        assert.verifySteps(["start,<=,2018-12-19 22:59:59,stop,>=,2018-12-18 23:00:00"]);

        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_next'));
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), '20 December 2018',
            'should contain "20 December 2018" in header');
        assert.verifySteps(["start,<=,2018-12-20 22:59:59,stop,>=,2018-12-19 23:00:00"]);

        // switch to week view and check week navigation
        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_scale[data-value=week]'));
        assert.verifySteps(["start,<=,2018-12-22 22:59:59,stop,>=,2018-12-15 23:00:00"]);

        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_prev'));
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), '09 December 2018 - 15 December 2018',
            'should contain "09 December 2018 - 15 December 2018" in header');
        assert.verifySteps(["start,<=,2018-12-15 22:59:59,stop,>=,2018-12-08 23:00:00"]);

        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_next'));
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), '16 December 2018 - 22 December 2018',
            'should contain "16 December 2018 - 22 December 2018" in header');
        assert.verifySteps(["start,<=,2018-12-22 22:59:59,stop,>=,2018-12-15 23:00:00"]);

        // switch to year view and check year navigation
        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_scale[data-value=year]'));
        assert.verifySteps(["start,<=,2018-12-31 22:59:59,stop,>=,2017-12-31 23:00:00"]);

        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_prev'));
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), '2017',
            'should contain "2017" in header');
        assert.verifySteps(["start,<=,2017-12-31 22:59:59,stop,>=,2016-12-31 23:00:00"]);

        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_next'));
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), '2018',
            'should contain "2018" in header');
        assert.verifySteps(["start,<=,2018-12-31 22:59:59,stop,>=,2017-12-31 23:00:00"]);

        gantt.destroy();
    });

    QUnit.test('if a on_create is specified, execute the action rather than opening a dialog. And reloads after the action', async function(assert){
        assert.expect(3);
        var reloadCount = 0;

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" on_create="this_is_create_action" />',
            viewOptions: {
                initialDate: initialDate,
            },
            mockRPC: function (route, args) {
                if (route === '/web/dataset/search_read') {
                    reloadCount++;
                }
                return this._super.apply(this, arguments);
            },
        });

        testUtils.mock.intercept(gantt, 'do_action', function (event) {
            assert.strictEqual(event.data.action, 'this_is_create_action');
            event.data.options.on_close();
        });

        assert.strictEqual(reloadCount, 1);

        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_add'));
        await testUtils.nextTick();

        assert.strictEqual(reloadCount, 2);

        gantt.destroy();
    })

    QUnit.test('open a dialog to add a new task', async function (assert) {
        assert.expect(3);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            archs: {
                'tasks,false,form': '<form>' +
                        '<field name="name"/>' +
                        '<field name="start"/>' +
                        '<field name="stop"/>' +
                    '</form>',
            },
        });

        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_add'));

        // check that the dialog is opened with prefilled fields
        var $modal = $('.modal');
        assert.strictEqual($modal.length, 1, 'There should be one modal opened');
        assert.strictEqual($modal.find('.o_field_widget[name=start] .o_input').val(), '12/01/2018 00:00:00',
            'the start date should be the start of the focus month');
        assert.strictEqual($modal.find('.o_field_widget[name=stop] .o_input').val(), '12/31/2018 23:59:59',
            'the end date should be the end of the focus month');

        gantt.destroy();
    });

    QUnit.test('open a dialog to create/edit a task', async function (assert) {
        assert.expect(12);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            archs: {
                'tasks,false,form': '<form>' +
                        '<field name="name"/>' +
                        '<field name="start"/>' +
                        '<field name="stop"/>' +
                        '<field name="stage"/>' +
                        '<field name="project_id"/>' +
                        '<field name="user_id"/>' +
                    '</form>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['user_id', 'project_id', 'stage'],
        });

        // open dialog to create a task
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_row_container .o_gantt_row:nth(3) .o_gantt_cell[data-date="2018-12-10 00:00:00"] .o_gantt_cell_add'), "click");
        await testUtils.nextTick();
        // check that the dialog is opened with prefilled fields
        var $modal = $('.modal');
        assert.strictEqual($modal.length, 1, 'There should be one modal opened');
        assert.strictEqual($modal.find('.modal-title').text(), "Create");
        await testUtils.fields.editInput($modal.find('input[name=name]'), 'Task 8');
        var $modalFieldStart = $modal.find('.o_field_widget[name=start]');
        assert.strictEqual($modalFieldStart.find('.o_input').val(), '12/10/2018 00:00:00',
            'The start field should have a value "12/10/2018 00:00:00"');
        var $modalFieldStop = $modal.find('.o_field_widget[name=stop]');
        assert.strictEqual($modalFieldStop.find('.o_input').val(), '12/10/2018 23:59:59',
            'The stop field should have a value "12/10/2018 23:59:59"');
        var $modalFieldProject = $modal.find('.o_field_widget.o_field_many2one[name=project_id]');
        assert.strictEqual($modalFieldProject.find('.o_input').val(), 'Project 1',
            'The project field should have a value "Project 1"');
        var $modalFieldUser = $modal.find('.o_field_widget.o_field_many2one[name=user_id]');
        assert.strictEqual($modalFieldUser.find('.o_input').val(), 'User 1',
            'The user field should have a value "User 1"');
        var $modalFieldStage = $modal.find('.o_field_widget[name=stage]');
        assert.strictEqual($modalFieldStage.val(), '"in_progress"',
            'The stage field should have a value "In Progress"');

        // create the task
        await testUtils.modal.clickButton('Save & Close');
        assert.strictEqual($('.modal-lg').length, 0, 'Modal should be closed');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_row:nth(3) .o_gantt_cell[data-date="2018-12-10 00:00:00"] .o_gantt_pill').text().trim(), 'Task 8',
            'Task should be created with name "Task 8"');

        // open dialog to view a task
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_row_container .o_gantt_row:nth(3) .o_gantt_cell[data-date="2018-12-10 00:00:00"] .o_gantt_pill'), "click");
        await testUtils.nextTick();

        $modal = $('.modal-lg');
        assert.strictEqual($modal.find('.modal-title').text(), "Open");
        assert.strictEqual($modal.length, 1, 'There should be one modal opened');
        assert.strictEqual($modal.find('input[name=name]').val(), 'Task 8',
            'should open dialog for "Task 8"');

        gantt.destroy();
    });

    QUnit.test('open a dialog stops the resize/drag', async function (assert) {
        assert.expect(3);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            archs: {
                'tasks,false,form': '<form><field name="name"/></form>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
            domain: [['id', '=', 2]],
        });

        // open dialog to create a task
        // note that these 3 events need to be triggered for jQuery draggable
        // to be activated
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_pill'), "mouseenter");
        await testUtils.nextTick();
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_pill'), "click");
        await testUtils.nextTick();

        assert.containsOnce($, '.modal', 'There should be one modal opened');

        // close the modal without moving the mouse by pressing ESC
        $('.modal').trigger({type: 'keydown', which: $.ui.keyCode.ESCAPE});
        await testUtils.nextTick();
        assert.containsNone($, '.modal', 'There should be no modal opened');

        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_cell:first'), "mousemove");
        await testUtils.nextTick();
        assert.containsNone(gantt, '.o_gantt_dragging', "the pill should not be dragging");

        gantt.destroy();
    });

    QUnit.test('open a dialog to create a task, does not have a delete button', async function(assert){
        assert.expect(1);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            archs: {
                'tasks,false,form': '<form>' +
                        '<field name="name"/>' +
                        '<field name="start"/>' +
                        '<field name="stop"/>' +
                        '<field name="stage"/>' +
                        '<field name="project_id"/>' +
                        '<field name="user_id"/>' +
                    '</form>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['user_id', 'project_id', 'stage'],
        });

        // open dialog to create a task
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_row_container .o_gantt_row:nth(3) .o_gantt_cell[data-date="2018-12-10 00:00:00"] .o_gantt_cell_add'), "click");
        await testUtils.nextTick();

        var $modal = $('.modal');
        assert.containsNone($modal, '.o_btn_remove', 'There should be no delete button on create dialog');

        gantt.destroy();

    });

    QUnit.test('open a dialog to edit a task, has a delete buttton', async function(assert){
        assert.expect(1);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            archs: {
                'tasks,false,form': '<form>' +
                        '<field name="name"/>' +
                        '<field name="start"/>' +
                        '<field name="stop"/>' +
                        '<field name="stage"/>' +
                        '<field name="project_id"/>' +
                        '<field name="user_id"/>' +
                    '</form>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['user_id', 'project_id', 'stage'],
        });

        // open dialog to create a task
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_row_container .o_gantt_row:nth(3) .o_gantt_cell[data-date="2018-12-10 00:00:00"] .o_gantt_cell_add'), "click");
        await testUtils.nextTick();
        // create the task
        await testUtils.modal.clickButton('Save & Close');
        // open dialog to view the task
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_row_container .o_gantt_row:nth(3) .o_gantt_cell[data-date="2018-12-10 00:00:00"] .o_gantt_pill'), "click");
        await testUtils.nextTick();

        var $modal = $('.modal');

        assert.strictEqual($modal.find('.o_btn_remove').length, 1, 'There should be a delete button on edit dialog');

        gantt.destroy();
    });

    QUnit.test('clicking on delete button in edit dialog triggers a confirmation dialog, clicking discard does not call unlink on the model', async function(assert){
        assert.expect(4);

        var unlinkCallCount = 0;

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            archs: {
                'tasks,false,form': '<form>' +
                        '<field name="name"/>' +
                        '<field name="start"/>' +
                        '<field name="stop"/>' +
                        '<field name="stage"/>' +
                        '<field name="project_id"/>' +
                        '<field name="user_id"/>' +
                    '</form>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['user_id', 'project_id', 'stage'],
            mockRPC: function (route, args) {
                if (args.method === 'unlink') {
                    unlinkCallCount++;
                }
                return this._super.apply(this, arguments);
            }
        });

        // open dialog to create a task
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_row_container .o_gantt_row:nth(3) .o_gantt_cell[data-date="2018-12-10 00:00:00"] .o_gantt_cell_add'), "click");
        await testUtils.nextTick();
        // create the task
        await testUtils.modal.clickButton('Save & Close');
        // open dialog to view the task
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_row_container .o_gantt_row:nth(3) .o_gantt_cell[data-date="2018-12-10 00:00:00"] .o_gantt_pill'), "click");
        await testUtils.nextTick();

        var $modal = $('.modal');

        // trigger the delete button
        await testUtils.modal.clickButton('Remove');
        await testUtils.nextTick();

        var $dialog = $('.modal-dialog');

        // there sould be one more dialog
        assert.strictEqual($dialog.length, 2, 'Should have opened a new dialog');
        assert.strictEqual(unlinkCallCount, 0, 'should not call unlink on the model if dialog is cancelled');

        // trigger cancel
        await testUtils.modal.clickButton('Cancel');
        await testUtils.nextTick();

        $dialog = $('.modal-dialog');
        assert.strictEqual($dialog.length, 0, 'Should have closed all dialog');
        assert.strictEqual(unlinkCallCount, 0, 'Unlink should not have been called');

        gantt.destroy();
    });

    QUnit.test('clicking on delete button in edit dialog triggers a confirmation dialog, clicking ok call unlink on the model', async function(assert){
        assert.expect(4);

        var unlinkCallCount = 0;

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            archs: {
                'tasks,false,form': '<form>' +
                        '<field name="name"/>' +
                        '<field name="start"/>' +
                        '<field name="stop"/>' +
                        '<field name="stage"/>' +
                        '<field name="project_id"/>' +
                        '<field name="user_id"/>' +
                    '</form>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['user_id', 'project_id', 'stage'],
            mockRPC: function (route, args) {
                if (args.method === 'unlink') {
                    unlinkCallCount++;
                }
                return this._super.apply(this, arguments);
            }
        });

        // open dialog to create a task
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_row_container .o_gantt_row:nth(3) .o_gantt_cell[data-date="2018-12-10 00:00:00"] .o_gantt_cell_add'), "click");
        await testUtils.nextTick();
        // create the task
        await testUtils.modal.clickButton('Save & Close');
        // open dialog to view the task
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_row_container .o_gantt_row:nth(3) .o_gantt_cell[data-date="2018-12-10 00:00:00"] .o_gantt_pill'), "click");
        await testUtils.nextTick();

        // trigger the delete button
        await testUtils.modal.clickButton('Remove');
        await testUtils.nextTick();

        var $dialog = $('.modal-dialog');

        // there sould be one more dialog
        assert.strictEqual($dialog.length, 2, 'Should have opened a new dialog');
        assert.strictEqual(unlinkCallCount, 0, 'should not call unlink on the model if dialog is cancelled');

        // trigger ok
        await testUtils.modal.clickButton('Ok');
        await testUtils.nextTick();

        $dialog = $('.modal-dialog');
        assert.strictEqual($dialog.length, 0, 'Should have closed all dialog');
        assert.strictEqual(unlinkCallCount, 1, 'Unlink should have been called');

        gantt.destroy();
    });

    QUnit.test('create dialog with timezone', async function (assert) {
        assert.expect(4);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            archs: {
                'tasks,false,form': '<form>' +
                        '<field name="name"/>' +
                        '<field name="start"/>' +
                        '<field name="stop"/>' +
                        '<field name="stage"/>' +
                        '<field name="project_id"/>' +
                        '<field name="user_id"/>' +
                    '</form>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
            session: {
                getTZOffset: function () {
                    return 60;
                },
            },
            mockRPC: function (route, args) {
                if (args.method === 'create') {
                    assert.deepEqual(args.args, [{
                        name: false,
                        project_id: false,
                        stage: false,
                        start: "2018-12-09 23:00:00",
                        stop: "2018-12-10 22:59:59",
                        user_id: false,
                    }], "the start/stop date should take timezone into account");
                }
                return this._super.apply(this, arguments);
            },
        });

        // open dialog to create a task
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_cell[data-date="2018-12-10 00:00:00"] .o_gantt_cell_add'), "click");
        await testUtils.nextTick();

        assert.strictEqual($('.modal').length, 1, 'There should be one modal opened');
        assert.strictEqual($('.modal .o_field_widget[name=start] .o_input').val(), '12/10/2018 00:00:00',
            'The start field should have a value "12/10/2018 00:00:00"');
        assert.strictEqual($('.modal .o_field_widget[name = stop] .o_input').val(), '12/10/2018 23:59:59',
            'The stop field should have a value "12/10/2018 23:59:59"');

        // create the task
        await testUtils.modal.clickButton('Save & Close');

        gantt.destroy();
    });

    QUnit.test('plan button is not present if edit === false and plan is not specified', async function (assert) {
        assert.expect(1);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" edit="false" />',
            archs: {
                'tasks,false,list': '<tree><field name="name"/></tree>',
                'tasks,false,search': '<search><field name="name"/></search>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.strictEqual(gantt.$('.o_gantt_cell_plan').length, 0);

        gantt.destroy();
    });

    QUnit.test('plan button is not present if edit === false and plan is true', async function (assert) {
        assert.expect(1);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" edit="false" plan="true" />',
            archs: {
                'tasks,false,list': '<tree><field name="name"/></tree>',
                'tasks,false,search': '<search><field name="name"/></search>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.strictEqual(gantt.$('.o_gantt_cell_plan').length, 0);

        gantt.destroy();
    });

    QUnit.test('plan button is not present if edit === true and plan === false', async function (assert) {
        assert.expect(1);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" edit="true" plan="false" />',
            archs: {
                'tasks,false,list': '<tree><field name="name"/></tree>',
                'tasks,false,search': '<search><field name="name"/></search>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.strictEqual(gantt.$('.o_gantt_cell_plan').length, 0);

        gantt.destroy();
    });

    QUnit.test('plan button is present if edit === true and plan is not set', async function (assert) {
        assert.expect(1);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" edit="true" />',
            archs: {
                'tasks,false,list': '<tree><field name="name"/></tree>',
                'tasks,false,search': '<search><field name="name"/></search>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.notStrictEqual(gantt.$('.o_gantt_cell_plan').length, 0);

        gantt.destroy();
    });

    QUnit.test('plan button is present if edit === true and plan is true', async function (assert) {
        assert.expect(1);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" edit="true" plan="true" />',
            archs: {
                'tasks,false,list': '<tree><field name="name"/></tree>',
                'tasks,false,search': '<search><field name="name"/></search>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.notStrictEqual(gantt.$('.o_gantt_cell_plan').length, 0);

        gantt.destroy();
    });

    QUnit.test('open a dialog to plan a task', async function (assert) {
        assert.expect(5);

        this.data.tasks.records.push({ id: 41, name: 'Task 41' });
        this.data.tasks.records.push({ id: 42, name: 'Task 42', stop: '2018-12-31 18:29:59' });
        this.data.tasks.records.push({ id: 43, name: 'Task 43', start: '2018-11-30 18:30:00' });

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            archs: {
                'tasks,false,list': '<tree><field name="name"/></tree>',
                'tasks,false,search': '<search><field name="name"/></search>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
            mockRPC: function (route, args) {
                if (args.method === 'write') {
                    assert.strictEqual(args.model, 'tasks', "should write on the current model");
                    assert.deepEqual(args.args[0], [41, 42], "should write on the selected ids");
                    assert.deepEqual(args.args[1], { start: "2018-12-10 00:00:00", stop: "2018-12-10 23:59:59" },
                        "should write the correct values on the correct fields");
                }
                return this._super.apply(this, arguments);
            },
        });

        // click on the plan button
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_cell[data-date="2018-12-10 00:00:00"] .o_gantt_cell_plan'), "click");
        await testUtils.nextTick();

        assert.strictEqual($('.modal .o_list_view').length, 1,
            "a list view dialog should be opened");
        assert.strictEqual($('.modal .o_list_view tbody .o_data_cell').text().replace(/\s+/g, ''), "Task41Task42Task43",
            "the 3 records without date set should be displayed");

        await testUtils.dom.click($('.modal .o_list_view tbody tr:eq(0) input'));
        await testUtils.dom.click($('.modal .o_list_view tbody tr:eq(1) input'));
        await testUtils.dom.click($('.modal .o_select_button:contains(Select)'));

        gantt.destroy();
    });

    QUnit.test('open a dialog to plan a task (with timezone)', async function (assert) {
        assert.expect(2);

        this.data.tasks.records.push({ id: 41, name: 'Task 41' });

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            archs: {
                'tasks,false,list': '<tree><field name="name"/></tree>',
                'tasks,false,search': '<search><field name="name"/></search>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
            mockRPC: function (route, args) {
                if (args.method === 'write') {
                    assert.deepEqual(args.args[0], [41], "should write on the selected id");
                    assert.deepEqual(args.args[1], { start: "2018-12-09 23:00:00", stop: "2018-12-10 22:59:59" },
                        "should write the correct start/stop taking timezone into account");
                }
                return this._super.apply(this, arguments);
            },
            session: {
                getTZOffset: function () {
                    return 60;
                },
            },
        });

        // click on the plan button
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_cell[data-date="2018-12-10 00:00:00"] .o_gantt_cell_plan'), "click");
        await testUtils.nextTick();

        await testUtils.dom.click($('.modal .o_list_view tbody tr:eq(0) input'));
        await testUtils.dom.click($('.modal .o_select_button:contains(Select)'));

        gantt.destroy();
    });

    QUnit.test('open a dialog to plan a task (multi-level)', async function (assert) {
        assert.expect(2);

        this.data.tasks.records.push({ id: 41, name: 'Task 41' });

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            archs: {
                'tasks,false,list': '<tree><field name="name"/></tree>',
                'tasks,false,search': '<search><field name="name"/></search>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['user_id', 'project_id', 'stage'],
            mockRPC: function (route, args) {
                if (args.method === 'write') {
                    assert.deepEqual(args.args[0], [41], "should write on the selected id");
                    assert.deepEqual(args.args[1], {
                        project_id: 1,
                        stage: "todo",
                        start: "2018-12-10 00:00:00",
                        stop: "2018-12-10 23:59:59",
                        user_id: 1,
                    }, "should write on all the correct fields");
                }
                return this._super.apply(this, arguments);
            },
        });

        // click on the plan button
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_row:not(.o_gantt_row_group):first .o_gantt_cell[data-date="2018-12-10 00:00:00"] .o_gantt_cell_plan'), "click");
        await testUtils.nextTick();

        await testUtils.dom.click($('.modal .o_list_view tbody tr:eq(0) input'));
        await testUtils.dom.click($('.modal .o_select_button:contains(Select)'));

        gantt.destroy();
    });

    QUnit.test('expand/collapse rows', async function (assert) {
        assert.expect(8);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            groupBy: ['user_id', 'project_id', 'stage'],
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.containsN(gantt, '.o_gantt_row_group.open', 6,
            "there should be 6 opened grouped (2 for the users + 2 projects by users = 6)");
        assert.containsN(gantt, '.o_gantt_row_group:not(.open)', 0,
            "all groups should be opened");

        // collapse all groups
        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_collapse_rows'));
        assert.containsN(gantt, '.o_gantt_row_group:not(.open)', 2,
            "there should be 2 closed groups");
        assert.containsN(gantt, '.o_gantt_row_group.open', 0,
            "all groups should now be closed");

        // expand all groups
        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_expand_rows'));
        assert.containsN(gantt, '.o_gantt_row_group.open', 6,
            "there should be 6 opened grouped");
        assert.containsN(gantt, '.o_gantt_row_group:not(.open)', 0,
            "all groups should be opened again");

        // collapse the first group
        await testUtils.dom.click(gantt.$('.o_gantt_row_group:first .o_gantt_row_sidebar'));
        assert.containsN(gantt, '.o_gantt_row_group.open', 3,
            "there should be three open groups");
        assert.containsN(gantt, '.o_gantt_row_group:not(.open)', 1,
            "there should be 1 closed group");

        gantt.destroy();
    });

    QUnit.test('collapsed rows remain collapsed at reload', async function (assert) {
        assert.expect(6);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            groupBy: ['user_id', 'project_id', 'stage'],
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.containsN(gantt, '.o_gantt_row_group.open', 6,
            "there should be 6 opened grouped (2 for the users + 2 projects by users = 6)");
        assert.containsN(gantt, '.o_gantt_row_group:not(.open)', 0,
            "all groups should be opened");

        // collapse the first group
        await testUtils.dom.click(gantt.$('.o_gantt_row_group:first .o_gantt_row_sidebar'));
        assert.containsN(gantt, '.o_gantt_row_group.open', 3,
            "there should be three open groups");
        assert.containsN(gantt, '.o_gantt_row_group:not(.open)', 1,
            "there should be 1 closed group");

        // reload
        gantt.reload({});

        assert.containsN(gantt, '.o_gantt_row_group.open', 3,
            "there should be three open groups");
        assert.containsN(gantt, '.o_gantt_row_group:not(.open)', 1,
            "there should be 1 closed group");

        gantt.destroy();
    });

    QUnit.test('resize a pill', async function (assert) {
        assert.expect(13);

        var nbWrite = 0;
        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            domain: [['id', '=', 1]],
            mockRPC: function (route, args) {
                if (args.method === 'write') {
                    assert.deepEqual(args.args[0], [1]);
                    // initial dates -- start: '2018-11-30 18:30:00', stop: '2018-12-31 18:29:59'
                    if (nbWrite === 0) {
                        assert.deepEqual(args.args[1], { stop: "2018-12-30 18:29:59" });
                    } else {
                        assert.deepEqual(args.args[1], { start: "2018-11-29 18:30:00" });
                    }
                    nbWrite++;
                }
                return this._super.apply(this, arguments);
            },
        });

        assert.containsOnce(gantt, '.o_gantt_pill',
            "there should be one pill (Task 1)");
        assert.containsNone(gantt, '.o_gantt_pill.ui-resizable',
            "the pill should not be resizable after initial rendering");

        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_pill'), 'mouseenter');

        assert.containsOnce(gantt, '.o_gantt_pill.ui-resizable',
            "the pill should be resizable after mouse enter");

        assert.containsNone(gantt, '.ui-resizable-w',
            "there should be no left resizer for task 1 (it starts before december)");
        assert.containsOnce(gantt, '.ui-resizable-e',
            "there should be one right resizer for task 1");

        // resize to one cell smaller (-1 day)
        var cellWidth = gantt.$('.o_gantt_cell:first').width();
        await testUtils.dom.dragAndDrop(
            gantt.$('.ui-resizable-e'),
            gantt.$('.ui-resizable-e'),
            { position: { left: -cellWidth, top: 0 } }
        );

        // go to previous month (november)
        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_prev'));
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_pill'), 'mouseenter');

        assert.containsOnce(gantt, '.o_gantt_pill',
            "there should still be one pill (Task 1)");
        assert.containsNone(gantt, '.ui-resizable-e',
            "there should be no right resizer for task 1 (it stops after november)");
        assert.containsOnce(gantt, '.ui-resizable-w',
            "there should be one left resizer for task 1");

        // resize to one cell smaller (-1 day)
        await testUtils.dom.dragAndDrop(
            gantt.$('.ui-resizable-w'),
            gantt.$('.ui-resizable-w'),
            { position: { left: -cellWidth, top: 0 } }
        );

        assert.strictEqual(nbWrite, 2);

        gantt.destroy();
    });

    QUnit.test('resize a pill (2)', async function (assert) {
        // This test checks a tricky situation where the user resizes a pill, and
        // triggers the mouseup (i.e. release the mouse) over the pill. In this
        // case, the click should not be considered as a click on the pill to
        // edit it.
        assert.expect(6);

        const def = testUtils.makeTestPromise();
        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            archs: {
                'tasks,false,form': '<form/>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
            domain: [['id', '=', 2]],
            mockRPC: async function (route, args) {
                const result = this._super(...arguments);
                if (args.method === 'write') {
                    assert.deepEqual(args.args[1], { stop: "2018-12-23 06:29:59" });
                    await def;
                }
                return result;
            },
        });

        assert.containsOnce(gantt, '.o_gantt_pill',
            "there should be one pill (Task 1)");
        assert.containsNone(gantt, '.o_gantt_pill.ui-resizable',
            "the pill should not be resizable after initial rendering");

        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_pill'), 'mouseenter');

        assert.containsOnce(gantt, '.o_gantt_pill.ui-resizable',
            "the pill should be resizable after mouse enter");
        assert.containsOnce(gantt, '.ui-resizable-e',
            "there should be one right resizer for task 2");

        // resize to one cell larger, but do the mouseup over the pill
        const $resize = gantt.$('.ui-resizable-e');
        const cellWidth = gantt.$('.o_gantt_cell:first').width();
        const options = {
            position: {
                left: 0.9 * cellWidth, // do the mouseup over the pill
                top: 10,
            },
            withTrailingClick: true,
            mouseupTarget: gantt.$('.o_gantt_pill'),
        };
        await testUtils.dom.dragAndDrop($resize, $resize, options);

        def.resolve();
        assert.containsNone(document.body, '.modal',
            'shoud not have opened the dialog to edit the pill');

        gantt.destroy();
    });

    QUnit.test('create a task maintains the domain', async function (assert) {
        assert.expect(2);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop"></gantt>',
            archs: {
                'tasks,false,form': '<form><field name="name"/></form>',
            },
            domain: [['user_id', '=', 2]],  // I am an important line
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.containsN(gantt, '.o_gantt_pill', 3, "the list view is filtered");
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_cell:first .o_gantt_cell_add'), "click");
        await testUtils.nextTick();
        await testUtils.fields.editInput($('.modal .modal-body input[name=name]'), 'new task');
        await testUtils.modal.clickButton('Save & Close');
        assert.containsN(gantt, '.o_gantt_pill', 3,
            "the list view is still filtered after the save");

        gantt.destroy();
    });

    QUnit.test('pill is updated after failed resized', async function (assert) {
        assert.expect(3);

        var nbRead = 0;
        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            domain: [['id', '=', 7]],
            mockRPC: function (route, args) {
                if (args.method === 'write') {
                    assert.strictEqual(true, true, "should perform a write");
                    return Promise.reject();
                }
                if (route === '/web/dataset/search_read') {
                    nbRead++;
                }
                return this._super.apply(this, arguments);
            },
        });

        var pillWidth = gantt.$('.o_gantt_pill').width();
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_pill'), 'mouseenter');

        // resize to one cell larger (1 day)
        var cellWidth = gantt.$('.o_gantt_cell:first').width();
        await testUtils.dom.dragAndDrop(
            gantt.$('.ui-resizable-e'),
            gantt.$('.ui-resizable-e'),
            { position: { left: cellWidth, top: 0 } }
        );

        assert.strictEqual(nbRead, 2);

        assert.strictEqual(pillWidth, gantt.$('.o_gantt_pill').width(),
            "the pill should have the same width as before the resize");

        gantt.destroy();
    });

    QUnit.test('move a pill in the same row', async function (assert) {
        assert.expect(5);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            domain: [['id', '=', 7]],
            mockRPC: function (route, args) {
                if (args.method === 'write') {
                    assert.deepEqual(args.args[0], [7],
                        "should write on the correct record");
                    assert.deepEqual(args.args[1], {
                        start: "2018-12-21 06:30:12",
                        stop: "2018-12-21 18:29:59",
                    }, "both start and stop date should be correctly set (+1 day)");
                }
                return this._super.apply(this, arguments);
            },
        });
        assert.containsOnce(gantt, '.o_gantt_pill',
            "there should be one pill (Task 1)");
        assert.doesNotHaveClass(gantt.$('.o_gantt_pill'), 'ui-draggable',
            "the pill should not be draggable after initial rendering");

        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_pill'), 'mouseenter');

        assert.hasClass(gantt.$('.o_gantt_pill'), 'ui-draggable',
            "the pill should be draggable after mouse enter");

        // move a pill in the next cell (+1 day)
        var cellWidth = gantt.$('.o_gantt_header_scale .o_gantt_header_cell:first')[0].getBoundingClientRect().width;
        await testUtils.dom.dragAndDrop(
            gantt.$('.o_gantt_pill'),
            gantt.$('.o_gantt_pill'),
            { position: { left: cellWidth, top: 0 } },
        );

        gantt.destroy();
    });

    QUnit.test('move a pill in the same row (with timezone)', async function (assert) {
        assert.expect(2);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            domain: [['id', '=', 7]],
            mockRPC: function (route, args) {
                if (args.method === 'write') {
                    assert.deepEqual(args.args[0], [7],
                        "should write on the correct record");
                    assert.deepEqual(args.args[1], {
                        start: "2018-12-21 06:30:12",
                        stop: "2018-12-21 18:29:59",
                    }, "both start and stop date should be correctly set (+1 day)");
                }
                return this._super.apply(this, arguments);
            },
            session: {
                getTZOffset: function () {
                    return 60;
                },
            },
        });

        // move a pill in the next cell (+1 day)
        var cellWidth = gantt.$('.o_gantt_header_scale .o_gantt_header_cell:first')[0].getBoundingClientRect().width;
        await testUtils.dom.dragAndDrop(
            gantt.$('.o_gantt_pill'),
            gantt.$('.o_gantt_pill'),
            { position: { left: cellWidth, top: 0 } },
        );

        gantt.destroy();
    });

    QUnit.test('move a pill in another row', async function (assert) {
        assert.expect(4);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            groupBy: ['project_id'],
            viewOptions: {
                initialDate: initialDate,
            },
            mockRPC: function (route, args) {
                if (args.method === 'write') {
                    assert.deepEqual(args.args[0], [7],
                        "should write on the correct record");
                    assert.deepEqual(args.args[1], {
                        project_id: 1,
                        start: "2018-12-21 06:30:12",
                        stop: "2018-12-21 18:29:59",
                    }, "all modified fields should be correctly set");
                }
                return this._super.apply(this, arguments);
            },
            domain: [['id', 'in', [1, 7]]],
        });

        assert.containsN(gantt, '.o_gantt_pill', 2,
            "there should be two pills (task 1 and task 7)");
        assert.containsN(gantt, '.o_gantt_row', 2,
            "there should be two rows (project 1 and project 2");

        // move a pill (task 7) in the other row and in the the next cell (+1 day)
        var cellWidth = gantt.$('.o_gantt_header_scale .o_gantt_header_cell:first')[0].getBoundingClientRect().width;
        var cellHeight = gantt.$('.o_gantt_cell:first').height();
        await testUtils.dom.dragAndDrop(
            gantt.$('.o_gantt_pill[data-id=7]'),
            gantt.$('.o_gantt_pill[data-id=7]'),
            { position: { left: cellWidth, top: -cellHeight } },
        );

        gantt.destroy();
    });

    QUnit.test('copy a pill in another row', async function (assert) {
            assert.expect(4);
    
            var gantt = await createView({
                View: GanttView,
                model: 'tasks',
                data: this.data,
                arch: '<gantt date_start="start" date_stop="stop" />',
                groupBy: ['project_id'],
                viewOptions: {
                    initialDate: initialDate,
                },
                mockRPC: function (route, args) {
                    if (args.method === 'copy') {
                        assert.deepEqual(args.args[0], 7,
                            "should copy the correct record");
                        assert.deepEqual(args.args[1],  {
                            start: "2018-12-21 06:30:12",
                            stop: "2018-12-21 18:29:59",
                            project_id: 1
                        },
                        "should use the correct default values when copying");
                    }
                    return this._super.apply(this, arguments);
                },
                domain: [['id', 'in', [1, 7]]],
            });
    
            assert.containsN(gantt, '.o_gantt_pill', 2,
                "there should be two pills (task 1 and task 7)");
            assert.containsN(gantt, '.o_gantt_row', 2,
                "there should be two rows (project 1 and project 2");
    
            // move a pill (task 7) in the other row and in the the next cell (+1 day)
            var cellWidth = gantt.$('.o_gantt_header_scale .o_gantt_header_cell:first')[0].getBoundingClientRect().width;
            var cellHeight = gantt.$('.o_gantt_cell:first').height() / 2;
            await testUtils.dom.triggerEvent(gantt.$el, 'keydown',{ctrlKey: true});

            await testUtils.dom.dragAndDrop(
                gantt.$('.o_gantt_pill[data-id=7]'),
                gantt.$('.o_gantt_pill[data-id=7]'),
                { position: { left: cellWidth, top: -cellHeight }, ctrlKey: true },
            );

            gantt.destroy();
        });

    QUnit.test('move a pill in another row in multi-level grouped', async function (assert) {
        assert.expect(3);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            groupBy: ['user_id', 'project_id', 'stage'],
            viewOptions: {
                initialDate: initialDate,
            },
            mockRPC: function (route, args) {
                if (args.method === 'write') {
                    assert.deepEqual(args.args[0], [7],
                        "should write on the correct record");
                    assert.deepEqual(args.args[1], {
                        user_id: 2,
                    }, "we should only write on user_id");
                }
                return this._super.apply(this, arguments);
            },
            domain: [['id', 'in', [3, 7]]],
        });

        gantt.$('.o_gantt_pill').each(function () {
            testUtils.dom.triggerMouseEvent($(this), 'mouseenter');
        });
        await testUtils.nextTick();

        assert.containsN(gantt, '.o_gantt_pill.ui-draggable:not(.o_fake_draggable)', 1,
            "there should be only one draggable pill (Task 7)");

        // move a pill (task 7) in the top-level group (User 2)
        var $pill = gantt.$('.o_gantt_pill.ui-draggable:not(.o_fake_draggable)');
        var groupHeaderHeight = gantt.$('.o_gantt_cell:first').height();
        var cellHeight = $pill.closest('.o_gantt_cell').height();
        await testUtils.dom.dragAndDrop(
            $pill,
            $pill,
            { position: { left: 0, top: -3 * groupHeaderHeight - cellHeight } },
        );

        gantt.destroy();
    });

    QUnit.test('grey pills should not be resizable nor draggable', async function (assert) {
        assert.expect(4);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" color="color" />',
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['user_id', 'project_id'],
            domain: [['id', '=', 7]],
        });


        gantt.$('.o_gantt_pill').each(function () {
            testUtils.dom.triggerMouseEvent($(this), 'mouseenter');
        });
        await testUtils.nextTick();

        assert.doesNotHaveClass(gantt.$('.o_gantt_row_group .o_gantt_pill'), 'ui-resizable',
            'the group row pill should not be resizable');
        assert.hasClass(gantt.$('.o_gantt_row_group .o_gantt_pill'), 'o_fake_draggable',
            'the group row pill should not be draggable');
        assert.hasClass(gantt.$('.o_gantt_row:not(.o_gantt_row_group) .o_gantt_pill'), 'ui-resizable',
            'the pill should be resizable');
        assert.hasClass(gantt.$('.o_gantt_row:not(.o_gantt_row_group) .o_gantt_pill'), 'ui-draggable',
            'the pill should be draggable');

        gantt.destroy();
    });

    QUnit.test('gantt_unavailability reloads when the view\'s scale changes', async function(assert){
        assert.expect(11);

        var unavailabilityCallCount = 0;
        var unavailabilityScaleArg = 'none';
        var reloadCount = 0;

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" display_unavailability="1" />',
            viewOptions: {
                initialDate: initialDate,
            },
            mockRPC: function (route, args) {
                var result;
                if (route === '/web/dataset/search_read') {
                    reloadCount++;
                    result = this._super.apply(this, arguments);
                }
                else if (args.method === 'gantt_unavailability') {
                    unavailabilityCallCount++;
                    unavailabilityScaleArg = args.args[2];
                    result = args.args[4];
                }
                return Promise.resolve(result);
            },
        });

        assert.strictEqual(reloadCount, 1, 'view should have loaded')
        assert.strictEqual(unavailabilityCallCount, 1, 'view should have loaded unavailability');

        await testUtils.dom.click(gantt.$('.o_gantt_button_scale[data-value=week]'));
        assert.strictEqual(reloadCount, 2, 'view should have reloaded when switching scale to week')
        assert.strictEqual(unavailabilityCallCount, 2, 'view should have reloaded when switching scale to week');
        assert.strictEqual(unavailabilityScaleArg, 'week', 'unavailability should have been called with the week scale');

        await testUtils.dom.click(gantt.$('.o_gantt_button_scale[data-value=month]'));
        assert.strictEqual(reloadCount, 3, 'view should have reloaded when switching scale to month')
        assert.strictEqual(unavailabilityCallCount, 3, 'view should have reloaded when switching scale to month');
        assert.strictEqual(unavailabilityScaleArg, 'month', 'unavailability should have been called with the month scale');

        await testUtils.dom.click(gantt.$('.o_gantt_button_scale[data-value=year]'));
        assert.strictEqual(reloadCount, 4, 'view should have reloaded when switching scale to year')
        assert.strictEqual(unavailabilityCallCount, 4, 'view should have reloaded when switching scale to year');
        assert.strictEqual(unavailabilityScaleArg, 'year', 'unavailability should have been called with the year scale');

        gantt.destroy();

    });

    QUnit.test('gantt_unavailability reload when period changes', async function(assert){
        assert.expect(6);

        var unavailabilityCallCount = 0;
        var reloadCount = 0;

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" display_unavailability="1" />',
            viewOptions: {
                initialDate: initialDate,
            },
            mockRPC: function (route, args) {
                var result;
                if (route === '/web/dataset/search_read') {
                    reloadCount++;
                    result = this._super.apply(this, arguments);
                }
                else if (args.method === 'gantt_unavailability') {
                    unavailabilityCallCount++;
                    result = args.args[4];
                }
                return Promise.resolve(result);
            },
        });

        assert.strictEqual(reloadCount, 1, 'view should have loaded')
        assert.strictEqual(unavailabilityCallCount, 1, 'view should have loaded unavailability');

        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_next'));
        assert.strictEqual(reloadCount, 2, 'view should have reloaded when clicking next')
        assert.strictEqual(unavailabilityCallCount, 2, 'view should have reloaded unavailability when clicking next');

        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_prev'));
        assert.strictEqual(reloadCount, 3, 'view should have reloaded when clicking prev')
        assert.strictEqual(unavailabilityCallCount, 3, 'view should have reloaded unavailability when clicking prev');

        gantt.destroy();

    });

    QUnit.test('gantt_unavailability should not reload when period changes if display_unavailability is not set', async function(assert){
        assert.expect(6);

        var unavailabilityCallCount = 0;
        var reloadCount = 0;

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            mockRPC: function (route, args) {
                var result;
                if (route === '/web/dataset/search_read') {
                    reloadCount++;
                    result = this._super.apply(this, arguments);
                }
                else if (args.method === 'gantt_unavailability') {
                    unavailabilityCallCount++;
                    result = {};
                }
                return Promise.resolve(result);
            },
        });

        assert.strictEqual(reloadCount, 1, 'view should have loaded')
        assert.strictEqual(unavailabilityCallCount, 0, 'view should not have loaded unavailability');

        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_next'));
        assert.strictEqual(reloadCount, 2, 'view should have reloaded when clicking next')
        assert.strictEqual(unavailabilityCallCount, 0, 'view should not have reloaded unavailability when clicking next');

        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_prev'));
        assert.strictEqual(reloadCount, 3, 'view should have reloaded when clicking prev')
        assert.strictEqual(unavailabilityCallCount, 0, 'view should not have reloaded unavailability when clicking prev');

        gantt.destroy();

    });

    QUnit.test('cancelled drag and tooltip', async function (assert) {
        assert.expect(6);

        var POPOVER_DELAY = GanttRow.prototype.POPOVER_DELAY;
        GanttRow.prototype.POPOVER_DELAY = 0;

        this.data.tasks.records[1].start = '2018-12-16 03:00:00';

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt default_scale="week" date_start="start" date_stop="stop" />',
            archs: {
                'tasks,false,form': '<form/>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
            mockRPC: function (route, args) {
                if (args.method === 'write') {
                    throw new Error('Should not do a write RPC');
                }
                return this._super.apply(this, arguments);
            },
        });

        assert.containsN(gantt, '.o_gantt_pill', 4);
        const $secondPill = gantt.$('.o_gantt_pill:nth(1)');

        // enable the drag feature
        await testUtils.dom.triggerMouseEvent($secondPill, 'mouseenter');
        assert.hasClass($secondPill, 'ui-draggable', "the pill should be draggable after mouse enter");
        assert.containsOnce(document.body, 'div.popover');

        // move the pill of a few px (not enough for it to actually move to another cell)
        await testUtils.dom.dragAndDrop($secondPill, $secondPill, {
            position: { left: 0, top: 4 },
            withTrailingClick: true,
        });

        // check popover
        await testUtils.dom.triggerEvents($secondPill, ['mouseenter']);
        assert.containsOnce(document.body, 'div.popover');

        // edit pill
        await testUtils.dom.triggerEvents($secondPill, ['click']);
        assert.containsOnce(document.body, '.modal .o_form_view');

        gantt.destroy();
        assert.containsNone(gantt, 'div.popover', 'should not have a popover anymore');
        GanttRow.prototype.POPOVER_DELAY = POPOVER_DELAY;
    });

    // ATTRIBUTES TESTS

    QUnit.test('create attribute', async function (assert) {
        assert.expect(2);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" create="false" />',
            viewOptions: {
                initialDate: initialDate,
            },
        });

        // the "Add" should not appear
        assert.containsNone(gantt.$buttons.find('.o_gantt_button_add'),
        "there should be no 'Add' button");

        await testUtils.dom.click(gantt.$('.o_gantt_cell:first'));

        assert.strictEqual($('.modal').length, 0,
            "there should be no opened modal");

        gantt.destroy();
    });

    QUnit.test('edit attribute', async function (assert) {
        assert.expect(4);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" edit="false" />',
            viewOptions: {
                initialDate: initialDate,
            },
            archs: {
                'tasks,false,form': '<form>' +
                        '<field name="name"/>' +
                    '</form>',
            },
        });

        assert.containsNone(gantt, '.o_gantt_pill.ui-resizable',
            "the pills should not be resizable");

        assert.containsNone(gantt, '.o_gantt_pill.ui-draggable',
            "the pills should not be draggable");

        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_pill:first'), 'click');
        await testUtils.nextTick();

        assert.strictEqual($('.modal').length, 1,
            "there should be a opened modal");
        assert.strictEqual($('.modal .o_form_view.o_form_readonly').length, 1,
            "the form view should be in readonly");

        gantt.destroy();
    });

    QUnit.test('total_row attribute', async function (assert) {
        assert.expect(6);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" total_row="1" />',
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.containsOnce(gantt, '.o_gantt_row_container .o_gantt_row',
            'should have 1 row');
        assert.containsOnce(gantt, '.o_gantt_total_row_container .o_gantt_row_total',
            'should have 1 total row');
        assert.containsNone(gantt, '.o_gantt_row_container .o_gantt_row_sidebar',
            'container should not have a sidebar');
        assert.containsNone(gantt, '.o_gantt_total_row_container .o_gantt_row_sidebar',
            'total container should not have a sidebar');
        assert.containsN(gantt, '.o_gantt_row_total .o_gantt_pill ', 7,
            'should have a 7 pills in the total row');
        assert.strictEqual(gantt.$('.o_gantt_row_total .o_gantt_consolidated_pill_title').text().replace(/\s+/g, ''), "2123212",
            "the total row should be correctly computed");

        gantt.destroy();
    });

    QUnit.test('default_scale attribute', async function (assert) {
        assert.expect(3);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" default_scale="day" />',
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.hasClass(gantt.$buttons.find('.o_gantt_button_scale[data-value=day]'), 'active',
            'day view should be activated');
        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), '20 December 2018',
            'should contain "20 December 2018" in header');
        assert.containsN(gantt, '.o_gantt_header_container .o_gantt_header_scale .o_gantt_header_cell', 24,
            'should have a 24 slots for day view');

        gantt.destroy();
    });

    QUnit.test('scales attribute', async function (assert) {
        assert.expect(3);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" scales="month,day,trololo" />',
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.containsN(gantt.$buttons, '.o_gantt_button_scale', 2,
            'only 2 scales should be available');
        assert.strictEqual(gantt.$buttons.find('.o_gantt_button_scale').first().text().trim(), 'Month',
            'Month scale should be the first option');
        assert.strictEqual(gantt.$buttons.find('.o_gantt_button_scale').last().text().trim(), 'Day',
            'Day scale should be the second option');

        gantt.destroy();
    });

    QUnit.test('precision attribute', async function (assert) {
        assert.expect(3);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" precision=\'{"day": "hour:quarter", "week": "day:half", "month": "day", "year": "month:quarter"}\' default_scale="day" />',
            viewOptions: {
                initialDate: initialDate,
            },
            domain: [['id', '=', 7]],
            mockRPC: function (route, args) {
                if (args.method === 'write') {
                    assert.deepEqual(args.args[1], { stop: "2018-12-20 18:44:59" });
                }
                return this._super.apply(this, arguments);
            },
        });

        var cellWidth = gantt.$('.o_gantt_cell:first').width();
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_pill'), 'mouseenter');

        // resize of a quarter
        await testUtils.dom.dragAndDrop(
            gantt.$('.ui-resizable-e'),
            gantt.$('.ui-resizable-e'),
            { disableDrop: true, position: { left: cellWidth / 4, top: 0 } }
        );

        assert.strictEqual(gantt.$('.o_gantt_pill_resize_badge').text().trim(), "+15 minutes",
            "the resize should be by 15min step");

        // manually trigger the drop to trigger a write
        var toOffset = gantt.$('.ui-resizable-e').offset();
        await gantt.$('.ui-resizable-e').trigger($.Event("mouseup", {
            which: 1,
            pageX: toOffset.left + cellWidth / 4,
            pageY: toOffset.top
        }));
        await testUtils.nextTick();

        assert.containsNone(gantt, '.o_gantt_pill_resize_badge',
            "the badge should disappear after drop");

        gantt.destroy();
    });

    QUnit.test('progress attribute', async function (assert) {
        assert.expect(7);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt string="Tasks" date_start="start" date_stop="stop" progress="progress" />',
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['project_id'],
        });

        assert.containsN(gantt, '.o_gantt_row_container .o_gantt_pill.o_gantt_progress', 6,
            'should have 6 rows with o_gantt_progress class');

        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_pill.o_gantt_progress:contains("Task 1")').css('background-size'), '0% 100%',
            'first pill should have 0% progress');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_pill.o_gantt_progress:contains("Task 2")').css('background-size'), '30% 100%',
            'second pill should have 30% progress');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_pill.o_gantt_progress:contains("Task 3")').css('background-size'), '60% 100%',
            'third pill should have 60% progress');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_pill.o_gantt_progress:contains("Task 4")').css('background-size'), '0% 100%',
            'fourth pill should have 0% progress');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_pill.o_gantt_progress:contains("Task 5")').css('background-size'), '100% 100%',
            'fifth pill should have 100% progress');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_pill.o_gantt_progress:contains("Task 7")').css('background-size'), '80% 100%',
            'seventh task should have 80% progress');

        gantt.destroy();
    });


    QUnit.test('form_view_id attribute', async function (assert) {
        assert.expect(1);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt string="Tasks" date_start="start" date_stop="stop" form_view_id="42"/>',
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['project_id'],
        });

        testUtils.mock.intercept(gantt, 'load_views', function (event) {
            assert.strictEqual(event.data.views[0][0], 42, "should do a do_action with view id 42");
        });

        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_add'));
        await testUtils.nextTick();

        gantt.destroy();
    });


    QUnit.test('decoration attribute', async function (assert) {
        assert.expect(2);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" decoration-info="stage == \'todo\'">' +
                    '<field name="stage"/>' +
                '</gantt>',
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.hasClass(gantt.$('.o_gantt_pill[data-id=1]'), 'decoration-info',
            'should have a "decoration-info" class on task 1');
        assert.doesNotHaveClass(gantt.$('.o_gantt_pill[data-id=2]'), 'decoration-info',
            'should not have a "decoration-info" class on task 2');

        gantt.destroy();
    });

    QUnit.test('decoration attribute with date', async function (assert) {
        assert.expect(6);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" decoration-danger="start &lt; \'2018-12-19 00:00:00\'">' +
                '</gantt>',
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.hasClass(gantt.$('.o_gantt_pill[data-id=1]'), 'decoration-danger',
            'should have a "decoration-danger" class on task 1');
        assert.hasClass(gantt.$('.o_gantt_pill[data-id=2]'), 'decoration-danger',
            'should have a "decoration-danger" class on task 2');
        assert.hasClass(gantt.$('.o_gantt_pill[data-id=5]'), 'decoration-danger',
            'should have a "decoration-danger" class on task 5');
        assert.doesNotHaveClass(gantt.$('.o_gantt_pill[data-id=3]'), 'decoration-danger',
            'should not have a "decoration-danger" class on task 3');
        assert.doesNotHaveClass(gantt.$('.o_gantt_pill[data-id=4]'), 'decoration-danger',
            'should not have a "decoration-danger" class on task 4');
        assert.doesNotHaveClass(gantt.$('.o_gantt_pill[data-id=7]'), 'decoration-danger',
            'should not have a "decoration-danger" class on task 7');

        gantt.destroy();
    });

    QUnit.test('consolidation feature', async function (assert) {
        assert.expect(25);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt string="Tasks" date_start="start" date_stop="stop" consolidation="progress" consolidation_max=\'{"user_id": 100}\' consolidation_exclude="exclude" progress="progress"/>',
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['user_id', 'project_id', 'stage'],
        });

        assert.containsN(gantt, '.o_gantt_row_container .o_gantt_row', 18,
            'should have a 18 rows');
        assert.containsN(gantt, '.o_gantt_row_container .o_gantt_row_group.open', 12,
            'should have a 12 opened groups as consolidation implies collapse_first_level');
        assert.containsN(gantt, '.o_gantt_row_container .o_gantt_row:not(.o_gantt_row_group)', 6,
            'should have a 6 rows');
        assert.containsOnce(gantt, '.o_gantt_row_container .o_gantt_row:first .o_gantt_row_sidebar',
            'should have a sidebar');

        // Check grouped rows
        assert.hasClass(gantt.$('.o_gantt_row_container .o_gantt_row:first'), 'o_gantt_row_group',
            '1st row should be a group');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_row:first .o_gantt_row_title').text().trim(), 'User 1',
            '1st row title should be "User 1"');

        assert.hasClass(gantt.$('.o_gantt_row_container .o_gantt_row:nth(9)'), 'o_gantt_row_group',
            '7th row should be a group');
        assert.strictEqual(gantt.$('.o_gantt_row_container .o_gantt_row:nth(9) .o_gantt_row_title').text().trim(), 'User 2',
            '7th row title should be "User 2"');

        // Consolidation
        // 0 over the size of Task 5 (Task 5 is 100 but is excluded !) then 0 over the rest of Task 1, cut by Task 4 which has progress 0
        assert.strictEqual(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_consolidated_pill_title ').text().replace(/\s+/g, ''), "0000",
            "the consolidation should be correctly computed");

        assert.strictEqual(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_pill:eq(0)').css('background-color'), "rgb(0, 160, 74)",
            "the 1st group pill should have the correct color)");
        assert.strictEqual(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_pill:eq(1)').css('background-color'), "rgb(0, 160, 74)",
            "the 2nd group pill should have the correct color)");
        assert.strictEqual(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_pill:eq(2)').css('background-color'), "rgb(0, 160, 74)",
            "the 3rd group pill should have the correct color");

        assert.strictEqual(getPillItemWidth(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_pill_wrapper:eq(0)')), "calc(300% + 2px)",
            "the 1st group pill should have the correct width (1 to 3 dec)");
        assert.strictEqual(getPillItemWidth(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_pill_wrapper:eq(1)')), "calc(1600% + 15px)",
            "the 2nd group pill should have the correct width (4 to 19 dec)");
        assert.strictEqual(getPillItemWidth(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_pill_wrapper:eq(2)')), "50%",
            "the 3rd group pill should have the correct width (20 morning dec");
        assert.strictEqual(getPillItemWidth(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_pill_wrapper:eq(3)')), "calc(1150% + 10px)",
            "the 4th group pill should have the correct width (20 afternoon to 31 dec");

        // 30 over Task 2 until Task 7 then 110 (Task 2 (30) + Task 7 (80)) then 30 again until end of task 2 then 60 over Task 3
        assert.strictEqual(gantt.$('.o_gantt_row_group:eq(6) .o_gantt_consolidated_pill_title').text().replace(/\s+/g, ''), "301103060",
            "the consolidation should be correctly computed");

        assert.strictEqual(gantt.$('.o_gantt_row_group:eq(6) .o_gantt_pill:eq(0)').css('background-color'), "rgb(0, 160, 74)",
            "the 1st group pill should have the correct color)");
        assert.strictEqual(gantt.$('.o_gantt_row_group:eq(6) .o_gantt_pill:eq(1)').css('background-color'), "rgb(220, 105, 101)",
            "the 2nd group pill should have the correct color)");
        assert.strictEqual(gantt.$('.o_gantt_row_group:eq(6) .o_gantt_pill:eq(2)').css('background-color'), "rgb(0, 160, 74)",
            "the 3rd group pill should have the correct color");
        assert.strictEqual(gantt.$('.o_gantt_row_group:eq(6) .o_gantt_pill:eq(3)').css('background-color'), "rgb(0, 160, 74)",
            "the 4th group pill should have the correct color");

        assert.strictEqual(getPillItemWidth(gantt.$('.o_gantt_row_group:eq(6) .o_gantt_pill_wrapper:eq(0)')), "calc(300% + 2px)",
            "the 1st group pill should have the correct width (17 afternoon to 20 dec morning)");
        assert.strictEqual(getPillItemWidth(gantt.$('.o_gantt_row_group:eq(6) .o_gantt_pill_wrapper:eq(1)')), "50%",
            "the 2nd group pill should have the correct width (20 dec afternoon)");
        assert.strictEqual(getPillItemWidth(gantt.$('.o_gantt_row_group:eq(6) .o_gantt_pill_wrapper:eq(2)')), "150%",
            "the 3rd group pill should have the correct width (21 to 22 dec morning dec");
        assert.strictEqual(getPillItemWidth(gantt.$('.o_gantt_row_group:eq(6) .o_gantt_pill_wrapper:eq(3)')), "calc(450% + 3px)",
            "the 4th group pill should have the correct width (27 afternoon to 31 dec");

        gantt.destroy();
    });

    QUnit.test('color attribute', async function (assert) {
        assert.expect(2);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" color="color" />',
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.hasClass(gantt.$('.o_gantt_pill[data-id=1]'), 'o_gantt_color_0',
            'should have a color_0 class on task 1');
        assert.hasClass(gantt.$('.o_gantt_pill[data-id=2]'), 'o_gantt_color_2',
            'should have a color_0 class on task 2');

        gantt.destroy();
    });

    QUnit.test('color attribute in multi-level grouped', async function (assert) {
        assert.expect(2);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" color="color" />',
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['user_id', 'project_id'],
            domain: [['id', '=', 1]],
        });

        assert.doesNotHaveClass(gantt.$('.o_gantt_row_group .o_gantt_pill'), 'o_gantt_color_0',
            "the group row pill should not be colored");
        assert.hasClass(gantt.$('.o_gantt_row:not(.o_gantt_row_group) .o_gantt_pill'), 'o_gantt_color_0',
            'the pill should be colored');

        gantt.destroy();
    });

    QUnit.test('color attribute on a many2one', async function (assert) {
        assert.expect(3);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" color="project_id" />',
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.hasClass(gantt.$('.o_gantt_pill[data-id=1]'), 'o_gantt_color_1',
            'should have a color_1 class on task 1');
        assert.containsN(gantt, '.o_gantt_pill.o_gantt_color_1', 4,
            "there should be 4 pills with color 1");
        assert.containsN(gantt, '.o_gantt_pill.o_gantt_color_2', 2,
            "there should be 2 pills with color 2");

        gantt.destroy();
    });

    QUnit.test('display_unavailability attribute', async function (assert) {
        assert.expect(16);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" display_unavailability="1" />',
            viewOptions: {
                initialDate: initialDate,
            },
            mockRPC: function (route, args) {
                if (args.method === 'gantt_unavailability') {
                    assert.strictEqual(args.model, 'tasks',
                        "the availability should be fetched on the correct model");
                    assert.strictEqual(args.args[0], '2018-12-01 00:00:00',
                        "the start_date argument should be in the server format");
                    assert.strictEqual(args.args[1], '2018-12-31 23:59:59',
                        "the end_date argument should be in the server format");
                    var rows = args.args[4];
                    rows.forEach(function(r) {
                        r.unavailabilities = [{
                            start: '2018-12-05 11:30:00',
                            stop: '2018-12-08 08:00:00'
                        }, {
                            start: '2018-12-16 09:00:00',
                            stop: '2018-12-18 13:00:00'
                        }]
                    });
                    return Promise.resolve(rows);
                }
                return this._super.apply(this, arguments);
            },
        });

        var cell5 = gantt.$('.o_gantt_row_container .o_gantt_cell[data-date="2018-12-05 00:00:00"]');
        assert.hasClass(cell5, 'o_gantt_unavailability', "the 5th cell should have unavailabilities");
        assert.hasClass(cell5, 'o_gantt_unavailable_second_half', "the 5th cell should be gray in the afternoon");

        var cell6 = gantt.$('.o_gantt_row_container .o_gantt_cell[data-date="2018-12-06 00:00:00"]');
        assert.hasClass(cell6, 'o_gantt_unavailability', "the 6th cell should have unavailabilities");
        assert.hasClass(cell6, 'o_gantt_unavailable_full', "the 6th cell should be fully grayed-out");

        var cell7 = gantt.$('.o_gantt_row_container .o_gantt_cell[data-date="2018-12-07 00:00:00"]');
        assert.hasClass(cell7, 'o_gantt_unavailability', "the 7th cell should have unavailabilities");
        assert.hasClass(cell7, 'o_gantt_unavailable_full', "the 7th cell should be fully grayed-out");

        var cell16 = gantt.$('.o_gantt_row_container .o_gantt_cell[data-date="2018-12-16 00:00:00"]');
        assert.hasClass(cell16, 'o_gantt_unavailability', "the 16th cell should have unavailabilities");
        assert.hasClass(cell16, 'o_gantt_unavailable_second_half', "the 16th cell should be gray in the afternoon");

        var cell17 = gantt.$('.o_gantt_row_container .o_gantt_cell[data-date="2018-12-17 00:00:00"]');
        assert.hasClass(cell17, 'o_gantt_unavailability', "the 18th cell should have unavailabilities");
        assert.hasClass(cell17, 'o_gantt_unavailable_full', "the 18th cell should be fully grayed-out");

        var cell18 = gantt.$('.o_gantt_row_container .o_gantt_cell[data-date="2018-12-18 00:00:00"]');
        assert.hasClass(cell18, 'o_gantt_unavailability', "the 18th cell should have unavailabilities");
        assert.hasClass(cell18, 'o_gantt_unavailable_first_half', "the 18th cell should be gray in the morning");

        assert.containsN(gantt, '.o_gantt_cell.o_gantt_unavailability', 6, "6 cells have unavailabilities data");

        gantt.destroy();
    });

    QUnit.test('offset attribute', async function (assert) {
        assert.expect(1);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" offset="-4" default_scale="day"/>',
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), '16 December 2018',
            'gantt view should be set to 4 days before initial date');

        gantt.destroy();
    });

    QUnit.test('default_group_by attribute', async function (assert) {
        assert.expect(2);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" default_group_by="user_id" />',
            viewOptions: {
                initialDate: initialDate,
            },
        });

        assert.containsN(gantt, '.o_gantt_row', 2,
            "there should be 2 rows");
        assert.strictEqual(gantt.$('.o_gantt_row:last .o_gantt_row_title').text().trim(), 'User 2',
            'should be grouped by user');

        gantt.destroy();
    });

    QUnit.test('collapse_first_level attribute with single-level grouped', async function (assert) {
        assert.expect(13);

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt string="Tasks" date_start="start" date_stop="stop" collapse_first_level="1" />',
            archs: {
                'tasks,false,form': '<form>' +
                    '<field name="name"/>' +
                    '<field name="start"/>' +
                    '<field name="stop"/>' +
                    '<field name="project_id"/>' +
                    '</form>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['project_id'],
        });

        assert.containsOnce(gantt, '.o_gantt_header_container',
            'should have a header');
        assert.ok(gantt.$buttons.find('.o_gantt_button_expand_rows').is(':visible'),
            "the expand button should be visible");
        assert.containsN(gantt, '.o_gantt_row_container .o_gantt_row', 4,
            'should have a 4 rows');
        assert.containsN(gantt, '.o_gantt_row_container .o_gantt_row.o_gantt_row_group', 2,
            'should have 2 group rows');
        assert.strictEqual(gantt.$('.o_gantt_row_group:eq(0) .o_gantt_row_title').text().trim(), 'Project 1',
            'should contain "Project 1" in sidebar title');
        assert.containsN(gantt, '.o_gantt_row:eq(1) .o_gantt_pill', 4,
            'should have a 4 pills in first row');
        assert.strictEqual(gantt.$('.o_gantt_row_group:eq(1) .o_gantt_row_title').text().trim(), 'Project 2',
            'should contain "Project 2" in sidebar title');
        assert.containsN(gantt, '.o_gantt_row:eq(3) .o_gantt_pill', 2,
            'should have a 2 pills in second row');


        // open dialog to create a task
        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_row:nth(3) .o_gantt_cell[data-date="2018-12-10 00:00:00"] .o_gantt_cell_add'), "click");
        await testUtils.nextTick();

        assert.strictEqual($('.modal').length, 1, 'There should be one modal opened');
        assert.strictEqual($('.modal .modal-title').text(), "Create");
        assert.strictEqual($('.modal .o_field_widget[name=project_id] .o_input').val(), 'Project 2',
            'project_id should be set');
        assert.strictEqual($('.modal .o_field_widget[name=start] .o_input').val(), '12/10/2018 00:00:00',
            'start should be set');
        assert.strictEqual($('.modal .o_field_widget[name = stop] .o_input').val(), '12/10/2018 23:59:59',
            'stop should be set');

        gantt.destroy();
    });

    // CONCURRENCY TESTS
    QUnit.test('concurrent scale switches return in inverse order', async function (assert) {
        assert.expect(11);

        testUtils.patch(GanttRenderer, {
            _render: function () {
                assert.step('render');
                return this._super.apply(this, arguments);
            },
        });

        var firstReloadProm = null;
        var reloadProm = firstReloadProm;
        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            mockRPC: function (route) {
                var result = this._super.apply(this, arguments);
                if (route === '/web/dataset/search_read') {
                    return Promise.resolve(reloadProm).then(_.constant(result));
                }
                return result;
            },
        });

        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), 'December 2018',
            "should be in 'month' scale");
        assert.strictEqual(gantt.model.get().records.length, 6,
            "should have 6 records in the state");

        // switch to 'week' scale (this rpc will be delayed)
        firstReloadProm = testUtils.makeTestPromise();
        reloadProm = firstReloadProm;
        await testUtils.dom.click(gantt.$('.o_gantt_button_scale[data-value=week]'));

        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), 'December 2018',
            "should still be in 'month' scale");
        assert.strictEqual(gantt.model.get().records.length, 6,
            "should still have 6 records in the state");

        // switch to 'year' scale
        reloadProm = null;
        await testUtils.dom.click(gantt.$('.o_gantt_button_scale[data-value=year]'));

        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), '2018',
            "should be in 'year' scale");
        assert.strictEqual(gantt.model.get().records.length, 7,
            "should have 7 records in the state");

        firstReloadProm.resolve();

        assert.strictEqual(gantt.$('.o_gantt_header_container > .col > .row:first-child').text().trim(), '2018',
            "should still be in 'year' scale");
        assert.strictEqual(gantt.model.get().records.length, 7,
            "should still have 7 records in the state");

        assert.verifySteps(['render', 'render']); // should only re-render once

        gantt.destroy();
        testUtils.unpatch(GanttRenderer);
    });

    QUnit.test('concurrent pill resizes return in inverse order', async function (assert) {
        assert.expect(7);

        testUtils.patch(GanttRenderer, {
            _render: function () {
                assert.step('render');
                return this._super.apply(this, arguments);
            },
        });

        var writeProm = testUtils.makeTestPromise();
        var firstWriteProm = writeProm;
        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            domain: [['id', '=', 2]],
            mockRPC: function (route, args) {
                var result = this._super.apply(this, arguments);
                assert.step(args.method || route);
                if (args.method === 'write') {
                    return Promise.resolve(writeProm).then(_.constant(result));
                }
                return result;
            },
        });

        var cellWidth = gantt.$('.o_gantt_cell:first').width();

        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_pill'), 'mouseenter');

        // resize to 1 cell smaller (-1 day) ; this RPC will be delayed
        await testUtils.dom.dragAndDrop(
            gantt.$('.ui-resizable-e'),
            gantt.$('.ui-resizable-e'),
            { position: { left: -cellWidth, top: 0 } }
        );

        // resize to two cells larger (+2 days)
        writeProm = null;
        await testUtils.dom.dragAndDrop(
            gantt.$('.ui-resizable-e'),
            gantt.$('.ui-resizable-e'),
            { position: { left: 2 * cellWidth, top: 0 } }
        );

        firstWriteProm.resolve();

        await testUtils.nextTick();

        assert.verifySteps([
            '/web/dataset/search_read',
            'render',
            'write',
            'write',
            '/web/dataset/search_read', // should only reload once
            'render', // should only re-render once
        ]);

        gantt.destroy();
        testUtils.unpatch(GanttRenderer);
    });

    QUnit.test('concurrent pill resizes and open, dialog show updated number', async function (assert) {
        assert.expect(1);

        var def = testUtils.makeTestPromise();
        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            archs: {
                'tasks,false,form': '<form>' +
                        '<field name="name"/>' +
                        '<field name="start"/>' +
                        '<field name="stop"/>' +
                    '</form>',
            },
            viewOptions: {
                initialDate: initialDate,
            },
            domain: [['id', '=', 2]],
            mockRPC: function (route, args) {
                var self = this;
                if (args.method === 'write') {
                    var super_self = this._super
                    return def.then(() => {
                        return super_self.apply(self, arguments);
                    });
                }
                return this._super.apply(this, arguments);;
            },
        });

        var cellWidth = gantt.$('.o_gantt_cell:first').width();

        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_pill'), 'mouseenter');

        await testUtils.dom.dragAndDrop(
            gantt.$('.ui-resizable-e'),
            gantt.$('.ui-resizable-e'),
            { position: { left: 2 * cellWidth, top: 0 } }
        );

        await testUtils.dom.triggerMouseEvent(gantt.$('.o_gantt_pill'), "click");
        def.resolve();
        await testUtils.nextTick();
        assert.strictEqual($('.modal').find('input[name=stop]').val(), '12/24/2018 06:29:59');

        gantt.destroy();
    });

    QUnit.test('dst spring forward', async function (assert) {
        assert.expect(2);

        // This is one of the few tests which have dynamic assertions, see
        // our justification for it in the comment at the top of this file.

        var firstStartDateUTCString = '2019-03-30 03:00:00';
        var firstStartDateUTC = moment.utc(firstStartDateUTCString);
        var firstStartDateLocalString = firstStartDateUTC.local().format('YYYY-MM-DD hh:mm:ss');
        this.data.tasks.records.push({
            id: 99,
            name: 'DST Task 1',
            start: firstStartDateUTCString,
            stop: '2019-03-30 03:30:00',
        });

        var secondStartDateUTCString = '2019-03-31 03:00:00';
        var secondStartDateUTC = moment.utc(secondStartDateUTCString);
        var secondStartDateLocalString = secondStartDateUTC.local().format('YYYY-MM-DD hh:mm:ss');
        this.data.tasks.records.push({
            id: 99,
            name: 'DST Task 2',
            start: secondStartDateUTCString,
            stop: '2019-03-31 03:30:00',
        });

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" default_scale="day"/>',
            viewOptions: {
                initialDate: new Date(2019, 2, 30, 8, 0, 0),
            },
        });

        assert.containsOnce(gantt, '.o_gantt_row_container .o_gantt_cell[data-date="' + firstStartDateLocalString + '"] .o_gantt_pill_wrapper:contains(DST Task 1)',
            'should be in the right cell');

        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_next'));

        assert.containsOnce(gantt, '.o_gantt_row_container .o_gantt_cell[data-date="' + secondStartDateLocalString + '"] .o_gantt_pill_wrapper:contains(DST Task 2)',
            'should be in the right cell');

        gantt.destroy();
    });

    QUnit.test('dst fall back', async function (assert) {
        assert.expect(2);

        // This is one of the few tests which have dynamic assertions, see
        // our justification for it in the comment at the top of this file.

        var firstStartDateUTCString = '2019-10-26 03:00:00';
        var firstStartDateUTC = moment.utc(firstStartDateUTCString);
        var firstStartDateLocalString = firstStartDateUTC.local().format('YYYY-MM-DD hh:mm:ss');
        this.data.tasks.records.push({
            id: 99,
            name: 'DST Task 1',
            start: firstStartDateUTCString,
            stop: '2019-10-26 03:30:00',
        });

        var secondStartDateUTCString = '2019-10-27 03:00:00';
        var secondStartDateUTC = moment.utc(secondStartDateUTCString);
        var secondStartDateLocalString = secondStartDateUTC.local().format('YYYY-MM-DD hh:mm:ss');
        this.data.tasks.records.push({
            id: 99,
            name: 'DST Task 2',
            start: secondStartDateUTCString,
            stop: '2019-10-27 03:30:00',
        });

        var gantt = await createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" default_scale="day"/>',
            viewOptions: {
                initialDate: new Date(2019, 9, 26, 8, 0, 0),
            },
        });

        assert.containsOnce(gantt, '.o_gantt_row_container .o_gantt_cell[data-date="' + firstStartDateLocalString + '"] .o_gantt_pill_wrapper:contains(DST Task 1)',
            'should be in the right cell');

        await testUtils.dom.click(gantt.$buttons.find('.o_gantt_button_next'));

        assert.containsOnce(gantt, '.o_gantt_row_container .o_gantt_cell[data-date="' + secondStartDateLocalString + '"] .o_gantt_pill_wrapper:contains(DST Task 2)',
            'should be in the right cell');

        gantt.destroy();
    });

    // OTHER TESTS

    QUnit.skip('[for manual testing] scripting time of large amount of records (ungrouped)', async function (assert) {
        assert.expect(1);

        this.data.tasks.records = [];
        for (var i = 1; i <= 1000; i++) {
            this.data.tasks.records.push({
                id: i,
                name: 'Task ' + i,
                start: '2018-12-01 00:00:00',
                stop: '2018-12-02 00:00:00',
            });
        }

        createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
        });
    });

    QUnit.skip('[for manual testing] scripting time of large amount of records (one level grouped)', async function (assert) {
        assert.expect(1);

        this.data.tasks.records = [];
        this.data.users.records = [];

        var i;
        for (i = 1; i <= 100; i++) {
            this.data.users.records.push({
                id: i,
                name: i,
            });
        }

        for (i = 1; i <= 10000; i++) {
            var day1 = (i % 30) + 1;
            var day2 = ((i % 30) + 2);
            if (day1 < 10) {
                day1 = '0' + day1;
            }
            if (day2 < 10) {
                day2 = '0' + day2;
            }
            this.data.tasks.records.push({
                id: i,
                name: 'Task ' + i,
                user_id: Math.floor(Math.random() * Math.floor(100)) + 1,
                start: '2018-12-' + day1,
                stop: '2018-12-' + day2,
            });
        }

        createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['user_id'],
        });
    });

    QUnit.skip('[for manual testing] scripting time of large amount of records (two level grouped)', async function (assert) {
        assert.expect(1);

        this.data.tasks.records = [];
        this.data.users.records = [];
        var stages = this.data.tasks.fields.stage.selection;

        var i;
        for (i = 1; i <= 100; i++) {
            this.data.users.records.push({
                id: i,
                name: i,
            });
        }

        for (i = 1; i <= 10000; i++) {
            this.data.tasks.records.push({
                id: i,
                name: 'Task ' + i,
                stage: stages[i % 2][0],
                user_id: (i % 100) + 1,
                start: '2018-12-01 00:00:00',
                stop: '2018-12-02 00:00:00',
            });
        }

        createView({
            View: GanttView,
            model: 'tasks',
            data: this.data,
            arch: '<gantt date_start="start" date_stop="stop" />',
            viewOptions: {
                initialDate: initialDate,
            },
            groupBy: ['user_id', 'stage'],
        });
    });
});
});
