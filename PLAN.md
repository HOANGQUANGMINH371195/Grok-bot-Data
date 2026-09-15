# PLAN — VDaAgent R1, 30 người, 6 tuần

> Baseline R1-DEMO-2026-09, chốt 15/09/2026: gần30 người, 6 tuần, AWS hiện có và GitHub Actions; **đủ demo trước, scale sau** theo xác nhận mới nhất. [ARCHITECTURE.md](ARCHITECTURE.md) chốt kỹ thuật; [IMPLEMENT.md](IMPLEMENT.md) là execution contract bất biến. Tiến độ/blockers ghi riêng, không tích ô trong IMPLEMENT. Không triển khai HA/Kubernetes/Jenkins/Argo trong R1.

## 1. Sản phẩm sẽ giao là gì?

VDaAgent là web messenger dành cho nhóm làm việc với dữ liệu. Người dùng nói chuyện riêng hoặc trong nhóm có cả người và bot, tải CSV/Parquet, hiểu chất lượng dữ liệu, hỏi bằng ngôn ngữ tự nhiên, tạo biểu đồ và báo cáo có bằng chứng. Người dùng vẫn quyết định việc chia sẻ dữ liệu, xác nhận metadata, chạy Official và review/publish.

Điểm khác một chatbot CSV: mọi con số cần trả lời “từ file/version nào, tính bằng gì/filter nào, giới hạn gì và ai đã duyệt?”. Bot không được tự bịa số hoặc coi một câu trả lời trôi chảy là bằng chứng.

Platform ở đây là core conversation/identity/bot/runtime/memory/tool policy dùng lại được cho domain khác. Bốn bot là cấu hình trên cùng runtime, không bốn ứng dụng hoặc bốn microservices độc lập.

## 2. Đội bot được giao trong R1

| Bot mẫu | Người dùng nhờ việc gì? | Công cụ/quyền riêng |
| --- | --- | --- |
| DataAssistant | Hiểu yêu cầu, hỏi lại, phối hợp đội, tổng hợp câu trả lời có evidence | Đọc nguồn/evidence; subtask, mailbox, handoff; không cần trực tiếp chạy mọi compute |
| DataSteward | Nhập file từ nguồn đã cấp, profile, quality, đề xuất metadata, lịch pipeline | Import/profile/quality; metadata proposal; pipeline/schedule requests |
| DataAnalyst | Lập phép phân tích, Preview, yêu cầu Official, chart, drift và kiểm định | Bounded analysis AST, compute requests, chart/test catalog; không raw SQL/Python |
| ReportWriter | Soạn báo cáo từ kết quả, snapshot, yêu cầu người submit và export | Draft/patch/snapshot, request submit, draft/published export; không approve/publish |

Tối thiểu runtime chạy được một bot. R1 seed bốn templates theo team mode; compact DataAssistant là preset union được human bật rõ ràng. Không bắt buộc cả bốn gọi LLM cho mỗi câu hỏi.

Mỗi bot có identity, instructions/skills versioned, model config, invoke/delegation grants, memory theo conversation, scratchpad, working-file namespace, connection refs, routines và budget. Không bot nào tự đọc raw secret, nâng quyền, tạo DAG/code, gọi Kubernetes hoặc dùng quyền admin của owner.

Có tổng cộng **44 tool IDs v1** trong ARCHITECTURE mục 8.2; mỗi ID phải có schema/handler/permission/effect/test. Các bot dùng chung handler. Profiler, QualityEngine, Evidence Validator, scheduler và Observatory là services; Reviewer là human, không thêm bot để giả làm authority.

Subagents là helper read-only có context/task riêng, không tự là thành viên nhóm. Max 3 parallel, depth1, total8/root task; budget/cancellation chung. Mailbox/handoff chỉ cùng phòng, có correlation/fence/idempotency/hop cap. Tạo bot mới qua human UI, không autonomous spawning.

## 3. Luồng người dùng và ranh giới tin cậy

