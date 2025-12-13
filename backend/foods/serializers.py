from foods.models import FoodEntry, FoodProposal
from rest_framework.serializers import ModelSerializer, SerializerMethodField
from urllib.parse import quote


# Serializer for FoodEntry model
class FoodEntrySerializer(ModelSerializer):
    imageUrl = SerializerMethodField()

    class Meta:
        model = FoodEntry
        fields = "__all__"

    def get_imageUrl(self, obj):
        """
        Transform external image URLs to use the caching proxy.
        Local URLs are returned as-is.
        Returns relative URLs that work in all environments (dev proxy, production).
        """
        if not obj.imageUrl:
            return ""

        # Skip proxy for local media URLs
        if obj.imageUrl.startswith("/media/"):
            return obj.imageUrl

        # Skip proxy for localhost/127.0.0.1
        if "localhost" in obj.imageUrl or "127.0.0.1" in obj.imageUrl:
            return obj.imageUrl

        # Use proxy for external URLs - return relative URL for compatibility
        encoded_url = quote(obj.imageUrl, safe="")
        return f"/api/foods/image-proxy/?url={encoded_url}"


class FoodProposalSerializer(ModelSerializer):
    class Meta:
        model = FoodProposal
        fields = "__all__"
        read_only_fields = ("proposedBy", "nutritionScore")
