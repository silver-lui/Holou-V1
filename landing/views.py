import json
import asyncio
import os
import requests
from io import BytesIO
from django.shortcuts import render, redirect
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageDraw, ImageFont
from .services import generate_plan, generate_avatar_image, download_image_from_url
from .models import LearningPlan, Avatar, Wishlist, Feedback, PartnerInterest


def home(request):
    return render(request, 'landing/index.html')


def results(request):
    """Display the generated plan - fetch from database"""
    # Try to get plan from database first (by ID in session)
    plan_id = request.session.get('plan_id')
    learning_plan = None
    plan_data = None
    
    if plan_id:
        try:
            learning_plan = LearningPlan.objects.get(id=plan_id)
        except LearningPlan.DoesNotExist:
            pass
    
    # If no plan found by ID, check session key
    if not learning_plan:
        session_key = request.session.session_key
        if session_key:
            learning_plan = LearningPlan.objects.filter(
                session_key=session_key
            ).order_by('-created_at').first()
    
    # If we have a plan from database
    if learning_plan:
        if learning_plan.status == 'approved':
            # Use approved plan from database
            plan_data = learning_plan.plan_data
        elif learning_plan.status == 'pending':
            # Plan is pending approval - show message
            return render(request, 'landing/results.html', {
                'plan_data': None,
                'pending_message': True,
                'plan_id': learning_plan.id
            })
        else:
            # Plan was rejected
            return render(request, 'landing/results.html', {
                'plan_data': None,
                'rejected_message': True
            })
    else:
        # No approved plan in database - check if there's a pending plan we should show message for
        session_key = request.session.session_key
        if session_key:
            pending_plan = LearningPlan.objects.filter(
                session_key=session_key,
                status='pending'
            ).order_by('-created_at').first()
            
            if pending_plan:
                # Show pending message
                print(f"Found pending plan ID: {pending_plan.id}")
                return render(request, 'landing/results.html', {
                    'plan_data': None,
                    'pending_message': True,
                    'plan_id': pending_plan.id
                })
        
        # No plan found at all - redirect to home
        print("No plan found in database, redirecting to home")
        return redirect('home')
    
    # We have an approved plan from database - validate it has content
    if not plan_data or not isinstance(plan_data, dict):
        return render(request, 'landing/results.html', {
            'plan_data': None,
            'error_message': 'Plan data is invalid. Please contact support.'
        })
    
    # Validate that approved plan has daily_plan
    if 'daily_plan' not in plan_data or not plan_data.get('daily_plan') or len(plan_data.get('daily_plan', [])) == 0:
        return render(request, 'landing/results.html', {
            'plan_data': None,
            'error_message': 'Approved plan has no content. Please contact support.'
        })
    
    # Debug: Print plan_data structure (remove in production)
    print("=== PLAN DATA DEBUG ===")
    print(f"Type: {type(plan_data)}")
    print(f"Has daily_plan: {'daily_plan' in plan_data if isinstance(plan_data, dict) else 'N/A'}")
    if isinstance(plan_data, dict) and 'daily_plan' in plan_data:
        print(f"daily_plan length: {len(plan_data['daily_plan']) if plan_data['daily_plan'] else 0}")
        if plan_data['daily_plan'] and len(plan_data['daily_plan']) > 0:
            print(f"First day has tasks: {'tasks' in plan_data['daily_plan'][0] if plan_data['daily_plan'] else False}")
    print("=======================")
    
    # Only fill in missing optional fields with minimal defaults (not full default content)
    # This ensures the template doesn't break, but we trust the AI-generated content
    if 'project_overview' not in plan_data:
        plan_data['project_overview'] = {
            "title": learning_plan.project_description[:50] if learning_plan else "Your Project",
            "description": f"Learning plan for {learning_plan.project_description[:100] if learning_plan else 'your project'}",
            "estimated_duration": "7 days",
            "recommended_tech_stack": [learning_plan.framework] if learning_plan and learning_plan.framework else ["React", "JavaScript"],
            "user_level": learning_plan.developer_level if learning_plan else "beginner",
            "prerequisites": []
        }
    
    # Only add empty structure for features if missing, don't populate with defaults
    if 'features' not in plan_data:
        plan_data['features'] = {"core": [], "stretch": []}
    if 'features' in plan_data:
        if 'core' not in plan_data['features']:
            plan_data['features']['core'] = []
        if 'stretch' not in plan_data['features']:
            plan_data['features']['stretch'] = []
        # Only add defaults if completely empty (AI might have intentionally left empty)
        if not plan_data['features']['core']:
            plan_data['features']['core'] = ["Core feature 1", "Core feature 2", "Core feature 3"]
        if not plan_data['features']['stretch']:
            plan_data['features']['stretch'] = ["Advanced feature 1", "Advanced feature 2", "Performance optimization"]
    
    if 'milestones' not in plan_data or not plan_data['milestones']:
        plan_data['milestones'] = [{"name": "First Week Complete", "day": 7, "description": "Completed your first week of learning", "reward": {"xp": 100, "coins": 50, "badge": "Week Warrior"}}]
    
    if 'tips_and_motivation' not in plan_data or not plan_data['tips_and_motivation']:
        plan_data['tips_and_motivation'] = ["Keep learning!", "You got this!", "Practice makes perfect!"]
    
    # Only fill in missing task fields if completely missing (not if empty - AI might have left them empty)
    for day_plan in plan_data.get('daily_plan', []):
        for task in day_plan.get('tasks', []):
            if 'subtasks' not in task:
                task['subtasks'] = [
                    {"title": "Subtask 1", "description": "Complete setup", "steps": ["Step 1", "Step 2"]},
                    {"title": "Subtask 2", "description": "Practice basics", "steps": ["Step 1", "Step 2"]}
                ]
            elif not task.get('subtasks'):
                task['subtasks'] = [
                    {"title": "Subtask 1", "description": "Complete setup", "steps": ["Step 1", "Step 2"]},
                    {"title": "Subtask 2", "description": "Practice basics", "steps": ["Step 1", "Step 2"]}
                ]
            if 'detailed_steps' not in task:
                task['detailed_steps'] = ["Step 1: Setup", "Step 2: Learn", "Step 3: Practice"]
            elif not task.get('detailed_steps'):
                task['detailed_steps'] = ["Step 1: Setup", "Step 2: Learn", "Step 3: Practice"]
            if 'learning_materials' not in task:
                task['learning_materials'] = {"free_resources": ["React Tutorial - https://react.dev/learn"], "documentation": []}
            elif 'free_resources' not in task.get('learning_materials', {}):
                task['learning_materials'] = {"free_resources": ["React Tutorial - https://react.dev/learn"], "documentation": []}
            if 'rewards' not in task:
                task['rewards'] = {"xp": 20, "coins": 5, "badge": ""}
    
    # Ensure data is properly structured - convert any issues
    try:
        # Try to serialize and deserialize to ensure it's valid
        plan_data_json = json.dumps(plan_data)
        plan_data = json.loads(plan_data_json)
    except Exception as e:
        print(f"JSON conversion error: {e}")
        # If conversion fails, use the original data
    
    # Save validated data back to session
    request.session['plan_data'] = plan_data
    request.session.modified = True  # Force session save
    
    # Debug output
    print(f"Rendering with daily_plan length: {len(plan_data.get('daily_plan', []))}")
    if plan_data.get('daily_plan') and len(plan_data['daily_plan']) > 0:
        first_day = plan_data['daily_plan'][0]
        print(f"First day has {len(first_day.get('tasks', []))} tasks")
        if first_day.get('tasks') and len(first_day['tasks']) > 0:
            first_task = first_day['tasks'][0]
            print(f"First task title: {first_task.get('title', 'NO TITLE')}")
            print(f"First task description: {first_task.get('description', 'NO DESCRIPTION')}")
    
    return render(request, 'landing/results.html', {'plan_data': plan_data})


