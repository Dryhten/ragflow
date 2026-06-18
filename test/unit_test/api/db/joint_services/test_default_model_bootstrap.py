import json
from types import SimpleNamespace


def test_bootstrap_matrix_endpoint_imports_all_remote_models(monkeypatch):
    from api.db.joint_services import default_model_bootstrap as module

    module._SYNCED_TENANT_KEYS.clear()
    provider_inserts = []
    instance_creates = []
    model_inserts = []
    tenant_updates = []
    requested_urls = []

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {"id": "matrix-chat"},
                    {"id": "matrix-embedding"},
                ]
            }

    class ProviderService:
        @staticmethod
        def get_by_tenant_id_and_provider_name(tenant_id, provider_name):
            if provider_inserts:
                return SimpleNamespace(id="provider-1", provider_name=provider_name)
            return None

        @staticmethod
        def insert(**kwargs):
            provider_inserts.append(kwargs)

    class InstanceService:
        @staticmethod
        def get_by_provider_id_and_instance_name(provider_id, instance_name):
            return None

        @staticmethod
        def create_instance(provider_id, instance_name, api_key, extra):
            instance_creates.append(
                {
                    "provider_id": provider_id,
                    "instance_name": instance_name,
                    "api_key": api_key,
                    "extra": json.loads(extra),
                }
            )
            return SimpleNamespace(id="instance-1", instance_name=instance_name)

    class ModelService:
        @staticmethod
        def get_by_provider_id_and_instance_id_and_model_type_and_model_name(
            provider_id, instance_id, model_type, model_name
        ):
            return None

        @staticmethod
        def insert(**kwargs):
            model_inserts.append(kwargs)

    class TenantService:
        @staticmethod
        def get_by_id(tenant_id):
            return True, SimpleNamespace()

        @staticmethod
        def update_by_id(tenant_id, payload):
            tenant_updates.append((tenant_id, payload))

    monkeypatch.setattr(module, "TenantModelProviderService", ProviderService)
    monkeypatch.setattr(module, "TenantModelInstanceService", InstanceService)
    monkeypatch.setattr(module, "TenantModelService", ModelService)
    monkeypatch.setattr(module, "TenantService", TenantService)
    monkeypatch.setattr(
        module,
        "config_utils",
        SimpleNamespace(get_base_config=lambda key, default=None: {
            "name": "Matrix",
            "factory": "OpenAI-API-Compatible",
            "api_key": "sk-from-config",
            "base_url": "https://models.example/v1",
        }
        if key == "user_default_llm"
        else default),
    )
    monkeypatch.setattr(
        module.requests,
        "get",
        lambda url, **kwargs: requested_urls.append((url, kwargs)) or Response(),
    )

    created = module.ensure_configured_default_models_for_tenant("tenant-1")

    assert created == 2
    assert requested_urls == [
        (
            "https://models.example/v1/models",
            {
                "headers": {"Authorization": "Bearer sk-from-config"},
                "timeout": 15,
            },
        )
    ]
    assert provider_inserts == [
        {
            "tenant_id": "tenant-1",
            "provider_name": "OpenAI-API-Compatible",
        }
    ]
    assert instance_creates == [
        {
            "provider_id": "provider-1",
            "instance_name": "Matrix",
            "api_key": "sk-from-config",
            "extra": {"base_url": "https://models.example/v1"},
        }
    ]
    assert model_inserts == [
        {
            "provider_id": "provider-1",
            "instance_id": "instance-1",
            "model_name": "matrix-chat",
            "model_type": "chat",
            "extra": json.dumps({"max_tokens": 8192}, ensure_ascii=False),
        },
        {
            "provider_id": "provider-1",
            "instance_id": "instance-1",
            "model_name": "matrix-embedding",
            "model_type": "embedding",
            "extra": json.dumps({"max_tokens": 8192}, ensure_ascii=False),
        },
    ]
    assert tenant_updates == [
        (
            "tenant-1",
            {
                "llm_id": "matrix-chat@Matrix@OpenAI-API-Compatible",
                "embd_id": "matrix-embedding@Matrix@OpenAI-API-Compatible",
            },
        )
    ]


def test_bootstrap_keeps_existing_tenant_default_models(monkeypatch):
    from api.db.joint_services import default_model_bootstrap as module

    module._SYNCED_TENANT_KEYS.clear()
    tenant_updates = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"id": "matrix-chat"}]}

    class ProviderService:
        @staticmethod
        def get_by_tenant_id_and_provider_name(_tenant_id, provider_name):
            return SimpleNamespace(id="provider-1", provider_name=provider_name)

    class InstanceService:
        @staticmethod
        def get_by_provider_id_and_instance_name(_provider_id, instance_name):
            return SimpleNamespace(id="instance-1", instance_name=instance_name)

        @staticmethod
        def update_by_id(_instance_id, _payload):
            return True

    class ModelService:
        @staticmethod
        def get_by_provider_id_and_instance_id_and_model_type_and_model_name(
            _provider_id, _instance_id, _model_type, _model_name
        ):
            return None

        @staticmethod
        def insert(**_kwargs):
            return True

    class TenantService:
        @staticmethod
        def get_by_id(_tenant_id):
            return True, SimpleNamespace(llm_id="custom-chat@Other@Provider")

        @staticmethod
        def update_by_id(tenant_id, payload):
            tenant_updates.append((tenant_id, payload))

    monkeypatch.setattr(module, "TenantModelProviderService", ProviderService)
    monkeypatch.setattr(module, "TenantModelInstanceService", InstanceService)
    monkeypatch.setattr(module, "TenantModelService", ModelService)
    monkeypatch.setattr(module, "TenantService", TenantService)
    monkeypatch.setattr(
        module,
        "config_utils",
        SimpleNamespace(get_base_config=lambda key, default=None: {
            "name": "Matrix",
            "factory": "OpenAI-API-Compatible",
            "api_key": "sk-from-config",
            "base_url": "https://models.example/v1",
        }
        if key == "user_default_llm"
        else default),
    )
    monkeypatch.setattr(module.requests, "get", lambda *_args, **_kwargs: Response())

    module.ensure_configured_default_models_for_tenant("tenant-1")

    assert tenant_updates == []
