from django import template
import re

register = template.Library()

@register.filter
def extract_url(resource_string):
    """Extract URL from resource string (format: 'Title - https://url.com')"""
    if not resource_string:
        return ''
    
    # Find URL pattern (http:// or https://)
    url_pattern = r'https?://[^\s]+'
    match = re.search(url_pattern, resource_string)
    if match:
        return match.group(0)
    
    # If no URL found but string contains http, return the whole string
    if 'http' in resource_string:
        return resource_string
    
    return ''

@register.filter
def extract_title(resource_string):
    """Extract title from resource string (format: 'Title - https://url.com')"""
    if not resource_string:
        return resource_string
    
    # Split by ' - ' and take the first part
    if ' - ' in resource_string:
        parts = resource_string.split(' - ', 1)
        return parts[0]
    
    # If no separator, try to remove URL
    url_pattern = r'https?://[^\s]+'
    title = re.sub(url_pattern, '', resource_string).strip()
    return title if title else resource_string
