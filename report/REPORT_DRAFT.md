# Phân tích Cơ chế và Đánh giá Thực nghiệm Sharding trên MongoDB với Dữ liệu Hồ sơ Bệnh án Điện tử (Synthea EHR)

> [!NOTE] Mục đích của bản Markdown này
> Đây là bản sao định dạng **Markdown (Obsidian-friendly)** khớp 100% nội dung với bộ mã nguồn LaTeX trong thư mục `report/` (`main.pdf`). Mỗi mục đều ghi chú rõ tên file `.tex` tương ứng để bạn dễ dàng đọc, review, đánh dấu chỉnh sửa và cập nhật ngược lại vào LaTeX.

- **Kho lưu trữ GitHub:** https://github.com/DatHoang-git/DBMS-distributed-method-benchmarking
- **Mẫu LaTeX:** UET-VNU (`report/main.tex` → `report/main.pdf`)

---

## Thông tin Trang bìa (`cover/bia-ngoai.tex`, `cover/bia-trong.tex`)

- **Nhóm thực hiện:** Nhóm 5
- **Thành viên:**
  - Đỗ Hoàng Đạt — `24020060`
  - Nguyễn Thị Ngọc Mai — `22025510`
  - Hoàng Công Thắng — `24022832`
- **Lớp học phần:** `INT3202 1`
- **Giảng viên hướng dẫn:** TS. Nguyễn Thị Cẩm Vân

---

## Tóm tắt (`cover/tom-tat.tex`)

Sự tăng trưởng nhanh chóng của dữ liệu hồ sơ bệnh án điện tử (*Electronic Health Records — EHR*) đặt ra thách thức mở rộng hiệu năng đọc và ghi vượt quá giới hạn phần cứng của một máy chủ cơ sở dữ liệu đơn lẻ. Đề tài này tập trung phân tích cơ chế hoạt động bên trong và đánh giá thực nghiệm chiến lược phân mảnh ngang phân tán (*Horizontal Sharding*) tích hợp sẵn của MongoDB trên tập dữ liệu tổng hợp Synthea EHR ở bốn mốc quy mô từ $100{,}000$ đến $3{,}000{,}000$ lượt khám bệnh.

Về mặt lý thuyết, báo cáo làm rõ sự khác biệt bản chất giữa kỹ thuật phân vùng bảng trên một máy chủ (*Single-node Partitioning*) trong các hệ quản trị cơ sở dữ liệu quan hệ và kỹ thuật phân mảnh ngang đa nút (*Multi-node Horizontal Sharding*) trong MongoDB, đồng thời giải thích cơ chế định tuyến mục tiêu giúp loại bỏ các mảnh dữ liệu không liên quan khi thực thi truy vấn (*Shard Pruning*). Về mặt thực nghiệm, hệ thống được triển khai trên hạ tầng điện toán đám mây Microsoft Azure với dung lượng bộ nhớ đệm được kiểm soát chặt chẽ, đối chiếu cấu hình máy chủ đơn lẻ với cụm phân mảnh một nút và hai nút (áp dụng hai chiến lược phân mảnh theo hàm băm và theo khoảng giá trị) nhằm trả lời ba câu hỏi nghiên cứu: (1) ngưỡng quy mô dữ liệu để cụm phân mảnh vượt qua máy chủ đơn lẻ về độ trễ đọc và mức tách bạch giữa chi phí điều phối với lợi ích mở rộng bộ nhớ đệm; (2) mức độ đồng đều phân bố dữ liệu và tải ghi giữa chiến lược phân mảnh băm và phân mảnh theo khoảng khi dữ liệu phân bố lệch tự nhiên và lệch nặng ($1\%$ bệnh nhân chiếm $30\%$ lượt khám); và (3) chi phí định lượng của truy vấn xuyên mảnh cũng như mức độ ảnh hưởng chéo khi trộn tải truy vấn giao dịch với truy vấn phân tích.

> [!TODO] Cập nhật sau thực nghiệm
> Các chỉ số kết quả định lượng (ngưỡng quy mô hòa vốn, hệ số tăng tốc ghi và hệ số chi phí xuyên mảnh) sẽ được bổ sung vào phần tóm tắt sau khi hoàn tất thực nghiệm trên cụm Azure.

**Từ khóa:** *MongoDB, Horizontal Sharding, Shard Pruning, Synthea EHR, Cơ sở dữ liệu phân tán, Đánh giá hiệu năng.*

---

## Danh mục các từ viết tắt (`cover/viet-tat.tex`)

| Viết tắt | Tiếng Anh | Giải nghĩa |
| :--- | :--- | :--- |
| **BSON** | Binary JSON | Định dạng nhị phân biểu diễn tài liệu trong MongoDB. |
| **CI** | Confidence Interval | Khoảng tin cậy thống kê (mặc định $95\%$ trong báo cáo). |
| **CSRS** | Config Server Replica Set | Cụm máy chủ cấu hình lưu siêu dữ liệu định tuyến của cụm sharded. |
| **DBMS** | Database Management System | Hệ quản trị cơ sở dữ liệu. |
| **EHR** | Electronic Health Record | Hồ sơ bệnh án điện tử. |
| **MVCC** | Multi-Version Concurrency Control | Cơ chế kiểm soát tương tranh đa phiên bản. |
| **OLAP** | Online Analytical Processing | Tải truy vấn phân tích, tổng hợp dữ liệu diện rộng. |
| **OLTP** | Online Transaction Processing | Tải giao dịch trực tuyến tốc độ cao, truy cập điểm. |
| **QPS** | Queries Per Second | Thông lượng truy vấn mỗi giây. |
| **RDBMS** | Relational DBMS | Hệ quản trị cơ sở dữ liệu quan hệ. |
| **RQ** | Research Question | Câu hỏi nghiên cứu (`RQ1`–`RQ3`). |
| **SA** | Standalone | Môi trường MongoDB chạy đơn nút (1-node replica set). |
| **VM** | Virtual Machine | Máy ảo triển khai trên hạ tầng đám mây Azure. |
| **WT** | WiredTiger | Bộ máy lưu trữ (Storage Engine) mặc định của MongoDB. |

---

# Mở đầu (`chapter/Chap0_MoDau.tex`)

## 1. Bối cảnh và Lý do chọn đề tài

Trong các hệ thống thông tin y tế hiện đại, dữ liệu hồ sơ bệnh án điện tử (*Electronic Health Records — EHR*) mang hai đặc trưng nổi bật: tính **bán cấu trúc** (*semi-structured*) và tốc độ tăng trưởng liên tục theo thời gian. Khác với dữ liệu có cấu trúc chặt chẽ trong các bảng quan hệ truyền thống — nơi mọi bản ghi đều phải tuân theo một tập cột cố định — dữ liệu bán cấu trúc cho phép mỗi bản ghi chứa các thuộc tính tùy chọn và các thành phần lồng nhau có số lượng biến thiên lớn. Cụ thể, trong một lượt khám bệnh, bệnh nhân này có thể chỉ có một mã chẩn đoán cơ bản, trong khi bệnh nhân khác lại phát sinh hàng chục kết quả xét nghiệm và chẩn đoán đi kèm. Khi quy mô dữ liệu tích lũy qua nhiều năm vượt quá dung lượng bộ nhớ đệm RAM của một máy chủ cơ sở dữ liệu đơn lẻ, hiệu năng hệ thống suy giảm mạnh do tần suất đọc/ghi ổ đĩa tăng đột biến và hiện tượng tranh chấp tài nguyên xử lý.

