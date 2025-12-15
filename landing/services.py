import asyncio
import json
import re
import os
import base64
import requests
from agents import Agent, Runner
from django.conf import settings
from openai import OpenAI

# Set OpenAI API Key
os.environ["OPENAI_API_KEY"] = "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"


def extract_json_from_text(text):
    """Extract JSON from text that might contain markdown or extra content"""
    if not text:
        return "{}"
    
    # Try to find JSON in code blocks first
    json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        return match.group(1)
    
    # Try to find JSON object by finding the first { and matching braces
    # This is more robust for nested JSON
    start_idx = text.find('{')
    if start_idx == -1:
        return text
    
    # Count braces to find the matching closing brace
    brace_count = 0
    in_string = False
    escape_next = False
    
    for i in range(start_idx, len(text)):
        char = text[i]
        
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        
        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    # Found matching closing brace
                    return text[start_idx:i+1]
    
    # If we couldn't find matching brace, try simpler approach
    # Find the last } after the first {
    end_idx = text.rfind('}')
    if end_idx > start_idx:
        return text[start_idx:end_idx+1]
    
    return text


def create_atlas_agent():
    """Create the Atlas AI agent with enhanced instructions"""
    return Agent(
        name="Atlas",
        instructions="""You are an expert coding mentor. Generate a REAL, personalized learning plan.

CRITICAL REQUIREMENTS:
1. Use the ACTUAL project description provided - reference it in your tasks
2. Make tasks SPECIFIC to that project - use the project name and details
3. Generate REAL content, not generic placeholders like "Task 1.1: Setup and basics"
4. Include project-specific learning resources
5. Make task descriptions reference the actual project

Return ONLY valid JSON. Be concise but include real, project-specific content.

JSON: Properly escaped, no trailing commas.

STRUCTURE:
{
  "project_overview": {
    "title": "Project name",
    "description": "Brief project description",
    "estimated_duration": "X days (full plan duration - can be 14+ days, but only show first 7 days in daily_plan)",
    "recommended_tech_stack": ["tech1", "tech2", "tech3"],
    "user_level": "complete beginner/beginner/intermediate/advanced",
    "prerequisites": ["What they need to learn first - ONLY for complete beginners"]
  },
  "features": {
    "core": ["Feature 1", "Feature 2", "Feature 3"],
    "stretch": ["Advanced feature 1", "Advanced feature 2", "Performance optimization"]
  },
  "overall_learning_materials": {
    "foundational": [
      "JavaScript Basics - https://www.freecodecamp.org/learn/programming-with-javascript/"
    ],
    "project_specific": [
      "React Guide - https://react.dev/learn"
    ],
    "paid_comprehensive": [
      "Web Dev Bootcamp - https://www.udemy.com/course/the-web-developer-bootcamp/"
    ]
  },
  "daily_plan": [
    {
      "day": 1,
      "focus": "Clear theme for the day",
      "type": "learning/building/mixed",
      "tasks": [
        {
          "id": "D1-T1",
          "title": "Specific, actionable task title",
          "task_type": "learning/building/practice/review",
          "description": "Brief description of task",
          "how_to_guide": "Short step-by-step guide",
          "subtasks": [
            {"title": "Subtask 1", "description": "Brief", "steps": ["Step 1", "Step 2"]},
            {"title": "Subtask 2", "description": "Brief", "steps": ["Step 1", "Step 2"]}
          ],
          "detailed_steps": ["Step 1", "Step 2", "Step 3"],
          "time_estimate": "X hours",
          "difficulty": "easy/medium/hard",
          "skills_learned": [
            "Specific skill 1 they'll master",
            "Specific skill 2"
          ],
          "common_mistakes": [{"mistake": "Mistake", "solution": "Fix", "prevention_tip": "Tip"}],
          "learning_materials": {
            "free_resources": ["React Tutorial - https://react.dev/learn"],
            "documentation": ["React Docs - https://react.dev/learn"]
          },
          "rewards": {
            "xp": 20,
            "coins": 5,
            "badge": "Badge name if milestone task"
          }
        }
      ],
      "daily_summary": "Day summary"
    }
  ],
  "milestones": [
    {
      "name": "Milestone Name",
      "day": 3,
      "description": "Milestone description",
      "reward": {
        "xp": 100,
        "coins": 50,
        "badge": "Achievement Badge Name"
      }
    }
  ],
  "rewards_system": {
    "xp_levels": {
      "level_1": "0-100 XP - Novice Coder",
      "level_2": "101-300 XP - Apprentice Developer",
      "level_3": "301-600 XP - Skilled Builder",
      "level_4": "601-1000 XP - Master Developer"
    },
    "shop_items": [
      {"item": "Extra hint for difficult task", "cost": 10},
      {"item": "Code review session", "cost": 50},
      {"item": "Skip one optional task", "cost": 30}
    ]
  },
  "tips_and_motivation": [
    "Practical success tip",
    "Encouragement message",
    "Learning advice"
  ]
}

RULES:
- Generate a COMPLETE plan (estimated_duration can be 14+ days for full plan)
- BUT daily_plan should contain ONLY the first 7 days
- estimated_duration should reflect the FULL plan duration (e.g., "14 days", "21 days")
- daily_plan should have exactly 7 days (first week only)
- 2 tasks per day
- 2 subtasks per task
- 1-2 resources per task
- CRITICAL: Make tasks SPECIFIC to the project - use the actual project description
- CRITICAL: Task titles should reference the project, not be generic like "Setup and basics"
- CRITICAL: Task descriptions should mention the project name/type
- Use the actual project name and details in task descriptions
- URLs: Use real URLs relevant to the project
- Format: "Title - Description - https://link.com"
- DO NOT use generic task names like "Task 1.1: Setup and basics" - make them project-specific
- Generate valid JSON with REAL, personalized content for the specific project.""",
        model="gpt-4o-mini",
    )


