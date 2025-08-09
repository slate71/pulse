-- Migration: Create feedback table
-- Created: Initial migration
-- Description: Store user feedback on AI-generated focus actions

CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    
    -- Reference to the report/focus action
    report_date DATE NOT NULL,
    focus_action_index INTEGER NOT NULL, -- Index of the focus action (0, 1, 2)
    focus_action_text TEXT NOT NULL, -- Original AI-generated text
    
    -- User feedback
    user_id VARCHAR(255), -- User identifier (email, username, etc.)
    rating INTEGER CHECK (rating >= 1 AND rating <= 5), -- 1-5 star rating
    feedback_type VARCHAR(50) NOT NULL, -- 'helpful', 'not_helpful', 'irrelevant', 'actionable'
    comment TEXT, -- Optional user comment
    
    -- Action taken
    action_taken BOOLEAN DEFAULT FALSE, -- Did user act on this recommendation?
    action_notes TEXT, -- What action was taken?
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Metadata for learning
    ai_model_version VARCHAR(50), -- Track which model version generated this
    prompt_version VARCHAR(50), -- Track prompt variations
    context_data JSONB -- Store context that influenced the AI recommendation
);

-- Indexes for efficient querying and analytics
CREATE INDEX IF NOT EXISTS idx_feedback_report_date ON feedback(report_date);
CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(rating);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_feedback_action_taken ON feedback(action_taken);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at);

-- Index for AI model performance analysis
CREATE INDEX IF NOT EXISTS idx_feedback_model_version ON feedback(ai_model_version);
CREATE INDEX IF NOT EXISTS idx_feedback_context_gin ON feedback USING GIN (context_data);