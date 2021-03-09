odoo.define('documents.MockServer', function (require) {
'use strict';

var MockServer = require('web.MockServer');

MockServer.include({
    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     * @private
     */
    _performRpc: function (route) {
        if (route.indexOf('/documents/image') >= 0 ||
            _.contains(['.png', '.jpg'], route.substr(route.length - 4))) {
            return Promise.resolve();
        }
        return this._super.apply(this, arguments);
    },
    /**
     * Override to handle the specific case of model 'documents.document'.
     *
     * @override
     * @private
     */
    _mockSearchPanelSelectRange: function (model, args) {
        var fieldName = args[0];

        if (model === 'documents.document' && fieldName === 'folder_id') {
            var fields = ['display_name', 'description', 'parent_folder_id'];
            return {
                parent_field: 'parent_folder_id',
                values: this._mockSearchRead('documents.folder', [[], fields], {}),
            };
        }
        return this._super.apply(this, arguments);
    },
    /**
     * Override to handle the specific case of model 'documents.document'.
     *
     * @override
     * @private
     */
    _mockSearchPanelSelectMultiRange: function (model, args, kwargs) {
        var self = this;
        var fieldName = args[0];
        var categoryDomain = kwargs.category_domain || [];
        var filterValues = [];
        var groups;
        var modelDomain;

        function get_models(domain) {
            var models = [];
            var notAttached = [];
            var notAFile = [];
            groups = self._mockReadGroup('documents.document', {
                domain: domain,
                fields: ['res_model', 'res_model_name'],
                groupby: ['res_model', 'res_model_name'],
            });
            groups.forEach(function (group) {
                // we don't want undefined value
                var res_model = group.res_model || false;
                var model = {
                    count: group.res_model_count,
                    id: res_model,
                };
                if (!res_model) {
                    model.name = 'Not a file';
                    notAFile.push(model);
                } else if (res_model === 'documents.document') {
                    model.name = 'Not attached';
                    notAttached.push(model);
                } else {
                    model.name = self.data['documents.document'].records.find(function (record) {
                        return record.res_model === res_model;
                    }).res_model_name;
                    models.push(model);
                }
            });
            return Array.prototype.concat.apply([], [models, notAttached, notAFile]);
        }

        if (model === 'documents.document') {
            if (fieldName === 'tag_ids') {
                var folderId = categoryDomain.length && categoryDomain[0][2] || false;
                if (folderId) {
                    modelDomain = Array.prototype.concat.apply([], [
                        kwargs.search_domain || [],
                        kwargs.category_domain || [],
                        kwargs.filter_domain || [],
                        [[fieldName, '!=', false]]
                    ]);
                    filterValues = this.data['documents.tag'].get_tags(modelDomain, folderId);
                }
                return filterValues;
            } else if (fieldName === 'res_model') {
                var modelDomainEnlarge = Array.prototype.concat.apply([], [
                    kwargs.search_domain || [],
                    kwargs.category_domain || []
                ]);
                var modelDomainEnlargeImage = get_models(modelDomainEnlarge);
                if (kwargs.filter_domain.length) {
                    modelDomain = Array.prototype.concat.apply([], [
                        kwargs.search_domain || [],
                        kwargs.category_domain || [],
                        kwargs.filter_domain || []
                    ]);
                    var modelDomainImage = get_models(modelDomain);
                    var modelIds = modelDomainImage.map(function (m) {
                        return m.id;
                    });
                    filterValues = modelDomainImage;
                    modelDomainEnlargeImage.forEach(function (model) {
                        if (!_.contains(modelIds, model.id)) {
                            model.count = 0;
                            filterValues.push(model);
                        }
                    });
                } else {
                    filterValues = modelDomainEnlargeImage;
                }
                return _.sortBy(filterValues, 'name');
            }
        }
        return this._super.apply(this, arguments);
    },
});

});
