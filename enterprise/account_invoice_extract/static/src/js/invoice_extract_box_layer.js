odoo.define('account_invoice_extract.BoxLayer', function (require) {
"use strict";

var InvoiceExtractBox = require('account_invoice_extract.Box');

var Widget = require('web.Widget');

/**
 * This widget is layer on top of a page in the attachment preview, in which
 * boxes are inserted. This widget handles boxes of a given page.
 */
var InvoiceExtractBoxLayer = Widget.extend({
    events: {
        'click': '_onClick',
    },
    className: 'boxLayer',
    /**
     * @override
     * @param {Class} parent a class with EventDispatcherMixin
     * @param {Object} data
     * @param {Object[]} data.boxesData list of all boxes data. Should filter
     *   on boxes that are linked to this box layer.
     * @param {string} data.mode either 'pdf' or 'img'
     * @param {integer} [data.pageNum=0]
     * @param {$.Element} [data.$buttons] mandatory in mode 'pdf': container of
     *   the field buttons, which is useful in adapt the height of box layer
     *   accordingly.
     * @param {$.Element} data.$page useful in order to auto resize box layer
     *   accordingly when attached to the DOM.
     * @param {$.Element} [data.$textLayer] mandatory in mode 'pdf': useful in
     *   order to size box layer similarly to text layer.
     */
    init: function (parent, data) {
        var self = this;
        this._super.apply(this, arguments);

        this._boxes = [];
        this._boxesData = data.boxesData;
        this._mode = data.mode;
        this._pageNum = data.pageNum || 0;

        this._$buttons = data.$buttons;
        this._$page = data.$page;
        this._$textLayer = data.$textLayer;

        // filter boxes data on current box layer
        this._boxesData = _.filter(this._boxesData, function (boxData) {
            return boxData.page === self._pageNum;
        });
    },
    /**
     * @override
     */
    start: function () {
        var self = this;
        // adapt box layer size
        if (this._isOnPDF()) {
            this.el.style.width = this._$textLayer[0].style.width;
            this.el.style.height = this._$textLayer[0].style.height;
            this._$page[0].style.height = 'calc(100% - ' + this._$buttons.height() + 'px)';
        } else if (this._isOnImg()) {
            this.el.style.width = this._$page[0].clientWidth + 'px';
            this.el.style.height = this._$page[0].clientHeight + 'px';
            this.el.style.left = this._$page[0].offsetLeft + 'px';
            this.el.style.top = this._$page[0].offsetTop + 'px';
        }

        // make boxes (hidden by default)
        this._boxes = [];
        _.forEach(this._boxesData, function (boxData) {
            var box = new InvoiceExtractBox(self, _.extend({}, boxData, {
                $boxLayer: self.$el,
            }));
            box.appendTo(self.$el).then(function () {
                box.do_hide();
                self._boxes.push(box);
            });
        });

        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Shows the boxes in this box layer, based on the selected field.
     *
     * @param {Object} params
     * @param {string} params.fieldName only show boxes of given field name
     */
    displayBoxes: function (params) {
        var selectedFieldName = params.fieldName;
        _.each(this._boxes, function (box) {
            if (box.getFieldName() === selectedFieldName) {
                box.do_show();
            } else {
                box.do_hide();
            }
        });
    },

    /**
     * Sets the textLayer for this box layer.
     *
     * @param {Object} params
     * @param {$.Element} [params.$textLayer] the new text layer
     */
    setTextLayer: function(params) {
        var $textLayer = params.$textLayer;
        this._$textLayer = $textLayer;
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @returns {boolean}
     */
    _isOnImg: function () {
        return this._mode === 'img';
    },
    /**
     * @private
     * @returns {boolean}
     */
    _isOnPDF: function () {
        return this._mode === 'pdf';
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Called when clicking on the box layer.
     * This function should handle click away from a selected box.
     * This is ignored if the click on a box.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onClick: function (ev) {
        this.trigger_up('click_invoice_extract_box_layer');
    },
});

return InvoiceExtractBoxLayer;

});
