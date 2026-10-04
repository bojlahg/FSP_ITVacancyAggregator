import { Link } from "react-router";
import { Logo } from "@/components/Logo";
import { Trace } from "@/components/Trace";
import { Button } from "@/components/ui/button";

export default function NotFoundPage() {
  return (
    <div className="relative flex min-h-dvh flex-col overflow-hidden px-4 py-6 sm:px-8 lg:px-16">
      <Link to="/" aria-label="На главную">
        <Logo className="h-8" />
      </Link>
      <div className="flex flex-1 flex-col justify-center gap-6 py-16">
        <span className="font-mono text-sm font-medium text-muted-foreground">
          status: <code className="text-primary">404 Not Found</code>
        </span>
        <h1 className="text-6xl font-extrabold tracking-tighter text-primary sm:text-8xl">
          4<span className="text-foreground">0</span>4
        </h1>
        <p className="max-w-lg text-lg">Такой страницы нет. Возможно, ссылка устарела или в адресе опечатка.</p>
        <div className="flex flex-wrap gap-3">
          <Button asChild>
            <Link to="/">На главную</Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/login">Войти</Link>
          </Button>
        </div>
      </div>
      <Trace width={260} height={360} radius={48} className="absolute top-24 right-16 hidden xl:block" />
    </div>
  );
}
