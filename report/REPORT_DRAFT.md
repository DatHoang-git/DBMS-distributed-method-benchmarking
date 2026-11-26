# Phân tích Cơ chế và Đánh giá Thực nghiệm Sharding trên MongoDB với Dữ liệu Hồ sơ Bệnh án Điện tử (Synthea EHR)

> [!NOTE] Mục đích của bản Markdown này
> Đây là bản sao định dạng **Markdown (Obsidian-friendly)** khớp 100% nội dung với bộ mã nguồn LaTeX trong thư mục `report/` (`main.pdf`). Mỗi mục đều ghi chú rõ tên file `.tex` tương ứng để bạn dễ dàng đọc, review, đánh dấu chỉnh sửa và cập nhật ngược lại vào LaTeX.

- **Kho lưu trữ GitHub:** https://github.com/DatHoang-git/DBMS-distributed-method-benchmarking
- **Mẫu LaTeX:** UET-VNU (`report/main.tex` → `report/main.pdf`)

---

## Thông tin Trang bìa (`cover/bia-ngoai.tex`, `cover/bia-trong.tex`)

> [!TODO] Cần điền thông tin hành chính
> - **Nhóm thực hiện:** `[TODO: Nhóm XX]`
> - **Thành viên:** `[TODO: Họ tên & MSSV các thành viên]`
> - **Lớp học phần:** `[TODO: Mã lớp học phần]`
> - **Giảng viên hướng dẫn:** `[TODO: Học vị, Họ và tên GV]`

---

## Tóm tắt (`cover/tom-tat.tex`)

Sự tăng trưởng nhanh chóng của dữ liệu hồ sơ bệnh án điện tử (*Electronic Health Records — EHR*) đặt ra bài toán mở rộng hiệu năng đọc/ghi vượt giới hạn phần cứng của một máy chủ cơ sở dữ liệu đơn lẻ. Đề tài tập trung phân tích cơ chế hoạt động bên trong và đánh giá thực nghiệm chiến lược phân mảnh ngang gốc (*Native Horizontal Sharding*) của MongoDB trên tập dữ liệu tổng hợp Synthea EHR ở bốn mốc quy mô từ $100{,}000$ đến $3{,}000{,}000$ lượt khám (`encounters`).

Báo cáo làm rõ ranh giới kỹ thuật giữa phân vùng đơn nút (*Single-node Partitioning*) trong các hệ quản trị quan hệ và phân mảnh đa nút (*Multi-node Horizontal Sharding*) trong MongoDB, đồng thời ánh xạ cơ chế tỉa phân vùng sang định tuyến mục tiêu (*Shard Pruning / Targeted Routing*) của bộ định tuyến `mongos`. Trên hạ tầng điện toán đám mây Microsoft Azure for Students với bộ nhớ cache WiredTiger được kiểm soát chặt chẽ, hệ thống thực nghiệm đối chiếu bốn cấu hình (`SA`, `B1`, `SH-hash`, `SH-range`) nhằm trả lời ba câu hỏi nghiên cứu: (1) ngưỡng quy mô để cụm sharded vượt qua standalone về độ trễ đọc và tách bạch chi phí điều phối `mongos` với lợi ích chia đôi cache; (2) mức độ đồng đều phân bố dữ liệu và tải ghi giữa chiến lược *Hashed* và *Ranged* khi dữ liệu bị lệch tự nhiên và lệch nặng ($1\%$ bệnh nhân chiếm $30\%$ lượt khám); và (3) chi phí định lượng của truy vấn xuyên shard (`SHARD_MERGE`) cũng như mức độ nhiễu chéo trong tải hỗn hợp.

> [!TODO] Cập nhật sau thực nghiệm
> Bổ sung tóm tắt kết quả định lượng (ngưỡng *break-even*, hệ số `write_speedup`, hệ số `cross_shard_factor`) sau khi hoàn tất chạy benchmark trên cụm Azure.

**Từ khóa:** *MongoDB, Native Sharding, Shard Pruning, WiredTiger, Synthea EHR, Distributed DBMS, Benchmarking.*

---

## Danh mục các từ viết tắt (`cover/viet-tat.tex`)

| Viết tắt | Tiếng Anh | Giải nghĩa |
| :--- | :--- | :--- |
| **BSON** | Binary JSON | Định dạng nhị phân biểu diễn tài liệu trong MongoDB. |
| **CI** | Confidence Interval | Khoảng tin cậy thống kê (mặc định $95\%$ trong báo cáo). |
| **CSRS** | Config Server Replica Set | Cụm máy chủ cấu hình lưu siêu dữ liệu định tuyến của cụm sharded. |
| **DBMS** | Database Management System | Hệ quản trị cơ sở dữ liệu. |
| **EHR** | Electronic Health Record | Hồ sơ bệnh án điện tử. |
| **OLAP** | Online Analytical Processing | Tải truy vấn phân tích, tổng hợp diện rộng. |
| **OLTP** | Online Transaction Processing | Tải giao dịch trực tuyến tốc độ cao, truy cập điểm. |
| **QPS** | Queries Per Second | Thông lượng truy vấn mỗi giây. |
| **RDBMS** | Relational DBMS | Hệ quản trị cơ sở dữ liệu quan hệ. |
| **RQ** | Research Question | Câu hỏi nghiên cứu chuẩn hóa (`RQ1`–`RQ3`). |
| **SA** | Standalone | Môi trường MongoDB chạy đơn nút (1-node replica set). |
| **VM** | Virtual Machine | Máy ảo triển khai trên hạ tầng đám mây Azure. |
| **WT** | WiredTiger | Bộ máy lưu trữ (Storage Engine) mặc định của MongoDB. |

---

# Mở đầu (`chapter/Chap0_MoDau.tex`)

## 1. Bối cảnh và Lý do chọn đề tài

