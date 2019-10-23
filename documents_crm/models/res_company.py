# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _


class ResCompany(models.Model):
    _inherit = "res.company"

    dms_crm_settings = fields.Boolean()
    crm_folder = fields.Many2one('documents.folder',
                                     default=lambda self: self.env.ref('documents.documents_internal_folder',
                                                                       raise_if_not_found=False))
    crm_tags = fields.Many2many('documents.tag', 'crm_tags_table')

    @api.multi
    def write(self, values):
        for company in self:
            if not company.dms_project_settings and values.get('dms_crm_settings'):
                attachments = self.env['ir.attachment'].search([('folder_id', '=', False),
                                                                ('res_model', 'in', ['crm.lead',
                                                                                     'sale.order'])])
                if attachments.exists():
                    vals = {}
                    if values.get('crm_folder'):
                        vals['folder_id'] = values['crm_folder']
                    elif company.project_folder:
                        vals['folder_id'] = company.crm_folder.id

                    if values.get('crm_tags'):
                        vals['tag_ids'] = values['crm_tags']
                    elif company.project_tags:
                        vals['tag_ids'] = [(6, 0, company.project_tags.ids)]
                    if len(vals):
                        attachments.write(vals)

        return super(ResCompany, self).write(values)
