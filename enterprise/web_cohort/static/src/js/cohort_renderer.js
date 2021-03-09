odoo.define('web_cohort.CohortRenderer', function (require) {
'use strict';

var AbstractRenderer = require('web.AbstractRenderer');
var core = require('web.core');
var field_utils = require('web.field_utils');

var qweb = core.qweb;

var CohortRenderer = AbstractRenderer.extend({
    className: 'o_cohort_view',
    events: _.extend({}, AbstractRenderer.prototype.events, {
        'click .o_cohort_row_clickable': '_onClickRow',
    }),
    /**
     * @override
     * @param {Widget} parent
     * @param {Object} state
     * @param {Object} params
     * @param {Object} params.measures
     * @param {Object} params.intervals
     * @param {string} params.dateStartString
     * @param {string} params.dateStopString
     * @param {string} params.mode
     * @param {string} params.timeline
     */
    init: function (parent, state, params) {
        this._super.apply(this, arguments);
        this.measures = params.measures;
        this.intervals = params.intervals;
        this.dateStartString = params.dateStartString;
        this.dateStopString = params.dateStopString;
        this.timeRangeDescription = params.timeRangeDescription;
        this.comparisonTimeRangeDescription = params.comparisonTimeRangeDescription;
        this.mode = params.mode;
        this.timeline = params.timeline;
    },
    /**
     * @override
     * @param {Object} state
     * @param {Object} params
     */
    updateState: function (state, params) {
        if (params.context !== undefined) {
            var timeRangeMenuData = params.context.timeRangeMenuData;
            if (timeRangeMenuData) {
                this.timeRangeDescription = timeRangeMenuData.timeRangeDescription;
                this.comparisonTimeRangeDescription = timeRangeMenuData.comparisonTimeRangeDescription;
            } else {
                this.timeRangeDescription = undefined;
                this.comparisonTimeRangeDescription = undefined;
            }
        }
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Used to determine whether or not to display the no content helper.
     *
     * @private
     * @returns {boolean}
     */
    _hasContent: function () {
        return this.state.report.rows.length ||
               (this.state.comparisonReport && this.state.comparisonReport.rows.length);
    },
    /**
     * @override
     * @private
     * @returns {Promise}
     */
    _render: function () {
        var self = this;
        if (!this._hasContent()) {
           // display the nocontent helper
            this.$el.empty().append(qweb.render('View.NoContentHelper'));
            return this._super.apply(this, arguments);
        }
        this.$el.empty().append(qweb.render('CohortView', {
            report: this.state.report,
            comparisonReport: this.state.comparisonReport,
            measure: this.measures[this.state.measure],
            interval: this.intervals[this.state.interval],
            date_start_string: this.dateStartString,
            date_stop_string: this.dateStopString,
            timeRangeDescription: this.timeRangeDescription,
            comparisonTimeRangeDescription: this.comparisonTimeRangeDescription,
            mode: this.mode,
            timeline: this.timeline,
            format_float: this._format_float,
            format_percentage: this._format_percentage,
        }));
        this.$('.o_cohort_highlight.o_cohort_value').tooltip({
            title: function () {
                var $cell = $(this);
                return qweb.render('CohortView.tooltip', {
                    period: $cell.data('period'),
                    count: $cell.data('count'),
                    measure: self.measures[self.state.measure],
                });
            },
        });
        return this._super.apply(this, arguments);
    },
    /**
     * @private
     * @param {float} value
     * @returns {string} formatted value with 1 digit
     */
    _format_float: function (value) {
        return field_utils.format.float(value, null, {
            digits: [42, 1],
        });
    },
    /**
     * @private
     * @param {float} value
     * @returns {string} formatted value with 1 digit
     */
    _format_percentage: function (value) {
        return field_utils.format.percentage(value, null, {
            digits: [42, 1],
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent} event
     */
    _onClickRow: function (event) {
        if (!$(event.target).hasClass('o_cohort_value')) {
            return;
        }
        var rowData = $(event.currentTarget).data();
        var rowIndex = rowData.row;
        var colIndex = $(event.target).data().col;
        var row = (rowData.type === 'data') ?
                    this.state.report.rows[rowIndex] :
                    this.state.comparisonReport.rows[rowIndex];
        var rowDomain = row ? row.domain : [];
        var cellContent = row ? row.columns[colIndex] : false;
        var cellDomain = cellContent ? cellContent.domain : [];

        var fullDomain = rowDomain.concat(cellDomain);
        if (cellDomain.length) {
            fullDomain.unshift('&');
        }
        if (fullDomain.length) {
            this.trigger_up('row_clicked', {domain: fullDomain});
        }
    },
});

return CohortRenderer;

});
