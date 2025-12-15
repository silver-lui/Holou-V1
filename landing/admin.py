from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import LearningPlan, Avatar, Wishlist, Feedback, PartnerInterest
import json


@admin.register(LearningPlan)
class LearningPlanAdmin(admin.ModelAdmin):
    list_display = ['id', 'project_title_display', 'developer_level', 'status', 'created_at', 'action_buttons']
    list_filter = ['status', 'developer_level', 'created_at']
    search_fields = ['project_description', 'framework', 'software_type']
    readonly_fields = ['created_at', 'updated_at', 'approved_at', 'session_key', 'plan_data_display']
    
    fieldsets = (
        ('User Input', {
            'fields': ('project_description', 'developer_level', 'framework', 'software_type', 'session_key')
        }),
        ('Plan Data', {
            'fields': ('plan_data_display', 'plan_data'),
            'classes': ('wide',)
        }),
        ('Status', {
            'fields': ('status', 'created_at', 'updated_at', 'approved_at')
        }),
    )
    
    def project_title_display(self, obj):
        """Display project title in list view"""
        title = obj.get_project_title()
        return title[:50] + '...' if len(title) > 50 else title
    project_title_display.short_description = 'Project Title'
    
    def plan_data_display(self, obj):
        """Display formatted plan data"""
        if not obj.plan_data:
            return "No plan data"
        
        # Format the JSON nicely
        formatted_json = json.dumps(obj.plan_data, indent=2, ensure_ascii=False)
        return format_html('<pre style="max-height: 500px; overflow-y: auto; background: #f5f5f5; padding: 10px; border-radius: 5px;">{}</pre>', formatted_json)
    plan_data_display.short_description = 'Plan Data (Read-only)'
    
    def action_buttons(self, obj):
        """Display action buttons"""
        if obj.status == 'pending':
            approve_url = reverse('admin:landing_learningplan_approve', args=[obj.pk])
            reject_url = reverse('admin:landing_learningplan_reject', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" style="background: #28a745; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px; margin-right: 5px;">Approve</a>'
                '<a class="button" href="{}" style="background: #dc3545; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">Reject</a>',
                approve_url, reject_url
            )
        elif obj.status == 'approved':
            return format_html('<span style="color: #28a745; font-weight: bold;">✓ Approved</span>')
        else:
            return format_html('<span style="color: #dc3545;">✗ Rejected</span>')
    action_buttons.short_description = 'Actions'
    
    def get_urls(self):
        """Add custom URLs for approve/reject actions"""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:plan_id>/approve/',
                self.admin_site.admin_view(self.approve_plan),
                name='landing_learningplan_approve',
            ),
            path(
                '<int:plan_id>/reject/',
                self.admin_site.admin_view(self.reject_plan),
                name='landing_learningplan_reject',
            ),
        ]
        return custom_urls + urls
    
    def approve_plan(self, request, plan_id):
        """Approve a learning plan"""
        from django.shortcuts import redirect, get_object_or_404
        from django.contrib import messages
        
        plan = get_object_or_404(LearningPlan, pk=plan_id)
        plan.approve()
        messages.success(request, f'Plan "{plan.get_project_title()}" has been approved.')
        return redirect('admin:landing_learningplan_changelist')
    
    def reject_plan(self, request, plan_id):
        """Reject a learning plan"""
        from django.shortcuts import redirect, get_object_or_404
        from django.contrib import messages
        
        plan = get_object_or_404(LearningPlan, pk=plan_id)
        plan.reject()
        messages.success(request, f'Plan "{plan.get_project_title()}" has been rejected.')
        return redirect('admin:landing_learningplan_changelist')


@admin.register(Avatar)
class AvatarAdmin(admin.ModelAdmin):
    list_display = ['id', 'character_class', 'profession', 'created_at', 'avatar_preview']
    list_filter = ['character_class', 'profession', 'created_at']
    search_fields = ['character_class', 'profession', 'session_key']
    readonly_fields = ['created_at', 'avatar_preview', 'original_image_preview']
    
    fieldsets = (
        ('Avatar Info', {
            'fields': ('character_class', 'profession', 'session_key', 'created_at')
        }),
        ('Images', {
            'fields': ('original_image', 'original_image_preview', 'generated_avatar', 'avatar_preview')
        }),
    )
    
    def avatar_preview(self, obj):
        """Display generated avatar preview"""
        if obj.generated_avatar:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px; border-radius: 8px;" />',
                obj.generated_avatar.url
            )
        return "No avatar generated"
    avatar_preview.short_description = 'Generated Avatar'
    
    def original_image_preview(self, obj):
        """Display original image preview"""
        if obj.original_image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px; border-radius: 8px;" />',
                obj.original_image.url
            )
        return "No original image"
    original_image_preview.short_description = 'Original Image'


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['email', 'full_name', 'company_name', 'job_title', 'created_at']
    list_filter = ['created_at', 'company_name']
    search_fields = ['email', 'first_name', 'last_name', 'company_name', 'job_title']
    readonly_fields = ['created_at', 'updated_at', 'session_key']
    
    fieldsets = (
        ('Contact Information', {
            'fields': ('email', 'first_name', 'last_name')
        }),
        ('Professional Information', {
            'fields': ('company_name', 'job_title')
        }),
        ('Additional Information', {
            'fields': ('additional_info',)
        }),
        ('Metadata', {
            'fields': ('session_key', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def full_name(self, obj):
        """Display full name"""
        name = f"{obj.first_name} {obj.last_name}".strip()
        return name if name else "—"
    full_name.short_description = 'Name'


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['id', 'feedback_preview', 'email', 'name', 'created_at']
    list_filter = ['created_at']
    search_fields = ['feedback_text', 'email', 'name', 'session_key']
    readonly_fields = ['created_at', 'updated_at', 'session_key']
    
    fieldsets = (
        ('Feedback', {
            'fields': ('feedback_text',)
        }),
        ('Contact Information', {
            'fields': ('email', 'name')
        }),
        ('Metadata', {
            'fields': ('session_key', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def feedback_preview(self, obj):
        """Display feedback preview"""
        preview = obj.feedback_text[:100] + '...' if len(obj.feedback_text) > 100 else obj.feedback_text
        return preview
    feedback_preview.short_description = 'Feedback'


@admin.register(PartnerInterest)
class PartnerInterestAdmin(admin.ModelAdmin):
    list_display = ['id', 'email', 'name', 'company_name', 'created_at']
    list_filter = ['created_at', 'company_name']
    search_fields = ['email', 'name', 'company_name', 'message', 'session_key']
    readonly_fields = ['created_at', 'updated_at', 'session_key']
    
    fieldsets = (
        ('Contact Information', {
            'fields': ('email', 'name', 'company_name')
        }),
        ('Message', {
            'fields': ('message',)
        }),
        ('Metadata', {
            'fields': ('session_key', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
