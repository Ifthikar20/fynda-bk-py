"""
User Views

Authentication and user management endpoints.
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model

from .serializers import UserSerializer, RegisterSerializer, LoginSerializer, ChangePasswordSerializer

User = get_user_model()


class RegisterView(APIView):
    """
    User registration endpoint.
    
    POST /api/auth/register/
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                "user": UserSerializer(user).data,
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                }
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """
    User login endpoint.
    
    POST /api/auth/login/
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user = authenticate(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"]
        )
        
        if not user:
            return Response(
                {"error": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {"error": "Account is disabled"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            "user": UserSerializer(user).data,
            "tokens": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        })


class ProfileView(APIView):
    """
    User profile endpoint.
    
    GET /api/auth/profile/ - Get current user profile
    PATCH /api/auth/profile/ - Update profile
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    """
    Change password endpoint.
    
    POST /api/auth/change-password/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        if not request.user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"old_password": "Incorrect password"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        
        return Response({"message": "Password changed successfully"})


class LogoutView(APIView):
    """
    Logout endpoint - blacklists refresh token.
    
    POST /api/auth/logout/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({"message": "Logged out successfully"})
        except Exception:
            return Response({"message": "Logged out"})


class OAuthView(APIView):
    """
    OAuth callback endpoint for social login.
    
    POST /api/auth/oauth/
    Body: {
        "provider": "google" | "apple",
        "code": "authorization_code",
        "redirect_uri": "callback_url",
        "id_token": "apple_id_token" (Apple only),
        "user": {"name": {...}} (Apple first login only)
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        from users.services import UserService
        from fynda.exceptions import ValidationError as FyndaValidation, AuthenticationError

        provider = request.data.get('provider', '').lower()
        code = request.data.get('code')
        redirect_uri = request.data.get('redirect_uri')
        
        if not provider or not code:
            return Response(
                {"error": "Missing provider or code"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if provider not in ['google', 'apple']:
            return Response(
                {"error": "Invalid provider. Use 'google' or 'apple'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Build extra params for Apple
            extra_params = {}
            if provider == 'apple':
                extra_params['id_token'] = request.data.get('id_token')
                extra_params['user'] = request.data.get('user', {})

            # Exchange code for user info
            user_info = UserService.get_oauth_user_info(
                provider, code, redirect_uri, **extra_params
            )

            # Authenticate or create user
            user, created = UserService.authenticate_oauth(provider, user_info)
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                "user": UserSerializer(user).data,
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
                "created": created,
            })
            
        except FyndaValidation as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except AuthenticationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception("OAuth error")
            return Response(
                {"error": "OAuth authentication failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

