odoo.define('web_studio.KanbanRecordEditor', function (require) {
"use strict";

var config = require('web.config');
var core = require('web.core');
var Dialog = require('web.Dialog');
var KanbanRecord = require('web.KanbanRecord');
var utils = require('web.utils');

var EditorMixin = require('web_studio.EditorMixin');
var FieldSelectorDialog = require('web_studio.FieldSelectorDialog');

var _t = core._t;

var KanbanRecordEditor = KanbanRecord.extend(EditorMixin, {
    nearest_hook_tolerance: 50,
    /**
     * @constructor
     * @param {Widget} parent
     * @param {Object} state
     * @param {Object} options
     * @param {Object} viewArch
     * @param {Boolean} is_dashboard
     */
    init: function (parent, state, options, viewArch, is_dashboard) {
        this._super.apply(this, arguments);
        this.node_id = 1;
        this.hook_nodes = [];
        this.viewArch = viewArch;
        this.is_dashboard = is_dashboard;
    },
    /**
     * @override
     * @private
     */
    _render: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            // prevent the click on the record and remove the corresponding style
            self.$el.removeClass('oe_kanban_global_click oe_kanban_global_click_edit');

            // prevent the color dropdown to be displayed
            self.$('.o_dropdown_kanban > a')
                .removeAttr('data-toggle')
                .click(function (event) {
                    event.preventDefault();
                });

            self.$el.droppable({
                accept: ".o_web_studio_component",
                drop: function (event, ui) {
                    var $hook = self.$('.o_web_studio_nearest_hook');
                    if ($hook.length) {
                        var hook_id = $hook.data('hook_id');
                        var hook = self.hook_nodes[hook_id];

                        var values = {
                            type: 'add',
                            structure: ui.draggable.data('structure'),
                            field_description: ui.draggable.data('field_description'),
                            node: hook.node,
                            new_attrs: _.defaults(ui.draggable.data('new_attrs'), {
                                display: 'full',
                            }),
                            position: hook.position,
                        };
                        ui.helper.removeClass('ui-draggable-helper-ready');
                        self.trigger_up('on_hook_selected');
                        self.trigger_up('view_change', values);
                    }
                },
            });
        });
    },
    /**
     * @override
     */
    start: function () {
        this._undelegateEvents();
        this.$el.click(function (e) {
            e.stopPropagation();
            e.preventDefault();
        });
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    highlightNearestHook: function ($helper, position) {
        EditorMixin.highlightNearestHook.apply(this, arguments);

        var $nearest_form_hook = this.$('.o_web_studio_hook')
            .touching({
                    x: position.pageX - this.nearest_hook_tolerance,
                    y: position.pageY - this.nearest_hook_tolerance,
                    w: this.nearest_hook_tolerance*2,
                    h: this.nearest_hook_tolerance*2
                },{
                    container: document.body
                }
            ).nearest({x: position.pageX, y: position.pageY}, {container: document.body}).eq(0);
        if ($nearest_form_hook.length) {
            $nearest_form_hook.addClass('o_web_studio_nearest_hook');
            return true;
        }
        return false;
    },
    /**
     * @override
     */
    setLocalState: function (state) {
        if (state.selected_node_id) {
            var $selected_node = this.$('[data-node-id="' + state.selected_node_id + '"]');
            if ($selected_node) {
                $selected_node.click();
            }
        }
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _addSpecialHooks: function () {
        var self = this;

        // add the tags hook
        if (!this.$('.o_kanban_tags').length) {
            var $kanban_tags_hook = $('<span>')
                .addClass('o_web_studio_add_kanban_tags')
                .append($('<span>', {
                    text: _t('Add tags'),
                }));
            $kanban_tags_hook.prependTo(this.$el);
            $kanban_tags_hook.click(function () {
                var compatible_fields = _.pick(self.state.fields, function (e) {
                    return e.type === 'many2many';
                });
                if (_.isEmpty(compatible_fields)) {
                    Dialog.alert(self, _t('You first need to create a many2many field in the form view.'));
                    return;
                }
                var dialog = new FieldSelectorDialog(self, compatible_fields, false);
                dialog.open();
                dialog.on('confirm', self, function (field_name) {
                    self.trigger_up('view_change', {
                        type: 'add',
                        structure: 'field',
                        new_attrs: { name: field_name },
                        node: {
                            tag: 'div/*[1]',
                        },
                        position: 'before',
                    });
                });
            });
        }

        // add the dropdown hook
        var $dropdown = this.$('.o_dropdown_kanban');
        if ($dropdown.length) {
            $dropdown.attr('data-node-id', this.node_id++);
            // find dropdown node from the arch
            var node = this._findNodeWithClass({
                tag: 'div',
                class: 'o_dropdown_kanban',
            });
            // bind handler on dropdown clicked to be able to remove it
            this.setSelectable($dropdown);
            $dropdown.click(function () {
                self.selected_node_id = $dropdown.data('node-id');
                self.trigger_up('node_clicked', {
                    node: node,
                    $node: $dropdown,
                });
            });
        } else {
            var $top_left_hook = $('<div>')
                .addClass('o_web_studio_add_dropdown o_dropdown_kanban dropdown')
                .append($('<a>', {
                    class: 'dropdown-toggle o-no-caret btn',
                    'data-toggle': 'dropdown',
                    href: '#',
                }).append($('<span>', {
                    class: 'fa fa-bars fa-lg',
                })));
            $top_left_hook.prependTo(this.$el);
            $top_left_hook.click(function () {
                Dialog.confirm(self, _t("Do you want to add a dropdown with colors?"), {
                    size: 'small',
                    confirm_callback: function () {
                        self.trigger_up('view_change', {
                            structure: 'kanban_dropdown',
                        });
                    },
                });
            });
        }

        // add the priority hook
        var priorityWidget = this._findNodeWithWidget({
            tag: 'field',
            widget: 'priority',
        });
        if (_.isUndefined(priorityWidget)) {
            var $priority_hook = $('<div>')
                .addClass('o_web_studio_add_priority oe_kanban_bottom_left')
                .append($('<span>', {
                    text: _t('Add a priority'),
                }));
            $priority_hook.appendTo(this.$el);
            $priority_hook.click(function () {
                var compatible_fields = _.pick(self.state.fields, function (e) {
                    return e.type === 'selection';
                });
                var dialog = new FieldSelectorDialog(self, compatible_fields, true).open();
                dialog.on('confirm', self, function (field) {
                    self.trigger_up('view_change', {
                        structure: 'kanban_priority',
                        field: field,
                    });
                });
            });
        }

        // add the image hook
        var $image = this.$('img.oe_kanban_avatar');
        if ($image.length) {
            $image.attr('data-node-id', this.node_id++);
            // find image node from the arch
            var imgNode = this._findNodeWithClass({
                tag: 'img',
                class: 'oe_kanban_avatar',
            });
            // bind handler on image clicked to be able to remove it
            this.setSelectable($image);
            $image.click(function () {
                self.selected_node_id = $image.data('node-id');
                self.trigger_up('node_clicked', {
                    node: imgNode,
                    $node: $image,
                });
            });
        } else {
            var $kanban_image_hook = $('<div>')
                .addClass('o_web_studio_add_kanban_image oe_kanban_bottom_right')
                .append($('<span>', {
                    text: _t('Add an image'),
                }));
            $kanban_image_hook.appendTo(this.$el);
            $kanban_image_hook.click(function () {
                var compatible_fields = _.pick(self.state.fields, function (e) {
                    return e.type === 'many2one' && (e.relation === 'res.partner' || e.relation === 'res.users');
                });
                if (_.isEmpty(compatible_fields)) {
                    Dialog.alert(self, _t('You first need to create a many2one field to Partner or User in the form view.'));
                    return;
                }
                var dialog = new FieldSelectorDialog(self, compatible_fields, false).open();
                dialog.on('confirm', self, function (field) {
                    self.trigger_up('view_change', {
                        structure: 'kanban_image',
                        field: field,
                    });
                });
            });
        }
    },
    /**
     * @private
     * @param {jQueryElement} $node
     * @param {String} fieldName
     */
    _bindHandler: function ($node, fieldName) {
        var self = this;

        var node = {
            tag: 'field',
            attrs: { name: fieldName }
        };

        this.setSelectable($node);
        $node.click(function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            self.selected_node_id = $node.data('node-id');
            self.trigger_up('node_clicked', {
                node: node,
                $node: $node,
            });
        });

        // insert a hook to add new fields
        var $hook = this._renderHook(node);
        $hook.insertAfter($node);

        var invisibleModifier = this.fieldsInfo[fieldName].modifiers.invisible;
        if (invisibleModifier && this._computeDomain(invisibleModifier)) {
            $node.addClass('o_web_studio_show_invisible');
        }
    },
    /**
     * @private
     * @param {string} [attrs.tag] - node tag
     * @param {string} [attrs.class] - node class
     * @returns {Object|undefined} found node in the arch
     */
    _findNodeWithClass: function (attrs) {
        var foundNode;
         utils.traverse(this.viewArch, function (node) {
            if (_.isObject(node) && node.tag === attrs.tag) {
                if (_.str.include(node.attrs.class, attrs.class)) {
                    foundNode = node;
                    return false;
                }
            }
            return true;
        });
        return foundNode;
    },
    /**
     * @private
     * @param {string} [attrs.tag] - node tag
     * @param {string} [attrs.widget] - node widget
     * @returns {Object|undefined} found node in the arch
     */
    _findNodeWithWidget: function (attrs) {
        var foundNode;
        utils.traverse(this.viewArch, function(node) {
            if (_.isObject(node) && node.tag === attrs.tag && node.attrs.widget === attrs.widget) {
                    foundNode = node;
                    return false;
            }
            return true;
        });
        return foundNode;
    },
    /**
     * @private
     * @param {any} value
     * @returns {Boolean}
     */
    _isEmpty: function (value) {
        if (typeof(value) === 'object') {
            return _.isEmpty(value);
        } else {
            return !value && value !== 0;
        }
    },
    /**
     * @override
     */
    _processFields: function () {
        this._super.apply(this, arguments);

        // the layout of the special hooks are broken in the kanban dashboards
        if (!this.is_dashboard) {
            this._addSpecialHooks();
        }
    },
    /**
     * @override
     */
    _processField: function ($field, field_name) {
        $field = this._super.apply(this, arguments);

        var field = this.record[field_name];
        // make empty widgets appear
        if (this._isEmpty(field.value)) {
            $field.text(field.string);
            $field.addClass('o_web_studio_widget_empty');
        }
        $field.attr('data-node-id', this.node_id++);

        // bind handler on field clicked to edit field's attributes
        this._bindHandler($field, field_name);

        var invisibleModifier = this.fieldsInfo[field_name].modifiers.invisible;
        if (invisibleModifier && this._computeDomain(invisibleModifier)) {
            $field.addClass('o_web_studio_show_invisible');
        }

        return $field;
    },
    /**
     * @override
     */
    _processWidget: function ($field, field_name) {
        var self = this;
        // '_processWidget' in KanbanRecord adds a promise to this.defs only if
        // the widget is async. Here, we need to hook on this def to access the
        // widget's $el (it doesn't exist until the def is resolved). As calling
        // '_super' may or may not push a promise in this.defs, we store the
        // length of this.defs as index before calling '_super'. Note that if
        // it doesn't push a promise, this.defs[currentDefIndex] is undefined.
        // FIXME: get rid of this hack in master with a small refactoring
        var currentDefIndex = this.defs.length;
        var widget = this._super.apply(this, arguments);
        Promise.resolve(this.defs[currentDefIndex]).then(function () {
            widget.$el.off();

            // make empty widgets appear
            if (self._isEmpty(widget.value)) {
                widget.$el.addClass('o_web_studio_widget_empty');
                widget.$el.text(widget.string);
            }
            widget.$el.attr('data-node-id', self.node_id++);

            // bind handler on field clicked to edit field's attributes
            self._bindHandler(widget.$el, field_name);
        });

        return widget;
    },
    /**
     * @private
     * @param {Object} node
     * @returns {JQuery}
     */
    _renderHook: function (node) {
        var hook_id = _.uniqueId();
        this.hook_nodes[hook_id] = {
            node: node,
            position: 'after',
        };
        var $hook = $('<span>', {
            class: 'o_web_studio_hook',
            data: {
                hook_id: hook_id,
            }
        });
        return $hook;
    },
    /**
     * @override
     */
    _setState: function () {
        this._super.apply(this, arguments);

        if (this.options.showInvisible) {
            this.qweb_context.kanban_compute_domain = function () {
                // always consider a domain falsy to see invisible elements
                return false;
            };
        }
    },
});

return KanbanRecordEditor;

});
