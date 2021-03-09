odoo.define('mail_enterprise.ThreadWindow', function (require) {
"use strict";

var ThreadWindow = require('mail.ThreadWindow');
var mobileMixins = require('web_mobile.mixins');

ThreadWindow.include(_.extend({}, mobileMixins.BackButtonEventMixin, {
    /**
     * We override destroy() to be able to call on_detach_callback at the very
     * last moment before detaching the ThreadWindow from the DOM.
     *
     * @override
     */
    destroy: function () {
        this.on_detach_callback();
        this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Call on_attach_callback when the ThreadWindow has been just attached to
     * the DOM.
     *
     * @override
     */
    appendTo: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self.on_attach_callback();
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Bind directly the thread window click-to-close method to the
     * 'backbutton' event.
     *
     * @private
     * @override
     */
    _onBackButton: ThreadWindow.prototype._onClickClose,
}));

});
