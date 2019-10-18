# -*- coding: utf-8 -*-

import datetime

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from ast import literal_eval
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo import api, fields, models, _

class Lead(models.Model):
    _name = "crm.lead"
    _inherit = 'crm.lead'
    
    type_of_offer = fields.Selection([('saas', 'SaaS'), ('pass', 'PaaS'),('battery', 'Battery'),
                                      ('pass_diesel', 'PaaS Diesel'),('lease', 'Lease to'), ('own', 'Own'),
                                      ('sale', 'Sale')], string='Type of Offer', required=False,default='saas')
    size = fields.Float(string='Size (kWp)')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('approve', 'Approved'),
        ('reject', 'Rejected'),
        ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')
    
    budget = fields.Float(string='Estimate project costs')
    legal_review = fields.Boolean(string='Legal Review')
    legal_review_done = fields.Boolean(string='Legal Review Done')
    
    site_location_id = fields.Many2one(comodel_name='res.country.state', string='Site Location', domain=[('country_id.name','=','Nigeria')])
    #site_location_id = fields.Char(string='Site Location')

    
    default_site_code = fields.Char(string='Site Code') 
    
    client_type = fields.Char(string='Client Type')
    site_area = fields.Char(string='Site Area')
    site_address = fields.Char(string='Site Address')
    site_type = fields.Char(string='Site Type')
    region = fields.Char(string='Region')
    country_id = fields.Many2one(comodel_name='res.country', string="Country")
    project_status = fields.Char(string='Status.')
    contract_duration = fields.Date(string='Contract Duration (year)')
    coordinates = fields.Char(string='Coordinates')
    
    type_of_offer = fields.Selection([('lease_to_own', 'Lease to Own'), ('pass_battery', 'PaaS Battery'), ('paas_diesel', 'PaaS Diesel'),
                                      ('pass_diesel', 'PaaS Diesel'), ('saas', 'SaaS'), ('sale', 'Sale')], string='Service Type', required=False,default='saas')
    #atm_power_at_night = fields.Selection([('yes', 'Yes'), ('no', 'No'),], string='Does the system power ATM night/we?', required=False,default='yes')
    
    tariff_per_kwp = fields.Float(string='Tariff per kWh (kWp)')
    
    currency_id = fields.Many2one(comodel_name='res.currency', string='Currency.')
    monthly_service_fees = fields.Float(string='Monthly Service fees')
    #lease_duration = fields.Char(string='If lease, contract duration')
    sales_price = fields.Float(string="Sale Revenue")
    
    lead_approval = fields.Boolean(string="lead approval", related='company_id.company_lead_approval')
    site_location_id = fields.Many2one(comodel_name='res.country.state', string='Site Location', domain=[('country_id.name','=','Nigeria')])
    
    default_site_code = fields.Char(string='Site Code')
    
    @api.multi
    def generate_site_code(self, vals):
        site = self.env['res.country.state'].search([('id','=',vals['site_location_id'])])
        client = self.env['res.partner'].search([('id','=',vals['partner_id'])])
        if site and client:
            code = client.parent_account_number + "_" +  site.code
            
            no = self.env['ir.sequence'].next_by_code('project.site.code')
            site_code = code + "_" +  str(no)
            vals['default_site_code'] = site_code
    
    @api.multi
    def button_reset(self):
        self.write({'state': 'draft'})
        return {}
    
    @api.multi
    def button_submit(self):
        self.write({'state': 'submit'})
        group_id = self.env['ir.model.data'].xmlid_to_object('sunray.group_hr_line_manager')
        user_ids = []
        partner_ids = []
        for user in group_id.users:
            user_ids.append(user.id)
            partner_ids.append(user.partner_id.id)
        self.message_subscribe(partner_ids=partner_ids)
        subject = "Created Lead {} is ready for Approval".format(self.name)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
        return False
        return {}
    
    @api.multi
    def button_approve(self):
        self.write({'state': 'approve'})
        self.active = True
        self.send_introductory_mail()
        subject = "Created Lead {} has been approved".format(self.name)
        partner_ids = []
        for partner in self.message_partner_ids:
            partner_ids.append(partner.id)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
        return {}
    
    @api.multi
    def button_reject(self):
        self.write({'state': 'reject'})
        return {}
    
    @api.model
    def create(self, vals):
        result = super(Lead, self).create(vals)
        result.check_lead_approval()
        return result
    
    @api.multi
    def check_lead_approval(self):
        if self.company_id.company_lead_approval == True:
            self.active = False
        else:
            self.send_introductory_mail()
    
    @api.multi
    def button_submit_legal(self):
        self.legal_review = True
        group_id = self.env['ir.model.data'].xmlid_to_object('sunray.group_legal_team')
        user_ids = []
        partner_ids = []
        for user in group_id.users:
            user_ids.append(user.id)
            partner_ids.append(user.partner_id.id)
        self.message_subscribe(partner_ids=partner_ids)
        subject = "Opportunity '{}' needs a review from the legal team".format(self.name)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
        return False
    
    @api.multi
    def button_submit_legal_done(self):
        self.legal_review_done = True
        subject = "Opportunity {} has been reviewed by the legal team".format(self.name)
        partner_ids = []
        for partner in self.message_partner_ids:
            partner_ids.append(partner.id)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
    
    @api.multi
    def send_introductory_mail(self):
        config = self.env['mail.template'].sudo().search([('name','=','Introductory Email Template')], limit=1)
        mail_obj = self.env['mail.mail']
        if config:
            values = config.generate_email(self.id)
            mail = mail_obj.create(values)
            if mail:
                mail.send()
                subject = "Introductory message for {} has been sent to client".format(self.name)
                partner_ids = []
                for partner in self.sheet_id.message_partner_ids:
                    partner_ids.append(partner.id)
                self.sheet_id.message_post(subject=subject,body=subject,partner_ids=partner_ids)
                
    
    @api.multi
    def send_site_audit_request_mail(self):
        config = self.env['mail.template'].sudo().search([('name','=','Site Audit Request Template')], limit=1)
        mail_obj = self.env['mail.mail']
        if config:
            values = config.generate_email(self.id)
            mail = mail_obj.create(values)
            if mail:
                mail.send()
                subject = "Site audit request {} has been sent to client".format(self.name)
                partner_ids = []
                for partner in self.message_partner_ids:
                    partner_ids.append(partner.id)
                self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
    
    @api.multi
    def create_project(self):
        """
        Method to open create project form
        """
        #self.generate_site_code(vals)
        partner_id = self.partner_id
        site_location_id = self.site_location_id
        default_site_code = self.default_site_code
             
        view_ref = self.env['ir.model.data'].get_object_reference('project', 'edit_project')
        view_id = view_ref[1] if view_ref else False
         
        res = {
            'type': 'ir.actions.act_window',
            'name': ('Project'),
            'res_model': 'project.project',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'context': {'default_partner_id': partner_id.id, 'default_name': self.name, 'default_site_location_id': self.site_location_id.id, 'default_default_site_code': self.default_site_code,  'default_crm_lead_id': self.id}
        }
        
        return res
    
    @api.multi
    def create_manufacturing_order(self):
        """
        Method to open create purchase agreement form
        """

        partner_id = self.partner_id
        #client_id = self.client_id
        #store_request_id = self.id
        #sub_account_id = self.sub_account_id
        #product_id = self.move_lines.product_id
             
        view_ref = self.env['ir.model.data'].get_object_reference('mrp', 'mrp_production_form_view')
        view_id = view_ref[1] if view_ref else False
        
        #purchase_line_obj = self.env['purchase.order.line']
        '''for subscription in self:
            order_lines = []
            for line in subscription.move_lines:
                order_lines.append((0, 0, {
                    'product_uom_id': line.product_id.uom_id.id,
                    'product_id': line.product_id.id,
                    'account_analytic_id': 1,
                    'product_qty': line.product_uom_qty,
                    'schedule_date': date.today(),
                    'price_unit': line.product_id.standard_price,
                }))
        ''' 
        res = {
            'type': 'ir.actions.act_window',
            'name': ('Manufacturing Order'),
            'res_model': 'mrp.production',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'context': {'default_origin': self.name}
        }
        
        return res

