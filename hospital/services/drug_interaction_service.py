"""
Drug Interaction Checking Service
Validates drug-drug interactions for prescriptions
"""
from django.db.models import Q
from ..models_missing_features import DrugInteraction
from ..models import Drug, Prescription, Patient


class DrugInteractionService:
    """Service for checking drug interactions"""
    
    @staticmethod
    def check_interactions(drugs_list, patient=None):
        """
        Check for interactions between drugs in a list
        
        Args:
            drugs_list: List of Drug objects or drug IDs
            patient: Optional Patient object to check against existing prescriptions
            
        Returns:
            dict with 'interactions' (list of DrugInteraction objects) and 'warnings' (list of warnings)
        """
        interactions = []
        warnings = []
        
        # Convert to Drug objects if needed
        drug_objects = []
        for drug in drugs_list:
            if isinstance(drug, int):
                try:
                    drug = Drug.objects.get(pk=drug)
                except Drug.DoesNotExist:
                    continue
            drug_objects.append(drug)
        
        # Check interactions between all pairs of drugs in the list
        for i, drug1 in enumerate(drug_objects):
            for drug2 in drug_objects[i+1:]:
                # Check both directions (drug1-drug2 and drug2-drug1)
                interaction = DrugInteraction.objects.filter(
                    Q(drug1=drug1, drug2=drug2) | Q(drug1=drug2, drug2=drug1)
                ).first()
                
                if interaction:
                    interactions.append(interaction)
                    
                    # Create warning message
                    severity_icons = {
                        'contraindicated': '🚫',
                        'major': '⚠️',
                        'moderate': '⚡',
                        'minor': 'ℹ️',
                    }
                    icon = severity_icons.get(interaction.severity, '⚠️')
                    warning = {
                        'severity': interaction.severity,
                        'drug1': drug1.name,
                        'drug2': drug2.name,
                        'message': f"{icon} {interaction.get_severity_display()}: {interaction.description}",
                        'clinical_significance': interaction.clinical_significance,
                        'management': interaction.management,
                    }
                    warnings.append(warning)
        
        # Check interactions with patient's existing active prescriptions
        if patient:
            active_prescriptions = Prescription.objects.filter(
                order__encounter__patient=patient,
                order__encounter__status='active',
                is_deleted=False
            ).select_related('drug')
            
            existing_drugs = [prescription.drug for prescription in active_prescriptions]
            
            for new_drug in drug_objects:
                for existing_drug in existing_drugs:
                    if new_drug != existing_drug:
                        interaction = DrugInteraction.objects.filter(
                            Q(drug1=new_drug, drug2=existing_drug) | 
                            Q(drug1=existing_drug, drug2=new_drug)
                        ).first()
                        
                        if interaction and interaction not in interactions:
                            interactions.append(interaction)
                            severity_icons = {
                                'contraindicated': '🚫',
                                'major': '⚠️',
                                'moderate': '⚡',
                                'minor': 'ℹ️',
                            }
                            icon = severity_icons.get(interaction.severity, '⚠️')
                            warning = {
                                'severity': interaction.severity,
                                'drug1': new_drug.name,
                                'drug2': existing_drug.name,
                                'message': f"{icon} {interaction.get_severity_display()} with existing prescription: {interaction.description}",
                                'clinical_significance': interaction.clinical_significance,
                                'management': interaction.management,
                            }
                            warnings.append(warning)
        
        # Check for duplicate drugs
        if len(drug_objects) != len(set(drug_objects)):
            warnings.append({
                'severity': 'moderate',
                'drug1': '',
                'drug2': '',
                'message': '⚠️ Duplicate drugs detected in prescription',
                'clinical_significance': '',
                'management': 'Review prescription for duplicate entries',
            })
        
        return {
            'interactions': interactions,
            'warnings': warnings,
            'has_critical': any(w['severity'] in ['contraindicated', 'major'] for w in warnings)
        }
    
    @staticmethod
    def check_prescription_interactions(prescription):
        """Check interactions for a single prescription"""
        drugs = [prescription.drug]
        patient = prescription.order.encounter.patient if prescription.order.encounter else None
        return DrugInteractionService.check_interactions(drugs, patient)
    
    @staticmethod
    def check_order_interactions(order):
        """Check interactions for all prescriptions in an order"""
        prescriptions = Prescription.objects.filter(
            order=order,
            is_deleted=False
        ).select_related('drug')
        
        drugs = [prescription.drug for prescription in prescriptions]
        patient = order.encounter.patient if order.encounter else None
        return DrugInteractionService.check_interactions(drugs, patient)


# Singleton instance
drug_interaction_service = DrugInteractionService()