Giải pháp mở rộng theo chiều dọc (*scale-up* — nâng cấp phần cứng trên cùng một máy chủ) sớm chạm trần chi phí và giới hạn vật lý. Do đó, mở rộng theo chiều ngang thông qua phân mảnh dữ liệu phân tán (*Horizontal Sharding*) trở thành giải pháp kiến trúc quan trọng trong các hệ quản trị cơ sở dữ liệu hiện đại [Kleppmann2017]. Tuy nhiên, phân mảnh ngang không mang lại cải thiện hiệu năng tuyệt đối trong mọi tình huống: hệ thống luôn phải đánh đổi giữa lợi ích chia tải bộ nhớ đệm và I/O trên nhiều máy chủ với chi phí điều phối mạng qua tầng định tuyến, rủi ro phân bố dữ liệu không đều (*data skew*) và chi phí thu gom kết quả của các truy vấn phải quét qua nhiều mảnh dữ liệu (*cross-shard queries*).

MongoDB là một trong những hệ quản trị cơ sở dữ liệu hướng tài liệu phổ biến nhất hỗ trợ sẵn cơ chế phân mảnh ngang phân tán [MongoDBSharding]. Việc nghiên cứu cơ chế bên trong và đánh giá định lượng hiệu năng sharding của MongoDB trên tập dữ liệu y tế mô phỏng sát thực tế Synthea EHR [Walonoski2018] giúp trả lời những câu hỏi thiết thực về mặt kỹ thuật: *từ quy mô dữ liệu nào sharding bắt đầu phát huy hiệu quả, chiến lược chọn khóa phân mảnh nào chịu được dữ liệu lệch tốt hơn, và chi phí thực tế của các truy vấn phân tích xuyên mảnh lớn tới mức nào*.

## 2. Phạm vi nghiên cứu và Câu hỏi nghiên cứu

Nhằm đi sâu vào bản chất kỹ thuật thay vì khảo sát dàn trải trên nhiều hệ quản trị khác nhau, đề tài giới hạn phạm vi thực nghiệm tập trung vào **một hệ quản trị duy nhất (`MongoDB`)** và **một bài toán dữ liệu chính (`Synthea EHR`)**, khảo sát qua bốn mốc quy mô từ $100{,}000$ đến $3{,}000{,}000$ bản ghi lượt khám (`encounters`, tương ứng khoảng $1{,}822$ đến $55{,}448$ bệnh nhân tổng hợp).

| Mã | Trọng tâm | Nội dung câu hỏi nghiên cứu |
| :--- | :--- | :--- |
| **RQ1** | Mở rộng đọc & Ngưỡng quy mô | Từ quy mô dữ liệu nào (`100K → 3M` lượt khám) thì cụm MongoDB phân mảnh theo hàm băm đạt hiệu năng đọc tốt hơn máy chủ đơn lẻ (Standalone); chi phí điều phối của bộ định tuyến trung gian và lợi ích chia đôi bộ nhớ đệm được tách bạch như thế nào dưới tải đơn luồng và đa luồng? |
| **RQ2** | Phân bố dữ liệu & Tải ghi khi lệch | Khi dữ liệu phân bố lệch (lệch tự nhiên và lệch nặng) dưới tải thiên về ghi, hai chiến lược phân mảnh theo hàm băm (*Hashed*) và theo khoảng giá trị (*Ranged*) phân bố dữ liệu (số bản ghi, dung lượng, số mảnh) và lưu lượng ghi giữa các nút đồng đều đến mức nào, đồng thời thông lượng ghi tăng được bao nhiêu so với máy chủ đơn lẻ? |
| **RQ3** | Tỉa mảnh & Chi phí xuyên mảnh | Trên cụm phân mảnh, cơ chế định tuyến chỉ vào một mảnh dữ liệu duy nhất khác biệt thế nào với truy vấn quét xuyên nhiều mảnh về kế hoạch thực thi, lưu lượng mạng, tốc độ tăng độ trễ theo quy mô `100K → 3M`, và mức độ ảnh hưởng chéo khi trộn đồng thời hai loại truy vấn này? |

## 3. Mục tiêu và Nội dung thực hiện

- **Phân tích có hệ thống cơ chế hoạt động bên trong của MongoDB Sharding:** Làm rõ mối quan hệ giữa kiến trúc lưu trữ lõi của MongoDB với cơ chế phân mảnh ngang đa nút, giải phẫu quy trình định tuyến truy vấn, sự khác biệt giữa chiến lược khóa phân mảnh theo hàm băm và theo khoảng, cũng như cơ chế chia mảnh dữ liệu và cân bằng tải nền.
- **Thiết kế và triển khai thực nghiệm có kiểm soát biến:** Xây dựng bốn cấu hình đối chứng (máy chủ đơn lẻ, cụm 1 shard có bộ định tuyến, cụm 2 shard theo hàm băm và cụm 2 shard theo khoảng) với giới hạn bộ nhớ đệm cố định, cho phép tách riêng chi phí điều phối mạng khỏi lợi ích chia tải bộ nhớ và đo lường định lượng các chỉ số độ trễ, thông lượng và tài nguyên hệ thống.
- **Tổng hợp khuyến nghị thiết kế và đánh giá giới hạn thực nghiệm:** Từ kết quả định lượng, đề xuất định hướng lựa chọn kiến trúc lưu trữ và khóa phân mảnh phù hợp cho từng đặc trưng tải công việc EHR, kèm theo phân tích thẳng thắn các yếu tố ảnh hưởng đến độ giá trị thực nghiệm (*Threats to Validity*).

## 4. Bố cục của báo cáo

- *Chương 1. Giới thiệu và Triển khai MongoDB:* Trình bày các thành phần kiến trúc nền tảng của MongoDB (mô hình tài liệu, bộ máy lưu trữ WiredTiger, chỉ mục B-Tree và tập bản sao Replica Set) cùng tổng quan mô hình triển khai cụm thử nghiệm trên hạ tầng đám mây Microsoft Azure.
- *Chương 2. Cơ chế Hoạt động của MongoDB Sharding:* Phân biệt bản chất giữa phân vùng đơn nút và phân mảnh ngang đa nút, trình bày kiến trúc cụm sharded, cơ chế định tuyến và tỉa mảnh (*Shard Pruning*), so sánh chiến lược *Hashed* với *Ranged*, cơ chế chia chunk và tiến trình Balancer.
- *Chương 3. Phương pháp và Thiết kế Thực nghiệm:* Đặc tả cấu trúc dữ liệu lượt khám tối giản, sáu bộ dữ liệu Synthea, bộ bốn truy vấn đại diện (`Q1–Q4`), hệ thống chỉ mục đồng nhất, quy chuẩn đo đạc tài nguyên và các công thức đánh giá cho `RQ1–RQ3`.
- *Chương 4. Kết quả Thực nghiệm và Phân tích Kỹ thuật:* Trình bày và phân tích định lượng kết quả thu thập được cho từng câu hỏi nghiên cứu `RQ1`, `RQ2` và `RQ3`.
- *Chương 5. Khuyến nghị Thiết kế, Giới hạn và Kết luận:* Đề xuất ma trận lựa chọn chiến lược phân mảnh cho hệ thống EHR, thảo luận các giới hạn thực nghiệm (*Threats to Validity*) và tổng kết hướng phát triển.
- *Phụ lục A và Phụ lục B:* Tổng hợp chi tiết thông số phần cứng máy ảo Azure, cổng dịch vụ, tham số cấu hình MongoDB cố định, mẫu cấu trúc tài liệu JSON và mã truy vấn MongoDB chính xác của bộ `Q1–Q4`.