class Stage(models.Model):
    _name = "crm.stage"
    _inherit = "crm.stage"
    
    company_id = fields.Many2one('res.company', string='Company', store=True,
        default=lambda self: self.env.user.company_id, track_visibility='onchange')
    
class SubAccount(models.Model):
        
    _name = "sub.account"
    _description = "sub account form"
    _order = "parent_id"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    
    @api.multi
    def name_get(self):
        res = []
        for partner in self:
            result = partner.name
            if partner.child_account:
                result = str(partner.name) + " " + str(partner.child_account)
            res.append((partner.id, result))
        return res
    
    def _default_category(self):
        return self.env['res.partner.category'].browse(self._context.get('category_id'))

    def _default_company(self):
        return self.env['res.company']._company_default_get('res.partner')
            
    def _compute_company_type(self):
        for partner in self:
            partner.company_type = 'company' if partner.is_company else 'person'
            
#     def _createSub(self):
#         partner_ids = self.search([('parent_id','=',self.parent_id.id)])
#         number = len(partner_ids) + 1
#         number = "SA00" + str(number)
#         return number

    name = fields.Char(index=True, track_visibility='onchange')
    
    parent_id = fields.Many2one('res.partner', string='Customer', domain="[('customer','=',True)]", index=True, ondelete='cascade', track_visibility='onchange')
        
    function = fields.Char(string='Description')
    
    comment = fields.Text(string='Desription')
    
    addinfo = fields.Text(string='Additional Information')
    
    child_account = fields.Char(string='Child Account Number', index=True, copy=False, default='/', track_visibility='onchange')
    
    website = fields.Char(help="Website of Partner or Company")
    
    employee = fields.Boolean(help="Check this box if this contact is an Employee.")
    
    fax = fields.Char(help="fax")
    
    create_date = fields.Date(string='Create Date', readonly=True, track_visibility='onchange')
    
    activation_date = fields.Date(string='Activation Date', readonly=False, track_visibility='onchange')
    
    term_date = fields.Date(string='Termination Date', track_visibility='onchange')
    
    perm_up_date = fields.Date(string='Permanent Activation Date', readonly=False, track_visibility='onchange')
    
    price_review_date = fields.Date(string='Price Review Date', readonly=False, track_visibility='onchange')
    
    contact_person = fields.Many2one('res.partner.title')
    
    company_name = fields.Many2many('Company Name')
    
    employee = fields.Boolean(help="Check this box if this contact is an Employee.")
      
    type = fields.Selection(
        [('contact', 'Contact'),
         ('invoice', 'Invoice address'),
         ('delivery', 'Shipping address'),
         ('other', 'Other address')], string='Address Type',
        default='invoice',
        help="Used to select automatically the right address according to the context in sales and purchases documents.")
    street = fields.Char()
    street2 = fields.Char()
    zip = fields.Char(change_default=True)
    city = fields.Char()
    state_id = fields.Many2one("res.country.state", string='State', ondelete='restrict')
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict')
    email = fields.Char()
    
    phone = fields.Char()
    mobile = fields.Char()
    
    company_type = fields.Selection(string='Company Type',
        selection=[('person', 'Individual'), ('company', 'Company')],
        compute='_compute_company_type', inverse='_write_company_type')
    company_id = fields.Many2one('res.company', 'Company', index=True, default=_default_company)
    
    contact_address = fields.Char(compute='_compute_contact_address', string='Complete Address')
    company_name = fields.Char('Company Name') 
    
    state = fields.Selection([
        ('new', 'Waiting Approval'),
        ('approve', 'Approved'),
        ('activate', 'Activated'),
        ('suspend', 'Suspended'),
        ('terminate', 'Terminated'),
        ('cancel', 'Canceled'),
        ('reject', 'Rejected'),
        ], string='Status', index=True, copy=False, default='new', track_visibility='onchange')

    @api.model
    def create(self, vals):
        partner_ids = self.search([('parent_id','=',vals['parent_id'])],order="child_account desc")
        for p in  partner_ids:
            print(p.child_account)
        if not partner_ids:
            vals['child_account'] = "SA001"
        else:
            number = partner_ids[0].child_account.split("A",2)
            number = int(number[1]) + 1
            vals['child_account'] = "SA" + str(number).zfill(3)
        return super(SubAccount, self).create(vals)
    
    
    #partners = self.search([len('child_account')])
     #       print(partners)
      #      partners = partners + 1
       #     label = "SA"
        #    partners = str(label) + str(partners.child_account)
        
    
    @api.multi
    def button_new(self):
        self.write({'state': 'new'})
        return {}
    
    @api.multi
    def button_activate(self):
        self.write({'state': 'activate'})
#        self.activation_date = date.today()
        return {}
    
    @api.multi
    def button_suspend(self):
        self.write({'state': 'suspend'})
        return {}
    
    @api.multi
    def button_terminate(self):
        self.write({'state': 'terminate'})
        self.term_date = date.today()
        return {}
    
    @api.multi
    def button_cancel(self):
        self.write({'state': 'cancel'})
        return {}
    
    @api.multi
    def button_approve(self):
        self.write({'state': 'approve'})
        return {}
    
    @api.multi
    def button_reject(self):
        self.write({'state': 'reject'})
        return {}

class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"
    _description = 'Ticket'
    
    project_id = fields.Many2one(comodel_name='project.project', string='Project')
    project_site_code = fields.Char(string='Site Code', related='project_id.default_site_code', store = True)
    
    
class ItemType(models.Model):
    _name = "item.type"
    _description = "Item Types"
    _order = "name"
    _inherit = ['mail.thread']

    name = fields.Char('Name', required=True, track_visibility='onchange')
    code = fields.Char('Code', required=True, track_visibility='onchange')
    active = fields.Boolean('Active', default='True')

class BrandType(models.Model):
    _name = "brand.type"
    _description = "Brand Types"
    _order = "name"
    _inherit = ['mail.thread']

    name = fields.Char('Name', required=True, track_visibility='onchange')
    code = fields.Char('Code', required=True, track_visibility='onchange')
    active = fields.Boolean('Active', default='True')

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    business_unit = fields.Char(string='Business Unit')
    manufacturer = fields.Char(string='Manufacturer')
    dimension = fields.Char(string='Dimension (mm) (W x D x H)')
    manufacturer_part_number = fields.Char(string='Manufacturer part number')
    
    brand = fields.Many2one('brand.type', string='Brand', track_visibility='onchange', index=True)
    item_type = fields.Many2one('item.type', string='Item Type', track_visibility='onchange', index=True)
    
    @api.model
    def create(self, vals):
        brand = self.env['brand.type'].search([('id','=',vals['brand'])])
        item = self.env['item.type'].search([('id','=',vals['item_type'])])
        if brand and item:
            code = brand.code + item.code
        
            no = self.env['ir.sequence'].next_by_code('product.template')
            item_code = code + str(no)
            vals['default_code'] = item_code
        return super(ProductTemplate, self).create(vals)
    
class Employee(models.Model):
    _name = "hr.employee"
    _description = "Employee"
    _inherit = "hr.employee"
    
    @api.multi
    def reminder_deactivate_employee_contract(self):
        group_id = self.env['ir.model.data'].xmlid_to_object('hr.group_hr_manager')
        user_ids = []
        partner_ids = []
        for user in group_id.users:
            user_ids.append(user.id)
            partner_ids.append(user.partner_id.id)
        self.message_subscribe(partner_ids=partner_ids)
        subject = "This is a reminder to deactivate any running contract for this employee".format(self.name)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
        return False
        return {}
    
    @api.multi
    def button_deactivate_employee(self):
        self.ensure_one()
        if self.active == True:
            config = self.env['mail.template'].sudo().search([('name','=','Employee Departure')], limit=1)
            mail_obj = self.env['mail.mail']
            if config:
                values = config.generate_email(self.id)
                mail = mail_obj.create(values)
                if mail:
                    mail.send()
            self.active = False
            self.reminder_deactivate_employee_contract()
    
