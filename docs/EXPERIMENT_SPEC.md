# Đặc tả Kỹ thuật & Kịch bản Thực nghiệm — MongoDB Sharding (Synthea EHR)

> **Mục đích:** Tài liệu chuẩn thống nhất (*Single Source of Truth*) dùng chung cho cả nhóm, quy định rõ kiến trúc hạ tầng, schema dữ liệu, bộ truy vấn, quy trình đo đạc, định dạng file kết quả và tiêu chuẩn hoàn thành cho báo cáo cuối kỳ môn DBMS.

---

## 1. Thông tin Chung & Ràng buộc Học thuật (Project Charter)

- **Tên đề tài:** Phân tích cơ chế và đánh giá thực nghiệm Sharding trên MongoDB với dữ liệu hồ sơ bệnh án điện tử (Synthea EHR, 100K–3M `encounters`).
- **Mốc thời gian bắt buộc:**
  - Nộp báo cáo PDF (`NhomXX_TenDeTai_BaoCao.pdf`) lên SharePoint: **28/11/2026**.
  - Hoàn thành câu hỏi phản biện chéo (4 nhóm phản biện): **29/11/2026**.
  - Thuyết trình: tối đa **15 phút** (10–12 phút trình bày, 2–3 phút hỏi đáp).
- **Phạm vi chốt (đáp ứng trọn vẹn 3 nhận xét của giảng viên):**
  1. **Tách bạch Partitioning vs. Sharding:** Phần 2.1 trình bày rõ *Single-node Partitioning* (trong RDBMS) giải quyết bài toán pruning và quản trị vòng đời dữ liệu trên 1 máy, còn *Multi-node Horizontal Sharding* giải quyết bài toán scale-out vượt trần phần cứng qua nhiều node độc lập. Đề tài đi sâu **100% vào MongoDB Native Sharding**.
  2. **Ánh xạ khái niệm "Partition Pruning":** Vì MongoDB không có declarative table partitioning đơn lẻ kiểu RDBMS, cơ chế tương ứng trong đề tài được định nghĩa và đo lường chính xác là **Shard Pruning / Targeted Routing** (`SINGLE_SHARD` vs `SHARD_MERGE`) của `mongos`.
  3. **Gom gọn phạm vi để đi sâu:** Chốt **1 DBMS (`MongoDB`)**, **1 workload chính (`Synthea EHR`)**, đo đạc ở 4 mốc quy mô **`100K / 500K / 1M / 3M` documents trong collection `encounters`** (**KHÔNG** phải 3M bệnh nhân).

---

## 2. 3 Câu hỏi Nghiên cứu Chuẩn hóa (Research Questions)

| Mã | Trọng tâm | Câu hỏi nghiên cứu chính thức |
| :--- | :--- | :--- |
| **RQ1** | **Scale-out Đọc & Ngưỡng quy mô** | Từ quy mô nào (`100K → 3M encounters`) thì cụm MongoDB Sharded (`SH-hash`) đạt hiệu năng đọc tốt hơn Standalone (`SA`, 1 VM); chi phí điều phối của `mongos` (`B1 - SA`) và lợi ích chia đôi RAM/Index (`B1 - SH-hash`) tách bạch như thế nào dưới tải 1 luồng và đa luồng (`1 / 4 / 8` ở Profile A hoặc `1 / 4 / 16` ở Profile B)? |
| **RQ2** | **Phân bố dữ liệu & Tải ghi khi dữ liệu lệch** | Khi dữ liệu bị lệch (*Natural Skew* và *Heavy Skew*) và tải thiên về ghi, mỗi chiến lược sharding (`SH-hash` vs `SH-range`) phân bố dữ liệu (docs, MB, chunks) và lượng `insert` giữa các shard đều đến mức nào, và write throughput tăng được bao nhiêu so với Standalone? |
| **RQ3** | **Shard Pruning & Chi phí Cross-Shard** | Trên cụm sharded, cơ chế **Shard Pruning** (`SINGLE_SHARD`) khác biệt thế nào với truy vấn xuyên bệnh nhân (`SHARD_MERGE`) về kế hoạch thực thi, băng thông mạng, chi phí cross-shard theo quy mô `100K → 3M` (lấy `SH-range` làm đối chứng cho truy vấn theo thời gian), và mức độ ảnh hưởng chéo khi trộn tải `P:X`? |

---

## 3. Tiêu chuẩn Hạ tầng & Cấu hình Môi trường (Infrastructure Contract)

### 3.1. Bố trí VM trên Azure for Students (Khớp Quota 4–6 vCPU)

> [!IMPORTANT]
> **Ràng buộc thực tế của gói Microsoft Azure for Students (100 USD credit):**
> - Microsoft giới hạn cứng **tổng 4–6 vCPU mỗi region** và **4 vCPU mỗi VM family** (không cho gửi yêu cầu tăng quota). Do đó cấu hình cũ `4 × D2s_v3 (8 vCPU)` trên 1 tài khoản Student sẽ bị từ chối cấp phát.
> - Trước khi tạo VM, **bắt buộc** kiểm tra region được phép trong *Azure Policy → Assignments* và chạy `az vm list-usage --location <region>` để chọn 1 trong 2 Profile chuẩn dưới đây:

#### Profile A — Chuẩn 4 vCPU tổng *(An toàn 100% trên mọi tài khoản Azure Student)*
- **Biến thể 3 VM (khớp đúng 3 VM nhóm đã có):**
  - `vm-coord`: `Standard_B2s` (2 vCPU, 4 GB RAM) — chạy `mongos` + Config Server + `bench.py` (giữ tổng CPU `< 75%`).
  - `vm-w1`, `vm-w2`: `Standard_B1ms` (1 vCPU, 2 GB RAM mỗi VM) — Shard 1 / `SA` và Shard 2.
  - Tổng = **4 vCPU**.
