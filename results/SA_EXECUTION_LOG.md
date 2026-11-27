2026-11-27T21:53:37+07:00
# Nhật ký thực nghiệm MongoDB SA

## Kiểm tra ban đầu

- Dự án tại `/home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking`. Ban đầu có bốn ZIP trong `data/` và thư mục .git trống trong phiên sandbox. Tìm thấy hướng dẫn tại `../HUONG_DAN_01_SA.md`, đã đọc toàn bộ và đối chiếu với bản trong repo, nội dung trùng khớp.
- Ubuntu 26.04.1 LTS x86_64, kernel 7.0.0-31-generic, 20 CPU logic, RAM 12 GiB, swap 4 GiB, đĩa còn 22 GiB lúc kiểm tra. Python 3.14.4, Docker CLI 29.1.3, sysstat 12.7.7. Docker socket báo Permission denied trong sandbox. Compose không có, cấu hình SA dùng Docker CLI.
- Git clone trong sandbox không phân giải được github.com. Đã clone ngoài sandbox theo phê duyệt vào `source/`, commit `48bc539544d75c831f1ec560dea636b2ecccf6fc`. Đã rà đường chạy SA trong đặc tả, mã nạp và mã benchmark. Đã tạo môi trường ảo `.venv`. Pip trong sandbox không phân giải được máy chủ gói.
- Hướng dẫn tạo chỉ mục rồi gọi `load_dataset.py --drop`. Mã nguồn xác nhận tùy chọn này xóa cả collection patients lẫn encounters, nên cũng xóa ba chỉ mục. Đã gửi yêu cầu quyết định về chỉ mục và xác nhận kiểm tra Docker.
- Mã benchmark tính rate trong metadata TN1 bằng số truy vấn thành công chia cho elapsed_s bao gồm 20 giây warm-up. CSV chỉ chứa các truy vấn đo. TN2-write giữ các bản ghi thử sau mỗi lần chạy và chúng tiếp tục tồn tại ở mốc D3M khi dùng nguyên quy trình. CPU sampler lấy CPU toàn máy từ /proc/stat.

## SHA-256 đầu vào

ce8dd0af7bd29086f8bd728e7f54a8456d240c161ac95e6d8c38714cdd5493ab  ../HUONG_DAN_01_SA.md
4d1a4709747f86e749c192c31df758c190c784ff5233794ee0111243163d917e  data/D100K-20261127T143339Z-1-001.zip
7eecef6d727ad2e115fab51990e497dd6f0d1a3a1111ffe3bb63a72aff7759ee  data/D1M-20261127T143331Z-1-001.zip
0ae4b96f238582c294d0bf0dfe9099a2a3e10c28bc91c1dfd5f278b19b560cf0  data/D3M-20261127T143337Z-1-001.zip
bdd5db4ca3455460b6d4f538f6106df1b789e0266ee4e9aaebf7f8a62e58bb0b  data/D500K-20261127T143342Z-1-001.zip
2026-11-27T21:53:45+07:00
No errors detected in compressed data of data/D100K-20261127T143339Z-1-001.zip.
No errors detected in compressed data of data/D1M-20261127T143331Z-1-001.zip.
No errors detected in compressed data of data/D3M-20261127T143337Z-1-001.zip.
No errors detected in compressed data of data/D500K-20261127T143342Z-1-001.zip.
cp: warning: behavior of -n is non-portable and may change in future; use --update=none instead
cp: warning: behavior of -n is non-portable and may change in future; use --update=none instead
cp: warning: behavior of -n is non-portable and may change in future; use --update=none instead
cp: warning: behavior of -n is non-portable and may change in future; use --update=none instead
Done S1 (D100K): 100,000 encounters
Done S2 (D500K): 400,000 encounters
Done S3 (D1M): 500,000 encounters
2026-11-27T21:56:05+07:00

## Xác minh công cụ và mã nguồn

WARNING: The directory '/home/benchmark-user/.cache/pip' or its parent directory is not owned or is not writable by the current user. The cache has been disabled. Check the permissions and owner of that directory. If executing pip with sudo, you should use sudo's -H flag.
dnspython==2.9.2
pymongo==4.20.2
WARNING: The directory '/home/benchmark-user/.cache/pip' or its parent directory is not owned or is not writable by the current user. The cache has been disabled. Check the permissions and owner of that directory. If executing pip with sudo, you should use sudo's -H flag.
No broken requirements found.
Hai script hiện CLI help bình thường. Git working tree sạch.
Traceback (most recent call last):
  File "<stdin>", line 30, in <module>