---

# Chương 1. Giới thiệu và Triển khai MongoDB (`chapter/Chap1_GioiThieuMongoDB.tex`)

## 1.1. Tổng quan kiến trúc nền tảng của MongoDB

### 1.1.1. Mô hình dữ liệu hướng tài liệu

MongoDB là hệ quản trị cơ sở dữ liệu NoSQL hướng tài liệu (*document-oriented DBMS*), được thiết kế phù hợp với các bài toán dữ liệu bán cấu trúc như hồ sơ bệnh án điện tử [MongoDBSharding]. Đơn vị lưu trữ cơ bản trong MongoDB là **tài liệu** (*document*) — một cấu trúc gồm các cặp khóa–giá trị tương tự định dạng JSON, cho phép nhúng trực tiếp các mảng hoặc tài liệu con bên trong một bản ghi duy nhất. Trên thực tế, MongoDB mã hóa các tài liệu này dưới dạng nhị phân gọi là **BSON** (*Binary JSON*) để hỗ trợ thêm các kiểu dữ liệu chuyên biệt (như kiểu thời gian `ISODate`, kiểu số nguyên 64-bit) và rút ngắn thời gian phân tích dữ liệu khi đọc ghi.

Các tài liệu có cùng mục đích nghiệp vụ được tổ chức thành từng **collection**. Có thể hình dung một *collection* trong MongoDB đóng vai trò tương đương với một *bảng* (*table*) trong cơ sở dữ liệu quan hệ (RDBMS), còn mỗi *tài liệu* tương ứng với một *hàng* (*row*). Điểm khác biệt căn bản là các tài liệu trong cùng một collection không bị ràng buộc phải sở hữu cùng một tập trường cố định; nhờ vậy, toàn bộ thông tin chẩn đoán và xét nghiệm của một lượt khám bệnh có thể được lưu gói gọn trong một tài liệu thuộc collection `encounters` mà không cần tách bảng và thực hiện phép nối phức tạp.

### 1.1.2. Bộ máy lưu trữ WiredTiger

Để tổ chức lưu trữ các tài liệu BSON xuống ổ đĩa và xử lý đồng thời nhiều yêu cầu truy cập, MongoDB sử dụng tầng bộ máy lưu trữ (*storage engine*). Kể từ phiên bản 3.2, **WiredTiger** trở thành bộ máy lưu trữ mặc định của MongoDB [MongoDBWiredTiger], thay thế cho bộ máy tiền nhiệm là **MMAPv1**.

**Kiểm soát tương tranh ở mức tài liệu:** Trong môi trường cơ sở dữ liệu nhiều người dùng, khi nhiều luồng xử lý cùng đọc và ghi dữ liệu tại một thời điểm sẽ phát sinh hiện tượng *tương tranh* (xung đột tài nguyên và nguy cơ sai lệch dữ liệu). Ở bộ máy lưu trữ tiền nhiệm **MMAPv1**, MongoDB áp dụng cơ chế khóa ở phạm vi rộng (khóa mức toàn bộ cơ sở dữ liệu hoặc mức toàn bộ collection), khiến nhiều thao tác ghi vào các tài liệu hoàn toàn khác nhau trong cùng một collection vẫn bị xung đột khóa và phải xếp hàng chờ đợi nhau. WiredTiger khắc phục nút thắt này bằng cơ chế **kiểm soát tương tranh ở mức tài liệu** (*document-level concurrency control*) kết hợp với **kiểm soát tương tranh đa phiên bản** (*Multi-Version Concurrency Control — MVCC*). Nhờ lưu giữ các ảnh chụp dữ liệu (*snapshot*) nhất quán theo phiên bản, các luồng đọc không bị chặn bởi luồng ghi và nhiều luồng ghi trên các tài liệu khác nhau trong cùng một collection có thể thực thi song song mà không xảy ra xung đột khóa.

**Cơ chế bộ nhớ đệm hai tầng và mối liên hệ với RQ1:** Hiệu năng đọc của MongoDB phụ thuộc chặt chẽ vào cách WiredTiger phối hợp hai tầng bộ nhớ đệm trên máy chủ:
- **WiredTiger Internal Cache:** Là vùng bộ nhớ đệm nội bộ do chính tiến trình MongoDB cấp phát và quản lý (mặc định chiếm khoảng $50\%$ dung lượng $\text{RAM} - 1\text{ GB}$). Trên ổ đĩa, dữ liệu được lưu ở dạng nén để tiết kiệm dung lượng lưu trữ và giảm băng thông I/O; khi được nạp vào WiredTiger Internal Cache, các tài liệu và nút chỉ mục sẽ được giải nén sang định dạng bộ nhớ làm việc để bộ xử lý truy vấn thao tác trực tiếp với độ trễ thấp nhất.
- **Filesystem Cache:** Là vùng bộ nhớ đệm tệp tin của hệ điều hành Linux (tận dụng phần RAM còn dư ngoài WiredTiger Internal Cache). Tầng này lưu giữ các khối dữ liệu còn ở dạng nén vừa được đọc từ ổ đĩa, đóng vai trò lớp đệm trung gian giúp tránh việc phải truy cập trực tiếp xuống ổ đĩa vật lý khi một trang dữ liệu bị đẩy ra khỏi WiredTiger Internal Cache nhưng sớm được truy vấn lại.

Cơ chế bộ nhớ đệm hai tầng này dẫn trực tiếp đến khái niệm **tập dữ liệu làm việc** (*working set*) — tổng dung lượng của các tài liệu đang hoạt động và các chỉ mục thường xuyên được truy cập. Khi kích thước *working set* nhỏ hơn dung lượng WiredTiger Internal Cache, phần lớn truy vấn được phục vụ hoàn toàn trong RAM với độ trễ rất ổn định. Ngược lại, khi quy mô dữ liệu tăng lên làm *working set* vượt quá giới hạn bộ nhớ đệm nội bộ, WiredTiger buộc phải liên tục đẩy các trang nhớ cũ ra khỏi bộ nhớ đệm (*cache eviction*) để nhường chỗ nạp trang mới từ Filesystem Cache hoặc từ ổ đĩa (*pages read into cache*). Sự gia tăng đột biến của thao tác đọc đĩa này làm độ trễ truy vấn tăng vọt trên một máy chủ đơn lẻ — và chính là nút thắt kỹ thuật đặt nền móng cho **câu hỏi nghiên cứu RQ1**: xác định mốc quy mô dữ liệu tại đó việc chia nhỏ *working set* ra nhiều máy chủ độc lập mang lại lợi ích bộ nhớ đệm đủ lớn để bù đắp chi phí điều phối mạng của cụm phân tán.

### 1.1.3. Chỉ mục B-Tree và Tập bản sao (Replica Set)

