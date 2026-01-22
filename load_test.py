#!/usr/bin/env python3
"""
Load testing script for counter application.
Used to compare performance of single instance vs cluster.

Usage:
    python load_test.py --url http://localhost:5000 --requests 1000 --concurrency 10
"""

import argparse
import asyncio
import time
import statistics
from collections import defaultdict

try:
    import aiohttp
except ImportError:
    print("Install aiohttp: pip install aiohttp")
    exit(1)


async def make_request(session, url, results, hostnames):
    """Execute one HTTP request and record results."""
    start = time.perf_counter()
    try:
        async with session.get(url) as response:
            elapsed = time.perf_counter() - start
            data = await response.json()
            results['success'] += 1
            results['times'].append(elapsed * 1000)  # in milliseconds

            hostname = data.get('hostname', 'unknown')
            hostnames[hostname] += 1

            return True
    except Exception as e:
        elapsed = time.perf_counter() - start
        results['failed'] += 1
        results['errors'].append(str(e))
        return False


async def run_load_test(url, total_requests, concurrency):
    """Run load test."""
    results = {
        'success': 0,
        'failed': 0,
        'times': [],
        'errors': []
    }
    hostnames = defaultdict(int)

    print(f"\n{'='*60}")
    print(f"LOAD TEST")
    print(f"{'='*60}")
    print(f"URL: {url}")
    print(f"Total requests: {total_requests}")
    print(f"Concurrency: {concurrency}")
    print(f"{'='*60}\n")

    connector = aiohttp.TCPConnector(limit=concurrency)
    timeout = aiohttp.ClientTimeout(total=30)

    start_time = time.perf_counter()

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded_request():
            async with semaphore:
                return await make_request(session, url, results, hostnames)

        tasks = [bounded_request() for _ in range(total_requests)]
        await asyncio.gather(*tasks)

    total_time = time.perf_counter() - start_time

    print_results(results, hostnames, total_time, total_requests)

    return results, hostnames


def print_results(results, hostnames, total_time, total_requests):
    """Print test results."""
    print(f"\n{'='*60}")
    print(f"TEST RESULTS")
    print(f"{'='*60}")

    print(f"\n[STATS]")
    print(f"   Successful requests: {results['success']}")
    print(f"   Failed requests: {results['failed']}")
    print(f"   Total time: {total_time:.2f} seconds")
    print(f"   Requests per second (RPS): {total_requests / total_time:.2f}")

    if results['times']:
        times = results['times']
        print(f"\n[RESPONSE TIME (ms)]")
        print(f"   Min: {min(times):.2f}")
        print(f"   Max: {max(times):.2f}")
        print(f"   Avg: {statistics.mean(times):.2f}")
        print(f"   Median: {statistics.median(times):.2f}")
        if len(times) > 1:
            print(f"   Std dev: {statistics.stdev(times):.2f}")

        sorted_times = sorted(times)
        p50 = sorted_times[int(len(sorted_times) * 0.50)]
        p90 = sorted_times[int(len(sorted_times) * 0.90)]
        p95 = sorted_times[int(len(sorted_times) * 0.95)]
        p99 = sorted_times[int(len(sorted_times) * 0.99)]
        print(f"\n[PERCENTILES (ms)]")
        print(f"   P50: {p50:.2f}")
        print(f"   P90: {p90:.2f}")
        print(f"   P95: {p95:.2f}")
        print(f"   P99: {p99:.2f}")

    print(f"\n[HOST DISTRIBUTION (load balancing)]")
    total_host_requests = sum(hostnames.values())
    for hostname, count in sorted(hostnames.items(), key=lambda x: -x[1]):
        percentage = (count / total_host_requests) * 100
        bar = '#' * int(percentage / 5)
        print(f"   {hostname}: {count} ({percentage:.1f}%) {bar}")

    if results['errors']:
        print(f"\n[ERRORS (first 5)]")
        for error in results['errors'][:5]:
            print(f"   - {error}")

    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Load testing for counter application'
    )
    parser.add_argument(
        '--url', '-u',
        default='http://localhost:5000',
        help='URL to test (default: http://localhost:5000)'
    )
    parser.add_argument(
        '--requests', '-n',
        type=int,
        default=1000,
        help='Number of requests (default: 1000)'
    )
    parser.add_argument(
        '--concurrency', '-c',
        type=int,
        default=10,
        help='Number of concurrent requests (default: 10)'
    )

    args = parser.parse_args()

    asyncio.run(run_load_test(args.url, args.requests, args.concurrency))


if __name__ == '__main__':
    main()
