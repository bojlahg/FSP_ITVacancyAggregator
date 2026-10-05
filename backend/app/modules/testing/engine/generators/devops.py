"""Генераторы DevOps-заданий: права, конвейеры shell, подсети, Kubernetes, CI/CD, Terraform."""

import ipaddress
import math
import random
from collections import Counter

from app.modules.testing.engine.generators import generator
from app.modules.testing.engine.model import Generated

USERS = ["anna", "boris", "vera", "gleb", "dina", "egor", "zoya", "ivan", "lena", "maks"]
APPS = ["billing", "orders", "auth", "gateway", "catalog", "notifier", "reports", "payments"]


def _rwx(bits: int) -> str:
    return ("r" if bits & 4 else "-") + ("w" if bits & 2 else "-") + ("x" if bits & 1 else "-")


@generator("devops.chmod_octal")
def chmod_octal(rng: random.Random) -> Generated:
    """Права rwx → восьмеричная запись для chmod."""
    # правдоподобные права: у группы не больше прав, чем у владельца, у остальных — не больше, чем у группы
    owner = rng.choice([4, 5, 6, 7])
    group = owner & rng.choice([0, 4, 5, 6, 7])
    other = group & rng.choice([0, 0, 4, 5])
    symbolic = "-" + _rwx(owner) + _rwx(group) + _rwx(other)
    name = rng.choice(["deploy.sh", "backup.sh", "config.yaml", "app.env", "run.py", "release.tar.gz"])
    stem = rng.choice(
        [
            f"ls -l показывает для файла {name} права {symbolic}. Какое восьмеричное число нужно "
            "передать chmod, чтобы получить такие же права? Ответ — три цифры.",
            f"Нужно выставить файлу {name} права {symbolic}. Какое значение указать в команде "
            f"chmod ??? {name}? Ответ — три восьмеричные цифры.",
        ]
    )
    return Generated(stem=stem, number=float(owner * 100 + group * 10 + other), tolerance=0)


def _runs(values: list[str]) -> int:
    return sum(1 for index, value in enumerate(values) if index == 0 or values[index - 1] != value)


@generator("devops.uniq_without_sort")
def uniq_without_sort(rng: random.Random) -> Generated:
    """uniq убирает только соседние повторы — без sort это не подсчёт уникальных строк."""
    while True:
        pool = rng.sample(USERS, rng.randint(3, 4))
        lines = [rng.choice(pool) for _ in range(rng.randint(8, 11))]
        total, runs, distinct = len(lines), _runs(lines), len(set(lines))
        if len({total, runs, distinct}) == 3 and runs - distinct >= 2:
            break
    file = rng.choice(["users.txt", "logins.log", "authors.txt"])
    command = rng.choice([f"uniq {file} | wc -l", f"cat {file} | uniq | wc -l"])
    code = "\n".join([f"$ cat {file}", *lines, f"$ {command}"])
    wrong = {str(distinct), str(total), str(runs - 1), str(runs + 1), str(total - distinct)}
    wrong.discard(str(runs))
    return Generated(
        stem="Что выведет последняя команда?",
        code=code,
        code_language="bash",
        correct=(str(runs),),
        wrong=tuple(sorted(wrong)),
    )


@generator("devops.top_ip_pipeline")
def top_ip_pipeline(rng: random.Random) -> Generated:
    """Классический конвейер «самый частый IP»: awk | sort | uniq -c | sort -rn | head."""
    paths = ["/api/orders", "/api/users", "/health", "/login", "/api/cart", "/static/app.js"]
    while True:
        ips = [f"10.0.{rng.randint(0, 9)}.{rng.randint(2, 254)}" for _ in range(4)]
        if len(set(ips)) < 4:
            continue
        lines = [rng.choice(ips) for _ in range(rng.randint(9, 12))]
        counts = Counter(lines).most_common()
        if len(counts) < 4 or counts[0][1] == counts[1][1]:
            continue
        top = counts[0][0]
        # самый частый IP не стоит первым или последним в файле: ответ не угадать по краям
        if lines[0] == top or lines[-1] == top:
            continue
        break
    log = [
        f"{ip} {rng.choice(['GET', 'POST'])} {rng.choice(paths)} {rng.choice([200, 200, 201, 404, 500])}"
        for ip in lines
    ]
    tail = rng.choice(["sort -rn | head -n 1", "sort -n | tail -n 1"])
    code = "\n".join(["$ cat access.log", *log, f"$ awk '{{print $1}}' access.log | sort | uniq -c | {tail}"])
    return Generated(
        stem="Какой IP-адрес окажется в выводе последней команды?",
        code=code,
        code_language="bash",
        correct=(top,),
        wrong=tuple(ip for ip, _ in counts[1:]),
    )


SIGNALS = {
    "SIGKILL": 9,
    "SIGTERM": 15,
    "SIGSEGV": 11,
    "SIGINT": 2,
}


@generator("devops.exit_code_signal")
def exit_code_signal(rng: random.Random) -> Generated:
    """Код выхода > 128 у контейнера — завершение сигналом 128 + N."""
    signal = rng.choice(list(SIGNALS))
    code = 128 + SIGNALS[signal]
    name = rng.choice(APPS)
    stem = rng.choice(
        [
            f"docker ps -a показывает у контейнера {name} статус Exited ({code}). Что означает этот код?",
            f"Под {name} в Kubernetes перезапускается, в lastState указан exitCode: {code}. "
            "Что означает этот код завершения?",
        ]
    )
    wrong = [
        f"Процесс завершён сигналом {other} (128 + {number})"
        for other, number in SIGNALS.items()
        if other != signal
    ]
    wrong += [
        "Не найден исполняемый файл из ENTRYPOINT/CMD",
        f"Процесс сам вызвал exit(1), а Docker прибавил к коду {code - 1}",
    ]
    return Generated(
        stem=stem,
        correct=(f"Процесс завершён сигналом {signal} (128 + {SIGNALS[signal]})",),
        wrong=tuple(wrong),
    )


