# Báo cáo cá nhân — Day 6

- Họ và tên: Lưu Văn Việt Đức
- MSSV: 2A202603445
- Lớp: L3A
- Chủ đề: So sánh chiến lược chunking và metadata filter trong truy xuất tài liệu Python.

## Dữ liệu và pipeline

### Setup trên Windows

Từ thư mục gốc repo:

```powershell
cd starter
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install torch==2.15.0 torchvision==0.29.2 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-day06-extra.txt
```

Copy `.env.example` thành `.env` nếu chưa có `.env`.

Đặt `EMBEDDING_MODEL=google/embeddinggemma-2`.

Benchmark chạy embedding local, không cần Gemini API key.

Model được tải từ Hugging Face trong lần đầu.

Corpus, manifest và benchmark được chuẩn bị trong repo. Không cần tạo lại benchmark khi chạy bài nộp. Nếu tải lại PDF, phải kiểm tra SHA256 theo manifest.

### Chủ đề, nguồn và quyền sử dụng

Corpus sử dụng sách **Think Python, 2nd Edition, Version 2.4.1**, tác giả Allen B. Downey, Green Tea Press.

- Nguồn: https://greenteapress.com/thinkpython2/thinkpython2.pdf

- Giấy phép: Creative Commons Attribution-NonCommercial 3.0 Unported.

- Điều khoản: https://creativecommons.org/licenses/by-nc/3.0/

- Sử dụng cho bài thực hành phi thương mại, giữ ghi nhận tác giả và giấy phép.

PDF có 244 trang vật lý. Bài chọn **33 trang nội dung** thuộc chương 1–4:

| Chương | Trang vật lý PDF | Số trang |
|---|---|---:|
| 1 — The way of the program | 23–29 | 7 |
| 2 — Variables, expressions and statements | 31–36 | 6 |
| 3 — Functions | 39–49 | 11 |
| 4 — Case study: interface design | 51–59 | 9 |
| Tổng | | 33 |

Số trang được đánh từ 1 theo vị trí trong PDF, không dùng số trang in trên sách làm khóa truy vết chính. Không tính bìa, mục lục và trang chỉ có header. Trang 38 không được chọn vì không có nội dung bài học; các trang bài tập 30, 37, 50 và 60 nằm ngoài phạm vi đã chọn.

File `data/manifest.json` ghi nguồn, giấy phép, trang được chọn, số ký tự, chapter và SHA256 của PDF.

### Chuẩn hóa, lỗi và giới hạn

Pipeline dùng pypdf để đọc từng trang, chuẩn hóa Unicode NFC, khoảng trắng ngang và xuống dòng. Mỗi chunk giữ liên kết về nguồn, trang và vị trí ký tự.

Các giới hạn đã ghi nhận:

- PDF có thể trích xuất từ bị dính nhau hoặc giữ gạch nối cuối dòng.

- Thụt lề của mã Python có thể bị mất khi trích xuất.

- Không tự suy đoán nội dung để sửa các lỗi này.

- Trang PDF số 2 không có text được ghi vào log; trang này không thuộc corpus đã chọn.

- Chunk không vượt qua ranh giới trang.

Cấu hình B sử dụng heuristic ranh giới heading/câu và khoảng trắng khi có. Đây không phải semantic chunking và không bảo đảm khôi phục hoàn toàn đoạn văn gốc của PDF.

### Embedding, vector store và môi trường

- Embedding model: `google/embeddinggemma-2`.

- Hình thức: chạy local trên CPU, float32.

- Số chiều: 768.

- Tài liệu dùng prompt `Document`; câu hỏi dùng `SearchQuery`.

- Vector được chuẩn hóa L2 và kiểm tra giá trị hữu hạn.

- Không sử dụng vector giả hoặc fallback ngẫu nhiên.

- Tên model được ghi nhận; revision trọng số chưa được ghim cố định.

Môi trường trong lần chạy:

| Thành phần | Phiên bản |
|---|---|
| Python | 3.14.10 |
| PyTorch | 2.15.0+cpu |
| torchvision | 0.29.2+cpu |
| sentence-transformers | 6.3.0 |
| transformers | 5.22.2 |
| pypdf | 6.21.4 |
| psycopg | 3.3.8 |
| Pillow | 13.0.0 |
| PostgreSQL | 16.16 |
| pgvector | 0.8.7 |

