import type { ReactNode } from "react";
import { Trace } from "@/components/Trace";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/** Общая обёртка для экранов входа/регистрации/подтверждения почты. */
export function AuthCard({ title, description, children }: { title: string; description?: ReactNode; children: ReactNode }) {
  return (
    <div className="relative flex flex-1 items-center justify-center py-12">
      <Trace width={300} height={420} radius={48} className="absolute top-8 right-0 hidden xl:block" />
      <Card className="relative w-full max-w-md gap-6 py-7 shadow-sm">
        <CardHeader className="px-7">
          <CardTitle className="text-2xl font-extrabold">
            <h1>{title}</h1>
          </CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
        <CardContent className="px-7">{children}</CardContent>
      </Card>
    </div>
  );
}
