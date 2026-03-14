from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()

# Маппинг поле → (label, блок)
FIELD_LABELS: dict[str, tuple[str, int]] = {
    "q1_1": ("Приветствие клиента, уточнение имени", 1),
    "q1_2": ("Представить себя и позицию", 1),
    "q1_3": ("Причина звонка, уточнение заказа, удобно ли говорить", 1),
    "q2_1": ("Уточнение региона/города после приветствия", 2),
    "q2_2": ("Уточнение города до выявления потребностей", 2),
    "q2_3": ("Не запрашивать полный адрес на этом этапе", 2),
    "q3_1": ("Задать клиенту 5-10 вопросов", 3),
    "q3_2": ("Узнать потребности для точного предложения", 3),
    "q4_1": ("Презентация с акцентом на преимущества", 4),
    "q4_2": ("Поэтапное действие продукта", 4),
    "q4_3": ("Продукт решает потребности клиента", 4),
    "q4_4": ("Без озвучивания цены на презентации", 4),
    "q5_1": ("Вилка: объяснить необходимость курсов", 5),
    "q5_2": ("Вилка: корректная цена и количество упаковок", 5),
    "q5_3": ("Вилка: вопрос с призывом оформить заказ", 5),
    "q6_1": ("Скидка: объяснить почему можем сделать скидку", 6),
    "q6_2": ("Скидка: корректная цена и количество упаковок", 6),
    "q6_3": ("Скидка: вопрос с призывом оформить заказ", 6),
    "q7_1": ("Базовый: объяснить необходимость курса", 7),
    "q7_2": ("Базовый: корректная цена и количество упаковок", 7),
    "q7_3": ("Базовый: вопрос с призывом оформить заказ", 7),
    "q8_1": ("Возражение: принятие позиции клиента", 8),
    "q8_2": ("Возражение: аргументация через потребность", 8),
    "q8_3": ("Возражение: вопрос с призывом оформить", 8),
    "q9_1": ("CRM: ФИО и корректный адрес", 9),
    "q9_2": ("CRM: верное количество упаковок и цена", 9),
    "q10_1": ("Доставка: актуальные сроки", 10),
    "q10_2": ("Доставка: самый быстрый способ", 10),
    "q11_1": ("УД: информирование по регламенту", 11),
    "q11_2": ("УД: обязательства компании и клиента", 11),
    "q11_3": ("УД: вопрос «вы согласны?»", 11),
    "q12_1": ("Озвучил бонус/подарок", 12),
    "q13_1": ("Вежливое прощание", 13),
    "q14_1": ("Попытка перезвонить", 14),
}

Q_FIELDS = list(FIELD_LABELS.keys())


# --------------------------------------------------------------------------- #
# GET /analytics/operators — рейтинг операторов
# --------------------------------------------------------------------------- #
@router.get("/operators")
async def operator_stats(
    db: AsyncSession = Depends(get_db),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    team: Optional[str] = Query(None),
):
    conditions = ["ca.processing_status = 'done'", "ca.call_type = 'standard'"]
    params: dict = {}

    if date_from:
        conditions.append("ca.call_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("ca.call_date <= :date_to")
        params["date_to"] = date_to
    if team:
        conditions.append("ca.team = :team")
        params["team"] = team

    where = " AND ".join(conditions)

    sql = text(f"""
        SELECT
            ca.operator_id,
            o.external_id  AS operator_external_id,
            o.name         AS operator_name,
            ca.team,
            COUNT(*)                                   AS calls_total,
            COUNT(*) FILTER (WHERE ca.call_type = 'standard') AS calls_standard,
            ROUND(AVG(ca.total_score)::numeric, 2)     AS avg_score,
            29                                         AS max_score,
            ROUND(AVG(ca.total_score)::numeric / 29 * 100, 1) AS avg_score_pct,
            SUM(ca.triggers_count)                     AS triggers_fired
        FROM call_analytics ca
        JOIN operators o ON o.id = ca.operator_id
        WHERE {where}
        GROUP BY ca.operator_id, o.external_id, o.name, ca.team
        ORDER BY avg_score DESC NULLS LAST
    """)

    result = await db.execute(sql, params)
    rows = result.mappings().all()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# GET /analytics/weak-spots — слабые места по критериям
# --------------------------------------------------------------------------- #
@router.get("/weak-spots")
async def weak_spots(
    db: AsyncSession = Depends(get_db),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    operator_external_id: Optional[str] = Query(None),
):
    conditions = ["ca.processing_status = 'done'", "ca.call_type = 'standard'"]
    params: dict = {}

    if date_from:
        conditions.append("ca.call_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("ca.call_date <= :date_to")
        params["date_to"] = date_to
    if operator_external_id:
        conditions.append("o.external_id = :ext_id")
        params["ext_id"] = operator_external_id

    where = " AND ".join(conditions)
    join = "JOIN operators o ON o.id = ca.operator_id" if operator_external_id else ""

    avg_fields = ", ".join(
        f"ROUND(AVG({f}::int)::numeric, 4) AS {f}" for f in Q_FIELDS
    )

    sql = text(f"""
        SELECT {avg_fields}
        FROM call_analytics ca
        {join}
        WHERE {where}
    """)

    result = await db.execute(sql, params)
    row = result.mappings().one_or_none()
    if not row:
        return []

    spots = []
    for field in Q_FIELDS:
        val = row[field]
        label, block = FIELD_LABELS[field]
        spots.append({
            "field": field,
            "label": label,
            "block": block,
            "pass_rate": float(val) if val is not None else None,
        })

    # Самые слабые — первые, None в конец
    spots.sort(key=lambda x: (x["pass_rate"] is None, x["pass_rate"] or 0))
    return spots