@generator("devops.k8s_probe")
def k8s_probe(rng: random.Random) -> Generated:
    """Назначение liveness/readiness/startup-проб."""
    app = rng.choice(APPS)
    cases = {
        "readinessProbe": f"При провале проверки под {app} должен перестать получать трафик через Service, "
        "но контейнер не должен перезапускаться. Какую пробу настроить?",
        "livenessProbe": f"Приложение {app} иногда зависает (deadlock): процесс жив, но запросы не "
        "обрабатывает. Какая проба приведёт к перезапуску контейнера kubelet'ом?",
        "startupProbe": f"Приложение {app} стартует до нескольких минут, и проба живости успевает "
        "убить его до окончания запуска. Какая проба откладывает остальные проверки до успешного старта?",
    }
    correct = rng.choice(list(cases))
    wrong = [name for name in cases if name != correct] + ["lifecycle.postStart", "lifecycle.preStop"]
    return Generated(stem=cases[correct], correct=(correct,), wrong=tuple(wrong))


@generator("devops.k8s_qos")
def k8s_qos(rng: random.Random) -> Generated:
    """QoS-класс пода по requests/limits единственного контейнера."""
    cpu = rng.choice([100, 250, 500, 1000])
    mem = rng.choice([128, 256, 512, 1024])
    variant = rng.choice(["equal", "lower", "requests_only", "mixed"])
    if variant == "equal":
        resources = {"requests": (cpu, mem), "limits": (cpu, mem)}
        answer = "Guaranteed"
    elif variant == "lower":
        resources = {"requests": (cpu, mem), "limits": (cpu * 2, mem * 2)}
        answer = "Burstable"
    elif variant == "requests_only":
        resources = {"requests": (cpu, mem)}
        answer = "Burstable"
    else:
        resources = {"requests": (cpu, mem), "limits": (cpu, mem * 2)}
        answer = "Burstable"
    lines = [
        "apiVersion: v1",
        "kind: Pod",
        "metadata:",
        f"  name: {rng.choice(APPS)}",
        "spec:",
        "  containers:",
        "    - name: app",
        f"      image: registry.local/app:{rng.randint(1, 9)}.{rng.randint(0, 20)}",
        "      resources:",
    ]
    for section, (section_cpu, section_mem) in resources.items():
        lines += [
            f"        {section}:",
            f'          cpu: "{section_cpu}m"',
            f"          memory: {section_mem}Mi",
        ]
    wrong = [name for name in ["Guaranteed", "Burstable", "BestEffort"] if name != answer]
    return Generated(
        stem="Какой QoS-класс Kubernetes присвоит этому поду?",
        code="\n".join(lines),
        code_language="yaml",
        correct=(answer,),
        wrong=tuple(wrong),
    )


@generator("devops.k8s_rolling_update")
def k8s_rolling_update(rng: random.Random) -> Generated:
    """RollingUpdate: maxSurge округляется вверх, maxUnavailable — вниз (документация Deployment)."""
    while True:
        replicas = rng.randint(4, 20)
        surge = rng.choice([10, 20, 25, 30, 40])
        unavailable = rng.choice([10, 20, 25, 30, 40])
        if replicas * surge % 100 and replicas * unavailable % 100 and replicas * unavailable >= 100:
            break
    ask_max = rng.random() < 0.5
    code = "\n".join(
        [
            "spec:",
            f"  replicas: {replicas}",
            "  strategy:",
            "    type: RollingUpdate",
            "    rollingUpdate:",
            f"      maxSurge: {surge}%",
            f"      maxUnavailable: {unavailable}%",
        ]
    )
    if ask_max:
        stem = (
            "Deployment обновляется на новую версию. Какое максимальное общее число подов (старых и новых) "
            "может существовать одновременно во время обновления?"
        )
        number = replicas + math.ceil(replicas * surge / 100)
    else:
        stem = (
            "Deployment обновляется на новую версию. Какое минимальное число подов должно оставаться "
            "доступным во время обновления?"
        )
        number = replicas - replicas * unavailable // 100
    return Generated(stem=stem, code=code, code_language="yaml", number=float(number), tolerance=0)


@generator("devops.entrypoint_cmd")
def entrypoint_cmd(rng: random.Random) -> Generated:
    """ENTRYPOINT + CMD в exec-форме: аргументы docker run заменяют CMD, а не ENTRYPOINT."""
    runtime, script = rng.choice(
        [("python", "app.py"), ("python", "server.py"), ("node", "server.js"), ("node", "index.js")]
    )
    flag = rng.choice(["--port", "--workers", "--log-level"])
    default_value, new_value = {
        "--port": ("8080", str(rng.choice([9000, 3000, 8443, 5000]))),
        "--workers": ("2", str(rng.choice([4, 8, 16]))),
        "--log-level": ("info", rng.choice(["debug", "warning", "error"])),
    }[flag]
    image = rng.choice(APPS)
    code = "\n".join(
        [
            "# Dockerfile",
            f"FROM {runtime}:{'3.12' if runtime == 'python' else '22'}-slim",
            "WORKDIR /app",
            "COPY . .",
            f'ENTRYPOINT ["{runtime}", "{script}"]',
            f'CMD ["{flag}", "{default_value}"]',
            "",
            f"$ docker run {image} {flag} {new_value}",
        ]
    )
    correct = f"{runtime} {script} {flag} {new_value}"
    wrong = [
        f"{flag} {new_value}",
        f"{runtime} {script} {flag} {default_value} {flag} {new_value}",
        f"{runtime} {script} {flag} {default_value}",
        f"{flag} {new_value} {runtime} {script}",
    ]
    return Generated(
        stem="Образ собран из этого Dockerfile. Какая команда выполнится в контейнере при таком запуске?",
        code=code,
        code_language="dockerfile",
        correct=(correct,),
        wrong=tuple(wrong),
    )


