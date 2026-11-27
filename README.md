# Phân tích Cơ chế và Đánh giá Thực nghiệm Sharding trên MongoDB 7.0 (Synthea EHR)

Kho lưu trữ chính thức phục vụ **Báo cáo cuối kỳ môn Hệ quản trị Cơ sở dữ liệu (DBMS — INT3202 1, Nhóm 5)** tại Trường Đại học Công nghệ — ĐHQGHN (UET-VNU), chứa đặc tả thực nghiệm bản tinh gọn (**v3**), mã nguồn chuẩn bị dữ liệu Synthea, kịch bản benchmark, cấu hình Docker dry-run và mã nguồn báo cáo LaTeX.

---

## 1. Cấu trúc Kho lưu trữ

```text
DBMS-distributed-method-benchmarking/
├── docs/
│   └── EXPERIMENT_SPEC.md       # Tài liệu thiết kế thực nghiệm bản tinh gọn (v3: 3 env, 3 bảng)
├── data/
│   ├── DATASET_SUMMARY.json     # Thống kê dữ liệu Synthea gốc
│   └── V2_ANALYSIS.json         # Phân tích ngoại tuyến kích thước, tập làm việc & độ chọn lọc truy vấn
├── scripts/
│   ├── build_datasets.py        # Pipeline sinh tập JSONL từ Synthea CSV
│   ├── verify_datasets.py       # Kiểm chứng số lượng docs và tính lồng nhau 100K–3M
│   ├── prepare_v2.py            # Sinh workload_v2.json, V2_ANALYSIS.json và gói nạp theo START (load_v2)
│   ├── load_dataset.py          # Nạp nối tiếp từng mốc (S1..S5) kèm metadata thời gian nạp
│   └── bench_v2.py              # Script đo thực nghiệm (TN1, TN2, TN3; SA, SH-hash, SH-range)
├── infra/
│   └── docker/                  # Docker Compose + init-cluster.sh (Pha 0 MongoDB 7.0 dry-run)
├── results/                     # Dữ liệu CSV/JSON thu được từ cụm Azure (RQ1, RQ2, RQ3)
└── report/                      # Mã nguồn báo cáo LaTeX (theo mẫu UET-VNU)
    ├── main.tex
    ├── build.sh                 # Biên dịch nhanh ra main.pdf
    ├── cover/                   # Trang bìa, tóm tắt, danh mục từ viết tắt
    ├── chapter/                 # Mở đầu & Chương 1–5 (đúng 3 bảng kết quả chính)
    └── appendix/                # Phụ lục A (Hạ tầng) & Phụ lục B (Schema thực tế & Q1, Q3, Q4)
```

---

## 2. Tóm tắt 3 Câu hỏi Nghiên cứu & 3 Thực nghiệm (v3)

- **RQ1 — Mở rộng Đọc (`TN1`):** So sánh `SA` (1 máy) với `SH-hash` (2 máy, `{PATIENT: "hashed"}`) trên 1 truy vấn `Q1` qua `100K → 500K → 1M → 3M` ở `1 / 4 / 8` luồng → **Bảng 1** (`p95`, `QPS`).
- **RQ2 — Độ đều Dữ liệu & Tốc độ Ghi mới (`TN2`):** So sánh `SA`, `SH-hash` và `SH-range` (`{START: 1, PATIENT: 1}`) tại mốc `1M` về tỷ lệ dữ liệu giữa 2 máy, tỷ lệ lượt ghi mới (`START = now()`), `inserts/s` và `p95` → **Bảng 2**.
- **RQ3 — Tỉa mảnh & Chi phí Xuyên mảnh (`TN3`):** So sánh `Q1` (1 bệnh nhân), `Q3` (xuyên bệnh nhân, kết quả nhỏ) và `Q4` (xuyên bệnh nhân, kết quả lớn) trên `SH-hash` và `SH-range` tại `1M` (kèm đo độ dốc `100K → 3M` trên `SH-hash`) về số máy hỏi (`explain`), `p95` và lưu lượng mạng `KB/req` → **Bảng 3**.

---

## 3. Quy trình Chạy nhanh

```bash
# 1. Tạo gói nạp tăng dần theo thứ tự thời gian START
python3 scripts/prepare_v2.py --data-root data workload
python3 scripts/prepare_v2.py --data-root data loadorder --tmp-dir data/.tmp

# 2. Pha 0 kiểm thử cục bộ trên Docker (MongoDB 7.0)
docker compose -f infra/docker/docker-compose.yml up -d
./infra/docker/init-cluster.sh
python3 scripts/load_dataset.py --uri mongodb://localhost:27017 --dataset data/load_v2/S1 --drop --env SH-hash

# 3. Biên dịch báo cáo LaTeX -> report/main.pdf
cd report && ./build.sh
```