Bên cạnh việc giữ dữ liệu nóng trong bộ nhớ đệm WiredTiger, tốc độ định vị bản ghi trên các collection chứa hàng triệu tài liệu phụ thuộc quyết định vào cấu trúc chỉ mục. MongoDB xây dựng các chỉ mục dựa trên cấu trúc cây cân bằng **B-Tree** (cụ thể là biến thể B+Tree trong WiredTiger), hỗ trợ từ chỉ mục đơn trường, chỉ mục phức hợp trên nhiều trường (ví dụ kết hợp mã bệnh nhân và thời điểm khám) cho đến chỉ mục đa khóa (*multikey index*) cho phép đánh chỉ mục từng phần tử bên trong trường mảng như danh sách mã chẩn đoán. Vì toàn bộ chỉ mục đang được sử dụng đều cần nằm trong *working set* để tránh quét đĩa ngẫu nhiên, dung lượng chỉ mục cũng là một thành phần quan trọng quyết định thời điểm tràn bộ nhớ đệm ở quy mô lớn.

Tuy nhiên, việc tối ưu hóa tốc độ đọc ghi trên một máy chủ đơn lẻ thông qua WiredTiger và chỉ mục B-Tree vẫn chưa đủ cho các hệ thống thực tế: một tiến trình cơ sở dữ liệu độc lập luôn tồn tại điểm lỗi đơn lẻ (*single point of failure*) và dễ gián đoạn dịch vụ khi gặp sự cố phần cứng. Để giải quyết yêu cầu sẵn sàng cao (*High Availability*) và khả năng chịu lỗi, MongoDB tổ chức các máy chủ dữ liệu thành **Tập bản sao** (*Replica Set*). Một Replica Set gồm nhiều tiến trình `mongod` duy trì cùng một tập dữ liệu, trong đó một nút chính (*Primary*) tiếp nhận toàn bộ thao tác ghi và ghi nhận thay đổi vào nhật ký thao tác (*operations log — oplog*), còn các nút phụ (*Secondary*) đọc `oplog` để đồng bộ dữ liệu và sẵn sàng bầu chọn làm Primary mới nếu nút chính gặp sự cố.

Trong kiến trúc MongoDB hiện đại, Replica Set không chỉ là cơ chế dự phòng cho một cụm đơn lẻ mà còn đóng vai trò là đơn vị lưu trữ nền tảng cấu thành nên từng mảnh dữ liệu khi mở rộng hệ thống ra nhiều máy chủ. Khi tổng dung lượng *working set* và lưu lượng ghi vượt quá giới hạn của một Replica Set đơn lẻ, MongoDB áp dụng cơ chế phân mảnh ngang phân tán (*Native Horizontal Sharding*) — nội dung sẽ được phân tích chuyên sâu và có hệ thống trong **Chương 2**.

## 1.2. Tổng quan mô hình triển khai trên Microsoft Azure

Để đánh giá định lượng hiệu năng MongoDB trong điều kiện tiệm cận thực tế mạng phân tán thay vì mô phỏng toàn bộ trên một máy đơn, cụm thực nghiệm của đề tài được triển khai trên nền tảng điện toán đám mây **Microsoft Azure for Students** [AzureStudents]. Do gói tài khoản giáo dục áp đặt hạn mức cứng từ $4$ đến $6\text{ vCPU}$ trên mỗi vùng địa lý (*region*), mô hình triển khai được thiết kế tinh gọn theo ba nguyên tắc cốt lõi sau:

1. **Phân tách vai trò nút trong cùng mạng ảo nội bộ:** Toàn bộ máy ảo được đặt trong cùng một mạng ảo (*Virtual Network — VNet*) để đảm bảo độ trễ truyền tin nội bộ thấp và ổn định. Kiến trúc tách bạch ba nhóm nút chức năng: nút sinh tải và thu thập số liệu (`vm-client`), nút điều phối cụm (`vm-coord`) và tối đa hai nút dữ liệu đối xứng (`vm-w1`, `vm-w2`). Trong cấu hình đối chứng đơn nút (`SA`), nút điều phối và nút dữ liệu thứ hai được tắt hoàn toàn để client kết nối trực tiếp vào một máy chủ MongoDB duy nhất.
2. **Chuẩn hóa hai cấu hình tài nguyên và kiểm soát chặt bộ nhớ đệm:** Tùy theo hạn mức vCPU được cấp phát thực tế tại vùng triển khai, hệ thống hỗ trợ hai cấu hình chuẩn là **Profile A** (tổng $4\text{ vCPU}$, giới hạn WiredTiger Cache ở mức $0.75\text{ GB}$ mỗi nút dữ liệu) và **Profile B** (tổng $6\text{ vCPU}$, giới hạn WiredTiger Cache ở mức $1.5\text{ GB}$ mỗi nút dữ liệu). Việc ấn định mức bộ nhớ đệm cố định này bảo đảm tập dữ liệu lớn nhất của thực nghiệm ($3\text{ triệu}$ lượt khám, *working set* ước tính khoảng $4.97\text{ GB}$) vượt xa dung lượng RAM đệm trên một máy chủ đơn lẻ, qua đó tái hiện chính xác hiện tượng tràn cache cần khảo sát.
3. **Kiểm thử khô cục bộ trước khi vận hành trên đám mây:** Toàn bộ pipeline nạp dữ liệu, thiết lập chỉ mục và kịch bản đo được chạy kiểm thử khô (*Pha 0 — Docker Dry-run*) trên môi trường Docker cục bộ với tập dữ liệu nhỏ nhất ($100{,}000$ lượt khám) trước khi triển khai chính thức trên Azure.

Toàn bộ bảng đối chiếu cấu hình phần cứng chi tiết giữa Profile A và Profile B, sơ đồ cổng dịch vụ của từng máy ảo, bộ tham số cố định của MongoDB và danh mục kiểm tra xác minh cụm vận hành được trình bày đầy đủ tại **Phụ lục A** và lưu trữ tại kho GitHub của nhóm [ProjectRepo].

---

# Chương 2. Cơ chế Hoạt động của MongoDB Sharding (`chapter/Chap2_CoCheSharding.tex`)

## 2.1. Bài toán Mở rộng Dữ liệu: Phân vùng Đơn nút và Phân mảnh Đa nút

### 2.1.1. Phân biệt Single-node Partitioning và Multi-node Horizontal Sharding

Khi dung lượng dữ liệu và lưu lượng truy vấn vượt quá khả năng xử lý hiệu quả của một bảng hoặc một máy chủ đơn lẻ (như nút thắt bộ nhớ đệm ở Chương 1), các hệ quản trị cơ sở dữ liệu thường áp dụng chiến lược chia nhỏ dữ liệu. Tuy nhiên, hai kỹ thuật *Partitioning* (phân vùng trên một máy chủ) và *Sharding* (phân mảnh phân tán trên nhiều máy chủ) thường bị sử dụng lẫn lộn dù giải quyết hai lớp bài toán kiến trúc khác nhau [Kleppmann2017]. Làm rõ ranh giới này giúp xác định chính xác mục tiêu mở rộng vượt trần phần cứng mà đề tài theo đuổi.

