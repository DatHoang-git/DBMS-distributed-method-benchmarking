# Hướng dẫn Chạy Local — Cấu hình 1: `SA` (1 Máy Dữ liệu Đơn)

> **Áp dụng cho:** Máy chạy EndeavourOS hoặc Ubuntu (Docker local).  
> **Phạm vi của cấu hình này:** Chạy **TN1** (`Q1` qua 4 mốc `100K → 500K → 1M → 3M` ở `1 / 4 / 8` luồng) và **TN2-write** (ghi mới `4` luồng ở mốc `1M`) làm mốc đối chứng cho cụm 2 shard.

---

## 1. Tải dữ liệu từ Google Drive (`DBMS_Synthea_EHR_Datasets`)

Mở thư mục Drive: https://drive.google.com/drive/folders/1HMKFEmCLFd-vF_dU8yiSMllxgo1IN42H

| Thư mục / Tệp trên Drive | Cần tải? | Dung lượng | Ghi chú |
| :--- | :---: | :---: | :--- |
| **`D3M/`** *(tải cả thư mục)* | **BẮT BUỘC** | ~445 MB | Chứa trọn bộ 3 triệu lượt khám (dùng để trích ra cả 4 mốc). |
| **`D100K/`** *(chỉ cần `patient_ids.txt`, `query_params.json`)* | **BẮT BUỘC** | ~0.2 MB *(hoặc ~12 MB nếu tải cả thư mục)* | Dùng danh sách bệnh nhân và cửa sổ truy vấn mốc 100K. |
| **`D500K/`** *(chỉ cần `patient_ids.txt`, `query_params.json`)* | **BẮT BUỘC** | ~0.5 MB *(hoặc ~72 MB nếu tải cả thư mục)* | Dùng danh sách bệnh nhân mốc 500K. |
| **`D1M/`** *(chỉ cần `patient_ids.txt`, `query_params.json`)* | **BẮT BUỘC** | ~0.8 MB *(hoặc ~146 MB nếu tải cả thư mục)* | Dùng danh sách bệnh nhân mốc 1M. |
| `D1M-heavy/` | **KHÔNG TẢI** | ~140 MB | Dư thừa từ phiên bản cũ, đã cắt bỏ. |
| `D1M-nat` | **KHÔNG TẢI** | shortcut | Chỉ là liên kết tới `D1M/`. |
| `DATASET_SUMMARY.json` | Tùy chọn | 2.4 KB | Có sẵn trong repo GitHub. |

**Đặt thư mục sau khi tải vào đúng cấu trúc trong repo:**
```text
DBMS-distributed-method-benchmarking/
└── data/
    ├── D100K/{patient_ids.txt, query_params.json}
    ├── D500K/{patient_ids.txt, query_params.json}
    ├── D1M/{patient_ids.txt, query_params.json}
    └── D3M/{encounters.jsonl.gz, patients.jsonl.gz, patient_ids.txt, query_params.json}
```

---

## 2. Cài đặt công cụ (làm 1 lần)

### Trên EndeavourOS (Arch)
```bash
sudo pacman -S --needed docker sysstat python git
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
newgrp docker
```

### Trên Ubuntu
```bash
sudo apt update && sudo apt install -y docker.io sysstat python3-venv git
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
newgrp docker
```

### Clone repo & cài `pymongo`
```bash
git clone https://github.com/DatHoang-git/DBMS-distributed-method-benchmarking.git
cd DBMS-distributed-method-benchmarking
python3 -m venv .venv
source .venv/bin/activate
pip install pymongo
```

---

## 3. Chuẩn bị dữ liệu nạp theo thứ tự thời gian `START` (~3 phút)

Vì dữ liệu trên Drive thuộc bản v1 (chưa có `workload_v2.json` và các lượt khám đang xếp gom theo từng bệnh nhân), chạy đúng đoạn lệnh sau để:
1. Tạo `workload_v2.json` (từ `query_params.json` có sẵn, khớp 100% cửa sổ thời gian).
2. Tách `D3M` thành 4 gói tăng dần `S1` (`100K`), `S2` (`+400K`), `S3` (`+500K`), `S4` (`+2M`) đã sắp theo `START` (không cần `D1M-heavy` hay `D2M`).

