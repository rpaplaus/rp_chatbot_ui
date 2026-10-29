from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, desc

from app.api.deps import get_db, get_current_active_user, get_current_admin_user
from app.models.user import User
from app.models.token_usage import TokenUsage
from app.schemas.metrics import (
    ModelUsageBreakdown,
    UserUsageSummaryResponse,
    AdminUserRankingItem,
    AdminUsageSummaryResponse
)

router = APIRouter(prefix="/metrics", tags=["Metrics & Telemetry"])


def _get_current_month_start_utc() -> datetime:
    """Returns the UTC datetime for the 1st day of the current month at 00:00:00."""
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)


@router.get(
    "/usage",
    response_model=UserUsageSummaryResponse,
    summary="Get token consumption and USD cost telemetry for the authenticated user"
)
async def get_user_usage_metrics(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns total and current-month token consumption and financial cost (USD)
    broken down by AI model and provider for the currently authenticated user.
    """
    month_start = _get_current_month_start_utc()

    # 1. Global & Current Month Totals for current_user
    totals_stmt = select(
        func.count(TokenUsage.id).label("total_requests"),
        func.coalesce(func.sum(TokenUsage.prompt_tokens), 0).label("total_prompt_tokens"),
        func.coalesce(func.sum(TokenUsage.completion_tokens), 0).label("total_completion_tokens"),
        func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(TokenUsage.total_cost), 0).label("total_cost_usd"),
        func.coalesce(
            func.sum(
                case(
                    (TokenUsage.created_at >= month_start, TokenUsage.total_cost),
                    else_=0
                )
            ),
            0
        ).label("current_month_cost_usd"),
        func.coalesce(
            func.sum(
                case(
                    (TokenUsage.created_at >= month_start, TokenUsage.total_tokens),
                    else_=0
                )
            ),
            0
        ).label("current_month_tokens"),
    ).where(TokenUsage.user_id == current_user.id)

    totals_res = await db.execute(totals_stmt)
    totals_row = totals_res.one()

    total_cost_float = float(totals_row.total_cost_usd or 0.0)

    # 2. Breakdown by Provider & Model
    model_stmt = (
        select(
            TokenUsage.provider,
            TokenUsage.model_name,
            func.count(TokenUsage.id).label("request_count"),
            func.coalesce(func.sum(TokenUsage.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(TokenUsage.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(TokenUsage.total_cost), 0).label("total_cost_usd"),
        )
        .where(TokenUsage.user_id == current_user.id)
        .group_by(TokenUsage.provider, TokenUsage.model_name)
        .order_by(desc(func.sum(TokenUsage.total_cost)), desc(func.sum(TokenUsage.total_tokens)))
    )

    model_res = await db.execute(model_stmt)
    by_model: List[ModelUsageBreakdown] = []

    for row in model_res.all():
        m_cost = float(row.total_cost_usd or 0.0)
        pct = (m_cost / total_cost_float * 100.0) if total_cost_float > 0 else 0.0
        by_model.append(
            ModelUsageBreakdown(
                provider=row.provider,
                model_name=row.model_name,
                request_count=int(row.request_count or 0),
                prompt_tokens=int(row.prompt_tokens or 0),
                completion_tokens=int(row.completion_tokens or 0),
                total_tokens=int(row.total_tokens or 0),
                total_cost_usd=round(m_cost, 8),
                percentage_of_cost=round(pct, 2)
            )
        )

    return UserUsageSummaryResponse(
        user_id=current_user.id,
        username=current_user.username,
        total_requests=int(totals_row.total_requests or 0),
        total_prompt_tokens=int(totals_row.total_prompt_tokens or 0),
        total_completion_tokens=int(totals_row.total_completion_tokens or 0),
        total_tokens=int(totals_row.total_tokens or 0),
        total_cost_usd=round(total_cost_float, 8),
        current_month_cost_usd=round(float(totals_row.current_month_cost_usd or 0.0), 8),
        current_month_tokens=int(totals_row.current_month_tokens or 0),
        by_model=by_model
    )


@router.get(
    "/admin/usage",
    response_model=AdminUsageSummaryResponse,
    summary="Get global platform FinOps telemetry and user cost ranking (Admin only)"
)
async def get_admin_usage_metrics(
    _admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Protected administrator endpoint (role='admin') returning:
    1. Global platform USD cost and token totals (all-time & current month).
    2. Global breakdown by AI provider/model.
    3. Ranking of users ordered by highest financial consumption.
    """
    month_start = _get_current_month_start_utc()

    # 1. Global Platform Totals
    global_stmt = select(
        func.count(TokenUsage.id).label("total_requests"),
        func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(TokenUsage.total_cost), 0).label("total_cost_usd"),
        func.coalesce(
            func.sum(
                case(
                    (TokenUsage.created_at >= month_start, TokenUsage.total_cost),
                    else_=0
                )
            ),
            0
        ).label("current_month_cost_usd"),
    )
    global_res = await db.execute(global_stmt)
    global_row = global_res.one()

    total_platform_cost = float(global_row.total_cost_usd or 0.0)

    # 2. Active Users Count
    active_users_res = await db.execute(
        select(func.count(User.id)).where(User.is_active.is_(True))
    )
    active_users_count = int(active_users_res.scalar() or 0)

    # 3. Global Breakdown by Model
    model_stmt = (
        select(
            TokenUsage.provider,
            TokenUsage.model_name,
            func.count(TokenUsage.id).label("request_count"),
            func.coalesce(func.sum(TokenUsage.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(TokenUsage.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(TokenUsage.total_cost), 0).label("total_cost_usd"),
        )
        .group_by(TokenUsage.provider, TokenUsage.model_name)
        .order_by(desc(func.sum(TokenUsage.total_cost)), desc(func.sum(TokenUsage.total_tokens)))
    )
    model_res = await db.execute(model_stmt)
    by_model: List[ModelUsageBreakdown] = []

    for row in model_res.all():
        m_cost = float(row.total_cost_usd or 0.0)
        pct = (m_cost / total_platform_cost * 100.0) if total_platform_cost > 0 else 0.0
        by_model.append(
            ModelUsageBreakdown(
                provider=row.provider,
                model_name=row.model_name,
                request_count=int(row.request_count or 0),
                prompt_tokens=int(row.prompt_tokens or 0),
                completion_tokens=int(row.completion_tokens or 0),
                total_tokens=int(row.total_tokens or 0),
                total_cost_usd=round(m_cost, 8),
                percentage_of_cost=round(pct, 2)
            )
        )

    # 4. User Consumption Ranking (LEFT OUTER JOIN so all registered users appear ranked)
    ranking_stmt = (
        select(
            User.id.label("user_id"),
            User.username,
            User.email,
            User.role,
            User.is_active,
            func.count(TokenUsage.id).label("request_count"),
            func.coalesce(func.sum(TokenUsage.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(TokenUsage.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(TokenUsage.total_cost), 0).label("total_cost_usd"),
            func.coalesce(
                func.sum(
                    case(
                        (TokenUsage.created_at >= month_start, TokenUsage.total_cost),
                        else_=0
                    )
                ),
                0
            ).label("current_month_cost_usd"),
        )
        .outerjoin(TokenUsage, TokenUsage.user_id == User.id)
        .group_by(User.id, User.username, User.email, User.role, User.is_active)
        .order_by(
            desc(func.coalesce(func.sum(TokenUsage.total_cost), 0)),
            desc(func.coalesce(func.sum(TokenUsage.total_tokens), 0)),
            User.username.asc()
        )
    )

    ranking_res = await db.execute(ranking_stmt)
    user_ranking: List[AdminUserRankingItem] = []

    for r in ranking_res.all():
        user_ranking.append(
            AdminUserRankingItem(
                user_id=r.user_id,
                username=r.username,
                email=r.email,
                role=r.role,
                is_active=bool(r.is_active),
                request_count=int(r.request_count or 0),
                prompt_tokens=int(r.prompt_tokens or 0),
                completion_tokens=int(r.completion_tokens or 0),
                total_tokens=int(r.total_tokens or 0),
                total_cost_usd=round(float(r.total_cost_usd or 0.0), 8),
                current_month_cost_usd=round(float(r.current_month_cost_usd or 0.0), 8),
            )
        )

    return AdminUsageSummaryResponse(
        total_platform_cost_usd=round(total_platform_cost, 8),
        current_month_platform_cost_usd=round(float(global_row.current_month_cost_usd or 0.0), 8),
        total_platform_tokens=int(global_row.total_tokens or 0),
        total_platform_requests=int(global_row.total_requests or 0),
        active_users_count=active_users_count,
        by_model=by_model,
        user_ranking=user_ranking
    )