- **Biến thể 4 VM (nếu tách riêng `vm-client`):** `4 × Standard_B1ms` (1 vCPU, 2 GB RAM mỗi VM). Tổng = **4 vCPU**.
- **Tham số MongoDB Profile A:** `wiredTigerCacheSizeGB: 0.75` (768 MB) và systemd `MemoryMax=1.4G` (tránh OOM trên VM 2 GB RAM).
- **Kiểm soát B-series CPU Credit:** Vì `B-series` có cơ chế credit, bắt buộc kiểm tra CPU credit trên **tất cả các VM (`vm-w1`, `vm-w2`, `vm-coord`) `>= 50%`** trước mỗi pha chạy; nếu credit tụt `< 40%`, tạm dừng 10–15 phút để hồi credit rồi mới đo tiếp.

#### Profile B — Tối ưu 6 vCPU tổng *(Ưu tiên nếu region cấp 6 vCPU hoặc ghép 2 tài khoản Azure Student của nhóm)*
- `vm-w1`, `vm-w2` (2 Data Nodes đối xứng): `Standard_D2s_v5` / `D2as_v5` / `D2s_v3` (2 vCPU, 8 GB RAM — **không bị bóp CPU credit**, vừa khít 4/4 vCPU của family D).
- `vm-coord`: `Standard_B1ms` (1 vCPU, 2 GB RAM); `vm-client`: `Standard_B1ms` (1 vCPU, 2 GB RAM). Tổng = **6 vCPU**.
- **Tham số MongoDB Profile B:** `wiredTigerCacheSizeGB: 1.5` và systemd `MemoryMax=3G`.

| Hostname | Vai trò trong cụm Sharded | Vai trò trong `SA` | Yêu cầu kiểm soát |
| :--- | :--- | :--- | :--- |
| `vm-client` *(hoặc dùng chung `vm-coord` ở Profile A 3 VM)* | Chạy `bench.py` (`pymongo` + `multiprocessing`), thu thập CSV & logs | Chạy `bench.py` kết nối trực tiếp tới `vm-w1:27017` | CPU luôn phải **`< 80%`** (hoặc `< 75%` nếu ghép trên `vm-coord`). Nếu vượt ngưỡng, đánh dấu `client_bound: true` trong metadata JSON và loại khỏi phân tích throughput. |
| `vm-coord` | Chạy `mongos` (port `27017`) + Config Server (`--configsvr --replSet cfgRS`, port `27019`) | Tắt / Deallocate | Điểm tiếp nhận kết nối duy nhất của client trong `B1`, `SH-hash`, `SH-range`. |
| `vm-w1` | Chạy Shard 1 (`--shardsvr --replSet shard1RS`, port `27018`) | Chạy `mongod` 1-node replica set (`rs0`, port `27017`); tắt tiến trình shard | Cố định RAM và cache đúng theo Profile A hoặc Profile B. |
| `vm-w2` | Chạy Shard 2 (`--shardsvr --replSet shard2RS`, port `27018`) | Tắt / Deallocate | Chỉ bật ở `SH-hash` và `SH-range`. |

### 3.2. 4 Mã Môi trường Chuẩn (`--env`)

| Mã `env` | Kiến trúc | VM đang bật | Shard Key của `encounters` | Ghi chú triển khai |
| :--- | :--- | :--- | :--- | :--- |
| **`SA`** | Standalone (1-node Replica Set) | `vm-w1`, `vm-client` *(hoặc `vm-coord`)* | Không shard | Client nối trực tiếp `vm-w1:27017`. |
| **`B1`** | Sharded Cluster **1 shard** | `vm-coord`, `vm-w1`, `vm-client` | `{ PATIENT: "hashed" }` | Đi qua `mongos` để tách riêng *coordination overhead*. |
| **`SH-hash`** | Sharded Cluster **2 shards** | Toàn cụm (3 hoặc 4 VM) | `{ PATIENT: "hashed" }` | Khởi tạo với **`numInitialChunks: 16`** để chia đều chunk sẵn giữa 2 shards. |
| **`SH-range`** | Sharded Cluster **2 shards** | Toàn cụm (3 hoặc 4 VM) | `{ START: 1, PATIENT: 1 }` | Không dùng `numInitialChunks`; Balancer tự chia hoặc split khi nạp. |

### 3.3. Tham số MongoDB Cố định trên Mọi Node Dữ liệu

- **Phiên bản DBMS:** Thống nhất một bản duy nhất trên toàn cụm (`MongoDB 7.0` hoặc `8.0 Community`, ghi chính xác version vào `meta/*.json`).
- **Giới hạn bộ nhớ (ép `D3M` vượt cache trên 1 node):**
  - **Profile A:** `storage.wiredTiger.engineConfig.cacheSizeGB: 0.75` + systemd `MemoryMax=1.4G`.
  - **Profile B:** `storage.wiredTiger.engineConfig.cacheSizeGB: 1.5` + systemd `MemoryMax=3G`.
- **Chunk size:** `32` MB (cấu hình trong `config.settings`: `{ _id: "chunksize", value: 32 }`).
- **Collection `patients`:** Luôn shard theo `{ _id: "hashed" }` ở mọi cụm sharded (`B1`, `SH-hash`, `SH-range`); không shard ở `SA`.
- **Consistency Concern:**
  - `writeConcern: { w: "majority" }`
  - `readConcern: { level: "local" }`
  - *Ghi chú bắt buộc trong báo cáo:* Với replica set 1 thành viên trên mỗi shard (hoặc `SA`), `w: "majority"` tương đương `w: 1` về mặt xác nhận ghi, không phát sinh độ trễ đồng bộ replica.
