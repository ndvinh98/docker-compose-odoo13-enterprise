odoo.define('hr_referral.welcome', function (require) {
"use strict";

var config = require('web.config');
var AbstractAction = require('web.AbstractAction');
var core = require('web.core');
var _t = core._t;


var MyReferral = AbstractAction.extend({
    contentTemplate: 'HrReferralWelcome',
    events: {
        'click .o_hr_referral_start': '_completeOnboarding',
        'click .o_hr_referral_level_up': '_upgradeLevel',
        'click .o_referral_action': '_onActionClicked',
        'click .o_choose_friend_available': '_chooseFriend',
        'slide.bs.carousel #carouselOnboarding': '_onNewSlide',
    },

    /**
     * @override
     */
    willStart: function () {
        var self = this;

        this.onboardingLength = 0;

        var def = this._rpc({
                model: 'hr.applicant',
                method: 'retrieve_referral_welcome_screen',
            })
            .then(function (res) {
                self.dashboardData = res;
                self.onboardingLength = res.onboarding && res.onboarding.length;
                self.applicantId = res.new_friend_id;
                self.debug = config.isDebug();
            });

        return Promise.all([def, this._super.apply(this, arguments)]);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent} e
     */
    _onActionClicked: function (e) {
        e.preventDefault();
        var target = $(e.currentTarget);
        return this.do_action(target.attr('name'), {
            additional_context: py.eval(target.attr('context') || '{}')
        });
    },

    _onNewSlide: function (e) {
        if (e.to === this.onboardingLength - 1) {
            $('#btn_skip').hide();
            $('#btn_next').hide();
            $('#btn_start').show(400);
        } else {
            $('#btn_skip').show();
            $('#btn_next').show();
            $('#btn_start').hide();
        }
    },

    /**
     * Save that user has seen the onboarding screen then restart the view
     *
     * @private
     * @param {MouseEvent} e
     */
    _completeOnboarding: function (e) {
        var self = this;
        e.preventDefault();
        var completed = ($(e.currentTarget).attr('completed') === 'true');
        this._rpc({
                model: 'res.users',
                method: 'action_complete_onboarding',
                args: [completed],
            })
            .then(function (res) {
                self.do_action({
                    type: 'ir.actions.client',
                    tag: 'hr_referral_welcome',
                    name: _t('Dashboard'),
                    target: 'main'
                });
            });
    },

    /**
     * User upgrade his level then restart the view
     *
     * @private
     * @param {MouseEvent} e
     */
    _upgradeLevel: function (e) {
        var self = this;
        e.preventDefault();
        this._rpc({
                model: 'hr.applicant',
                method: 'upgrade_level',
                args: [],
            })
            .then(function (res) {
                self.do_action({
                    type: 'ir.actions.client',
                    tag: 'hr_referral_welcome',
                    name: _t('Dashboard'),
                    target: 'main'
                });
            });
    },

    /**
     * Save the new user's friend then restart the view
     *
     * @private
     * @param {MouseEvent} e
     */
    _chooseFriend: function (e) {
        var self = this;
        e.preventDefault();
        var friendId = parseInt($(e.currentTarget).attr('name'));
        this._rpc({
                model: 'hr.applicant',
                method: 'choose_a_friend',
                args: [[self.applicantId], friendId],
            })
            .then(function (res) {
                self.do_action({
                    type: 'ir.actions.client',
                    tag: 'hr_referral_welcome',
                    name: _t('Dashboard'),
                    target: 'main'
                });
            });
    },
});

core.action_registry.add('hr_referral_welcome', MyReferral);

return MyReferral;

});
