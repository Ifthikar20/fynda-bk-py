"""
Email Sending Service using AWS SES
"""

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
import logging
import time

from .models import Subscriber, Campaign, CampaignSend

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via AWS SES"""
    
    def __init__(self):
        self.from_email = getattr(
            settings, 
            'DEFAULT_FROM_EMAIL', 
            'Fynda <noreply@fynda.shop>'
        )
        self.base_url = getattr(
            settings,
            'SITE_URL',
            'https://fynda.shop'
        )
    
    def send_single(self, to_email, subject, html_content, text_content=None):
        """
        Send a single email
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML body
            text_content: Plain text body (optional)
        
        Returns:
            bool: Success status
        """
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content or self._strip_html(html_content),
                from_email=self.from_email,
                to=[to_email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            logger.info(f"Email sent to {to_email}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_campaign(self, campaign: Campaign, batch_size=50, delay=1):
        """
        Send a campaign to all active subscribers
        
        Args:
            campaign: Campaign model instance
            batch_size: Number of emails per batch
            delay: Seconds to wait between batches (rate limiting)
        """
        if campaign.status not in ['draft', 'scheduled']:
            logger.error(f"Campaign {campaign.id} cannot be sent (status: {campaign.status})")
            return
        
        # Update campaign status
        campaign.status = 'sending'
        campaign.save()
        
        # Get target subscribers
        subscribers = Subscriber.objects.filter(
            is_active=True,
            is_verified=True
        )
        
        # Apply preference filters if specified
        if campaign.target_preferences:
            # Filter by categories if specified
            categories = campaign.target_preferences.get('categories', [])
            if categories:
                subscribers = subscribers.filter(
                    preferences__categories__overlap=categories
                )
        
        total_sent = 0
        total_failed = 0
        
        # Process in batches
        subscriber_list = list(subscribers)
        for i in range(0, len(subscriber_list), batch_size):
            batch = subscriber_list[i:i + batch_size]
            
            for subscriber in batch:
                success = self._send_campaign_email(campaign, subscriber)
                if success:
                    total_sent += 1
                else:
                    total_failed += 1
            
            # Rate limiting delay between batches
            if i + batch_size < len(subscriber_list):
                time.sleep(delay)
        
        # Update campaign stats
        campaign.status = 'sent'
        campaign.sent_at = timezone.now()
        campaign.total_sent = total_sent
        campaign.save()
        
        logger.info(
            f"Campaign {campaign.name} sent: {total_sent} success, {total_failed} failed"
        )
    
    def _send_campaign_email(self, campaign: Campaign, subscriber: Subscriber):
        """Send campaign email to a single subscriber with tracking"""
        
        # Create or get send record
        send, created = CampaignSend.objects.get_or_create(
            campaign=campaign,
            subscriber=subscriber
        )
        
        if not created:
            # Already sent to this subscriber
            return True
        
        # Prepare tracking URLs
        tracking_pixel = f"{self.base_url}/api/email/track/open/{send.tracking_id}/"
        unsubscribe_url = f"{self.base_url}/api/unsubscribe/{subscriber.unsubscribe_token}/"
        
        # Add tracking pixel and unsubscribe link to HTML
        html_content = campaign.content_html
        html_content = html_content.replace(
            '</body>',
            f'<img src="{tracking_pixel}" width="1" height="1" alt="" />'
            f'<p style="text-align:center;font-size:12px;color:#666;">'
            f'<a href="{unsubscribe_url}">Unsubscribe</a></p></body>'
        )
        
        # Replace tracked links (wrap all links)
        html_content = self._add_link_tracking(html_content, send.tracking_id)
        
        # Send email
        try:
            msg = EmailMultiAlternatives(
                subject=campaign.subject,
                body=campaign.content_text or self._strip_html(campaign.content_html),
                from_email=self.from_email,
                to=[subscriber.email]
            )
            msg.attach_alternative(html_content, "text/html")
            
            # Add custom headers
            msg.extra_headers = {
                'X-Campaign-ID': str(campaign.id),
                'X-Subscriber-ID': str(subscriber.id),
                'List-Unsubscribe': f'<{unsubscribe_url}>',
            }
            
            msg.send()
            send.delivered = True
            send.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send campaign to {subscriber.email}: {str(e)}")
            send.delivered = False
            send.bounced = True
            send.bounce_reason = str(e)
            send.save()
            return False
    
    def _add_link_tracking(self, html_content, tracking_id):
        """Add click tracking to links in HTML content"""
        import re
        
        def replace_link(match):
            url = match.group(1)
            # Don't track unsubscribe or tracking links
            if 'unsubscribe' in url.lower() or 'track' in url.lower():
                return match.group(0)
            
            tracked_url = (
                f"{self.base_url}/api/email/track/click/{tracking_id}/"
                f"?url={url}"
            )
            return f'href="{tracked_url}"'
        
        # Replace href attributes
        pattern = r'href="([^"]+)"'
        return re.sub(pattern, replace_link, html_content)
    
    def _strip_html(self, html_content):
        """Convert HTML to plain text"""
        import re
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html_content)
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def send_welcome_email(self, subscriber: Subscriber):
        """Send welcome email to new subscriber"""
        
        subject = "Welcome to Fynda! 🎉"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                     max-width: 600px; margin: 0 auto; padding: 20px; background: #f8f9fa;">
            <div style="background: white; border-radius: 16px; padding: 40px; 
                        box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                <h1 style="color: #1a1a1a; margin-bottom: 20px;">
                    Welcome to Fynda!
                </h1>
                <p style="color: #666; font-size: 16px; line-height: 1.6;">
                    Hi{' ' + subscriber.name if subscriber.name else ''}! 👋
                </p>
                <p style="color: #666; font-size: 16px; line-height: 1.6;">
                    Thanks for signing up for early access to Fynda - your AI-powered 
                    shopping assistant that finds the best deals for you.
                </p>
                <p style="color: #666; font-size: 16px; line-height: 1.6;">
                    We're working hard to bring you:
                </p>
                <ul style="color: #666; font-size: 16px; line-height: 1.8;">
                    <li>🔍 AI-powered product search</li>
                    <li>📷 Visual search - upload any image to find similar products</li>
                    <li>💰 Best price comparisons from top retailers</li>
                    <li>🔔 Price drop alerts for items you love</li>
                </ul>
                <p style="color: #666; font-size: 16px; line-height: 1.6;">
                    We'll email you as soon as we launch!
                </p>
                <div style="margin-top: 30px; text-align: center;">
                    <a href="https://fynda.shop" 
                       style="display: inline-block; background: linear-gradient(135deg, #22c55e, #16a34a);
                              color: white; padding: 14px 32px; border-radius: 8px;
                              text-decoration: none; font-weight: 600;">
                        Visit Fynda
                    </a>
                </div>
            </div>
            <p style="text-align: center; color: #999; font-size: 12px; margin-top: 20px;">
                <a href="{self.base_url}/api/unsubscribe/{subscriber.unsubscribe_token}/" 
                   style="color: #999;">Unsubscribe</a>
            </p>
        </body>
        </html>
        """
        
        return self.send_single(subscriber.email, subject, html_content)


# Singleton instance
email_service = EmailService()
