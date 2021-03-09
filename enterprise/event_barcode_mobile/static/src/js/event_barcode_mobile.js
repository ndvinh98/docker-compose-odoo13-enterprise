odoo.define('web.event.barcode_mobile', function (require) {
"use strict";

var EventBarcodeScanView = require('event_barcode.EventScanView');
var mobile = require('web_mobile.rpc');

EventBarcodeScanView.include({
    events: _.defaults({
        'click .o_event_barcode_mobile': 'open_mobile_scanner'
    }, EventBarcodeScanView.prototype.events),
    start: function(){
        if(!mobile.methods.scanBarcode){
            this.$el.find(".o_event_barcode_mobile").remove();
        }
        return this._super.apply(this, arguments);

    },
    open_mobile_scanner: function(){
        var self = this;
        mobile.methods.scanBarcode().then(function(response){
            var barcode = response.data;
            if(barcode){
                self._onBarcodeScanned(barcode);
                mobile.methods.vibrate({'duration': 100});
            }else{
                mobile.methods.showToast({'message':'Please, Scan again !!'});
            }
        });
    }
});


});
