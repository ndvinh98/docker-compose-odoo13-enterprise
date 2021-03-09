odoo.define('documents.DocumentsInspectorMobile', function (require) {
"use strict";

var config = require('web.config');

if (!config.device.isMobile) {
    return;
}

var DocumentsInspector = require('documents.DocumentsInspector');

DocumentsInspector.include({
    template: 'documents.DocumentsInspectorMobile',

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Return the insternal state of the widget.
     * Add the 'open' status to the state.
     *
     * @override
     * @returns {Object}
     */
    getLocalState: function () {
        return _.extend({}, this._super.apply(this, arguments), {
            open: this.el.getAttribute('open') === '',
        });
    },
    /**
     * Restore the given state.
     *
     * @override
     * @param {Object} state
     * @param {integer} state.open the 'open' status to restore
     */
    setLocalState: function (state) {
        this._super.apply(this, arguments);
        if (state.open) {
            this.open();
        }
    },
    /**
     * Open the inspector.
     */
    open: function () {
        this.el.setAttribute('open', '');
    },
});

});