def create_quality_checker_agent():
    """Create the quality checker and improvement agent"""
    return Agent(
        name="QualityImprover",
        instructions="""You are a Quality Improver AI that reviews AND enhances coding curriculum plans.

Your job is to:
1. Check JSON structure and required fields
2. Ensure all learning resources have REAL URLs (no placeholders)
3. Validate task breakdown for skill level
4. Check common mistakes, subtasks, and how-to guides
5. CRITICAL: Verify daily_plan length matches estimated_duration
6. CRITICAL: Verify EVERY task has subtasks (2-5) - MANDATORY

IMPROVEMENT ACTIONS:
- Fix missing/placeholder links with real URLs
- Add missing common mistakes and solutions
- Enhance how-to guides with specific instructions
- Add missing subtasks for ALL tasks (not just complex ones)
- Fix duration mismatches - ensure daily_plan has exactly the number of days in estimated_duration

Return ONLY a JSON object with this structure:
{
  "is_valid": true/false,
  "quality_score": 0-100,
  "issues_found": [
    {
      "type": "missing_field|invalid_structure|missing_links|incomplete_task|duration_mismatch",
      "description": "What's wrong",
      "severity": "low|medium|high",
      "suggestion": "How to fix it"
    }
  ],
  "improvements": [
    "Specific improvement suggestions"
  ],
  "overall_feedback": "Overall assessment of the plan quality",
  "improved_plan": {
    // ENHANCED VERSION OF THE ORIGINAL PLAN
    // Fix all issues found and implement improvements
    // Use the same structure as the original but with fixes
    // CRITICAL: Ensure daily_plan length matches estimated_duration exactly
  }
}

Focus on:
- Completeness of required fields
- REAL URLs (no placeholders)
- Task breakdown for skill level
- Common mistakes, subtasks, how-to guides
- CRITICAL: daily_plan length matches estimated_duration exactly
- CRITICAL: EVERY task has subtasks (2-5) - MANDATORY

IMPROVEMENT PRIORITIES:
1. Fix duration mismatches - ensure daily_plan matches estimated_duration exactly
2. Fix missing/placeholder links with real URLs
3. Add missing common mistakes and solutions
4. Enhance how-to guides with specific commands
5. Add missing subtasks for ALL tasks (mandatory)""",
        model="gpt-4o-mini",
    )