| Khía cạnh | Single-node Partitioning (RDBMS) | Multi-node Horizontal Sharding (MongoDB) |
| :--- | :--- | :--- |
| **Mục tiêu chính** | Giảm không gian quét chỉ mục/bảng trên cùng một máy chủ; hỗ trợ quản trị vòng đời dữ liệu (xóa nhanh phân vùng cũ, lưu trữ phân tầng). | Vượt trần phần cứng (RAM, CPU, Disk I/O) của một máy chủ đơn lẻ bằng cách chia tải ra nhiều nút độc lập (*scale-out*). |
| **Phạm vi tài nguyên** | Toàn bộ phân vùng dùng chung CPU, RAM, bộ nhớ đệm và kênh I/O của một nút vật lý. | Mỗi mảnh (*shard*) sở hữu tiến trình `mongod`, bộ nhớ đệm WiredTiger, CPU và đĩa riêng biệt. |
| **Cơ chế định tuyến** | Bộ tối ưu hóa truy vấn cục bộ (*Query Planner*) loại bỏ phân vùng không khớp ngay trong cùng tiến trình DB. | Tiến trình định tuyến trung gian đọc siêu dữ liệu cụm để chuyển tiếp yêu cầu qua mạng tới đúng shard đích. |
| **Chi phí phát sinh** | Chi phí lập kế hoạch thấp; không phát sinh độ trễ mạng giữa các phân vùng. | Phát sinh chi phí mạng qua tầng định tuyến, đồng bộ siêu dữ liệu và gom kết quả xuyên nút khi truy vấn không khớp khóa phân mảnh. |

### 2.1.2. Tối ưu phạm vi truy vấn phân tán: Cơ chế Shard Pruning

Một lợi ích quan trọng khi chia nhỏ dữ liệu là tránh phải quét những phần dữ liệu không liên quan đến điều kiện truy vấn. Trong các hệ quản trị quan hệ có phân vùng bảng, cơ chế này được gọi là tỉa phân vùng (*Partition Pruning*). Khi chuyển sang kiến trúc phân mảnh ngang đa nút của MongoDB, nguyên lý tối ưu tương ứng được thể hiện qua cơ chế **Shard Pruning** (định tuyến mục tiêu — *Targeted Routing*) [MongoDBExplain], chia truy vấn đọc thành hai chế độ thực thi đối lập:

- **Truy vấn định tuyến mục tiêu (`SINGLE_SHARD`):** Điều kiện lọc chứa đầy đủ khóa phân mảnh (hoặc tiền tố phù hợp của khóa phân mảnh theo khoảng) → bộ định tuyến chỉ gửi yêu cầu đến đúng một shard duy nhất chứa dữ liệu cần tìm.
- **Truy vấn phát tán–thu gom (`SHARD_MERGE` / `SHARD_MERGE_SORT`):** Truy vấn không chứa khóa phân mảnh → bộ định tuyến buộc phải phát tán đến *tất cả* các shard, thu thập kết quả trung gian qua mạng, trộn hoặc sắp xếp lại trước khi trả về.

## 2.2. Kiến trúc cụm Sharded của MongoDB

Một cụm phân mảnh (*Sharded Cluster*) của MongoDB gồm ba thành phần phối hợp chặt chẽ [MongoDBSharding]:
- **Shard (`mongod --shardsvr`):** Mỗi shard là một Replica Set độc lập lưu trữ một tập con dữ liệu của toàn cụm; toàn bộ đọc ghi thực thi trực tiếp trên WiredTiger của các shard liên quan.
- **Config Server (`mongod --configsvr`):** Một Replica Set chuyên biệt (`cfgRS`) lưu giữ toàn bộ siêu dữ liệu (*metadata*) của cụm trong cơ sở dữ liệu hệ thống `config` (`config.chunks`, `config.collections`, `config.settings`, `config.changelog`).
- **Query Router (`mongos`):** Tiến trình trung gian không lưu dữ liệu người dùng (*stateless router*) tiếp nhận mọi kết nối từ ứng dụng, đọc siêu dữ liệu từ Config Server vào bộ nhớ đệm cục bộ để định tuyến truy vấn và tổng hợp kết quả.

Dựa trên **Khóa phân mảnh (*Shard Key*)**, MongoDB chia không gian dữ liệu thành các **Chunk** (mỗi chunk là một khoảng liên tục giá trị Shard Key, dung lượng mục tiêu cố định $32\text{ MB}$ trong thực nghiệm). Tiến trình nền **Balancer** chạy trên nút Primary của Config Server giám sát sự chênh lệch giữa các shard và tự động di chuyển chunk (*chunk migration*) khi cụm mất cân bằng.

## 2.3. Cơ chế định tuyến, Chiến lược Shard Key và Cân bằng tải

### 2.3.1. Quy trình định tuyến của `mongos` và Phân rã độ trễ

Khi nhận truy vấn, `mongos` tra cứu bảng định tuyến cục bộ (tự làm mới từ Config Server nếu gặp *stale config*), chuyển tiếp yêu cầu qua mạng nội bộ và tổng hợp kết quả. Với truy vấn xuyên shard (`SHARD_MERGE`), tổng độ trễ bị chi phối bởi nút chậm nhất (*straggler effect*) cộng chi phí mạng và trộn tại `mongos`:

$$T_{\text{total}} \approx \max\big(T_{\text{shard1}},\, T_{\text{shard2}}\big) + T_{\text{network + merge}}$$

*(Với các truy vấn phân tích trả về ít kết quả như Top-10, thực thi song song trên nhiều shard có thể rút ngắn $\max(T_{\text{shard1}}, T_{\text{shard2}})$ — tạo sự đánh đổi giữa **Shard Pruning** và **Parallel Scan**).*

### 2.3.2. So sánh chiến lược Hashed Sharding và Ranged Sharding

- **Hashed Sharding (`{PATIENT: "hashed"}`):** Băm 64-bit phân bổ đều dữ liệu và lưu lượng ghi mới ngay từ lúc khởi tạo (kết hợp `numInitialChunks: 16`). Mọi truy vấn lọc theo `PATIENT` đạt `SINGLE_SHARD`, nhưng phá vỡ tính cục bộ theo khoảng (*range locality*) nên truy vấn theo `START` buộc phải chạy `SHARD_MERGE`.
- **Ranged Sharding (`{START: 1, PATIENT: 1}`):** Bảo toàn tính cục bộ theo khoảng thời gian, hỗ trợ *Shard Pruning* (`SINGLE_SHARD`) nếu cửa sổ thời gian nằm gọn trong 1 chunk. Nhược điểm: rất dễ gặp **điểm nóng ghi (*Write Hotspot*)** khi khóa tăng đơn điệu (`START = now()`), dồn $100\%$ lưu lượng ghi OLTP vào chunk cuối chứa `MaxKey` trên **một shard duy nhất**.

### 2.3.3. Cơ chế chia Chunk, Jumbo Chunk và Tiến trình Balancer

- **Chia Chunk (Split):** Khi chunk vượt $32\text{ MB}$, MongoDB tách thành 2 chunk nhỏ hơn (thao tác thuần siêu dữ liệu, không di chuyển vật lý).
- **Jumbo Chunk:** Khi dữ liệu lệch nặng làm một giá trị Shard Key đơn lẻ vượt quá $32\text{ MB}$ (không có điểm chia hợp lệ), MongoDB gắn cờ `jumbo: true` trong `config.chunks`; Balancer không thể di chuyển tự động các Jumbo Chunk.
- **Balancer:** Di chuyển chunk nền tiêu tốn mạng/CPU/I/O, nên thực nghiệm chỉ bật Balancer ở pha chờ cân bằng của `R2-1`, `R2-4` và tắt hoàn toàn (`sh.stopBalancer()`) trước mọi pha đo Read và OLTP Write.

