import { FileDown, Sheet } from "lucide-react"

import { Button } from "@/components/ui/button"

type ExportButtonsProps = {
    onExportPdf?: () => void
    onExportExcel?: () => void
}

export default function ExportButtons({ onExportPdf, onExportExcel }: ExportButtonsProps) {
    return (
        <div className="flex gap-2 ml-auto">
            <Button
                onClick={onExportPdf}
                variant="outline"
                className="h-14 rounded-2xl px-5 text-base"
            >
                <FileDown className="size-4" />
                Exportar PDF
            </Button>
            <Button
                onClick={onExportExcel}
                variant="outline"
                className="h-14 rounded-2xl px-5 text-base"
            >
                <Sheet className="size-4" />
                Exportar Excel
            </Button>
        </div>
    )
}
