"""
Management command to seed dental procedures with prices
"""
from django.core.management.base import BaseCommand
from hospital.models_specialists import DentalProcedureCatalog
from decimal import Decimal


class Command(BaseCommand):
    help = 'Seed dental procedures catalog with codes and prices for Ghana'

    def handle(self, *args, **options):
        # Common dental procedures with codes and prices in Ghana Cedis (GHS)
        # Based on common dental procedure codes (CDT codes)
        procedures = [
            # Diagnostic Procedures
            {'code': 'D0110', 'name': 'Oral Evaluation - New Patient', 'procedure_type': 'diagnostic', 'description': 'Complete oral evaluation for new patient', 'default_price': Decimal('50.00')},
            {'code': 'D0120', 'name': 'Oral Evaluation - Periodic', 'procedure_type': 'diagnostic', 'description': 'Routine oral evaluation', 'default_price': Decimal('30.00')},
            {'code': 'D0140', 'name': 'Oral Evaluation - Limited', 'procedure_type': 'diagnostic', 'description': 'Focused oral evaluation', 'default_price': Decimal('25.00')},
            {'code': 'D0150', 'name': 'Oral Evaluation - Emergency', 'procedure_type': 'diagnostic', 'description': 'Emergency oral evaluation', 'default_price': Decimal('40.00')},
            {'code': 'D0210', 'name': 'Intraoral X-Ray - Periapical', 'procedure_type': 'diagnostic', 'description': 'Periapical X-ray', 'default_price': Decimal('15.00')},
            {'code': 'D0220', 'name': 'Intraoral X-Ray - Bitewing', 'procedure_type': 'diagnostic', 'description': 'Bitewing X-ray', 'default_price': Decimal('15.00')},
            {'code': 'D0270', 'name': 'Bitewing X-Ray - Two Films', 'procedure_type': 'diagnostic', 'description': 'Two bitewing X-rays', 'default_price': Decimal('25.00')},
            {'code': 'D0330', 'name': 'Panoramic X-Ray', 'procedure_type': 'diagnostic', 'description': 'Panoramic radiograph', 'default_price': Decimal('40.00')},
            
            # Preventive Procedures
            {'code': 'D1110', 'name': 'Adult Prophylaxis', 'procedure_type': 'preventive', 'description': 'Adult teeth cleaning', 'default_price': Decimal('80.00')},
            {'code': 'D1120', 'name': 'Child Prophylaxis', 'procedure_type': 'preventive', 'description': 'Child teeth cleaning', 'default_price': Decimal('60.00')},
            {'code': 'D1206', 'name': 'Topical Fluoride - Child', 'procedure_type': 'preventive', 'description': 'Fluoride application for children', 'default_price': Decimal('30.00')},
            {'code': 'D1208', 'name': 'Topical Fluoride - Adult', 'procedure_type': 'preventive', 'description': 'Fluoride application for adults', 'default_price': Decimal('40.00')},
            {'code': 'D1330', 'name': 'Oral Hygiene Instruction', 'procedure_type': 'preventive', 'description': 'Oral hygiene education', 'default_price': Decimal('20.00')},
            {'code': 'D1351', 'name': 'Sealant - Per Tooth', 'procedure_type': 'preventive', 'description': 'Dental sealant application', 'default_price': Decimal('50.00')},
            
            # Restorative Procedures - Fillings
            {'code': 'D2140', 'name': 'Amalgam Restoration - One Surface', 'procedure_type': 'restorative', 'description': 'Amalgam filling - one surface', 'default_price': Decimal('80.00')},
            {'code': 'D2150', 'name': 'Amalgam Restoration - Two Surfaces', 'procedure_type': 'restorative', 'description': 'Amalgam filling - two surfaces', 'default_price': Decimal('120.00')},
            {'code': 'D2160', 'name': 'Amalgam Restoration - Three Surfaces', 'procedure_type': 'restorative', 'description': 'Amalgam filling - three surfaces', 'default_price': Decimal('150.00')},
            {'code': 'D2391', 'name': 'Resin Composite - One Surface', 'procedure_type': 'restorative', 'description': 'Composite filling - one surface', 'default_price': Decimal('100.00')},
            {'code': 'D2392', 'name': 'Resin Composite - Two Surfaces', 'procedure_type': 'restorative', 'description': 'Composite filling - two surfaces', 'default_price': Decimal('150.00')},
            {'code': 'D2393', 'name': 'Resin Composite - Three Surfaces', 'procedure_type': 'restorative', 'description': 'Composite filling - three surfaces', 'default_price': Decimal('200.00')},
            {'code': 'D2394', 'name': 'Resin Composite - Four Surfaces', 'procedure_type': 'restorative', 'description': 'Composite filling - four surfaces', 'default_price': Decimal('250.00')},
            
            # Endodontic Procedures (Root Canal)
            {'code': 'D3310', 'name': 'Root Canal - Anterior', 'procedure_type': 'endodontic', 'description': 'Root canal treatment - anterior tooth', 'default_price': Decimal('250.00')},
            {'code': 'D3320', 'name': 'Root Canal - Bicuspid', 'procedure_type': 'endodontic', 'description': 'Root canal treatment - bicuspid', 'default_price': Decimal('300.00')},
            {'code': 'D3330', 'name': 'Root Canal - Molar', 'procedure_type': 'endodontic', 'description': 'Root canal treatment - molar', 'default_price': Decimal('400.00')},
            {'code': 'D3348', 'name': 'Root Canal Retreatment', 'procedure_type': 'endodontic', 'description': 'Root canal retreatment', 'default_price': Decimal('450.00')},
            
            # Periodontic Procedures
            {'code': 'D4341', 'name': 'Scaling and Root Planing - Per Quadrant', 'procedure_type': 'periodontic', 'description': 'Deep cleaning per quadrant', 'default_price': Decimal('150.00')},
            {'code': 'D4910', 'name': 'Periodontal Maintenance', 'procedure_type': 'periodontic', 'description': 'Periodontal maintenance cleaning', 'default_price': Decimal('100.00')},
            
            # Oral Surgery Procedures
            {'code': 'D7111', 'name': 'Tooth Extraction - Simple', 'procedure_type': 'oral_surgery', 'description': 'Simple tooth extraction', 'default_price': Decimal('50.00')},
            {'code': 'D7210', 'name': 'Tooth Extraction - Surgical', 'procedure_type': 'oral_surgery', 'description': 'Surgical tooth extraction', 'default_price': Decimal('150.00')},
            {'code': 'D7240', 'name': 'Impacted Tooth Removal', 'procedure_type': 'oral_surgery', 'description': 'Surgical removal of impacted tooth', 'default_price': Decimal('200.00')},
            {'code': 'D7310', 'name': 'Alveoloplasty', 'procedure_type': 'oral_surgery', 'description': 'Alveolar ridge recontouring', 'default_price': Decimal('300.00')},
            
            # Prosthodontic Procedures
            {'code': 'D2510', 'name': 'Crown - Porcelain Fused to Metal', 'procedure_type': 'prosthodontic', 'description': 'PFM crown', 'default_price': Decimal('500.00')},
            {'code': 'D2520', 'name': 'Crown - All Porcelain', 'procedure_type': 'prosthodontic', 'description': 'All-ceramic crown', 'default_price': Decimal('600.00')},
            {'code': 'D2710', 'name': 'Crown - All Metal', 'procedure_type': 'prosthodontic', 'description': 'Metal crown', 'default_price': Decimal('400.00')},
            {'code': 'D5213', 'name': 'Partial Denture - Maxillary', 'procedure_type': 'prosthodontic', 'description': 'Upper partial denture', 'default_price': Decimal('800.00')},
            {'code': 'D5214', 'name': 'Partial Denture - Mandibular', 'procedure_type': 'prosthodontic', 'description': 'Lower partial denture', 'default_price': Decimal('800.00')},
            {'code': 'D5110', 'name': 'Complete Denture - Upper', 'procedure_type': 'prosthodontic', 'description': 'Complete upper denture', 'default_price': Decimal('1000.00')},
            {'code': 'D5120', 'name': 'Complete Denture - Lower', 'procedure_type': 'prosthodontic', 'description': 'Complete lower denture', 'default_price': Decimal('1000.00')},
            {'code': 'D6010', 'name': 'Implant - Surgical Placement', 'procedure_type': 'prosthodontic', 'description': 'Dental implant placement', 'default_price': Decimal('1500.00')},
            
            # Orthodontic Procedures
            {'code': 'D8080', 'name': 'Comprehensive Orthodontic Treatment', 'procedure_type': 'orthodontic', 'description': 'Full orthodontic treatment', 'default_price': Decimal('3000.00')},
            {'code': 'D8670', 'name': 'Orthodontic Retainer', 'procedure_type': 'orthodontic', 'description': 'Orthodontic retainer', 'default_price': Decimal('300.00')},
            
            # Cosmetic Procedures
            {'code': 'D9971', 'name': 'Teeth Whitening - In-Office', 'procedure_type': 'cosmetic', 'description': 'In-office teeth whitening', 'default_price': Decimal('400.00')},
            {'code': 'D9972', 'name': 'Teeth Whitening - Take-Home Kit', 'procedure_type': 'cosmetic', 'description': 'Take-home whitening kit', 'default_price': Decimal('250.00')},
            {'code': 'D9973', 'name': 'Veneer - Porcelain', 'procedure_type': 'cosmetic', 'description': 'Porcelain veneer per tooth', 'default_price': Decimal('700.00')},
            
            # Additional Ghana-specific Procedures
            {'code': 'D-CONSULT-001', 'name': 'Specialist Consultation-Dental', 'procedure_type': 'diagnostic', 'description': 'Dental specialist consultation', 'default_price': Decimal('80.00')},
            {'code': 'D-PREV-001', 'name': 'Scaling & Polishing', 'procedure_type': 'preventive', 'description': 'Professional teeth scaling and polishing', 'default_price': Decimal('100.00')},
            {'code': 'D-PREV-002', 'name': 'Scaling & Polishing -Intermediate', 'procedure_type': 'preventive', 'description': 'Intermediate scaling and polishing', 'default_price': Decimal('120.00')},
            {'code': 'D-OS-001', 'name': 'Dental Simple Extraction Less than 12 Molar', 'procedure_type': 'oral_surgery', 'description': 'Simple extraction for teeth less than 12 years (molar)', 'default_price': Decimal('60.00')},
            {'code': 'D-OS-002', 'name': 'Surgical Extraction 3', 'procedure_type': 'oral_surgery', 'description': 'Surgical extraction procedure', 'default_price': Decimal('200.00')},
            {'code': 'D-OS-003', 'name': 'Dental Surgical Extraction 3', 'procedure_type': 'oral_surgery', 'description': 'Surgical tooth extraction', 'default_price': Decimal('200.00')},
            {'code': 'D-OS-004', 'name': 'Operculectomy', 'procedure_type': 'oral_surgery', 'description': 'Removal of operculum (gum flap over wisdom tooth)', 'default_price': Decimal('150.00')},
            {'code': 'D-REST-001', 'name': 'Composite Filling,Pass and Call', 'procedure_type': 'restorative', 'description': 'Composite filling with pass and call', 'default_price': Decimal('120.00')},
            {'code': 'D-REST-002', 'name': 'Dental Large Restoration-Composite', 'procedure_type': 'restorative', 'description': 'Large composite restoration', 'default_price': Decimal('180.00')},
            {'code': 'D-REST-003', 'name': 'Restoration GIC', 'procedure_type': 'restorative', 'description': 'Glass Ionomer Cement restoration', 'default_price': Decimal('100.00')},
            {'code': 'D-REST-004', 'name': 'Restoration Composite 1&2', 'procedure_type': 'restorative', 'description': 'Composite restoration - one and two surfaces', 'default_price': Decimal('150.00')},
            {'code': 'D-REST-005', 'name': 'Large Restoration Composite 1 & GIC 1', 'procedure_type': 'restorative', 'description': 'Large restoration using composite and GIC', 'default_price': Decimal('200.00')},
            {'code': 'D-REST-006', 'name': 'Dental Large Restoration-Composite GIC-1', 'procedure_type': 'restorative', 'description': 'Large composite restoration with GIC', 'default_price': Decimal('200.00')},
            {'code': 'D-REST-007', 'name': 'Dental Small Restoration-Composite 1', 'procedure_type': 'restorative', 'description': 'Small composite restoration - one surface', 'default_price': Decimal('100.00')},
            {'code': 'D-REST-008', 'name': 'Single Denture Composite Restoration', 'procedure_type': 'restorative', 'description': 'Composite restoration for single denture', 'default_price': Decimal('150.00')},
            {'code': 'D-ENDO-001', 'name': 'Dental Retreatment Molar RCT', 'procedure_type': 'endodontic', 'description': 'Root canal retreatment for molar', 'default_price': Decimal('500.00')},
            {'code': 'D-ENDO-002', 'name': 'RCT Premolar { Upper}', 'procedure_type': 'endodontic', 'description': 'Root canal treatment for upper premolar', 'default_price': Decimal('350.00')},
            {'code': 'D-PERIO-001', 'name': 'Scaling & Root Planning', 'procedure_type': 'periodontic', 'description': 'Scaling and root planing procedure', 'default_price': Decimal('180.00')},
            {'code': 'D-PROST-001', 'name': 'Dental Post Insertion', 'procedure_type': 'prosthodontic', 'description': 'Post insertion for crown restoration', 'default_price': Decimal('150.00')},
            {'code': 'D-PROST-002', 'name': 'Dental Recementation,Crown', 'procedure_type': 'prosthodontic', 'description': 'Recementation of dental crown', 'default_price': Decimal('100.00')},
            {'code': 'D-PROST-003', 'name': 'VALPLAST { Ante & Post }', 'procedure_type': 'prosthodontic', 'description': 'VALPLAST flexible partial denture - anterior and posterior', 'default_price': Decimal('1200.00')},
            {'code': 'D-PROST-004', 'name': 'VALPLAST { Post }', 'procedure_type': 'prosthodontic', 'description': 'VALPLAST flexible partial denture - posterior', 'default_price': Decimal('1000.00')},
            {'code': 'D-DIAG-001', 'name': 'Dental X-Ray', 'procedure_type': 'diagnostic', 'description': 'Dental X-ray examination', 'default_price': Decimal('30.00')},
        ]
        
        created_count = 0
        updated_count = 0
        
        for proc_data in procedures:
            procedure, created = DentalProcedureCatalog.objects.update_or_create(
                code=proc_data['code'],
                defaults={
                    'name': proc_data['name'],
                    'procedure_type': proc_data['procedure_type'],
                    'description': proc_data['description'],
                    'default_price': proc_data['default_price'],
                    'currency': 'GHS',
                    'is_active': True,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created: {procedure.code} - {procedure.name} - GHS {procedure.default_price}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'Updated: {procedure.code} - {procedure.name} - GHS {procedure.default_price}'))
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully seeded dental procedures!\n'
                f'Created: {created_count}\n'
                f'Updated: {updated_count}\n'
                f'Total: {len(procedures)}'
            )
        )
