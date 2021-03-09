odoo.define('iot.scan', function (require) {
'use strict';

var core = require('web.core');

var QWeb = core.qweb;
var _t = core._t;

return {
    box_connect: null,
    ipRegex: /([0-9]{1,3}(\.[0-9]{1,3}){3}|[a-f0-9]{1,4}(:[a-f0-9]{1,4}){7})/g,
    protocol: window.location.protocol,
    controlImage: '/iot.jpg',

    /**
    * Entry point to start to scan network
    *
    * @private
    */
    findIOTs: function () {
        var self = this;
        var ranges = this.ranges;
        window.dispatchEvent(new Event('_clearIOTProgress'));
        _.keys(ranges).forEach(function (range) {
            self._addIPRange(range);
        });
        _.each(this.ranges, this._processRangeToScan, this);
    },

    /**
    * Reset cache
    */
    reset: function () {
        this.ranges = {};
        this.iots = {};
    },

    /**
    * Add an IP range to scan
    *
    * @param {string} range
    * @return {Object}
    * @private
    */
    _addIPRange: function (range) {
        var ipPerRange = 256;

        this.ranges[range] = {
            range: range,
            ips: [],
            current: 0,
            total: ipPerRange,
        };

        for (var i = 0; i < ipPerRange; i++) {
            var port = '';
            if (this.protocol === 'http:') {
                port = ':8069';
            }
            this.ranges[range].ips.push(this.protocol + '//' + (range + i) + port);
        }

        window.dispatchEvent(new CustomEvent('_onAddRange', { detail: this.ranges[range] }));

        return this.ranges[range];
    },

    /**
    * Connect to IoT
    *
    * @param {string} ip
    */
    _connectToIOT: function (url) {
        var img = new Image();
        var self = this;
        img.src = url.replace('https://', 'http://') + self.box_connect;
        img.onload = function(jqXHR) {
            if (img.height === 10){
                window.dispatchEvent(new CustomEvent('_updateIOTProgress', { detail: { url: url, status: 'success', message: _t('IoTBox connected') } }));
            } else {
                window.dispatchEvent(new CustomEvent('_updateIOTProgress', { detail: { url: url, status: 'error', message: _t('This IoTBox is already connected') } }));
            }
        };
        img.onerror = function(jqXHR) {
            window.dispatchEvent(new CustomEvent('_updateIOTProgress', { detail: { url: url, status: 'error', message: _t('Connection failed') } }));
        };
    },

    /**
    * Get current client IP
    *
    * @param {function} onNewIP : your listener function for new IPs
    * @private
    */
    _getLocalIP: function () {
        var self = this;
        //compatibility for firefox and chrome
        var MyPeerConnection = window.RTCPeerConnection || window.mozRTCPeerConnection || window.webkitRTCPeerConnection;

        if (MyPeerConnection) {
            this.peerConnection = new MyPeerConnection({
                iceServers: []
            });
            var noop = function () {};
            this.localIPs = {};

            if (typeof this.peerConnection.createDataChannel !== "undefined") {
                //create a bogus data channel
                this.peerConnection.createDataChannel('');

                // create offer and set local description
                this.peerConnection.createOffer().then(function (sdp) {
                    sdp.sdp.split('\n').forEach(function (line) {
                        if (line.indexOf('candidate') < 0) return;
                        line.match(self.ipRegex).map(self._iterateIP.bind(self));
                    });

                    self.peerConnection.setLocalDescription(sdp, noop, noop);
                });

                //listen for candidate events
                this.peerConnection.onicecandidate = this._onIceCandidate.bind(this);
            }
        }
    },

    /**
    * Check size of the ip
    * Convert ip to range
    *
    * @param {string} ip
    * @private
    */
    _iterateIP:function(ip) {
        if (!this.localIPs[ip]){
            if (ip.length < 16){
                this.localIPs[ip] = true;
                var range = ip.substring(0, ip.lastIndexOf('.') + 1);
                if (!_.keys(this.ranges).includes(range)) {
                    this._addIPRange(range);
                }
            }
        }
    },

    /**
    *
    * @param {Object} ice
    * @private
    */
    _onIceCandidate: function (ice) {
        if (!ice || !ice.candidate || !ice.candidate.candidate || !ice.candidate.candidate.match(this.ipRegex)) {
            if(this.peerConnection.iceGatheringState === 'complete' && _.isEmpty(this.ranges)) {
                this._addIPRange('192.168.0.');
                this._addIPRange('192.168.1.');
                this._addIPRange('10.0.0.');
            }
            return;
        }
        var res = ice.candidate.candidate.match(this.ipRegex);
        res.forEach(this._iterateIP.bind(this));

    },

    /**
    * Start scanning range
    * Create 6 parallel threads
    *
    * @param {Object} range
    * @private
    */
    _processRangeToScan: function (range) {
        for (var i = 0; i < 6; i++) {
            this._scanRange(range.ips, range);
        }
    },

    /**
    * Create thread to scan the network
    *
    * @param {Array} urls
    * @param {Object} range
    * @private
    */
    _scanRange: function (urls, range) {
        var self = this;
        var img = new Image();
        var url = urls.shift();
        if (url){
            var promise = new Promise(function (resolve, reject) {
                $.ajax({
                    url: url + '/hw_proxy/hello',
                    method: 'GET',
                    timeout: 400,
                }).then(function () {
                    window.dispatchEvent(new CustomEvent('_addIOTProgress', { detail: url }));
                    self._connectToIOT(url);
                    self._scanRange(urls, range);
                    window.dispatchEvent(new CustomEvent('_updateRangeProgress', { detail: range }));
                    resolve();
                }).fail(reject);
            });
            promise.guardedCatch(function (jqXHR) {
                // * If the request to /hw_proxy/hello returns an error while we contacted it in https,
                // * it could mean the server certificate is not yet accepted by the client.
                // * To know if it is really the case, we try to fetch an image on the http port of the server.
                // * If it loads successfully, we put informations of connection in parameter of image.
                if (jqXHR.statusText === 'error' && self.protocol === 'https:') {
                    var imgSrc = url + self.controlImage;
                    img.src = imgSrc.replace('https://', 'http://');
                    img.onload = function(XHR) {
                        window.dispatchEvent(new CustomEvent('_addIOTProgress', { detail: url }));
                        self._connectToIOT(url);
                    };
                }
                self._scanRange(urls, range);
                window.dispatchEvent(new CustomEvent('_updateRangeProgress', { detail: range }));
            });
        }
    },
};
});
