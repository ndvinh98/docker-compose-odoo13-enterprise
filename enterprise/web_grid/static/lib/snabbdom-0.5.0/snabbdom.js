odoo.define('snabbdom.vnode', function (require) {
    return function (sel, data, children, text, elm) {
        var key = data === undefined ? undefined : data.key;
        return {
            sel: sel,
            data: data,
            children: children,
            text: text,
            elm: elm,
            key: key
        };
    };
});

odoo.define('snabbdom.is', function (require) {
    return {
        array: Array.isArray,
        primitive: function (s) { return typeof s === 'string' || typeof s === 'number'; },
    };
});

odoo.define('snabbdom.h', function (require) {
    var VNode = require('snabbdom.vnode');
    var is = require('snabbdom.is');

    function addNS(data, children) {
        data.ns = 'http://www.w3.org/2000/svg';
        if (children !== undefined) {
            for (var i = 0; i < children.length; ++i) {
                addNS(children[i].data, children[i].children);
            }
        }
    }

    return function h(sel, b, c) {
        var data = {}, children, text, i;
        if (arguments.length === 3) {
            data = b;
            if (is.array(c)) { children = c; } else if (is.primitive(c)) { text = c; }
        } else if (arguments.length === 2) {
            if (is.array(b)) { children = b; } else if (is.primitive(b)) { text = b; } else { data = b; }
        }
        if (is.array(children)) {
            for (i = 0; i < children.length; ++i) {
                if (is.primitive(children[i])) children[i] = VNode(undefined, undefined, undefined, children[i]);
            }
        }
        if (sel[0] === 's' && sel[1] === 'v' && sel[2] === 'g') {
            addNS(data, children);
        }
        return VNode(sel, data, children, text, undefined);
    };
});

