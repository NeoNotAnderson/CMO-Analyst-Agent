"""
Django management command to migrate existing prospectuses to chunking system.

Usage:
    python manage.py migrate_to_chunking [--prospectus-id ID] [--force]

Options:
    --prospectus-id ID    Migrate specific prospectus by ID (optional)
    --force               Force re-chunking even if already done
    --dry-run             Show what would be migrated without making changes
"""

from django.core.management.base import BaseCommand, CommandError
from core.models import Prospectus, ProspectusChunk
from agents.parsing_agent.chunking import process_prospectus_to_chunks


class Command(BaseCommand):
    help = 'Migrate existing prospectuses to chunking system for hybrid search'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prospectus-id',
            type=str,
            help='Specific prospectus ID to migrate',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-chunking even if already done',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without making changes',
        )

    def handle(self, *args, **options):
        prospectus_id = options.get('prospectus_id')
        force = options.get('force', False)
        dry_run = options.get('dry_run', False)

        # Get prospectuses to migrate
        if prospectus_id:
            try:
                prospectuses = [Prospectus.objects.get(prospectus_id=prospectus_id)]
            except Prospectus.DoesNotExist:
                raise CommandError(f'Prospectus with ID {prospectus_id} does not exist')
        else:
            # Get all completed prospectuses
            prospectuses = Prospectus.objects.filter(parse_status='completed')

        self.stdout.write(f"Found {len(prospectuses)} completed prospectus(es)")

        migrated_count = 0
        skipped_count = 0
        error_count = 0

        for prospectus in prospectuses:
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"Processing: {prospectus.prospectus_name}")
            self.stdout.write(f"ID: {prospectus.prospectus_id}")

            # Check if already chunked
            existing_chunks = ProspectusChunk.objects.filter(prospectus=prospectus).count()
            chunks_generated = prospectus.metadata.get('chunks_generated', False) if prospectus.metadata else False

            if existing_chunks > 0 and chunks_generated and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped (already has {existing_chunks} chunks). Use --force to re-chunk."
                    )
                )
                skipped_count += 1
                continue

            # Check if parsed_file exists
            if not prospectus.parsed_file or 'sections' not in prospectus.parsed_file:
                self.stdout.write(
                    self.style.ERROR("Skipped (no parsed_file data)")
                )
                skipped_count += 1
                continue

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        "[DRY RUN] Would generate chunks and embeddings"
                    )
                )
                migrated_count += 1
                continue

            # Perform migration
            try:
                # Delete existing chunks if force
                if force and existing_chunks > 0:
                    self.stdout.write(f"Deleting {existing_chunks} existing chunks...")
                    ProspectusChunk.objects.filter(prospectus=prospectus).delete()

                self.stdout.write("Generating chunks and embeddings...")

                # Process prospectus into chunks
                chunks_data = process_prospectus_to_chunks(prospectus.parsed_file)
                self.stdout.write(f"Generated {len(chunks_data)} chunks")

                # Bulk create chunks
                chunk_objects = [
                    ProspectusChunk(
                        prospectus=prospectus,
                        chunk_text=chunk['chunk_text'],
                        chunk_index=chunk['chunk_index'],
                        embedding=chunk['embedding'],
                        metadata=chunk['metadata']
                    )
                    for chunk in chunks_data
                ]

                ProspectusChunk.objects.bulk_create(chunk_objects, batch_size=100)
                self.stdout.write(f"Saved {len(chunk_objects)} chunks to database")

                # Update prospectus metadata
                if not prospectus.metadata:
                    prospectus.metadata = {}
                prospectus.metadata['chunks_generated'] = True
                prospectus.metadata['chunk_count'] = len(chunk_objects)
                prospectus.metadata['migration_date'] = str(prospectus.upload_date)
                prospectus.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Successfully migrated {prospectus.prospectus_name}"
                    )
                )
                migrated_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Error migrating {prospectus.prospectus_name}: {str(e)}"
                    )
                )
                error_count += 1

                # Save error in metadata
                if not prospectus.metadata:
                    prospectus.metadata = {}
                prospectus.metadata['chunks_generated'] = False
                prospectus.metadata['chunking_error'] = str(e)
                prospectus.save()

        # Summary
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(self.style.SUCCESS(f"MIGRATION SUMMARY"))
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"Migrated: {migrated_count}")
        self.stdout.write(f"Skipped:  {skipped_count}")
        self.stdout.write(f"Errors:   {error_count}")
        self.stdout.write(f"Total:    {len(prospectuses)}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n[DRY RUN] No changes were made. Run without --dry-run to perform migration."
                )
            )
