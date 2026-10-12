from . import models


def ks_dna_uninstall_hook(env):
    for rec in env['ks_dashboard_ninja.item'].search([]):
        if rec.ks_data_calculation_type == 'query':
            rec.unlink()
