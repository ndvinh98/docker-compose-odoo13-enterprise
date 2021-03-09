odoo.define('mrp.viewer_common', function (require) {
"use strict";

var mrpViewerCommon = {
    supportedFieldTypes: [],

    /**
     * @override
     */
    init: function (parent, name, record, options) {
        this._super.apply(this, arguments);
        this.iFrameId = (record.id + '.' + name).replace(/\./g, "_");
        this.invisible = this._isInvisible(parent);
        this.page = this.recordData['worksheet_page'] || this.page || 1;
    },
    /**
     * Gets called when parent is attached to DOM
     *
     * @override
     */
    on_attach_callback: function () {
        this._fixFormHeight();
        this._moveAndInitIFrame();
    },

    /**
     * Don't destroy this widget.
     *
     * @override
     */
    destroy: function () { },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Set Form top part to be fixed height to avoid flickers
     * If iFrame is hidden, show full height of form
     *
     * @private
     */
    _fixFormHeight: function () {
        var $form = $('.o_form_view.o_workorder_tablet');
        if ($form.length) {
            if (this._needFormHeightFix()) {
                $form.css('min-height', 'auto');
            } else {
                $form.css('min-height', '100%');
            }
        }
    },
    /**
     * We have to re_compute the value of the modifier because
     * it is not update yet by the rendered. So the state is the state
     * of the previous Widget. Usually, it's ok because the modifiers are applied
     * after the start(), but since we detached this widget from the framework, it's broken.
     *
     * @param {Object} parent
     * @private
     */
    _isInvisible: function (parent) {
        var self = this;
        var invisible = false;
        _.forEach(parent.allModifiersData, function (item) {
            if (item.node.attrs.name === self.name) {
                invisible = item.evaluatedModifiers[self.record.id].invisible;
                return;
            }
        });
        return invisible;
    },

    /**
     * Returns whether form height need to be fixed or not
     *
     * @private
     * @returns { boolean }
     */
    _needFormHeightFix: function () {
        var parent = this.getParent();
        var self = this;
        var invisible = _.all(parent.allModifiersData, function (item) {
            if (_.contains(['worksheet', 'worksheet_google_slide'], item.node.attrs.name)) {
                return item.evaluatedModifiers[self.record.id].invisible;
            }
            return true;
        });
        return !invisible;
    },

    /**
     * Move the iFrame out of the Odoo Form rendered
     * So that it will not be destroyed along the Form DOM
     * Also call _super.start after the DOM is moved to avoid double loading
     *
     * @private
     */
    _moveAndInitIFrame: function () {
        var $el = this.$el;
        var $iFrame = $el.find('iframe');
        var $container = $el.closest('.o_content');

        // Save the PDFViewerApp on the DOM element since this widget will be destroyed on any action
        $iFrame.on('load', function () {
            if (this.contentWindow.window.PDFViewerApplication) {
                $el.data('pdfViewer', this.contentWindow.window.PDFViewerApplication.pdfViewer);
            }
        });

        // Appended to the container and adjust CSS rules
        $el.closest('.workorder_pdf').appendTo($container);
        $container.css('display', 'flex');
        $container.css('flex-direction', 'column');

        // Add unique ID to get it back after the next destroy/start cycle
        $el.attr('id', this.iFrameId);

        // Initialize the Widget only when it has been moved in the DOM
        this._superStart.apply(this, arguments);
    },
};

return mrpViewerCommon;
});
