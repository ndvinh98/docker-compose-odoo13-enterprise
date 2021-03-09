odoo.define('documents.DocumentsKanbanView', function (require) {
"use strict";

var DocumentsKanbanController = require('documents.DocumentsKanbanController');
var DocumentsKanbanModel = require('documents.DocumentsKanbanModel');
var DocumentsKanbanRenderer = require('documents.DocumentsKanbanRenderer');
var DocumentsSearchPanel = require('documents.DocumentsSearchPanel');

var core = require('web.core');
var KanbanView = require('web.KanbanView');
var view_registry = require('web.view_registry');

var _lt = core._lt;

var DocumentsKanbanView = KanbanView.extend({
    config: _.extend({}, KanbanView.prototype.config, {
        Controller: DocumentsKanbanController,
        Model: DocumentsKanbanModel,
        Renderer: DocumentsKanbanRenderer,
        SearchPanel: DocumentsSearchPanel,
    }),
    display_name: _lt('Attachments Kanban'),
    searchMenuTypes: ['filter', 'favorite'],

    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        // force the presence of a searchpanel in Documents
        this.withSearchPanel = true;
        this.rendererParams.withSearchPanel = true;

        // add the fields used in the DocumentsInspector to the list of fields to fetch
        var inspectorFields = [
            'active',
            'activity_ids',
            'available_rule_ids',
            'checksum',
            'display_name', // necessary for the mail tracking system to work correctly
            'folder_id',
            'lock_uid',
            'message_attachment_count',
            'message_follower_ids',
            'message_ids',
            'mimetype',
            'name',
            'owner_id',
            'partner_id',
            'res_id',
            'res_model',
            'res_model_name',
            'res_name',
            'share_ids',
            'tag_ids',
            'type',
            'url',
        ];
        _.defaults(this.fieldsInfo[this.viewType], _.pick(this.fields, inspectorFields));

        // force fetch of relational data (display_name and tooltip) for related
        // rules to display in the DocumentsInspector
        this.fieldsInfo[this.viewType].available_rule_ids = _.extend({}, {
            fieldsInfo: {
                default: {
                    display_name: {},
                    note: {},
                    limited_to_single_record: {},
                },
            },
            relatedFields: {
                display_name: {type: 'string'},
                note: {type: 'string'},
                limited_to_single_record: {type: 'boolean'},
            },
            viewType: 'default',
        }, this.fieldsInfo[this.viewType].available_rule_ids);
    },
});

view_registry.add('documents_kanban', DocumentsKanbanView);

return DocumentsKanbanView;

});
