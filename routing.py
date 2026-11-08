import argparse
import heapq
import random
import time
from datetime import datetime

ciphered_bssid = "84:27:49:1H:21:71"

CITIES = ["NYC", "LON", "FRA", "AMS", "VNO", "WAW", "STO", "TYO",
          "SIN", "SYD", "SFO", "CHI", "PAR", "MAD", "DXB", "MUM"]
PROTOCOLS = ["TCP", "UDP", "ICMP", "OSPF", "BGP"]
LEVELS = ["INFO", "INFO", "INFO", "DEBUG", "WARN"]

RESET, DIM, GREEN, YELLOW, RED, CYAN = (
    "\033[0m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[36m")


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def rand_ip(rng) -> str:
    return f"10.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"


def build_topology(rng, names):
    graph = {n: {} for n in names}
    shuffled = names[:]
    rng.shuffle(shuffled)
    for a, b in zip(shuffled, shuffled[1:]):
        graph[a][b] = graph[b][a] = rng.randint(2, 40)
    for _ in range(len(names)):
        a, b = rng.sample(names, 2)
        graph[a].setdefault(b, rng.randint(2, 40))
        graph[b][a] = graph[a][b]
    return graph


def dijkstra(graph, src):
    dist = {n: float("inf") for n in graph}
    prev = {}
    dist[src] = 0
    heap = [(0, src)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, w in graph[u].items():
            nd = d + w
            if nd < dist[v]:
                dist[v], prev[v] = nd, u
                heapq.heappush(heap, (nd, v))
    return dist, prev


def path_to(prev, src, dst):
    path = [dst]
    while path[-1] != src:
        path.append(prev[path[-1]])
    return path[::-1]


def log(level, msg):
    color = {"INFO": GREEN, "DEBUG": DIM, "WARN": YELLOW, "ERROR": RED}[level]
    print(f"{DIM}{ts()}{RESET} {color}[{level:<5}]{RESET} {msg}")


def print_table(graph, src):
    dist, prev = dijkstra(graph, src)
    print(f"\n{CYAN}=== Routing table for {src} ==={RESET}")
    print(f"{'DEST':<6}{'NEXT HOP':<10}{'COST':<6}PATH")
    for dst in sorted(graph):
        if dst == src or dist[dst] == float("inf"):
            continue
        p = path_to(prev, src, dst)
        print(f"{dst:<6}{p[1]:<10}{dist[dst]:<6}{' > '.join(p)}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", type=int, default=10)
    ap.add_argument("--speed", type=float, default=1.0, help="higher = faster")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    names = rng.sample(CITIES, min(args.nodes, len(CITIES)))
    graph = build_topology(rng, names)
    local = names[0]
    sent = dropped = 0
    delay = lambda: time.sleep(rng.uniform(0.05, 0.4) / args.speed)

    log("INFO", f"Booting virtual router at {local} (node id {rng.randint(1000, 9999)})")
    for n in names:
        log("INFO", f"Neighbor discovery: {n} -> {len(graph[n])} links")
        delay()
    print_table(graph, local)

    try:
        tick = 0
        while True:
            tick += 1
            roll = rng.random()

            if roll < 0.60:
                a, b = rng.sample(names, 2)
                dist, prev = dijkstra(graph, a)
                route = path_to(prev, a, b)
                proto = rng.choice(PROTOCOLS)
                size = rng.choice([64, 128, 512, 1024, 1500])
                if rng.random() < 0.05:
                    dropped += 1
                    log("WARN", f"{proto} {rand_ip(rng)} -> {rand_ip(rng)} "
                                f"DROPPED (TTL exceeded) hop={rng.choice(route)}")
                else:
                    sent += 1
                    log("INFO", f"{proto:<4} {size:>4}B {rand_ip(rng)} -> {rand_ip(rng)} "
                                f"via {' > '.join(route)} ({dist[b]}ms)")

            elif roll < 0.80:
                a, b = rng.choice(names), rng.choice(names)
                if b in graph[a]:
                    old = graph[a][b]
                    new = max(1, old + rng.randint(-8, 8))
                    graph[a][b] = graph[b][a] = new
                    log("DEBUG", f"Link {a}<->{b} metric {old} -> {new}, recomputing SPF")

            elif roll < 0.90:
                n = rng.choice(names)
                log("INFO", f"Hello packet from {n} ({rand_ip(rng)}), "
                            f"seq={rng.randint(1, 99999)}")

            elif roll < 0.95:
                a, b = rng.choice(names), rng.choice(names)
                if b in graph[a] and len(graph[a]) > 2 and len(graph[b]) > 2:
                    cost = graph[a].pop(b)
                    graph[b].pop(a)
                    log("WARN", f"Link {a}<->{b} DOWN, rerouting traffic")
                    delay()
                    dist, _ = dijkstra(graph, local)
                    if all(d != float("inf") for d in dist.values()):
                        log("INFO", "Convergence complete")
                    else:
                        graph[a][b] = graph[b][a] = cost
                        log("INFO", f"Link {a}<->{b} restored")

            else:
                print_table(graph, local)

            if tick % 25 == 0:
                total = sent + dropped
                loss = dropped / total * 100 if total else 0
                log("INFO", f"STATS sent={sent} dropped={dropped} loss={loss:.1f}% "
                            f"uptime_ticks={tick}")
            delay()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Shutting down router... {sent} packets forwarded.{RESET}")


if __name__ == "__main__":
    main()
