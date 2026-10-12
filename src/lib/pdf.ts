/**
 * Сохраняет HTML-элемент в PDF (A4, книжная).
 * Элемент растеризуется через html2canvas-pro: так кириллица и шрифт Inter выглядят
 * как на экране — встроенные шрифты jsPDF кириллицу не поддерживают.
 */
export async function elementToPdf(el: HTMLElement, fileName: string) {
  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([import('html2canvas-pro'), import('jspdf')])
  await document.fonts?.ready
  const canvas = await html2canvas(el, { scale: 2, backgroundColor: '#ffffff' })
  const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
  const pageW = pdf.internal.pageSize.getWidth()
  const pageH = pdf.internal.pageSize.getHeight()
  const imgH = (canvas.height * pageW) / canvas.width
  const data = canvas.toDataURL('image/jpeg', 0.92)
  // Если бланк длиннее страницы — продолжаем на следующих
  let y = 0
  pdf.addImage(data, 'JPEG', 0, y, pageW, imgH)
  while (imgH + y > pageH + 1) {
    y -= pageH
    pdf.addPage()
    pdf.addImage(data, 'JPEG', 0, y, pageW, imgH)
  }
  pdf.save(fileName)
}
