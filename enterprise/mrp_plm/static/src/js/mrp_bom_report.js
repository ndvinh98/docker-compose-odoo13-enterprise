odoo.define('mrp_plm.mrp_bom_report', function (require) {
"use strict";

var core = require('web.core');
var _t = core._t;

var MrpBomReport = require('mrp.mrp_bom_report');

MrpBomReport.include({
    events: _.extend({}, MrpBomReport.prototype.events, {
        'click .o_mrp_ecos_action': '_onClickEcos',
    }),
    _onClickEcos: function (ev) {
        ev.preventDefault();
        var product_id = $(ev.currentTarget).data('res-id');
        return this.do_action({
            name: _t('ECOs'),
            type: 'ir.actions.act_window',
            res_model: 'mrp.eco',
            domain: [['product_tmpl_id.product_variant_ids', 'in', [product_id]]],
            views: [[false, 'kanban'], [false, 'list'], [false, 'form']],
            target: 'current',
        });
    },
    _reload_report_type: function () {
        this._super.apply(this, arguments);

        if (this.given_context.report_type === 'bom_cost') {
            this.$('.o_mrp_bom_ver, .o_mrp_ecos').addClass('o_hidden');
        }
        else {
            this.$('.o_mrp_bom_ver, .o_mrp_ecos').removeClass('o_hidden');
        }
    }
});

});
