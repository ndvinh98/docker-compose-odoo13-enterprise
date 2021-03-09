odoo.define('iot.widgets', function (require) {
'use strict';

var core = require('web.core');
var Widget = require('web.Widget');
var field_registry = require('web.field_registry');
var widget_registry = require('web.widget_registry');
var Dialog = require('web.Dialog');
var ActionManager = require('web.ActionManager');
var basic_fields = require('web.basic_fields');
var BusService = require('bus.BusService');
var IoTScan = require('iot.scan');

var _t = core._t;
var QWeb = core.qweb;

ActionManager.include({
    _executeReportAction: function (action) {
        if (action.device_id) {
            // Call new route that sends you report to send to printer
            var self = this;
            self.action = action;
            return this._rpc({
                model: 'ir.actions.report',
                method: 'iot_render',
                args: [action.id, action.context.active_ids, {'device_id': action.device_id}]
            }).then(function (result) {
                var iot_device = new DeviceProxy({ iot_ip: result[0], identifier: result[1] });
                iot_device.add_listener(self._onValueChange.bind(self));
                iot_device.action({'document': result[2]})
                    .then(function(data) {
                        self._onIoTActionResult.call(self, data);
                    }).guardedCatch(self._onIoTActionFail.bind(self, result[0]));
            });
        }
        else {
            return this._super.apply(this, arguments);
        }
    },

    _onIoTActionResult: function (data){
        if (data.result === true) {
            this.do_notify(_t('Successfully sent to printer!'));
        } else {
            this.do_warn(_t('Connection to Printer failed'), _t('Please check if the printer is still connected.'));
        }
    },

    _onIoTActionFail: function (ip){
        // Display the generic warning message when the connection to the IoT box failed.
        this.call('iot_longpolling', '_doWarnFail', ip);
    },

    _onValueChange: function (data) {
        this.do_notify("Printer " + data.status);
    }
});

var IotScanButton = Widget.extend({
    tagName: 'button',
    className: 'o_iot_detect_button btn btn-primary',
    events: {
        'click': '_onButtonClick',
    },

    /**
    * @override
    */
    init: function (parent, record) {
        this._super.apply(this, arguments);
        IoTScan.box_connect = '/hw_drivers/box/connect?token=' + btoa(record.data.token);
    },

    /**
    * @override
    */
    start: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function() {
            self.$el.text(_t('SCAN'));
            IoTScan._getLocalIP();
        });
    },

    /**
    * @override
    */
    destroy: function (){
        IoTScan.reset();
        this._super.apply(this, arguments);
    },

    /**
    * @private
    */
    _onButtonClick: function (e) {
        IoTScan.findIOTs();
    },
});

widget_registry.add('iot_detect_button', IotScanButton);



