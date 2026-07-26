"""Роутер промпт-шаблонов.

Importers: main.py (include_router).
Affected API: GET /api/prompts, GET/PATCH /api/prompts/{key}, POST /api/prompts/{key}/reset.
Data schemas: PromptOut, PromptCategoryOut, PromptsResponse, PromptUpdate (schemas/prompt.py).
User instruction: "всё понятно разложено по полочкам в одном месте, я это могу прочитать, отредактировать"
"""

from fastapi import APIRouter, HTTPException

from app.api.deps import AuthDep, DbSession
from app.api.schemas.prompt import (
    PromptCategoryOut,
    PromptOut,
    PromptsResponse,
    PromptUpdate,
)
from app.domain.prompt_defaults import PROMPT_DEFAULTS
from app.domain.prompt_errors import PromptNotFoundError
from app.services.prompt_service import PromptService

router = APIRouter(prefix="/prompts", tags=["prompts"])


def _to_out(prompt, *, check_default: bool = True) -> PromptOut:
    is_default = False
    if check_default:
        default = PROMPT_DEFAULTS.get(prompt.key)
        if default is not None:
            is_default = prompt.template_text.strip() == default.template_text.strip()
    return PromptOut.model_validate(prompt, update={"is_default": is_default})


@router.get("", response_model=PromptsResponse)
async def get_prompts(session: DbSession, _: AuthDep) -> PromptsResponse:
    svc = PromptService(session)
    groups = await svc.get_all_grouped()
    categories = []
    for group in groups:
        prompts = [_to_out(p) for p in group["prompts"]]
        categories.append(
            PromptCategoryOut(
                category=group["category"],
                label=group["label"],
                prompts=prompts,
            )
        )
    return PromptsResponse(categories=categories)


@router.get("/{key:path}", response_model=PromptOut)
async def get_prompt(key: str, session: DbSession, _: AuthDep) -> PromptOut:
    svc = PromptService(session)
    try:
        prompt = await svc.get_template(key)
    except PromptNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_out(prompt)


@router.patch("/{key:path}", response_model=PromptOut)
async def update_prompt(
    key: str, data: PromptUpdate, session: DbSession, _: AuthDep
) -> PromptOut:
    svc = PromptService(session)
    try:
        prompt = await svc.update(
            key,
            data.template_text,
            name=data.name,
            description=data.description,
        )
    except PromptNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_out(prompt)


@router.post("/{key:path}/reset", response_model=PromptOut)
async def reset_prompt(key: str, session: DbSession, _: AuthDep) -> PromptOut:
    svc = PromptService(session)
    try:
        prompt = await svc.reset(key)
    except PromptNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_out(prompt)