---

# Chương 3. Phương pháp và Thiết kế Thực nghiệm (`chapter/Chap3_ThietKeThucNghiem.tex`)

## 3.1. Mô hình hóa Dữ liệu và Schema Synthea Tối giản

Mỗi tài liệu trong collection `encounters` biểu diễn **1 lượt khám bệnh**, chỉ giữ lại các thuộc tính cốt lõi (`_id`, `PATIENT`, `ORGANIZATION`, `ENCOUNTERCLASS`, `START` ở kiểu ngày giờ nhị phân) cùng hai mảng nhúng tối giản là danh sách mã chẩn đoán (`conditions`) và kết quả xét nghiệm (`observations`). Cấu trúc JSON mẫu đầy đủ được trình bày tại **Phụ lục B**.

- Kích thước trung bình thực tế (`D100K`): **$1{,}248.7\text{ B}$ JSON** ($\approx 1{,}366.3\text{ B}$ BSON).
- Ngoại suy cho **`D3M`**: $\approx 3.82\text{ GB}$ BSON giải nén + $1.15\text{ GB}$ chỉ mục $\approx \mathbf{4.97\text{ GB}}$ *working set* ($\approx 1.91\text{ GB}$ nén trên đĩa) → vượt xa trần WiredTiger Internal Cache trên một máy chủ đơn lẻ ở cả Profile A ($0.75\text{ GB}$) và Profile B ($1.5\text{ GB}$).

## 3.2. Đặc tả Sáu Bộ Dữ liệu Thực nghiệm (Số liệu thật từ `DATASET_SUMMARY.json`)

| Mã dataset | Số `encounters` | Số `PATIENT` | TB khám/BN | TB JSON (B) | Gzip (MB) | Mục đích sử dụng |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| `D100K` | 100,000 | 1,822 | 54.88 | 1,248.7 | 11.44 | `RQ1`, `RQ3`, Pha 0 dry-run |
| `D500K` | 500,000 | 9,202 | 54.34 | 1,272.6 | 70.79 | `RQ1`, `RQ3` |
| `D1M` | 1,000,000 | 18,443 | 54.22 | 1,271.4 | 144.65 | `RQ1`, `RQ3` |
| `D3M` | 3,000,000 | 55,448 | 54.10 | 1,273.6 | 440.78 | `RQ1`, `RQ3` |
| `D1M-nat` | 1,000,000 | 18,443 | 54.22 | 1,271.4 | 144.65 | `RQ2` (Natural Skew, liên kết `D1M`) |
| `D1M-heavy` | 1,000,000 | 13,000 | 76.92 | 1,229.3 | 138.45 | `RQ2` (`R2-4`: $1\%$ BN = 130 BN chiếm $30\%$ = 300K docs) |

Các tập lồng nhau theo nguyên nhóm `PATIENT` (`D100K ⊂ D500K ⊂ D1M ⊂ D3M`), cố định `SEED = 42` kèm `patient_ids.txt` và `query_params.json`.

## 3.3. Bộ Truy vấn Đại diện (`Q1`–`Q4`) và Hệ thống Chỉ mục

Bảng tóm tắt mục đích nghiệp vụ và định tuyến kỳ vọng của bốn truy vấn đại diện (mã MongoDB chính xác xem tại **Phụ lục B**):

| Mã | Nhóm | Mục đích nghiệp vụ & Điều kiện lọc chính | Định tuyến kỳ vọng |
| :--- | :---: | :--- | :--- |
| `Q1` | $P$ | Truy xuất 10 lượt khám gần nhất của một bệnh nhân (lọc `PATIENT`, sắp xếp giảm dần theo `START`). | `SINGLE_SHARD` trên `SH-hash` |
| `Q2` | $P$ | Tổng hợp kết quả xét nghiệm (`laboratory`) trong 12 tháng gần nhất của một bệnh nhân (lọc `PATIENT` + `START`, bung mảng `observations`). | `SINGLE_SHARD` trên `SH-hash` |
| `Q3` | $X$ | Thống kê Top 10 mã bệnh phổ biến nhất trong một quý (lọc khoảng `START`, gom nhóm theo mã chẩn đoán, kết quả nhỏ). | `SHARD_MERGE` trên `SH-hash`; `SINGLE_SHARD` trên `SH-range` |
| `Q4` | $X$ | Liệt kê các lượt khám chẩn đoán tiểu đường type 2 (mã `44054006`) trong một tháng (lọc mã bệnh + khoảng `START`, kết quả dài). | `SHARD_MERGE` trên `SH-hash`; `SINGLE_SHARD` trên `SH-range` |

- **Quy tắc chọn cửa sổ `Q3/Q4`:** Kiểm tra biên chunk qua `sh.status()` trên `SH-range` để bảo đảm `qStart..qEnd` và `mStart..mEnd` nằm trọn trong **1 chunk duy nhất**.
- **Bộ 4 chỉ mục đồng nhất** (loại bỏ sai lệch giữa quét toàn bộ collection `COLLSCAN` và quét chỉ mục B-Tree `IXSCAN`):
  1. `{PATIENT: 1, START: -1}`
  2. `{START: 1}`
  3. `{"conditions.CODE": 1, START: 1}` *(chỉ mục đa khóa)*
  4. `{ENCOUNTERCLASS: 1, START: 1}`
  *(Kèm index Shard Key tương ứng: `{PATIENT: "hashed"}` cho `B1/SH-hash`, `{START: 1, PATIENT: 1}` cho `SH-range`.)*

## 3.4. Ma trận Môi trường, Quy chuẩn Đo đạc và Công thức Phân tích

### 3.4.1. Bốn môi trường kiểm soát biến

| Mã `env` | Kiến trúc | Shard Key (`encounters`) | Mục đích kiểm soát biến |
| :--- | :--- | :--- | :--- |
| `SA` | Standalone (1-node RS) | Không shard | Baseline không qua `mongos`; client nối thẳng 1 nút dữ liệu duy nhất. |
| `B1` | Sharded 1 shard | `{PATIENT: "hashed"}` | Qua `mongos` nhưng 1 shard → cô lập chi phí điều phối (*coordination overhead*). |
| `SH-hash` | Sharded 2 shards | `{PATIENT: "hashed"}` | Khởi tạo sẵn 16 chunk (`numInitialChunks: 16`); đánh giá scale-out đọc/ghi và `SHARD_MERGE`. |
| `SH-range` | Sharded 2 shards | `{START: 1, PATIENT: 1}` | Đối chứng cho điểm nóng ghi (`RQ2`) và Shard Pruning theo thời gian (`RQ3`). |

### 3.4.2. Quy trình đo, Thu thập chỉ số hệ thống và Ma trận 12 kịch bản

