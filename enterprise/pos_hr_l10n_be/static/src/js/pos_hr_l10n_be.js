odoo.define('pos_hr_l10n_be.pos_hr_l10n_be', function (require) {
    var core = require('web.core');
    var chrome = require('point_of_sale.chrome');
    var gui = require('point_of_sale.gui');
    var models = require('point_of_sale.models');
    var devices = require('point_of_sale.devices');

    var _t = core._t;
    var _lt = core._lt;

     devices.ProxyDevice.include({
        //allow the use of the employee INSZ number
        _get_insz_or_bis_number: function() {
            if(this.pos.config.module_pos_hr) {
                var insz = this.pos.get_cashier().insz_or_bis_number;
                if (! insz) {
                    this.pos.gui.show_popup('error',{
                        'title': _t("Fiscal Data Module error"),
                        'body': _t("INSZ or BIS number not set for current cashier."),
                    });
                    return false;
                }
                return insz;
            }
            else
                return this._super();
        }
     });

     chrome.Chrome.include({
        return_to_login_screen: function() {
            var insz = this.pos.get_cashier().insz_or_bis_number;
            if (this.pos.config.blackbox_pos_production_id && !insz) {
                this.pos.gui.show_popup('error',{
                    'title': _t("Fiscal Data Module error"),
                    'body': _t("INSZ or BIS number not set for current cashier."),
                });
            } else if(this.pos.config.blackbox_pos_production_id && this.pos.check_if_user_clocked()) {
                this.pos.gui.show_popup("error", {
                    'title': _t("POS error"),
                    'body':  _t("You need to clock out before closing the POS."),
                });
            } else{
                this.gui.show_screen('login');
            }
        },
     });

    var posmodel_super = models.PosModel.prototype;
    models.PosModel = models.PosModel.extend({
        check_if_user_clocked: function() {
            if(!this.config.module_pos_hr)
                return posmodel_super.check_if_user_clocked.apply(this,arguments);
            var employee_id = this.get_cashier().id;
            return this.pos_session.employees_clocked_ids.find(function(elem) { return elem === employee_id });
        },
        get_args_for_clocking: function() {
            if(!this.config.module_pos_hr)
                return posmodel_super.get_args_for_clocking.apply(this,arguments);
            return [this.pos_session.id, this.get_cashier().id];
        },
        set_clock_values: function(values) {
            if(!this.config.module_pos_hr)
                return posmodel_super.set_clock_values.apply(this,arguments);
            this.pos_session.employees_clocked_ids = values;
        },
        get_method_call_for_clocking: function() {
            if(!this.config.module_pos_hr)
               return posmodel_super.get_method_call_for_clocking.apply(this,arguments);
            return 'get_employee_session_work_status';
        },
        set_method_call_for_clocking: function() {
            if(!this.config.module_pos_hr)
               return posmodel_super.set_method_call_for_clocking.apply(this,arguments);
            return 'set_employee_session_work_status';
        }
    });

    models.load_fields("hr.employee", "insz_or_bis_number");
    models.load_fields("pos.session", "employees_clocked_ids");
});
