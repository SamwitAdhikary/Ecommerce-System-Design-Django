import threading
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

def _send_email_thread(subject, html_content, to_email):
    """
    Worker function executed in a background daemon thread.
    Prevents SMTP network latency from blocking the Django HTTP request-response cycle.
    """
    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'YourStore <no-reply@yourstore.com>')
        msg = EmailMultiAlternatives(
            subject=subject,
            body="Your email client does not support HTML emails. Please contact support.",
            from_email=from_email,
            to=[to_email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
    except Exception as e:
        print(f"Error sending email to {to_email}: {e}")

def send_email_async(subject, html_content, to_email):
    """
    Spawns an asynchronous daemon thread for email dispatch.
    """
    thread = threading.Thread(
        target=_send_email_thread,
        args=(subject, html_content, to_email)
    )
    thread.daemon = True
    thread.start()

def send_otp_email(email, otp):
    """
    Renders the OTP verification HTML template and dispatches asynchronously.
    """
    subject = "Verify Your Email Address - YourStore"
    html_content = render_to_string('emails/otp_verification.html', {'otp': otp})
    send_email_async(subject, html_content, email)

def send_password_reset_email(email, reset_url):
    """
    Renders the Password Reset HTML template and dispatches asynchronously.
    """
    subject = "Reset Your Password - YourStore"
    html_content = render_to_string('emails/password_reset.html', {'reset_url': reset_url})
    send_email_async(subject, html_content, email)
