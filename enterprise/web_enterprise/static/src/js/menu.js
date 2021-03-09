odoo.define('web_enterprise.Menu', function (require) {
"use strict";

var config = require('web.config');
var core = require('web.core');
var dom = require('web.dom');
var Widget = require('web.Widget');
var SystrayMenu = require('web.SystrayMenu');
var UserMenu = require('web.UserMenu');

UserMenu.prototype.sequence = 0; // force UserMenu to be the right-most item in the systray
SystrayMenu.Items.push(UserMenu);

var QWeb = core.qweb;

var Menu = Widget.extend({
    template: 'Menu',
    menusTemplate: 'Menu.sections',
    events: {
        'click .o_menu_toggle': '_onToggleHomeMenu',
        'mouseover .o_menu_sections > li:not(.show)': '_onMouseOverMenu',
        'click .o_menu_brand': '_onAppNameClicked',
    },

    init: function (parent, menu_data) {
        var self = this;
        this._super.apply(this, arguments);
        this.home_menu_displayed = false;
        this.backbutton_displayed = false;

        this.$menu_sections = {};
        this.menu_data = menu_data;

        // Prepare navbar's menus
        var $menu_sections = $(QWeb.render(this.menusTemplate, {
            menu_data: this.menu_data,
        }));
        $menu_sections.filter('section').each(function () {
            self.$menu_sections[parseInt(this.className, 10)] = $(this).children('li');
        });

        // Bus event
        core.bus.on('change_menu_section', this, this.change_menu_section);
        core.bus.on('toggle_mode', this, this.toggle_mode);
    },
    start: function () {
        var self = this;

        this.$menu_toggle = this.$('.o_menu_toggle');
        this.$menu_brand_placeholder = this.$('.o_menu_brand');
        this.$section_placeholder = this.$('.o_menu_sections');

        // Navbar's menus event handlers
        var on_secondary_menu_click = function (ev) {
            ev.preventDefault();
            var menu_id = $(ev.currentTarget).data('menu');
            var action_id = $(ev.currentTarget).data('action-id');
            self._on_secondary_menu_click(menu_id, action_id);
        };
        var menu_ids = _.keys(this.$menu_sections);
        var primary_menu_id, $section;
        for(var i = 0; i < menu_ids.length; i++) {
            primary_menu_id = menu_ids[i];
            $section = this.$menu_sections[primary_menu_id];
            $section.on('click', 'a[data-menu]', self, on_secondary_menu_click.bind(this));
        }

        // Systray Menu
        this.systray_menu = new SystrayMenu(this);
        var autoMoreMenu = this.systray_menu.attachTo(this.$('.o_menu_systray')).then(function () {
            dom.initAutoMoreMenu(self.$section_placeholder, {
                maxWidth: function () {
                    return self.$el.width() - (self.$menu_toggle.outerWidth(true) + self.$menu_brand_placeholder.outerWidth(true) + self.systray_menu.$el.outerWidth(true));
                },
            });
        });

        return Promise.all([this._super.apply(this, arguments), autoMoreMenu]);
    },
    toggle_mode: function (home_menu, overapp) {
        this.home_menu_displayed = !!home_menu;
        this.backbutton_displayed = this.home_menu_displayed && !!overapp;

        this.$menu_toggle.toggleClass('fa-chevron-left', this.home_menu_displayed)
                         .toggleClass('fa-th', !this.home_menu_displayed);
        this.$menu_toggle.toggleClass('d-none', this.home_menu_displayed && !this.backbutton_displayed);
        this.$menu_brand_placeholder.toggleClass('d-none', this.home_menu_displayed);
        this.$section_placeholder.toggleClass('d-none', this.home_menu_displayed);

        if (!home_menu) {
            // we force here a recomputation of the layout to make sure that the
            // menus are properly rearranged (if there are too many for the size
            // of the screen)
            core.bus.trigger('resize');
        }
    },
    change_menu_section: function (primary_menu_id) {
        if (!this.$menu_sections[primary_menu_id]) {
            this._updateMenuBrand();
            return; // unknown menu_id
        }

        if (this.current_primary_menu === primary_menu_id) {
            return; // already in that menu
        }

        if (this.current_primary_menu) {
            this.$menu_sections[this.current_primary_menu].detach();
        }

        // Get back the application name
        for (var i = 0; i < this.menu_data.children.length; i++) {
            if (this.menu_data.children[i].id === primary_menu_id) {
                this._updateMenuBrand(this.menu_data.children[i].name);
                break;
            }
        }

        this.$menu_sections[primary_menu_id].appendTo(this.$section_placeholder);
        this.current_primary_menu = primary_menu_id;

        core.bus.trigger('resize');
    },
    _trigger_menu_clicked: function(menu_id, action_id) {
        this.trigger_up('menu_clicked', {
            id: menu_id,
            action_id: action_id,
            previous_menu_id: this.current_secondary_menu || this.current_primary_menu,
        });
    },
    /**
     * Updates the name of the app in the menu to the value of brandName.
     * If brandName is falsy, hides the menu and its sections.
     *
     * @private
     * @param {brandName} string
     */
    _updateMenuBrand: function (brandName) {
        if (brandName) {
            this.$menu_brand_placeholder.text(brandName).show();
            this.$section_placeholder.show();
        } else {
            this.$menu_brand_placeholder.hide()
            this.$section_placeholder.hide();
        }
    },
    _on_secondary_menu_click: function(menu_id, action_id) {
        var self = this;

        // It is still possible that we don't have an action_id (for example, menu toggler)
        if (action_id) {
            self._trigger_menu_clicked(menu_id, action_id);
            this.current_secondary_menu = menu_id;
        }
    },
    /**
     * Helpers used by web_client in order to restore the state from
     * an url (by restore, read re-synchronize menu and action manager)
     */
    action_id_to_primary_menu_id: function (action_id) {
        var primary_menu_id, found;
        for (var i = 0; i < this.menu_data.children.length && !primary_menu_id; i++) {
            found = this._action_id_in_subtree(this.menu_data.children[i], action_id);
            if (found) {
                primary_menu_id = this.menu_data.children[i].id;
            }
        }
        return primary_menu_id;
    },
    _action_id_in_subtree: function (root, action_id) {
        // action_id can be a string or an integer
        if (root.action && root.action.split(',')[1] === String(action_id)) {
            return true;
        }
        var found;
        for (var i = 0; i < root.children.length && !found; i++) {
            found = this._action_id_in_subtree(root.children[i], action_id);
        }
        return found;
    },
    menu_id_to_action_id: function (menu_id, root) {
        if (!root) {
            root = $.extend(true, {}, this.menu_data);
        }

        if (root.id === menu_id) {
            return root.action.split(',')[1] ;
        }
        for (var i = 0; i < root.children.length; i++) {
            var action_id = this.menu_id_to_action_id(menu_id, root.children[i]);
            if (action_id !== undefined) {
                return action_id;
            }
        }
        return undefined;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Returns the id of the current primary (first level) menu.
     *
     * @returns {integer}
     */
    getCurrentPrimaryMenu: function () {
        return this.current_primary_menu;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * When clicking on app name, opens the first action of the app
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onAppNameClicked: function (ev) {
        ev.preventDefault();
        var actionID = this.menu_id_to_action_id(this.current_primary_menu);
        this._trigger_menu_clicked(this.current_primary_menu, actionID);
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onMouseOverMenu: function (ev) {
        if (config.device.isMobile) {
            return;
        }
        var $target = $(ev.currentTarget);
        var $opened = $target.siblings('.show');
        if ($opened.length) {
            $opened.find('[data-toggle="dropdown"]:first').dropdown('toggle');
            $opened.removeClass('show');
            $target.find('[data-toggle="dropdown"]:first').dropdown('toggle');
            $target.addClass('show');
        }
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onToggleHomeMenu: function (ev) {
        ev.preventDefault();
        this.trigger_up(this.home_menu_displayed ? 'hide_home_menu' : 'show_home_menu');
        this.$el.parent().removeClass('o_mobile_menu_opened');
    },
});

return Menu;

});