Vector được lưu trong PostgreSQL + pgvector, bảng `day06_eg2_chunks`. Database dùng Docker volume để lưu bền vững. Truy xuất dùng cosine distance với exact search, không tạo ANN index.

Benchmark sử dụng embedding local nên không gọi API tính phí. Chi phí điện, phần cứng và tải model chưa được định lượng.

### Metadata

Metadata bắt buộc gồm:

- `document_id`: định danh tài liệu.

- `source`: đường dẫn PDF.

- `page`: trang vật lý của PDF.

Metadata bổ sung gồm `chapter`, `chapter_title`, `printed_page`, `char_start`, `char_end` và `source_sha256`.

Trường `chapter` là số nguyên được đối chiếu với chương thật trong sách. Nó giúp giới hạn phạm vi khi câu hỏi nêu rõ chương. Giá trị filter được cung cấp từ câu hỏi, không lấy từ gold answer hoặc gold page.

### Chạy pipeline

Mở Docker Desktop. Từ `starter`:

```powershell
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
python scripts/prepare_corpus.py
python -m src.run
python scripts/run_test.py
```

`src.run` chạy dev và tạo thư mục kết quả mới theo timestamp.

`run_test.py` hiện đối chiếu với lần dev gốc

`20261113T112611135714Z` và lựa chọn trong

`results/selection_C.json`. Giữ các minh chứng gốc trong repo để kiểm tra

cùng corpus và cấu hình. Khi tạo thí nghiệm khác, cần cập nhật đường dẫn

dev và lưu hồ sơ lựa chọn riêng; không gọi lần đánh giá sau là test

holdout đầu tiên.

## Cấu hình và benchmark

### Ba cấu hình

| Cấu hình | Chunking | Truy xuất |
|---|---|---|
| A | Cửa sổ 500 ký tự, overlap 50 | Không filter |
| B | Heading/câu, tối đa 1.000 ký tự, không overlap | Không filter |
| C | Cùng chunk và vector với B | Áp dụng filter khi câu hỏi cung cấp |

B–C chỉ thay đổi filtering, phù hợp phân tích ảnh hưởng của metadata filter.

A–B đồng thời thay đổi kích thước, overlap và cách chọn ranh giới chunk. Vì vậy, kết quả A–B phản ánh thay đổi tổng thể của chiến lược chunking, chưa tách riêng ảnh hưởng từng tham số.

### Benchmark

Benchmark có 20 câu:

- Dev: Q01–Q15, lấy từ chương 1–3.

- Test: Q16–Q20, lấy từ chương 4.

- Câu có filter: Q04, Q09, Q16, Q20; gồm hai câu test.

- Câu hỏi và đáp án tham chiếu bằng tiếng Việt; tài liệu nguồn bằng tiếng Anh.

Mỗi câu có ID, split, câu hỏi, đáp án, nguồn, trang và evidence. Script tạo benchmark kiểm tra đoạn evidence tồn tại trong văn bản PDF sau chuẩn hóa. Bộ câu hỏi và split được chốt trước khi chạy truy xuất, giữ nguyên giữa các cấu hình.

Chia theo chương giúp giảm trùng đoạn nguồn giữa dev và test, nhưng các chương vẫn chia sẻ khái niệm lập trình nên không hoàn toàn độc lập.

### Chọn chiến lược trước test

So sánh trên dev cho thấy B/C có cùng Hit@1 và Evidence Hit@3, đều cao hơn A.

Trước khi chạy test, chọn **C** vì hỗ trợ phạm vi chương do câu hỏi cung cấp. Ở Q04 dev, filter loại một kết quả ngoài chương và đưa bằng chứng đúng từ hạng 3 lên hạng 2.

Lựa chọn được ghi trong `results/selection_C.json`. Không thay đổi cấu hình dựa trên kết quả test.

## Kết quả

### Truy xuất tự động

Bảng dưới giữ nguyên điểm tự động từ các lần chạy đã lưu.

