# Tài liệu Thiết kế Thực nghiệm (Bản Tinh gọn — v3)
**Đề tài:** Phân tích cơ chế và đánh giá thực nghiệm Sharding trên MongoDB 7.0 với dữ liệu hồ sơ bệnh án điện tử (Synthea EHR)

> **Mục tiêu bản tài liệu này:** Gọn, dễ hiểu, dễ triển khai cho cả 3 thành viên và khớp trực tiếp với bài thuyết trình 10–12 phút. Toàn bộ đề tài gồm **3 môi trường**, **3 truy vấn đọc (`Q1`, `Q3`, `Q4`) + 1 tải ghi (`INSERT`)**, và **đúng 3 bảng kết quả chính** (mỗi câu hỏi nghiên cứu 1 bảng).

---

## 1. Tóm tắt 3 Câu hỏi Nghiên cứu

| Câu hỏi | Nội dung ngắn gọn | Bảng đầu ra chính |
| :--- | :--- | :--- |
| **RQ1 — Mở rộng Đọc** | Dữ liệu lớn đến mức nào (`100K → 3M` lượt khám) và mức tải đồng thời nào (`1 / 4 / 8` luồng) thì cụm 2 máy (`SH-hash`) đọc nhanh hơn 1 máy (`SA`)? | **Bảng 1** (`12` dòng × `6` cột) |
| **RQ2 — Phân bố & Ghi mới** | Giữa chia băm theo mã bệnh nhân (`SH-hash`) và chia theo khoảng thời gian (`SH-range`), cách nào phân bố dữ liệu và tải ghi mới đều hơn, và tốc độ ghi có nhanh hơn 1 máy (`SA`) không? | **Bảng 2** (`3` dòng × `5` cột) |
| **RQ3 — Tỉa mảnh & Xuyên mảnh** | Khi truy vấn chỉ hỏi **1/2 máy** (khớp khóa chia) so với phải hỏi **2/2 máy** (không khớp khóa chia), độ trễ `p95` và lưu lượng mạng qua `mongos` khác nhau thế nào (và chi phí xuyên mảnh tăng ra sao từ `100K → 3M`)? | **Bảng 3** (`3` dòng × `6` cột ở `1M`) + 1 biểu đồ độ dốc `100K → 3M` |

---

## 2. Thiết lập Dùng chung (Cố định cho Cả 3 Thực nghiệm)

### 2.1. Ba môi trường triển khai (MongoDB 7.0 Community LTS)
1. **`SA` (1 máy dữ liệu):** 1 nút `mongod` chạy chế độ 1-node Replica Set (`rs0`) trên `vm-w1`; máy test (`vm-client`) nối thẳng tới `vm-w1:27017`. *(Dùng 1-node RS để có ghi `oplog` công bằng với các shard thật.)*
2. **`SH-hash` (2 máy dữ liệu — băm theo bệnh nhân):** `vm-coord` (`mongos` + Config Server `cfgRS`) + `vm-w1` (Shard 1) + `vm-w2` (Shard 2). Chia `encounters` theo `{ PATIENT: "hashed" }` với `numInitialChunks: 16`.
3. **`SH-range` (2 máy dữ liệu — khoảng theo thời gian):** Cùng kiến trúc 2 shard như trên, chia `encounters` theo `{ START: 1, PATIENT: 1 }`.

### 2.2. Các quy tắc kiểm soát biến bắt buộc
- **Giới hạn RAM mỗi máy dữ liệu (`vm-w1`, `vm-w2`):** `wiredTigerCacheSizeGB = 0.50` (512 MB) và systemd `MemoryMax = 1G` — ép máy đơn tràn cả RAM đệm MongoDB lẫn OS Page Cache ở mốc `1M–3M`.
- **Ổ đĩa dữ liệu trên Azure:** Standard SSD `E4` (32 GB), bắt buộc đặt **`Host Caching = None`** (tránh tầng cache ẩn ngoài cgroup).
- **Kích thước chunk (`rangeSize`):** `32 MB` (`config.settings: {_id: "chunksize", value: 32}`). *(Lưu ý MongoDB 7.0: auto-split khi ghi đã bỏ, Balancer cân bằng theo dung lượng và dừng khi chênh lệch `< 3 × 32 = 96 MB`, có AutoMerger nên luôn đo độ đều bằng dung lượng MB từ `getShardDistribution()`.)*
- **Chính sách đọc/ghi:** `writeConcern: { w: "majority" }` và `readConcern: { level: "local" }`.
- **Bộ 3 chỉ mục tạo sẵn giống hệt nhau trên mọi môi trường:**
  1. `{ PATIENT: 1, START: -1 }` *(phục vụ `Q1`)*
  2. `{ START: 1 }` *(phục vụ `Q3`)*
  3. `{ "conditions.CODE": 1, START: 1 }` *(phục vụ `Q4`)*
