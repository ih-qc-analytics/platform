import type { ReactNode } from "react"

import ExportButtons from "@/components/filters/ExportButtons"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

type ReportFilterBarShellProps = {
    children: ReactNode
    onClear?: () => void
    onExportPdf?: () => void
    onExportExcelWithFilters?: () => void
    onExportExcelWithoutFilters?: () => void
    isExportingPdf?: boolean
    isExportingExcel?: boolean
    exportingExcelVariant?: "filtered" | "all" | null
    exportError?: string | null
}

export default function ReportFilterBarShell({
    children,
    onClear,
    onExportPdf,
    onExportExcelWithFilters,
    onExportExcelWithoutFilters,
    isExportingPdf,
    isExportingExcel,
    exportingExcelVariant,
    exportError,
}: ReportFilterBarShellProps) {
    return (
        <Card className="rounded-[2rem] shadow-sm">
            <CardContent className="flex flex-col gap-5 p-6 xl:flex-row xl:items-end xl:justify-between">
                <div className="flex flex-1 flex-wrap items-end gap-4">
                    {children}
                </div>
                <div className="flex flex-col items-stretch gap-3 xl:items-end">
                    {onClear ? (
                        <Button variant="ghost" className="self-start rounded-2xl px-2 text-sm text-slate-600" onClick={onClear}>
                            Limpiar filtros
                        </Button>
                    ) : null}
                    <ExportButtons
                        onExportPdf={onExportPdf}
                        onExportExcelWithFilters={onExportExcelWithFilters}
                        onExportExcelWithoutFilters={onExportExcelWithoutFilters}
                        isExportingPdf={isExportingPdf}
                        isExportingExcel={isExportingExcel}
                        exportingExcelVariant={exportingExcelVariant}
                        exportError={exportError}
                    />
                </div>
            </CardContent>
        </Card>
    )
}
