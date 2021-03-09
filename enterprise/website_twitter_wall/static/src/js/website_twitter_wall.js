odoo.define('website_twitter_wall.views', function (require) {
'use strict';

var core = require('web.core');
var Widget = require('web.Widget');
var publicWidget = require('web.public.widget');

var qweb = core.qweb;

var TweetWall = Widget.extend({
    template: 'website_twitter_wall_tweets',

    /**
     * @override
     * @param {number} wall_id
     */
    init: function (parent, wallID) {
        this._super.apply(this, arguments);
        var self = this;
        this.wall_id = wallID;
        this.pool_cache = {};
        this.repeat = false;
        this.shuffle = false;
        this.limit = 25;
        this.num = 1;
        this.timeout = 7000;
        this.last_tweet_id = $('.o-tw-tweet:first').data('tweet-id') || 0;
        this.fetchPromise = undefined;
        this.prependTweetsTo = $('.o-tw-walls-col:first');
        this.interval = setInterval(function () {
            self._getData();
        }, this.timeout);
        var zoomLevel = 1 / (window.devicePixelRatio * 0.80);
        this.zoom(zoomLevel);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {string} level
     */
    _zoom: function (level) {
        this.zoomLevel = level;
        if ($.browser.mozilla) {
            $('body').css('MozTransform', 'scale(' + this.zoomLevel + ')');
        } else {
            $('body').css('zoom', this.zoomLevel);
            $('iframe').each(function (iframe) {
                $(iframe.contentDocument).find('body').css('zoom', level);
            });
        }
    },
    /**
     * @private
     */
    _toggleRepeat: function () {
        if (this.repeat) {
            this.repeat = false;
            this.limit = 25;
            _.each(this.pool_cache, function (t) {
                t.round = t.round ? 1 : 0;
            });
        } else {
            this.repeat = true;
            this.limit = 5;
        }
    },
    /**
     * @private
     */
    _toggleShuffle: function () {
        this.shuffle = this.shuffle === false ? true : false;
    },
    /**
     * @private
     */
    _getData: function () {
        var self = this;
        if (!this.fetchPromise) {
            self.fetchPromise = this._rpc({
                route: '/twitter_wall/get_tweet/' + self.wall_id,
                params: {
                    'last_tweet_id': self.last_tweet_id,
                },
            }).then(function (res) {
                self.fetchPromise = undefined;
                if (res.length) {
                    self.last_tweet_id = res[0].id;
                    _.each(res, function (r) {
                        r.round = 0;
                        self.pool_cache[r.id] = r;
                    });
                }
                var atLeastOneNotSeen = _.some(self.pool_cache, function (t) {
                    return t.round === 0;
                });
                if (atLeastOneNotSeen || self.repeat) {
                    self.process_tweet();
                }
            }).guardedCatch(function () {
                self.fetchPromise = undefined;
            });
        }
    },
    /**
     * @private
     */
    _processTweet: function () {
        var self = this;
        var leastRound = _.min(self.pool_cache, function (o) {
            return o.round;
        }).round;
        // Filter tweets that have not been seen for the most time,
        // excluding the ones that are visible on the screen
        // (the last case is when there is not much tweets to loop on, when looping)
        var tweets = _.filter(self.pool_cache, function (f) {
            var el = $('*[data-tweet-id="' + f.id + '"]');
            if (f.round <= leastRound && (!el.length || el.offset().top > $(window).height())) {
                return f;
            }
        });
        if (this.shuffle) {
            tweets = _.shuffle(tweets);
        }
        if (tweets.length) {
            var tweet = tweets[0];
            self.pool_cache[tweet.id].round = leastRound + 1;
            var tweetDesc = $(tweet.tweet_html);
            $(qweb.render('website_twitter_wall_tweets', {
                tweet: tweetDesc.prop('outerHTML'),
            })).prependTo(self.prependTweetsTo);
            var nextPrepend = self.prependTweetsTo.next('.o-tw-walls-col');
            self.prependTweetsTo = nextPrepend.length ? nextPrepend.first() : $('.o-tw-walls-col').first();
        }
    },
    /**
     * @private
     */
    _destroy: function () {
        clearInterval(this.interval);
        this.zoom(1);
    },
});

publicWidget.registry.websiteTwitterWall = publicWidget.Widget.extend({
    selector: '.o-tw-walls',
    xmlDependencies: ['/website_twitter_wall/static/src/xml/website_twitter_wall_tweet.xml'],
    events: {
        'click .o-tw-tweet-delete': '_onDeleteTweet',
        'click .o-tw-live-btn': '_onLiveButton',
        'click .o-tw-option': '_onOption',
        'click .o-tw-zoom': '_onZoom',
    },

    /**
     * @override
     * @param {Object} parent
     */
    start: function () {
        var self = this;
        this.twitterWall;
        this.mouseTimer;

        // create an observer instance
        var observer = new MutationObserver(function (mutations) {
            mutations.forEach(function (mutation) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'data-tweet-id') {
                    $(mutation.target.contentDocument).find('.Tweet-header .Tweet-brand, .Tweet-body .Tweet-actions').remove();
                    $(mutation.target.contentDocument).find('body').css('zoom', $('body').css('zoom'));
                    $(mutation.target.contentDocument).find('.EmbeddedTweet').removeClass('js-clickToOpenTarget');
                }
            });
        });

        // pass in the target node, as well as the observer options
        observer.observe($('.o-tw-walls')[0], {
            attributes: true,
            childList: true,
            characterData: false,
            subtree: true,
        });

        // Do some stuff on Fullscreen and exit Fullscreen
        $(document).on('webkitfullscreenchange mozfullscreenchange fullscreenchange MSFullscreenChange', function () {
            $('#oe_main_menu_navbar, header, .o-tw-toggle, footer').slideToggle('slow');
            if (document.fullScreen || document.mozFullScreen || document.webkitIsFullScreen) {

                // Initialize widgets
                this.twitterWall = new TweetWall(self, parseInt($('.o-tw-walls').data('wall-id')));

                // Hide scroll
                window.scrollTo(0, 0);
                $('body').css({'position': 'fixed'}).addClass('o-tw-view-live');
                $('center.o-tw-tweet > span').hide();
                $('.o-tw-tweet-delete').hide();
                if ($('#oe_main_menu_navbar').length) {
                    $('.o-tw-walls').css('margin-top', '64px');
                } else {
                    $('.o-tw-walls').css('margin-top', '98px');
                }
                // Hide mouse cursor after 2 seconds
                var cursorVisible = true;
                document.onmousemove = function () {
                    if (this.mouseTimer) {
                        window.clearTimeout(this.mouseTimer);
                    }
                    if (!cursorVisible) {
                        document.body.style.cursor = 'default';
                        cursorVisible = true;
                    }
                    this.mouseTimer = window.setTimeout(function () {
                        this.mouseTimer = null;
                        document.body.style.cursor = 'none';
                        cursorVisible = false;
                    }, 2000);
                };
            } else {
                $('body').css({'position': 'initial'}).removeClass('o-tw-view-live');
                $('center.o-tw-tweet > span').show();
                $('.o-tw-tweet-delete').show();
                $('.o-tw-walls').css('margin-top', '0');
                document.body.style.cursor = 'default';
                if (this.mouseTimer) {
                    clearTimeout(this.mouseTimer);
                }
                this.twitterWall.destroy();
            }
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {number} number
     * @param {string} single
     */
    _setColumns: function (number, single) {
        var cols = $('.o-tw-walls-col').length;
        var i = cols;
        var newCols = [];
        while (i < number) {
            newCols.push($('<div class="o-tw-walls-col col-' + 12 / number + '"></div>').appendTo('.o-tw-walls'));
            i++;
        }
        $('.o-tw-walls-col:gt(' + (number - 1) + ')').remove();
        $('.o-tw-walls-col').removeClass('col-4 col-6 col-12').addClass('col-' + 12 / number);
        if (single) {
            $('.o-tw-walls-col').addClass('o-tw-tweet-single');
        } else if (single === false) {
            $('.o-tw-walls-col').removeClass('o-tw-tweet-single');
        }
        if (newCols.length) {
            this.twitterWall.prependTweetsTo = newCols[0];
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Delete tweet
     *
     * @override
     * @param {Event} ev
     */
    _onDeleteTweet: function (ev) {
        var tweet = $(ev.target).closest('.o-tw-tweet');
        this._rpc({'model':
            'website.twitter.tweet',
            'method': 'unlink',
            'args': [[tweet.data('tweet-id')]]
        }).then(function (res) {
            if (res) {
                tweet.slideUp(500);
            }
        });
    },
    /**
     * Toggle Fullscreen
     *
     * @override
     */
    _onLiveButton: function () {
        if ((document.fullScreenElement && document.fullScreenElement !== null) || (!document.mozFullScreen && !document.webkitIsFullScreen)) {
            if (document.documentElement.requestFullScreen) {
                document.documentElement.requestFullScreen();
            } else if (document.documentElement.mozRequestFullScreen) {
                document.documentElement.mozRequestFullScreen();
            } else if (document.documentElement.webkitRequestFullScreen) {
                document.documentElement.webkitRequestFullScreen(Element.ALLOW_KEYBOARD_INPUT);
            }
        } else {
            if (document.cancelFullScreen) {
                document.cancelFullScreen();
            } else if (document.mozCancelFullScreen) {
                document.mozCancelFullScreen();
            } else if (document.webkitCancelFullScreen) {
                document.webkitCancelFullScreen();
            }
        }
    },
    /**
     * Handle all options
     *
     * @override
     * @param {Event} ev
     */
    _onOption: function (ev) {
        this.twitterWall.timeout = 7000;
        var active = $(ev.target).hasClass('active');
        $(ev.target).toggleClass('active');
        switch ($(ev.target).data('operation')) {
            case 'list':
                $(ev.target).siblings().removeClass('active');
                this._setColumns(1);
                break;
            case 'double':
                $(ev.target).siblings().removeClass('active');
                this._setColumns(2);
                break;
            case 'triple':
                $(ev.target).siblings().removeClass('active');
                this._setColumns(3);
                break;
            case 'single':
                this._setColumns($('.o-tw-walls-col').length, !active);
                this.twitterWall.timeout = 15000;
                break;
            case 'repeat':
                this.twitterWall.toggle_repeat();
                break;
            case 'shuffle':
                this.twitterWall.toggle_shuffle();
                break;
        }
        $(document).trigger('clear_tweet_queue');
    },
    /**
     * Handle zoom options
     *
     * @override
     * @param {Event} ev
     */
    _onZoom: function (ev) {
        var step = $(ev.target).data('operation') === 'plus' ? 0.05 : -0.05;
        this.twitterWall.zoom(this.twitterWall.zoomLevel + step);
    },
});
});
