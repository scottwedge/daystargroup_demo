# -*- coding: utf-8 -*-

import datetime

from datetime import date, timedelta
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo import api, fields, models, _

class Lead(models.Model):
    _name = "crm.lead"
    _inherit = 'crm.lead'
    
    type_of_offer = fields.Selection([('saas', 'SaaS'), ('pass', 'PaaS '), ('sale', 'Sale ')], string='Type of Offer', required=False,default='saas')
    size = fields.Char(string='Size (kWp)')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('approve', 'Approved'),
        ('reject', 'Rejected'),
        ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')

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
        for partner in self.sheet_id.message_partner_ids:
            partner_ids.append(partner.id)
        self.sheet_id.message_post(subject=subject,body=subject,partner_ids=partner_ids)
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
                subject = "Site audit request request {} has been sent to client".format(self.name)
                partner_ids = []
                for partner in self.sheet_id.message_partner_ids:
                    partner_ids.append(partner.id)
                self.sheet_id.message_post(subject=subject,body=subject,partner_ids=partner_ids)
    
    @api.multi
    def create_project(self):
        """
        Method to open create project form
        """

        partner_id = self.partner_id
             
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
            'context': {'default_partner_id': partner_id.id, 'default_name': self.name, 'default_crm_lead_id': self.id}
        }
        
        return res

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
    _description = "vendor request form"
    _order = "name"
    _inherit = ['res.partner']
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('approve', 'Approved'),
        ('reject', 'Rejected'),
        ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')

    @api.depends('is_company', 'parent_id.commercial_partner_id')
    def _compute_commercial_partner(self):
        return {}
            
          
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
            'email' : self.email,
            'customer': self.customer,
            'supplier' : self.supplier,
            'company' : self.company_id.id
        }
        self.env['res.partner'].create(vals)
        return {}
    
    @api.multi
    def button_reject(self):
        self.write({'state': 'reject'})
        return {}

class HolidaysRequest(models.Model):
    _name = "hr.leave"
    _inherit = "hr.leave"
    
    @api.model
    def create(self, vals):
        result = super(HolidaysRequest, self).create(vals)
        result.send_mail()
        return result
    
    @api.multi
    def send_mail(self):
        incomplete_propation_period = self.env['hr.contract'].search([('employee_id', '=', self.employee_id.id), ('state','=','open'), ('trial_date_end','>',date.today())], limit=1)
        print(incomplete_propation_period)
        if incomplete_propation_period:
            raise UserError(_("You currently can't apply for leave as your probation period isn't over"))
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

        current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        self.filtered(lambda hol: hol.validation_type == 'both').write({'state': 'validate1', 'first_approver_id': current_employee.id}).send_manager_approved_mail()
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
            'email' : self.email,
            'customer': self.customer,
            'supplier' : self.supplier,
            'supplier' : self.company_id.id
        }
        self.env['res.partner'].create(vals)
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
    
    availability_id = fields.Many2one('availability.request', 'Availability Demand Form')
    
    product_id = fields.Many2one('product.product', 'Product')
    product_oum_qty = fields.Float(string="Quantity")
    price_cost  = fields.Float(string="Cost", related="product_id.standard_price")
    
class Expreliminary(models.Model):
    _name = 'expense.report'
   
    def _default_employee(self): # this method is to search the hr.employee and return the user id of the person clicking the form atm
        self.env['hr.employee'].search([('user_id','=',self.env.uid)])
        return self.env['hr.employee'].search([('user_id','=',self.env.uid)])
    
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Employee', default=_default_employee) #used as a signature to pull the currently employee    
    employee_sign_date = fields.Date(string='Date', default=date.today())# used as a signature date. 
       

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

    expense_id = fields.Many2one(comodel_name='expense.report')

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
   
    def _default_employee(self): # this method is to search the hr.employee and return the user id of the person clicking the form atm
        self.env['hr.employee'].search([('user_id','=',self.env.uid)])
        return self.env['hr.employee'].search([('user_id','=',self.env.uid)])

    date = fields.Date(string='Date')
    request_no = fields.Char(string='Request Number')
    site = fields.Char(string='Site')
    requester = fields.Char(string='Requester')

    reciever_id = fields.Many2one(comodel_name='hr.employee', string='Received By', default=_default_employee)
    receiver_sign_date = fields.Date(string='Date', default=date.today())

    line_ids = fields.One2many(comodel_name='parking.list.line',inverse_name='parking_id', string='Parking ID')

    employee_id = fields.Many2one(comodel_name='hr.employee', string='Name', default=_default_employee) #used as a signature to pull the currently employee    
    employee_sign_date = fields.Date(string='Date', default=date.today())# used as a signature date. 

    security_id = fields.Many2one(comodel_name='hr.employee', string='Name', default=_default_employee) #used as a signature to pull the currently employee    
    security_sign_date = fields.Date(string='Date', default=date.today())# used as a signature date. 



class parkinglistreport(models.Model):
    _name = 'parking.list.line'

    parking_id = fields.Many2one(comodel_name='hr.employee')

    serial_no = fields.Char(string='Serial No')
    item = fields.Char(string='Items')
    part_no = fields.Char(string='Part Number')
    quantity = fields.Char(string='Quantity')
    packaging = fields.Char(string='Partackaging') 
    
    
class paypreliminary(models.Model):
    _name = 'payment.request'

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

    purchase_id = fields.Many2one(comodel_name='payment.request')

    material = fields.Char(string='Material Need')
    specification = fields.Char(string='Specification')
    part_no = fields.Char(string='Part No')
    quantity = fields.Char(string='Quantity')
    unit = fields.Char(string='Unit')
    
    
    
    
    
    
    