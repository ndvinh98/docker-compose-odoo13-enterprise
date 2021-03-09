# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from os.path import join, dirname, realpath

from odoo import tools

_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    _load_product_sat_catalog(cr, registry)
    _assign_codes_uom(cr, registry)
    _load_locality_sat_catalog(cr, registry)
    _load_tariff_fraction_catalog(cr, registry)


def uninstall_hook(cr, registry):
    cr.execute("DELETE FROM l10n_mx_edi_product_sat_code;")
    cr.execute("DELETE FROM ir_model_data WHERE model='l10n_mx_edi.product.sat.code';")
    cr.execute("DELETE FROM ir_model_data WHERE model='l10n_mx_edi.tariff.fraction';")

def _load_product_sat_catalog(cr, registry):
    """Import CSV data as it is faster than xml and because we can't use
    noupdate anymore with csv"""
    csv_path = join(dirname(realpath(__file__)), 'data',
                    'l10n_mx_edi.product.sat.code.csv')
    csv_file = open(csv_path, 'rb')
    cr.copy_expert(
        """COPY l10n_mx_edi_product_sat_code(code, name, applies_to, active)
           FROM STDIN WITH DELIMITER '|'""", csv_file)
    # Create xml_id, to allow make reference to this data
    cr.execute(
        """INSERT INTO ir_model_data
           (name, res_id, module, model, noupdate)
           SELECT concat('prod_code_sat_', code), id, 'l10n_mx_edi', 'l10n_mx_edi.product.sat.code', true
           FROM l10n_mx_edi_product_sat_code """)


def _assign_codes_uom(cr, registry):
    """Assign the codes in UoM of each data, this is here because the data is
    created in the last method"""
    tools.convert.convert_file(
        cr, 'l10n_mx_edi', 'data/product_data.xml', None, mode='init',
        kind='data')


def _load_locality_sat_catalog(cr, registry):
    """Import CSV data as it is faster than xml and because we can't use
    noupdate anymore with csv"""

    # Triggers temporarily added to find the ids of many2one fields
    cr.execute(
        """CREATE OR REPLACE FUNCTION l10n_mx_edi_locality()
            RETURNS trigger AS $locality$
            DECLARE
                new_array text[];
            BEGIN
                new_array := (SELECT regexp_split_to_array(NEW.name, E'--+'));
                NEW.name := new_array[1];
                NEW.state_id := (SELECT res_id FROM ir_model_data
                    WHERE name=new_array[2] and model='res.country.state');
                NEW.country_id := (SELECT res_id FROM ir_model_data
                    WHERE name='mx' and model='res.country');
                RETURN NEW;
            END;
           $locality$ LANGUAGE plpgsql;
           CREATE TRIGGER l10n_mx_edi_locality BEFORE INSERT
               ON l10n_mx_edi_res_locality
               FOR EACH ROW EXECUTE PROCEDURE l10n_mx_edi_locality();
           CREATE TRIGGER l10n_mx_edi_locality BEFORE INSERT ON res_city
               FOR EACH ROW EXECUTE PROCEDURE l10n_mx_edi_locality();
        """)

    # Read file and copy data from file
    csv_path = join(dirname(realpath(__file__)), 'data',
                    'l10n_mx_edi.res.locality.csv')
    csv_file = open(csv_path, 'rb')
    cr.copy_from(csv_file, 'l10n_mx_edi_res_locality', sep='|',
                 columns=('code', 'name'))

    csv_path = join(dirname(realpath(__file__)), 'data',
                    'res.city.csv')
    csv_file = open(csv_path, 'rb')
    cr.copy_from(
        csv_file, 'res_city', sep='|', columns=('l10n_mx_edi_code', 'name'))

    cr.execute(
        """delete from res_city where l10n_mx_edi_code is null and name in (select name from res_city where l10n_mx_edi_code is not null)""")

    # Remove triggers
    cr.execute(
        """DROP TRIGGER IF EXISTS l10n_mx_edi_locality
               ON l10n_mx_edi_res_locality;
           DROP TRIGGER IF EXISTS l10n_mx_edi_locality ON res_city;""")

    # Create xml_id, to allow make reference to this data
    # Locality
    cr.execute("""
               INSERT INTO ir_model_data (name, res_id, module, model, noupdate)
               SELECT
               ('res_locality_mx_' || lower(state.code) || '_' || loc.code),
                    loc.id, 'l10n_mx_edi', 'l10n_mx_edi.res.locality', true
               FROM l10n_mx_edi_res_locality AS loc, res_country_state AS state
               WHERE state.id = loc.state_id
               AND (('res_locality_mx_' || lower(state.code) || '_' || loc.code), 'l10n_mx_edi') not in (select name, module from ir_model_data)""")
    # City or Municipality
    cr.execute("""
               INSERT INTO ir_model_data (name, res_id, module, model, noupdate)
               SELECT ('res_city_mx_' || lower(state.code)
               || '_' || city.l10n_mx_edi_code),
                city.id, 'l10n_mx_edi', 'res.city', true
               FROM  res_city AS city, res_country_state AS state
               WHERE state.id = city.state_id AND city.country_id = (
                SELECT id FROM res_country WHERE code = 'MX')
                AND (('res_city_mx_' || lower(state.code)|| '_' || city.l10n_mx_edi_code), 'l10n_mx_edi') not in (select name,  module from ir_model_data)
                """)


def _load_tariff_fraction_catalog(cr, registry):
    """Import CSV data as it is faster than xml and because we can't use
    noupdate anymore with csv"""
    csv_path = join(dirname(realpath(__file__)), 'data',
                    'l10n_mx_edi.tariff.fraction.csv')
    csv_file = open(csv_path, 'rb')
    cr.copy_expert(
        """COPY l10n_mx_edi_tariff_fraction(code, name, uom_code)
           FROM STDIN WITH DELIMITER '|'""", csv_file)
    # Create xml_id, to allow make reference to this data
    cr.execute(
        """UPDATE l10n_mx_edi_tariff_fraction
        SET active = 't'""")
    cr.execute(
        """INSERT INTO ir_model_data
           (name, res_id, module, model)
           SELECT concat('tariff_fraction_', code), id,
                'l10n_mx_edi_external_trade', 'l10n_mx_edi.tariff.fraction'
           FROM l10n_mx_edi_tariff_fraction """)
