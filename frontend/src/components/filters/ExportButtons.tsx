import { ChevronDown, FileDown, Loader2, Sheet } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

type ExportButtonsProps = {
    onExportPdf?: () => void
    onExportExcelWithFilters?: () => void
    onExportExcelWithoutFilters?: () => void
    isExportingPdf?: boolean
    isExportingExcel?: boolean
    exportingExcelVariant?: "filtered" | "all" | null
    exportError?: string | null
}

export default function ExportButtons({
    onExportPdf,
    onExportExcelWithFilters,
    onExportExcelWithoutFilters,
    isExportingPdf = false,
    isExportingExcel = false,
    exportingExcelVariant = null,
    exportError,
}: ExportButtonsProps) {
    const handleExportClick = (mode: "filtered" | "all") => {
        if (mode === "filtered") {
            onExportExcelWithFilters?.()
            return
        }
        onExportExcelWithoutFilters?.()
    }

    return (
        <div className="ml-auto flex flex-col items-stretch gap-2">
            <div className="flex gap-2">
                <Button
                    onClick={onExportPdf}
                    variant="outline"
                    className="h-14 rounded-2xl px-5 text-base"
                    disabled={isExportingPdf}
                >
                    {isExportingPdf ? <Loader2 className="size-4 animate-spin" /> : <FileDown className="size-4" />}
                    {isExportingPdf ? "Generando PDF..." : "Exportar PDF"}
                </Button>
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button
                            variant="outline"
                            className="h-14 rounded-2xl px-5 text-base"
                            disabled={isExportingExcel}
                        >
                            {isExportingExcel ? <Loader2 className="size-4 animate-spin" /> : <Sheet className="size-4" />}
                            {isExportingExcel ? "Exportando..." : "Exportar Excel"}
                            <ChevronDown className="size-4" />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="min-w-64 rounded-2xl p-2">
                        <DropdownMenuItem
                            className="rounded-xl px-3 py-3"
                            disabled={isExportingExcel}
                            onClick={() => handleExportClick("filtered")}
                        >
                            <span>Exportar con filtros</span>
                            {exportingExcelVariant === "filtered" ? <Loader2 className="ml-auto size-4 animate-spin" /> : null}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                            className="rounded-xl px-3 py-3"
                            disabled={isExportingExcel}
                            onClick={() => handleExportClick("all")}
                        >
                            <span>Exportar sin filtros</span>
                            {exportingExcelVariant === "all" ? <Loader2 className="ml-auto size-4 animate-spin" /> : null}
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
            {exportError ? <p className="text-sm text-destructive">{exportError}</p> : null}
        </div>
    )
}
