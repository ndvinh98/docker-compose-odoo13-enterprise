odoo.define('timesheet_grid.timesheet_uom', function (require) {
'use strict';

var gridRegistry = require('web_grid.widget_registry');
var gridWidgets = require('web_grid.widget');
var session = require('web.session');

/**
 * Extend the float toggle widget to set default value for timesheet
 * use case. The 'range' is different from the default one of the
 * native widget, and the 'factor' is forced to be the UoM timesheet
 * conversion.
 **/

var FloatFactorWidgetTimesheet = gridWidgets.FloatFactorWidget.extend({
	init: function(gridRenderer, fieldInfo, nodeOptions){
		this._super.apply(this, arguments);
		// force factor in format and parse options
        if (session.timesheet_uom_factor) {
            this.nodeOptions.factor = session.timesheet_uom_factor;
            this.formatOptions.factor = session.timesheet_uom_factor;
            this.parseOptions.factor = session.timesheet_uom_factor;
        }
	},
});

var FloatToggleWidgetTimesheet = gridWidgets.FloatToggleWidget.extend({
	init: function(gridRenderer, fieldInfo, nodeOptions){
        var hasRange = _.contains(_.keys(nodeOptions || {}), 'range');
		this._super.apply(this, arguments);
		// force factor in format and parse options
        if (session.timesheet_uom_factor) {
            this.nodeOptions.factor = session.timesheet_uom_factor;
            this.formatOptions.factor = session.timesheet_uom_factor;
            this.parseOptions.factor = session.timesheet_uom_factor;
        }
        // the range can be customized by setting the
        // option on the field in the view arch
		if (!hasRange) {
            var timesheet_range = [0.00, 1.00, 0.50];
            this.nodeOptions.range = timesheet_range;
            this.formatOptions.range = timesheet_range;
            this.parseOptions.range = timesheet_range;
			this.range = timesheet_range;
		}
	},
});

/**
 * Binding depending on Company Preference
 *
 * determine wich widget will be the timesheet one.
 * Simply match the 'timesheet_uom' widget key with the correct
 * implementation (float_time, float_toggle, ...). The default
 * value will be 'float_factor'.
**/
var FieldTimesheetUom = FloatFactorWidgetTimesheet;
var widgetName = 'timesheet_uom' in session ?
         session.timesheet_uom.timesheet_widget : 'float_factor';
if (widgetName === "float_toggle") {
	var FieldTimesheetUom = FloatToggleWidgetTimesheet;
} else if (widgetName === "float_factor") {
    var FieldTimesheetUom = FloatFactorWidgetTimesheet;
} else {
    var FieldTimesheetUom = (
        gridRegistry.get(widgetName) &&
        gridRegistry.get(widgetName).extend({})
    ) || FloatFactorWidgetTimesheet;
}

gridRegistry.add('timesheet_uom', FieldTimesheetUom);

return FieldTimesheetUom;
});