Trong các hệ thống thông tin y tế hiện đại, dữ liệu hồ sơ bệnh án điện tử (*Electronic Health Records — EHR*) có đặc trưng vừa bán cấu trúc (mỗi lượt khám bao gồm danh sách chẩn đoán, chỉ số xét nghiệm, đơn thuốc có số lượng biến thiên lớn), vừa tăng trưởng liên tục theo thời gian và số lượng bệnh nhân. Khi quy mô tập dữ liệu làm việc (*working set*, gồm cả tài liệu và chỉ mục) vượt quá dung lượng bộ nhớ đệm RAM của một máy chủ cơ sở dữ liệu đơn lẻ, hiệu năng hệ thống suy giảm mạnh do tần suất đọc/ghi đĩa tăng đột biến và hiện tượng tranh chấp tài nguyên CPU/I/O.

Mở rộng theo chiều dọc (*scale-up*) sớm chạm trần chi phí và giới hạn phần cứng vật lý. Do đó, mở rộng theo chiều ngang thông qua phân mảnh dữ liệu phân tán (*Horizontal Sharding*) trở thành giải pháp kiến trúc cốt lõi trong các hệ quản trị cơ sở dữ liệu hiện đại [Kleppmann2017]. Tuy nhiên, sharding không phải là giải pháp mang lại lợi ích tuyệt đối ở mọi kịch bản: nó luôn tồn tại sự đánh đổi giữa lợi ích chia tải RAM/I/O trên nhiều nút với chi phí điều phối mạng qua lớp định tuyến, độ lệch phân bố dữ liệu (*data skew*) và chi phí gom kết quả cho các truy vấn xuyên phân mảnh (*scatter-gather / cross-shard*).

MongoDB là một trong những hệ quản trị cơ sở dữ liệu hướng tài liệu phổ biến nhất hỗ trợ cơ chế *Native Horizontal Sharding* tích hợp sẵn [MongoDBSharding]. Việc đánh giá định lượng cơ chế này trên một bài toán dữ liệu sát thực tế như EHR (sử dụng bộ sinh dữ liệu chuẩn Synthea [Walonoski2018]) giúp làm rõ: *khi nào sharding thực sự hiệu quả, chiến lược khóa phân mảnh nào phù hợp với từng loại tải đọc/ghi, và chi phí ẩn của các truy vấn phân tích xuyên shard lớn đến mức nào*.

## 2. Phạm vi nghiên cứu và Câu hỏi nghiên cứu

Nhằm đi sâu vào bản chất kỹ thuật thay vì dàn trải trên nhiều hệ quản trị khác nhau, đề tài chốt phạm vi thực nghiệm tập trung vào **một hệ quản trị duy nhất (`MongoDB`)** và **một bài toán dữ liệu chính (`Synthea EHR`)**, khảo sát trên bốn mốc quy mô từ $100{,}000$ đến $3{,}000{,}000$ tài liệu trong collection `encounters` (tương ứng khoảng $1{,}822$ đến $55{,}448$ bệnh nhân tổng hợp).

| Mã | Trọng tâm | Câu hỏi nghiên cứu chính thức |
| :--- | :--- | :--- |
| **RQ1** | Scale-out Đọc & Ngưỡng quy mô | Từ quy mô nào (`100K → 3M encounters`) thì cụm MongoDB Sharded (`SH-hash`) đạt hiệu năng đọc tốt hơn Standalone (`SA`, 1 VM); chi phí điều phối của `mongos` (`B1 - SA`) và lợi ích chia đôi RAM/Index (`B1 - SH-hash`) tách bạch như thế nào dưới tải 1 luồng và đa luồng? |
| **RQ2** | Phân bố dữ liệu & Tải ghi khi lệch | Khi dữ liệu bị lệch (*Natural Skew* và *Heavy Skew*) và tải thiên về ghi, mỗi chiến lược sharding (`SH-hash` so với `SH-range`) phân bố dữ liệu (số tài liệu, dung lượng MB, số chunk) và lượng `insert` giữa các shard đều đến mức nào, và thông lượng ghi tăng được bao nhiêu so với Standalone? |
| **RQ3** | Shard Pruning & Chi phí Cross-Shard | Trên cụm sharded, cơ chế *Shard Pruning* (`SINGLE_SHARD`) khác biệt thế nào với truy vấn xuyên bệnh nhân (`SHARD_MERGE`) về kế hoạch thực thi, lưu lượng mạng, chi phí cross-shard theo quy mô `100K → 3M` (lấy `SH-range` làm đối chứng cho truy vấn theo thời gian), và mức độ nhiễu chéo khi trộn tải `P:X`? |

## 3. Đóng góp chính của báo cáo

- **Chuẩn hóa khái niệm kiến trúc:** Tách bạch rõ ràng giữa *Single-node Partitioning* trong RDBMS và *Multi-node Horizontal Sharding* trong MongoDB, đồng thời ánh xạ cơ chế tỉa phân vùng (*Partition Pruning*) sang cơ chế định tuyến mục tiêu (*Shard Pruning / Targeted Routing*) của `mongos`.
- **Thiết kế thực nghiệm có kiểm soát biến chặt chẽ:** Xây dựng bốn môi trường đối chứng (`SA`, `B1`, `SH-hash`, `SH-range`) trên hạ tầng Microsoft Azure for Students với giới hạn bộ nhớ WiredTiger cố định, giúp tách riêng chi phí điều phối của `mongos` khỏi lợi ích mở rộng bộ nhớ đệm.
- **Pipeline dữ liệu Synthea và kịch bản đo có thể tái lập:** Chuẩn hóa schema tối giản cho tập `encounters`, sinh sáu bộ dữ liệu chuẩn (`100K → 3M`, `D1M-nat`, `D1M-heavy`) với hạt giống cố định (`SEED = 42`) và công khai toàn bộ mã nguồn trên GitHub [ProjectRepo].
- **Khuyến nghị kiến trúc dựa trên số liệu:** Cung cấp ma trận lựa chọn chiến lược shard key cho các workload EHR thực tế cùng phân tích thẳng thắn các giới hạn thực nghiệm (*Threats to Validity*).

