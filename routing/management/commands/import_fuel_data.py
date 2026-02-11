"""
Management command to import fuel station data from CSV.
Includes geocoding for stations without coordinates.

Live Geocoding Notes:
--------------------
1. Nominatim API allows only 1 request/sec.
2. Messy highway addresses (e.g., "I-44, EXIT 4, Harrold, TX") may fail.
3. Geocoding 6,738 stations live takes ~1.8 hours.
   Without a sleep timer, API will return errors (403 or "Location not found").

Recommendations:
* Use `--use-mock` during development for instant geocoding.
* Use live API only for final data, with `time.sleep(1.1)` in the loop.
"""

import csv
import logging
import time
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand
from routing.models import FuelStation
from routing.map_api import MapAPIClient, MockMapAPIClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import fuel station data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to CSV file with fuel prices'
        )
        parser.add_argument(
            '--geocode',
            action='store_true',
            help='Geocode stations missing coordinates'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Batch size for bulk insert'
        )
        parser.add_argument(
            '--use-mock',
            action='store_true',
            help='Use MockMapAPIClient for fast geocoding'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        geocode = options['geocode']
        batch_size = options['batch_size']
        use_mock = options['use_mock']

        self.stdout.write(f"Importing fuel stations from {csv_file}")

        # Clear existing stations
        FuelStation.objects.all().delete()
        self.stdout.write("Cleared existing fuel stations")

        stations_to_create = []
        seen_opis_ids = set()

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for i, row in enumerate(reader, 1):
                    try:
                        opis_id = int(row['OPIS Truckstop ID'])

                        if opis_id in seen_opis_ids:
                            continue
                        seen_opis_ids.add(opis_id)

                        try:
                            price = Decimal(row['Retail Price'])
                        except (InvalidOperation, ValueError):
                            logger.warning(
                                f"Invalid price for OPIS ID {opis_id}: {row['Retail Price']}"
                            )
                            continue

                        rack_id = None
                        if row.get('Rack ID'):
                            try:
                                rack_id = int(row['Rack ID'])
                            except ValueError:
                                pass

                        station = FuelStation(
                            opis_id=opis_id,
                            name=row['Truckstop Name'].strip(),
                            address=row['Address'].strip(),
                            city=row['City'].strip(),
                            state=row['State'].strip().upper(),
                            rack_id=rack_id,
                            retail_price=price,
                            latitude=None,
                            longitude=None
                        )

                        stations_to_create.append(station)

                        if len(stations_to_create) >= batch_size:
                            FuelStation.objects.bulk_create(
                                stations_to_create,
                                ignore_conflicts=True
                            )
                            self.stdout.write(f"Imported {i} stations...")
                            stations_to_create = []

                    except Exception as e:
                        logger.error(f"Error processing row {i}: {e}")
                        continue

        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"File not found: {csv_file}"))
            return

        if stations_to_create:
            FuelStation.objects.bulk_create(
                stations_to_create,
                ignore_conflicts=True
            )

        total_imported = FuelStation.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully imported {total_imported} fuel stations"
            )
        )

        if geocode:
            self.stdout.write("Starting geocoding...")
            self._geocode_stations(use_mock=use_mock)

    # -------------------------------------------------
    # Geocoding (Logic preserved)
    # -------------------------------------------------
    def _geocode_stations(self, use_mock=False):
        """
        Geocode stations missing coordinates.

        Notes:
        * Live API requires 1-second delay between requests.
        * Mock client is recommended for development/testing.
        """
        stations = FuelStation.objects.filter(
            latitude__isnull=True
        )

        total = stations.count()
        self.stdout.write(f"Found {total} stations to geocode")

        # Select client
        map_client = (
            MockMapAPIClient(use_cache=True)
            if use_mock
            else MapAPIClient(use_cache=True)
        )

        geocoded = 0
        failed = 0

        for i, station in enumerate(stations, 1):
            try:
                location = f"{station.address}, {station.city}, {station.state}, USA"

                lat, lng = map_client.geocode_location(location)

                station.latitude = Decimal(str(lat))
                station.longitude = Decimal(str(lng))
                station.save(update_fields=["latitude", "longitude"])

                geocoded += 1

                if i % 100 == 0:
                    self.stdout.write(f"Geocoded {i}/{total} stations...")

                # Respect Nominatim usage policy if live
                if not use_mock:
                    time.sleep(1.1)  # Wait 1.1s to avoid rate-limiting

            except Exception as e:
                logger.error(f"Failed to geocode {station.name}: {e}")
                failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Geocoding complete: {geocoded} succeeded, {failed} failed"
            )
        )
