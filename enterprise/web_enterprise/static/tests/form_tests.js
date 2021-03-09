odoo.define('web_enterprise.form_tests', function (require) {
"use strict";

var FormView = require('web.FormView');
var testUtils = require('web.test_utils');

var createView = testUtils.createView;

QUnit.module('web_enterprise', {
    beforeEach: function () {
        this.data = {
            partner: {
                fields: {
                    display_name: { string: "Displayed name", type: "char" },
                    trululu: {string: "Trululu", type: "many2one", relation: 'partner'},
                },
                records: [{
                    id: 1,
                    display_name: "first record",
                    trululu: 4,
                }, {
                    id: 2,
                    display_name: "second record",
                    trululu: 1,
                }, {
                    id: 4,
                    display_name: "aaa",
                }],
            },
        };
    }
}, function () {

    QUnit.module('Mobile FormView');

    QUnit.test('statusbar buttons are correctly rendered in mobile', async function (assert) {
        assert.expect(5);

        var form = await createView({
            View: FormView,
            model: 'partner',
            data: this.data,
            arch: '<form string="Partners">' +
                    '<header>' +
                        '<button string="Confirm"/>' +
                        '<button string="Do it"/>' +
                    '</header>' +
                    '<sheet>' +
                        '<group>' +
                            '<button name="display_name"/>' +
                        '</group>' +
                    '</sheet>' +
                '</form>',
            res_id: 1,
        });

        assert.strictEqual(form.$('.o_statusbar_buttons a:contains(Action)').length, 1,
            "statusbar should contain a button 'Action'");
        assert.containsOnce(form, '.o_statusbar_buttons .dropdown-menu',
            "statusbar should contain a dropdown");
        assert.containsNone(form, '.o_statusbar_buttons .dropdown-menu:visible',
            "dropdown should be hidden");

        // open the dropdown
        await testUtils.dom.click(form.$('.o_statusbar_buttons a'));
        assert.containsOnce(form, '.o_statusbar_buttons .dropdown-menu:visible',
            "dropdown should be visible");
        assert.containsN(form, '.o_statusbar_buttons .dropdown-menu > button', 2,
            "dropdown should contain 2 buttons");

        form.destroy();
    });

    QUnit.test('statusbar "Action" button not displayed if no buttons', async function (assert) {
        assert.expect(1);

        var form = await createView({
            View: FormView,
            model: 'partner',
            data: this.data,
            arch: '<form string="Partners">' +
                    '<header><field name="trululu" widget="statusbar"/></header>' +
                    '<sheet>' +
                        '<group>' +
                            '<button name="display_name"/>' +
                        '</group>' +
                    '</sheet>' +
                '</form>',
            res_id: 1,
        });

        assert.containsNone(form, '.o_statusbar_buttons',
            "statusbar buttons are not displayed as there is no button");

        form.destroy();
    });

    QUnit.test('statusbar "Action" button not displayed if all buttons inside it are invisible', async function (assert) {
        assert.expect(4);

        var form = await createView({
            View: FormView,
            model: 'partner',
            data: this.data,
            arch: '<form>' +
                    '<header>' +
                        '<button string="Confirm" attrs=\'{"invisible": [["display_name", "=", "first record"]]}\'/>' +
                    '</header>' +
                    '<sheet>' +
                        '<group>' +
                            '<field name="display_name"/>' +
                        '</group>' +
                    '</sheet>' +
                '</form>',
            res_id: 1,
        });


        // if all buttons are invisible then action button should also be invisible
        assert.hasClass(form.$('.o_statusbar_buttons .dropdown-menu button'), 'o_invisible_modifier',
            "'Confirm' button should have 'o_invisible_modifier' class");
        assert.hasClass(form.$('.o_statusbar_buttons'), 'o_invisible_modifier',
            "'Action' button should be invisible");

        // change display_name to update buttons modifiers and make it visible
        await testUtils.form.clickEdit(form);
        await testUtils.fields.editInput(form.$('input[name=display_name]'), 'test');
        await testUtils.form.clickSave(form);
        assert.doesNotHaveClass(form.$('.o_statusbar_buttons .dropdown-menu button'), 'o_invisible_modifier',
            "button should be o_invisible_modifier class");
        assert.doesNotHaveClass(form.$('.o_statusbar_buttons'), 'o_invisible_modifier',
            "'Action' button should be visible");

        form.destroy();
    });

    QUnit.test('statusbar "Action" button not displayed in edit mode with .oe_read_only button', async function (assert) {
        assert.expect(2);

        var form = await createView({
            View: FormView,
            model: 'partner',
            data: this.data,
            arch: `
                <form>
                    <header>
                        <button string="Share" type="action" class="oe_highlight oe_read_only"/>
                    </header>
                    <sheet>
                        <group>
                            <field name="display_name"/>
                        </group>
                    </sheet>
                </form>
            `,
            res_id: 1,
            viewOptions: {
                mode: 'edit',
            },
        });

        assert.hasClass(form.$('.o_statusbar_buttons'), 'o_invisible_modifier',
            "'Action' button should be visible");
        await testUtils.form.clickSave(form);
        assert.doesNotHaveClass(form.$('.o_statusbar_buttons'), 'o_invisible_modifier',
            "'Action' button should be invisible");
        form.destroy();
    });
});

});