async def generate_minimal_plan(project_description, developer_level, framework, software_type):
    """Generate a minimal plan quickly as fallback"""
    try:
        # Ultra-simple prompt for fast generation
        simple_prompt = f"""Project: {project_description}
Level: {developer_level}
Framework: {framework}
Type: {software_type}

Generate MINIMAL plan: Full plan but only show first 7 days in daily_plan. estimated_duration should be full plan duration. 2 tasks/day, 1 resource/task. Be VERY brief."""
        
        # Create minimal agent
        minimal_agent = Agent(
            name="AtlasFast",
            instructions="""Return ONLY valid JSON. Generate MINIMAL plan:
- Full plan but only show first 7 days in daily_plan
- estimated_duration should be full plan duration (can be 14+ days)
- daily_plan should have exactly 7 days
- 2 tasks per day
- 1 resource per task
- 1 sentence descriptions
- 2 subtasks per task
- Generate in 30 seconds

JSON structure same as before but MINIMAL content.""",
            model="gpt-4o-mini",
        )
        
        # Try with 10 second timeout - extremely fast
        try:
            result = await asyncio.wait_for(
                Runner.run(minimal_agent, simple_prompt),
                timeout=30.0  # 30 seconds - faster fallback option
            )
        except asyncio.TimeoutError:
            # If even minimal plan times out, return basic structure immediately
            raise Exception("Timeout - using basic plan")
        
        raw_output = result.final_output
        json_text = extract_json_from_text(raw_output)
        json_text = fix_json_string(json_text)
        
        plan_data = json.loads(json_text)
        
        # Ensure only first 7 days are shown (keep full plan duration)
        if 'daily_plan' in plan_data and isinstance(plan_data['daily_plan'], list):
            if len(plan_data['daily_plan']) > 7:
                # Keep only first 7 days, but don't change estimated_duration
                plan_data['daily_plan'] = plan_data['daily_plan'][:7]
                # estimated_duration should remain as the full plan duration
        
        # CRITICAL: Only validate, DON'T replace AI-generated content
        # If daily_plan is completely missing, that means AI failed - raise error to trigger fallback
        print(f"=== VALIDATING AI GENERATED PLAN ===")
        print(f"Has daily_plan key: {'daily_plan' in plan_data}")
        if 'daily_plan' in plan_data:
            print(f"daily_plan type: {type(plan_data['daily_plan'])}")
            print(f"daily_plan length: {len(plan_data['daily_plan']) if plan_data['daily_plan'] else 0}")
            if plan_data['daily_plan'] and len(plan_data['daily_plan']) > 0:
                first_day = plan_data['daily_plan'][0]
                print(f"First day has tasks: {'tasks' in first_day}")
                if 'tasks' in first_day and first_day['tasks']:
                    first_task = first_day['tasks'][0]
                    print(f"First task title: {first_task.get('title', 'NO TITLE')}")
        print("=====================================")
        
        if 'daily_plan' not in plan_data or not plan_data['daily_plan'] or len(plan_data['daily_plan']) == 0:
            print("ERROR: AI generated plan but daily_plan is missing or empty - this should not happen")
            raise Exception("AI generated plan but daily_plan is missing - use fallback")
        
        # Only fill in missing optional fields, don't replace existing content
        if 'features' not in plan_data:
            plan_data['features'] = {"core": [], "stretch": []}
        if 'features' in plan_data:
            if 'core' not in plan_data['features'] or not plan_data['features']['core']:
                plan_data['features']['core'] = ["Core feature 1", "Core feature 2", "Core feature 3"]
            if 'stretch' not in plan_data['features'] or not plan_data['features']['stretch']:
                plan_data['features']['stretch'] = ["Advanced feature 1", "Advanced feature 2", "Performance optimization"]
        
        if 'milestones' not in plan_data or not plan_data['milestones']:
            plan_data['milestones'] = [{"name": "First Week Complete", "day": 7, "description": "Completed your first week of learning", "reward": {"xp": 100, "coins": 50, "badge": "Week Warrior"}}]
        
        if 'tips_and_motivation' not in plan_data or not plan_data['tips_and_motivation']:
            plan_data['tips_and_motivation'] = ["Keep learning!", "You got this!", "Practice makes perfect!"]
        
        # Ensure each task has all required fields
        for day_plan in plan_data.get('daily_plan', []):
            for task in day_plan.get('tasks', []):
                if 'subtasks' not in task or not task['subtasks']:
                    task['subtasks'] = [
                        {"title": "Subtask 1", "description": "Complete setup", "steps": ["Step 1", "Step 2"]},
                        {"title": "Subtask 2", "description": "Practice basics", "steps": ["Step 1", "Step 2"]}
                    ]
                if 'detailed_steps' not in task or not task['detailed_steps']:
                    task['detailed_steps'] = ["Step 1: Setup", "Step 2: Learn", "Step 3: Practice"]
                if 'learning_materials' not in task:
                    task['learning_materials'] = {"free_resources": ["React Tutorial - https://react.dev/learn"], "documentation": []}
                if 'rewards' not in task:
                    task['rewards'] = {"xp": 20, "coins": 5, "badge": ""}
        
        return plan_data
    except Exception as e:
        # Ultimate fallback - return a basic structure immediately (no AI needed)
        # This ensures we always return something quickly
        return {
            "project_overview": {
                "title": project_description[:50],
                "description": f"Learning plan for {project_description}",
                "estimated_duration": "7 days",
                "recommended_tech_stack": [framework] if framework else ["Recommended tech"],
                "user_level": developer_level,
                "prerequisites": []
            },
            "features": {
                "core": ["Core feature 1", "Core feature 2", "Core feature 3"],
                "stretch": ["Advanced feature 1", "Advanced feature 2", "Performance optimization"]
            },
            "overall_learning_materials": {
                "foundational": ["https://developer.mozilla.org"],
                "project_specific": ["https://react.dev/learn"],
                "paid_comprehensive": []
            },
            "daily_plan": [
                {
                    "day": i,
                    "focus": f"Day {i} focus",
                    "type": "mixed",
                    "tasks": [
                        {
                            "id": f"D{i}-T1",
                            "title": f"Task for day {i}",
                            "task_type": "learning",
                            "description": "Complete this task",
                            "how_to_guide": "Follow the steps",
                            "subtasks": [
                                {"title": "Subtask 1", "description": "Do this", "steps": ["Step 1", "Step 2"]},
                                {"title": "Subtask 2", "description": "Do that", "steps": ["Step 1", "Step 2"]}
                            ],
                            "detailed_steps": ["Step 1", "Step 2", "Step 3"],
                            "time_estimate": "2 hours",
                            "difficulty": "medium",
                            "skills_learned": ["Skill 1"],
                            "common_mistakes": [{"mistake": "Common error", "solution": "Fix", "prevention_tip": "Tip"}],
                            "learning_materials": {
                                "free_resources": ["https://developer.mozilla.org"],
                                "documentation": []
                            },
                            "rewards": {"xp": 20, "coins": 5, "badge": ""}
                        }
                    ],
                    "daily_summary": f"Completed day {i}"
                }
                for i in range(1, 8)
            ],
            "milestones": [],
            "rewards_system": {
                "xp_levels": {
                    "level_1": "0-100 XP",
                    "level_2": "101-300 XP",
                    "level_3": "301-600 XP",
                    "level_4": "601-1000 XP"
                },
                "shop_items": []
            },
            "tips_and_motivation": ["Keep learning!", "You got this!"]
        }