- **Read (`R1-2`, `R1-3`, `R3-2`, `R3-4`):** 10s làm nóng bộ nhớ đệm (*warm-up*) → 30s đo chính thức → 10s nghỉ × 3 lần lặp.
- **OLTP Write (`R2-2`, `R2-3`):** 10s warm-up → 60s đo (6 cửa sổ 10s) → 15s nghỉ × 3 lần lặp.
- **Chỉ số thống kê & Telemetry:** Báo cáo các phân vị độ trễ `p50` (trung vị), `p95` (độ trễ đuôi chính), `p99` kèm khoảng tin cậy $95\%$ (`95% CI`); thu song song tài nguyên OS bằng `sar` (*System Activity Reporter*, 1 giây/lần) và bộ đếm nội bộ MongoDB qua `db.serverStatus()`. Kịch bản `R2-3` sử dụng **phân phối Zipf** ($\theta = 1.2$) — phân phối quy luật lũy thừa mô phỏng nhóm nhỏ bệnh nhân phát sinh tỷ trọng lớn lưu lượng ghi mới (*hot patients*).

| RQ | Mã | Tên kịch bản | Thiết lập chính & Chỉ số thu thập |
| :--- | :--- | :--- | :--- |
| **RQ1** | `R1-1` | Kích thước & tỷ lệ cache | `collStats` trên 4 datasets × 3 envs; `(Data + Index) / Cache`. |
| **RQ1** | `R1-2` | Latency 1 luồng | `Q1`, `Q2` riêng, 1 luồng (72 lượt); `p50/p95/p99`, tỷ lệ trúng cache, số trang đọc đĩa. |
| **RQ1** | `R1-3` | Quét đa luồng | Trộn `Q1:Q2 = 50:50` ở 1/4/8 (Profile A) hoặc 1/4/16 luồng (Profile B) trên `D100K, D1M, D3M`. |
| **RQ1** | `R1-4` | Cold Cache (tùy chọn) | `D3M`, khởi động lại `mongod` + xóa page cache hệ điều hành, đo 30s đầu không warm-up. |
| **RQ2** | `R2-1` | Nạp hàng loạt & Balancer | `D1M-nat`, `insert_many` lô 500–1000 docs, `ordered=False`; tốc độ nạp, phân bố shard, số lần di chuyển chunk. |
| **RQ2** | `R2-2` | Ghi OLTP lệch tự nhiên | Ghi mới (`START=now()`), chọn `PATIENT` đều, 4/8 luồng, 60s × 3 reps; `inserts/s`, `% insert/shard` mỗi 10s. |
| **RQ2** | `R2-3` | Ghi OLTP lệch truy cập | Giống `R2-2` nhưng chọn `PATIENT` theo phân phối Zipf ($\theta = 1.2$). |
| **RQ2** | `R2-4` | Lệch dữ liệu nặng | Nạp `D1M-heavy` trên `SH-hash` và `SH-range`; `max/avg`, `Imbalance (%)`, `jumbo_chunks`. |
| **RQ3** | `R3-1` | Giải phẫu `explain` | 5 bộ tham số cho `Q1–Q4`; kế hoạch thắng cuộc, tỷ lệ Shard Pruning, số khóa/tài liệu quét, thời gian từng shard. |
| **RQ3** | `R3-2` | Latency 1 luồng (`Q3, Q4`) | `Q3`, `Q4` trên `SA`, `SH-hash`, `SH-range` qua 4 datasets (ghép cùng `Q1, Q2` từ `R1-2`). |
| **RQ3** | `R3-3` | Lưu lượng mạng | Chênh lệch `serverStatus().network` trên `mongos`; số KB trung bình/truy vấn. |
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
| Quy mô nhỏ, *working set* nằm gọn trong bộ nhớ đệm 1 nút | **Standalone / Replica Set (`SA`)** | Tránh chi phí mạng, chi phí điều phối `mongos` và độ phức tạp quản trị cụm sharded. |
| Thiên về OLTP theo bệnh nhân (`Q1, Q2`) và ghi mới liên tục (`START = now()`) | **Hashed Sharding (`{PATIENT: "hashed"}`)** | Bảo đảm `SINGLE_SHARD` cho truy vấn bệnh nhân và rải đều lưu lượng ghi mới, triệt tiêu điểm nóng ghi (*write hotspot*). |
| Thiên về báo cáo định kỳ theo khung thời gian (`Q3, Q4`), tải ghi theo lô | **Ranged Sharding (`{START: 1, PATIENT: 1}`)** | Tận dụng *Shard Pruning* theo khoảng thời gian; cần tách riêng hoặc chấp nhận nút thắt ghi tại biên `MaxKey`. |
| Hỗn hợp OLTP nặng + phân tích xuyên bệnh nhân ($X \ge 10\text{–}30\%$) | **Hashed Sharding + Cô lập tải** | Tránh nhiễu chéo từ `SHARD_MERGE` lên `p95` nhóm `P`; sản xuất nên hướng truy vấn phân tích sang nút Secondary (`readPreference: secondary`) hoặc kho phân tích riêng. |

> [!TODO] Cập nhật định lượng cho Mục 5.1
> Bổ sung mốc *break-even* cụ thể, hệ số tăng tốc ghi và mức suy giảm `p95` nhóm `P` từ Chương 4 sau khi có số liệu thực.

## 5.2. Giới hạn Thực nghiệm (*Threats to Validity*)

1. **Replica Set 1 thành viên trên mỗi shard (*Internal/Construct Validity*):** Do hạn mức 4–6 vCPU của Azure Student, chính sách xác nhận ghi đa số (`writeConcern: {w: "majority"}`) tương đương `w: 1`, không phản ánh độ trễ đồng bộ nhật ký thao tác `oplog` qua mạng tới nút Secondary như trong môi trường sản xuất (3 thành viên/shard). Tuy nhiên bản chất định tuyến `mongos`, chia chunk và khác biệt Hashed/Ranged vẫn giữ nguyên.
2. **Giới hạn bộ nhớ đệm nhân tạo và cụm 2 shard (*External Validity*):** Thu nhỏ WiredTiger Internal Cache (`0.75/1.5 GB`) và kích thước chunk (`32 MB`) có chủ đích để kích hoạt tràn cache ở `3M` docs. Xu hướng định tính khái quát hóa tốt, nhưng trị tuyệt đối (ms) gắn với cấu hình phần cứng thử nghiệm cụ thể.
3. **Đặc thù VM dòng B-series trên đám mây công cộng (nếu dùng Profile A):** Dù kiểm soát hạn mức CPU (*CPU credit*) $\ge 50\%$ trước mỗi pha, nhiễu tài nguyên từ các máy ảo thuê chung hạ tầng vật lý (*noisy neighbor*) vẫn có thể gây ngoại lai ở `p99`; do đó dùng `p95` kèm $95\%\text{ CI}$ qua 3 lần lặp làm chỉ số kết luận chính.
4. **Dữ liệu tổng hợp Synthea và schema tối giản (*Ecological Validity*):** Giữ kích thước tài liệu quanh `1.27 KB` tối ưu cho Standard SSD nhưng nhẹ hơn hồ sơ bệnh án thực tế chứa nhiều ghi chú văn bản tự do.

## 5.3. Kết luận và Hướng phát triển

> [!TODO] Hoàn thiện Mục 5.3
> Sau khi có Chương 4, tổng kết ngắn gọn ba phát hiện định lượng tương ứng `RQ1`, `RQ2`, `RQ3`.

