import { Download } from "lucide-react"

type ExportButtonsProps = {
    onExportPdf?: () => void
    onExportExcel?: () => void
}

export default function ExportButtons({ onExportPdf, onExportExcel }: ExportButtonsProps) {
    return (
        <div className="flex gap-2 ml-auto">
            <button
                onClick={onExportPdf}
                className="flex items-center gap-2 px-4 py-2 text-sm border rounded-md hover:bg-accent"
            >
                <Download className="size-4" />
                Exportar PDF
            </button>
            <button
                onClick={onExportExcel}
                className="flex items-center gap-2 px-4 py-2 text-sm border rounded-md hover:bg-accent"
            >
                <Download className="size-4" />
                Exportar Excel
            </button>
        </div>
    )
}