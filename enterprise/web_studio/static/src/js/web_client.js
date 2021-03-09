odoo.define('web_studio.WebClient', function (require) {
"use strict";

var ajax = require('web.ajax');
var core = require('web.core');
var session = require('web.session');
var WebClient = require('web.WebClient');

var bus = require('web_studio.bus');
var SystrayItem = require('web_studio.SystrayItem');

var _t = core._t;

WebClient.include({
    custom_events: _.extend({}, WebClient.prototype.custom_events, {
        'new_app_created': '_onNewAppCreated',
        'reload_menu_data': '_onReloadMenuData',
        'studio_icon_clicked': '_onStudioIconClicked',
        'studio_history_back': '_onStudioHistoryBack',
        'switch_studio_view': '_onSwitchStudioView',
    }),

    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);

        // can either be 'app_creator' or 'main' while in Studio
        this.studioMode = undefined;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    current_action_updated: function (action) {
        this._super.apply(this, arguments);

        // in Studio, the systray item is replaced by a "Close" button so no
        // need to update it
        if (!this.studioMode) {
            this._updateStudioSystray(this._isStudioEditable(action));
        }
    },
    /**
     * Considers the Studio menu when instatiating the menu.
     *
     * @override
     */
    instanciate_menu_widgets: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function() {
            if (self.studioMode === 'main') {
                var action = self.action_manager.getCurrentStudioAction();
                if (action) {
                    return self.menu.renderStudioMenu(action);
                }
            }
        });
    },
    /**
     * @override
     */
    do_action: function (action, options) {
        if (this.studioMode === 'main' && action.target === 'new') {
            // Wizards in the app creator can be opened (ex: Import wizard)
            // TODO: what if we modify target = 'curent' to modify it?
            this.do_warn("Studio", _t("Wizards are not editable with Studio."));
            return Promise.reject();
        }

        var blockPushState = this.studioMode && !action.studioNavigation;
        if (blockPushState) {
            // we are doing action inside Studio but as the currently edited
            // action in Studio does not change, the state cannot change
            options = options || {};
            options.pushState = false;
        }
        var prom =  this._super(action, options)
        prom.then(function (action) {
            if (blockPushState) {
                // pushState is reset to true in action_manager (see @doAction)
                // but we never want the state to be updated in Studio
                action.pushState = false;
            }
        });
        return prom;
    },
    /**
     * @override
     */
    on_app_clicked: function () {
        var self = this;
        if (this.studioMode) {
            // used to avoid a flickering issue (see @toggle_home_menu)
            this.openingMenu = true;
        }
        return this._super.apply(this, arguments).then(function () {
            // this is normally done by _on_app_clicked_done but should also be
            // done if the promise is rejected
            self.openingMenu = false;
        });
    },
    /**
     * Opens the App Creator action.
     *
     * @returns {Promise}
     */
    openAppCreator: function () {
        var self = this;
        return this.do_action('action_web_studio_app_creator').then(function () {
            self.menu.toggle_mode(true, false);  // hide the back button
        });
    },
    /**
     * @override
     */
    show_application: function () {
        var self = this;
        var qs = $.deparam.querystring();
        self.studioMode = _.contains(['main', 'app_creator'], qs.studio) ? qs.studio : false;
        var def = self.studioMode ? ajax.loadLibs({assetLibs: this._studioAssets}) : Promise.resolve();
        var _super = this._super;
        return def.then(function () {
            return _super.apply(self, arguments).then(function () {
                if (self.studioMode) {
                    self._updateContext();
                    return self._openStudio();
                }
            });
        });
    },
    /**
     * @override
     */
    toggle_home_menu: function (display) {
        if (this.studioMode) {
            if (display) {
                // use case: we are in Studio main and we toggle the home menu
                // --> will open the app_creator
                this.studioMode = 'app_creator';
            } else {
                var action = this.action_manager.getCurrentAction();
                if (action && action.tag === 'action_web_studio_app_creator') {
                    // use case: Studio has been toggled and the app creator is
                    // opened by clicking on the "New App" icon
                    this.studioMode = 'app_creator';
                } else {
                    // use case: being on the HomeMenu in Studio mode and then
                    // toggling the HomeMenu
                    this.studioMode = 'main';
                }
                if (this.openingMenu) {
                    // use case: navigating in an app from the app switcher
                    // the first toggle_home_menu will be triggered when opening
                    // a menu ; it must be prevented to avoid flickering
                    return;
                }
            }
            this._toggleStudioMode();
        } else {
            if (display) {
                // Studio icon is enabled in the home menu (to be able to always
                // open the AppCreator)
                this._updateStudioSystray(true);
            }
        }
        this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Closes Studio.
     *
     * @private
     * @returns {Promise}
     */
    _closeStudio: function () {
        var self = this;
        var def;
        var action = this.action_manager.getCurrentAction();

        if (this.home_menu_displayed) {
            this.toggle_home_menu(true);
            this.menu.toggle_mode(true, false);  // hide the back button
        } else if (action.tag === 'action_web_studio_app_creator') {
            // we are not in the home_menu but we want to display it
            this.toggle_home_menu(true);
            // use case: closing Studio from the AppCreator: remove the back
            // button in the home menu to avoid going back in the AppCreator
            // TODO: maybe clear the actionStack before instead?
            this.menu.toggle_mode(true, false);
        } else {
            def = this.action_manager.restoreStudioAction();
        }

        return Promise.resolve(def).then(function () {
            self._toggleStudioMode();
            self.$el.toggleClass('o_in_studio', !!self.studioMode);
        });
    },
    /**
     * Studio is disabled by default in systray.
     * Add conditions here to enable it.
     *
     * @private
     * @returns {Boolean} the 'Studio editable' property of an action
     */
    _isStudioEditable: function (action) {
        return action
               && action.xml_id
               && action.type === 'ir.actions.act_window'
               && action.res_model
               // we don't want to edit Settings as it is a special case of form view
               // this is a heuristic to determine if the action is Settings
               && (action.res_model.indexOf('settings') === -1 || action.res_model.indexOf('x_') === 0)
               // we don't want to edit Dashboard views
               && action.res_model !== 'board.board'
               ? true : false;
    },
    /**
     * Opens the Studio main action with the AM current action.
     *
     * @private
     * @param {string} [viewType]
     * @returns {Promise}
     */
    _navigateInStudio: function (viewType) {
        var self = this;
        // the action has been processed by the AM
        var action = this.action_manager.getLastAction();
        var options = {
            action: action,
            viewType: viewType,
        };
        return this._openStudioMain(options).then(function () {
            self.openingMenu = false;  // see @toggle_home_menu
        });
    },
    /**
     * @override
     */
    _openMenu: function (action, options) {
        var self = this;
        if (this.studioMode) {
            if (!this._isStudioEditable(action)) {
                this.do_warn("Studio", _t("This action is not editable by Studio"));
                return Promise.reject();
            }
            // tag the action for the actionManager
            action.studioNavigation = true;
        }
        return this._super.apply(this, arguments).then(function () {
            if (self.studioMode) {
                return self._navigateInStudio(options.viewType);
            }
        });
    },
    /**
     * @private
     * @returns {Promise}
     */
     _studioAssets: ['web_editor.compiled_assets_wysiwyg', 'web_studio.compiled_assets_studio'],
    _openStudio: function () {
        var self = this;
        var def = ajax.loadLibs({assetLibs: this._studioAssets});

        if (this.studioMode === 'main') {
            var action = this.action_manager.getCurrentAction();
            var controller = this.action_manager.getCurrentController();
            def = def.then(this._openStudioMain.bind(this, {
                action: action,
                controllerState: controller.widget.exportState(),
                viewType: controller.viewType,
            }));
        } else {
            def.then(function() {
                // the app creator is not opened here, it's opened by clicking on
                // the "New App" icon, when the HomeMenu is in `studio` mode.
                self.menu.toggle_mode(true, false);  // hide the back button
            });
        }

        return Promise.resolve(def).then(function () {
            self.$el.toggleClass('o_in_studio', !!self.studioMode);
            self._toggleStudioMode();
        });
    },
    /**
     * Opens the Studio main action with a specific action.
     *
     * @private
     * @param {Object} options
     * @param {Object} options.action
     * @param {string} options.action.res_model
     * @returns {Promise}
     */
    _openStudioMain: function (options) {
        return this.do_action('action_web_studio_action_editor', options);
    },
    /**
     * @private
     * @returns {Promise}
     */
    _redrawMenuWidgets: function () {
        var self = this;
        var oldHomeMenu = this.home_menu;
        var oldMenu = this.menu;
        return this.instanciate_menu_widgets().then(function () {
            if (oldHomeMenu) {
                oldHomeMenu.destroy();
            }
            if (oldMenu) {
                oldMenu.destroy();
            }
            self.menu.$el.prependTo(self.$el);
        });
    },
    /**
     * @private
     */
    _toggleStudioMode: function () {
        bus.trigger('studio_toggled', this.studioMode);

        // update the URL query string with Studio
        var qs = $.deparam.querystring();
        if (this.studioMode) {
            qs.studio = this.studioMode;
        } else {
            delete qs.studio;
        }
        var l = window.location;
        var url = l.protocol + "//" + l.host + l.pathname + '?' + $.param(qs) + l.hash;
        window.history.pushState({ path:url }, '', url);
    },
    /**
     * Writes in user_context that we are in Studio.
     * This is used server-side to flag with Studio the ir.model.data of
     * customizations.
     *
     * @private
     */
    _updateContext: function () {
        if (this.studioMode) {
            session.user_context.studio = 1;
        } else {
            delete session.user_context.studio;
        }
    },
    /**
     * Enables or disables the Studio systray icon.
     *
     * @private
     * @param {Boolean} show
     */
    _updateStudioSystray: function (show) {
        var systray_item = _.find(this.menu.systray_menu.widgets, function (item) {
            return item instanceof SystrayItem;
        });
        if (show) {
            systray_item.enable();
        } else {
            systray_item.disable();
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    _onStudioHistoryBack: function () {
        this.action_manager.studioHistoryBack();
    },
    /**
     * @private
     * @param {OdooEvent} ev
     */
    _onNewAppCreated: function (ev) {
        var self = this;
        this._redrawMenuWidgets().then(function () {
            self.on_app_clicked({
                data: {
                    menu_id: ev.data.menu_id,
                    action_id: ev.data.action_id,
                    options: {
                        viewType: 'form',
                    }
                }
            }).then(function () {
                self.menu.toggle_mode(false);  // display home menu button
            });
        });
    },
    /**
     * @private
     * @param {OdooEvent} ev
     */
    _onReloadMenuData: function (ev) {
        var self = this;

        var current_primary_menu = this.menu.current_primary_menu;
        core.bus.trigger('clear_cache'); // invalidate cache
        this._redrawMenuWidgets().then(function () {
            // reload previous state
            self.menu.toggle_mode(self.home_menu_displayed);
            self.menu.change_menu_section(current_primary_menu); // entering the current menu
            if (self.home_menu_displayed) {
                self.append_home_menu();
            }

            self.menu.switchMode(self.studioMode);
            self._updateStudioSystray(!!self.studioMode);
            self.home_menu.toggleStudioMode(!!self.studioMode);

            if (ev && ev.data.keep_open) {
                self.menu.edit_menu.editMenu();
            }
            if (ev && ev.data.def) {
                ev.data.def.resolve();
            }
        });
    },
    /**
     * @private
     */
    _onStudioIconClicked: function () {
        // the app creator will be opened if the home menu is displayed
        var newMode = this.home_menu_displayed ? 'app_creator': 'main';
        this.studioMode = this.studioMode ? false : newMode;

        this._updateContext();
        if (this.studioMode) {
            this._openStudio();
        } else {
            this._closeStudio();
        }
    },
    /**
     * @private
     * @param {OdooEvent} ev
     */
    _onSwitchStudioView: function (ev) {
        var action = this.action_manager.getCurrentStudioAction();
        var controller = this.action_manager.getCurrentStudioController();
        var params = _.extend({}, ev.data, {
            action: action,
        });
        if (controller.widget) {
            // not always the case in case of navigation
            params.controllerState = controller.widget.exportState();
        }
        this._openStudioMain(params);
    },
});

});
