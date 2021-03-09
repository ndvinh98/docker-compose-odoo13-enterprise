odoo.define('hr_payroll.WorkEntryControllerMixin', function(require) {
    'use strict';

    var core = require('web.core');
    var time = require('web.time');

    var _t = core._t;
    var QWeb = core.qweb;

    /*
        This mixin implements the behaviours necessary to generate and validate work entries and Payslips
        It is intended to be used in a Controller and requires four methods to be defined on your Controller

         1. _fetchRecords
            Which should return a list of records containing at least the state and id fields

         2. _fetchFirstDay
            Which should return the first day for which we will generate the work entries, it should be a Moment instance
            (Typically the first day of the current month)

         3. _fetchLastDay
            Same as _fetchFirstDay except that this is the last day of the period

         4. _displayWarning
            Which should insert in the DOM the warning rendered template received as argument.

        This mixin is responsible for rendering the buttons in the control panel and adds the two following methods

        1. _generateWorkEntries
        2. _generatePayslips
    */

    var WorkEntryControllerMixin = {

        events: {
            'click .btn-payslip-generate': '_onGeneratePayslips',
        },

        /**
         * @override
         * @returns {Promise}
         */
        _update: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                self.firstDay = self._fetchFirstDay().toDate();
                self.lastDay = self._fetchLastDay().toDate();
                self._renderWorkEntryButtons();
                var now = moment();
                if (self.firstDay > now) return Promise.resolve();
                return self._generateWorkEntries();
            });
        },

        /*
            Private
        */

        _generateWorkEntries: function () {
            var self = this;
            return this._rpc({
                model: 'hr.employee',
                method: 'generate_work_entries',
                args: [[], time.date_to_str(this.firstDay), time.date_to_str(this.lastDay)],
            }).then(function (new_work_entries) {
                if (new_work_entries) {
                    self.reload();
                }
            });
        },

        _generatePayslips: function () {
            this.do_action('hr_payroll.action_generate_payslips_from_work_entries', {
                additional_context: {
                    default_date_start: time.date_to_str(this.firstDay),
                    default_date_end: time.date_to_str(this.lastDay),
                },
            });
        },

        _renderWorkEntryButtons: function () {
            if (this.modelName !== "hr.work.entry") {
                return;
            }

            var records = this._fetchRecords();
            var hasConflicts = records.some(function (record) { return record.state === 'conflict'; });
            var allValidated = records.every(function (record) { return record.state === 'validated'; });

            this.$buttons.find('.btn-work-entry').remove();

            if (!allValidated && records.length !== 0) {
                this.$buttons.append(QWeb.render('hr_work_entry.work_entry_button', {
                    button_text: _t("Generate Payslips"),
                    event_class: 'btn-payslip-generate',
                    disabled: hasConflicts,
                }));
            }
        },

        _onGeneratePayslips: function (e) {
            e.preventDefault();
            e.stopImmediatePropagation();
            this._generatePayslips();
        },
    };

    return WorkEntryControllerMixin;

});
