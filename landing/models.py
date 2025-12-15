from django.db import models
import json


class LearningPlan(models.Model):
    """Model to store AI-generated learning plans"""
    
    # User input fields
    project_description = models.TextField()
    developer_level = models.CharField(max_length=50)
    framework = models.CharField(max_length=100, blank=True)
    software_type = models.CharField(max_length=100)
    
    # Generated plan data (stored as JSON)
    plan_data = models.JSONField(default=dict)
    
    # Status and metadata
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Session ID to link back to user session
    session_key = models.CharField(max_length=100, blank=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Learning Plan'
        verbose_name_plural = 'Learning Plans'
    
    def __str__(self):
        title = self.plan_data.get('project_overview', {}).get('title', 'Untitled Plan')
        return f"{title} - {self.status} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
    
    def get_project_title(self):
        """Get project title from plan data"""
        return self.plan_data.get('project_overview', {}).get('title', 'Untitled Project')
    
    def approve(self):
        """Approve this plan"""
        from django.utils import timezone
        self.status = 'approved'
        self.approved_at = timezone.now()
        self.save()
    
    def reject(self):
        """Reject this plan"""
        self.status = 'rejected'
        self.save()


class Avatar(models.Model):
    """Model to store AI-generated avatars"""
    
    # User selections
    character_class = models.CharField(max_length=50)  # elf, demon, etc.
    profession = models.CharField(max_length=100)  # web development, frontend development, etc.
    
    # Original uploaded image
    original_image = models.ImageField(upload_to='avatars/original/', blank=True, null=True)
    
    # Generated avatar image
    generated_avatar = models.ImageField(upload_to='avatars/generated/')
    
    # Session ID to link back to user session
    session_key = models.CharField(max_length=100, blank=True, db_index=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Avatar'
        verbose_name_plural = 'Avatars'
    
    def __str__(self):
        return f"{self.character_class} {self.profession} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class Wishlist(models.Model):
    """Model to store wishlist signups (email and user information, no password)"""
    
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    additional_info = models.TextField(blank=True, help_text="Any additional information provided by the user")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Session ID to link back to user session
    session_key = models.CharField(max_length=100, blank=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Wishlist Signup'
        verbose_name_plural = 'Wishlist Signups'
    
    def __str__(self):
        name = f"{self.first_name} {self.last_name}".strip() or "No name"
        return f"{name} ({self.email}) - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class Feedback(models.Model):
    """Model to store user feedback from 'Tell us what you think' section"""
    
    feedback_text = models.TextField()
    email = models.EmailField(blank=True, null=True, help_text="Optional email if user provides it")
    name = models.CharField(max_length=200, blank=True, null=True, help_text="Optional name if user provides it")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Session ID to link back to user session
    session_key = models.CharField(max_length=100, blank=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Feedback'
        verbose_name_plural = 'Feedback Entries'
    
    def __str__(self):
        preview = self.feedback_text[:50] + '...' if len(self.feedback_text) > 50 else self.feedback_text
        email_part = f" ({self.email})" if self.email else ""
        return f"{preview}{email_part} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class PartnerInterest(models.Model):
    """Model to store partner interest from 'Partner with Holou' section"""
    
    email = models.EmailField(db_index=True)
    company_name = models.CharField(max_length=200, blank=True, null=True)
    name = models.CharField(max_length=200, blank=True, null=True)
    message = models.TextField(blank=True, null=True, help_text="Optional message from partner")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Session ID to link back to user session
    session_key = models.CharField(max_length=100, blank=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Partner Interest'
        verbose_name_plural = 'Partner Interests'
    
    def __str__(self):
        name_part = f"{self.name} - " if self.name else ""
        company_part = f"{self.company_name} - " if self.company_name else ""
        return f"{name_part}{company_part}{self.email} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"