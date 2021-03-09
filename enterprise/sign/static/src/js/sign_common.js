odoo.define('sign.PDFIframe', function (require) {
    'use strict';

    var config = require('web.config');
    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var Widget = require('web.Widget');

    var _t = core._t;

    const PinchItemMixin = {

        events: {
            'touchstart .o_pinch_item': '_onResetPinchCache',
            'touchmove .o_pinch_item': '_onPinchMove',
            'touchend .o_pinch_item': '_onResetPinchCache',
        },

        /**
         * @param {Object} options
         * @param {jQuery} options.$target
         *        Element used as target where the pinch must be applied
         * @param {function} [options.increaseDistanceHandler]
         *        Handler called when the distance pinched between the 2 pointer is decreased
         * @param {function} [options.decreaseDistanceHandler]
         *        Handler called when the distance pinched between the 2 pointer is increased
         * }
         */
        init(options) {
            this.prevDiff = null;
            this.$target = options.$target;
            this.$target.addClass('o_pinch_item');
            this.increaseDistanceHandler = options.increaseDistanceHandler ? options.increaseDistanceHandler : () => {};
            this.decreaseDistanceHandler = options.decreaseDistanceHandler ? options.decreaseDistanceHandler : () => {};
        },

        //--------------------------------------------------------------------------
        // Handlers
        //--------------------------------------------------------------------------

        /**
         * This function implements a 2-pointer horizontal pinch/zoom gesture.
         *
         * If the distance between the two pointers has increased (zoom in),
         * distance is decreasing (zoom out)
         *
         * This function sets the target element's border to "dashed" to visually
         * indicate the pointer's target received a move event.
         * @param ev
         * @private
         */
        _onPinchMove(ev) {
            const touches = ev.touches;
            // If two pointers are down, check for pinch gestures
            if (touches.length === 2) {
                // Calculate the current distance between the 2 fingers
                const deltaX = touches[0].pageX - touches[1].pageX;
                const deltaY = touches[0].pageY - touches[1].pageY;
                const curDiff = Math.hypot(deltaX, deltaY);
                if (this.prevDiff == null) {
                    this.prevDiff = curDiff;
                }
                const scale = this.prevDiff / curDiff;
                if (scale < 1) {
                    this.decreaseDistanceHandler(ev);
                } else if (scale > 1) {
                    this.increaseDistanceHandler(ev);
                }
            }
        },

        /**
         *
         * @private
         */
        _onResetPinchCache() {
            this.prevDiff = null;
        },
    };

    var PDFIframe = Widget.extend(Object.assign({}, PinchItemMixin, {
        init: function(parent, attachmentLocation, editMode, datas, role) {
            this._super(parent);
            var self = this;
            this.attachmentLocation = attachmentLocation;
            this.editMode = editMode;
            for(var dataName in datas) {
                this._set_data(dataName, datas[dataName]);
            }

            this.role = role || 0;
            this.configuration = {};

            var _res, _rej;
            this.fullyLoaded = new Promise(function(resolve, reject) {
                _res = resolve;
                _rej = reject;
            }).then(function() {
                // Init pinch event only after have the pdf loaded
                PinchItemMixin.init.call(self, {
                    $target: self.$el.find('#viewerContainer #viewer'),
                    decreaseDistanceHandler: () => self.$('button#zoomIn').click(),
                    increaseDistanceHandler: () => self.$('button#zoomOut').click()
                });
                return arguments;
            });
            this.fullyLoaded.resolve = _res;
            this.fullyLoaded.reject = _rej;
        },

        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------
        _appendDownloadCompleteButton() {
            const cloneDownloadButton = $button => $button.clone()
                .attr('id', $button.attr('id') + '_completed')
                .prop('title', _t("Download Document"))
                .on('click', () => window.location = this.attachmentLocation.replace('origin', 'completed'));
            // inside toolbar
            const $buttonDownloadPrimary = this.$('button#download');
            $buttonDownloadPrimary.after(cloneDownloadButton($buttonDownloadPrimary));
            // inside the more button on the toolbar
            const $buttonDownloadSecondary = this.$('button#secondaryDownload');
            const $buttonDownloadSecond = cloneDownloadButton($buttonDownloadSecondary);
            if ($buttonDownloadSecond.hasClass('secondaryToolbarButton')) {
                $buttonDownloadSecond.find('span').text(_t("Download Document"));
            }
            $buttonDownloadSecondary.after($buttonDownloadSecond);
        },
        _set_data: function(dataName, data) {
            this[dataName] = {};
            if(data instanceof jQuery) {
                var self = this;
                data.each(function(i, el) {
                    self[dataName][$(el).data('id')] = $(el).data();
                }).detach();
            } else {
                for(var i = 0 ; i < data.length ; i++) {
                    this[dataName][data[i].id] = data[i];
                }
            }
        },

        start: function() {
            this.$iframe = this.$el; // this.$el will be changed to the iframe html tag once loaded
            var self = this;
            this.pdfView = (this.$iframe.attr('readonly') === "readonly");
            this.readonlyFields = this.pdfView || this.editMode;

            var viewerURL = "/web/static/lib/pdfjs/web/viewer.html?unique="+ (+new Date()) +"&file=";
            viewerURL += encodeURIComponent(this.attachmentLocation).replace(/'/g,"%27").replace(/"/g,"%22") + "#page=1";
            viewerURL += config.device.isMobile ? "&zoom=page-fit" : "&zoom=page-width";
            this.$iframe.ready(function () {
                self.waitForPDF();
            });
            this.$iframe.attr('src', viewerURL);

            return Promise.all([this._super(), this.fullyLoaded]);
        },

        waitForPDF: function() {
            if(this.$iframe.contents().find('#errorMessage').is(":visible")) {
                this.fullyLoaded.resolve();
                return Dialog.alert(this, _t("Need a valid PDF to add signature fields !"));
            }

            var nbPages = this.$iframe.contents().find('.page').length;
            var nbLayers = this.$iframe.contents().find('.textLayer').length;
            if(nbPages > 0 && nbLayers > 0) {
                this.nbPages = nbPages;
                this.doPDFPostLoad();
            } else {
                var self = this;
                setTimeout(function() { self.waitForPDF(); }, 50);
            }
        },

        doPDFPostLoad: function() {
            var self = this;
            this.setElement(this.$iframe.contents().find('html'));

            this.$('#openFile, #pageRotateCw, #pageRotateCcw, #pageRotateCcw, #viewBookmark').add(this.$('#lastPage').next()).hide();
            this.$('button#print').prop('title', _t("Print original document"));
            this.$('button#download').prop('title', _t("Download original document"));
            if (this.readonlyFields && !this.editMode) {
                this._appendDownloadCompleteButton();
            }
            if (config.device.isMobile) {
                this.$('button#zoomIn').click();
            } else {
                this.$('button#zoomOut').click().click();
            }
            for(var i = 1 ; i <= this.nbPages ; i++) {
                this.configuration[i] = [];
            }

            var $cssLink = $("<link/>", {
                rel: "stylesheet", type: "text/css",
                href: "/sign/static/src/css/iframe.css"
            });
            var $faLink = $("<link/>", {
                rel: "stylesheet", type: "text/css",
                href: "/web/static/lib/fontawesome/css/font-awesome.css"
            });
            var $jqueryLink = $("<link/>", {
                rel: "stylesheet", type: "text/css",
                href: "/web/static/lib/jquery.ui/jquery-ui.css"
            });
            var $select2Css = $("<link/>", {
                rel: "stylesheet", type: "text/css",
                href: "/web/static/lib/select2/select2.css"
            });
            // use Node.appendChild to add resources and not jQuery that load script in top frame
            this.$('head')[0].appendChild($cssLink[0]);
            this.$('head')[0].appendChild($faLink[0]);
            this.$('head')[0].appendChild($jqueryLink[0]);
            this.$('head')[0].appendChild($select2Css[0]);

            var waitFor = [];

            $(Object.keys(this.signatureItems).map(function(id) { return self.signatureItems[id]; }))
                .sort(function(a, b) {
                    if(a.page !== b.page) {
                        return (a.page - b.page);
                    }

                    if(Math.abs(a.posY - b.posY) > 0.01) {
                        return (a.posY - b.posY);
                    } else {
                        return (a.posX - b.posX);
                    }
                }).each(function(i, el) {
                    var $signatureItem = self.createSignItem(
                        self.types[parseInt(el.type || el.type_id[0])],
                        !!el.required,
                        parseInt(el.responsible || el.responsible_id[0]) || 0,
                        parseFloat(el.posX),
                        parseFloat(el.posY),
                        parseFloat(el.width),
                        parseFloat(el.height),
                        el.value,
                        el.option_ids,
                        el.name
                    );
                    $signatureItem.data({itemId: el.id, order: i});
                    self.configuration[parseInt(el.page)].push($signatureItem);
                });

            Promise.all(waitFor).then(function() {
                refresh_interval();

                self.$('.o_sign_sign_item').each(function(i, el) {
                    self.updateSignItem($(el));
                });
                self.updateFontSize();

                self.$('#viewerContainer').css('visibility', 'visible').animate({'opacity': 1}, 1000);
                self.fullyLoaded.resolve();

                /**
                 * This function is called every 2sec to check if the PDFJS viewer did not detach some signature items.
                 * Indeed, when scrolling, zooming, ... the PDFJS viewer replaces page content with loading icon, removing
                 * any custom content with it.
                 * Previous solutions were tried (refresh after scroll, on zoom click, ...) but this did not always work
                 * for some reason when the PDF was too big.
                 */
                function refresh_interval() {
                    try { // if an error occurs it means the iframe has been detach and will be reinitialized anyway (so the interval must stop)
                        self.refreshSignItems();
                        self.refresh_timer = setTimeout(refresh_interval, 2000);
                    } catch (e) {}
                }
            });
        },

        refreshSignItems: function() {
            for(var page in this.configuration) {
                var $pageContainer = this.$('body #pageContainer' + page);
                for(var i = 0 ; i < this.configuration[page].length ; i++) {
                    if(!this.configuration[page][i].parent().hasClass('page')) {
                        $pageContainer.append(this.configuration[page][i]);
                    }
                }
            }
            this.updateFontSize();
        },

        display_select_options: function ($container, options, selected_options, readonly, active_option) {
            readonly = (readonly === undefined)? false : readonly;
            $container.empty();

            selected_options.forEach(function (id, index) {
                if (index !== 0) {
                    $container.append($('<span class="o_sign_option_separator">/</span>'));
                }
                var $op = $('<span class="o_sign_item_option"/>').text(options[id].value);
                $op.data('id', id);
                $container.append($op);
                if (!readonly) {
                    $op.on('click', click_handler);
                }
            });

            if (active_option) {
                select_option($container, active_option);
            }
            function select_option($container, option_id) {
                var $selected_op = $container.find(':data(id)').filter(function () { return $(this).data('id') === option_id;});
                var $other_options = $container.find(':data(id)').filter(function () { return $(this).data('id') !== option_id;});
                $selected_op.css("color", "black");
                $other_options.css("color", "black");
                $selected_op.addClass('o_sign_selected_option');
                $selected_op.removeClass('o_sign_not_selected_option');
                $other_options.removeClass('o_sign_selected_option');
                $other_options.addClass('o_sign_not_selected_option');
            }

            function click_handler(e) {
                var id = $(e.target).data('id');
                $container = $(e.target.parentElement);
                $container.parent().val(id);
                $container.parent().trigger('input');
                select_option($container, id);
            }
        },

        updateFontSize: function() {
            var self = this;
            var normalSize = this.$('.page').first().innerHeight() * 0.015;
            this.$('.o_sign_sign_item').each(function(i, el) {
                var $elem = $(el);
                var size = parseFloat($elem.css('height'));
                if ($.inArray(self.types[$elem.data('type')].item_type, ['signature', 'initial', 'textarea', 'selection']) > -1) {
                    size = normalSize;
                }

                $elem.css('font-size', size * 0.8);
            });
        },

        createSignItem: function (type, required, responsible, posX, posY, width, height, value, option_ids, name) {
            // jQuery.data parse 0 as integer, but 0 is not considered falsy for signature item
            if (value === 0) {
                value = "0";
            }
            var readonly = this.readonlyFields || (responsible > 0 && responsible !== this.role) || !!value;
            var selected_options = option_ids || [];

            var $signatureItem = $(core.qweb.render('sign.sign_item', {
                editMode: this.editMode,
                readonly: readonly,
                type: type['item_type'],
                value: value || "",
                options: selected_options,
                placeholder: (name) ? name : type['placeholder']
            }));

            if (type['item_type'] === 'selection') {
                var $options_display = $signatureItem.find('.o_sign_select_options_display');
                this.display_select_options($options_display, this.select_options, selected_options, readonly, value);
            }
            return $signatureItem.data({type: type['id'], required: required, responsible: responsible, posx: posX, posy: posY, width: width, height: height, name:name, option_ids: option_ids})
                                 .data('hasValue', !!value);
        },

        deleteSignItem: function($item) {
            var pageNo = parseInt($item.parent().prop('id').substr('pageContainer'.length));
            $item.remove();
            for(var i = 0 ; i < this.configuration[pageNo].length ; i++) {
                if(this.configuration[pageNo][i].data('posx') === $item.data('posx') && this.configuration[pageNo][i].data('posy') === $item.data('posy')) {
                    this.configuration[pageNo].splice(i, 1);
                }
            }
        },

        updateSignItem: function($signatureItem) {
            var posX = $signatureItem.data('posx'), posY = $signatureItem.data('posy');
            var width = $signatureItem.data('width'), height = $signatureItem.data('height');

            if(posX < 0) {
                posX = 0;
            } else if(posX+width > 1.0) {
                posX = 1.0-width;
            }
            if(posY < 0) {
                posY = 0;
            } else if(posY+height > 1.0) {
                posY = 1.0-height;
            }

            $signatureItem.data({posx: Math.round(posX*1000)/1000, posy: Math.round(posY*1000)/1000})
                          .css({left: posX*100 + '%', top: posY*100 + '%', width: width*100 + '%', height: height*100 + '%'});

            var resp = $signatureItem.data('responsible');
            $signatureItem.toggleClass('o_sign_sign_item_required', ($signatureItem.data('required') && (this.editMode || resp <= 0 || resp === this.role)))
                          .toggleClass('o_sign_sign_item_pdfview', (this.pdfView || !!$signatureItem.data('hasValue') || (resp !== this.role && resp > 0 && !this.editMode)));
        },

        disableItems: function() {
            this.$('.o_sign_sign_item').addClass('o_sign_sign_item_pdfview').removeClass('ui-selected');
        },

        destroy: function() {
            clearTimeout(this.refresh_timer);
            this._super.apply(this, arguments);
        },
    }));

    return PDFIframe;
});

odoo.define('sign.Document', function (require) {
    'use strict';

    var ajax = require('web.ajax');
    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var PDFIframe = require('sign.PDFIframe');
    var Widget = require('web.Widget');

    var _t = core._t;

    var Document = Widget.extend({
        start: function() {
            this.attachmentLocation = this.$('#o_sign_input_attachment_location').val();
            this.requestID = parseInt(this.$('#o_sign_input_sign_request_id').val());
            this.requestToken = this.$('#o_sign_input_sign_request_token').val();
            this.accessToken = this.$('#o_sign_input_access_token').val();
            this.signerName = this.$('#o_sign_signer_name_input_info').val();
            this.signerPhone = this.$('#o_sign_signer_phone_input_info').val();
            this.RedirectURL = this.$('#o_sign_input_optional_redirect_url').val();
            this.RedirectURLText = this.$('#o_sign_input_optional_redirect_url_text').val();
            this.types = this.$('.o_sign_field_type_input_info');
            this.items = this.$('.o_sign_item_input_info');
            this.select_options = this.$('.o_sign_select_options_input_info');

            this.$validateBanner = this.$('.o_sign_validate_banner').first();

            return Promise.all([this._super.apply(this, arguments), this.initialize_iframe()]);
        },

        get_pdfiframe_class: function () {
            return PDFIframe;
        },

        initialize_iframe: function() {
            this.$iframe = this.$('iframe.o_sign_pdf_iframe').first();
            if(this.$iframe.length > 0 && !this.iframeWidget) {
                this.iframeWidget = new (this.get_pdfiframe_class())(this,
                                                                     this.attachmentLocation,
                                                                     !this.requestID,
                                                                     {
                                                                         types: this.types,
                                                                         signatureItems: this.items,
                                                                         select_options: this.select_options,
                                                                     },
                                                                     parseInt(this.$('#o_sign_input_current_role').val()));
                return this.iframeWidget.attachTo(this.$iframe);
            }
            return Promise.resolve();
        },
    });

    return Document;
});

odoo.define('sign.utils', function (require) {
    'use strict';

    var ajax = require("web.ajax");
    var core = require('web.core');

    var _t = core._t;

    function getSelect2Options(placeholder) {
        return {
            placeholder: placeholder,
            allowClear: false,
            width: '100%',

            formatResult: function(data, resultElem, searchObj) {
                if(!data.text) {
                    $(data.element[0]).data('create_name', searchObj.term);
                    return $("<div/>", {text: _t("Create: \"") + searchObj.term + "\""});
                }
                return $("<div/>", {text: data.text});
            },

            formatSelection: function(data) {
                if(!data.text) {
                    return $("<div/>", {text: $(data.element[0]).data('create_name')}).html();
                }
                return $("<div/>", {text: data.text}).html();
            },

            matcher: function(search, data) {
                if(!data) {
                    return (search.length > 0);
                }
                return (data.toUpperCase().indexOf(search.toUpperCase()) > -1);
            }
        };
    }

    function getOptionsSelectConfiguration(item_id, select_options, selected) {
        if(getOptionsSelectConfiguration.configuration === undefined) {
            var data = [];
            for (var id in select_options) {
                data.push({id: parseInt(id), text: select_options[id].value});
            }
            var select2Options = {
                data: data,
                multiple: true,
                placeholder: _t("Select available options"),
                allowClear: true,
                width: '200px',
                createSearchChoice:function (term, data) {
                    if ($(data).filter(function () { return this.text.localeCompare(term)===0; }).length===0) {
                        return {id:-1, text:term};
                    }
                },
            };

            var selectChangeHandler = function(e) {
                var $select = $(e.target), option = e.added || e.removed;
                $select.data('item_options', $select.select2('val'));
                var option_id = option.id;
                var value = option.text || option.data('create_name');
                if (option_id >= 0 || !value) {
                    return false;
                }
                ajax.rpc('/web/dataset/call_kw/sign.template/add_option', {
                    model: 'sign.template',
                    method: 'add_option',
                    args: [value],
                    kwargs: {}
                }).then(process_option);

                function process_option(optionId) {
                    var option = {id: optionId, value: value};
                    select_options[optionId] = option;
                    selected = $select.select2('val');
                    selected.pop(); // remove temp element (with id=-1)
                    selected.push(optionId.toString());
                    $select.data('item_options', selected);
                    resetOptionsSelectConfiguration();
                    setAsOptionsSelect($select, item_id, selected, select_options);
                    $select.select2('focus');
                }
            };

            getOptionsSelectConfiguration.configuration = {
                options: select2Options,
                handler: selectChangeHandler,
                item_id: item_id,
            };
        }

        return getOptionsSelectConfiguration.configuration;
    }

    function getResponsibleSelectConfiguration(parties) {
        if(getResponsibleSelectConfiguration.configuration === undefined) {
            var select2Options = getSelect2Options(_t("Select the responsible"));

            var selectChangeHandler = function(e) {
                var $select = $(e.target), $option = $(e.added.element[0]);

                var resp = parseInt($option.val());
                var name = $option.text() || $option.data('create_name');

                if(resp >= 0 || !name) {
                    return false;
                }

                ajax.rpc('/web/dataset/call_kw/sign.item.role/add', {
                    model: 'sign.item.role',
                    method: 'add',
                    args: [name],
                    kwargs: {}
                }).then(process_party);

                function process_party(partyID) {
                    parties[partyID] = {id: partyID, name: name};
                    getResponsibleSelectConfiguration.configuration = undefined;
                    setAsResponsibleSelect($select, partyID, parties);
                }
            };

            var $responsibleSelect = $('<select/>').append($('<option/>'));
            for(var id in parties) {
                $responsibleSelect.append($('<option/>', {
                    value: parseInt(id),
                    text: parties[id].name,
                }));
            }
            $responsibleSelect.append($('<option/>', {value: -1}));

            getResponsibleSelectConfiguration.configuration = {
                html: $responsibleSelect.html(),
                options: select2Options,
                handler: selectChangeHandler,
            };
        }

        return getResponsibleSelectConfiguration.configuration;
    }

    function resetResponsibleSelectConfiguration() {
        getResponsibleSelectConfiguration.configuration = undefined;
    }

    function resetOptionsSelectConfiguration() {
        getOptionsSelectConfiguration.configuration = undefined;
    }

    function setAsResponsibleSelect($select, selected, parties) {
        var configuration = getResponsibleSelectConfiguration(parties);
        setAsSelect(configuration, $select, selected);
    }

    function setAsOptionsSelect($select, item_id, selected, select_options) {
        var configuration = getOptionsSelectConfiguration(item_id, select_options, selected);
        setAsSelect(configuration, $select, selected);
    }

    function setAsSelect(configuration, $select, selected) {
        $select.select2('destroy');
        if (configuration.html) {
            $select.html(configuration.html).addClass('form-control');
        }
        $select.select2(configuration.options);
        if(selected !== undefined) {
            $select.select2('val', selected);
        }

        $select.off('change').on('change', configuration.handler);
    }

    return {
        setAsResponsibleSelect: setAsResponsibleSelect,
        resetResponsibleSelectConfiguration: resetResponsibleSelectConfiguration,
        setAsOptionsSelect: setAsOptionsSelect,
        resetOptionsSelectConfiguration: resetOptionsSelectConfiguration,
    };
});

// Signing part
odoo.define('sign.document_signing', function (require) {
    'use strict';

    var ajax = require('web.ajax');
    var config = require('web.config');
    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var Document = require('sign.Document');
    var NameAndSignature = require('web.name_and_signature').NameAndSignature;
    var PDFIframe = require('sign.PDFIframe');
    var session = require('web.session');
    var Widget = require('web.Widget');

    var _t = core._t;

    // The goal of this override is to fetch a default signature if one was
    // already set by the user for this request.
    var SignNameAndSignature = NameAndSignature.extend({

        //----------------------------------------------------------------------
        // Public
        //----------------------------------------------------------------------

        /**
         * Adds requestID and accessToken.
         *
         * @constructor
         * @param {Widget} parent
         * @param {Object} options
         * @param {number} requestID
         * @param {string} accessToken
         */
        init: function (parent, options, requestID, accessToken) {
            this._super.apply(this, arguments);

            this.requestID = requestID;
            this.accessToken = accessToken;

            this.defaultSignature = '';
        },
        /**
         * Fetches the existing signature.
         *
         * @override
         */
        willStart: function () {
            var self = this;
            return Promise.all([
                this._super.apply(this, arguments),
                self._rpc({
                    route: '/sign/get_signature/' + self.requestID + '/' + self.accessToken,
                    params: {
                        signature_type: self.signatureType,
                    },
                }).then(function (signature) {
                    if (signature) {
                        signature = 'data:image/png;base64,' + signature;
                        self.defaultSignature = signature;
                    }
                })
            ]);
        },
        /**
         * Sets the existing signature.
         *
         * @override
         */
        resetSignature: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                if (self.defaultSignature && self.defaultSignature !== self.emptySignature) {
                    self.$signatureField.jSignature("importData", self.defaultSignature);
                    return self._waitForSignatureNotEmpty();
                }
            });
        },
    });

    // The goal of this dialog is to ask the user a signature request.
    // It uses @see SignNameAndSignature for the name and signature fields.
    var SignatureDialog = Dialog.extend({
        template: 'sign.signature_dialog',

        custom_events: {
            'signature_changed': '_onChangeSignature',
        },

        //----------------------------------------------------------------------
        // Public
        //----------------------------------------------------------------------

        /**
         * Allows options.
         *
         * @constructor
         * @param {Widget} parent
         * @param {Object} options
         * @param {string} [options.title='Adopt Your Signature'] - modal title
         * @param {string} [options.size='medium'] - modal size
         * @param {Object} [options.nameAndSignatureOptions={}] - options for
         *  @see NameAndSignature.init()
         * @param {number} requestID
         * @param {string} accessToken
         */
        init: function (parent, options, requestID, accessToken) {
            options = options || {};

            options.title = options.title || _t("Adopt Your Signature");
            options.size = options.size || 'medium';
            options.technical = false;
            if (config.device.isMobile) {
                options.technical = true;
                options.fullscreen = true;
            }

            if (!options.buttons) {
                options.buttons = [];
                options.buttons.push({text: _t("Cancel"), close: true});
                options.buttons.push({text: _t("Adopt and Sign"), classes: "btn-primary", disabled: true, click: function (e) {
                    this.confirmFunction();
                }});
            }

            this._super(parent, options);

            this.confirmFunction = function () {};

            this.nameAndSignature = new SignNameAndSignature(this, options.nameAndSignatureOptions, requestID, accessToken);
        },
        /**
         * Start the nameAndSignature widget and wait for it.
         *
         * @override
         */
            willStart: function () {
                return Promise.all([
                    this.nameAndSignature.appendTo($('<div>')),
                    this._super.apply(this, arguments)
                ]);
            },
        /**
         * Initialize the name and signature widget when the modal is opened.
         *
         * @override
         */
        start: function () {
            var self = this;
            this.$primaryButton = this.$footer.find('.btn-primary');
            this.opened().then(function () {
                self.$('.o_web_sign_name_and_signature').replaceWith(self.nameAndSignature.$el);
                // initialize the signature area
                self.nameAndSignature.resetSignature();
            });
            return this._super.apply(this, arguments);
        },

        onConfirm: function (fct) {
            this.confirmFunction = fct;
        },
        /**
         * Gets the name currently given by the user.
         *
         * @see NameAndSignature.getName()
         * @returns {string} name
         */
        getName: function () {
            return this.nameAndSignature.getName();
        },
        /**
         * Gets the signature currently drawn.
         *
         * @see NameAndSignature.getSignatureImage()
         * @returns {string[]} Array that contains the signature as a bitmap.
         *  The first element is the mimetype, the second element is the data.
         */
        getSignatureImage: function () {
            return this.nameAndSignature.getSignatureImage();
        },
        /**
         * Gets the signature currently drawn, in a format ready to be used in
         * an <img/> src attribute.
         *
         * @see NameAndSignature.getSignatureImageSrc()
         * @returns {string} the signature currently drawn, src ready
         */
        getSignatureImageSrc: function () {
            return this.nameAndSignature.getSignatureImageSrc();
        },
        /**
         * Returns whether the drawing area is currently empty.
         *
         * @see NameAndSignature.isSignatureEmpty()
         * @returns {boolean} Whether the drawing area is currently empty.
         */
        isSignatureEmpty: function () {
            return this.nameAndSignature.isSignatureEmpty();
        },
        /**
         * Gets the current name and signature, validates them, and
         * returns the result. If they are invalid, it also displays the
         * errors to the user.
         *
         * @see NameAndSignature.validateSignature()
         * @returns {boolean} whether the current name and signature are valid
         */
        validateSignature: function () {
            return this.nameAndSignature.validateSignature();
        },

        //----------------------------------------------------------------------
        // Handlers
        //----------------------------------------------------------------------

        /**
         * Toggles the submit button depending on the signature state.
         *
         * @private
         */
        _onChangeSignature: function () {
            var isEmpty = this.nameAndSignature.isSignatureEmpty();
            this.$primaryButton.prop('disabled', isEmpty);
        },
        /**
         * @override
         */
        renderElement: function () {
            this._super.apply(this, arguments);
             // this trigger the adding of a custom css
             this.$modal.addClass('o_sign_signature_dialog');
         },
    });

    var SignItemNavigator = Widget.extend({
        className: 'o_sign_sign_item_navigator',

        events: {
            'click': 'onClick'
        },

        init: function(parent, types) {
            this._super(parent);

            this.types = types;
            this.started = false;
            this.isScrolling = false;
        },

        start: function() {
            this.$signatureItemNavLine = $('<div/>').addClass("o_sign_sign_item_navline").insertBefore(this.$el);
            this.setTip(_t("Click to start"));
            this.$el.focus();

            return this._super();
        },

        setTip: function(tip) {
            this.$el.text(tip);
        },

        onClick: function(e) {
            var self = this;

            if(!self.started) {
                self.started = true;

                self.getParent().$iframe.prev().animate({'height': '0px', 'opacity': 0}, {
                    duration: 750,
                    complete: function() {
                        self.getParent().$iframe.prev().hide();
                        self.getParent().refreshSignItems();

                        self.onClick();
                    }
                });

                return false;
            }

            var $toComplete = self.getParent().checkSignItemsCompletion().sort(function(a, b) {
                return ($(a).data('order') || 0) - ($(b).data('order') || 0);
            });
            if($toComplete.length > 0) {
                self.scrollToSignItem($toComplete.first());
            }
        },

        scrollToSignItem: function($item) {
            var self = this;
            if(!this.started) {
                return;
            }
            this._scrollToSignItemPromise($item).then(function () {
                const type = self.types[$item.data('type')];
                if($item.val() === "" && !$item.data('signature')) {
                    self.setTip(type.tip);
                }

                self.getParent().refreshSignItems();
                $item.focus();
                if (['signature', 'initial'].indexOf(type.item_type) > -1) {
                    if($item.data("has-focus")) {
                        $item.click();
                    } else {
                        $item.data("has-focus", true);
                    }
                }
                self.isScrolling = false;
            });

            this.getParent().$('.ui-selected').removeClass('ui-selected');
            $item.addClass('ui-selected').focus();
        },

        _scrollToSignItemPromise($item) {
            if (config.device.isMobile) {
                return new Promise(resolve => {
                    this.isScrolling = true;
                    $item[0].scrollIntoView({behavior: 'smooth', block: 'center', inline: 'center'});
                    resolve();
                });
            }

            var $container = this.getParent().$('#viewerContainer');
            var $viewer = $container.find('#viewer');
            var containerHeight = $container.outerHeight();
            var viewerHeight = $viewer.outerHeight();

            var scrollOffset = containerHeight/4;
            var scrollTop = $item.offset().top - $viewer.offset().top - scrollOffset;
            if(scrollTop + containerHeight > viewerHeight) {
                scrollOffset += scrollTop + containerHeight - viewerHeight;
            }
            if(scrollTop < 0) {
                scrollOffset += scrollTop;
            }
            scrollOffset += $container.offset().top - this.$el.outerHeight()/2 + parseInt($item.css('height'))/2;

            var duration = Math.min(
                1000,
                5*(Math.abs($container[0].scrollTop - scrollTop) + Math.abs(parseFloat(this.$el.css('top')) - scrollOffset))
            );

            var self = this;
            this.isScrolling = true;
            var def1 = new Promise(function (resolve, reject) {
                $container.animate({'scrollTop': scrollTop}, duration, function() {
                    resolve();
                });
            });
            var def2 = new Promise(function (resolve, reject) {
                self.$el.add(self.$signatureItemNavLine).animate({'top': scrollOffset}, duration, function() {
                    resolve();
                });
            });
            return Promise.all([def1, def2]);
        },
    });

    var PublicSignerDialog = Dialog.extend({
        template: "sign.public_signer_dialog",

        init: function(parent, requestID, requestToken, RedirectURL, options) {
            var self = this;
            options = (options || {});

            options.title = options.title || _t("Final Validation");
            options.size = options.size || "medium";
            options.technical = false;

            if (config.device.isMobile) {
                options.technical = true;
                options.fullscreen = true;
            }

            if(!options.buttons) {
                options.buttons = [];
                options.buttons.push({text: _t("Validate & Send"), classes: "btn-primary", click: function(e) {
                    var name = this.$inputs.eq(0).val();
                    var mail = this.$inputs.eq(1).val();
                    if(!name || !mail || mail.indexOf('@') < 0) {
                        this.$inputs.eq(0).closest('.form-group').toggleClass('o_has_error', !name).find('.form-control, .custom-select').toggleClass('is-invalid', !name);
                        this.$inputs.eq(1).closest('.form-group').toggleClass('o_has_error', !mail || mail.indexOf('@') < 0).find('.form-control, .custom-select').toggleClass('is-invalid', !mail || mail.indexOf('@') < 0);
                        return false;
                    }

                    ajax.jsonRpc("/sign/send_public/" + this.requestID + '/' + this.requestToken, 'call', {
                        name: name,
                        mail: mail,
                    }).then(function() {
                        self.close();
                        self.sentResolve();
                    });
                }});
                options.buttons.push({text: _t("Cancel"), close: true});
            }

            this._super(parent, options);

            this.requestID = requestID;
            this.requestToken = requestToken;
            this.sentResolve;
            this.sent = new Promise(function(resolve) {
                self.sentResolve = resolve;
            });
        },

        open: function(name, mail) {
            var self = this;
            this.opened(function() {
                self.$inputs = self.$('input');
                self.$inputs.eq(0).val(name);
                self.$inputs.eq(1).val(mail);
            });
            return this._super.apply(this, arguments);
        },
    });

    var SMSSignerDialog = Dialog.extend({
        template: "sign.public_sms_signer",

        events: {
            'click button.o_sign_resend_sms': function(e) {
                var $btn = self.$('.o_sign_resend_sms');
                $btn.attr('disabled', true)
                var route = '/sign/send-sms/' + this.requestID + '/' + this.requestToken + '/' + this.$('#o_sign_phone_number_input').val();
                session.rpc(route, {}).then(function(success) {
                    if (!success) {
                        Dialog.alert(self, _t("Unable to send the SMS, please contact the sender of the document."), {
                            title: _t("Error"),
                        });
                    }
                    else {
                        $btn.html("<span><i class='fa fa-check'/> "+_t("SMS Sent")+"</span>");
                        setTimeout(function() {
                            $btn.removeAttr('disabled');
                            $btn.text(_t('Re-send SMS'));
                        }, 15000);
                    }
                }).guardedCatch(function (error) {
                    $btn.removeAttr('disabled');
                    Dialog.alert(self, _t("Unable to send the SMS, please contact the sender of the document."), {
                        title: _t("Error"),
                    });
                });;
            }
        },

        _onValidateSMS: function () {
            var $btn = this.$('.o_sign_validate_sms');
            var input = this.$('#o_sign_public_signer_sms_input')
            if(!input.val()) {
                input.closest('.form-group').toggleClass('o_has_error').find('.form-control, .custom-select').toggleClass('is-invalid');
                return false;
            }
            var route = '/sign/sign/' + this.requestID + '/' + this.requestToken + '/' + input.val();
            var params = {
                signature: this.signature
            };
            var self = this;
            $btn.attr('disabled', true);
            session.rpc(route, params).then(function(response) {
                if (!response) {
                    Dialog.alert(self, _t("Your signature was not submitted. Ensure that all required field of the documents are completed and that the SMS validation code is correct."), {
                        title: _t("Error"),
                    });
                    $btn.removeAttr('disabled');
                }
                if (response === true) {
                    (new (self.get_thankyoudialog_class())(self, self.RedirectURL, self.RedirectURLText, self.requestID)).open();
                    self.do_hide();
                }
                if (typeof response === 'object') {
                    if (response.url) {
                        document.location.pathname = success['url'];
                    }
                }
            });
        },

        get_thankyoudialog_class: function () {
            return ThankYouDialog;
        },

        init: function(parent, requestID, requestToken, signature, signerPhone, RedirectURL, options) {
            options = (options || {});
            if (config.device.isMobile) {
                options.fullscreen = true;
            }
            options.title = options.title || _t("Final Validation");
            options.size = options.size || "medium";
            if(!options.buttons) {
                options.buttons = [{
                    text: _t("Verify"),
                    classes: "btn btn-primary o_sign_validate_sms",
                    click: this._onValidateSMS
                }]
            }
            this._super(parent, options);
            this.requestID = requestID;
            this.requestToken = requestToken;
            this.signature = signature;
            this.signerPhone = signerPhone;
            this.RedirectURL = RedirectURL;
            this.sent = $.Deferred();
        },
    });

    var EncryptedDialog = Dialog.extend({
        template: "sign.public_password",

        _onValidatePassword: function () {
            var input = this.$('#o_sign_public_signer_password_input')
            if(!input.val()) {
                input.closest('.form-group').toggleClass('o_has_error').find('.form-control, .custom-select').toggleClass('is-invalid');
                return false;
            }
            var route = '/sign/password/' + this.requestID ;
            var params = {
                password: input.val()
            };
            var self = this;
            session.rpc(route, params).then(function(response) {
                if (!response) {
                    Dialog.alert(self, _t("Password is incorrect."), {
                        title: _t("Error"),
                    });
                }
                if (response === true) {
                    self.close();
                }
            });
        },

        init: function(parent, requestID, options) {
            options = (options || {});
            if (config.device.isMobile) {
                options.fullscreen = true;
            }
            options.title = options.title || _t("PDF is encrypted");
            options.size = options.size || "medium";
            if(!options.buttons) {
                options.buttons = [{
                    text: _t("Generate PDF"),
                    classes: "btn btn-primary o_sign_validate_encrypted",
                    click: this._onValidatePassword
                }]
            }
            this._super(parent, options);
            this.requestID = requestID;
        },

        /**
         * @override
         */
        renderElement: function () {
            this._super.apply(this, arguments);
            this.$modal.find('button.close').addClass('invisible')
        },
    });

    var ThankYouDialog = Dialog.extend({
        template: "sign.thank_you_dialog",
        events: {
            'click .o_go_to_document': 'on_closed',
        },

        get_passworddialog_class: function () {
            return EncryptedDialog;
        },

        init: function(parent, RedirectURL, RedirectURLText, requestID, options) {
            var self = this;
            options = (options || {});
            options.title = options.title || _t("Thank You !");
            options.subtitle = options.subtitle || _t("Your signature has been saved.");
            options.size = options.size || "medium";
            options.technical = false;
            options.buttons = [];
            if (RedirectURL) {
                // check if url contains http:// or https://
                if (!/^(f|ht)tps?:\/\//i.test(RedirectURL)) {
                RedirectURL = "http://" + RedirectURL;
             }
            options.buttons.push({text: _t(RedirectURLText), classes: 'btn-primary', click: function (e) {
                window.location.replace(RedirectURL);
                }});
            }

            // If sign now: do_action to return to templates
            // If request sent by mail: reload the document
            var ButtonName = "";
            if (! session.uid) {
                ButtonName = "View Signed Document";
                var NextAction = function() {
                window.location.reload();
                };
                } else {
                    ButtonName = "Return to templates";
                    var NextAction = function() {
                        return self.do_action('sign.sign_template_action', {
                            clear_breadcrumbs: true
                            });
                        };
                }

            options.buttons.push({text: _t(ButtonName), classes: 'btn-primary', close: true, click: function (e) {
                new NextAction();
            }});
            this.RedirectURL = RedirectURL;
            this.requestID = requestID;
            this._super(parent, options);

            this.on('closed', this, this.on_closed);

            var self = this;
            this._rpc({
                route: '/sign/encrypted/' + requestID
            }).then(function (response) {
                if (response === true) {
                    (new (self.get_passworddialog_class())(self, requestID)).open();
                }
            });
        },

        /**
         * @override
         */
        renderElement: function () {
            this._super.apply(this, arguments);
            // this trigger the adding of a custom css
            this.$modal.addClass('o_sign_thank_you_dialog');
            this.$modal.find('button.close').addClass('invisible');
            this.$modal.find('.modal-header .o_subtitle').before('<br/>');
        },

        on_closed: function () {
            window.location.reload();
        },
    });

    var NextDirectSignDialog = Dialog.extend({
        template: "sign.next_direct_sign_dialog",
        events: {
            'click .o_go_to_document': 'on_closed',
            'click .o_nextdirectsign_link': 'on_click_next',
        },

        init: function(parent, RedirectURL, requestID, options) {
            this.token_list = (parent.token_list || {});
            this.name_list = (parent.name_list || {});
            this.requestID = parent.requestID;
            this.create_uid = parent.create_uid;
            this.state = parent.state;

            options = (options || {});
            options.title = options.title || _t("Thank You !") + "<br/>";
            options.subtitle = options.subtitle || _t("Your signature has been saved.") + " " +_.str.sprintf(_t("Next signatory is %s"), this.name_list[0]);
            options.size = options.size || "medium";
            options.technical = false;
            if (config.device.isMobile) {
                options.technical = true;
                options.fullscreen = true;
            }
            options.buttons = [{text: _.str.sprintf(_t("Next signatory (%s)"), this.name_list[0]), click: this.on_click_next}],
            this.RedirectURL = "RedirectURL";
            this.requestID = requestID;
            this._super(parent, options);
        },

        /**
         * @override
         */
        renderElement: function () {
            this._super.apply(this, arguments);
            this.$modal.addClass('o_sign_next_dialog');
            this.$modal.find('button.close').addClass('invisible');
        },

        on_click_next: function () {

            var newCurrentToken = this.token_list[0];
            var newCurrentName = this.name_list[0];
            var self = this;
            this.token_list.shift();
            this.name_list.shift();

            self.do_action({
                type: "ir.actions.client",
                tag: 'sign.SignableDocument',
                name: _t("Sign"),
            }, {
                additional_context: {
                    id: this.requestID,
                    create_uid: this.create_uid,
                    state: this.state,
                    token: newCurrentToken,
                    sign_token: newCurrentToken,
                    token_list: this.token_list,
                    name_list: this.name_list,
                    current_signor_name: newCurrentName,
                },
                replace_last_action: true,
            });

            this.destroy();
        },
    });

    var SignablePDFIframe = PDFIframe.extend({
        init: function() {
            this._super.apply(this, arguments);

            this.events = _.extend(this.events || {}, {
                'keydown .page .ui-selected': function(e) {
                    if((e.keyCode || e.which) !== 13) {
                        return true;
                    }
                    e.preventDefault();
                    this.signatureItemNav.onClick();
                },
            });
        },

        doPDFPostLoad: function() {
            var self = this;
            this.fullyLoaded.then(function() {
                self.signatureItemNav = new SignItemNavigator(self, self.types);
                return self.signatureItemNav.prependTo(self.$('#viewerContainer')).then(function () {

                    self.checkSignItemsCompletion();

                    self.$('#viewerContainer').on('scroll', function(e) {
                        if(!self.signatureItemNav.isScrolling && self.signatureItemNav.started) {
                            self.signatureItemNav.setTip(_t('next'));
                        }
                    });
                });
            });

            this._super.apply(this, arguments);
        },

        createSignItem: function(type, required, responsible, posX, posY, width, height, value, options, name) {
            // jQuery.data parse 0 as integer, but 0 is not considered falsy for signature item
            if (value === 0) {
                value = "0";
            }
            var self = this;
            var $signatureItem = this._super.apply(this, arguments);
            var readonly = this.readonlyFields || (responsible > 0 && responsible !== this.role) || !!value;
            if(!readonly) {
                // Do not display the placeholder of Text and Multiline Text if the name of the item is the default one.
                if ( type['name'].includes('Text') && type['placeholder'] === $signatureItem.prop('placeholder')) {
                    $signatureItem.attr('placeholder', ' ');
                    $signatureItem.find(".o_placeholder").text(" ");
                 }
                if (type['item_type'] === "signature" || type['item_type'] === "initial") {
                    $signatureItem.on('click', function(e) {
                        self.refreshSignItems();
                        var $signedItems = self.$('.o_sign_sign_item').filter(function(i) {
                            var $item = $(this);
                            return ($item.data('type') === type['id']
                                        && $item.data('signature') && $item.data('signature') !== $signatureItem.data('signature')
                                        && ($item.data('responsible') <= 0 || $item.data('responsible') === $signatureItem.data('responsible')));
                        });

                        if($signedItems.length > 0) {
                            $signatureItem.data('signature', $signedItems.first().data('signature'));
                            $signatureItem.html('<span class="o_sign_helper"/><img src="' + $signatureItem.data('signature') + '"/>');
                            $signatureItem.trigger('input');
                        } else {
                            var nameAndSignatureOptions = {
                                defaultName: self.getParent().signerName || "",
                                signatureType: type['item_type'],
                                displaySignatureRatio: parseFloat($signatureItem.css('width')) / parseFloat($signatureItem.css('height')),
                            };
                            var signDialog = new SignatureDialog(self, {nameAndSignatureOptions: nameAndSignatureOptions}, self.getParent().requestID, self.getParent().accessToken);

                            signDialog.open().onConfirm(function () {
                                if (!signDialog.isSignatureEmpty()) {
                                    var name = signDialog.getName();
                                    var signature = signDialog.getSignatureImageSrc();
                                    self.getParent().signerName = name;
                                    $signatureItem.data('signature', signature)
                                                  .empty()
                                                  .append($('<span/>').addClass("o_sign_helper"), $('<img/>', {src: $signatureItem.data('signature')}));
                                } else {
                                    $signatureItem.removeData('signature')
                                                  .empty()
                                                  .append($('<span/>').addClass("o_sign_helper"), type['placeholder']);
                                }

                                $signatureItem.trigger('input').focus();
                                signDialog.close();
                            });
                        }
                    });
                }

                if(type['auto_field']) {
                    $signatureItem.on('focus', function(e) {
                        if($signatureItem.val() === "") {
                            $signatureItem.val(type['auto_field']);
                            $signatureItem.trigger('input');
                        }
                    });
                }

                $signatureItem.on('input', function(e) {
                    self.checkSignItemsCompletion(self.role);
                    self.signatureItemNav.setTip(_t('next'));
                });
            } else {
                $signatureItem.val(value);
            }
            return $signatureItem;
        },

        checkSignItemsCompletion: function() {
            this.refreshSignItems();
            var $toComplete = this.$('.o_sign_sign_item.o_sign_sign_item_required:not(.o_sign_sign_item_pdfview)').filter(function(i, el) {
                var $elem = $(el);
                var unchecked_box = $elem.val() == 'on' && !$elem.is(":checked")
                return !(($elem.val() && $elem.val().trim()) || $elem.data('signature')) || unchecked_box;
            });

            this.signatureItemNav.$el.add(this.signatureItemNav.$signatureItemNavLine).toggle($toComplete.length > 0);
            this.$iframe.trigger(($toComplete.length > 0)? 'pdfToComplete' : 'pdfCompleted');

            return $toComplete;
        },
    });

    var SignableDocument = Document.extend({
        events: {
            'pdfToComplete .o_sign_pdf_iframe': function(e) {
                this.$validateBanner.hide().css('opacity', 0);
            },

            'pdfCompleted .o_sign_pdf_iframe': function(e) {
                if (this.name_list && this.name_list.length > 0) {
                    var next_name_signatory = this.name_list[0];
                    var next_signatory = _.str.sprintf(_t("Validate & the next signatory is %s"), next_name_signatory);
                    this.$validateBanner.find('.o_validate_button').prop('textContent', next_signatory);
                }
                this.$validateBanner.show().animate({'opacity': 1}, 500, () => {
                    if (config.device.isMobile) {
                        this.$validateBanner[0].scrollIntoView({behavior: 'smooth', block: 'center', inline: 'center'});
                    }
                });
            },

            'click .o_sign_validate_banner button': 'signItemDocument',
            'click .o_sign_sign_document_button': 'signDocument',
        },

        custom_events: { // do_notify is not supported in backend so it is simulated with a bootstrap alert inserted in a frontend-only DOM element
            'notification': function (e) {
                $('<div/>', {html: e.data.message}).addClass('alert alert-success').insertAfter(self.$('.o_sign_request_reference_title'));
            },
        },

        init: function (parent, options) {
            this._super(parent, options);
            if (parent) {
                this.token_list = (parent.token_list || {});
                this.name_list = (parent.name_list || {});
                this.create_uid = parent.create_uid;
                this.state = parent.state;
                this.current_name = parent.current_name;
            }

            if (this.current_name) {
                parent.$('div.container-fluid .col-lg-6').first().removeClass('col-lg-6').addClass('col-lg-4')
                parent.$('div.container-fluid .col-lg-4').first().after('<div class="col-lg-4"><div class="o_sign_request_from text-center"><h2>'+this.current_name+'</h2></div></div>')
                parent.$('div.container-fluid .col-lg-6').first().removeClass('col-lg-6').addClass('col-lg-4')
            }
        },
        get_pdfiframe_class: function () {
            return SignablePDFIframe;
        },

        get_thankyoudialog_class: function () {
            return ThankYouDialog;
        },

        get_nextdirectsigndialog_class: function () {
            return NextDirectSignDialog;
        },

        signItemDocument: function(e) {
            var $btn = this.$('.o_sign_validate_banner button');
            var init_btn_text = $btn.text();
            $btn.prepend('<i class="fa fa-spin fa-spinner" />');
            $btn.attr('disabled', true);
            var mail = "";
            this.iframeWidget.$('.o_sign_sign_item').each(function(i, el) {
                var value = $(el).val();
                if(value && value.indexOf('@') >= 0) {
                    mail = value;
                }
            });

            if(this.$('#o_sign_is_public_user').length > 0) {
                (new PublicSignerDialog(this, this.requestID, this.requestToken, this.RedirectURL))
                    .open(this.signerName, mail).sent.then(_.bind(_sign, this));
            } else {
                _sign.call(this);
            }

            function _sign() {
                var signatureValues = {};
                for(var page in this.iframeWidget.configuration) {
                    for(var i = 0 ; i < this.iframeWidget.configuration[page].length ; i++) {
                        var $elem = this.iframeWidget.configuration[page][i];
                        var resp = parseInt($elem.data('responsible')) || 0;
                        if(resp > 0 && resp !== this.iframeWidget.role) {
                            continue;
                        }
                        var value = ($elem.val() && $elem.val().trim())? $elem.val() : false;
                        if($elem.data('signature')) {
                            value = $elem.data('signature');
                        }
                        if($elem[0].type === 'checkbox') {
                            value = false ;
                            if ($elem[0].checked) {
                                value = 'on';
                            } else {
                                if (!$elem.data('required')) value = 'off';
                            }
                        } else if($elem[0].type === 'textarea') {
                            value = this.textareaApplyLineBreak($elem[0]);
                        }
                        if(!value) {
                            if($elem.data('required')) {
                                this.iframeWidget.checkSignItemsCompletion();
                                Dialog.alert(this, _t("Some fields have still to be completed !"), {title: _t("Warning")});
                                return;
                            }
                            continue;
                        }

                        signatureValues[parseInt($elem.data('item-id'))] = value;
                    }
                }
                var route = '/sign/sign/' + this.requestID + '/' + this.accessToken;
                var params = {
                    signature: signatureValues
                };
                var self = this;
                session.rpc(route, params).then(function(response) {
                    $btn.text(init_btn_text);
                    if (!response) {
                        Dialog.alert(self, _t("Sorry, an error occured, please try to fill the document again."), {
                            title: _t("Error"),
                            confirm_callback: function() {
                                window.location.reload();
                            },
                        });
                    }
                    if (response === true) {
                        $btn.removeAttr('disabled', true);
                        self.iframeWidget.disableItems();
                        if (self.name_list && self.name_list.length > 0) {
                            (new (self.get_nextdirectsigndialog_class())(self, self.RedirectURL, self.requestID)).open();
                        }
                        else {
                            (new (self.get_thankyoudialog_class())(self, self.RedirectURL, self.RedirectURLText, self.requestID)).open();
                        }
                    }
                    if (typeof response === 'object') {
                        $btn.removeAttr('disabled', true);
                        if (response.sms) {
                            (new SMSSignerDialog(self, self.requestID, self.accessToken, signatureValues, self.signerPhone, self.RedirectURL))
                                .open();
                        }
                        if (response.credit_error) {
                            Dialog.alert(self, _t("Unable to send the SMS, please contact the sender of the document."), {
                                title: _t("Error"),
                                confirm_callback: function() {
                                    window.location.reload();
                                },
                            });
                        }
                        if (response.url) {
                            document.location.pathname = response['url'];
                        }
                    }
                });
            }
        },

        signDocument: function (e) {
            var self = this;

            var nameAndSignatureOptions = {defaultName: this.signerName};
            var options = {nameAndSignatureOptions: nameAndSignatureOptions};
            var signDialog = new SignatureDialog(this, options, self.requestID, self.accessToken);

            signDialog.open().onConfirm(function () {
                if (!signDialog.validateSignature()) {
                    return false;
                }

                var name = signDialog.getName();
                var signature = signDialog.getSignatureImage()[1];

                signDialog.$('.modal-footer .btn-primary').prop('disabled', true);
                signDialog.close();

                if (self.$('#o_sign_is_public_user').length > 0) {
                    (new PublicSignerDialog(self, self.requestID, self.requestToken, this.RedirectURL))
                        .open(name, "").sent.then(_sign);
                } else {
                    _sign();
                }

                function _sign() {
                    ajax.jsonRpc('/sign/sign/' + self.requestID + '/' + self.accessToken, 'call', {
                        signature: signature,
                    }).then(function(success) {
                        if(!success) {
                            setTimeout(function() { // To be sure this dialog opens after the thank you dialog below
                                Dialog.alert(self, _t("Sorry, an error occured, please try to fill the document again."), {
                                    title: _t("Error"),
                                    confirm_callback: function() {
                                        window.location.reload();
                                    },
                                });
                            }, 500);
                        }
                    });
                    (new (self.get_thankyoudialog_class())(self, self.RedirectURL, self.RedirectURLText, self.requestID)).open();
                }
            });
        },

        textareaApplyLineBreak: function (oTextarea) {
            // Removing wrap in order to have scrollWidth > width
            oTextarea.setAttribute('wrap', 'off');

            var strRawValue = oTextarea.value;
            oTextarea.value = "";

            var nEmptyWidth = oTextarea.scrollWidth;
            var nLastWrappingIndex = -1;

            // Computing new lines
            for (var i = 0; i < strRawValue.length; i++) {
                var curChar = strRawValue.charAt(i);
                oTextarea.value += curChar;

                if (curChar === ' ' || curChar === '-' || curChar === '+') {
                    nLastWrappingIndex = i;
                }

                if (oTextarea.scrollWidth > nEmptyWidth) {
                    var buffer = '';
                    if (nLastWrappingIndex >= 0) {
                        for (var j = nLastWrappingIndex + 1; j < i; j++) {
                            buffer += strRawValue.charAt(j);
                        }
                        nLastWrappingIndex = -1;
                    }
                    buffer += curChar;
                    oTextarea.value = oTextarea.value.substr(0, oTextarea.value.length - buffer.length);
                    oTextarea.value += '\n' + buffer;
                }
            }
            oTextarea.setAttribute('wrap', '');
            return oTextarea.value;
        }
    });

    function initDocumentToSign(parent) {
        return session.session_bind(session.origin).then(function () {
            // Manually add 'sign' to module list and load the
            // translations.
            session.module_list.push('sign');
            return session.load_translations().then(function () {
                var documentPage = new SignableDocument(parent);
                return documentPage.attachTo($('body')).then(function() {
                    // Geolocation
                    var askLocation = ($('#o_sign_ask_location_input').length > 0);
                    if(askLocation && navigator.geolocation) {
                        navigator.geolocation.getCurrentPosition(function(position) {
                            var coords = _.pick(position.coords, ['latitude', 'longitude']);
                            ajax.jsonRpc('/sign/save_location/' + documentPage.requestID + '/' + documentPage.accessToken, 'call', coords);
                        });
                    }
                });
            });
        });
    }

    return {
        EncryptedDialog: EncryptedDialog,
        ThankYouDialog: ThankYouDialog,
        initDocumentToSign: initDocumentToSign,
        SignableDocument: SignableDocument,
        SignNameAndSignature: SignNameAndSignature,
        SMSSignerDialog: SMSSignerDialog,
    };
});
