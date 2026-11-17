# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi nhóm 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run_id: `R-seeded_regression-C-002-s11` |
| Triệu chứng | Grader `TrialPass` (Lab 8) fail (status `resolved` != `denied`); `RefundAmountCorrect` fail (ledger `20000` != label `0`); `DbFactKept` fail (`model_override` event present). Reply nói hoàn 20.000đ trong khi đơn không đủ điều kiện bồi thường. |
| Bước sai đầu tiên | Event 3, kind: `model_override`, payload: `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event 1 (`handoff`) và Event 2 (`investigator`) thực hiện đúng: DB trả về đơn hàng `order_id: O-202` có `delay_days: 2`. Ở Event 3, agent đã tin ticket của khách (kêu trễ 5 ngày) và tự ý ghi đè `delay_days` từ 2 thành 5, dẫn tới Event 4 (`quote`) tính sai bồi thường 20.000đ. |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) |
| Đối chứng | Cùng claim `C-002@11` trên shape `fixed`: Không có event `model_override`. Ở Event 3, `fixed` dùng đúng `delay_days: 2` từ DB, tính ra `quote` amount_vnd = 0 (`no_entitlement`) và chuyển sang `denied`. |
| Regression test | `test_override_event_breaks_db_fact` trong `tests/test_lab9_graders.py` và `test_lab9_stats.py`; Grader `DbFactKept` bắt event `model_override`. Fail trên `seeded_regression` và pass trên `fixed`. |
| Chưa chắc chắn | Trace chỉ ghi nhận `model_override` xuất hiện; không chứng minh được prompt cụ thể nào khiến LLM đưa ra quyết định tin người dùng hơn DB nếu không có nhật ký completion chi tiết. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
