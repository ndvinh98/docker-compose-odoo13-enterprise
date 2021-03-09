odoo.define('pos_blackbox_be.pos_blackbox_be', function (require) {
    var core    = require('web.core');
    var screens = require('point_of_sale.screens');
    var models = require('point_of_sale.models');
    var devices = require('point_of_sale.devices');
    var chrome = require('point_of_sale.chrome');
    var gui = require('point_of_sale.gui');
    var DB = require('point_of_sale.DB');
    var popups = require('point_of_sale.popups');
    var Class = require('web.Class');
    var utils = require('web.utils');
    var PosBaseWidget = require('point_of_sale.BaseWidget');
    var SplitbillScreenWidget = require('pos_restaurant.splitbill').SplitbillScreenWidget;
    var floors = require('pos_restaurant.floors');
    var rpc = require('web.rpc');

    var _t      = core._t;
    var round_pr = utils.round_precision;
    var QWeb = core.qweb;

    var orderline_super = models.Orderline.prototype;
    models.Orderline = models.Orderline.extend({
        // Let the user set the quantity of product with UOM different of unit because we can't reduce it without negative quantity.
        initialize: function(attr,options){
            orderline_super.initialize.apply(this, arguments);
            if(this.pos.config.blackbox_pos_production_id) {
                var self = this;
                if(this.product.uom_id[1] !== "Units") {
                    this.pos.gui.show_popup("number", {
                        'title': _t("Set the quantity by"),
                        'confirm': function (qty) {
                            if (qty)
                                self.set_quantity(qty);
                        }
                    });
                }
            }
        },
        // generates a table of the form
        // {..., 'char_to_translate': translation_of_char, ...}
        _generate_translation_table: function () {
            var replacements = [
                ["ÄÅÂÁÀâäáàã", "A"],
                ["Ææ", "AE"],
                ["ß", "SS"],
                ["çÇ", "C"],
                ["ÎÏÍÌïîìí", "I"],
                ["€", "E"],
                ["ÊËÉÈêëéè", "E"],
                ["ÛÜÚÙüûúù", "U"],
                ["ÔÖÓÒöôóò", "O"],
                ["Œœ", "OE"],
                ["ñÑ", "N"],
                ["ýÝÿ", "Y"]
            ];

            var lowercase_to_uppercase = _.range("a".charCodeAt(0), "z".charCodeAt(0) + 1).map(function (lowercase_ascii_code) {
                return [String.fromCharCode(lowercase_ascii_code), String.fromCharCode(lowercase_ascii_code).toUpperCase()];
            });
            replacements = replacements.concat(lowercase_to_uppercase);

            var lookup_table = {};

            _.forEach(replacements, function (letter_group) {
                _.forEach(letter_group[0], function (special_char) {
                    lookup_table[special_char] = letter_group[1];
                });
            });

            return lookup_table;
        },

        _replace_hash_and_sign_chars: function (str) {
            if (typeof str !== 'string') {
                throw "Can only handle strings";
            }

            var translation_table = this._generate_translation_table();

            var replaced_char_array = _.map(str, function (char, index, str) {
                var translation = translation_table[char];
                if (translation) {
                    return translation;
                } else {
                    return char;
                }
            });

            return replaced_char_array.join("");
        },

        // for hash and sign the allowed range for DATA is:
        //   - A-Z
        //   - 0-9
        // and SPACE as well. We filter SPACE out here though, because
        // SPACE will only be used in DATA of hash and sign as description
        // padding
        _filter_allowed_hash_and_sign_chars: function (str) {
            if (typeof str !== 'string') {
                throw "Can only handle strings";
            }

            var filtered_char_array = _.filter(str, function (char) {
                var ascii_code = char.charCodeAt(0);

                if ((ascii_code >= "A".charCodeAt(0) && ascii_code <= "Z".charCodeAt(0)) ||
                    (ascii_code >= "0".charCodeAt(0) && ascii_code <= "9".charCodeAt(0))) {
                    return true;
                } else {
                    return false;
                }
            });

            return filtered_char_array.join("");
        },

        // for both amount and price
        // price should be in eurocent
        // amount should be in gram
        _prepare_number_for_plu: function (number, field_length) {
            number = Math.abs(number);
            number = Math.round(number); // todo jov: don't like this

            var number_string = number.toFixed(0);

            number_string = this._replace_hash_and_sign_chars(number_string);
            number_string = this._filter_allowed_hash_and_sign_chars(number_string);

            // get the required amount of least significant characters
            number_string = number_string.substr(-field_length);

            // pad left with 0 to required size
            while (number_string.length < field_length) {
                number_string = "0" + number_string;
            }

            return number_string;
        },

        _prepare_description_for_plu: function (description) {
            description = this._replace_hash_and_sign_chars(description);
            description = this._filter_allowed_hash_and_sign_chars(description);

            // get the 20 most significant characters
            description = description.substr(0, 20);

            // pad right with SPACE to required size of 20
            while (description.length < 20) {
                description = description + " ";
            }

            return description;
        },

        _get_amount_for_plu: function () {
            // three options:
            // 1. unit => need integer
            // 2. weight => need integer gram
            // 3. volume => need integer milliliter

            var amount = this.get_quantity();
            var uom = this.get_unit();

            if (uom.is_unit) {
                return amount;
            } else {
                if (uom.category_id[1] === "Weight") {
                    var uom_gram = _.find(this.pos.units_by_id, function (unit) {
                        return unit.category_id[1] === "Weight" && unit.name === "g";
                    });
                    amount = (amount / uom.factor) * uom_gram.factor;
                } else if (uom.category_id[1] === "Volume") {
                    var uom_milliliter = _.find(this.pos.units_by_id, function (unit) {
                        return unit.category_id[1] === "Volume" && unit.name === "Milliliter(s)";
                    });
                    amount = (amount / uom.factor) * uom_milliliter.factor;
                }

                return amount;
            }
        },

       get_vat_letter: function () {
            if(this.pos.config.blackbox_pos_production_id) {
                var taxes = this.get_taxes()[0];
                taxes = this._map_tax_fiscal_position(taxes);
                var line_name = this.get_product().display_name;

                 if (!taxes) {
                    if (this.pos.gui.popup_instances.error) {
                        this.pos.gui.show_popup("error", {
                            'title': _t("POS error"),
                            'body': _t("Product has no tax associated with it."),
                        });

                         return false;
                    }
                }

                var vat_letter = taxes[0].identification_letter;
                if (!vat_letter) {
                    if (this.pos.gui.popup_instances.error) {
                        this.pos.gui.show_popup("error", {
                            'title': _t("POS error"),
                            'body': _t("Product has an invalid tax amount. Only 21%, 12%, 6% and 0% are allowed."),
                        });

                        return false;
                    }
                }
            }

         return vat_letter;
    },

        generate_plu_line: function () {
            // |--------+-------------+-------+-----|
            // | AMOUNT | DESCRIPTION | PRICE | VAT |
            // |      4 |          20 |     8 |   1 |
            // |--------+-------------+-------+-----|

            // steps:
            // 1. replace all chars
            // 2. filter out forbidden chars
            // 3. build PLU line

            var amount = this._get_amount_for_plu();
            var description = this.get_product().display_name;
            var price_in_eurocent = this.get_display_price() * 100;
            var vat_letter = this.get_vat_letter();

            amount = this._prepare_number_for_plu(amount, 4);
            description = this._prepare_description_for_plu(description);
            price_in_eurocent = this._prepare_number_for_plu(price_in_eurocent, 8);

            return amount + description + price_in_eurocent + vat_letter;
        },
        can_be_merged_with: function(orderline) {
            var res = orderline_super.can_be_merged_with.apply(this, arguments);
            if(this.pos.config.blackbox_pos_production_id && this.blackbox_pro_forma_finalized || this.quantity < 0)
                return false;
            return res;
        },

        _show_finalized_error: function () {
            this.pos.gui.show_popup("error", {
                'title': _t("Order error"),
                'body':  _t("This orderline has already been finalized in a pro forma order and \
can no longer be modified. Please create a new line with eg. a negative quantity."),
            });
        },

        set_discount: function (discount) {
            if (this.blackbox_pro_forma_finalized) {
                this._show_finalized_error();
            } else {
                orderline_super.set_discount.apply(this, arguments);
            }
        },

        set_unit_price: function (price) {
            if (this.blackbox_pro_forma_finalized) {
                this._show_finalized_error();
            } else {
                orderline_super.set_unit_price.apply(this, arguments);
            }
        },

        set_quantity: function (quantity, keep_price) {
            var current_quantity = this.get_quantity();
            var future_quantity = parseFloat(quantity) || 0;
            if (this.pos.config.blackbox_pos_production_id && keep_price && (future_quantity === 0 || future_quantity < current_quantity)) {
                this.pos.gui.show_popup("number", {
                    'title': _((current_quantity > 0? "Decrease": "Increase") + " the quantity by"),
                    'confirm': function (qty_decrease) {
                        if (qty_decrease) {
                            var order = this.pos.get_order();
                            var selected_orderline = order.get_selected_orderline();
                            qty_decrease = qty_decrease.replace(_t.database.parameters.decimal_point, '.');
                            qty_decrease = parseFloat(qty_decrease, 10);

                            if(selected_orderline.product.uom_id[1] === "Units")
                                qty_decrease = parseInt(qty_decrease, 10);

                             var current_total_quantity_remaining = selected_orderline.get_quantity();
                            order.get_orderlines().forEach(function (orderline, index, array) {
                                if (selected_orderline.id != orderline.id &&
                                    selected_orderline.get_product().id === orderline.get_product().id &&
                                    selected_orderline.get_discount() === orderline.get_discount()) {
                                    current_total_quantity_remaining += orderline.get_quantity();
                                }
                            });

                            if (current_quantity > 0 && qty_decrease > current_total_quantity_remaining) {
                                this.pos.gui.show_popup("error", {
                                    'title': _t("Order error"),
                                    'body':  _t("Not allowed to take back more than was ordered."),
                                });
                            } else {
                                var decrease_line = order.get_selected_orderline().clone();
                                decrease_line.order = order;
                                decrease_line.set_quantity(current_quantity > 0? -qty_decrease: qty_decrease);
                                order.add_orderline(decrease_line);
                            }
                        }
                    }
                });
            } else {
                orderline_super.set_quantity.apply(this, arguments);
            }
        },

        init_from_JSON: function (json) {
            orderline_super.init_from_JSON.apply(this, arguments);
            this.blackbox_pro_forma_finalized = json.blackbox_pro_forma_finalized;
        },

        export_as_JSON: function () {
            var json = orderline_super.export_as_JSON.apply(this, arguments);

            return _.extend(json, {
                'vat_letter': this.get_vat_letter(),
                'blackbox_pro_forma_finalized': this.blackbox_pro_forma_finalized
            });
        },

        export_for_printing: function () {
            var json = orderline_super.export_for_printing.apply(this, arguments);

            return _.extend(json, {
                'vat_letter': this.get_vat_letter()
            });
        }
    });

    screens.OrderWidget.include({
        set_value: function (val) {
            var order = this.pos.get_order();
            var mode = this.numpad_state.get('mode');

            if (order.get_selected_orderline() && mode === 'quantity') {
                order.get_selected_orderline().set_quantity(val, "dont_allow_decreases");
            } else {
                this._super(val);
            }
        },

        update_summary: function () {
            if (this.pos.get_order()) {
                return this._super();
            } else {
                return undefined;
            }
        },

        orderline_change: function(line) {
            // don't try to rerender non-visible lines
            if (this.pos.get_order() && line.node && line.node.parentNode) {
                return this._super(line);
            } else {
                return undefined;
            }
        }
    });

    var order_model_super = models.Order.prototype;
    models.Order = models.Order.extend({
        // we need to patch export_as_JSON because that's what's used
        // when sending orders to backend
        export_as_JSON: function () {
            var json = order_model_super.export_as_JSON.bind(this)();

            var to_return = _.extend(json, {
                'blackbox_date': this.blackbox_date,
                'blackbox_time': this.blackbox_time,
                'blackbox_amount_total': this.blackbox_amount_total,
                'blackbox_ticket_counters': this.blackbox_ticket_counters,
                'blackbox_unique_fdm_production_number': this.blackbox_unique_fdm_production_number,
                'blackbox_vsc_identification_number': this.blackbox_vsc_identification_number,
                'blackbox_signature': this.blackbox_signature,
                'blackbox_plu_hash': this.blackbox_plu_hash,
                'blackbox_pos_version': this.blackbox_pos_version,
                'blackbox_pos_production_id': this.blackbox_pos_production_id,
                'blackbox_terminal_id': this.blackbox_terminal_id,
                'blackbox_pro_forma': this.blackbox_pro_forma,
                'blackbox_hash_chain': this.blackbox_hash_chain,
            });

            if (this.blackbox_base_price_in_euro_per_tax_letter) {
                to_return = _.extend(to_return, {
                    'blackbox_tax_category_a': this.blackbox_base_price_in_euro_per_tax_letter[0].amount,
                    'blackbox_tax_category_b': this.blackbox_base_price_in_euro_per_tax_letter[1].amount,
                    'blackbox_tax_category_c': this.blackbox_base_price_in_euro_per_tax_letter[2].amount,
                    'blackbox_tax_category_d': this.blackbox_base_price_in_euro_per_tax_letter[3].amount,
                });
            }

            if (this.blackbox_pos_receipt_time) {
                var DEFAULT_SERVER_DATETIME_FORMAT = "YYYY-MM-DD HH:mm:ss";
                var original_zone = this.blackbox_pos_receipt_time.utcOffset();

                this.blackbox_pos_receipt_time.utcOffset(0); // server expects UTC
                to_return['blackbox_pos_receipt_time'] = this.blackbox_pos_receipt_time.format(DEFAULT_SERVER_DATETIME_FORMAT);
                this.blackbox_pos_receipt_time.utcOffset(original_zone);
            }

            return to_return;
        },

        export_for_printing: function () {
            var receipt = order_model_super.export_for_printing.bind(this)();

            receipt = _.extend(receipt, {
                'company': _.extend(receipt.company, {
                    'street': this.pos.company.street
                })
            });

            return receipt;
        },

        // don't allow to add orderlines without a vat letter
        add_orderline: function (line) {
            if (line.get_vat_letter()) {
                order_model_super.add_orderline.apply(this, arguments);
            }
        },

        // don't allow to add products without a vat letter
        add_product: function (product, options) {
            if (this.pos.config.blackbox_pos_production_id && !this.pos.check_if_user_clocked() && product !== this.pos.work_in_product) {
                this.pos.gui.show_popup("error", {
                    'title': _t("POS error"),
                    'body':  _t("Session is not initialized yet. Register a Work In event first."),
                });
            } else if (this.pos.config.blackbox_pos_production_id && product.taxes_id.length === 0) {
                this.pos.gui.show_popup("error", {
                    'title': _t("POS error"),
                    'body':  _t("Product has no tax associated with it."),
                });
            } else if (this.pos.config.blackbox_pos_production_id && !this.pos.taxes_by_id[product.taxes_id[0]].identification_letter) {
                this.pos.gui.show_popup("error", {
                    'title': _t("POS error"),
                    'body':  _t("Product has an invalid tax amount. Only 21%, 12%, 6% and 0% are allowed."),
                });
            } else {
                return order_model_super.add_product.apply(this, arguments);
            }

            return false;
        },

        _hash_and_sign_string: function () {
            var order_str = "";

            this.get_orderlines().forEach(function (current, index, array) {
                order_str += current.generate_plu_line();
            });

            return order_str;
        },

        get_total_with_tax_without_discounts: function () {
            var positive_orderlines = _.filter(this.get_orderlines(), function (line) {
                return line.get_price_without_tax() > 0;
            });

            var total_without_tax = round_pr(positive_orderlines.reduce((function(sum, orderLine) {
                return sum + orderLine.get_price_without_tax();
            }), 0), this.pos.currency.rounding);

            var total_tax = round_pr(positive_orderlines.reduce((function(sum, orderLine) {
                return sum + orderLine.get_tax();
            }), 0), this.pos.currency.rounding);

            return total_without_tax + total_tax;
        },

        get_tax_percentage_for_tax_letter: function (tax_letter) {
            var percentage_per_letter = {
                'A': 21,
                'B': 12,
                'C': 6,
                'D': 0
            };

            return percentage_per_letter[tax_letter];
        },

        get_price_in_eurocent_per_tax_letter: function (base) {
            var price_per_tax_letter = {
                'A': 0,
                'B': 0,
                'C': 0,
                'D': 0
            };

            this.get_orderlines().forEach(function (current, index, array) {
                var tax_letter = current.get_vat_letter();

                if (tax_letter) {
                    if (base) {
                        price_per_tax_letter[tax_letter] += Math.round(current.get_price_without_tax() * 100);
                    } else {
                        price_per_tax_letter[tax_letter] += Math.round(current.get_price_with_tax() * 100);
                    }
                }
            });

            return price_per_tax_letter;
        },

        // returns an array of the form:
        // [{'letter', 'amount'}, {'letter', 'amount'}, ...]
        get_base_price_in_euro_per_tax_letter_list: function () {
            var base_price_per_tax_letter = this.get_price_in_eurocent_per_tax_letter("base price");
            var base_price_per_tax_letter_list = _.map(_.keys(base_price_per_tax_letter), function (key) {
                return {
                    'letter': key,
                    'amount': base_price_per_tax_letter[key] / 100
                };
            });

            return base_price_per_tax_letter_list;
        },

        calculate_hash: function () {
            return Sha1.hash(this._hash_and_sign_string());
        },

        set_validation_time: function () {
            this.blackbox_pos_receipt_time = moment();
        },
        wait_for_push_order: function () {
            var result = order_model_super.wait_for_push_order.apply(this,arguments);
            result = Boolean(this.pos.config.blackbox_pos_production_id || result);
            return result;
        },
    });

    var FDMPacketField = Class.extend({
        init: function (name, length, content, pad_character) {
            if (typeof content !== 'string') {
                throw "Can only handle string contents";
            }

            if (content.length > length) {
                throw "Content (" + content + ") too long (should be max " + length + ")";
            }

            this.name = name;
            this.length = length;

            this.content = this._pad_left_to_length(content, pad_character);
        },

        _pad_left_to_length: function (content, pad_character) {
            if (content.length < this.length && ! pad_character) {
                throw "Can't pad without a pad character";
            }

            while (content.length < this.length) {
                content = pad_character + content;
            }

            return content;
        },

        to_string: function () {
            return this.content;
        }
    });

    var FDMPacket = Class.extend({
        init: function () {
            this.fields = [];
        },

        add_field: function (field) {
            this.fields.push(field);
        },

        to_string: function () {
            return _.map(this.fields, function (field) {
                return field.to_string();
            }).join("");
        },

        to_human_readable_string: function () {
            return _.map(this.fields, function (field) {
                return field.name + ": " + field.to_string();
            }).join("\n");
        }
    });

    gui.Gui.include({
        show_screen: function(screen_name, params, refresh) {
            if (screen_name === "receipt" || screen_name === "bill") {
                var order = this.pos.get_order();
                if (order && order.blackbox_signature && order.blackbox_signature.toLowerCase().match(/[a-z]/)) {
                    this._super(screen_name, params, refresh);
                }
            } else {
                this._super(screen_name, params, refresh);
            }
        },

        close: function () {
            // send a PS when closing the POS
            if (this.pos.check_if_user_clocked()) {
                this.pos.gui.show_popup("error", {
                    'title': _t("POS error"),
                    'body':  _t("You need to clock out before closing the POS."),
                });
                this.chrome.widget.close_button.$el.removeClass('confirm');
                this.chrome.widget.close_button.$el.text(_t('Close'));
                this.chrome.widget.close_button.confirmed = false;
            } else {
                this.pos._push_pro_forma().then(this._super.bind(this), this._super.bind(this));
            }
        }
    });

    devices.ProxyDevice.include({
        _get_sequence_number: function () {
            var sequence_number = this.pos.db.load('sequence_number', 0);
            this.pos.db.save('sequence_number', (sequence_number + 1) % 100);

            return sequence_number;
        },

        build_request: function (id) {
            var packet = new FDMPacket();

            packet.add_field(new FDMPacketField("id", 1, id));
            packet.add_field(new FDMPacketField("sequence number", 2, this._get_sequence_number().toString(), "0"));
            packet.add_field(new FDMPacketField("retry number", 1, "0"));

            return packet;
        },

        // ignore_non_critical: will ignore warnings and will ignore
        // certain 'real' errors defined in non_critical_errors
        _handle_fdm_errors: function (parsed_response, ignore_non_critical) {
            var self = this;
            var error_1 = parsed_response.error_1;
            var error_2 = parsed_response.error_2;

            var non_critical_errors = [
                1, // no vat signing card
                2, // initialize vat signing card with pin
                3, // vsc blocked
                5, // memory full
                9, // real time clock corrupt
                10, // vsc not compatible
            ];

            if (error_1 === 0) { // no errors
                if (error_2 === 1) {
                    this.pos.gui.show_popup("confirm", {
                        'title': _t("Fiscal Data Module"),
                        'body':  _t("PIN accepted."),
                    });
                }

                return true;
            } else if (error_1 === 1 && ! ignore_non_critical) { // warnings
                if (error_2 === 1) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module warning"),
                        'body':  _t("Fiscal Data Module memory 90% full."),
                    });
                } else if (error_2 === 2) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module warning"),
                        'body':  _t("Already handled request."),
                    });
                } else if (error_2 === 3) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module warning"),
                        'body':  _t("No record."),
                    });
                } else if (error_2 === 99) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module warning"),
                        'body':  _t("Unspecified warning."),
                    });
                }

                return true;
            } else { // errors
                if (ignore_non_critical && non_critical_errors.indexOf(error_2) !== -1) {
                    return true;
                }

                if (error_2 === 1) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("No Vat Signing Card or Vat Signing Card broken."),
                    });
                } else if (error_2 === 2) {
                    this.pos.gui.show_popup("number", {
                        'title': _t("Please initialize the Vat Signing Card with PIN."),
                        'confirm': function (pin) {
                            self.pos.proxy.request_fdm_pin_verification(pin);
                        }
                    });
                } else if (error_2 === 3) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Vat Signing Card blocked."),
                    });
                } else if (error_2 === 4) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Invalid PIN."),
                    });
                } else if (error_2 === 5) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Fiscal Data Module memory full."),
                    });
                } else if (error_2 === 6) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Unknown identifier."),
                    });
                } else if (error_2 === 7) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Invalid data in message."),
                    });
                } else if (error_2 === 8) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Fiscal Data Module not operational."),
                    });
                } else if (error_2 === 9) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Fiscal Data Module real time clock corrupt."),
                    });
                } else if (error_2 === 10) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Vat Signing Card not compatible with Fiscal Data Module."),
                    });
                } else if (error_2 === 99) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Unspecified error."),
                    });
                }

                return false;
            }
        },

        _parse_fdm_common_response: function (response) {
            return {
                identifier: response[0],
                sequence_number: parseInt(response.substr(1, 2), 10),
                retry_counter: parseInt(response[3], 10),
                error_1: parseInt(response[4], 10),
                error_2: parseInt(response.substr(5, 2), 10),
                error_3: parseInt(response.substr(7, 3), 10),
                fdm_unique_production_number: response.substr(10, 11),
            };
        },

        parse_fdm_identification_response: function (response) {
            return _.extend(this._parse_fdm_common_response(response),
                            {
                                fdm_firmware_version_number: response.substr(21, 20),
                                fdm_communication_protocol_version: response[41],
                                vsc_identification_number: response.substr(42, 14),
                                vsc_version_number: parseInt(response.substr(56, 3), 10)
                            });
        },

        parse_fdm_pin_response: function (response) {
            return _.extend(this._parse_fdm_common_response(response),
                            {
                                vsc_identification_number: response.substr(21, 14),
                            });
        },

        parse_fdm_hash_and_sign_response: function (response) {
            return _.extend(this._parse_fdm_common_response(response),
                            {
                                vsc_identification_number: response.substr(21, 14),
                                date: response.substr(35, 8),
                                time: response.substr(43, 6),
                                event_label: response.substr(49, 2),
                                vsc_ticket_counter: parseInt(response.substr(51, 9)),
                                vsc_total_ticket_counter: parseInt(response.substr(60, 9)),
                                signature: response.substr(69, 40)
                            });
        },

        _build_fdm_identification_request: function () {
            return this.build_request("I");
        },

        _build_fdm_pin_request: function (pin) {
            var packet = this.build_request("P");
            packet.add_field(new FDMPacketField("pin code", 5, pin.toString(), "0"));

            return packet;
        },

        // fdm needs amounts in cents with at least 3 numbers (eg. 0.5
        // euro => '050') and encoded as a string
        _amount_to_fdm_amount_string: function (amount) {
            amount *= 100; // to eurocent
            amount = round_pr(amount, 0.01); // make sure it's properly rounded (to avoid eg. x.9999999999999999999)
            amount = amount.toString();

            while (amount.length < 3) {
                amount = "0" + amount;
            }

            return amount;
        },

        _get_insz_or_bis_number: function() {
            var insz = this.pos.user.insz_or_bis_number;
            if (! insz) {
                this.pos.gui.show_popup('error',{
                    'title': _t("Fiscal Data Module error"),
                    'body': _t("INSZ or BIS number not set for current cashier."),
                });
                return false;
            }
            return insz;
        },

        // todo jov: p77
        _build_fdm_hash_and_sign_request: function (order) {
            var packet = this.build_request("H");
            var insz_or_bis_number = this._get_insz_or_bis_number();

            if (! insz_or_bis_number) {
                return false;
            }

            packet.add_field(new FDMPacketField("ticket date", 8, order.blackbox_pos_receipt_time.format("YYYYMMDD")));
            packet.add_field(new FDMPacketField("ticket time", 6, order.blackbox_pos_receipt_time.format("HHmmss")));
            packet.add_field(new FDMPacketField("insz or bis number", 11, insz_or_bis_number));
            packet.add_field(new FDMPacketField("production number POS", 14, this.pos.config.blackbox_pos_production_id));
            packet.add_field(new FDMPacketField("ticket number", 6, (++this.pos.config.backend_sequence_number).toString(), " "));

            if (order.blackbox_pro_forma) {
                packet.add_field(new FDMPacketField("event label", 2, "PS"));
            } else {
                packet.add_field(new FDMPacketField("event label", 2, "NS"));
            }

            packet.add_field(new FDMPacketField("total amount to pay in eurocent", 11, this._amount_to_fdm_amount_string(order.blackbox_amount_total), " "));

            packet.add_field(new FDMPacketField("tax percentage 1", 4, "2100"));
            packet.add_field(new FDMPacketField("amount at tax percentage 1 in eurocent", 11, this._amount_to_fdm_amount_string(order.blackbox_base_price_in_euro_per_tax_letter[0].amount), " "));
            packet.add_field(new FDMPacketField("tax percentage 2", 4, "1200"));
            packet.add_field(new FDMPacketField("amount at tax percentage 2 in eurocent", 11, this._amount_to_fdm_amount_string(order.blackbox_base_price_in_euro_per_tax_letter[1].amount), " "));
            packet.add_field(new FDMPacketField("tax percentage 3", 4, " 600"));
            packet.add_field(new FDMPacketField("amount at tax percentage 3 in eurocent", 11, this._amount_to_fdm_amount_string(order.blackbox_base_price_in_euro_per_tax_letter[2].amount), " "));
            packet.add_field(new FDMPacketField("tax percentage 4", 4, " 000"));
            packet.add_field(new FDMPacketField("amount at tax percentage 4 in eurocent", 11, this._amount_to_fdm_amount_string(order.blackbox_base_price_in_euro_per_tax_letter[3].amount), " "));
            packet.add_field(new FDMPacketField("PLU hash", 40, order.calculate_hash()));

            return packet;
        },

        _show_could_not_connect_error: function (reason) {
            var body = _t("Could not connect to the Fiscal Data Module.");
            var self = this;
            if (reason) {
                body = body + ' ' + reason;
            }
            setTimeout(function(){self.pos.gui.close()}, 5000);
            this.pos.gui.show_popup("blocking-error", {
                'title': _t("Fiscal Data Module error"),
                'body':  body,
            });
        },

        _verify_pin: function (data) {
            if (!data.value) {
                this._show_could_not_connect_error();
            } else {
                var parsed_response = this.parse_fdm_pin_response(response);

                 // pin being verified will show up as 'error'
                this._handle_fdm_errors(parsed_response);
            }
        },

        _check_and_parse_fdm_identification_response: function (resolve, reject, data) {
            if (!data.value) {
                this._show_could_not_connect_error();
                return "";
            } else {
                var parsed_response = this.parse_fdm_identification_response(data.value);
                if (this._handle_fdm_errors(parsed_response, true)) {
                    resolve(parsed_response);
                } else {
                    reject("");
                }
            }
        },

        request_fdm_identification: function () {
            var self = this;
            var fdm = this.pos.iot_device_proxies.fiscal_data_module;
            return new Promise(function (resolve, reject) {
                fdm.add_listener(self._check_and_parse_fdm_identification_response.bind(self, resolve, reject));
                fdm.action({
                    action: 'request',
                    high_level_message: self._build_fdm_identification_request().to_string(),
                    response_size: 59
                });
            });
        },

        request_fdm_pin_verification: function (pin) {
            var self = this;
            var fdm = this.pos.iot_device_proxies.fiscal_data_module;
            fdm.add_listener(self._verify_pin.bind(self));
            fdm.action({
                action: 'request',
                high_level_message: self._build_fdm_pin_request(pin).to_string(),
                response_size: 35
            });
        },

        _check_and_parse_fdm_hash_and_sign_response: function (resolve, reject, hide_error, data) {
            if (!data.value) {
                return this._retry_request_fdm_hash_and_sign(packet, hide_error);
            } else {
                var parsed_response = this.parse_fdm_hash_and_sign_response(data.value);

                 // close any blocking-error popup
                this.pos.gui.close_popup();

                 if (this._handle_fdm_errors(parsed_response)) {
                    resolve(parsed_response);
                } else {
                    reject("");
                }
            }
        },

        request_fdm_identification: function () {
            var self = this;
            var fdm = this.pos.iot_device_proxies.fiscal_data_module;
            return new Promise(function (resolve, reject) {
                fdm.add_listener(self._check_and_parse_fdm_identification_response.bind(self, resolve, reject));
                fdm.action({
                    action: 'request',
                    high_level_message: self._build_fdm_identification_request().to_string(),
                    response_size: 59
                });
            });
        },

        _retry_request_fdm_hash_and_sign: function (packet, hide_error) {
            var self = this;

            if (!hide_error) {
                self._show_could_not_connect_error();
            }

            return new Promise(function (resolve, reject) {
                // rate limit the retries to 1 every 2 sec
                // because the blackbox freaks out if we send messages too fast
                setTimeout(function () {
                    resolve();
                }, 5000);
            }).then(function () {
                return self.request_fdm_hash_and_sign(packet, "hide error");
            });
        },

        request_fdm_hash_and_sign: function (packet, hide_error) {
            var self = this;
            var fdm = this.pos.iot_device_proxies.fiscal_data_module;
            return new Promise(function (resolve, reject) {
                fdm.add_listener(self._check_and_parse_fdm_hash_and_sign_response.bind(self, resolve, reject, hide_error));
                fdm.action({
                    action: 'request',
                    high_level_message: packet.to_string(),
                    response_size: 109
                });
            });
        }
    });

    var BlackBoxIdentificationWidget = PosBaseWidget.extend({
        template: 'BlackboxIdentificationWidget',
        start: function () {
            var self = this;

            this.$el.click(function () {
                self.pos.proxy.request_fdm_identification().then(function (parsed_response) {
                    if (parsed_response) {
                        var list = _.map(_.pairs(_.pick(parsed_response, 'fdm_unique_production_number',
                                                        'fdm_firmware_version_number',
                                                        'fdm_communication_protocol_version',
                                                        'vsc_identification_number',
                                                        'vsc_version_number')), function (current) {
                                                            return {
                                                                'label': current[0].replace(/_/g, " ") + ": " + current[1]
                                                            };
                                                        });

                        self.gui.show_popup("selection", {
                            'title': _t("FDM identification"),
                            'list': list
                        });
                    }
                });
            });

            if (! this.pos.config.use_proxy) {
                this.$().addClass('oe_hidden');
            }
        },
    });

    chrome.Chrome.include({
        build_widgets: function () {
            // add blackbox id widget to left of proxy widget
            var proxy_status_index = _.findIndex(this.widgets, function (widget) {
                return widget.name === "proxy_status";
            });

            this.widgets.splice(proxy_status_index, 0, {
                'name': 'blackbox_identification',
                'widget': BlackBoxIdentificationWidget,
                'append': '.pos-rightheader',
            });

            var debug_widget = _.find(this.widgets, function (widget) {
                return widget.name === "debug";
            });

            debug_widget.widget.include({
                start: function () {
                    var self = this;
                    this._super();

                    this.$('.button.build-hash-and-sign-request').click(function () {
                        var order = self.pos.get_order();
                        order.set_validation_time();
                        order.blackbox_base_price_in_euro_per_tax_letter = order.get_base_price_in_euro_per_tax_letter_list();
                    });
                }
            });

            this._super();
        },

        // show_error with the option of showing user-friendly errors
        // (without backtrace etc.)
        show_error: function(error) {
            if (error.message.indexOf("FDM error: ") > -1) {
                this.gui.show_popup('error',{
                    'title': _t("POS Error"),
                    'body':  error.message,
                });
            } else {
                this._super(error);
            }
        }
    });
    var posmodel_super = models.PosModel.prototype;
    models.PosModel = models.PosModel.extend({
        _extract_order_number: function (records) {
            if (records.length) {
                return parseInt(records[0]['name'].match(/\d+$/)[0], 10);
            } else {
                return 0;
            }
        },

        _get_hash_chain: function (records) {
            if (records.length) {
                return records[0]['hash_chain'];
            } else {
                return "";
            }
        },

        _prepare_date_for_ticket: function (date) {
            // format of date coming from blackbox is YYYYMMDD
            var year = date.substr(0, 4);
            var month = date.substr(4, 2);
            var day = date.substr(6, 2);

            return day + "/" + month + "/" + year;
        },

        _prepare_time_for_ticket: function (time) {
            // format of time coming from blackbox is HHMMSS
            var hours = time.substr(0, 2);
            var minutes = time.substr(2, 2);
            var seconds = time.substr(4, 2);

            return hours + ":" + minutes + ":" + seconds;
        },

        _prepare_ticket_counter_for_ticket: function (counter, total_counter, event_type) {
            return counter + "/" + total_counter + " " + event_type;
        },

        _prepare_hash_for_ticket: function (hash) {
            var amount_of_least_significant_characters = 8;

            return hash.substr(-amount_of_least_significant_characters);
        },

        _check_validation_constraints: function () {
            if (! this.company.street) {
                this.gui.show_popup("error", {
                    'title': _t("Fiscal Data Module error"),
                    'body':  _t("Company address must be set."),
                });

                return false;
            } else if (! this.company.vat) {
                this.gui.show_popup("error", {
                    'title': _t("Fiscal Data Module error"),
                    'body':  _t("VAT number must be set."),
                });

                return false;
            }

            return true;
        },

        _check_iotbox_serial: function (data) {
            var self = this;
            if (!data.value) {
                this.proxy._show_could_not_connect_error(_t("Unreachable FDM"));
            } else if ("BODO001" + data.value.toUpperCase() != this.config.blackbox_pos_production_id.toUpperCase()) {
                this.proxy._show_could_not_connect_error(
                    _t("Incorrect PosBox serial") + ' ' + this.config.blackbox_pos_production_id.toUpperCase()
                );
            } else {
                this.chrome.ready.then(function () {
                    $(self.chrome.$el).find('.placeholder-posVersion').text(' Ver: ' + self.version.server_version + "1807BE_FDM");
                    var current = $(self.chrome.$el).find('.placeholder-posID').text();
                    $(self.chrome.$el).find('.placeholder-posID').text(' ID: ' + self.config.blackbox_pos_production_id);
                });
            }
        },

        connect_to_proxy: function () {
            if(this.config.blackbox_pos_production_id) {
                var self = this;
                var fdm = this.iot_device_proxies.fiscal_data_module;
                return posmodel_super.connect_to_proxy.apply(this, arguments).then(function () {
                    fdm.add_listener(self._check_iotbox_serial.bind(self));
                    fdm.action({ action: 'request_serial' });
                });
            } else {
                return Promise.resolve();
            }
        },

        push_order_to_blackbox: function (order) {
            var self = this;

            if (! this._check_validation_constraints()) {
                return Promise.reject();
            }

            order.set_validation_time();
            order.blackbox_amount_total = order.get_total_with_tax();
            order.blackbox_base_price_in_euro_per_tax_letter = order.get_base_price_in_euro_per_tax_letter_list();

            var packet = this.proxy._build_fdm_hash_and_sign_request(order);
            if (!packet) {
                return Promise.reject();
            }
            var prom = this.proxy.request_fdm_hash_and_sign(packet).then(function (parsed_response) {
                return new Promise(function (resolve, reject) {
                    if (parsed_response) {
                        // put fields that we need on tickets on order
                        order.blackbox_order_name = self.config.name + "/" + self.config.backend_sequence_number;
                        order.blackbox_date = self._prepare_date_for_ticket(parsed_response.date);
                        order.blackbox_time = self._prepare_time_for_ticket(parsed_response.time);
                        order.blackbox_ticket_counters =
                        self._prepare_ticket_counter_for_ticket(parsed_response.vsc_ticket_counter,
                                                                parsed_response.vsc_total_ticket_counter,
                                                                parsed_response.event_label);
                        order.blackbox_signature = parsed_response.signature;
                        order.blackbox_vsc_identification_number = parsed_response.vsc_identification_number;
                        order.blackbox_unique_fdm_production_number = parsed_response.fdm_unique_production_number;
                        order.blackbox_plu_hash = self._prepare_hash_for_ticket(packet.fields[packet.fields.length - 1].content);
                        order.blackbox_pos_version = "Odoo " + self.version.server_version + "1807BE_FDM";
                        order.blackbox_pos_production_id = self.config.blackbox_pos_production_id;
                        order.blackbox_terminal_id = self.blackbox_terminal_id;

                        self.config.blackbox_most_recent_hash = self._prepare_hash_for_ticket(Sha1.hash(self.config.blackbox_most_recent_hash + order.blackbox_plu_hash));
                        order.blackbox_hash_chain = self.config.blackbox_most_recent_hash;


                        resolve();
                    } else {
                        reject();
                    }
                });
            });

            return prom;
        },

        push_order: function (order, opts) {
            if (this.config.blackbox_pos_production_id && order) {
                var self = this;
                opts = opts || {};
                order.blackbox_pro_forma = opts.pro_forma || false;

                // split discount lines
                this._split_discount_lines();
                return this.push_order_to_blackbox(order).then(function () {
                    order.get_orderlines().forEach(function (current, index, array) {
                        delete current.blackbox_pro_forma_finalized;
                    });

                    res = posmodel_super.push_order.apply(self, [order, opts]);

                    order.get_orderlines().forEach(function (current, index, array) {
                        current.blackbox_pro_forma_finalized = true;
                        current.trigger('change', current); // force export
                    });
                     return res;
                }, function () {
                    return Promise.reject();
                });
            } else {
                return posmodel_super.push_order.apply(this, arguments);
            }
        },

        push_and_invoice_order: async function (order) {
            if(this.config.blackbox_pos_production_id) {
                var self = this;

                // these will never be sent as pro_forma
                order.blackbox_pro_forma = false;

                // this is a duplicate test from _super(), it is necessary
                // because we do not want to send orders to the blackbox
                // which will not be sent to the backend
                if(! order.get_client()) {
                    return Promise.reject({code:400, message:'Missing Customer', data:{}});
                }
                try {
                    await self.push_order_to_blackbox(order);
                    return await posmodel_super.push_and_invoice_order.apply(self, [order]);
                } catch(err) {
                    return err;
                }
            } else {
                return posmodel_super.push_and_invoice_order.apply(this, [order]);
            }
        },


        _push_pro_forma: function () {
            var old_order = this.get_order();

            // Only push orders with something in them as pro forma.
            // Also don't push orders which have pro_forma set to
            // false. Because those are 'real orders' that we already
            // handled.
            if (old_order && old_order.get_orderlines().length && old_order.blackbox_pro_forma !== false) {
                return this.push_order(old_order, {'pro_forma': true});
            } else {
                return Promise.reject();
            }
        },

        // for pos_loyalty
        _split_discount_lines: function () {
            var self = this;
            var order = this.get_order();
            var lines_to_delete = [];
            var lines_to_add = [];

            order.get_orderlines().forEach(function (line) {
                // discount or resale
                if (line.reward_id && line.get_price_with_tax() < 0) {
                    var discount_line = line;
                    lines_to_delete.push(line);

                    var price_per_tax_letter = order.get_price_in_eurocent_per_tax_letter();

                    // we need to filter out negative orderlines
                    var order_total = self.get_order().get_total_with_tax_without_discounts();
                    var discount_percentage_on_order = Math.abs(discount_line.get_price_with_tax() / order_total);
                    var resale_quantity = discount_line.get_quantity();

                    // 1. delete line
                    // 2. re-add lines with the same product id but with modified taxes
                    //    essentially just adding a discount_percentage_on_order% per tax

                    _.forEach(_.pairs(price_per_tax_letter), function (tax) {
                        tax[1] = tax[1] / 100; // was in eurocents
                        if (tax[1] > 0.00001) {
                            var percentage_of_this_tax_in_total = round_pr(tax[1] / order_total, 0.01);

                            // add correct tax on product
                            var new_line_tax = _.find(self.taxes, function (pos_tax) {
                                return tax[0] === pos_tax.identification_letter;
                            });

                            var cloned_product = _.clone(discount_line.product);

                            cloned_product.taxes_id = [new_line_tax.id];

                            lines_to_add.push([cloned_product, {
                                quantity: resale_quantity * percentage_of_this_tax_in_total,
                                merge: false,
                                extras: { reward_id: discount_line.reward_id },
                            }]);
                        }
                    });
                }
            });

            _.map(lines_to_delete, function (line) { self.get_order().remove_orderline(line); });
            _.map(lines_to_add, function (line) { self.get_order().add_product.apply(self.get_order(), line); });
        },

        add_new_order: function () {
            this._push_pro_forma();

            return posmodel_super.add_new_order.apply(this, arguments);
        },

        set_order: function (order) {
            this._push_pro_forma();

            return posmodel_super.set_order.apply(this, arguments);
        },

        // we need to be able to identify devices that do
        // transactions, the best we can do is to generate a terminal
        // id per device in localstorage and use that. We don't use
        // the PosDB because it uses a name prefix that allows
        // multiple db's per browser (in theory).
        get_blackbox_terminal_id: function () {
            if (!localStorage.odoo_pos_blackbox_pos_production_id) {
                // the production id needs to be 14 characters long,
                // so we can generate a 64 bit id and encode it in
                // base 36, which gives us a max size of 13.
                var production_id = Math.floor(Math.random() * Math.pow(2, 64)) + 1;

                // represent it as a string with base 36 for compactness
                production_id = production_id.toString(36);

                // pad it with 0 so it's exactly 14 characters
                while (production_id.length < 14) {
                    production_id = "0" + production_id;
                }

                localStorage.odoo_pos_blackbox_pos_production_id = production_id;
            }

            return localStorage.odoo_pos_blackbox_pos_production_id;
        },

        after_load_server_data: function () {
            var self = this;
            // with this module we will always have to connect to the
            // proxy, regardless of user preferences
            this.config.use_proxy = true;
            this.blackbox_terminal_id = this.get_blackbox_terminal_id() || false;

            this.chrome.ready.then(function () {
                var current = $(self.chrome.$el).find('.placeholder-terminalID').text();
                $(self.chrome.$el).find('.placeholder-terminalID').text(' TID: ' + self.blackbox_terminal_id);
            });

            // With pos_cache product.product isn't loaded the normal uncached way.
            // So there are no products in pos.db when models are loaded and
            // work_in_product / work_out_product end up unidentified.
            if (!self.work_in_product) {
                var products = this.db.product_by_id;
                for (var id in products) {
                    if (products[id].display_name === 'WORK IN') {
                        self.work_in_product = products[id];
                    } else if (products[id].display_name === 'WORK OUT') {
                        self.work_out_product = products[id];
                    }
                }
            }

            return posmodel_super.after_load_server_data.apply(this, arguments);
        },

        delete_current_order: function () {
            if (this.get_order().get_orderlines().length) {
                this.gui.show_popup("error", {
                    'title': _t("Fiscal Data Module error"),
                    'body':  _t("Deleting of orders is not allowed."),
                });
            } else {
                posmodel_super.delete_current_order.apply(this, arguments);
            }
        },

        transfer_order_to_different_table: function () {
            if(this.config.blackbox_pos_production_id) {
                var self = this;
                var old_order = this.get_order();
                var new_order = this.add_new_order();
                new_order.draft = true;
                // remove all lines of the previous order and create a new one
                old_order.get_orderlines().forEach(function (current) {
                    var decrease_line = current.clone();
                    decrease_line.order = old_order;
                    decrease_line.set_quantity(-current.get_quantity());
                    old_order.add_orderline(decrease_line);

                    var moved_line = current.clone();
                    moved_line.order = new_order;
                    new_order.add_orderline(moved_line);
                });

                // save the order with canceled lines
                posmodel_super.set_order.call(this, old_order);
                this.push_order(old_order).then(function () {

                    posmodel_super.set_order.call(self, new_order);
                    // disable blackbox_pro_forma to avoid saving a pro forma on set_order(null) call
                    new_order.blackbox_pro_forma = false;
                    new_order.table = null;

                    // show table selection screen
                    posmodel_super.transfer_order_to_different_table.apply(self, arguments);
                    new_order.blackbox_pro_forma = true;
                });
            } else {
                posmodel_super.transfer_order_to_different_table();
            }
         },

        set_table: function(table) {
            if(this.config.blackbox_pos_production_id) {
                if (!table) { // no table ? go back to the floor plan, see ScreenSelector
                    this.set_order(null);
                } else if (this.order_to_transfer_to_different_table) {
                    this.order_to_transfer_to_different_table.table = table;
                    this.order_to_transfer_to_different_table.save_to_db();
                    this.order_to_transfer_to_different_table = null;

                    // set this table
                    this.set_table(table);

                } else {
                    this.table = table;
                    var orders = this.get_order_list();
                    if (orders.length) {
                        this.set_order(orders[0]); // and go to the first one ...
                    } else {
                        this.add_new_order();  // or create a new order with the current table
                    }
                }
            } else {
                return posmodel_super.set_table.apply(this, table);
            }
        },
        check_if_user_clocked: function() {
            return this.pos_session.users_clocked_ids.find(elem => elem === this.user.id);
        },
        get_args_for_clocking: function() {
            return [this.pos_session.id, this.pos_session.user_id[0]];
        },
        set_clock_values: function(values) {
            this.pos_session.users_clocked_ids = values;
        },
        get_method_call_for_clocking: function() {
            return 'get_user_session_work_status';
        },
        set_method_call_for_clocking: function() {
            return 'set_user_session_work_status';
        }
    });

    DB.include({
        // do not remove pro forma to keep them in localstorage after sent
        // to server and avoid losing it when the browser is closed
        remove_unpaid_order: function(order){
            var orders = this.load('unpaid_orders',[]);
            orders = _.filter(orders, function(o){
                return (order.blackbox_pro_forma === true ||
                        o.id !== order.uid);
            });
            this.save('unpaid_orders',orders);
        },
    });

    screens.ProductScreenWidget.include({
        start: function () {
            this._super();

            var print_bill_button = this.action_buttons['print_bill'];

            if (print_bill_button) {
                var print_bill_super = print_bill_button.button_click;

                // don't allow bill spamming, because:
                // 1. according to minfin it leads to weird characters
                //    being printed, I can't reproduce it though.
                // 2. if you press fast enough you'll end up with
                //    bills being printed before the order gets updated.
                var disabled = false;

                print_bill_button.button_click = function () {
                    var self = this;
                    if (! disabled) {
                        disabled = true;

                        setTimeout(function () {
                            disabled = false;
                        }, 5000);

                        this.pos._push_pro_forma().then(function () {
                            print_bill_super.bind(self)();

                            var order = self.pos.get_order();
                            var to_delete = [];
                            // after we push the order to EJ and FDM we are
                            // allowed to consolidate all the orderlines
                            order.get_orderlines().forEach(function (current, index) {
                                order.get_orderlines().forEach(function (other, other_index) {
                                    if (index != other_index && to_delete.indexOf(current) == -1 && current.can_be_merged_with(other, "ignore blackbox finalized")) {
                                        // we cannot allow consolidation that clears the
                                        // entire order because you cannot validate an
                                        // empty order in the POS. This would cause a
                                        // problem because the government requires that
                                        // every PS order is eventually encoded in an NS
                                        // order. In fact, the backend won't allow you to
                                        // close the session if there are non-finalized
                                        // orders.
                                        if (order.get_orderlines().length - to_delete.length != 2 || Math.abs(current.get_quantity()) - Math.abs(other.get_quantity()) != 0) {
                                            current.merge(other);
                                            to_delete.push(other);

                                            if (current.get_quantity() === 0) {
                                                to_delete.push(current);
                                            }
                                        }
                                    }
                                });
                            });

                            to_delete.forEach(function (current) {
                                order.remove_orderline(current);
                            });
                        });
                    }
                };
            }

            // splitting bills is not an issue. The issue is that
            // during bill splitting you can select orders and click
            // on back. This splits the order into two orders. In
            // order to make this legal, we have to generate a Pro
            // Forma sale for the new order and a Pro Forma refund for
            // the old table (should be identical to the new order I
            // suppose).
            var split_bill_button = this.action_buttons['splitbill'];

            if (split_bill_button) {
                split_bill_button.hide();
            }
        }
    });

    screens.NumpadWidget.include({
        start: function(event) {
            this._super(event);
            if(this.pos.config.blackbox_pos_production_id) {
                this.$el.find('.mode-button[data-mode=price]').prop("disabled",true);
                this.$el.find('.numpad-minus').prop("disabled",true);
            }
        },
        clickChangeMode: function (event) {
            if (this.pos.config.blackbox_pos_production_id && event.currentTarget.attributes['data-mode'].nodeValue === "price") {
                this.gui.show_popup("error", {
                    'title': _t("Fiscal Data Module error"),
                    'body':  _t("Adjusting the price is not allowed."),
                });
            } else {
                this._super(event);
            }
        }
    });

    screens.ProductListWidget.include({
        set_product_list: function (product_list) {
            var self = this;

            // get rid of the work_in and work_out products because
            // we're not allowed to have pro forma work_in/out orders.
            product_list = _.reject(product_list, function (current) {
                return current === self.pos.work_in_product || current === self.pos.work_out_product;
            });

            return this._super(product_list);
        }
    });

    SplitbillScreenWidget.include({
        set_line_on_order: function(neworder, split, line) {
            if( split.quantity && this.pos.config.blackbox_pos_production_id){
                if ( !split.line ){
                    split.line = line.clone();
                    neworder.add_orderline(split.line);
                }
                split.line.set_quantity(split.quantity);

            }else if( split.line && this.pos.config.blackbox_pos_production_id) {
                neworder.remove_orderline(split.line);
                split.line = null;
            } else {
                this._super(neworder, split, line);
            }
        },

        set_quantity_on_order: function(splitlines, order) {
            if(this.pos.config.blackbox_pos_production_id) {
                for(var id in splitlines){
                    var split = splitlines[id];
                    var line  = order.get_orderline(parseInt(id));

                    var decrease_line = line.clone();
                    decrease_line.order = order;
                    decrease_line.set_quantity(-split.quantity);
                    order.add_orderline(decrease_line);

                    delete splitlines[id];
                }
            } else {
                 this._super(splitlines, order);
            }
        },

        check_full_pay_order:function(order, splitlines) {
            // Because of the lines added with negative quantity when we remove product,
            // we have to check if the sum of the negative and positive lines are equals to the split.
            if(this.pos.config.blackbox_pos_production_id) {
                var full = true;
                var groupedLines = _.groupBy(order.get_orderlines(), line => line.get_product().id);

                Object.keys(groupedLines).forEach(function (lineId) {
                    var maxQuantity = groupedLines[lineId].reduce(((quantity, line) => quantity + line.get_quantity()), 0);
                    Object.keys(splitlines).forEach(id => {
                        var split = splitlines[id];
                        if(split.line.get_product().id === groupedLines[lineId][0].get_product().id)
                            maxQuantity -= split.quantity;
                    });
                    if(maxQuantity !== 0)
                        full = false;
                });

                return full;
            } else {
                this._super(order, splitlines);
            }
        },

        lineselect: function($el,order,neworder,splitlines,line_id){
            var split = splitlines[line_id] || {'quantity': 0, line: null};
            var line  = order.get_orderline(line_id);

            this.split_quantity(split, line, splitlines);

            this.set_line_on_order(neworder, split, line);

            splitlines[line_id] = split;
            $el.replaceWith($(QWeb.render('SplitOrderline',{
                widget: this,
                line: line,
                selected: split.quantity !== 0,
                quantity: split.quantity,
                id: line_id,
            })));
            this.$('.order-info .subtotal').text(this.format_currency(neworder.get_subtotal()));
        },

        split_quantity: function(split, line, splitlines) {
            if(this.pos.config.blackbox_pos_production_id) {
                var total_quantity = 0;
                var splitted = 0;
                var order = line.order;

                order.get_orderlines().forEach(function(orderLine) {
                    if(orderLine.get_product().id === line.product.id){
                        total_quantity += orderLine.get_quantity();
                        splitted += splitlines[orderLine.id]? splitlines[orderLine.id].quantity: 0;
                    }
                });

                if(line.get_quantity() > 0) {
                    if( !line.get_unit().is_pos_groupable ){
                        if( split.quantity !== total_quantity){
                            split.quantity = total_quantity;
                        }else{
                            split.quantity = 0;
                        }
                    }else{
                        if( splitted < total_quantity && split.quantity < line.get_quantity()){
                            split.quantity += line.get_unit().is_pos_groupable ? 1 : line.get_unit().rounding;
                            if(splitted > total_quantity){
                                split.quantity = line.get_quantity();
                            }
                        }else{
                            split.quantity = 0;
                        }
                    }
                }
            } else {
                this._super(split, line);
            }
        },
    });

    var work_out_button = screens.ActionButtonWidget.extend({
        template: 'WorkOutButton',
        button_click: function () {
            var self = this;
            if(this.pos.clicked_on_clocked)
                return false;
            this.pos.clicked_on_clocked = true;
            if(!this.pos._check_validation_constraints())
                return false;
            rpc.query({
                model: 'pos.session',
                method: this.pos.get_method_call_for_clocking(),
                args: this.pos.get_args_for_clocking(),
            })
            .then(function (clocked){
                if(clocked) {
                    var unpaid_tables = self.pos.db.load('unpaid_orders', [])
                        .filter(function (order) { return order.data.amount_total > 0; })
                        .map(function (order) { return order.data.table; });
                    if (unpaid_tables.length) {
                        self.pos.gui.show_popup('error', {
                            'title': _t("Fiscal Data Module error"),
                            'body': _.str.sprintf(_t("Tables %s still have unpaid orders. You will not be able to clock out untill all orders have been paid."), unpaid_tables.sort().join(', ')),
                        });
                        return false;
                    }

                    self.pos.proxy.request_fdm_identification().then(function (parsed_response) {
                        if (parsed_response) {
                            self.pos.add_new_order();
                            self.pos.get_order().add_product(self.pos.work_out_product);
                            self.pos.get_order().draft = false;
                            self.pos.push_order(self.pos.get_order()).then(function() {
                                self.gui.show_screen('receipt');
                                args = self.pos.get_args_for_clocking().concat(false);
                                rpc.query({
                                    model: 'pos.session',
                                    method: self.pos.set_method_call_for_clocking(),
                                    args: args,
                                })
                                .then(function(users_logged) {
                                    self.pos.clicked_on_clocked = false;
                                    self.pos.set_clock_values(users_logged);
                                })
                            });
                        }
                    });
                } else {
                    self.pos.gui.show_popup("error", {
                        'title': _t("POS error"),
                        'body': _t("Session is not initialized. Register a Work In event first."),
                    });
                    self.pos.clicked_on_clocked = false;
                    return false;
                }
            });
        }
    });

    screens.define_action_button({
        'name': 'work_out',
        'widget': work_out_button,
    });

    var work_in_button = screens.ActionButtonWidget.extend({
        template: 'WorkInButton',
        button_click: function () {
            var self = this;
            if(this.pos.clicked_on_clocked)
                return false;
            this.pos.clicked_on_clocked = true;
            if(!this.pos._check_validation_constraints())
                return false;
            rpc.query({
                model: 'pos.session',
                method: this.pos.get_method_call_for_clocking(),
                args: this.pos.get_args_for_clocking(),
            })
            .then(function (clocked){
                if(!clocked) {
                    self.pos.proxy.request_fdm_identification().then(function (parsed_response) {
                        if (parsed_response) {
                            self.pos.add_new_order();
                            self.pos.get_order().add_product(self.pos.work_in_product);
                            self.pos.get_order().draft = false;
                            self.pos.push_order(self.pos.get_order()).then(function() {
                                self.gui.show_screen('receipt');
                                var args = self.pos.get_args_for_clocking().concat(true);
                                rpc.query({
                                    model: 'pos.session',
                                    method: self.pos.set_method_call_for_clocking(),
                                    args: args,
                                })
                                .then(function(users_logged) {
                                    self.pos.set_clock_values(users_logged);
                                    self.pos.clicked_on_clocked = false;
                                })
                            });
                        }
                    });
                } else {
                    self.pos.gui.show_popup("error", {
                        'title': _t("POS error"),
                        'body':  _t("Session has already been initialized Worked In."),
                    });
                    self.pos.clicked_on_clocked = false;
                    return false;
                }
            });
        }
    });

    var NumberPopupWidget = popups.include({
        show: function(options){
           this._super(options);
           $(document).off('keydown.productscreen', this.gui.screen_instances.products._onKeypadKeyDown);
        },
        close: function(){
            $(document).on('keydown.productscreen', this.gui.screen_instances.products._onKeypadKeyDown);
        },
    });
    var blocking_error_popup = popups.extend({
        template: 'BlockingErrorPopupWidget',
        show: function (options) {
            this._super(options);
        }
    });
    gui.define_popup({name:'blocking-error', widget: blocking_error_popup});

    screens.define_action_button({
        'name': 'work_in',
        'widget': work_in_button,
    });

    models.load_models({
        model: "pos.order",
        domain: function (self) { return [['config_id', '=', self.config.id]]; },
        fields: ['name', 'hash_chain'],
        order:  _.map(['date_order'], function (name) { return {name: name, asc: false}; }),
        limit: 1,  // TODO this works?
        loaded: function (self, params) {
            self.config.backend_sequence_number = self._extract_order_number(params);
            self.config.blackbox_most_recent_hash = self._get_hash_chain(params);
        }
    }, {
        'after': "pos.config"
    });

    // pro forma and regular orders share numbers, so we also need to check the pro forma orders and pick the max
    models.load_models({
        model: "pos.order_pro_forma",
        domain: function (self) { return [['config_id', '=', self.config.id]]; },
        fields: ['name', 'hash_chain'],
        order:  _.map(['date_order'], function (name) { return {name: name, asc: false}; }),
        limit: 1,
        loaded: function (self, params) {
            var pro_forma_number = self._extract_order_number(params);

            if (pro_forma_number > self.config.backend_sequence_number) {
                self.config.backend_sequence_number = pro_forma_number;
                self.config.most_recent_hash = self._get_hash_chain(params);
            }
        }
    }, {
        'after': "pos.order"
    });

    models.load_models({
        'model': "ir.model.data",
        'domain': ['|', ['name', '=', 'product_product_work_in'], ['name', '=', 'product_product_work_out']],
        'fields': ['name', 'res_id'],
        'loaded': function (self, params) {
            params.forEach(function (current, index, array) {
                if (current.name === "product_product_work_in") {
                    self.work_in_product = self.db.product_by_id[current['res_id']];
                } else if (current.name === "product_product_work_out") {
                    self.work_out_product = self.db.product_by_id[current['res_id']];
                }
            });
        }
    }, {
        'after': "product.product"
    });

    models.load_fields("res.users", "insz_or_bis_number");
    models.load_fields("account.tax", "identification_letter");
    models.load_fields("res.company", "street");
    models.load_fields("pos.session", "users_clocked_ids");

    return {
        'FDMPacketField': FDMPacketField,
        'FDMPacket': FDMPacket
    };
});
