# Guide: Serve Ray LLM using Inference Gateway on GKE

## Overview

This guide will walk you through setting up an OpenAI-compatible endpoint using
Ray Serve with a load balancer configured and managed through [Inference
Gateway](https://gateway-api-inference-extension.sigs.k8s.io/) on GKE.

Inference Gateway will provide a load balancer provisioned by your infra
provider, in this case GKE on GCP. The load balancer will be configured with
HTTPRoute objects, ideal for platform operators seeking to manager inference
endpoints managed by ai/ml workload owners. It will also take advantage of an
Endpoint Picker which monitors the vLLM metrics on the Ray workers and directs
traffic.

Ray Serve will manage deployment and autoscaling of the model.

**Key points**:

1. The kubernetes cluster will be configured to take full advantage of the new
   extensions to kubernetes.
2. An _Endpoint Picker_ (EPP) will be configured to monitor Ray for vLLM metrics
   for routing choices.
3. An OpenAI-compatible endpoint for an open model will run on Ray Serve.
4. Ray Serve will use **routing hints from the EPP** to direct traffic.

## Dependencies

-   gcloud
-   kubectl

Set up some variables to set up our cluster:

```
CLUSTER=$(whoami)-ray-igw
PROJECT=  # Your project.
LOCATION=us-central1-b
HUGGING_FACE_TOKEN=  # Your token.
```

Create your GKE cluster:

```
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

Create a GPU pool with four L4s:

```
gcloud container node-pools create gpu-pool \
    --cluster=$CLUSTER \
    --location=$LOCATION \
    --accelerator="type=nvidia-l4,count=1,gpu-driver-version=latest" \
    --machine-type=g2-standard-8 \
    --num-nodes=4
```

Deploy your hugging face token to the cluster:

```
kubectl create secret generic hf-secret \
    --from-literal=hf_api_token=${HUGGING_FACE_TOKEN?}
```

## Deploy Ray Serve

Apply the `RayService` manifest to deploy `gemma-2b-it` and associated
networking objects.

This command will create:
1. A gateway with class `gke-l7-rilb`. See [other types
   available](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/gatewayclass-capabilities)
   if tinkering.
1. An HTTPRoute with sends all traffic on `/` to our inferencepool
1. An InferencePool, which has a label selector for the worker nodes of our Ray
   cluster, as well as a reference to the endpoint picker's Service (see below).
1. A HealthCheckPolicy, which instructs the load balancer to monitor the Ray
   workers' health to select backends.
1. The RayService object. This is configured to provision four worker nodes with
   L4 GPUs and four backend replicas. See serve.py for the complete
   configuration.
1. Also in serve.py, we are using a custom request router that inspects for
   hints from the load balancer (a header named
   `x-gateway-destination-endpoint`) to direct requests internally.

*Note: The worker nodes use `RAY_SERVE_ENABLE_HA_PROXY=1` to enable improved
network performance in Ray Serve.*

```bash
kubectl apply -f gemma-2b-it.yaml
```

## Configure and Deploy the Endpoint Picker (EPP)

The EPP requires explicit metrics configuration to interpret Ray Serve's renamed
vLLM metrics, and the experimental Data Layer must be enabled.

The  configuration correctly formats the Ray Prometheus metrics (e.g.,
`ray_vllm_num_requests_waiting`) as PromQL selectors and places the
`core-metrics-extractor` securely within the Data Layer configuration.


Apply the EPP manifest. This manifest includes a custom `ServiceAccount` and
`Role` that grant the EPP necessary access to `pods`, `inferencepools`, and
`inferenceobjectives`.


```bash
kubectl apply -f endpoint-picker.yaml
```

*Note: The EPP container image is the reference endpoint picker; see
https://github.com/kubernetes-sigs/gateway-api-inference-extension if you would
like to tinker.*

## Test the Deployment

Port-forward or otherwise access your Gateway/Service IP, and send an
OpenAI-compatible request.

```bash
kubectl get gateways

# Note this must be in the same network as your cluster, unless you reconfigured
# your gateway to be external.
curl http://<YOUR_ENDPOINT>/v1/chat/completions \
  --header 'Content-Type: application/json' \
  --data '{"model":"gemma-2b-it","messages":[{"role":"user","content":"Provide steps to serve an LLM using Ray Serve"}]}'
```

You may find [kubectl-curl](https://github.com/spencer-p/kubectl-curl) useful.

To test an alternate network path, you may deploy `ingress.yaml` to provision a
"plain" load balancer and rely completely on Ray's internal routing.
