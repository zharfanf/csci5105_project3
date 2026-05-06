"""
eval.py - evaluation script for the marketplace system
runs through several test scenarios and collects metrics

scenarios:
1. basic functionality - make sure all RPCs work
2. read-heavy workload - 80% reads, 20% writes with multiple threads
3. burst traffic - sudden spike of concurrent requests
4. auction scenario - concurrent bidders on multiple items
5. consistency check - write then read, make sure data matches
6. concurrent writes - multiple threads updating same item

run with: python eval.py
set TARGET env var to point at the frontend service (default localhost:50051)
"""

import os
import sys
import time
import random
import threading
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

import grpc
import marketplace_pb2 as pb2
import marketplace_pb2_grpc as pb2_grpc

TARGET = os.environ.get("TARGET", "localhost:50051")


# ---- metrics collection ----

class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self.latencies = {}
        self.errors = {}
        self.successes = {}

    def record(self, op, latency_ms, success):
        with self._lock:
            if op not in self.latencies:
                self.latencies[op] = []
                self.errors[op] = 0
                self.successes[op] = 0
            self.latencies[op].append(latency_ms)
            if success:
                self.successes[op] += 1
            else:
                self.errors[op] += 1

    def report(self, title=""):
        print(f"\n{'='*60}")
        if title:
            print(f"  {title}")
            print(f"{'='*60}")

        total_reqs = 0
        total_errs = 0
        all_lats = []

        for op in sorted(self.latencies.keys()):
            lats = self.latencies[op]
            errs = self.errors.get(op, 0)
            succs = self.successes.get(op, 0)
            total_reqs += len(lats)
            total_errs += errs
            all_lats.extend(lats)

            print(f"\n  {op}:")
            print(f"    requests:  {len(lats)}")
            print(f"    success:   {succs}")
            print(f"    errors:    {errs}")
            if lats:
                sorted_lats = sorted(lats)
                p95 = sorted_lats[int(len(sorted_lats) * 0.95)] if len(sorted_lats) > 1 else sorted_lats[0]
                p99 = sorted_lats[int(len(sorted_lats) * 0.99)] if len(sorted_lats) > 1 else sorted_lats[0]
                print(f"    min:       {min(lats):.1f}ms")
                print(f"    max:       {max(lats):.1f}ms")
                print(f"    mean:      {statistics.mean(lats):.1f}ms")
                print(f"    median:    {statistics.median(lats):.1f}ms")
                print(f"    p95:       {p95:.1f}ms")
                print(f"    p99:       {p99:.1f}ms")

        print(f"\n  totals:")
        print(f"    requests:  {total_reqs}")
        print(f"    errors:    {total_errs}")
        if all_lats:
            print(f"    avg lat:   {statistics.mean(all_lats):.1f}ms")
        print(f"{'='*60}\n")


def timed(metrics, op, func, *args, **kwargs):
    start = time.time()
    try:
        result = func(*args, **kwargs)
        ms = (time.time() - start) * 1000
        success = result.success if hasattr(result, "success") else True
        metrics.record(op, ms, success)
        return result
    except Exception as e:
        ms = (time.time() - start) * 1000
        metrics.record(op, ms, False)
        print(f"    ERROR [{op}]: {e}")
        return None


# ---- seed data ----