- **Bộ Index đồng nhất (PHẢI tạo sẵn trước mọi bài đo Read và Write):**
  1. `{ PATIENT: 1, START: -1 }`
  2. `{ START: 1 }`
  3. `{ "conditions.CODE": 1, START: 1 }`
  4. `{ ENCOUNTERCLASS: 1, START: 1 }`
  *(Kèm index phục vụ Shard Key tương ứng: `{ PATIENT: "hashed" }` cho `B1`/`SH-hash`, `{ START: 1, PATIENT: 1 }` cho `SH-range`.)*

### 3.4. Dự toán Chi phí & Quản trị Azure Student (Mục tiêu < 5–8 USD / 100 USD credit)

- **Ổ đĩa:** Dùng **Standard SSD** (`E4` 32 GB ~2.4 USD/tháng hoặc `E6` 64 GB ~4.8 USD/tháng) thay cho Premium SSD; tắt Availability Zones (*No infrastructure redundancy required*); chọn *Security type: Standard* nếu SKU cũ báo lỗi Trusted Launch.
- **Chi phí ước tính cho 3–4 giờ chạy trong 3 ngày:**
  - **Profile A:** khoảng **2.5–3.5 USD** (bao gồm compute + Standard SSD + Public IP).
  - **Profile B:** khoảng **4–6 USD**.
- **Cảnh báo rò rỉ tiền sau khi dừng VM:** Azure vẫn tính phí Managed Disk **24/7 ngay cả khi VM đã `Deallocate`**. Sau khi kéo toàn bộ `results/` về máy cá nhân và kiểm tra đủ file, **bắt buộc xóa toàn bộ Resource Group**. Bật **Budget Alert** ở mức 15 USD trên Azure Portal.

### 3.5. Ràng buộc cho Máy Cá nhân (Pha 0 Docker Dry-run & Sinh Synthea)

- **Nguyên tắc an toàn RAM/ổ đĩa trên máy cá nhân:** Tránh chạy đồng thời nhiều tiến trình nặng gây tràn RAM (đặc biệt trên máy không bật Swap hoặc còn dưới 4 GB RAM trống).
- **Pha 0 Docker Compose (4 containers):** Bắt buộc giới hạn `mem_limit: 512m` và `--wiredTigerCacheSizeGB 0.25` cho mỗi container MongoDB (tổng < 1.8 GB RAM) để tránh Linux OOM killer ngắt tiến trình giữa chừng.
- **Sinh dữ liệu Synthea:** Không chạy 1 lệnh sinh 90K bệnh nhân cùng lúc; bắt buộc sinh theo **từng đợt nhỏ (`10,000` bệnh nhân/đợt)** với `Java -Xmx2g`, chuyển đổi streaming sang JSONL tối giản rồi **xóa CSV trung gian ngay** sau mỗi đợt để không tràn RAM/đĩa.

---

## 4. Tiêu chuẩn Dữ liệu & Schema Synthea (Data Contract)

### 4.1. Quy tắc Đơn vị, Tối giản Payload & Cảnh báo Dung lượng
- **Đơn vị quy mô:** `D100K`, `D500K`, `D1M`, `D3M` là **số lượng documents trong collection `encounters`** (tương ứng khoảng ~3K / 15K / 30K / 90K bệnh nhân Synthea), **TUYỆT ĐỐI KHÔNG** sinh 3 triệu bệnh nhân.
- **Tối giản Payload cho VM 2 GB RAM & SSD 32–64 GB:** Lược bỏ toàn bộ trường CSV Synthea không phục vụ `Q1–Q4` (chỉ giữ `CODE` trong `conditions`, bỏ `DESCRIPTION`; chỉ giữ `CATEGORY`, `CODE`, `VALUE` trong `observations`, bỏ `UNITS`; lược bỏ `STOP` và `TOTAL_CLAIM_COST`) để giữ `avgObjSize` quanh mức **1–2 KB/doc**. Khi đó `D3M` chỉ tốn khoảng **3–5 GB** (data + index), vừa vượt hẳn cả cache `0.75 GB` lẫn `1.5 GB`, vừa nạp nhanh gấp 2–3 lần và nằm gọn trên Standard SSD 32–64 GB.
- **Kiểm tra sớm:** Ngay sau khi nạp `D100K`, phải ghi nhận `avgObjSize` và tổng dung lượng Data + Index để tính ngoại suy dung lượng `D3M` trước khi nạp lên Azure.

### 4.2. Schema JSON Chuẩn (Tối giản) của Collection `encounters`

Mỗi document là **1 lượt khám (`encounter`)**, nhúng các trường tối thiểu của `conditions` và `observations` phát sinh trong chính lượt khám đó:

```json
{
  "_id": "enc_uuid_string",
  "PATIENT": "pat_uuid_string",
  "ORGANIZATION": "org_uuid_string",
  "ENCOUNTERCLASS": "ambulatory",
  "START": "2023-05-12T08:30:00Z",
  "conditions": [
    {
      "CODE": "44054006"
    }
  ],
  "observations": [
    {
      "CATEGORY": "laboratory",
      "CODE": "4548-4",
      "VALUE": 6.8
    }
  ]
}
```

*(Lưu ý: `START` lưu ở kiểu `ISODate` / BSON `datetime` trong MongoDB; `observations.VALUE` dạng số thực khi parse được, giữ nguyên string nếu giá trị phi số.)*

### 4.3. Danh sách 6 Bộ Dữ liệu Chuẩn (`--dataset`)

