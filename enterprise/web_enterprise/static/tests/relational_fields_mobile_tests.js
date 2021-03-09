odoo.define('web_enterprise.relational_fields_mobile_tests', function (require) {
"use strict";

var FormView = require('web.FormView');
var testUtils = require('web.test_utils');

var createView = testUtils.createView;

QUnit.module('web_enterprise', {}, function () {

QUnit.module('relational_fields', {
    beforeEach: function () {
        this.data = {
            partner: {
                fields: {
                    display_name: { string: "Displayed name", type: "char" },
                    trululu: {string: "Trululu", type: "many2one", relation: 'partner'},
                    sibling_ids: {string: "Sibling", type: "many2many", relation: 'partner'},
                    p: { string: "one2many field", type: "one2many", relation: 'partner', relation_field: 'trululu' },
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

    QUnit.module('FieldStatus');

    QUnit.test('statusbar is rendered correclty on small devices', async function (assert) {
        assert.expect(7);

        var form = await createView({
            View: FormView,
            model: 'partner',
            data: this.data,
            arch:
                '<form string="Partners">' +
                    '<header><field name="trululu" widget="statusbar"/></header>' +
                    '<field name="display_name"/>' +
                '</form>',
            res_id: 1,
        });

        assert.strictEqual(form.$('.o_statusbar_status > button:contains(aaa)').length, 1,
            "should have only one visible status in mobile, the active one");
        assert.containsOnce(form, '.o_statusbar_status .dropdown-menu',
            "should have a dropdown containing all status");
        assert.containsNone(form, '.o_statusbar_status .dropdown-menu:visible',
            "dropdown should be hidden");

        // open the dropdown
        testUtils.dom.click(form.$('.o_statusbar_status > button'));
        assert.containsOnce(form, '.o_statusbar_status .dropdown-menu:visible',
            "dropdown should be visible");
        assert.containsN(form, '.o_statusbar_status .dropdown-menu button', 3,
            "should have 3 status");
        assert.containsN(form, '.o_statusbar_status button:disabled', 3,
            "all status should be disabled");
        var $activeStatus = form.$('.o_statusbar_status .dropdown-menu button[data-value=4]');
        assert.hasClass($activeStatus,'btn-primary', "active status should be btn-primary");

        form.destroy();
    });

    QUnit.test('statusbar with no status on extra small screens', async function (assert) {
        assert.expect(9);

        var form = await createView({
            View: FormView,
            model: 'partner',
            data: this.data,
            arch:'<form string="Partners">' +
                    '<header><field name="trululu" widget="statusbar"/></header>' +
                '</form>',
            res_id: 4,
        });

        assert.hasClass(form.$('.o_statusbar_status'),'o_field_empty',
            'statusbar widget should have class o_field_empty');
        assert.strictEqual(form.$('.o_statusbar_status').children().length, 2,
            'statusbar widget should have two children');
        assert.containsOnce(form, '.o_statusbar_status button.dropdown-toggle',
            'statusbar widget should have a button');
        assert.strictEqual(form.$('.o_statusbar_status button.dropdown-toggle').text().trim(), '',
            'statusbar button has no text');  // Behavior as of saas-15, might be improved
        assert.containsOnce(form, '.o_statusbar_status .dropdown-menu',
            'statusbar widget should have a dropdown menu');
        assert.containsN(form, '.o_statusbar_status .dropdown-menu button', 3,
            'statusbar widget dropdown menu should have 3 buttons');
        assert.strictEqual(form.$('.o_statusbar_status .dropdown-menu button').eq(0).text().trim(), 'first record',
            'statusbar widget dropdown first button should display the first record display_name');
        assert.strictEqual(form.$('.o_statusbar_status .dropdown-menu button').eq(1).text().trim(), 'second record',
            'statusbar widget dropdown second button should display the second record display_name');
        assert.strictEqual(form.$('.o_statusbar_status .dropdown-menu button').eq(2).text().trim(), 'aaa',
            'statusbar widget dropdown third button should display the third record display_name');
        form.destroy();
    });

    QUnit.test('clickable statusbar widget on mobile view', async function (assert) {
        assert.expect(5);

        var form = await createView({
            View: FormView,
            model: 'partner',
            data: this.data,
            arch:'<form string="Partners">' +
                    '<header><field name="trululu" widget="statusbar" options=\'{"clickable": "1"}\'/></header>' +
                '</form>',
            res_id: 1,
        });

        var $selectedStatus = form.$('.o_statusbar_status button[data-value="4"]');
        assert.hasClass($selectedStatus, 'btn-primary');
        assert.hasClass($selectedStatus,'disabled');
        var selector = '.o_statusbar_status button.btn-secondary:not(.dropdown-toggle):not(:disabled)';
        assert.containsN(form, selector, 2, "other status should be btn-secondary and not disabled");

        await testUtils.dom.click(form.$('.o_statusbar_status .dropdown-toggle'));
        await testUtils.dom.clickFirst(form.$(selector));

        var $status = form.$('.o_statusbar_status button[data-value="1"]');
        assert.hasClass($status, 'btn-primary');
        assert.hasClass($status, 'disabled');

        form.destroy();
    });

    QUnit.module('FieldMany2One');

    QUnit.test("many2one in a enterprise environment", async function (assert) {
        assert.expect(7);

        var form = await createView({
            View: FormView,
            arch:
                '<form>' +
                    '<sheet>' +
                        '<field name="trululu"/>' +
                    '</sheet>' +
                '</form>',
            archs: {
                'partner,false,kanban': '<kanban>' +
                    '<templates><t t-name="kanban-box">' +
                        '<div class="oe_kanban_global_click"><field name="display_name"/></div>' +
                    '</t></templates>' +
                '</kanban>',
                'partner,false,search': '<search></search>',
            },
            data: this.data,
            model: 'partner',
            res_id: 2,
            viewOptions: {mode: 'edit'},
        });

        var $input = form.$('.o_field_many2one input');

        assert.doesNotHaveClass($input, 'ui-autocomplete-input',
            "autocomplete should not be visible in a mobile environment");

        await testUtils.dom.click($input);

        var $modal = $('.o_modal_full .modal-lg');
        assert.equal($modal.length, 1, 'there should be one modal opened in full screen');
        assert.containsOnce($modal, '.o_kanban_view',
            'kanban view should be open in SelectCreateDialog');
        assert.containsOnce($modal, '.o_cp_searchview',
            'should have Search view inside SelectCreateDialog');
        assert.containsNone($modal.find(".o_control_panel .o_cp_buttons"), '.o-kanban-button-new',
            "kanban view in SelectCreateDialog should not have Create button");
        assert.strictEqual($modal.find(".o_kanban_view .o_kanban_record:not(.o_kanban_ghost)").length, 3,
            "popup should load 3 records in kanban");

        await testUtils.dom.click($modal.find('.o_kanban_view .o_kanban_record:first'));

        assert.strictEqual($input.val(), 'first record',
            'clicking kanban card should select record for many2one field');
        form.destroy();
    });

    QUnit.test("hide/show element using selection_mode in kanban view in a enterprise environment", async function (assert) {
        assert.expect(5);

        this.data.partner.fields.foo =  {string: "Foo", type: "char", default: "My little Foo Value"};

        var form = await createView({
            View: FormView,
            arch:
                '<form>' +
                    '<sheet>' +
                        '<field name="trululu"/>' +
                    '</sheet>' +
                '</form>',
            archs: {
                'partner,false,kanban': '<kanban>' +
                    '<templates><t t-name="kanban-box">' +
                        '<div class="oe_kanban_global_click">' +
                            '<field name="display_name"/>' +
                        '</div>' +
                        '<div class="o_sibling_tags" t-if="!selection_mode">' +
                            '<field name="sibling_ids"/>' +
                        '</div>' +
                        '<div class="o_foo" t-if="selection_mode">' +
                            '<field name="foo"/>' +
                        '</div>' +
                    '</t></templates>' +
                '</kanban>',
                'partner,false,search': '<search></search>',
            },
            data: this.data,
            model: 'partner',
            res_id: 2,
            viewOptions: {mode: 'edit'},
        });

        var $input = form.$('.o_field_many2one input');

        assert.doesNotHaveClass($input, 'ui-autocomplete-input',
            "autocomplete should not be visible in a mobile environment");

        await testUtils.dom.click($input);

        var $modal = $('.o_modal_full .modal-lg');
        assert.equal($modal.length, 1, 'there should be one modal opened in full screen');
        assert.containsOnce($modal, '.o_kanban_view',
            'kanban view should be open in SelectCreateDialog');
        assert.containsNone($modal, '.o_kanban_view .o_sibling_tags',
            'o_sibling_tags div should not be available as div have condition on selection_mode');
        assert.containsN($modal, '.o_kanban_view .o_foo', 3,
            'o_foo div should be available as div have condition on selection_mode');

        form.destroy();
    });

    QUnit.test("kanban_view_ref attribute opens specific kanban view given as a reference in a mobile environment", async function (assert) {
        assert.expect(5);

        var form = await createView({
            View: FormView,
            arch:
                '<form>' +
                    '<sheet>' +
                        '<field name="trululu" kanban_view_ref="2"/>' +
                    '</sheet>' +
                '</form>',
            archs: {
                'partner,1,kanban': '<kanban class="kanban1">' +
                    '<templates><t t-name="kanban-box">' +
                        '<div class="oe_kanban_global_click">' +
                            '<field name="display_name"/>' +
                        '</div>' +
                    '</t></templates>' +
                '</kanban>',
                'partner,2,kanban': '<kanban class="kanban2">' +
                    '<templates><t t-name="kanban-box">' +
                        '<div class="oe_kanban_global_click">' +
                            '<div>' +
                                '<field name="display_name"/>' +
                            '</div>' +
                            '<div>' +
                                '<field name="trululu"/>' +
                            '</div>' +
                        '</div>' +
                    '</t></templates>' +
                '</kanban>',
                'partner,false,search': '<search></search>',
            },
            data: this.data,
            model: 'partner',
            res_id: 2,
            viewOptions: {mode: 'edit'},
        });

        var $input = form.$('.o_field_many2one input');

        assert.doesNotHaveClass($input, 'ui-autocomplete-input',
            "autocomplete should not be visible in a mobile environment");

        await testUtils.dom.click($input);

        var $modal = $('.o_modal_full .modal-lg');
        assert.equal($modal.length, 1, 'there should be one modal opened in full screen');
        assert.containsOnce($modal, '.o_kanban_view',
            'kanban view should be open in SelectCreateDialog');
        assert.hasClass($modal.find('.o_kanban_view'), 'kanban2',
            'kanban view with id 2 should be opened as it is given as kanban_view_ref');
        assert.strictEqual($modal.find('.o_kanban_view .o_kanban_record:first').text(),
            'first recordaaa',
            'kanban with two fields should be opened');

        form.destroy();
    });

    QUnit.test("many2one dialog on mobile: clear button header", async function (assert) {
        assert.expect(7);

        const form = await createView({
            View: FormView,
            arch: `
                <form>
                    <sheet>
                        <field name="trululu"/>
                    </sheet>
                </form>
            `,
            archs: {
                'partner,false,kanban': `
                    <kanban>
                        <templates><t t-name="kanban-box">
                            <div class="oe_kanban_global_click"><field name="display_name"/></div>
                        </t></templates>
                    </kanban>
                `,
                'partner,false,search': '<search></search>',
            },
            data: this.data,
            model: 'partner',
            res_id: 2,
            viewOptions: {mode: 'edit'},
        });

        let $input = form.$('.o_field_many2one input');

        assert.doesNotHaveClass($input, 'ui-autocomplete-input',
            "autocomplete should not be visible in a mobile environment");

        await testUtils.dom.click($input);
        assert.containsOnce($('body'), '.modal.o_modal_full',
            "there should be a modal opened in full screen");
        assert.containsN($('.modal'), '.o_kanban_view .o_kanban_record:not(.o_kanban_ghost)', 3,
            "popup should load 3 records in kanban");

        await testUtils.dom.click($('.modal').find('.o_kanban_view .o_kanban_record:first'));
        assert.strictEqual($input.val(), 'first record',
            'clicking kanban card should select record for many2one field');

        await testUtils.dom.click($input);
        // clear button.
        assert.containsOnce($('.modal').find('.modal-header'), '.o_clear_button',
            "there should be a Clear button in the modal header");

        await testUtils.dom.click($('.modal').find('.modal-header .o_clear_button'));
        assert.containsNone($('body'), '.modal', "there should be no more modal");

        $input = form.$('.o_field_many2one input');
        assert.strictEqual($input.val(), "", "many2one should be cleared");
        form.destroy();
    });

    QUnit.module('FieldMany2Many');

    QUnit.test("many2many_tags in a mobile environment", async function (assert) {
        assert.expect(10);

        var rpcReadCount = 0;

        var form = await createView({
            View: FormView,
            arch:
                '<form>' +
                    '<sheet>' +
                        '<field name="sibling_ids" widget="many2many_tags"/>' +
                    '</sheet>' +
                '</form>',
            archs: {
                'partner,false,kanban': '<kanban>' +
                    '<templates><t t-name="kanban-box">' +
                        '<div class="oe_kanban_global_click"><field name="display_name"/></div>' +
                    '</t></templates>' +
                '</kanban>',
                'partner,false,search': '<search></search>',
            },
            data: this.data,
            model: 'partner',
            res_id: 2,
            viewOptions: {mode: 'edit'},
            mockRPC: function (route, args) {
                if (args.method === "read" && args.model === "partner") {
                    if (rpcReadCount === 0) {
                        assert.deepEqual(args.args[0], [2], "form should initially show partner 2");
                    } else if (rpcReadCount === 1) {
                        assert.deepEqual(args.args[0], [1], "partner with id 1 should be selected");
                    }
                    rpcReadCount++;
                }
                return this._super.apply(this, arguments);
            },
        });

        var $input = form.$(".o_field_widget .o_input");

        assert.strictEqual($input.find(".badge").length, 0,
            "many2many_tags should have no tags");

        await testUtils.dom.click($input);

        var $modal = $('.o_modal_full .modal-lg');
        assert.equal($modal.length, 1, 'there should be one modal opened in full screen');
        assert.containsOnce($modal, '.o_kanban_view',
            'kanban view should be open in SelectCreateDialog');
        assert.containsOnce($modal, '.o_cp_searchview',
            'should have Search view inside SelectCreateDialog');
        assert.containsNone($modal.find(".o_control_panel .o_cp_buttons"), '.o-kanban-button-new',
            "kanban view in SelectCreateDialog should not have Create button");
        assert.strictEqual($modal.find(".o_kanban_view .o_kanban_record:not(.o_kanban_ghost)").length, 3,
            "popup should load 3 records in kanban");

        await testUtils.dom.click($modal.find('.o_kanban_view .o_kanban_record:first'));

        assert.strictEqual(rpcReadCount, 2, "there should be a read for current form record and selected sibling");
        assert.strictEqual(form.$(".o_field_widget.o_input .badge").length, 1,
            "many2many_tags should have partner coucou3");

        form.destroy();
    });

    QUnit.module('FieldOne2Many');

    QUnit.test('one2many on mobile: remove header button', async function (assert) {
        assert.expect(9);
        this.data.partner.records[0].p = [1, 2, 4];
        const form = await createView({
            View: FormView,
            model: 'partner',
            data: this.data,
            arch: `
                <form string="Partners">
                    <field name="p"/>
                </form>
            `,
            archs: {
                'partner,false,form': `
                    <form string="Partner">
                        <field name="display_name"/>
                    </form>
                `,
                'partner,false,kanban': `
                    <kanban>
                        <templates><t t-name="kanban-box">
                            <div class="oe_kanban_global_click">
                                <field name="display_name"/>
                            </div>
                        </t></templates>
                    </kanban>
                `,
            },
            res_id: 1,
            mockRPC(route, args) {
                if (route === '/web/dataset/call_kw/partner/write') {
                    const commands = args.args[1].p;
                    assert.strictEqual(commands.length, 3,
                        'should have generated three commands');
                    assert.ok(commands[0][0] === 4 && commands[0][1] === 2,
                        'should have generated the command 4 (LINK_TO) with id 2');
                    assert.ok(commands[1][0] === 4 && commands[1][1] === 4,
                        'should have generated the command 2 (LINK_TO) with id 1');
                    assert.ok(commands[2][0] === 2 && commands[2][1] === 1,
                        'should have generated the command 2 (DELETE) with id 2');
                }
                return this._super.apply(this, arguments);
            },
        });

        await testUtils.form.clickEdit(form);
        assert.containsN(form, '.o_kanban_view .o_kanban_record:not(.o_kanban_ghost)', 3,
            "should have 3 records in kanban");

        await testUtils.dom.click(form.$('.o_kanban_view .o_kanban_record:first'));
        assert.containsOnce($('body'), '.modal.o_modal_full',
            "there should be a modal opened in full screen");

        // remove button.
        assert.containsOnce($('.modal').find('.modal-header'), '.o_btn_remove',
            "there should be a 'Remove' button in the modal header");

        await testUtils.dom.click($('.modal').find('.modal-header .o_btn_remove'));
        assert.containsNone($('body'), '.modal', "there should be no more modal");
        assert.containsN(form, '.o_kanban_view .o_kanban_record:not(.o_kanban_ghost)', 2,
            "should have 2 records in kanban");

        // save and check that the correct command has been generated
        await testUtils.form.clickSave(form);

        form.destroy();
    });
});
});
});
