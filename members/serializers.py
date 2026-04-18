from django.db import transaction
from rest_framework import serializers

from members.models import Member, MemberLocation, Visitor


class MemberListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = [
            "id",
            "full_name",
            "gender",
            "membership_status",
            "member_since",
            "phone_primary",
            "email",
            "system_user_id",
        ]
        read_only_fields = fields

    full_name = serializers.SerializerMethodField()
    phone_primary = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        return obj.full_name

    def get_phone_primary(self, obj):
        if hasattr(obj, "location") and obj.location:
            return obj.location.phone_primary
        return None

    def get_email(self, obj):
        if hasattr(obj, "location") and obj.location:
            return obj.location.email
        return None


class MemberLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberLocation
        fields = "__all__"
        read_only_fields = [
            "id",
            "member",
            "church",
            "created_at",
            "updated_at",
            "deleted_at",
        ]


class MemberSerializer(serializers.ModelSerializer):
    location = MemberLocationSerializer(required=False)

    class Meta:
        model = Member
        fields = "__all__"
        read_only_fields = [
            "id",
            "church",
            "created_at",
            "updated_at",
            "deleted_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["department_names"] = self._department_names_list(instance)
        return data

    @staticmethod
    def _department_names_list(instance: Member) -> list[str]:
        """Active MemberDepartment rows → department names (sorted). Uses prefetch when present."""
        names: list[str] = []
        for md in instance.memberdepartment_set.all():
            if md.deleted_at is not None:
                continue
            dept = md.department
            if dept is not None and dept.name:
                names.append(dept.name)
        return sorted(set(names))

    def create(self, validated_data):
        request = self.context.get("request")
        location_data = validated_data.pop("location", None)

        if not request or not request.user or not request.user.church:
            raise serializers.ValidationError(
                "User must belong to a church to create a member"
            )

        # Create member
        member = Member.objects.create(church=request.user.church, **validated_data)

        # Create location
        if location_data:
            MemberLocation.objects.create(
                member=member, church=request.user.church, **location_data
            )

        return member

    def update(self, instance, validated_data):
        location_data = validated_data.pop("location", None)

        # Update member fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update or create location
        if location_data:
            location, _ = MemberLocation.objects.get_or_create(
                member=instance,
                defaults={"church": instance.church},
            )

            for attr, value in location_data.items():
                setattr(location, attr, value)
            location.save()

        return instance


class VisitorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Visitor
        fields = "__all__"
        read_only_fields = [
            "id",
            "church",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        request = self.context.get("request")

        if not request or not request.user or not request.user.church:
            raise serializers.ValidationError("User must belong to a church")

        validated_data["church"] = request.user.church
        return super().create(validated_data)


class VisitorToMemberSerializer(serializers.Serializer):
    visitor_id = serializers.UUIDField()
    member_since = serializers.DateField()

    # Optional member fields
    occupation = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_visitor_id(self, value):
        try:
            visitor = Visitor.objects.get(id=value)
        except Visitor.DoesNotExist:
            raise serializers.ValidationError("Visitor not found")

        if visitor.converted_to_member:
            raise serializers.ValidationError("Visitor already converted")

        return value

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        visitor_id = validated_data["visitor_id"]

        if not request or not request.user or not request.user.church:
            raise serializers.ValidationError("User must belong to a church")

        visitor = Visitor.objects.get(id=visitor_id)

        # Create member
        member = Member.objects.create(
            church=request.user.church,
            first_name=visitor.full_name.split(" ")[0],
            last_name=" ".join(visitor.full_name.split(" ")[1:]) or visitor.full_name,
            gender=visitor.gender or "MALE",
            member_since=validated_data["member_since"],
            membership_status="NEW_CONVERT",
            occupation=validated_data.get("occupation"),
            notes=validated_data.get("notes"),
        )

        # Create member location
        MemberLocation.objects.create(
            member=member,
            church=request.user.church,
            phone_primary=visitor.phone,
            email=visitor.email,
            city=visitor.city,
            address=visitor.city or "Unknown",
        )

        # Mark visitor as converted
        visitor.converted_to_member = True
        visitor.save()

        return member
