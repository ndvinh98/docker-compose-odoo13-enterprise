odoo.define('social_facebook.test_comments', function (require) {
"use strict";

var StreamPostFacebookComments = require('social.social_facebook_post_kanban_comments')
var StreamPostKanbanView = require('social.social_stream_post_kanban_view');
var StreamPostComments = require('social.social_post_kanban_comments');
var testUtils = require('web.test_utils');
var createView = testUtils.createView;

var getArch = function (){
return '<kanban class="o_social_stream_post_kanban"' +
    '    create="0"' +
    '    edit="0"' +
    '    records_draggable="false"' +
    '    group_create="false"' +
    '    js_class="social_stream_post_kanban_view">' +
    '    <field name="id"/>' +
    '    <field name="author_name"/>' +
    '    <field name="author_link"/>' +
    '    <field name="post_link"/>' +
    '    <field name="published_date"/>' +
    '    <field name="formatted_published_date"/>' +
    '    <field name="message"/>' +
    '    <field name="media_type"/>' +
    '    <field name="account_id"/>' +
    '    <field name="link_url"/>' +
    '    <field name="link_image_url"/>' +
    '    <field name="link_title"/>' +
    '    <field name="link_description"/>' +
    '    <field name="stream_post_image_ids"/>' +
    '    <field name="stream_post_image_urls"/>' +
    '    <field name="stream_id" readonly="1"/>' +
    '    <field name="facebook_author_id"/>' +
    '    <field name="facebook_likes_count"/>' +
    '    <field name="facebook_user_likes"/>' +
    '    <field name="facebook_comments_count"/>' +
    '    <field name="facebook_shares_count"/>' +
    '    <field name="facebook_reach"/>' +
    '    <field name="facebook_page_id"/>' +
    '    <templates>' +
    '        <t t-name="kanban-box">' +
    '            <div class="o_social_stream_post_kanban_global p-0 mb8">' +
    '                <div class="o_social_stream_post_message">' +
    '                    <div class="col-md-12 p-2 pb0 m-0 row">' +
    '                        <div class="o_social_stream_post_author col-md-8 m-0 p-0">' +
    '                            <t t-if="record.post_link.value">' +
    '                                <a t-att-href="record.post_link.value" target="_blank">' +
    '                                    <div class="d-inline-block"><t t-esc="record.author_name.value or \'Unknown\'"></t></div>' +
    '                                </a>' +
    '                            </t>' +
    '                            <t t-else="">' +
    '                                <div class="d-inline-block"><t t-esc="record.author_name.value or \'Unknown\'"></t></div>' +
    '                            </t>' +
    '                        </div>' +
    '                        <div class="o_social_stream_post_published_date col-md-4 m-0 p-0 text-right">' +
    '                            <small>' +
    '                                <span t-esc="record.published_date.value and record.published_date.value.split(\' \')[0] or \'\'"' +
    '                                    t-att-title="record.published_date.value">' +
    '                                </span>' +
    '                            </small>' +
    '                        </div>' +
    '                    </div>' +
    '                    <div class="pt8">' +
    '                        <t t-set="has_attachments" t-value="record.stream_post_image_ids.raw_value.length !== 0 || record.link_url.value"></t>' +
    '                        <div t-attf-class="o_social_stream_post_message_text p-2 pb0 mb-3 #{has_attachments ? \'o_social_stream_post_with_attachments\' : \'\'}">' +
    '                            <field name="message"  widget="social_kanban_field_emoji" />' +
    '                        </div>' +
    '                        <div t-if="record.stream_post_image_ids.raw_value.length !== 0"' +
    '                            class="o_social_stream_post_image pt8 p-2"' +
    '                            t-att-data-images="record.stream_post_image_urls.raw_value">' +
    '                            <t t-set="image_urls_json" t-value="JSON.parse(record.stream_post_image_urls.raw_value)"></t>' +
    '                            <t t-foreach="image_urls_json.length > 5 ? image_urls_json.slice(0, 4) : image_urls_json" t-as="image_url">' +
    '                                <img class="o_social_stream_post_image_click" t-att-src="image_url" alt="Post Image" t-att-data-current-index="image_url_index" />' +
    '                            </t>' +
    '                            <t t-if="image_urls_json.length > 5">' +
    '                                <a class="d-inline-block o_social_stream_post_image_more" t-att-data-current-index="4">' +
    '                                    <img t-att-src="image_urls_json[4]" alt="Post Image" />' +
    '                                    <div>' +
    '                                        +<t t-esc="image_urls_json.length - 5"></t>' +
    '                                    </div>' +
    '                                </a>' +
    '                            </t>' +
    '                        </div>' +
    '                        <a t-if="record.link_url.value"' +
    '                            class="o_social_stream_post_link p-2"' +
    '                            t-att-href="record.link_url.raw_value"' +
    '                            target="_blank">' +
    '                            <img t-if="record.link_image_url.raw_value" t-att-src="record.link_image_url.raw_value" alt="Link Image" />' +
    '                            <div class="o_social_stream_post_link_text">' +
    '                                <div class="o_social_stream_post_link_title" t-esc="record.link_title.value"></div>' +
    '                                <div class="o_social_stream_post_link_description" t-esc="record.link_description.value"></div>' +
    '                            </div>' +
    '                        </a>' +
    '                    </div>' +
    '                </div>' +
    '                <div class="o_social_stream_post_facebook_stats col-md-12 row m-0 p-0" t-if="record.media_type.raw_value === \'facebook\'">' +
    '                    <div t-attf-class="o_social_facebook_likes #{record.facebook_user_likes.raw_value ? \'o_social_facebook_user_likes\' : \'\'} col-md-3 border border-left-0 border-bottom-0 m-0 p-0 text-center"' +
    '                        t-att-data-user-likes="record.facebook_user_likes.raw_value"' +
    '                        t-att-data-post-id="record.id.raw_value">' +
    '                        <span class="o_social_kanban_likes_count" t-esc="record.facebook_likes_count.raw_value !== 0 ? record.facebook_likes_count.raw_value : \'\'"></span>' +
    '                        <i class="fa fa-thumbs-up" title="Likes"></i>' +
    '                    </div>' +
    '                    <div class="o_social_facebook_comments o_social_comments o_social_subtle_btn px-3"' +
    '                        data-media-type="facebook"' +
    '                        t-att-data-post-message="record.message.raw_value"' +
    '                        t-att-data-post-images="record.stream_post_image_urls.raw_value"' +
    '                        t-att-data-post-link="record.post_link.raw_value"' +
    '                        t-att-data-facebook-author-id="False"' +
    '                        t-att-data-author-name="record.author_name.raw_value"' +
    '                        t-att-data-author-link="record.author_link.raw_value"' +
    '                        t-att-data-published-date="record.published_date.value"' +
    '                        t-att-data-formatted-published-date="record.formatted_published_date.value"' +
    '                        t-att-data-link-url="record.link_url.raw_value"' +
    '                        t-att-data-link-image="record.link_image_url.raw_value"' +
    '                        t-att-data-link-title="record.link_title.raw_value"' +
    '                        t-att-data-link-description="record.link_description.raw_value"' +
    '                        t-att-data-post-id="record.id.raw_value"' +
    '                        t-att-data-facebook-page-id="record.account_id.raw_value"' +
    '                        t-att-data-facebook-user-likes="record.facebook_user_likes.raw_value"' +
    '                        t-att-data-facebook-likes-count="record.facebook_likes_count.raw_value"' +
    '                        t-att-data-facebook-shares-count="record.facebook_shares_count.raw_value"' +
    '                        t-att-data-facebook-reach="record.facebook_reach.raw_value">' +
    '                        <i class="fa fa-comments" title="Comments"></i>' +
    '                        <b t-esc="record.facebook_comments_count.value !== \'0\' ? record.facebook_comments_count.value : \'\'"/>' +
    '                    </div>' +
    '                    <div class="col-md-3 border border-left-0 border-bottom-0 m-0 p-0 text-center">' +
    '                        <t t-esc="record.facebook_shares_count.value"></t>' +
    '                        <i class="fa fa-share-alt" title="Shares"></i>' +
    '                    </div>' +
    '                    <div class="col-md-3 border border-left-0 border-bottom-0 border-right-0 m-0 p-0 text-center">' +
    '                        <t t-esc="record.facebook_reach.value"></t>' +
    '                        <i class="fa fa-eye" title="Reach"></i>' +
    '                    </div>' +
    '                </div>' +
    '            </div>' +
    '        </t>' +
    '    </templates>' +
    '</kanban>';
};


QUnit.module('Facebook Comments', {
    beforeEach: function () {
        this.data = {
            'social.media': {
                fields: {
                    id: {type: 'integer'},
                    name: {type: 'char'},
                    has_streams: {type: 'boolean'},
                },
                records: [{
                    id: 1,
                    name: 'Facebook',
                    has_streams: true,
                }]
            },
            'social.account': {
                fields: {
                    id: {type: 'integer'},
                    name: {type: 'char'},
                    is_media_disconnected: {type: 'boolean'},
                    facebook_account_id: {type: 'char'},
                    audience: {type: 'integer'},
                    audience_trend: {type: 'double'},
                    engagement: {type: 'integer'},
                    engagement_trend: {type: 'double'},
                    stories: {type: 'integer'},
                    stories_trend: {type: 'double'},
                    has_account_stats: {type: 'boolean'},
                    has_trends: {type: 'boolean'},
                    stats_link: {type: 'char'},
                    media_id: {
                        string: 'Media',
                        type: 'many2one',
                        relation: 'social.media'
                    }
                },
                records: [{
                    id: 1,
                    name: 'Jack\'s Page',
                    is_media_disconnected: false,
                    has_account_stats: true,
                    has_trends: true,
                    audience: 519,
                    audience_trend: 50,
                    engagement: 6000,
                    engagement_trend: 60,
                    stories: 70000,
                    stories_trend: -20,
                    stats_link: 'facebook.com/jack',
                    media_id: 1
                }, {
                    id: 2,
                    name: 'Jhon\'s Page',
                    has_account_stats: true,
                    has_trends: false,
                    audience: 400,
                    audience_trend: 0,
                    engagement: 400,
                    engagement_trend: 0,
                    stories: 4000,
                    stories_trend: 0,
                    stats_link: 'facebook.com/jhon',
                    media_id: 1
                }]
            },
            social_stream: {
                fields: {
                    id: {type: 'integer'},
                    name: {type: 'char'},
                    media_id: {
                        string: 'Media',
                        type: 'many2one',
                        relation: 'social.media'
                    }
                },
                records: [{
                    id: 1,
                    name: 'Stream 1',
                    media_id: 1
                }, {
                    id: 2,
                    name: 'Stream 2',
                    media_id: 1
                }]
            },
            social_stream_post_image: {
                fields: {
                    id: {type: 'integer'},
                    image_url: {type: 'char'}
                }
            },
            social_stream_post: {
                fields: {
                    id: {type: 'integer'},
                    name: {type: 'char'},
                    author_name: {type: 'char'},
                    author_link: {type: 'char'},
                    post_link: {type: 'char'},
                    published_date: {type: 'datetime'},
                    formatted_published_date: {type: 'char'},
                    message: {type: 'text'},
                    media_type: {type: 'char'},
                    link_url: {type: 'char'},
                    link_image_url: {type: 'char'},
                    link_title: {type: 'char'},
                    link_description: {type: 'char'},
                    stream_post_image_urls: {type: 'char'},
                    facebook_author_id: {type: 'integer'},
                    facebook_likes_count: {type: 'integer'},
                    facebook_user_likes: {type: 'boolean'},
                    facebook_comments_count: {type: 'integer'},
                    facebook_shares_count: {type: 'integer'},
                    facebook_reach: {type: 'integer'},
                    stream_post_image_ids: {
                        string: 'Stream Post Images',
                        type: 'one2many',
                        relation: 'social_stream_post_image'
                    },
                    stream_id: {
                        string: 'Stream',
                        type: 'many2one',
                        relation: 'social_stream'
                    },
                    facebook_page_id: {
                        string: 'Facebook Page',
                        type: 'many2one',
                        relation: 'social.account'
                    },
                    account_id: {
                        string: 'Account',
                        type: 'many2one',
                        relation: 'social.account'
                    }
                },
                records: [{
                    id: 1,
                    author_name: 'Jhon',
                    post_link: 'www.odoosocial.com/link1',
                    author_link: 'www.odoosocial.com/author1',
                    published_date: "2019-08-20 14:16:00",
                    formatted_published_date: "2019-08-20 14:16:00",
                    message: 'Message 1 Youtube',
                    media_type: 'facebook',
                    link_url: 'blog.com/odoosocial',
                    link_title: 'Odoo Social',
                    link_description: 'Odoo Social Description',
                    facebook_author_id: 1,
                    facebook_likes_count: 5,
                    facebook_user_likes: true,
                    facebook_comments_count: 15,
                    facebook_shares_count: 3,
                    facebook_reach: 18,
                    facebook_page_id: 1,
                    account_id: 1,
                    stream_id: 1
                }, {
                    id: 2,
                    author_name: 'Jack',
                    post_link: 'www.odoosocial.com/link2',
                    author_link: 'www.odoosocial.com/author2',
                    published_date: "2019-08-20 14:17:00",
                    formatted_published_date: "2019-08-20 14:17:00",
                    message: 'Message 2 Images',
                    media_type: 'facebook',
                    social_stream_post_image: '["photos.com/image1.png","photos.com/image2.png"]',
                    facebook_author_id: 2,
                    facebook_likes_count: 10,
                    facebook_user_likes: false,
                    facebook_comments_count: 25,
                    facebook_shares_count: 4,
                    facebook_page_id: 1,
                    account_id: 1,
                    facebook_reach: 33,
                    stream_id: 2
                }, {
                    id: 3,
                    author_name: 'Michel',
                    post_link: 'www.odoosocial.com/link3',
                    author_link: 'www.odoosocial.com/author3',
                    published_date: "2019-08-20 14:18:00",
                    formatted_published_date: "2019-08-20 14:18:00",
                    message: 'Message 3',
                    media_type: 'facebook',
                    facebook_author_id: 3,
                    facebook_likes_count: 0,
                    facebook_user_likes: false,
                    facebook_comments_count: 0,
                    facebook_shares_count: 0,
                    facebook_page_id: 1,
                    account_id: 1,
                    facebook_reach: 42,
                    stream_id: 2
                }]
            }
        };
    }
}, function (){
    QUnit.test('Check accounts statistics', async function (assert) {
        var self = this;
        assert.expect(7);

        var kanban = await createView({
            View: StreamPostKanbanView,
            model: 'social_stream_post',
            data: this.data,
            arch: getArch(),
            mockRPC: function (route, params) {
                if (params.method === 'refresh_all') {
                    assert.ok(true);
                    return Promise.resolve({});
                } else if (params.method === 'refresh_statistics') {
                    assert.ok(true);
                    var records = self.data['social.account'].records.slice();
                    for(var i = 0; i < records.length; i++){
                        if (!Array.isArray(records[i].media_id)) {
                            records[i].media_id = [records[i].media_id, 'Facebook'];
                        }
                    }
                    return Promise.resolve(records);
                } else if(route.startsWith('https://graph.facebook.com/')) {
                    return Promise.resolve('');
                }
                return this._super.apply(this, arguments);
            }
        });

        assert.containsN(kanban, ".o_social_stream_stat_box", 2,
            "Kanban View should contain exactly 2 lines of account statistics.");

        // 3 because '50%' counts as a match (and 60M, and -20%)
        // so if we want to check that there are no actual 0%, it means we want only 3 times "contains 0%"
        assert.containsN(kanban, ".o_social_stream_stat_box small:contains('0%')", 3,
            "Accounts with has_trends = false should not display trends.");

        assert.containsOnce(kanban, ".o_social_stream_stat_box b:contains('519')",
            "Audience is correctly displayed.");

        assert.containsOnce(kanban, ".o_social_stream_stat_box small:contains('50%')",
            "Audience trend is correctly displayed.");

        kanban.destroy();
    });


    QUnit.test('Check messages display', async function (assert) {
        assert.expect(5);

        var kanban = await createView({
            View: StreamPostKanbanView,
            model: 'social_stream_post',
            data: this.data,
            arch: getArch(),
            mockRPC: function (route, params) {
                if (params.method === 'refresh_all' || params.method === 'refresh_statistics') {
                    return Promise.resolve({});
                } else if(route.startsWith('https://graph.facebook.com/')) {
                    return Promise.resolve('');
                }
                return this._super.apply(this, arguments);
            }
        });

        assert.containsN(kanban, '.o_social_stream_post_kanban_global', 3,
            "There should be 3 posts displayed on kanban view.");

        assert.containsOnce(kanban,
            ".o_social_stream_post_facebook_stats div:contains('5') .fa-thumbs-up",
            "The first comment should have 5 likes");

        assert.containsOnce(kanban,
            ".o_social_stream_post_facebook_stats div:contains('15') .fa-comments",
            "The first comment should have 15 comments");

        assert.containsOnce(kanban,
            ".o_social_stream_post_facebook_stats div:contains('4') .fa-share-alt",
            "The first comment should have 4 shares");

        assert.containsOnce(kanban,
            ".o_social_stream_post_facebook_stats div:contains('18') .fa-eye",
            "The first comment should have 18 'reach'");

        kanban.destroy();
    });

    QUnit.test('Check comments behavior', async function (assert) {
        assert.expect(17);

        // Patch getAuthorPictureSrc to avoid trying to fetch images from FB
        testUtils.mock.patch(StreamPostFacebookComments, {
            getAuthorPictureSrc: function () {
                return '';
            }
        });

        var kanban = await createView({
            View: StreamPostKanbanView,
            model: 'social_stream_post',
            data: this.data,
            arch: getArch(),
            mockRPC: function (route, params) {
                if (params.method === 'refresh_all' || params.method === 'refresh_statistics') {
                    return Promise.resolve({});
                } else if(params.method === 'get_facebook_comments') {
                    return Promise.resolve({
                        summary: {
                            total_count: 1
                        },
                        comments: [{
                            from: {
                                id: 1,
                                picture: {
                                    data: {
                                        url: 'socialtest/picture'
                                    }
                                }
                            },
                            user_likes: false,
                            message: 'Root Comment',
                            likes: {
                                summary: {
                                    total_count: 3
                                }
                            },
                            comments: {
                                data: [{
                                    from: {
                                        id: 2,
                                        picture: {
                                            data: {
                                                url: 'socialtest/picture'
                                            }
                                        }
                                    },
                                    user_likes: true,
                                    message: 'Sub Comment 1',
                                    likes: {
                                        summary: {
                                            total_count: 5
                                        }
                                    }
                                }, {
                                    from: {
                                        id: 3,
                                        picture: {
                                            data: {
                                                url: 'socialtest/picture'
                                            }
                                        }
                                    },
                                    user_likes: false,
                                    message: 'Sub Comment 2',
                                    likes: {
                                        summary: {
                                            total_count: 10
                                        }
                                    }
                                }]
                            }
                        }]
                    });
                } else if (params.method === 'like_facebook_comment') {
                    // test that 2 calls are made
                    assert.ok(true);
                    return Promise.resolve({});
                } else if(route.startsWith('https://graph.facebook.com/')) {
                    return Promise.resolve('');
                } else if(route === 'socialtest/picture') {
                    return Promise.resolve('');
                }
                return this._super.apply(this, arguments);
            }
        });

        await testUtils.dom.click(kanban.$('.o_social_stream_post_facebook_stats:first .fa-comments'));

        // 1. Root comment is displayed with 3 likes and 2 replies options.
        assert.containsOnce($('body'),
            ".o_social_comment_wrapper .o_social_comment_message div.o_social_comment_text:contains('Root Comment')",
            "Root comment should be displayed.");

        assert.containsOnce($('body'),
            ".o_social_comment_wrapper div.o_social_comment_message:contains('View 2 replies')",
            "There are 2 replies below the root comment.");

        assert.containsOnce($('body'),
            ".o_social_comment_wrapper .o_social_likes_count:contains('3')",
            "The root comment should have 3 likes");

        // 2. Load replies and check display.
        await testUtils.dom.click(
            $(".o_social_comment_wrapper span.o_social_comment_load_replies"));

        assert.containsOnce($('body'),
            ".o_social_comment_wrapper .o_social_comment_message div.o_social_comment_text:contains('Sub Comment 1')",
            "First sub comment should be loaded");

        assert.containsOnce($('body'),
            ".o_social_comment_wrapper .o_social_comment_message div.o_social_comment_text:contains('Sub Comment 2')",
            "Second sub comment should be loaded");

        // 3. Check like/dislike behavior

        // 3a. Check like status and count
        assert.containsOnce($('body'),
            ".o_social_comment .o_social_comment:contains('Sub Comment 1') .o_social_comment_user_likes",
            "First comment is liked");

        assert.containsOnce($('body'),
            ".o_social_comment .o_social_comment:contains('Sub Comment 2'):not(.o_social_comment_user_likes)",
            "Second comment is NOT liked");

        assert.containsOnce($('body'),
            ".o_social_comment .o_social_comment:contains('Sub Comment 1') .o_social_likes_count:contains('5')",
            "Sub comment 1 should have 5 likes");

        assert.containsOnce($('body'),
            ".o_social_comment .o_social_comment:contains('Sub Comment 2') .o_social_likes_count:contains('10')",
            "Sub comment 2 should have 10 likes");

        // 3b. Dislike first and like second
        await testUtils.dom.click(
            $(".o_social_comment .o_social_comment:contains('Sub Comment 1') .o_social_comment_like"));

        await testUtils.dom.click(
            $(".o_social_comment .o_social_comment:contains('Sub Comment 2') .o_social_comment_like"));

        // 3a. Check like status and count now that it's reversed
        assert.containsOnce($('body'),
            ".o_social_comment .o_social_comment:contains('Sub Comment 1'):not(.o_social_comment_user_likes)",
            "First comment is NOT liked");

        assert.containsOnce($('body'),
            ".o_social_comment .o_social_comment:contains('Sub Comment 2') .o_social_comment_user_likes",
            "Second comment is liked");

        assert.containsOnce($('body'),
            ".o_social_comment .o_social_comment:contains('Sub Comment 1') .o_social_likes_count:contains('4')",
            "Sub comment 1 should have 4 likes");

        assert.containsOnce($('body'),
            ".o_social_comment .o_social_comment:contains('Sub Comment 2') .o_social_likes_count:contains('11')",
            "Sub comment 2 should have 11 likes");

        // 4. Add comment

        // Patch ajaxRequest to return New Comment
        testUtils.mock.patch(StreamPostComments, {
            _ajaxRequest: function (endpoint, params) {
                return Promise.resolve(JSON.stringify({
                    from: {
                        id: 1,
                        picture: {
                            data: {
                                url: 'socialtest/picture'
                            }
                        }
                    },
                    message: params.data.get('message'),
                    likes: {
                        summary: {
                            total_count: 3
                        }
                    }
                }));
            },
        });

        await testUtils.fields.editInput(
            $('.o_social_write_reply:first .o_social_add_comment'), 'New Comment');
        await testUtils.fields.triggerKeydown(
            $('.o_social_write_reply:first .o_social_add_comment'), 'enter');

        assert.containsOnce($('body'),
            ".o_social_comment_wrapper .o_social_comment_message div.o_social_comment_text:contains('New Comment')",
            "New Comment should be displayed.");

        // 5. Add reply to comment
        await testUtils.dom.click(
            $(".o_social_comment .o_social_comment:contains('Sub Comment 1') .o_social_comment_reply"));
        await testUtils.fields.editInput(
            $(".o_social_comment:contains('Root Comment') .o_social_add_comment"), 'New Reply');
        await testUtils.fields.triggerKeydown(
            $(".o_social_comment:contains('Root Comment') .o_social_add_comment"), 'enter');

        assert.containsOnce($('body'),
            ".o_social_comment_wrapper .o_social_comment_message div.o_social_comment_text:contains('New Reply')",
            "New Reply should be displayed");

        kanban.destroy();
        $('body .modal').remove();
    });
});

});