var IotScanProgress = Widget.extend({
    tagName: 'div',
    className: 'scan_progress',
    events: {
        'click .add_scan_range': '_onClickAddScanRange',
        'click .add_scan_range_ip': '_onClickAddScanRangeIp',
    },

    /**
    * @override
    */
    init: function () {
        this._super.apply(this, arguments);

        IoTScan.reset();

        this.eventListeners = {
            '_onAddRange': this._onAddRange.bind(this),
            '_updateRangeProgress': this._updateRangeProgress.bind(this),
            '_addIOTProgress': this._addIOTProgress.bind(this),
            '_updateIOTProgress': this._updateIOTProgress.bind(this),
            '_clearIOTProgress': this._clearIOTProgress.bind(this),
        };

        _.each(this.eventListeners, function (listener, event) {
            window.addEventListener(event, listener);
        });
    },

    /**
    * @override
    */
    start: function () {
        this._super.apply(this, arguments);
        this.$el.html(QWeb.render('iot.scan_progress_template'));

        this.$progressRanges = this.$('.scan_ranges');
        this.$scanNetwork = this.$('.scan_network');
        this.$progressFound = this.$('.found_devices');
        this.$addRange = this.$('.add_scan_range');
        this.$addRangeInput = this.$('.add_scan_range_ip');
        this.$progressIotFound = this.$('.iot_box_found');


    },

    /**
     * @override
     */
    destroy: function () {
        this._super.apply(this, arguments);
        _.each(this.eventListeners, function (listener, event) {
            window.removeEventListener(event, listener);
        });
    },

    /**
    * Add an IoT to the progress bar UI
    *
    * @param {Object} event
    * @param {string} event.url
    * @private
    */
    _addIOTProgress: function (event) {
        var url = event.detail;
        this.$progressIotFound.text(_t('Found IoT Box(s)'));
        var $iot = $('<li/>')
            .addClass('list-group-item')
            .appendTo(this.$progressFound);

        $('<a/>')
            .attr('href', url)
            .attr('target', '_blank')
            .text(url)
            .appendTo($iot);

        $iot.append('<i class="iot-scan-status-icon"/>')
            .append('<div class="iot-scan-status-msg"/>');

        IoTScan.iots[url] = $iot;
        this.$progressFound.append($iot);
    },

    /**
    * Clear all IoT
    *
    * @private
    */
    _clearIOTProgress: function () {
        this.$progressRanges.empty();
        this.$progressFound.empty();
        this.$progressIotFound.empty();
    },

    /**
    * Validate IP range format
    * ex: xxx.xxx.xxx.* or xxx.xxx.xxx.xxx
    *
    * @param {string} range
    * @return {Object}
    * @private
    */
    _getNetworkId: function (range) {
        var rangeLength = (range.match(/\./g) || []).length;
        var pattern = new RegExp(['^([01]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5])\\.',
            '([01]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5])\\.',
            '([01]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5])\\.',
            '.*$'].join(''));
        if (rangeLength === 3) {
            return range.substring(0, range.lastIndexOf('.') + 1).match(pattern);
        } else if (rangeLength === 2) {
            return (range + '.').match(pattern);
        } else {
            return false;
        }
    },

    /**
    * start range scan status
    *
    * @private
    */
    _RangeProgress: function () {
        this.$scanNetwork.text(_t('Scanning Network'));
        this.$scanNetwork.append('<i class="fa pull-right iot-scan-status-icon mt-1 fa-spinner fa-spin"/>');
    },

    /**
    * start range scan status
    *
    * @private
    */
    _RangeProgressDone: function () {
        this.$scanNetwork.text(_t('Scanning Network'));
        this.$scanNetwork.append('<i class="fa pull-right iot-scan-status-icon mt-1 fa-check text-success"/>');
    },

    /**
    * Update IoT progress
    *
    * @param {Object} event
    * @param {string} event.url
    * @param {string} event.status
    * @param {string} event.message
    * @private
    */
    _updateIOTProgress: function (event) {
        if (IoTScan.iots[event.detail.url]) {
            var $iot = IoTScan.iots[event.detail.url];
            var $icon = $iot.find('.iot-scan-status-icon');
            var $msg = $iot.find('.iot-scan-status-msg');

            var icon = 'fa pull-right iot-scan-status-icon mt-1 ';
            switch (event.detail.status) {
                case "loading":
                    icon += 'fa-spinner fa-spin';
                    break;
                case "success":
                    icon += "fa-check text-success";
                    break;
                default:
                    icon += "fa-exclamation-triangle text-danger";
            }
            $icon.removeClass().addClass(icon);
            $msg.empty().append(event.detail.message);
        }
    },

    /**
    * Update range scan status
    *
    * @param {Object} event
    * @param {Object} event.range
    * @private
    */
    _updateRangeProgress: function (event) {
        var range = event.detail;
        this._RangeProgress();
        range.current ++;
        var percent = Math.round(range.current / range.total * 100);
        range.$bar.css('width', percent + '%').attr('aria-valuenow', percent).text(percent + '%');
        if (percent === 100) {
            this._RangeProgressDone();
            range.$bar.text(_t('Done'));
            if (_.isEmpty(IoTScan.iots)) {
                this.$progressIotFound.text(_t('No IoT Box(s) found'));
            }
        }
    },

    /**
    * Add range to scan in list-group
    *
    * @param {Object} event
    * @param {Object} event.range
    * @return {Object}
    * @private
    */
    _onAddRange: function (event){
        var range = event.detail;
        var $range = $('<li/>')
            .addClass('list-group-item')
            .append('<b>' + range.range + '*' + '</b>')
            .appendTo(this.$progressRanges);

        var $progress = $('<div class="progress"/>').appendTo($range);
        var $bar = $('<div class="progress-bar" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"/>')
            .css('width', '0%')
            .text('0%')
            .appendTo($progress);

        range.$range = $range;
        range.$bar = $bar;

        return range;
    },

    /**
    * Click to add a network ID to scan
    * With this function it is possible to scan a specific range
    * 1 - get the typed ip address
    * 2 - check its validity
    * 3 - extract the /24 subnet id
    * 4 - perform a scan of this subnet
    */
    _onClickAddScanRange: function () {
        var range = this.$addRangeInput.removeClass('is-invalid').val().trim();
        var networkId = this._getNetworkId(range);
        if (networkId && !_.keys(IoTScan.ranges).includes(networkId[0])) {
            IoTScan._addIPRange(networkId[0]);
            this.$addRangeInput[0].value = '';
        } else {
            this.$addRangeInput.addClass('is-invalid');
        }
    },

    /**
    */
    _onClickAddScanRangeIp: function () {
        this.$addRangeInput.removeClass('is-invalid').val().trim();
    },
});