odoo.define('snabbdom.init', function (require) {
    'use strict';

    var VNode = require('snabbdom.vnode');
    var is = require('snabbdom.is');

    function isUndef(s) { return s === undefined; }

    function isDef(s) { return s !== undefined; }

    var emptyNode = VNode('', {}, [], undefined, undefined);

    function sameVnode(vnode1, vnode2) {
        return vnode1.key === vnode2.key && vnode1.sel === vnode2.sel;
    }

    function createKeyToOldIdx(children, beginIdx, endIdx) {
        var i, map = {}, key;
        for (i = beginIdx; i <= endIdx; ++i) {
            key = children[i].key;
            if (isDef(key)) map[key] = i;
        }
        return map;
    }

    var hooks = ['create', 'update', 'remove', 'destroy', 'pre', 'post'];

    function init(modules) {
        var i, j, cbs = {};

        for (i = 0; i < hooks.length; ++i) {
            cbs[hooks[i]] = [];
            for (j = 0; j < modules.length; ++j) {
                if (modules[j][hooks[i]] !== undefined) cbs[hooks[i]].push(modules[j][hooks[i]]);
            }
        }

        function emptyNodeAt(elm) {
            return VNode(elm.tagName.toLowerCase(), {}, [], undefined, elm);
        }

        function createRmCb(childElm, listeners) {
            return function () {
                if (--listeners === 0) {
                    var parent = childElm.parentElement;
                    parent.removeChild(childElm);
                }
            };
        }

        function createElm(vnode, insertedVnodeQueue) {
            var i, data = vnode.data;
            if (isDef(data)) {
                if (isDef(i = data.hook) && isDef(i = i.init)) {
                    i(vnode);
                    data = vnode.data;
                }
            }
            var elm, children = vnode.children, sel = vnode.sel;
            if (isDef(sel)) {
                // Parse selector
                var hashIdx = sel.indexOf('#');
                var dotIdx = sel.indexOf('.', hashIdx);
                var hash = hashIdx > 0 ? hashIdx : sel.length;
                var dot = dotIdx > 0 ? dotIdx : sel.length;
                var tag = hashIdx !== -1 || dotIdx !== -1 ? sel.slice(0, Math.min(hash, dot)) : sel;
                elm = vnode.elm = isDef(data) && isDef(i = data.ns) ? document.createElementNS(i, tag) : document.createElement(tag);
                if (hash < dot) elm.id = sel.slice(hash + 1, dot);
                if (dotIdx > 0) elm.className = sel.slice(dot + 1).replace(/\./g, ' ');
                if (is.array(children)) {
                    for (i = 0; i < children.length; ++i) {
                        elm.appendChild(createElm(children[i], insertedVnodeQueue));
                    }
                } else if (is.primitive(vnode.text)) {
                    elm.appendChild(document.createTextNode(vnode.text));
                }
                for (i = 0; i < cbs.create.length; ++i) cbs.create[i](emptyNode, vnode);
                i = vnode.data.hook; // Reuse variable
                if (isDef(i)) {
                    if (i.create) i.create(emptyNode, vnode);
                    if (i.insert) insertedVnodeQueue.push(vnode);
                }
            } else {
                elm = vnode.elm = document.createTextNode(vnode.text);
            }
            return vnode.elm;
        }

        function addVnodes(parentElm, before, vnodes, startIdx, endIdx, insertedVnodeQueue) {
            for (; startIdx <= endIdx; ++startIdx) {
                parentElm.insertBefore(createElm(vnodes[startIdx], insertedVnodeQueue), before);
            }
        }

        function invokeDestroyHook(vnode) {
            var i, j, data = vnode.data;
            if (isDef(data)) {
                if (isDef(i = data.hook) && isDef(i = i.destroy)) i(vnode);
                for (i = 0; i < cbs.destroy.length; ++i) cbs.destroy[i](vnode);
                if (isDef(i = vnode.children)) {
                    for (j = 0; j < vnode.children.length; ++j) {
                        invokeDestroyHook(vnode.children[j]);
                    }
                }
            }
        }

        function removeVnodes(parentElm, vnodes, startIdx, endIdx) {
            for (; startIdx <= endIdx; ++startIdx) {
                var i, listeners, rm, ch = vnodes[startIdx];
                if (isDef(ch)) {
                    if (isDef(ch.sel)) {
                        invokeDestroyHook(ch);
                        listeners = cbs.remove.length + 1;
                        rm = createRmCb(ch.elm, listeners);
                        for (i = 0; i < cbs.remove.length; ++i) cbs.remove[i](ch, rm);
                        if (isDef(i = ch.data) && isDef(i = i.hook) && isDef(i = i.remove)) {
                            i(ch, rm);
                        } else {
                            rm();
                        }
                    } else { // Text node
                        parentElm.removeChild(ch.elm);
                    }
                }
            }
        }

        function updateChildren(parentElm, oldCh, newCh, insertedVnodeQueue) {
            var oldStartIdx = 0, newStartIdx = 0;
            var oldEndIdx = oldCh.length - 1;
            var oldStartVnode = oldCh[0];
            var oldEndVnode = oldCh[oldEndIdx];
            var newEndIdx = newCh.length - 1;
            var newStartVnode = newCh[0];
            var newEndVnode = newCh[newEndIdx];
            var oldKeyToIdx, idxInOld, elmToMove, before;

            while (oldStartIdx <= oldEndIdx && newStartIdx <= newEndIdx) {
                if (isUndef(oldStartVnode)) {
                    oldStartVnode = oldCh[++oldStartIdx]; // Vnode has been moved left
                } else if (isUndef(oldEndVnode)) {
                    oldEndVnode = oldCh[--oldEndIdx];
                } else if (sameVnode(oldStartVnode, newStartVnode)) {
                    patchVnode(oldStartVnode, newStartVnode, insertedVnodeQueue);
                    oldStartVnode = oldCh[++oldStartIdx];
                    newStartVnode = newCh[++newStartIdx];
                } else if (sameVnode(oldEndVnode, newEndVnode)) {
                    patchVnode(oldEndVnode, newEndVnode, insertedVnodeQueue);
                    oldEndVnode = oldCh[--oldEndIdx];
                    newEndVnode = newCh[--newEndIdx];
                } else if (sameVnode(oldStartVnode, newEndVnode)) { // Vnode moved right
                    patchVnode(oldStartVnode, newEndVnode, insertedVnodeQueue);
                    parentElm.insertBefore(oldStartVnode.elm, oldEndVnode.elm.nextSibling);
                    oldStartVnode = oldCh[++oldStartIdx];
                    newEndVnode = newCh[--newEndIdx];
                } else if (sameVnode(oldEndVnode, newStartVnode)) { // Vnode moved left
                    patchVnode(oldEndVnode, newStartVnode, insertedVnodeQueue);
                    parentElm.insertBefore(oldEndVnode.elm, oldStartVnode.elm);
                    oldEndVnode = oldCh[--oldEndIdx];
                    newStartVnode = newCh[++newStartIdx];
                } else {
                    if (isUndef(oldKeyToIdx)) oldKeyToIdx = createKeyToOldIdx(oldCh, oldStartIdx, oldEndIdx);
                    idxInOld = oldKeyToIdx[newStartVnode.key];
                    if (isUndef(idxInOld)) { // New element
                        parentElm.insertBefore(createElm(newStartVnode, insertedVnodeQueue), oldStartVnode.elm);
                        newStartVnode = newCh[++newStartIdx];
                    } else {
                        elmToMove = oldCh[idxInOld];
                        patchVnode(elmToMove, newStartVnode, insertedVnodeQueue);
                        oldCh[idxInOld] = undefined;
                        parentElm.insertBefore(elmToMove.elm, oldStartVnode.elm);
                        newStartVnode = newCh[++newStartIdx];
                    }
                }
            }
            if (oldStartIdx > oldEndIdx) {
                before = isUndef(newCh[newEndIdx + 1]) ? null : newCh[newEndIdx + 1].elm;
                addVnodes(parentElm, before, newCh, newStartIdx, newEndIdx, insertedVnodeQueue);
            } else if (newStartIdx > newEndIdx) {
                removeVnodes(parentElm, oldCh, oldStartIdx, oldEndIdx);
            }
        }

        function patchVnode(oldVnode, vnode, insertedVnodeQueue) {
            var i, hook;
            if (isDef(i = vnode.data) && isDef(hook = i.hook) && isDef(i = hook.prepatch)) {
                i(oldVnode, vnode);
            }
            var elm = vnode.elm = oldVnode.elm, oldCh = oldVnode.children, ch = vnode.children;
            if (oldVnode === vnode) return;
            if (!sameVnode(oldVnode, vnode)) {
                var parentElm = oldVnode.elm.parentElement;
                elm = createElm(vnode, insertedVnodeQueue);
                parentElm.insertBefore(elm, oldVnode.elm);
                removeVnodes(parentElm, [oldVnode], 0, 0);
                return;
            }
            if (isDef(vnode.data)) {
                for (i = 0; i < cbs.update.length; ++i) cbs.update[i](oldVnode, vnode);
                i = vnode.data.hook;
                if (isDef(i) && isDef(i = i.update)) i(oldVnode, vnode);
            }
            if (isUndef(vnode.text)) {
                if (isDef(oldCh) && isDef(ch)) {
                    if (oldCh !== ch) updateChildren(elm, oldCh, ch, insertedVnodeQueue);
                } else if (isDef(ch)) {
                    if (isDef(oldVnode.text)) { elm.textContent = ''; }
                    addVnodes(elm, null, ch, 0, ch.length - 1, insertedVnodeQueue);
                } else if (isDef(oldCh)) {
                    removeVnodes(elm, oldCh, 0, oldCh.length - 1);
                } else if (isDef(oldVnode.text)) {
                    elm.textContent = '';
                }
            } else if (oldVnode.text !== vnode.text) {
                elm.textContent = vnode.text;
            }
            if (isDef(hook) && isDef(i = hook.postpatch)) {
                i(oldVnode, vnode);
            }
        }

        return function (oldVnode, vnode) {
            var i, elm, parent;
            var insertedVnodeQueue = [];
            for (i = 0; i < cbs.pre.length; ++i) cbs.pre[i]();

            if (isUndef(oldVnode.sel)) {
                oldVnode = emptyNodeAt(oldVnode);
            }

            if (sameVnode(oldVnode, vnode)) {
                patchVnode(oldVnode, vnode, insertedVnodeQueue);
            } else {
                elm = oldVnode.elm;
                parent = elm.parentElement;
                createElm(vnode, insertedVnodeQueue);

                if (parent !== null) {
                    parent.insertBefore(vnode.elm, elm.nextSibling);
                    removeVnodes(parent, [oldVnode], 0, 0);
                }
            }

            for (i = 0; i < insertedVnodeQueue.length; ++i) {
                insertedVnodeQueue[i].data.hook.insert(insertedVnodeQueue[i]);
            }
            for (i = 0; i < cbs.post.length; ++i) cbs.post[i]();
            return vnode;
        };
    }

    return init;
});

