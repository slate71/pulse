"use client";

import React, { useState, useEffect } from "react";
import { QueryClient, QueryClientProvider, useQuery, useMutation } from "@tanstack/react-query";

// Types
interface PrimaryAction {
  action: string;
  why: string;
  expected_impact: number;
  time_estimate: string;
  confidence: number;
  urgency: number;
  importance: number;
}

interface Alternative {
  action: string;
  why: string;
  when_to_consider: string;
  time_estimate: string;
}

interface PriorityRecommendation {
  generated_at: string;
  context_id: string;
  primary_action: PrimaryAction;
  alternatives: Alternative[];
  context_summary: string;
  journey_alignment: string;
  momentum_insight: string;
  energy_match: string;
  debug_info: {
    total_actions_considered: number;
    context_layers: string[];
    ai_reasoning_used: boolean;
  };
}

interface JourneyState {
  id: string;
  desired_state: {
    role: string;
    timeline: string;
    priorities: string[];
  };
  current_state: {
    status: string;
    momentum: string;
    current_project?: string;
  };
  preferences: {
    work_hours: string;
    energy_pattern: string;
  };
}

// API functions
const fetchPriorityRecommendation = async (): Promise<PriorityRecommendation> => {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/priority/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  
  if (!response.ok) {
    throw new Error('Failed to generate recommendation');
  }
  
  return response.json();
};