## 4. Bố cục của báo cáo

- *Chương 1. Giới thiệu và Cài đặt MongoDB (~20%):* Kiến trúc lõi MongoDB và cấu hình triển khai cụm trên Azure for Students.
- *Chương 2. Cơ chế Hoạt động của MongoDB Sharding:* Partitioning vs. Sharding, Shard Pruning, định tuyến `mongos`, Hashed vs. Ranged, Chunk & Balancer.
- *Chương 3. Phương pháp và Thiết kế Thực nghiệm:* Schema `encounters`, 6 bộ dữ liệu Synthea, 4 truy vấn `Q1–Q4`, hệ thống chỉ mục, quy chuẩn đo đạc & công thức đánh giá.
- *Chương 4. Kết quả Thực nghiệm và Phân tích Kỹ thuật:* Kết quả định lượng cho `RQ1`, `RQ2`, `RQ3`.
- *Chương 5. Khuyến nghị Thiết kế, Giới hạn và Kết luận:* Ma trận chọn chiến lược sharding, *Threats to Validity* và hướng phát triển.

---

# Chương 1. Giới thiệu và Cài đặt MongoDB (`chapter/Chap1_GioiThieuMongoDB.tex`)

## 1.1. Tổng quan kiến trúc MongoDB liên quan đến đề tài

MongoDB là hệ quản trị cơ sở dữ liệu NoSQL hướng tài liệu (*document-oriented DBMS*), lưu trữ dữ liệu dưới dạng các đối tượng BSON (*Binary JSON*) có cấu trúc linh hoạt và hỗ trợ nhúng mảng/tài liệu con trực tiếp bên trong bản ghi [MongoDBSharding].

### 1.1.1. Bộ máy lưu trữ WiredTiger (Cache và Nén dữ liệu)

Kể từ phiên bản 3.2, **WiredTiger** là bộ máy lưu trữ mặc định của MongoDB [MongoDBWiredTiger]. WiredTiger hỗ trợ kiểm soát đồng thời ở mức tài liệu (*document-level concurrency control*) kết hợp với cơ chế đa phiên bản (*MVCC*), cho phép nhiều luồng ghi đồng thời trên các tài liệu khác nhau trong cùng một collection mà không khóa toàn bộ collection như cơ chế cũ.

Về quản lý bộ nhớ, WiredTiger duy trì một vùng nhớ đệm nội bộ gọi là **WiredTiger Internal Cache** (mặc định bằng $50\%$ dung lượng $\text{RAM} - 1\text{ GB}$), đồng thời tận dụng thêm **Filesystem Cache** của hệ điều hành Linux. Dữ liệu trên đĩa được lưu ở dạng nén khối (mặc định *Snappy* cho collection và nén tiền tố *prefix compression* cho chỉ mục B-Tree), nhưng khi nạp vào WiredTiger Cache sẽ được giải nén sang định dạng bộ nhớ để phục vụ truy cập nhanh. Do đó, khi kích thước *working set* (tài liệu giải nén + chỉ mục) vượt quá giới hạn WiredTiger Cache, hệ thống phải liên tục đẩy trang nhớ ra (*cache eviction*) và đọc trang từ đĩa (*pages read into cache*), trở thành nút thắt cổ chai quyết định điểm hòa vốn (*break-even point*) trong **RQ1**.

### 1.1.2. Chỉ mục B-Tree và Tập bản sao (Replica Set)

MongoDB sử dụng cấu trúc **B-Tree** (biến thể B+Tree trong WiredTiger) cho các chỉ mục đơn trường, chỉ mục phức hợp (*compound index*), chỉ mục đa khóa (*multikey index* trên mảng như `conditions.CODE`) và chỉ mục băm (*hashed index*). Toàn bộ các chỉ mục đang hoạt động cần nằm gọn trong RAM để tránh truy cập đĩa ngẫu nhiên khi tìm kiếm khóa.

**Replica Set** là nhóm các tiến trình `mongod` duy trì cùng một tập dữ liệu nhằm đảm bảo tính sẵn sàng cao (*High Availability*) thông qua một nút chính (*Primary*) nhận thao tác ghi và các nút phụ (*Secondary*) sao chép bất đồng bộ qua `oplog`. Từ MongoDB 4.0 trở đi, ngay cả một shard đơn lẻ hay máy chủ cấu hình trong cụm sharded cũng bắt buộc khởi chạy dưới dạng một Replica Set (tối thiểu 1 thành viên khi triển khai thử nghiệm).

### 1.1.3. Kiến trúc Native Sharding của MongoDB

Một cụm MongoDB Sharded tiêu chuẩn bao gồm ba thành phần phối hợp chặt chẽ [MongoDBSharding]:
- **Shard (`mongod --shardsvr`):** Mỗi shard là một Replica Set độc lập lưu giữ một tập con dữ liệu của toàn cụm.
- **Config Server (`mongod --configsvr`):** Một Replica Set chuyên biệt (`cfgRS`) lưu trữ siêu dữ liệu (*metadata*) của cụm trong cơ sở dữ liệu `config` (`config.chunks`, `config.collections`, `config.settings`, `config.changelog`).
- **Query Router (`mongos`):** Tiến trình trung gian không lưu trữ dữ liệu (*stateless router*) tiếp nhận mọi kết nối từ client, đọc siêu dữ liệu từ Config Server vào bộ nhớ đệm cục bộ, định tuyến truy vấn tới một hoặc nhiều shard và gom kết quả trả về.

Đơn vị phân chia và di chuyển dữ liệu logic là **Chunk** (cố định $32\text{ MB}$ trong đề tài). Tiến trình nền **Balancer** chạy trên nút Primary của Config Server giám sát sự chênh lệch dữ liệu giữa các shard và tự động kích hoạt *chunk migration* khi vượt ngưỡng cân bằng.

## 1.2. Kiến trúc triển khai trên Microsoft Azure for Students

### 1.2.1. Ràng buộc hạn mức và Hai cấu hình triển khai (Profile A và Profile B)

