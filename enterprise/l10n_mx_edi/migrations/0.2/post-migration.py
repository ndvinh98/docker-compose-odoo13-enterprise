from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    l10n_mx_edi_add_fuel_product_sat_codes(cr)


def l10n_mx_edi_add_fuel_product_sat_codes(cr):
    """These fuel codes were added in the `l10n_mx_edi.product.sat.code.csv` file
    but that file is loaded only when the `l10n_mx_edi` module is installed (by hook).
    Because of that, if the module was already installed when the patch was applied,
    they weren't added, so they need to be added manually."""

    env = api.Environment(cr, SUPERUSER_ID, {})
    field_names = ['id', 'code', 'name', 'applies_to', 'active']
    new_fuel_sat_codes = [
        ['prod_code_sat_15111512', '15111512', 'Gas natural', 'product', '1'],
        ['prod_code_sat_15101514', '15101514',
         'Gasolina regular menor a 91 octanos', 'product', '1'],
        ['prod_code_sat_15101515', '15101515',
         'Gasolina premium mayor o igual a 91 octanos', 'product', '1']
    ]
    ctx = {'current_module': 'l10n_mx_edi', 'noupdate': True}
    env['l10n_mx_edi.product.sat.code'].with_context(ctx).load(
        field_names, new_fuel_sat_codes)
