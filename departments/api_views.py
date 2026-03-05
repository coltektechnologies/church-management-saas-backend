from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Church
from members.models import Member

from .models import Department


@csrf_exempt
@require_GET
def get_members_by_church(request):
    """API endpoint to get members by church ID"""
    church_id = request.GET.get("church_id")
    if not church_id:
        return JsonResponse({"error": "church_id parameter is required"}, status=400)

    try:
        # Verify the church exists
        church = Church.objects.get(id=church_id)

        # Get active members for the church
        members = Member.objects.filter(church=church, is_active=True).values(
            "id", "first_name", "last_name"
        )

        # Format the response
        members_list = [
            {
                "id": str(member["id"]),
                "name": f"{member['first_name']} {member['last_name']}",
            }
            for member in members
        ]

        return JsonResponse(members_list, safe=False)
    except Church.DoesNotExist:
        return JsonResponse({"error": "Church not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


@csrf_exempt
@require_http_methods(["GET"])
def get_departments_by_church(request):
    """Simple API endpoint to get departments by church ID"""
    # Set CORS headers
    response = JsonResponse({})
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"

    if request.method == "OPTIONS":
        # Handle preflight requests
        return response

    church_id = request.GET.get("church_id")

    if not church_id:
        return JsonResponse({"error": "church_id parameter is required"}, status=400)

    try:
        # Verify the church exists
        church = Church.objects.get(id=church_id)

        # Get active departments for the church
        departments = Department.objects.filter(church=church, is_active=True).values(
            "id", "name"
        )

        # Convert to list for JSON serialization
        departments_list = list(departments)

        return JsonResponse(departments_list, safe=False)

    except Church.DoesNotExist:
        return JsonResponse({"error": "Church not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
