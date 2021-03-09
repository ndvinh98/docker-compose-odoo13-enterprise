odoo.define('voip.tests', function (require) {
"use strict";

var config = require('web.config');
var FormView = require('web.FormView');
var ListView = require('web.ListView');
var testUtils = require('web.test_utils');

var createView = testUtils.createView;

QUnit.module('voip', {
    beforeEach: function () {
        this.data = {
            partner: {
                fields: {
                    foo: {string: "Foo", type: "char", default: "My little Foo Value", searchable: true},
                },
                records: [
                    {id: 1, foo: "yop"},
                    {id: 2, foo: "blip"},
                    {id: 4, foo: "abc"},
                    {id: 3, foo: "gnap"},
                    {id: 5, foo: "blop"},
                ],
            },
        };
    },
}, function () {

    QUnit.module('PhoneWidget');

    QUnit.test('phone field in form view on normal screens', async function (assert) {
        assert.expect(7);

        var form = await createView({
            View: FormView,
            model: 'partner',
            data: this.data,
            arch:'<form string="Partners">' +
                    '<sheet>' +
                        '<group>' +
                            '<field name="foo" widget="phone"/>' +
                        '</group>' +
                    '</sheet>' +
                '</form>',
            res_id: 1,
            config: {
                device: {
                    size_class: config.device.SIZES.MD,
                }
            },
        });

        var $phoneLink = form.$('a.o_form_uri.o_field_widget');
        assert.strictEqual($phoneLink.length, 1,
            "should have a anchor with correct classes");
        assert.strictEqual($phoneLink.text(), 'yop',
            "value should be displayed properly");
        assert.hasAttrValue($phoneLink, 'href', 'tel:yop',
            "should have proper tel prefix");

        // switch to edit mode and check the result
        await testUtils.form.clickEdit(form);
        assert.containsOnce(form, 'input[type="text"].o_field_widget',
            "should have an input for the phone field");
        assert.strictEqual(form.$('input[type="text"].o_field_widget').val(), 'yop',
            "input should contain field value in edit mode");

        // change value in edit mode
        await testUtils.fields.editInput(form.$('input[type="text"].o_field_widget'), 'new');

        // save
        await testUtils.form.clickSave(form);
        $phoneLink = form.$('a.o_form_uri.o_field_widget');
        assert.strictEqual($phoneLink.text(), 'new',
            "new value should be displayed properly");
        assert.hasAttrValue($phoneLink, 'href', 'tel:new',
            "should still have proper tel prefix");

        form.destroy();
    });

    QUnit.test('phone field in editable list view on normal screens', async function (assert) {
        assert.expect(10);

        var list = await createView({
            View: ListView,
            model: 'partner',
            data: this.data,
            arch: '<tree editable="bottom"><field name="foo"  widget="phone"/></tree>',
            config: {
                device: {
                    size_class: config.device.SIZES.MD,
                }
            },
        });

        assert.containsN(list, 'tbody td:not(.o_list_record_selector)', 5,
            "should have 5 cells");
        assert.strictEqual(list.$('tbody td:not(.o_list_record_selector)').first().text(), 'yop',
            "value should be displayed properly");

        var $phoneLink = list.$('a.o_form_uri.o_field_widget');
        assert.strictEqual($phoneLink.length, 5,
            "should have anchors with correct classes");
        assert.hasAttrValue($phoneLink.first(), 'href', 'tel:yop',
            "should have proper tel prefix");

        // Edit a line and check the result
        var $cell = list.$('tbody td:not(.o_list_record_selector)').first();
        await testUtils.dom.click($cell);
        assert.hasClass($cell.parent(),'o_selected_row', 'should be set as edit mode');
        assert.strictEqual($cell.find('input').val(), 'yop',
            'should have the corect value in internal input');
        await testUtils.fields.editInput($cell.find('input'), 'new');

        // save
        await testUtils.dom.click(list.$buttons.find('.o_list_button_save'));
        $cell = list.$('tbody td:not(.o_list_record_selector)').first();
        assert.doesNotHaveClass($cell.parent(), 'o_selected_row', 'should not be in edit mode anymore');
        assert.strictEqual(list.$('tbody td:not(.o_list_record_selector)').first().text(), 'new',
            "value should be properly updated");
        $phoneLink = list.$('a.o_form_uri.o_field_widget');
        assert.strictEqual($phoneLink.length, 5,
            "should still have anchors with correct classes");
        assert.hasAttrValue($phoneLink.first(), 'href', 'tel:new',
            "should still have proper tel prefix");

        list.destroy();
    });

});
});