def fix_json_string(json_str):
    """Try to fix common JSON issues including escape sequences"""
    if not json_str:
        return json_str
    
    # Remove trailing commas before closing braces/brackets
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
    
    # Fix unescaped backslashes in string values
    # Valid JSON escape sequences: \\, \", \/, \b, \f, \n, \r, \t, \uXXXX
    # We need to escape backslashes that aren't part of valid escape sequences
    
    result = []
    i = 0
    in_string = False
    
    while i < len(json_str):
        char = json_str[i]
        
        # Track when we're inside a string (quotes toggle string state unless escaped)
        # Check if quote is escaped by counting backslashes before it
        if char == '"':
            # Count consecutive backslashes before this quote
            backslash_count = 0
            j = i - 1
            while j >= 0 and json_str[j] == '\\':
                backslash_count += 1
                j -= 1
            # If even number of backslashes (or zero), quote is not escaped
            if backslash_count % 2 == 0:
                in_string = not in_string
            result.append(char)
            i += 1
            continue
        
        if char == '\\' and in_string:
            # We're in a string and found a backslash
            if i + 1 < len(json_str):
                next_char = json_str[i + 1]
                # Check if it's a valid escape sequence
                valid_escapes = ['\\', '"', '/', 'b', 'f', 'n', 'r', 't', 'u']
                if next_char in valid_escapes:
                    # Valid escape sequence - keep as is
                    result.append(char)
                    result.append(next_char)
                    i += 2
                    # Handle \uXXXX sequences
                    if next_char == 'u' and i + 4 <= len(json_str):
                        hex_chars = json_str[i:i+4]
                        if all(c in '0123456789abcdefABCDEF' for c in hex_chars):
                            result.append(hex_chars)
                            i += 4
                    continue
                else:
                    # Invalid escape - escape the backslash (double it)
                    result.append('\\\\')
                    result.append(next_char)
                    i += 2
                    continue
            else:
                # Backslash at end - escape it
                result.append('\\\\')
                i += 1
                continue
        
        # Regular character or backslash outside string
        result.append(char)
        i += 1
    
    return ''.join(result)


