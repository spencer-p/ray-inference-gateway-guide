import logging
from typing import List, Optional

from ray.llm._internal.serve.core.protocol import RawRequestInfo
from ray.serve._private.constants import SERVE_LOGGER_NAME
from ray.serve._private.request_router.common import PendingRequest
from ray.serve._private.request_router.pow_2_router import PowerOfTwoChoicesRequestRouter
from ray.serve._private.request_router.replica_wrapper import RunningReplica
from ray.util.annotations import PublicAPI
from ray.serve.llm import build_openai_app

logger = logging.getLogger(SERVE_LOGGER_NAME)

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
        logger.info(f"routing request for {pending_request}")
        if not pending_request:
          return []

        # Look for RawRequestInfo in arguments or keyword arguments.
        raw_request_info = None
        for arg in pending_request.args:
            if isinstance(arg, RawRequestInfo):
                logger.info("raw_request_info found in pending_request.args")
                raw_request_info = arg
                break

        if not raw_request_info and "raw_request_info" in pending_request.kwargs:
            logger.info("raw_request_info found in kwargs")
            raw_request_info = pending_request.kwargs["raw_request_info"]

        if not raw_request_info:
            logger.warning("no raw request info found")
            return await super().choose_replicas(candidate_replicas, pending_request)

        target_endpoint = raw_request_info.headers.get(
            "x-gateway-destination-endpoint"
        )
        if not target_endpoint:
            logger.warning(f"no gateway endpoint found in {raw_request_info.headers}")
            return await super().choose_replicas(candidate_replicas, pending_request)
        logger.info(f"igw provided hint to route to {target_endpoint}")

        # Header is "ip:port", we only care about IP.
        target_ip = target_endpoint.split(":")[0]

        # TODO(spencer-p): Cache a lookup map of IP to replica ID.
        filtered_replicas = [
            r for r in candidate_replicas if r._replica_info.node_ip == target_ip
        ]

        if not filtered_replicas:
            logger.warning(
                f"Request specified target IP {target_ip} via header, "
                "but no matching replicas were found. Falling back to default routing."
            )
            return await super().choose_replicas(candidate_replicas, pending_request)

        if len(filtered_replicas) == 1:
          return [filtered_replicas]

        # Run power of two choices with the filtered replicas.
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