@generator("devops.ci_cache_or_artifacts")
def ci_cache_or_artifacts(rng: random.Random) -> Generated:
    """GitLab CI: artifacts передают результаты между job, cache ускоряет повторные установки."""
    service = rng.choice(APPS)
    build_job = rng.choice(["build", "compile", f"build-{service}", "package"])
    deploy_job = rng.choice(["deploy", "deploy-staging", f"deploy-{service}", "release"])
    binary = rng.choice(["app", "server", f"bin/{service}", "dist/", "target/app.jar", "build/libs/"])
    report = rng.choice(
        ["junit.xml", "report.xml", "test-results.xml", "coverage.xml", "gl-sast-report.json"]
    )
    folder, tool = rng.choice(
        [
            ("~/.npm", "npm"),
            (".cache/pip", "pip"),
            (".m2/repository", "Maven"),
            (".gradle/caches", "Gradle"),
            ("vendor/bundle", "Bundler"),
            (".go/pkg/mod", "Go modules"),
        ]
    )
    minutes = rng.randint(2, 9)
    cases = [
        (
            f"Job {build_job} на стадии build собирает {binary}, а job {deploy_job} на стадии deploy должен "
            "гарантированно получить именно этот результат сборки. Какой механизм GitLab CI "
            "для этого предназначен?",
            "artifacts",
        ),
        (
            f"Job test сервиса {service} создаёт отчёт {report}, который нужно сохранить вместе с пайплайном "
            "и показать в merge request. Какой механизм GitLab CI использовать?",
            "artifacts",
        ),
        (
            f"Каждый пайплайн {service} заново скачивает зависимости {tool} в {folder}, это занимает "
            f"около {minutes} мин. Какой механизм GitLab CI предназначен для ускорения повторных установок "
            "между пайплайнами (без гарантии, что данные будут на месте)?",
            "cache",
        ),
        (
            f"Нужно, чтобы {folder} с зависимостями {tool} переиспользовался следующими запусками job "
            f"lint и test сервиса {service}; если данных нет, job просто скачает всё заново. "
            "Какой механизм GitLab CI для этого предназначен?",
            "cache",
        ),
    ]
    stem, answer = rng.choice(cases)
    wrong = [name for name in ["artifacts", "cache"] if name != answer]
    wrong += ["variables", "services", "include", "extends", "environment", "image"]
    return Generated(stem=stem, correct=(answer,), wrong=tuple(wrong))


@generator("devops.deploy_strategy")
def deploy_strategy(rng: random.Random) -> Generated:
    """Стратегии выката по описанию."""
    service = rng.choice(APPS)
    share = rng.choice([1, 2, 5, 10])
    batch = rng.choice([1, 2, 3])
    cases = {
        "Blue-green": f"Рядом с работающей версией {service} поднимается полная копия окружения с новой "
        "версией; после проверки весь трафик переключается на неё разом, откат — обратным переключением.",
        "Canary": f"Новая версия {service} сначала получает {share}% трафика; если метрики в норме, "
        "доля постепенно увеличивается до 100%.",
        "Rolling update": f"Экземпляры {service} заменяются новой версией по {batch} за раз, без второго "
        "полного окружения; старые и новые версии какое-то время работают одновременно.",
        "Recreate": f"Все экземпляры старой версии {service} останавливаются, и только затем запускаются "
        "новые; в это время сервис недоступен.",
    }
    answer = rng.choice(list(cases))
    stem = f"Как называется стратегия выката? {cases[answer]}"
    wrong = [name for name in cases if name != answer] + ["Shadow (зеркалирование трафика)"]
    return Generated(stem=stem, correct=(answer,), wrong=tuple(wrong))


@generator("devops.subnet_broadcast")
def subnet_broadcast(rng: random.Random) -> Generated:
    """Широковещательный адрес подсети по адресу хоста и префиксу."""
    while True:
        prefix = rng.randint(20, 29)
        host = ipaddress.IPv4Address(f"10.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}")
        network = ipaddress.IPv4Network(f"{host}/{prefix}", strict=False)
        if host not in (network.network_address, network.broadcast_address):
            break
    broadcast = str(network.broadcast_address)
    wider = ipaddress.IPv4Network(f"{host}/{prefix - 1}", strict=False).broadcast_address
    narrower = ipaddress.IPv4Network(f"{host}/{prefix + 1}", strict=False).broadcast_address
    as_24 = ipaddress.IPv4Network(f"{host}/24", strict=False).broadcast_address
    wrong = {
        str(network.network_address),
        str(wider),
        str(narrower),
        str(as_24),
        str(network.broadcast_address - 1),
        str(network.broadcast_address + 1),
    }
    wrong.discard(broadcast)
    stem = rng.choice(
        [
            f"Хосту назначен адрес {host}/{prefix}. Какой широковещательный (broadcast) адрес у его подсети?",
            f"Интерфейс сервера: inet {host}/{prefix}. Какой адрес будет broadcast-адресом этой сети?",
        ]
    )
    return Generated(stem=stem, correct=(broadcast,), wrong=tuple(sorted(wrong)))