1. Login qua SSO, chọn workspace/room được phép, thêm bot bằng grants rõ ràng.
2. Upload CSV/flat Parquet hoặc chọn approved S3 source. Xác nhận parse/schema policy; kiểm bytes/version rồi mới ready.
3. DataSteward chạy profile/quality, hiển thị metrics và đề xuất metadata. Human quyết định các nhãn nhạy cảm.
4. DataAnalyst tạo Analysis Session, filter/plan có version; chạy Preview và chart có badge sample/limitations.
5. Muốn số chính thức, human duyệt action gắn đúng plan/source/context/budget; Official chạy lại full source trong giới hạn.
6. DataAssistant trả lời với verified result cells và evidence refs; thiếu chứng cứ thì hỏi hoặc abstain.
7. ReportWriter tạo draft/snapshot. Human submit, Owner khác submitter approve, human publish; exports dùng published pointer.
8. Phiên bản file mới không sửa báo cáo cũ. So sánh same-dataset mapping đã xác nhận để xem drift.
9. Observatory hiển thị bot/subtask/tool/pipeline đang làm gì, context manifest dùng nguồn nào, lỗi/cost và evidence; thao tác recovery phải có quyền.

Tin nhắn người dùng được ACK sau commit dù bot hết quota; UI báo dispatch rejected riêng. PostgreSQL giữ lịch sử/memory/journal; Redis tăng tốc presence/cache/fanout, không tăng model context window. Reconnect phục hồi từ DB, không phụ thuộc Redis giữ mọi event.

Cùng bot ở hai DM và một group không trộn dữ liệu. Bot/tool context chỉ nạp dữ liệu audience đầu ra được phép nhận; không đưa private data vào prompt rồi trông chờ model giữ bí mật. Messenger là mô hình tương tác, R1 không tuyên bố E2EE.

## 4. Scope R1 và phần không làm

| Miền | Bắt buộc trong R1 | Không thuộc R1 |
| --- | --- | --- |
| Messenger | DM/group human+bot, membership/rejoin, mention/reply, attachment, read cursors, typing, reactions, edit/delete/reconnect | Voice/mobile, full-text global inbox/search UX, nested channels |
| Bot/runtime | 4 templates, grants/config, bounded delegation, approvals, cancellation/recovery, memory/summaries | Swarm tự do, cross-room delegation, plugin marketplace, arbitrary tool/code |
| Data foundation | CSV/flat Parquet, S3 approved source, immutable versions, parser policy | Excel/archives/nested Parquet, arbitrary URLs, CDC |
| Profiling/quality | 28 metric families, 8 native quality rules, metadata review | Big-data distributed engines, all-pairs candidate-key search |
| Analysis | Bounded AST, Preview/Official, bar/line/histogram, grounded QA | Joins/UDF/raw SQL, tự chọn thống kê vô giới hạn |
| Drift/statistics | Same-dataset approved mapping, descriptive drift, Welch/chi-square có assumptions | Causal claims, cross-dataset tự ghép |
| Report | Versioned draft/snapshot, maker-checker, publish, HTML/PDF/JSON export | Collaborative rich document editor, auto-publish |
| Observatory | Activity/run explorer, graph/timeline, metadata context inspector, tools/evidence/cost, safe single-run recovery | Raw prompt capture, content bundles, autonomous bulk remediation |
| Data pipeline | Một Airflow DAG template, approved schedule/backfill, OpenLineage exporter | Kafka/Spark/Flink/GX runtime/DataHub/Marquez |
| Operations | AWS single-host Compose, GitHub Actions OIDC, Terraform demo, Ansible bootstrap, backup/restore/telemetry và demo gates | Kubernetes/Jenkins/Argo/HA/24x7, multi-region, full compliance certification |

Default input bounds: 256 MiB/file, 1 triệu rows, 200 columns, decoded bytes<=1 GiB, phải thỏa tất cả. Compute deadline 10 phút; quá budget trả lỗi hoặc yêu cầu thu hẹp, không giả Official bằng sample. Các giới hạn phải được benchmark; acceptance fixtures có pinned hardware/versions.

