odoo.define('web_mobile.FormRenderer', function (require) {
"use strict";

var FormRenderer = require('web.FormRenderer');

var ContactSync = require('web_mobile.ContactSync');

/**
 * Include the FormRenderer to instanciate widget ContactSync.
 * The method will be automatically called to replace the tag <contactsync>.
 */
FormRenderer.include({

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /** We always return a $el even if it's asynchronous (see _renderFieldWidget).
     *
     * @private
     * @returns {jQueryElement}
     */
    _renderTagContactsync: function () {
        var $el = $('<div>');
        var widget = new ContactSync(this, {
            res_id: this.state.res_id,
            res_model: this.state.model,
        });
        // Prepare widget rendering and save the related promise
        var prom = widget._widgetRenderAndInsert(function () { });
        prom.then(function () {
            $el.replaceWith(widget.$el);
        });

        this.widgets.push(widget);
        this.defs.push(prom);

        return $el;
    },
});

});
