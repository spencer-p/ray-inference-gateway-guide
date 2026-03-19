import logging
from typing import List, Optional

from ray.serve.llm import build_openai_app
from ray.serve.request_router import PendingRequest, RunningReplica

from ray.llm._internal.serve.core.protocol import RawRequestInfo
from ray.serve._private.request_router.pow_2_router import PowerOfTwoChoicesRequestRouter

logger = logging.getLogger(__name__)

# TODO(spencer-p): Ideally the IGW-aware request router would be provided as a
# mixin from Ray LLM's ray.serve.request_router package. This implementation
# uses some private apis, like RawRequestInfo and the running replicas' IPs.
class InferenceGatewayRequestRouter(PowerOfTwoChoicesRequestRouter):
    """Request router that routes to a specific backend IP if a header is present.

    It looks for 'x-gateway-destination-endpoint' header in the request.
    If present, it filters candidate replicas by their node IP.
    """

    async def choose_replicas(
        self,
        candidate_replicas: List[RunningReplica],
        pending_request: Optional[PendingRequest] = None,
    ) -> List[List[RunningReplica]]:
        if not pending_request:
          return []

        # Look for RawRequestInfo in arguments to read HTTP headers.
        raw_request_info = None
        for arg in pending_request.args:
            if isinstance(arg, RawRequestInfo):
                raw_request_info = arg
                break

        if not raw_request_info:
            logger.warning("igw: No request metadata is available; cannot route from headers. Falling back.")
            return await super().choose_replicas(candidate_replicas, pending_request)

        target_endpoint = raw_request_info.headers.get(
            "x-gateway-destination-endpoint"
        )
        if not target_endpoint:
            logger.warning(f"igw: no gateway endpoint found in {raw_request_info.headers}")
            return await super().choose_replicas(candidate_replicas, pending_request)

        # Header is "ip:port", we only care about IP.
        target_ip = target_endpoint.split(":")[0]

        # TODO(spencer-p): Cache a lookup map of IP to replica ID.
        filtered_replicas = [
            r for r in candidate_replicas if r._replica_info.node_ip == target_ip
        ]

        if not filtered_replicas:
            logger.warning(
                f"igw: Request specified target IP {target_ip} via header, "
                "but no matching replicas were found. Falling back to default routing."
            )
            return await super().choose_replicas(candidate_replicas, pending_request)

        if len(filtered_replicas) == 1:
          logger.info(f"igw: requested endpoint {target_ip} can only be fulfilled by {filtered_replicas[0].replica_id}")
          return [filtered_replicas]

        # Run power of two choices with the filtered replicas.
        logger.info(f"igw: requested endpoint {target_ip} has {len(filtered_replicas)} target replicas, falling back")
        return await super().choose_replicas(
            filtered_replicas, pending_request
        )


app = build_openai_app({
    "llm_configs": [
        {
            "model_loading_config": {
                "model_id": "gemma-2b-it",
                "model_source": "google/gemma-2b-it",
            },
            "accelerator_type": "L4",
            "log_engine_metrics": True,
            "deployment_config": {
                "autoscaling_config": {
                    "min_replicas": 4,
                    "max_replicas": 4,
                },
                "health_check_period_s": 600,
                "health_check_timeout_s": 300,
                "request_router_config": {
                    "request_router_class": "serve.InferenceGatewayRequestRouter"
                }
            },
            "runtime_env": {
                "env_vars": {
                    "VLLM_USE_V1": "1",
                    "TENSOR_PARALLELISM": "2",
                }
            }
        }
    ]
})
