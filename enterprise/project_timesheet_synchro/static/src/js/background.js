var clockInterval = null;
var min = 0;

var drawClock = function () {
    // changing the extension icon
    chrome.browserAction.setIcon({
        path: 'project_timesheet_synchro/static/src/img/'+((min++)%5+1)+'.png'
    });
}

var startClock = function () {
    if(!clockInterval){
        clockInterval = setInterval(drawClock, 1000);
    }
}
var stopClock = function () {
    clearInterval(clockInterval);
    clockInterval = null;
    chrome.browserAction.setIcon({ path: 'project_timesheet_synchro/static/src/img/icon.png' });
}

chrome.storage.onChanged.addListener(function (changes, namespace) {
    if ('isTimerOn' in changes) {
        changes.isTimerOn.newValue ? startClock() : stopClock();
    }
});
chrome.windows.onCreated.addListener(function () {
    chrome.storage.local.get("isTimerOn", function (items) {
        items.isTimerOn ? startClock() : stopClock();
    });
});