async def generate_plan(project_description, developer_level, framework, software_type):
    """Generate a learning plan using Atlas AI"""
    try:
        # Prepare prompt that generates REAL, personalized content
        full_prompt = f"""Create a personalized learning plan for this project:

Project: {project_description}
Developer Level: {developer_level}
Framework/Technology: {framework}
Software Type: {software_type}

REQUIREMENTS:
- Generate a COMPLETE learning plan (can be 14+ days total)
- BUT only include the FIRST 7 days in the daily_plan array
- The estimated_duration should reflect the FULL plan duration (e.g., "14 days", "21 days")
- daily_plan should contain ONLY the first 7 days
- 2 tasks per day
- CRITICAL: Make tasks SPECIFIC to this project - reference "{project_description}" in task titles and descriptions
- CRITICAL: Do NOT use generic task names like "Setup and basics" - make them about the actual project
- Include real learning resources relevant to the project
- Tasks should be tailored to {developer_level} level
- Use {framework} if specified, or recommend appropriate tech
- Make content PROJECT-SPECIFIC, not generic
- Task titles should be like "Build [project feature]" not "Task 1.1: Setup and basics"

IMPORTANT: Generate a full plan but only show first 7 days in daily_plan. The estimated_duration should be the full plan duration.

Generate valid JSON with real, personalized content for this specific project: {project_description}"""
        
        # Create the Atlas AI agent
        agent = create_atlas_agent()
        
        # Run the agent with 175-second timeout (3 minutes) - give it enough time
        try:
            print(f"Starting AI generation for project: {project_description[:50]}...")
            result = await asyncio.wait_for(
                Runner.run(agent, full_prompt),
                timeout=175.0  # 175 seconds - slightly less than view timeout (3 minutes)
            )
            print("AI generation completed successfully!")
        except asyncio.TimeoutError:
            # Only raise timeout if it actually times out
            print("AI generation timed out after 175 seconds")
            raise Exception("Timeout - use basic plan")
        
        # Extract and parse JSON
        raw_output = result.final_output
        
        # Try to extract JSON
        json_text = extract_json_from_text(raw_output)
        
        # Try to fix common JSON issues
        json_text = fix_json_string(json_text)
        
        # Try parsing with better error handling and recovery strategies
        plan_data = None
        parse_error = None
        
        # Strategy 1: Try parsing the fixed JSON
        try:
            plan_data = json.loads(json_text)
            print("=== JSON PARSING SUCCESS ===")
            print(f"Successfully parsed AI-generated JSON!")
            # Verify it has real content (not just structure)
            if plan_data and 'daily_plan' in plan_data and plan_data['daily_plan']:
                print(f"Plan has {len(plan_data['daily_plan'])} days")
                if plan_data['daily_plan']:
                    first_day = plan_data['daily_plan'][0]
                    first_task = first_day.get('tasks', [{}])[0] if first_day.get('tasks') else {}
                    print(f"First task: {first_task.get('title', 'NO TITLE')}")
                    print(f"First task desc: {first_task.get('description', 'NO DESC')[:80]}")
            print("============================")
        except json.JSONDecodeError as e:
            parse_error = e
            # Strategy 2: Re-run fix_json_string in case it missed something
            try:
                json_text_retry = fix_json_string(json_text)
                if json_text_retry != json_text:
                    plan_data = json.loads(json_text_retry)
                    json_text = json_text_retry
            except (json.JSONDecodeError, Exception):
                # Strategy 3: Try a more aggressive fix for escape sequences
                try:
                    # Process character by character to fix remaining escape issues
                    # This is a fallback that handles edge cases
                    fixed_chars = []
                    i = 0
                    in_str = False
                    while i < len(json_text):
                        c = json_text[i]
                        # Check if quote is escaped by counting backslashes before it
                        if c == '"':
                            backslash_count = 0
                            j = i - 1
                            while j >= 0 and json_text[j] == '\\':
                                backslash_count += 1
                                j -= 1
                            if backslash_count % 2 == 0:
                                in_str = not in_str
                            fixed_chars.append(c)
                            i += 1
                            continue
                        elif c == '\\' and in_str and i + 1 < len(json_text):
                            next_c = json_text[i + 1]
                            if next_c not in ['\\', '"', '/', 'b', 'f', 'n', 'r', 't', 'u']:
                                # Invalid escape - double the backslash
                                fixed_chars.append('\\\\')
                                fixed_chars.append(next_c)
                                i += 2
                                continue
                            else:
                                # Valid escape sequence
                                fixed_chars.append(c)
                                fixed_chars.append(next_c)
                                i += 2
                                # Handle \uXXXX sequences
                                if next_c == 'u' and i + 4 <= len(json_text):
                                    hex_part = json_text[i:i+4]
                                    if all(h in '0123456789abcdefABCDEF' for h in hex_part):
                                        fixed_chars.append(hex_part)
                                        i += 4
                                continue
                        else:
                            fixed_chars.append(c)
                        i += 1
                    
                    fixed_json = ''.join(fixed_chars)
                    plan_data = json.loads(fixed_json)
                except (json.JSONDecodeError, Exception) as e3:
                    # All strategies failed - log and raise error
                    error_msg = f"JSON parse error at position {e.pos}: {e.msg}" if hasattr(e, 'pos') else str(e)
                    error_context = json_text[max(0, e.pos-100):e.pos+100] if hasattr(e, 'pos') and e.pos and e.pos < len(json_text) else "N/A"
                    
                    # Save raw output for debugging
                    try:
                        import os
                        debug_dir = os.path.join(os.path.dirname(__file__), '..', 'debug_output')
                        os.makedirs(debug_dir, exist_ok=True)
                        with open(os.path.join(debug_dir, 'raw_ai_output.txt'), 'w', encoding='utf-8') as f:
                            f.write("=== RAW AI OUTPUT ===\n")
                            f.write(raw_output)
                            f.write("\n\n=== EXTRACTED JSON ===\n")
                            f.write(json_text)
                            f.write(f"\n\n=== ERROR ===\n")
                            f.write(f"Position: {e.pos if hasattr(e, 'pos') else 'N/A'}\n")
                            f.write(f"Message: {e.msg if hasattr(e, 'msg') else str(e)}\n")
                            f.write(f"Context: {error_context}\n")
                    except:
                        pass  # Don't fail if we can't save debug file
                    
                    # Raise a more helpful error
                    raise Exception(f"Failed to parse JSON response from AI. The AI may have returned malformed JSON. Error: {error_msg}. Please try again.")
        
        # Ensure we have valid plan_data
        if plan_data is None:
            raise Exception("Failed to parse JSON after all recovery attempts.")
        
        # Ensure only first 7 days are shown (but keep full plan duration in estimated_duration)
        if 'daily_plan' in plan_data and isinstance(plan_data['daily_plan'], list):
            if len(plan_data['daily_plan']) > 7:
                # Keep only first 7 days, but don't change estimated_duration
                plan_data['daily_plan'] = plan_data['daily_plan'][:7]
                # estimated_duration should remain as the full plan duration
        
        # CRITICAL: Only fill in missing fields, DON'T replace AI-generated content
        # If daily_plan is completely missing, that means AI failed - raise error to trigger fallback
        print(f"=== VALIDATING AI GENERATED PLAN ===")
        print(f"Has daily_plan key: {'daily_plan' in plan_data}")
        if 'daily_plan' in plan_data:
            print(f"daily_plan type: {type(plan_data['daily_plan'])}")
            print(f"daily_plan length: {len(plan_data['daily_plan']) if plan_data['daily_plan'] else 0}")
            if plan_data['daily_plan'] and len(plan_data['daily_plan']) > 0:
                first_day = plan_data['daily_plan'][0]
                print(f"First day has tasks: {'tasks' in first_day}")
                if 'tasks' in first_day and first_day['tasks']:
                    first_task = first_day['tasks'][0]
                    print(f"First task title: {first_task.get('title', 'NO TITLE')}")
        print("=====================================")
        
        if 'daily_plan' not in plan_data or not plan_data['daily_plan'] or len(plan_data['daily_plan']) == 0:
            print("ERROR: AI generated plan but daily_plan is missing or empty - this should not happen")
            raise Exception("AI generated plan but daily_plan is missing - use fallback")
        
        # Only fill in missing optional fields, don't replace existing content
        if 'features' not in plan_data:
            plan_data['features'] = {"core": [], "stretch": []}
        if 'features' in plan_data:
            if 'core' not in plan_data['features'] or not plan_data['features']['core']:
                plan_data['features']['core'] = ["Core feature 1", "Core feature 2", "Core feature 3"]
            if 'stretch' not in plan_data['features'] or not plan_data['features']['stretch']:
                plan_data['features']['stretch'] = ["Advanced feature 1", "Advanced feature 2", "Performance optimization"]
        
        if 'milestones' not in plan_data or not plan_data['milestones']:
            plan_data['milestones'] = [{"name": "First Week Complete", "day": 7, "description": "Completed your first week of learning", "reward": {"xp": 100, "coins": 50, "badge": "Week Warrior"}}]
        
        if 'tips_and_motivation' not in plan_data or not plan_data['tips_and_motivation']:
            plan_data['tips_and_motivation'] = ["Keep learning!", "You got this!", "Practice makes perfect!"]
        
        # Ensure each task has all required fields
        for day_plan in plan_data.get('daily_plan', []):
            for task in day_plan.get('tasks', []):
                if 'subtasks' not in task or not task['subtasks']:
                    task['subtasks'] = [
                        {"title": "Subtask 1", "description": "Complete setup", "steps": ["Step 1", "Step 2"]},
                        {"title": "Subtask 2", "description": "Practice basics", "steps": ["Step 1", "Step 2"]}
                    ]
                if 'detailed_steps' not in task or not task['detailed_steps']:
                    task['detailed_steps'] = ["Step 1: Setup", "Step 2: Learn", "Step 3: Practice"]
                if 'learning_materials' not in task:
                    task['learning_materials'] = {"free_resources": ["React Tutorial - https://react.dev/learn"], "documentation": []}
                if 'rewards' not in task:
                    task['rewards'] = {"xp": 20, "coins": 5, "badge": ""}
        
        # Skip quality checker for speed - return plan immediately
        # Quality checking doubles the generation time and can cause timeouts
        print(f"=== RETURNING AI PLAN ===")
        print(f"Plan has {len(plan_data.get('daily_plan', []))} days")
        if plan_data.get('daily_plan'):
            first_day = plan_data['daily_plan'][0]
            first_task = first_day.get('tasks', [{}])[0] if first_day.get('tasks') else {}
            print(f"Returning plan with first task: {first_task.get('title', 'NO TITLE')}")
        print("=========================")
        return plan_data
        
    except asyncio.TimeoutError:
        # Fallback to minimal plan
        print("Main generation timed out - trying minimal plan")
        raise Exception("Timeout - use basic plan")  # Let views.py handle fallback
    except json.JSONDecodeError as e:
        # If JSON parsing fails, try minimal plan
        print(f"JSON parsing failed: {str(e)} - trying minimal plan")
        raise Exception("JSON parse failed - use basic plan")  # Let views.py handle fallback
    except Exception as e:
        # Check if it's our intentional error about missing daily_plan
        if "daily_plan is missing" in str(e):
            print("AI generated plan but daily_plan was missing - using fallback")
            raise Exception("Timeout - use basic plan")  # Let views.py handle fallback
        # Any other error - raise to let views.py handle
        print(f"Generation error: {str(e)} - using fallback")
        raise Exception("Generation failed - use basic plan")  # Let views.py handle fallback


