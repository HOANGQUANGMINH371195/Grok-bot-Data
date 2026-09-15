## **Bản đồ chương**

| \# | Chương | Bạn cần lấy được gì |
| :---- | :---- | :---- |
| 1 | VDaAgent là sản phẩm gì? | Hiểu vấn đề, giá trị và phạm vi. |
| 2 | Ai sử dụng hệ thống? | Nhận diện persona và quyền lợi/trách nhiệm. |
| 3 | Bản đồ capability | Nhìn sản phẩm theo các khối chức năng. |
| 4 | Luồng end-to-end | Theo dõi dataset từ upload đến report. |
| 5 | Workspace & onboarding | Hiểu tenant, membership và context. |
| 6 | Ingestion | Hiểu dataset, artifact, version và trạng thái. |
| 7 | Profiling | Hiểu dữ liệu được đo và mô tả thế nào. |
| 8 | Metadata & HITL | Hiểu AI đề xuất nhưng người quyết định ở đâu. |
| 9 | Analysis Session | Hiểu phiên phân tích và context version. |
| 10 | Preview vs Official | Phân biệt khám phá nhanh và bằng chứng chính thức. |
| 11 | QA & insight | Hiểu cách user hỏi và nhận câu trả lời grounded. |
| 12 | Chart & visualization | Hiểu chart plan, execution và limitation. |
| 13 | Drift & statistical test | Hiểu use case so sánh và kiểm định. |
| 14 | Report lifecycle | Hiểu draft → submit → review → publish. |
| 15 | Evidence & lineage | Hiểu “tại sao tin được” từ góc nhìn người dùng. |
| 16 | Failure & recovery UX | Hiểu lỗi, retry và trạng thái dài. |
| 17 | Workshop scenarios | Áp dụng vào hai tình huống cụ thể. |
| 18 | Checklist & glossary | Chuẩn bị cho buổi thảo luận. |

# **1\. VDaAgent là sản phẩm gì?**

VDaAgent là một nền tảng phân tích dữ liệu có hỗ trợ agent, được thiết kế để đưa Analyst từ dữ liệu dạng bảng đến profile, phân tích, câu trả lời và báo cáo có thể kiểm chứng. Điểm phân biệt quan trọng không phải “chat với dữ liệu”, mà là khả năng gắn mọi kết luận định lượng với compute, tool, retrieval hoặc Official execution đã lưu. Đây là nguyên tắc evidence-first xuất hiện xuyên suốt tài liệu kiến trúc hiện trạng.

## **Bài toán người dùng**

· Dữ liệu thô thường có schema khó hiểu, missing value, duplicate, outlier, PII và semantic type chưa rõ.

· Analyst tốn thời gian viết query lặp lại, kiểm tra chất lượng dữ liệu và tạo chart/report thủ công.

· LLM có thể giải thích tốt nhưng dễ tạo con số không có nguồn, làm giảm niềm tin và tăng rủi ro quyết định sai.

· Một nhóm nhiều người cần cùng nhìn vào đúng phiên bản dữ liệu và biết kết quả nào chỉ là khám phá, kết quả nào đủ chuẩn để đưa vào báo cáo.

## **Giá trị sản phẩm**

| Nhu cầu | VDaAgent hỗ trợ | Điều kiện để đáng tin |
| :---- | :---- | :---- |
| Hiểu nhanh dataset | Profiling \+ metadata proposal | Bind đúng ArtifactVersion; metrics deterministic |
| Khám phá câu hỏi | Preview \+ chart \+ QA | Có limitation rõ; không giả thành Official |
| Ra số liệu dùng được | Official execution \+ tools | Full-source trong giới hạn; có result hash/evidence |
| Tạo báo cáo | Report Draft \+ snapshot \+ workflow | Review/publish tách vai trò; provenance giữ nguyên |

# **2\. Persona: ai dùng VDaAgent và họ cần gì?**

| Persona | Mục tiêu chính | Hành động điển hình | Rủi ro cần bảo vệ |
| :---- | :---- | :---- | :---- |
| Analyst | Hiểu dữ liệu, trả lời câu hỏi, tạo insight | Upload/import, profile, chart, QA, draft report | Sai số liệu; chọn nhầm version; lộ PII |
| Data Engineer | Đảm bảo dữ liệu và lineage đúng | Kiểm ingestion, quality, schema, rerun | Silent corruption; job lỗi; drift không comparable |
| Owner/Admin | Quản trị workspace và publish | Membership, review, approve, publish | Privilege escalation; tự duyệt; cross-tenant access |
| Reviewer/Manager | Đọc và phê duyệt đầu ra | Review snapshot, evidence, limitation | Đọc Preview như Official; thiếu provenance |

