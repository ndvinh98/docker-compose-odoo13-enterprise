odoo.define('helpdesk.dashboard_tests', function (require) {
"use strict";

var testUtils = require('web.test_utils');
var view_registry = require('web.view_registry');

var createView = testUtils.createView;

QUnit.module('Views', {}, function () {

QUnit.module('Helpdesk Dashboard', {
    beforeEach: function() {
        this.data = {
            partner: {
                fields: {
                    foo: {string: "Foo", type: "char"},
                },
                records: [
                    {id: 1, foo: "yop"},
                    {id: 2, foo: "blip"},
                    {id: 3, foo: "gnap"},
                    {id: 4, foo: "blip"},
                ]
            },
        };
        this.dashboard_data = {
            '7days': {count: 0, rating: 0, success: 0},
            helpdesk_target_closed: 12,
            helpdesk_target_rating: 0,
            helpdesk_target_success: 0,
            my_all: {count: 0, hours: 0, failed: 0},
            my_high: {count: 0, hours: 0, failed: 0},
            my_urgent: {count: 0, hours: 0, failed: 0},
            rating_enable: false,
            show_demo: false,
            success_rate_enable: false,
            today: {count: 0, rating: 0, success: 0},
        };
    }
});

QUnit.test('dashboard basic rendering', async function(assert) {
    assert.expect(4);

    var dashboard_data = this.dashboard_data;
    var kanban = await createView({
        View: view_registry.get('helpdesk_dashboard'),
        model: 'partner',
        data: this.data,
        arch: '<kanban class="o_kanban_test">' +
                '<templates><t t-name="kanban-box">' +
                    '<div><field name="foo"/></div>' +
                '</t></templates>' +
              '</kanban>',
        mockRPC: function(route, args) {
            if (args.method === 'retrieve_dashboard') {
                assert.ok(true, "should call /retrieve_dashboard");
                return Promise.resolve(dashboard_data);
            }
            return this._super(route, args);
        },
    });

    assert.containsOnce(kanban, 'div.o_helpdesk_dashboard',
            "should render the dashboard");
    assert.strictEqual(kanban.$('.o_target_to_set').text().trim(), '12',
        "should have written correct target");
    assert.hasAttrValue(kanban.$('.o_target_to_set'), 'value', '12',
        "target's value is 12");
    kanban.destroy();
});

QUnit.test('edit the target', async function(assert) {
    assert.expect(6);

    var dashboard_data = this.dashboard_data;
    dashboard_data.helpdesk_target_closed = 0;
    var kanban = await createView({
        View: view_registry.get('helpdesk_dashboard'),
        model: 'partner',
        data: this.data,
        arch: '<kanban class="o_kanban_test">' +
                '<templates><t t-name="kanban-box">' +
                    '<div><field name="foo"/></div>' +
                '</t></templates>' +
              '</kanban>',
        mockRPC: function(route, args) {
            if (args.method === 'retrieve_dashboard') {
                // should be called twice: for the first rendering, and after the target update
                assert.ok(true, "should call /retrieve_dashboard");
                return Promise.resolve(dashboard_data);
            }
            if (args.model === 'res.users' && args.method === 'write') {
                assert.ok(true, "should modify helpdesk_target_closed");
                dashboard_data.helpdesk_target_closed = args.args[1]['helpdesk_target_closed'];
                return Promise.resolve();
            }
            return this._super(route, args);
        },
    });

    assert.strictEqual(kanban.$('.o_target_to_set').text().trim(), "Click to set",
        "should have correct target");
    assert.ok(!kanban.$('.o_target_to_set').attr('value'), "should have no target");

    // edit the target
    await testUtils.dom.click(kanban.$('.o_target_to_set'));
    await testUtils.fields.editAndTrigger(kanban.$('.o_helpdesk_dashboard input'), 
        1200, [$.Event('keyup', {which: $.ui.keyCode.ENTER})]); // set the target

    assert.strictEqual(kanban.$('.o_target_to_set').text().trim(), "1200",
        "should have correct target");
    kanban.destroy();
});

QUnit.test('dashboard rendering with empty many2one', async function(assert) {
    assert.expect(2);

    // add an empty many2one
    this.data.partner.fields.partner_id = {string: "Partner", type: 'many2one', relation: 'partner'};
    this.data.partner.records[0].partner_id = false;

    var dashboard_data = this.dashboard_data;
    var kanban = await createView({
        View: view_registry.get('helpdesk_dashboard'),
        model: 'partner',
        data: this.data,
        arch: '<kanban class="o_kanban_test">' +
                '<field name="partner_id"/>' +
                '<templates><t t-name="kanban-box">' +
                    '<div><field name="foo"/></div>' +
                '</t></templates>' +
              '</kanban>',
        mockRPC: function(route, args) {
            if (args.method === 'retrieve_dashboard') {
                assert.ok(true, "should call /retrieve_dashboard");
                return Promise.resolve(dashboard_data);
            }
            return this._super(route, args);
        },
    });

    assert.containsOnce(kanban, 'div.o_helpdesk_dashboard',
            "should render the dashboard");
    kanban.destroy();
});

});

});
