odoo.define('web.FieldColorPicker', function (require) {
"use strict";

var basic_fields = require('web.basic_fields');
var FieldInteger = basic_fields.FieldInteger;
var field_registry = require('web.field_registry');

var core = require('web.core');
var QWeb = core.qweb;

var FieldColorPicker = FieldInteger.extend({
    /**
     * Prepares the rendering, since we are based on an input but not using it
     * setting tagName after parent init force the widget to not render an input
     *
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        this.tagName = 'div';
    },
    /**
     * Render the widget when it is edited.
     *
     * @override
     */
    _renderEdit: function () {
        this.$el.html(QWeb.render('web.ColorPicker'));
        this._setupColorPicker();
        this._highlightSelectedColor();
    },
    /**
     * Render the widget when it is NOT edited.
     *
     * @override
     */
    _renderReadonly: function () {
        this.$el.html(QWeb.render('web.ColorPickerReadonly', {active_color: this.value,}));
        this.$el.on('click', 'a', function(ev){ ev.preventDefault(); });
    },
    /**
     * Render the kanban colors inside first ul element.
     * This is the same template as in KanbanRecord.
     *
     * <a> elements click are bound to _onColorChanged
     *
     */
    _setupColorPicker: function () {
        var $colorpicker = this.$('ul');
        if (!$colorpicker.length) {
            return;
        }
        $colorpicker.html(QWeb.render('KanbanColorPicker'));
        $colorpicker.on('click', 'a', this._onColorChanged.bind(this));
    },
    /**
     * Returns the widget value.
     * Since NumericField is based on an input, but we don't use it,
     * we override this function to use the internal value of the widget.
     *
     *
     * @override
     * @returns {string}
     */
    _getValue: function (){
        return this.value;
    },
    /**
     * Listener in edit mode for click on a color.
     * The actual color can be found in the data-color
     * attribute of the target element.
     *
     * We re-render the widget after the update because
     * the selected color has changed and it should
     * be reflected in the ui.
     *
     * @param ev
     */
    _onColorChanged: function(ev) {
        ev.preventDefault();
        var color = null;
        if(ev.currentTarget && ev.currentTarget.dataset && ev.currentTarget.dataset.color){
            color = ev.currentTarget.dataset.color;
        }
        if(color){
            this.value = color;
            this._onChange();
            this._renderEdit();
        }
    },
    /**
     * Helper to modify the active color's style
     * while in edit mode.
     *
     */
    _highlightSelectedColor: function(){
        try{
            $(this.$('li')[parseInt(this.value)]).css('border', '2px solid teal');
        } catch(err) {

        }
    },
});

field_registry.add('color_picker', FieldColorPicker);

return FieldColorPicker;

});
