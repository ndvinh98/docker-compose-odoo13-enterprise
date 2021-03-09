odoo.define('mrp_workorder.PDFViewerNoReload', function (require) {
"use strict";

var FormRenderer = require('web.FormRenderer');
var FormView = require('web.FormView');
var viewRegistry = require('web.view_registry');


var PDFViewerNoReloadRenderer = FormRenderer.extend({
    init: function () {
        this._super.apply(this, arguments);
        this.workorderViewer = undefined;
    },
    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------
    /**
     * Overrides the function to make the workorder_pdf's render full-cycle only
     * the first time. After that, we call its renderer (to trigger `start`
     * method of `FieldPdfViewerNoReload`) but return nothing to avoid to add it
     * again in the DOM.
     *
     * @override
     * @private
     */
    _renderNode: function (node) {
        if (node.tag === 'div' && node.attrs.class === 'workorder_pdf') {
            if (!this.workorderViewer) {
                this.workorderViewer = this._super.apply(this, arguments);
                return this.workorderViewer;
            } else {
                this._super.apply(this, arguments);
                return;
            }
        } else {
            return this._super.apply(this, arguments);
        }
    },
});

var TabletPDFViewer = FormView.extend({
    config: _.extend({}, FormView.prototype.config, {
        Renderer: PDFViewerNoReloadRenderer,
    }),
});

viewRegistry.add('tablet_pdf_viewer', TabletPDFViewer);

return {
    PDFViewerNoReloadRenderer: PDFViewerNoReloadRenderer,
    TabletPDFViewer: TabletPDFViewer,
};
});