class Job(models.Model):

    _name = "hr.job"
    _inherit = "hr.job"
    
    appliaction_deadline = fields.Date(string="Application Deadline")
    todays_date = fields.Date(string="Todays Date", default = date.today())
    
    @api.multi
    def check_deadline(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        if self.appliaction_deadline == today:
            self.set_open()


class VendorRequest(models.Model):
    _name = "vendor.request"
    _description = "Contact Request"
    _order = "name"
    _inherit = ['res.partner']
    
    def _default_employee(self): # this method is to search the hr.employee and return the user id of the person clicking the form atm
        self.env['hr.employee'].search([('user_id','=',self.env.uid)])
        return self.env['hr.employee'].search([('user_id','=',self.env.uid)])
    
    @api.multi
    def _check_line_manager(self):
        current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if current_employee == self.employee_id:
            raise UserError(_('You are not allowed to approve your own request.'))
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_info', 'Pending Partner info'),
        ('approve', 'Pending Approval 1'),
        ('validate', 'pending Approval 2'),
        ('registered', 'Registered'),
        ('reject', 'Rejected'),
        ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')
    
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Requesting Employee', default=_default_employee)
    
    vendor_registration = fields.Boolean ('Vendor fully Registered', track_visibility="onchange", readonly=True)
    
    checklist_count = fields.Integer(compute="_checklist_count",string="Checklist", store=False)
    
    #this is the vendor checklist
    completed_vendor_information = fields.Boolean(string="COMPLETED VENDOR INFORMATION FORM (AS  ATTACHED)")
    report_of_proposers_follow_up = fields.Boolean(string="REPORT OF PROPOSER'S FOLLOW UP REVIEW OF SECTIONS 4 & 5")
    true_copy_incorporation = fields.Boolean(string="COPY OF CERTIFICATE OF INCORPORATION / BUSINESS NAME REGISTRATION CERTIFICATE")
    true_copy_memorandum = fields.Boolean(string="CERTIFIED TRUE COPY OF MEMORANDUM AND ARTICLE OF  ASSOCIATION FOR LIMITED LIABILITY COMPANIES")
    true_copy_form_c02 = fields.Boolean(string="CERTIFIED TRUE COPY OF FORM C02 AND C07 FOR LIMITED LIABILITY COMPANIES")
    Vat_cert = fields.Boolean(string="VAT CERTIFICATE / FIRS REGISTRATION CERTIFICATE")
    sign_and_stamp = fields.Boolean(string="SIGN AND STAMP THE FOLLOWING SUNRAY VENRURES GENERAL TERMS & CONDITIONS BY AUTHORIZED STAFF")

    current_dpr = fields.Boolean(string="CURRENT DPR CERTIFICATE (If Applicable)")
    commercial_certificate = fields.Boolean(string="COMMERCIAL PROPOSAL OR WEBSITE REVIEW (COMPANY PROFILE INCLUDING DETAILS OF MANAGEMENT TEAM, REFERENCES & CASE STUDIES)")
    proposers_report = fields.Boolean(string="PROPOSER'S REPORT CONFIRMING CLEAN REVIEW ON INTERNET & OTHER AVAILABLE SOURCES (IF NOT CLEAN, FURTHER INFORMATION ON MATTERS IDENTIFIED)")
    copies_of_required_specialist = fields.Boolean(string="COPIES OF REQUIRED SPECIALIST CERTIFICATIONS, REGISTRATIONS & LICENCES (If Applicable)")

    recommendation_letters_from_applicant = fields.Boolean(string="RECOMMENDATION LETTER FROM APPLICANT BANKERS IN RESPECT TO THE OPERATION OF HIS/HER COMPANY'S ACCOUNT")
    evidence_of_tax = fields.Boolean(string="EVIDENCE OF TAX PAYMENT")
    code_of_conduct = fields.Boolean(string="CODE OF CONDUCT AND CODE OF ETHICS - SIGNED BY THE COMPANY'S MD OR AUTHORIZED STAFF")
    specific_references = fields.Boolean(string="SPECIFIC REFERENCES")
    latest_financials = fields.Boolean(string="LATEST FINANCIAL STATEMENTS / KEY KPIs")
    
    legal_review = fields.Boolean(string='Legal Review')
    legal_review_done = fields.Boolean(string='Legal Review Done')
    
    contact_email = fields.Char(string="email")
    
    @api.multi
    def button_submit_legal(self):
        self.legal_review = True
        group_id = self.env['ir.model.data'].xmlid_to_object('sunray.group_legal_team')
        user_ids = []
        partner_ids = []
        for user in group_id.users:
            user_ids.append(user.id)
            partner_ids.append(user.partner_id.id)
        self.message_subscribe(partner_ids=partner_ids)
        subject = "Vendor request '{}' needs a review from the legal team".format(self.name)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
        return False
    
    @api.multi
    def button_submit_legal_done(self):
        self.legal_review_done = True
        subject = "Vendor request {} has been reviewed by the legal team".format(self.name)
        partner_ids = []
        for partner in self.message_partner_ids:
            partner_ids.append(partner.id)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
    
    @api.depends('is_company', 'parent_id.commercial_partner_id')
    def _compute_commercial_partner(self):
        return {}
    
    @api.multi
    def send_request_information(self):
        self.write({'state': 'pending_info'})
        config = self.env['mail.template'].sudo().search([('name','=','Request Information')], limit=1)
        mail_obj = self.env['mail.mail']
        if config:
            values = config.generate_email(self.id)
            mail = mail_obj.create(values)
            if mail:
                mail.send()
    
    @api.multi
    def button_reset(self):
        self.write({'state': 'draft'})
        return {}
    
    @api.multi
    def button_submit(self):
        self.write({'state': 'approve'})
        group_id = self.env['ir.model.data'].xmlid_to_object('sunray.group_one_vendor_approval')
        user_ids = []
        partner_ids = []
        for user in group_id.users:
            user_ids.append(user.id)
            partner_ids.append(user.partner_id.id)
        self.message_subscribe(partner_ids=partner_ids)
        subject = "This Vendor {} needs first approval".format(self.name)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
        return {}
    
    @api.multi
    def button_validate(self):
        self._check_line_manager()
        self.write({'state': 'validate'})
        group_id = self.env['ir.model.data'].xmlid_to_object('sunray.group_two_vendor_approval')
        user_ids = []
        partner_ids = []
        for user in group_id.users:
            user_ids.append(user.id)
            partner_ids.append(user.partner_id.id)
        self.message_subscribe(partner_ids=partner_ids)
        subject = "This Vendor {} needs second approval".format(self.name)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
        return {}
    
    @api.multi
    def button_approve(self):
        self.write({'state': 'registered'})
        self.vendor_registration = True
        vals = {
            'name' : self.name,
            'company_type' : self.company_type,
            'image' : self.image,
            'parent_id' : self.parent_id.id,
            'street' : self.street,
            'street2' : self.street2,
            'city' : self.city,
            'state_id' : self.state_id.id,
            'zip' : self.zip,
            'country_id' : self.country_id.id,            
            'vat' : self.vat,
            'function' : self.function,
            'phone' : self.phone,
            'mobile' : self.mobile,
            'email' : self.contact_email,
            'customer': self.customer,
            'supplier' : self.supplier,
            'company' : self.company_id.id,
            'vendor_registration' : self.vendor_registration,
            'completed_vendor_information' : self.completed_vendor_information,
            'report_of_proposers_follow_up' : self.report_of_proposers_follow_up,
            'true_copy_incorporation' : self.true_copy_incorporation,
            'true_copy_memorandum' : self.true_copy_memorandum,
            'sign_and_stamp' : self.Vat_cert,
            'Vat_cert' : self.sign_and_stamp,
            'current_dpr' : self.current_dpr,
            'commercial_certificate' : self.commercial_certificate,
            'proposers_report' : self.proposers_report,
            'copies_of_required_specialist' : self.copies_of_required_specialist,
            'recommendation_letters_from_applicant' : self.recommendation_letters_from_applicant,
            'evidence_of_tax' : self.evidence_of_tax,
            'code_of_conduct' : self.code_of_conduct,
            'specific_references' : self.specific_references,
            'latest_financials' : self.latest_financials,
        }
        self.env['res.partner'].create(vals)
        return {}
    
    @api.multi
    def open_checklist_ticket(self):
        self.ensure_one()
        action = self.env.ref('sunray.sunray_vendor_request_checklist_action').read()[0]
        action['domain'] = literal_eval(action['domain'])
        action['domain'].append(('name', 'child_of', self.id))
        return action
    
    @api.multi
    def button_reject(self):
        self.write({'state': 'reject'})
        return {}
    
    @api.multi
    def _checklist_count(self):
        oe_checklist = self.env['vendor.internal.approval.checklist']
        for pa in self:
            domain = [('name', '=', pa.id)]
            pres_ids = oe_checklist.search(domain)
            pres = oe_checklist.browse(pres_ids)
            checklist_count = 0
            for pr in pres:
                checklist_count+=1
            pa.checklist_count = checklist_count
        return True
    
class HolidaysRequest(models.Model):
    _name = "hr.leave"
    _inherit = "hr.leave"
    
    @api.model
    def create(self, vals):
        result = super(HolidaysRequest, self).create(vals)
        result.send_mail()
        return result
    
    @api.multi
    def _check_line_manager(self):
        current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if current_employee == self.employee_id:
            raise UserError(_('Only your line manager can approve your leave request.'))
    
    @api.multi
    def send_mail(self):
        incomplete_propation_period = self.env['hr.contract'].search([('employee_id', '=', self.employee_id.id), ('state','=','open'), ('trial_date_end','>',date.today())], limit=1)
        
        unset_propation_period_contract = self.env['hr.contract'].search([('employee_id', '=', self.employee_id.id), ('state','=','open')], limit=1)
        
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        current_dates = datetime.datetime.strptime(today, "%Y-%m-%d")
        
        contract_start_date = unset_propation_period_contract.date_start
        
        between_contracts = relativedelta(current_dates, contract_start_date)
        months_between_contracts = between_contracts.months
        
        if incomplete_propation_period:
            raise UserError(_("You currently can't apply for leave as your probation period isn't over"))
        elif months_between_contracts < 5:
            raise UserError(_("You currently can't apply for leave as your contract hasn't exhausted 5 months"))
        else:
            if self.state in ['confirm']:
                config = self.env['mail.template'].sudo().search([('name','=','Leave Approval Request Template')], limit=1)
                mail_obj = self.env['mail.mail']
                if config:
                    values = config.generate_email(self.id)
                    mail = mail_obj.create(values)
                    if mail:
                        mail.send()
                        
    @api.multi
    def send_manager_approved_mail(self):
        config = self.env['mail.template'].sudo().search([('name','=','Leave Manager Approval')], limit=1)
        mail_obj = self.env['mail.mail']
        if config:
            values = config.generate_email(self.id)
            mail = mail_obj.create(values)
            if mail:
                mail.send()
                
    @api.multi
    def action_approve(self):
        # if validation_type == 'both': this method is the first approval approval
        # if validation_type != 'both': this method calls action_validate() below
        if any(holiday.state != 'confirm' for holiday in self):
            raise UserError(_('Leave request must be confirmed ("To Approve") in order to approve it.'))
        
        self._check_line_manager()
        
        current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        self.filtered(lambda hol: hol.validation_type == 'both').write({'state': 'validate1', 'first_approver_id': current_employee.id})
        self.send_manager_approved_mail()
        self.filtered(lambda hol: not hol.validation_type == 'both').action_validate()
        if not self.env.context.get('leave_fast_create'):
            self.activity_update()
        return True
    
    @api.multi
    def send_hr_approved_mail(self):
        config = self.env['mail.template'].sudo().search([('name','=','Leave HR Approval')], limit=1)
        mail_obj = self.env['mail.mail']
        if config:
            values = config.generate_email(self.id)
            mail = mail_obj.create(values)
            if mail:
                mail.send()
    
    
    @api.multi
    def action_validate(self):
        current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if any(holiday.state not in ['confirm', 'validate1'] for holiday in self):
            raise UserError(_('Leave request must be confirmed in order to approve it.'))

        self.write({'state': 'validate'})
        self.send_hr_approved_mail()
        self.filtered(lambda holiday: holiday.validation_type == 'both').write({'second_approver_id': current_employee.id})
        self.filtered(lambda holiday: holiday.validation_type != 'both').write({'first_approver_id': current_employee.id})

        for holiday in self.filtered(lambda holiday: holiday.holiday_type != 'employee'):
            if holiday.holiday_type == 'category':
                employees = holiday.category_id.employee_ids
            elif holiday.holiday_type == 'company':
                employees = self.env['hr.employee'].search([('company_id', '=', holiday.mode_company_id.id)])
            else:
                employees = holiday.department_id.member_ids

            if self.env['hr.leave'].search_count([('date_from', '<=', holiday.date_to), ('date_to', '>', holiday.date_from),
                               ('state', 'not in', ['cancel', 'refuse']), ('holiday_type', '=', 'employee'),
                               ('employee_id', 'in', employees.ids)]):
                raise ValidationError(_('You can not have 2 leaves that overlaps on the same day.'))

            values = [holiday._prepare_holiday_values(employee) for employee in employees]
            leaves = self.env['hr.leave'].with_context(
                tracking_disable=True,
                mail_activity_automation_skip=True,
                leave_fast_create=True,
            ).create(values)
            leaves.action_approve()
            # FIXME RLi: This does not make sense, only the parent should be in validation_type both
            if leaves and leaves[0].validation_type == 'both':
                leaves.action_validate()

        employee_requests = self.filtered(lambda hol: hol.holiday_type == 'employee')
        employee_requests._validate_leave_request()
        if not self.env.context.get('leave_fast_create'):
            employee_requests.activity_update()
        return True
    
    @api.multi
    def send_leave_notification_mail(self):

        employees = self.env['hr.leave'].search([])
        
        current_dates = False
        
        for self in employees:
            if self.date_from:
                
                current_dates = datetime.datetime.strptime(self.date_from, "%Y-%m-%d")
                current_datesz = current_dates - relativedelta(days=3)
                
                date_start_day = current_datesz.day
                date_start_month = current_datesz.month
                date_start_year = current_datesz.year
                
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                
                test_today = datetime.datetime.today().strptime(today, "%Y-%m-%d")
                date_start_day_today = test_today.day
                date_start_month_today = test_today.month
                date_start_year_today = test_today.year
                
                
                if date_start_month == date_start_month_today:
                    if date_start_day == date_start_day_today:
                        if date_start_year == date_start_year_today:
                            config = self.env['mail.template'].sudo().search([('name','=','Leave Reminder')], limit=1)
                            mail_obj = self.env['mail.mail']
                            if config:
                                values = config.generate_email(self.id)
                                mail = mail_obj.create(values)
                                if mail:
                                    mail.send()
                                return True
        return
'''
class Holidays(models.Model):
    _name = "hr.leave"
    _inherit = "hr.leave"
    
    state = fields.Selection([
            ('draft', 'To Submit'),
            ('cancel', 'Cancelled'),
            ('confirm', 'To Approve'),
            ('refuse', 'Refused'),
            ('validate1', 'Second Approval'),
            ('validate', 'Approved')
            ], string='Status', readonly=False, track_visibility='onchange', copy=False, default='confirm',
                help="The status is set to 'To Submit', when a leave request is created." +
                "\nThe status is 'To Approve', when leave request is confirmed by user." +
                "\nThe status is 'Refused', when leave request is refused by manager." +
                "\nThe status is 'Approved', when leave request is approved by manager.")
    
    date_from = fields.Date('Start Date', readonly=True, index=True, copy=False,
        states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]}, track_visibility='onchange')
    date_to = fields.Date('End Date', readonly=True, copy=False,
        states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]}, track_visibility='onchange')
    
    @api.model
    def create(self, vals):
        result = super(Holidays, self).create(vals)
        result.send_mail()
        return result
    
    @api.multi
    def send_mail(self):
        if self.state in ['confirm']:
            config = self.env['mail.template'].sudo().search([('name','=','Leave Approval Request Template')], limit=1)
            mail_obj = self.env['mail.mail']
            if config:
                values = config.generate_email(self.id)
                mail = mail_obj.create(values)
                if mail:
                    mail.send()
                    
    #add followers for odoo 12          
    @api.multi
    def add_follower(self, employee_id):
        employee = self.env['hr.employee'].browse(employee_id)
        if employee.user_id:
            self.message_subscribe(partner_ids=employee.user_id.partner_id.ids)          
          
    @api.multi
    def send_manager_approved_mail(self):
        config = self.env['mail.template'].sudo().search([('name','=','Leave Manager Approval')], limit=1)
        mail_obj = self.env['mail.mail']
        if config:
            values = config.generate_email(self.id)
            mail = mail_obj.create(values)
            if mail:
                mail.send()
    
    @api.multi
    def send_hr_approved_mail(self):
        config = self.env['mail.template'].sudo().search([('name','=','Leave HR Approval')], limit=1)
        mail_obj = self.env['mail.mail']
        if config:
            values = config.generate_email(self.id)
            mail = mail_obj.create(values)
            if mail:
                mail.send()
    
    @api.multi
    def send_hr_notification(self):
        group_id = self.env['ir.model.data'].xmlid_to_object('sunray.group_hr_leave_manager')
        user_ids = []
        partner_ids = []
        for user in group_id.users:
            user_ids.append(user.id)
            partner_ids.append(user.partner_id.id)
        self.message_subscribe_users(user_ids=user_ids)
        subject = "Leave Request for {} is Ready for Second Approval".format(self.display_name)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
        return False
    
    @api.multi
    def _check_security_action_validate(self):
        #current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if not self.env.user.has_group('hr_holidays.group_hr_holidays_user'):
            raise UserError(_('Only an HR Officer or Manager can approve leave requests.'))
    
    @api.multi
    def _check_line_manager(self):
        current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if current_employee == self.employee_id:
            raise UserError(_('Only your line manager can approve your leave request.'))
    
    @api.multi
    def action_approve(self):
        # if double_validation: this method is the first approval approval
        # if not double_validation: this method calls action_validate() below
        self._check_security_action_approve()
        self._check_line_manager()

        current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        for holiday in self:
            if holiday.state != 'confirm':
                raise UserError(_('Leave request must be confirmed ("To Approve") in order to approve it.'))

            if holiday.double_validation:
                holiday.send_manager_approved_mail()
                holiday.send_hr_notification()
                return holiday.write({'state': 'validate1', 'first_approver_id': current_employee.id})
            else:
                holiday.action_validate()
    
    
    @api.multi
    def action_validate(self):
        self._check_security_action_validate()

        current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        for holiday in self:
            if holiday.state not in ['confirm', 'validate1']:
                raise UserError(_('Leave request must be confirmed in order to approve it.'))
            if holiday.state == 'validate1' and not holiday.env.user.has_group('hr_holidays.group_hr_holidays_manager'):
                raise UserError(_('Only an HR Manager can apply the second approval on leave requests.'))

            holiday.write({'state': 'validate'})
            holiday.send_hr_approved_mail()
            if holiday.double_validation:
                holiday.write({'second_approver_id': current_employee.id})
            else:
                holiday.write({'first_approver_id': current_employee.id})
            if holiday.holiday_type == 'employee' and holiday.type == 'remove':
                holiday._validate_leave_request()
            elif holiday.holiday_type == 'category':
                leaves = self.env['hr.leave']
                for employee in holiday.category_id.employee_ids:
                    values = holiday._prepare_create_by_category(employee)
                    leaves += self.with_context(mail_notify_force_send=False).create(values)
                # TODO is it necessary to interleave the calls?
                leaves.action_approve()
                if leaves and leaves[0].double_validation:
                    leaves.action_validate()
        return True
    
    @api.multi
    def send_leave_notification_mail(self):

        employees = self.env['hr.leave'].search([])
        
        current_dates = False
        
        for self in employees:
            if self.date_from:
                
                current_dates = datetime.datetime.strptime(self.date_from, "%Y-%m-%d")
                current_datesz = current_dates - relativedelta(days=3)
                
                date_start_day = current_datesz.day
                date_start_month = current_datesz.month
                date_start_year = current_datesz.year
                
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                
                test_today = datetime.datetime.today().strptime(today, "%Y-%m-%d")
                date_start_day_today = test_today.day
                date_start_month_today = test_today.month
                date_start_year_today = test_today.year
                
                
                if date_start_month == date_start_month_today:
                    if date_start_day == date_start_day_today:
                        if date_start_year == date_start_year_today:
                            config = self.env['mail.template'].sudo().search([('name','=','Leave Reminder')], limit=1)
                            mail_obj = self.env['mail.mail']
                            if config:
                                values = config.generate_email(self.id)
                                mail = mail_obj.create(values)
                                if mail:
                                    mail.send()
                                return True
        return

'''
class EmployeeContract(models.Model):
    _name = 'hr.contract'
    _inherit = 'hr.contract'
    
    trial_date_end_bool = fields.Boolean(string="Update Probation", store=True)
    
    @api.onchange('trial_date_end')
    def send_notification(self):
        self.trial_date_end_bool = True
    
    @api.multi
    def write(self, vals):
        result = super(EmployeeContract, self).write(vals)
        self.send_notification_message()
        return result
    
    @api.depends('trial_date_end_bool')
    def send_notification_message(self):
        if self.trial_date_end_bool == True:
            group_id = self.env['ir.model.data'].xmlid_to_object('sunray.group_hr_line_manager')
            user_ids = []
            partner_ids = []
            for user in group_id.users:
                user_ids.append(user.id)
                partner_ids.append(user.partner_id.id)
            self.message_subscribe(partner_ids=partner_ids)
            subject = "Probation period for {}'s contract had been updated and is Hence {}".format(self.name, self.trial_date_end)
            self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
            self.trial_date_end_bool = False
            return False
    
class AvailabilityRequest(models.Model):
    _name = "availability.request"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    #_inherit = 'stock.picking'
    _description = "Availability Demand Form"
    
    name = fields.Char('Order Reference', readonly=True, required=True, index=True, copy=False, default='New')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('approve', 'Approved'),
        ('reject', 'Rejected'),
        ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')
    
    def _default_employee(self):
        self.env['hr.employee'].search([('user_id','=',self.env.uid)])
        return self.env['hr.employee'].search([('user_id','=',self.env.uid)])
    
    @api.multi
    def button_reset(self):
        self.write({'state': 'draft'})
        return {}
    
    @api.multi
    def button_submit(self):
        self.write({'state': 'submit'})
        return {}
    
    @api.multi
    def button_approve(self):
        self.write({'state': 'approve'})
        '''vals = {
            'name' : self.name,
            'company_type' : self.company_type,
            'image' : self.image,
            'parent_id' : self.parent_id.id,
            'street' : self.street,
            'street2' : self.street2,
            'city' : self.city,
            'state_id' : self.state_id.id,
            'zip' : self.zip,
            'country_id' : self.country_id.id,            
            'vat' : self.vat,
            'function' : self.function,
            'phone' : self.phone,
            'mobile' : self.mobile,
            'email' : self.email,
            'customer': self.customer,
            'supplier' : self.supplier,
            'supplier' : self.company_id.id
        }
        self.env['res.partner'].create(vals)
        '''
        return {}
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('availability.request') or '/'
        return super(AvailabilityRequest, self).create(vals)
    
    @api.multi
    def create_purchase_order(self):
        """
        Method to open create purchase order form
        """

        partner_id = self.request_client_id
        client_id = self.request_client_id
        #sub_account_id = self.sub_account_id
        #product_id = self.move_lines.product_id
             
        view_ref = self.env['ir.model.data'].get_object_reference('purchase', 'purchase_order_form')
        view_id = view_ref[1] if view_ref else False
        
        #purchase_line_obj = self.env['purchase.order.line']
        for subscription in self:
            order_lines = []
            for line in subscription.request_move_line:
                order_lines.append((0, 0, {
                    'name': line.product_id.name,
                    'product_uom': line.product_id.uom_id.id,
                    'product_id': line.product_id.id,
                    'account_id': line.product_id.property_account_expense_id.id,
                    'account_analytic_id': 1,
                    'product_qty': line.product_oum_qty,
                    'date_planned': date.today(),
                    'price_unit': line.product_id.standard_price,
                }))
         
        res = {
            'type': 'ir.actions.act_window',
            'name': ('Purchase Order'),
            'res_model': 'purchase.order',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'context': {'default_client_id': client_id.id, 'default_stock_source': self.name, 'default_order_line': order_lines}
        }
        
        return res
    
    @api.multi
    def create_store_request(self):
        """
        Method to open create purchase order form
        """

        partner_id = self.request_client_id
        client_id = self.request_client_id
        #sub_account_id = self.sub_account_id
        #product_id = self.move_lines.product_id
             
        view_ref = self.env['ir.model.data'].get_object_reference('sunray', 'sunray_stock_form_view')
        view_id = view_ref[1] if view_ref else False
        
        #purchase_line_obj = self.env['purchase.order.line']
        for subscription in self:
            order_lines = []
            for line in subscription.request_move_line:
                order_lines.append((0, 0, {
                    'name': line.product_id.name,
                    'product_uom': line.product_id.uom_id.id,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.product_oum_qty,
                    'additional': True,
                    'date_expected': date.today(),
                    'price_cost': line.product_id.standard_price,
                }))
         
        res = {
            'type': 'ir.actions.act_window',
            'name': ('Store Request'),
            'res_model': 'stock.picking',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'context': {'default_client_id': client_id.id, 'default_origin': self.name, "default_is_locked":False, "default_picking_type_id":self.env.ref("sunray.stock_picking_type_emp").id, 'default_move_lines': order_lines}
        }
        
        return res
    
    requestor_id = fields.Many2one('hr.employee', 'Requesting Employee', default=_default_employee, help="Default Owner")
    
    department_name = fields.Char(string="Department", related="requestor_id.department_id.name", readonly=True)    
    
    request_client_id = fields.Many2one('res.partner', string='Clients', index=True, ondelete='cascade', required=False)
    
    request_date = fields.Datetime(string="Due Date")
    
    request_move_line = fields.One2many('availability.request.line', 'availability_id', string="Stock Move", copy=True)

class AvailabilityRequestLine(models.Model):
    _name = "availability.request.line"
    _description = 'Availability Request Line'
    
    availability_id = fields.Many2one('availability.request', 'Availability Demand Form')
    
    product_id = fields.Many2one('product.product', 'Product')
    product_oum_qty = fields.Float(string="Quantity")
    price_cost  = fields.Float(string="Cost", related="product_id.standard_price")
    
class Expreliminary(models.Model):
    _name = 'expense.report'
    _description = 'Expense Report'
   
    def _default_employee(self): # this method is to search the hr.employee and return the user id of the person clicking the form atm
        self.env['hr.employee'].search([('user_id','=',self.env.uid)])
        return self.env['hr.employee'].search([('user_id','=',self.env.uid)])
    
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Employee', default=_default_employee) #used as a signature to pull the currently employee    
    employee_sign_date = fields.Date(string='Employee Sign Date', default=date.today())# used as a signature date. 
       

    name = fields.Char(string='Name')
    purpose = fields.Char(string='Purpose')
    date_from = fields.Date(string='From')
    date_to = fields.Date(string='To')

    expense_advanced = fields.Integer(string= 'Expense Advanced')
    balance_company = fields.Integer(string='Balance due To Employee')
    balance_employee = fields.Integer(string='Balance due to Company')

    total_expense = fields.Integer(string='Total Expense')

    line_ids = fields.One2many('expense.report.line','expense_id',string='Expenses')

    day = fields.Selection(related = 'line_ids.day', string='Day')
    date = fields.Date(related = 'line_ids.date', string='Date')
    description = fields.Char(related = 'line_ids.description', string='Description')
    expense = fields.Integer(related = 'line_ids.expense', string=' Total Expense')
    receipt = fields.Selection(related = 'line_ids.receipt', string='receipt')



class businessexpensereport(models.Model):
    _name = 'expense.report.line'
    _description = 'Expense Report Line'

    expense_id = fields.Many2one(comodel_name='expense.report', string="Expense id")

    date = fields.Date(string='Date')

    day = fields.Selection([
        ('monday','Monday'),
        ('tuesday','Tuesday'),
        ('wednesday','Wednesday'),
        ('thursday','Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday')],
        string='Day',
        required=True)

    description = fields.Char(string='Description')
    expense = fields.Integer(string='Expense')
    receipt = fields.Selection([
            ('yes','Yes'),
            ('no','No')],
            string='Receipt Available',
            required=True)
    
class parkpreliminary(models.Model):
    _name = 'parking.list'
    _description = 'Parking List'
   
    def _default_employee(self): # this method is to search the hr.employee and return the user id of the person clicking the form atm
        self.env['hr.employee'].search([('user_id','=',self.env.uid)])
        return self.env['hr.employee'].search([('user_id','=',self.env.uid)])

    date = fields.Date(string='Date')
    request_no = fields.Char(string='Request Number')
    site = fields.Char(string='Site')
    requester = fields.Char(string='Requester')

    reciever_id = fields.Many2one(comodel_name='hr.employee', string='Received By', default=_default_employee)
    receiver_sign_date = fields.Date(string='Receivers Date', default=date.today())

    line_ids = fields.One2many(comodel_name='parking.list.line',inverse_name='parking_id', string='Parking ID')

    employee_id = fields.Many2one(comodel_name='hr.employee', string='Employee Name', default=_default_employee) #used as a signature to pull the currently employee    
    employee_sign_date = fields.Date(string='Employees Date', default=date.today())# used as a signature date. 

    security_id = fields.Many2one(comodel_name='hr.employee', string='Security Name', default=_default_employee) #used as a signature to pull the currently employee    
    security_sign_date = fields.Date(string='Securitys Date', default=date.today())# used as a signature date. 



class parkinglistreport(models.Model):
    _name = 'parking.list.line'
    _description = 'Parking List Line'

    parking_id = fields.Many2one(comodel_name='hr.employee')

    serial_no = fields.Char(string='Serial No')
    item = fields.Char(string='Items')
    part_no = fields.Char(string='Part Number')
    quantity = fields.Char(string='Quantity')
    packaging = fields.Char(string='Partackaging') 
    
    
class paypreliminary(models.Model):
    _name = 'payment.request'
    _description = 'Payment Request'
    
    pr_no = fields.Char(string='PR_ No.')
    issue_date = fields.Date(string='Date of Issue')
    request_company = fields.Char(string='Requesting Company')
    item_type = fields.Selection ([
              ('fixed asset','Fixed Asset'),
              ('inventory','Inventory'),
              ('maintenance','Maintenance'),
              ('supplies','Supplies'),
              ('others','Others')],
              string ='Item type',
              required=True)

    name = fields.Char(string='Name')

    line_ids = fields.One2many('purchase.request.line','purchase_id',string='Purchases')

    description = fields.Char(string='Description')

    company_name = fields.Char(string='Company Name')
    contact_person = fields.Char(string='Contact Person')
    contact_email = fields.Char(string='Email Address')
    contact_phone = fields.Char(string='Phone')


class purchaserequesttable(models.Model):
    _name = 'purchase.request.line'
    _description = 'Purchase Request Line'

    purchase_id = fields.Many2one(comodel_name='payment.request')

    material = fields.Char(string='Material Need')
    specification = fields.Char(string='Specification')
    part_no = fields.Char(string='Part No')
    quantity = fields.Char(string='Quantity')
    unit = fields.Char(string='Unit')
    
    
class ProjectAction(models.Model):
    _name = "project.action"
    _description = 'Project Action'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    def _default_employee(self): # this method is to search the hr.employee and return the user id of the person clicking the form atm
        self.env['hr.employee'].search([('user_id','=',self.env.uid)])
        return self.env['hr.employee'].search([('user_id','=',self.env.uid)])
    
    @api.model
    def _get_default_project(self):
        ctx = self._context
        if ctx.get('active_model') == 'project.project':
            return self.env['project.project'].browse(ctx.get('active_ids')[0]).id
  
    partner_id = fields.Many2one(comodel_name='res.partner', related='project_id.partner_id', string='Customer', readonly=True)
    
    project_id = fields.Many2one(comodel_name='project.project', string='Project', readonly=True, default=_get_default_project)
    
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Owner', default=_default_employee)
    
    state = fields.Selection([
        ('draft', 'New'),
        ('wip', 'Wip'),
        ('closed', 'Closed'),
        ('on_hold', 'On Hold'),
        ('open', 'Open'),
        ], string='Status', readonly=False, index=True, copy=False, default='draft', track_visibility='onchange')
    
    project_action_priority = fields.Selection([('0', '0'),('1', 'Low'), ('2', 'Medium'), ('3', 'High'), ('4', 'Urgent')], string='Priority', required=False)
    project_action_line_ids = fields.One2many('project.action.line', 'project_action_id', string="Action Move", copy=True)
    due_date = fields.Date(string='Due Date')
    
    
class ProjectActionLine(models.Model):
    _name = "project.action.line"
    _description = 'Project Action Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    project_action_id = fields.Many2one('project.action', 'Project Action')
    
    s_n = fields.Float(string='S/N', compute='_total_cost', readonly=False)
    action_items = fields.Char(string='Action Item')
    comments = fields.Char(string='Comments')
    
    #@api.depends('s_n')
    def _total_cost(self):
        s_n = 1
        for a in self:
            s_n +=1
            a.s_n = s_n
        
class ProjectIssue(models.Model):
    _name = "project.issues"
    _description = 'Project Issues'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    def _default_employee(self): # this method is to search the hr.employee and return the user id of the person clicking the form atm
        self.env['hr.employee'].search([('user_id','=',self.env.uid)])
        return self.env['hr.employee'].search([('user_id','=',self.env.uid)])
    
    @api.model
    def _get_default_project(self):
        ctx = self._context
        if ctx.get('active_model') == 'project.project':
            return self.env['project.project'].browse(ctx.get('active_ids')[0]).id
        
    name = fields.Char(string='Issue Title', required=True)
    
    description = fields.Char(string='Issue Description')
    
    partner_id = fields.Many2one(comodel_name='res.partner', related='project_id.partner_id', string='Customer', readonly=True)
    
    project_id = fields.Many2one(comodel_name='project.project', string='Project', readonly=True, default=_get_default_project)
    
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Reported By', default=_default_employee)
    
    state = fields.Selection([
        ('draft', 'New'),
        ('wip', 'Wip'),
        ('closed', 'Closed'),
        ('on_hold', 'On Hold'),
        ('open', 'Open'),
        ], string='Status', readonly=False, index=True, copy=False, default='draft', track_visibility='onchange')
    
    project_issue_severity = fields.Selection([('1', 'Low'), ('2', 'Medium'), ('3', 'High'), ('4', 'Urgent')], string='Severity', required=False)
    project_action_priority = fields.Selection([('0', '0'),('1', 'Low'), ('2', 'Medium'), ('3', 'High'), ('4', 'Urgent')], string='Priority', required=False)
    date = fields.Date(string='Reported On', default=date.today())
    comments = fields.Char(string='Comments')
    
class ProjectRisk(models.Model):
    _name = "project.risk"
    _description = 'Project Risk'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    def _default_employee(self): # this method is to search the hr.employee and return the user id of the person clicking the form atm
        self.env['hr.employee'].search([('user_id','=',self.env.uid)])
        return self.env['hr.employee'].search([('user_id','=',self.env.uid)])
    
    @api.model
    def _get_default_project(self):
        ctx = self._context
        if ctx.get('active_model') == 'project.project':
            return self.env['project.project'].browse(ctx.get('active_ids')[0]).id
    
    state = fields.Selection([
        ('draft', 'New'),
        ('wip', 'Wip'),
        ('closed', 'Closed'),
        ('on_hold', 'On Hold'),
        ('open', 'Open'),
        ], string='Status', readonly=False, index=True, copy=False, default='draft', track_visibility='onchange')
    
    partner_id = fields.Many2one(comodel_name='res.partner', related='project_id.partner_id', string='Customer', readonly=True)
    
    project_id = fields.Many2one(comodel_name='project.project', string='Project', readonly=True, default=_get_default_project)
    
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Owner', default=_default_employee)
    
    project_risk_line_ids = fields.One2many('project.risk.line', 'project_risk_id', string="Project Risk", copy=True)

class ProjectRiskLine(models.Model):
    _name = "project.risk.line"
    _description = 'project Risk Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    project_risk_id = fields.Many2one ('project.risk', 'Project Risk')

    risk_title = fields.Char(string='Risk Title')
    risk_impact = fields.Char(string='Risk Description/Impact')
    risk_status = fields.Selection([
        ('new','New'),
        ('wip','WIP'),
        ('closed', 'Closed'), 
        ('on hold', 'On Hold'),
        ('open', 'Open'),
        ], string = 'Status', track_visibility='onchange')
    
    employee_id = fields.Many2one(comodel_name='project.risk')

    date = fields.Date(string='Identified Date')


    risk_category = fields.Selection([
        ('project', 'Project'),
        ('organizational', 'Organizational'),
        ('resource','Resource'),
        ('environment','Environment'), 
        ], string = 'Risk Categories', track_visibility='onchange')


    mitigation= fields.Char(string='Possible Mitigation')

    date_closed = fields.Date(string='Date Closed')

class ProjectEHS(models.Model):
    _name = "project.ehs"
    _description = 'Project EHS'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    def _default_employee(self): # this method is to search the hr.employee and return the user id of the person clicking the form atm
        self.env['hr.employee'].search([('user_id','=',self.env.uid)])
        return self.env['hr.employee'].search([('user_id','=',self.env.uid)])

    @api.model
    def _get_default_project(self):
        ctx = self._context
        if ctx.get('active_model') == 'project.project':
            return self.env['project.project'].browse(ctx.get('active_ids')[0]).id
        
    project_ehs_name = fields.Char(string='Issue Title', required=True)
    
    project_ehs_description = fields.Char(string='Issue Description')
    
    partner_id = fields.Many2one(comodel_name='res.partner', related='project_id.partner_id', string='Customer', readonly=True)
    
    project_id = fields.Many2one(comodel_name='project.project', string='Project', readonly=True, default=_get_default_project)
    
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Reported By', default=_default_employee)

    project_ehs_state = fields.Selection([
        ('draft', 'New'),
        ('wip', 'Wip'),
        ('closed', 'Closed'),
        ('on_hold', 'On Hold'),
        ('open', 'Open'),
        ], string='Status', readonly=False, index=True, copy=False, default='draft', track_visibility='onchange')
    

    project_ehs_severity = fields.Selection([('1', 'Low'), ('2', 'Medium'), ('3', 'High'), ('4', 'Critical')], string='Severity', required=False)


    project_ehs_priority = fields.Selection([('0', '0'),('1', 'Low'), ('2', 'Medium'), ('3', 'High'), ('4', 'Urgent')], string='Priority', required=False)

    date = fields.Date(string='Reported On', default=date.today())
    comments = fields.Char(string='Comments')


class ProjectDecisions(models.Model):
    _name = "project.decision"
    _description = 'Project Decision'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    def _default_employee(self): # this method is to search the hr.employee and return the user id of the person clicking the form atm
        self.env['hr.employee'].search([('user_id','=',self.env.uid)])
        return self.env['hr.employee'].search([('user_id','=',self.env.uid)])

    @api.model
    def _get_default_project(self):
        ctx = self._context
        if ctx.get('active_model') == 'project.project':
            return self.env['project.project'].browse(ctx.get('active_ids')[0]).id
        
    decision_detail = fields.Char(string='Decision Details', required=True)
    
    decision_impact = fields.Char(string='Decision Impact')

    staff_id = fields.Char(comodel_name='hr.employee', string = 'Proposed by')

    partner_id = fields.Many2one(comodel_name='res.partner', related='project_id.partner_id', string='Customer', readonly=True)
    
    project_id = fields.Many2one(comodel_name='project.project', string='Project', readonly=True, default=_get_default_project)
    
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Approved By', default=_default_employee)

    project_decision_state = fields.Selection([
        ('draft', 'New'),
        ('wip', 'Wip'),
        ('closed', 'Closed'),
        ('on_hold', 'On Hold'),
        ('open', 'Open'),
        ], string='Status', readonly=False, index=True, copy=False, default='draft', track_visibility='onchange')
    

    date = fields.Date(string='Date', default=date.today())
    comments = fields.Char(string='Resulting Actions/Comments')


class ProjectChangeRequest(models.Model):
    _name = 'project.change_request'
    _description = 'Project Change Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    def _default_employee(self): # this method is to search the hr.employee and return the user id of the person clicking the form atm
        self.env['hr.employee'].search([('user_id','=',self.env.uid)])
        return self.env['hr.employee'].search([('user_id','=',self.env.uid)])

    @api.model
    def _get_default_project(self):
        ctx = self._context
        if ctx.get('active_model') == 'project.project':
            return self.env['project.project'].browse(ctx.get('active_ids')[0]).id
        
    
    partner_id = fields.Many2one(comodel_name='res.partner', related='project_id.partner_id', string='Customer', readonly=True)
    
    project_id = fields.Many2one(comodel_name='project.project', string='Project', readonly=True, default=_get_default_project)
    
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Requester', default=_default_employee)

    date = fields.Date(string='Date Raised', default=date.today())
    
    project_change_request_priority = fields.Selection([('0', '0'),('1', 'Low'), ('2', 'Medium'), ('3', 'High'), ('4', 'Urgent')], string='Priority', required=False)

    project_change_request_line_ids = fields.One2many('project.change_request.line', 'project_change_request_id', string="Request Move", copy=True)
    
class ProjectChangeRequestLine(models.Model):
    _name = "project.change_request.line"
    _description = 'Project Action Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    project_change_request_id = fields.Many2one('project.change_request', 'Project Change Request')

    s_n = fields.Float(string='S/N', readonly=False)

    project_change_request_description = fields.Char(string='Change Description')

    project_change_request_decision = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('closed', 'Closed'),
        ('on_hold', 'On Hold'),
        ('new', 'New'),
        ], string='Status', readonly=False, index=True, copy=False, default='draft', track_visibility='onchange')

    project_change_request_severity = fields.Selection([('1', 'Low'), ('2', 'Medium'), ('3', 'High'), ('4', 'Critical')], string='Severity', required=False)

    project_change_request_priority = fields.Selection([('0', '0'),('1', 'Low'), ('2', 'Medium'), ('3', 'High'), ('4', 'Urgent')], string='Priority', required=False)

    comments = fields.Char(string='Comments')
    