const fetchJourneyState = async (): Promise<JourneyState> => {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/journey/state`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch journey state');
  }
  
  return response.json();
};

const submitFeedback = async (feedback: {
  recommendation_id: string;
  action_taken?: string;
  outcome?: string;
  feedback_score?: number;
  time_to_complete_minutes?: number;
}) => {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/priority/feedback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(feedback),
  });
  
  if (!response.ok) {
    throw new Error('Failed to submit feedback');
  }
  
  return response.json();
};

// Components
const JourneyProgress: React.FC<{ journey: JourneyState }> = ({ journey }) => {
  const progressPercentage = journey.current_state.momentum === "high" ? 65 : 
                           journey.current_state.momentum === "medium" ? 40 : 25;

  return (
    <div className="bg-white rounded-lg p-6 shadow-sm border border-slate-200 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-900">Journey Progress</h2>
        <span className="text-sm text-slate-600">{progressPercentage}% complete</span>
      </div>
      
      <div className="w-full bg-slate-200 rounded-full h-2 mb-4">
        <div 
          className="bg-blue-600 h-2 rounded-full transition-all duration-500"
          style={{ width: `${progressPercentage}%` }}
        ></div>
      </div>
      
      <div className="flex justify-between text-sm">
        <span className="text-slate-600">{journey.current_state.status.replace(/_/g, ' ')}</span>
        <span className="font-medium text-slate-900">{journey.desired_state.role}</span>
      </div>
      
      {journey.current_state.current_project && (
        <p className="text-sm text-slate-600 mt-2">
          Current focus: {journey.current_state.current_project}
        </p>
      )}
    </div>
  );
};

const PriorityCard: React.FC<{ action: PrimaryAction }> = ({ action }) => {
  const confidenceColor = action.confidence >= 0.8 ? "text-green-600" :
                          action.confidence >= 0.6 ? "text-amber-600" : "text-red-600";

  return (
    <div className="bg-white rounded-lg p-8 shadow-sm border border-slate-200 mb-6">
      <div className="flex items-start justify-between mb-4">
        <h2 className="text-xl font-bold text-slate-900">Next Priority</h2>
        <div className="flex items-center space-x-4 text-sm">
          <span className="text-slate-600">{action.time_estimate}</span>
          <span className={`font-medium ${confidenceColor}`}>
            {Math.round(action.confidence * 100)}% confidence
          </span>
        </div>
      </div>
      
      <div className="mb-6">
        <h3 className="text-2xl font-semibold text-slate-900 mb-3 leading-tight">
          {action.action}
        </h3>
        <p className="text-slate-700 text-lg leading-relaxed">
          {action.why}
        </p>
      </div>
      
      <div className="flex space-x-6 text-sm">
        <div className="flex items-center space-x-2">
          <span className="text-slate-600">Impact:</span>
          <div className="flex space-x-1">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className={`w-3 h-3 rounded-full ${
                  i < action.expected_impact * 5 ? 'bg-blue-500' : 'bg-slate-200'
                }`}
              />
            ))}
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          <span className="text-slate-600">Urgency:</span>
          <div className="flex space-x-1">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className={`w-3 h-3 rounded-full ${
                  i < action.urgency * 5 ? 'bg-red-500' : 'bg-slate-200'
                }`}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

const ContextInsight: React.FC<{ 
  contextSummary: string; 
  momentumInsight: string; 
  energyMatch: string; 
}> = ({ contextSummary, momentumInsight, energyMatch }) => {
  return (
    <div className="bg-blue-50 rounded-lg p-6 border border-blue-200 mb-6">
      <h3 className="text-lg font-semibold text-blue-900 mb-3">Context Analysis</h3>
      <div className="space-y-3 text-blue-800">
        <p><strong>Situation:</strong> {contextSummary}</p>
        <p><strong>Momentum:</strong> {momentumInsight}</p>
        <p><strong>Energy Match:</strong> {energyMatch}</p>
      </div>
    </div>
  );
};

const Alternatives: React.FC<{ alternatives: Alternative[] }> = ({ alternatives }) => {
  return (
    <div className="bg-white rounded-lg p-6 shadow-sm border border-slate-200 mb-6">
      <h3 className="text-lg font-semibold text-slate-900 mb-4">Alternative Actions</h3>
      <div className="space-y-4">
        {alternatives.map((alt, index) => (
          <div key={index} className="border-l-4 border-slate-300 pl-4">
            <h4 className="font-medium text-slate-900 mb-1">{alt.action}</h4>
            <p className="text-slate-600 text-sm mb-1">{alt.why}</p>
            <p className="text-slate-500 text-xs">
              Consider when: {alt.when_to_consider} • {alt.time_estimate}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};

const FeedbackCapture: React.FC<{ 
  contextId: string;
  onFeedbackSubmit: () => void;
}> = ({ contextId, onFeedbackSubmit }) => {
  const [feedbackScore, setFeedbackScore] = useState<number | null>(null);
  const [outcome, setOutcome] = useState("");
  const [actionTaken, setActionTaken] = useState("");
  const [timeSpent, setTimeSpent] = useState<number | null>(null);

  const feedbackMutation = useMutation({
    mutationFn: submitFeedback,
    onSuccess: () => {
      onFeedbackSubmit();
    },
  });

  const handleSubmit = () => {
    feedbackMutation.mutate({
      recommendation_id: contextId,
      action_taken: actionTaken || undefined,
      outcome: outcome || undefined,
      feedback_score: feedbackScore || undefined,
      time_to_complete_minutes: timeSpent || undefined,
    });
  };

  return (
    <div className="bg-white rounded-lg p-6 shadow-sm border border-slate-200">
      <h3 className="text-lg font-semibold text-slate-900 mb-4">How did it go?</h3>
      
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Was this recommendation helpful?
          </label>
          <div className="flex space-x-4">
            {[-1, 0, 1].map((score) => (
              <button
                key={score}
                onClick={() => setFeedbackScore(score)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  feedbackScore === score
                    ? score === 1 ? 'bg-green-100 text-green-800 border-green-300'
                      : score === 0 ? 'bg-yellow-100 text-yellow-800 border-yellow-300'
                      : 'bg-red-100 text-red-800 border-red-300'
                    : 'bg-slate-100 text-slate-600 border-slate-300'
                } border`}
              >
                {score === 1 ? '👍 Helpful' : score === 0 ? '😐 Neutral' : '👎 Not helpful'}
              </button>
            ))}
          </div>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            What did you actually work on? (optional)
          </label>
          <input
            type="text"
            value={actionTaken}
            onChange={(e) => setActionTaken(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            placeholder="e.g., Implemented AI Priority Engine frontend"
          />
        </div>
        
        <div className="flex space-x-4">
          <div className="flex-1">
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Outcome (optional)
            </label>
            <select
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            >
              <option value="">Select outcome</option>
              <option value="completed">Completed successfully</option>
              <option value="progress">Made progress</option>
              <option value="blocked">Got blocked</option>
              <option value="deferred">Deferred to later</option>
              <option value="skipped">Skipped entirely</option>
            </select>
          </div>
          
          <div className="flex-1">
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Time spent (minutes)
            </label>
            <input
              type="number"
              value={timeSpent || ''}
              onChange={(e) => setTimeSpent(e.target.value ? parseInt(e.target.value) : null)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
              placeholder="e.g., 120"
            />
          </div>
        </div>
        
        <button
          onClick={handleSubmit}
          disabled={feedbackMutation.isPending}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {feedbackMutation.isPending ? 'Submitting...' : 'Submit Feedback'}
        </button>
        
        {feedbackMutation.isSuccess && (
          <p className="text-green-600 text-sm text-center">Feedback submitted successfully!</p>
        )}
        
        {feedbackMutation.isError && (
          <p className="text-red-600 text-sm text-center">Failed to submit feedback</p>
        )}
      </div>
    </div>
  );
};

// Main component
const PriorityEngineContent: React.FC = () => {
  const [showFeedback, setShowFeedback] = useState(false);

  const {
    data: recommendation,
    isLoading: loadingRecommendation,
    error: recommendationError,
    refetch: refetchRecommendation
  } = useQuery({
    queryKey: ['priority-recommendation'],
    queryFn: fetchPriorityRecommendation,
    refetchOnWindowFocus: false,
  });

  const {
    data: journey,
    isLoading: loadingJourney,
    error: journeyError
  } = useQuery({
    queryKey: ['journey-state'],
    queryFn: fetchJourneyState,
    refetchOnWindowFocus: false,
  });

  const handleFeedbackSubmit = () => {
    setShowFeedback(false);
    // Optionally refetch recommendation for next action
  };

  if (loadingRecommendation || loadingJourney) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-pulse">
            <div className="w-16 h-16 bg-blue-200 rounded-full mx-auto mb-4"></div>
          </div>
          <p className="text-slate-600">Analyzing context and generating priority...</p>
        </div>
      </div>
    );
  }

  if (recommendationError || journeyError) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="text-red-500 text-6xl mb-4">⚠️</div>
          <h1 className="text-2xl font-bold text-slate-900 mb-2">Unable to Generate Priority</h1>
          <p className="text-slate-600 mb-4">
            {recommendationError?.message || journeyError?.message || 'An error occurred'}
          </p>
          <button
            onClick={() => refetchRecommendation()}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="container mx-auto px-6 py-8 max-w-4xl">
        {/* Header */}
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">AI Priority Engine</h1>
          <p className="text-slate-600">Your next action, intelligently determined</p>
        </header>

        {/* Journey Progress */}
        {journey && <JourneyProgress journey={journey} />}

        {/* Main Priority */}
        {recommendation && (
          <>
            <PriorityCard action={recommendation.primary_action} />
            
            <ContextInsight
              contextSummary={recommendation.context_summary}
              momentumInsight={recommendation.momentum_insight}
              energyMatch={recommendation.energy_match}
            />
            
            {recommendation.alternatives.length > 0 && (
              <Alternatives alternatives={recommendation.alternatives} />
            )}
            
            {/* Journey Alignment */}
            <div className="bg-green-50 rounded-lg p-6 border border-green-200 mb-6">
              <h3 className="text-lg font-semibold text-green-900 mb-2">Journey Alignment</h3>
              <p className="text-green-800">{recommendation.journey_alignment}</p>
            </div>
            
            {/* Action Buttons */}
            <div className="flex space-x-4 mb-6">
              <button
                onClick={() => setShowFeedback(!showFeedback)}
                className="flex-1 bg-slate-800 text-white py-3 px-6 rounded-lg font-medium hover:bg-slate-700 transition-colors"
              >
                {showFeedback ? 'Hide Feedback' : 'Mark Complete & Give Feedback'}
              </button>
              
              <button
                onClick={() => refetchRecommendation()}
                className="px-6 py-3 bg-white border border-slate-300 text-slate-700 rounded-lg font-medium hover:bg-slate-50 transition-colors"
              >
                Get New Recommendation
              </button>
            </div>
            
            {/* Feedback Form */}
            {showFeedback && (
              <FeedbackCapture
                contextId={recommendation.context_id}
                onFeedbackSubmit={handleFeedbackSubmit}
              />
            )}
            
            {/* Debug Info */}
            {recommendation.debug_info && (
              <details className="bg-slate-100 rounded-lg p-4 text-sm">
                <summary className="cursor-pointer font-medium text-slate-700 mb-2">
                  Debug Information
                </summary>
                <div className="text-slate-600 space-y-1">
                  <p>Actions considered: {recommendation.debug_info.total_actions_considered}</p>
                  <p>Context layers: {recommendation.debug_info.context_layers.join(', ')}</p>
                  <p>AI reasoning: {recommendation.debug_info.ai_reasoning_used ? 'Yes' : 'No'}</p>
                  <p>Generated at: {new Date(recommendation.generated_at).toLocaleString()}</p>
                </div>
              </details>
            )}
          </>
        )}
      </div>
    </div>
  );
};

// Create a query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
    },
  },
});

export default function PriorityEnginePage() {
  return (
    <QueryClientProvider client={queryClient}>
      <PriorityEngineContent />
    </QueryClientProvider>
  );
}