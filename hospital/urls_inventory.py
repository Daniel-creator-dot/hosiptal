"""
URL Configuration for World-Class Inventory Management System
"""
from django.urls import path
from . import views_inventory_worldclass as inventory_views

app_name = 'inventory'

urlpatterns = [
    # Main Dashboard
    path('dashboard/', inventory_views.inventory_dashboard, name='inventory_dashboard'),
    
    # Inventory Items
    path('items/', inventory_views.inventory_items_list, name='items_list'),
    path('items/<uuid:item_id>/', inventory_views.inventory_item_detail, name='item_detail'),
    
    # Stock Alerts
    path('alerts/', inventory_views.stock_alerts_list, name='alerts_list'),
    path('alerts/<uuid:alert_id>/acknowledge/', inventory_views.acknowledge_alert, name='acknowledge_alert'),
    path('alerts/<uuid:alert_id>/resolve/', inventory_views.resolve_alert, name='resolve_alert'),
    
    # Requisitions
    path('requisitions/', inventory_views.requisitions_list, name='requisitions_list'),
    path('requisitions/create/', inventory_views.create_requisition, name='create_requisition'),
    path('requisitions/<uuid:req_id>/', inventory_views.requisition_detail, name='requisition_detail'),
    
    # Transfers
    path('transfers/', inventory_views.transfers_list, name='transfers_list'),
    
    # Analytics
    path('analytics/', inventory_views.inventory_analytics, name='analytics'),
    
    # API Endpoints
    path('api/stats/', inventory_views.inventory_api_stats, name='api_stats'),
    path('api/store-items/', inventory_views.api_store_items_for_requisition, name='api_store_items'),
]



