# realistic-ish item data
ITEM_TEMPLATES = [
    # electronics
    {"title": "Wireless Bluetooth Headphones", "category": "electronics", "description": "noise cancelling over-ear headphones with 30hr battery", "price": 79.99},
    {"title": "USB-C Charging Cable 6ft", "category": "electronics", "description": "braided fast charging cable compatible with most devices", "price": 12.99},
    {"title": "Mechanical Keyboard RGB", "category": "electronics", "description": "cherry mx blue switches, full size with numpad", "price": 89.99},
    {"title": "Portable SSD 1TB", "category": "electronics", "description": "external solid state drive usb 3.2 gen 2", "price": 109.99},
    {"title": "Webcam 1080p", "category": "electronics", "description": "hd webcam with built in microphone for streaming", "price": 49.99},
    {"title": "Smart Watch Fitness Tracker", "category": "electronics", "description": "heart rate monitor step counter sleep tracking", "price": 149.99},
    {"title": "Wireless Mouse Ergonomic", "category": "electronics", "description": "vertical design reduces wrist strain, usb receiver", "price": 29.99},
    {"title": "HDMI Cable 4K 10ft", "category": "electronics", "description": "high speed hdmi 2.1 cable for gaming and streaming", "price": 14.99},
    # books
    {"title": "Introduction to Algorithms", "category": "books", "description": "CLRS textbook fourth edition hardcover", "price": 85.00},
    {"title": "Designing Data-Intensive Applications", "category": "books", "description": "by Martin Kleppmann, distributed systems concepts", "price": 45.99},
    {"title": "The Pragmatic Programmer", "category": "books", "description": "20th anniversary edition, software development", "price": 39.99},
    {"title": "Clean Code", "category": "books", "description": "a handbook of agile software craftsmanship by Robert Martin", "price": 34.99},
    {"title": "System Design Interview Vol 1", "category": "books", "description": "an insiders guide by Alex Xu", "price": 36.99},
    # clothing
    {"title": "Running Shoes Size 10", "category": "clothing", "description": "lightweight mesh breathable for daily training", "price": 89.99},
    {"title": "Winter Jacket Waterproof", "category": "clothing", "description": "insulated parka with hood, rated to -20F", "price": 149.99},
    {"title": "Cotton T-Shirt Pack of 5", "category": "clothing", "description": "crew neck basic tees assorted colors", "price": 29.99},
    {"title": "Hiking Boots Waterproof", "category": "clothing", "description": "mid ankle support, vibram sole, leather upper", "price": 129.99},
    # furniture
    {"title": "Standing Desk Adjustable", "category": "furniture", "description": "electric sit-stand desk 48x30 bamboo top", "price": 399.99},
    {"title": "Office Chair Ergonomic", "category": "furniture", "description": "mesh back lumbar support adjustable armrests", "price": 249.99},
    {"title": "Bookshelf 5 Tier", "category": "furniture", "description": "solid wood industrial style open shelving", "price": 119.99},
    {"title": "Monitor Stand Riser", "category": "furniture", "description": "wooden desk organizer with storage drawer", "price": 34.99},
    # collectibles (these become auction items)
    {"title": "Vintage Pokemon Card Charizard", "category": "collectibles", "description": "base set holographic, near mint condition", "price": 50.00},
    {"title": "Signed Baseball Mickey Mantle", "category": "collectibles", "description": "authenticated autograph with certificate", "price": 200.00},
    {"title": "First Edition Book 1984", "category": "collectibles", "description": "George Orwell first UK printing, good condition", "price": 500.00},
    {"title": "Rare Vinyl Record Abbey Road", "category": "collectibles", "description": "original 1969 pressing, sleeve has minor wear", "price": 150.00},
    {"title": "Antique Pocket Watch 1890", "category": "collectibles", "description": "gold plated, still runs, engraved case back", "price": 300.00},
    # toys
    {"title": "LEGO Technic Set 1500 pieces", "category": "toys", "description": "mechanical crane with working winch and gears", "price": 119.99},
    {"title": "Board Game Settlers of Catan", "category": "toys", "description": "base game 3-4 players, new sealed", "price": 39.99},
    {"title": "RC Drone with Camera", "category": "toys", "description": "foldable quadcopter 4k camera 30min flight time", "price": 199.99},
    {"title": "Puzzle 1000 Pieces Mountain", "category": "toys", "description": "jigsaw puzzle scenic landscape photo", "price": 15.99},
]

# search queries that actually match our data
SEARCH_KEYWORDS = [
    "wireless", "keyboard", "cable", "book", "shoes", "desk",
    "watch", "drone", "vintage", "cotton", "chair", "LEGO",
    "camera", "running", "puzzle", "signed", "portable", "smart",
    "design", "code", "hiking", "jacket", "monitor", "card",
]

SEARCH_CATEGORIES = ["electronics", "books", "clothing", "furniture", "collectibles", "toys", ""]


