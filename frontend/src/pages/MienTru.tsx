/**
 * Read — trang có hậu quả thật. KLAW trả lời câu hỏi pháp luật cho người lao
 * động thật; nội dung ở đây là bắt buộc theo site-spec.md, viết bằng lời
 * thường để người lao động đọc hiểu ngay. Không làm nhẹ đi các sự thật đo
 * được của dự án (4 nghị định bị CSDL quốc gia đánh sai hiệu lực, corpus là
 * văn bản gốc không phải bản hợp nhất, đây là sản phẩm khóa luận tốt nghiệp).
 */
export default function MienTru() {
  return (
    <div className="mx-auto w-full max-w-[46rem] px-4 py-10">
      <h1 className="mat-doc text-2xl font-semibold text-phim focus:outline-2 focus:outline-den-sang focus:outline-offset-4 md:text-3xl">
        Miễn trừ trách nhiệm
      </h1>
      <p className="mat-doc mt-3 text-phim">
        Đọc trang này trước khi dựa vào một câu trả lời của KLAW để quyết định điều gì đó. Không
        có đoạn nào dưới đây là câu rào đón cho có — đây là những giới hạn thật của hệ thống.
      </p>

      <section className="mt-8">
        <h2 className="text-lg font-medium text-phim">KLAW không phải tư vấn pháp lý</h2>
        <p className="mat-doc mt-3 text-phim">
          KLAW không thay thế luật sư, cán bộ công đoàn, hay thanh tra lao động. Đây là công cụ
          tra cứu và soạn thảo, giúp bạn tìm nhanh điều luật liên quan và đọc đúng nguyên văn —
          không phải một ý kiến pháp lý cho tình huống cụ thể của bạn.
        </p>
        <p className="mat-doc mt-2 text-phim">
          Với bất kỳ quyết định nào có hậu quả thật — bị sa thải, tranh chấp lương, khởi kiện, ký
          một văn bản ràng buộc — hãy để người có chuyên môn kiểm tra lại trước khi hành động.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-medium text-phim">
          Văn bản gốc, không phải bản hợp nhất
        </h2>
        <p className="mat-doc mt-3 text-phim">
          Một điều luật có thể được sửa đổi nhiều lần theo thời gian. "Bản hợp nhất" là bản đã gộp
          mọi lần sửa đổi thành một bản duy nhất, phản ánh đúng điều luật tại thời điểm hiện tại.
          Kho dữ liệu của KLAW <strong className="font-medium">không chứa bản hợp nhất</strong> —
          chỉ chứa văn bản gốc, tức bản được công bố tại thời điểm ban hành.
        </p>
        <p className="mat-doc mt-2 text-phim">
          Hệ thống bảo đảm hai điều: trích dẫn bạn thấy{' '}
          <strong className="font-medium">có thật</strong> (nó trỏ đúng tới một văn bản tồn tại
          trong kho), và câu trích{' '}
          <strong className="font-medium">đúng nguyên văn</strong> (không bị rút gọn hay sửa
          chính tả). Hệ thống{' '}
          <strong className="font-medium">không bảo đảm</strong> đây là bản{' '}
          <strong className="font-medium">đang có hiệu lực</strong> tại thời điểm bạn đọc — một
          văn bản sau đó có thể đã sửa đổi hoặc thay thế điều luật này. Luôn đọc nhãn hiệu lực đi
          kèm mỗi trích dẫn, và đối chiếu với nguồn chính thức trước khi hành động.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-medium text-phim">
          Ngay cả cơ sở dữ liệu chính thức cũng có sai sót
        </h2>
        <p className="mat-doc mt-3 text-phim">
          Cơ sở dữ liệu văn bản quy phạm pháp luật quốc gia — nguồn mà KLAW và nhiều hệ thống khác
          dựa vào — đã đánh dấu{' '}
          <strong className="font-medium">bốn nghị định quy định mức lương tối thiểu</strong> là
          "còn hiệu lực" dù chúng thực tế đã bị thay thế. KLAW phát hiện và sửa cả bốn trường hợp
          này trong dữ liệu của mình.
        </p>
        <p className="mat-doc mt-2 text-phim">
          Đây không phải lời khẳng định rằng KLAW không thể sai — ngược lại, nó là bằng chứng đo
          được rằng ngay cả nguồn chính thức cũng có sai sót. Vì vậy, đừng coi bất kỳ nguồn nào —
          kể cả KLAW — là đúng tuyệt đối. Luôn đối chiếu trước khi hành động, đặc biệt với những
          quyết định có hậu quả thật.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-medium text-phim">Đây là sản phẩm khóa luận tốt nghiệp</h2>
        <p className="mat-doc mt-3 text-phim">
          KLAW được xây dựng như một sản phẩm khóa luận tốt nghiệp, với cơ chế kiểm chứng trích
          dẫn thật và được đo lường nghiêm túc — nhưng đây không phải một dịch vụ pháp lý thương
          mại có đội ngũ hỗ trợ hay cam kết chất lượng dịch vụ. Hãy cân nhắc điều đó khi quyết định
          mức độ tin cậy đặt vào một câu trả lời.
        </p>
      </section>
    </div>
  );
}