- **Hướng phát triển:** (1) Mở rộng lên 3–4 shard với Replica Set 3 thành viên/shard (1 Primary, 2 Secondary) để đo độ trễ `w: "majority"` và cô lập tải bằng tùy chọn đọc từ nút phụ (`readPreference: "secondary"`); (2) Khảo sát khóa phân mảnh băm phức hợp (*Compound Hashed Shard Key*, ví dụ `{PATIENT: "hashed", START: 1}`) và phân mảnh theo vùng (*Zone Sharding*).

---

# Phụ lục A. Chi tiết Cấu hình Hạ tầng và Tham số Triển khai MongoDB (`appendix/AppendixA_CauHinhHaTang.tex`)

## A.1. Đối chiếu Hai Cấu hình Máy ảo trên Azure for Students

| Tiêu chí | Profile A (4 vCPU tổng) | Profile B (6 vCPU tổng) |
| :--- | :--- | :--- |
| **Điều kiện áp dụng** | An toàn $100\%$ trên mọi tài khoản Azure Student. | Ưu tiên khi region cấp 6 vCPU hoặc ghép 2 tài khoản. |
| **Nút dữ liệu (`vm-w1`, `vm-w2`)** | $2 \times$ `Standard_B1ms` (1 vCPU, 2 GB RAM/VM). | $2 \times$ `Standard_D2s_v5` / `D2s_v3` (2 vCPU, 8 GB RAM/VM, không giới hạn CPU credit). |
| **Nút điều phối & Client** | Biến thể 3 VM: `vm-coord` dùng `Standard_B2s` (2 vCPU, 4 GB RAM, chạy chung `mongos`, Config Server và `bench.py`); hoặc 4 VM dùng $4 \times$ `B1ms`. | Tách riêng `vm-coord` (`Standard_B1ms`) và `vm-client` (`Standard_B1ms`). |
| **WiredTiger Cache** | `cacheSizeGB = 0.75` (768 MB) | `cacheSizeGB = 1.5` (1536 MB) |
| **Giới hạn RAM systemd** | `MemoryMax = 1.4G` | `MemoryMax = 3G` |
| **Kiểm soát B-series** | Kiểm tra CPU credit $\ge 50\%$ trên mọi VM trước mỗi pha; nghỉ 10–15 phút nếu tụt $< 40\%$. | Không bị bóp CPU credit trên hai nút dữ liệu dòng D. |
| **Ổ đĩa lưu trữ** | Standard SSD (`E4` 32 GB hoặc `E6` 64 GB), tắt Availability Zones. | Standard SSD (`E4` 32 GB hoặc `E6` 64 GB), tắt Availability Zones. |

## A.2. Phân công Vai trò và Cổng Dịch vụ theo Máy ảo

| Hostname | Vai trò trong cụm Sharded (`B1`, `SH-hash`, `SH-range`) | Vai trò trong `SA` |
| :--- | :--- | :--- |
| `vm-client` | Chạy `bench.py` (`pymongo` + `multiprocessing`), thu CSV độ trễ & metadata; giữ CPU $< 80\%$ (hoặc $< 75\%$ nếu ghép trên `vm-coord`). | Kết nối trực tiếp tới `vm-w1:27017`. |
| `vm-coord` | Chạy `mongos` (cổng `27017`) và Config Server (`--configsvr --replSet cfgRS`, cổng `27019`). | Tắt / Deallocate. |
| `vm-w1` | Chạy Shard 1 (`--shardsvr --replSet shard1RS`, cổng `27018`). | Chạy `mongod` đơn nút (`rs0`, cổng `27017`). |
| `vm-w2` | Chạy Shard 2 (`--shardsvr --replSet shard2RS`, cổng `27018`); chỉ bật ở `SH-hash`, `SH-range`. | Tắt / Deallocate. |

## A.3. Bộ Tham số MongoDB Cố định và Quy trình Xác minh Cụm

- **Phiên bản DBMS:** Thống nhất một phiên bản MongoDB Community (`7.0` hoặc `8.0`) trên toàn cụm; tự động ghi vào metadata JSON.
- **Kích thước Chunk:** Cố định `32 MB` (`{_id: "chunksize", value: 32}` trong `config.settings`).
- **Chính sách nhất quán đọc/ghi:** `writeConcern: {w: "majority"}`, `readConcern: {level: "local"}`.
- **Collection phụ `patients`:** Luôn phân mảnh theo `{_id: "hashed"}` ở mọi cụm sharded; không sharding ở `SA`.
- **Kiểm soát nghẽn máy khách:** Mọi lượt đo vượt ngưỡng CPU client ($80\%$ / $75\%$) gắn cờ `client_bound: true` và loại khỏi phân tích thông lượng.
- **Docker Dry-run (Pha 0 trên máy cá nhân):** 4 container (`cfgsvr`, `shard1`, `shard2`, `mongos`), áp dụng `mem_limit: 512m` và `--wiredTigerCacheSizeGB 0.25`.
- **Danh mục 4 bước xác minh cụm trên Azure:** (1) `ping` & kiểm tra cổng `27017/27018/27019`; (2) `sh.status()`; (3) xác nhận `sar` ghi log trên mọi VM; (4) xác nhận `sh.isBalancerRunning() == false` trước mọi pha đo Read và OLTP Write.

---

# Phụ lục B. Đặc tả Schema Dữ liệu và Mã Truy vấn Thực nghiệm (`appendix/AppendixB_SchemaVaTruyVan.tex`)

## B.1. Cấu trúc JSON Tối giản của Tài liệu `encounters`

Kịch bản tiền xử lý (`scripts/build_datasets.py`) đọc Synthea CSV, lược bỏ `DESCRIPTION`, `UNITS`, `STOP`, `TOTAL_CLAIM_COST` và kiểm chứng bằng `scripts/verify_datasets.py` (`SEED = 42`):

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

## B.2. Mã Truy vấn MongoDB cho Bộ `Q1`–`Q4`

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

---

# Tài liệu tham khảo (`main.tex`)

1. **[MongoDBSharding]** MongoDB, Inc., *Sharding — MongoDB Manual (v7.0 / v8.0)*. https://www.mongodb.com/docs/manual/sharding/
2. **[MongoDBWiredTiger]** MongoDB, Inc., *WiredTiger Storage Engine — MongoDB Manual*. https://www.mongodb.com/docs/manual/core/wiredtiger/
3. **[MongoDBExplain]** MongoDB, Inc., *Explain Results and Query Plans in Sharded Clusters — MongoDB Manual*. https://www.mongodb.com/docs/manual/reference/explain-results/
4. **[Walonoski2018]** J. Walonoski et al., "Synthea: An approach, method, and software mechanism for generating synthetic patients and the synthetic electronic health care record," *JAMIA*, vol. 25, no. 3, pp. 230–238, 2018.
5. **[Kleppmann2017]** M. Kleppmann, *Designing Data-Intensive Applications*, O'Reilly Media, 2017.
6. **[AzureStudents]** Microsoft Azure, *Azure for Students — Virtual Machine Sizes and Quota Limits*. https://learn.microsoft.com/en-us/azure/virtual-machines/sizes
7. **[ProjectRepo]** Nhóm thực hiện, *DBMS-distributed-method-benchmarking*, GitHub Repository, 2026. https://github.com/DatHoang-git/DBMS-distributed-method-benchmarking
