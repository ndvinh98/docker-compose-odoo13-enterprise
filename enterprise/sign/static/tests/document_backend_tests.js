odoo.define('sign.document_backend_tests', function (require) {
"use strict";

var FormView = require('web.FormView');
var testUtils = require('web.test_utils');

var createActionManager = testUtils.createActionManager;
var createView = testUtils.createView;

QUnit.module('document_backend_tests', {
    beforeEach: function () {
        this.data = {
            'partner': {
                fields: {
                    display_name: { string: "Displayed name", type: "char" },
                    template_id: {string: "Template", type: "many2one", relation: 'sign.template'},
                },
                records: [{
                    id: 1,
                    display_name: "some record",
                    template_id: 1,
                }],
            },
            'sign.template': {
                fields: {
                    display_name: {string: "Template Name", type: "char"}
                },
                records: [{
                    id: 1, display_name: "some template",
                }],
            },
        };
    }
}, function () {
    QUnit.test('simple rendering', async function (assert) {
        assert.expect(1);

        var actionManager = await createActionManager({
            actions: [{
                id: 9,
                name: 'A Client Action',
                tag: 'sign.Document',
                type: 'ir.actions.client',
                context: {id: 5, token: 'abc'},
            }],
            mockRPC: function (route) {
                if (route === '/sign/get_document/5/abc') {
                    return Promise.resolve('<span>def</span>');
                }
                return this._super.apply(this, arguments);
            },
        });


        await actionManager.doAction(9);

        assert.strictEqual(actionManager.$('.o_sign_document').text().trim(), 'def',
            'should display text from server');

        actionManager.destroy();
    });

    QUnit.test('do not crash when leaving the action', async function (assert) {
        assert.expect(0);

        var actionManager = await createActionManager({
            actions: [{
                id: 9,
                name: 'A Client Action',
                tag: 'sign.Document',
                type: 'ir.actions.client',
                context: {id: 5, token: 'abc'},
            }],
            mockRPC: function (route) {
                if (route === '/sign/get_document/5/abc') {
                    return Promise.resolve('<span>def</span>');
                }
                return this._super.apply(this, arguments);
            },
        });


        await actionManager.doAction(9);
        await actionManager.doAction(9);

        actionManager.destroy();
    });

    QUnit.test('search more in many2one pointing to sign.template model', async function (assert) {
        // Addon sign patches the ListController for some models, like 'sign.template'.
        assert.expect(1);

        this.data['sign.template'].records = this.data['sign.template'].records.concat([
            {id: 11, display_name: "Template 11"},
            {id: 12, display_name: "Template 12"},
            {id: 13, display_name: "Template 13"},
            {id: 14, display_name: "Template 14"},
            {id: 15, display_name: "Template 15"},
            {id: 16, display_name: "Template 16"},
            {id: 17, display_name: "Template 17"},
        ]);

        var form = await createView({
            View: FormView,
            model: 'partner',
            data: this.data,
            arch: '<form><field name="template_id"/></form>',
            archs: {
                'sign.template,false,list': '<tree><field name="display_name"/></tree>',
                'sign.template,false,search': '<search></search>',
            },
        });

        await testUtils.fields.many2one.clickOpenDropdown('template_id');
        await testUtils.fields.many2one.clickItem('template_id', 'Search');

        await testUtils.dom.click($('.modal .o_data_row:first'));

        assert.strictEqual(form.$('.o_field_widget[name=template_id] input').val(), 'some template');

        form.destroy();
    });
});

});
