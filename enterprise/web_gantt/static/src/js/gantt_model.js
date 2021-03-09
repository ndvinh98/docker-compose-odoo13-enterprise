odoo.define('web_gantt.GanttModel', function (require) {
"use strict";

var AbstractModel = require('web.AbstractModel');
var concurrency = require('web.concurrency');
var core = require('web.core');
var fieldUtils = require('web.field_utils');
var session = require('web.session');

var _t = core._t;


var GanttModel = AbstractModel.extend({
    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);

        this.dp = new concurrency.DropPrevious();
        this.mutex = new concurrency.Mutex();
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Collapses the given row.
     *
     * @param {string} rowId
     */
    collapseRow: function (rowId) {
        this.allRows[rowId].isOpen = false;
    },
    /**
     * Collapses all rows (first level only).
     */
    collapseRows: function () {
        this.ganttData.rows.forEach(function (group) {
            group.isOpen = false;
        });
    },
    /**
     * Convert date to server timezone
     *
     * @param {Moment} date
     * @returns {string} date in server format
     */
    convertToServerTime: function (date) {
        var result = date.clone();
        if (!result.isUTC()) {
            result.subtract(session.getTZOffset(date), 'minutes');
        }
        return result.locale('en').format('YYYY-MM-DD HH:mm:ss');
    },
    /**
     * @override
     * @param {string} [rowId]
     * @returns {Object} the whole gantt data if no rowId given, the given row's
     *   description otherwise
     */
    get: function (rowId) {
        if (rowId) {
            return this.allRows[rowId];
        } else {
            return _.extend({}, this.ganttData);
        }
    },
    /**
     * Expands the given row.
     *
     * @param {string} rowId
     */
    expandRow: function (rowId) {
        this.allRows[rowId].isOpen = true;
    },
    /**
     * Expands all rows.
     */
    expandRows: function () {
        var self = this;
        Object.keys(this.allRows).forEach(function (rowId) {
            var row = self.allRows[rowId];
            if (row.isGroup) {
                self.allRows[rowId].isOpen = true;
            }
        });
    },
    /**
     * @override
     * @param {Object} params
     * @param {Object} params.context
     * @param {Object} params.colorField
     * @param {string} params.dateStartField
     * @param {string} params.dateStopField
     * @param {string[]} params.decorationFields
     * @param {string[]} params.defaultGroupBy
     * @param {boolean} params.displayUnavailability
     * @param {Array[]} params.domain
     * @param {Object} params.fields
     * @param {string[]} params.groupedBy
     * @param {Moment} params.initialDate
     * @param {string} params.modelName
     * @param {string} params.scale
     * @returns {Promise<any>}
     */
    load: function (params) {
        this.modelName = params.modelName;
        this.fields = params.fields;
        this.domain = params.domain;
        this.context = params.context;
        this.decorationFields = params.decorationFields;
        this.colorField = params.colorField;
        this.progressField = params.progressField;
        this.consolidationParams = params.consolidationParams;
        this.collapseFirstLevel = params.collapseFirstLevel;
        this.displayUnavailability = params.displayUnavailability;

        this.defaultGroupBy = params.defaultGroupBy ? [params.defaultGroupBy] : [];
        if (!params.groupedBy || !params.groupedBy.length) {
            params.groupedBy = this.defaultGroupBy;
        }

        this.ganttData = {
            dateStartField: params.dateStartField,
            dateStopField: params.dateStopField,
            groupedBy: params.groupedBy,
            fields: params.fields,
        };
        this._setRange(params.initialDate, params.scale);
        return this._fetchData().then(function () {
            // The 'load' function returns a promise which resolves with the
            // handle to pass to the 'get' function to access the data. In this
            // case, we don't want to pass any argument to 'get' (see its API).
            return Promise.resolve();
        });
    },
    /**
     * @param {any} handle
     * @param {Object} params
     * @param {Array[]} params.domain
     * @param {string[]} params.groupBy
     * @param {string} params.scale
     * @param {Moment} params.date
     * @returns {Promise<any>}
     */
    reload: function (handle, params) {
        if ('scale' in params) {
            this._setRange(this.ganttData.focusDate, params.scale);
        }
        if ('date' in params) {
            this._setRange(params.date, this.ganttData.scale);
        }
        if ('domain' in params) {
            this.domain = params.domain;
        }
        if ('groupBy' in params) {
            if (params.groupBy && params.groupBy.length) {
                this.ganttData.groupedBy = params.groupBy.filter(
                    groupedByField => {
                        var fieldName = groupedByField.split(':')[0]
                        return fieldName in this.fields && this.fields[fieldName].type.indexOf('date') === -1;
                    }
                );
                if(this.ganttData.groupedBy.length !== params.groupBy.length){
                    this.do_warn(_t('Invalid group by'), _t('Grouping by date is not supported, ignoring it'));
                }
            } else {
                this.ganttData.groupedBy = this.defaultGroupBy;
            }
        }
        return this._fetchData()
    },
    /**
     * Create a copy of a task with defaults determined by schedule.
     *
     * @param {integer} id
     * @param {Object} schedule
     * @returns {Promise}
     */
    copy: function (id, schedule) {
        var self = this;
        const defaults = this.rescheduleData(schedule);
        return this.mutex.exec(function () {
            return self._rpc({
                model: self.modelName,
                method: 'copy',
                args: [id, defaults],
                context: self.context,
            });
        });
    },
    /**
     * Reschedule a task to the given schedule.
     *
     * @param {integer} id
     * @param {Object} schedule
     * @param {boolean} isUTC
     * @returns {Promise}
     */
    reschedule: function (ids, schedule, isUTC) {
        var self = this;
        if (!_.isArray(ids)) {
            ids = [ids];
        }
        const data = this.rescheduleData(schedule, isUTC);
        return this.mutex.exec(function () {
            return self._rpc({
                model: self.modelName,
                method: 'write',
                args: [ids, data],
                context: self.context,
            });
        });
    },
    /**
     * @param {Object} schedule
     * @param {boolean} isUTC
     */
    rescheduleData: function (schedule, isUTC) {
        const allowedFields = [
            this.ganttData.dateStartField,
            this.ganttData.dateStopField,
            ...this.ganttData.groupedBy
        ];

        const data = _.pick(schedule, allowedFields);

        let type;
        for (let k in data) {
            type = this.fields[k].type;
            if (data[k] && (type === 'datetime' || type === 'date') && !isUTC) {
                data[k] = this.convertToServerTime(data[k]);
            }
        };
        return data
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Fetches records to display (and groups if necessary).
     *
     * @private
     * @returns {Deferred}
     */
    _fetchData: function () {
        var self = this;
        var domain = this._getDomain();
        var context = _.extend(this.context, {'group_by': this.ganttData.groupedBy});

        var groupsDef;
        if (this.ganttData.groupedBy.length) {
            groupsDef = this._rpc({
                model: this.modelName,
                method: 'read_group',
                fields: this._getFields(),
                domain: domain,
                context: context,
                groupBy: this.ganttData.groupedBy,
                orderBy: this.ganttData.groupedBy.map(function (f) { return {name: f}; }),
                lazy: this.ganttData.groupedBy.length === 1,
            });
        }

        var dataDef = this._rpc({
            route: '/web/dataset/search_read',
            model: this.modelName,
            fields: this._getFields(),
            context: context,
            domain: domain,
        });

        return this.dp.add(Promise.all([groupsDef, dataDef])).then(function (results) {
            var groups = results[0];
            var searchReadResult = results[1];
            if (groups) {
                _.each(groups, function (group) {
                    group.id = _.uniqueId('group');
                });
            }
            var oldRows = self.allRows;
            self.allRows = {};
            self.ganttData.groups = groups;
            self.ganttData.records = self._parseServerData(searchReadResult.records);
            self.ganttData.rows = self._generateRows({
                groupedBy: self.ganttData.groupedBy,
                groups: groups,
                oldRows: oldRows,
                records: self.ganttData.records,
            });
            var unavailabilityProm;
            if (self.displayUnavailability) {
                unavailabilityProm = self._fetchUnavailability();
            }
            return unavailabilityProm;
        });
    },
    /**
     * Compute rows for unavailability rpc call.
     *
     * @private
     * @param {Object} rows in the format of ganttData.rows
     * @returns {Object} simplified rows only containing useful attributes
     */
    _computeUnavailabilityRows: function(rows) {
        var self = this;
        return _.map(rows, function (r) {
            if (r) {
                return {
                    groupedBy: r.groupedBy,
                    records: r.records,
                    name: r.name,
                    resId: r.resId,
                    rows: self._computeUnavailabilityRows(r.rows)
                }
            } else {
                return r;
            }
        });
    },
    /**
     * Fetches gantt unavailability.
     *
     * @private
     * @returns {Deferred}
     */
    _fetchUnavailability: function () {
        var self = this;
        return this._rpc({
            model: this.modelName,
            method: 'gantt_unavailability',
            args: [
                this.convertToServerTime(this.ganttData.startDate),
                this.convertToServerTime(this.ganttData.stopDate),
                this.ganttData.scale,
                this.ganttData.groupedBy,
                this._computeUnavailabilityRows(this.ganttData.rows),
            ],
            context: this.context,
        }).then(function (enrichedRows) {
            // Update ganttData.rows with the new unavailabilities data
            self._updateUnavailabilityRows(self.ganttData.rows, enrichedRows);
        });
    },
    /**
     * Update rows with unavailabilities from enriched rows.
     *
     * @private
     * @param {Object} original rows in the format of ganttData.rows
     * @param {Object} enriched rows as returned by the gantt_unavailability rpc call
     * @returns {Object} original rows enriched with the unavailabilities data
     */
    _updateUnavailabilityRows: function (original, enriched) {
        var self = this;
        _.zip(original, enriched).forEach(function (rowPair) {
            var o = rowPair[0];
            var e = rowPair[1];
            o.unavailabilities = _.map(e.unavailabilities, function (u) {
                // These are new data from the server, they haven't been parsed yet
                u.start = self._parseServerValue({ type: 'datetime' }, u.start);
                u.stop = self._parseServerValue({ type: 'datetime' }, u.stop);
                return u;
            });
            if (o.rows && e.rows) {
                self._updateUnavailabilityRows(o.rows, e.rows);
            }
        });
    },
    /**
     * Process groups and records to generate a recursive structure according
     * to groupedBy fields. Note that there might be empty groups (filled by
     * read_goup with group_expand) that also need to be processed.
     *
     * @private
     * @param {Object} params
     * @param {Object[]} params.groups
     * @param {Object[]} params.records
     * @param {string[]} params.groupedBy
     * @param {Object} params.oldRows previous version of this.allRows (prior to
     *   this reload), used to keep collapsed rows collapsed
     * @param {string} [params.parentPath=''] persistent identifier of the
     *   parent row (concatenation of the value of each ancestor group), used to
     *   identify rows between two reloads, to restore their collapsed state
     * @returns {Object[]}
     */
    _generateRows: function (params) {
        var self = this;
        var groups = params.groups;
        var groupedBy = params.groupedBy;
        var rows;
        if (!groupedBy.length) {
            // When no groupby, all records are in a single row
            var row = {
                groupId: groups && groups.length && groups[0].id,
                id: _.uniqueId('row'),
                records: params.records,
            };
            rows = [row];
            this.allRows[row.id] = row;
        } else {
            // Some groups might be empty (thanks to expand_groups), so we can't
            // simply group the data, we need to keep all returned groups
            var groupedByField = groupedBy[0];
            var currentLevelGroups = _.groupBy(groups, groupedByField);
            rows = Object.keys(currentLevelGroups).map(function (key) {
                var subGroups = currentLevelGroups[key];
                var groupRecords = _.filter(params.records, function (record) {
                    return _.isEqual(record[groupedByField], subGroups[0][groupedByField]);
                });

                // For empty groups, we can't look at the record to get the
                // formatted value of the field, we have to trust expand_groups
                var value;
                if (groupRecords.length) {
                    value = groupRecords[0][groupedByField];
                } else {
                    value = subGroups[0][groupedByField];
                }

                var path = (params.parentPath || '') + JSON.stringify(value);
                var minNbGroups = self.collapseFirstLevel ? 0 : 1;
                var isGroup = groupedBy.length > minNbGroups;
                var row = {
                    name: self._getFieldFormattedValue(value, self.fields[groupedByField]),
                    groupId: subGroups[0].id,
                    groupedBy: groupedBy,
                    groupedByField: groupedByField,
                    id: _.uniqueId('row'),
                    resId: _.isArray(value) ? value[0] : value,
                    isGroup: isGroup,
                    isOpen: !_.findWhere(params.oldRows, {path: path, isOpen: false}),
                    path: path,
                    records: groupRecords,
                };

                // Generate sub groups
                if (isGroup) {
                    row.rows = self._generateRows({
                        groupedBy: groupedBy.slice(1),
                        groups: subGroups,
                        oldRows: params.oldRows,
                        parentPath: row.path + '/',
                        records: groupRecords,
                    });
                    row.childrenRowIds = [];
                    row.rows.forEach(function (subRow) {
                        row.childrenRowIds.push(subRow.id);
                        row.childrenRowIds = row.childrenRowIds.concat(subRow.childrenRowIds || []);
                    });
                }

                self.allRows[row.id] = row;

                return row;
            });
            if (!rows.length) {
                // we want to display an empty row in this case
                rows = [{
                    groups: [],
                    records: [],
                }];
            }
        }
        return rows;
    },
    /**
     * Get domain of records to display in the gantt view.
     *
     * @private
     * @returns {Array[]}
     */
    _getDomain: function () {
        var domain = [
            [this.ganttData.dateStartField, '<=', this.convertToServerTime(this.ganttData.stopDate)],
            [this.ganttData.dateStopField, '>=', this.convertToServerTime(this.ganttData.startDate)],
        ];
        return this.domain.concat(domain);
    },
    /**
     * Get all the fields needed.
     *
     * @private
     * @returns {string[]}
     */
    _getFields: function () {
        var fields = ['display_name', this.ganttData.dateStartField, this.ganttData.dateStopField];
        fields = fields.concat(this.ganttData.groupedBy, this.decorationFields);

        if (this.progressField) {
            fields.push(this.progressField);
        }

        if (this.colorField) {
            fields.push(this.colorField);
        }

        if (this.consolidationParams.field) {
            fields.push(this.consolidationParams.field);
        }

        if (this.consolidationParams.excludeField) {
            fields.push(this.consolidationParams.excludeField);
        }

        return _.uniq(fields);
    },
    /**
     * Format field value to display purpose.
     *
     * @private
     * @param {any} value
     * @param {Object} field
     * @returns {string} formatted field value
     */
    _getFieldFormattedValue: function (value, field) {
        var options = {};
        if (field.type === 'boolean') {
            options = {forceString: true};
        }
        var formattedValue = fieldUtils.format[field.type](value, field, options);
        return formattedValue || _.str.sprintf(_t('Undefined %s'), field.string);
    },
    /**
     * Parse in place the server values (and in particular, convert datetime
     * field values to moment in UTC).
     *
     * @private
     * @param {Object} data the server data to parse
     * @returns {Promise<any>}
     */
    _parseServerData: function (data) {
        var self = this;

        data.forEach(function (record) {
            Object.keys(record).forEach(function (fieldName) {
                record[fieldName] = self._parseServerValue(self.fields[fieldName], record[fieldName]);
            });
        });

        return data;
    },
    /**
     * Set date range to render gantt
     *
     * @private
     * @param {Moment} focusDate current activated date
     * @param {string} scale current activated scale
     */
    _setRange: function (focusDate, scale) {
        this.ganttData.scale = scale;
        this.ganttData.focusDate = focusDate;
        this.ganttData.startDate = focusDate.clone().startOf(scale);
        this.ganttData.stopDate = focusDate.clone().endOf(scale);
    },
});

return GanttModel;

});
