from django.urls import path

from .views import (  # Income Categories; Income Transactions; Expense Categories; Expense Transactions; Expense Requests; Assets; Statistics
    AssetDetailView, AssetView, ExpenseCategoryDetailView, ExpenseCategoryView,
    ExpenseRequestDetailView, ExpenseRequestView, ExpenseTransactionDetailView,
    ExpenseTransactionView, IncomeCategoryDetailView, IncomeCategoryView,
    IncomeTransactionDetailView, IncomeTransactionView,
    approve_expense_request_dept_head, approve_expense_request_first_elder,
    approve_expense_request_treasurer, disburse_expense_request,
    get_treasury_statistics, reject_expense_request, submit_expense_request)

app_name = "treasury"

urlpatterns = [
    # ==========================================
    # INCOME CATEGORY ENDPOINTS
    # ==========================================
    path(
        "income-categories/",
        IncomeCategoryView.as_view(),
        name="income-category-list-create",
    ),
    path(
        "income-categories/<uuid:pk>/",
        IncomeCategoryDetailView.as_view(),
        name="income-category-detail",
    ),
    # ==========================================
    # INCOME TRANSACTION ENDPOINTS
    # ==========================================
    path(
        "income-transactions/",
        IncomeTransactionView.as_view(),
        name="income-transaction-list-create",
    ),
    path(
        "income-transactions/<uuid:pk>/",
        IncomeTransactionDetailView.as_view(),
        name="income-transaction-detail",
    ),
    # ==========================================
    # EXPENSE CATEGORY ENDPOINTS
    # ==========================================
    path(
        "expense-categories/",
        ExpenseCategoryView.as_view(),
        name="expense-category-list-create",
    ),
    path(
        "expense-categories/<uuid:pk>/",
        ExpenseCategoryDetailView.as_view(),
        name="expense-category-detail",
    ),
    # ==========================================
    # EXPENSE TRANSACTION ENDPOINTS
    # ==========================================
    path(
        "expense-transactions/",
        ExpenseTransactionView.as_view(),
        name="expense-transaction-list-create",
    ),
    path(
        "expense-transactions/<uuid:pk>/",
        ExpenseTransactionDetailView.as_view(),
        name="expense-transaction-detail",
    ),
    # ==========================================
    # EXPENSE REQUEST ENDPOINTS
    # ==========================================
    path(
        "expense-requests/",
        ExpenseRequestView.as_view(),
        name="expense-request-list-create",
    ),
    path(
        "expense-requests/<uuid:pk>/",
        ExpenseRequestDetailView.as_view(),
        name="expense-request-detail",
    ),
    # Expense Request Actions
    path(
        "expense-requests/<uuid:pk>/submit/",
        submit_expense_request,
        name="expense-request-submit",
    ),
    # Department Head Approval
    path(
        "expense-requests/<uuid:pk>/approve-dept-head/",
        approve_expense_request_dept_head,
        name="expense-request-approve-dept-head",
    ),
    # First Elder Approval
    path(
        "expense-requests/<uuid:pk>/approve-first-elder/",
        approve_expense_request_first_elder,
        name="expense-request-approve-first-elder",
    ),
    path(
        "expense-requests/<uuid:pk>/approve-treasurer/",
        approve_expense_request_treasurer,
        name="expense-request-approve-treasurer",
    ),
    path(
        "expense-requests/<uuid:pk>/reject/",
        reject_expense_request,
        name="expense-request-reject",
    ),
    path(
        "expense-requests/<uuid:pk>/disburse/",
        disburse_expense_request,
        name="expense-request-disburse",
    ),
    # ==========================================
    # ASSET ENDPOINTS
    # ==========================================
    path("assets/", AssetView.as_view(), name="asset-list-create"),
    path("assets/<uuid:pk>/", AssetDetailView.as_view(), name="asset-detail"),
    # ==========================================
    # STATISTICS & REPORTS
    # ==========================================
    path("statistics/", get_treasury_statistics, name="treasury-statistics"),
]