widget_registry.add('iot_scan_progress', IotScanProgress);

var IoTLongpolling = BusService.extend({
    // constants
    POLL_TIMEOUT: 60000,
    POLL_ROUTE: '/hw_drivers/event',
    ACTION_TIMEOUT: 6000,
    ACTION_ROUTE: '/hw_drivers/action',

    RPC_DELAY: 1500,
    MAX_RPC_DELAY: 1500 * 10,
    
    _retries: 0,

    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        this._session_id = this._createUUID();
        this._listeners = {};
        this._delayedStartPolling(this.RPC_DELAY);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------
    /**
     * Add a device_id to listeners[iot_ip] and restart polling
     *
     * @param {String} iot_ip
     * @param {Array} devices list of devices
     * @param {Callback} callback
     */
    addListener: function (iot_ip, devices, callback) {
        if (!this._listeners[iot_ip]) {
            this._listeners[iot_ip] = {
            devices: {},
            session_id: this._session_id,
            rpc: false,
            };
        }
        for (var device in devices) {
            this._listeners[iot_ip].devices[devices[device]] = {
                device_id: devices[device],
                callback: callback,
            };
        }
        this.stopPolling(iot_ip);
        this.startPolling(iot_ip);
        return Promise.resolve();
    },
    /**
     * Stop listening to iot device with id `device_id`
     * @param {string} iot_ip 
     * @param {string} device_id 
     */
    removeListener: function(iot_ip, device_id) {
        delete this._listeners[iot_ip].devices[device_id];
    },
    /**
     * Execute a action on device_id
     * Action depend of driver that support the device
     *
     * @param {String} iot_ip
     * @param {String} device_id
     * @param {Object} data contains the information needed to perform an action on this device_id
     */
    action: function (iot_ip, device_id, data) {
        this.protocol = window.location.protocol;
        var self = this;
        var data = {
            params: {
                session_id: self._session_id,
                device_id: device_id,
                data: JSON.stringify(data),
            }
        };
        var options = {
            timeout: this.ACTION_TIMEOUT,
        };
        var prom = new Promise(function(resolve, reject) {
            self._rpcIoT(iot_ip, self.ACTION_ROUTE, data, options)
                .then(resolve)
                .fail(reject);
        });
        return prom;
    },

    /**
     * Start a long polling, i.e. it continually opens a long poll
     * connection as long as it is not stopped (@see `stopPolling`)
     */
    startPolling: function (iot_ip) {
        if (iot_ip) {
            if (!this._listeners[iot_ip].rpc) {
                this._poll(iot_ip);
            }
        } else {
            var self = this;
            _.each(this._listeners, function (listener, ip) {
                self.startPolling(ip);
            });
        }
    },
    /**
     * Stops any started long polling
     *
     * Aborts a pending longpoll so that we immediately remove ourselves
     * from listening on notifications on this channel.
     */
    stopPolling: function (iot_ip) {
        if (this._listeners[iot_ip].rpc) {
            this._listeners[iot_ip].rpc.abort();
            this._listeners[iot_ip].rpc = false;
        }
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------
    _delayedStartPolling: function (delay){
        var self = this;
        setTimeout(function (){
            self.startPolling();
        }, delay);
    },

    _createUUID: function () {
        var s = [];
        var hexDigits = "0123456789abcdef";
        for (var i = 0; i < 36; i++) {
            s[i] = hexDigits.substr(Math.floor(Math.random() * 0x10), 1);
        }
        s[14] = "4";  // bits 12-15 of the time_hi_and_version field to 0010
        s[19] = hexDigits.substr((s[19] & 0x3) | 0x8, 1);  // bits 6-7 of the clock_seq_hi_and_reserved to 01
        s[8] = s[13] = s[18] = s[23] = "-";
        return s.join("");
    },
    /**
     * Execute a RPC to the box
     * Used to do polling or an action
     *
     * @param {String} iot_ip
     * @param {String} route
     * @param {Object} data information needed to perform an action or the listener for the polling
     * @param {Object} options.timeout
     */
    _rpcIoT: function (iot_ip, route, data, options) {
        this.protocol = window.location.protocol;
        var port = this.protocol === 'http:' ? ':8069' : '';
        var url = this.protocol + '//' + iot_ip + port;
        var queryOptions = _.extend({
            url: url + route,
            dataType: 'json',
            contentType: "application/json;charset=utf-8",
            data: JSON.stringify(data),
            method: 'POST',
        }, options);
        var request = $.ajax(queryOptions);
        if (this._listeners[iot_ip] && route === '/hw_drivers/event') {
            this._listeners[iot_ip].rpc = request;
            return this._listeners[iot_ip].rpc;
        } else {
            return request;
        }
    },
    /**
     * Make a request to an IoT Box
     *
     * @param {String} iot_ip
     */
    _poll: function (iot_ip) {
        var self = this;
        var listener = this._listeners[iot_ip];
        var data = {
            params: {
                listener: listener,
            }
        };
        var options = {
            timeout: this.POLL_TIMEOUT,
        };

        // The backend has a maximum cycle time of 50 seconds so give +10 seconds
        this._rpcIoT(iot_ip, this.POLL_ROUTE, data, options)
            .then(function (result) {
                self._retries = 0;
                self._listeners[iot_ip].rpc = false;
                if (result.result) {
                    if (self._session_id === result.result.session_id) {
                        self._onSuccess(iot_ip, result.result);
                    }
                } else if (!_.isEmpty(self._listeners[iot_ip].devices)) {
                    self._poll(iot_ip);
                }
            }).fail(function (jqXHR, textStatus) {
                if (textStatus === 'error') {
                    self._doWarnFail(iot_ip);
                } else {
                    self._onError();
                }
            });
    },

    _onSuccess: function (iot_ip, result){
        var devices = this._listeners[iot_ip].devices;
        if (devices[result.device_id]) {
            devices[result.device_id].callback(result);
        }
        if (!_.isEmpty(devices)) {
            this._poll(iot_ip);
        }
    },

    _onError: function (){
        this._retries++;
        this._delayedStartPolling(Math.min(this.RPC_DELAY * this._retries, this.MAX_RPC_DELAY));
    },

    _doWarnFail: function (url){
        var $content = $('<div/>')
            .append($('<p/>').text(_t('Odoo cannot reach the IoT Box.')))
            .append($('<span/>').text(_t('Please check if the IoT Box is still connected.')))
            .append($('<p/>').text(_t('If you are on a secure server (HTTPS) check if you accepted the certificate:')))
            .append($('<p/>').html(_.str.sprintf('<a href="https://%s" target="_blank"><i class="fa fa-external-link"/>' + _t('Click here to open your IoT Homepage') + '</a>', url)))
            .append($('<li/>').text(_t('Please accept the certificate of your IoT Box (procedure depends on your browser) :')))
            .append($('<li/>').text(_t('Click on Advanced/Show Details/Details/More information')))
            .append($('<li/>').text(_t('Click on Proceed to .../Add Exception/Visit this website/Go on to the webpage')))
            .append($('<li/>').text(_t('Firefox only : Click on Confirm Security Exception')))
            .append($('<li/>').text(_t('Close this window and try again')));

        var dialog = new Dialog(this, {
            title: _t('Connection to IoT Box failed'),
            $content: $content,
            buttons: [
                {
                    text: _t('Close'),
                    classes: 'btn-secondary o_form_button_cancel',
                    close: true,
                }
            ],
        });

        dialog.open();
    },
});

core.serviceRegistry.add('iot_longpolling', IoTLongpolling);

var IotValueFieldMixin = {

    /**
     * @returns {Promise}
     */
    willStart: function() {
        this.iot_device = null; // the attribute to which the device proxy created with ``_getDeviceInfo`` will be assigned.
        return Promise.all([this._super(), this._getDeviceInfo()]);
    },

    start: function() {
        this._super.apply(this, arguments);
        if (this.iot_device) {
            this.iot_device.add_listener(this._onValueChange.bind(this));
        }
    },

    /**
     * To implement
     * @abstract
     * @private
     */
    _getDeviceInfo: function() {},

    /**
     * To implement
     * @abstract
     * @private
     */
    _onValueChange: function (data){},
     /**
     * After a request to make action on device and this call don't return true in the result
     * this means that the IoT Box can't connect to device
     *
     * @param {Object} data.result
     */
    _onIoTActionResult: function (data) {
        if (data.result !== true) {
            var $content = $('<p/>').text(_t('Please check if the device is still connected.'));
            var dialog = new Dialog(this, {
                title: _t('Connection to device failed'),
                $content: $content,
            });
            dialog.open();
          }
    },

    /**
     * After a request to make action on device and this call fail
     * this means that the customer browser can't connect to IoT Box
     */
    _onIoTActionFail: function () {
        // Display the generic warning message when the connection to the IoT box failed.
        this.call('iot_longpolling', '_doWarnFail', this.ip);
    },
};

var IotRealTimeValue = basic_fields.InputField.extend(IotValueFieldMixin, {

    /**
     * @private
     */
    _getDeviceInfo: function() {
        var record_data = this.record.data;
        if (record_data.test_type === 'measure' && record_data.identifier) {
            this.iot_device = new DeviceProxy({ iot_ip: record_data.ip, identifier: record_data.identifier });            
        }
        return Promise.resolve();
    },

    /**
     * @private
     */
    _onValueChange: function (data){
        var self = this;
        this._setValue(data.value.toString())
            .then(function() {
                if (!self.isDestroyed()) {
                    self._render();
                }
            });
    },

});

var IotDeviceValueDisplay = Widget.extend(IotValueFieldMixin, {

    init: function (parent, params) {
        this._super.apply(this, arguments);
        this.identifier = params.data.identifier;
        this.iot_ip = params.data.iot_ip;
    },
    /**
     * @override
     * @private
     */
    _getDeviceInfo: function() {
        var self = this;
        self.iot_device = new DeviceProxy({ identifier: this.identifier, iot_ip:this.iot_ip });
        return Promise.resolve();
    },

    /**
     * @override
     * @private
     */
    _onValueChange: function (data){
        if (this.$el) {
            this.$el.text(data.value);
        }
    },

});


field_registry.add('iot_realtime_value', IotRealTimeValue);
widget_registry.add('iot_device_value_display', IotDeviceValueDisplay);

var _iot_longpolling = new IoTLongpolling();

/**
 * Frontend interface to iot devices
 */
var DeviceProxy = core.Class.extend({
    /**
     * @param {Object} iot_device - Representation of an iot device
     * @param {string} iot_device.iot_ip - The ip address of the iot box the device is connected to
     * @param {string} iot_device.identifier - The device's unique identifier
     */
    init: function(iot_device) {
        this._iot_longpolling = _iot_longpolling;
        this._iot_ip = iot_device.iot_ip;
        this._identifier = iot_device.identifier;
        this.manufacturer = iot_device.manufacturer;
    },

    /**
     * Call actions on the device
     * @param {Object} data
     * @returns {Promise}
     */
    action: function(data) {
        return this._iot_longpolling.action(this._iot_ip, this._identifier, data);
    },

    /**
     * Add `callback` to the listeners callbacks list it gets called everytime the device's value is updated.
     * @param {function} callback
     * @returns {Promise}
     */
    add_listener: function(callback) {
        return this._iot_longpolling.addListener(this._iot_ip, [this._identifier, ], callback);
    },
    /**
     * Stop listening the device
     */
    remove_listener: function() {
        return this._iot_longpolling.removeListener(this._iot_ip, this._identifier);
    },
});

return {
    IotValueFieldMixin: IotValueFieldMixin,
    IotRealTimeValue: IotRealTimeValue,
    IotDeviceValueDisplay: IotDeviceValueDisplay,
    IoTLongpolling: IoTLongpolling,
    DeviceProxy: DeviceProxy
};
});