def analyze_uploaded_image(image_path):
    """
    Analyze uploaded image using GPT-4 Vision to extract facial features
    
    Args:
        image_path: Path to the uploaded image
    
    Returns:
        String description of facial features
    """
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Read and encode the image to base64
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Determine image format
        image_format = 'jpeg'
        if image_path.lower().endswith('.png'):
            image_format = 'png'
        elif image_path.lower().endswith('.gif'):
            image_format = 'gif'
        elif image_path.lower().endswith('.webp'):
            image_format = 'webp'
        
        # Use GPT-4 Vision to analyze the image
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this character design reference image for creating a 2D game avatar. Describe the visual characteristics you observe: 1) HAIR: color (dark brown, black, blonde, red, etc.), style (curly, straight, wavy, short, long, messy, neat), length. 2) EYES: color (brown, blue, green, hazel), shape, size. 3) SKIN TONE: shade (light, medium, dark, olive, etc.). 4) FACE SHAPE: round, oval, square, heart, etc. 5) GLASSES: if visible, describe style (round, square, rectangular), frame color, size. 6) FACIAL HAIR: if visible, describe style (full beard, goatee, mustache, stubble), color, length. 7) VISUAL FEATURES: any notable visual characteristics. 8) EXPRESSION: neutral, smiling, serious, etc. 9) ARTISTIC STYLE NOTES: any relevant details for character design. Provide a detailed technical description of the visual elements for character design purposes."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_format};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=800
        )
        
        description = response.choices[0].message.content
        
        # Check if the model refused to analyze (content policy)
        if "can't help" in description.lower() or "sorry" in description.lower() or "cannot" in description.lower():
            print(f"WARNING: Image analysis was refused by the model. Trying alternative approach...")
            # Try a different prompt that's more focused on artistic/technical aspects
            return analyze_uploaded_image_alternative(image_path)
        
        print(f"Image analysis completed. Full description: {description}")
        print(f"Description length: {len(description)} characters")
        return description
        
    except Exception as e:
        print(f"Error analyzing image: {str(e)}")
        # Try alternative approach
        try:
            return analyze_uploaded_image_alternative(image_path)
        except:
            # Return None if all attempts fail - we'll still generate an avatar without the image description
            return None


