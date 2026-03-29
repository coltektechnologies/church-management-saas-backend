from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter

from .api_views import DepartmentsByChurchListView

# Import views directly from their modules to avoid circular imports
from .views.activity_views import DepartmentActivityViewSet
from .views.department_views import DepartmentViewSet, MemberDepartmentViewSet
from .views.program_step_views import DepartmentListForProgramAPIView
from .views.program_views import ProgramBudgetItemViewSet, ProgramViewSet

app_name = "departments"

# Main router for top-level endpoints
router = DefaultRouter()
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(
    r"member-departments", MemberDepartmentViewSet, basename="member-department"
)

# Nested router for programs and activities under departments
program_router = NestedDefaultRouter(router, r"departments", lookup="department")
program_router.register(r"programs", ProgramViewSet, basename="department-programs")
program_router.register(
    r"activities", DepartmentActivityViewSet, basename="department-activities"
)

# Nested router for budget items under programs
budget_item_router = NestedDefaultRouter(program_router, r"programs", lookup="program")
budget_item_router.register(
    r"budget-items", ProgramBudgetItemViewSet, basename="program-budget-items"
)

urlpatterns = [
    # ==========================================
    # Custom paths MUST come BEFORE router URLs (prefix matching)
    # ==========================================
    path(
        "departments/by-church/",
        DepartmentsByChurchListView.as_view(),
        name="api-departments-by-church",
    ),
    path(
        "departments/for-program/",
        DepartmentListForProgramAPIView.as_view(),
        name="departments-for-program",
    ),
    # Include nested routers BEFORE main router so departments/{id}/programs/ matches
    # ProgramViewSet (GET+POST) instead of DepartmentViewSet.programs (GET only)
    path("", include(program_router.urls)),
    path("", include(budget_item_router.urls)),
    path("", include(router.urls)),
    # 5-step program flow
    path(
        "programs/step1/",
        ProgramViewSet.as_view({"post": "step1_create"}),
        name="program-step1",
    ),
    # Direct program URLs (not nested under departments)
    path(
        "programs/",
        ProgramViewSet.as_view({"get": "list", "post": "create"}),
        name="program-list",
    ),
    path(
        "programs/<uuid:pk>/",
        ProgramViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="program-detail",
    ),
    path(
        "programs/<uuid:pk>/step2/",
        ProgramViewSet.as_view(
            {"put": "step2_budget_items", "patch": "step2_budget_items"}
        ),
        name="program-step2",
    ),
    path(
        "programs/<uuid:pk>/step3/",
        ProgramViewSet.as_view(
            {"put": "step3_justification", "patch": "step3_justification"}
        ),
        name="program-step3",
    ),
    path(
        "programs/<uuid:pk>/step4/documents/",
        ProgramViewSet.as_view({"post": "step4_upload_document"}),
        name="program-step4",
    ),
    path(
        "programs/<uuid:pk>/step5/review/",
        ProgramViewSet.as_view({"get": "step5_review"}),
        name="program-step5-review",
    ),
    path(
        "programs/<uuid:pk>/step5/submit/",
        ProgramViewSet.as_view({"post": "step5_submit"}),
        name="program-step5-submit",
    ),
    path(
        "programs/<uuid:pk>/submit/",
        ProgramViewSet.as_view({"post": "submit_program"}),
        name="program-submit",
    ),
    path(
        "programs/<uuid:pk>/review/",
        ProgramViewSet.as_view({"post": "review_program"}),
        name="program-review",
    ),
]


# URL Patterns Documentation:
#
# Department Activities (events): title, date, time, location, description; upcoming/past by time
# GET    /api/departments/{id}/activities/?time_filter=upcoming|past - List activities
# POST   /api/departments/{id}/activities/ - Create (optional: notify_to, member_ids, send_email, send_sms)
# GET    /api/departments/{id}/activities/{activity_id}/ - Retrieve
# PUT    /api/departments/{id}/activities/{activity_id}/ - Update
# PATCH  /api/departments/{id}/activities/{activity_id}/ - Partial update
# DELETE /api/departments/{id}/activities/{activity_id}/ - Soft delete
#
# By-church helpers (JWT + church scope): see MembersByChurchListView, DepartmentsByChurchListView
#
# Department Endpoints:
# GET    /api/departments/                          - List all departments
# POST   /api/departments/                          - Create a new department
# GET    /api/departments/{id}/                     - Get department details
# PUT    /api/departments/{id}/                     - Update department
# PATCH  /api/departments/{id}/                     - Partial update
# DELETE /api/departments/{id}/                     - Delete department
#
# Department Custom Actions:
# GET    /api/departments/{id}/members/             - Get department members
# POST   /api/departments/{id}/assign_member/       - Assign member to department
# DELETE /api/departments/{id}/members/{member_id}/  - Remove member from department
# PUT    /api/departments/{id}/head/                - Assign department head (primary)
# PUT    /api/departments/{id}/assistant-head/      - Assign assistant head (member_id null to clear)
# GET    /api/departments/statistics/               - Get statistics
#
# Program Endpoints (nested under departments):
# GET    /api/departments/{department_id}/programs/  - List programs for a department
# POST   /api/departments/{department_id}/programs/  - Create a program for a department
#
# Program Endpoints (direct access):
# GET    /api/programs/                             - List all programs
# POST   /api/programs/                             - Create a new program
# GET    /api/programs/{id}/                        - Get program details
# PUT    /api/programs/{id}/                        - Update program
# PATCH  /api/programs/{id}/                        - Partial update
# DELETE /api/programs/{id}/                        - Delete program
# POST   /api/programs/{id}/submit/                 - Submit program for approval
# POST   /api/programs/{id}/review/                 - Approve/Reject program (admin)
#
# Program Budget Item Endpoints (nested under programs):
# GET    /api/departments/{department_id}/programs/{program_id}/budget-items/     - List budget items
# POST   /api/departments/{department_id}/programs/{program_id}/budget-items/     - Create budget item
# GET    /api/departments/{department_id}/programs/{program_id}/budget-items/{id}/ - Get budget item
# PUT    /api/departments/{department_id}/programs/{program_id}/budget-items/{id}/ - Update budget item
# DELETE /api/departments/{department_id}/programs/{program_id}/budget-items/{id}/ - Delete budget item
