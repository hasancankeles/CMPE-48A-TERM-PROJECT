from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.conf import settings
from django.db.models import Q

from .serializers import (
    UserSerializer,
    ChangePasswordSerializer,
    ContactInfoSerializer,
    PhotoSerializer,
    PhotoUploadSerializer,
    AllergenInputSerializer,
    AllergenOutputSerializer,
    TagInputSerializer,
    TagOutputSerializer,
    ReportSerializer,
    UserMetricsSerializer,
    NutritionTargetsSerializer,
)

from .services import register_user, list_users, update_user
from .models import User, Allergen, Tag, UserTag, Follow
from forum.models import Like, Post, Recipe
from forum.serializers import PostSerializer, RecipeSerializer
import os
from google.cloud import storage
import logging
from google.auth import default as google_auth_default

logger = logging.getLogger(__name__)


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom login view that extends TokenObtainPairView.
    After successful login, publishes a notification to Pub/Sub
    for sending login email to the user.
    """
    
    def post(self, request, *args, **kwargs):
        # Call the parent's post method to handle authentication
        response = super().post(request, *args, **kwargs)
        
        # If login was successful (status 200), send login notification
        if response.status_code == 200:
            try:
                # Get the user from the request data
                username = request.data.get('username')
                if username:
                    user = User.objects.get(username=username)
                    
                    # Publish login notification to Pub/Sub
                    from .email_utils import publish_login_notification
                    publish_login_notification(user, request)
                    
            except User.DoesNotExist:
                logger.warning(f"User {username} not found for login notification")
            except Exception as e:
                # Don't fail the login if notification fails
                logger.error(f"Failed to send login notification: {e}")
        
        return response


class UserListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        GET /
        Fetch and return a list of all users in the system.
        """
        users = list_users()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