def analyze_uploaded_image_alternative(image_path):
    """
    Alternative image analysis using a more technical/artistic approach
    """
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Read and encode the image to base64
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Determine image format
        image_format = 'jpeg'
        if image_path.lower().endswith('.png'):
            image_format = 'png'
        elif image_path.lower().endswith('.gif'):
            image_format = 'gif'
        elif image_path.lower().endswith('.webp'):
            image_format = 'webp'
        
        # Use GPT-4 Vision with a more technical/artistic prompt
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "This is a reference image for creating a 2D game character avatar. Describe the visual design elements you see: hair color and style, eye color, skin tone, face shape, any accessories like glasses, facial hair style, and overall visual characteristics. Focus on the artistic and design aspects that would be needed to recreate this character in a 2D game style. Be specific about colors, shapes, and style details."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_format};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=600
        )
        
        description = response.choices[0].message.content
        
        # Check again if refused
        if "can't help" in description.lower() or "sorry" in description.lower() or "cannot" in description.lower():
            print(f"WARNING: Alternative analysis also refused. Will generate avatar without person transformation.")
            return None
        
        print(f"Alternative image analysis completed. Description: {description[:200]}...")
        return description
        
    except Exception as e:
        print(f"Error in alternative image analysis: {str(e)}")
        return None


