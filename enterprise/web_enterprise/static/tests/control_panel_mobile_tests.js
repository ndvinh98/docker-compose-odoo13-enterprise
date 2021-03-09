odoo.define('web.control_panel_mobile_tests', function (require) {
"use strict";

var testUtils = require('web.test_utils');

var createActionManager = testUtils.createActionManager;

QUnit.module('Control Panel', {
    beforeEach: function () {
        this.data = {
            partner: {
                fields: {
                    foo: {string: "Foo", type: "char"},
                },
                records: [
                    {id: 1, display_name: "First record", foo: "yop"},
                ],
            },
        };

        this.actions = [{
            id: 1,
            name: 'Partners Action 1',
            res_model: 'partner',
            type: 'ir.actions.act_window',
            views: [[false, 'list']],
        }];

        this.archs = {
            // list views
            'partner,false,list': '<tree><field name="foo"/></tree>',

            // search views
            'partner,false,search': '<search><field name="foo" string="Foo"/></search>',
        };
    },
}, function () {
    QUnit.test('searchview should be hidden by default', async function (assert) {
        assert.expect(2);

        var actionManager = await createActionManager({
            actions: this.actions,
            archs: this.archs,
            data: this.data,
        });

        await actionManager.doAction(1);

        assert.notOk($('.o_control_panel .o_mobile_search').is(':visible'),
            "search options are hidden by default");
        assert.strictEqual($('.o_control_panel .o_enable_searchview').length, 1,
            "should display a button to toggle the searchview");

        actionManager.destroy();
    });

});

});
