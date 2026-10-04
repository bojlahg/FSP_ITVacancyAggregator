import { isRouteErrorResponse, Link, useRouteError } from "react-router";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";

export default function RouteErrorPage() {
  const error = useRouteError();
  const status = isRouteErrorResponse(error) ? error.status : 500;
  if (import.meta.env.DEV) console.error(error);

  return (
    <div className="flex min-h-dvh flex-col gap-10 px-4 py-6 sm:px-8 lg:px-16">
      <Link to="/" aria-label="На главную">
        <Logo className="h-8" />
      </Link>
      <div className="flex flex-col gap-4" role="alert">
        <span className="font-mono text-sm text-muted-foreground">
          status: <code className="text-primary">{status}</code>
        </span>
        <h1 className="text-3xl font-extrabold">Что-то пошло не так</h1>
        <p className="max-w-lg text-muted-foreground">
          Произошла ошибка при открытии страницы. Обновите страницу или вернитесь на главную.
        </p>
        <div className="flex gap-3">
          <Button onClick={() => window.location.reload()}>Обновить</Button>
          <Button asChild variant="outline">
            <Link to="/">На главную</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
