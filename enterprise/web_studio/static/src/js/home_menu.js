odoo.define('web_studio.HomeMenu', function (require) {
"use strict";

var core = require('web.core');
var Dialog = require('web.Dialog');
var session = require('web.session');
var web_client = require('web.web_client');
var HomeMenu = require('web_enterprise.HomeMenu');

var bus = require('web_studio.bus');
var IconCreator = require('web_studio.IconCreator');

var QWeb = core.qweb;
var _t = core._t;

HomeMenu.include({
    events: _.extend(HomeMenu.prototype.events, {
        'click .o_web_studio_edit_icon': '_onEditIcon',
        'click .o_web_studio_new_app': '_onNewApp',
    }),
    /**
     * @override
     */
    start: function () {
        bus.on('studio_toggled', this, this.toggleStudioMode);
        return this._super.apply(this, arguments);
    },
    /**
     * @override
     */
    on_attach_callback: function () {
        this.in_DOM = true;
        this._super.apply(this, arguments);
    },
    /**
     * @override
     */
    on_detach_callback: function () {
        this._super.apply(this, arguments);
        this.in_DOM = false;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @param {boolean} [display]
     */
    toggleStudioMode: function (display) {
        this._inStudioMode = display;
        if (!this.in_DOM) {
            return;
        }
        if (display) {
            this._state = this._getInitialState();
            this.on_detach_callback();  // de-bind hanlders on home menu
            this.in_DOM = true;  // avoid effect of on_detach_callback
        } else {
            this.on_attach_callback();
        }
        this._render();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Overrides to add a new app icon in Studio and a small button to edit
     * existing icons.
     *
     * @private
     * @override
     */
    _render: function () {
        this._super.apply(this, arguments);
        if (this._inStudioMode) {
            this.$('.o_app').append(
                $('<i>', {
                    class: "o_web_studio_edit_icon fa fa-pencil-square",
                })
            );
            this._renderNewApp();
        }
    },
    /**
     * Add the 'New App' icon.
     *
     * @private
     */
    _renderNewApp: function () {
        this._$newApp = $(QWeb.render('web_studio.AppCreator.NewApp'));
        this._$newApp.appendTo(this.$('.o_apps'));
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Event} ev
     */
    _onEditIcon: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();  // do not open the menu

        var self = this;
        var menuID = $(ev.currentTarget).closest('.o_app').data('menu');
        var app = _.findWhere(this._state.apps, {id: menuID});
        this.iconCreator = new IconCreator(this, {
            background_color: app.web_icon.background,
            color: app.web_icon.color,
            icon_class: app.web_icon.class,
            webIconData: app.web_icon_data,
        });
        var fragment = document.createDocumentFragment();
        this.iconCreator.appendTo(fragment).then(function () {
            new Dialog(self, {
                dialogClass: 'o_web_studio_edit_menu_icon_modal',
                size: 'medium',
                title: _t('Edit Application Icon'),
                $content: $('<div>').append(self.iconCreator.$el),
                buttons: [{
                    text: _t("Confirm"),
                    classes: 'btn-primary',
                    click: self._onIconSaved.bind(self, menuID),
                }, {
                    text: _t("Cancel"),
                    close: true,
                }],
            }).open();
        });
    },
    /**
     * @private
     * @param {number} menuID
     */
    _onIconSaved: function (menuID) {
        var self = this;
        this._rpc({
            route: '/web_studio/edit_menu_icon',
            params: {
                menu_id: menuID,
                icon: this.iconCreator.getValue(),
                context: session.user_context,
            },
        }).then(function () {
            self.trigger_up('reload_menu_data');
        });
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onNewApp: function (ev) {
        ev.preventDefault();
        web_client.openAppCreator().then(function () {
            core.bus.trigger('toggle_mode', true, false);
        });
    },
});

});