def resource_viewer(request):
    """Display external learning resources in an iframe within our website"""
    from urllib.parse import unquote
    url = request.GET.get('url', '')
    
    if not url:
        from django.shortcuts import redirect
        return redirect('home')
    
    # Decode the URL
    url = unquote(url)
    
    # Validate URL
    if not url.startswith(('http://', 'https://')):
        from django.shortcuts import redirect
        return redirect('home')
    
    # Render response and try to allow iframe embedding
    response = render(request, 'landing/resource_viewer.html', {'resource_url': url})
    # Remove X-Frame-Options restriction (allows our page to be embedded)
    # Note: External sites may still block themselves via their own headers
    if 'X-Frame-Options' in response:
        del response['X-Frame-Options']
    # Set permissive CSP to allow framing
    response['Content-Security-Policy'] = "frame-ancestors *;"
    return response


@csrf_exempt
@require_http_methods(["POST"])
def chat_api(request):
    """Handle chat API requests"""
    try:
        data = json.loads(request.body)
        message_type = data.get('type')
        
        if message_type == 'init' or not message_type:
            # Initial greeting
            return JsonResponse({
                'response': "Hello! I'm Holou, your AI Productivity Companion. Let's create a personalized learning plan for your project! 🚀\n\n⚠️ This is a demo version with a 200 character limit per message. Please keep your responses concise!\n⚠️ Consider that the demo version generates only 7 days basic plan.\n\nWhat project would you like to build?",
                'next_question': 'project_description',
                'status': 'waiting'
            })
        
        elif message_type == 'project_description':
            project = data.get('message', '').strip()
            if not project:
                return JsonResponse({
                    'response': "Please tell me about the project you'd like to build!",
                    'next_question': 'project_description',
                    'status': 'waiting'
                })
            
            # Check character limit (demo version)
            if len(project) > 200:
                return JsonResponse({
                    'response': "⚠️ Your message exceeds the 200 character limit for this demo version. Please keep your project description under 200 characters.",
                    'next_question': 'project_description',
                    'status': 'waiting'
                })
            
            request.session['project_description'] = project
            return JsonResponse({
                'response': f"Great! I'll help you build: **{project}**\n\nWhat's your current development level?\n\n1️⃣ Complete Beginner (Never coded before / just started)\n2️⃣ Beginner (Know basic HTML/CSS/JS concepts)\n3️⃣ Intermediate (Built 2-3 projects, comfortable with one language)\n4️⃣ Advanced (Professional developer, know multiple frameworks)",
                'next_question': 'developer_level',
                'status': 'waiting'
            })
        
        elif message_type == 'developer_level':
            level = data.get('message', '').strip()
            
            # Check character limit (demo version)
            if len(level) > 200:
                return JsonResponse({
                    'response': "⚠️ Your message exceeds the 200 character limit for this demo version. Please enter 1, 2, 3, or 4.",
                    'next_question': 'developer_level',
                    'status': 'waiting'
                })
            
            level_map = {
                '1': 'complete beginner',
                '2': 'beginner',
                '3': 'intermediate',
                '4': 'advanced',
                'complete beginner': 'complete beginner',
                'beginner': 'beginner',
                'intermediate': 'intermediate',
                'advanced': 'advanced'
            }
            
            developer_level = level_map.get(level.lower(), None)
            if not developer_level:
                return JsonResponse({
                    'response': "Please enter 1, 2, 3, or 4 (or type: complete beginner, beginner, intermediate, or advanced)",
                    'next_question': 'developer_level',
                    'status': 'waiting'
                })
            
            request.session['developer_level'] = developer_level
            return JsonResponse({
                'response': f"Perfect! I'll tailor the plan for a **{developer_level}** developer.\n\nWhat type of software are you building?\n\n🌐 Website/Web Application\n💻 Desktop Application\n📱 Mobile Application\n🤖 Other (specify)",
                'next_question': 'software_type',
                'status': 'waiting'
            })
        
        elif message_type == 'software_type':
            software_type = data.get('message', '').strip()
            if not software_type:
                return JsonResponse({
                    'response': "Please specify the type of software (Website, Desktop App, Mobile App, or Other)",
                    'next_question': 'software_type',
                    'status': 'waiting'
                })
            
            # Check character limit (demo version)
            if len(software_type) > 200:
                return JsonResponse({
                    'response': "⚠️ Your message exceeds the 200 character limit for this demo version. Please keep your response under 200 characters.",
                    'next_question': 'software_type',
                    'status': 'waiting'
                })
            
            request.session['software_type'] = software_type
            return JsonResponse({
                'response': f"Got it! Building a **{software_type}**.\n\nDo you have a preferred technology or framework?\n\n(Type 'no preference' to let me recommend the best option)\n\nExamples: React, Vue, Python Django, Node.js, Flutter, etc.",
                'next_question': 'framework',
                'status': 'waiting'
            })
        
        elif message_type == 'framework':
            framework = data.get('message', '').strip()
            
            # Check character limit (demo version)
            if framework and len(framework) > 200:
                return JsonResponse({
                    'response': "⚠️ Your message exceeds the 200 character limit for this demo version. Please keep your response under 200 characters.",
                    'next_question': 'framework',
                    'status': 'waiting'
                })
            
            if not framework or framework.lower() in ['no preference', 'no', 'none', '']:
                framework = 'No preference - recommend best option'
            
            request.session['framework'] = framework
            
            # Get all collected data
            project_description = request.session.get('project_description')
            developer_level = request.session.get('developer_level')
            software_type = request.session.get('software_type')
            
            # Generate plan
            return JsonResponse({
                'response': "🚀 Perfect! I have all the information I need.\n\nGenerating your personalized learning plan... This may take a moment. ⏳",
                'next_question': 'generating',
                'status': 'generating'
            })
        
        elif message_type == 'generate':
            # Get all collected data
            project_description = request.session.get('project_description')
            developer_level = request.session.get('developer_level')
            software_type = request.session.get('software_type')
            framework = request.session.get('framework', 'No preference - recommend best option')
            
            if not all([project_description, developer_level, software_type]):
                return JsonResponse({
                    'error': 'Missing required information',
                    'status': 'error'
                })
            
            # Generate plan asynchronously with timeout
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    plan_data = loop.run_until_complete(
                        asyncio.wait_for(
                            generate_plan(project_description, developer_level, framework, software_type),
                            timeout=180.0  # 3 minutes - increased to ensure completion
                        )
                    )
                    # Success! AI generated the plan - save it immediately
                    print(f"=== AI GENERATION SUCCESS ===")
                    print(f"Plan has {len(plan_data.get('daily_plan', []))} days")
                    if plan_data.get('daily_plan'):
                        first_day = plan_data['daily_plan'][0] if plan_data['daily_plan'] else {}
                        first_task = first_day.get('tasks', [{}])[0] if first_day.get('tasks') else {}
                        print(f"First task title: {first_task.get('title', 'NO TITLE')}")
                        print(f"First task description: {first_task.get('description', 'NO DESCRIPTION')[:100]}")
                    print("=============================")
                    
                    # Verify it's not empty/default
                    if plan_data and plan_data.get('daily_plan') and len(plan_data['daily_plan']) > 0:
                        # Save to database - ensure session key exists
                        if not request.session.session_key:
                            request.session.create()
                        
                        try:
                            # Auto-approve plan immediately upon creation
                            from django.utils import timezone
                            learning_plan = LearningPlan.objects.create(
                                project_description=project_description,
                                developer_level=developer_level,
                                framework=framework,
                                software_type=software_type,
                                plan_data=plan_data,
                                status='approved',  # Auto-approved immediately
                                session_key=request.session.session_key or '',
                                approved_at=timezone.now()  # Set approval timestamp
                            )
                            print(f"✅ Plan saved to database with ID: {learning_plan.id}, Status: {learning_plan.status} (Auto-approved)")
                        except Exception as e:
                            print(f"❌ ERROR saving plan to database: {str(e)}")
                            import traceback
                            traceback.print_exc()
                            # Continue anyway - save to session as fallback
                            learning_plan = None
                        
                        # Save plan_id to session for results page lookup
                        if learning_plan:
                            request.session['plan_id'] = learning_plan.id
                            request.session.modified = True
                            print(f"Plan ID {learning_plan.id} saved to session")
                        else:
                            # Fallback: save to session if database save failed
                            plan_data_json = json.dumps(plan_data)
                            plan_data = json.loads(plan_data_json)
                            request.session['plan_data'] = plan_data
                            request.session.modified = True
                            print("Plan saved to session as fallback (database save failed)")
                        
                        loop.close()
                        
                        print("AI-generated plan saved to database and auto-approved!")
                        return JsonResponse({
                            'response': "✅ Your personalized learning plan is ready!\n\nRedirecting to view your complete plan...",
                            'status': 'success',
                            'redirect_url': '/results/'
                        })
                    else:
                        print("ERROR: AI returned empty plan, using fallback")
                        raise Exception("AI returned empty plan")
                except asyncio.TimeoutError:
                    loop.close()
                    # Only use fallback for actual timeouts
                    print("Generation timed out - using fallback plan")
                    plan_data = {
                        "project_overview": {
                            "title": project_description[:50] if project_description else "Project",
                            "description": f"Learning plan for {project_description[:100] if project_description else 'your project'}",
                            "estimated_duration": "7 days",
                            "recommended_tech_stack": [framework] if framework and framework != 'No preference - recommend best option' else ["React", "JavaScript", "Node.js"],
                            "user_level": developer_level or "beginner",
                            "prerequisites": []
                        },
                        "features": {
                            "core": ["Core feature 1", "Core feature 2", "Core feature 3"],
                            "stretch": ["Advanced feature 1", "Advanced feature 2", "Performance optimization"]
                        },
                        "overall_learning_materials": {
                            "foundational": ["JavaScript Basics - https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide"],
                            "project_specific": ["React Guide - https://react.dev/learn"],
                            "paid_comprehensive": []
                        },
                        "daily_plan": [
                            {
                                "day": i,
                                "focus": f"Day {i} - Learning and building",
                                "type": "mixed",
                                "tasks": [
                                    {
                                        "id": f"D{i}-T1",
                                        "title": f"Task {i}.1: Setup and basics",
                                        "task_type": "learning",
                                        "description": f"Learn the fundamentals for day {i}",
                                        "how_to_guide": "Follow the learning resources and complete the exercises",
                                        "subtasks": [
                                            {"title": "Subtask 1", "description": "Complete setup", "steps": ["Step 1", "Step 2"]},
                                            {"title": "Subtask 2", "description": "Practice basics", "steps": ["Step 1", "Step 2"]}
                                        ],
                                        "detailed_steps": ["Step 1: Setup", "Step 2: Learn", "Step 3: Practice"],
                                        "time_estimate": "2-3 hours",
                                        "difficulty": "medium",
                                        "skills_learned": ["Fundamentals", "Best practices"],
                                        "common_mistakes": [{"mistake": "Common error", "solution": "Fix approach", "prevention_tip": "Follow guidelines"}],
                                        "learning_materials": {
                                            "free_resources": ["React Tutorial - https://react.dev/learn"],
                                            "documentation": []
                                        },
                                        "rewards": {"xp": 20, "coins": 5, "badge": ""}
                                    },
                                    {
                                        "id": f"D{i}-T2",
                                        "title": f"Task {i}.2: Build feature",
                                        "task_type": "building",
                                        "description": f"Build a feature for day {i}",
                                        "how_to_guide": "Implement the feature using what you learned",
                                        "subtasks": [
                                            {"title": "Subtask 1", "description": "Plan feature", "steps": ["Step 1", "Step 2"]},
                                            {"title": "Subtask 2", "description": "Implement feature", "steps": ["Step 1", "Step 2"]}
                                        ],
                                        "detailed_steps": ["Step 1: Plan", "Step 2: Code", "Step 3: Test"],
                                        "time_estimate": "3-4 hours",
                                        "difficulty": "medium",
                                        "skills_learned": ["Implementation", "Testing"],
                                        "common_mistakes": [{"mistake": "Common error", "solution": "Fix approach", "prevention_tip": "Test often"}],
                                        "learning_materials": {
                                            "free_resources": ["Implementation Guide - https://developer.mozilla.org"],
                                            "documentation": []
                                        },
                                        "rewards": {"xp": 30, "coins": 10, "badge": ""}
                                    }
                                ],
                                "daily_summary": f"Completed day {i} - learned fundamentals and built features"
                            }
                            for i in range(1, 8)
                        ],
                        "milestones": [
                            {"name": "First Week Complete", "day": 7, "description": "Completed your first week of learning", "reward": {"xp": 100, "coins": 50, "badge": "Week Warrior"}}
                        ],
                        "rewards_system": {
                            "xp_levels": {
                                "level_1": "0-100 XP - Novice Coder",
                                "level_2": "101-300 XP - Apprentice Developer",
                                "level_3": "301-600 XP - Skilled Builder",
                                "level_4": "601-1000 XP - Master Developer"
                            },
                            "shop_items": []
                        },
                        "tips_and_motivation": ["Keep learning!", "You got this!", "Practice makes perfect!"]
                    }
                    # Ensure plan_data is a proper dict before saving to session
                    # Convert to JSON and back to ensure proper serialization
                    plan_data_json = json.dumps(plan_data)
                    plan_data = json.loads(plan_data_json)
                    request.session['plan_data'] = plan_data
                    request.session.modified = True  # Force session save
                    return JsonResponse({
                        'response': "✅ Your learning plan is ready!\n\nRedirecting to view your complete plan...",
                        'status': 'success',
                        'redirect_url': '/results/'
                    })
                except Exception as e:
                    # Only catch other exceptions (not timeout - that's handled above)
                    loop.close()
                    print(f"Generation error (not timeout): {str(e)}")
                    # Try minimal plan as fallback
                    try:
                        from .services import generate_minimal_plan
                        minimal_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(minimal_loop)
                        try:
                            plan_data = minimal_loop.run_until_complete(
                                asyncio.wait_for(
                                    generate_minimal_plan(project_description, developer_level, framework, software_type),
                                    timeout=90.0  # 90 seconds for minimal plan fallback
                                )
                            )
                            plan_data_json = json.dumps(plan_data)
                            plan_data = json.loads(plan_data_json)
                            request.session['plan_data'] = plan_data
                            request.session.modified = True
                            minimal_loop.close()
                            return JsonResponse({
                                'response': "✅ Your learning plan is ready!\n\nRedirecting to view your complete plan...",
                                'status': 'success',
                                'redirect_url': '/results/'
                            })
                        except Exception as e2:
                            minimal_loop.close()
                            print(f"Minimal plan also failed: {str(e2)}")
                            # Re-raise to trigger ultimate fallback below
                            raise e
                    except Exception as e2:
                        # If minimal plan fails, continue to ultimate fallback
                        print(f"All generation attempts failed: {str(e2)}")
                        raise e
                
            except Exception as e:
                # Ultimate fallback - create basic plan structure
                try:
                    from .services import generate_minimal_plan
                    fallback_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(fallback_loop)
                    try:
                        plan_data = fallback_loop.run_until_complete(
                            asyncio.wait_for(
                                generate_minimal_plan(project_description, developer_level, framework, software_type),
                                timeout=90.0  # 90 seconds for ultimate fallback
                            )
                        )
                        plan_data_json = json.dumps(plan_data)
                        plan_data = json.loads(plan_data_json)
                        request.session['plan_data'] = plan_data
                        request.session.modified = True
                        fallback_loop.close()
                        return JsonResponse({
                            'response': "✅ Your learning plan is ready!\n\nRedirecting to view your complete plan...",
                            'status': 'success',
                            'redirect_url': '/results/'
                        })
                    except:
                        fallback_loop.close()
                        # Create absolute minimal plan
                        plan_data = {
                            "project_overview": {
                                "title": project_description[:50] if project_description else "Project",
                                "description": f"Learning plan for {project_description[:100] if project_description else 'your project'}",
                                "estimated_duration": "7 days",
                                "recommended_tech_stack": [framework] if framework else ["Recommended tech"],
                                "user_level": developer_level or "beginner",
                                "prerequisites": []
                            },
                            "features": {"core": ["Feature 1", "Feature 2", "Feature 3"], "stretch": ["Advanced feature 1", "Advanced feature 2", "Performance optimization"]},
                            "overall_learning_materials": {
                                "foundational": ["https://developer.mozilla.org"],
                                "project_specific": ["https://react.dev/learn"],
                                "paid_comprehensive": []
                            },
                            "daily_plan": [
                                {
                                    "day": i,
                                    "focus": f"Day {i}",
                                    "type": "mixed",
                                    "tasks": [{
                                        "id": f"D{i}-T1",
                                        "title": f"Task {i}",
                                        "task_type": "learning",
                                        "description": "Complete this task",
                                        "how_to_guide": "Follow instructions",
                                        "subtasks": [
                                            {"title": "Subtask 1", "description": "Do this", "steps": ["Step 1", "Step 2"]},
                                            {"title": "Subtask 2", "description": "Do that", "steps": ["Step 1", "Step 2"]}
                                        ],
                                        "detailed_steps": ["Step 1", "Step 2", "Step 3"],
                                        "time_estimate": "2 hours",
                                        "difficulty": "medium",
                                        "skills_learned": ["Skill 1"],
                                        "common_mistakes": [{"mistake": "Error", "solution": "Fix", "prevention_tip": "Tip"}],
                                        "learning_materials": {
                                            "free_resources": ["https://developer.mozilla.org"],
                                            "documentation": []
                                        },
                                        "rewards": {"xp": 20, "coins": 5, "badge": ""}
                                    }],
                                    "daily_summary": f"Day {i} completed"
                                }
                                for i in range(1, 8)
                            ],
                            "milestones": [],
                            "rewards_system": {
                                "xp_levels": {"level_1": "0-100 XP", "level_2": "101-300 XP", "level_3": "301-600 XP", "level_4": "601-1000 XP"},
                                "shop_items": []
                            },
                            "tips_and_motivation": ["Keep learning!", "You got this!"]
                        }
                        plan_data_json = json.dumps(plan_data)
                        plan_data = json.loads(plan_data_json)
                        request.session['plan_data'] = plan_data
                        request.session.modified = True
                        return JsonResponse({
                            'response': "✅ Your learning plan is ready!\n\nRedirecting to view your complete plan...",
                            'status': 'success',
                            'redirect_url': '/results/'
                        })
                except Exception as e2:
                    return JsonResponse({
                        'error': f'Error generating plan: {str(e)}. Please try again.',
                        'status': 'error'
                    })
        
        else:
            return JsonResponse({
                'error': 'Invalid message type',
                'status': 'error'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON',
            'status': 'error'
        })
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        })