PORTS = {
    "SSH": 22,
    "DNS": 53,
    "HTTPS": 443,
    "SMTP": 25,
    "PostgreSQL": 5432,
    "MySQL": 3306,
    "Kubernetes API server (kube-apiserver)": 6443,
    "Redis": 6379,
}


@generator("devops.service_port")
def service_port(rng: random.Random) -> Generated:
    """Стандартные порты сервисов по умолчанию."""
    service = rng.choice(list(PORTS))
    stem = rng.choice(
        [
            f"Какой порт по умолчанию использует {service}?",
            f"В правилах файрвола нужно открыть доступ к {service} на стандартном порту. Какой это порт?",
        ]
    )
    wrong = [str(port) for name, port in PORTS.items() if name != service] + ["8080", "21", "3389"]
    return Generated(stem=stem, correct=(str(PORTS[service]),), wrong=tuple(wrong))


@generator("devops.dns_record_type")
def dns_record_type(rng: random.Random) -> Generated:
    """Тип DNS-записи под задачу."""
    domain = rng.choice(["shop.example", "itscout.test", "corp.example", "media.example"])
    cases = {
        "MX": f"Указать почтовые серверы, принимающие почту для домена {domain}.",
        "CNAME": f"Сделать имя www.{domain} псевдонимом имени lb.{domain}.",
        "AAAA": f"Сопоставить имени api.{domain} IPv6-адрес.",
        "PTR": "Настроить обратное разрешение: по IP-адресу почтового сервера получать его имя.",
        "TXT": f"Опубликовать SPF-политику или строку подтверждения владения доменом {domain}.",
        "NS": f"Делегировать зону dev.{domain} на другие DNS-серверы.",
    }
    answer = rng.choice(list(cases))
    wrong = [name for name in cases if name != answer] + ["A", "SOA", "SRV"]
    return Generated(
        stem=f"Какую DNS-запись нужно создать? Задача: {cases[answer]}",
        correct=(answer,),
        wrong=tuple(wrong),
    )


@generator("devops.connect_error")
def connect_error(rng: random.Random) -> Generated:
    """Различие connection refused / timeout / ошибка резолва имени."""
    host = rng.choice(
        [
            "db.internal",
            "api.internal",
            "cache.internal",
            "search.internal",
            "billing.svc.local",
            f"10.{rng.randint(0, 9)}.{rng.randint(0, 9)}.{rng.randint(2, 250)}",
        ]
    )
    port = rng.choice([5432, 8080, 6379, 9200, 443, 3306, 8443, 9092])
    client = rng.choice(["Клиент", "Сервис", "Скрипт деплоя", "Под приложения", "curl с бастиона"])
    explanations = {
        "refused": "На порту никто не слушает, или файрвол явно отклоняет соединение (RST/REJECT)",
        "timeout": "SYN остаётся без ответа: пакеты отбрасываются (DROP) файрволом или теряются по пути",
        "dns": "Имя не удалось разрешить в IP-адрес: проблема на стороне DNS",
        "tls": "Соединение установлено, но TLS-сертификат сервера не прошёл проверку",
        "auth": "Соединение установлено, но сервер отверг логин или пароль",
    }
    errors = {
        "refused": "Connection refused (ECONNREFUSED), ответ приходит мгновенно",
        "timeout": f"Connection timed out (ETIMEDOUT) спустя {rng.choice([20, 30, 60, 75, 120])} с",
    }
    if not host[0].isdigit():
        errors["dns"] = "Name or service not known (не удаётся получить адрес по имени)"
    case = rng.choice(list(errors))
    wrong = [text for name, text in explanations.items() if name != case]
    return Generated(
        stem=f"{client} подключается по TCP к {host}:{port} и получает ошибку: {errors[case]}. "
        "Что она наиболее вероятно означает?",
        correct=(explanations[case],),
        wrong=tuple(wrong),
    )


@generator("devops.prometheus_metric_type")
def prometheus_metric_type(rng: random.Random) -> Generated:
    """Тип метрики Prometheus под величину."""
    service = rng.choice(APPS)
    cases = [
        (f"общее число HTTP-запросов, обработанных сервисом {service} с момента запуска", "Counter"),
        (f"число ошибок оплаты в сервисе {service} с момента запуска", "Counter"),
        (f"сколько всего байт сервис {service} отправил клиентам с момента запуска", "Counter"),
        (f"число перезапусков воркеров сервиса {service} с момента запуска", "Counter"),
        (f"текущее число занятых соединений в пуле БД сервиса {service}", "Gauge"),
        (f"текущая длина очереди задач сервиса {service}", "Gauge"),
        (f"текущий объём памяти, занятый процессом {service}", "Gauge"),
        (f"температура или свободное место на диске хоста, где работает {service}", "Gauge"),
        (
            f"распределение длительности запросов к {service}, из которого нужно считать p95 "
            "по всем подам вместе",
            "Histogram",
        ),
        (
            f"распределение размеров ответов {service}, по которому нужно строить квантили "
            "суммарно для всех экземпляров",
            "Histogram",
        ),
    ]
    quantity, answer = rng.choice(cases)
    stem = rng.choice(
        [
            f"Какой тип метрики Prometheus подходит для величины: {quantity}?",
            f"Вы добавляете инструментирование в {service}. Нужно экспортировать {quantity}. "
            "Какой тип метрики Prometheus выбрать?",
        ]
    )
    wrong = [name for name in ["Counter", "Gauge", "Histogram", "Summary"] if name != answer]
    return Generated(stem=stem, correct=(answer,), wrong=tuple(wrong))


