# Phân tích Cơ chế và Đánh giá Thực nghiệm Sharding trên MongoDB (Synthea EHR)

Kho lưu trữ chính thức phục vụ **Báo cáo cuối kỳ môn Hệ quản trị Cơ sở dữ liệu (DBMS)** tại Trường Đại học Công nghệ — ĐHQGHN (UET-VNU), chứa toàn bộ đặc tả kỹ thuật, mã nguồn chuẩn bị dữ liệu Synthea, kịch bản benchmark, kết quả thực nghiệm thô và mã nguồn báo cáo LaTeX.

---

## 1. Cấu trúc Kho lưu trữ

```text
DBMS-distributed-method-benchmarking/
├── docs/
│   └── EXPERIMENT_SPEC.md       # Đặc tả kỹ thuật & ma trận thực nghiệm chuẩn (RQ1–RQ3)
├── data/
│   └── DATASET_SUMMARY.json     # Thống kê 6 bộ dữ liệu Synthea (D100K..D3M, D1M-nat, D1M-heavy)
├── scripts/
│   ├── build_datasets.py        # Pipeline sinh & tối giản JSONL từ Synthea CSV
│   ├── load_dataset.py          # Nạp dữ liệu vào MongoDB
│   └── verify_datasets.py       # Kiểm chứng số lượng docs, kích thước & phân phối lệch
├── infra/
│   ├── docker/                  # (Đang cập nhật) Docker Compose dry-run Pha 0
│   └── azure/                   # (Đang cập nhật) Script dựng VM Azure Student Profile A/B
├── analysis/                    # (Đang cập nhật) Script tổng hợp CSV & xuất biểu đồ PDF/PNG
├── results/                     # (Đang cập nhật) Raw CSV/JSON kết quả RQ1, RQ2, RQ3
└── report/                      # Mã nguồn báo cáo LaTeX (theo mẫu UET-VNU)
    ├── main.tex
    ├── build.sh                 # Biên dịch nhanh ra main.pdf
    ├── cover/                   # Trang bìa, tóm tắt, danh mục từ viết tắt
    ├── chapter/                 # Các chương báo cáo (Mở đầu, Chương 1–5)
    └── figures/                 # Logo và hình vẽ/biểu đồ
```

---

## 2. Câu hỏi Nghiên cứu (Research Questions)

- **RQ1 (Scale-out Đọc & Ngưỡng quy mô):** Từ quy mô nào (`100K → 3M encounters`) cụm MongoDB Sharded (`SH-hash`) đạt hiệu năng đọc tốt hơn Standalone (`SA`), và tách bạch chi phí điều phối `mongos` (`B1 - SA`) với lợi ích chia đôi RAM/Index (`B1 - SH-hash`).
- **RQ2 (Phân bố dữ liệu & Tải ghi khi dữ liệu lệch):** So sánh độ đồng đều phân bố dữ liệu (docs, MB, chunks) và tải ghi giữa `SH-hash` và `SH-range` dưới *Natural Skew* (`D1M-nat`) và *Heavy Skew* (`D1M-heavy`, 1% bệnh nhân chiếm 30% lượt khám).
- **RQ3 (Shard Pruning & Chi phí Cross-Shard):** Định lượng khác biệt giữa `SINGLE_SHARD` và `SHARD_MERGE`, lưu lượng mạng qua `mongos`, độ dốc chi phí theo quy mô `100K → 3M` và mức độ nhiễu chéo khi trộn tải `P:X` (`100:0 / 90:10 / 70:30`).

---

## 3. Hướng dẫn Biên dịch Báo cáo LaTeX

### Trên máy local (Linux / TeX Live)
```bash
cd report
./build.sh
```
File kết quả sẽ được sinh tại `report/main.pdf`.

### Trên Overleaf
1. Nén toàn bộ thư mục `report/` thành file `.zip`.
2. Tạo dự án mới trên Overleaf → **Upload Project** → chọn compiler **pdfLaTeX** và file chính `main.tex`.

---

## 4. Ghi chú về Dữ liệu lớn
Các file dữ liệu thô (`data/*/*.jsonl.gz`, tổng ~800 MB) được loại trừ khỏi Git qua `.gitignore`. Để tái tạo bộ dữ liệu với đúng `SEED = 42`, xem hướng dẫn trong `docs/EXPERIMENT_SPEC.md` và chạy `scripts/build_datasets.py`.