- **Tắt Balancer trước mọi bài đo đọc và ghi trực tuyến:** chạy `sh.stopBalancer()` và kiểm tra `db.adminCommand("balancerStatus")` có `mode == "off"`, `inBalancerRound == false`, và `config.migrations` rỗng.
- **Chốt an toàn máy sinh tải (`vm-client`):** CPU của `vm-client` phải luôn **`< 75%`**. Kiểm tra ngay ở `D100K` mức `8` luồng; nếu `vm-client` vượt `75%` CPU (ví dụ trên VM 1 vCPU) thì hạ dải luồng xuống **`1 / 2 / 4`** luồng đồng nhất cho toàn bộ TN1.

### 2.3. Dữ liệu & Thứ tự nạp
- **4 mốc lồng nhau theo `PATIENT`:** `D100K` (`100.000` lượt khám / `1.822` BN) $\subset$ `D500K` (`500.000` / `9.202` BN) $\subset$ `D1M` (`1.000.000` / `18.443` BN) $\subset$ `D3M` (`3.000.000` / `55.448` BN).
- **Schema thực tế (9 trường):** `_id`, `PATIENT`, `ORGANIZATION`, `ENCOUNTERCLASS`, `START` (`ISODate`), `STOP` (`ISODate`), `TOTAL_CLAIM_COST`, `conditions` (`[{CODE, DESCRIPTION}]`), `observations` (`[{CATEGORY, CODE, VALUE, UNITS}]`); trung bình ~1.273 B JSON (~1.374 B BSON).
- **Cách nạp:** Dùng bộ dữ liệu đã sắp xếp tăng dần theo `START` trong `data/load_v2/` (`S1` = `100K`, `S2` = `+400K`, `S3` = `+500K`, `S4+S5` = `+2M`) để mô phỏng thứ tự ghi thời gian thực và **nạp nối tiếp 1 lần duy nhất** cho mỗi cấu hình.
- **Lấy mẫu tham số (`SEED = 42`):** Chọn `PATIENT` ngẫu nhiên đều trên **toàn bộ** `patient_ids.txt` của mốc đang đo; mọi môi trường chạy đúng cùng chuỗi tham số.

### 2.4. Ba truy vấn đọc đại diện (`Q1`, `Q3`, `Q4`)
```javascript
// Q1 (Theo 1 bệnh nhân -> dùng cho RQ1 và tái sử dụng cho RQ3):
db.encounters.find(
  { PATIENT: pid },
  { START: 1, ENCOUNTERCLASS: 1, ORGANIZATION: 1, conditions: 1 }
).sort({ START: -1 })

// Q3 (Xuyên bệnh nhân, kết quả NHỎ = 10 dòng -> dùng cho RQ3):
db.encounters.aggregate([
  { $match: { START: { $gte: qStart, $lt: qEnd } } },
  { $unwind: "$conditions" },
  { $group: { _id: "$conditions.CODE", n: { $sum: 1 } } },
  { $sort: { n: -1 } },
  { $limit: 10 }
])

// Q4 (Xuyên bệnh nhân, kết quả LỚN = ~834 dòng/tháng ở 1M -> dùng cho RQ3):
db.encounters.find(
  { "conditions.CODE": "314529007", START: { $gte: mStart, $lt: mEnd } },
  { PATIENT: 1, START: 1, ORGANIZATION: 1 }
)
```

---

## 3. Chi tiết 3 Thực nghiệm & 3 Bảng Kết quả Duy nhất

### Thực nghiệm 1 (`TN1` — RQ1: Mở rộng Đọc theo Quy mô & Số luồng)
- **Môi trường:** `SA` vs `SH-hash` | **Mốc dữ liệu:** `100K`, `500K`, `1M`, `3M` | **Truy vấn:** `Q1`
- **Cách chạy:** Ở mỗi mốc chạy `1`, `4`, `8` luồng *(hoặc `1 / 2 / 4` nếu `vm-client` chạm `> 75%` CPU ở 8 luồng)*. Làm nóng `20–30s` → đo ít nhất `30s` và `≥ 2.000` truy vấn → lặp **3 lần** lấy trung bình. Ghi ngầm `pages_read_into_cache` và `sar` (CPU%, Disk read) để giải thích lý do trong phần phân tích.
- **Lý do chọn chỉ số:** Cặp `p95` (đủ nhạy để bắt tràn RAM/đĩa mà không méo vì nhiễu vặt cloud như `Mean`/`p99`) và `QPS` (đo sức gánh tổng thể đa luồng); không chèn các cột tính lại làm phình bảng.
- **Bảng kết quả 1 (12 dòng):**

| Quy mô | Số luồng | `SA` — `p95` (ms) | `SH-hash` — `p95` (ms) | `SA` — `QPS` | `SH-hash` — `QPS` |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `100K` / `500K` / `1M` / `3M` | `1` / `4` / `8` | `--` | `--` | `--` | `--` |

---