Không cắt tenant/ACL, source integrity, evidence, human authority hoặc recoverability để kịp demo. Hạng mục không đạt là FAIL/BLOCKED; không tự lén chuyển sang optional.

## 5. Stack đã chốt và vai trò data engineering

| Lớp | Stack R1 |
| --- | --- |
| Web | React, TypeScript, Vite, TanStack Query, Vega-Lite subset |
| Backend | Python 3.13, FastAPI/Pydantic v2, SQLAlchemy/Alembic, REST+WebSocket |
| Runtime/jobs | Python state machine, PostgreSQL job ledger/outbox/fences, separate bot/compute/control workers |
| Data | DuckDB, PyArrow, Parquet, SciPy; native QualityEngine; Jinja2/Playwright export |
| Storage | PostgreSQL 17, Redis-compatible approved deployment, versioned S3-compatible object store |
| AI | Anthropic adapter + deterministic fake provider, shared ModelProvider port; model/cost policy pin |
| Pipeline | Airflow3 trusted DAG template + LocalExecutor parallelism2; separate metadata DB; OpenLineage export |
| Observatory | Product UI/API+journal; OTel/Prometheus/Grafana private, redacted CloudWatch logs; Tempo/Loki/HA FUTURE |
| Infra | AWS EC2+Compose, RDS Single-AZ, S3/ECR/Secrets/Cognito/ALB; Terraform nhỏ+Ansible; GitHub Actions OIDC+SSM deploy |

Airflow điều phối batch import→profile→quality→drift→notify; core giữ grants/executions/evidence. Không chạy bot chat qua scheduler Airflow hoặc để hai scheduler tạo cùng execution. Bot chỉ request template/parameters đã duyệt. Kafka chỉ thêm sau R1 khi có nguồn streaming và offset/window/replay requirements. Không cần thêm công nghệ chỉ vì sản phẩm liên quan data.

Dependency exact versions/digests lock tại M0 qua compatibility tests; không latest hoặc patch đoán. AWS/GitHub Actions đã được user chọn; account/region/domain/model credentials/budget là binding còn cần, không lý do dựng cloud/CI khác. Cloud apply phải được approval riêng; hiện mới chốt tài liệu.

## 6. Phân công đội và ngân sách thời gian

Allocation nominal 30 người; nếu headcount thực tế khác, giữ module owners và cập nhật staffing ngoài IMPLEMENT, không tự đổi scope.

| Nhóm | Người | Ownership |
| --- | --- | --- |
| Leads | 2 | Product/architecture; release/integration, contracts và quyết định go/no-go |
| Web | 5 | Messenger, bots/settings, data/chart/report, Observatory UI, frontend tests |
| Core | 5 | Identity/ACL, messaging/WS, DB/migrations, APIs, audit |
| Runtime | 5 | Model/tools, 4 templates, grants, context, subtask/mailbox, budget/recovery |
| Data | 6 | Ingestion/profile/quality, AST/evidence, drift, report, Airflow/lineage |
| Platform/SRE | 4 | AWS demo/GitHub Actions/IaC, security hardening, telemetry, backup/restore; không build scale ngay |
| QA/Security | 3 | Independent contract/security/load/fault/UAT harnesses và release evidence |

30×6=180 người-tuần danh nghĩa. Dành khoảng 120 cho build/contracts/infra và 60 cho tích hợp, review, sửa lỗi, kiểm chứng/buffer; đây là ngân sách planning, không benchmark năng suất. Testing chạy từ tuần1, không đẩy hết sang QA hay tuần5.

Mỗi module một owner ghi bảng; shared schema/event/tool change có owner và consumer review trước merge. Tối đa một migration owner điều phối thứ tự; feature teams dùng thin vertical slices, daily integration trên main protected. Không có 30 nhánh biệt lập chờ cuối kỳ ghép.

## 7. Mốc 6 tuần và dependency gates

