odoo.define('account_consolidation.GridView', function (require) {
    "use strict";

    var WebGridView = require('web_grid.GridView');
    var viewRegistry = require('web.view_registry');
    var ConsolidationGridController = require('account_consolidation.GridController');
    var ConsolidationGridRenderer = require('account_consolidation.GridRenderer');

    var ConsolidationGridView = WebGridView.extend({
        // Needed to allow grid to work without ranges
        _default_context: {'name': 'bla'},
        _extract_ranges: function() {
            return [this._default_context];
        },
        config: _.extend({}, WebGridView.prototype.config, {
            Renderer: ConsolidationGridRenderer,
            Controller: ConsolidationGridController
        })
    });

    viewRegistry.add('consolidation_grid', ConsolidationGridView);

    return ConsolidationGridView;
});
