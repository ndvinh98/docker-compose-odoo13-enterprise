odoo.define('account_asset.AssetFormView', function(require) {
"use strict";

var FormRenderer = require('web.FormRenderer');
var FormView = require('web.FormView');
var core = require('web.core');
var viewRegistry = require('web.view_registry');

var _t = core._t;

var AccountAssetFormRenderer = FormRenderer.extend({
    events: _.extend({}, FormRenderer.prototype.events, {
        'click .add_original_move_line': '_onAddOriginalMoveLine',
    }),
    /*
     * Open the m2o item selection from another button
     */
    _onAddOriginalMoveLine: function(ev) {
        _.find(this.allFieldWidgets[this.state.id], x => x['name'] == 'original_move_line_ids').onAddRecordOpenDialog();
    },
});

var AssetFormView = FormView.extend({
    config: _.extend({}, FormView.prototype.config, {
        Renderer: AccountAssetFormRenderer,
    }),
});

viewRegistry.add("asset_form", AssetFormView);
return AssetFormView;

});
