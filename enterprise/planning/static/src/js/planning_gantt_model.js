odoo.define('planning.PlanningGanttModel', function (require) {
    "use strict";

    var GanttModel = require('web_gantt.GanttModel');
    var _t = require('web.core')._t;

    var PlanningGanttModel = GanttModel.extend({
        /**
         * Overrides the load method to inject
         * a context which will be sent to
         * rpc requests.
         *
         * It allows to check if we want to do
         * the custom read_group in planning.py
         *
         * @override
         * @param {Object} params
         * @returns {Promise}
         */
        load: function (params) {
            params.context['prepend_open_shifts'] = true;
            return this._super.apply(this, arguments);
        },
        /**
         * @private
         * @override
         * @returns {Object[]}
         */
        _generateRows: function (params) {
            var rows = this._super(params);
            // is the data grouped by?
            if(params.groupedBy && params.groupedBy.length){
                // in the last row is the grouped by field is null
                if(rows && rows.length && rows[rows.length - 1] && !rows[rows.length - 1].resId){
                    // then make it the first one
                    rows.unshift(rows.pop());
                }
            }
            // rename 'Undefined Employee' into 'Open Shifts'
            _.each(rows, function(row){
                if(row.groupedByField === 'employee_id' && !row.resId){
                    row.name = _t('Open Shifts');
                }
            });
            return rows;
        },
    });

    return PlanningGanttModel;
});