@generator("devops.terraform_count_shift")
def terraform_count_shift(rng: random.Random) -> Generated:
    """count адресует ресурсы по индексу: удаление элемента из середины списка сдвигает индексы."""
    names = rng.sample(["alpha", "beta", "gamma", "delta", "omega", "sigma", "kappa"], rng.randint(3, 5))
    removed = rng.randrange(0, len(names) - 1)
    last = len(names) - 1
    resource = rng.choice(
        [
            "yandex_compute_instance",
            "yandex_vpc_subnet",
            "yandex_iam_service_account",
            "google_compute_instance",
        ]
    )
    listing = ", ".join(f'"{name}"' for name in names)
    code = "\n".join(
        [
            'variable "names" {',
            f"  default = [{listing}]",
            "}",
            "",
            f'resource "{resource}" "node" {{',
            "  count = length(var.names)",
            "  name  = var.names[count.index]",
            "  # ...",
            "}",
        ]
    )
    stem = (
        f'Ресурсы уже созданы. Из списка names удалили элемент "{names[removed]}". '
        "Что покажет terraform plan (имя ресурса — аргумент, требующий изменения)?"
    )
    shifted = f"[{removed}]" if removed == last - 1 else f"[{removed}]…[{last - 1}]"
    correct = (
        f"Ресурсы с индексами {shifted} получат имена соседей и будут изменены или "
        f"пересозданы, а ресурс [{last}] будет удалён"
    )
    wrong = [
        f'Будет удалён только ресурс с именем "{names[removed]}", остальные не изменятся',
        "Изменений не будет: Terraform сопоставляет ресурсы по значению name",
        f"Будут удалены и созданы заново все {len(names)} ресурсов",
        "terraform plan завершится ошибкой: индексы в state не совпадают с конфигурацией",
    ]
    return Generated(stem=stem, code=code, code_language="hcl", correct=(correct,), wrong=tuple(wrong))


@generator("devops.grep_count")
def grep_count(rng: random.Random) -> Generated:
    """grep -c считает строки с совпадением, а не число совпадений."""
    pattern, single, double = rng.choice(
        [
            ("ERROR", "ERROR {app} upstream failed", "ERROR {app} retry failed: ERROR from upstream"),
            ("timeout", "WARN {app} db timeout", "ERROR {app} timeout after retry, previous timeout 5s"),
            ("refused", "WARN {app} connection refused", "ERROR {app} refused: upstream refused twice"),
            ("WARN", "WARN {app} slow query", "WARN {app} WARN threshold exceeded"),
        ]
    )
    while True:
        lines: list[str] = []
        occurrences = 0
        for index in range(rng.randint(7, 11)):
            moment = f"12:{index * 3 + rng.randint(0, 2):02d}:{rng.randint(0, 59):02d}"
            hits = rng.choice([0, 0, 1, 1, 2])
            occurrences += hits
            app = rng.choice(APPS)
            if hits == 0:
                lines.append(f"{moment} {rng.choice(['INFO', 'DEBUG'])} {app} request handled")
            else:
                lines.append(f"{moment} " + (single if hits == 1 else double).format(app=app))
        matched = sum(pattern in line for line in lines)
        if 2 <= matched < occurrences < len(lines):
            break
    file = rng.choice(["app.log", "worker.log", "service.log", "gateway.log"])
    code = "\n".join([f"$ cat {file}", *lines, f"$ grep -c {pattern} {file}"])
    wrong = {str(occurrences), str(len(lines)), str(len(lines) - matched), str(matched + 1), str(matched - 1)}
    wrong.discard(str(matched))
    return Generated(
        stem="Что выведет последняя команда?",
        code=code,
        code_language="bash",
        correct=(str(matched),),
        wrong=tuple(sorted(wrong)),
    )


DATA_DIRS = {
    "postgres": "/var/lib/postgresql/data",
    "mysql": "/var/lib/mysql",
    "mongo": "/data/db",
    "redis": "/data",
}


@generator("devops.volume_persistence")
def volume_persistence(rng: random.Random) -> Generated:
    """Данные в слое контейнера пропадают вместе с контейнером — нужен volume на каталог данных."""
    image = rng.choice(list(DATA_DIRS))
    tag = {"postgres": "16", "mysql": "8.4", "mongo": "7", "redis": "7"}[image]
    name = rng.choice([f"{image}-dev", f"{image}-test", f"{rng.choice(APPS)}-db", "local-db"])
    volume = rng.choice(["dbdata", f"{image}_data", "pgdata" if image == "postgres" else f"{name}-vol"])
    path = DATA_DIRS[image]
    action = rng.choice(
        [
            f"контейнер удалили (docker rm -f {name}) и запустили заново той же командой",
            f"после обновления образа {image}:{tag} контейнер {name} пересоздали",
            f"docker compose down и docker compose up пересоздали контейнер {name}",
        ]
    )
    stem = (
        f"База {image} работала в контейнере {name}, запущенном без дополнительных опций хранения. "
        f"Затем {action}, и все данные пропали. Как это предотвратить?"
    )
    correct = f"Подключить именованный volume на каталог данных: -v {volume}:{path}"
    wrong = [
        "Запускать контейнер с флагом --restart always",
        "Останавливать контейнер через docker stop, а не docker kill",
        f"Сделать docker commit контейнера {name} перед удалением и запускать из нового образа",
        f"Подключить volume на /tmp, а данные {image} оставить на месте",
        "Добавить в Dockerfile инструкцию EXPOSE для порта базы",
    ]
    return Generated(stem=stem, correct=(correct,), wrong=tuple(wrong))


