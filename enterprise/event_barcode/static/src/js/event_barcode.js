odoo.define('event_barcode.EventScanView', function (require) {
"use strict";

var AbstractAction = require('web.AbstractAction');
var core = require('web.core');
var Dialog = require('web.Dialog');

var _t = core._t;
var QWeb = core.qweb;


// load widget with main barcode scanning View
var EventScanView = AbstractAction.extend({
    contentTemplate: 'event_barcode_template',
    events: {
        'click .o_event_select_attendee': '_onClickSelectAttendee'
    },

    /**
     * @override
     */
    init: function(parent, action) {
        this._super.apply(this, arguments);
        this.action = action;
    },
    /**
     * @override
     */
    willStart: function() {
        var self = this;
        return this._super().then(function() {
            return self._rpc({
                route: '/event_barcode/event',
                params: {
                    event_id: self.action.context.active_id
                }
            }).then(function (result) {
                self.data = result;
            });
        });
    },
    /**
     * @override
     */
    start: function() {
        core.bus.on('barcode_scanned', this, this._onBarcodeScanned);
    },
    /**
     * @override
     */
    destroy: function () {
        core.bus.off('barcode_scanned', this, this._onBarcodeScanned);
        this._super();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {string} barcode
     */
    _onBarcodeScanned: function(barcode) {
        var self = this;
        this._rpc({
            route: '/event_barcode/register_attendee',
            params: {
                barcode: barcode,
                event_id: self.action.context.active_id
            }
        }).then(function(result) {
            if (result.registration && (result.registration.alert || !_.isEmpty(result.registration.information))) {
                new Dialog(self, {
                    title: _t('Registration Summary'),
                    size: 'medium',
                    $content: QWeb.render('event_registration_summary', {
                        'success': result.success,
                        'warning': result.warning,
                        'registration': result.registration
                    }),
                    buttons: [
                        {text: _t('Close'), close: true, classes: 'btn-primary'},
                        {text: _t('Print'), click: function () {
                          self.do_action({
                              type: 'ir.actions.report',
                              report_type: 'qweb-pdf',
                              report_name: 'event.event_registration_report_template_badge/' + result.registration.id,
                          });
                        }
                    },
                    {text: _t('View'), close: true, click: function() {
                        self.do_action({
                            type: 'ir.actions.act_window',
                            res_model: 'event.registration',
                            res_id: result.registration.id,
                            views: [[false, 'form']],
                            target: 'current'
                        });
                    }},
                ]}).open();
            } else if (result.success) {
                self.do_notify(result.success, false, false, 'o_event_success');
            } else if (result.warning) {
                self.do_warn(_t("Warning"), result.warning);
            }
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onClickSelectAttendee(ev) {
        this.do_action('event_barcode.act_event_registration_from_barcode', {
            additional_context: {
                active_id: this.action.context.active_id,
            },
        });
    }
});

core.action_registry.add('even_barcode.scan_view', EventScanView);

return EventScanView;

});
