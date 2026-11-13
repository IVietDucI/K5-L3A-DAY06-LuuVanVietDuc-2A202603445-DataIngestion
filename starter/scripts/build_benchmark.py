"""Place at starter/scripts/build_benchmark.py; run from starter.
Build verified gold only. No embeddings, retrieval, or LLM calls.
"""
import hashlib
import json
import unicodedata
from pathlib import Path
from pypdf import PdfReader

# split, chapter, page, question, answer, start anchor, end anchor, filter
ROWS = [
('dev',1,23,'Theo sách, kỹ năng quan trọng nhất của một nhà khoa học máy tính là gì?', 'Giải quyết vấn đề (problem solving).', 'The single most important skill', 'isproblem solving.', None),
('dev',1,23,'Một chương trình là gì?', 'Một chuỗi chỉ dẫn xác định cách thực hiện một phép tính hoặc xử lý.', 'Aprogramis a sequence', 'perform a computation.', None),
('dev',1,25,'Toán tử lũy thừa trong Python là gì?', 'Toán tử **.', 'Finally, the operator**', 'raises a number to a power:', None),
('dev',1,26,'Trong chương 1, nếu chưa biết kiểu dữ liệu của một giá trị thì kiểm tra bằng hàm nào?', 'Dùng type(value), ví dụ type(2) trả về int.', 'If you are not sure what type', "<class'int'>", {'chapter':1}),
('dev',1,27,'Quá trình xác định cấu trúc của một câu hoặc câu lệnh được gọi là gì?', 'Parsing (phân tích cú pháp).', 'When you read a sentence', 'This process is calledparsing.', None),
('dev',2,31,'Biến là gì và câu lệnh gán làm gì?', 'Biến là tên tham chiếu tới một giá trị; câu lệnh gán tạo biến mới và gán giá trị cho nó.', 'A variable is a name', 'gives it a value:', None),
('dev',2,32,'Theo quy tắc trong sách, tên biến có thể bắt đầu bằng một chữ số không?', 'Không; tên biến có thể chứa chữ và số nhưng không bắt đầu bằng số.', 'Variable names can be as long', 'begin with a number.', None),
('dev',2,32,'Một biểu thức được cấu thành từ những thành phần nào?', 'Các giá trị, biến và toán tử.', 'Anexpressionis a combination', 'values, variables, and operators.', None),
('dev',2,33,'Trong chương 2, vì sao một biểu thức đứng riêng trong script không hiện kết quả, và cần làm gì để hiện kết quả?', 'Script đánh giá biểu thức nhưng không tự hiển thị; cần dùng print.', 'In script mode an expression', 'printstatement like this:', {'chapter':2}),
('dev',2,34,'Khi các toán tử có cùng độ ưu tiên, thứ tự đánh giá thông thường là gì và ngoại lệ nào được sách nêu?', 'Từ trái sang phải, ngoại trừ phép lũy thừa.', 'Operators with the same precedence', 'except exponentiation).', None),
('dev',3,39,'Theo sách, một hàm là gì?', 'Một chuỗi câu lệnh có tên để thực hiện một phép tính.', 'In the context of programming', 'performs a computation.', None),
('dev',3,39,'int chuyển một số thực thành số nguyên bằng cách làm tròn hay bỏ phần thập phân?', 'Bỏ phần thập phân, không làm tròn.', 'intcan convert floating-point', 'fraction part:', None),
('dev',3,41,'Dòng đầu của định nghĩa hàm được gọi là gì, kết thúc bằng dấu nào và phần thân phải trình bày ra sao?', 'Header kết thúc bằng dấu hai chấm; body phải thụt lề.', 'The first line of the function definition', 'body has to be indented.', None),
('dev',3,44,'Biến được tạo bên trong một hàm có phạm vi tồn tại thế nào?', 'Là biến cục bộ, chỉ tồn tại bên trong hàm.', 'When you create a variable inside a function', 'inside the function.', None),
('dev',3,46,'Traceback cho biết những thông tin nào khi chương trình gặp lỗi?', 'File và dòng xảy ra lỗi, các hàm đang thực thi, cùng dòng mã gây lỗi.', 'This list of functions is called', 'code that caused the error.', None),
('test',4,54,'Trong chương 4, việc gói một đoạn mã vào một hàm được gọi là gì?', 'Encapsulation (đóng gói).', 'Wrapping a piece of code', 'is calledencapsulation.', {'chapter':4}),
('test',4,55,'Khi một hàm có nhiều đối số số học và dễ quên thứ tự, sách đề xuất cách gọi nào?', 'Ghi tên tham số trong lời gọi, tức keyword arguments, ví dụ polygon(bob, n=7, length=70).', 'When a function has more than a few numeric arguments', 'polygon(bob, n=7, length=70)', None),
('test',4,55,'Một giao diện hàm sạch giúp người gọi sử dụng hàm như thế nào?', 'Cho phép người gọi làm điều họ muốn mà không phải xử lý các chi tiết không cần thiết.', 'An interface is', 'without dealing with unnecessary details.', None),
('test',4,57,'Docstring nằm ở đâu và dùng để giải thích điều gì?', 'Là chuỗi ở đầu hàm, giải thích giao diện của hàm.', 'Adocstringis a string', 'explains the interface', None),
('test',4,58,'Theo phần Debugging của chương 4, nếu preconditions được đáp ứng nhưng postconditions không đạt thì lỗi nằm ở đâu?', 'Lỗi nằm trong hàm.', 'If the preconditions are satisfied', 'the bug is in the function.', {'chapter':4}),
]

