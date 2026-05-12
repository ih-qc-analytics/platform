import { pdf } from "@react-pdf/renderer"
import type { DocumentProps } from "@react-pdf/renderer"
import type { ReactElement } from "react"

export const downloadPdf = async (
    document: ReactElement<DocumentProps>,
    filename: string,
): Promise<void> => {
    const blob = await pdf(document).toBlob()
    const url = URL.createObjectURL(blob)
    const anchor = window.document.createElement("a")
    anchor.href = url
    anchor.download = filename
    window.document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
}
