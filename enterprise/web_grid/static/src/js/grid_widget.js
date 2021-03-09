odoo.define('web_grid.widget', function (require) {
"use strict";

var core = require('web.core');
var Class = require('web.Class');
var mixins = require('web.mixins');
var utils = require('web.utils');
var field_utils = require('web.field_utils');
var h = require('snabbdom.h');

/**
 * Grid Widget
 *
 * A grid widget is a set of 3 methods:
 *  - format: responsible to format the value, as the traditionnal
 *          widget does, using the field_utils methods.
 *  - parse: responsible to parse the value. Same as 'format'.
 *  - render: returning a virtual dom, using snabbdom lib, as the grid view
 *          use.
 * Each of these method will be called binded on the grid view, so `this`
 * will be the grid renderer instance.
 * A grid widget is responsible of formatting and the DOM of what will be
 * displayed in the inner cell.
 *
 * The widget should also trigger up `grid_cell_edited` event when a change
 * value has to be committed, and `grid_cell_refresh` when the appearance of
 * the widget should be modified, without sending the value to the server.
 * Those 2 events will be handled by the widget parent (aka the GridRenderer).
 **/

var BaseGridWidget = Class.extend(mixins.EventDispatcherMixin, {
    init: function(parent, fieldInfo, nodeOptions){
        mixins.EventDispatcherMixin.init.call(this);
        this.setParent(parent);
        this.field = fieldInfo;

        // formatType is used to determine which format (and parse) functions
        // to call to format the field's value to insert into the DOM. If the widget
        // does no specify one, the field type will be taken as fallback.
        if (!this.formatType) {
            this.formatType = this.field.type;
        }

        // formatOptions (resp. parseOptions) is a dict of options passed to
        // calls to the format (resp. parse) function.
        this.nodeOptions = nodeOptions || {};
        this.formatOptions = nodeOptions || {};
        this.parseOptions = nodeOptions || {};
    },
    format: function(value) {
        return field_utils.format[this.formatType](value, {}, this.formatOptions);
    },
    parse: function(value) {
        return field_utils.parse[this.formatType](value, {}, this.parseOptions);
    },
    render: function(isReadonly, path) {
        var self = this;

        return function(value) {
            if (isReadonly) {
                return self._renderReadonly(self.format(value), path);
            } else {
                return self._renderEdit(self.format(value), path);
            }
        }
    },
    _renderEdit: function (formattedValue, path) {
        return h('div.o_grid_input', {attrs: {contentEditable: "true"}}, formattedValue);
    },
    _renderReadonly: function (formattedValue, path) {
        return h('div.o_grid_show', formattedValue);
    },
});

var FloatFactorWidget = BaseGridWidget.extend({
    formatType: 'float_factor',
});

var FloatTimeWidget = BaseGridWidget.extend({
    formatType: 'float_time',
});

var FloatToggleWidget = BaseGridWidget.extend({
    formatType: 'float_factor',
    init: function(gridRenderer, fieldInfo, nodeOptions){
        this._super.apply(this, arguments);
        // default values
        if (!nodeOptions.factor){
            this.nodeOptions.factor = 1;
            this.formatOptions.factor = 1;
            this.parseOptions.factor = 1;
        }
        var range = [0.0, 0.5, 1.0];
        if (this.nodeOptions.range){
            range = this.nodeOptions.range;
        }
        this.range = range;
    },
    _renderEdit: function (formattedValue, path) {
        var self = this;

        var range = this.range;
        var current = formattedValue;

        // handlers
        function onClick () {
            // current is in user's format
            var currentFloat = field_utils.parse['float'](current);
            var closest = utils.closestNumber(currentFloat, range);
            var closest_index = _.indexOf(range, closest);
            var next_index = closest_index+1 < range.length ? closest_index+1 : 0;

            current = range[next_index];
            current = field_utils.format['float'](current, {}, self.formatOptions); // format the string to display on the button

            self.trigger_up('grid_cell_refresh', {
                selector: 'button',
                formattedValue: current.toString(),
                path: path,
            });
        }
        function triggerSaveChange () {
            self.trigger_up('grid_cell_edited', {
                path: path,
            });
        }

        // add 'disabled' class in readonly mode
        var classes = '.o_grid_float_toggle.btn.btn-default.btn-block';

        return h('button' + classes, {
            on: {
                'click': onClick,
                'blur': triggerSaveChange,
            },
            attrs: {
                'type': 'button',
                'data-value': parseFloat(formattedValue),
            }
        }, formattedValue);
    },
    _renderReadonly: function (formattedValue, path) {
        // add 'disabled' class in readonly mode
        var classes = '.o_grid_float_toggle.btn.btn-default.btn-block.disabled';
        return h('button' + classes, {
            attrs: {
                'type': 'button',
                'data-value': parseFloat(formattedValue),
            }
        }, formattedValue);
    },
});

return {
    FloatFactorWidget: FloatFactorWidget,
    FloatTimeWidget: FloatTimeWidget,
    FloatToggleWidget: FloatToggleWidget,
};

});
