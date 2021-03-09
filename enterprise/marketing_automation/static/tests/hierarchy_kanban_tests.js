odoo.define('marketing_automation.hirarchy_kanban_tests', function (require) {
"use strict";

var testUtils = require('web.test_utils');
var FormView = require('web.FormView');

var createView = testUtils.createView;

QUnit.module('Marketing Automation', {
    beforeEach: function () {
        this.data = {
            'campaign': {
                fields: {
                    name: {string : "Campaign Name", type: "char"},
                    activity_ids: {string : "Activities", relation: 'activity', type: 'one2many', relation_field: 'campaign_id',},
                },
                records: [{
                    id: 1,
                    name: 'Campaign 1',
                    activity_ids: [1, 2, 3, 4, 5, 6],
                }]
            }, 
            'activity': {
                fields: {
                    name: {string : "Activity Name", type: "char"},
                    parent_id: {string : "Parent Activity", relation: 'activity', type: 'many2one'},
                    campaign_id: {string : "Campaign", relation: 'campaign', type: 'many2one'},
                },
                records: [{
                    id: 1,
                    name: 'Parent 1',
                }, {
                    id: 2,
                    name: 'Parent 1 > Child 1',
                    parent_id: 1,
                }, {
                    id: 3,
                    name: 'Parent 2',
                }, {
                    id: 4,
                    name: 'Parent 2 > Child 1',
                    parent_id: 3,
                }, {
                    id: 5,
                    name: 'Parent 2 > Child 2',
                    parent_id: 3
                }, {
                    id: 6,
                    name: 'Parent 2 > Child 2 > Child 1',
                    parent_id: 5
                }]
            }
        };
    }
}, function () {

    QUnit.test('render basic hirarchy kanban', async function (assert) {
        assert.expect(10);

        var form = await createView({
            View: FormView,
            model: 'campaign',
            data: this.data,
            arch: '<form string="Campaign">' +
                    '<sheet>' +
                        '<group>' +
                            '<field name="name"/>' +
                        '</group>' +
                        '<div>' +
                            '<field name="activity_ids" widget="hierarchy_kanban" class="o_ma_hierarchy_container">' +
                                '<kanban>' +
                                    '<field name="name"/>' +
                                    '<field name="parent_id"/>' +
                                    '<templates>' +
                                        '<div t-name="kanban-box">' +
                                            '<div class="o_title">' +
                                                 '<t t-esc="record.name.value"/>' +
                                            '</div>' +
                                            '<div class="o_hierarchy_children" />' +
                                        '</div>' +
                                    '</templates>' +
                                '</kanban>' +
                            '</field>' +
                        '</div>' +
                    '</sheet>' +
                '</form>',
            res_id: 1
        });

        // Checking number of child and their positions
        var $parentRecords = form.$('.o_ma_hierarchy_container .o_kanban_view > .o_kanban_record');
        assert.strictEqual($parentRecords.length, 2, "There should be 2 parent");
        assert.containsOnce($($parentRecords[0]), '> .o_hierarchy_children > .o_kanban_record', "First parent should have 1 child");
        assert.containsN($($parentRecords[1]), '> .o_hierarchy_children > .o_kanban_record', 2, "Second parent should have 2 child");
        assert.containsOnce($($parentRecords[1]), '.o_hierarchy_children .o_hierarchy_children > .o_kanban_record', "2nd parent's 2nd Child should have 1 child");

        // Checking titles of kanban to verify proper values
        assert.strictEqual($($parentRecords[0]).find('> .o_title').text(), 'Parent 1', "Title of 1st parent");
        assert.strictEqual($($parentRecords[1]).find('> .o_title').text(), 'Parent 2', "Title of 1st parent");
        assert.strictEqual($($parentRecords[0]).find('> .o_hierarchy_children > .o_kanban_record > .o_title').text(), 'Parent 1 > Child 1', "Title of 1st parent's child");
        assert.strictEqual($($parentRecords[1]).find('> .o_hierarchy_children > .o_kanban_record:first > .o_title').text(), 'Parent 2 > Child 1', "Title of 2nd parent's 1st child");
        assert.strictEqual($($parentRecords[1]).find('> .o_hierarchy_children > .o_kanban_record:last > .o_title').text(), 'Parent 2 > Child 2', "Title of 2nd parent's 2nd child");
        assert.strictEqual($($parentRecords[1]).find('> .o_hierarchy_children .o_hierarchy_children > .o_kanban_record:last > .o_title').text(), 'Parent 2 > Child 2 > Child 1', "Title of 2ed parent's 2ed child's 1st child");
        form.destroy();
    });

});
});