odoo.define('snabbdom.thunk', function (require) {
    var h = require('snabbdom.h');

    function copyToThunk(vnode, thunk) {
        thunk.elm = vnode.elm;
        vnode.data.fn = thunk.data.fn;
        vnode.data.args = thunk.data.args;
        thunk.data = vnode.data;
        thunk.children = vnode.children;
        thunk.text = vnode.text;
        thunk.elm = vnode.elm;
    }

    function init(thunk) {
        var i, cur = thunk.data;
        var vnode = cur.fn.apply(undefined, cur.args);
        copyToThunk(vnode, thunk);
    }

    function prepatch(oldVnode, thunk) {
        var i, old = oldVnode.data, cur = thunk.data, vnode;
        var oldArgs = old.args, args = cur.args;
        if (old.fn !== cur.fn || oldArgs.length !== args.length) {
            copyToThunk(cur.fn.apply(undefined, args), thunk);
        }
        for (i = 0; i < args.length; ++i) {
            if (oldArgs[i] !== args[i]) {
                copyToThunk(cur.fn.apply(undefined, args), thunk);
                return;
            }
        }
        copyToThunk(oldVnode, thunk);
    }

    return function (sel, key, fn, args) {
        if (args === undefined) {
            args = fn;
            fn = key;
            key = undefined;
        }
        return h(sel, {
            key: key,
            hook: {init: init, prepatch: prepatch},
            fn: fn,
            args: args
        });
    };

});

