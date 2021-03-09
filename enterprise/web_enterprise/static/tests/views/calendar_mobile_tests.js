odoo.define('web_enterprise.calendar_mobile_tests', function (require) {
"use strict";

const CalendarView = require('web.CalendarView');
const testUtils = require('web.test_utils');

var initialDate = new Date(2016, 11, 12, 8, 0, 0);
initialDate = new Date(initialDate.getTime() - initialDate.getTimezoneOffset()*60*1000);

QUnit.module('CalendarViewMobile', {
    beforeEach: function () {
        this.data = {
            event: {
                fields: {
                    id: {string: "ID", type: "integer"},
                    name: {string: "name", type: "char"},
                    start: {string: "start datetime", type: "datetime"},
                    stop: {string: "stop datetime", type: "datetime"},
                },
                records: [
                    {id: 1, name: "event 1", start: "2016-12-11 00:00:00", stop: "2016-12-11 00:00:00"},
                ],
                check_access_rights: function () {
                    return Promise.resolve(true);
                }
            },
        };
    },
}, function () {
    QUnit.test('calendar: popover rendering in mobile', async function (assert) {
        assert.expect(4);

        let calendar = await testUtils.createCalendarView({
            View: CalendarView,
            model: 'event',
            data: this.data,
            arch:
                '<calendar date_start="start" date_stop="stop">' +
                '<field name="name"/>' +
                '</calendar>',
            viewOptions: {
                initialDate: initialDate,
            },
        }, {positionalClicks: true});

        let fullCalendarEvent = calendar.el.querySelector('.fc-event');

        await testUtils.dom.click(fullCalendarEvent);
        await testUtils.nextTick();

        let popover = document.querySelector('.o_cw_popover');
        assert.ok(popover !== null, "there should be a modal");
        assert.ok(popover.parentNode === document.body, "the container of popover must be the body");

        // Check if the popover is "fullscreen"
        let actualPosition = popover.getBoundingClientRect();
        let windowRight = document.documentElement.clientWidth;
        let windowBottom = document.documentElement.clientHeight;
        let expectedPosition = [
            0,
            windowRight,
            windowBottom,
            0
        ];

        assert.deepEqual([
            actualPosition.top,
            actualPosition.right,
            actualPosition.bottom,
            actualPosition.left
        ], expectedPosition, "popover should be at position 0 " + windowRight + " " + windowBottom + " 0 (top right bottom left)");
        let closePopoverButton = document.querySelector('.o_cw_popover_close');
        await testUtils.dom.click(closePopoverButton);

        popover = document.querySelector('.o_cw_popover');
        assert.ok(popover === null, "there should be any modal");

        calendar.destroy();
    });
});
});
