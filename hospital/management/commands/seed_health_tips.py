"""
Management command to seed default health tips for the queue display
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from hospital.models_queue import HealthTip


class Command(BaseCommand):
    help = 'Seed default health tips for the queue wellness spotlight'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing tips before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            HealthTip.objects.all().delete()
            self.stdout.write(self.style.WARNING('Cleared existing health tips.'))

        tips_data = [
            {
                'title': 'Stay Hydrated!',
                'message': 'Welcome! Sip water frequently while you wait to keep energized for your consultation. We care about your well-being! 🌟',
                'icon': '💧',
                'category': 'Wellness',
                'audience': 'general',
                'display_order': 1,
            },
            {
                'title': 'Practice Deep Breathing',
                'message': 'Take slow, deep breaths to help you relax. Breathe in through your nose for 4 counts, hold for 4, and exhale through your mouth for 4. It works wonders! 😌',
                'icon': '🧘',
                'category': 'Relaxation',
                'audience': 'general',
                'display_order': 2,
            },
            {
                'title': 'Limit Screen Time',
                'message': 'While waiting, try to rest your eyes. Look away from your phone or book every 20 minutes. Your eyes will thank you! 👀',
                'icon': '📱',
                'category': 'Eye Care',
                'audience': 'general',
                'display_order': 3,
            },
            {
                'title': 'Gentle Movement',
                'message': 'Feel free to stand and stretch gently if you\'ve been sitting. Gentle movement improves circulation and helps reduce tension. 💪',
                'icon': '🚶',
                'category': 'Physical Health',
                'audience': 'general',
                'display_order': 4,
            },
            {
                'title': 'Stay Positive',
                'message': 'Remember, our healthcare team is here to help! We\'re working efficiently to ensure everyone receives the best care possible. Stay positive! 🌈',
                'icon': '😊',
                'category': 'Mental Health',
                'audience': 'general',
                'display_order': 5,
            },
            {
                'title': 'Prepare Your Questions',
                'message': 'Use this time to note down any questions or concerns you\'d like to discuss with your healthcare provider. It helps make the most of your consultation! 📋',
                'icon': '📝',
                'category': 'Preparation',
                'audience': 'general',
                'display_order': 6,
            },
            {
                'title': 'Eat Nutritious Meals',
                'message': 'If possible, enjoy a light, nutritious snack while waiting. Fresh fruits, nuts, or whole grains give you sustained energy. Your body will appreciate it! 🥗',
                'icon': '🍎',
                'category': 'Nutrition',
                'audience': 'general',
                'display_order': 7,
            },
            {
                'title': 'We\'re Here for You',
                'message': 'Your health is our priority! Our friendly staff is available to assist you with any questions or concerns. Don\'t hesitate to ask! 💙',
                'icon': '🤝',
                'category': 'Support',
                'audience': 'general',
                'display_order': 8,
            },
            {
                'title': 'Wash Your Hands',
                'message': 'Remember to wash your hands regularly, especially before eating or touching your face. Good hygiene protects you and others! 🧼',
                'icon': '🧼',
                'category': 'Hygiene',
                'audience': 'general',
                'display_order': 9,
            },
            {
                'title': 'Get Enough Sleep',
                'message': 'Adequate rest is essential for healing. Aim for 7-9 hours of quality sleep each night. Your body repairs itself while you sleep! 😴',
                'icon': '😴',
                'category': 'Rest',
                'audience': 'general',
                'display_order': 10,
            },
            {
                'title': 'Stay Active',
                'message': 'Regular physical activity boosts your immune system and improves overall health. Even a short walk can make a big difference! 🏃',
                'icon': '🏃',
                'category': 'Physical Health',
                'audience': 'general',
                'display_order': 11,
            },
            {
                'title': 'Manage Stress',
                'message': 'Take time for activities you enjoy. Reading, listening to music, or meditating can help reduce stress and improve your well-being. 🎵',
                'icon': '🎵',
                'category': 'Mental Health',
                'audience': 'general',
                'display_order': 12,
            },
        ]

        created_count = 0
        updated_count = 0

        for tip_data in tips_data:
            tip, created = HealthTip.objects.update_or_create(
                title=tip_data['title'],
                defaults={
                    'message': tip_data['message'],
                    'icon': tip_data['icon'],
                    'category': tip_data['category'],
                    'audience': tip_data['audience'],
                    'display_order': tip_data['display_order'],
                    'is_active': True,
                }
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {tip.title}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'↻ Updated: {tip.title}'))

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Successfully seeded {len(tips_data)} health tips! '
            f'({created_count} created, {updated_count} updated)'
        ))
        self.stdout.write(self.style.SUCCESS(
            '\n💡 Tips will automatically rotate every 8 seconds on the queue display.'
        ))