Gói **Microsoft Azure for Students** (\$100 credit) áp đặt giới hạn cứng $4\text{–}6\text{ vCPU}$ mỗi region và tối đa $4\text{ vCPU}$ mỗi VM family [AzureStudents]. Đề tài chuẩn hóa hai cấu hình hạ tầng:

| Tiêu chí | Profile A (4 vCPU tổng) | Profile B (6 vCPU tổng) |
| :--- | :--- | :--- |
| **Phạm vi áp dụng** | An toàn $100\%$ trên mọi tài khoản Azure Student. | Ưu tiên nếu region cấp 6 vCPU hoặc ghép 2 tài khoản. |
| **Nút dữ liệu (`vm-w1`, `vm-w2`)** | $2 \times$ `Standard_B1ms` (1 vCPU, 2 GB RAM/VM). | $2 \times$ `Standard_D2s_v5` / `D2s_v3` (2 vCPU, 8 GB RAM/VM, không giới hạn CPU credit). |
| **Nút điều phối & Client** | Biến thể 3 VM: `vm-coord` dùng `Standard_B2s` (2 vCPU, 4 GB RAM, chạy chung `mongos` + Config Server + `bench.py`); hoặc 4 VM dùng $4 \times$ `B1ms`. | Tách riêng `vm-coord` (`B1ms`) và `vm-client` (`B1ms`). |
| **WiredTiger Cache** | `cacheSizeGB = 0.75` (768 MB) | `cacheSizeGB = 1.5` (1536 MB) |
| **Giới hạn RAM systemd** | `MemoryMax = 1.4G` | `MemoryMax = 3G` |
| **Kiểm soát B-series** | CPU credit $\ge 50\%$ trước mỗi pha; nghỉ 10–15 phút nếu $< 40\%$. | Không bị bóp CPU credit trên hai nút dữ liệu dòng D. |
| **Ổ đĩa lưu trữ** | Standard SSD (`E4` 32 GB hoặc `E6` 64 GB), tắt Availability Zones. | Standard SSD (`E4` 32 GB hoặc `E6` 64 GB), tắt Availability Zones. |

Mức sử dụng CPU của nút chạy `bench.py` luôn phải $< 80\%$ (hoặc $< 75\%$ nếu ghép trên `vm-coord`); mọi lượt đo vượt ngưỡng đều gắn cờ `client_bound: true` và loại khỏi phân tích thông lượng.

### 1.2.2. Vai trò từng nút và Tham số MongoDB cố định

| Hostname | Vai trò trong cụm Sharded (`B1`, `SH-hash`, `SH-range`) | Vai trò trong `SA` |
| :--- | :--- | :--- |
| `vm-client` | Chạy `bench.py` (`pymongo` + `multiprocessing`), thu CSV độ trễ & metadata. | Kết nối trực tiếp tới `vm-w1:27017`. |
| `vm-coord` | Chạy `mongos` (port `27017`) và Config Server (`--configsvr --replSet cfgRS`, port `27019`). | Tắt / Deallocate. |
| `vm-w1` | Chạy Shard 1 (`--shardsvr --replSet shard1RS`, port `27018`). | Chạy `mongod` đơn nút (`rs0`, port `27017`). |
| `vm-w2` | Chạy Shard 2 (`--shardsvr --replSet shard2RS`, port `27018`); chỉ bật ở `SH-hash`, `SH-range`. | Tắt / Deallocate. |

**Tham số MongoDB cố định:**
- **Phiên bản DBMS:** Thống nhất một phiên bản MongoDB Community (`7.0` hoặc `8.0`) trên toàn cụm.
- **Giới hạn bộ nhớ:** `(0.75 GB / 1.4G)` cho Profile A hoặc `(1.5 GB / 3G)` cho Profile B, ép `D3M` (working set $\approx 4.97\text{ GB}$) vượt hẳn cache trên 1 nút.
- **Chunk size:** `32 MB` (`{_id: "chunksize", value: 32}`).
- **Consistency Concern:** `writeConcern: {w: "majority"}` và `readConcern: {level: "local"}` *(lưu ý: với 1-node RS mỗi shard, `w: "majority"` tương đương `w: 1`)*.
- **Collection `patients`:** Luôn shard theo `{_id: "hashed"}` ở mọi cụm sharded; không shard ở `SA`.

## 1.3. Quy trình triển khai, dry-run và xác minh cụm vận hành

- **Pha 0 (Docker Dry-run trên máy cá nhân):** Docker Compose 4 container (`cfgsvr`, `shard1`, `shard2`, `mongos`), giới hạn `mem_limit: 512m` và `--wiredTigerCacheSizeGB 0.25`.
- **Xác minh trên Azure:** (1) `ping` & cổng `27017/27018/27019`; (2) `sh.status()`; (3) `sar` hoạt động trên mọi VM; (4) `sh.isBalancerRunning() == false` trước mọi pha đo Read và OLTP Write. Lệnh cài đặt chi tiết dẫn link sang GitHub [ProjectRepo].

---

# Chương 2. Cơ chế Hoạt động của MongoDB Sharding (`chapter/Chap2_CoCheSharding.tex`)

## 2.1. Đặt vấn đề và Tách bạch bản chất kỹ thuật

### 2.1.1. Single-node Partitioning (RDBMS) và Multi-node Horizontal Sharding