def seed_items(stub, metrics):
    """create a realistic set of items for testing"""
    print("\n  seeding marketplace data...")
    regular_ids = []
    auction_ids = []
    sellers = [f"seller-{i}" for i in range(1, 8)]

    # create one of each template
    for template in ITEM_TEMPLATES:
        is_auction = template["category"] == "collectibles"
        resp = timed(metrics, "CreateItem_seed", stub.CreateItem, pb2.CreateItemRequest(
            seller_id=random.choice(sellers),
            title=template["title"],
            category=template["category"],
            description=template["description"],
            starting_price=template["price"],
            quantity=1 if is_auction else random.randint(1, 50),
            status="auction" if is_auction else "active"
        ))
        if resp and resp.success:
            if is_auction:
                auction_ids.append(resp.item_id)
            else:
                regular_ids.append(resp.item_id)

    # create extras for bulk - gives us ~50 total items
    # important for fault tolerance testing so theres enough data to sync
    for i in range(20):
        template = random.choice(ITEM_TEMPLATES)
        resp = timed(metrics, "CreateItem_seed", stub.CreateItem, pb2.CreateItemRequest(
            seller_id=random.choice(sellers),
            title=f"{template['title']} #{i+100}",
            category=template["category"],
            description=template["description"],
            starting_price=round(template["price"] * random.uniform(0.8, 1.2), 2),
            quantity=random.randint(1, 30),
            status="active"
        ))
        if resp and resp.success:
            regular_ids.append(resp.item_id)

    total = len(regular_ids) + len(auction_ids)
    print(f"  seeded {total} items ({len(regular_ids)} regular, {len(auction_ids)} auction)")
    return regular_ids, auction_ids


# ---- scenario 1: basic functionality ----

def test_basic(stub, metrics):
    print("\n--- scenario 1: basic functionality ---")

    # create
    print("  creating item...")
    resp = timed(metrics, "CreateItem", stub.CreateItem, pb2.CreateItemRequest(
        seller_id="test-seller",
        title="Basic Test Widget",
        category="electronics",
        description="a simple test item",
        starting_price=25.0,
        quantity=10,
        status="active"
    ))
    if not resp or not resp.success:
        print("  FAILED to create item")
        return None

    item_id = resp.item_id
    print(f"  created: {item_id}")

    # get
    print("  getting item...")
    resp = timed(metrics, "GetItem", stub.GetItem, pb2.GetItemRequest(item_id=item_id))
    if resp and resp.success:
        print(f"  got: {resp.item.title} ${resp.item.current_price:.2f} v{resp.item.version}")
    else:
        print("  FAILED to get item")

    # search by keyword
    print("  searching by keyword...")
    resp = timed(metrics, "SearchItems", stub.SearchItems,
                 pb2.SearchItemsRequest(keyword="Widget", category=""))
    if resp and resp.success:
        print(f"  keyword search found {len(resp.items)} items")

    # search by category
    print("  searching by category...")
    resp = timed(metrics, "SearchItems", stub.SearchItems,
                 pb2.SearchItemsRequest(keyword="", category="electronics"))
    if resp and resp.success:
        print(f"  category search found {len(resp.items)} items")

    # search by both
    print("  searching by keyword + category...")
    resp = timed(metrics, "SearchItems", stub.SearchItems,
                 pb2.SearchItemsRequest(keyword="Test", category="electronics"))
    if resp and resp.success:
        print(f"  combined search found {len(resp.items)} items")

    # update
    print("  updating item...")
    resp = timed(metrics, "UpdateItem", stub.UpdateItem, pb2.UpdateItemRequest(
        item_id=item_id,
        description="updated description for testing",
        quantity=5,
        status="active",
        current_price=0,
        expected_version=0
    ))
    if resp and resp.success:
        print(f"  updated to v{resp.item.version}")

    # verify update
    print("  verifying update...")
    resp = timed(metrics, "GetItem", stub.GetItem, pb2.GetItemRequest(item_id=item_id))
    if resp and resp.success:
        if resp.item.description == "updated description for testing":
            print("  update verified")
        else:
            print(f"  MISMATCH: expected updated description, got '{resp.item.description}'")

    # bid test
    print("  creating auction item for bid test...")
    resp = timed(metrics, "CreateItem", stub.CreateItem, pb2.CreateItemRequest(
        seller_id="test-seller",
        title="Bid Test Item",
        category="collectibles",
        description="testing bids",
        starting_price=10.0,
        quantity=1,
        status="auction"
    ))
    if resp and resp.success:
        bid_item = resp.item_id
        print(f"  auction item: {bid_item}")

        # valid bid
        print("  placing valid bid...")
        bid_resp = timed(metrics, "PlaceBid", stub.PlaceBid, pb2.PlaceBidRequest(
            item_id=bid_item, bidder_id="test-bidder", bid_amount=15.0
        ))
        if bid_resp and bid_resp.success:
            print(f"  bid accepted at ${bid_resp.current_price:.2f}")

        # low bid - should fail
        print("  placing low bid (should fail)...")
        bid_resp = timed(metrics, "PlaceBid", stub.PlaceBid, pb2.PlaceBidRequest(
            item_id=bid_item, bidder_id="test-bidder-2", bid_amount=5.0
        ))
        if bid_resp and not bid_resp.success:
            print(f"  correctly rejected: {bid_resp.message}")
        elif bid_resp and bid_resp.success:
            print("  ERROR: low bid accepted when it shouldn't have been")

    print("  basic tests done\n")
    return item_id


