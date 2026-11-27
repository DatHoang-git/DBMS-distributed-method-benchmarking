# Hướng dẫn Chạy Local — Cấu hình 2: `SH-hash` (Cụm 2 Shard Chia Băm theo `PATIENT`)

> **Áp dụng cho:** Máy chạy EndeavourOS hoặc Ubuntu (Docker local, khuyến nghị máy có ≥ 8 GB RAM trống và ≥ 8 GB ổ đĩa trống).  
> **Phạm vi của cấu hình này:** Chạy trọn **TN1** (`100K → 3M`), **TN2** (`1M`: độ đều dữ liệu + ghi 4 luồng), **TN3** (`1M`: explain + đọc `Q3/Q4` kèm trừ nền 15s idle) và đo thêm độ dốc `Q3/Q4` ở `100K, 500K, 3M`.

---

## 1. Tải dữ liệu từ Google Drive (`DBMS_Synthea_EHR_Datasets`)

Mở thư mục Drive: https://drive.google.com/drive/folders/1HMKFEmCLFd-vF_dU8yiSMllxgo1IN42H

| Thư mục / Tệp trên Drive | Cần tải? | Dung lượng | Ghi chú |
| :--- | :---: | :---: | :--- |
| **`D3M/`** *(tải cả thư mục)* | **BẮT BUỘC** | ~445 MB | Nguồn chính để tách ra cả 4 gói nạp `S1..S4`. |
| **`D100K/`** *(chỉ cần `patient_ids.txt`, `query_params.json`)* | **BẮT BUỘC** | ~0.2 MB *(hoặc ~12 MB nếu tải cả thư mục)* | Danh sách bệnh nhân và cửa sổ mốc 100K. |
| **`D500K/`** *(chỉ cần `patient_ids.txt`, `query_params.json`)* | **BẮT BUỘC** | ~0.5 MB *(hoặc ~72 MB nếu tải cả thư mục)* | Danh sách bệnh nhân mốc 500K. |
| **`D1M/`** *(chỉ cần `patient_ids.txt`, `query_params.json`)* | **BẮT BUỘC** | ~0.8 MB *(hoặc ~146 MB nếu tải cả thư mục)* | Danh sách bệnh nhân và cửa sổ mốc 1M. |
| `D1M-heavy/` | **KHÔNG TẢI** | ~140 MB | Dư thừa từ phiên bản cũ, đã cắt bỏ. |
| `D1M-nat` | **KHÔNG TẢI** | shortcut | Chỉ là liên kết tới `D1M/`. |
| `DATASET_SUMMARY.json` | Tùy chọn | 2.4 KB | Có sẵn trong repo GitHub. |

**Đặt dữ liệu tải về vào đúng đường dẫn trong repo:**
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

Chạy đoạn lệnh sau để sinh `workload_v2.json` và tách `D3M` thành 4 gói tăng dần `S1` (`100K`), `S2` (`+400K`), `S3` (`+500K`), `S4` (`+2M`) đã sắp theo `START` *(nếu máy này đã chạy bước này ở cấu hình `SA` rồi thì bỏ qua Bước 3!)*:

```bash
for ds in D100K D500K D1M D3M; do
  cp "data/$ds/query_params.json" "data/$ds/workload_v2.json"
done

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

## 4. Dựng Cụm MongoDB 7.0 (`SH-hash`) & Chia Băm

```bash
docker rm -f mdb-mongos mdb-shard1 mdb-shard2 mdb-cfgsvr 2>/dev/null || true
docker network create mdb-net 2>/dev/null || true

docker run -d --name mdb-cfgsvr --network mdb-net --memory=512m --cpus=1 -p 27019:27019 \
  mongo:7.0 mongod --configsvr --replSet cfgRS --port 27019 --bind_ip_all --wiredTigerCacheSizeGB 0.25

docker run -d --name mdb-shard1 --network mdb-net --memory=1g --cpus=2 -p 27118:27018 \
  mongo:7.0 mongod --shardsvr --replSet shard1RS --port 27018 --bind_ip_all --wiredTigerCacheSizeGB 0.50

