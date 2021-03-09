odoo.define('web_mobile.ControlPanelRenderer', function (require) {
"use strict";

var config = require('web.config');
var ControlPanelController = require('web.ControlPanelController');

if (!config.device.isMobile) {
    return;
}

ControlPanelController.include({
    /**
     * Constant value for scrolling direction
     */
    SCROLL_DIRECTION: Object.freeze({
        UP: -1,
        NONE: 0,
        DOWN: 1
    }),
    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        // Create a reference for bind function
        this._throttleMoveControlPanel = _.throttle(this._throttleMoveControlPanel.bind(this), 1);
    },
    /**
     * @override
     */
    on_attach_callback: function () {
        if (this._isControlPanel()) {
            this._initScrollControlPanel();
            document.addEventListener('scroll', this._throttleMoveControlPanel);
        }
        this._super.apply(this, arguments);
    },
    /**
     * @override
     */
    on_detach_callback: function () {
        document.removeEventListener('scroll', this._throttleMoveControlPanel);
        this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Get top attribute of control panel
     *
     * @private
     * @return {number|undefined}
     */
    _getControlPanelTop: function () {
        var pixelRegex = /(-?\d+)px/;
        var topString = this.el.style.top;
        var match = pixelRegex.exec(topString);
        return match ? parseInt(match[1], 10) : undefined;
    },
    /**
     * Get delta of scroll
     *
     * @param {number} scrollPosition
     * @returns {number}
     * @private
     */
    _getDeltaScroll: function (scrollPosition) {
        return Math.round(scrollPosition - this.oldScrollPositionY);
    },
    /**
     * Get the direction of scrolling event
     *
     * @param {number} scrollDelta
     * @returns {number}
     * @private
     */
    _getDirection: function (scrollDelta) {
        if (scrollDelta > 0) {
            return this.SCROLL_DIRECTION.DOWN;
        } else if (scrollDelta < 0) {
            return this.SCROLL_DIRECTION.UP;
        }
        return this.SCROLL_DIRECTION.NONE;
    },
    /**
     * Hide control panel step by step
     *
     * @param {number} delta
     * @private
     */
    _hideControlPanelBy: function (delta) {
        var top = this._getControlPanelTop();
        var controlPanelHeight = this.el.clientHeight;
        this._setControlPanelTop(Math.max(-controlPanelHeight, top + delta));
    },
    /**
     * Init variable
     *
     * @private
     */
    _initScrollControlPanel: function () {
        this.el.style.top = '0px';
        this.oldScrollPositionY = 0;
        this.controlPanelInitialPositionY = this.el.offsetTop;
    },
    /**
     * Detect if we are in the main control panel
     *
     * @return {boolean}
     * @private
     */
    _isControlPanel: function () {
        return this.el.querySelector('.o_control_panel') !== null;
    },
    /**
     * Set top attribute of control panel
     *
     * @param top
     * @private
     */
    _setControlPanelTop: function (top) {
        this.el.style.top = top + 'px';
    },
    /**
     * Show control panel step by step
     *
     * @param {number} delta
     * @private
     */
    _showControlPanelBy: function (delta) {
        var top = this._getControlPanelTop();
        this._setControlPanelTop(Math.min(0, top + delta));
    },
    /**
     * Show or hide the control panel on the top screen
     *
     * @private
     */
    _throttleMoveControlPanel: function () {
        var scrollPosition = document.documentElement.scrollTop || window.pageYOffset;

        var deltaScroll = this._getDeltaScroll(scrollPosition);
        var directionScroll = this._getDirection(deltaScroll);

        var stickyClass = 'o_mobile_sticky';

        if (scrollPosition > this.controlPanelInitialPositionY) {
            this.el.classList.add(stickyClass);
            if (directionScroll === this.SCROLL_DIRECTION.UP) {
                this._showControlPanelBy(-deltaScroll);
            } else {
                this._hideControlPanelBy(-deltaScroll);
            }
        } else {
            if (this.el.classList.contains(stickyClass)) {
                this.el.classList.remove(stickyClass);
            }
        }

        this.oldScrollPositionY = scrollPosition;
    },
});
});
