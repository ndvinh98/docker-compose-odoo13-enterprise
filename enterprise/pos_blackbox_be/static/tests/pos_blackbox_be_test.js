odoo.define_section('pos_blackbox_be.Order', ['point_of_sale.models'], function (test, mock) {
    function mock_pos() {
        var pos = {
            'pos_session': {
                'id': 1
            },
            'db': {
                'save_unpaid_order': function () {}
            },
            'currency': {
                'rounding': 0.01
            },
            'company': {
                'tax_calculation_rounding_method': ""
            },
            'config': {
                'id': 1,
                'blackbox_sequence_id': 1
            },
            'taxes_by_id': [
                {},
                {'amount': 21, 'identification_letter': "A"}, // type A
                {'amount': 12, 'identification_letter': "B"}, // type B
                {'amount':  6, 'identification_letter': "C"}, // type C
                {'amount':  0, 'identification_letter': "D"}  // type D
            ],
            'units_by_id': [{
                "name": "Units",
                "factor_inv": 1,
                "rounding": 0.001,
                "active": true,
                "factor": 1,
                "uom_type": "reference",
                "display_name": "Units",
                "category_id": [1, "Unit"],
                "id": 0,
                "groupable": false,
                "is_unit": true
            }, {
                "name": "g",
                "factor_inv": 0.001,
                "rounding": 0.01,
                "active": true,
                "factor": 1000,
                "uom_type": "smaller",
                "display_name": "g",
                "category_id": [2, "Weight"],
                "id": 1,
                "groupable": false,
                "is_unit": false
            }, {
                "name": "kg",
                "factor_inv": 1,
                "rounding": 0.001,
                "active": true,
                "factor": 1,
                "uom_type": "reference",
                "display_name": "kg",
                "category_id": [2, "Weight"],
                "id": 2,
                "groupable": false,
                "is_unit": false
            }, {
                "name": "lb(s)",
                "factor_inv": 0.45359290943563974,
                "rounding": 0.01,
                "active": true,
                "factor": 2.20462,
                "uom_type": "smaller",
                "display_name": "lb(s)",
                "category_id": [2, "Weight"],
                "id": 3,
                "groupable": false,
                "is_unit": false
            }, {
                "name": "oz(s)",
                "factor_inv": 0.02834949254408346,
                "rounding": 0.01,
                "active": true,
                "factor": 35.274,
                "uom_type": "smaller",
                "display_name": "oz(s)",
                "category_id": [2, "Weight"],
                "id": 4,
                "groupable": false,
                "is_unit": false
            }, {
                "name": "t",
                "factor_inv": 1000,
                "rounding": 0.01,
                "active": true,
                "factor": 0.001,
                "uom_type": "bigger",
                "display_name": "t",
                "category_id": [2, "Weight"],
                "id": 5,
                "groupable": false,
                "is_unit": false
            }, {
                "name": "Liter(s)",
                "factor_inv": 1,
                "rounding": 0.01,
                "active": true,
                "factor": 1,
                "uom_type": "reference",
                "display_name": "Liter(s)",
                "category_id": [3, "Volume"],
                "id": 6,
                "groupable": false,
                "is_unit": false
            }, {
                "name": "Milliliter(s)",
                "factor_inv": 0.001,
                "rounding": 0.01,
                "active": true,
                "factor": 1000,
                "uom_type": "smaller",
                "display_name": "Milliliter(s)",
                "category_id": [3, "Volume"],
                "id": 7,
                "groupable": false,
                "is_unit": false
            }]
        };

        pos.taxes = _.map(pos.taxes_by_id, function (tax, id) {
            return {'id': id, 'amount': tax.amount, 'identification_letter': tax.identification_letter};
        });

        return pos;
    }

    function mock_product(name, price, quantity, tax_id, uom_id) {
        var product = {
            'display_name': name,
            'price': price,
            'list_price': price,
            'taxes_id': [tax_id],
            'uom_id': uom_id
        };

        return product;
    }

    function mock_order_line(models) {
        var attrs = {};
        var options = {
            'product': mock_product("name", 1, 1, 1),
            'pos': mock_pos()
        };

        var mock_order_line = new models.Orderline(attrs, options);

        return mock_order_line;
    }

    function mock_order(models) {
        var mock_order = new models.Order({}, {
            'pos': mock_pos()
        });

        return mock_order;
    }

    function add_order_line(order, name, price, quantity, tax_id, uom_id) {
        var product = mock_product(name, price, quantity, tax_id, uom_id);
        var options = {
            'quantity': quantity
        };

        order.add_product(product, options);
    }

    // allowed range of DATA is
    // 0x20 <= byte <= 0x7E
    function test_data_range(data) {
        // todo
    }

    test('hash and sign data replace', function (assert, models) {
        var order_line = mock_order_line(models);

        assert.strictEqual(order_line._replace_hash_and_sign_chars(""), "");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("ABC"), "ABC");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("0123456789"), "0123456789");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("2.2"), "2.2");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("abcdef  ghijkl"), "ABCDEF  GHIJKL");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("AaA"), "AAA");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("ÄÅÂÁÀâäáàã"), "AAAAAAAAAA");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("Ææ"), "AEAE");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("ß"), "SS");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("çÇ"), "CC");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("ÎÏÍÌïîìí"), "IIIIIIII");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("€"), "E");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("ÊËÉÈêëéè"), "EEEEEEEE");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("ÛÜÚÙüûúù"), "UUUUUUUU");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("ÔÖÓÒöôóò"), "OOOOOOOO");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("Œœ"), "OEOE");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("ñÑ"), "NN");
        assert.strictEqual(order_line._replace_hash_and_sign_chars("ýÝÿ"), "YYY");
    });

    test('hash and sign data filter', function (assert, models) {
        var order_line = mock_order_line(models);

        assert.strictEqual(order_line._filter_allowed_hash_and_sign_chars(""), "");
        assert.strictEqual(order_line._filter_allowed_hash_and_sign_chars("ABC"), "ABC");
        assert.strictEqual(order_line._filter_allowed_hash_and_sign_chars("0123456789"), "0123456789");
        assert.strictEqual(order_line._filter_allowed_hash_and_sign_chars("abcdef"), "");
        assert.strictEqual(order_line._filter_allowed_hash_and_sign_chars("ÄÅÂÁÀâäáàãÆæßçÇÎÏÍÌïîìí€ÊËÉÈêëéèÛÜÚÙüûúùÔÖÓÒöôóòŒœñÑýÝÿ"), "");
        assert.strictEqual(order_line._filter_allowed_hash_and_sign_chars("AaA"), "AA");
        assert.strictEqual(order_line._filter_allowed_hash_and_sign_chars("A  A"), "AA");
    });

    test('_get_plu_amount', function (assert, models) {
        var order = mock_order(models);

        add_order_line(order, "name", 0, 0, 1, [0, "Unit"]);
        assert.strictEqual(order.get_last_orderline()._get_amount_for_plu(), 0);

        add_order_line(order, "name", 0, 100, 1, [0, "Unit"]);
        assert.strictEqual(order.get_last_orderline()._get_amount_for_plu(), 100);

        add_order_line(order, "name", 0, 0, 1, [1, "g"]);
        assert.strictEqual(order.get_last_orderline()._get_amount_for_plu(), 0);

        add_order_line(order, "name", 0, 100, 1, [1, "g"]);
        assert.strictEqual(order.get_last_orderline()._get_amount_for_plu(), 100);

        add_order_line(order, "name", 0, 0, 1, [2, "kg"]);
        assert.strictEqual(order.get_last_orderline()._get_amount_for_plu(), 0);

        add_order_line(order, "name", 0, 100, 1, [2, "kg"]);
        assert.strictEqual(order.get_last_orderline()._get_amount_for_plu(), 100000);

        add_order_line(order, "name", 0, 1, 1, [7, "Milliliter(s)"]);
        assert.strictEqual(order.get_last_orderline()._get_amount_for_plu(), 1);

        add_order_line(order, "name", 0, 1, 1, [6, "Liter(s)"]);
        assert.strictEqual(order.get_last_orderline()._get_amount_for_plu(), 1000);

        add_order_line(order, "name", 0, 23, 1, [3, "lb(s)"]);
        assert.strictEqual(Math.floor(order.get_last_orderline()._get_amount_for_plu()), 10432);
    });

    test('_prepare_number_for_plu amount', function (assert, models) {
        var order_line = mock_order_line(models);

        // values represent grams
        assert.strictEqual(order_line._prepare_number_for_plu(0, 4), "0000");
        assert.strictEqual(order_line._prepare_number_for_plu(-0, 4), "0000");
        assert.strictEqual(order_line._prepare_number_for_plu(1, 4), "0001");
        assert.strictEqual(order_line._prepare_number_for_plu(1234, 4), "1234");
        assert.strictEqual(order_line._prepare_number_for_plu(-1234, 4), "1234");
        assert.strictEqual(order_line._prepare_number_for_plu(123456, 4), "3456");
        assert.strictEqual(order_line._prepare_number_for_plu(-123456, 4), "3456");
        assert.strictEqual(order_line._prepare_number_for_plu(0.527, 4), "0001");
        assert.strictEqual(order_line._prepare_number_for_plu(3.14159265359, 4), "0003");
        assert.strictEqual(order_line._prepare_number_for_plu(-3.14159265359, 4), "0003");
        assert.strictEqual(order_line._prepare_number_for_plu(0.12, 4), "0000");
        assert.strictEqual(order_line._prepare_number_for_plu(-0.12, 4), "0000");
    });

    test('_prepare_number_for_plu price', function (assert, models) {
        var order_line = mock_order_line(models);

        // values represent eurocent
        assert.strictEqual(order_line._prepare_number_for_plu(0, 8), "00000000");
        assert.strictEqual(order_line._prepare_number_for_plu(-0, 8), "00000000");
        assert.strictEqual(order_line._prepare_number_for_plu(100, 8), "00000100");
        assert.strictEqual(order_line._prepare_number_for_plu(-100, 8), "00000100");
        assert.strictEqual(order_line._prepare_number_for_plu(0.01, 8), "00000000");
        assert.strictEqual(order_line._prepare_number_for_plu(-0.01, 8), "00000000");
        assert.strictEqual(order_line._prepare_number_for_plu(123400, 8), "00123400");
        assert.strictEqual(order_line._prepare_number_for_plu(-123400, 8), "00123400");
        assert.strictEqual(order_line._prepare_number_for_plu(123412.3, 8), "00123412");
        assert.strictEqual(order_line._prepare_number_for_plu(-123412.3, 8), "00123412");
        assert.strictEqual(order_line._prepare_number_for_plu(10000000, 8), "10000000");
        assert.strictEqual(order_line._prepare_number_for_plu(-10000000, 8), "10000000");
    });

    test('_prepare_description_for_plu', function(assert, models) {
        var order_line = mock_order_line(models);

        assert.strictEqual(order_line._prepare_description_for_plu(""), "                    ");
        assert.strictEqual(order_line._prepare_description_for_plu("a"), "A                   ");
        assert.strictEqual(order_line._prepare_description_for_plu("     "), "                    ");
        assert.strictEqual(order_line._prepare_description_for_plu("product name"), "PRODUCTNAME         ");
        assert.strictEqual(order_line._prepare_description_for_plu("this is longer than the allowed 20 characters"), "THISISLONGERTHANTHEA");
    });

    test('hash order empty', function (assert, models) {
        var order = mock_order(models);

        assert.strictEqual(order._hash_and_sign_string(), "", "_hash_and_sign_string of empty order");
        assert.strictEqual(order.calculate_hash(), "da39a3ee5e6b4b0d3255bfef95601890afd80709", "calculate_hash of empty order");
    });

    test('hash order 1', function (assert, models) {
        var order = mock_order(models);

        add_order_line(order, "Soda LIGHT 33 CL.", 2.20, 3, 1, [0, "Unit"]);
        add_order_line(order, "Spaghetti Bolognaise (KLEIN)", 5.00, 2, 2, [0, "Unit"]);
        add_order_line(order, "Salad Bar (kg)", 16.186, 0.527, 2, [2, "kg"]);
        add_order_line(order, "Steak Haché", 14.50, 1, 2, [0, "Unit"]);
        add_order_line(order, "Koffie verkeerd medium", 3.00, 2, 1, [0, "Unit"]);
        add_order_line(order, "Dame Blanche", 7.00, 1, 2, [0, "Unit"]);
        add_order_line(order, "Soda LIGHT 33 CL.", -2.20, -1, 1, [0, "Unit"]);
        add_order_line(order, "Huiswijn (liter)", 10.00, 1.25, 1, [6, "Liter(s)"]);

        assert.strictEqual(order._hash_and_sign_string(),
"0003SODALIGHT33CL       00000660A\
0002SPAGHETTIBOLOGNAISEK00001000B\
0527SALADBARKG          00000853B\
0001STEAKHACHE          00001450B\
0002KOFFIEVERKEERDMEDIUM00000600A\
0001DAMEBLANCHE         00000700B\
0001SODALIGHT33CL       00000220A\
1250HUISWIJNLITER       00001250A");
        assert.strictEqual(order.calculate_hash(), "bd532992502a62c40a741ec76423198d88d5a4f3");
    });

    test('hash order 2', function (assert, models) {
        var order = mock_order(models);

        add_order_line(order, "DAGSOEP", 5, 1, 2, [0, "Unit"]);
        add_order_line(order, "SEIZOENSSUGGESTIE", 20, 1, 2, [0, "Unit"]);
        add_order_line(order, "CRÈME BRULÉE", 5, 1, 2, [0, "Unit"]);

        assert.strictEqual(order._hash_and_sign_string(),
"0001DAGSOEP             00000500B\
0001SEIZOENSSUGGESTIE   00002000B\
0001CREMEBRULEE         00000500B");
        assert.strictEqual(order.calculate_hash(), "046bfc9425c488b9fe31b78820c21a70ae28005a");
    });

    test('hash order 3', function (assert, models) {
        var order = mock_order(models);

        add_order_line(order, "DAGSOEP", 7, 1, 2, [0, "Unit"]);
        add_order_line(order, "SEIZOENSSUGGESTIE", 25, 1, 2, [0, "Unit"]);
        add_order_line(order, "CRÈME BRULÉE", 7, 1, 2, [0, "Unit"]);
        add_order_line(order, "KORTING LENTEMENU", -9, 1, 2, [0, "Unit"]);
        add_order_line(order, "LENTEMENU DRINKS", 10, 1, 1, [0, "Unit"]);

        assert.strictEqual(order._hash_and_sign_string(),
"0001DAGSOEP             00000700B\
0001SEIZOENSSUGGESTIE   00002500B\
0001CREMEBRULEE         00000700B\
0001KORTINGLENTEMENU    00000900B\
0001LENTEMENUDRINKS     00001000A");

        assert.strictEqual(order.calculate_hash(), "095452a3e62d36b5255b18b1070f6832f0c57a85");
    });
});

