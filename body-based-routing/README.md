Create a proxy only subnet with
```
gcloud compute networks subnets create spencerjp-proxy-only-subnet \
    --purpose=REGIONAL_MANAGED_PROXY \
    --role=ACTIVE \
    --region=us-central1 \
    --network=default \
    --range=192.168.10.0/24
```

Ensure gcloud services enable networkservices.googleapis.com

```
helm install body-based-router oci://registry.k8s.io/gateway-api-inference-extension/charts/body-based-routing \
    --version v1.4.0 \
    --set provider.name=gke \
    --set inferenceGateway.name=ray-multi-model-gateway \
    --values helm-values.yaml
```
