odoo.define('social_twitter.stream_post_formatter_mixin', function (require) {
"use strict";

var SocialStreamPostFormatterMixin = require('social.stream_post_formatter_mixin');
var _superFormatStreamPost = SocialStreamPostFormatterMixin._formatStreamPost;

/**
 * Wraps simple hashtags (e.g: #odoo) around a twitter link.
 *
 * Regex partially extracted from here:
 * https://stackoverflow.com/questions/21421526/javascript-jquery-parse-hashtags-in-a-string-using-regex-except-for-anchors-i
 *
 * @param {String} formattedValue
 */
SocialStreamPostFormatterMixin._formatStreamPost = function (formattedValue) {
    formattedValue = _superFormatStreamPost.apply(this, arguments);
    return formattedValue
        .replace(/\B#([a-zA-Z\d-]+)/g, "<a href='https://twitter.com/hashtag/$1?src=hash' target='_blank'>#$1</a>");
};

});