class VendorRequestersReport(models.Model):
    _name = "vendor.requesters.report"
    _description = 'Vendor Requesters Report'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    def _get_employee_id(self):
        employee_rec = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        return employee_rec.id
    
    name = fields.Char(string='Customer Name', required=True)
    code = fields.Char(string='Customer Code', required=True)
    vendor_request_line = fields.One2many(comodel_name='vendor.requesters.report.line', inverse_name='line_id')
    vendor_request_line_two = fields.One2many(comodel_name='vendor.requesters.report.line.two', inverse_name='line_two_id')
    overview = fields.Text(string='Overview of matrial funds Code')
    
    requester_name_id = fields.Many2one(comodel_name='hr.employee', string="Requester's name", default=_get_employee_id, required=True) 
    position = fields.Many2one(comodel_name='hr.job', string="Position", related="requester_name_id.job_id") 
    date = fields.Date(string='Date')
    signature = fields.Many2one(comodel_name='res.users', string="Signature") 
    
class VendorRequestersReportLine(models.Model):
    _name = "vendor.requesters.report.line"
    _description = 'Vendor requesters report line 1'
    
    line_id = fields.Many2one(comodel_name='vendor.requesters.report')
    individuals_searched = fields.Char(string='Individuals searched')
    investors_senior_management = fields.Char(string='Investors or senior management?')
    findings = fields.Selection([('none', 'None'), ('yes', 'Yes ')], string='Findings (None/Yes)')
    description = fields.Char(string='Description')
    
