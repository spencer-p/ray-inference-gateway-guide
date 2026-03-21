# GKE Inference Gateway for Ray Serve: Implementation Guides

This repository contains implementation guides and manifests for deploying [Ray Serve](https://docs.ray.io/en/latest/serve/index.html) with the [Inference Gateway](https://gateway-api-inference-extension.sigs.k8s.io/) on GKE. These patterns enable platform operators to manage high-performance inference endpoints with advanced routing and load balancing.

## Implementation Patterns

Select a guide based on your routing and load-balancing requirements:

### 1. [Ray Serve with External Endpoint Picker (EPP)](./external-epp/README.md)
**Best for: Performance-Optimized Single Model Routing.**
This guide demonstrates using an **Endpoint Picker** that monitors vLLM-specific metrics (like request queue lengths) on Ray workers. It uses these metrics to make real-time routing decisions, ensuring traffic is directed to the most available worker node.

*   **Key Feature**: Metric-aware load balancing using the `InferencePool` and `EndpointPicker`.
*   **Routing**: Standard path-based routing via `HTTPRoute`.

### 2. [Body-Based Routing (BBR)](./body-based-routing/README.md)
**Best for: Multi-Model OpenAI-Compatible Endpoints.**
This guide shows how to route traffic to different Ray Services based on the `model` field within the JSON request body. This allows a single Gateway IP to serve multiple different LLMs (e.g., Gemma, Qwen, Llama) without requiring clients to manage custom HTTP headers.

*   **Key Feature**: Automatic header extraction from JSON payloads using the `body-based-router` extension.
*   **Routing**: Body-field-to-header mapping combined with header-based `HTTPRoute` rules.

## Prerequisites

Regardless of the pattern chosen, you will need:
*   A GKE cluster (v1.35+) with `GatewayAPI` and `RayOperator` addons enabled.
*   GPU-enabled node pools (e.g., NVIDIA L4).
*   A Hugging Face API token stored as a Kubernetes secret (`hf-secret`).

---
*For more information on the underlying technology, see the [Gateway API Inference Extension repository](https://github.com/kubernetes-sigs/gateway-api-inference-extension).*