| Khía cạnh | Single-node Partitioning (RDBMS) | Multi-node Horizontal Sharding (MongoDB) |
| :--- | :--- | :--- |
| **Mục tiêu chính** | Giảm không gian quét chỉ mục/bảng trên 1 máy chủ; hỗ trợ quản trị vòng đời dữ liệu (`DROP PARTITION`, lưu trữ phân tầng). | Vượt trần phần cứng (RAM, CPU, Disk I/O) của 1 máy chủ đơn lẻ bằng cách chia tải ra nhiều nút độc lập (*scale-out*). |
| **Phạm vi tài nguyên** | Toàn bộ phân vùng dùng chung CPU, RAM, bộ nhớ đệm và kênh I/O của một nút vật lý. | Mỗi shard sở hữu tiến trình `mongod`, bộ nhớ đệm WiredTiger, CPU và đĩa riêng biệt. |
| **Cơ chế định tuyến** | Bộ tối ưu hóa truy vấn cục bộ (*Query Planner*) loại bỏ phân vùng không khớp ngay trong tiến trình DB. | Tiến trình định tuyến trung gian `mongos` đọc siêu dữ liệu từ Config Server để chuyển tiếp yêu cầu qua mạng tới shard đích. |
| **Chi phí phát sinh** | Chi phí lập kế hoạch thấp; không phát sinh độ trễ mạng giữa các phân vùng. | Phát sinh chi phí mạng qua `mongos`, đồng bộ siêu dữ liệu và gom kết quả xuyên nút khi truy vấn không khớp shard key. |

### 2.1.2. Ánh xạ khái niệm "Partition Pruning" sang Shard Pruning trong MongoDB

- **Targeted Query (`SINGLE_SHARD`):** Điều kiện lọc chứa đầy đủ khóa phân mảnh (hoặc tiền tố phù hợp của khóa Ranged) → `mongos` chỉ gửi truy vấn đến đúng 1 shard đích.
- **Scatter-Gather Query (`SHARD_MERGE` / `SHARD_MERGE_SORT`):** Truy vấn không chứa khóa phân mảnh → `mongos` phát tán đến tất cả các shard, thu thập kết quả trung gian qua mạng, trộn và sắp xếp lại tại `mongos`.

## 2.2. Cơ chế hoạt động bên trong MongoDB Sharding

### 2.2.1. Quy trình định tuyến của `mongos` và Phân rã độ trễ

Với truy vấn xuyên shard (`SHARD_MERGE`), tổng độ trễ bị chi phối bởi nút chậm nhất (*straggler effect*) cộng chi phí mạng và trộn tại `mongos`:

$$T_{\text{total}} \approx \max\big(T_{\text{shard1}},\, T_{\text{shard2}}\big) + T_{\text{network + merge}}$$

*(Lưu ý sự đánh đổi giữa **Shard Pruning** và **Parallel Scan** với các truy vấn phân tích trả về kết quả nhỏ như Top-10).*

### 2.2.2. So sánh chiến lược Hashed Sharding và Ranged Sharding

- **Hashed Sharding (`{PATIENT: "hashed"}`):** Băm 64-bit rải đều tài liệu và lưu lượng ghi mới trên mọi shard (kết hợp `numInitialChunks: 16`). Truy vấn theo `PATIENT` đạt `SINGLE_SHARD`, nhưng truy vấn theo khoảng thời gian `START` hoặc mã bệnh buộc phải chạy `SHARD_MERGE`.
- **Ranged Sharding (`{START: 1, PATIENT: 1}`):** Bảo toàn tính cục bộ theo khoảng thời gian, cho phép *Shard Pruning* (`SINGLE_SHARD`) với truy vấn lọc theo `START` nằm trong 1 chunk. Nhược điểm: cực nhạy cảm với khóa tăng đơn điệu (`START = now()`), làm $100\%$ lưu lượng ghi OLTP dồn vào chunk cuối (`MaxKey`) trên **1 shard duy nhất** (*Write Hotspot*).

### 2.2.3. Cơ chế chia Chunk, Jumbo Chunk và Tiến trình Balancer

- **Chia Chunk (Split):** Khi chunk vượt $32\text{ MB}$, MongoDB tách thành 2 chunk nhỏ hơn (thao tác thuần metadata).
- **Jumbo Chunk:** Nếu toàn bộ tài liệu trong một chunk vượt $32\text{ MB}$ nhưng cùng 1 giá trị khóa phân mảnh (không thể tách) → gắn cờ `jumbo: true` và Balancer không thể di chuyển tự động.
- **Balancer:** Di chuyển chunk nền giữa các shard; trong thực nghiệm được bật ở pha cân bằng của `R2-1`, `R2-4` và tắt hoàn toàn (`sh.stopBalancer()`) trước mọi pha đo Read và OLTP Write.

---

# Chương 3. Phương pháp và Thiết kế Thực nghiệm (`chapter/Chap3_ThietKeThucNghiem.tex`)

## 3.1. Mô hình hóa Dữ liệu và Schema Synthea Tối giản

Mỗi tài liệu trong collection `encounters` biểu diễn **1 lượt khám**, nhúng mảng `conditions` và `observations` đã tối giản (bỏ `DESCRIPTION`, `UNITS`, `STOP`, `TOTAL_CLAIM_COST`):

```json
{
  "_id": "enc_uuid_string",
  "PATIENT": "pat_uuid_string",
  "ORGANIZATION": "org_uuid_string",
  "ENCOUNTERCLASS": "ambulatory",
  "START": "2023-05-12T08:30:00Z",
  "conditions": [
    { "CODE": "44054006" }
  ],
  "observations": [
    { "CATEGORY": "laboratory", "CODE": "4548-4", "VALUE": 6.8 }
  ]
}
```

- Kích thước trung bình thực tế (`D100K`): **$1{,}248.7\text{ B}$ JSON** ($\approx 1{,}366.3\text{ B}$ BSON).
- Ngoại suy cho **`D3M`**: $\approx 3.82\text{ GB}$ BSON giải nén + $1.15\text{ GB}$ index $\approx \mathbf{4.97\text{ GB}}$ *working set* ($\approx 1.91\text{ GB}$ nén WiredTiger trên đĩa) → vượt hẳn cache ở cả Profile A ($0.75\text{ GB}$) và Profile B ($1.5\text{ GB}$).

## 3.2. Đặc tả Sáu Bộ Dữ liệu Chuẩn (Số liệu thật từ `DATASET_SUMMARY.json`)