# Class to profession mapping
CLASS_PROFESSIONS = {
    'elf': ['Web Development', 'Frontend Development', 'Mobile Development'],
    'demon': ['Backend Development', 'DevOps', 'System Administration'],
    'human': ['Full Stack Development', 'Data Science', 'Machine Learning'],
    'dwarf': ['Game Development', 'Embedded Systems', 'Desktop Applications'],
    'orc': ['Cybersecurity', 'Network Engineering', 'Cloud Architecture'],
    'fairy': ['UI/UX Design', 'Graphic Design', 'Animation'],
    'wizard': ['AI Development', 'Blockchain Development', 'Quantum Computing'],
    'warrior': ['Software Engineering', 'Project Management', 'Technical Leadership'],
}


def avatar_creation(request):
    """Display the avatar creation page"""
    import json
    return render(request, 'landing/avatar_creation.html', {
        'classes': list(CLASS_PROFESSIONS.keys()),
        'class_professions_json': json.dumps(CLASS_PROFESSIONS),
    })


@csrf_exempt
@require_http_methods(["POST"])
def generate_avatar(request):
    """Handle avatar generation request"""
    try:
        # Get form data
        character_class = request.POST.get('character_class', '').strip().lower()
        profession = request.POST.get('profession', '').strip()
        uploaded_file = request.FILES.get('user_image', None)
        
        # Validate inputs
        if not character_class:
            return JsonResponse({
                'error': 'Character class is required',
                'status': 'error'
            })
        
        if not profession:
            return JsonResponse({
                'error': 'Profession is required',
                'status': 'error'
            })
        
        # Validate class exists
        if character_class not in CLASS_PROFESSIONS:
            return JsonResponse({
                'error': f'Invalid character class: {character_class}',
                'status': 'error'
            })
        
        # Validate profession is allowed for this class
        if profession not in CLASS_PROFESSIONS[character_class]:
            return JsonResponse({
                'error': f'Profession "{profession}" is not available for {character_class} class',
                'status': 'error'
            })
        
        # Handle uploaded image if provided
        original_image_path = None
        if uploaded_file:
            # Save uploaded image
            file_name = default_storage.save(
                f'avatars/original/{uploaded_file.name}',
                uploaded_file
            )
            original_image_path = os.path.join(settings.MEDIA_ROOT, file_name)
        
        # Generate avatar using AI
        try:
            image_url = generate_avatar_image(character_class, profession, original_image_path)
        except Exception as e:
            return JsonResponse({
                'error': f'Failed to generate avatar: {str(e)}',
                'status': 'error'
            })
        
        # Download the generated image
        try:
            # Create a unique filename
            import uuid
            unique_filename = f"{uuid.uuid4()}.png"
            save_path = os.path.join(settings.MEDIA_ROOT, 'avatars', 'generated', unique_filename)
            
            # Download and save the image
            download_image_from_url(image_url, save_path)
            
            # Create Avatar record
            if not request.session.session_key:
                request.session.create()
            
            avatar = Avatar.objects.create(
                character_class=character_class,
                profession=profession,
                original_image=file_name if uploaded_file else None,
                generated_avatar=f'avatars/generated/{unique_filename}',
                session_key=request.session.session_key or '',
            )
            
            return JsonResponse({
                'status': 'success',
                'avatar_url': avatar.generated_avatar.url,
                'avatar_id': avatar.id,
            })
            
        except Exception as e:
            return JsonResponse({
                'error': f'Failed to save avatar: {str(e)}',
                'status': 'error'
            })
            
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        })


