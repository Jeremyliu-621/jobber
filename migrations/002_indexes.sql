CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_company_title ON jobs(company, title);
CREATE INDEX IF NOT EXISTS idx_job_criteria_job ON job_criteria(job_id);
CREATE INDEX IF NOT EXISTS idx_job_evaluations_job_created ON job_evaluations(job_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_application_questions_application ON application_questions(application_id);
CREATE INDEX IF NOT EXISTS idx_application_answers_question ON application_answers(question_id);
CREATE INDEX IF NOT EXISTS idx_application_events_application_created ON application_events(application_id, created_at);