| Mã `dataset` | Số docs `encounters` | Quy tắc sinh & phân bố | Dùng cho |
| :--- | :--- | :--- | :--- |
| **`D100K`** | `100,000` | Trích tập con theo nguyên nhóm `PATIENT` từ tập gốc `D3M` | `RQ1`, `RQ3` (và dry-run Pha 0) |
| **`D500K`** | `500,000` | Tập lồng `D100K ⊂ D500K` (theo `PATIENT`) | `RQ1`, `RQ3` |
| **`D1M`** | `1,000,000` | Tập lồng `D500K ⊂ D1M` (theo `PATIENT`) | `RQ1`, `RQ3` |
| **`D3M`** | `3,000,000` | Tập lồng `D1M ⊂ D3M` (~90K bệnh nhân Synthea) | `RQ1`, `RQ3` |
| **`D1M-nat`** | `1,000,000` | 1M `encounters` giữ nguyên phân phối tự nhiên của Synthea (tương đương hoặc tái dùng danh sách `D1M`) | `RQ2` |
| **`D1M-heavy`** | `1,000,000` | **1% số `PATIENT` chiếm đúng 30% tổng số `encounters` (`300,000` docs)**; tạo bằng cách nhân bản lượt khám của nhóm 1% này kèm đổi `_id` mới và dịch `START` hợp lệ trong khung 3 năm gần nhất | `RQ2` (`R2-4`) |

### 4.4. Quy tắc Cố định Tham số Truy vấn
- **Seed cố định:** `SEED = 42` cho toàn bộ script sinh dữ liệu và sinh chuỗi tham số benchmark.
- **Tệp tham số chuẩn đi kèm mỗi dataset:**
  - `data/<dataset>/patient_ids.txt`: danh sách `PATIENT` ID hợp lệ thuộc dataset đó.
  - `data/<dataset>/query_params.json`: chuỗi tham số đã chọn sẵn theo `SEED = 42` (`pid` ngẫu nhiên đều cho `Q1/Q2`; `d12mAgo`; các cửa sổ `qStart/qEnd` cho `Q3` và `mStart/mEnd` cho `Q4`) để mọi môi trường chạy **cùng một dãy truy vấn giống hệt nhau**.

---

## 5. Tiêu chuẩn Bộ Truy vấn (`Q1`–`Q4` Query Contract)

### 5.1. Định nghĩa Chính xác 4 Truy vấn

```javascript
// Q1: 10 lượt khám gần nhất của 1 bệnh nhân (theo bệnh nhân -> kỳ vọng SINGLE_SHARD trên SH-hash)
db.encounters.find({ PATIENT: pid }).sort({ START: -1 }).limit(10)

// Q2: Xét nghiệm 12 tháng của 1 bệnh nhân (theo bệnh nhân, aggregation -> kỳ vọng SINGLE_SHARD trên SH-hash)
db.encounters.aggregate([
  { $match: { PATIENT: pid, START: { $gte: d12mAgo } } },
  { $unwind: "$observations" },
  { $match: { "observations.CATEGORY": "laboratory" } },
  { $project: { START: 1, "observations.CODE": 1, "observations.VALUE": 1 } }
])

// Q3: Top 10 mã bệnh trong 1 quý (xuyên bệnh nhân, aggregation, kết quả nhỏ -> SHARD_MERGE trên SH-hash)
db.encounters.aggregate([
  { $match: { START: { $gte: qStart, $lt: qEnd } } },
  { $unwind: "$conditions" },
  { $group: { _id: "$conditions.CODE", n: { $sum: 1 } } },
  { $sort: { n: -1 } },
  { $limit: 10 }
])

// Q4: Danh sách lượt khám chẩn đoán tiểu đường type 2 trong 1 tháng (xuyên bệnh nhân, kết quả dài)
db.encounters.find(
  { "conditions.CODE": "44054006", START: { $gte: mStart, $lt: mEnd } },
  { PATIENT: 1, START: 1, ORGANIZATION: 1 }
)
```

### 5.2. Quy tắc Bắt buộc khi Chọn `qStart/qEnd` và `mStart/mEnd` cho `Q3`, `Q4`
- Cửa sổ tháng/quý lấy trong **3 năm gần nhất** của dữ liệu.
- **Kiểm tra ranh giới chunk trên `SH-range` trước khi chạy RQ3:** Phải đọc `sh.status()` của `SH-range` để chọn các khoảng `qStart..qEnd` và `mStart..mEnd` **nằm trọn trong 1 chunk duy nhất** (không vắt ngang mốc split giữa Shard 1 và Shard 2). Nếu không kiểm tra, `SH-range` có thể rơi vào `SHARD_MERGE`, làm hỏng phép đối chứng 1-shard vs 2-shard ở RQ3. Ghi rõ ranh giới chunk đã chọn vào báo cáo.

---

## 6. Quy chuẩn Đo đạc, Telemetry & Định dạng File Kết quả (Measurement & File I/O Contract)

### 6.1. Quy trình & Thời lượng Chuẩn cho Mỗi Lượt Chạy
1. **Tiền kiểm:**
   - Xác minh `sh.isBalancerRunning() == false` và số chunk ổn định (không đổi trong 5 phút).
   - Nếu chạy **Profile A (`B-series`)**, kiểm tra CPU credit còn lại trên mọi VM `>= 50%` (dưới `40%` thì nghỉ 10–15 phút hồi credit).
   - **Tắt Balancer (`sh.stopBalancer()`)** trước mọi kịch bản đo Read (`RQ1`, `RQ3`) và đo OLTP Write (`R2-2`, `R2-3`). *(Chỉ bật Balancer ở pha chờ cân bằng của `R2-1` và `R2-4`).*
