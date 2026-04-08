# Serve multiple RayServices on one endpoint with Inference Gateway

The Kubernetes [Gateway
API](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/gateway-api)
and its inference extensions represent the next generation of Kubernetes Ingress
and load balancing, while Ray Serve offers the best and most flexible inference
serving stack you know and love.

Together, these combine to enable key features like multi-cluster serving
capabilities that can't be performed with Ray alone. With Gateway, your
application developers can manage many Ray Services, while your cluster operator
can configure managing traffic between them.

With KubeRay or the [Ray Operator addon for
GKE](https://docs.cloud.google.com/kubernetes-engine/docs/add-on/ray-on-gke/concepts/overview),
each RayService you deploy gets its own Service. By configuring HTTPRoute
objects with these services plus a Gateway, we can enable:

1. **Path routing**: Configure each RayService with a path prefix, then serve
   them with one Gateway routing to multiple Ray Services using the HTTPRoute
   HTTPPathMatch.
2. **Model aware routing**: choosing a Ray Service to route to based on the request body, for example by
   extracting the requested model from an OpenAI-API JSON request.
3. **Governance**: Require API keys to use your service or enforce quota for
   users using [Apigee for authentication and API
   management](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/customize-gke-inference-gateway-configurations#config-auth-api-management).
4. Split traffic across multiple GKE clusters with RayServices, to attain higher
   availability or capacity with [multi-cluster Gateways](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/multi-cluster-gateways).
