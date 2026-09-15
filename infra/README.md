# Infrastructure blueprint — R1 DEMO trên AWS

> R1-DEMO-2026-09: gần30 người,6 tuần; AWS và GitHub Actions, demo đủ luồng trước, scale sau. Đây là blueprint, chưa có tài nguyên được tạo. [IMPLEMENT.md](../IMPLEMENT.md) bất biến khóa tasks; [ARCHITECTURE.md](../ARCHITECTURE.md) mục13 chốt topology/security/budgets.

## 1. R1 phải triển khai

Một private EC2 host chạy Compose app services + Redis cache + Airflow LocalExecutor + OTel/Prometheus/Grafana. RDS PostgreSQL17 Single-AZ giữ core và Airflow metadata trong DB/roles riêng; S3 private/versioned; ECR images; Cognito OIDC; Secrets Manager/KMS; ALB/ACM cùng origin web/API/WS; SSM thay public SSH.

Network cần ALB/subnet group đúng yêu cầu dịch vụ, một approved NAT egress tới AWS APIs và model provider; app/RDS vẫn single-instance, không hứa HA. Tài nguyên phải gắn owner/environment/budget tags; dry plan không có nghĩa đã được quyền apply.

## 2. Ownership và deliverables

| Đường dẫn dự kiến | Trách nhiệm |
| --- | --- |
| terraform/bootstrap/ | S3 protected state/native lock, initial scoped IAM |
| terraform/modules/demo_network/ | VPC/subnets/ALB/egress/SGs hoặc approved imported bindings |
| terraform/modules/demo_data/ | RDS/S3/KMS/secrets references, backup/retention |
| terraform/modules/demo_compute/ | EC2/SSM/IAM/ECR/Cognito bindings |
| terraform/environments/demo/ | Root stack, variables và nonsecret environment values |
| ansible/roles/demo_host/ | OS/SSM/Compose/bootstrap, không quản application release |
| compose/compose.local.yaml | Local dependencies và deterministic fake services |
| compose/compose.demo.yaml | Pin cloud demo images/config, resource limits/private networks |
| deploy/ | Validated SSM document/helper, release manifest schema, rollback |
| observability/ | OTel redaction/limits, Prometheus/Grafana demo dashboards/alerts |
| tests/ | IAM/network/deploy/restore/load fixtures |
| runbooks/ | Bootstrap/deploy/rollback/backup/restore/incident/stop-cost |
| .github/workflows/ tại repo root | CI, build, deploy-demo, infra-plan/apply, baseline guard |

Đây là planned tree, không tuyên bố các files đã tồn tại. Terraform owns cloud, Ansible owns host config, GitHub Actions/SSM owns app digest rollout. Không nhiều reconcilers cùng sửa một resource.

## 3. Quy trình delivery

PR offline tests → trusted merge build/scan/SBOM/sign/ECR → human protected demo approval → short-lived AWS OIDC deploy role → pinned SSM release document → migration tương thích → Compose rollout/smoke → receipt. Build/push/deploy/infra roles tách. OIDC sub/aud bind đúng repo/environment hiện hành, không wildcard toàn organization.

Deploy không được tùy ý chạy shell parameters hoặc sửa IAM/document/đọc secrets. Host helper chỉ nhận release manifest đã kiểm provenance/digest; protected environment bảo vệ người có thể deploy code privileged. Rollback previous compatible image/config; không reverse destructive migrations.

Infra plan/apply workflow riêng, state encrypted/versioned/private, approvals cho cost/destructive changes. Không long-lived AWS keys, raw kubeconfig, tfstate/plan hoặc secret values trong Git. No untrusted PR cloud credentials.

## 4. Demo release gates

- Scope resource/input/cost/runs bounded theo ARCHITECTURE.
- Web TLS/auth, private DB/Airflow/Grafana, deny metadata/secret access từ compute.
- 100 WS/20rooms/10sends/s,1h load+4h soak; no lost committed state trong tested restart scope.
- Restart API/worker/Redis/Airflow, timeout provider, duplicate delivery; không duplicate visible outcome.
- RDS backup health+isolated restore với S3 manifests/latest deletion ledger, target RPO24h/RTO4h có số đo.
- Terraform plan, OIDC negatives, signed image, deploy/rollback receipt.
- Demo operator/known issues/maintenance window được công bố; không 24/7/SLA.

## 5. Inputs còn cần, không đổi kiến trúc

Account/approved region, domain/DNS control, allowed existing VPC/resource IDs, budget caps, IAM approval, model ID/connection secret refs, allowed data residency và demo operator/contact. Nếu thiếu thì block apply/deploy/live model lane; local coding vẫn tiếp tục với fixtures. Không gửi credentials vào chat hoặc baseline files.

Exact versions/digests ở config/versions.lock.yaml do M0 compatibility tests tạo; account secrets ở Secrets Manager. Mọi binding phải qua config schema validation, không defaults giả.

## 6. FUTURE scale

EKS/Helm/managed Redis/RDS Multi-AZ/multiple pools/GitOps là release riêng sau capacity evidence. Giữ Terraform module boundaries, stateless API và job launcher/storage/provider ports để chuyển. GitHub Actions có thể tiếp tục dùng khi scale; Jenkins/Argo chỉ khi có nhu cầu, không bắt buộc dựng ngay. Airflow chuyển executor sau conformance, core vẫn owns execution/evidence. Không tạo các stacks FUTURE trong R1 chỉ để đầy thư mục.
