"""
Fuel Station Data Management Pipeline

This module provides a robust administrative command for importing and updating 
fuel station records from OPIS-formatted CSV data. It implements an UPSERT 
strategy to maintain data integrity and preserve expensive geocoding results.

Key Features:
-------------
* Idempotent Updates: Uses database-level UPSERT to update prices/metadata 
    without overwriting existing latitude/longitude coordinates.
* Hybrid Geocoding: Tiered resolution logic (Google Maps -> Nominatim -> Mock).
* Resilience: Handles messy highway addresses (Exits/Mile Markers) via 
    internal fallback logic in the MapAPIClient.
* Performance: Batch processing for high-volume CSVs (default 1000 records).
* User Experience: Real-time progress tracking and graceful Ctrl+C handling.

Operational Constraints & Notes:
--------------------------------
1.  Rate Limiting: When using Nominatim (free tier), a 1.1s delay is enforced 
    to prevent IP blacklisting. 
2.  Throughput: Full live geocoding of ~6,700 stations takes approx. 1.8 hours.
3.  Recommendation: Use the `--use-mock` flag for development and CI/CD pipelines
     to avoid API costs and latency.

Usage Examples:
---------------
# Standard import (Updates prices, adds new stations)
$ python manage.py import_fuel_data fuel_prices.csv

# Standard import + Geocode missing entries (Live API)
$ python manage.py import_fuel_data fuel_prices.csv --geocode

# Development mode (Instant geocoding with deterministic mock data)
$ python manage.py import_fuel_data fuel_prices.csv --geocode --use-mock
"""

import csv
import logging
import time
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction

from routing.models import FuelStation
from routing.map_api import MapAPIClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import or update fuel station data without losing geocoding"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str)
        parser.add_argument("--geocode", action="store_true")
        parser.add_argument("--batch-size", type=int, default=1000)
        parser.add_argument("--use-mock", action="store_true")

    # ============================================================
    # MAIN IMPORT HANDLER (UPSERT STRATEGY)
    # ============================================================

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        batch_size = options["batch_size"]

        self.stdout.write(f"🔄 Processing file: {csv_file}")

        stations_to_upsert = []
        seen_ids = set()
        processed = 0
        skipped = 0

        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for i, row in enumerate(reader, 1):
                    try:
                        opis_id = int(row["OPIS Truckstop ID"])

                        if opis_id in seen_ids:
                            skipped += 1
                            continue
                        seen_ids.add(opis_id)

                        price = Decimal(row["Retail Price"])

                        station = FuelStation(
                            opis_id=opis_id,
                            name=row["Truckstop Name"].strip(),
                            address=row["Address"].strip(),
                            city=row["City"].strip(),
                            state=row["State"].strip().upper(),
                            retail_price=price,
                        )

                        stations_to_upsert.append(station)
                        processed += 1

                        if len(stations_to_upsert) >= batch_size:
                            self._do_upsert(stations_to_upsert)
                            stations_to_upsert = []
                            self.stdout.write(f"Processed {i} rows...")

                    except (InvalidOperation, ValueError, KeyError) as e:
                        skipped += 1
                        logger.warning(f"Skipping row {i}: {e}")

                if stations_to_upsert:
                    self._do_upsert(stations_to_upsert)

        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"❌ File not found: {csv_file}"))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Import complete. Processed: {processed} | Skipped: {skipped} | Total in DB: {FuelStation.objects.count()}"
            )
        )

        if options["geocode"]:
            self._geocode_stations(use_mock=options["use_mock"])

    # ============================================================
    # UPSERT LOGIC (DO NOT TOUCH LAT/LNG)
    # ============================================================

    def _do_upsert(self, station_list):
        """
        Uses Django 4.1+ update_conflicts feature.
        Preserves latitude/longitude.
        """

        FuelStation.objects.bulk_create(
            station_list,
            update_conflicts=True,
            unique_fields=["opis_id"],
            update_fields=[
                "retail_price",
                "name",
                "address",
                "city",
                "state",
            ],
        )

    # ============================================================
    # ROBUST GEOCODING (INTERRUPT SAFE)
    # ============================================================

    def _geocode_stations(self, use_mock=False):
        stations = FuelStation.objects.filter(latitude__isnull=True)
        total = stations.count()

        if total == 0:
            self.stdout.write(
                self.style.SUCCESS("🎯 All stations already have coordinates.")
            )
            return

        estimated_time = total if not use_mock else 0
        self.stdout.write(
            f"🌐 Target: {total} stations | Estimated time: ~{estimated_time} seconds"
        )

        client = MapAPIClient(use_cache=True, use_mock=use_mock)

        geocoded = 0
        failed = 0

        try:
            for i, station in enumerate(stations, 1):
                location = f"{station.address}, {station.city}, {station.state}, USA"

                try:
                    lat, lng = client.geocode_location(location)

                    station.latitude = Decimal(str(lat))
                    station.longitude = Decimal(str(lng))
                    station.save(update_fields=["latitude", "longitude"])

                    geocoded += 1

                except Exception as e:
                    failed += 1
                    logger.error(f"Failed to geocode {station.opis_id}: {e}")

                # Progress indicator
                if i % 10 == 0 or i == total:
                    self.stdout.write(
                        f"Progress: [{i}/{total}] | Success: {geocoded} | Failed: {failed}"
                    )

                # Global Nominatim protection (if Google not configured)
                if (
                    not use_mock
                    and not getattr(settings, "GOOGLE_MAPS_API_KEY", None)
                ):
                    time.sleep(1.1)

        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING("\n⚠ Interrupted by user. Progress safely saved.")
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"🏁 Finished. Geocoded: {geocoded} | Failed: {failed} | Remaining: {total - geocoded - failed}"
            )
        )
