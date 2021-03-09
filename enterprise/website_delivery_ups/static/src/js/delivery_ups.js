odoo.define('website_delivery_ups.delivery_ups', function (require) {
"use strict";

    var ajax = require('web.ajax');

    $(document).ready(function () {

        $('#service_type select[name="ups_service_type"]').on('change', function () {
            var value = $(this).val();
            var apply_button = $('.o_apply_ups_bill_my_account');
            var sale_id = $('#service_type input[name="sale_order_id"]').val();
            apply_button.prop("disabled", true);

            ajax.jsonRpc('/shop/ups_check_service_type', 'call', {'sale_id': sale_id, 'ups_service_type': value}).then(function (data) {
                var ups_service_error = $('#ups_service_error');
                if(data.error){
                    ups_service_error.html('<strong>' +data.error+ '</strong>').removeClass('d-none');
                }
                else {
                    ups_service_error.addClass('d-none');
                    apply_button.prop("disabled", false);
                }
            });
        });
    });
});