def generate_avatar_image(character_class, profession, uploaded_image_path=None):
    """
    Generate a 2D game-style vector avatar image using OpenAI DALL-E API
    
    Args:
        character_class: The character class (elf, demon, etc.)
        profession: The profession (web development, frontend development, etc.)
        uploaded_image_path: Optional path to uploaded user image
    
    Returns:
        URL of the generated image
    """
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Analyze uploaded image if provided
        image_description = None
        if uploaded_image_path and os.path.exists(uploaded_image_path):
            print(f"Analyzing uploaded image: {uploaded_image_path}")
            try:
                image_description = analyze_uploaded_image(uploaded_image_path)
                if image_description:
                    print(f"Image analysis completed successfully. Description length: {len(image_description)} characters")
                    print(f"Description preview: {image_description[:300]}...")
                else:
                    print("WARNING: Image analysis returned no description. Avatar will be generated without person transformation.")
            except Exception as e:
                print(f"ERROR during image analysis: {str(e)}")
                print("Avatar will be generated without person transformation.")
                image_description = None
        
        # Create a detailed prompt for a 2D game avatar style
        # Keep prompt concise to stay under 4000 character limit
        prompt = "ONE single character portrait. NOT two. NOT multiple. NOT side-by-side. Just ONE character on white background. "
        prompt += "Forbidden: second character, multiple, side-by-side, variations, separate parts, hair sections, eye variations, hand components, numbered elements, circles, lines, arrows, text, labels, UI, swatches, design sheet, decorative elements. "
        
        # If we have an uploaded image, make transformation the PRIMARY requirement
        if image_description:
            # Truncate image description if too long to keep prompt under limit
            max_desc_length = 600
            if len(image_description) > max_desc_length:
                image_description = image_description[:max_desc_length] + "..."
            
            prompt += f"Transform this person into {character_class}: {image_description}. "
            prompt += f"Preserve: hair, eyes, skin, face, glasses, facial hair. Add {character_class} features (horns/ears/etc) but keep recognizable. "
        else:
            prompt += f"{character_class} character, {profession} professional. "
        
        # Add character class specific features
        class_features = {
            'elf': 'pointed ears',
            'demon': 'small horns, glowing eyes',
            'human': 'normal features',
            'dwarf': 'beard, sturdy',
            'orc': 'tusks, strong features',
            'fairy': 'delicate, small wings',
            'wizard': 'wise appearance',
            'warrior': 'strong, determined'
        }
        
        if character_class in class_features:
            prompt += f"{class_features[character_class]}. "
        
        prompt += "Style: 2D game avatar, clean flat vector art, simple stylized, flat colors, cartoon-like, bold lines, bright colors. Square format, head and shoulders, centered, front-facing. Plain white background. "
        prompt += "CRITICAL: ONLY ONE unified character. No second character. No multiple. No side-by-side. No separate parts. No design elements. Just ONE character on white. "
        
        # Check prompt length and truncate if needed
        if len(prompt) > 4000:
            print(f"WARNING: Prompt length is {len(prompt)}, truncating to 4000 characters")
            prompt = prompt[:4000]
        
        print(f"Generating avatar with prompt length: {len(prompt)} characters")
        print(f"Prompt preview: {prompt[:200]}...")
        
        # Generate image using DALL-E 3
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        
        image_url = response.data[0].url
        print(f"Avatar generated successfully: {image_url}")
        
        return image_url
        
    except Exception as e:
        print(f"Error generating avatar: {str(e)}")
        raise Exception(f"Failed to generate avatar: {str(e)}")


def download_image_from_url(url, save_path):
    """
    Download an image from a URL and save it to the specified path
    
    Args:
        url: URL of the image
        save_path: Local path where to save the image
    
    Returns:
        Path to the saved image
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # Save the image
        with open(save_path, 'wb') as f:
            f.write(response.content)
        
        print(f"Image downloaded and saved to: {save_path}")
        return save_path
        
    except Exception as e:
        print(f"Error downloading image: {str(e)}")
        raise Exception(f"Failed to download image: {str(e)}")