### Thực nghiệm 2 (`TN2` — RQ2: Độ đều Dữ liệu & Tốc độ Ghi mới)
- **Môi trường:** `SA`, `SH-hash`, `SH-range` | **Mốc dữ liệu:** `1M` (`D1M`)
- **Cách chạy:**
  1. Nạp `1M` lượt khám, bật Balancer chờ ổn định, đọc `getShardDistribution()` lấy **% dung lượng MB trên Máy 1 / Máy 2**.
  2. Tắt Balancer; chạy **4 luồng** ghi liên tục lượt khám mới (`START = now()`, `PATIENT` ngẫu nhiên đều) trong **60 giây**, lặp **3 lần**; đọc `opcounters.insert` trên 2 shard để lấy **% lượng ghi vào Máy 1 / Máy 2**, `inserts/s` và `p95`.
- **Bảng kết quả 2 (3 dòng):**

| Cấu hình | Dữ liệu: Máy 1 / Máy 2 (%) | Lượng ghi mới: Máy 1 / Máy 2 (%) | Tốc độ ghi (`inserts/s`) | Độ trễ ghi `p95` (ms) |
| :--- | :---: | :---: | :---: | :---: |
| **`SA`** | `100% / 0%` | `100% / 0%` | `--` | `--` |
| **`SH-hash`** | `--% / --%` | `--% / --%` | `--` | `--` |
| **`SH-range`** | `--% / --%` | `--% / --%` | `--` | `--` |

---

### Thực nghiệm 3 (`TN3` — RQ3: Tỉa mảnh & Chi phí Xuyên mảnh)
- **Môi trường:** `SH-hash` vs `SH-range` tại **`1M`** *(tái dùng ngay cụm của TN2, không cần nạp lại `SH-range`)* | **Truy vấn:** `Q1` *(tái sử dụng từ TN1)*, `Q3`, `Q4`
- **Cách chạy:**
  - Dùng **cùng một bộ cửa sổ thời gian cố định** (12 quý cho `Q3`, 36 tháng cho `Q4` trong 3 năm gần nhất) xoay vòng cho cả `SH-hash` và `SH-range`.
  - Chạy `.explain("executionStats")` ghi **Số máy bị hỏi (`1/2` hay `2/2`)** (lưu ý: `find` đọc `SINGLE_SHARD`/`SHARD_MERGE`; `aggregate` đọc `shards`, `splitPipeline`, `mergeType`).
  - Đo nhanh **`15 giây` lưu lượng mạng lúc rảnh** trên `mongos` để trừ nền (heartbeat/metadata) khi tính `KB/req` từ delta `serverStatus().network`.
  - Chạy 1 luồng đo `p95` (làm nóng 20s → đo ít nhất `30s` và `≥ 300` truy vấn cho `Q3/Q4`, lặp 3 lần).
  - **Đo thêm độ dốc `100K → 3M` trên `SH-hash` (~6 phút, không thêm bảng):** Trong Pha 2 khi `SH-hash` lần lượt đi qua `100K, 500K, 1M, 3M`, chạy thêm `Q3, Q4` (1 luồng) để vẽ **1 biểu đồ đường** đối chiếu tốc độ tăng độ trễ của `Q1` (1 máy) với `Q3, Q4` (2 máy) qua cả 4 mốc.
- **Bảng kết quả 3 (3 dòng tại mốc `1M`):**

| Truy vấn | `SH-hash`: Số máy hỏi | `SH-hash`: `p95` (ms) | `SH-hash`: Mạng (KB/req) | `SH-range`: Số máy hỏi | `SH-range`: `p95` (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`Q1`** *(1 bệnh nhân)* | `-- / 2` | `--` | `--` | `—` | `—` |
| **`Q3`** *(Xuyên BN, KQ nhỏ)* | `-- / 2` | `--` | `--` | `-- / 2` | `--` |
| **`Q4`** *(Xuyên BN, KQ lớn)* | `-- / 2` | `--` | `--` | `-- / 2` | `--` |

---

## 4. Lịch chạy Gọn trên Azure (3 Pha — Ước tính ~2–2,5 giờ)

| Pha | Môi trường | Việc cần làm | Ước tính |
| :---: | :--- | :--- | :---: |
| **1** | `SA` | Nạp nối tiếp `100K → 500K → 1M → 3M`: chạy **TN1** tại cả 4 mốc; dừng tại `1M` chạy luôn **TN2** (`SA`). | ~45 phút |
| **2** | `SH-hash` | Nạp nối tiếp `100K → 500K → 1M → 3M`: chạy **TN1** tại cả 4 mốc + đo nhẹ `Q3, Q4` tại `100K, 500K, 3M`; dừng tại `1M` chạy **TN2** & **TN3** (`SH-hash`, kèm 15s idle network). | ~60 phút |
| **3** | `SH-range` | Chỉ nạp đúng **1 lần mốc `1M`**: chờ Balancer ổn định → chạy **TN2** → chạy tiếp **TN3** (`SH-range`). | ~35 phút |
| **4** | Dọn dẹp | Kéo toàn bộ CSV/log về máy cá nhân, **xóa Resource Group Azure** ngay để tránh phát sinh phí ổ đĩa. | ~5 phút |
