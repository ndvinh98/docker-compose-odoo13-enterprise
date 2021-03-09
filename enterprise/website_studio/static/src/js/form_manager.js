odoo.define('website_studio.FormManager', function (require) {
"use strict";

/**
 * This is the widget used by studio to render the website forms linked to
 * the model being edited and to redirect to the frontend to modify
 * a given website form or to create a new website form.
 *
 * @module website_studio.FormManager
 */

var AbstractAction = require('web.AbstractAction');
var core = require('web.core');
var framework = require('web.framework');

var _t = core._t;

var FormManager = AbstractAction.extend({
    contentTemplate: 'website_studio.FormManager',

    events: {
        'click .o_web_studio_thumbnail': '_onClickThumbnail',
    },

    /**
     * Form Manager class

     * @constructor
     * @param {Widget} parent
     * @param {Object} context - The ir.actions.client
     * @param {Object} options - An object with possible values:
     *                           - action: all the information about
     *                              the action currently edited
     *                           - clear_breadcrumbs: a boolean
     *                              to reset the breadcrumbs
     */
    init: function (parent, action, options) {
        this._super.apply(this, arguments);
        this.action = options.action;
        this._onClickThumbnail = _.debounce(this._onClickThumbnail, 300, true);
    },
    /**
     * When the form manager is instantiated the willStart method is called
     * before the widget rendering. This method will make a rpc call to
     * gather the website forms information.
     *
     * @returns {Promise}
     */
    willStart: function () {
        var self = this;
        if (!this.action) {
            return Promise.reject();
        }
        this.res_model = this.action.res_model;
        return this._super.apply(this, arguments).then(function () {
            return self._rpc({
                route: '/website_studio/get_forms',
                params: {
                  res_model: self.res_model,
                },
            }).then(function (forms) {
                self.forms = forms;
            });
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * This method is called by the widget to redirect to the form in the
     * frontend and in edit mode.
     *
     * @private
     * @param {string} url
     */
    _redirectToForm: function (url) {
        url = url + '?enable_editor=1';
        framework.redirect(url);
    },
    /**
     * This method is called by the widget to create a new website form
     * for the model being edited and then call the '_redirectToForm' method
     * to reach this newly created website form.
     *
     * @private
     */
    _redirectToNewForm: function () {
        var self = this;
        this.getSession()
            .user_has_group('website.group_website_designer')
            .then(function (is_website_designer) {
                if (is_website_designer) {
                    self._rpc({
                        route: '/website_studio/create_form',
                        params: {
                            res_model: self.res_model,
                        },
                    }).then(function (url) {
                        self._redirectToForm(url);
                    });
                } else {
                    var msg = _t("Sorry, only users with the following" +
                        " access level are currently allowed to do that:" +
                        " 'Website/Editor and Designer'");
                    self.do_warn(_t("Error"), msg);
                }
            });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * intercept the click on a website form thumbnail and redirect to
     * a new or existing website form.
     *
     * @private
     * @param {jQuery.Event} ev
     */
    _onClickThumbnail: function (ev) {
        if ($(ev.currentTarget).data('new-form')) {
            this._redirectToNewForm();
        } else {
            this._redirectToForm($(ev.currentTarget).data('url'));
        }
    },
});

core.action_registry.add('action_web_studio_form', FormManager);

return FormManager;

});
