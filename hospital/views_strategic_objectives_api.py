"""
Strategic Objectives API - Real-time updates
"""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .views_strategic_objectives import calculate_strategic_objectives_metrics
import logging

logger = logging.getLogger(__name__)


@login_required
def strategic_objectives_api(request):
    """
    API endpoint for real-time strategic objectives data
    Returns JSON with current progress for all objectives
    """
    try:
        objectives_data = calculate_strategic_objectives_metrics()
        
        # Format for frontend consumption
        formatted_data = {
            'success': True,
            'overall_progress': objectives_data.get('overall_progress', 0),
            'last_updated': objectives_data.get('last_updated'),
            'objectives': {}
        }
        
        # Format each objective
        for key, obj in objectives_data.get('objectives', {}).items():
            formatted_data['objectives'][key] = {
                'title': obj.get('title', ''),
                'description': obj.get('description', ''),
                'progress': float(obj.get('progress', 0)),
                'color': obj.get('color', '#3b82f6'),
                'icon': obj.get('icon', 'bi-circle'),
                'kpis': obj.get('kpis', []),
                'metrics': obj.get('metrics', {})
            }
        
        return JsonResponse(formatted_data)
    except Exception as e:
        logger.error(f"Error in strategic objectives API: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e),
            'overall_progress': 0,
            'objectives': {}
        }, status=500)
