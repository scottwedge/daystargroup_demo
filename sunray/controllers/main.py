# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request
from odoo.addons.website_form.controllers.main import WebsiteForm

class WebsiteForm(WebsiteForm):
    
    @http.route('/vendor/information',type='http', auth="public", website=True)
    def vendor_form(self, **kw):
        country_id = http.request.env['res.country'].sudo().search([])
        return http.request.render("sunray.vendor_information", {'country_id':country_id})
    
    @http.route('/customer/information',type='http', auth="public", website=True)
    def customer_form(self, **kw):
        country_id = http.request.env['res.country'].sudo().search([])
        return http.request.render("sunray.customer_information", {})
    
    @http.route('/contact/information',type='http', auth="public", website=True)
    def customer_form(self, **kw):
        return http.request.render("sunray.contact_information", {})
    
    @http.route('/website_form/<string:model_name>', type='http', auth="public", methods=['POST'], website=True)
    def website_form(self, model_name, **kwargs):
        return super(WebsiteForm, self).website_form(model_name, **kwargs)