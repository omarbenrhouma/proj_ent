const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('candidate_token')
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Une erreur est survenue.' }))
    throw new Error(body.detail ?? 'Une erreur est survenue.')
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

async function download(path: string, filename: string): Promise<void> {
  const token = localStorage.getItem('candidate_token')
  const response = await fetch(`${API_URL}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!response.ok) { const body = await response.json().catch(() => ({ detail: 'Export impossible.' })); throw new Error(body.detail ?? 'Export impossible.') }
  const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url)
}

export type TestState = {
  id: string
  status: string
  version: string
  duration_seconds: number
  started_at: string | null
  expires_at: string | null
  answered_count: number
  total_questions: number
}

export type Question = {
  id: string
  position: number
  statement: string
  question_type: string
  options: { key: string; label: string }[]
  points: number
  skill: string
  category: string
}

export type Score = {
  earned_points: number
  maximum_points: number
  normalized_score: number
  level: string
  breakdown: Record<string, { earned: number; maximum: number; score: number }>
}

export type CurrentUser = { id: string; email: string; role: 'CANDIDATE' | 'RECRUITER' | 'ADMIN' }
export type CandidateRow = { id: string; first_name: string; last_name: string; email: string; status: string; version: string; score: number | null; level: string | null; submitted_at: string | null }
export type Dashboard = { registered_candidates: number; completed_tests: number; pending_tests: number; average_score: number; best_score: number; completion_rate: number; candidates: CandidateRow[] }
export type QuestionOption = { key: string; label: string; correct: boolean }
export type AdminQuestion = { id: string; category_id: string; skill_id: string; statement: string; category: string; skill: string; difficulty: string; question_type: string; points: number; status: string; options: QuestionOption[] }
export type CandidateAnswerDetail = { position: number; statement: string; category: string; skill: string; candidate_answer: unknown; correct_answer: string[]; earned_points: number; maximum_points: number }
export type CandidateDetail = CandidateRow & { phone: string | null; education: string | null; experience: string | null; location: string | null; linkedin_url: string | null; availability: string | null; summary: string | null; breakdown: Record<string, unknown>; answers: CandidateAnswerDetail[] }
export type TestVersion = { id: string; campaign_id: string; code: string; duration_seconds: number; published: boolean; question_count: number; max_points: number }
export type JobOffer = { id: string; name: string; job_title: string; duration_seconds: number; status: string }
export type CandidateProfile = { user_id: string; first_name: string; last_name: string; email: string; phone: string | null; education: string | null; experience: string | null; location: string | null; linkedin_url: string | null; availability: string | null; summary: string | null; cv_name: string | null }
export type CvDocument = { id: string; original_name: string; mime_type: string; size_bytes: number }

export const api = {
  login: (email: string, password: string) => request<{ access_token: string }>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string, first_name: string, last_name: string) => request<{ access_token: string }>('/api/v1/auth/register', { method: 'POST', body: JSON.stringify({ email, password, first_name, last_name }) }),
  offers: () => request<JobOffer[]>('/api/v1/candidate/job-offers'),
  state: (campaignId?: string) => request<TestState>(`/api/v1/candidate/test${campaignId ? `?campaign_id=${campaignId}` : ''}`),
  start: (campaignId?: string) => request<TestState>(`/api/v1/candidate/test/start${campaignId ? `?campaign_id=${campaignId}` : ''}`, { method: 'POST' }),
  questions: (campaignId?: string) => request<Question[]>(`/api/v1/candidate/test/questions${campaignId ? `?campaign_id=${campaignId}` : ''}`),
  savedAnswers: (campaignId?: string) => request<Record<string, { answer: string; marked_for_review: boolean }>>(`/api/v1/candidate/test/answers${campaignId ? `?campaign_id=${campaignId}` : ''}`),
  answer: (campaignId: string, id: string, answer: string | string[], marked_for_review: boolean) => request<{ status: string }>(`/api/v1/candidate/test/answers/${id}?campaign_id=${campaignId}`, { method: 'PUT', body: JSON.stringify({ answer, marked_for_review }) }),
  submit: (campaignId: string) => request<Score>(`/api/v1/candidate/test/submit?campaign_id=${campaignId}`, { method: 'POST' }),
  result: (campaignId: string) => request<Score>(`/api/v1/candidate/result?campaign_id=${campaignId}`),
  me: () => request<CurrentUser>('/api/v1/auth/me'),
  dashboard: () => request<Dashboard>('/api/v1/recruiter/dashboard'),
  exportCandidates: () => download('/api/v1/recruiter/export.csv', 'resultats-candidats.csv'),
  adminQuestions: () => request<AdminQuestion[]>('/api/v1/admin/questions'),
  candidateDetail: (id: string) => request<CandidateDetail>(`/api/v1/recruiter/candidates/${id}`),
  downloadCandidateCv: (id: string) => download(`/api/v1/recruiter/cv/${id}`, 'cv-candidat'),
  updateCandidate: (id: string, payload: { first_name: string; last_name: string; email: string; phone?: string | null; education?: string | null; experience?: string | null }) => request<CandidateDetail>(`/api/v1/recruiter/candidates/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deactivateCandidate: (id: string) => request<void>(`/api/v1/recruiter/candidates/${id}`, { method: 'DELETE' }),
  createQuestion: (payload: unknown) => request<AdminQuestion>('/api/v1/admin/questions', { method: 'POST', body: JSON.stringify(payload) }),
  updateQuestion: (id: string, payload: unknown) => request<AdminQuestion>(`/api/v1/admin/questions/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  archiveQuestion: (id: string) => request<void>(`/api/v1/admin/questions/${id}`, { method: 'DELETE' }),
  archiveQuestions: (questionIds: string[]) => request<{ archived: number }>('/api/v1/admin/questions/archive', { method: 'POST', body: JSON.stringify({ question_ids: questionIds }) }),
  importQuestions: async (file: File) => { const token = localStorage.getItem('candidate_token'); const data = new FormData(); data.append('file', file); const response = await fetch(`${API_URL}/api/v1/admin/questions/import`, { method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}, body: data }); if (!response.ok) { const body = await response.json().catch(() => ({ detail: 'Import impossible.' })); throw new Error(body.detail ?? 'Import impossible.') } return response.json() as Promise<{ imported: number }> },
  profile: () => request<CandidateProfile>('/api/v1/candidate/profile'),
  updateProfile: (payload: Partial<Pick<CandidateProfile, 'phone' | 'education' | 'experience' | 'location' | 'linkedin_url' | 'availability' | 'summary'>>) => request<CandidateProfile>('/api/v1/candidate/profile', { method: 'PUT', body: JSON.stringify(payload) }),
  uploadCv: async (file: File) => {
    const token = localStorage.getItem('candidate_token')
    const response = await fetch(`${API_URL}/api/v1/candidate/cv`, { method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}, body: (() => { const data = new FormData(); data.append('file', file); return data })() })
    if (!response.ok) { const body = await response.json().catch(() => ({ detail: 'Upload impossible.' })); throw new Error(body.detail ?? 'Upload impossible.') }
    return response.json() as Promise<CvDocument>
  },
  validateQuestion: (id: string) => request<AdminQuestion>(`/api/v1/admin/questions/${id}/validate`, { method: 'POST' }),
  versions: () => request<TestVersion[]>('/api/v1/admin/test-versions'),
  createVersion: (payload: { campaign_id: string; code: string; duration_seconds: number }) => request<TestVersion>('/api/v1/admin/test-versions', { method: 'POST', body: JSON.stringify(payload) }),
  deleteVersion: (id: string) => request<void>(`/api/v1/admin/test-versions/${id}`, { method: 'DELETE' }),
  setVersionQuestions: (id: string, question_ids: string[]) => request<TestVersion>(`/api/v1/admin/test-versions/${id}/questions`, { method: 'PUT', body: JSON.stringify({ question_ids }) }),
  publishVersion: (id: string) => request<TestVersion>(`/api/v1/admin/test-versions/${id}/publish`, { method: 'POST' }),
}
