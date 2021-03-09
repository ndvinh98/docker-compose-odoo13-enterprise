odoo.define('mrp_workorder.pdf_viewer_no_reload', function (require) {
"use strict";

var fieldRegistry = require('web.field_registry');
var basicFields = require('web.basic_fields');
var mrpViewerCommon = require('mrp.viewer_common');

var FieldPdfViewer = basicFields.FieldPdfViewer;

/**
 * /!\/!\/!\ WARNING /!\/!\/!\
 * Do not use this widget else where
 * Due to limitation of the framework, a lot of hacks have been used
 *
 * Override of the default PDF Viewer Widget to prevent reload of the iFrame content
 * on any action (typically, click on a button)
 */

var FieldPdfViewerNoReload = FieldPdfViewer.extend(mrpViewerCommon, {
    template: 'FieldPdfViewer',

    /**
     * Do not start the widget in the normal lifecycle
     * The first start will be called in the on_attach_callback
     * After that, this start will just update the active page
     *
     * @override
     */
    start: function () {
        this._superStart = this._super;
        var $existing = $('#' + this.iFrameId);

        if ($existing.length) {
            if (!this.invisible){
                this.pdfViewer = $existing.data('pdfViewer');
                this._goToPage(this.page);
            }
            $existing.toggleClass('o_invisible_modifier', this.invisible);
        }

        this._fixFormHeight();

        return Promise.resolve();
    },

    /**
     * Try to go to page
     * The PDFViewerApp will try to reset to the last viewed page
     * several times when the iFrame resizes, so we have to wait a few ms,
     * then try to scroll. Could be called several times.
     *
     * TODO: Find a better way to do this ...
     *
     * @param {string} page
     * @private
     */
    _goToPage: function (page){
        var self = this;
        if (self.pdfViewer && page !== self.pdfViewer.currentPageNumber){
            setTimeout(function (){
                self.pdfViewer.currentPageNumber = page;
                self._goToPage(page);
            }, 200);
        } else {
            this._checkCorrectPage(page);
        }
    },

    /**
     * After Goto page, it's possible that the PDFViewerApp will
     * still reset the page to last viewed. So this function will
     * check after a longer time if the page is still set to what
     * we want.
     *
     * @param {string} page
     * @private
     */
    _checkCorrectPage: function (page) {
        var self = this;
        setTimeout(function () {
            if (self.pdfViewer && page !== self.pdfViewer.currentPageNumber) {
                self._goToPage(page);
            }
        }, 500);
    },
});

fieldRegistry.add('mrp_pdf_viewer_no_reload', FieldPdfViewerNoReload);

return FieldPdfViewerNoReload;
});