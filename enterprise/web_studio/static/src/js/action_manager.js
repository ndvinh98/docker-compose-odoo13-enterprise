odoo.define('web_studio.ActionManager', function (require) {
"use strict";

var ActionManager = require('web.ActionManager');

var bus = require('web_studio.bus');

/**
 * Logic of the Studio action manager: the Studio client action (i.e.
 * "action_web_studio_action_editor") will always be pushed on top of another
 * controller, which corresponds to the edited action by Studio.
 */

ActionManager.include({
    custom_events: _.extend({}, ActionManager.prototype.custom_events, {
        'reload_action': '_onReloadAction',
    }),

    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        this.studioControllerIndex = undefined;
        bus.on('edition_mode_entered', this, this._onEditionModeEntered);
        bus.on('studio_toggled', this, this._onStudioToggled);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    clearUncommittedChanges: function () {
        var currentController = this.getCurrentController();
        if (currentController && !currentController.widget) {
            // navigate with Studio will push a "fake" controller without widget
            // (see @_executeWindowAction) before doAction on the Studio action
            // but @_executeAction will call this function so no need to do
            // anything in this case
            return Promise.resolve();
        }
        return this._super.apply(this, arguments);
    },
    /**
     * Returns the action of the Studio controller in the controllerStack, i.e.
     * the action currently edited in Studio.
     *
     * @returns {Object|null}
     */
    getCurrentStudioAction: function () {
        var controller = this.getCurrentStudioController();
        return controller ? this.actions[controller.actionID] : null;
    },
    /**
     * Returns the Studio controller in the controllerStack.
     *
     * @returns {Object|null}
     */
    getCurrentStudioController: function () {
        var controllerID = this.controllerStack[this.studioControllerIndex];
        var controller = this.controllers[controllerID];
        return controller;
    },
    /**
     * we cannot use getCurrentAction because when navigating in Studio, we
     * bypass the logic (and getCurrentController has not widget key)
     */
    getLastAction: function () {
        var currentControllerID = _.last(this.controllerStack);
        var controller = currentControllerID ? this.controllers[currentControllerID] : null;
        return controller ? this.actions[controller.actionID] : null;
    },
    /**
     * Restores the action currently edited by Studio.
     *
     * @returns {Promise}
     */
    restoreStudioAction: function () {
        var self = this;
        var studioControllerIndex = this.studioControllerIndex;
        var controllerID = this.controllerStack[studioControllerIndex];
        var controller = this.controllers[controllerID];
        var action = this.actions[controller.actionID];

        // find the index in the controller stack of the first controller
        // associated to the action to restore
        var index = _.findIndex(this.controllerStack, function(controllerID) {
            var controller = self.controllers[controllerID];
            return controller.actionID === action.jsID;
        });

        // reset to correctly update the breadcrumbs
        this.studioControllerIndex = undefined;

        var options = {
            additional_context: action.context,
            index: index,
            viewType: this.studioViewType,
        };
        if (this.studioViewType === 'form') {
            // widget could be unset in case of navigation (see @_executeWindowAction)
            if (controller.widget) {
                options.resID = controller.widget.exportState().currentId;
            }
        }
        return this.doAction(action.id, options);
    },
    /**
     * Restores the first controller after Studio controller.
     */
    studioHistoryBack: function () {
        var controller = this.controllerStack[this.studioControllerIndex + 1];
        this._restoreController(controller);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Controllers pushed in the controller stack for actions flagged with
     * 'studioNavigation' don't have an instantiated widget, so in this case,
     * there is nothing to detach from the DOM (see @_executeWindowAction).
     *
     * @override
     * @private
     */
    _detachCurrentController: function () {
        var currentAction = this.getCurrentAction();
        if (currentAction && !currentAction.studioNavigation) {
            this._super.apply(this, arguments);
        }
    },
    /**
     * Overrides to deal with actions tagged for the Studio navigation by the
     * WebClient.
     *
     * @override
     * @private
     */
    _executeWindowAction: function (action, options) {
        if (action.studioNavigation) {
            // We don't call _pushController or super here to avoid destroying
            // the previous actions ; they will be destroyed afterwards (see
            // override of @_pushController). We just create a new controller
            // and push it in the controller stack.
            this._processStudioAction(action, options);
            this.actions[action.jsID] = action;
            var controller = {
                actionID: action.jsID,
                jsID: _.uniqueId('controller_'),
            };
            this.controllers[controller.jsID] = controller;
            this.controllerStack.push(controller.jsID);

            // as we are navigating through Studio (with a menu), reset the
            // breadcrumb index
            this.studioControllerIndex = 0;
            this.navigatingInStudio = true;

            return Promise.resolve(action);
        }
        return this._super.apply(this, arguments);
    },
    /**
     * @private
     * @override
     */
    _getControllerStackIndex: function (options) {
        if (options.studio_clear_studio_breadcrumbs) {
            // only display the controllers that are after Studio in the
            // breadcrumbs
            return this.studioControllerIndex + 1;
        }
        return this._super.apply(this, arguments);
    },
    /**
     * @override
     * @private
     */
    _pushController: function (controller) {
        var length;
        if (this.navigatingInStudio) {
            // we are navigating inside Studio, so we destroy the whole
            // controller stack except the last controller, which is the one
            // associated with the action edited by Studio
            this.navigatingInStudio = false;
            length = this.controllerStack.length;
            var toDestroy = this.controllerStack.slice(0, length - 1);
            this._removeControllers(toDestroy);
            this.controllerStack = this.controllerStack.slice(length - 1);
            // set controller index to 1 as this is its position in the stack
            controller.index = 1;
        }

        this._super.apply(this, arguments);

        if (this.studioControllerIndex !== undefined) {
            // we are inside studio, so we update the breadcrumbs once the
            // controller has been added to the controllerStack (from Studio
            // controller excluded, to the last but one controller, which will
            // add its part to the breadcrumbs itself)
            // updating it afterwards is easier than trying to guess what will
            // be the controllerStack (after the push) beforehand
            var indexFrom = this.studioControllerIndex + 1;
            var indexTo = this.controllerStack.length - 1;
            var breadcrumbs = this._getBreadcrumbs(this.controllerStack.slice(indexFrom, indexTo));
            controller.widget.updateControlPanel({breadcrumbs: breadcrumbs}, {clear: false});
        }
    },
    /**
     * @_executeWindowAction is overridden when navigating in Studio but some
     * processing in said function still needs to be done.
     *
     * @private
     * @param {Object} action
     */
    _processStudioAction: function (action) {
        // needed in _createViewController
        action.controllers = {};

        // similar to what is done in @_generateActionViews), but without
        // _loadViews - needed in Submenu and ActionEditor to have the same
        // structure than if the action was opened after being executed
        var views = _.map(action.views, function (view) {
            return {
                type: view[1],
                viewID: view[0],
            };
        });
        action._views = action.views;  // save the initial attribute
        action.views = views;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /*
     * @private
     * @param {string} viewType
     */
    _onEditionModeEntered: function (viewType) {
        if (viewType !== 'search') {
            this.studioViewType = viewType;
        }
    },
    /**
     * Overrides to let the event bubble if the push_state comes from Studio.
     *
     * @override
     * @private
     */
    _onPushState: function (ev) {
        if (!ev.data.studioPushState) {
            this._super.apply(this, arguments);
        }
    },
    /**
     * @private
     * @param {OdooEvent} ev
     * @param {string} ev.data.actionID
     */
    _onReloadAction: function (ev) {
        var self = this;
        var action = _.findWhere(this.actions, {id: ev.data.actionID});
        this._loadAction(action.id).then(function (result) {
            self._preprocessAction(result, {additional_context: action.context});
            self._processStudioAction(result, {});

            result.jsID = action.jsID; // used in @restoreStudioAction
            // update internal reference to the old action
            self.actions[action.jsID] = result;

            bus.trigger('action_changed', result);
            if (ev.data.onSuccess) {
                ev.data.onSuccess(result);
            }
        });
    },
    /**
     * @private
     * @param {string} mode
     */
    _onStudioToggled: function (mode) {
        if (mode === 'main') {
            // Studio has directly been opened on the action so the action to
            // restore is not the last one (which is Studio) but the one before
            this.studioControllerIndex = this.controllerStack.length - 2;
        }
    },
});

});