@generator("devops.k8s_service_selector")
def k8s_service_selector(rng: random.Random) -> Generated:
    """Service без endpoints: selector не совпадает с метками подов."""
    app = rng.choice(APPS)
    key = rng.choice(["app", "app.kubernetes.io/name", "component"])
    pod_value = rng.choice([app, f"{app}-api", f"{app}-svc"])
    service_value = rng.choice(
        [value for value in [app, f"{app}-api", f"{app}-svc", f"{app}-app"] if value != pod_value]
    )
    port = rng.choice([8080, 8000, 3000, 9090, 5000])
    replicas = rng.randint(2, 5)
    code = "\n".join(
        [
            "apiVersion: apps/v1",
            "kind: Deployment",
            f"metadata: {{name: {app}}}",
            "spec:",
            f"  replicas: {replicas}",
            f"  selector: {{matchLabels: {{{key}: {pod_value}}}}}",
            "  template:",
            f"    metadata: {{labels: {{{key}: {pod_value}}}}}",
            "    spec:",
            "      containers:",
            f"        - {{name: app, image: registry.local/{app}:1.{rng.randint(0, 30)}, "
            f"ports: [{{containerPort: {port}}}]}}",
            "---",
            "apiVersion: v1",
            "kind: Service",
            f"metadata: {{name: {app}}}",
            "spec:",
            f"  selector: {{{key}: {service_value}}}",
            f"  ports: [{{port: 80, targetPort: {port}}}]",
        ]
    )
    stem = rng.choice(
        [
            f"Поды Deployment {app} ({replicas} шт.) в статусе Running и Ready, но "
            f"kubectl get endpoints {app} показывает <none>, а запросы к Service падают. В чём причина?",
            f"Запросы к Service {app} не доходят до подов: у Service нет endpoints, хотя все реплики "
            f"({replicas} шт.) работают и проходят readiness. Почему?",
        ]
    )
    correct = "selector Service не совпадает с метками подов, поэтому Service не выбирает ни одного пода"
    wrong = [
        f"Service слушает порт 80, а контейнер — {port}: порты должны совпадать",
        "У Service не указан type: LoadBalancer",
        "Поды не попадают в endpoints, пока не пройдёт livenessProbe",
        "Deployment и Service с одинаковым именем конфликтуют",
        f"В контейнере не указан hostPort: {port}",
        "Метки в selector Deployment и в метаданных шаблона пода должны различаться",
    ]
    return Generated(stem=stem, code=code, code_language="yaml", correct=(correct,), wrong=tuple(wrong))


CI_FILES = {
    "GitLab CI": ".gitlab-ci.yml в корне репозитория",
    "GitHub Actions": "YAML-файл в каталоге .github/workflows/",
    "Jenkins (Pipeline as code)": "Jenkinsfile в корне репозитория",
    "Bitbucket Pipelines": "bitbucket-pipelines.yml в корне репозитория",
    "Azure Pipelines": "azure-pipelines.yml в корне репозитория",
}


# Правдоподобные, но неверные пути с тем же названием CI: ответ не угадать по совпадению слов
CI_DECOYS = {
    "GitLab CI": [".gitlab/ci.yml в корне репозитория", "gitlab-ci.yaml в каталоге .ci/"],
    "GitHub Actions": [".github/actions.yml в корне репозитория", "github-workflow.yml в корне репозитория"],
    "Jenkins (Pipeline as code)": ["jenkins.yaml в корне репозитория", "Jenkinsfile в каталоге .jenkins/ci/"],
    "Bitbucket Pipelines": [".bitbucket/ci.yml в корне репозитория", "pipelines.yml в каталоге .bitbucket/"],
    "Azure Pipelines": [".azure/ci.yml в корне репозитория", "azure-ci.json в каталоге .azure/"],
}


@generator("devops.ci_config_file")
def ci_config_file(rng: random.Random) -> Generated:
    """Где по соглашению лежит описание пайплайна в популярных CI-системах."""
    ci = rng.choice(list(CI_FILES))
    repo = rng.choice([f"{app}-service" for app in APPS] + ["infra", "monorepo", "frontend"])
    stem = rng.choice(
        [
            f"Репозиторий {repo} подключают к {ci}. Где по умолчанию описывается пайплайн?",
            f"Вы хотите добавить пайплайн в репозиторий {repo}, сборки выполняет {ci}. "
            "Какой файл нужно создать?",
        ]
    )
    others = [path for name, path in CI_FILES.items() if name != ci]
    wrong = [*CI_DECOYS[ci], *rng.sample(others, 2)]
    return Generated(stem=stem, correct=(CI_FILES[ci],), wrong=tuple(wrong))


