#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail
# set -o xtrace

__dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__file="${__dir}/$(basename "${BASH_SOURCE[0]}")"
__base="$(basename ${__file} .sh)"

function print0_files {
    find . -name "${1}" -print0
}

function python_files {
    print0_files "*.py"
}

function js_files {
    print0_files "*.js"
}

echo "Clearing previous build..."
rm -rf "${__dir}/pos_blackbox_be"

# don't compile manifest file because it is used by Odoo to
# determine whether a directory contains a module or not.
echo "Copying over files..."
rsync -a --exclude '*.pyc' --exclude tools --exclude __manifest__.py "${__dir}/../" "${__dir}/pos_blackbox_be"

echo "Compiling Python..."
python_files | xargs -0 python3 -m py_compile

echo "Deleting Python source..."
python_files | xargs -0 rm

# move over uncompiled manifest file
rsync -a "${__dir}/../__manifest__.py" "${__dir}/pos_blackbox_be/"

# sudo npm install -g minifier
echo "Obfuscating JS..."
js_files | xargs -n 1 -0 minify --template {{filename}}.js

# boot.js scans string representations of functions for the substring
# 'require' so we have to make sure that that doesn't get renamed. The
# minifier will put all require related stuff on the first line which
# means we can figure out what they translated 'require' to and
# replace it back.
to_replace=$(head -n 1 "${__dir}/pos_blackbox_be/static/src/js/pos_blackbox_be.js" | sed 's/.*function(\(.*\)){.*/\1/')

echo "replacing ${to_replace} with require..."
# replace require argument name
sed -i "1 s/(${to_replace})/(require)/g" "${__dir}/pos_blackbox_be/static/src/js/pos_blackbox_be.js"
# replace calls to require
sed -i "1 s/=${to_replace}(/=require(/g" "${__dir}/pos_blackbox_be/static/src/js/pos_blackbox_be.js"
