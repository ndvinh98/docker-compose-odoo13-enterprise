(function (py) {

/**
 *
 * ´py.extract´ is an extension used only by AbstractEditComponent,
 * to parse the python values of the views so that it can be used
 * in javascript.
 *
 * The string converted into a dictionary in the case of options, and
 * a list of fieldName and non-usable rest (free code, functions,
 * calculations ...)
 *
 * eg:
 *
 *   t-esc="o.doc.get_currency()"
 *   t-options='{"field": o.doc.product_id, "toto": o.toto, "tata": "string"}'
 *   t-options='dict(field=o.doc.product_id, toto=o.toto, tata="string")'
 *   t-options-currency="o.doc.amount + 11.0"
 *
 * @see _splitRelatedValue in edit_components.js
 * @see _extractTOptions in edit_components.js
 *
 * Although it is functional, this must be redone, it is a poc.
 **/

var Python = function (expr, type, params) {
    this.expr = expr;
    this.params = params;
    if (type === 'call') {
        this.isCall = true;
    }
    if (type === 'field') {
        this.isField = true;
    }
    if (type === 'operator') {
        this.isOperator = true;
    }
};
Python.prototype.isPython = true;
Python.prototype.toString = function () {
    return this.expr + '';
};

function extract (expr) {
    switch (expr.id) {
        case '(name)':
            return new Python(expr.value, 'field');
        case '(string)':
        case '(number)':
        case '(constant)':
            switch (expr.value) {
                case 'None': return null;
                case 'False': return false;
                case 'True': return true;
            }
            return expr.value;
        case '(':
            var func = extract(expr.first);
            var error = false;
            if (func.isPython && func.expr === 'dict') {
                var obj = {};
                for(var l=0; l<expr.second.length; ++l) {
                    var kv = expr.second[l];
                    if (kv.id === "=") {
                        obj[extract(kv.first)] = extract(kv.second);
                    } else {
                        error = true;
                    }
                }
                if (!error) {
                    return obj;
                }
            }
            var array = [];
            for(var l=0; l<expr.second.length; ++l) {
                var kv = expr.second[l];
                array.push(extract(kv));
            }
            var res = new Python(func + '(' + array.join(', ') + ')', 'call', {
                object: func.isField ? func.params.slice(0, -1) : [],
                method: func.isField ? func.params[func.params.length-1] : func,
                args: array,
            });
            if (error) {
                throw new Error('SyntaxError: ' + res);
            }
            return res;
        case '[':
            if (expr.second) {
                var value = extract(expr.first);
                var attribute = extract(expr.second);
                return new Python(value + '[' + attribute + ']', 'attribute', {
                    value: value,
                    attribute: attribute,
                });
            }
            var array = [];
            for(var l=0; l<expr.first.length; ++l) {
                array.push(extract(expr.first[l]));
            }
            return array;
        case '{':
            var obj = {};
            for(var l=0; l<expr.first.length; ++l) {
                var kv = expr.first[l];
                obj[extract(kv[0])] = extract(kv[1]);
            }
            return obj;
        case '.':
            if (expr.second.id !== '(name)') {
                throw new Error('SyntaxError: ' + expr);
            }
            var params = [];
            var first = extract(expr.first);
            if (first.isAttribute) {
                params.push.apply(params, first.params);
            } else {
                params.push(first.expr);
            }
            var second = extract(expr.second);
            if (second.isAttribute) {
                params.push.apply(params, second.params);
            } else {
                params.push(second.expr);
            }
            return new Python(params.join('.'), 'field', params);
        case '=':
            return extract(expr.first) + '=' + extract(expr.second);
        case '(comparator)':
            var string = '';
            var values = [];
            for(var l=0; l<expr.expressions.length; ++l) {
                var value = extract(expr.expressions[l]);
                values.push(value);
                if (l > 0) {
                    string += expr.operators[l-1];
                }
                string += value;
            }
            return new Python(string, 'operator', {
                operators: expr.operators,
                values: values,
            });
    }
}
py.extract = function (str) {
    return extract(py.parse(py.tokenize(str)));
};


})(typeof exports === 'undefined' ? py : exports);