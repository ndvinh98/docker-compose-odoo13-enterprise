odoo.define('account_invoice_extract.FormViewTests', function (require) {
"use strict";

var mailTestUtils = require('mail.testUtils');

var FormRenderer = require('account_invoice_extract.FormRenderer');
var FormView = require('account_invoice_extract.FormView');
var invoiceExtractTestUtils = require('account_invoice_extract.testUtils');

var config = require('web.config');
var testUtils = require('web.test_utils');

QUnit.module('account_invoice_extract', {}, function () {
QUnit.module('FormView', {
    beforeEach: function () {
        this.data = {
            'account.move': {
                fields: {
                    amount_total: { string: 'Amount Total', type: 'integer' },
                    currency_id: { string: 'Currency', type: 'many2one', relation: 'res.currency' },
                    date: { string: 'Date', type: 'date' },
                    date_due: { string: 'Due Date', type: 'date' },
                    invoice_date: { string: 'Invoice Date', type: 'date' },
                    display_name: { string: 'Name', type: 'string' },
                    invoice_id: { string: 'InvoiceId', type: 'string' },
                    message_attachment_count: { string: 'Attachment count', type: 'integer' },
                    message_ids: {
                        string: 'messages',
                        type: 'one2many',
                        relation: 'mail.message',
                        relation_field: 'res_id',
                    },
                },
                records: [{
                    amount_total: 100,
                    currency_id: [2, 'USD'],
                    date: '1984-12-15',
                    date_due: '1984-12-20',
                    invoice_date: '1984-12-15',
                    display_name: 'MyInvoice',
                    invoice_id: 'INV_15/26/34',
                    id: 2,
                    message_attachment_count: 1,
                    message_ids: [1]
                }],
            },
            'mail.message': {
                fields: {
                    // attachment_ids: { string: 'Attachments', type: 'one2many', relation: 'ir.attachment'},
                    author_id: { string: '', type: '' },
                    body: { string: '', type: 'string' },
                    date: { string: 'Date', type: 'date' },
                    displayed_author: { string: '', type: 'string' },
                    is_note: { string: '', type: 'boolean' },
                    is_discussion: { string: '', type: 'boolean' },
                    is_starred: { string: 'Starred', type: 'boolean' },
                    model: { string: 'Document Model', type: 'string' },
                    res_id: { string: 'Document ID', type: 'integer' },
                },
                records: [{
                    attachment_ids: [{
                        filename: 'image1.jpg',
                        id:1,
                        mimetype: 'image/jpeg',
                        name: 'Test Image 1',
                        url: '/web/content/1?download=true',
                    }],
                    author_id: [1, "Kamlesh Sulochan"],
                    body: "Attachment viewer test",
                    date: "2016-12-20 09:35:40",
                    displayed_author: "Kamlesh Sulochan",
                    id: 1,
                    is_note: false,
                    is_discussion: true,
                    is_starred: false,
                    model: 'account.move',
                    res_id: 2,
                }],
            }
        };

        testUtils.mock.patch(FormRenderer, {
            /**
             * Called when chatter is rendered
             *
             * @param {OdooEvent} ev
             */
            _onAttachmentPreviewValidation: function (ev) {
                ev.stopPropagation();
                var $attachment = this.$attachmentPreview.find('.img-fluid');
                this._startInvoiceExtract($attachment);
            },
        });
    },
    afterEach: function () {
        testUtils.mock.unpatch(FormRenderer);
    },
}, function () {

    QUnit.test('basic', async function (assert) {
        assert.expect(27);

        var form = await testUtils.createView({
            View: FormView,
            model: 'account.move',
            data: this.data,
            arch: '<form string="Account Invoice">' +
                    '<div class="o_success_ocr"/>' +
                    '<div class="o_attachment_preview" options="{\'order\':\'desc\'}"></div>' +
                    '<div class="oe_chatter">' +
                        '<field name="message_ids" widget="mail_thread" options="{\'display_log_button\': True}"/>' +
                    '</div>' +
                '</form>',
            res_id: 2,
            services: mailTestUtils.getMailServices(),
            config: {
                device: {
                    size_class: config.device.SIZES.XXL,
                },
            },
            mockRPC: function (route, args) {
                if (args.method === 'get_boxes') {
                    return Promise.resolve(invoiceExtractTestUtils.createBoxesData());
                } else if (args.method === 'search_read') {
                    return Promise.resolve([this.data['mail.message'].records[0].attachment_ids[0]]);
                } else if (args.method === 'register_as_main_attachment') {
                    return Promise.resolve(true);
                }
                return this._super.apply(this, arguments);
            },
        });

        // Need to load form view before going to edit mode, otherwise
        // 'o_success_ocr' is not loaded.
        await testUtils.dom.click($('.o_form_button_edit'));

        var $attachmentPreview = form.$('.o_attachment_preview_img');

        // check presence of attachment, buttons, box layer, boxes
        assert.strictEqual($attachmentPreview.length, 1,
            "should display attachment preview");
        assert.containsOnce($attachmentPreview, '.o_invoice_extract_buttons',
            "should display the field extract buttons on attachment preview");
        assert.strictEqual($('.o_invoice_extract_button').length, 5,
            "should display 5 invoice extract buttons");
        assert.strictEqual($('.o_invoice_extract_button.active').length, 1,
            "should have one field extract button that is active");
        assert.strictEqual($('.o_invoice_extract_button.active').data('field-name'),
            'VAT_Number',
            "should have 'VAT_Number' as the active field");
        assert.strictEqual($attachmentPreview.find('.boxLayer').length, 1,
            "should contain a box layer on attachment");
        assert.containsN($attachmentPreview, '.o_invoice_extract_box', 5,
            "should contain all boxes");

        // check field name of boxes
        assert.strictEqual(form.$('.o_invoice_extract_box[data-id=1]').data('field-name'),
            'VAT_Number',
            "box with ID 1 should be related to field 'VAT_Number'");
        assert.strictEqual(form.$('.o_invoice_extract_box[data-id=2]').data('field-name'),
            'VAT_Number',
            "box with ID 2 should be related to field 'VAT_Number'");
        assert.strictEqual(form.$('.o_invoice_extract_box[data-id=3]').data('field-name'),
            'VAT_Number',
            "box with ID 3 should be related to field 'VAT_Number'");
        assert.strictEqual(form.$('.o_invoice_extract_box[data-id=4]').data('field-name'),
            'invoice_id',
            "box with ID 4 should be related to field 'invoice_id'");
        assert.strictEqual(form.$('.o_invoice_extract_box[data-id=5]').data('field-name'),
            'invoice_id',
            "box with ID 5 should be related to field 'invoice_id'");

        // check visibility of boxes
        // the box is appended in the o_attachment_preview, which is displayed
        // on XXL screens thanks to mediaqueries ; however, the test suite is
        // executed on a 1366x768 screen, so the rule doesn't apply and the
        // boxes are actually not visible ; for that reason, we don't use the
        // is(Not)Visible helpers, but directly check the presence/absence of
        // class o_hidden
        assert.notOk(form.$('.o_invoice_extract_box[data-id=1]').hasClass('o_hidden'),
            "box with ID 1 should be visible");
        assert.notOk(form.$('.o_invoice_extract_box[data-id=2]').hasClass('o_hidden'),
            "box with ID 2 should be visible");
        assert.notOk(form.$('.o_invoice_extract_box[data-id=3]').hasClass('o_hidden'),
            "box with ID 3 should be visible");
        assert.ok(form.$('.o_invoice_extract_box[data-id=4]').hasClass('o_hidden'),
            "box with ID 4 should be invisible");
        assert.ok(form.$('.o_invoice_extract_box[data-id=5]').hasClass('o_hidden'),
            "box with ID 5 should be invisible");

        // check selection of boxes
        assert.doesNotHaveClass(form.$('.o_invoice_extract_box[data-id=1]'), 'ocr_chosen',
            "box with ID 1 should not be OCR chosen");
        assert.doesNotHaveClass(form.$('.o_invoice_extract_box[data-id=1]'), 'selected',
            "box with ID 1 should not be selected");
        assert.hasClass(form.$('.o_invoice_extract_box[data-id=2]'),'ocr_chosen',
            "box with ID 2 should be OCR chosen");
        assert.doesNotHaveClass(form.$('.o_invoice_extract_box[data-id=2]'), 'selected',
            "box with ID 2 should not be selected");
        assert.doesNotHaveClass(form.$('.o_invoice_extract_box[data-id=3]'), 'ocr_chosen',
            "box with ID 3 should not be OCR chosen");
        assert.hasClass(form.$('.o_invoice_extract_box[data-id=3]'),'selected',
            "box with ID 3 should be selected");
        assert.doesNotHaveClass(form.$('.o_invoice_extract_box[data-id=4]'), 'ocr_chosen',
            "box with ID 4 should not be OCR chosen");
        assert.doesNotHaveClass(form.$('.o_invoice_extract_box[data-id=4]'), 'selected',
            "box with ID 4 should not be selected");
        assert.hasClass(form.$('.o_invoice_extract_box[data-id=5]'),'ocr_chosen',
            "box with ID 5 should be OCR chosen");
        assert.hasClass(form.$('.o_invoice_extract_box[data-id=5]'),'selected',
            "box with ID 5 should be selected");

        form.destroy();
    });

    QUnit.test('no box and button in readonly mode', async function (assert) {
        assert.expect(15);

        var form = await testUtils.createView({
            View: FormView,
            model: 'account.move',
            data: this.data,
            arch: '<form string="Account Invoice">' +
                    '<div class="o_success_ocr"/>' +
                    '<div class="o_attachment_preview" options="{\'order\':\'desc\'}"></div>' +
                    '<div class="oe_chatter">' +
                        '<field name="message_ids" widget="mail_thread" options="{\'display_log_button\': True}"/>' +
                    '</div>' +
                '</form>',
            res_id: 2,
            services: mailTestUtils.getMailServices(),
            config: {
                device: {
                    size_class: config.device.SIZES.XXL,
                },
            },
            mockRPC: function (route, args) {
                if (args.method === 'get_boxes') {
                    return Promise.resolve(invoiceExtractTestUtils.createBoxesData());
                } else if (args.method === 'search_read') {
                    return Promise.resolve([this.data['mail.message'].records[0].attachment_ids[0]]);
                } else if (args.method === 'register_as_main_attachment') {
                    return Promise.resolve(true);
                }
                return this._super.apply(this, arguments);
            },
        });

        var $attachmentPreview = form.$('.o_attachment_preview_img');
        assert.strictEqual($attachmentPreview.length, 1,
            "should display attachment preview");
        assert.strictEqual($attachmentPreview.find('.o_invoice_extract_buttons').length, 0,
            "should not display any field extract buttons on attachment preview in readonly mode");
        assert.strictEqual($('.o_invoice_extract_button').length, 0,
            "should not display any invoice extract buttons in readonly mode");
        assert.strictEqual($('.boxLayer').length, 0,
            "should not display any box layer in readonly mode");
        assert.strictEqual($('.o_invoice_extract_box').length, 0,
            "should not display any box in readonly mode");

        // Need to load form view before going to edit mode, otherwise
        // 'o_success_ocr' is not loaded.
        await testUtils.dom.click($('.o_form_button_edit'));

        $attachmentPreview = form.$('.o_attachment_preview_img');
        assert.strictEqual($attachmentPreview.length, 1,
            "should still display an attachment preview in edit mode");
        assert.strictEqual($attachmentPreview.find('.o_invoice_extract_buttons').length, 1,
            "should now display field extract buttons on attachment preview in edit mode");
        assert.strictEqual($('.o_invoice_extract_button').length, 5,
            "should now display 5 invoice extract buttons in edit mode");
        assert.strictEqual($('.boxLayer').length, 1,
            "should now display box layer in edit mode");
        assert.strictEqual($('.o_invoice_extract_box').length, 5,
            "should now display boxes in edit mode");

        await testUtils.dom.click($('.o_form_button_save'));

        $attachmentPreview = form.$('.o_attachment_preview_img');
        assert.strictEqual($attachmentPreview.length, 1,
            "should still display attachment preview in readonly mode");
        assert.strictEqual($attachmentPreview.find('.o_invoice_extract_buttons').length, 0,
            "should no longer display field extract buttons on attachment preview in readonly mode");
        assert.strictEqual($('.o_invoice_extract_button').length, 0,
            "should no longer display invoice extract buttons in readonly mode");
        assert.strictEqual($('.boxLayer').length, 0,
            "should no longer display box layer in readonly mode");
        assert.strictEqual($('.o_invoice_extract_box').length, 0,
            "should no longer display boxes in readonly mode");

        form.destroy();
    });

    QUnit.test('change active field', async function (assert) {
        assert.expect(12);

        var form = await testUtils.createView({
            View: FormView,
            model: 'account.move',
            data: this.data,
            arch: '<form string="Account Invoice">' +
                    '<div class="o_success_ocr"/>' +
                    '<div class="o_attachment_preview" options="{\'order\':\'desc\'}"></div>' +
                    '<div class="oe_chatter">' +
                        '<field name="message_ids" widget="mail_thread" options="{\'display_log_button\': True}"/>' +
                    '</div>' +
                '</form>',
            res_id: 2,
            services: mailTestUtils.getMailServices(),
            config: {
                device: {
                    size_class: config.device.SIZES.XXL,
                },
            },
            mockRPC: function (route, args) {
                if (args.method === 'get_boxes') {
                    return Promise.resolve(invoiceExtractTestUtils.createBoxesData());
                } else if (args.method === 'search_read') {
                    return Promise.resolve([this.data['mail.message'].records[0].attachment_ids[0]]);
                } else if (args.method === 'register_as_main_attachment') {
                    return Promise.resolve(true);
                }
                return this._super.apply(this, arguments);
            },
        });

        // Need to load form view before going to edit mode, otherwise
        // 'o_success_ocr' is not loaded.
        await testUtils.form.clickEdit(form);

        assert.strictEqual($('.o_invoice_extract_button.active').data('field-name'),
            'VAT_Number', "should have 'VAT_Number' as the active field");

        // the box is appended in the o_attachment_preview, which is displayed
        // on XXL screens thanks to mediaqueries ; however, the test suite is
        // executed on a 1366x768 screen, so the rule doesn't apply and the
        // boxes are actually not visible ; for that reason, we don't use the
        // click and is(Not)Visible helpers
        assert.notOk(form.$('.o_invoice_extract_box[data-id=1]').hasClass('o_hidden'),
            "box with ID 1 should be visible");
        assert.notOk(form.$('.o_invoice_extract_box[data-id=2]').hasClass('o_hidden'),
            "box with ID 2 should be visible");
        assert.notOk(form.$('.o_invoice_extract_box[data-id=3]').hasClass('o_hidden'),
            "box with ID 3 should be visible");
        assert.ok(form.$('.o_invoice_extract_box[data-id=4]').hasClass('o_hidden'),
            "box with ID 4 should be invisible");
        assert.ok(form.$('.o_invoice_extract_box[data-id=5]').hasClass('o_hidden'),
            "box with ID 5 should be invisible");

        assert.containsOnce($('body'), '.o_invoice_extract_button[data-field-name="invoice_id"]');
        await testUtils.dom.click($('.o_invoice_extract_button[data-field-name="invoice_id"]'), {'allowInvisible': true});

        assert.ok(form.$('.o_invoice_extract_box[data-id=1]').hasClass('o_hidden'),
            "box with ID 1 should become invisible");
        assert.ok(form.$('.o_invoice_extract_box[data-id=2]').hasClass('o_hidden'),
            "box with ID 2 should become invisible");
        assert.ok(form.$('.o_invoice_extract_box[data-id=3]').hasClass('o_hidden'),
            "box with ID 3 should become invisible");
        assert.notOk(form.$('.o_invoice_extract_box[data-id=4]').hasClass('o_hidden'),
            "box with ID 4 should become visible");
        assert.notOk(form.$('.o_invoice_extract_box[data-id=5]').hasClass('o_hidden'),
            "box with ID 5 should become visible");

        form.destroy();
    });

});
});
});
