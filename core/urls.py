from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('smart-input/', views.smart_input_processor, name='smart_input_processor'),
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/create/', views.invoice_create, name='invoice_create'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/edit/', views.invoice_edit, name='invoice_edit'),
    path('invoices/<int:pk>/pdf/', views.invoice_pdf, name='invoice_pdf'),
    path('invoices/<int:pk>/clear/', views.clear_invoice_firs, name='clear_invoice_firs'),
    path('invoices/public/<uuid:token>/', views.public_invoice_detail, name='public_invoice_detail'),
    path('invoices/public/<uuid:token>/pdf/', views.public_invoice_pdf, name='public_invoice_pdf'),
    
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/create/', views.customer_create, name='customer_create'),
    path('customers/quick-create/', views.quick_customer_create, name='quick_customer_create'),
    path('customers/<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('customers/<int:pk>/contact/', views.update_customer_contact, name='update_customer_contact'),
    
    path('products/', views.product_list, name='product_list'),
    path('products/create/', views.product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),

    path('notifications/unread-count/', views.unread_notifications_count, name='unread_notifications_count'),
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('onboarding/', views.onboarding, name='onboarding'),
    path('profile/', views.profile_settings, name='profile_settings'),
    path('signup/', views.signup, name='signup'),
]
