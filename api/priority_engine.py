"""
AI Priority Engine for intelligent task prioritization.

Uses multi-factor scoring and OpenAI reasoning to generate contextual recommendations.
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from openai import OpenAI, OpenAIError, RateLimitError, APITimeoutError
from context_builder import ContextBuilder

logger = logging.getLogger(__name__)


class PriorityEngine:
    """Generates intelligent priority recommendations based on context."""
    
    def __init__(self):
        self.context_builder = ContextBuilder()
        
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and api_key.strip():
            self.openai_client = OpenAI(api_key=api_key)
            self.openai_available = True
        else:
            self.openai_client = None
            self.openai_available = False
            logger.warning("OpenAI API key not configured, using fallback reasoning")
    
    async def generate_recommendation(self, journey_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate priority recommendation with full context analysis.
        
        Args:
            journey_id: Optional specific journey ID
            
        Returns:
            Complete recommendation with primary action, alternatives, and reasoning
        """
        try:
            # Step 1: Build comprehensive context
            context = await self.context_builder.build_context(journey_id)
            
            # Step 2: Identify and score possible actions
            actions = await self._identify_possible_actions(context)
            scored_actions = await self._score_actions(actions, context)
            
            # Step 3: Generate AI reasoning
            reasoning = await self._generate_reasoning(scored_actions, context)
            
            # Step 4: Format final recommendation
            recommendation = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "context_id": self._generate_context_id(context),
                "primary_action": {
                    "action": scored_actions[0]["action"],
                    "why": reasoning.get("primary_reasoning", scored_actions[0]["reasoning"]),
                    "expected_impact": scored_actions[0]["impact_score"],
                    "time_estimate": scored_actions[0]["time_estimate"],
                    "confidence": scored_actions[0]["confidence"],
                    "urgency": scored_actions[0]["urgency"],
                    "importance": scored_actions[0]["importance"]
                },
                "alternatives": [
                    {
                        "action": alt["action"],
                        "why": alt["reasoning"],
                        "when_to_consider": alt.get("trigger", "If primary action is blocked"),
                        "time_estimate": alt["time_estimate"]
                    } for alt in scored_actions[1:3]  # Top 2 alternatives
                ],
                "context_summary": reasoning.get("situation_analysis", "Context analysis unavailable"),
                "journey_alignment": reasoning.get("goal_alignment", "Goal alignment analysis unavailable"),
                "momentum_insight": self._generate_momentum_insight(context),
                "energy_match": self._assess_energy_match(scored_actions[0], context),
                "debug_info": {
                    "total_actions_considered": len(actions),
                    "context_layers": list(context.keys()),
                    "ai_reasoning_used": self.openai_available
                }
            }
            
            logger.info(f"Generated recommendation: {scored_actions[0]['action'][:50]}...")
            return recommendation
            
        except Exception as e:
            logger.error(f"Failed to generate recommendation: {e}")
            return self._generate_fallback_recommendation()
    
    async def _identify_possible_actions(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify all possible actions from the current context."""
        actions = []
        
        # Action: Work on blocked items
        blocked_items = context.get("blocked_items", [])
        for item in blocked_items[:2]:  # Top 2 blocked items
            actions.append({
                "action": f"Unblock: {item.get('title', 'Unknown item')}",
                "type": "unblock",
                "source": "linear",
                "ref_id": item.get("ref_id"),
                "url": item.get("url"),
                "reasoning": f"Item blocked since {item.get('blocked_since', 'recently')}",
                "urgency": 0.8,  # Blocked items are urgent
                "importance": 0.6,
                "time_estimate": "30-60 minutes"
            })
        
        # Action: Review aging PRs
        pr_status = context.get("pr_status", [])
        aging_prs = [pr for pr in pr_status if pr.get("needs_review", False)]
        for pr in aging_prs[:2]:  # Top 2 aging PRs
            actions.append({
                "action": f"Review PR: {pr.get('title', 'Unknown PR')}",
                "type": "pr_review", 
                "source": "github",
                "ref_id": pr.get("ref_id"),
                "url": pr.get("url"),
                "reasoning": f"PR aging for {pr.get('hours_old', 0):.0f} hours",
                "urgency": min(0.9, pr.get("hours_old", 0) / 48),  # More urgent as it ages
                "importance": 0.5,
                "time_estimate": "15-30 minutes"
            })
        
        # Action: Work on active issues
        active_issues = context.get("active_issues", [])
        for issue in active_issues[:3]:  # Top 3 active issues
            priority_multiplier = {"urgent": 1.0, "high": 0.8, "normal": 0.6, "low": 0.4, "none": 0.3}
            priority = issue.get("priority", "normal")
            
            actions.append({
                "action": f"Advance: {issue.get('title', 'Unknown issue')}",
                "type": "issue_work",
                "source": "linear",
                "ref_id": issue.get("ref_id"),
                "url": issue.get("url"),
                "reasoning": f"Issue in {issue.get('state', 'unknown')} state for {issue.get('days_old', 0):.0f} days",
                "urgency": min(0.8, issue.get("days_old", 0) / 7) * priority_multiplier.get(priority, 0.6),
                "importance": priority_multiplier.get(priority, 0.6),
                "time_estimate": "1-3 hours"
            })
        
        # Action: Journey-specific goals
        journey = context.get("journey", {})
        desired_state = journey.get("desired_state", {})
        priorities = desired_state.get("priorities", [])
        
        for i, priority in enumerate(priorities[:2]):  # Top 2 journey priorities
            actions.append({
                "action": f"Advance journey goal: {priority}",
                "type": "journey_goal",
                "source": "journey",
                "ref_id": f"journey_priority_{i}",
                "reasoning": f"Strategic goal aligned with {desired_state.get('role', 'career objectives')}",
                "urgency": 0.4,  # Strategic, less urgent
                "importance": 0.9,  # But very important
                "time_estimate": "2-4 hours"
            })
        
        # Action: Quick wins (if low energy or end of day)
        time_context = context.get("time_context", {})
        if time_context.get("energy_level") == "low" or time_context.get("work_day_remaining", 8) < 2:
            actions.extend([
                {
                    "action": "Review and update documentation",
                    "type": "maintenance",
                    "source": "system",
                    "reasoning": "Low-energy task for end of day",
                    "urgency": 0.2,
                    "importance": 0.4,
                    "time_estimate": "30-60 minutes"
                },
                {
                    "action": "Organize and clean up local development environment",
                    "type": "maintenance", 
                    "source": "system",
                    "reasoning": "Maintenance task suitable for low energy",
                    "urgency": 0.1,
                    "importance": 0.3,
                    "time_estimate": "15-45 minutes"
                }
            ])
        
        # Ensure we have at least one action
        if not actions:
            actions.append({
                "action": "Review project status and plan next steps",
                "type": "planning",
                "source": "fallback",
                "reasoning": "No specific actions identified, time for strategic review",
                "urgency": 0.5,
                "importance": 0.6,
                "time_estimate": "30-60 minutes"
            })
        
        return actions
    
    async def _score_actions(self, actions: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Score actions using multi-factor algorithm."""
        journey = context.get("journey", {})
        time_context = context.get("time_context", {})
        momentum = context.get("momentum", {})
        
        for action in actions:
            # Base scoring factors
            urgency = action.get("urgency", 0.5)
            importance = action.get("importance", 0.5)
            
            # Journey alignment factor
            desired_role = journey.get("desired_state", {}).get("role", "")
            if "staff" in desired_role.lower() or "senior" in desired_role.lower():
                if action.get("type") in ["journey_goal", "issue_work"]:
                    alignment = 0.8
                elif action.get("type") in ["pr_review", "unblock"]:
                    alignment = 0.7
                else:
                    alignment = 0.5
            else:
                alignment = 0.6
            
            # Momentum factor
            momentum_multiplier = 1.2 if momentum.get("trend") == "increasing" else 1.0
            
            # Energy fit factor
            energy_level = time_context.get("energy_level", "medium")
            energy_fit = self._calculate_energy_fit(action, energy_level)
            
            # Time availability factor
            work_remaining = time_context.get("work_day_remaining", 8)
            time_fit = self._calculate_time_fit(action, work_remaining)
            
            # Combined score
            score = (
                urgency * 0.25 +
                importance * 0.25 +
                alignment * 0.20 +
                energy_fit * 0.15 +
                time_fit * 0.15
            ) * momentum_multiplier
            
            action["score"] = score
            action["alignment"] = alignment
            action["energy_fit"] = energy_fit
            action["time_fit"] = time_fit
            action["confidence"] = min(0.95, (urgency + importance + alignment) / 3)
            action["impact_score"] = importance * alignment
        
        # Sort by score descending
        return sorted(actions, key=lambda x: x["score"], reverse=True)
    
    def _calculate_energy_fit(self, action: Dict[str, Any], energy_level: str) -> float:
        """Calculate how well action fits current energy level."""
        action_type = action.get("type", "unknown")
        
        energy_requirements = {
            "journey_goal": {"high": 0.9, "medium": 0.7, "low": 0.3},
            "issue_work": {"high": 0.8, "medium": 0.8, "low": 0.4},
            "unblock": {"high": 0.7, "medium": 0.8, "low": 0.6},
            "pr_review": {"high": 0.6, "medium": 0.8, "low": 0.7},
            "maintenance": {"high": 0.4, "medium": 0.6, "low": 0.9},
            "planning": {"high": 0.7, "medium": 0.8, "low": 0.5}
        }
        
        return energy_requirements.get(action_type, {"high": 0.6, "medium": 0.6, "low": 0.6})[energy_level]
    
    def _calculate_time_fit(self, action: Dict[str, Any], hours_remaining: float) -> float:
        """Calculate how well action fits remaining time."""
        time_estimate = action.get("time_estimate", "1-2 hours")
        
        # Extract max hours from estimate (rough parsing)
        if "15-" in time_estimate or "30-" in time_estimate:
            max_hours = 1.0
        elif "1-2" in time_estimate or "1-3" in time_estimate:
            max_hours = 2.5
        elif "2-4" in time_estimate:
            max_hours = 4.0
        else:
            max_hours = 2.0
        
        if max_hours <= hours_remaining:
            return 1.0
        elif max_hours <= hours_remaining + 1:
            return 0.7
        else:
            return 0.3
    
    async def _generate_reasoning(self, scored_actions: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, str]:
        """Generate AI reasoning for the recommendation."""
        if not self.openai_available or not scored_actions:
            return self._generate_fallback_reasoning(scored_actions, context)
        
        try:
            primary_action = scored_actions[0]
            journey = context.get("journey", {})
            time_context = context.get("time_context", {})
            
            prompt = self._build_reasoning_prompt(primary_action, context)
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an AI assistant helping prioritize engineering tasks. Provide clear, concise reasoning for task recommendations based on context. Be specific and actionable."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=800,
                temperature=0.3,
                timeout=30.0  # 30 second timeout
            )
            
            reasoning_text = response.choices[0].message.content.strip()
            
            # Parse reasoning into components
            return self._parse_ai_reasoning(reasoning_text, primary_action, context)
            
        except RateLimitError as e:
            logger.warning(f"OpenAI rate limit exceeded: {e}")
            return self._generate_fallback_reasoning(scored_actions, context)
        except APITimeoutError as e:
            logger.warning(f"OpenAI timeout: {e}")
            return self._generate_fallback_reasoning(scored_actions, context)
        except OpenAIError as e:
            logger.error(f"OpenAI API error: {e}")
            return self._generate_fallback_reasoning(scored_actions, context)
        except Exception as e:
            logger.error(f"Unexpected error in OpenAI reasoning: {e}")
            return self._generate_fallback_reasoning(scored_actions, context)
    
    def _build_reasoning_prompt(self, primary_action: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Build prompt for AI reasoning generation."""
        journey = context.get("journey", {})
        time_context = context.get("time_context", {})
        momentum = context.get("momentum", {})
        
        return f"""
I need to prioritize my next action. Here's the context:

RECOMMENDED ACTION: {primary_action.get('action')}
Action Type: {primary_action.get('type')}
Urgency: {primary_action.get('urgency'):.2f}
Importance: {primary_action.get('importance'):.2f}
Score: {primary_action.get('score'):.2f}

JOURNEY CONTEXT:
Goal: {journey.get('desired_state', {}).get('role', 'Career advancement')}
Current Status: {journey.get('current_state', {}).get('status', 'Working')}
Timeline: {journey.get('desired_state', {}).get('timeline', 'Unknown')}

TIME CONTEXT:
Current Time: {time_context.get('local_time', 'Unknown')}
Energy Level: {time_context.get('energy_level', 'medium')}
Work Hours Remaining: {time_context.get('work_day_remaining', 'unknown')}
Is Weekend: {time_context.get('is_weekend', False)}

MOMENTUM:
Trend: {momentum.get('trend', 'stable')}
Recent Activity: {momentum.get('recent_activity', 0)} events
Velocity Change: {momentum.get('velocity_change', 0):.1f}x

CURRENT METRICS:
PRs opened (48h): {context.get('metrics', {}).get('prs_open_48h', 0)}
PRs merged (48h): {context.get('metrics', {}).get('prs_merged_48h', 0)}
Tickets moved (48h): {context.get('metrics', {}).get('tickets_moved_48h', 0)}
Blocked tickets: {context.get('metrics', {}).get('tickets_blocked_now', 0)}

Please provide reasoning in this format:
SITUATION_ANALYSIS: [Brief analysis of current situation]
PRIMARY_REASONING: [Why this specific action is the best choice right now]
GOAL_ALIGNMENT: [How this action advances the journey goals]
"""
    
    def _parse_ai_reasoning(self, reasoning_text: str, primary_action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, str]:
        """Parse AI reasoning response into structured format."""
        try:
            lines = reasoning_text.split('\n')
            
            situation_analysis = ""
            primary_reasoning = ""
            goal_alignment = ""
            
            current_section = None
            
            for line in lines:
                line = line.strip()
                if line.startswith("SITUATION_ANALYSIS:"):
                    current_section = "situation"
                    situation_analysis = line.replace("SITUATION_ANALYSIS:", "").strip()
                elif line.startswith("PRIMARY_REASONING:"):
                    current_section = "primary"
                    primary_reasoning = line.replace("PRIMARY_REASONING:", "").strip()
                elif line.startswith("GOAL_ALIGNMENT:"):
                    current_section = "goal"
                    goal_alignment = line.replace("GOAL_ALIGNMENT:", "").strip()
                elif line and current_section:
                    if current_section == "situation":
                        situation_analysis += " " + line
                    elif current_section == "primary":
                        primary_reasoning += " " + line
                    elif current_section == "goal":
                        goal_alignment += " " + line
            
            return {
                "situation_analysis": situation_analysis or "Current context analyzed",
                "primary_reasoning": primary_reasoning or primary_action.get("reasoning", "Best available action"),
                "goal_alignment": goal_alignment or "Supports overall objectives"
            }
            
        except Exception as e:
            logger.error(f"Failed to parse AI reasoning: {e}")
            return self._generate_fallback_reasoning([primary_action], context)
    
    def _generate_fallback_reasoning(self, scored_actions: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, str]:
        """Generate fallback reasoning when AI is unavailable."""
        if not scored_actions:
            return {
                "situation_analysis": "No specific actions identified from current context",
                "primary_reasoning": "Time for strategic planning and review",
                "goal_alignment": "Planning supports all objectives"
            }
        
        primary = scored_actions[0]
        time_context = context.get("time_context", {})
        
        return {
            "situation_analysis": f"Based on {len(scored_actions)} possible actions. Current energy: {time_context.get('energy_level', 'medium')}. {time_context.get('work_day_remaining', 0):.0f} hours remaining.",
            "primary_reasoning": f"{primary.get('reasoning', 'Highest priority action')} Score: {primary.get('score', 0):.2f}",
            "goal_alignment": f"This {primary.get('type', 'action')} supports your journey toward {context.get('journey', {}).get('desired_state', {}).get('role', 'career goals')}."
        }
    
    def _generate_momentum_insight(self, context: Dict[str, Any]) -> str:
        """Generate insight about current momentum."""
        momentum = context.get("momentum", {})
        trend = momentum.get("trend", "stable")
        velocity = momentum.get("velocity_change", 1.0)
        
        if trend == "increasing":
            return f"Momentum is strong (↑{velocity:.1f}x). Great time to tackle challenging work."
        elif trend == "decreasing":
            return f"Activity has slowed (↓{velocity:.1f}x). Consider quick wins to rebuild momentum."
        else:
            return "Activity is steady. Good time for consistent progress on priorities."
    
    def _assess_energy_match(self, action: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Assess how well the action matches current energy level."""
        energy_fit = action.get("energy_fit", 0.5)
        energy_level = context.get("time_context", {}).get("energy_level", "medium")
        
        if energy_fit >= 0.8:
            return f"Perfect match for {energy_level} energy level"
        elif energy_fit >= 0.6:
            return f"Good fit for current {energy_level} energy"
        else:
            return f"May be challenging given {energy_level} energy level"
    
    def _generate_context_id(self, context: Dict[str, Any]) -> str:
        """Generate unique ID for this context snapshot."""
        import hashlib
        
        # Create hash from key context elements
        context_string = json.dumps({
            "time": context.get("time_context", {}).get("current_utc", ""),
            "journey_id": context.get("journey", {}).get("id", ""),
            "metrics": context.get("metrics", {}),
            "active_issues_count": len(context.get("active_issues", [])),
            "blocked_count": len(context.get("blocked_items", []))
        }, sort_keys=True)
        
        return hashlib.md5(context_string.encode()).hexdigest()[:12]
    
    def _generate_fallback_recommendation(self) -> Dict[str, Any]:
        """Generate fallback recommendation when everything fails."""
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "context_id": "fallback",
            "primary_action": {
                "action": "Review project status and plan next steps",
                "why": "System unable to analyze current context. Time for manual review.",
                "expected_impact": 0.6,
                "time_estimate": "30-60 minutes",
                "confidence": 0.5,
                "urgency": 0.5,
                "importance": 0.6
            },
            "alternatives": [
                {
                    "action": "Check for urgent notifications or messages",
                    "why": "Ensure nothing critical is waiting",
                    "when_to_consider": "If planning feels premature",
                    "time_estimate": "10-15 minutes"
                }
            ],
            "context_summary": "Unable to analyze current context. Recommending strategic review.",
            "journey_alignment": "Planning supports all objectives.",
            "momentum_insight": "Context analysis unavailable.",
            "energy_match": "Default recommendation suitable for any energy level",
            "debug_info": {
                "total_actions_considered": 1,
                "context_layers": [],
                "ai_reasoning_used": False
            }
        }