IndexError: list index out of range
2026-11-27T21:56:32+07:00
S4 gặp IndexError vì TSV sau GNU sort có một bản ghi bị tách trên hai dòng (dòng 9232–9233). Giữ lại artifact lỗi. Thử lại S4 với GNU sort một luồng và bộ đệm 256 MiB, giữ nguyên khóa START, LC_ALL=C và sắp xếp ổn định.
S1: xác minh 100000 lượt khám, 1822 bệnh nhân, thứ tự START, ID duy nhất và phân nhóm PATIENT. SHA-256 JSONL encounters: 55bcfd4fa4722665b247a3049e052565aa993dffbe0f312a5369e88e7527c09a
S2: xác minh 400000 lượt khám, 7380 bệnh nhân, thứ tự START, ID duy nhất và phân nhóm PATIENT. SHA-256 JSONL encounters: 2fe649df54d1edca13ef7525f30e6e51c382973892e8534b15d98abe453b8af4
S3: xác minh 500000 lượt khám, 9241 bệnh nhân, thứ tự START, ID duy nhất và phân nhóm PATIENT. SHA-256 JSONL encounters: 4a014c922e6fe59ee9055c8d580b8bbf072e0418166ca15ba4e46569011d1e19
Đính chính: /usr/bin/sort trên Ubuntu này là uutils 0.8.0. Máy cũng có /usr/bin/gnusort. Sẽ dùng GNU sort để đối chiếu nếu lần thử lại không xác minh được.
Traceback (most recent call last):
  File "<stdin>", line 30, in <module>
IndexError: list index out of range
2026-11-27T21:57:16+07:00
uutils sort một luồng vẫn cho TSV lỗi. Chạy lại S4 với GNU sort 9.7, cùng tùy chọn sort của hướng dẫn.
Đã kiểm thử sar lấy mẫu CPU, RAM và I/O đĩa trên máy.
Done S4 (D3M): 2,000,000 encounters
2026-11-27T21:58:18+07:00
2026-11-27T21:58:46+07:00

## Xác minh đối chiếu với D3M

S1 patients.jsonl.gz: 1822 bản ghi, khớp nội dung nguồn D3M; ID duy nhất.
S2 patients.jsonl.gz: 7380 bản ghi, khớp nội dung nguồn D3M; ID duy nhất.
S3 patients.jsonl.gz: 9241 bản ghi, khớp nội dung nguồn D3M; ID duy nhất.
S4 patients.jsonl.gz: 37005 bản ghi, khớp nội dung nguồn D3M; ID duy nhất.
2026-11-27T21:58:54+07:00

## Trạng thái Docker

Docker CLI 29.1.3. Sau khi xin phê duyệt kiểm tra chỉ đọc ngoài sandbox, docker version, docker ps -a và docker image ls vẫn báo Permission denied tại /var/run/docker.sock. Chưa có quyền kiểm tra tên container hoặc image qua daemon. Đang chờ lựa chọn của người dùng về quyền Docker và cách xử lý chỉ mục S1. Chưa chạy MongoDB, TN1 hoặc TN2-write.
S1 encounters.jsonl.gz: 100000 bản ghi, khớp nội dung nguồn D3M; ID duy nhất.
S2 encounters.jsonl.gz: 400000 bản ghi, khớp nội dung nguồn D3M; ID duy nhất.
S3 encounters.jsonl.gz: 500000 bản ghi, khớp nội dung nguồn D3M; ID duy nhất.
2026-11-27T21:59:45+07:00
Xác nhận ngoài sandbox: socket 0660 root:docker; getent group docker có hoangcongthang, nhưng id của tiến trình Codex thiếu GID 123. sg và newgrp không có. Đã cập nhật đề xuất: đăng xuất/đăng nhập để phiên mới nhận nhóm đã cấp, không chạy usermod. Không dùng sudo.
S4 encounters.jsonl.gz: 2000000 bản ghi, khớp nội dung nguồn D3M; ID duy nhất.
4b2a4a43de89380483d5e4c7c9d1bcf3b39a68a1a5e2f664b98f27f74cdca3a1  data/load_v2/S1/encounters.jsonl.gz
e4f8b05f02fb36dfb3d5f717e39e065ce9abef3442001aadd01298bdc4fe79b2  data/load_v2/S1/patients.jsonl.gz
86712d3e950c2b1ce96e027eda6b8341cde76dc496fe9fc68ab9562bb918e5a4  data/load_v2/S2/encounters.jsonl.gz
5e401fed2037e2bc86951254fc073d214c24fa426c2053d1dabc16f8cab7ac91  data/load_v2/S2/patients.jsonl.gz
58d7fec2f9143597ed88cc2a16bf46e7de2ef7002a6760fba9056a07a362c326  data/load_v2/S3/encounters.jsonl.gz
a941db1f4d45f9afb612f9d6e559d9f82e5b154302a00ae2b312f207f09e227d  data/load_v2/S3/patients.jsonl.gz
3a32b1620fccf8fe61f41dd87dd909915d5de039a8b0be1b6878f4fc800ff5aa  data/load_v2/S4/encounters.jsonl.gz
1ce76d193eff24d918214e5772d997abebb6bc15f1cb4859c74f9d32e9b359e0  data/load_v2/S4/patients.jsonl.gz
0ad811e1150cbc7f5782a5edf03e2fc7f042692c385a0f93e9db13a393d093ff  data/D100K/workload_v2.json
5450ffc074db3abb842c1e9177c3fd69ba322170b416c980b1d2ef2352efbee7  data/D1M/workload_v2.json
5f20adc86031429ba513213879b601a68260ac9294802615254e5ae69fb669a0  data/D3M/workload_v2.json
8ff3577e1ecd160222e50f7432a78fcace5bf81d4d1702339571b8076f179e5d  data/D500K/workload_v2.json
2026-11-27T21:59:58+07:00
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p6   49G   31G   16G  66% /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking
2026-11-27T22:05:58+07:00