| Mã dataset | Số `encounters` | Số `PATIENT` | TB khám/BN | TB JSON (B) | Gzip (MB) | Mục đích sử dụng |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| `D100K` | 100,000 | 1,822 | 54.88 | 1,248.7 | 11.44 | `RQ1`, `RQ3`, Pha 0 dry-run |
| `D500K` | 500,000 | 9,202 | 54.34 | 1,272.6 | 70.79 | `RQ1`, `RQ3` |
| `D1M` | 1,000,000 | 18,443 | 54.22 | 1,271.4 | 144.65 | `RQ1`, `RQ3` |
| `D3M` | 3,000,000 | 55,448 | 54.10 | 1,273.6 | 440.78 | `RQ1`, `RQ3` |
| `D1M-nat` | 1,000,000 | 18,443 | 54.22 | 1,271.4 | 144.65 | `RQ2` (Natural Skew, liên kết `D1M`) |
| `D1M-heavy` | 1,000,000 | 13,000 | 76.92 | 1,229.3 | 138.45 | `RQ2` (`R2-4`: $1\%$ BN = 130 BN chiếm $30\%$ = 300K docs) |

Toàn bộ các tập lồng nhau theo nguyên nhóm `PATIENT` (`D100K ⊂ D500K ⊂ D1M ⊂ D3M`), cố định `SEED = 42` kèm `patient_ids.txt` và `query_params.json`.

## 3.3. Bộ Truy vấn Chuẩn hóa (`Q1`–`Q4`) và Hệ thống Chỉ mục

```javascript
// Q1: 10 lượt khám gần nhất của 1 bệnh nhân (OLTP điểm -> SINGLE_SHARD trên SH-hash)
db.encounters.find({ PATIENT: pid }).sort({ START: -1 }).limit(10)

// Q2: Kết quả xét nghiệm 12 tháng của 1 bệnh nhân (Aggregation -> SINGLE_SHARD trên SH-hash)
db.encounters.aggregate([
  { $match: { PATIENT: pid, START: { $gte: d12mAgo } } },
  { $unwind: "$observations" },
  { $match: { "observations.CATEGORY": "laboratory" } },
  { $project: { START: 1, "observations.CODE": 1, "observations.VALUE": 1 } }
])

// Q3: Top 10 mã bệnh trong 1 quý (Xuyên bệnh nhân, kết quả nhỏ -> SHARD_MERGE trên SH-hash)
db.encounters.aggregate([
  { $match: { START: { $gte: qStart, $lt: qEnd } } },
  { $unwind: "$conditions" },
  { $group: { _id: "$conditions.CODE", n: { $sum: 1 } } },
  { $sort: { n: -1 } },
  { $limit: 10 }
])

// Q4: Lượt khám chẩn đoán tiểu đường type 2 trong 1 tháng (Xuyên bệnh nhân, kết quả dài)
db.encounters.find(
  { "conditions.CODE": "44054006", START: { $gte: mStart, $lt: mEnd } },
  { PATIENT: 1, START: 1, ORGANIZATION: 1 }
)
```

- **Quy tắc chọn cửa sổ `Q3/Q4`:** Kiểm tra biên chunk qua `sh.status()` trên `SH-range` để bảo đảm `qStart..qEnd` và `mStart..mEnd` nằm trọn trong **1 chunk duy nhất**.
- **Bộ 4 chỉ mục đồng nhất (tạo sẵn trước mọi bài đo):**
  1. `{PATIENT: 1, START: -1}`
  2. `{START: 1}`
  3. `{"conditions.CODE": 1, START: 1}`
  4. `{ENCOUNTERCLASS: 1, START: 1}`
  *(Kèm index Shard Key tương ứng: `{PATIENT: "hashed"}` cho `B1/SH-hash`, `{START: 1, PATIENT: 1}` cho `SH-range`.)*

## 3.4. Ma trận Môi trường, Quy chuẩn Đo đạc và Công thức Phân tích

### 3.4.1. Bốn môi trường kiểm soát biến

| Mã `env` | Kiến trúc | Shard Key (`encounters`) | Mục đích kiểm soát biến |
| :--- | :--- | :--- | :--- |
| `SA` | Standalone (1-node RS) | Không shard | Baseline không qua `mongos`; client nối thẳng `vm-w1:27017`. |
| `B1` | Sharded 1 shard | `{PATIENT: "hashed"}` | Qua `mongos` nhưng 1 shard → đo riêng *coordination overhead*. |
| `SH-hash` | Sharded 2 shards | `{PATIENT: "hashed"}` | `numInitialChunks: 16`; đánh giá scale-out đọc/ghi và `SHARD_MERGE`. |
| `SH-range` | Sharded 2 shards | `{START: 1, PATIENT: 1}` | Đối chứng cho write hotspot (`RQ2`) và Shard Pruning theo thời gian (`RQ3`). |

### 3.4.2. Quy chuẩn đo & Ma trận 12 kịch bản

- **Read (`R1-2`, `R1-3`, `R3-2`, `R3-4`):** 10s warm-up → 30s đo → 10s nghỉ × 3 reps.
- **OLTP Write (`R2-2`, `R2-3`):** 10s warm-up → 60s đo (6 cửa sổ 10s) → 15s nghỉ × 3 reps.
- **Telemetry song song:** Latency CSV phía client + `sar -u -r -d -n DEV 1` trên mọi VM + delta `db.serverStatus()` trên `mongos`, `vm-w1`, `vm-w2`.

