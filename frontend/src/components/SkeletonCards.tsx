import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/** Состояние загрузки для списков карточек. */
export function SkeletonCards({ count = 3, className }: { count?: number; className?: string }) {
  return (
    <div className={cn("grid gap-4", className)} aria-busy="true" aria-label="Загрузка">
      {Array.from({ length: count }, (_, index) => (
        <Card key={index}>
          <CardHeader>
            <Skeleton className="h-5 w-1/3" />
            <Skeleton className="h-4 w-1/2" />
          </CardHeader>
          <CardContent className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-4/5" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