odoo.define('snabbdom.class', function (require) {
    function updateClass(oldVnode, vnode) {
        var cur, name, elm = vnode.elm, oldClass = oldVnode.data.class || {}, klass = vnode.data.class || {};
        for (name in oldClass) {
            if (!klass[name]) {
                elm.classList.remove(name);
            }
        }
        for (name in klass) {
            cur = klass[name];
            if (cur !== oldClass[name]) {
                elm.classList[cur ? 'add' : 'remove'](name);
            }
        }
    }

    return {create: updateClass, update: updateClass};
});

odoo.define('snabbdom.props', function (require) {
    function updateProps(oldVnode, vnode) {
        var key, cur, old, elm = vnode.elm, oldProps = oldVnode.data.props || {}, props = vnode.data.props || {};
        for (key in oldProps) {
            if (!props[key]) {
                delete elm[key];
            }
        }
        for (key in props) {
            cur = props[key];
            old = oldProps[key];
            if (old !== cur && (key !== 'value' || elm[key] !== cur)) {
                elm[key] = cur;
            }
        }
    }

    return {create: updateProps, update: updateProps};
});

odoo.define('snabbdom.attributes', function (require) {
    var booleanAttrs = [
        "allowfullscreen", "async", "autofocus", "autoplay", "checked",
        "compact", "controls", "declare", "default", "defaultchecked",
        "defaultmuted", "defaultselected", "defer", "disabled", "draggable",
        "enabled", "formnovalidate", "hidden", "indeterminate", "inert",
        "ismap", "itemscope", "loop", "multiple", "muted", "nohref",
        "noresize", "noshade", "novalidate", "nowrap", "open", "pauseonexit",
        "readonly", "required", "reversed", "scoped", "seamless", "selected",
        "sortable", "spellcheck", "translate", "truespeed", "typemustmatch",
        "visible"
    ];

    var booleanAttrsDict = {};
    for (var i = 0, len = booleanAttrs.length; i < len; i++) {
        booleanAttrsDict[booleanAttrs[i]] = true;
    }

    function updateAttrs(oldVnode, vnode) {
        var key, cur, old, elm = vnode.elm, oldAttrs = oldVnode.data.attrs || {}, attrs = vnode.data.attrs || {};

        // update modified attributes, add new attributes
        for (key in attrs) {
            cur = attrs[key];
            old = oldAttrs[key];
            if (old !== cur) {
                // TODO: add support to namespaced attributes (setAttributeNS)
                if (!cur && booleanAttrsDict[key])
                    elm.removeAttribute(key); else
                    elm.setAttribute(key, cur);
            }
        }
        //remove removed attributes
        // use `in` operator since the previous `for` iteration uses it (.i.e. add even attributes with undefined value)
        // the other option is to remove all attributes with value == undefined
        for (key in oldAttrs) {
            if (!(key in attrs)) {
                elm.removeAttribute(key);
            }
        }
    }

    return {create: updateAttrs, update: updateAttrs};
});