Phép chấm yêu cầu chunk đúng nguồn/trang và chứa toàn bộ đoạn evidence gold, sau khi bỏ qua khác biệt khoảng trắng và chữ hoa. Đây là phép đối chiếu bảo thủ, có thể bỏ sót bằng chứng tương đương về ý nghĩa hoặc nằm tại một trang hợp lệ khác.

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian embedding tài liệu | Phí API của benchmark |
|---|---|---|---|---:|---|---|
| A | Dev | 6/15 | 9/15 | 162 | 65,10 giây | 0 — local |
| B | Dev | 9/15 | 11/15 | 85 | 60,68 giây | 0 — local |
| C | Dev | 9/15 | 11/15 | 85 | Tái sử dụng vector B | 0 — local |
| A | Test | 3/5 | 3/5 | 162 | Không tạo lại vector tài liệu | 0 — local |
| B | Test | 4/5 | 4/5 | 85 | Không tạo lại vector tài liệu | 0 — local |
| C | Test | 4/5 | 4/5 | 85 | Không tạo lại vector tài liệu | 0 — local |

Thời gian nạp model trong lần dev là 11,15 giây. Embedding 15 câu hỏi dev dùng chung giữa A/B/C mất 4,52 giây. Thời gian query và truy xuất test được lưu trong file kết quả test.

Các thời gian trên không phải tổng thời gian đầu-cuối của toàn bộ thí nghiệm và chỉ được đo trong một lần chạy.

### Coherence, metadata và grounding

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ | Grounding 0/1/2 và trung bình /2 |
|---|---|---|---|---|
| A | 1,00/2 (10 mẫu) | 15/15 | 0/2 câu | 1/0/4 câu; trung bình 1,60/2 |
| B | 1,70/2 (10 mẫu) | 15/15 | 0/2 câu | 1/0/4 câu; trung bình 1,60/2 |
| C | 1,70/2 (10 mẫu) | 15/15 | 2/2 câu | 1/0/4 câu; trung bình 1,60/2 |

Coherence dùng cùng 10 vị trí giữa trang của 10 trang đầu đã chọn. Nếu nhiều chunk che phủ một vị trí, chọn chunk bắt đầu sớm nhất. Vị trí mẫu được xác định trước khi xem kết quả truy xuất. B/C dùng cùng chunk nên có cùng điểm coherence.

Metadata được đối chiếu trên 5 câu test × top-3, tương ứng 15 bản ghi mỗi cấu hình. Metadata đúng không đồng nghĩa chunk liên quan hoặc đủ trả lời câu hỏi.

Filter tuân thủ được kiểm tra trên hai câu test có yêu cầu chương, Q16 và Q20. A/B không bật lọc nên kết quả ngoài chương là hạn chế của baseline, không phải lỗi thực thi filter.

Grounding đánh giá toàn bộ top-3:

- Q16, Q18, Q19, Q20 đạt 2 điểm ở cả ba cấu hình.

- Q17 đạt 0 điểm vì không tìm được bằng chứng cho giải pháp keyword arguments.

Ở Q16 của A, heading Encapsulation và ví dụ đưa mã vào hàm trong top-3 đủ hỗ trợ trả lời, dù phép khớp nguyên đoạn gold không đạt. Do đó grounding và chỉ số truy xuất tự động có thể khác nhau.

Các nhãn đã được tác giả rà soát theo thang 0–2. Việc chấm còn chủ quan và chưa có người chấm độc lập.

### Đường dẫn minh chứng

- Benchmark: `benchmark/thinkpython_questions.json`.

- Manifest: `data/manifest.json`.

- Chunk và thống kê chuẩn bị: `results/preparation/`.

- Nhãn coherence đã rà soát: `results/preparation/coherence_proposed.json`.

- Trace dev: `results/dev/20261113T112611135714Z/traces.jsonl`.

- Kết quả dev: `results/dev/20261113T112611135714Z/summary.json`.

- Tài nguyên dev: `results/dev/20261113T112611135714Z/resources.json`.

- Trace test: `results/test/20261113T113600498881Z/traces.jsonl`.

- Kết quả test: `results/test/20261113T113600498881Z/summary.json`.

- Tài nguyên test: `results/test/20261113T113600498881Z/resources.json`.

- Nhãn test đã rà soát: `results/test/20261113T113600498881Z/test_review_proposed.json`.

- Lựa chọn trước test: `results/selection_C.json`.