2. **Thời lượng từng lượt chạy (tối ưu tổng thời gian Azure xuống ~3.0–4.0 giờ):**
   - **Các bài đo Read (`R1-2`, `R1-3`, `R3-2`, `R3-4`):** Warm-up **10 giây** (không ghi số liệu) → Đo chính thức **30 giây** → Nghỉ **10 giây** (`~50s/lượt`). Lặp **3 lần** (`r1`, `r2`, `r3`).
   - **Các bài đo OLTP Write (`R2-2`, `R2-3`):** Warm-up **10 giây** → Đo chính thức **60 giây** (6 cửa sổ 10 giây) → Nghỉ **15 giây**. Lặp **3 lần** (`r1`, `r2`, `r3`).
   - **Các bài nạp hàng loạt (`R2-1`, `R2-4`):** Chạy **1 lần** (`r1`) để ghi nhận tốc độ nạp + thời gian Balancer ổn định + số lần chunk migration, sau đó **tái sử dụng nguyên trạng cụm dữ liệu đã cân bằng** cho `R2-2` và `R2-3`.
   - **Bài đo Cold Cache (`R1-4`, tùy chọn):** Chỉ chạy nếu còn thời gian sau Pha 4; khởi động lại `mongod` + xóa OS page cache (`sync && echo 3 > /proc/sys/vm/drop_caches`), không warm-up, đo **30 giây** đầu tiên.

### 6.2. Telemetry Thu Song Song
- **Client:** Ghi latency (ms) và số docs trả về của từng truy vấn thành công/thất bại ra CSV.
- **Tài nguyên hệ điều hành trên mọi VM đang bật:** Chạy `sar -u -r -d -n DEV 1` (lấy mẫu 1 giây/lần cho CPU, RAM, Disk I/O, Network) trong đúng khung thời gian đo.
- **Số liệu nội bộ MongoDB trên mọi node (`mongos`, `vm-w1`, `vm-w2`):** Chụp `db.serverStatus()` tại thời điểm bắt đầu và kết thúc lượt đo để tính chênh lệch `opcounters`, `wiredTiger.cache`, và `network.bytesIn / bytesOut`.

### 6.3. Quy ước Đường dẫn & Schema File Kết quả (Bắt buộc)

Mọi output được lưu tập trung dưới thư mục gốc `results/`:

1. **Latency CSV (từng request):**  
   `results/<RQ>/<env>_<dataset>_<scenario>_<query>_t<threads>_r<rep>.csv`  
   *(Ví dụ: `results/RQ1/SH-hash_D1M_R1-3_mix_t16_r1.csv`; với bài chạy đơn lẻ dùng `Q1`, `Q2`, `Q3`, `Q4`, bài trộn dùng `mix` hoặc `mixP90X10`.)*  
   **Header bắt buộc:**
   ```csv
   timestamp_iso,thread_id,query_id,latency_ms,docs_returned,success,error_msg
   ```
2. **System Telemetry CSV (theo VM):**  
   `results/<RQ>/sys/<env>_<dataset>_<scenario>_t<threads>_r<rep>_<hostname>.csv`  
   **Header tối thiểu:** `timestamp_iso,cpu_user,cpu_sys,cpu_iowait,cpu_idle,mem_used_mb,disk_read_kbps,disk_write_kbps,net_rx_kbps,net_tx_kbps`
3. **ServerStatus Delta JSON (theo node MongoDB):**  
   `results/<RQ>/status/<env>_<dataset>_<scenario>_t<threads>_r<rep>_<node>.json`
4. **Shard Distribution Snapshot JSON (cho `R1-1`, `R2-1`, `R2-4`):**  
   `results/<RQ>/dist/<env>_<dataset>_<scenario>_<phase>.json` *(ví dụ `phase = after_load`, `after_balance`)*
5. **Explain Output JSON (cho `R3-1`):**  
   `results/RQ3/explain/<env>_<dataset>_<query>_s<sample>.json` *(với `sample = 1..5`)*
6. **Run Metadata JSON (mỗi lượt chạy bắt buộc có 1 file):**  
   `results/<RQ>/meta/<env>_<dataset>_<scenario>_t<threads>_r<rep>.json`  
   **Trường bắt buộc:** `profile` (`A|B`), `env`, `dataset`, `scenario`, `threads`, `rep`, `seed`, `vm_sku`, `mongo_version`, `wiredtiger_cache_gb`, `client_cpu_max`, `client_bound`, `cpu_credit_min` *(tùy chọn nếu chạy B-series)*, `start_utc`, `end_utc`.

### 6.4. Giao diện CLI Thống nhất của Script Benchmark (`bench.py`)

```bash
python bench.py \
  --profile <A|B> \
  --env <SA|B1|SH-hash|SH-range> \
  --dataset <D100K|D500K|D1M|D3M|D1M-nat|D1M-heavy> \
  --scenario <R1-1|R1-2|R1-3|R1-4|R2-1|R2-2|R2-3|R2-4|R3-1|R3-2|R3-3|R3-4> \
  --query <Q1|Q2|Q3|Q4|mix|all> \
  --threads <1|2|4|8|16> \
  --rep <1|2|3> \
  --seed 42 \
  --output-dir results/<RQ>
```

---

## 7. Ma trận Kịch bản Thực nghiệm Chi tiết

### 7.1. RQ1 — Từ quy mô nào thì Sharding đọc tốt hơn Standalone?

- **Môi trường:** `SA`, `B1`, `SH-hash` | **Bộ dữ liệu:** `D100K`, `D500K`, `D1M`, `D3M` *(R1-3 gọn trên `D100K, D1M, D3M`)* | **Truy vấn:** `Q1`, `Q2`.

