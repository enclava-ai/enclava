# Kubernetes Deployment for Enclava

This directory contains Kubernetes manifests and configuration for deploying Enclava to a Kubernetes cluster.

## Directory Structure

```
k8s/
├── base/                   # Base Kustomize configuration
│   ├── namespace.yaml     # Namespace definition
│   ├── configmap.yaml     # Application configuration
│   ├── secrets.yaml       # Sensitive configuration
│   ├── postgres.yaml      # PostgreSQL StatefulSet
│   ├── redis.yaml         # Redis StatefulSet
│   ├── qdrant.yaml        # Qdrant vector database
│   ├── backend.yaml       # Backend deployment
│   ├── frontend.yaml      # Frontend deployment
│   ├── nginx.yaml         # Nginx ingress
│   ├── migration-job.yaml # Database migration job
│   └── kustomization.yaml # Kustomize configuration
├── overlays/              # Environment-specific configurations
│   ├── dev/              # Development environment
│   ├── staging/          # Staging environment
│   └── prod/             # Production environment
├── create-ghcr-secret.sh  # Script to create image pull secret
└── README_GHCR.md         # GitHub Container Registry setup guide
```

## Prerequisites

- Kubernetes cluster (1.24+)
- kubectl configured with cluster access
- Kustomize (or kubectl with kustomize support)
- Default StorageClass configured in cluster

## Quick Start

### 1. Create Namespace and Secrets

```bash
# Create namespace
kubectl create namespace enclava

# Create image pull secret (if images are private)
./create-ghcr-secret.sh

# Or manually:
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=<github-username> \
  --docker-password=<github-token> \
  --namespace=enclava
```

### 2. Configure Application

Edit the configuration files with your values:

```bash
# Edit secrets (use base64 encoded values)
vi base/secrets.yaml

# Edit configmap if needed
vi base/configmap.yaml
```

### 3. Deploy

```bash
# Deploy base configuration
kubectl apply -k base/

# Or deploy with environment overlay
kubectl apply -k overlays/production/
```

### 4. Verify Deployment

```bash
# Check pods
kubectl get pods -n enclava

# Check services
kubectl get svc -n enclava

# Check ingress (if configured)
kubectl get ingress -n enclava

# View logs
kubectl logs -f deployment/backend-deployment -n enclava
```

## Configuration Management

### Using Environment Variables

You can generate Kubernetes secrets from your `.env` file:

```bash
# Create secret from env file
kubectl create secret generic enclava-env \
  --from-env-file=../../.env \
  --namespace=enclava
```

### Using Kustomize Overlays

Create environment-specific configurations:

```bash
# Development
kubectl apply -k overlays/dev/

# Staging
kubectl apply -k overlays/staging/

# Production
kubectl apply -k overlays/prod/
```

## Storage Configuration

The deployment uses PersistentVolumeClaims for:
- PostgreSQL data (10Gi)
- Redis data (2Gi)
- Qdrant data (5Gi)

Ensure your cluster has a default StorageClass or modify the PVCs accordingly.

## Networking

### Internal Services

All services communicate internally using ClusterIP services:
- `postgres-service:5432` - PostgreSQL
- `redis-service:6379` - Redis
- `qdrant-service:6333` - Qdrant
- `backend-service:8000` - Backend API
- `frontend-service:3000` - Frontend

### External Access

Configure external access using:

1. **LoadBalancer** (Cloud providers):
```yaml
spec:
  type: LoadBalancer
  ports:
    - port: 80
```

2. **NodePort** (On-premise):
```yaml
spec:
  type: NodePort
  ports:
    - port: 80
      nodePort: 30080
```

3. **Ingress** (Recommended):
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: enclava-ingress
spec:
  rules:
  - host: enclava.your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: nginx-service
            port:
              number: 80
```

## Scaling

### Horizontal Scaling

```bash
# Scale backend
kubectl scale deployment backend-deployment --replicas=3 -n enclava

# Scale frontend
kubectl scale deployment frontend-deployment --replicas=2 -n enclava

# Autoscaling
kubectl autoscale deployment backend-deployment \
  --min=2 --max=10 --cpu-percent=70 -n enclava
```

### Vertical Scaling

Edit resource limits in deployment files:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "2000m"
```

## Monitoring

### Basic Monitoring

```bash
# Resource usage
kubectl top pods -n enclava
kubectl top nodes

# Events
kubectl get events -n enclava --sort-by='.lastTimestamp'

# Describe resources
kubectl describe pod <pod-name> -n enclava
```

### Prometheus Integration

Add annotations for Prometheus scraping:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/metrics"
```

## Backup and Recovery

### Database Backup

```bash
# Create backup
kubectl exec -it postgres-0 -n enclava -- \
  pg_dump -U enclava_user enclava_db > backup.sql

# Restore backup
kubectl exec -i postgres-0 -n enclava -- \
  psql -U enclava_user enclava_db < backup.sql
```

### Volume Snapshots

If your storage provider supports snapshots:

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: postgres-snapshot
spec:
  volumeSnapshotClassName: csi-snapclass
  source:
    persistentVolumeClaimName: postgres-pvc
```

## Troubleshooting

### Common Issues

1. **Image Pull Errors**:
```bash
kubectl describe pod <pod-name> -n enclava
# Check for ImagePullBackOff
# Verify ghcr-secret is created correctly
```

2. **Database Connection Issues**:
```bash
# Check if postgres is running
kubectl get pod postgres-0 -n enclava
# Check logs
kubectl logs postgres-0 -n enclava
```

3. **PVC Issues**:
```bash
# Check PVC status
kubectl get pvc -n enclava
# Check available storage classes
kubectl get storageclass
```

4. **Service Discovery Issues**:
```bash
# Test DNS resolution
kubectl exec -it backend-deployment-xxx -n enclava -- nslookup postgres-service
```

## Security Considerations

1. **Network Policies**: Implement network policies to restrict traffic
2. **RBAC**: Use proper RBAC for service accounts
3. **Secrets Management**: Consider using external secret managers (Vault, Sealed Secrets)
4. **Pod Security**: Use security contexts and pod security policies
5. **Image Scanning**: Scan images for vulnerabilities before deployment

## Cleanup

To remove the deployment:

```bash
# Delete all resources
kubectl delete -k base/

# Delete namespace (removes everything)
kubectl delete namespace enclava

# Delete PVCs (if not automatically deleted)
kubectl delete pvc --all -n enclava
```

## Advanced Configuration

See [overlays/](overlays/) directory for examples of:
- Resource limits customization
- Replica count adjustments
- Environment-specific configurations
- Custom ingress rules
- TLS/SSL configuration

## Support

For issues specific to Kubernetes deployment:
- Check pod logs: `kubectl logs <pod-name> -n enclava`
- Check events: `kubectl get events -n enclava`
- Review [GHCR setup guide](README_GHCR.md)
- Open an issue on [GitHub](https://github.com/enclava-ai/enclava/issues)