| Mốc | Thời gian | Kết quả nghiệm thu |
| --- | --- | --- |
| M0 | Tuần1 | Frozen baseline/guard, layout/locks/commands/contracts, threat model, fake fixtures, AWS demo bindings và deployment skeleton |
| M1 | Tuần2 | Human+bot chat/reconnect/ACL chạy; upload→immutable artifact→profile có UI; durable job/fence/journal slice |
| M2 | Tuần3 | 4 bots/grants/context/subtask/mailbox/handoff, QA/Preview/chart/evidence; quality/metadata; pipeline request/status và Observatory drilldown |
| M3 | Tuần4 | Official/human approvals/report publish, drift/tests, Airflow end-to-end/OpenLineage, graph/cost/recovery; feature freeze |
| M4 | Tuần5 | Security/tenant negatives, process crash/retry/demo load, restore/deletion replay, cost reconciliation, N/N-1 và rollback |
| M5 | Tuần6 | UAT hai workshop, 4h demo soak, independent security review, known issues, operator guide/evidence và APPROVE_DEMO/NO_GO |

Critical path: shared identity/refs → canonical ingestion/profile → plan/evidence → Official → report governance. Runtime, UI và infra làm song song trên fake contracts rồi tích hợp từng tuần. Airflow gọi core operations đã có, không tự build engine thứ hai.

Checkpoint cuối tuần2 thiếu chat+upload/profile thì leads re-estimate/báo user; cuối tuần4 chưa end-to-end thì không thêm scope. Delay AWS deployment bindings quá ngày2 tuần1 block deploy lane, không block local code. Không dùng cloud khác hoặc public data endpoint để né blocker.


## 8. Curation các repo tham khảo

Bằng chứng Rakazo và quyết định runtime nằm trong [ARCHITECTURE.md](ARCHITECTURE.md); inventory dưới đây là nguồn tham khảo, không phải dependencies phải cài. Nguyên tắc là giữ repo nhỏ, có mục đích; không biến `outsource-sub` thành bãi chứa mọi ý tưởng.

| Repo | Quyết định | Dùng cho |
| --- | --- | --- |
| `outsource-main/rakazo` | GIỮ tham khảo | web/API/worker, auth, persistent job và adapter boundary; Apache-2.0 |
| `outsource-main/grok-bot-0.18-reconstructed` | GIỮ tham khảo | chat UX, router, preload/RPC, streaming, sandbox; license/provenance không phải quyền tái phân phối |
| `outsource-main/recovered-0.47.0` | GIỮ hồ sơ điều tra | contract/protobuf/process boundary; binary không dùng làm source sản phẩm |
| `OpenSandbox` | GIỮ | sandbox lifecycle và SDK; chỉ đưa vào khi có untrusted execution |
| `sqlite-vector` | GIỮ tùy chọn | local/dev retrieval; không bắt buộc production vector DB |
| `zvec` | GIỮ tùy chọn | nghiên cứu vector index; không đưa vào core trước benchmark |
| `archify` | GIỮ tài liệu | render sơ đồ/kiến trúc; không phải runtime dependency |
| `LLMRouter` | GIỮ tham khảo có điều kiện | provider/model routing và usage telemetry; không kéo training/runtime không cần thiết |
| `NVIDIA-NeMo/Switchyard` | GIỮ tham khảo có điều kiện | routing theo capability/cost/quality trong provider gateway; pin version, không dùng standalone server làm production authority |
| `t3code` | GIỮ tham khảo có điều kiện | typed event/remote web control surface; không lấy coding-agent domain |
| `donnemartin/system-design-primer` | THAM KHẢO REMOTE | trade-offs consistency/cache/queue/scaling; áp dụng theo workload, không là dependency |
| `codegraph`, `codepropertygraph`, `joern`, `grit`, `ripwire` | LOẠI KHỎI ACTIVE SET | phân tích mã nguồn hoặc retrieval/security research; không phục vụ profiling bảng cốt lõi |
| `codex`, `codex-multi-auth`, `context-mode`, `opendev`, `orca`, `ruflo` | LOẠI KHỎI ACTIVE SET | agent/CLI/desktop orchestration có thể học contract, nhưng kéo theo scope không cần cho web VDaAgent |
| `icm`, `temp-rs-ddd` | GIỮ tham khảo có điều kiện | memory/FTS và DDD layering; chỉ lấy contract nhỏ, không kéo toàn bộ runtime vào sản phẩm |
| `browser`, `ghostty`, `rtk`, `T3MP3ST`, `product` | LOẠI KHỎI ACTIVE SET | browser/terminal/offensive workflow hoặc report cũ không liên quan; browser/T3MP3ST có license AGPL cần đánh giá riêng nếu sau này tích hợp |

