"""
Email Marketing Views and API Endpoints
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import logging

from .models import Subscriber, Campaign, CampaignSend

logger = logging.getLogger(__name__)

# 1x1 transparent PNG for tracking pixel
TRACKING_PIXEL = bytes([
    0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D,
    0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4, 0x89, 0x00, 0x00, 0x00,
    0x0A, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
    0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49,
    0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
])


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def subscribe(request):
    """
    Subscribe a new email address
    
    POST /api/subscribe/
    {
        "email": "user@example.com",
        "name": "John Doe",  // optional
        "source": "website"  // optional
    }
    """
    email = request.data.get('email', '').strip().lower()
    name = request.data.get('name', '').strip()
    source = request.data.get('source', 'website')
    
    # Validate email
    if not email:
        return Response(
            {'error': 'Email address is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        validate_email(email)
    except ValidationError:
        return Response(
            {'error': 'Invalid email address'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if already subscribed
    existing = Subscriber.objects.filter(email=email).first()
    if existing:
        if existing.is_active:
            return Response(
                {'message': 'You are already subscribed!'},
                status=status.HTTP_200_OK
            )
        else:
            # Reactivate subscription
            existing.is_active = True
            existing.unsubscribed_at = None
            existing.save()
            return Response(
                {'message': 'Welcome back! Your subscription has been reactivated.'},
                status=status.HTTP_200_OK
            )
    
    # Get IP address
    ip_address = get_client_ip(request)
    
    # Create subscriber
    subscriber = Subscriber.objects.create(
        email=email,
        name=name,
        source=source,
        ip_address=ip_address,
        is_verified=True  # Auto-verify for now, can add email verification later
    )
    
    logger.info(f"New subscriber: {email} from {source}")
    
    return Response(
        {
            'message': 'Successfully subscribed! We\'ll notify you when Fynda launches.',
            'subscriber_id': str(subscriber.id)
        },
        status=status.HTTP_201_CREATED
    )


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def unsubscribe(request, token):
    """
    Unsubscribe using token
    
    GET/POST /api/unsubscribe/<token>/
    """
    try:
        subscriber = Subscriber.objects.get(unsubscribe_token=token)
    except Subscriber.DoesNotExist:
        return Response(
            {'error': 'Invalid unsubscribe link'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if not subscriber.is_active:
        return Response(
            {'message': 'You are already unsubscribed'},
            status=status.HTTP_200_OK
        )
    
    subscriber.is_active = False
    subscriber.unsubscribed_at = timezone.now()
    subscriber.save()
    
    logger.info(f"Unsubscribed: {subscriber.email}")
    
    return Response(
        {'message': 'You have been successfully unsubscribed.'},
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def track_open(request, tracking_id):
    """
    Track email open via pixel
    
    GET /api/email/track/open/<tracking_id>/
    """
    try:
        send = CampaignSend.objects.get(tracking_id=tracking_id)
        
        # Update open stats
        send.open_count += 1
        if not send.opened:
            send.opened = True
            send.opened_at = timezone.now()
            
            # Update campaign stats
            send.campaign.total_opened += 1
            send.campaign.save(update_fields=['total_opened'])
        
        send.save()
        
    except CampaignSend.DoesNotExist:
        pass  # Silently ignore invalid tracking IDs
    
    # Return 1x1 transparent PNG
    return HttpResponse(
        TRACKING_PIXEL,
        content_type='image/png'
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def track_click(request, tracking_id):
    """
    Track email link click and redirect
    
    GET /api/email/track/click/<tracking_id>/?url=<redirect_url>
    """
    redirect_url = request.GET.get('url', 'https://fynda.shop')
    
    try:
        send = CampaignSend.objects.get(tracking_id=tracking_id)
        
        # Update click stats
        send.click_count += 1
        if not send.clicked:
            send.clicked = True
            send.clicked_at = timezone.now()
            
            # Update campaign stats
            send.campaign.total_clicked += 1
            send.campaign.save(update_fields=['total_clicked'])
        
        send.save()
        
    except CampaignSend.DoesNotExist:
        pass  # Silently ignore invalid tracking IDs
    
    # Redirect to destination
    from django.shortcuts import redirect
    return redirect(redirect_url)


@api_view(['GET'])
@permission_classes([AllowAny])
def subscriber_count(request):
    """
    Get subscriber count
    
    GET /api/subscribers/count/
    """
    count = Subscriber.objects.filter(is_active=True).count()
    
    return Response({
        'count': count,
        'display': format_subscriber_count(count)
    })


def get_client_ip(request):
    """Extract client IP from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def format_subscriber_count(count):
    """Format subscriber count for display"""
    if count < 100:
        return str(count)
    elif count < 1000:
        return f"{count}+"
    elif count < 10000:
        return f"{count // 100 * 100}+"
    else:
        return f"{count // 1000}K+"