class CreateUserView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.create(serializer.validated_data)
            return Response(
                UserSerializer(user).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UpdateUserView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = ContactInfoSerializer(data=request.data)
        if serializer.is_valid():
            user = update_user(request.user, serializer.validated_data)
            return Response(
                UserSerializer(user).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            user = request.user
            user.set_password(
                serializer.validated_data["new_password"]
            )  # Hashes password internally
            user.save()
            return Response(
                {"detail": "Password changed successfully"}, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    # use jwt authentication
    authentication_classes = [JWTAuthentication]
    # require authentication
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        GET /profile/
        Fetch the current user's profile information.
        """
        # current user is available in request.user
        user = request.user
        # serialize user data
        serializer = UserSerializer(user)
        return Response(serializer.data)


class PublicUserProfileView(APIView):
    """
    GET /users/@{username}/
    Fetch a user's public profile information by username.
    Authentication is optional - works for both authenticated and anonymous users.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, username):
        try:
            user = User.objects.get(username=username)
            serializer = UserSerializer(user)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )


class LogoutView(APIView):
    """
    POST /users/token/logout/
    Body: { "refresh": "<refresh_token>" }
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class AllergenAddView(APIView):
    # use jwt authentication
    authentication_classes = [JWTAuthentication]
    # require authentication
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        GET /profile/
        Fetch the current user's profile information.
        """
        # current user is available in request.user
        # serialize user data
        serializer = AllergenOutputSerializer(data=request.data)
        if serializer.is_valid():
            allergen = serializer.save()
            return Response(
                AllergenOutputSerializer(allergen).data, status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AllergenSetView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        POST /allergens/
        Set or add allergens for the current user.
        Accepts a list of allergens, each with optional id or name/common fields.
        """
        data = request.data
        user = request.user

        if not isinstance(data, list):
            return Response(
                {"detail": "Expected a list of allergens."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AllergenInputSerializer(data=data, many=True)
        if serializer.is_valid():
            allergens = []
            for allergen_data in serializer.validated_data:
                if "id" in allergen_data:
                    # Attach existing allergen by ID
                    try:
                        allergen = Allergen.objects.get(id=allergen_data["id"])
                    except Allergen.DoesNotExist:
                        continue
                elif "name" in allergen_data:
                    # Create new allergen if not exists
                    allergen, _ = Allergen.objects.get_or_create(
                        name=allergen_data["name"],
                        defaults={"common": allergen_data.get("common", False)},
                    )
                else:
                    # Skip invalid entries
                    continue

                allergens.append(allergen)

            # Replace user's allergens
            user.allergens.set(allergens)

            # Return serialized allergens
            response_serializer = AllergenOutputSerializer(allergens, many=True)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TagSetView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        user = request.user

        # Expecting a list of tag objects
        if not isinstance(data, list):
            return Response(
                {"detail": "Expected a list of tags."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = TagInputSerializer(data=data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        tags = []
        for tag_data in serializer.validated_data:
            if "id" in tag_data:
                try:
                    tag = Tag.objects.get(id=tag_data["id"])
                except Tag.DoesNotExist:
                    continue
            elif "name" in tag_data:
                # Validate and sanitize tag name
                tag_name = tag_data["name"].strip()

                # Check if name is empty after stripping
                if not tag_name:
                    return Response(
                        {"detail": "Tag name cannot be empty."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Check max length (Tag model has max_length=64)
                if len(tag_name) > 64:
                    return Response(
                        {"detail": "Tag name cannot exceed 64 characters."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                tag, _ = Tag.objects.get_or_create(name=tag_name)
            else:
                continue  # skip invalid entries

            tags.append(tag)

        # Clear existing UserTag relationships
        UserTag.objects.filter(user=user).delete()

        # Create new UserTag relationships
        for tag in tags:
            UserTag.objects.create(user=user, tag=tag, verified=False)

        # Serialize response with user context
        response_serializer = TagOutputSerializer(
            tags, many=True, context={"user": user}
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class GetCommonAllergensView(APIView):
    # use jwt authentication
    authentication_classes = []
    # require authentication
    permission_classes = [AllowAny]

    def get(self, request):
        """
        GET /common-allergens/
        Fetch a list of common allergens.
        """
        common_allergens = Allergen.objects.filter(common=True)
        serializer = AllergenOutputSerializer(common_allergens, many=True)
        return Response(serializer.data)


class ProfileImageView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [permission() for permission in self.permission_classes]

    def get(self, request):
        user_id = (
            request.query_params.get("user_id") or request.user.id
        )  # Optional user_id param
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = PhotoSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        user = request.user
        image = request.FILES.get("profile_image")

        logger.info(
            "Profile image upload attempt: user_id=%s, size=%s, content_type=%s",
            getattr(user, "id", None),
            getattr(image, "size", None),
            getattr(image, "content_type", None),
        )

        if not image:
            return Response(
                {"detail": "No image file uploaded."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        #  Validate file size (max 5 MB)
        max_size = 5 * 1024 * 1024  # 5 MB in bytes
        if image.size > max_size:
            return Response(
                {"detail": "File size exceeds 5 MB limit."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        #  Validate file type
        valid_mime_types = ["image/jpeg", "image/png"]
        if image.content_type not in valid_mime_types:
            return Response(
                {"detail": "Only JPG and PNG images are allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Upload to GCS and store gs:// URI
        bucket_name = os.environ.get("GCS_MEDIA_BUCKET") or os.environ.get("CLOUD_STORAGE_BUCKET")
        if not bucket_name:
            logger.warning("GCS config missing for profile image upload: no bucket configured")
            return Response(
                {"detail": "GCS configuration missing. Set GCS_MEDIA_BUCKET or CLOUD_STORAGE_BUCKET."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        try:
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            ext = ".jpg" if image.content_type == "image/jpeg" else ".png"
            object_name = f"profile_images/{str(user.profile_image_token)}{ext}"
            blob = bucket.blob(object_name)
            blob.cache_control = "public, max-age=86400"
            blob.upload_from_file(image, content_type=image.content_type)

            # Save URI on user and clear local field
            if hasattr(user, "profile_image_gcs_uri"):
                user.profile_image_gcs_uri = f"gs://{bucket_name}/{object_name}"
                user.profile_image = None
                user.save(update_fields=["profile_image_gcs_uri", "profile_image"])
            else:
                # Fallback: keep existing flow if field missing
                upload_serializer = PhotoUploadSerializer(user, data=request.data, partial=True)
                if upload_serializer.is_valid():
                    upload_serializer.save()

            read_serializer = PhotoSerializer(user)
            return Response(read_serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(
                "GCS upload failed for profile image: user_id=%s, error=%s",
                getattr(user, "id", None),
                str(e),
            )
            return Response({"detail": f"GCS upload failed: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request):
        user = request.user

        if not user.profile_image and not getattr(user, "profile_image_gcs_uri", None):
            return Response(
                {"detail": "No profile image to remove."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # If in GCS, delete blob; else local
        gcs_uri = getattr(user, "profile_image_gcs_uri", None)
        if gcs_uri and gcs_uri.startswith("gs://"):
            try:
                _, path_part = gcs_uri.split("gs://", 1)
                bucket_name, object_name = path_part.split("/", 1)
                storage_client = storage.Client()
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(object_name)
                blob.delete()
            except Exception as e:
                print(f"GCS delete error: {e}")
            user.profile_image_gcs_uri = None
            user.save(update_fields=["profile_image_gcs_uri"])
        else:
            image_path = user.profile_image.path
            user.profile_image = None
            user.save()
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception as e:
                    print(f"Error deleting image file: {e}")

        return Response(
            {"detail": "Profile image removed successfully."}, status=status.HTTP_200_OK
        )


class CertificateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        tag_id = request.data.get("tag_id")
        certificate = request.FILES.get("certificate")

        logger.info(
            "Certificate upload attempt: user_id=%s, tag_id=%s, size=%s, content_type=%s",
            getattr(user, "id", None),
            tag_id,
            getattr(certificate, "size", None),
            getattr(certificate, "content_type", None),
        )

        if not tag_id:
            return Response(
                {"detail": "Missing tag_id."}, status=status.HTTP_400_BAD_REQUEST
            )

        if not certificate:
            return Response(
                {"detail": "No certificate file uploaded."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ensure the user has this tag
        try:
            user_tag = UserTag.objects.get(user=user, tag__id=tag_id)
            tag = user_tag.tag
        except UserTag.DoesNotExist:
            return Response(
                {"detail": "Tag not found or not associated with user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        #  Validate file size (max 5 MB)
        max_size = 5 * 1024 * 1024  # 5 MB
        if certificate.size > max_size:
            return Response(
                {"detail": "File size exceeds 5 MB limit."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        #  Validate file type
        valid_mime_types = ["image/jpeg", "image/png", "application/pdf"]
        if certificate.content_type not in valid_mime_types:
            return Response(
                {"detail": "Only JPG, PNG, or PDF files are allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Upload certificate to GCS and store gs:// URI
        bucket_name = os.environ.get("GCS_MEDIA_BUCKET") or os.environ.get("CLOUD_STORAGE_BUCKET")
        if not bucket_name:
            logger.warning("GCS config missing for certificate upload: no bucket configured")
            return Response(
                {"detail": "GCS configuration missing. Set GCS_MEDIA_BUCKET or CLOUD_STORAGE_BUCKET."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        try:
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf"}
            ext = ext_map.get(certificate.content_type, ".bin")
            object_name = f"certificates/{str(user_tag.certificate_token)}{ext}"
            blob = bucket.blob(object_name)
            blob.cache_control = "private, max-age=0"
            blob.upload_from_file(certificate, content_type=certificate.content_type)
            user_tag.certificate_gcs_uri = f"gs://{bucket_name}/{object_name}"
            user_tag.certificate = None
            user_tag.save(update_fields=["certificate_gcs_uri", "certificate"])
            serializer = TagOutputSerializer(tag, context={"user": user})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(
                "GCS upload failed for certificate: user_id=%s, tag_id=%s, error=%s",
                getattr(user, "id", None),
                tag_id,
                str(e),
            )
            return Response({"detail": f"GCS upload failed: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request):
        """
        DELETE /users/certificate/
        Remove certificate from a profession tag.
        Expected body: { "tag_id": <tag_id> }
        """
        user = request.user
        tag_id = request.data.get("tag_id")

        if not tag_id:
            return Response(
                {"detail": "Missing tag_id."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Ensure the user has this tag
        try:
            user_tag = UserTag.objects.get(user=user, tag__id=tag_id)
            tag = user_tag.tag
        except UserTag.DoesNotExist:
            return Response(
                {"detail": "Tag not found or not associated with user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Remove certificate from GCS if present; else local
        if getattr(user_tag, "certificate_gcs_uri", None) and user_tag.certificate_gcs_uri.startswith("gs://"):
            try:
                _, path_part = user_tag.certificate_gcs_uri.split("gs://", 1)
                bucket_name, object_name = path_part.split("/", 1)
                storage_client = storage.Client()
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(object_name)
                blob.delete()
            except Exception as e:
                print(f"GCS delete error: {e}")
            user_tag.certificate_gcs_uri = None
            user_tag.save(update_fields=["certificate_gcs_uri"])
        elif user_tag.certificate:
            user_tag.certificate.delete(save=False)
            user_tag.certificate = None
            user_tag.save()

        # Return updated tag info with user context
        serializer = TagOutputSerializer(tag, context={"user": user})
        return Response(serializer.data, status=status.HTTP_200_OK)


class LikedPostsView(APIView):
    """
    GET /users/profile/liked-posts/
    Fetch posts that the current user has liked.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Get all likes by this user
        liked_post_ids = Like.objects.filter(user=user).values_list(
            "post_id", flat=True
        )

        # Get the posts that were liked
        liked_posts = Post.objects.filter(id__in=liked_post_ids).order_by("-created_at")

        # Paginate results
        paginator = PageNumberPagination()
        paginator.page_size = 10
        paginated_posts = paginator.paginate_queryset(liked_posts, request)

        # Serialize the posts
        serializer = PostSerializer(paginated_posts, many=True)

        return paginator.get_paginated_response(serializer.data)


class LikedRecipesView(APIView):
    """
    GET /users/profile/liked-recipes/
    Fetch recipes whose posts the current user has liked.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Get all post IDs that the user has liked
        liked_post_ids = Like.objects.filter(user=user).values_list(
            "post_id", flat=True
        )

        # Get recipes where the post is in the liked posts
        liked_recipes = Recipe.objects.filter(post_id__in=liked_post_ids).order_by(
            "-created_at"
        )

        # Paginate results
        paginator = PageNumberPagination()
        paginator.page_size = 10
        paginated_recipes = paginator.paginate_queryset(liked_recipes, request)

        # Serialize the recipes
        serializer = RecipeSerializer(paginated_recipes, many=True)

        return paginator.get_paginated_response(serializer.data)


class ReportUserView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReportSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            report = serializer.save()
            return Response(
                {"message": "Report submitted successfully.", "report_id": report.id},
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class IsCertificateOwnerOrAdmin(BasePermission):
    """
    Custom permission to only allow certificate owners or admin users to view certificates.
    """

    def has_permission(self, request, view):
        # Check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Get the token from the URL
        token = view.kwargs.get("token")
        if not token:
            return False

        try:
            # Find the UserTag by certificate token
            user_tag = UserTag.objects.get(certificate_token=token)

            # Allow if user is the owner or an admin
            return (
                request.user == user_tag.user
                or request.user.is_staff
                or request.user.is_superuser
            )
        except UserTag.DoesNotExist:
            return False


class ServeProfileImageView(APIView):
    """
    Serve profile images by token. Public access.
    GET /api/users/profile-image/<uuid:token>/
    """

    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            user = User.objects.get(profile_image_token=token)
        except User.DoesNotExist:
            raise Http404("Profile image not found")

        if not user.profile_image and not getattr(user, "profile_image_gcs_uri", None):
            raise Http404("User has no profile image")

        # If stored in GCS, generate a signed URL and redirect
        gcs_uri = getattr(user, "profile_image_gcs_uri", None)
        if gcs_uri and gcs_uri.startswith("gs://"):
            try:
                _, path_part = gcs_uri.split("gs://", 1)
                bucket_name, object_name = path_part.split("/", 1)

                # Use default credentials (Workload Identity) and IAM-based signing.
                credentials, _ = google_auth_default()
                storage_client = storage.Client(credentials=credentials)
                blob = storage_client.bucket(bucket_name).blob(object_name)

                expiration = int(os.environ.get("GS_EXPIRATION_SECONDS", "3600"))
                signed = blob.generate_signed_url(
                    version="v4",
                    expiration=expiration,
                    method="GET",
                    credentials=credentials,
                    service_account_email=getattr(
                        credentials, "service_account_email", None
                    ),
                )
                return HttpResponseRedirect(signed)
            except Exception as e:
                logger.error(f"GCS signed URL error: {e}")
                raise Http404("Profile image file not found")

        # Fallback to local path
        file_path = os.path.join(settings.MEDIA_ROOT, user.profile_image.name)
        if not os.path.exists(file_path):
            raise Http404("Profile image file not found")

        return FileResponse(open(file_path, "rb"))


class ServeCertificateView(APIView):
    """
    Serve certificates by token. Restricted to certificate owner or admin.
    GET /api/users/certificate/<uuid:token>/
    Supports both JWT (for API clients) and Session (for Django admin) authentication.
    """

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsCertificateOwnerOrAdmin]

    def get(self, request, token):
        try:
            user_tag = UserTag.objects.get(certificate_token=token)
        except UserTag.DoesNotExist:
            raise Http404("Certificate not found")

        if not user_tag.certificate and not getattr(user_tag, "certificate_gcs_uri", None):
            raise Http404("No certificate file attached")

        # If in GCS, generate signed URL and redirect
        gcs_uri = getattr(user_tag, "certificate_gcs_uri", None)
        if gcs_uri and gcs_uri.startswith("gs://"):
            try:
                _, path_part = gcs_uri.split("gs://", 1)
                bucket_name, object_name = path_part.split("/", 1)

                credentials, _ = google_auth_default()
                storage_client = storage.Client(credentials=credentials)
                blob = storage_client.bucket(bucket_name).blob(object_name)

                expiration = int(os.environ.get("GS_EXPIRATION_SECONDS", "3600"))
                signed = blob.generate_signed_url(
                    version="v4",
                    expiration=expiration,
                    method="GET",
                    credentials=credentials,
                    service_account_email=getattr(
                        credentials, "service_account_email", None
                    ),
                )
                return HttpResponseRedirect(signed)
            except Exception as e:
                logger.error(f"GCS signed URL error: {e}")
                raise Http404("Certificate file not found")

        # Fallback to local path
        file_path = os.path.join(settings.MEDIA_ROOT, user_tag.certificate.name)
        if not os.path.exists(file_path):
            raise Http404("Certificate file not found")

        return FileResponse(open(file_path, "rb"))

class FollowUserView(APIView):
    """
    POST /users/follow/
    Body: { "username": "<target_username>" }
    Toggle follow/unfollow operation.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        current_user = request.user
        target_username = request.data.get("username")

        if not target_username:
            return Response(
                {"detail": "username field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if target_username == current_user.username:
            return Response(
                {"detail": "You cannot follow yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check target user existence
        try:
            target_user = User.objects.get(username=target_username)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check existing follow relation
        existing = Follow.objects.filter(
            follower=current_user, following=target_user
        ).first()

        if existing:
            # UNFOLLOW
            existing.delete()
            return Response(
                {"message": f"You unfollowed {target_user.username}."},
                status=status.HTTP_200_OK,
            )
        else:
            # FOLLOW
            Follow.objects.create(follower=current_user, following=target_user)
            return Response(
                {"message": f"You are now following {target_user.username}."},
                status=status.HTTP_201_CREATED,
            )

class FollowersListView(APIView):
    """
    GET /users/followers/<username>/
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, username):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        followers = User.objects.filter(following_set__following=user)
        serializer = UserSerializer(followers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FollowingListView(APIView):
    """
    GET /users/following/<username>/
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, username):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        following = User.objects.filter(followers_set__follower=user)
        serializer = UserSerializer(following, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FeedView(APIView):
    """
    GET /forum/feed/
    Returns a feed of posts that includes:
    - Posts from users the current user follows
    - Posts the current user has liked
    """
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user

        # 1. Get IDs of users the current user follows
        following_ids = Follow.objects.filter(follower=user).values_list(
            "following_id", flat=True
        )

        # 2. Get posts the user has liked
        liked_post_ids = Like.objects.filter(user=user).values_list(
            "post_id", flat=True
        )

        # 3. Fetch feed posts: posts by followed users OR liked posts
        posts = (
            Post.objects.filter(
                Q(author_id__in=following_ids) | Q(id__in=liked_post_ids)
            )
            .distinct()
            .order_by("-created_at")
        )

        # 4. Pagination
        paginator = PageNumberPagination()
        paginator.page_size = 10
        paginated_posts = paginator.paginate_queryset(posts, request)

        serializer = PostSerializer(paginated_posts, many=True)
        return paginator.get_paginated_response(serializer.data)


class UserMetricsView(APIView):
    """
    GET /api/users/metrics/
    Get user's physical metrics.
    
    POST /api/users/metrics/
    Create or update user's physical metrics.
    Auto-calculates nutrition targets if not custom.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            metrics = request.user.metrics
            serializer = UserMetricsSerializer(metrics)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except:
            return Response(
                {"detail": "User metrics not found."},
                status=status.HTTP_404_NOT_FOUND
            )

    def post(self, request):
        from .models import UserMetrics, NutritionTargets
        
        try:
            # Update existing metrics
            metrics = request.user.metrics
            serializer = UserMetricsSerializer(metrics, data=request.data, partial=True)
        except:
            # Create new metrics
            serializer = UserMetricsSerializer(data=request.data)

        if serializer.is_valid():
            metrics = serializer.save(user=request.user)
            
            # Auto-recalculate targets if not custom
            try:
                targets = request.user.nutrition_targets
                if not targets.is_custom:
                    NutritionTargets.create_from_metrics(metrics)
            except:
                # No targets exist, create them
                NutritionTargets.create_from_metrics(metrics)
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class NutritionTargetsView(APIView):
    """
    GET /api/users/nutrition-targets/
    Get user's nutrition targets (auto-calculated if not set).
    
    PUT /api/users/nutrition-targets/
    Update custom nutrition targets.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import NutritionTargets
        
        try:
            targets = request.user.nutrition_targets
        except:
            # Try to auto-generate from metrics
            try:
                metrics = request.user.metrics
                targets = NutritionTargets.create_from_metrics(metrics)
            except:
                return Response(
                    {"detail": "No nutrition targets or metrics found. Please set your metrics first."},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        serializer = NutritionTargetsSerializer(targets)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        from .models import NutritionTargets
        
        try:
            targets = request.user.nutrition_targets
            serializer = NutritionTargetsSerializer(targets, data=request.data, partial=True)
        except:
            serializer = NutritionTargetsSerializer(data=request.data)

        if serializer.is_valid():
            targets = serializer.save(user=request.user, is_custom=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetNutritionTargetsView(APIView):
    """
    POST /api/users/nutrition-targets/reset/
    Reset nutrition targets to auto-calculated values from user metrics.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import NutritionTargets
        
        try:
            metrics = request.user.metrics
        except:
            return Response(
                {"detail": "User metrics not found. Please set your metrics first."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        targets = NutritionTargets.create_from_metrics(metrics)
        serializer = NutritionTargetsSerializer(targets)
        
        return Response(serializer.data, status=status.HTTP_200_OK)


# ==================== BADGES ====================

@api_view(["POST"])
@permission_classes([AllowAny])  # Cloud Function needs to call this without auth
def badges_callback(request):
    """
    POST /api/users/badges-callback/
    Called by the Cloud Function after calculating badges.
    Updates the user's badges in the database.
    
    Expected payload: {
        "user_id": <int>,
        "badges": [<badge objects>],
        "stats": {"recipe_count": int, "total_likes": int, "post_count": int}
    }
    """
    from .badge_utils import update_user_badges
    
    user_id = request.data.get("user_id")
    badges = request.data.get("badges", [])
    stats = request.data.get("stats", {})
    
    if not user_id:
        return Response(
            {"error": "user_id is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(id=user_id)
        update_user_badges(user, badges, stats)
        
        return Response({
            "message": "Badges updated successfully",
            "user_id": user_id,
            "badge_count": len(badges)
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response(
            {"error": f"User {user_id} not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error updating badges for user {user_id}: {e}")
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class UserBadgesView(APIView):
    """
    GET /api/users/badges/
    Get the authenticated user's badges.
    
    GET /api/users/badges/<user_id>/
    Get a specific user's badges.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, user_id=None):
        from .badge_utils import calculate_badges_sync, get_user_badge_stats, publish_badge_calculation_request
        
        # Determine which user to get badges for
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response(
                    {"error": "User not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            user = request.user
        
        # Get current stats
        stats = get_user_badge_stats(user)
        
        # If badges are not cached or outdated, calculate them
        if not user.badges or user.badges_updated_at is None:
            # Calculate synchronously for immediate response
            badges, _ = calculate_badges_sync(user)
            
            # Also trigger async calculation via Cloud Function (if configured)
            publish_badge_calculation_request(user, event_type="profile_view")
        else:
            badges = user.badges
        
        return Response({
            "user_id": user.id,
            "username": user.username,
            "badges": badges,
            "stats": stats,
            "badges_updated_at": user.badges_updated_at,
        }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def recalculate_badges(request):
    """
    POST /api/users/badges/recalculate/
    Force recalculation of the authenticated user's badges.
    Triggers the Cloud Function to recalculate.
    """
    from .badge_utils import calculate_badges_sync, update_user_badges, publish_badge_calculation_request
    
    user = request.user
    
    # Calculate badges synchronously for immediate response
    badges, stats = calculate_badges_sync(user)
    
    # Update in database
    update_user_badges(user, badges, stats)
    
    # Also trigger Cloud Function for future consistency
    published = publish_badge_calculation_request(user, event_type="manual_recalculate")
    
    return Response({
        "message": "Badges recalculated",
        "badges": badges,
        "stats": stats,
        "cloud_function_triggered": published,
    }, status=status.HTTP_200_OK)