Các mục loại khỏi active set đã được chuyển nguyên trạng tới `/home/minh/projects/grok-bot-reference-archive-20260915` trong lần dọn trước; gồm codegraph có thay đổi cục bộ, product và PLAN.md cũ. Có thể khôi phục; lần viết lại kiến trúc này không dọn thêm repo.


## 9. Tiêu chí bàn giao và trạng thái

Hai workshop phải chạy được: Sales CSV từ upload đến report được người khác duyệt; file tháng kế tiếp từ pipeline đến profile/quality/drift/notification. Mỗi bước có source/version/actor/status/limitations và failure path.

Bắt buộc có evidence theo task ID trong IMPLEMENT: exact commit/config/fixture, command, result, artifact/hash, reviewer. Không ghi PASS vì có skeleton, vì upstream tests pass hoặc vì đọc được tài liệu.

Gate demo: zero known tenant/audience leak; bot không approve/publish; đúng golden fixtures; reboot/retry không duplicate visible effects; context bounded; Observatory đúng ACL; Airflow không bypass core; demo load/soak/restore/rollback có số đo. ARCHITECTURE mục15 là gate demo, mục13.7 là FUTURE scale; chưa có runtime gate nào đã chạy trong lần chốt này.

Bàn giao code, locked dependencies, schemas/migrations, images/manifests, fixtures/tests, runbooks, operator training và signed-off release evidence. GA cần bindings/quota/retention/on-call thật và approvals; 6 tuần kết thúc với NO-GO vẫn phải báo thật nếu chưa đạt.

## 10. Quản lý thay đổi, immutable IMPLEMENT và inputs

IMPLEMENT.md chứa checklist yêu cầu cố định, không file báo tiến độ. Không tick sửa trực tiếp, không reformat/append sau freeze. Progress/receipts/blockers ở docs/execution/ và không được thay nghĩa requirements. ARCHITECTURE/PLAN không được thay scope trái IMPLEMENT; discovery cần thay baseline thì dừng affected item và xin chỉ đạo, không tự coi ADR là giấy phép.

User đã xác nhận AWS+GitHub Actions, demo trước scale sau. Deployment owner cung cấp account/approved region/domain/access/budget/model/secret refs và demo operators; không cần chọn lại cloud/CI. Credentials nằm secret manager, không chat/Git. Data region/cost caps/retention phải có trước live run; demo không hứa24x7 hoặc production SLA.

Đã chốt maker-checker: một Owner có thể draft/export DRAFT nhưng chưa tự approve report mình submit. Tenant/room/resource scopes, report/source deletion và context semantics theo ARCHITECTURE; không để model tự quyết.

## 11. Nguồn và kết luận chốt

Nghiệp vụ gốc: [Team 06 - Data Profiling.md](Team%2006%20-%20Data%20Profiling.md). Rakazo/T3 Code/Switchyard là source tham khảo, không ứng dụng đã chạy. Nguồn chính thức và các trade-offs data/infra được dẫn ngay trong ARCHITECTURE; [infra blueprint](infra/README.md) mô tả ownership và deliverables.

Chốt: đội gần 30 người cho phép R1 rộng hơn pilot 7 người, nhưng không cần Kafka/lakehouse/swarm tùy ý để chứng minh platform. Scope R1 là một sản phẩm data có cộng tác người+bot, tooling/permission/evidence nghiêm túc, Observatory và pipeline/hạ tầng có nghiệm thu. Thành công được quyết định bằng code và evidence, không số trang tài liệu hoặc số công cụ cài đặt.