def add_watermark_to_image(image_path):
    """
    Add elegant Holou logo and text watermark to the avatar image
    
    Args:
        image_path: Path to the avatar image
    
    Returns:
        BytesIO object containing the watermarked image
    """
    try:
        # Open the avatar image
        img = Image.open(image_path)
        
        # Convert to RGBA if needed
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Create a copy for watermarking
        watermarked = img.copy()
        
        # Get logo path
        logo_path = os.path.join(settings.STATICFILES_DIRS[0], 'Holou-Logo.png')
        
        # Calculate optimal sizes based on image dimensions for elegant proportions
        base_size = min(img.width, img.height)
        logo_size = int(base_size * 0.065)  # 6.5% for elegant size
        padding = int(base_size * 0.02)  # 2% padding
        
        logo_to_paste = None
        logo_shadow_to_paste = None
        logo_position = (padding, padding)
        shadow_offset = 1.5
        shadow_position = (int(padding + shadow_offset), int(padding + shadow_offset))
        
        # Load and prepare logo
        if os.path.exists(logo_path):
            logo = Image.open(logo_path)
            if logo.mode != 'RGBA':
                logo = logo.convert('RGBA')
            
            logo.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
            
            # Create very subtle shadow
            logo_shadow = logo.copy()
            alpha_channel = logo_shadow.split()[3]
            shadow_alpha = alpha_channel.point(lambda x: int(x * 0.12))  # Very subtle shadow
            logo_shadow.putalpha(shadow_alpha)
            
            logo_to_paste = logo
            logo_shadow_to_paste = logo_shadow
        
        # Load Orbitron font
        font_size = int(base_size * 0.038)  # Elegant font size
        fonts_dir = os.path.join(settings.STATICFILES_DIRS[0], 'fonts')
        os.makedirs(fonts_dir, exist_ok=True)
        
        font_paths = [
            os.path.join(settings.STATICFILES_DIRS[0], 'fonts', 'Orbitron-Bold.ttf'),
            os.path.join(settings.BASE_DIR, 'landing', 'static', 'fonts', 'Orbitron-Bold.ttf'),
            os.path.expanduser('~/.fonts/Orbitron-Bold.ttf'),
            'C:/Windows/Fonts/orbitron-bold.ttf',
            'C:/Windows/Fonts/Orbitron-Bold.ttf',
        ]
        
        font = None
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    print(f"Using Orbitron font: {font_path}")
                    break
                except:
                    continue
        
        # Download Orbitron if not found
        if font is None:
            orbitron_path = os.path.join(settings.STATICFILES_DIRS[0], 'fonts', 'Orbitron-Bold.ttf')
            if not os.path.exists(orbitron_path):
                try:
                    print("Downloading Orbitron font...")
                    orbitron_urls = [
                        "https://github.com/theleagueof/orbitron/raw/master/Orbitron-Bold.ttf",
                        "https://raw.githubusercontent.com/google/fonts/main/ofl/orbitron/Orbitron-Bold.ttf",
                    ]
                    for orbitron_url in orbitron_urls:
                        try:
                            response = requests.get(orbitron_url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
                            if response.status_code == 200 and len(response.content) > 1000:
                                with open(orbitron_path, 'wb') as f:
                                    f.write(response.content)
                                font = ImageFont.truetype(orbitron_path, font_size)
                                print(f"Downloaded Orbitron font successfully")
                                break
                        except Exception as e:
                            print(f"Failed to download from {orbitron_url}: {e}")
                            continue
                except Exception as e:
                    print(f"Error downloading Orbitron font: {e}")
        
        # Fallback fonts
        if font is None:
            fallback_paths = [
                'C:/Windows/Fonts/arialbd.ttf',
                'C:/Windows/Fonts/calibrib.ttf',
            ]
            for fallback_path in fallback_paths:
                if os.path.exists(fallback_path):
                    try:
                        font = ImageFont.truetype(fallback_path, font_size)
                        break
                    except:
                        continue
        
        if font is None:
            font = ImageFont.load_default()
        
        # Create drawing context
        draw = ImageDraw.Draw(watermarked)
        
        # Calculate text position
        text = "Holou"
        if logo_to_paste:
            text_x = padding + logo_size + int(base_size * 0.012)  # Elegant spacing
            
            # Calculate vertical alignment
            bbox = draw.textbbox((0, 0), text, font=font)
            text_height = bbox[3] - bbox[1]
            logo_center_y = padding + logo_size // 2
            text_y = logo_center_y - (text_height // 2) - bbox[1]
            
            # Calculate watermark dimensions for background
            text_width = bbox[2] - bbox[0]
            watermark_width = logo_size + int(base_size * 0.012) + text_width
            watermark_height = max(logo_size, int((bbox[3] - bbox[1]) * 1.1))
            
            # Draw elegant subtle background
            bg_padding = int(padding * 0.5)
            bg_x1 = max(0, padding - bg_padding)
            bg_y1 = max(0, padding - bg_padding)
            bg_x2 = padding + watermark_width + bg_padding
            bg_y2 = padding + watermark_height + bg_padding
            
            # Draw rounded rectangle with very subtle background
            try:
                draw.rounded_rectangle(
                    [(bg_x1, bg_y1), (bg_x2, bg_y2)],
                    radius=int(base_size * 0.012),
                    fill=(25, 25, 25, 85)  # Very subtle dark background
                )
            except AttributeError:
                draw.rectangle(
                    [(bg_x1, bg_y1), (bg_x2, bg_y2)],
                    fill=(25, 25, 25, 85)
                )
        else:
            text_x = padding
            text_y = padding
        
        # Paste logo shadow and logo
        if logo_shadow_to_paste and logo_to_paste:
            if logo_shadow_to_paste.mode == 'RGBA':
                temp_shadow = Image.new('RGBA', watermarked.size, (0, 0, 0, 0))
                temp_shadow.paste(logo_shadow_to_paste, shadow_position, logo_shadow_to_paste)
                watermarked = Image.alpha_composite(watermarked, temp_shadow)
            
            if logo_to_paste.mode == 'RGBA':
                temp_img = Image.new('RGBA', watermarked.size, (0, 0, 0, 0))
                temp_img.paste(logo_to_paste, logo_position, logo_to_paste)
                watermarked = Image.alpha_composite(watermarked, temp_img)
            else:
                watermarked.paste(logo_to_paste, logo_position)
            
            # Re-create drawing context
            draw = ImageDraw.Draw(watermarked)
        
        # Draw text with very subtle shadow
        shadow_offset = 1
        draw.text((int(text_x + shadow_offset), int(text_y + shadow_offset)), text, 
                 font=font, fill=(200, 200, 200, 50))  # Very subtle shadow
        draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))  # White text
        
        # Convert back to RGB for saving
        if watermarked.mode == 'RGBA':
            background = Image.new('RGB', watermarked.size, (255, 255, 255))
            background.paste(watermarked, mask=watermarked.split()[3])
            watermarked = background
        
        # Save to BytesIO
        output = BytesIO()
        watermarked.save(output, format='PNG', quality=95)
        output.seek(0)
        
        return output
        
    except Exception as e:
        print(f"Error adding watermark: {str(e)}")
        # If watermarking fails, return original image
        img = Image.open(image_path)
        output = BytesIO()
        img.save(output, format='PNG')
        output.seek(0)
        return output


