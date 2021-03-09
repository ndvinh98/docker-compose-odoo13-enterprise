odoo.define('mrp_workorder.update_kanban', function (require) {
"use strict";

var basic_fields = require('web.basic_fields');
var field_registry = require('web.field_registry');
var KanbanController = require('web.KanbanController');
var KanbanRecord = require('web.KanbanRecord');
var KanbanView = require('web.KanbanView');
var view_registry = require('web.view_registry');
var ListController = require('web.ListController');
var ListView = require('web.ListView');

var FieldInteger = basic_fields.FieldInteger;
var FieldBinaryImage = basic_fields.FieldBinaryImage;

var core = require('web.core');
var QWeb = core.qweb;

KanbanRecord.include({
    _openRecord: function () {
        if (this.modelName === 'mrp.workorder') {
            var self = this;
            this._rpc({
                method: 'open_tablet_view',
                model: self.modelName,
                args: [self.id],
            }).then(function (result) {
                self.do_action(result);
            });
        } else {
            this._super.apply(this, arguments);
        }
    },
});

var BackArrow = FieldInteger.extend({
    events: {
        'click': '_onClick',
    },
    _render: function () {
        this.$el.html('<button class="btn btn-secondary o_workorder_icon_btn o_workorder_icon_back"><i class="fa fa-arrow-left"/></button>');
    },
    _onClick: function () {
        var self = this;
        this._rpc({
            method: 'action_back',
            model: 'mrp.workorder',
            args: [self.recordData.id],
        }).then(function () {
            self.trigger_up('history_back');
        });
    },
});

function tabletRenderButtons($node) {
        var self = this;
        this.$buttons = $('<div/>');
        this.$buttons.html('<button class="btn btn-secondary back-button"><i class="fa fa-arrow-left"/></button>');
        this.$buttons.on('click', function () {
            self.do_action('mrp.mrp_workcenter_kanban_action', {clear_breadcrumbs: true});
        });
        this.$buttons.appendTo($node);
}

var TabletKanbanController = KanbanController.extend({
    renderButtons: function ($node) {
        return tabletRenderButtons.apply(this, arguments);
    },
});

var TabletKanbanView = KanbanView.extend({
    config: _.extend({}, KanbanView.prototype.config, {
        Controller: TabletKanbanController,
    }),
});

var TabletListController = ListController.extend({
    renderButtons: function ($node) {
        return tabletRenderButtons.apply(this, arguments);
    },
});

var TabletListView = ListView.extend({
    config: _.extend({}, ListView.prototype.config, {
        Controller: TabletListController,
    }),
});

field_registry.add('back_arrow', BackArrow);
view_registry.add('tablet_kanban_view', TabletKanbanView);
view_registry.add('tablet_list_view', TabletListView);

return {
    BackArrow: BackArrow,
    TabletKanbanView: TabletKanbanView,
    TabletListView: TabletListView,
};
});