odoo.define_section('pos_blackbox_be.FDMPacket', ['pos_blackbox_be.pos_blackbox_be'], function (test, mock) {
    test('empty FDMPackets to_string', function (assert, blackbox) {
        var packet = new blackbox.FDMPacket();

        assert.strictEqual(packet.to_string(), "");

        packet.add_field(new blackbox.FDMPacketField("", 0, "", ""));
        assert.strictEqual(packet.to_string(), "");

        packet.add_field(new blackbox.FDMPacketField("", 0, "", "0"));
        assert.strictEqual(packet.to_string(), "");
    });

    test('filled FDMPackets to_string', function (assert, blackbox) {
        var packet = new blackbox.FDMPacket();

        packet.add_field(new blackbox.FDMPacketField("hello", 5, "world", ""));
        assert.strictEqual(packet.to_string(), "world");

        packet = new blackbox.FDMPacket();
        packet.add_field(new blackbox.FDMPacketField("pad", 5, "me", " "));
        assert.strictEqual(packet.to_string(), "   me");

        packet = new blackbox.FDMPacket();
        packet.add_field(new blackbox.FDMPacketField("pad", 10, "zeros", "0"));
        assert.strictEqual(packet.to_string(), "00000zeros");

        packet = new blackbox.FDMPacket();
        packet.add_field(new blackbox.FDMPacketField("hello", 5, "world", ""));
        packet.add_field(new blackbox.FDMPacketField("pad", 5, "me", " "));
        packet.add_field(new blackbox.FDMPacketField("pad", 10, "zeros", "0"));
        assert.strictEqual(packet.to_string(), "world   me00000zeros");
    });
});