## Tiếp tục sau khởi động lại

Docker Engine 29.1.3 truy cập được với nhóm docker của tài khoản. Tại kiểm tra ban đầu, không có container, image mongo:7.0 chưa có, cổng 27017 chưa có listener. Dùng lại S1–S4 và workload đã xác minh ở phiên trước.
Người dùng đồng ý xác minh database ehr mới, tạo ba chỉ mục rồi nạp S1 không dùng --drop. --drop xóa collection encounters cùng chỉ mục, làm thay đổi đường thực thi Q1. Cổng host chỉ mở trên loopback, phù hợp URI localhost và MongoDB không bật xác thực.
Unable to find image 'mongo:7.0' locally
7.0: Pulling from library/mongo
caf983e1c374: Pulling fs layer
7ea409122e19: Pulling fs layer
3315360f1e39: Pulling fs layer
ba082564e660: Pulling fs layer
d73fe992c926: Pulling fs layer
524da04abc09: Pulling fs layer
4112fed2e0fa: Pulling fs layer
64a5be57bd8f: Pulling fs layer
caf983e1c374: Download complete
7ea409122e19: Download complete
524da04abc09: Download complete
4112fed2e0fa: Download complete
a3cf077bfadf: Download complete
d73fe992c926: Download complete
3315360f1e39: Download complete
2935ee5bd93a: Download complete
ba082564e660: Download complete
7ea409122e19: Pull complete
ba082564e660: Pull complete
4112fed2e0fa: Pull complete
d73fe992c926: Pull complete
3315360f1e39: Pull complete
524da04abc09: Pull complete
64a5be57bd8f: Download complete
caf983e1c374: Pull complete
64a5be57bd8f: Pull complete
Digest: sha256:41e8195b2791692695e1dc9bd21cd51d0a3af05fff8ace9304a5c1acf94f1ae1
Status: Downloaded newer image for mongo:7.0
901ffaf3a79f66f1d9659503fb4143a06a284cefab78323f350a6266c489668d
Image=sha256:41e8195b2791692695e1dc9bd21cd51d0a3af05fff8ace9304a5c1acf94f1ae1 Memory=1073741824 NanoCpus=2000000000 PortBindings={"27017/tcp":[{"HostIp":"127.0.0.1","HostPort":"27017"}]} Cmd=["mongod","--replSet","rs0","--port","27017","--bind_ip_all","--wiredTigerCacheSizeGB","0.50"]
["mongo@sha256:41e8195b2791692695e1dc9bd21cd51d0a3af05fff8ace9304a5c1acf94f1ae1"]
2026-11-27T15:07:46.540035+00:00 Replica set init: {'ok': 1.0}
2026-11-27T15:07:47.544418+00:00 Initial databases: ['admin', 'config', 'local']
2026-11-27T15:07:47.548865+00:00 MongoDB 7.0.48 WiredTiger configured max bytes=536870912
2026-11-27T15:07:47.583857+00:00 before S1 indexes: [('_id_', [('_id', 1)]), ('PATIENT_1_START_-1', [('PATIENT', 1), ('START', -1)]), ('START_1', [('START', 1)]), ('conditions.CODE_1_START_1', [('conditions.CODE', 1), ('START', 1)])]
2026-11-27T15:07:47.592151+00:00 before S1: collStats count encounters=0, patients=0
2026-11-27T15:07:47.592361+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/load_dataset.py --uri 'mongodb://localhost:27017/?directConnection=true' --dataset data/load_v2/S1 --env SA --meta-out results/load/SA_S1.json
Loaded patients: 1,822 docs in 0.0s (68,618 docs/s)
Loaded encounters: 100,000 docs in 3.6s (27,919 docs/s)
Wrote results/load/SA_S1.json
2026-11-27T15:07:51.751798+00:00 after S1: collStats count encounters=100000, patients=1822
2026-11-27T15:07:51.752209+00:00 after S1 indexes: [('_id_', [('_id', 1)]), ('PATIENT_1_START_-1', [('PATIENT', 1), ('START', -1)]), ('START_1', [('START', 1)]), ('conditions.CODE_1_START_1', [('conditions.CODE', 1), ('START', 1)])]
2026-11-27T15:07:51.752234+00:00 Starting 100K pilot: 9 planned TN1 runs
2026-11-27T15:07:51.752282+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D100K --scenario TN1 --threads 1 --rep 1 --output-dir results/RQ1 --query Q1
DONE SA_D100K_TN1_Q1_t1_r1: n=53710, rate=1074.11/s, p95=1.392ms, net=21.415KB/req, client_cpu_max=8.3% (bound=False)
2026-11-27T15:08:42.657121+00:00 Validated SA_D100K_TN1_Q1_t1_r1: 53710 successful operations, elapsed=50.004s
2026-11-27T15:08:42.657990+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D100K --scenario TN1 --threads 1 --rep 2 --output-dir results/RQ1 --query Q1
DONE SA_D100K_TN1_Q1_t1_r2: n=53931, rate=1078.58/s, p95=1.419ms, net=20.575KB/req, client_cpu_max=8.73% (bound=False)
2026-11-27T15:09:33.487821+00:00 Validated SA_D100K_TN1_Q1_t1_r2: 53931 successful operations, elapsed=50.002s
2026-11-27T15:09:33.488337+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D100K --scenario TN1 --threads 1 --rep 3 --output-dir results/RQ1 --query Q1
DONE SA_D100K_TN1_Q1_t1_r3: n=56088, rate=1121.74/s, p95=1.261ms, net=20.719KB/req, client_cpu_max=12.0% (bound=False)
2026-11-27T15:10:24.365267+00:00 Validated SA_D100K_TN1_Q1_t1_r3: 56088 successful operations, elapsed=50.001s
2026-11-27T15:10:24.365802+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D100K --scenario TN1 --threads 4 --rep 1 --output-dir results/RQ1 --query Q1
DONE SA_D100K_TN1_Q1_t4_r1: n=38121, rate=762.34/s, p95=6.05ms, net=24.894KB/req, client_cpu_max=17.49% (bound=False)
2026-11-27T15:11:15.223227+00:00 Validated SA_D100K_TN1_Q1_t4_r1: 38121 successful operations, elapsed=50.005s
2026-11-27T15:11:15.223552+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D100K --scenario TN1 --threads 4 --rep 2 --output-dir results/RQ1 --query Q1
DONE SA_D100K_TN1_Q1_t4_r2: n=38479, rate=769.5/s, p95=6.057ms, net=24.166KB/req, client_cpu_max=19.1% (bound=False)
2026-11-27T15:12:06.072497+00:00 Validated SA_D100K_TN1_Q1_t4_r2: 38479 successful operations, elapsed=50.005s
2026-11-27T15:12:06.072885+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D100K --scenario TN1 --threads 4 --rep 3 --output-dir results/RQ1 --query Q1
DONE SA_D100K_TN1_Q1_t4_r3: n=51851, rate=1036.92/s, p95=5.302ms, net=20.291KB/req, client_cpu_max=33.59% (bound=False)
2026-11-27T15:12:56.963444+00:00 Validated SA_D100K_TN1_Q1_t4_r3: 51851 successful operations, elapsed=50.005s
2026-11-27T15:12:56.963942+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D100K --scenario TN1 --threads 8 --rep 1 --output-dir results/RQ1 --query Q1
DONE SA_D100K_TN1_Q1_t8_r1: n=41272, rate=825.31/s, p95=12.736ms, net=22.048KB/req, client_cpu_max=26.17% (bound=False)
2026-11-27T15:13:47.840749+00:00 Validated SA_D100K_TN1_Q1_t8_r1: 41272 successful operations, elapsed=50.008s
2026-11-27T15:13:47.841292+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D100K --scenario TN1 --threads 8 --rep 2 --output-dir results/RQ1 --query Q1
DONE SA_D100K_TN1_Q1_t8_r2: n=41584, rate=831.58/s, p95=12.098ms, net=21.883KB/req, client_cpu_max=26.83% (bound=False)
2026-11-27T15:14:38.710934+00:00 Validated SA_D100K_TN1_Q1_t8_r2: 41584 successful operations, elapsed=50.006s
2026-11-27T15:14:38.711273+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D100K --scenario TN1 --threads 8 --rep 3 --output-dir results/RQ1 --query Q1
DONE SA_D100K_TN1_Q1_t8_r3: n=47570, rate=951.25/s, p95=12.239ms, net=20.327KB/req, client_cpu_max=43.19% (bound=False)
2026-11-27T15:15:29.605411+00:00 Validated SA_D100K_TN1_Q1_t8_r3: 47570 successful operations, elapsed=50.008s
2026-11-27T15:15:29.605770+00:00 PILOT_VALID: all 9 runs validated and CPU below stop threshold; using pilot as D100K TN1
2026-11-27T15:15:29.605828+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/load_dataset.py --uri 'mongodb://localhost:27017/?directConnection=true' --dataset data/load_v2/S2 --env SA --meta-out results/load/SA_S2.json
Loaded patients: 7,380 docs in 0.1s (80,899 docs/s)
Loaded encounters: 400,000 docs in 18.4s (21,694 docs/s)
Wrote results/load/SA_S2.json
2026-11-27T15:15:48.760091+00:00 after S2: collStats count encounters=500000, patients=9202
2026-11-27T15:15:48.760685+00:00 after S2 indexes: [('_id_', [('_id', 1)]), ('PATIENT_1_START_-1', [('PATIENT', 1), ('START', -1)]), ('START_1', [('START', 1)]), ('conditions.CODE_1_START_1', [('conditions.CODE', 1), ('START', 1)])]
2026-11-27T15:15:48.760749+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D500K --scenario TN1 --threads 1 --rep 1 --output-dir results/RQ1 --query Q1
DONE SA_D500K_TN1_Q1_t1_r1: n=17115, rate=342.27/s, p95=3.833ms, net=19.804KB/req, client_cpu_max=23.84% (bound=False)
2026-11-27T15:16:39.506743+00:00 Validated SA_D500K_TN1_Q1_t1_r1: 17115 successful operations, elapsed=50.004s
2026-11-27T15:16:39.506919+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D500K --scenario TN1 --threads 1 --rep 2 --output-dir results/RQ1 --query Q1
DONE SA_D500K_TN1_Q1_t1_r2: n=17584, rate=351.65/s, p95=4.177ms, net=20.483KB/req, client_cpu_max=20.54% (bound=False)
2026-11-27T15:17:30.288816+00:00 Validated SA_D500K_TN1_Q1_t1_r2: 17584 successful operations, elapsed=50.004s
2026-11-27T15:17:30.288998+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D500K --scenario TN1 --threads 1 --rep 3 --output-dir results/RQ1 --query Q1
DONE SA_D500K_TN1_Q1_t1_r3: n=17035, rate=340.69/s, p95=4.032ms, net=20.72KB/req, client_cpu_max=17.94% (bound=False)
2026-11-27T15:18:21.025637+00:00 Validated SA_D500K_TN1_Q1_t1_r3: 17035 successful operations, elapsed=50.001s
2026-11-27T15:18:21.025816+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D500K --scenario TN1 --threads 4 --rep 1 --output-dir results/RQ1 --query Q1
DONE SA_D500K_TN1_Q1_t4_r1: n=25751, rate=514.9/s, p95=21.627ms, net=18.104KB/req, client_cpu_max=24.29% (bound=False)
2026-11-27T15:19:11.789152+00:00 Validated SA_D500K_TN1_Q1_t4_r1: 25751 successful operations, elapsed=50.012s
2026-11-27T15:19:11.789377+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D500K --scenario TN1 --threads 4 --rep 2 --output-dir results/RQ1 --query Q1
DONE SA_D500K_TN1_Q1_t4_r2: n=25941, rate=518.38/s, p95=20.42ms, net=17.882KB/req, client_cpu_max=30.24% (bound=False)
2026-11-27T15:20:02.570735+00:00 Validated SA_D500K_TN1_Q1_t4_r2: 25941 successful operations, elapsed=50.042s
2026-11-27T15:20:02.570958+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D500K --scenario TN1 --threads 4 --rep 3 --output-dir results/RQ1 --query Q1
DONE SA_D500K_TN1_Q1_t4_r3: n=25569, rate=511.35/s, p95=21.38ms, net=18.421KB/req, client_cpu_max=35.63% (bound=False)
2026-11-27T15:20:53.331891+00:00 Validated SA_D500K_TN1_Q1_t4_r3: 25569 successful operations, elapsed=50.003s
2026-11-27T15:20:53.332142+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D500K --scenario TN1 --threads 8 --rep 1 --output-dir results/RQ1 --query Q1
DONE SA_D500K_TN1_Q1_t8_r1: n=16813, rate=336.14/s, p95=65.891ms, net=22.319KB/req, client_cpu_max=38.37% (bound=False)
2026-11-27T15:21:44.070862+00:00 Validated SA_D500K_TN1_Q1_t8_r1: 16813 successful operations, elapsed=50.018s
2026-11-27T15:21:44.071038+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D500K --scenario TN1 --threads 8 --rep 2 --output-dir results/RQ1 --query Q1
DONE SA_D500K_TN1_Q1_t8_r2: n=15650, rate=312.94/s, p95=67.253ms, net=22.41KB/req, client_cpu_max=29.77% (bound=False)
2026-11-27T15:22:34.782015+00:00 Validated SA_D500K_TN1_Q1_t8_r2: 15650 successful operations, elapsed=50.01s
2026-11-27T15:22:34.782195+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D500K --scenario TN1 --threads 8 --rep 3 --output-dir results/RQ1 --query Q1
DONE SA_D500K_TN1_Q1_t8_r3: n=17903, rate=357.61/s, p95=64.529ms, net=20.663KB/req, client_cpu_max=33.03% (bound=False)
2026-11-27T15:23:25.584179+00:00 Validated SA_D500K_TN1_Q1_t8_r3: 17903 successful operations, elapsed=50.063s
2026-11-27T15:23:25.584362+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/load_dataset.py --uri 'mongodb://localhost:27017/?directConnection=true' --dataset data/load_v2/S3 --env SA --meta-out results/load/SA_S3.json
Loaded patients: 9,241 docs in 0.1s (84,196 docs/s)
Loaded encounters: 500,000 docs in 37.3s (13,412 docs/s)
Wrote results/load/SA_S3.json
2026-11-27T15:24:03.269818+00:00 after S3: collStats count encounters=1000000, patients=18443
2026-11-27T15:24:03.270678+00:00 after S3 indexes: [('_id_', [('_id', 1)]), ('PATIENT_1_START_-1', [('PATIENT', 1), ('START', -1)]), ('START_1', [('START', 1)]), ('conditions.CODE_1_START_1', [('conditions.CODE', 1), ('START', 1)])]
2026-11-27T15:24:03.270749+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D1M --scenario TN1 --threads 1 --rep 1 --output-dir results/RQ1 --query Q1
DONE SA_D1M_TN1_Q1_t1_r1: n=10369, rate=207.37/s, p95=6.438ms, net=19.285KB/req, client_cpu_max=22.15% (bound=False)
2026-11-27T15:24:53.988474+00:00 Validated SA_D1M_TN1_Q1_t1_r1: 10369 successful operations, elapsed=50.003s
2026-11-27T15:24:53.988599+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D1M --scenario TN1 --threads 1 --rep 2 --output-dir results/RQ1 --query Q1
DONE SA_D1M_TN1_Q1_t1_r2: n=9362, rate=187.21/s, p95=7.697ms, net=20.037KB/req, client_cpu_max=21.33% (bound=False)
2026-11-27T15:25:44.708515+00:00 Validated SA_D1M_TN1_Q1_t1_r2: 9362 successful operations, elapsed=50.007s
2026-11-27T15:25:44.708666+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D1M --scenario TN1 --threads 1 --rep 3 --output-dir results/RQ1 --query Q1
DONE SA_D1M_TN1_Q1_t1_r3: n=9705, rate=194.09/s, p95=7.319ms, net=20.04KB/req, client_cpu_max=17.86% (bound=False)
2026-11-27T15:26:35.400205+00:00 Validated SA_D1M_TN1_Q1_t1_r3: 9705 successful operations, elapsed=50.002s
2026-11-27T15:26:35.400334+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D1M --scenario TN1 --threads 4 --rep 1 --output-dir results/RQ1 --query Q1
DONE SA_D1M_TN1_Q1_t4_r1: n=17079, rate=341.35/s, p95=41.318ms, net=17.14KB/req, client_cpu_max=25.18% (bound=False)
2026-11-27T15:27:26.152282+00:00 Validated SA_D1M_TN1_Q1_t4_r1: 17079 successful operations, elapsed=50.034s
2026-11-27T15:27:26.152460+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D1M --scenario TN1 --threads 4 --rep 2 --output-dir results/RQ1 --query Q1
DONE SA_D1M_TN1_Q1_t4_r2: n=16396, rate=327.87/s, p95=41.641ms, net=17.407KB/req, client_cpu_max=23.81% (bound=False)
2026-11-27T15:28:16.898909+00:00 Validated SA_D1M_TN1_Q1_t4_r2: 16396 successful operations, elapsed=50.008s
2026-11-27T15:28:16.899078+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D1M --scenario TN1 --threads 4 --rep 3 --output-dir results/RQ1 --query Q1
DONE SA_D1M_TN1_Q1_t4_r3: n=16267, rate=324.93/s, p95=41.334ms, net=17.236KB/req, client_cpu_max=28.2% (bound=False)
2026-11-27T15:29:07.648546+00:00 Validated SA_D1M_TN1_Q1_t4_r3: 16267 successful operations, elapsed=50.063s
2026-11-27T15:29:07.648746+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D1M --scenario TN1 --threads 8 --rep 1 --output-dir results/RQ1 --query Q1
DONE SA_D1M_TN1_Q1_t8_r1: n=8189, rate=163.49/s, p95=86.896ms, net=23.108KB/req, client_cpu_max=30.41% (bound=False)
2026-11-27T15:29:58.444628+00:00 Validated SA_D1M_TN1_Q1_t8_r1: 8189 successful operations, elapsed=50.09s
2026-11-27T15:29:58.444816+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D1M --scenario TN1 --threads 8 --rep 2 --output-dir results/RQ1 --query Q1
DONE SA_D1M_TN1_Q1_t8_r2: n=8005, rate=159.8/s, p95=88.691ms, net=22.478KB/req, client_cpu_max=29.79% (bound=False)
2026-11-27T15:30:49.234918+00:00 Validated SA_D1M_TN1_Q1_t8_r2: 8005 successful operations, elapsed=50.094s
2026-11-27T15:30:49.235021+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D1M --scenario TN1 --threads 8 --rep 3 --output-dir results/RQ1 --query Q1
DONE SA_D1M_TN1_Q1_t8_r3: n=8454, rate=168.93/s, p95=86.029ms, net=22.19KB/req, client_cpu_max=34.24% (bound=False)
2026-11-27T15:31:39.953714+00:00 Validated SA_D1M_TN1_Q1_t8_r3: 8454 successful operations, elapsed=50.044s
2026-11-27T15:31:39.959054+00:00 before TN2-write r1: collStats count encounters=1000000, patients=18443
2026-11-27T15:31:39.959123+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D1M --scenario TN2-write --threads 4 --rep 1 --output-dir results/RQ2 --duration 60
DONE SA_D1M_TN2-write_t4_r1: n=93678, rate=1560.65/s, p95=3.763ms, net=0.892KB/req, client_cpu_max=25.55% (bound=False)
2026-11-27T15:32:40.912351+00:00 Validated SA_D1M_TN2-write_t4_r1: 93678 successful operations, elapsed=60.025s
2026-11-27T15:32:40.919338+00:00 after TN2-write r1: collStats count encounters=1093678, patients=18443
2026-11-27T15:32:40.924138+00:00 before TN2-write r2: collStats count encounters=1093678, patients=18443
2026-11-27T15:32:40.924188+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D1M --scenario TN2-write --threads 4 --rep 2 --output-dir results/RQ2 --duration 60
DONE SA_D1M_TN2-write_t4_r2: n=86257, rate=1437.47/s, p95=3.938ms, net=0.892KB/req, client_cpu_max=27.13% (bound=False)
2026-11-27T15:33:41.850105+00:00 Validated SA_D1M_TN2-write_t4_r2: 86257 successful operations, elapsed=60.006s
2026-11-27T15:33:41.857060+00:00 after TN2-write r2: collStats count encounters=1179935, patients=18443
2026-11-27T15:33:41.862392+00:00 before TN2-write r3: collStats count encounters=1179935, patients=18443
2026-11-27T15:33:41.862444+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D1M --scenario TN2-write --threads 4 --rep 3 --output-dir results/RQ2 --duration 60
DONE SA_D1M_TN2-write_t4_r3: n=89784, rate=1496.23/s, p95=3.861ms, net=0.892KB/req, client_cpu_max=27.16% (bound=False)
2026-11-27T15:34:42.880268+00:00 Validated SA_D1M_TN2-write_t4_r3: 89784 successful operations, elapsed=60.007s
2026-11-27T15:34:42.885527+00:00 after TN2-write r3: collStats count encounters=1269719, patients=18443
2026-11-27T15:34:42.889848+00:00 before S4: collStats count encounters=1269719, patients=18443
2026-11-27T15:34:42.889864+00:00 TN2-write added 269719 docs retained at D3M according to the guide's cumulative sequence
2026-11-27T15:34:42.889902+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/load_dataset.py --uri 'mongodb://localhost:27017/?directConnection=true' --dataset data/load_v2/S4 --env SA --meta-out results/load/SA_S4.json
Loaded patients: 37,005 docs in 0.5s (69,325 docs/s)
Loaded encounters: 2,000,000 docs in 299.3s (6,682 docs/s)
Wrote results/load/SA_S4.json
2026-11-27T15:39:43.374689+00:00 after S4: collStats count encounters=3269719, patients=55448
2026-11-27T15:39:43.375510+00:00 after S4 indexes: [('_id_', [('_id', 1)]), ('PATIENT_1_START_-1', [('PATIENT', 1), ('START', -1)]), ('START_1', [('START', 1)]), ('conditions.CODE_1_START_1', [('conditions.CODE', 1), ('START', 1)])]
2026-11-27T15:39:43.375585+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D3M --scenario TN1 --threads 1 --rep 1 --output-dir results/RQ1 --query Q1
DONE SA_D3M_TN1_Q1_t1_r1: n=2188, rate=43.74/s, p95=31.852ms, net=20.519KB/req, client_cpu_max=16.19% (bound=False)
2026-11-27T15:40:34.175654+00:00 Validated SA_D3M_TN1_Q1_t1_r1: 2188 successful operations, elapsed=50.028s
2026-11-27T15:40:34.175778+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D3M --scenario TN1 --threads 1 --rep 2 --output-dir results/RQ1 --query Q1
DONE SA_D3M_TN1_Q1_t1_r2: n=2567, rate=51.33/s, p95=26.089ms, net=20.569KB/req, client_cpu_max=18.2% (bound=False)
2026-11-27T15:41:24.918518+00:00 Validated SA_D3M_TN1_Q1_t1_r2: 2567 successful operations, elapsed=50.009s
2026-11-27T15:41:24.918599+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D3M --scenario TN1 --threads 1 --rep 3 --output-dir results/RQ1 --query Q1
DONE SA_D3M_TN1_Q1_t1_r3: n=2940, rate=58.78/s, p95=24.443ms, net=22.386KB/req, client_cpu_max=19.42% (bound=False)
2026-11-27T15:42:15.645021+00:00 Validated SA_D3M_TN1_Q1_t1_r3: 2940 successful operations, elapsed=50.017s
2026-11-27T15:42:15.645105+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D3M --scenario TN1 --threads 4 --rep 1 --output-dir results/RQ1 --query Q1
DONE SA_D3M_TN1_Q1_t4_r1: n=7906, rate=158.06/s, p95=47.035ms, net=16.59KB/req, client_cpu_max=30.64% (bound=False)
2026-11-27T15:43:06.354980+00:00 Validated SA_D3M_TN1_Q1_t4_r1: 7906 successful operations, elapsed=50.018s
2026-11-27T15:43:06.355098+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D3M --scenario TN1 --threads 4 --rep 2 --output-dir results/RQ1 --query Q1
DONE SA_D3M_TN1_Q1_t4_r2: n=8461, rate=169.19/s, p95=44.279ms, net=15.896KB/req, client_cpu_max=19.83% (bound=False)
2026-11-27T15:43:57.072829+00:00 Validated SA_D3M_TN1_Q1_t4_r2: 8461 successful operations, elapsed=50.01s
2026-11-27T15:43:57.072962+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D3M --scenario TN1 --threads 4 --rep 3 --output-dir results/RQ1 --query Q1
DONE SA_D3M_TN1_Q1_t4_r3: n=7656, rate=152.99/s, p95=48.697ms, net=16.448KB/req, client_cpu_max=29.93% (bound=False)
2026-11-27T15:44:47.834683+00:00 Validated SA_D3M_TN1_Q1_t4_r3: 7656 successful operations, elapsed=50.043s
2026-11-27T15:44:47.834783+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D3M --scenario TN1 --threads 8 --rep 1 --output-dir results/RQ1 --query Q1
DONE SA_D3M_TN1_Q1_t8_r1: n=3863, rate=77.04/s, p95=113.448ms, net=19.269KB/req, client_cpu_max=26.24% (bound=False)
2026-11-27T15:45:38.686817+00:00 Validated SA_D3M_TN1_Q1_t8_r1: 3863 successful operations, elapsed=50.141s
2026-11-27T15:45:38.686924+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D3M --scenario TN1 --threads 8 --rep 2 --output-dir results/RQ1 --query Q1
DONE SA_D3M_TN1_Q1_t8_r2: n=4136, rate=82.64/s, p95=109.499ms, net=18.175KB/req, client_cpu_max=25.37% (bound=False)
2026-11-27T15:46:29.441649+00:00 Validated SA_D3M_TN1_Q1_t8_r2: 4136 successful operations, elapsed=50.048s
2026-11-27T15:46:29.441744+00:00 /home/benchmark-user/Downloads/DBMS-distributed-method-benchmarking/.venv/bin/python source/scripts/bench_v2.py --uri 'mongodb://localhost:27017/?directConnection=true' --env SA --dataset D3M --scenario TN1 --threads 8 --rep 3 --output-dir results/RQ1 --query Q1
DONE SA_D3M_TN1_Q1_t8_r3: n=3974, rate=79.25/s, p95=110.85ms, net=18.933KB/req, client_cpu_max=23.32% (bound=False)
2026-11-27T15:47:20.286018+00:00 Validated SA_D3M_TN1_Q1_t8_r3: 3974 successful operations, elapsed=50.148s
2026-11-27T15:47:20.286535+00:00 COMPLETE: 36 TN1 and 3 TN2-write runs validated and summarized. TN1 rate uses benchmark metadata denominator including warm-up.
2026-11-27T22:47:35+07:00

## Kiểm tra bàn giao

Container=/mdb-sa Running=true OOMKilled=false RestartCount=0
Đủ 36 CSV/meta/status TN1 và 3 CSV/meta/status TN2-write, 4 metadata nạp, 13 dòng tổng hợp và log sar. Git working tree của mã nguồn sạch.
Gói bàn giao gồm results, nhật ký, đặc tả/hướng dẫn và hai tập lệnh upstream tại commit đã ghi. Dữ liệu đầu vào được tham chiếu bằng SHA-256 trong nhật ký. Container được giữ để bảo toàn dữ liệu.
