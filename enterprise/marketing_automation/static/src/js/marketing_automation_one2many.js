odoo.define('marketing_automation.hierarchy_kanban', function (require) {
"use strict";

var core = require('web.core');
var Domain = require('web.Domain');
var DomainSelector = require('web.DomainSelector');
var Dialog = require('web.Dialog');
var FieldOne2Many = require('web.relational_fields').FieldOne2Many;
var KanbanRenderer = require('web.KanbanRenderer');
var KanbanRecord = require('web.KanbanRecord');
var registry = require('web.field_registry');

var _t = core._t;

var HierarchyKanban = FieldOne2Many.extend({
    custom_events: _.extend({}, FieldOne2Many.prototype.custom_events, {
        'add_child_act': '_onAddChild',
    }),

    /**
     * @override
     */
    on_attach_callback: function () {
        this.renderer.on_attach_callback();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @override
     * @returns {Promise}
     */
    _render: function () {
        var self = this;
        this._setHierarchyData();
        var _super = this._super.bind(this);
        var rendererProm;
        if (!this.renderer) {
            this.renderer = new HierarchyKanbanRenderer(this, this.value, {
                arch: this.view.arch,
                viewType: 'kanban',
                record_options: {
                    editable: false,
                    deletable: false,
                    read_only_mode: this.isReadonly,
                },
            });
            rendererProm = this.renderer.appendTo(this.$el);
        }
        return Promise.resolve(rendererProm).then(function () {
            // Move control_panel at bottom
            if (self.control_panel) {
                self.control_panel.$el.appendTo(self.$el);
            }
            return _super();
        });
    },
    /**
     * Transforms the widget value into parent and child relationship.
     *
     * @private
     */
    _setHierarchyData: function () {
        var data = this.value.data;
        this.allData = data;
        var parentMap = {};
        this.value.data = _.filter(data, function (record) {
            parentMap[record.res_id] = record;
            record.children = [];
            return record.data.parent_id === false;
        });
        _.each(data, function (record) {
            if (record.data.parent_id && parentMap[record.data.parent_id.res_id]) {
                parentMap[record.data.parent_id.res_id].children.push(record);
            }
        });
    },
    /**
     * The implicit contract on this.value.data has been broken by _setHierarchyData
     * so we need to make sure that we generated the right command by checking
     * if the record id is in all_data (which is what this.value.data should be)
     *
     * if we delete a record, we also need to delete every child of this record
     * @override
     * @private
     */
    _setValue: function (value, options) {
        if (value.operation === 'ADD' && _.some(this.allData, {id: value.id})) {
            value.operation = 'UPDATE';
        } else if(value.operation === 'DELETE') {
            var removedRecords = this.allData.filter(function (record) {return value.ids.includes(record.id);});

            // we want to delete these records and also each children which derive from the records
            value.ids = this._getAllSubChildren(removedRecords)
                .map(function (record) {return record.id;});
        }
        return this._super(value, options);
    },

    /**
     * Return the elements and all children which derive from the ``parentRecords``
     *
     * @private
     */
    _getAllSubChildren: function (parentRecords) {
        var childrenRecords = [];
        parentRecords.forEach(function (record) {
            childrenRecords = childrenRecords.concat(record.children || []);
        });
        return childrenRecords.length ? parentRecords.concat(this._getAllSubChildren(childrenRecords)) : parentRecords;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Opens the record with custom context and adds the child activity on saved.
     *
     * @private
     */
    _onAddChild: function (params) {
        var self = this;
        var context = _.extend(this.record.getContext(this.recordParams), params.data);
        this.trigger_up('open_one2many_record', {
            domain: this.record.getDomain(this.recordParams),
            context: context,
            field: this.field,
            fields_view: this.attrs.views && this.attrs.views.form,
            parentID: this.value.id,
            viewInfo: this.view,
            on_saved: function (record) {
                self._setValue({operation: 'ADD', id: record.id});
            },
        });
    },
});

var HierarchyKanbanRenderer = KanbanRenderer.extend({

    /**
     * Renders kanban records with its children.
     *
     * @private
     * @override
     */
    _renderUngrouped: function (fragment, records) {
        this.defs.push(this._renderUngroupedAux(fragment, records));
    },
    _renderUngroupedAux: function (fragment, records) {
        var self = this;
        var recordsDefs = [];
        _.each(records || this.state.data, function (record) {
            var kanbanRecord = new HierarchyKanbanRecord(self, record, self.recordOptions);
            self.widgets.push(kanbanRecord);
            var def = kanbanRecord.appendTo(fragment).then(function() {
                if (record.children.length) {
                    var newFragment = kanbanRecord.$('.o_hierarchy_children');
                    return self._renderUngroupedAux(newFragment, record.children);
                }
            });
            recordsDefs.push(def);
        });
        return Promise.all(recordsDefs);
    },
});

var HierarchyKanbanRecord = KanbanRecord.extend({
    events: _.extend({}, KanbanRecord.prototype.events, {
        'click .o_ma_switch span': '_onClickSwitch',
        'click .o_add_child': '_onKanbanActionClicked',
    }),

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Renders DomainSelector.
     *
     * @private
     * @returns {Promise}
     */
    _renderDomainSelector: function () {
        if (!this.domainSelector) {
            var domainModel = this.state.data.model_name;
            var domain = Domain.prototype.stringToArray(this.state.data.domain);
            this.domainSelector = new DomainSelector(this, domainModel, domain, {
                readonly: true,
                filters: {},
            });
            return this.domainSelector.prependTo(this.$('.o_ma_card:first > .o_pane_filter'));
        }
        return Promise.resolve();
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Displays dialog if user try to delete record having children.
     * Triggers custom actions related to add child activities.
     *
     * @private
     * @override
     * @param {Event} event
     */
    _onKanbanActionClicked: function (event) {
        event.stopPropagation();
        event.preventDefault();
        var type = $(event.currentTarget).data('type') || 'button';
        if (type === 'delete' && this.state.children.length) {
            new Dialog(this, {
                title: _t('Delete Activity'),
                buttons: [{
                    text: _t('Delete All'),
                    classes: 'btn-primary',
                    close: true,
                    click: this._super.bind(this, event)
                }, {
                    text: _t('Discard'),
                    close: true
                }],
                $content: $('<div>', {
                    html: _t("This Activity has a dependant child activity. 'DELETE ALL' will delete all child activities."),
                }),
            }).open();
        } else if (_.indexOf(['act', 'mail_open', 'mail_not_open', 'mail_reply', 'mail_not_reply', 'mail_click', 'mail_not_click', 'mail_bounce'], type) !== -1) {
            // If we are in edit mode and we create a new kanban record,
            // we cannot add a child activity for this record before saving.
            if (this.id) {
                this.trigger_up('add_child_act', {
                    'default_parent_id': this.id,
                    'default_trigger_type': type
                });
            } else {
                this.do_warn(_t('Please save the campaign to add a child activity'));
            }
        } else {
            this._super.apply(this, arguments);
        }
    },

    /**
     * Handles toggling of kanban pane.
     *
     * @private
     * @param {Event} event
     */
    _onClickSwitch: function (event) {
        event.stopPropagation();
        var self = this;
        $(event.currentTarget).siblings().removeClass('active');
        $(event.currentTarget).addClass('active');
        var mode = $(event.currentTarget).data('mode');
        this._renderDomainSelector().then(function () {
            self.$('.o_ma_card:first > [class*="o_pane_"]').addClass('d-none');
            self.$('.o_ma_card:first > .o_pane_' + mode).removeClass('d-none');
        });
    }
});

registry.add('hierarchy_kanban', HierarchyKanban);

return {
    HierarchyKanbanRecord: HierarchyKanbanRecord,
    HierarchyKanbanRenderer: HierarchyKanbanRenderer,
    HierarchyKanban: HierarchyKanban,
};

});