class VendorRequestersReportLineTwo(models.Model):
    _name = "vendor.requesters.report.line.two"
    _description = 'Vendor requesters report line 2'
    
    line_two_id = fields.Many2one(comodel_name='vendor.requesters.report')
    entities_searched = fields.Char(string='Entities searched')
    parent_entities = fields.Char(string='Parent entities or ultimate parent entities?')
    findings = fields.Selection([('none', 'None'), ('yes', 'Yes ')], string='Findings (None/Yes)')
    description = fields.Char(string='Description')
    
class VendorInternalApprovalChecklist(models.Model):
    _name = "vendor.internal.approval.checklist"
    _description = 'Vendor Internal Approval Checklist'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    
    @api.model
    def _get_default_partner(self):
        ctx = self._context
        if ctx.get('active_model') == 'vendor.request':
            return self.env['vendor.request'].browse(ctx.get('active_ids')[0]).id

    
    name = fields.Many2one(comodel_name='vendor.request', string='Vendor Request', default=_get_default_partner)
    
    @api.multi
    def button_select_all(self):
        self.write({'completed_vendor_information': True})
        self.write({'report_of_proposers_follow_up': True})
        self.write({'true_copy_incorporation': True})
        self.write({'true_copy_memorandum': True})
        self.write({'true_copy_form_c02': True})
        self.write({'Vat_cert': True})
        self.write({'sign_and_stamp': True})
        self.write({'current_dpr': True})
        self.write({'commercial_certificate': True})
        self.write({'proposers_report': True})
        self.write({'copies_of_required_specialist': True})
        self.write({'evidence_of_tax': True})
        self.write({'recommendation_letters_from_applicant': True})
        self.write({'code_of_conduct': True})
        self.write({'specific_references': True})
        self.write({'latest_financials': True})
        return {}
    
    completed_vendor_information = fields.Boolean(string="COMPLETED VENDOR INFORMATION FORM (AS  ATTACHED)")
    report_of_proposers_follow_up = fields.Boolean(string="REPORT OF PROPOSER'S FOLLOW UP REVIEW OF SECTIONS 4 & 5")
    true_copy_incorporation = fields.Boolean(string="COPY OF CERTIFICATE OF INCORPORATION / BUSINESS NAME REGISTRATION CERTIFICATE")
    true_copy_memorandum = fields.Boolean(string="CERTIFIED TRUE COPY OF MEMORANDUM AND ARTICLE OF  ASSOCIATION FOR LIMITED LIABILITY COMPANIES")
    true_copy_form_c02 = fields.Boolean(string="CERTIFIED TRUE COPY OF FORM C02 AND C07 FOR LIMITED LIABILITY COMPANIES")
    Vat_cert = fields.Boolean(string="VAT CERTIFICATE / FIRS REGISTRATION CERTIFICATE")
    sign_and_stamp = fields.Boolean(string="SIGN AND STAMP THE FOLLOWING SUNRAY VENRURES GENERAL TERMS & CONDITIONS BY AUTHORIZED STAFF")

    current_dpr = fields.Boolean(string="CURRENT DPR CERTIFICATE (If Applicable)")
    commercial_certificate = fields.Boolean(string="COMMERCIAL PROPOSAL OR WEBSITE REVIEW (COMPANY PROFILE INCLUDING DETAILS OF MANAGEMENT TEAM, REFERENCES & CASE STUDIES)")
    proposers_report = fields.Boolean(string="PROPOSER'S REPORT CONFIRMING CLEAN REVIEW ON INTERNET & OTHER AVAILABLE SOURCES (IF NOT CLEAN, FURTHER INFORMATION ON MATTERS IDENTIFIED)")
    copies_of_required_specialist = fields.Boolean(string="COPIES OF REQUIRED SPECIALIST CERTIFICATIONS, REGISTRATIONS & LICENCES (If Applicable)")

    recommendation_letters_from_applicant = fields.Boolean(string="RECOMMENDATION LETTER FROM APPLICANT BANKERS IN RESPECT TO THE OPERATION OF HIS/HER COMPANY'S ACCOUNT")
    evidence_of_tax = fields.Boolean(string="EVIDENCE OF TAX PAYMENT")
    code_of_conduct = fields.Boolean(string="CODE OF CONDUCT AND CODE OF ETHICS - SIGNED BY THE COMPANY'S MD OR AUTHORIZED STAFF")
    specific_references = fields.Boolean(string="SPECIFIC REFERENCES")
    latest_financials = fields.Boolean(string="LATEST FINANCIAL STATEMENTS / KEY KPIs")

    
    
    
    
    
    
    
    
                