odoo.define('website_crm_score.filters', function (require) {
"use strict";

var AbstractField = require('web.AbstractField');
var field_registry = require('web.field_registry');


var Filters = AbstractField.extend({
    /**
        bnf grammar of a filter:
            <filter>    ::= <expr>
            <expr>      ::= <tuple> | '!' <expr> | <bin_op> <expr> <expr>
            <bin_op>    ::= '&' | '|'
            <tuple>     ::= '(' <field_name> ',' <operator> ',' <field_value> ')'
            <operator>  ::= '=' | '!=' | '<=' | '<' | '>' | '>=' | '=?' |
                            '=like' | '=ilike' | 'like' | 'not like' |
                            'ilike' | 'not ilike' | 'in' | 'not in' | 'child_of'
        some operators are negative
    */
    NEG_OP: ['!=', 'not like', 'not ilike', 'not in'],
    MAX_LEN: 5,
    render: function() {
        var val = this.value;
        if (val) {
                // This widget is temporary
                // To keep only while the widget domain filter doesn't exist !

                // Ugly hack to have (more) python domains which can be evaluated in JS
                val = val.replace('(', '[').replace(')', ']').replace('False', 'false').replace('True', 'true');
                try {
                    val = eval(val);
                }
                catch(err) {
                    // don't block UI if domain is not evaluable in JS
                    console.debug(err.message);
                    val = [['error','=', err.message]];
                }
            var $span;
            if (val.length <= this.MAX_LEN) {
                var i = 0;
                while (i < val.length) {
                    var res = this.interpret(val, i);
                    i = res[0];
                    $span = res[1];
                    this.$el.append($span);
                }
            }
            else {
                $span = '<span class="badge" style="background-color:#fce9e9;">Domain too big<span>';
                this.$el.append($span);
            }
        }
    },

    interpret: function(val, i) {
        var a = val[i];
        var span;
        if(typeof a !== 'string'){
            // a is a tuple (field, op, value)
            var tag = a[0]; // field name
            var tip = a[2]; // field value
            if (this.NEG_OP.indexOf(a[1]) !== -1){
                // op in NEG_OP
                tip = 'not ' + tip;
            }
            span = '<span class="badge" title="' + tip + '">'+ tag +'</span>';
            return [i+1, span];
        }
        else if (a === '!'){
            var res = this.interpret(val, i+1);
            span = '<span class="badge">!</span>' + res[1];
            return [res[0], span];
        }
        else {
            // binary operator
            return this.binary_operator(val, i);
        }
        return [i+1, ''];
    },

    binary_operator: function(val, i) {
        var resA = this.interpret(val, i+1);
        var resB = this.interpret(val, resA[0]);
        var label = '';
        var op = '';
        if (val[i] === '|') {
            label = 'badge-success';
            op = ' or ';
        }
        else if (val[i] === '&') {
            label = 'badge-primary';
            op = ' and ';
        }
        var span = resA[1] + resB[1];
        return [resB[0], span];
    }
});

field_registry.add('filters', Filters);

});
