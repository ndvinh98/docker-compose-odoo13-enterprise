odoo.define('mrp_embed_viewer_widget_no_reload.tests', function (require) {
    "use strict";

    var FormView = require('web.FormView');
    var testUtils = require("web.test_utils");
    var createView = testUtils.createView;

    QUnit.module('mrp_embed_viewer_widget_no_reload', {
        beforeEach: function () {
            var attrs = "{'invisible': [('worksheet', '=', False)]}";
            this.formArch =
                '<form>' +
                    '<field name="worksheet" widget="mrp_embed_viewer_no_reload" attrs="'+attrs+'"/>' +
                '</form>';

            this.data = {
                'mrp.workorder': {
                    fields: {
                        worksheet: { string: "worksheet", type: "char" },
                        worksheet_slide: { string: "worksheet slide", type: "char" },
                    },
                    records: [
                        {
                            id: 1,
                            worksheet: 'https://docs.google.com/presentation/d/1yVipMA_MFXDnxl8G_LyBPdmB7sHsLXoTT-Pn6dx6Em0/edit#slide=id.p'
                        },
                        {
                            id: 2,
                            worksheet: false
                        },
                    ],
                },
            };
        },
    });

    QUnit.test("Embedded Viewer Widget No Reload : Visible Slide", async function (assert) {
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

    QUnit.test("Embedded Viewer Widget No Reload : Invisible Slide", async function (assert) {
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
