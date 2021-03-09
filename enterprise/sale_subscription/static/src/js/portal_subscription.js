odoo.define('sale_subscription.portal_subscription', function (require) {
'use strict';

var publicWidget = require('web.public.widget');

publicWidget.registry.ContractSubmit = publicWidget.Widget.extend({
    selector: '.contract-submit',
    events: {
        'click': '_onClick',
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _onClick: function () {
        this.$el.attr('disabled', true);
        this.$el.prepend('<i class="fa fa-refresh fa-spin"></i> ');
        this.$el.closest('form').submit();
    },
});
});
