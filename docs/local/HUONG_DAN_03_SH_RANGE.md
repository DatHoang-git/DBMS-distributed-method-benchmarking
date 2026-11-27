# Hướng dẫn Chạy Local — Cấu hình 3: `SH-range` (Cụm 2 Shard Chia Khoảng theo `START`)

> **Áp dụng cho:** Máy chạy EndeavourOS hoặc Ubuntu (Docker local).  
> **Phạm vi của cấu hình này:** **Nhẹ nhất trong 3 cấu hình!** Chỉ chạy duy nhất mốc **`1M`** cho **TN2** (độ đều dữ liệu + ghi mới 4 luồng để quan sát điểm nóng ghi) và **TN3** (explain + đọc `Q3`, `Q4` để đối chiếu tỉa mảnh với `SH-hash`).

---

## 1. Tải dữ liệu từ Google Drive (`DBMS_Synthea_EHR_Datasets`)

Mở thư mục Drive: https://drive.google.com/drive/folders/1HMKFEmCLFd-vF_dU8yiSMllxgo1IN42H

| Thư mục / Tệp trên Drive | Cần tải? | Dung lượng | Ghi chú |
| :--- | :---: | :---: | :--- |
| **`D1M/`** *(tải cả thư mục)* | **BẮT BUỘC (DUY NHẤT)** | **~146 MB** | Đủ trọn vẹn cho toàn bộ TN2 & TN3 của `SH-range`. |
| `D100K/`, `D500K/`, `D3M/` | **KHÔNG CẦN TẢI** | ~529 MB | `SH-range` không chạy các mốc này! |
| `D1M-heavy/` | **KHÔNG TẢI** | ~140 MB | Dư thừa từ phiên bản cũ, đã cắt bỏ. |
| `D1M-nat` | **KHÔNG TẢI** | shortcut | Chỉ là liên kết tới `D1M/`. |

**Đặt dữ liệu tải về vào đúng đường dẫn trong repo:**
```text
DBMS-distributed-method-benchmarking/
└── data/
    └── D1M/
        ├── encounters.jsonl.gz
        ├── patients.jsonl.gz
        ├── patient_ids.txt
        └── query_params.json
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

## 3. Chuẩn bị `workload_v2.json` & Sắp xếp `D1M` theo `START` (~30 giây)

Chạy đúng đoạn lệnh sau (chỉ xử lý `D1M`, không cần `D3M` hay `D1M-heavy`):
```bash
cp data/D1M/query_params.json data/D1M/workload_v2.json

python3 - <<'EOF'
import gzip, json, os, shutil, subprocess
from pathlib import Path

src = Path("data/D1M")
dst = Path("data/load_v2/D1M_sorted")
tmp = Path("data/.tmp_range")
dst.mkdir(parents=True, exist_ok=True)
tmp.mkdir(parents=True, exist_ok=True)

raw, srt = tmp / "d1m.tsv", tmp / "d1m.sorted.tsv"
with gzip.open(src / "encounters.jsonl.gz", "rt") as fin, raw.open("w") as fout:
    for line in fin:
        fout.write(json.loads(line)["START"] + "\t" + line)
subprocess.run(["sort", "-s", "-t", "\t", "-k1,1", "-S", "1G", "-T", str(tmp), "-o", str(srt), str(raw)],
               check=True, env=dict(os.environ, LC_ALL="C"))
raw.unlink()
n = 0
with srt.open() as fin, gzip.open(dst / "encounters.jsonl.gz", "wt", compresslevel=6) as fout:
    for line in fin:
        fout.write(line.split("\t", 1)[1])
        n += 1
srt.unlink()
shutil.copyfile(src / "patients.jsonl.gz", dst / "patients.jsonl.gz")
shutil.rmtree(tmp, ignore_errors=True)
print(f"Ready: {dst} ({n:,} encounters sorted by START)")
EOF
```

---

## 4. Dựng Cụm MongoDB 7.0 (`SH-range`) & Bật Balancer

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
  sh.shardCollection("ehr.encounters", {START: 1, PATIENT: 1});
  const col = db.getSiblingDB("ehr").encounters;
  col.createIndex({PATIENT: 1, START: -1});
  col.createIndex({START: 1});
  col.createIndex({"conditions.CODE": 1, START: 1});
  sh.startBalancer();
'
```

---

## 5. Nạp `1M`, Chờ Balancer Cân bằng & Chạy Đo (`TN2`, `TN3`)

```bash
URI_SH="mongodb://localhost:27017"
NODES=(
  --node-uri "mongos=mongodb://localhost:27017"
  --node-uri "s1=mongodb://localhost:27118/?directConnection=true"
  --node-uri "s2=mongodb://localhost:27218/?directConnection=true"
)

# 1. Nạp 1M lượt khám đã sắp theo START
python3 scripts/load_dataset.py --uri "$URI_SH" --dataset data/load_v2/D1M_sorted --env SH-range

# 2. Chờ Balancer dời dữ liệu sang Shard 2 (chạy lại lệnh này mỗi 1-2 phút đến khi thấy 2 shard gần đều
#    và inBalancerRound: false — lưu ý MongoDB 7.0 dừng cân bằng khi lệch < 96 MB, khoảng ~53%/47%)
docker exec mdb-mongos mongosh --port 27017 --eval '
  printjson(db.adminCommand("balancerStatus"));
  print("Active migrations:", db.getSiblingDB("config").migrations.countDocuments({}));
  db.getSiblingDB("ehr").encounters.getShardDistribution();
'

# 3. Khi Balancer đã dừng ổn định -> TẮT Balancer rồi đo
docker exec mdb-mongos mongosh --port 27017 --eval 'sh.stopBalancer()'

# 4. TN2-dist: chụp tỷ lệ % dung lượng Máy 1 / Máy 2
python3 scripts/bench_v2.py --uri "$URI_SH" --env SH-range --dataset D1M \
  --scenario TN2-dist --output-dir results/RQ2

# 5. TN3-explain + TN3-read (Q3, Q4 tại 1M, có trừ nền 15s idle)
python3 scripts/bench_v2.py --uri "$URI_SH" --env SH-range --dataset D1M \
  --scenario TN3-explain --output-dir results/RQ3
for q in Q3 Q4; do
  for r in 1 2 3; do
    python3 scripts/bench_v2.py --uri "$URI_SH" "${NODES[@]}" --env SH-range --dataset D1M \
      --scenario TN3-read --query $q --threads 1 --idle-net-s 15 --rep $r --output-dir results/RQ3
  done
done

# 6. TN2-write: ghi mới 4 luồng x 60s x 3 lần (chạy CUỐI CÙNG để thấy 100% ghi mới dồn vào 1 shard)
for r in 1 2 3; do
  python3 scripts/bench_v2.py --uri "$URI_SH" "${NODES[@]}" --env SH-range --dataset D1M \
    --scenario TN2-write --threads 4 --duration 60 --rep $r --output-dir results/RQ2
done
```

### Dọn container sau khi xong
```bash
docker rm -f mdb-mongos mdb-shard1 mdb-shard2 mdb-cfgsvr
docker network rm mdb-net
```

---

## 6. Kết quả cần bàn giao lại
Gửi thư mục `results/RQ2/` và `results/RQ3/` để điền:
- Dòng **`SH-range`** của **Bảng 2** (`% dữ liệu` từ `dist/`, `% lượng ghi s1/s2` từ `status/*_s1.json` & `*_s2.json`, `inserts/s`, `p95`).
- Các cột **`SH-range`** của **Bảng 3** (số máy hỏi của `Q3`, `Q4` từ `explain/`, và `p95` tại `1M`).
