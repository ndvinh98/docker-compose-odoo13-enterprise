# -*- coding: utf-8 -*-
import logging
import os

from lxml import etree

from odoo.loglevels import ustr
from odoo.tools import misc, view_validation
from odoo.modules.module import get_resource_path

_logger = logging.getLogger(__name__)

_gantt_validator = None


@view_validation.validate('gantt')
def schema_gantt(arch, **kwargs):
    """ Check the gantt view against its schema

    :type arch: etree._Element
    """
    global _gantt_validator

    if _gantt_validator is None:
        with misc.file_open(os.path.join('web_gantt', 'views', 'gantt.rng')) as f:
            # gantt.rng needs to include common.rng from the `base/rng/` directory. The idea
            # here is to set the base url of lxml lib in order to load relative file from the
            # `base/rng` directory.
            base_url = os.path.join(get_resource_path('base', 'rng'), '')
            _gantt_validator = etree.RelaxNG(etree.parse(f, base_url=base_url))

    if _gantt_validator.validate(arch):
        return True

    for error in _gantt_validator.error_log:
        _logger.error(ustr(error))
    return False
