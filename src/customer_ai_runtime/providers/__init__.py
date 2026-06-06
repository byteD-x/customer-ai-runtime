"""Provider package exports.

Concrete provider modules are loaded lazily so local runtime startup stays
independent from optional cloud SDKs.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORT_MODULES = {
    "AliyunASRProvider": "customer_ai_runtime.providers.aliyun_provider",
    "AliyunTTSProvider": "customer_ai_runtime.providers.aliyun_provider",
    "GraphQLBusinessAdapter": "customer_ai_runtime.providers.graphql_business_provider",
    "GrpcBusinessAdapter": "customer_ai_runtime.providers.grpc_business_provider",
    "HttpBusinessAdapter": "customer_ai_runtime.providers.http_business_provider",
    "LocalASRProvider": "customer_ai_runtime.providers.local",
    "LocalBusinessAdapter": "customer_ai_runtime.providers.local",
    "LocalLLMProvider": "customer_ai_runtime.providers.local",
    "LocalTTSProvider": "customer_ai_runtime.providers.local",
    "LocalVectorStoreProvider": "customer_ai_runtime.providers.local",
    "MilvusVectorStoreProvider": "customer_ai_runtime.providers.milvus_provider",
    "OpenAIASRProvider": "customer_ai_runtime.providers.openai_provider",
    "OpenAILLMProvider": "customer_ai_runtime.providers.openai_provider",
    "OpenAITTSProvider": "customer_ai_runtime.providers.openai_provider",
    "PineconeVectorStoreProvider": "customer_ai_runtime.providers.pinecone_provider",
    "QdrantVectorStoreProvider": "customer_ai_runtime.providers.qdrant_provider",
    "TencentASRProvider": "customer_ai_runtime.providers.tencent_provider",
    "TencentTTSProvider": "customer_ai_runtime.providers.tencent_provider",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


__all__ = [
    "AliyunASRProvider",
    "AliyunTTSProvider",
    "GraphQLBusinessAdapter",
    "GrpcBusinessAdapter",
    "HttpBusinessAdapter",
    "LocalASRProvider",
    "LocalBusinessAdapter",
    "LocalLLMProvider",
    "LocalTTSProvider",
    "LocalVectorStoreProvider",
    "MilvusVectorStoreProvider",
    "OpenAIASRProvider",
    "OpenAILLMProvider",
    "OpenAITTSProvider",
    "PineconeVectorStoreProvider",
    "QdrantVectorStoreProvider",
    "TencentASRProvider",
    "TencentTTSProvider",
]