| Mã | Kịch bản | Thiết lập chạy | Chỉ số thu thập |
| :--- | :--- | :--- | :--- |
| **`R1-1`** | Kích thước & Tỷ lệ cache | Sau khi nạp từng dataset vào mỗi môi trường (4 dataset × 3 env) | Dung lượng Data, Index trên mỗi node (`collStats`), tỷ lệ `(Data + Index) / cache` (`0.75 GB` cho Profile A, `1.5 GB` cho Profile B). |
| **`R1-2`** | Latency 1 luồng | `Q1` và `Q2` chạy riêng, 1 luồng, **30s đo + 10s warm-up** × 3 reps (3 env × 4 dataset × 2 query × 3 rep = **72 lượt**, ~60 phút) | `p50`, `p95`, `p99` Latency; WiredTiger cache hit ratio; pages read from disk. |
| **`R1-3`** | Quét Concurrency gọn | Trộn `Q1:Q2 = 50:50`, chạy **`1 / 4 / 8` luồng** *(Profile A)* hoặc **`1 / 4 / 16` luồng** *(Profile B)* trên **`D100K, D1M, D3M`**, 30s đo × 3 reps (3 env × 3 dataset × 3 threads × 3 rep = **81 lượt**, ~68 phút) | Throughput (`QPS`), `p95` Latency ở từng mức luồng; điểm bão hòa. |
| **`R1-4`** *(Tùy chọn)* | Cold Cache (`D3M`) | Chỉ chạy nếu còn thời gian; khởi động lại `mongod` + drop OS page cache, chạy `Q1, Q2` ở 1 luồng trong 30s đầu không warm-up | `p95` trong 30 giây đầu trên `SA` vs `SH-hash`. |

- **Công thức phân tích RQ1:**
  - `mongos_overhead = p95(B1) - p95(SA)`
  - `sharding_cache_benefit = p95(B1) - p95(SH-hash)`
  - **Ngưỡng quy mô (*break-even point*):** Mốc dữ liệu nhỏ nhất mà `p95(SH-hash) < p95(SA)` với khoảng tin cậy 95% (95% CI) của hai bên không chồng lấn.

### 7.2. RQ2 — Dữ liệu và tải ghi phân bố đều đến mức nào khi dữ liệu lệch?

- **Môi trường:** `SA`, `SH-hash`, `SH-range` | **Bộ dữ liệu:** `D1M-nat`, `D1M-heavy`.

| Mã | Kịch bản | Thiết lập chạy | Chỉ số thu thập |
| :--- | :--- | :--- | :--- |
| **`R2-1`** | Nạp hàng loạt & Cân bằng | `D1M-nat`, `insert_many` batch `500–1,000` docs, **`ordered=False`**, **2 luồng** *(Profile A)* hoặc **4 luồng** *(Profile B)*, 1 lần/env; sau đó bật Balancer và chờ ổn định (số chunk không đổi 5 phút) | Thời gian nạp (s), Write Throughput (`docs/s`); ảnh chụp `getShardDistribution()` ngay sau nạp và sau cân bằng; thời gian ổn định; số lần chunk migration (`config.changelog`). |
| **`R2-2`** | Ghi OLTP, lệch tự nhiên | Chạy ngay trên dữ liệu đã cân bằng của `R2-1`; insert từng lượt khám mới (`START = now()`) cho `PATIENT` ngẫu nhiên đều, **4 luồng** *(Profile A)* hoặc **8 luồng** *(Profile B)*, **60s** × 3 reps | `inserts/sec`, `p95` insert latency, **`% lượng insert vào mỗi shard` theo cửa sổ 10 giây** (`opcounters.insert`), CPU & Disk I/O từng shard. |
| **`R2-3`** | Ghi OLTP, lệch truy cập nặng | Giống `R2-2`, nhưng chọn `PATIENT` theo **phân phối Zipf ($\theta = 1.2$)**, **4 luồng** *(Profile A)* hoặc **8 luồng** *(Profile B)*, **60s** × 3 reps | Như `R2-2` (đo tác động *hot patient* vs *hot time-range*). |
| **`R2-4`** | Lệch kích thước dữ liệu (`D1M-heavy`) | Nạp `D1M-heavy` (1% `PATIENT` chiếm 30% docs) theo quy trình `R2-1` trên `SH-hash` và `SH-range` (1 lần/env) | **Chỉ số chính:** `max/avg` dung lượng (MB), số docs, số chunks, và `Imbalance (%) = \|S1 - S2\| / Total × 100%`. **Chỉ số phụ:** số `jumbo_chunks` (`config.chunks` có `jumbo: true`, dự kiến có thể bằng `0` do 1% bệnh nhân vẫn nhỏ hơn 32 MB/key). |

- **Công thức phân tích RQ2:**
  - **Độ đều dữ liệu:** `max/avg` của dung lượng (MB) và số documents giữa các shard; `Imbalance (%)`.
  - **Độ đều tải ghi:** Tỷ lệ `% insert` rơi vào shard nhận nhiều nhất qua từng cửa sổ 10s.
  - **Mức tăng throughput:** `write_speedup = inserts_per_sec(SH) / inserts_per_sec(SA)`, báo cáo kèm `inserts/sec/vCPU`.

### 7.3. RQ3 — Truy vấn xuyên shard tốn bao nhiêu, và tăng thế nào theo quy mô?

- **Môi trường:** `SH-hash` (chính), `SH-range` (đối chứng 1-shard cho `Q3/Q4`), `SA` (tham chiếu) | **Bộ dữ liệu:** `D100K`, `D500K`, `D1M`, `D3M`.

