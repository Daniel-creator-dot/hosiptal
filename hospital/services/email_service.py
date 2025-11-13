"""
Email Service for Lab Results and Notifications
Sends HTML formatted emails with optional PDF attachments
"""
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from email.mime.application import MIMEApplication
import logging
import os

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for sending notifications"""
    
    def __init__(self):
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@primecare.com')
        self.hospital_name = getattr(settings, 'HOSPITAL_NAME', 'PrimeCare Hospital')
        self.hospital_logo_url = getattr(settings, 'HOSPITAL_LOGO_URL', '')
        self.site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    
    def send_email(self, recipient_email, subject, message_html, message_text=None,
                   attachment_path=None, attachment_name=None, recipient_name=''):
        """
        Send email with HTML content and optional attachment
        
        Args:
            recipient_email: Recipient email address
            subject: Email subject
            message_html: HTML email content
            message_text: Plain text fallback (auto-generated from HTML if not provided)
            attachment_path: Path to file attachment (e.g., PDF report)
            attachment_name: Name for the attachment file
            recipient_name: Name of recipient
            
        Returns:
            dict with status and details
        """
        result = {
            'success': False,
            'status': 'failed',
            'message': '',
            'sent_at': None,
            'recipient_email': recipient_email,
            'recipient_name': recipient_name
        }
        
        try:
            # Validate email
            if not recipient_email or not recipient_email.strip():
                result['message'] = "Email address is required"
                return result
            
            # Create email message
            if not message_text:
                # Strip HTML tags for plain text version (basic version)
                import re
                message_text = re.sub('<[^<]+?>', '', message_html)
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=message_text,
                from_email=self.from_email,
                to=[recipient_email]
            )
            
            # Attach HTML version
            email.attach_alternative(message_html, "text/html")
            
            # Attach file if provided
            if attachment_path and os.path.exists(attachment_path):
                with open(attachment_path, 'rb') as f:
                    file_data = f.read()
                    file_name = attachment_name or os.path.basename(attachment_path)
                    email.attach(file_name, file_data, 'application/pdf')
            
            # Send email
            email.send(fail_silently=False)
            
            result['success'] = True
            result['status'] = 'sent'
            result['sent_at'] = timezone.now()
            result['message'] = 'Email sent successfully'
            
        except Exception as e:
            logger.error(f"Email send error: {str(e)}", exc_info=True)
            result['message'] = f"Email error: {str(e)}"
        
        return result
    
    def send_lab_result_email(self, lab_result, patient, include_pdf=False, pdf_path=''):
        """Send lab result notification email with professional HTML template"""
        try:
            test = lab_result.test
            
            # Prepare template context
            context = {
                'patient': patient,
                'lab_result': lab_result,
                'test': test,
                'hospital_name': self.hospital_name,
                'hospital_logo_url': self.hospital_logo_url,
                'site_url': self.site_url,
                'year': timezone.now().year,
            }
            
            # Render HTML email template
            html_content = self._render_lab_result_html(context)
            
            # Prepare subject
            subject = f"Lab Result Ready: {test.name} - {self.hospital_name}"
            
            # Get patient email
            email_address = patient.email
            if hasattr(patient, 'notification_preference'):
                pref = patient.notification_preference
                email_address = pref.get_email()
            
            if not email_address:
                return {
                    'success': False,
                    'message': f"Patient {patient.full_name} does not have an email address",
                    'status': 'failed'
                }
            
            # Send email
            return self.send_email(
                recipient_email=email_address,
                subject=subject,
                message_html=html_content,
                attachment_path=pdf_path if include_pdf else None,
                attachment_name=f"Lab_Result_{test.code}_{patient.mrn}.pdf" if include_pdf else None,
                recipient_name=patient.full_name
            )
            
        except Exception as e:
            logger.error(f"Error sending lab result email: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f"Error: {str(e)}",
                'status': 'failed'
            }
    
    def _render_lab_result_html(self, context):
        """Render HTML email template for lab results"""
        # Try to use Django template if available
        try:
            from django.template.loader import render_to_string
            return render_to_string('hospital/emails/lab_result_notification.html', context)
        except:
            # Fallback to inline HTML template
            return self._get_lab_result_html_template(context)
    
    def _get_lab_result_html_template(self, context):
        """Generate HTML email template inline"""
        patient = context['patient']
        lab_result = context['lab_result']
        test = context['test']
        hospital_name = context['hospital_name']
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Lab Result Notification</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f4f4f4;
                }}
                .email-container {{
                    background-color: #ffffff;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                }}
                .content {{
                    padding: 30px;
                }}
                .result-box {{
                    background-color: #f8f9fa;
                    border-left: 4px solid #667eea;
                    padding: 20px;
                    margin: 20px 0;
                    border-radius: 5px;
                }}
                .result-item {{
                    margin: 10px 0;
                }}
                .result-label {{
                    font-weight: bold;
                    color: #555;
                }}
                .abnormal-warning {{
                    background-color: #fff3cd;
                    border-left: 4px solid #ffc107;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 5px;
                }}
                .footer {{
                    background-color: #f8f9fa;
                    padding: 20px;
                    text-align: center;
                    font-size: 12px;
                    color: #666;
                }}
                .button {{
                    display: inline-block;
                    padding: 12px 30px;
                    background-color: #667eea;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 20px 0;
                }}
                .button:hover {{
                    background-color: #764ba2;
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <h1>🏥 {hospital_name}</h1>
                    <p style="margin: 5px 0 0 0;">Lab Results Notification</p>
                </div>
                
                <div class="content">
                    <p>Dear <strong>{patient.first_name}</strong>,</p>
                    
                    <p>Your laboratory test results are now available.</p>
                    
                    <div class="result-box">
                        <h3 style="margin-top: 0; color: #667eea;">Test Information</h3>
                        <div class="result-item">
                            <span class="result-label">Test Name:</span> {test.name}
                        </div>
                        <div class="result-item">
                            <span class="result-label">Test Code:</span> {test.code}
                        </div>
                        <div class="result-item">
                            <span class="result-label">Patient MRN:</span> {patient.mrn}
                        </div>
        """
        
        # Add result details if available
        if lab_result.status == 'completed' and lab_result.value:
            html += f"""
                        <hr style="margin: 15px 0; border: none; border-top: 1px solid #ddd;">
                        <h4 style="margin: 15px 0 10px 0; color: #667eea;">Result</h4>
                        <div class="result-item">
                            <span class="result-label">Value:</span> {lab_result.value}"""
            
            if lab_result.units:
                html += f" {lab_result.units}"
            
            html += "</div>"
            
            if lab_result.range_low and lab_result.range_high:
                html += f"""
                        <div class="result-item">
                            <span class="result-label">Normal Range:</span> {lab_result.range_low} - {lab_result.range_high}
                        </div>"""
            
            # Add abnormal warning
            if lab_result.is_abnormal:
                html += """
                    </div>
                    <div class="abnormal-warning">
                        <strong>⚠️ Abnormal Result</strong><br>
                        This result is outside the normal range. Please consult with your doctor for proper interpretation and follow-up.
                    </div>
                    <div class="result-box">"""
        
        # Add verification info
        if lab_result.verified_by:
            verifier = lab_result.verified_by.user.get_full_name() or lab_result.verified_by.user.username
            html += f"""
                        <div class="result-item">
                            <span class="result-label">Verified by:</span> Dr. {verifier}
                        </div>"""
        
        if lab_result.verified_at:
            verified_date = lab_result.verified_at.strftime('%B %d, %Y at %I:%M %p')
            html += f"""
                        <div class="result-item">
                            <span class="result-label">Verified on:</span> {verified_date}
                        </div>"""
        
        # Close result box and add portal link
        html += """
                    </div>
                    
                    <p style="text-align: center; margin: 30px 0;">
                        <a href="{site_url}/patient-portal" class="button">
                            View Full Report in Patient Portal
                        </a>
                    </p>
                    
                    <p style="color: #666; font-size: 14px;">
                        <strong>Note:</strong> This is an automated notification. For detailed interpretation and medical advice, please consult with your healthcare provider.
                    </p>
                </div>
                
                <div class="footer">
                    <p><strong>{hospital_name}</strong></p>
                    <p>This email contains confidential medical information intended only for {patient.full_name}.</p>
                    <p>If you received this email in error, please delete it immediately.</p>
                    <p style="margin-top: 15px;">&copy; {year} {hospital_name}. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """.format(**context)
        
        return html


# Singleton instance
email_service = EmailService()