# ---- scenario 2: read-heavy workload ----

def test_read_heavy(stub, metrics, item_ids, duration=20, threads=8):
    print(f"\n--- scenario 2: read-heavy workload ({duration}s, {threads} threads) ---")
    if not item_ids:
        print("  no items, skipping")
        return

    end_time = time.time() + duration
    counter = [0]
    counter_lock = threading.Lock()

    def worker():
        while time.time() < end_time:
            r = random.random()
            if r < 0.35:
                timed(metrics, "GetItem_load", stub.GetItem,
                      pb2.GetItemRequest(item_id=random.choice(item_ids)))
            elif r < 0.70:
                kw = random.choice(SEARCH_KEYWORDS + [""])
                cat = random.choice(SEARCH_CATEGORIES)
                timed(metrics, "SearchItems_load", stub.SearchItems,
                      pb2.SearchItemsRequest(keyword=kw, category=cat))
            elif r < 0.90:
                timed(metrics, "UpdateItem_load", stub.UpdateItem,
                      pb2.UpdateItemRequest(
                          item_id=random.choice(item_ids),
                          description=f"load test update {time.time():.0f}",
                          quantity=random.randint(1, 20),
                          status="", current_price=0, expected_version=0
                      ))
            else:
                t = random.choice(ITEM_TEMPLATES)
                timed(metrics, "CreateItem_load", stub.CreateItem,
                      pb2.CreateItemRequest(
                          seller_id=f"load-seller-{random.randint(1,5)}",
                          title=f"{t['title']} load-{random.randint(1000,9999)}",
                          category=t["category"],
                          description=t["description"],
                          starting_price=t["price"],
                          quantity=random.randint(1, 10),
                          status="active"
                      ))
            with counter_lock:
                counter[0] += 1
            time.sleep(random.uniform(0.01, 0.05))

    workers = [threading.Thread(target=worker) for _ in range(threads)]
    start = time.time()
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    elapsed = time.time() - start
    print(f"  {counter[0]} requests in {elapsed:.1f}s ({counter[0]/elapsed:.1f} req/s)")


# ---- scenario 3: burst traffic ----

def test_burst(stub, metrics, item_ids, burst_size=50):
    print(f"\n--- scenario 3: burst traffic ({burst_size} concurrent requests) ---")
    if not item_ids:
        print("  no items, skipping")
        return

    def single_req(i):
        r = random.random()
        if r < 0.5:
            return timed(metrics, "GetItem_burst", stub.GetItem,
                         pb2.GetItemRequest(item_id=random.choice(item_ids)))
        elif r < 0.8:
            kw = random.choice(SEARCH_KEYWORDS)
            return timed(metrics, "SearchItems_burst", stub.SearchItems,
                         pb2.SearchItemsRequest(keyword=kw, category=""))
        else:
            return timed(metrics, "UpdateItem_burst", stub.UpdateItem,
                         pb2.UpdateItemRequest(
                             item_id=random.choice(item_ids),
                             description=f"burst update {i}",
                             quantity=0, status="", current_price=0,
                             expected_version=0
                         ))

    start = time.time()
    with ThreadPoolExecutor(max_workers=burst_size) as pool:
        futures = [pool.submit(single_req, i) for i in range(burst_size)]
        for f in as_completed(futures):
            pass
    elapsed = time.time() - start
    print(f"  {burst_size} requests in {elapsed:.1f}s ({burst_size/elapsed:.1f} req/s)")


