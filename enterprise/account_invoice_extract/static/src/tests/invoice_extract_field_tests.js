odoo.define('account_invoice_extract.FieldTests', function (require) {
"use strict";

var InvoiceExtractField = require('account_invoice_extract.Field');

var testUtils = require('web.test_utils');

QUnit.module('account_invoice_extract', {}, function () {
QUnit.module('Field', {}, function () {

    QUnit.test('basic modeling', function (assert) {
        assert.expect(2);
        var parent = testUtils.createParent({});
        var field = new InvoiceExtractField(parent, {
            fieldName: 'my_field',
        });

        assert.strictEqual(field.getName(), 'my_field');
        assert.notOk(field.isActive(), "should not be active by default");

        parent.destroy();
    });

    QUnit.test('active/inactive', function (assert) {
        assert.expect(3);
        var parent = testUtils.createParent({});
        var field = new InvoiceExtractField(parent, {
            fieldName: 'my_field',
        });

        assert.notOk(field.isActive(), "should not be active by default");

        field.setActive();
        assert.ok(field.isActive(), "should become active");

        field.setInactive();
        assert.notOk(field.isActive(), "should become inactive");

        parent.destroy();
    });

    QUnit.test('render button', async function (assert) {
        assert.expect(3);
        var parent = testUtils.createParent({});
        var field = new InvoiceExtractField(parent, {
            fieldName: 'my_field',
            text: 'myField',
        });

        await field.renderButton({$container: $('#qunit-fixture')});
        assert.strictEqual($('.o_invoice_extract_button').length, 1,
            "should display a button");
        assert.strictEqual($('.o_invoice_extract_button').text().trim(), "myField",
            "should display correct text on the button");
        assert.strictEqual($('.o_invoice_extract_button').data('field-name'), "my_field",
            "should refer to correct field name");

        parent.destroy();
    });

    QUnit.test('set (in)active with button', async function (assert) {
        assert.expect(4);
        var parent = testUtils.createParent({});
        var field = new InvoiceExtractField(parent, {
            fieldName: 'my_field',
            text: 'myField',
        });

        await field.renderButton({$container: $('#qunit-fixture')});
        assert.strictEqual($('.o_invoice_extract_button').length, 1,
            "should display a button");
        assert.doesNotHaveClass($('.o_invoice_extract_button'), 'active',
            "button should not be active by default");

        field.setActive();
        assert.hasClass($('.o_invoice_extract_button'),'active',
            "button should become active");

        field.setInactive();
        assert.doesNotHaveClass($('.o_invoice_extract_button'), 'active',
            "button should become inactive");

        parent.destroy();
    });

    QUnit.test('click on button', async function (assert) {
        assert.expect(4);

        var field;
        var parent = testUtils.createParent({
            intercepts: {
                /**
                 * @param {OdooEvent} ev
                 * @param {string} ev.data.fieldName the name of the field
                 */
                active_invoice_extract_field: function (ev) {
                    ev.stopPropagation();
                    assert.step('set active field');
                    assert.strictEqual(ev.data.fieldName, field.getName(),
                        "should have the name of the field");
                },
            },
        });
        field = new InvoiceExtractField(parent, {
            fieldName: 'my_field',
            text: 'myField',
        });

        await field.renderButton({$container: $('#qunit-fixture')});
        assert.strictEqual($('.o_invoice_extract_button').length, 1,
            "should display a button");

        await testUtils.dom.click($('.o_invoice_extract_button'));

        assert.verifySteps(['set active field']);

        parent.destroy();
    });

});
});
});
