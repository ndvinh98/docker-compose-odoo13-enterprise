odoo.define('web_studio.EditMenu', function (require) {
"use strict";

var config = require('web.config');
var core = require('web.core');
var Dialog = require('web.Dialog');
var FieldManagerMixin = require('web.FieldManagerMixin');
var form_common = require('web.view_dialogs');
var relational_fields = require('web.relational_fields');
var session = require('web.session');
var StandaloneFieldManagerMixin = require('web.StandaloneFieldManagerMixin');
var Widget = require('web.Widget');

var Many2One = relational_fields.FieldMany2One;
var _t = core._t;

var MenuItem = Widget.extend({
    template: 'web_studio.EditMenu.MenuItem',
    events: {
        'click .o_web_edit_menu': '_onClick',
    },
    /**
     * @constructor
     * @param {Widget} parent
     * @param {Object} menu_data
     * @param {Integer} current_primary_menu
     */
    init: function (parent, menu_data, current_primary_menu) {
        this._super.apply(this, arguments);
        this.menu_data = menu_data;
        this.current_primary_menu = current_primary_menu;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    editMenu: function () {
        new EditMenuDialog(this, this.menu_data, this.current_primary_menu)
            .open();
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Open a dialog to edit the clicked menu.
     *
     * @private
     * @param {Event} event
     */
    _onClick: function (event) {
        event.preventDefault();
        this.editMenu();
    },
});

var EditMenuDialog = Dialog.extend({
    template: 'web_studio.EditMenu.Dialog',
    events: _.extend({}, Dialog.prototype.events, {
        'click a.js_add_menu': '_onAddMenu',
        'click button.js_edit_menu': '_onEditMenu',
        'click button.js_delete_menu': '_onDeleteMenu',
    }),
    /**
     * @constructor
     * @param {Widget} parent
     * @param {Object} menu_data
     * @param {Integer} current_primary_menu
     */
    init: function (parent, menu_data, current_primary_menu) {
        var options = {
            title: _t('Edit Menu'),
            size: 'medium',
            dialogClass: 'o_web_studio_edit_menu_modal',
            buttons: [{
                text: _t("Confirm"),
                classes: 'btn-primary',
                click: this._onSave.bind(this),
            }, {
                text: _t("Cancel"),
                close: true,
            }],
        };
        this.current_primary_menu = current_primary_menu;
        this.roots = this.getMenuDataFiltered(menu_data);

        this.to_delete = [];
        this.to_move = {};

        this._super(parent, options);
    },
    /**
     * @override
     */
    start: function () {
        this.$('.oe_menu_editor').nestedSortable({
            listType: 'ul',
            handle: 'div',
            items: 'li',
            maxLevels: 5,
            toleranceElement: '> div',
            forcePlaceholderSize: true,
            opacity: 0.6,
            placeholder: 'oe_menu_placeholder',
            tolerance: 'pointer',
            attribute: 'data-menu-id',
            expression: '()(.+)', // nestedSortable takes the second match of an expression (*sigh*)
            relocate: this.moveMenu.bind(this),
        });

        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @param {Object} menu_data
     * @returns {Object}
     */
    getMenuDataFiltered: function (menu_data) {
        var self = this;
        var menus = menu_data.children.filter(function (el) {
            return el.id === self.current_primary_menu;
        });
        return menus;
    },
    /**
     * @param {Event} ev
     */
    moveMenu: function (ev, ui) {
        var self = this;

        var $menu = $(ui.item);
        var menu_id = $menu.data('menu-id');

        this.to_move[menu_id] = {
            parent_id: $menu.parents('[data-menu-id]').data('menu-id') || this.current_primary_menu,
            sequence: $menu.index(),
        };

        // Resequence siblings
        _.each($menu.siblings('li'), function (el) {
            var menu_id = $(el).data('menu-id');
            if (menu_id in self.to_move) {
                self.to_move[menu_id].sequence = $(el).index();
            } else {
                self.to_move[menu_id] = {sequence: $(el).index()};
            }
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Boolean} keep_open
     */
    _reloadMenuData: function (keep_open) {
        this.trigger_up('reload_menu_data', {keep_open: keep_open});
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Event} ev
     */
    _onAddMenu: function (ev) {
        ev.preventDefault();

        var self = this;
        new NewMenuDialog(this, {
            parent_id: this.current_primary_menu,
            on_saved: function () {
                self._saveChanges().then(function () {
                    self._reloadMenuData(true);
                });
            },
        }).open();
    },
    /**
     * @private
     * @param {Event} ev
     */
    _onDeleteMenu: function (ev) {
        var $menu = $(ev.currentTarget).closest('[data-menu-id]');
        var menu_id = $menu.data('menu-id') || 0;
        if (menu_id) {
            this.to_delete.push(menu_id);
        }
        $menu.remove();
    },
    /**
     * @private
     * @param {Event} ev
     */
    _onEditMenu: function (ev) {
        var self = this;
        var menu_id = $(ev.currentTarget).closest('[data-menu-id]').data('menu-id');
        new form_common.FormViewDialog(this, {
            res_model: 'ir.ui.menu',
            res_id: menu_id,
            on_saved: function () {
                self._saveChanges().then(function () {
                    self._reloadMenuData(true);
                });
            },
        }).open();
    },
    /**
     * Save the current changes (in `to_move` and `to_delete`).
     *
     * @private
     */
    _onSave: function () {
        var self = this;
        if (
            !_.isEmpty(this.to_move) ||
            !_.isEmpty(this.to_delete)
        ) {
            // do not make an rpc (and then reload menu) if there is nothing to save
            this._saveChanges().then(function () {
                self._reloadMenuData();
            });
        } else {
            this.close();
        }
    },
    /**
     * Save the current changes (in `to_move` and `to_delete`).
     *
     * @private
     * @returns {Promise}
     */
    _saveChanges: function () {
        return this._rpc({
            model: 'ir.ui.menu',
            method: 'customize',
            kwargs: {
                to_move: this.to_move,
                to_delete: this.to_delete,
            },
        });
    },
});

// The Many2One field is extended to catch when a model is quick created
// to avoid letting the user click on the save menu button
// before the model is created.
var EditMenuMany2One = Many2One.extend({
    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     * @private
     */
    _quickCreate: function () {
        this.trigger_up('edit_menu_disable_save');
        var def = this._super.apply(this, arguments);
        Promise.resolve(def).then(this.trigger_up.bind(this, 'edit_menu_enable_save'),
                                  this.trigger_up.bind(this, 'edit_menu_enable_save'));

    },
});

var NewMenuDialog = Dialog.extend(StandaloneFieldManagerMixin, {
    template: 'web_studio.EditMenu.Dialog.New',
    custom_events: _.extend({}, Dialog.prototype.custom_events, FieldManagerMixin.custom_events, {
        edit_menu_disable_save: function () {
            this.$footer.find('.confirm_button').attr("disabled", "disabled");
        },
        edit_menu_enable_save: function () {
            this.$footer.find('.confirm_button').removeAttr("disabled");
        },
    }),

    /**
     * @constructor
     * @param {Widget} parent
     * @param {Object} params
     * @param {Integer} params.parent_id - ID of the parent menu
     * @param {function} params.on_saved - callback executed after saving
     */
    init: function (parent, params) {
        this.parent_id = params.parent_id;
        this.on_saved = params.on_saved;
        var options = {
            title: _t('Create a new Menu'),
            size: 'small',
            buttons: [{
                text: _t("Confirm"),
                classes: 'btn-primary confirm_button',
                click: this._onSave.bind(this)
            }, {
                text: _t("Cancel"),
                close: true
            }],
        };
        this._super(parent, options);
        StandaloneFieldManagerMixin.init.call(this);
    },
    /**
     * @override
     */
    start: function () {
        var self = this;
        var defs = [];
        this.opened().then(function () {
            self.$modal.addClass('o_web_studio_add_menu_modal');
            // focus on input
            self.$el.find('input[name="name"]').focus();
        });

        defs.push(this._super.apply(this, arguments));

        defs.push(this.model.makeRecord('ir.actions.act_window', [{
            name: 'model',
            relation: 'ir.model',
            type: 'many2one',
            domain: [['transient', '=', false], ['abstract', '=', false]],
        }]).then(function (recordID) {
            var options = {
                mode: 'edit',
            };
            var record = self.model.get(recordID);
            self.many2one = new EditMenuMany2One(self, 'model', record, options);
            self.many2one.nodeOptions.no_create_edit = !config.isDebug();
            self._registerWidget(recordID, 'model', self.many2one);
            self.many2one.appendTo(self.$('.js_model'));
        }));
        return Promise.all(defs);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {String} menu_name
     * @param {Integer} parent_id
     * @param {Integer} model_id
     * @returns {Promise}
     */
    _createNewMenu: function (menu_name, parent_id, model_id) {
        core.bus.trigger('clear_cache');
        return this._rpc({
            route: '/web_studio/create_new_menu',
            params: {
                menu_name: menu_name,
                model_id: model_id,
                parent_id: parent_id,
                context: session.user_context,
            },
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Creates the new menu.
     *
     * @private
     */
    _onSave: function () {
        var self = this;

        this.$footer.find('.confirm_button').addClass('disabled');

        var name = this.$el.find('input').first().val();
        var model_id = this.many2one.value && this.many2one.value.res_id;

        var def = this._createNewMenu(name, this.parent_id, model_id);
        def.then(function () {
            self.on_saved();
        }).guardedCatch(function () {
            self.$footer.find('.confirm_button').removeClass('disabled');
        });
    },


});

return {
    MenuItem: MenuItem,
    Dialog: EditMenuDialog,
};

});
