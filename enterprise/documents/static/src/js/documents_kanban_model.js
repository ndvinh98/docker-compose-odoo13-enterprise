odoo.define('documents.DocumentsKanbanModel', function (require) {
"use strict";

/**
 * This file defines the Model for the Documents Kanban view, which is an
 * override of the KanbanModel.
 */

var KanbanModel = require('web.KanbanModel');


var DocumentsKanbanModel = KanbanModel.extend({
    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @param {Integer} recordID
     * @returns {Promise}
     */
    fetchActivities: function (recordID) {
        var record = this.localData[recordID];
        return this._fetchSpecialActivity(record, 'activity_ids').then(function (data) {
            record.specialData.activity_ids = data;
        });
    },
    /**
     * @override
     */
    get: function (dataPointID) {
        var result = this._super.apply(this, arguments);
        if (result && result.type === 'list') {
            var dataPoint = this.localData[dataPointID];
            result.size = dataPoint.size;
        }
        return result;
    },
    /**
     * Override to explicitly specify the 'searchDomain', which is the domain
     * coming from the search view. This domain is used to load the related
     * models, whereas a combination of this domain and the domain of the
     * DocumentsSelector is used for the classical search_read.
     *
     * Also fetch the folders here, so that it is done only once, as it doesn't
     * depend on the domain. Moreover, the folders are necessary to fetch the
     * tags, as we first fetch tags of the default folder.
     *
     * @override
     */
    load: function (params) {
        var self = this;
        var def = this._super.apply(this, arguments);
        return self._fetchAdditionalData(def, params).then(function (dataPointID) {
            var dataPoint = self.localData[dataPointID];
            dataPoint.isRootDataPoint = true;
            return dataPointID;
        });
    },
    /**
     * Override to handle the 'selectorDomain' coming from the
     * DocumentsInspector, and to explicitely specify the 'searchDomain', which
     * is the domain coming from the search view. This domain is used to load
     * the related models, whereas a combination of the 'searchDomain' and the
     * 'selectorDomain' is used for the classical search_read.
     *
     * @override
     * @param {Array[]} [options.selectorDomain] the domain coming from the
     *   DocumentsInspector
     */
    reload: function (id, options) {
        var element = this.localData[id];
        var def = this._super.apply(this, arguments);
        if (element.isRootDataPoint) {
            return this._fetchAdditionalData(def, options);
        } else {
            return def;
        }
    },
    /**
     * Save changes on several records in a mutex, and reload.
     *
     * @param {string[]} recordIDs
     * @param {Object} values
     * @param {string} parentID
     * @returns {Promise<string>} resolves with the parentID
     */
    saveMulti: function (recordIDs, values, parentID) {
        return this.mutex.exec(this._saveMulti.bind(this, recordIDs, values, parentID));
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Fetch additional data required by the DocumentsKanban view.
     *
     * @param {Promise<string>} def resolves with the id of the dataPoint
     *   created by the load/reload call
     * @param {Object} params parameters/options passed to the load/reload function
     * @returns {Promise<string>} resolves with the dataPointID
     */
    _fetchAdditionalData: function (def, params) {
        var self = this;
        var defs = [def];
        defs.push(this._fetchSize(params));
        return Promise.all(defs).then(function (results) {
            var dataPointID = results[0];
            var size = results[1];
            var dataPoint = self.localData[dataPointID];
            dataPoint.size = size;
            return dataPointID;
        });
    },
    /**
     * Fetch the sum of the size of the documents matching the current domain.
     *
     * @private
     * @param {Object} params
     * @returns {Promise<integer>} the size, in MB
     */
    _fetchSize: function (params) {
        params = params || {};
        return this._rpc({
            model: 'documents.document',
            method: 'read_group',
            domain: params.domain || [],
            fields: ['file_size'],
            groupBy: [],
        }).then(function (result) {
            var size = result[0].file_size / (1000 * 1000); // in MB
            return Math.round(size * 100) / 100;
        });
    },
    /**
     * Save changes on several records. Be careful that this function doesn't
     * handle all field types: only primitive types, many2ones and many2manys
     * (forget and link_to commands) are covered.
     *
     * @private
     * @param {string[]} recordIDs
     * @param {Object} values
     * @param {string} parentID
     * @returns {Promise<string>} resolves with the parentID
     */
    _saveMulti: function (recordIDs, values, parentID) {
        var self = this;
        var parent = this.localData[parentID];
        var resIDs = _.map(recordIDs, function (recordID) {
            return self.localData[recordID].res_id;
        });
        var changes = _.mapObject(values, function (value, fieldName) {
            var field = parent.fields[fieldName];
            if (field.type === 'many2one') {
                value = value.id || false;
            } else if (field.type === 'many2many') {
                var command = value.operation === 'FORGET' ? 3 : 4;
                value = _.map(value.resIDs, function (resID) {
                    return [command, resID];
                });
            }
            return value;
        });

        return this._rpc({
            model: parent.model,
            method: 'write',
            args: [resIDs, changes],
        });
    },
});

return DocumentsKanbanModel;

});