```bash
# 1. Tạo workload_v2.json cho 4 mốc
for ds in D100K D500K D1M D3M; do
  cp "data/$ds/query_params.json" "data/$ds/workload_v2.json"
done

# 2. Tách 4 gói nạp nối tiếp S1..S4 sắp xếp tăng dần theo START
python3 - <<'EOF'
import gzip, json, os, shutil, subprocess
from pathlib import Path

root = Path("data")
out = root / "load_v2"
tmp = root / ".tmp_sort"
tmp.mkdir(parents=True, exist_ok=True)

def read_ids(ds):
    return {l.strip() for l in (root / ds / "patient_ids.txt").open() if l.strip()}

steps = [("S1", "D100K", None), ("S2", "D500K", "D100K"), ("S3", "D1M", "D500K"), ("S4", "D3M", "D1M")]
for step, ds, prev in steps:
    keep = read_ids(ds) - (read_ids(prev) if prev else set())
    d = out / step
    d.mkdir(parents=True, exist_ok=True)
    raw = tmp / f"{step}.tsv"
    srt = tmp / f"{step}.sorted.tsv"
    with gzip.open(root / "D3M/encounters.jsonl.gz", "rt") as fin, raw.open("w") as fout:
        for line in fin:
            doc = json.loads(line)
            if doc["PATIENT"] in keep:
                fout.write(doc["START"] + "\t" + line)
    subprocess.run(["sort", "-s", "-t", "\t", "-k1,1", "-S", "1G", "-T", str(tmp), "-o", str(srt), str(raw)],
                   check=True, env=dict(os.environ, LC_ALL="C"))
    raw.unlink()
    n = 0
    with srt.open() as fin, gzip.open(d / "encounters.jsonl.gz", "wt", compresslevel=6) as fout:
        for line in fin:
            fout.write(line.split("\t", 1)[1])
            n += 1
    srt.unlink()
    with gzip.open(root / "D3M/patients.jsonl.gz", "rt") as fin, gzip.open(d / "patients.jsonl.gz", "wt") as fout:
        for line in fin:
            if json.loads(line)["_id"] in keep:
                fout.write(line)
    print(f"Done {step} ({ds}): {n:,} encounters")
shutil.rmtree(tmp, ignore_errors=True)
EOF
```

---

## 4. Dựng MongoDB 7.0 (`SA`) & Tạo chỉ mục

```bash
docker rm -f mdb-sa 2>/dev/null || true
docker run -d --name mdb-sa \
  --memory=1g --cpus=2 \
  -p 27017:27017 \
  mongo:7.0 mongod --replSet rs0 --port 27017 --bind_ip_all --wiredTigerCacheSizeGB 0.50

sleep 4
docker exec mdb-sa mongosh --port 27017 --eval '
  rs.initiate({_id: "rs0", members: [{_id: 0, host: "localhost:27017"}]});
'
sleep 4
docker exec mdb-sa mongosh --port 27017 --eval '
  const col = db.getSiblingDB("ehr").encounters;
  col.createIndex({PATIENT: 1, START: -1});
  col.createIndex({START: 1});
  col.createIndex({"conditions.CODE": 1, START: 1});
'
```

---

## 5. Chạy Thực nghiệm (`TN1` & `TN2`)

Mở thêm 1 terminal phụ để ghi log tài nguyên máy (tùy chọn nhưng nên làm):
```bash
mkdir -p results/sys
sar -u -r -d 1 > results/sys/SA_sar.log
```

Tại terminal chính (đã `source .venv/bin/activate`):
```bash
URI_SA="mongodb://localhost:27017/?directConnection=true"

# --- Mốc 100K (S1) ---
python3 scripts/load_dataset.py --uri "$URI_SA" --dataset data/load_v2/S1 --drop --env SA
for t in 1 4 8; do
  for r in 1 2 3; do
    python3 scripts/bench_v2.py --uri "$URI_SA" --env SA --dataset D100K \
      --scenario TN1 --query Q1 --threads $t --rep $r --output-dir results/RQ1
  done
done
# KIỂM TRA NHANH: Nếu ở t=8 thấy "bound=True" (client_cpu_max >= 75%), đổi dải "1 4 8" thành "1 2 4" cho cả 3 máy!

# --- Mốc 500K (nạp nối tiếp S2) ---
python3 scripts/load_dataset.py --uri "$URI_SA" --dataset data/load_v2/S2 --env SA
for t in 1 4 8; do
  for r in 1 2 3; do
    python3 scripts/bench_v2.py --uri "$URI_SA" --env SA --dataset D500K \
      --scenario TN1 --query Q1 --threads $t --rep $r --output-dir results/RQ1
  done
done

# --- Mốc 1M (nạp nối tiếp S3) -> chạy TN1 trước, TN2-write sau ---
python3 scripts/load_dataset.py --uri "$URI_SA" --dataset data/load_v2/S3 --env SA
for t in 1 4 8; do
  for r in 1 2 3; do
    python3 scripts/bench_v2.py --uri "$URI_SA" --env SA --dataset D1M \
      --scenario TN1 --query Q1 --threads $t --rep $r --output-dir results/RQ1
  done
done
for r in 1 2 3; do
  python3 scripts/bench_v2.py --uri "$URI_SA" --env SA --dataset D1M \
    --scenario TN2-write --threads 4 --duration 60 --rep $r --output-dir results/RQ2
done

# --- Mốc 3M (nạp nối tiếp S4) ---
python3 scripts/load_dataset.py --uri "$URI_SA" --dataset data/load_v2/S4 --env SA
for t in 1 4 8; do
  for r in 1 2 3; do
    python3 scripts/bench_v2.py --uri "$URI_SA" --env SA --dataset D3M \
      --scenario TN1 --query Q1 --threads $t --rep $r --output-dir results/RQ1
  done
done
```

### Dọn container sau khi xong
```bash
docker rm -f mdb-sa
```

---

## 6. Kết quả cần bàn giao lại
Gửi thư mục `results/RQ1/` và `results/RQ2/` (chứa các tệp `.csv`, `meta/*.json`, `status/*.json`) để điền các cột **`SA`** của **Bảng 1** (`p95`, `QPS` qua `100K/500K/1M/3M × 1/4/8` luồng) và dòng **`SA`** của **Bảng 2** (`inserts/s`, `p95`).