docker run -d --name mdb-shard2 --network mdb-net --memory=1g --cpus=2 -p 27218:27018 \
  mongo:7.0 mongod --shardsvr --replSet shard2RS --port 27018 --bind_ip_all --wiredTigerCacheSizeGB 0.50

docker run -d --name mdb-mongos --network mdb-net --memory=512m --cpus=2 -p 27017:27017 \
  mongo:7.0 mongos --configdb cfgRS/mdb-cfgsvr:27019 --port 27017 --bind_ip_all

sleep 5
docker exec mdb-cfgsvr mongosh --port 27019 --eval 'rs.initiate({_id:"cfgRS", configsvr:true, members:[{_id:0, host:"mdb-cfgsvr:27019"}]})'
docker exec mdb-shard1 mongosh --port 27018 --eval 'rs.initiate({_id:"shard1RS", members:[{_id:0, host:"mdb-shard1:27018"}]})'
docker exec mdb-shard2 mongosh --port 27018 --eval 'rs.initiate({_id:"shard2RS", members:[{_id:0, host:"mdb-shard2:27018"}]})'
sleep 6

docker exec mdb-mongos mongosh --port 27017 --eval '
  sh.addShard("shard1RS/mdb-shard1:27018");
  sh.addShard("shard2RS/mdb-shard2:27018");
  db.getSiblingDB("config").settings.updateOne({_id:"chunksize"}, {$set:{value:32}}, {upsert:true});
  sh.enableSharding("ehr");
  sh.shardCollection("ehr.patients", {_id: "hashed"});
  sh.shardCollection("ehr.encounters", {PATIENT: "hashed"}, false, {numInitialChunks: 16});
  const col = db.getSiblingDB("ehr").encounters;
  col.createIndex({PATIENT: 1, START: -1});
  col.createIndex({START: 1});
  col.createIndex({"conditions.CODE": 1, START: 1});
  sh.stopBalancer();
  printjson(db.adminCommand("balancerStatus"));
'
```

---

## 5. Chạy Thực nghiệm (`TN1`, `TN2`, `TN3`)

Mở terminal phụ ghi log tài nguyên:
```bash
mkdir -p results/sys
sar -u -r -d 1 > results/sys/SH-hash_sar.log
```

Tại terminal chính (đã `source .venv/bin/activate`):
```bash
URI_SH="mongodb://localhost:27017"
NODES=(
  --node-uri "mongos=mongodb://localhost:27017"
  --node-uri "s1=mongodb://localhost:27118/?directConnection=true"
  --node-uri "s2=mongodb://localhost:27218/?directConnection=true"
)

# ================= MỐC 100K (S1) =================
python3 scripts/load_dataset.py --uri "$URI_SH" --dataset data/load_v2/S1 --env SH-hash
for t in 1 4 8; do
  for r in 1 2 3; do
    python3 scripts/bench_v2.py --uri "$URI_SH" "${NODES[@]}" --env SH-hash --dataset D100K \
      --scenario TN1 --query Q1 --threads $t --rep $r --output-dir results/RQ1
  done
done
# Độ dốc Q3, Q4 tại 100K
for q in Q3 Q4; do
  python3 scripts/bench_v2.py --uri "$URI_SH" "${NODES[@]}" --env SH-hash --dataset D100K \
    --scenario TN3-read --query $q --threads 1 --rep 1 --output-dir results/RQ3
done

# ================= MỐC 500K (S2) =================
python3 scripts/load_dataset.py --uri "$URI_SH" --dataset data/load_v2/S2 --env SH-hash
for t in 1 4 8; do
  for r in 1 2 3; do
    python3 scripts/bench_v2.py --uri "$URI_SH" "${NODES[@]}" --env SH-hash --dataset D500K \
      --scenario TN1 --query Q1 --threads $t --rep $r --output-dir results/RQ1
  done
