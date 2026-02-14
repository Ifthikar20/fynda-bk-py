"""
User Services
=============

Business logic for user operations, extracted from views.
"""

from django.contrib.auth import get_user_model

from core.services import BaseService
from core.exceptions import AuthenticationError, ValidationError

User = get_user_model()


class UserService(BaseService):
    """
    Centralised user business logic.

    Extracted from OAuthView so both web and mobile flows share
    the same authenticate-or-create logic.
    """

    @classmethod
    def authenticate_oauth(cls, provider: str, user_info: dict) -> tuple:
        """
        Authenticate (or create) a user via OAuth provider info.

        Steps:
            1. Look up by OAuth UID (strongest match)
            2. Fall back to email lookup
            3. Link existing email account to OAuth if unlinked
            4. Create new user if no match

        Args:
            provider: 'google' or 'apple'
            user_info: dict with keys: email, uid, first_name, last_name

        Returns:
            (user, created) tuple

        Raises:
            ValidationError: if email is missing
            AuthenticationError: if account is disabled
        """
        email = user_info.get("email")
        if not email:
            raise ValidationError("Could not retrieve email from provider")

        uid = user_info.get("uid")
        user = None
        created = False

        # 1. Look up by OAuth UID
        if uid:
            user = User.objects.filter(
                oauth_provider=provider,
                oauth_uid=uid,
            ).first()

        # 2. Fall back to email
        if not user:
            user = User.objects.filter(email__iexact=email).first()

            if user and not user.oauth_provider:
                # 3. Link existing email account to OAuth
                user.oauth_provider = provider
                user.oauth_uid = uid
                user.save(update_fields=["oauth_provider", "oauth_uid"])
                cls.logger.info("Linked existing user %s to %s OAuth", email, provider)

        # 4. Create new user
        if not user:
            with cls.atomic():
                user = User.objects.create_user(
                    email=email,
                    password=None,  # OAuth users don't have passwords
                    first_name=user_info.get("first_name", ""),
                    last_name=user_info.get("last_name", ""),
                    oauth_provider=provider,
                    oauth_uid=uid,
                )
            created = True
            cls.logger.info("Created new OAuth user %s via %s", email, provider)

        if not user.is_active:
            raise AuthenticationError("Account is disabled")

        return user, created

    @classmethod
    def get_oauth_user_info(cls, provider: str, code: str, redirect_uri: str, **extra_params) -> dict:
        """
        Exchange OAuth code for user info via the provider adapter.

        Args:
            provider: 'google' or 'apple'
            code: authorisation code
            redirect_uri: callback URL
            **extra_params: id_token, user (Apple)

        Returns:
            dict with email, uid, first_name, last_name
        """
        from users.oauth import get_oauth_provider

        oauth = get_oauth_provider(provider)
        return oauth.get_user_info(code=code, redirect_uri=redirect_uri, **extra_params)