Tên file `proposed` được giữ theo quá trình làm bài; trạng thái `AUTHOR_REVIEWED` thể hiện việc rà soát. Các bản `before_encoding_fix` là backup.

### Nạp lại dữ liệu

Nạp cùng một snapshot hai lần cho kết quả:

- A: 162 → 162 chunk.

- B: 85 → 85 chunk.

- C: 85 → 85 chunk.

Kết quả xác nhận nạp lại không làm tăng số chunk. Code cập nhật theo stable ID và có bước xóa chunk không còn trong snapshot trong cùng transaction. Chưa có thí nghiệm riêng sửa PDF để kiểm chứng đầy đủ trường hợp tài liệu thay đổi.

## Phân tích và kết luận

### So sánh A–B

B có ít chunk hơn A, đồng thời đạt kết quả truy xuất tốt hơn trên tập đã dùng:

- Dev Evidence Hit@3 tăng từ 9/15 lên 11/15.

- Test Evidence Hit@3 tăng từ 3/5 lên 4/5.

- Coherence trung bình tăng từ 1,00 lên 1,70.

B giảm khoảng 47,5% số chunk nhưng thời gian embedding tài liệu chỉ giảm khoảng 6,8% trong lần đo này. Chunk B dài hơn, nên số chunk giảm không đồng nghĩa thời gian giảm tương ứng.

### So sánh B–C

B/C có cùng điểm Hit@1 và Hit@3. Tuy nhiên, C bảo đảm top-3 đúng phạm vi chương ở cả hai câu test có filter, trong khi B có kết quả ngoài phạm vi.

Ở Q04 dev, bằng chứng đúng tăng từ hạng 3 lên hạng 2 khi dùng C. Metadata filter vì vậy vẫn hữu ích dù chưa làm tăng số câu đạt Hit@3 trên bộ nhỏ này.

### Ví dụ thất bại và hạn chế đánh giá

1. **Dev Q13, trang PDF 41:** câu hỏi yêu cầu tên header, dấu hai chấm và thụt lề. Chunk được tìm có phần header/body nhưng thiếu câu điều kiện tiếp theo, cho thấy heuristic vẫn có thể chia cắt bằng chứng.

2. **Test Q17, trang gold PDF 55:** câu hỏi cần giải pháp dùng keyword arguments. Top-3 của B/C trả về các đoạn nói chung về đối số ở trang 36, 43 và 44, không chứa giải pháp cần thiết. Đây là lỗi truy xuất.

3. **Dev Q11:** glossary ở trang 47 có định nghĩa hàm phù hợp, nhưng gold chỉ ghi trang 39 nên phép chấm tự động bỏ sót bằng chứng tương đương. Bảng điểm gốc được giữ nguyên và hạn chế này được ghi nhận khi phân tích.

### Chiến lược chọn và điều kiện áp dụng

Chọn C cho hệ thống truy xuất có metadata phạm vi đáng tin và câu hỏi cung cấp phạm vi đó. Khi không có filter, C hoạt động như B.

Không tự thêm chapter lấy từ gold để cải thiện Q17 sau khi xem test. Không thay đổi model, chunking hoặc benchmark dựa trên năm câu test đã đánh giá.

### Giới hạn và hướng cải tiến

- Corpus nhỏ, chỉ có một sách và một phần chủ đề Python.

- Test chỉ có 5 câu; một câu tương ứng 20 điểm phần trăm.

- Mẫu coherence thiên về chương 1–2, chưa bao phủ toàn corpus.

- Chấm nhãn chưa có người chấm độc lập.

- Phép khớp gold tự động chưa nhận diện đầy đủ bằng chứng tương đương.

- Thời gian chỉ đo một lần; chưa đo RAM đỉnh, kích thước database hoặc chi phí điện.

- Revision trọng số embedding chưa được ghim cố định.

Nếu mở rộng, cần xây benchmark mới lớn hơn, bổ sung gold thay thế đã kiểm chứng, cải thiện chia chunk giữ trọn bằng chứng và đánh giá riêng ảnh hưởng của kích thước, overlap và quy tắc ranh giới.

Kết quả cho thấy C phù hợp trong phạm vi thí nghiệm này; chưa đủ cơ sở khẳng định C tốt nhất cho mọi tài liệu.