done
# Độ dốc Q3, Q4 tại 500K
for q in Q3 Q4; do
  python3 scripts/bench_v2.py --uri "$URI_SH" "${NODES[@]}" --env SH-hash --dataset D500K \
    --scenario TN3-read --query $q --threads 1 --rep 1 --output-dir results/RQ3
done

# ================= MỐC 1M (S3) -> TN1 + TN2 + TN3 =================
python3 scripts/load_dataset.py --uri "$URI_SH" --dataset data/load_v2/S3 --env SH-hash

# TN2-dist: chụp tỷ lệ % dung lượng Máy 1 / Máy 2
python3 scripts/bench_v2.py --uri "$URI_SH" --env SH-hash --dataset D1M \
  --scenario TN2-dist --output-dir results/RQ2

# TN1 tại 1M (nhớ chạy thêm 1 lượt Q1 có --idle-net-s 15 để lấy KB/req cho Bảng 3)
for t in 1 4 8; do
  for r in 1 2 3; do
    IDLE_ARG=""
    [ "$t" = "1" ] && [ "$r" = "1" ] && IDLE_ARG="--idle-net-s 15"
    python3 scripts/bench_v2.py --uri "$URI_SH" "${NODES[@]}" --env SH-hash --dataset D1M \
      --scenario TN1 --query Q1 --threads $t $IDLE_ARG --rep $r --output-dir results/RQ1
  done
done

# TN3-explain + TN3-read (Q3, Q4 tại 1M, có trừ nền 15s idle)
python3 scripts/bench_v2.py --uri "$URI_SH" --env SH-hash --dataset D1M \
  --scenario TN3-explain --output-dir results/RQ3
for q in Q3 Q4; do
  for r in 1 2 3; do
    python3 scripts/bench_v2.py --uri "$URI_SH" "${NODES[@]}" --env SH-hash --dataset D1M \
      --scenario TN3-read --query $q --threads 1 --idle-net-s 15 --rep $r --output-dir results/RQ3
  done
done

# TN2-write tại 1M (chạy SAU TN1/TN3 để không làm phình số bản ghi khi đang đo đọc)
for r in 1 2 3; do
  python3 scripts/bench_v2.py --uri "$URI_SH" "${NODES[@]}" --env SH-hash --dataset D1M \
    --scenario TN2-write --threads 4 --duration 60 --rep $r --output-dir results/RQ2
done

# ================= MỐC 3M (S4) =================
python3 scripts/load_dataset.py --uri "$URI_SH" --dataset data/load_v2/S4 --env SH-hash
for t in 1 4 8; do
  for r in 1 2 3; do
    python3 scripts/bench_v2.py --uri "$URI_SH" "${NODES[@]}" --env SH-hash --dataset D3M \
      --scenario TN1 --query Q1 --threads $t --rep $r --output-dir results/RQ1
  done
done
# Độ dốc Q3, Q4 tại 3M
for q in Q3 Q4; do
  python3 scripts/bench_v2.py --uri "$URI_SH" "${NODES[@]}" --env SH-hash --dataset D3M \
    --scenario TN3-read --query $q --threads 1 --rep 1 --output-dir results/RQ3
done
```

### Dọn container sau khi xong
```bash
docker rm -f mdb-mongos mdb-shard1 mdb-shard2 mdb-cfgsvr
```

---

## 6. Kết quả cần bàn giao lại
Gửi trọn thư mục `results/RQ1/`, `results/RQ2/`, `results/RQ3/` để điền:
- Các cột **`SH-hash`** của **Bảng 1** (`p95`, `QPS` qua `100K..3M × 1/4/8`).
- Dòng **`SH-hash`** của **Bảng 2** (`% dữ liệu` từ `dist/`, `% ghi s1/s2` từ `status/*_s1.json` & `*_s2.json`, `inserts/s`, `p95`).
- Các cột **`SH-hash`** của **Bảng 3** (số máy hỏi từ `explain/`, `p95`, `net_kb_per_req` ở `1M`) và biểu đồ độ dốc `100K → 3M`.