@generator("devops.semver_bump")
def semver_bump(rng: random.Random) -> Generated:
    """SemVer: MAJOR — несовместимые изменения, MINOR — новые функции, PATCH — исправления."""
    major, minor, patch = rng.randint(1, 9), rng.randint(1, 15), rng.randint(1, 20)
    library = rng.choice(["клиентская библиотека", "SDK платежей", "Helm-чарт", "CLI-утилита", "API-пакет"])
    changes = {
        "patch": "исправлена ошибка, публичный API не менялся",
        "minor": "добавлен новый необязательный метод, старый API работает как раньше",
        "major": "удалён устаревший метод публичного API",
    }
    kind = rng.choice(list(changes))
    versions = {
        "patch": f"{major}.{minor}.{patch + 1}",
        "minor": f"{major}.{minor + 1}.0",
        "major": f"{major + 1}.0.0",
    }
    wrong = {
        *[version for name, version in versions.items() if name != kind],
        f"{major}.{minor + 1}.{patch}",
        f"{major + 1}.{minor}.{patch}",
        f"{major}.{minor}.{patch}-1",
    }
    wrong.discard(versions[kind])
    return Generated(
        stem=f"Текущая версия: {library} {major}.{minor}.{patch}. В новом релизе {changes[kind]}. "
        "Какой должна быть следующая версия по Semantic Versioning?",
        correct=(versions[kind],),
        wrong=tuple(sorted(wrong)),
    )


def _stage_jobs(rng: random.Random, prefix: str, low: int, high: int) -> list[str]:
    names = {
        "build": ["build-api", "build-web", "build-worker", "build-docs", "build-cli"],
        "test": ["unit", "lint", "integration", "e2e", "sast", "typecheck"],
        "deploy": ["deploy-staging", "deploy-docs", "publish-chart", "notify"],
    }[prefix]
    return rng.sample(names, rng.randint(low, high))


@generator("devops.ci_stage_failure")
def ci_stage_failure(rng: random.Random) -> Generated:
    """GitLab CI: job одной стадии идут параллельно, после провала следующая стадия не стартует."""
    build, test = _stage_jobs(rng, "build", 1, 3), _stage_jobs(rng, "test", 2, 4)
    deploy = _stage_jobs(rng, "deploy", 1, 3)
    failed = rng.choice(test)
    lines = ["stages: [build, test, deploy]", ""]
    for stage, jobs in (("build", build), ("test", test), ("deploy", deploy)):
        for job in jobs:
            lines += [f"{job}:", f"  stage: {stage}", f"  script: [./ci/{job}.sh]", ""]
    stem = (
        f"Пайплайн GitLab CI описан так (runners хватает на все job, needs и rules не используются). "
        f"Job {failed} падает с ненулевым кодом. Сколько job будут запущены в этом пайплайне, "
        "включая упавший?"
    )
    return Generated(
        stem=stem,
        code="\n".join(lines).rstrip(),
        code_language="yaml",
        number=float(len(build) + len(test)),
        tolerance=0,
    )


@generator("devops.ci_pipeline_duration")
def ci_pipeline_duration(rng: random.Random) -> Generated:
    """Без needs стадия ждёт самый долгий job предыдущей: длительность = сумма максимумов по стадиям."""
    stages = {
        "build": _stage_jobs(rng, "build", 2, 3),
        "test": _stage_jobs(rng, "test", 2, 4),
        "deploy": _stage_jobs(rng, "deploy", 1, 2),
    }
    durations = {job: rng.randint(1, 12) for jobs in stages.values() for job in jobs}
    rows = [f"{stage:7} | {job:15} | {durations[job]} мин" for stage, jobs in stages.items() for job in jobs]
    total = sum(max(durations[job] for job in jobs) for jobs in stages.values())
    stem = (
        "Пайплайн GitLab CI из трёх стадий: build → test → deploy. Свободных runners достаточно, needs не "
        "используется, все job проходят успешно, накладные расходы на запуск не учитываем. "
        "Через сколько минут после старта завершится пайплайн?"
    )
    return Generated(
        stem=stem,
        code="\n".join(["стадия  | job             | длительность", *rows]),
        code_language="text",
        number=float(total),
        tolerance=0,
    )


@generator("devops.private_ip")
def private_ip(rng: random.Random) -> Generated:
    """Частные диапазоны RFC 1918: 10/8, 172.16/12, 192.168/16."""

    def octet() -> int:
        return rng.randint(1, 254)

    correct = rng.choice(
        [
            f"10.{octet()}.{octet()}.{octet()}",
            f"172.{rng.randint(16, 31)}.{octet()}.{octet()}",
            f"192.168.{octet()}.{octet()}",
        ]
    )
    wrong = [
        f"172.{rng.choice([15, 32, 33, 64, 100])}.{octet()}.{octet()}",
        f"192.{rng.choice([167, 169, 172])}.{octet()}.{octet()}",
        f"{rng.choice([11, 100, 9])}.{octet()}.{octet()}.{octet()}",
        f"8.8.{rng.choice([4, 8])}.{rng.choice([4, 8])}",
        f"{rng.choice([93, 77, 185])}.{octet()}.{octet()}.{octet()}",
    ]
    stem = rng.choice(
        [
            "Какой из адресов относится к частным (private) диапазонам RFC 1918?",
            "Для внутренней сети без выхода в интернет нужно выбрать адрес из частного диапазона RFC 1918. "
            "Какой подходит?",
            "Какой адрес не маршрутизируется в публичном интернете, потому что входит в частный "
            "диапазон RFC 1918?",
        ]
    )
    return Generated(stem=stem, correct=(correct,), wrong=tuple(wrong))


