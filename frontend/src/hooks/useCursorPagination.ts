import { useCallback, useState } from "react"

export default function useCursorPagination<TCursor>() {
    const [page, setPage] = useState(0)
    const [pageCursors, setPageCursors] = useState<Array<TCursor | null>>([null])

    const currentCursor = pageCursors[page] ?? null

    const reset = useCallback(() => {
        setPage(0)
        setPageCursors([null])
    }, [])

    const goPrevious = useCallback(() => {
        setPage((current) => Math.max(0, current - 1))
    }, [])

    const goNext = useCallback(
        (nextCursor: TCursor | null | undefined) => {
            if (nextCursor == null) return

            setPageCursors((current) => {
                if (current[page + 1] === nextCursor) return current

                const next = current.slice(0, page + 1)
                next.push(nextCursor)
                return next
            })
            setPage((current) => current + 1)
        },
        [page],
    )

    return {
        page,
        currentCursor,
        reset,
        goPrevious,
        goNext,
    }
}
