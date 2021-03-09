odoo.define('stock_enterprise.ReportGridView', function (require) {
'use strict';

var GridView = require('web_grid.GridView');
var ReportGridController = require('stock_enterprise.ReportGridController');
var viewRegistry = require('web.view_registry');

var ReportGridView = GridView.extend({
    config: _.extend({}, GridView.prototype.config, {
        Controller: ReportGridController,
    }),
});

viewRegistry.add('stock_enterprise_report_grid', ReportGridView);

return ReportGridView;

});
