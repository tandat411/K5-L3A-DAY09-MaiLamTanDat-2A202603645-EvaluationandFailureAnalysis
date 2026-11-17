# Judge audit

Chạy: `python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5`
Và:   `python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | ĐẠT (κ=0.757 ≥ 0.6, P=0.857 ≥ 0.8, R=0.800 ≥ 0.7) | Dùng làm gate |
| helpful | 100 | 0.375 | 1.000 | 0.300 | KHÔNG ĐẠT (κ=0.375 < 0.6, R=0.300 < 0.7) | Loại (không dùng làm gate) |

## ≥5 case audit thủ công (từ `judge_tone_public.csv`)

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Đề xuất sửa rubric |
|---|---|---|---|---|---|---|
| 1 | `H-008`: "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người đúng | **Ghi chú:** Xưng "em" + "nha", ngôn từ suồng sã thiếu tính chuẩn mực B2B; Judge chỉ thấy thân thiện nên bỏ qua.<br>**Sửa rubric:** Cấm xưng hô thân mật tự phát; bắt buộc dùng đại từ quy chuẩn: xưng "LogiX" và gọi khách là "quý khách / anh/chị". |
| 2 | `H-029`: "Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm." | PASS | FAIL | Người đúng | **Ghi chú:** Giọng cộc lốc, ra lệnh gây phản cảm ("không cần nhắn thêm"); Judge bị đánh lừa bởi từ lịch sự đầu câu "Dạ, vui lòng".<br>**Sửa rubric:** Yêu cầu đánh giá toàn bộ ngữ điệu câu; cấm các câu mệnh lệnh tiêu cực hoặc xua đuổi khách hàng. |
| 3 | `H-042`: "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người đúng | **Ghi chú:** Câu trả lời ngắn gọn, đầy đủ thông tin, đúng chuẩn CS; Judge phạt máy móc vì "thiếu lời xin lỗi".<br>**Sửa rubric:** Khi khiếu nại đã được giải quyết thành công (hoàn tiền đúng hạn), phản hồi lịch sự không bắt buộc phải kèm lời xin lỗi. |
| 4 | `H-051`: "Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ." | FAIL | PASS | Người đúng | **Ghi chú:** Dùng từ mượn "refund" đã được quy chuẩn CSKH của LogiX chấp nhận; Judge phạt vì tiếng Anh.<br>**Sửa rubric:** Bổ sung danh mục whitelist các thuật ngữ nghiệp vụ song ngữ được phép dùng (refund, ship, voucher, tracking). |
| 5 | `H-070`: "Dạ, LogiX đã hoàn 90.000đ cho đơn O-909 ạ 😂😂" | PASS | FAIL | Người đúng | **Ghi chú:** Dùng emoji cười cợt (😂😂) trong trao đổi khiếu nại bồi thường là thiếu chuyên nghiệp; Judge xem là vui vẻ.<br>**Sửa rubric:** Cấm tuyệt đối các emoji mang tính đùa cợt/ỡm ờ (😂😂, 🤣, 😜); chỉ cho phép emoji lịch sự trung tính nếu cần. |

## Kết luận

1. **Tiêu chí bị loại và lý do:**
   - `judge_helpful` bị **loại bỏ hoàn toàn khỏi CI gate**.
   - **Ma trận nhầm lẫn của `helpful`:** `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}` trên $n=100$.
   - **Lý do:** Mặc dù Precision đạt 1.0 (không báo nhầm), Recall chỉ đạt **0.300** (sàn yêu cầu $\ge 0.7$). Trong số 30 ca thực tế không hữu ích (human=FAIL), judge bỏ sót tới 21 ca ($FN=21$, tỷ lệ bỏ sót 70%). Hệ số $\kappa = 0.375$ cho thấy độ đồng thuận với chuyên gia rất kém. Nếu dùng judge này làm gate sẽ tạo cảm giác an toàn giả tạo (false sense of security), để lọt lượng lớn lỗi regression.
2. **Rủi ro còn lại:**
   - Judge `judge_tone` chỉ mới được kiểm tra trên dữ liệu replay đã công khai (`judge_tone_public.csv`).
   - Có rủi ro overfitting vào tập prompt/replay hiện tại; cần định kỳ thu thập nhãn từ chuyên gia con người trên các trace mới để tạo tập held-out độc lập và hiệu chỉnh lại rubric/few-shot cho LLM judge.
