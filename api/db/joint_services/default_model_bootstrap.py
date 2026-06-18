#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import enum
import importlib
import json
import logging
from typing import Any

import requests

from common.constants import ActiveStatusEnum, LLMType


DEFAULT_PROVIDER_NAME = "OpenAI-API-Compatible"
DEFAULT_INSTANCE_NAME = "Matrix"
DEFAULT_MAX_TOKENS = 8192
MODEL_LIST_TIMEOUT_SECONDS = 15
DEFAULT_MODEL_FIELDS = {
    LLMType.CHAT.value: "llm_id",
    LLMType.EMBEDDING.value: "embd_id",
    LLMType.SPEECH2TEXT.value: "asr_id",
    "asr": "asr_id",
    LLMType.IMAGE2TEXT.value: "img2txt_id",
    "vision": "img2txt_id",
    LLMType.RERANK.value: "rerank_id",
    LLMType.TTS.value: "tts_id",
}
DEFAULT_MODEL_SETTING_FIELDS = {
    "llm_id": "CHAT_MDL",
    "embd_id": "EMBEDDING_MDL",
    "asr_id": "ASR_MDL",
    "img2txt_id": "IMAGE2TEXT_MDL",
    "rerank_id": "RERANK_MDL",
}

_SYNCED_TENANT_KEYS: set[tuple[str, str]] = set()

config_utils = None
TenantModelInstanceService = None
TenantModelProviderService = None
TenantModelService = None
TenantService = None


def _load_global(name: str, module_path: str, attr_name: str):
    current = globals()[name]
    if current is not None:
        return current

    module = importlib.import_module(module_path)
    loaded = getattr(module, attr_name)
    globals()[name] = loaded
    return loaded


def _get_config_utils():
    if config_utils is not None and hasattr(config_utils, "get_base_config"):
        return config_utils
    module = importlib.import_module("common.config_utils")
    globals()["config_utils"] = module
    return module


def _tenant_model_instance_service():
    return _load_global(
        "TenantModelInstanceService",
        "api.db.services.tenant_model_instance_service",
        "TenantModelInstanceService",
    )


def _tenant_model_provider_service():
    return _load_global(
        "TenantModelProviderService",
        "api.db.services.tenant_model_provider_service",
        "TenantModelProviderService",
    )


def _tenant_model_service():
    return _load_global(
        "TenantModelService",
        "api.db.services.tenant_model_service",
        "TenantModelService",
    )


def _tenant_service():
    return _load_global(
        "TenantService",
        "api.db.services.user_service",
        "TenantService",
    )


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _encode_api_key(api_key: str | dict | None) -> str:
    if isinstance(api_key, dict):
        return json.dumps(api_key, ensure_ascii=False)
    return api_key or ""


def _build_extra(base_url: str | None, region: str | None = None) -> str:
    extra: dict[str, str] = {}
    if base_url:
        extra["base_url"] = base_url
    if region:
        extra["region"] = region
    return json.dumps(extra, ensure_ascii=False)


def _get_endpoint_config() -> dict[str, Any] | None:
    llm_settings = _get_config_utils().get_base_config("user_default_llm", {}) or {}
    if not isinstance(llm_settings, dict):
        return None

    base_url = str(llm_settings.get("base_url") or "").strip()
    if not base_url:
        return None

    return {
        "instance_name": str(
            llm_settings.get("name")
            or llm_settings.get("instance_name")
            or DEFAULT_INSTANCE_NAME
        ).strip() or DEFAULT_INSTANCE_NAME,
        "provider_name": (
            str(llm_settings.get("factory") or DEFAULT_PROVIDER_NAME).strip()
            or DEFAULT_PROVIDER_NAME
        ),
        "api_key": llm_settings.get("api_key", ""),
        "base_url": base_url,
        "region": llm_settings.get("region"),
        "max_tokens": llm_settings.get("max_tokens", DEFAULT_MAX_TOKENS),
    }


def _get_model_list_url(base_url: str) -> str:
    base_url = base_url.strip().rstrip("/")
    if "/v1" in base_url:
        return base_url.split("/v1")[0].rstrip("/") + "/v1/models"
    return base_url + "/v1/models"


_EMBEDDING_HINTS = ("embed", "embedding", "bge")
_RERANK_HINTS = ("rerank", "reranker")
_SPEECH2TEXT_HINTS = ("asr", "stt", "transcribe", "transcriber", "whisper")
_TTS_HINTS = ("tts", "text-to-speech")
_VISION_HINTS = (
    "vl",
    "vision",
    "llava",
    "internvl",
    "minicpm-v",
    "gpt-4o",
    "glm-4v",
    "qvq",
    "qwen-vl",
    "pixtral",
)