# **3\. Bản đồ capability: nhìn sản phẩm như một hệ thống**&nbsp;

| Khối | Capability cốt lõi | Output quan trọng |
| :---- | :---- | :---- |
| Workspace & Access | login, membership, capability, workspace context | actor \+ workspace \+ authorization decision |
| Data Foundation | dataset, artifact, immutable version, storage | ArtifactRef \+ integrity status |
| Analytics | profile, Preview, Official, drift/test | metrics/result \+ limitations \+ hashes |
| Agent Experience | router, tools, retrieval, answer | AnswerEnvelope \+ citations/evidence |
| Governance | HITL, audit, report review/publish | review decision \+ immutable snapshot |

# **4\. User Flow end-to-end**

![][image1]

# **5\. Workspace, identity và onboarding**

| Browser → Bearer token \+ X-Workspace-IdFastAPI → verify JWT → resolve active membership → capabilities → workspace-scoped queryResponse → X-Correlation-Id |
| :---- |

## **User thấy gì khi vừa vào workspace**

* &nbsp;Workspace đang hoạt động và cách đổi workspace.  
* Quyền hiện tại: Viewer/Editor/Owne.  
* Nguồn dữ liệu nào user được phép nhập và giới hạn file.  
* Trạng thái trial/guest nếu có; production không được để guest thành đường tắt authorization.  
* Các thao tác nhạy cảm như Official, review/publish phải hiển thị rõ điều kiện.

# **6\. Ingestion: dataset, artifact và version**

| Khái niệm | Ý nghĩa | Không nên làm |
| :---- | :---- | :---- |
| Dataset | Tên/nhóm dữ liệu logic qua thời gian | Dùng dataset\_id như thể nó chỉ có một file |
| ArtifactVersion | Object bất biến, gắn SHA-256/size/type | Ghi đè object cũ mà vẫn giữ version |
| Ingestion source | Upload, Google Drive... | Coi source bên ngoài là canonical sau khi import |
| Integrity status | uploaded\_unverified → ready/rejected | Cho profiling chạy trước khi xác minh |

## **State machine đề xuất**

| reserved → uploading → uploaded\_unverified → scanning → ready                                      ↘ rejected / quarantined |
| :---- |

# **7\. Profiling: hệ thống “đọc hiểu” dữ liệu như thế nào?**

Profiling là lớp tạo hiểu biết định lượng ban đầu về dataset. Nó nên ưu tiên deterministic compute: schema, row/column count, missing, cardinality, uniqueness, duplicate, distribution, outlier, correlation và các chỉ báo PII/quasi-identifier/candidate key. LLM có thể hỗ trợ semantic type hoặc mô tả, nhưng không nên tự phát minh metric.

| Nhóm metric | Ví dụ | Dùng để làm gì |
| :---- | :---- | :---- |
| Structure | row count, column type, nullability | biết kích thước và schema |
| Quality | missing %, duplicate %, invalid values | xác định độ sạch |
| Distribution | min/max/quantile, histogram, top categories | hiểu hình dạng dữ liệu |
| Relationship | correlation, candidate key | tìm quan hệ và định danh |
| Privacy | PII/quasi-identifier signal | kích hoạt review/policy |

# **8\. Metadata và Human-in-the-loop**

Metadata là lớp giúp con người và agent hiểu ý nghĩa cột, không chỉ kiểu dữ liệu. Ví dụ: một cột số có thể là revenue, id, age hoặc latitude. Hệ thống có thể đề xuất semantic type, PII, candidate key và mô tả; nhưng những đề xuất rủi ro cao cần được người dùng review theo policy.

| Loại metadata | AI có thể đề xuất? | Có thể auto-accept? | Lý do |
| :---- | :---- | :---- | :---- |
| Description/semantic label | Có | Có thể, nếu confidence cao | Tác động thấp hơn |
| PII classification | Có | Thận trọng | Sai có thể gây rò rỉ |
| Candidate key | Có | Thường cần review | Ảnh hưởng join/lineage |
| Business definition | Có hỗ trợ | Cần owner/domain confirm | AI không phải source of truth |

# **9\. Analysis Session và context version**

Sau profiling, user thường thực hiện nhiều thao tác liên tiếp: chọn cột, filter, chart, câu hỏi, test. Analysis Session giúp gom chúng vào một context có version, thay vì mỗi request tự đoán “user đang nói về cái gì”.

