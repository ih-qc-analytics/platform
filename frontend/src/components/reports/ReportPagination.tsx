import { ChevronLeft, ChevronRight } from "lucide-react"

import { Button } from "@/components/ui/button"

type ReportPaginationProps = {
    page: number
    currentCount: number
    hasMore: boolean
    onPrevious: () => void
    onNext: () => void
}

export default function ReportPagination({ page, currentCount, hasMore, onPrevious, onNext }: ReportPaginationProps) {
    if (currentCount === 0) return null

    return (
        <div className="flex flex-col gap-3 border-t border-border px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
                Pagina {page + 1} · {currentCount} resultados
            </p>
            <div className="flex items-center gap-2 self-end sm:self-auto">
                <Button variant="outline" size="sm" onClick={onPrevious} disabled={page === 0}>
                    <ChevronLeft className="size-4" />
                    Anterior
                </Button>
                <span className="min-w-20 text-center text-sm font-medium text-foreground">Pagina {page + 1}</span>
                <Button variant="outline" size="sm" onClick={onNext} disabled={!hasMore}>
                    Siguiente
                    <ChevronRight className="size-4" />
                </Button>
            </div>
        </div>
    )
}