def _contains_hint(model_name: str, hints: tuple[str, ...]) -> bool:
    return any(hint in model_name for hint in hints)


def _infer_model_types(model_name: str) -> list[str]:
    model_name = model_name.lower()
    if _contains_hint(model_name, _RERANK_HINTS):
        return [LLMType.RERANK.value]
    if _contains_hint(model_name, _EMBEDDING_HINTS):
        return [LLMType.EMBEDDING.value]
    if _contains_hint(model_name, _SPEECH2TEXT_HINTS):
        return [LLMType.SPEECH2TEXT.value]
    if _contains_hint(model_name, _TTS_HINTS):
        return [LLMType.TTS.value]

    model_types = [LLMType.CHAT.value]
    if _contains_hint(model_name, _VISION_HINTS):
        model_types.append(LLMType.IMAGE2TEXT.value)
    return model_types


def _format_model_list(raw_model_list: Any) -> list[dict[str, Any]]:
    models = raw_model_list.get("data") if isinstance(raw_model_list, dict) else raw_model_list
    if not isinstance(models, list):
        return []

    model_list = []
    for model in models:
        if not isinstance(model, dict):
            continue

        model_name = model.get("id") or model.get("name")
        if not model_name:
            continue

        model_list.append(
            {
                "name": model_name,
                "model_types": _infer_model_types(model_name),
                "max_tokens": (
                    model.get("max_tokens")
                    or model.get("max_completion_tokens")
                    or model.get("context_length")
                    or model.get("max_model_len")
                    or DEFAULT_MAX_TOKENS
                ),
            }
        )

    return model_list


def _format_remote_model_list(
    raw_model_list: Any,
    api_key: str,
    base_url: str,
) -> list[dict[str, Any]]:
    try:
        model_meta_module = importlib.import_module("rag.llm.model_meta")
        model_meta_cls = getattr(model_meta_module, "OpenAIAPICompatible")
        model_meta = model_meta_cls(api_key=api_key, base_url=base_url)
        return model_meta._format_model_list(raw_model_list)
    except Exception as exc:
        logging.debug("Fallback to local OpenAI-compatible model parser: %s", exc)
        return _format_model_list(raw_model_list)


