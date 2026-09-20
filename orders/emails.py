from decimal import Decimal
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import escape
from .utils import generate_cart_recovery_token, build_cart_recovery_url


def send_abandoned_cart_email(cart, recovery_token: str | None = None) -> bool:
    """
    Formats and dispatches a multipart HTML and plain-text abandoned cart recovery email
    to the customer owning the cart, including line item details and a signed recovery link.
    """
    if not cart.user or not cart.user.email:
        return False

    if not recovery_token:
        recovery_token = generate_cart_recovery_token(cart)

    recovery_url = build_cart_recovery_url(recovery_token)
    recipient_email = cart.user.email
    recipient_name = cart.user.first_name or cart.user.email.split('@')[0]
    site_name = getattr(settings, 'SITE_NAME', 'Modern Storefront')
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@modernstore.com')

    subject = f"You left something behind at {site_name}! Complete your order"

    # Assemble item summaries
    items = cart.items.select_related('product', 'variant').all()
    if not items:
        return False

    subtotal_str = f"Rs.{cart.subtotal:.2f}"

    # Plain-text version
    text_lines = [
        f"Hi {recipient_name},",
        "",
        f"We noticed you left items in your shopping cart at {site_name}.",
        "Your selections are waiting for you, but popular sizes and items sell out quickly!",
        "",
        "YOUR SHOPPING MANIFEST:",
        "--------------------------------------------------",
    ]
    for item in items:
        variant_name = f" ({item.variant.name})" if item.variant else ""
        text_lines.append(
            f"• {item.quantity}x {item.product.name}{variant_name} - Rs.{item.line_total:.2f}"
        )
    text_lines.extend([
        "--------------------------------------------------",
        f"Cart Subtotal: {subtotal_str}",
        "",
        "Click the link below to restore your cart and proceed directly to checkout:",
        recovery_url,
        "",
        f"Thank you for shopping with {site_name}!",
    ])
    text_content = "\n".join(text_lines)

    # HTML version
    items_html_rows = []
    for item in items:
        variant_name = f"<br><small style='color: #666;'>Variant: {escape(item.variant.name)}</small>" if item.variant else ""
        items_html_rows.append(f"""
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: left;">
                    <strong>{escape(item.product.name)}</strong>{variant_name}
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center;">{item.quantity}</td>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: right;">Rs.{item.line_total:.2f}</td>
            </tr>
        """)
    items_table_html = "".join(items_html_rows)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 20px; background-color: #f8fafc;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
            <div style="background: #0f172a; padding: 24px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 22px; font-weight: 600;">{escape(site_name)}</h1>
            </div>
            <div style="padding: 32px 24px;">
                <h2 style="margin-top: 0; color: #1e293b; font-size: 20px;">You left items in your cart!</h2>
                <p>Hi {escape(recipient_name)},</p>
                <p>We saved the items you were looking at so you can pick up right where you left off:</p>
                
                <table style="width: 100%; border-collapse: collapse; margin: 24px 0;">
                    <thead>
                        <tr style="background: #f1f5f9; color: #475569; font-size: 13px; text-transform: uppercase;">
                            <th style="padding: 10px 12px; text-align: left;">Product</th>
                            <th style="padding: 10px 12px; text-align: center;">Qty</th>
                            <th style="padding: 10px 12px; text-align: right;">Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_table_html}
                    </tbody>
                    <tfoot>
                        <tr>
                            <td colspan="2" style="padding: 14px 12px; text-align: right; font-weight: 600; font-size: 16px;">Subtotal:</td>
                            <td style="padding: 14px 12px; text-align: right; font-weight: 700; font-size: 16px; color: #0f172a;">{subtotal_str}</td>
                        </tr>
                    </tfoot>
                </table>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="{escape(recovery_url)}" style="background: #2563eb; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: 600; display: inline-block;">Complete Your Order</a>
                </div>

                <p style="font-size: 13px; color: #64748b; text-align: center; margin-top: 24px;">
                    Button not working? Copy and paste this link into your browser:<br>
                    <a href="{escape(recovery_url)}" style="color: #2563eb; word-break: break-all;">{escape(recovery_url)}</a>
                </p>
            </div>
            <div style="background: #f8fafc; padding: 16px 24px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0;">
                © {site_name}. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=[recipient_email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)
    return True
