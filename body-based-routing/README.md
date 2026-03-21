# Guide: Body-Based Routing for Ray Serve on GKE

## Overview

This guide demonstrates how to implement **body-based routing** for an
OpenAI-compatible Ray Serve deployment on GKE. Using the [Inference
Gateway](https://gateway-api-inference-extension.sigs.k8s.io/) and its
body-based routing extension, you can route requests to different model backends
based on fields within the JSON request body (e.g., the `model` field).

This setup is ideal for multi-model endpoints where a single Gateway must
dispatch traffic to multiple Ray services depending on the requested model,
while allowing the RayServices to be managed separately (possibly by different
owning teams).

**Key points**:

1. A **Body-Based Router** extension is deployed via Helm to extract model names from JSON payloads.
2. A **GKE Gateway (L7 RILB)** handles the incoming traffic.
3. **HTTPRoute** rules use headers populated by the router to direct traffic to the correct Ray Service.
4. **Ray Serve**: Multiple clusters manage the lifecycle and autoscaling of siloed models.

## Dependencies

-   gcloud
-   kubectl
-   helm (v3.0+)

Set up environment variables:

```bash
CLUSTER=$(whoami)-ray-bbr
PROJECT=$(gcloud config get-value project)
LOCATION=us-central1-b
REGION=us-central1
HUGGING_FACE_TOKEN=<your-token>
```

## Infrastructure Setup

### 1. Create a GKE Cluster

Create a cluster with the Ray Operator and Gateway API enabled:

```bash
gcloud container clusters create $CLUSTER \
  --project $PROJECT \
  --location $LOCATION \
  --release-channel rapid \
  --cluster-version 1.35 \
  --gateway-api standard \
  --addons HttpLoadBalancing,RayOperator \
  --enable-ray-cluster-logging \
  --enable-ray-cluster-monitoring
```

### 2. Create a GPU Node Pool

Provision L4 GPUs for your model workloads:

```bash
gcloud container node-pools create gpu-pool \
    --cluster=$CLUSTER \
    --location=$LOCATION \
    --accelerator="type=nvidia-l4,count=1,gpu-driver-version=latest" \
    --machine-type=g2-standard-8 \
    --num-nodes=4
```

### 3. Configure Networking

Body-based routing requires a proxy-only subnet for the Regional Internal Load Balancer:

```bash
gcloud compute networks subnets create bbr-proxy-only-subnet \
    --purpose=REGIONAL_MANAGED_PROXY \
    --role=ACTIVE \
    --region=$REGION \
    --network=default \
    --range=192.168.10.0/24
```

Enable the necessary network services API:

```bash
gcloud services enable networkservices.googleapis.com
```

### 4. Deploy Hugging Face Secret

```bash
kubectl create secret generic hf-secret \
    --from-literal=hf_api_token=${HUGGING_FACE_TOKEN?}
```

## Deploy the Body-Based Router

The Body-Based Router extension intercepts requests, parses the JSON body, and extracts the `model` field into an `X-Gateway-Model-Name` header.

Install it using Helm:

```bash
helm install body-based-router oci://registry.k8s.io/gateway-api-inference-extension/charts/body-based-routing \
    --version v1.4.0 \
    --set provider.name=gke \
    --set inferenceGateway.name=ray-multi-model-gateway \
    --values helm-values.yaml
```

*Note: `helm-values.yaml` defines the mapping from the `model` JSON field to the `X-Gateway-Model-Name` header.*

## Deploy Ray Services

Apply the RayService manifests to deploy your models. Each manifest defines a Ray cluster running a specific LLM.

```bash
# Deploy Gemma 2B
kubectl apply -f gemma-2b-it.yaml

# Deploy Qwen 2.5 3B
kubectl apply -f qwen2.5-3b.yaml
```

### Configure Health Checks

Apply the `HealthCheckPolicy` to ensure the load balancer accurately monitors Ray worker health:

```bash
kubectl apply -f healthcheck-policy.yaml
```

## Configure Routing

Apply the `Gateway` and `HTTPRoute` manifests. The `HTTPRoute` contains rules that match the `X-Gateway-Model-Name` header (populated by the body-based router) to route traffic to the appropriate Ray service.

```bash
kubectl apply -f gateway.yaml
```

## Test the Deployment

Once the Gateway is provisioned and the Ray clusters are ready, you can test routing by sending requests with different model names in the JSON body.

### 1. Get the Gateway IP

```bash
kubectl get gateways ray-multi-model-gateway
```

### 2. Send Requests

Test routing to **Gemma**:

```bash
curl http://<GATEWAY_IP>/v1/chat/completions \
  --header 'Content-Type: application/json' \
  --data '{
    "model": "gemma-2b-it",
    "messages": [{"role": "user", "content": "Tell me about GKE."}]
  }'
```

Test routing to **Qwen**:

```bash
curl http://<GATEWAY_IP>/v1/chat/completions \
  --header 'Content-Type: application/json' \
  --data '{
    "model": "qwen-2.5-3b",
    "messages": [{"role": "user", "content": "How does Ray Serve work?"}]
  }'
```

The Body-Based Router will automatically extract the `"model"` value and ensure it reaches the correct backend service defined in `gateway.yaml`.
