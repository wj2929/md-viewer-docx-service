import argparse
import concurrent.futures
import json
import time
import urllib.request


def convert_once(url: str) -> float:
    payload = json.dumps({
        "markdown": "# 压测\n\n```dot\ndigraph { A -> B }\n```\n\n$$E=mc^2$$",
        "style": "standard",
        "renderCharts": False,
        "embedFont": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{url.rstrip('/')}/convert",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        resp.read()
    return time.perf_counter() - started


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:3179")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--requests", type=int, default=20)
    args = parser.parse_args()

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        durations = list(pool.map(lambda _: convert_once(args.url), range(args.requests)))

    durations.sort()
    p99 = durations[min(len(durations) - 1, int(len(durations) * 0.99))]
    print(json.dumps({
        "requests": args.requests,
        "concurrency": args.concurrency,
        "min": round(durations[0], 3),
        "max": round(durations[-1], 3),
        "p99": round(p99, 3),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