| RQ | Mã | Tên kịch bản | Thiết lập chính & Chỉ số thu thập |
| :--- | :--- | :--- | :--- |
| **RQ1** | `R1-1` | Kích thước & tỷ lệ cache | `collStats` trên 4 datasets × 3 envs; `(Data + Index) / Cache`. |
| **RQ1** | `R1-2` | Latency 1 luồng | `Q1`, `Q2` riêng, 1 luồng (72 lượt); `p50/p95/p99`, cache hit ratio, disk reads. |
| **RQ1** | `R1-3` | Quét Concurrency | Trộn `Q1:Q2 = 50:50` ở 1/4/8 (Profile A) hoặc 1/4/16 luồng (Profile B) trên `D100K, D1M, D3M`. |
| **RQ1** | `R1-4` | Cold Cache (tùy chọn) | `D3M`, restart `mongod` + drop OS page cache, đo 30s đầu không warm-up. |
| **RQ2** | `R2-1` | Nạp hàng loạt & Balancer | `D1M-nat`, `insert_many` batch 500–1000, `ordered=False`; tốc độ nạp, `getShardDistribution()`, chunk migrations. |
| **RQ2** | `R2-2` | Ghi OLTP lệch tự nhiên | Insert mới (`START=now()`), `PATIENT` đều, 4/8 luồng, 60s × 3 reps; `inserts/s`, `% insert/shard` mỗi 10s. |
| **RQ2** | `R2-3` | Ghi OLTP lệch truy cập | Giống `R2-2` nhưng `PATIENT` theo Zipf ($\theta = 1.2$). |
| **RQ2** | `R2-4` | Lệch dữ liệu nặng | Nạp `D1M-heavy` trên `SH-hash` và `SH-range`; `max/avg`, `Imbalance (%)`, `jumbo_chunks`. |
| **RQ3** | `R3-1` | Giải phẫu `explain` | 5 mẫu cho `Q1–Q4`; `winningPlan`, tỷ lệ Shard Pruning, `keys/docsExamined`, exec time từng shard. |
| **RQ3** | `R3-2` | Latency 1 luồng (`Q3, Q4`) | `Q3`, `Q4` trên `SA`, `SH-hash`, `SH-range` qua 4 datasets (ghép cùng `Q1, Q2` từ `R1-2`). |
| **RQ3** | `R3-3` | Lưu lượng mạng | Delta `serverStatus().network.bytesIn/Out` trên `mongos`; KB trung bình/truy vấn. |
| **RQ3** | `R3-4` | Nhiễu chéo tải hỗn hợp | Trên `SH-hash` (`D1M, D3M`), trộn `P:X = 100:0 / 90:10 / 70:30`; QPS tổng, `p95` nhóm `P`, CPU các VM. |

### 3.4.3. Công thức phân tích định lượng

- **RQ1:**
  $$\text{mongos\_overhead} = \text{p95}(\texttt{B1}) - \text{p95}(\texttt{SA}), \qquad \text{sharding\_cache\_benefit} = \text{p95}(\texttt{B1}) - \text{p95}(\texttt{SH-hash})$$
  *Break-even point:* mốc nhỏ nhất có $\text{p95}(\texttt{SH-hash}) < \text{p95}(\texttt{SA})$ với $95\%\text{ CI}$ không chồng lấn.
- **RQ2:**
  $$\text{Imbalance (\%)} = \frac{|S_1 - S_2|}{S_1 + S_2} \times 100\%, \qquad \text{write\_speedup} = \frac{\text{inserts\_per\_sec}(\texttt{SH})}{\text{inserts\_per\_sec}(\texttt{SA})}$$
- **RQ3:**
  $$\text{cross\_shard\_factor} = \frac{\text{p95}(\texttt{Q3/Q4 trên SH-hash})}{\text{p95}(\texttt{Q3/Q4 trên SH-range})}$$

---

# Chương 4. Kết quả Thực nghiệm và Phân tích Kỹ thuật (`chapter/Chap4_KetQuaThucNghiem.tex`)

> [!TODO] Khung chờ kết quả thực nghiệm (Pha 1 → Pha 4 trên Azure)
> Thay thế toàn bộ `--` trong các bảng và chèn các hình vẽ vector PDF sau khi hoàn tất chạy benchmark và kiểm định `client_bound: false`.

## 4.1. Kết quả RQ1: Ngưỡng Quy mô và Hiệu năng Đọc

- **Bảng 4.1 (`R1-1`):** Dung lượng Data/Index trên mỗi nút & tỷ lệ `(Data + Index) / Cache` cho `D100K`, `D500K`, `D1M`, `D3M` (`SA` vs `SH-hash`).
- **Hình 4.1 & Bảng 4.2 (`R1-2`):** Đồ thị `p95` Latency (kèm 95% CI) của `Q1`, `Q2` trên `SA`, `B1`, `SH-hash`; phân rã `mongos_overhead` vs `sharding_cache_benefit`; đánh dấu *break-even point*.
- **Hình 4.2 (`R1-3`):** Đồ thị Throughput (`QPS`) – Latency (`p95`) ở 1/4/8 (hoặc 1/4/16) luồng trên `D100K`, `D1M`, `D3M`.

## 4.2. Kết quả RQ2: Phân bố Dữ liệu và Tải Ghi khi Dữ liệu Lệch

- **Bảng 4.3 (`R2-1`, `R2-4`):** Docs, MB, Chunks trên S1/S2, `max/avg`, `Imbalance (%)`, `jumbo_chunks` cho `D1M-nat` và `D1M-heavy` trên `SH-hash` vs `SH-range`.
- **Hình 4.3 (`R2-2`, `R2-3`):** Biểu đồ `% insert` vào Shard 1 vs Shard 2 theo từng cửa sổ 10s (60s đo) cho Uniform và Zipf ($\theta = 1.2$).
- **Bảng 4.4 (`R2-2`, `R2-3`):** `inserts/s`, `p95` (ms), `write_speedup` và `inserts/s/vCPU` cho `SA`, `SH-hash`, `SH-range`.

## 4.3. Kết quả RQ3: Shard Pruning và Chi phí Truy vấn Xuyên Shard

- **Bảng 4.5 (`R3-1`):** Giải phẫu `explain("executionStats")` (`winningPlan`, Shards tham gia, `KeysExamined`, `DocsExamined`, Exec time) cho `Q1–Q4` (ghi rõ biên chunk `SH-range`).
- **Hình 4.4 & Hình 4.5 (`R3-2`, `R3-3`):** Biểu đồ cột chồng phân rã chi phí cross-shard + lưu lượng mạng (KB/truy vấn); đồ thị log–log `100K → 3M` kèm `cross_shard_factor`.
- **Hình 4.6 (`R3-4`):** Biểu đồ nhiễu chéo `P:X = 100:0 / 90:10 / 70:30` (QPS tổng, `p95` riêng nhóm `P`, CPU% của `vm-coord`, `vm-w1`, `vm-w2` tại `D1M` và `D3M`).