# ---- scenario 4: auction competition ----

def test_auction(stub, metrics, auction_ids, num_bidders=5, num_rounds=8):
    print(f"\n--- scenario 4: auction ({num_bidders} bidders, {num_rounds} rounds, {len(auction_ids)} items) ---")

    if not auction_ids:
        print("  no auction items, creating some...")
        auction_ids = []
        for i in range(3):
            resp = timed(metrics, "CreateItem_auction", stub.CreateItem, pb2.CreateItemRequest(
                seller_id="auction-seller",
                title=f"Auction Item {i}",
                category="collectibles",
                description=f"rare item {i}",
                starting_price=float(random.randint(5, 50)),
                quantity=1,
                status="auction"
            ))
            if resp and resp.success:
                auction_ids.append(resp.item_id)

    if not auction_ids:
        print("  couldn't create auction items, skipping")
        return

    results = {"accepted": 0, "rejected": 0, "errors": 0}
    results_lock = threading.Lock()

    def bidder(bidder_id):
        my_item = random.choice(auction_ids)
        for rnd in range(num_rounds):
            get_resp = timed(metrics, "GetItem_auction", stub.GetItem,
                             pb2.GetItemRequest(item_id=my_item))
            if not get_resp or not get_resp.success:
                with results_lock:
                    results["errors"] += 1
                continue

            current = get_resp.item.current_price
            bid_amount = current + random.uniform(0.50, 10.0)

            bid_resp = timed(metrics, "PlaceBid_auction", stub.PlaceBid,
                             pb2.PlaceBidRequest(
                                 item_id=my_item,
                                 bidder_id=f"bidder-{bidder_id}",
                                 bid_amount=round(bid_amount, 2)
                             ))
            with results_lock:
                if bid_resp is None:
                    results["errors"] += 1
                elif bid_resp.success:
                    results["accepted"] += 1
                else:
                    results["rejected"] += 1

            time.sleep(random.uniform(0.05, 0.3))

    threads = [threading.Thread(target=bidder, args=(i,)) for i in range(num_bidders)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for aid in auction_ids:
        resp = stub.GetItem(pb2.GetItemRequest(item_id=aid))
        if resp and resp.success:
            print(f"  {resp.item.title}: ${resp.item.current_price:.2f} (started ${resp.item.starting_price:.2f})")

    print(f"  bids: {results['accepted']} accepted, {results['rejected']} rejected, {results['errors']} errors")


# ---- scenario 5: consistency check ----

def test_consistency(stub, metrics, num_items=15):
    print(f"\n--- scenario 5: consistency check ({num_items} items) ---")

    mismatches = 0
    for i in range(num_items):
        template = random.choice(ITEM_TEMPLATES)
        title = f"{template['title']} consistency-{random.randint(10000,99999)}"
        price = round(template["price"] * random.uniform(0.9, 1.1), 2)

        create_resp = timed(metrics, "CreateItem_consistency", stub.CreateItem,
                            pb2.CreateItemRequest(
                                seller_id=f"consistency-seller-{i}",
                                title=title,
                                category=template["category"],
                                description=template["description"],
                                starting_price=price,
                                quantity=1,
                                status="active"
                            ))

        if not create_resp or not create_resp.success:
            mismatches += 1
            continue

        # read back immediately
        get_resp = timed(metrics, "GetItem_consistency", stub.GetItem,
                         pb2.GetItemRequest(item_id=create_resp.item_id))

        if not get_resp or not get_resp.success:
            mismatches += 1
            continue

        if get_resp.item.title != title:
            print(f"  MISMATCH title: wrote '{title}', read '{get_resp.item.title}'")
            mismatches += 1
        if abs(get_resp.item.current_price - price) > 0.01:
            print(f"  MISMATCH price: wrote ${price}, read ${get_resp.item.current_price}")
            mismatches += 1
        if get_resp.item.category != template["category"]:
            print(f"  MISMATCH category: wrote '{template['category']}', read '{get_resp.item.category}'")
            mismatches += 1

    if mismatches == 0:
        print(f"  all {num_items} items consistent")
    else:
        print(f"  {mismatches} mismatches out of {num_items}!")


# ---- scenario 6: concurrent writes to same item ----

def test_concurrent_writes(stub, metrics, num_writers=5, num_writes=10):
    print(f"\n--- scenario 6: concurrent writes ({num_writers} writers, {num_writes} each) ---")

    resp = timed(metrics, "CreateItem_concurrent", stub.CreateItem, pb2.CreateItemRequest(
        seller_id="concurrent-seller",
        title="Contested Item",
        category="electronics",
        description="many writers one item",
        starting_price=10.0,
        quantity=100,
        status="active"
    ))
    if not resp or not resp.success:
        print("  failed to create item, skipping")
        return

    item_id = resp.item_id
    success_count = [0]
    fail_count = [0]
    count_lock = threading.Lock()

    def writer(writer_id):
        for w in range(num_writes):
            resp = timed(metrics, "UpdateItem_concurrent", stub.UpdateItem,
                         pb2.UpdateItemRequest(
                             item_id=item_id,
                             description=f"writer-{writer_id} write-{w} t={time.time():.3f}",
                             quantity=random.randint(1, 50),
                             status="active",
                             current_price=0,
                             expected_version=0
                         ))
            with count_lock:
                if resp and resp.success:
                    success_count[0] += 1
                else:
                    fail_count[0] += 1
            time.sleep(random.uniform(0.01, 0.05))

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(num_writers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final = stub.GetItem(pb2.GetItemRequest(item_id=item_id))
    if final and final.success:
        desc = final.item.description
        if len(desc) > 50:
            desc = desc[:50] + "..."
        print(f"  final state: v{final.item.version}, desc='{desc}'")

    total = success_count[0] + fail_count[0]
    print(f"  {success_count[0]}/{total} writes succeeded, {fail_count[0]} failed")


# ---- main ----

def main():
    print(f"connecting to {TARGET}...")
    channel = grpc.insecure_channel(TARGET)
    stub = pb2_grpc.FrontendServiceStub(channel)

    try:
        resp = stub.CreateItem(pb2.CreateItemRequest(
            seller_id="ping", title="connectivity check", category="test",
            description="ignore", starting_price=1.0, quantity=1, status="active"
        ), timeout=5.0)
        print("connected!\n")
    except grpc.RpcError as e:
        print(f"can't connect to {TARGET}: {e}")
        print("is the system running?")
        return

    metrics = Metrics()
    start_time = time.time()

    # seed
    regular_ids, auction_ids = seed_items(stub, metrics)
    if not regular_ids:
        print("seeding failed, can't continue")
        return

    # run all scenarios
    test_basic(stub, metrics)
    test_read_heavy(stub, metrics, regular_ids, duration=20, threads=8)
    test_burst(stub, metrics, regular_ids, burst_size=50)
    test_auction(stub, metrics, auction_ids, num_bidders=5, num_rounds=8)
    test_consistency(stub, metrics, num_items=15)
    test_concurrent_writes(stub, metrics, num_writers=5, num_writes=10)

    elapsed = time.time() - start_time
    metrics.report(f"EVALUATION RESULTS (total time: {elapsed:.1f}s)")

    print("--- fault tolerance test (manual) ---")
    print("  1. run this eval script")
    print("  2. while running, kill a storage pod:")
    print("     kubectl delete pod storage-1")
    print("  3. watch controller logs:")
    print("     kubectl logs -f <controller-pod>")
    print("  4. observe recovery when pod restarts")
    print()
    print("--- autoscaling test (manual) ---")
    print("  1. increase load: TARGET=localhost:50051 python eval.py")
    print("     (or run multiple instances in parallel)")
    print("  2. watch HPA:")
    print("     kubectl get hpa -w")
    print("  3. watch pods scale:")
    print("     kubectl get pods -w")

    channel.close()


if __name__ == "__main__":
    main()
