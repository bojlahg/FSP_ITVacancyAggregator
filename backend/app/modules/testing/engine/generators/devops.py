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
    binary = rng.choice(["app", "server", "bin/service", "dist/"])
    report = rng.choice(["junit.xml", "report.xml", "test-results.xml"])
    folder = rng.choice(["~/.npm", ".cache/pip", ".m2/repository", ".gradle/caches"])
    cases = [
        (
            f"Job build на стадии build собирает {binary}, а job deploy на стадии deploy должен "
            "гарантированно получить именно этот результат сборки. Какой механизм GitLab CI "
            "для этого предназначен?",
            "artifacts",
        ),
        (
            f"Job test создаёт отчёт {report}, который нужно сохранить вместе с пайплайном и показать "
            "в merge request. Какой механизм GitLab CI использовать?",
            "artifacts",
        ),
        (
            f"Каждый пайплайн заново скачивает зависимости в {folder}, что занимает несколько минут. "
            "Какой механизм GitLab CI предназначен для ускорения повторных установок между пайплайнами?",
            "cache",
        ),
    ]
    stem, answer = rng.choice(cases)
    wrong = [name for name in ["artifacts", "cache"] if name != answer] + ["variables", "services", "include"]
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
    host = rng.choice(["db.internal", "api.internal", "cache.internal", "10.0.3.17", "10.1.0.44"])
    port = rng.choice([5432, 8080, 6379, 9200, 443])
    explanations = {
        "refused": "На порту никто не слушает, или файрвол явно отклоняет соединение (RST/REJECT)",
        "timeout": "SYN остаётся без ответа: пакеты отбрасываются (DROP) файрволом или теряются по пути",
        "dns": "Имя не удалось разрешить в IP-адрес: проблема на стороне DNS",
        "tls": "Соединение установлено, но TLS-сертификат сервера не прошёл проверку",
    }
    errors = {
        "refused": "Connection refused (ECONNREFUSED), ответ приходит мгновенно",
        "timeout": "Connection timed out (ETIMEDOUT) спустя несколько десятков секунд",
    }
    if not host[0].isdigit():
        errors["dns"] = "Name or service not known (не удаётся получить адрес по имени)"
    case = rng.choice(list(errors))
    wrong = [text for name, text in explanations.items() if name != case]
    return Generated(
        stem=f"Клиент подключается по TCP к {host}:{port} и получает ошибку: {errors[case]}. "
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
        (f"текущее число занятых соединений в пуле БД сервиса {service}", "Gauge"),
        (f"текущая длина очереди задач сервиса {service}", "Gauge"),
        (
            f"распределение длительности запросов к {service}, из которого нужно считать p95 "
            "по всем подам вместе",
            "Histogram",
        ),
    ]
    quantity, answer = rng.choice(cases)
    wrong = [name for name in ["Counter", "Gauge", "Histogram", "Summary"] if name != answer]
    return Generated(
        stem=f"Какой тип метрики Prometheus подходит для величины: {quantity}?",
        correct=(answer,),
        wrong=tuple(wrong),
    )


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
