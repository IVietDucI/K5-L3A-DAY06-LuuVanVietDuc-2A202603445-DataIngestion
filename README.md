# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Dùng [starter PostgreSQL + pgvector](starter/README.md) để dựng database và hoàn thiện các hàm TODO, hoặc tự chọn vector store tương đương. Starter chỉ là khung: **bạn tự hiện thực pipeline và benchmark**.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.

## Bài làm cá nhân — Day 06

- Học viên: Lưu Văn Việt Đức — 2A202603445 — L3A.
- Corpus: 33 trang nội dung từ Think Python, 2nd Edition.
- Embedding: google/embeddinggemma-2, chạy local.
- Vector store: PostgreSQL + pgvector.
- Báo cáo, cấu hình, môi trường và hướng dẫn setup/chạy:
  [Báo cáo cá nhân](report/individual/2A202603445_LuuVanVietDuc.md).
- Code chạy từ `starter`: `python -m src.run` cho dev và
  `python scripts/run_test.py` cho test.

  ## Setup và chạy bài làm cá nhân

### 1. Chuẩn bị môi trường

Cần Python và Docker Desktop. Môi trường đã thực nghiệm:
Python 3.14.10 trên Windows, chạy embedding bằng CPU.

Từ thư mục gốc repo:

```powershell
cd starter
python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
python -m pip install torch==2.15.0 torchvision==0.29.2 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-day06-extra.txt
```

### 2. Cấu hình

Tạo `.env` nếu chưa có:

```powershell
if (!(Test-Path .env)) {
    Copy-Item .env.example .env
}
```

Trong `starter/.env`, đặt:

```dotenv
DATABASE_URL=postgresql://day6:day6_local_only@127.0.0.1:55433/day6_lab
EMBEDDING_MODEL=google/embeddinggemma-2
```

Embedding chạy local, không cần Gemini API key. Lần đầu cần mạng
để tải model từ Hugging Face. Không commit `.env` hoặc môi trường `.venv`.

### 3. Dữ liệu

- PDF gốc: `data/raw/thinkpython2.pdf`.
- Manifest và danh sách 33 trang được chọn: `data/manifest.json`.
- Nguồn PDF: https://greenteapress.com/thinkpython2/thinkpython2.pdf
- Tác giả: Allen B. Downey.
- Giấy phép: CC BY-NC 3.0.
- Benchmark: `benchmark/thinkpython_questions.json`, gồm 15 dev và 5 test.

Các đường dẫn trên tính từ gốc repo. Dữ liệu và benchmark đã được
chuẩn bị, không cần tạo lại. Nếu tải lại PDF, phải đối chiếu SHA256
trong manifest.

### 4. Chạy pipeline

Mở Docker Desktop. Chạy từ thư mục `starter`:

```powershell
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
python scripts/prepare_corpus.py
python -m src.run
python scripts/run_test.py
```

- `prepare_corpus.py`: đọc 33 trang, chuẩn hóa, tạo chunk A/B/C.
- `src.run`: embedding tài liệu, lưu pgvector, kiểm tra nạp lại
  không nhân đôi và đánh giá dev.
- `run_test.py`: dùng vector tài liệu đã lưu và đánh giá 5 câu test.

`src.run` tạo thư mục dev mới theo timestamp. `run_test.py` hiện
tham chiếu lần dev gốc `20261113T112611135714Z` và lựa chọn trong
`results/selection_C.json`. Giữ các minh chứng gốc để đối chiếu.

Nếu tạo thí nghiệm mới, cần cập nhật đường dẫn dev trong script test
và lưu hồ sơ lựa chọn riêng; không trình bày lần chạy lại là lần
đánh giá holdout đầu tiên.

### 5. Kết quả và minh chứng

- `results/preparation/`: chunk, thống kê và nhãn coherence.
- `results/dev/20261113T112611135714Z/`: trace và kết quả dev gốc.
- `results/test/20261113T113600498881Z/`: trace và kết quả test.
- `results/selection_C.json`: lựa chọn C trước test.
- `artifacts/experiment_log.csv`: tổng hợp thí nghiệm A/B/C.
- `report/individual/2A202603445_LuuVanVietDuc.md`: báo cáo cá nhân.

Nhãn đã rà soát nằm trong `coherence_proposed.json` và
`test_review_proposed.json`; xem trường `review_status`.
Các file backup encoding và `finalize_lab.py` không cần chạy.

### 6. Dừng database

Dừng container nhưng giữ dữ liệu:

```powershell
docker compose -p day6_student_starter stop
```