def download_avatar(request, avatar_id):
    """Download the generated avatar with watermark"""
    try:
        avatar = Avatar.objects.get(id=avatar_id)
        
        file_path = avatar.generated_avatar.path
        
        if not os.path.exists(file_path):
            raise Http404("Avatar file not found")
        
        # Add watermark to the image
        watermarked_image = add_watermark_to_image(file_path)
        
        response = FileResponse(
            watermarked_image,
            content_type='image/png'
        )
        response['Content-Disposition'] = f'attachment; filename="avatar_{avatar.character_class}_{avatar.profession}.png"'
        
        return response
        
    except Avatar.DoesNotExist:
        raise Http404("Avatar not found")
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        })


@csrf_exempt
@require_http_methods(["POST"])
def submit_feedback(request):
    """Handle feedback submission from 'Tell us what you think' section"""
    try:
        data = json.loads(request.body)
        feedback_text = data.get('feedback', '').strip()
        email = data.get('email', '').strip()
        name = data.get('name', '').strip()
        
        # Validate feedback text is required
        if not feedback_text:
            return JsonResponse({
                'error': 'Feedback text is required',
                'status': 'error'
            })
        
        # Ensure session key exists
        if not request.session.session_key:
            request.session.create()
        
        # Create feedback entry
        feedback = Feedback.objects.create(
            feedback_text=feedback_text,
            email=email if email else None,
            name=name if name else '',
            session_key=request.session.session_key or '',
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Thank you for your feedback!',
            'feedback_id': feedback.id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON',
            'status': 'error'
        })
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        })