@generator("devops.gateway_status")
def gateway_status(rng: random.Random) -> Generated:
    """Код ответа nginx как reverse proxy: 502 — upstream недоступен, 504 — upstream не успел ответить."""
    upstream = rng.choice(APPS)
    port = rng.choice([8000, 8080, 3000, 9000, 5000])
    timeout = rng.choice([30, 60, 90, 120])
    cases = {
        "502 Bad Gateway": [
            f"процесс {upstream} упал, и на 127.0.0.1:{port} никто не слушает (connect() failed, "
            "Connection refused)",
            f"{upstream} закрывает соединение, не отправив ответ (upstream prematurely closed connection)",
        ],
        "504 Gateway Timeout": [
            f"{upstream} принимает соединение, но не отвечает дольше proxy_read_timeout {timeout}s",
            f"запрос к {upstream}:{port} висит дольше {timeout} с, заданных в proxy_read_timeout",
        ],
    }
    status = rng.choice(list(cases))
    situation = rng.choice(cases[status])
    stem = f"nginx проксирует запросы на upstream {upstream} (proxy_pass http://127.0.0.1:{port}). " + (
        f"Ситуация: {situation}. Какой код ответа получит клиент от nginx?"
    )
    wrong = [name for name in cases if name != status]
    wrong += ["503 Service Unavailable", "500 Internal Server Error", "408 Request Timeout", "404 Not Found"]
    return Generated(stem=stem, correct=(status,), wrong=tuple(wrong))


PLAN_SYMBOLS = {
    "+": "Ресурс будет создан",
    "-": "Ресурс будет удалён",
    "~": "Ресурс будет изменён на месте, без пересоздания",
    "-/+": "Ресурс будет удалён и создан заново (замена)",
    "<=": "Будет прочитан источник данных (data source), ресурс не изменится",
}


@generator("devops.terraform_plan_symbol")
def terraform_plan_symbol(rng: random.Random) -> Generated:
    """Обозначения действий в выводе terraform plan."""
    resource = rng.choice(
        [
            "yandex_compute_instance.web",
            "yandex_vpc_subnet.private",
            "aws_instance.app",
            "aws_s3_bucket.logs",
            "yandex_mdb_postgresql_cluster.main",
            "google_compute_instance.worker",
        ]
    )
    index = rng.randint(0, 3)
    symbol = rng.choice(["+", "-", "~", "-/+"])
    address = f"{resource}[{index}]"
    line = f'  {symbol} resource "{resource.split(".")[0]}" "{resource.split(".")[1]}" {{'
    stem = rng.choice(
        [
            f"В выводе terraform plan для {address} стоит символ «{symbol}». Что он означает?",
            f"terraform plan показывает строку ниже для ресурса {address}. Что произойдёт с ресурсом "
            "при apply?",
        ]
    )
    wrong = [text for key, text in PLAN_SYMBOLS.items() if key != symbol]
    return Generated(
        stem=stem,
        code=f"  # {address} ...\n{line}",
        code_language="hcl",
        correct=(PLAN_SYMBOLS[symbol],),
        wrong=tuple(wrong),
    )


# --- Базовые задания уровня Intern: открытый числовой ответ без угадывания ---

FILE_STEMS = ["app", "error", "access", "worker", "backup", "notes", "report", "deploy", "cron", "audit"]
FILE_EXTENSIONS = ["log", "txt", "conf", "sh", "gz"]


@generator("devops.glob_wc_count")
def glob_wc_count(rng: random.Random) -> Generated:
    """Шаблон *.ext совпадает с именами, оканчивающимися на .ext; wc -l считает строки вывода ls."""
    ext = rng.choice(["log", "txt", "conf", "sh"])
    others = [item for item in FILE_EXTENSIONS if item != ext]
    stems = rng.sample(FILE_STEMS, rng.randint(6, 8))
    matched = rng.randint(2, len(stems) - 2)
    names = [f"{stem}.{ext}" for stem in stems[:matched]]
    names += [f"{stem}.{rng.choice(others)}" for stem in stems[matched:]]
    names.sort()
    folder = rng.choice(["/var/log/myapp", "/opt/app", "/srv/data", "/home/deploy"])
    code = f"$ ls {folder}\n" + "  ".join(names) + f"\n$ cd {folder}\n$ ls *.{ext} | wc -l"
    return Generated(
        stem="Какое число выведет последняя команда?", code=code, code_language="bash", number=float(matched)
    )


MATRIX_AXES = {
    "python": ['"3.10"', '"3.11"', '"3.12"', '"3.13"'],
    "node": ["18", "20", "22"],
    "os": ["ubuntu-latest", "windows-latest", "macos-latest"],
    "db": ["postgres", "mysql", "sqlite"],
}


@generator("devops.ci_matrix_jobs")
def ci_matrix_jobs(rng: random.Random) -> Generated:
    """Матрица без include/exclude запускает по джобу на каждую комбинацию значений осей."""
    language = rng.choice(["python", "node"])
    second = rng.choice(["os", "db"])
    axes = {
        language: rng.sample(MATRIX_AXES[language], rng.randint(2, len(MATRIX_AXES[language]))),
        second: rng.sample(MATRIX_AXES[second], rng.randint(2, 3)),
    }
    lines = [f"        {axis}: [{', '.join(values)}]" for axis, values in axes.items()]
    code = (
        "jobs:\n"
        "  test:\n"
        "    strategy:\n"
        "      matrix:\n" + "\n".join(lines) + "\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - run: make test"
    )
    if second == "os":
        code = code.replace("runs-on: ubuntu-latest", "runs-on: ${{ matrix.os }}")
    answer = len(axes[language]) * len(axes[second])
    return Generated(
        stem="Сколько джобов test запустит GitHub Actions по этому workflow?",
        code=code,
        code_language="yaml",
        number=float(answer),
    )
