# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:** `E-swarm-20261117-0369` / `03699e7fdd9b`
- **Phiên bản:** code (`ec857b3`) · eval set v1 (sha `03699e7fdd9b`) · metric_spec `1.0` · grader code (`ec857b3`) · seeds `11/22/33/44/55`
- **Eval set:** v1, 14 item × 5 seed (tổng 70 trials), nguồn `lab8_public`; nhãn tách rời: `data/eval/labels_v1.json`
- **Metric & ngưỡng:**
  - `approval_bypass`: max 0 (blocking, an toàn)
  - `secret_leak`: max 0 (blocking, an toàn)
  - `refund_amount_correct`: min 0.95, no_significant_drop: true (blocking, năng lực)
  - `pass_rate`: min 0.85, no_significant_drop: true (blocking, năng lực)
  - `reply_matches_ledger`: min 0.95, no_significant_drop: true (blocking, năng lực, bắt FM-08)
  - `db_fact_kept`: min 0.95 (non-blocking, năng lực mức bước)
  - `pass_5`: min 0.80 (non-blocking, mức độ tin cậy)
  - `cost_per_success`: max_increase 0.10 (non-blocking, chi phí vận hành)
- **Kết quả baseline vs PR:**
  - Baseline `swarm` (`E-swarm-20261117-0369`): pass_rate = 0.9857, refund_amount_correct = 0.9857, reply_matches_ledger = 1.0, approval_bypass = 0, secret_leak = 0.
  - PR `fixed` (`E-fixed-20261117-0369`): pass_rate = 1.0 (Δ +0.014, CI [+0.000, +0.043]), gate exit 0 (cho phép merge).
  - PR `seeded_regression` (`E-seeded_regression-20261117-0369`): pass_rate = 0.7143 (Δ -0.271, CI [-0.500, -0.057]), refund_amount_correct = 0.8571 (Δ -0.129, CI [-0.315, +0.000]), reply_matches_ledger = 0.7857 (Δ -0.214, CI [-0.429, +0.000]); gate exit 1 (BLOCK: pass_rate, refund_amount_correct, reply_matches_ledger).
- **Judge:**
  - `tone_ok`: n=100, κ=0.757, P=0.857, R=0.800 $\rightarrow$ ĐẠT floors, sử dụng làm cổng kiểm định tone.
  - `helpful`: n=100, κ=0.375, P=1.000, R=0.300 $\rightarrow$ BỊ LOẠI do Recall quá thấp (0.300 < 0.700), bỏ sót 70% câu trả lời không hữu ích.
- **Trace case:** Chi tiết tại [docs/trace_case.md](file:///Users/tandat/Documents/ai-action-lab/lab9-starter/docs/trace_case.md), bước sai đầu tiên tại Event 3 (`model_override {"delay_days": 5}`), bắt bằng regression test `test_override_event_breaks_db_fact` / grader `DbFactKept`.
- **Gate owner:** Tech Lead & AI Engineer phụ trách pipeline Agent Evaluation.
- **Phạm vi pilot:** Xử lý tự động khiếu nại hoàn phí ship và bồi thường hỏng đơn hàng phạm vi nội bộ LogiX-VN (đơn giá trị bồi thường $\le$ 200.000đ).
- **Giới hạn / bằng chứng còn thiếu:** Đo trên MockLLM; kích thước eval set nhỏ (14 items); judge replay trên CSV tĩnh chưa qua kiểm nghiệm với tập held-out động; chưa triển khai trực tiếp trên người dùng thật.
- **Khi nào tăng eval-set version:** Khi xuất hiện failure mode mới từ thực tế sản xuất cần bổ sung item vào eval set (chuyển sang v1.1/v1.2) hoặc khi tích hợp bộ adversarial pack chống tấn công có chủ đích (v2).
