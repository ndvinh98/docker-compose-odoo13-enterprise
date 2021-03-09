odoo.define('web_studio.SubMenu', function (require) {
"use strict";

var ajax = require('web.ajax');
var core = require('web.core');
var session = require('web.session');
var Widget = require('web.Widget');

var bus = require('web_studio.bus');

var _t = core._t;

var SubMenu = Widget.extend({
    template: 'web_studio.Menu',
    events: {
        'click .o_menu_sections > li': '_onMenu',
        'click .o_web_studio_undo': '_onUndo',
        'click .o_web_studio_redo': '_onRedo',
        'click .o_menu_sections .o_web_studio_views_icons > a': '_onIcon',
    },
    /**
     * @constructor
     * @param {Widget} parent
     * @param {Object} action
     */
    init: function (parent, action) {
        this._super.apply(this, arguments);
        this.action = action;
        this.active_view_types = this._getActiveViewTypes();
        this.activeMenu = 'Views';
        this.studio_actions = [{action: 'action_web_studio_action_editor', title: 'Views'}];
        this.multi_lang = session.multi_lang;
        this._isRedoToggled = false;
        this._isUndoToggled = false;

        bus.on('action_changed', this, this._onActionChanged);

        bus.on('undo_available', this, this._onToggleUndo.bind(this, true));
        bus.on('undo_not_available', this, this._onToggleUndo.bind(this, false));
        bus.on('redo_available', this, this._onToggleRedo.bind(this, true));
        bus.on('redo_not_available', this, this._onToggleRedo.bind(this, false));

        bus.on('toggle_snack_bar', this, this._onToggleSnackBar);

        bus.on('edition_mode_entered', this, this._onEditionModeEntered);
        bus.on('edition_x2m_entered', this, this._onX2MEntered);

        bus.on('report_template_opened', this, this._onReportTemplateOpened);
        bus.on('report_template_closed', this, this._onReportTemplateClosed);
    },
    /**
     * @override
     */
    renderElement: function() {
        this._super.apply(this, arguments);
        this._setActiveButtons();
        this._renderBreadcrumb();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Object} options
     */
    _addAction: function (options) {
        this.studio_actions.push(options);
        if (this.$el) {
            this.$('.o_menu_sections li a.active').removeClass('active');
            this.renderElement();
        }
    },
    /**
     * @private
     * @returns {string[]} the current action active view types
     */
    _getActiveViewTypes: function () {
        return _.map(this.action.views, function (view) {
            return view.type;
        });
    },
    /**
     * @private
     */
    _renderBreadcrumb: function () {
        var self = this;
        var $breadcrumb = $('<ol>').addClass('breadcrumb');
        _.each(this.studio_actions, function (bc, index) {
            $breadcrumb.append(
                self._renderBreadcrumbsLi(bc, index, self.studio_actions.length)
            );
        });
        this.$('.o_web_studio_breadcrumb')
            .empty()
            .append($breadcrumb);
    },
    /**
     * @private
     * @param {TODO} bc
     * @param {Integer} index
     * @param {Integer} length
     * @returns {JQuery}
     */
    _renderBreadcrumbsLi: function (bc, index, length) {
        var self = this;
        var is_last = (index === length-1);
        var li_content = bc.title && _.escape(bc.title.trim());
        var $bc = $('<li>', {class: 'breadcrumb-item'})
            .append(li_content)
            .toggleClass('active', is_last);
        if (!is_last) {
            $bc.click(function () {
                if (bc.action.res_model === 'ir.actions.report') {
                    // here we cannot do_action with replace_last_action as an
                    // ir.act_window.action is put before the ReportEditoAction
                    // (and the search view state will be lost)
                    self.studio_actions.pop();
                    self.trigger_up('studio_history_back');
                    self.renderElement();
                    return;
                }
                var options = {
                    action: self.action,
                    replace_last_action: true,
                    index: index,
                };
                if (bc.viewType) {
                    options.viewType = bc.viewType;
                }
                if (bc.x2mEditorPath) {
                    options.x2mEditorPath = bc.x2mEditorPath.slice();
                }
                if (bc.viewName) {
                    options.viewName = bc.viewName;
                }
                self._replaceAction(bc.action, bc.title, options);
            });
            $bc.toggleClass('o_back_button');
        }
        return $bc;
    },
    /**
     * Replace the current action and render the breadcrumb.
     *
     * @param {Object} action
     * @param {String} title
     * @param {Object} options
     */
    _replaceAction: function (action, title, options) {
        if (options.viewType) {
            if (options.index > 1) {
                this.studio_actions.length = options.index + 1;
            } else {
                this.studio_actions = [
                    {action: 'action_web_studio_action_editor', title: _t('Views')},
                    {action: action, title: title, viewType: options.viewType},
                ];
            }
        } else {
            this.studio_actions = [{action: action, title: title}];
        }
        delete options.index; // to prevent collision with option of doAction

        if (action === 'action_web_studio_action_editor') {
            // do not open the default view in this case
            options.noEdit = !options.viewType;
        }
        this.activeMenu = title;
        if (action._originalAction) {
            action = JSON.parse(action._originalAction);
        }
        if (action === 'action_web_studio_action_editor') {
            this.trigger_up('switch_studio_view', options);
        } else {
            this.do_action(action, options);
        }
        this.renderElement();
    },
    /**
     * @private
     */
    _setActiveButtons() {
        this.$(`.o_menu_sections li:contains(${this.activeMenu})`).addClass('active');
        if (this.studio_actions.length === 0) {
            return;
        }
        const currentAction = _.last(this.studio_actions);
        const isReportAction = currentAction.action === 'web_studio.action_edit_report';
        // undo / redo button should be displayed only when editing view or a report
        this.$('.o_web_studio_menu_undo_redo')
            .toggleClass('d-none', !currentAction.viewType && !isReportAction);
        this.$('.o_web_studio_breadcrumb')
            .toggleClass('o_web_studio_breadcrumb_report', isReportAction);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Object} new_action
     */
    _onActionChanged: function (new_action) {
        this.action = new_action;
        this.active_view_types = this._getActiveViewTypes();
        this.studio_actions = [{action: 'action_web_studio_action_editor', title: 'Views'}];
        // TODO: fwi stuff with viewManager
        this.renderElement();
    },
    /**
     * @private
     * @param {string} viewType
     */
    _onEditionModeEntered: function (viewType) {
        if (this.studio_actions.length === 1) {
            var bcOptions = {
                action: 'action_web_studio_action_editor',
                viewType: viewType,
                title: viewType.charAt(0).toUpperCase() + viewType.slice(1),
            };
            this._addAction(bcOptions);
        }
    },
    /**
     * @private
     * @param {Event} ev
     */
    _onIcon: function (ev) {
        ev.preventDefault();
        var view_name = $(ev.currentTarget).data('name');
        return this._replaceAction('action_web_studio_action_editor', view_name, {
            action: this.action,
            replace_last_action: true,
            viewType: view_name,
        });
    },
    /**
     * @private
     * @param {Event} ev
     */
    _onMenu: function (ev) {
        var $menu = $(ev.currentTarget);
        if (!$menu.data('name')) { return; }

        // do the corresponding action
        var title = $menu.text();
        var name = $menu.data('name');
        if (name === 'views') {
            this._replaceAction('action_web_studio_action_editor', title, {
                action: this.action,
                studio_clear_studio_breadcrumbs: true,
            });
        } else if (_.contains(['automations', 'reports', 'acl', 'filters', 'translations'], name)) {
            var self = this;
            ajax.jsonRpc('/web_studio/get_studio_action', 'call', {
                action_name: name,
                model: this.action.res_model,
                view_id: this.action.view_id[0],
            }).then(function (result) {
                self._replaceAction(result, title, {
                    studio_clear_studio_breadcrumbs: true,
                });
            });
        }
    },
    /**
     * @private
     */
    _onRedo: function () {
        bus.trigger('redo_clicked');
    },
    /**
     * @private
     */
    _onReportTemplateClosed: function () {
        if (this.studio_actions.length > 1) {
            this.studio_actions.pop();
        }
        this.renderElement();
    },
    /**
     * @private
     * @param {string} reportName
     */
    _onReportTemplateOpened: function (reportName) {
        if (this.studio_actions.length > 1) {
            this.studio_actions.pop();
        }
        var bcOptions = {
            action: 'web_studio.action_edit_report',
            title: reportName,
        };
        this._addAction(bcOptions);
    },
    /**
     * @private
     * @param {Boolean} display
     */
    _onToggleUndo: function (display) {
        this._isUndoToggled = display;
        this.$('.o_web_studio_undo').toggleClass('o_web_studio_active', display);
    },
    /**
     * @private
     * @param {Boolean} display
     */
    _onToggleRedo: function (display) {
        this._isRedoToggled = display;
        this.$('.o_web_studio_redo').toggleClass('o_web_studio_active', display);
    },
    /**
     * @private
     * @param {string} param0.type ['saved', 'saving']
     */
    _onToggleSnackBar(type) {
        switch (type) {
            case 'saved':
                this.$('.o_web_studio_snackbar_icon')
                    .removeClass('fa-spinner fa-pulse');
                this.$('.o_web_studio_snackbar_icon')
                    .addClass('show fa fa-check');
                this.$('.o_web_studio_snackbar_text')
                    .text(_t("Saved"));
                break;
            case 'saving':
                this.$('.o_web_studio_snackbar_icon')
                    .addClass('show fa fa-spinner fa-pulse');
                this.$('.o_web_studio_snackbar_text')
                    .text(_t("Saving"));
                break;
        }
    },
    /**
     * @private
     */
    _onUndo: function () {
        bus.trigger('undo_clicked');
    },
    /**
     * @private
     * @param {string} subviewType
     * @param {Object[]} x2mEditorPath
     */
    _onX2MEntered: function (subviewType, x2mEditorPath) {
        var bcOptions = {
            action: 'action_web_studio_action_editor',
            viewType: subviewType,
            x2mEditorPath: x2mEditorPath.slice(),
            title: _t('Subview ') + subviewType,
        };
        this._addAction(bcOptions);
    },
});

return SubMenu;

});
