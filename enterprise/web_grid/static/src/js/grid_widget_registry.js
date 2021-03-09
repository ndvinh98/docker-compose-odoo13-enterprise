odoo.define('web_grid.widget_registry', function (require) {
"use strict";

var Registry = require('web.Registry');

return new Registry();
});



odoo.define('web_grid._widget_registry', function(require) {
"use strict";

var grid_widget = require('web_grid.widget');
var registry = require('web_grid.widget_registry');

// Basic fields
registry
    .add('float_factor', grid_widget.FloatFactorWidget)
    .add('float_time', grid_widget.FloatTimeWidget)
    .add('float_toggle', grid_widget.FloatToggleWidget)
});
