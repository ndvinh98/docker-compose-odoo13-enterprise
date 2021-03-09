odoo.define('web_mobile.Dialog', function (require) {
"use strict";

var Dialog = require('web.Dialog');
var mobileMixins = require('web_mobile.mixins');

Dialog.include(_.extend({}, mobileMixins.BackButtonEventMixin, {
    /**
     * As the Dialog is based on Bootstrap's Modal we don't handle ourself when
     * the modal is detached from the DOM and we have to rely on their events
     * to call on_detach_callback.
     * The 'hidden.bs.modal' is triggered when the hidding animation (if any)
     * is finished and the modal is detached from the DOM.
     *
     * @override
     */
    willStart: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self.$modal.on('hidden.bs.modal', self.on_detach_callback.bind(self));
        });
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * This method is called after the modal has been attached to the DOM and
     * started appearing.
     *
     * @override
     */
    opened: function () {
        return this._super.apply(this, arguments).then(this.on_attach_callback.bind(this));
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Close the current dialog on 'backbutton' event.
     *
     * @private
     * @override
     * @param {Event} ev
     */
    _onBackButton: function () {
        this.close();
    },
}));

});
