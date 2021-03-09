odoo.define('account_accountant.MoveLineListView', function (require) {
"use strict";

    var AttachmentViewer = require('mail_enterprise.AttachmentViewer');
    var config = require('web.config');
    var core = require('web.core');
    var ListController = require('web.ListController');
    var ListModel = require('web.ListModel');
    var ListRenderer = require('web.ListRenderer');
    var ListView = require('web.ListView');
    var viewRegistry = require('web.view_registry');

    var _t = core._t;

    var AccountMoveListModel = ListModel.extend({
        /**
         * Overridden to fetch extra fields even if `move_attachment_ids` is
         * invisible in the view.
         *
         * @override
         * @private
         */
        _fetchRelatedData: function (list, toFetch, fieldName) {
            if (fieldName === 'move_attachment_ids' && config.device.size_class >= config.device.SIZES.XXL) {
                var fieldsInfo = list.fieldsInfo[list.viewType][fieldName];
                // force to fetch extra fields
                fieldsInfo.__no_fetch = false;
                fieldsInfo.relatedFields = {
                    mimetype: {type: 'char'},
                };
            }
            return this._super.apply(this, arguments);
        },
    });

    var AccountMoveListController = ListController.extend({
        events: _.extend({}, ListController.prototype.events, {
            'click .o_attachment_control': '_onToggleAttachment',
        }),
        custom_events: _.extend({}, ListController.prototype.custom_events, {
            row_selected: '_onRowSelected',
        }),

        /**
         * @override
         */
        init: function () {
            this._super.apply(this, arguments);

            this.currentAttachments = [];
            this.hide_attachment = !!this.initialState.context.hide_attachment;
            this.last_selected = false;

        },

        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         * Overridden to add an attachment preview container.
         *
         * @override
         * @private
         */
        _update: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                self.$('.o_content').addClass('o_move_line_list_view');
                self.currentAttachments = [];
                if (!self.$attachmentPreview && config.device.size_class >= config.device.SIZES.XXL) {
                    self.$attachmentPreview = $('<div>', {
                        class: 'o_attachment_preview',
                    }).append($('<p>', {
                        class: 'o_move_line_empty',
                        text: _t("Choose a line to preview its attachments."),
                    })).append($('<div>', {
                        class: 'o_attachment_control',
                    }));
                    self.$attachmentPreview.appendTo(self.$('.o_content'));
                    self.$attachmentPreview.toggleClass('hidden', self.hide_attachment);
                }
            }).then(self._renderAttachmentPreview());
        },
        /**
         * Renders a preview of a record attachments.
         *
         * @param {string} recordId
         * @private
         */
        _renderAttachmentPreview: function (recordId) {
            var self = this;
            if (_.filter(this.model.localData, function(value, key, object) {return value.groupData == self.last_selected}).length) {
                recordId = _.filter(this.model.localData, function(value, key, object) {return value.groupData == self.last_selected})[0].data[0]
            }
            if (!recordId) {
                return Promise.resolve()
            }
            var record = this.model.get(recordId || this.last_selected);
            var types = ['pdf', 'image'];
            // record type will be list when multi groupby while expanding group row
            if (record.type === 'list') {
                return;
            }
            let attachments = record.data.move_attachment_ids.data.map(function (attachment) {
                return {
                    id: attachment.res_id,
                    filename: attachment.data.filename,
                    mimetype: attachment.data.mimetype,
                    url: '/web/content/' + attachment.res_id + '?download=true',
                };
            });
            attachments = _.filter(attachments, function (attachment) {
                var match = attachment.mimetype.match(types.join('|'));
                attachment.type = match ? match[0] : false;
                return match;
            });
            var prom;
            if (!_.isEqual(_.pluck(this.currentAttachments, 'id'), _.pluck(attachments, 'id'))) {
                if (this.attachmentViewer) {
                    this.attachmentViewer.updateContents(attachments);
                } else {
                    this.attachmentViewer = new AttachmentViewer(this, attachments);
                }
                prom = this.attachmentViewer.appendTo(this.$attachmentPreview.empty()).then(function () {
                    self.$attachmentPreview.resizable({
                        handles: 'w',
                        minWidth: 400,
                        maxWidth: 900,
                    });
                });
            }
            return Promise.resolve(prom).then(function () {
                self.currentAttachments = attachments;
                if (!attachments.length) {
                    var $empty = $('<p>', {
                        class: 'o_move_line_without_attachment',
                        text: _t("There is no attachment linked to this move."),
                    });
                    self.$attachmentPreview.empty().append($empty);
                }
                $('<div>', {class: 'o_attachment_control'}).appendTo(self.$attachmentPreview);
            });
        },

        _onToggleAttachment: function() {
            this.hide_attachment = !this.hide_attachment;
            this.$attachmentPreview.toggleClass('hidden');
        },

        //--------------------------------------------------------------------------
        // Handlers
        //--------------------------------------------------------------------------

        /**
         * @private
         * @param {OdooEvent} ev
         * @param {string} ev.data.recordId
         */
        _onRowSelected: function (ev) {
            if (config.device.size_class >= config.device.SIZES.XXL) {
                this.last_selected = ev.data.recordId;
                if (this.last_selected.includes('line')) { // if it comes from _onToggleGroup, this._update is triggered but not if it comes from _selectRow
                    this._renderAttachmentPreview(ev.data.recordId);
                }
            }
        },
    });
    var AccountMoveListRenderer = ListRenderer.extend({

        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         *
         * @param {integer} rowIndex
         * @private
         * @override
         */
        _selectRow: function (rowIndex) {
            var self = this;
            var recordId = this._getRecordID(rowIndex);
            var currentRow = this.currentRow; // currentRow is updated in _super
            return this._super.apply(this, arguments).then(function () {
                if (rowIndex !== currentRow) {
                    self.trigger_up('row_selected', {
                        recordId: recordId,
                    });
                }
            });
        },

        _onRowClicked: function (ev) {
            ev.stopPropagation();
            var id = $(ev.currentTarget).data('id');
            if (id) {
                this.trigger_up('row_selected', {
                    recordId: id,
                });
            }
        },

        _renderGroupRow: function (group, groupLevel) {
            var ret = this._super.apply(this, arguments);
            // Handle the markup of the name_get on account.move if name_groupby is in the context
            if (this.state.context.name_groupby) {
                var $th = ret.find('th.o_group_name');
                $th.addClass('o_group_name_custom');
                var text_node = $th.contents().filter(function () {
                    return this.nodeType == 3;
                })[0]; // we filter on text nodes (type 3) to get only the text and not the title tooltips we would have had with $.text()
                text_node.nodeValue = text_node.nodeValue.replace(/(\*\*)(.*)\1/g, '<strong>$2</strong>').replace(/\s+\([0-9]+\)/, ''); // we only change the value of the text and not eh html to keep the listeners on the buttons
                $(text_node).replaceWith($('<span>' + text_node.nodeValue + '</span>')); // we need to create a new node (span) to replace, just inserting with the new html would mean that we replace by multiple nodes, which is impossible
            }
            return ret;
        },

        _onToggleGroup: function (ev) {
            var group = $(ev.currentTarget).closest('tr').data('group');
            if (group.model === 'account.move.line' && group.groupData && group.groupData.model === 'account.move') {
                this.trigger_up('row_selected', {
                    recordId: group.groupData.id,
                });
            }
            this._super.apply(this, arguments);
        },
    });

    var AccountMoveListView = ListView.extend({
        config: _.extend({}, ListView.prototype.config, {
            Controller: AccountMoveListController,
            Model: AccountMoveListModel,
            Renderer: AccountMoveListRenderer,
        }),
    });

    viewRegistry.add('account_move_line_list', AccountMoveListView);

    return {
        AccountMoveListView: AccountMoveListView,
        AccountMoveListController: AccountMoveListController,
        AccountMoveListModel: AccountMoveListModel,
        AccountMoveListRenderer: AccountMoveListRenderer
    }
});
