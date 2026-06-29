import { API_BASE } from '../prompts';

export default function ExcelUpload() {
  async function upload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${API_BASE}/api/excel/upload`, { method: 'POST', body: formData });
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'saenggibu_results.xlsx';
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="excel-actions">
      <a className="secondary-button" href={`${API_BASE}/api/excel/template`}>엑셀 양식 다운로드</a>
      <label className="secondary-button upload-label">
        엑셀 업로드·일괄처리
        <input type="file" accept=".xlsx" onChange={upload} hidden />
      </label>
    </div>
  );
}
