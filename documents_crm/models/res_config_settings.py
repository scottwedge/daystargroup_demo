# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def _get_default_project_folder(self):
        folder_id = self.env.user.company_id.project_folder
        if folder_id.exists():
            return folder_id
        return False

    dms_crm_settings = fields.Boolean(related='company_id.dms_crm_settings', readonly=False,
                                          default=lambda self: self.env.user.company_id.dms_crm_settings,
                                          string="CRM Folder")
    crm_folder = fields.Many2one('documents.folder', related='company_id.crm_folder', readonly=False,
                                     default=_get_default_crm_folder,
                                     string="CRM default folder")
    crm_tags = fields.Many2many('documents.tag', 'crm_tags_table',
                                    related='company_id.crm_tags', readonly=False,
                                    default=lambda self: self.env.user.company_id.crm_tags.ids,
                                    string="CRM Tags")


