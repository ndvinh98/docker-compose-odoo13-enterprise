odoo.define('account_consolidation.GridRenderer', function (require) {
    "use strict";

    var WebGridRenderer = require('web_grid.GridRenderer');
    var h = require('snabbdom.h');
    var core = require('web.core');
    var _t = core._t;

    return WebGridRenderer.extend({
        /**
         * @private
         * @param {any} cell_value
         * @param {boolean} isReadonly
         * @param {any} classmap
         * @param {any} path
         * @returns {snabbdom}
         */
        _renderCellContent: function (cell_value, isReadonly, classmap, path) {
            classmap.o_grid_cell_empty = cell_value === 0;
            return this._super.apply(this, arguments);
        },

        /**
         * Return a node for the column total if needed
         * If the range is day this column is not rendered
         * We overwrite this method because we want to add a display total in red
         * in the footer total in case the total is != 0.
         * @private
         * @param {String} node node cell
         * @param {String} value the value to put in the cell
         * @return {snabbdom[]}
         */
        _renderGridColumnTotalCell: function (node, value) {
            var self = this;
            if (node === 'td') {
                if (value.length === 0) {
                    return [h(node, self._format(0.0))];
                }
                return [h('td.o_not_zero', value)];
            }
            return [h(node, value)];
        }
    });

});