| AnalysisSession  profile\_run\_id  selected\_columns  filters / time range  context\_version  quality\_gate\_status  created\_by / workspace\_id |
| :---- |

## **Tại sao context cần version?**

· Một Preview tạo ở context v3 không nên được promote khi user đã đổi filter ở v5 mà không rerun.

· Evidence cần chỉ ra điều kiện phân tích cụ thể, không chỉ dataset chung chung.

· Optimistic UI có thể thay đổi nhanh; backend cần canonical version để chống race condition.

· Report pin một kết quả phải biết kết quả đó được tạo trong context nào.

| Mental model — Session là “bối cảnh phân tích có version”, không phải “chat session” đơn thuần. |
| :---- |

# **10\. Preview và Official: hai mức độ cam kết khác nhau**

| Tiêu chí | Preview | Official |
| :---- | :---- | :---- |
| Mục đích | Khám phá nhanh | Kết quả có thể dùng làm bằng chứng |
| Nguồn | Có thể bounded/sample | Full-source trong giới hạn |
| Tốc độ | Ưu tiên nhanh | Ưu tiên reproducible/correct |
| Expiry | Có thể expire | Lưu provenance durable |
| Report quantitative | Không tự mặc định | Có thể pin nếu qua gate |
| UX label | Phải thấy rõ “Preview” | Phải thấy rõ “Official/Verified” |

Snapshot dự án nêu một gap quan trọng: generic execution-context approval và Preview promotion chưa thống nhất hoàn toàn. Đây là chủ đề cần team quyết định sớm vì ảnh hưởng API, UX, evidence và test.

## **Dễ hiểu sai ở điểm nào?**

· “Preview đúng một lần thì có thể lưu làm Official” — không; Official nên rerun theo contract.

· “Official nghĩa là không bao giờ sai” — không; nó vẫn có limitation, chỉ khác ở provenance và quality gate.

# **11\. QA & Insight: trải nghiệm hỏi dữ liệu bằng ngôn ngữ tự nhiên**

| Question → guardrail → router  ├─ blocked → refusal  ├─ ambiguous → clarification  ├─ quantitative → bounded tools / Official evidence  └─ qualitative → scoped retrieval→ evidence validator → answer |
| :---- |

# **12\. Chart & Visualization: từ intent đến biểu đồ có bằng chứng**

Chart Builder không chỉ là thư viện vẽ. Nó là chuỗi: user intent → sanitized chart plan → Preview → optional gate → Official → render. Chart plan nên dùng field/aggregate/filter allow-list, không cho model sinh code plotting hoặc SQL tùy ý.

| Bước | Output | Điều cần kiểm |
| :---- | :---- | :---- |
| Interpret | chart intent | metric/dimension/time scope rõ |
| Plan | structured chart plan | field tồn tại; aggregate hợp lệ |
| Preview | preview result | sample/limit/expiry hiển thị |
| Official | result \+ hash | full-source bounded \+ quality gate |
| Render | visual \+ evidence link | accessible labels \+ source status |

## **Nguyên tắc UX biểu đồ**

· Không dùng chart type “đẹp” nhưng sai semantics.

· Luôn ghi unit, denominator và time range.

· Cho user xem data table hoặc source summary phía sau chart.

· Khi aggregate approximate, hiển thị badge/limitation.

· Mọi chart được pin vào report cần giữ reference tới execution tạo nó.

## **Câu hỏi mang vào buổi thảo luận**

· Những chart type nào đủ cho pilot 5 tuần?

· Ai chịu trách nhiệm validate semantic correctness: frontend, backend hay agent? Câu trả lời nên là phối hợp nhưng authority nằm ở contract/backend.

# **13\. Drift và statistical test**

Drift giúp trả lời “dữ liệu mới khác dữ liệu trước như thế nào”; statistical test giúp kiểm một giả thuyết với phương pháp định lượng. Đây là capability dễ bị lạm dụng nếu hai Profile Run không comparable hoặc model chọn test không phù hợp.

| Use case | Cần input gì | Output cần lưu |
| :---- | :---- | :---- |
| Schema drift | 2 artifact/profile comparable | column add/remove/type changes |
| Distribution drift | same semantic column \+ windows | distance/test statistic \+ threshold |
| Business comparison | metric/dimension/time context | difference \+ denominator \+ limitations |
| Statistical test | hypothesis \+ variables \+ assumptions | test name, statistic, p-value/CI, assumptions |

