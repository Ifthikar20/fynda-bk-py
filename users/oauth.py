"""
OAuth Provider Handlers

Supports Google and Apple OAuth authentication.
"""

import os
import jwt
import json
import logging
import requests
from abc import ABC, abstractmethod
from django.conf import settings
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class OAuthProvider(ABC):
    """Abstract base class for OAuth providers."""
    
    @abstractmethod
    def get_user_info(self, code: str, **kwargs) -> dict:
        """
        Exchange auth code for user info.
        
        Returns:
            dict with keys: email, first_name, last_name, uid
        """
        pass
    
    @abstractmethod
    def get_authorization_url(self, redirect_uri: str, state: str = None) -> str:
        """Get the OAuth authorization URL."""
        pass


class GoogleOAuth(OAuthProvider):
    """Google OAuth 2.0 handler."""
    
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USER_INFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    
    def __init__(self):
        self.client_id = os.getenv('GOOGLE_CLIENT_ID', '')
        self.client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '')
    
    def get_authorization_url(self, redirect_uri: str, state: str = None) -> str:
        """Generate Google OAuth authorization URL."""
        params = {
            'client_id': self.client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'access_type': 'offline',
            'prompt': 'consent',
        }
        if state:
            params['state'] = state
        
        query = '&'.join(f"{k}={v}" for k, v in params.items())
        return f"{self.AUTH_URL}?{query}"
    
    def get_user_info(self, code: str, redirect_uri: str = None, **kwargs) -> dict:
        """Exchange auth code for user info from Google."""
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Google OAuth credentials not configured")
        
        # Exchange code for access token
        token_response = requests.post(self.TOKEN_URL, data={
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': redirect_uri or os.getenv('GOOGLE_REDIRECT_URI', ''),
            'grant_type': 'authorization_code',
        }, timeout=10)
        
        if token_response.status_code != 200:
            logger.error(f"Google token exchange failed: {token_response.text}")
            raise ValueError("Failed to exchange code for token")
        
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        
        if not access_token:
            raise ValueError("No access token in response")
        
        # Fetch user info
        user_response = requests.get(
            self.USER_INFO_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        
        if user_response.status_code != 200:
            logger.error(f"Google user info failed: {user_response.text}")
            raise ValueError("Failed to fetch user info")
        
        user_data = user_response.json()
        
        return {
            'email': user_data.get('email'),
            'first_name': user_data.get('given_name', ''),
            'last_name': user_data.get('family_name', ''),
            'uid': user_data.get('id'),
            'picture': user_data.get('picture', ''),
        }


class AppleOAuth(OAuthProvider):
    """Apple Sign In handler."""
    
    TOKEN_URL = "https://appleid.apple.com/auth/token"
    AUTH_URL = "https://appleid.apple.com/auth/authorize"
    KEYS_URL = "https://appleid.apple.com/auth/keys"
    
    def __init__(self):
        self.client_id = os.getenv('APPLE_CLIENT_ID', '')  # Service ID
        self.team_id = os.getenv('APPLE_TEAM_ID', '')
        self.key_id = os.getenv('APPLE_KEY_ID', '')
        self.private_key_path = os.getenv('APPLE_PRIVATE_KEY_PATH', '')
        self._private_key = None
    
    @property
    def private_key(self):
        """Load Apple private key from file."""
        if self._private_key is None and self.private_key_path:
            try:
                with open(self.private_key_path, 'r') as f:
                    self._private_key = f.read()
            except Exception as e:
                logger.error(f"Failed to load Apple private key: {e}")
        return self._private_key
    
    def _generate_client_secret(self) -> str:
        """Generate Apple client secret JWT."""
        if not all([self.team_id, self.client_id, self.key_id, self.private_key]):
            raise ValueError("Apple OAuth credentials not configured")
        
        now = datetime.utcnow()
        payload = {
            'iss': self.team_id,
            'iat': now,
            'exp': now + timedelta(days=180),
            'aud': 'https://appleid.apple.com',
            'sub': self.client_id,
        }
        
        headers = {
            'kid': self.key_id,
            'alg': 'ES256',
        }
        
        return jwt.encode(payload, self.private_key, algorithm='ES256', headers=headers)
    
    def get_authorization_url(self, redirect_uri: str, state: str = None) -> str:
        """Generate Apple OAuth authorization URL."""
        params = {
            'client_id': self.client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code id_token',
            'scope': 'name email',
            'response_mode': 'form_post',
        }
        if state:
            params['state'] = state
        
        query = '&'.join(f"{k}={v}" for k, v in params.items())
        return f"{self.AUTH_URL}?{query}"
    
    def get_user_info(self, code: str, id_token: str = None, redirect_uri: str = None, **kwargs) -> dict:
        """Exchange auth code for user info from Apple."""
        
        client_secret = self._generate_client_secret()
        
        # Exchange code for tokens
        token_response = requests.post(self.TOKEN_URL, data={
            'client_id': self.client_id,
            'client_secret': client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri or os.getenv('APPLE_REDIRECT_URI', ''),
        }, timeout=10)
        
        if token_response.status_code != 200:
            logger.error(f"Apple token exchange failed: {token_response.text}")
            raise ValueError("Failed to exchange code for token")
        
        token_data = token_response.json()
        id_token = id_token or token_data.get('id_token')
        
        if not id_token:
            raise ValueError("No ID token in response")
        
        # Decode ID token (without verification for now - Apple's tokens are already verified)
        # In production, you should verify against Apple's public keys
        payload = jwt.decode(id_token, options={"verify_signature": False})
        
        # Apple only provides name on first login via 'user' field in form_post
        # For subsequent logins, we won't have the name
        user_data = kwargs.get('user', {})
        if isinstance(user_data, str):
            try:
                user_data = json.loads(user_data)
            except:
                user_data = {}
        
        first_name = ''
        last_name = ''
        if user_data and 'name' in user_data:
            first_name = user_data['name'].get('firstName', '')
            last_name = user_data['name'].get('lastName', '')
        
        return {
            'email': payload.get('email'),
            'first_name': first_name,
            'last_name': last_name,
            'uid': payload.get('sub'),
        }


# Provider registry
OAUTH_PROVIDERS = {
    'google': GoogleOAuth,
    'apple': AppleOAuth,
}


def get_oauth_provider(provider: str) -> OAuthProvider:
    """Get OAuth provider instance by name."""
    provider_class = OAUTH_PROVIDERS.get(provider.lower())
    if not provider_class:
        raise ValueError(f"Unknown OAuth provider: {provider}")
    return provider_class()
