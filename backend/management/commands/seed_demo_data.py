from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from backend.models import Profile, Shoe, ShoeSize


class Command(BaseCommand):
    help = "Seed demo data (idempotent) for local/dev smoke testing."

    @transaction.atomic
    def handle(self, *args, **options):
        seeded_shoes = [
            {
                "brand": "Nike",
                "model": "Air Zoom Pegasus",
                "gender": Shoe.Gender.WOMEN,
                "price_usd": "129.99",
                "sizes": ["8.0", "8.5", "9.0"],
            },
            {
                "brand": "Adidas",
                "model": "Ultraboost Light",
                "gender": Shoe.Gender.UNISEX,
                "price_usd": "149.99",
                "sizes": ["8.5", "9.0", "9.5"],
            },
            {
                "brand": "New Balance",
                "model": "Fresh Foam X 1080",
                "gender": Shoe.Gender.MEN,
                "price_usd": "164.99",
                "sizes": ["9.0", "9.5", "10.0"],
            },
        ]

        created_shoes = 0
        created_sizes = 0

        for item in seeded_shoes:
            shoe, was_created = Shoe.objects.get_or_create(
                brand=item["brand"],
                model=item["model"],
                defaults={
                    "gender": item["gender"],
                    "price_usd": item["price_usd"],
                    # So recommendations can compute fit scores (see dev_backfill_shoe_insoles).
                    "insole_length_in": Decimal("10.500"),
                    "insole_width_in": Decimal("3.650"),
                },
            )
            if was_created:
                created_shoes += 1

            for us_size in item["sizes"]:
                _, size_created = ShoeSize.objects.get_or_create(
                    shoe=shoe,
                    us_size=us_size,
                    width=ShoeSize.Width.REGULAR,
                    defaults={"is_available": True},
                )
                if size_created:
                    created_sizes += 1

        user_model = get_user_model()
        demo_user, user_created = user_model.objects.get_or_create(
            username="demo_user",
            defaults={
                "email": "demo@shoeshopper.app",
            },
        )

        if user_created:
            demo_user.set_password("demo-pass-1234")
            demo_user.save(update_fields=["password"])

        _, profile_created = Profile.objects.get_or_create(
            user=demo_user,
            defaults={"display_name": "Demo User"},
        )

        self.stdout.write(self.style.SUCCESS("Seed complete."))
        self.stdout.write(
            f"Created shoes: {created_shoes}, created sizes: {created_sizes}, "
            f"demo user created: {user_created}, profile created: {profile_created}"
        )
        self.stdout.write(
            "Demo login -> username: demo_user, password: demo-pass-1234"
        )
