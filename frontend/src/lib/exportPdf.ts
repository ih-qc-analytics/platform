const parseFilename = (contentDisposition: string | null, fallback: string): string => {
    const match = contentDisposition?.match(/filename="?([^"]+)"?/)
    return match?.[1] ?? fallback
}

export const downloadPdfBlob = async (
    blob: Blob,
    fallbackFilename: string,
    contentDisposition?: string | null,
): Promise<void> => {
    const filename = parseFilename(contentDisposition ?? null, fallbackFilename)
    const url = URL.createObjectURL(blob)
    const anchor = window.document.createElement("a")
    anchor.href = url
    anchor.download = filename
    window.document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
}
