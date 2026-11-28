# Phân tích Cơ chế và Đánh giá Thực nghiệm Sharding trên MongoDB 7.0 (Synthea EHR)

Kho lưu trữ chính thức phục vụ **Báo cáo cuối kỳ môn Hệ quản trị Cơ sở dữ liệu (DBMS - INT3202 1, Nhóm 5)** tại Trường Đại học Công nghệ - ĐHQGHN (UET-VNU), chứa đặc tả thực nghiệm bản tinh gọn (**v3**), mã nguồn chuẩn bị dữ liệu Synthea, kịch bản benchmark MongoDB 7.0 trên Docker cô lập tài nguyên, kết quả đo thực tế (`114` lượt chạy sạch trên cùng một máy host), kịch bản tổng hợp biểu đồ và mã nguồn báo cáo LaTeX hoàn chỉnh.

---

## 1. Cấu trúc Kho lưu trữ

```text
DBMS-distributed-method-benchmarking/
├── docs/
│   ├── EXPERIMENT_SPEC.md       # Tài liệu thiết kế thực nghiệm bản tinh gọn (v3: 3 env, 3 bảng)
│   └── local/                   # Hướng dẫn triển khai cục bộ trên Docker cô lập tài nguyên
├── data/
│   ├── DATASET_SUMMARY.json     # Thống kê dữ liệu Synthea gốc
│   └── V2_ANALYSIS.json         # Phân tích ngoại tuyến kích thước, tập làm việc & độ chọn lọc truy vấn
├── scripts/
│   ├── build_datasets.py        # Pipeline sinh tập JSONL từ Synthea CSV
│   ├── verify_datasets.py       # Kiểm chứng số lượng docs và tính lồng nhau 100K-3M
│   ├── prepare_v2.py            # Sinh workload_v2.json, V2_ANALYSIS.json và gói nạp theo START (load_v2)
│   ├── load_dataset.py          # Nạp nối tiếp từng mốc (S1..S5) kèm metadata thời gian nạp
│   ├── bench_v2.py              # Script đo thực nghiệm (TN1, TN2, TN3; SA, SH-hash, SH-range)
│   └── run_all_local.py         # Điều phối tự động sạch 3 pha (SA, SH-hash, SH-range) trên 1 máy host
├── analysis/
│   ├── generate_arch_figures.py # Sinh 3 hình vẽ kiến trúc vector (SVG -> PNG/PDF) cho Chương 1 & 2
│   ├── generate_report_artifacts.py # Tổng hợp summary_tables.json và sinh 4 biểu đồ kết quả Chương 4
│   └── summary_tables.json      # Bảng số liệu tổng hợp chính thức từ 114 lượt chạy
├── infra/
│   └── docker/                  # Docker Compose + init-cluster.sh (MongoDB 7.0.48, 1 GB RAM / 2 vCPU mỗi nút)
├── results/                     # Dữ liệu CSV/JSON/telemetry sạch (RQ1, RQ2, RQ3, load, sys)
└── report/                      # Báo cáo hoàn chỉnh (Markdown Obsidian & LaTeX chuẩn UET-VNU)
    ├── REPORT_DRAFT.md          # Bản thảo Markdown hoàn chỉnh đồng bộ với LaTeX
    ├── main.tex / main.pdf      # Mã nguồn và tệp PDF báo cáo đã biên dịch
    ├── build.sh                 # Biên dịch nhanh ra main.pdf
    ├── figures/                 # 7 hình vẽ vector (PDF cho LaTeX, PNG cho Obsidian)
    ├── cover/                   # Trang bìa, tóm tắt, danh mục từ viết tắt
    ├── chapter/                 # Mở đầu & Chương 1-5 (Bảng 4.1-4.4 & Hình 1.1-4.4)
    └── appendix/                # Phụ lục A (Hạ tầng & Telemetry) & Phụ lục B (Schema & Q1, Q2, Q3)
```

---

## 2. Tóm tắt 3 Câu hỏi Nghiên cứu & 3 Thực nghiệm (v3)

- **RQ1 - Mở rộng Đọc (`TN1`):** So sánh `SA` (1 nút) với `SH-hash` (2 shard, `{PATIENT: "hashed"}`) trên truy vấn `Q1` qua `100K -> 500K -> 1M -> 3M` ở `1 / 4 / 8` luồng -> **Bảng 4.1** (`p95`, `QPS`, `Hit cache`, `Trang đĩa/req`).
- **RQ2 - Độ đều Dữ liệu & Tốc độ Ghi mới (`TN2`):** So sánh `SA`, `SH-hash` và `SH-range` (`{START: 1, PATIENT: 1}`) tại mốc `1M` về tỷ lệ dữ liệu giữa 2 shard, tỷ lệ lượt ghi mới (`START = now()`), `inserts/s` và `p95` -> **Bảng 4.2**.
- **RQ3 - Tỉa mảnh & Chi phí Xuyên mảnh (`TN3`):** So sánh `Q1` (1 bệnh nhân), `Q2` (xuyên bệnh nhân, kết quả nhỏ - mã tệp gốc `Q3`) và `Q3` (xuyên bệnh nhân, kết quả lớn - mã tệp gốc `Q4`) trên `SH-hash` và `SH-range` tại `1M` (kèm đo độ dốc `100K -> 3M` trên `SH-hash`) về số shard hỏi (`explain`), `p95`, `QPS` và lưu lượng mạng nội bộ `KB/req` -> **Bảng 4.3 & Bảng 4.4**.

---

## 3. Quy trình Tái lập Nhanh

```bash
# 1. Tạo gói nạp tăng dần theo thứ tự thời gian START
python3 scripts/prepare_v2.py --data-root data workload
python3 scripts/prepare_v2.py --data-root data loadorder --tmp-dir data/.tmp

# 2. Chạy toàn bộ 3 pha thực nghiệm sạch trên Docker (MongoDB 7.0.48)
python3 scripts/run_all_local.py

# 3. Sinh toàn bộ hình vẽ kiến trúc và biểu đồ kết quả (PNG + PDF)
python3 analysis/generate_arch_figures.py
python3 analysis/generate_report_artifacts.py

# 4. Biên dịch báo cáo LaTeX -> report/main.pdf
cd report && ./build.sh
```