odoo.define('snabbdom.eventlistener', function (require) {

    function invokeHandler(handler, vnode, event) {
        if (typeof handler === "function") {
            // call function handler
            handler.call(vnode, event, vnode);
        }
        else if (typeof handler === "object") {
            // call handler with arguments
            if (typeof handler[0] === "function") {
                // special case for single argument for performance
                if (handler.length === 2) {
                    handler[0].call(vnode, handler[1], event, vnode);
                }
                else {
                    var args = handler.slice(1);
                    args.push(event);
                    args.push(vnode);
                    handler[0].apply(vnode, args);
                }
            }
            else {
                // call multiple handlers
                for (var i = 0; i < handler.length; i++) {
                    invokeHandler(handler[i]);
                }
            }
        }
    }
    function handleEvent(event, vnode) {
        var name = event.type, on = vnode.data.on;
        // call event handler(s) if exists
        if (on && on[name]) {
            invokeHandler(on[name], vnode, event);
        }
    }
    function createListener() {
        return function handler(event) {
            handleEvent(event, handler.vnode);
        };
    }
    function updateEventListeners(oldVnode, vnode) {
        var oldOn = oldVnode.data.on, oldListener = oldVnode.listener, oldElm = oldVnode.elm, on = vnode && vnode.data.on, elm = (vnode && vnode.elm), name;
        // optimization for reused immutable handlers
        if (oldOn === on) {
            return;
        }
        // remove existing listeners which no longer used
        if (oldOn && oldListener) {
            // if element changed or deleted we remove all existing listeners unconditionally
            if (!on) {
                for (name in oldOn) {
                    // remove listener if element was changed or existing listeners removed
                    oldElm.removeEventListener(name, oldListener, false);
                }
            }
            else {
                for (name in oldOn) {
                    // remove listener if existing listener removed
                    if (!on[name]) {
                        oldElm.removeEventListener(name, oldListener, false);
                    }
                }
            }
        }
        // add new listeners which has not already attached
        if (on) {
            // reuse existing listener or create new
            var listener = vnode.listener = oldVnode.listener || createListener();
            // update vnode for listener
            listener.vnode = vnode;
            // if element changed or added we add all needed listeners unconditionally
            if (!oldOn) {
                for (name in on) {
                    // add listener if element was changed or new listeners added
                    elm.addEventListener(name, listener, false);
                }
            }
            else {
                for (name in on) {
                    // add listener if new listener added
                    if (!oldOn[name]) {
                        elm.addEventListener(name, listener, false);
                    }
                }
            }
        }
    }

    return {
        create: updateEventListeners,
        update: updateEventListeners,
        destroy: updateEventListeners
    }

});

odoo.define('snabbdom.patch', function (require) {
    // don't load styles or event listeners by default
    return require('snabbdom.init')([
        require('snabbdom.class'),
        require('snabbdom.props'),
        require('snabbdom.attributes'),
        require('snabbdom.eventlistener')
    ]);
});