| Mã | Kịch bản | Thiết lập chạy | Chỉ số thu thập |
| :--- | :--- | :--- | :--- |
| **`R3-1`** | Giải phẫu `explain` | Sau khi warm cache, chạy `Q1–Q4` kèm `.explain("executionStats")` với 5 bộ tham số khác nhau (trên `SH-hash`; thêm `Q3, Q4` trên `SH-range`) | `winningPlan` (`SINGLE_SHARD` vs `SHARD_MERGE` / `SHARD_MERGE_SORT`), số shard tham gia (tỷ lệ Shard Pruning), `totalKeysExamined`, `totalDocsExamined`, `nReturned`, execution time trên từng shard vs tổng thời gian ở `mongos`. |
| **`R3-2`** | Latency 1 luồng (`Q3, Q4`) | Chạy riêng `Q3` và `Q4` ở 1 luồng (**30s đo + 10s warm-up** × 3 reps) trên `SA`, `SH-hash`, `SH-range` qua 4 datasets *(tái sử dụng `Q1, Q2` từ `R1-2` trên `SA` & `SH-hash`)* | `p50`, `p95`, `p99` Latency cho đầy đủ 4 truy vấn `Q1–Q4`. |
| **`R3-3`** | Lưu lượng mạng | Thu ngay trong quá trình chạy `R3-2` (và `R1-2` cho `Q1, Q2`) từ delta `serverStatus().network.bytesIn/bytesOut` trên `mongos` | Số KB/truy vấn trung bình truyền giữa `mongos` và các shards. |
| **`R3-4`** | Nhiễu chéo khi trộn tải (`P:X`) | Trên `SH-hash` tại **`D1M` và `D3M`**, chạy **4 luồng** *(Profile A)* hoặc **8 luồng** *(Profile B)* (kiểm tra `vm-client`/`vm-coord` CPU < 80%/75%), trộn `P (Q1+Q2) : X (Q3+Q4)` theo 3 tỷ lệ **`100:0` / `90:10` / `70:30`**, **30s đo** × 3 reps | Throughput tổng (`QPS`), **`p95` riêng của nhóm `P`**, và CPU% của `vm-coord (mongos)`, `vm-w1`, `vm-w2`. |

- **Công thức phân tích RQ3:**
  - **Phân rã chi phí cross-shard:** `total_latency ≈ max(shard1_exec_ms, shard2_exec_ms) + (merge_and_network_ms)`.
  - **Hệ số cross-shard:** `cross_shard_factor = p95(Q3/Q4 trên SH-hash) / p95(Q3/Q4 trên SH-range)`. *(Lưu ý phân tích trung thực nếu ở `D3M` xảy ra trường hợp `SH-hash` quét song song 2 shards nhanh hơn 1 shard của `SH-range` — đánh đổi giữa Shard Pruning và Parallel Scan).*
  - **Độ dốc theo quy mô:** Biểu đồ log–log (`100K → 3M`) đối chiếu `Q1, Q2` (gần phẳng) vs `Q3, Q4` (tăng theo dữ liệu).

---

## 8. Thứ tự Thực hiện (Master Runbook) & Tiêu chuẩn Hoàn thành

### 8.1. Lịch trình Chạy 6 Pha (Tổng ~3.0–4.0 giờ Azure; mỗi dataset chỉ nạp 1 lần/cấu hình)

| Pha | Môi trường | Công việc thực hiện | Hạ tầng chạy | Ước tính |
| :--- | :--- | :--- | :--- | :--- |
| **Pha 0** | Cả 4 env (Docker) | Dry-run toàn bộ pipeline với `D100K`, `1 rep` để kiểm tra schema, `explain`, CSV, `sar` (`mem_limit: 512m`) | Máy cá nhân (Docker) | ~30 phút |
| **Pha 1** | `SA` | Nạp lần lượt `D100K → D500K → D1M → D3M`: chạy `R1-1/2/3`, `R3-2 (Q3,Q4)`, và trên `D1M` chạy `R2-1/2/3` | Azure (`vm-w1`, `vm-client`/`vm-coord`) | ~50 phút |
| **Pha 2** | `B1` | Nạp lần lượt `D100K → D500K → D1M → D3M`: chạy `R1-1/2/3` | Azure (`vm-coord`, `vm-w1`, `vm-client`) | ~35 phút |
| **Pha 3** | `SH-hash` | Nạp `D100K → D500K → D1M → D3M`: chạy `R1-1/2/3`, `R3-1/2/3/4`; sau đó chạy `R2-1/2/3` (`D1M-nat`) & `R2-4` (`D1M-heavy`) | Azure (toàn cụm) | ~75 phút *(+ nghỉ hồi credit nếu Profile A)* |
| **Pha 4** | `SH-range` | Nạp `D1M-nat` chạy `R2-1/2/3`, `D1M-heavy` chạy `R2-4`, và chạy `R3-1/2/3 (Q3, Q4)` trên `D100K–D3M` | Azure (toàn cụm) | ~45 phút |
| **Pha 5** | Offline | Kéo toàn bộ `results/` về máy cá nhân, **xóa Resource Group Azure**, gộp CSV, kiểm định `client_bound`, xuất biểu đồ, viết báo cáo | Máy cá nhân | — |

### 8.2. Tiêu chuẩn Hoàn thành theo Hạng mục (Definition of Done)