def _fetch_remote_models(endpoint_config: dict[str, Any]) -> list[dict[str, Any]]:
    api_key = _encode_api_key(endpoint_config.get("api_key"))
    base_url = endpoint_config["base_url"]
    model_list_url = _get_model_list_url(base_url)
    response = requests.get(
        model_list_url,
        headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        timeout=MODEL_LIST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    return _format_remote_model_list(response.json(), api_key, base_url)


def _ensure_provider(tenant_id: str, provider_name: str):
    service = _tenant_model_provider_service()
    provider = service.get_by_tenant_id_and_provider_name(
        tenant_id, provider_name
    )
    if provider:
        return provider

    service.insert(
        tenant_id=tenant_id,
        provider_name=provider_name,
    )
    return service.get_by_tenant_id_and_provider_name(
        tenant_id, provider_name
    )


def _ensure_instance(provider_id: str, endpoint_config: dict[str, Any]):
    api_key = _encode_api_key(endpoint_config.get("api_key"))
    extra = _build_extra(endpoint_config.get("base_url"), endpoint_config.get("region"))
    instance_name = endpoint_config["instance_name"]
    service = _tenant_model_instance_service()
    instance = service.get_by_provider_id_and_instance_name(
        provider_id, instance_name
    )
    if instance:
        service.update_by_id(
            instance.id,
            {"api_key": api_key, "extra": extra},
        )
        return instance

    created = service.create_instance(
        provider_id=provider_id,
        instance_name=instance_name,
        api_key=api_key,
        extra=extra,
    )
    if getattr(created, "id", None):
        return created
    return service.get_by_provider_id_and_instance_name(
        provider_id, instance_name
    )


def _ensure_model(
    provider_id: str,
    instance_id: str,
    model_name: str,
    model_type: str,
    max_tokens: int,
) -> bool:
    service = _tenant_model_service()
    get_model = service.get_by_provider_id_and_instance_id_and_model_type_and_model_name
    model = get_model(
        provider_id,
        instance_id,
        model_type,
        model_name,
    )
    extra = json.dumps(
        {"max_tokens": max_tokens or DEFAULT_MAX_TOKENS},
        ensure_ascii=False,
    )
    if model:
        if model.status != ActiveStatusEnum.ACTIVE.value or model.extra != extra:
            service.update_by_id(
                model.id,
                {"status": ActiveStatusEnum.ACTIVE.value, "extra": extra},
            )
        return False

    service.insert(
        provider_id=provider_id,
        instance_id=instance_id,
        model_name=model_name,
        model_type=model_type,
        extra=extra,
    )
    return True


def _config_key(endpoint_config: dict[str, Any]) -> str:
    api_key = _encode_api_key(endpoint_config.get("api_key"))
    return "|".join(
        [
            endpoint_config["provider_name"],
            endpoint_config["instance_name"],
            endpoint_config["base_url"],
            api_key,
        ]
    )


def _build_model_id(model_name: str, instance_name: str, provider_name: str) -> str:
    return f"{model_name}@{instance_name}@{provider_name}"


def _get_initial_default_model_id(field_name: str) -> str:
    setting_field_name = DEFAULT_MODEL_SETTING_FIELDS.get(field_name)
    if not setting_field_name:
        return ""
    try:
        settings_module = importlib.import_module("common.settings")
        return getattr(settings_module, setting_field_name, "") or ""
    except Exception:
        return ""


def _should_replace_tenant_default(tenant, field_name: str) -> bool:
    current_model_id = getattr(tenant, field_name, None)
    if not current_model_id:
        return True
    return current_model_id == _get_initial_default_model_id(field_name)


def _ensure_tenant_default_models(
    tenant_id: str,
    endpoint_config: dict[str, Any],
    instance_name: str,
    remote_models: list[dict[str, Any]],
) -> None:
    service = _tenant_service()
    exists, tenant = service.get_by_id(tenant_id)
    if not exists or not tenant:
        return

    updates: dict[str, str] = {}
    for remote_model in remote_models:
        model_name = remote_model.get("name")
        if not model_name:
            continue

        model_id = _build_model_id(
            model_name,
            instance_name,
            endpoint_config["provider_name"],
        )
        model_types = remote_model.get("model_types") or [LLMType.CHAT.value]
        for model_type in model_types:
            field_name = DEFAULT_MODEL_FIELDS.get(model_type)
            if not field_name or field_name in updates:
                continue
            if not _should_replace_tenant_default(tenant, field_name):
                continue
            updates[field_name] = model_id

    if updates:
        service.update_by_id(tenant_id, updates)


def ensure_configured_default_models_for_tenant(tenant_id: str) -> int:
    endpoint_config = _get_endpoint_config()
    if not endpoint_config:
        return 0

    sync_key = (tenant_id, _config_key(endpoint_config))
    if sync_key in _SYNCED_TENANT_KEYS:
        return 0

    try:
        remote_models = _fetch_remote_models(endpoint_config)
    except Exception as exc:
        logging.warning(
            "Failed to fetch configured model list from %s: %s",
            endpoint_config["base_url"],
            exc,
        )
        return 0

    if not remote_models:
        logging.warning(
            "No models returned from configured model endpoint %s",
            endpoint_config["base_url"],
        )
        return 0

    provider = _ensure_provider(tenant_id, endpoint_config["provider_name"])
    if not provider:
        logging.warning(
            "Skip configured model import because provider %s could not be created",
            endpoint_config["provider_name"],
        )
        return 0

    instance = _ensure_instance(provider.id, endpoint_config)
    if not instance:
        logging.warning(
            "Skip configured model import because instance %s could not be created",
            endpoint_config["instance_name"],
        )
        return 0

    created_models = 0
    for remote_model in remote_models:
        model_name = remote_model.get("name")
        model_types = remote_model.get("model_types") or [LLMType.CHAT.value]
        max_tokens = _to_int(
            remote_model.get("max_tokens") or endpoint_config["max_tokens"],
            DEFAULT_MAX_TOKENS,
        )
        for model_type in model_types:
            if _ensure_model(
                provider.id,
                instance.id,
                model_name,
                model_type,
                max_tokens,
            ):
                created_models += 1

    _ensure_tenant_default_models(
        tenant_id,
        endpoint_config,
        getattr(instance, "instance_name", endpoint_config["instance_name"]),
        remote_models,
    )
    _SYNCED_TENANT_KEYS.add(sync_key)
    return created_models


def ensure_configured_default_models_for_all_tenants() -> int:
    endpoint_config = _get_endpoint_config()
    if not endpoint_config:
        return 0

    total_created = 0
    for tenant in _tenant_service().get_all():
        total_created += ensure_configured_default_models_for_tenant(tenant.id)
    return total_created


def normalize_model_type(model_type: str | enum.Enum) -> str:
    model_type_value = model_type if isinstance(model_type, str) else model_type.value
    if model_type_value == "asr":
        return LLMType.SPEECH2TEXT.value
    if model_type_value == "vision":
        return LLMType.IMAGE2TEXT.value
    return model_type_value
