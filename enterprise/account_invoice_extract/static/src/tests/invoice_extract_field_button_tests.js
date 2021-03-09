odoo.define('account_invoice_extract.FieldButtonTests', function (require) {
"use strict";

var InvoiceExtractFieldButton = require('account_invoice_extract.FieldButton');

var testUtils = require('web.test_utils');

QUnit.module('account_invoice_extract', {}, function () {
QUnit.module('FieldButton', {}, function () {

    QUnit.test('modeling: basic', function (assert) {
        assert.expect(3);
        var parent = testUtils.createParent({});
        var fieldButton = new InvoiceExtractFieldButton(parent, {
            fieldName: 'my_field',
            text: 'myField',
        });
        fieldButton.appendTo($('#qunit-fixture'));

        assert.strictEqual(fieldButton.getFieldName(), 'my_field');
        assert.strictEqual(fieldButton.getText(), 'myField');
        assert.notOk(fieldButton.isActive(), "should not be active by default");

        parent.destroy();
    });

    QUnit.test('modeling: default active', function (assert) {
        assert.expect(1);
        var parent = testUtils.createParent({});
        var fieldButton = new InvoiceExtractFieldButton(parent, {
            fieldName: 'my_field',
            isActive: true,
            text: 'myField',
        });
        fieldButton.appendTo($('#qunit-fixture'));

        assert.ok(fieldButton.isActive(), "should be active by default");

        parent.destroy();
    });

    QUnit.test('modeling: set (in)active', function (assert) {
        assert.expect(3);
        var parent = testUtils.createParent({});
        var fieldButton = new InvoiceExtractFieldButton(parent, {
            fieldName: 'my_field',
            text: 'myField'
        });
        fieldButton.appendTo($('#qunit-fixture'));

        assert.notOk(fieldButton.isActive(), "should not be active by default");

        fieldButton.setActive();
        assert.ok(fieldButton.isActive(), "should become active");

        fieldButton.setInactive();
        assert.notOk(fieldButton.isActive(), "should become inactive");

        parent.destroy();
    });

    QUnit.test('rendering: basic', async function (assert) {
        assert.expect(5);
        var parent = testUtils.createParent({});
        var fieldButton = new InvoiceExtractFieldButton(parent, {
            fieldName: 'my_field',
            text: 'myField'
        });
        fieldButton.appendTo($('#qunit-fixture'));
        await testUtils.nextTick();

        assert.strictEqual($('.o_invoice_extract_button').length, 1,
            "should display the invoice extract field button");
        assert.strictEqual($('.o_invoice_extract_button')[0], fieldButton.el,
            "displayed button should be related to created field button widget");
        assert.strictEqual(fieldButton.$el.text().trim(), "myField",
            "should display the correct text on the button");
        assert.doesNotHaveClass(fieldButton.$el, 'active',
            "should not be active by default");
        assert.strictEqual(fieldButton.$el.data('field-name'), 'my_field',
            "button should refer to field name");

        parent.destroy();
    });

    QUnit.test('click', async function (assert) {
        assert.expect(2);
        var parent = testUtils.createParent({
            intercepts: {
                /**
                 * @param {OdooEvent} ev
                 */
                click_invoice_extract_field_button: function (ev) {
                    ev.stopPropagation();
                    assert.step('button clicked');
                },
            },
        });
        var fieldButton = new InvoiceExtractFieldButton(parent, {
            fieldName: 'my_field',
            text: 'myField'
        });
        fieldButton.appendTo($('#qunit-fixture'));
        await testUtils.nextTick();

        testUtils.dom.click(fieldButton.$el);
        assert.verifySteps(['button clicked']);

        parent.destroy();
    });

});
});
});
