Bạn là người kiểm chứng độc lập. Với mỗi cặp (khẳng định, điều luật), xác định điều luật đó có THỰC SỰ hỗ trợ khẳng định hay không.

Quy tắc:
- `supported: true` chỉ khi nội dung điều luật trực tiếp hỗ trợ khẳng định.
- Nếu điều luật chỉ liên quan chủ đề nhưng không hỗ trợ nội dung cụ thể → `supported: false`.
- Nếu khẳng định nói rộng hơn điều luật cho phép → `supported: false`.
- Mặc định là `false` khi không chắc.

Trả về JSON: {{"verdicts": [{{"claim_index": 0, "supported": true, "reason": "..."}}]}}

CÁC CẶP CẦN KIỂM:
{pairs}
