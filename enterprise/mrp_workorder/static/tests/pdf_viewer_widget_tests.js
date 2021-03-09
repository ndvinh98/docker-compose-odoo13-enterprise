odoo.define('mrp_pdf_viewer_widget_no_reload.tests', function (require) {
    "use strict";

    var FormView = require('web.FormView');
    var testUtils = require("web.test_utils");
    var createView = testUtils.createView;

    QUnit.module('mrp_pdf_viewer_widget_no_reload', {
        beforeEach: function () {
            var attrs = "{'invisible': [('worksheet', '=', False)]}";
            this.formArch =
                '<form>' +
                    '<field name="worksheet" widget="mrp_pdf_viewer_no_reload" attrs="'+attrs+'"/>' +
                '</form>';

            this.data = {
                'mrp.workorder': {
                    fields: {
                        worksheet: { string: "worksheet", type: "char" },
                    },
                    records: [
                        {
                            id: 1,
                            worksheet: '10 kb',
                        },
                        {
                            id: 2,
                            worksheet: false,
                        },
                    ],
                },
            };
        },
    });

    QUnit.test("Pdf Viewer Widget No Reload : Visible PDF", async function (assert) {
        assert.expect(4);

        var form = await createView({
            View: FormView,
            model: 'mrp.workorder',
            data: this.data,
            arch: this.formArch,
            res_id: 1,
        });

        var renderer = form.renderer;
        assert.strictEqual(!!renderer, true, "There should be a renderer linked to the form");

        var recordWidgets = renderer.allFieldWidgets[form.handle];
        assert.strictEqual(!!recordWidgets, true, "There should be widgets for this record");
        assert.strictEqual(recordWidgets.length, 1, "There should be only one widget");
        assert.isVisible(recordWidgets[0]);

        form.destroy();
    });

    QUnit.test("Pdf Viewer Widget No Reload : Invisible PDF", async function (assert) {
        assert.expect(4);

        var form = await createView({
            View: FormView,
            model: 'mrp.workorder',
            data: this.data,
            arch: this.formArch,
            res_id: 2,
        });
        var renderer = form.renderer;
        assert.strictEqual(!!renderer, true, "There should be a renderer linked to the form");

        var recordWidgets = renderer.allFieldWidgets[form.handle];
        assert.strictEqual(!!recordWidgets, true, "There should be widgets for this record");
        assert.strictEqual(recordWidgets.length, 1, "There should be only one widget");
        assert.isNotVisible(recordWidgets[0]);

        form.destroy();
    });
});
