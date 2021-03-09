odoo.define('social.stream_post_formatter_mixin', function (require) {
"use strict";

return {
    /**
     * Wraps (simple https) links around anchors
     * Regex from: https://stackoverflow.com/questions/30970068/js-regex-url-validation
     *
     * @param {String} formattedValue
     * @private
     */
    _formatStreamPost: function (formattedValue) {
        return formattedValue
            .replace(/http(s)?:\/\/(www\.)?[a-zA-Z0-9@:%\._\+~#=\-]{1,256}(\.[a-z]{2,6})?\b([a-zA-Z0-9@:%_\+\.~#?&//=\-]*)/g, "<a href='$&' target='_blank' rel='noreferrer noopener'>$&</a>");
    }
};

});
