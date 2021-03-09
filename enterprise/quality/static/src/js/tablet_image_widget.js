odoo.define('quality.tablet_image_field', function (require) {
    "use strict";

var basic_fields = require('web.basic_fields');
var core = require('web.core');
var field_registry = require('web.field_registry');
var FieldBinaryImage = basic_fields.FieldBinaryImage;

var QWeb = core.qweb;

var TabletImage = FieldBinaryImage.extend({
    template: 'FieldBinaryTabletImage',
    events: _.extend({}, FieldBinaryImage.prototype.events, {
        'click .o_form_image_controls': '_onOpenPreview',
        'click .o_input_file': function (ev) {
            ev.stopImmediatePropagation();
        },
    }),

    /**
     * After render, hide the controls if no image is set
     *
     * @return {Deferred}
     * @override
     * @private
     */
    _render: function (){
        var def = this._super.apply(this, arguments);
        this.$('.o_form_image_controls').toggleClass('o_invisible_modifier', !this.value);
        return def;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Just prevent propagation of click event on the overlay
     * that opens the preview when the Trash button is clicked
     *
     * @override
     */
    _onClearClick: function (ev){
        ev.stopImmediatePropagation();
        this._super.apply(this, arguments);
    },

    /**
     * Open the image preview
     *
     * @private
     */
    _onOpenPreview: function (ev) {
        ev.stopPropagation();
        this.src = this.$el.find('>img').attr('src');

        this.$modal = $(QWeb.render('FieldBinaryTabletImage.Preview', {
            url: this.src
        }));
        this.$modal.click(this._onClosePreview.bind(this));
        this.$modal.appendTo('body');
        this.$modal.modal('show');
    },

    /**
     * Close the image preview
     *
     * @private
     */
    _onClosePreview: function (ev) {
        ev.preventDefault();
        this.$modal.remove();
        $('.modal-backdrop').remove();
    },
});

field_registry.add('tablet_image', TabletImage);

return {
    TabletImage: TabletImage,
}
})