Snapshot dự án ghi nhận gap: drift chưa ép cùng dataset trong mọi đường đi. Team cần định nghĩa “comparable” rõ: cùng logical dataset? cùng schema? cùng semantic mapping? Nếu không, UX nên block hoặc yêu cầu explicit mapping.

| Không để LLM làm nhà thống kê toàn quyền — Model có thể đề xuất test, nhưng selection/assumptions/compute phải nằm trong bounded catalog và validator. |
| :---- |

## **Câu hỏi mang vào buổi thảo luận**

· “Comparable dataset” trong pilot nên định nghĩa thế nào?

· Khi test assumption không đạt, hệ thống nên fallback sang test nào hay yêu cầu user quyết định?

# **14\. Report lifecycle: từ insight cá nhân đến artifact được duyệt**

Report là nơi nhiều loại output hội tụ: profile metrics, Official chart, verified answer và note thủ công. Vì vậy nó cần lifecycle rõ. Theo snapshot hiện trạng: Draft mutable → snapshot bất biến có SHA-256 → author submit → Owner khác submitter review/approve → Owner publish → export theo đúng published version pointer.

| Draft (mutable, versioned)  ↓ snapshot \+ SHA-256Submit  ↓ reviewer \!= submitterReview / Approve  ↓Publish  ↓Export đúng published version |
| :---- |

## **Vì sao tách snapshot và publish?**

· Snapshot là capture bất biến để review; publish là quyết định governance.

· Sau snapshot, author vẫn có thể tiếp tục sửa draft mới mà không làm thay đổi bản đang review.

· Export phải dùng pointer published thay vì “latest draft”.

· Note thủ công có thể tồn tại nhưng không được nâng cấp thành quantitative evidence.

Một edge case cần quyết định: workspace chỉ có một Owner thì quy tắc reviewer khác submitter có thể làm flow bế tắc. Product policy cần nêu rõ pilot xử lý thế nào thay vì để code tự đoán.

## **Câu hỏi mang vào buổi thảo luận**

· Pilot có bắt buộc maker-checker không?

· Nếu workspace chỉ có một Owner, cho phép exception hay block publish? Ai phê duyệt exception?

# **15\. Evidence & lineage từ góc nhìn người dùng**

Evidence là câu trả lời cho ba câu: “con số này từ đâu?”, “được tính như thế nào?”, “trên phiên bản dữ liệu nào?”. Lineage là đường nối giữa các artifact/run/execution/report. Nếu UI chỉ có citation tên file nhưng không có version/context thì chưa đủ cho phân tích tái lập.

| Thành phần evidence | Ví dụ | Ý nghĩa |
| :---- | :---- | :---- |
| Source identity | artifact\_id \+ version \+ sha256 | đúng byte dữ liệu |
| Execution identity | profile\_run\_id / official\_execution\_id | đúng lần tính |
| Result identity | result\_hash | phát hiện thay đổi |
| Context | filters, time range, context\_version | đúng điều kiện |
| Limitations | approximate, sample, excluded rows | biết giới hạn |
| Actor/audit | created\_by, approved\_by | trách nhiệm và kiểm toán |

## **UX nên “progressive disclosure”**

User bình thường cần một badge \+ nguồn ngắn; reviewer cần mở drawer xem query/aggregate, artifact/version và limitation; engineer cần trace sâu hơn. Không nên bắt mọi persona đọc JSON evidence thô.

## **Câu hỏi mang vào buổi thảo luận**

· Mức evidence tối thiểu hiển thị cạnh mỗi answer/chart là gì?

· Khi evidence hết hạn hoặc artifact bị policy retention xóa, report phải biểu diễn ra sao?

# **16\. Failure & recovery UX: lỗi là một phần của sản phẩm**

VDaAgent có nhiều thao tác bất đồng bộ và phụ thuộc provider. Vì vậy product spec phải mô tả lỗi/khôi phục như first-class flow. Một nút “Retry” không đủ nếu backend không hỗ trợ idempotency và failure classification.

