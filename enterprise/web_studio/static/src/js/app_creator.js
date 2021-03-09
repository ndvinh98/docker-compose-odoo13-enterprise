odoo.define('web_studio.AppCreator', function (require) {
"use strict";

var AbstractAction = require('web.AbstractAction');
var config = require('web.config');
var core = require('web.core');
var framework = require('web.framework');
var relational_fields = require('web.relational_fields');
var session = require('web.session');

var StandaloneFieldManagerMixin = require('web.StandaloneFieldManagerMixin');
var IconCreator = require('web_studio.IconCreator');

var QWeb = core.qweb;
var FieldMany2One = relational_fields.FieldMany2One;
var _t = core._t;

var AppCreator = AbstractAction.extend(StandaloneFieldManagerMixin, {
    contentTemplate: 'web_studio.AppCreator',
    events: {
        'click .o_web_studio_app_creator_next': '_onNext',
        'click .o_web_studio_app_creator_back': '_onBack',
        'change input': '_onCheckFields',
        'keyup input': '_onCheckFields',
        'input input': '_onCheckFields',
        'paste input': '_onCheckFields',
        'focus input.o_web_studio_app_creator_field_warning': '_onWarning',
        'keyup input.o_web_studio_app_creator_field_warning': '_onWarning',
    },
    /**
     * @constructor
     */
    init: function () {
        this._super.apply(this, arguments);
        StandaloneFieldManagerMixin.init.call(this);
        this.currentStep = 1;
        this.debug = config.isDebug();
    },
    /**
     * @override
     */
    start: function () {
        // namespace the event to remove it easily (because of bind)
        $('body').on('keypress.app_creator', this._onKeyPress.bind(this));

        return this._super.apply(this, arguments).then(this._update.bind(this));
    },
    /**
     * @override
     */
    destroy: function () {
        $('body').off('keypress.app_creator');
        this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Re-render the widget and update its content according to @currentStep.
     * @returns {Promise}
     */
    update: function () {
        var self = this;
        this.renderElement();
        return this._update().then(function () {
            // focus on input
            self.$('input').first().focus();
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /*
     * Check that all the fields in the form are correctly filled, according to
     * the @currentStep. If one isn't, this is emphasized by ´_fieldWarning´.
     *
     * @private
     */
    _checkFields: function (field_warning) {
        var ready = false;
        var warningClass = 'o_web_studio_app_creator_field_warning';

        if (this.currentStep === 2) {
            var app_name = this.$('input[name="app_name"]').val();
            if (app_name) {
                ready = true;
                this.$next.find('span').text(_t('Next'));
            } else if (field_warning) {
                this.$next.find('span').empty();
                this.$('.o_web_studio_app_creator_name').addClass(warningClass);
            }
        } else if (this.currentStep === 3) {
            var menu_name = this.$('input[name="menu_name"]').val();
            if (field_warning && !menu_name) {
                this.$('.o_web_studio_app_creator_menu').addClass(warningClass);
            }
            var model_id = this.many2one.value && this.many2one.value.res_id;
            var model_choice = this.$('input[name="model_choice"]').is(':checked');

            if (field_warning && model_choice && !model_id) {
                this.$('.o_web_studio_app_creator_model').addClass(warningClass);
            }

            this.$next.find('span').empty();
            if (menu_name) {
                // we can only select a model in debug mode
                if (!this.debug || !model_choice || (model_choice && model_id)) {
                    ready = true;
                    this.$next.find('span').text(_t('Create your app'));
                }
            }
            this.$('.o_web_studio_app_creator_model').toggle(model_choice);
        }

        this.$next.toggleClass('is_ready', ready);
        return ready;
    },
    /**
     * @private
     * @param {String} app_name
     * @param {String} menu_name
     * @param {Integer} model_id
     * @param {Integer/Array} icon - can either be:
     *  - the ir.attachment id of the uploaded image
     *  - if the icon has been created with the IconCreator, an array containing:
     *      [icon_class, color, background_color]
     * @returns {Promise}
     */
    _createNewApp: function (app_name, menu_name, model_id, icon) {
        var self = this;
        framework.blockUI();
        return this._rpc({
            route: '/web_studio/create_new_menu',
            params: {
                app_name: app_name,
                menu_name: menu_name,
                model_id: model_id,
                is_app: true,
                icon: icon,
                context: session.user_context,
            },
        }).then(function (result) {
            core.bus.trigger('clear_cache');
            self.trigger_up('new_app_created', result);
            framework.unblockUI();
        }).guardedCatch(framework.unblockUI.bind(framework));
    },
    /**
     * Update the widget according to the @currentStep
     * The steps are:
     *  - welcome
     *  - form with the app name
     *  - form with the menu name and an optional model
     *
     * @private
     * @returns {Promise}
     */
    _update: function () {
        var self = this;

        this.$left = this.$('.o_web_studio_app_creator_left_content');
        this.$right = this.$('.o_web_studio_app_creator_right_content');
        this.$back = this.$('.o_web_studio_app_creator_back');
        this.$next = this.$('.o_web_studio_app_creator_next');

        // hide back button for step 1)
        this.$back.toggleClass('o_hidden', (this.currentStep === 1));

        this.$next.removeClass('is_ready');

        if (this.currentStep === 1) {
            // add 'Welcome to' content
            var $welcome = $(QWeb.render('web_studio.AppCreator.Welcome'));
            this.$left.append($welcome);
            this.$right.append($('<img>', {
                src: "/web_studio/static/src/img/studio_app_icon.png",
                class: 'o_web_studio_welcome_image',
            }));

            // manage 'previous' and 'next' buttons
            this.$back.addClass('o_hidden');
            this.$next.find('span').text(_t('Next'));
            this.$next.addClass('is_ready');
            return Promise.resolve();
        } else if (this.currentStep === 2) {
            // add 'Create your App' content
            var $appForm = $(QWeb.render('web_studio.AppCreator.App', {
                widget: this,
            }));
            this.$left.append($appForm);

            if (!this.iconCreator) {
                this.iconCreator = new IconCreator(this);
            } else {
                this.iconCreator.enableEdit();
            }
            return this.iconCreator.appendTo(this.$right).then(function () {
                self._checkFields();
            });
        } else {
            // create a Many2one field widget for the custom model
            return this.model.makeRecord('ir.actions.act_window', [{
                name: 'model',
                relation: 'ir.model',
                type: 'many2one',
                domain: [['transient', '=', false], ['abstract', '=', false]]
            }]).then(function (recordID) {
                var record = self.model.get(recordID);
                var options = {
                    mode: 'edit',
                };
                self.many2one = new FieldMany2One(self, 'model', record, options);
                self._registerWidget(recordID, 'model', self.many2one);

                // add 'Create your first Menu' content
                var $menuForm = $(QWeb.render('web_studio.AppCreator.Menu', {
                    widget: self,
                }));
                self.$left.append($menuForm);
                self.iconCreator.disableEdit();
                return Promise.all([
                    self.many2one.appendTo($menuForm.find('.js_model')),
                    self.iconCreator.appendTo(self.$right)
                ]).then(function () {
                    self._checkFields();
                });
            });
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _onBack: function () {
        this.currentStep--;
        this.update();
    },
    /**
     * @private
     */
    _onCheckFields: function () {
        this._checkFields(false);
    },
    /*
     * Override the method of the StandaloneFieldManagerMixin to call
     * ´_checkFields´ each time the field widget changes.
     *
     * @private
     * @override
     */
    _onFieldChanged: function () {
        StandaloneFieldManagerMixin._onFieldChanged.apply(this, arguments);
        this._checkFields(false);
    },
    /**
     * @param {KeyEvent} ev
     */
    _onKeyPress: function (ev) {
        if (ev.which === $.ui.keyCode.ENTER) {
            this._onNext();
        }
    },
    /**
     * @private
     * @param {Event} e
     */
    _onWarning: function (e) {
        $(e.currentTarget).removeClass('o_web_studio_app_creator_field_warning');
    },
    /**
     * @private
     */
    _onNext: function () {
        if (this.currentStep === 1) {
            this.currentStep++;
            this.update();
        } else if (this.currentStep === 2) {
            if (!this._checkFields(true)) { return; }

            // everything is fine, let's save the values before the next step
            this.app_name = this.$('input[name="app_name"]').val();
            this.icon = this.iconCreator.getValue();
            this.currentStep++;
            this.update();
        } else {
            if (!this._checkFields(true)) { return; }
            var menu_name = this.$('input[name="menu_name"]').val();
            var model_choice = this.$('input[name="model_choice"]').is(':checked');
            var model_id = model_choice && this.many2one.value.res_id;
            this._createNewApp(this.app_name, menu_name, model_id, this.icon);
        }
    },
});

core.action_registry.add('action_web_studio_app_creator', AppCreator);

return AppCreator;

});