def normalize(text):
    return ' '.join(unicodedata.normalize('NFC', text).split())

def indexed_letters(text):
    pairs = [(c.lower(), i) for i, c in enumerate(text) if c.isalnum()]
    return ''.join(c for c, _ in pairs), [i for _, i in pairs]

def extract_quote(text, start, end):
    searchable, positions = indexed_letters(text)
    left = indexed_letters(start)[0]
    right = indexed_letters(end)[0]
    a = searchable.index(left)
    b = searchable.index(right, a) + len(right)
    stop = positions[b-1] + 1
    while stop < len(text) and not text[stop].isalnum() and not text[stop].isspace():
        stop += 1
    return text[positions[a]:stop]

def main():
    # Expected location: <repo>/starter/scripts/build_benchmark.py
    root = Path(__file__).resolve().parents[2]
    source = root / 'data/raw/thinkpython2.pdf'
    manifest_path = root / 'data/manifest.json'
    outdir = root / 'benchmark'
    output = outdir / 'thinkpython_questions.json'
    if output.exists():
        raise SystemExit('Benchmark already exists; refusing to overwrite the frozen questions.')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != manifest['sha256']:
        raise ValueError('PDF hash differs from manifest. Check the corpus snapshot.')
    reader = PdfReader(source)
    selected = {p['page']: p for p in manifest['pages']}
    texts = {p: normalize(reader.pages[p-1].extract_text() or '') for p in selected}
    questions = []
    for number, row in enumerate(ROWS, 1):
        split, chapter, page, question, answer, start, end, query_filter = row
        if selected[page]['chapter'] != chapter:
            raise ValueError(f'Chapter mismatch: page {page}')
        try:
            evidence = extract_quote(texts[page], start, end)
        except ValueError as exc:
            raise ValueError(f'Evidence missing for Q{number:02d}, page {page}') from exc
        assert evidence in texts[page]
        questions.append({
            'id': f'Q{number:02d}', 'split': split,
            'question': question, 'expected_answer': answer,
            'gold_source_id': manifest['source_id'], 'gold_page': page,
            'evidence_quote': evidence, 'filter': query_filter,
            'filter_origin': 'Explicit chapter scope in the question' if query_filter else None,
            'alternative_gold': [],
        })
    assert len(questions) == 20
    assert sum(q['split'] == 'dev' for q in questions) == 15
    assert sum(q['split'] == 'test' for q in questions) == 5
    assert sum(bool(q['filter']) for q in questions) == 4
    outdir.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(questions, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    readme = '''# Think Python benchmark

20 questions: Q01-Q15 dev (Chapters 1-3), Q16-Q20 test (Chapter 4).
Four explicit chapter filters: Q04, Q09, Q16, Q20 (two in test).
Questions/answers are Vietnamese; source evidence is English. Keep this cross-language setting identical across A/B/C.
Physical PDF pages are numbered from 1. Evidence is a literal span from NFC/whitespace-normalized pypdf extraction.
Gold source/page/answer/evidence are evaluation data only; never send them as retrieval input.
Only question text and its explicit filter may enter retrieval. C applies filters; A/B do not.

## Split and limitations
Split is fixed before retrieval runs. Chapter-level holdout reduces near-duplicate passages, but all chapters belong to one book and share function-related concepts. Five test questions are a small illustrative sample. Preparing gold is allowed; do not tune retrieval from test results.

## Selection rule fixed before test
Compare configurations on dev Evidence Hit@3, then dev Hit@1; if tied, prefer lower measured embedding/storage resources. Use test only for final reporting. Report coherence, metadata correctness and human grounding separately; do not infer human scores from string matching.

## Gold verification and alternatives
The author must read each question, answer, physical page and extracted quote to confirm meaning. Script checks presence, not semantic sufficiency. alternative_gold starts empty, not a claim that answers occur on only one page. During manual review, record any equally valid source/page/evidence alternatives and apply them consistently to all strategies without changing the query/split/filter or tuning from test.

## Rebuild and audit
Run python scripts/build_benchmark.py from starter. It validates the PDF against data/manifest.json and refuses to overwrite an existing benchmark. Commit the script, questions, this note and the .sha256 file before retrieval. Never commit .env.
'''
    (outdir/'thinkpython_benchmark_README.md').write_text(readme, encoding='utf-8')
    fingerprint = hashlib.sha256(output.read_bytes()).hexdigest()
    (outdir/'thinkpython_questions.sha256').write_text(fingerprint+'  thinkpython_questions.json\n', encoding='utf-8')
    print('Benchmark:', output)
    print('Questions: 20 | dev: 15 | test: 5')
    print('Filtered questions: 4 | filtered test: 2')
    print('Evidence presence: 20/20 verified against PDF')
    print('Benchmark SHA256:', fingerprint)
    print('Benchmark OK | Human semantic review still required')

if __name__ == '__main__':
    main()