| Tình huống | UX mong muốn | Backend contract |
| :---- | :---- | :---- |
| Upload gián đoạn | resume/retry an toàn | upload session \+ idempotency \+ integrity verify |
| Profile timeout | state rõ, retry có kiểm soát | durable job \+ attempt \+ lease/stale recovery |
| LLM provider lỗi | thông báo/fallback nếu policy cho phép | provider gateway \+ timeout/retry/fallback reason |
| SSE rớt | reconnect từ last event hoặc polling | event id / durable terminal state |
| Official gate fail | nêu lý do \+ cách sửa | typed quality gate errors |
| Evidence thiếu | abstain, không bịa | validator fail closed |
| **Product principle —** Người dùng cần biết “hệ thống đã làm đến đâu” và “retry có tạo side effect không”. Đây là lý do status model và idempotency là yêu cầu sản phẩm, không chỉ backend. |  |  |

## **Câu hỏi mang vào buổi thảo luận**

· Danh sách failure state nào cần mock ngay trong prototype?

· Khi provider fallback sang model khác, user có cần biết không?

# **17\. Hai workshop scenario để cả team cùng đi qua**

## **Scenario A — Sales CSV**

Một Analyst upload sales\_aug.csv có order\_date, region, revenue, customer\_email. Mục tiêu: tìm khu vực giảm doanh thu, tạo chart và publish báo cáo. Team hãy đi tuần tự: artifact/version → profile → PII review → Analysis Session → Preview → Official → QA explanation → report. Với mỗi bước, ghi rõ state, API owner, permission, evidence và failure path.

## **Scenario B — Dataset phiên bản mới**

Tuần sau Analyst import sales\_sep.csv vào cùng logical dataset. Mục tiêu: so sánh drift với tháng 8\. Team phải quyết định hai version comparable không, map schema nếu thay đổi tên cột, chạy drift/test, và đảm bảo report cũ vẫn trỏ về artifact tháng 8 chứ không tự cập nhật.

| Câu hỏi workshop | Scenario A | Scenario B |
| :---- | :---- | :---- |
| Canonical identity là gì? | artifact\_aug \+ profile\_run | artifact\_aug & artifact\_sep |
| Điểm HITL? | PII/candidate key \+ report review | schema/semantic mapping nếu cần |
| Điểm cần Official? | revenue by region | comparison result nếu publish |
| Failure nguy hiểm nhất? | PII leak / wrong metric | compare khác dataset/version |

## **Câu hỏi mang vào buổi thảo luận**

· Mỗi nhóm chọn một scenario và vẽ sequence diagram 10–15 bước.

· Đánh dấu 3 điểm mà model tuyệt đối không được tự quyết.

# **18\. Checklist trước kick-off \+ glossary ngắn**

## **Checklist cá nhân**

· Tôi phân biệt được Dataset, ArtifactVersion và ProfileRun.

· Tôi mô tả được Preview khác Official.

· Tôi biết HITL nằm ở metadata/report và có thể mở rộng theo policy.

· Tôi biết answer/chart muốn “verified” phải có evidence.

· Tôi biết report có lifecycle chứ không chỉ export PDF.

· Tôi có ít nhất 3 câu hỏi cụ thể về scope/UX/policy để mang vào họp.

## **Glossary**

| Thuật ngữ | Định nghĩa ngắn |
| :---- | :---- |
| ArtifactVersion | Snapshot byte bất biến của dữ liệu, có identity/hash. |
| ProfileRun | Lần profiling bind vào đúng artifact. |
| Analysis Session | Bối cảnh phân tích có version. |
| Preview | Kết quả khám phá nhanh, có thể approximate/expire. |
| Official | Execution được gate và lưu provenance để làm evidence. |
| Evidence | Reference giúp kiểm chứng source/compute/result. |
| HITL | Điểm con người review/confirm theo policy. |
| Lineage | Quan hệ source → run → execution → answer/report. |
| Abstain | Hệ thống từ chối kết luận khi evidence không đủ. |

## **Nguồn tham chiếu chính**

· VDaAgent ARCHITECTURE(1).md — snapshot repository ngày 15/09/2026.

· VDaAgent PROJECT\_DEEP\_RESEARCH\_BRIEF(1).md — current state, gaps và điểm cần quyết định.

· VDaAgent README(1).md — feature/tech stack/API/quickstart hiện tại.

· Supabase Production Checklist — https://supabase.com/docs/guides/deployment/going-into-prod

· PostgreSQL Row Security — https://www.postgresql.org/docs/17/ddl-rowsecurity.html

| Câu hỏi kết thúc — Nếu chỉ nhớ một điều: VDaAgent không cố biến AI thành nguồn sự thật; nó dùng AI để giúp user điều hướng một hệ thống dữ liệu, compute và evidence có kiểm soát. |
| :---- |

&nbsp;

&nbsp;

[image1]: <data:image/png;base64,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>