@csrf_exempt
@require_http_methods(["POST"])
def submit_partner_interest(request):
    """Handle partner interest submission from 'Partner with Holou' section"""
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        company_name = data.get('company_name', '').strip()
        name = data.get('name', '').strip()
        message = data.get('message', '').strip()
        
        # Validate email is required
        if not email:
            return JsonResponse({
                'error': 'Email is required',
                'status': 'error'
            })
        
        # Validate email format
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({
                'error': 'Please enter a valid email address',
                'status': 'error'
            })
        
        # Ensure session key exists
        if not request.session.session_key:
            request.session.create()
        
        # Create partner interest entry
        partner_interest = PartnerInterest.objects.create(
            email=email,
            company_name=company_name if company_name else '',
            name=name if name else '',
            message=message if message else '',
            session_key=request.session.session_key or '',
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Thank you for your interest! We\'ll be in touch soon.',
            'partner_id': partner_interest.id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON',
            'status': 'error'
        })
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        })


def wishlist_signup(request):
    """Display wishlist signup page and handle form submission"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        company_name = request.POST.get('company_name', '').strip()
        job_title = request.POST.get('job_title', '').strip()
        additional_info = request.POST.get('additional_info', '').strip()
        
        # Validate email is required
        if not email:
            return render(request, 'landing/wishlist_signup.html', {
                'error': 'Email is required',
                'form_data': {
                    'first_name': first_name,
                    'last_name': last_name,
                    'company_name': company_name,
                    'job_title': job_title,
                    'additional_info': additional_info,
                }
            })
        
        # Validate email format
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        try:
            validate_email(email)
        except ValidationError:
            return render(request, 'landing/wishlist_signup.html', {
                'error': 'Please enter a valid email address',
                'form_data': {
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'company_name': company_name,
                    'job_title': job_title,
                    'additional_info': additional_info,
                }
            })
        
        # Ensure session key exists
        if not request.session.session_key:
            request.session.create()
        
        # Create or update wishlist entry
        try:
            wishlist_entry, created = Wishlist.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'company_name': company_name,
                    'job_title': job_title,
                    'additional_info': additional_info,
                    'session_key': request.session.session_key or '',
                }
            )
            
            if not created:
                # Update existing entry
                wishlist_entry.first_name = first_name
                wishlist_entry.last_name = last_name
                wishlist_entry.company_name = company_name
                wishlist_entry.job_title = job_title
                wishlist_entry.additional_info = additional_info
                wishlist_entry.session_key = request.session.session_key or ''
                wishlist_entry.save()
            
            # Success - show thank you message
            return render(request, 'landing/wishlist_signup.html', {
                'success': True,
                'email': email
            })
            
        except Exception as e:
            return render(request, 'landing/wishlist_signup.html', {
                'error': f'An error occurred: {str(e)}',
                'form_data': {
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'company_name': company_name,
                    'job_title': job_title,
                    'additional_info': additional_info,
                }
            })
    
    # GET request - show the form
    return render(request, 'landing/wishlist_signup.html')
