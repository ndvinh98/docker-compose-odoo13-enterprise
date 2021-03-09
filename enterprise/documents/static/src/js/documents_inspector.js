odoo.define('documents.DocumentsInspector', function (require) {
"use strict";

/**
 * This file defines the DocumentsInspector Widget, which is displayed next to
 * the KanbanRenderer in the DocumentsKanbanView.
 */

var core = require('web.core');
var fieldRegistry = require('web.field_registry');
var session = require('web.session');
var dialogs = require('web.view_dialogs');
var Widget = require('web.Widget');

var _t = core._t;
var qweb = core.qweb;

var TAGS_SEARCH_LIMIT = 8;

var DocumentsInspector = Widget.extend({
    template: 'documents.DocumentsInspector',
    custom_events: {
        field_changed: '_onFieldChanged',
    },
    events: {
        'click .o_inspector_archive': '_onArchive',
        'click .o_inspector_delete': '_onDelete',
        'click .o_inspector_download': '_onDownload',
        'click .o_inspector_replace': '_onReplace',
        'click .o_inspector_lock': '_onLock',
        'click .o_inspector_share': '_onShare',
        'click .o_inspector_open_chatter': '_onOpenChatter',
        'click .o_inspector_tag_add': '_onTagInputClicked',
        'click .o_inspector_tag_remove': '_onRemoveTag',
        'click .o_inspector_trigger_rule': '_onTriggerRule',
        'click .o_inspector_object_name': '_onOpenResource',
        'click .o_preview_available': '_onOpenPreview',
        'click .o_document_pdf': '_onOpenPDF',
        'mouseover .o_inspector_trigger_hover': '_onMouseoverRule',
        'mouseout .o_inspector_trigger_hover': '_onMouseoutRule',
    },

    /**
     * @override
     * @param {Object} params
     * @param {Array} params.recordIDs list of document's resIDs
     * @param {Object} params.state
     */
    init: function (parent, params) {
        var self = this;
        this._super.apply(this, arguments);

        this.nbDocuments = params.state.count;
        this.size = params.state.size;
        this.focusTagInput = params.focusTagInput;
        this.currentFolder = _.findWhere(params.folders, {id: params.folderId});
        this.recordsData = {};

        this.records = [];
        for (const resID of params.recordIDs) {
            var record = _.findWhere(params.state.data, {res_id: resID});
            if (record) {
                let youtubeToken;
                let youtubeUrlMatch;
                if (record.data.url && record.data.url.length) {
                    /** youtu<A>/<B><token>
                     * A = .be|be.com
                     * B = watch?v=|''
                     * token = <11 case sensitive alphanumeric characters and _>
                     */
                    youtubeUrlMatch = record.data.url.match('youtu(?:\.be|be\.com)/(?:.*v(?:/|=)|(?:.*/)?)([a-zA-Z0-9-_]{11})');
                }
                if (youtubeUrlMatch && youtubeUrlMatch.length > 1) {
                     youtubeToken = youtubeUrlMatch[1];
                }
                this.recordsData[record.id] = {
                    isGif: new RegExp('image.*(gif)').test(record.data.mimetype),
                    isImage: new RegExp('image.*(jpeg|jpg|png)').test(record.data.mimetype),
                    isYouTubeVideo: !!youtubeToken,
                    youtubeToken,
                };
                this.records.push(record);
            }
        }
        this.tags = params.tags;
        var tagIDsByRecord = _.map(this.records, function (record) {
            return record.data.tag_ids.res_ids;
        });
        this.commonTagIDs = _.intersection.apply(_, tagIDsByRecord);

        var ruleIDsByRecord = _.map(this.records, function (record) {
            return record.data.available_rule_ids.res_ids;
        });
        var commonRuleIDs = _.intersection.apply(_, ruleIDsByRecord);
        var record = this.records[0];
        this.rules = _.map(commonRuleIDs, function (ruleID) {
            var rule = _.findWhere(record.data.available_rule_ids.data, {
                res_id: ruleID,
            });
            return rule.data;
        });

        // we have to block some actions (like opening the record preview) when
        // there are pending 'multiSave' requests
        this.pendingSavingRequests = 0;

        this._isLocked = this.records.some(record =>
             record.data.lock_uid && record.data.lock_uid.res_id !== session.uid
        );
    },
    /**
     * @override
     */
    async start() {
        this._renderTags();
        this._renderRules();
        this._renderModel();
        this._updateButtons();
        await Promise.all([
            this._renderFields(),
            this._super.apply(this, arguments)
        ]);
        this.$('.o_inspector_table .o_input').prop('disabled', this._isLocked);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Return the internal state of the widget, which has to be restored after
     * an update (when this instance is destroyed, and another one is created).
     *
     * @returns {Object}
     */
    getLocalState: function () {
        return {
            scrollTop: this.el.scrollTop,
        };
    },
    /**
     * Restore the given state.
     *
     * @param {Object} state
     * @param {integer} state.scrollTop the scroll position to restore
     */
    setLocalState: function (state) {
        this.el.scrollTop = state.scrollTop;
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Generate the record dataPoint to pass to the FieldMany2one when several
     * records a selected, and when those records have different values for the
     * many2one field to display.
     *
     * @private
     * @param {string} fieldName a many2one field
     */
    _generateCommonRecord: function (fieldName) {
        var record = _.extend({}, this.records[0], {
            id: null,
            res_id: null,
        });
        record.data = _.extend({}, record.data);
        record.data[fieldName] = {
            data: {
                display_name: _t('Multiple values'),
                id: null,
            },
        };
        return record;
    },
    /**
     * Render and append a field widget for the given field and the current
     * records.
     *
     * @private
     * @param {string} fieldName
     * @param {Object} [options] options to pass to the field
     * @param {string} [options.icon] optional icon to display
     * @param {string} [options.label] the label to display
     * @return {Promise}
     */
    _renderField: function (fieldName, options) {
        options = options || {};

        // generate the record to pass to the FieldWidget
        var values = _.uniq(_.map(this.records, function (record) {
            return record.data[fieldName] && record.data[fieldName].res_id;
        }));
        var record;
        if (values.length > 1) {
            record = this._generateCommonRecord(fieldName);
        } else {
            record = this.records[0];
        }

        var $row = $(qweb.render('documents.DocumentsInspector.infoRow'));

        // render the label
        var $label = $(qweb.render('documents.DocumentsInspector.fieldLabel', {
            icon: options.icon,
            label: options.label || record.fields[fieldName].string,
            name: fieldName,
        }));
        $label.appendTo($row.find('.o_inspector_label'));

        // render and append field
        var type = record.fields[fieldName].type;
        var FieldWidget = fieldRegistry.get(type);
        options = _.extend({}, options, {
            noOpen: true, // option for many2one fields
            viewType: 'kanban',
        });
        var fieldWidget = new FieldWidget(this, fieldName, record, options);
        const prom = fieldWidget.appendTo($row.find('.o_inspector_value')).then(function() {
            fieldWidget.getFocusableElement().attr('id', fieldName);
            if (type === 'many2one' && values.length > 1) {
                fieldWidget.$el.addClass('o_multiple_values');
            }
        });
        $row.insertBefore(this.$('.o_inspector_fields tbody tr.o_inspector_divider'));
        return prom;
    },
    /**
     * @private
     * @return {Promise}
     */
    _renderFields: function () {
        var options = {mode: 'edit'};
        var proms = [];
        if (this.records.length === 1) {
            proms.push(this._renderField('name', options));
            if (this.records[0].data.type === 'url') {
                proms.push(this._renderField('url', options));
            }
            proms.push(this._renderField('partner_id', options));
        }
        if (this.records.length > 0) {
            proms.push(this._renderField('owner_id', options));
            proms.push(this._renderField('folder_id', {
                icon: 'fa fa-folder o_documents_folder_color',
                mode: 'edit',
            }));
        }
        return Promise.all(proms);
    },
    /**
     * @private
     */
    _renderModel: function () {
        if (this.records.length !== 1) {
           return;
        }
        var resModelName = this.records[0].data.res_model_name;
        if (!resModelName || this.records[0].data.res_model === 'documents.document') {
            return;
        }

        var $modelContainer = this.$('.o_model_container');
        var options = {
            res_model: resModelName,
            res_name: this.records[0].data.res_name,
        };
        $modelContainer.append(qweb.render('documents.DocumentsInspector.resModel', options));
    },
    /**
     * @private
     */
    _renderRules: function () {
        if (!this.currentFolder || this._isLocked) {
           return;
        }
        var self = this;
        _.each(this.rules, function (rule) {
            if (self.records.length === 1 || !rule.limited_to_single_record) {
                var $rule = $(qweb.render('documents.DocumentsInspector.rule', rule));
                $rule.appendTo(self.$('.o_inspector_rules'));
            }
        });
    },
    /**
     * @private
     */
    _renderTags: function () {
        var $tags = this.$('.o_inspector_tags');

        // render common tags
        const commonTags = this.tags.filter(tag => this.commonTagIDs.includes(tag.id));
        for (const tag of commonTags) {
            if (tag) {
                // hide unknown tags (this may happen if a document with tags
                // is moved to another folder, but we keep those tags in case
                // the document is moved back to its original folder)
                var $tag = $(qweb.render('documents.DocumentsInspector.tag', tag));
                $tag.appendTo(this.$('.o_inspector_tags'));
            }
        };

        // render autocomplete input (if there are still tags to add)
        if (this.tags.length > this.commonTagIDs.length) {
            this.$tagInput = $('<input>', {
                class: 'o_input o_inspector_tag_add',
                type: 'text',
            }).attr('placeholder', _t("+ Add a tag "));

            this.$tagInput.autocomplete({
                delay: 0,
                minLength: 0,
                autoFocus: true,
                select: (event, ui) => {
                    this.trigger_up('set_focus_tag_input');
                    const currentId = ui.item.id;
                    if (ui.item.special) {
                        if (ui.item.special === 'more') {
                            this._searchMore(this._lastSearchVal);
                        }
                    } else if (currentId) {
                        this._saveMulti({
                            tag_ids: {
                                operation: 'ADD_M2M',
                                resIDs: [currentId],
                            },
                        });
                    }
                },
                source: (req, resp) => {
                    resp(this._search(req.term));
                    this._lastSearchVal = req.term;
                },
            });

            var disabled = this._isLocked || (this.records.length === 1 && !this.records[0].data.active);
            $tags.closest('.o_inspector_custom_field').toggleClass('o_disabled', disabled);

            this.$tagInput.appendTo($tags);
            if (this.focusTagInput) {
                this.$tagInput.focus();
            }
        }
    },
    /**
     * Trigger a 'save_multi' event to save changes on the selected records.
     *
     * @private
     * @param {Object} changes
     */
    _saveMulti: function (changes) {
        var self = this;
        this.pendingSavingRequests++;
        this.trigger_up('save_multi', {
            changes: changes,
            dataPointIDs: _.pluck(this.records, 'id'),
            callback: function () {
                self.pendingSavingRequests--;
            },
        });
    },
    /**
     * Search for tags matching the given value. The result is given to jQuery
     * UI autocomplete.
     *
     * @private
     * @param {string} value
     * @returns {Object[]}
     */
    _search: function (value) {
        var self = this;
        var tags = [];
        _.each(this.tags, function (tag) {
            // don't search amongst already linked tags
            if (!_.contains(self.commonTagIDs, tag.id)) {
                tags.push({
                    id: tag.id,
                    label: tag.group_name + ' > ' + tag.name,
                });
            }
        });
        const lowerValue = value.toLowerCase();
        const allSearchResults = tags.filter(tag => tag.label.toLowerCase().includes(lowerValue));
        const searchResults = allSearchResults.slice(0, TAGS_SEARCH_LIMIT);
        if (allSearchResults.length > TAGS_SEARCH_LIMIT) {
            searchResults.push({
                label: _t("Search more..."),
                special: 'more',
                classname: 'o_m2o_dropdown_option',
            });
        }

        return searchResults;
    },
    /**
     * @private
     * @param {Object[]} [dynamicFilters=[]] filters to add to the search view
     *   in the dialog (each filter has keys 'description' and 'domain')
     */
    _searchCreatePopup(dynamicFilters=[]) {
        this.$('.o_inspector_tag_add').val('');
        return new dialogs.SelectCreateDialog(this, {
            domain: [['folder_id', '=', this.currentFolder.id]],
            dynamicFilters: dynamicFilters || [],
            no_create: true,
            on_selected: records => this._saveMulti({
                tag_ids: {
                   operation: 'ADD_M2M',
                   resIDs: records.map(record => record.id),
                },
            }),
            res_model: 'documents.tag',
            title: _t('Select tags'),
        }).open();
    },
    /**
     * Search for tags matching the value for either tag.name and tag.facet_id.name.
     *
     * @private
     * @param {String} value
     */
    async _searchMore(value) {
        let results;
        if (value) {
            results = await this._rpc({
                model: 'documents.tag',
                method: 'search_read',
                fields: ['id'],
                domain: ['&', '&',
                            ['id', 'not in', this.commonTagIDs],
                            ['folder_id', '=', this.currentFolder.id],
                            '|',
                                ['facet_id.name', 'ilike', value],
                                ['name', 'ilike', value]
                ],
            });
        }
        let dynamicFilters;
        if (results) {
            const ids = results.map(result => result.id);
            dynamicFilters = [{
                description: _.str.sprintf(_t('Name or Category contains: %s'), value),
                domain: [['id', 'in', ids]],
            }];
        }
        await this._searchCreatePopup(dynamicFilters);
    },
    /**
     * Disable buttons if at least one of the selected records is locked by
     * someone else
     *
     * @private
     */
    _updateButtons: function () {
        var binary = _.some(this.records, function (record) {
            return record.data.type === 'binary';
        });
        if (this._isLocked) {
            this.$('.o_inspector_replace').prop('disabled', true);
            this.$('.o_inspector_delete').prop('disabled', true);
            this.$('.o_inspector_archive').prop('disabled', true);
            this.$('.o_inspector_table .o_field_widget').prop('disabled', true);
        }
        if (!binary && (this.records.length > 1 || (this.records.length && this.records[0].data.type === 'empty'))) {
            this.$('.o_inspector_download').prop('disabled', true);
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _onArchive: function () {
        this.trigger_up('archive_records', {
            records: this.records,
        });
    },
    /**
     * @private
     */
    _onDelete: function () {
        this.trigger_up('delete_records', {
            records: this.records,
        });
    },
    /**
     * Download the selected documents (zipped if there are several documents).
     *
     * @private
     */
    _onDownload: function () {
        this.trigger_up('download', {
            resIDs: _.pluck(this.records, 'res_id'),
        });
    },
    /**
     * Intercept 'field_changed' events as they may concern several records, and
     * not one as the events suggest. Trigger a 'save_multi' event instead,
     * which will be handled by the DocumentsKanbanController.
     *
     * @private
     * @param {OdooEvent} ev
     */
    _onFieldChanged: function (ev) {
        ev.stopPropagation();
        this._saveMulti(ev.data.changes);
    },
    /**
     * Lock the current attachment for the current user. This assumes that there
     * is only one selected attachment (the lock button is hidden when several
     * records are selected).
     *
     * @private
     */
    _onLock: function () {
        this.trigger_up('lock_attachment', {
            resID: this.records[0].res_id,
        });
    },
    /**
     * Apply a style-class to a sidebar action when its button is hover
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onMouseoverRule: function (ev) {
        $(ev.currentTarget).closest('.o_inspector_trigger_hover_target').addClass('o_inspector_hover');
    },
    /**
     * Remove the style-class when the sidebar action button is not hover
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onMouseoutRule: function (ev) {
        $(ev.currentTarget).closest('.o_inspector_trigger_hover_target').removeClass('o_inspector_hover');
    },
    /**
     * @private
     */
    _onOpenChatter: function () {
        this.trigger_up('open_chatter', {
            id: this.records[0].data.id,
        });
    },
    /**
     * Open the document previewer, a fullscreen preview of the image with
     * download and print options.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onOpenPreview: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        if (this.pendingSavingRequests > 0)
            return;
        var activeID = $(ev.currentTarget).data('id');
        if (activeID) {
            var records = _.pluck(this.records, 'data');
            this.trigger_up('kanban_image_clicked', {
                recordID: activeID,
                recordList: records
            });
        }
    },
    /**
     * Open the business object linked to the selected record in a form view.
     *
     * @private
     */
    _onOpenResource: function () {
        var record = this.records[0];
        this.trigger_up('open_record', {
            resID: record.data.res_id,
            resModel: record.data.res_model,
        });
    },
    /**
     * Remove the clicked tag from the selected records.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onRemoveTag: function (ev) {
        ev.stopPropagation();
        var tagID = $(ev.currentTarget).closest('.o_inspector_tag').data('id');
        var changes = {
            tag_ids: {
                operation: 'FORGET',
                resIDs: [tagID],
            },
        };
        this._saveMulti(changes);
    },
    /**
     * TODO tests
     *
     * @private
     */
    _onReplace: function () {
        this.trigger_up('replace_file', {
            id: this.records[0].data.id,
        });
    },
    /**
     * Share the selected documents
     *
     * @private
     */
    _onShare: function () {
        this.trigger_up('share', {
            resIDs: _.pluck(this.records, 'res_id'),
        });
    },
    /**
     * Trigger a search or close the dropdown if it is already open when the
     * input is clicked.
     *
     * @private
     */
    _onTagInputClicked: function () {
        if (this.$tagInput.autocomplete("widget").is(":visible")) {
            this.$tagInput.autocomplete("close");
        } else {
            this.$tagInput.autocomplete('search');
        }
    },
    /**
     * Trigger a Workflow Rule's action on the selected records
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onTriggerRule: function (ev) {
        var $btn = $(ev.currentTarget);
        var ruleID = $btn.closest('.o_inspector_rule').data('id');
        $btn.prop('disabled', true);
        this.trigger_up('trigger_rule', {
            records: this.records,
            ruleID: ruleID
        });
    },
});

return DocumentsInspector;

});