| Hạng mục | Nội dung thực hiện | Tiêu chí hoàn thành (DoD) |
| :--- | :--- | :--- |
| **1. Hạ tầng & Môi trường** | Kiểm tra `az vm list-usage --location <region>` & region policy; dựng Profile A hoặc B với Standard SSD + Budget Alert 15 USD; cài MongoDB đúng limit (`0.75G/1.4G` hoặc `1.5G/3G`), `chunkSize=32`; viết script chuyển đổi `SA/B1/SH-hash/SH-range` và dọn Resource Group sau Pha 4. | • Đã chạy `az vm list-usage` và ghi rõ chọn Profile A hay B.<br>• File Docker Compose (`mem_limit: 512m`, `--wiredTigerCacheSizeGB 0.25`) cho Pha 0 + script cho Azure.<br>• Đã kiểm tra `sh.status()`, ping nội bộ, `sar` trên các VM, và **xóa Resource Group** ngay sau khi backup `results/`. |
| **2. Chuẩn bị Dữ liệu (Synthea)** | Sinh dữ liệu Synthea theo đợt `10,000` bệnh nhân/lần (`Java -Xmx2g`), chuyển đổi streaming sang JSONL tối giản (xóa CSV trung gian ngay); tạo đủ 6 tập `D100K..D3M`, `D1M-nat`, `D1M-heavy`, kèm `patient_ids.txt` và `query_params.json` (`SEED=42`). | • Đếm đúng số docs từng tập; kiểm chứng `D1M-heavy` có đúng 1% `PATIENT` chiếm 30% docs.<br>• Xác nhận `avgObjSize` của `D100K` ở quanh ~1–2 KB và dự toán dung lượng `D3M` vừa với Standard SSD trước khi nạp lên Azure. |
| **3. Thực thi Benchmark & Telemetry** | Viết `bench.py` theo đúng CLI Contract (Mục 6.4), tích hợp bộ thu `sar` và `serverStatus()`, `explain()` parser; chạy Pha 0 → Pha 4. | • Pha 0 pass 100% không lỗi schema/kết nối.<br>• Đủ toàn bộ CSV/JSON trong `results/` đúng quy ước đặt tên.<br>• Mọi file `meta/*.json` có `client_bound: false` cho các điểm throughput được dùng. |
| **4. Phân tích Số liệu & Biểu đồ** | Tổng hợp `results/`, tính `p50/p95/p99`, 95% CI, bảng phân rã `explain`, các chỉ số RQ1–RQ3; vẽ toàn bộ biểu đồ chuẩn học thuật (PNG 300 DPI + vector PDF). | • Bảng tổng hợp số liệu sạch + các biểu đồ không sai trục/đơn vị (có error bar hoặc 95% CI).<br>• Kiểm tra chéo không có file lỗi hoặc lượt chạy bị `client_bound: true` lọt vào bảng kết quả. |
| **5. Báo cáo PDF & Tài liệu GitHub** | Biên soạn báo cáo PDF theo đúng đề cương Mục 9; đồng bộ mã nguồn, dữ liệu mẫu, CSV thô, script biểu đồ lên GitHub để phục vụ giảng viên và 4 nhóm phản biện. | • File `NhomXX_TenDeTai_BaoCao.pdf` hoàn chỉnh trước hạn **28/11/2026**.<br>• Đường dẫn GitHub/Drive đã mở quyền truy cập công khai/cho giảng viên & 4 nhóm phản biện. |

---

## 9. Cấu trúc Báo cáo Cuối kỳ (Ánh xạ theo Yêu cầu PDF)

- **Phần 1 — Giới thiệu và Cài đặt MongoDB (~20% báo cáo | ~2 phút thuyết trình):**
  - Tổng quan kiến trúc MongoDB liên quan trực tiếp đến đề tài: Storage Engine WiredTiger (Cache & Compression), Replica Set, B-Tree Index, kiến trúc Native Sharding (`mongos`, Config Server, Shard, Chunk, Balancer).
  - Kiến trúc triển khai trên Azure Student (Profile A hoặc Profile B), bảng cấu hình phần cứng & tham số cố định (`wiredTigerCacheSizeGB=0.75`/`MemoryMax=1.4G` hoặc `1.5G`/`3G`, `chunkSize=32MB`), xác minh cụm vận hành *(lệnh cài đặt chi tiết dẫn link sang GitHub)*.
- **Phần 2 — Phân tích Chuyên sâu & Thực nghiệm (~80% báo cáo | ~8–10 phút thuyết trình):**
  - **2.1. Đặt vấn đề & Tách bạch bản chất kỹ thuật:** Bảng phân biệt *Single-node Partitioning* vs *Multi-node Horizontal Sharding*; ánh xạ *Shard Pruning* trong MongoDB.
  - **2.2. Cơ chế hoạt động bên trong MongoDB Sharding:** Cách `mongos` định tuyến (`SINGLE_SHARD` vs `SHARD_MERGE`), sự khác biệt giữa `Hashed` và `Ranged` Shard Key, cơ chế chia chunk và cân bằng tải.
  - **2.3. Thiết kế Thực nghiệm trên Dữ liệu Bệnh nhân (Synthea):** Schema `encounters` nhúng mảng tối giản, 6 bộ dữ liệu `100K–3M` & `D1M-heavy`, 4 truy vấn `Q1–Q4`, quy chuẩn kiểm soát biến (`SA`, `B1`, `SH-hash`, `SH-range`).
  - **2.4. Kết quả Thực nghiệm & Phân tích Kỹ thuật:**
    - *Kết quả RQ1:* Đồ thị `p95` theo quy mô `100K–3M`, tách `mongos overhead` vs `cache benefit`, đường throughput–latency ở `1/4/8` (hoặc `1/4/16`) luồng.
    - *Kết quả RQ2:* Phân bố dữ liệu (*Natural* vs *Heavy Skew*), biểu đồ `% insert/shard` theo cửa sổ 10s, bảng `write_speedup` và `inserts/sec/vCPU`.
    - *Kết quả RQ3:* Bảng giải phẫu `explain` (`SINGLE_SHARD` vs `SHARD_MERGE`), biểu đồ cột chồng phân rã chi phí cross-shard, đồ thị log–log `100K–3M`, biểu đồ nhiễu chéo `P:X` (`100:0 / 90:10 / 70:30`) kèm CPU/Network trên các VM.
  - **2.5. Khuyến nghị Thiết kế & Giới hạn Thực nghiệm (*Threats to Validity*):** Ma trận chọn chiến lược sharding theo workload EHR; phân tích thẳng thắn các giới hạn (1-node replica set mỗi shard, giới hạn RAM nhân tạo theo Profile A/B, dữ liệu giả lập Synthea) để chủ động đón đầu câu hỏi của 4 nhóm phản biện.
- **Tài liệu bổ sung trên GitHub:** Script dựng VM/Docker, pipeline chuyển đổi dữ liệu Synthea, `bench.py`, raw CSV/JSON trong `results/`, notebook phân tích & vẽ biểu đồ, và video demo dự phòng.