---

# Chương 5. Khuyến nghị Thiết kế, Giới hạn Thực nghiệm và Kết luận (`chapter/Chap5_KhuyenNghiKetLuan.tex`)

## 5.1. Khuyến nghị Thiết kế Sharding cho Hệ thống EHR

| Đặc trưng Workload EHR | Kiến trúc đề xuất | Lý do kỹ thuật & Lưu ý vận hành |
| :--- | :--- | :--- |
| Quy mô nhỏ, *working set* nằm gọn trong WiredTiger Cache 1 nút | **Standalone / Replica Set (`SA`)** | Tránh chi phí mạng/điều phối `mongos` và độ phức tạp quản trị cụm sharded. |
| Thiên về OLTP theo bệnh nhân (`Q1, Q2`) và ghi mới liên tục (`START = now()`) | **Hashed Sharding (`{PATIENT: "hashed"}`)** | Bảo đảm `SINGLE_SHARD` cho truy vấn bệnh nhân và rải đều 50/50 tải ghi, triệt tiêu *write hotspot*. |
| Thiên về báo cáo theo khung thời gian (`Q3, Q4`), ghi theo lô | **Ranged Sharding (`{START: 1, PATIENT: 1}`)** | Tận dụng *Shard Pruning* theo khoảng thời gian; chấp nhận hoặc tách riêng nút thắt ghi tại `MaxKey`. |
| Hỗn hợp OLTP nặng + phân tích xuyên bệnh nhân ($X \ge 10\text{–}30\%$) | **Hashed Sharding + Workload Isolation** | Tránh nhiễu chéo từ `SHARD_MERGE` lên `p95` nhóm `P`; sản xuất nên tách sang Secondary (`readPreference: secondary`) hoặc kho phân tích riêng. |

> [!TODO] Cập nhật định lượng cho Mục 5.1
> Bổ sung mốc *break-even* cụ thể và mức suy giảm `p95` nhóm `P` từ Chương 4 sau khi có số liệu thực.

## 5.2. Giới hạn Thực nghiệm (*Threats to Validity*)

1. **Replica Set 1 thành viên trên mỗi shard (*Internal/Construct Validity*):** Do giới hạn 4–6 vCPU của Azure Student, `w: "majority"` tương đương `w: 1`, không phản ánh độ trễ đồng bộ `oplog` qua mạng tới Secondary. Tuy nhiên bản chất định tuyến `mongos`, chia chunk và khác biệt Hashed/Ranged vẫn giữ nguyên.
2. **Giới hạn cache nhân tạo và cụm 2 shard (*External Validity*):** Thu nhỏ `wiredTigerCacheSizeGB` (`0.75/1.5 GB`) và `chunkSize = 32 MB` để kích hoạt tràn cache ở `3M` docs. Xu hướng định tính khái quát hóa tốt, nhưng trị tuyệt đối (ms) gắn với cấu hình phần cứng thử nghiệm.
3. **Đặc thù VM dòng B-series (nếu chạy Profile A):** Kiểm soát CPU credit $\ge 50\%$ trước mỗi pha, nhưng nhiễu đám mây đa thuê bao có thể ảnh hưởng `p99`; do đó dùng `p95` kèm $95\%\text{ CI}$ qua 3 lần lặp làm chỉ số kết luận chính.
4. **Dữ liệu tổng hợp Synthea và schema tối giản (*Ecological Validity*):** Giữ kích thước tài liệu quanh `1.27 KB` tối ưu cho Standard SSD nhưng nhẹ hơn bệnh án thực tế giàu văn bản tự do.

## 5.3. Kết luận và Hướng phát triển

> [!TODO] Hoàn thiện Mục 5.3
> Sau khi có Chương 4, tổng kết 3 phát hiện định lượng tương ứng `RQ1`, `RQ2`, `RQ3`.

- **Hướng phát triển:** (1) Mở rộng lên 3–4 shard với Replica Set 3 thành viên/shard để đo độ trễ `w: "majority"` và cô lập tải bằng `readPreference: "secondary"`; (2) Khảo sát *Compound Hashed Shard Key* (`{PATIENT: "hashed", START: 1}`) và *Zone Sharding*.

---

# Tài liệu tham khảo (`main.tex`)

1. **[MongoDBSharding]** MongoDB, Inc., *Sharding — MongoDB Manual (v7.0 / v8.0)*. https://www.mongodb.com/docs/manual/sharding/
2. **[MongoDBWiredTiger]** MongoDB, Inc., *WiredTiger Storage Engine — MongoDB Manual*. https://www.mongodb.com/docs/manual/core/wiredtiger/
3. **[MongoDBExplain]** MongoDB, Inc., *Explain Results and Query Plans in Sharded Clusters — MongoDB Manual*. https://www.mongodb.com/docs/manual/reference/explain-results/
4. **[Walonoski2018]** J. Walonoski et al., "Synthea: An approach, method, and software mechanism for generating synthetic patients and the synthetic electronic health care record," *JAMIA*, vol. 25, no. 3, pp. 230–238, 2018.
5. **[Kleppmann2017]** M. Kleppmann, *Designing Data-Intensive Applications*, O'Reilly Media, 2017.
6. **[AzureStudents]** Microsoft Azure, *Azure for Students — Virtual Machine Sizes and Quota Limits*. https://learn.microsoft.com/en-us/azure/virtual-machines/sizes
7. **[ProjectRepo]** Nhóm thực hiện, *DBMS-distributed-method-benchmarking*, GitHub Repository, 2026. https://github.com/DatHoang-git/DBMS-distributed-method-benchmarking
