import { useEffect, useMemo, useState } from 'react'
import { api } from './services/api'
import type { CandidateProfile, JobOffer, Question, Score, TestState } from './services/api'
import { RecruiterDashboard } from './pages/RecruiterDashboard'
import './App.css'

type View = 'home' | 'test' | 'result' | 'profile'

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('candidate_token'))
  const [view, setView] = useState<View>('home')
  const [state, setState] = useState<TestState | null>(null)
  const [questions, setQuestions] = useState<Question[]>([])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [current, setCurrent] = useState(0)
  const [score, setScore] = useState<Score | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [clock, setClock] = useState(Date.now())
  const [role, setRole] = useState<'CANDIDATE' | 'RECRUITER' | 'ADMIN' | null>(null)
  const [offers, setOffers] = useState<JobOffer[]>([])
  const [campaignId, setCampaignId] = useState(() => localStorage.getItem('candidate_campaign') ?? '')
  const [profile, setProfile] = useState<CandidateProfile | null>(null)

  useEffect(() => {
    if (!token) return
    api.me().then((user) => {
      setRole(user.role)
      if (user.role === 'CANDIDATE') return api.offers().then((availableOffers) => {
        setOffers(availableOffers)
        return api.profile().then((candidateProfile) => {
          setProfile(candidateProfile)
          const selectedId = availableOffers.some((offer) => offer.id === campaignId) ? campaignId : availableOffers[0]?.id ?? ''
          setCampaignId(selectedId)
          if (!selectedId) return undefined
          localStorage.setItem('candidate_campaign', selectedId)
          return api.state(selectedId).then((nextState) => {
            setState(nextState)
            if (nextState.status === 'SUBMITTED') return api.result(selectedId).then((nextScore) => { setScore(nextScore); setView('result') })
            return undefined
          })
        })
      })
      return undefined
    }).catch((reason: Error) => setError(reason.message))
  }, [token])

  const currentQuestion = questions[current]
  const remaining = useMemo(() => {
    if (!state?.expires_at) return null
    return Math.max(0, Math.floor((new Date(state.expires_at).getTime() - clock) / 1000))
  }, [state?.expires_at, clock])

  useEffect(() => {
    if (view !== 'test') return
    const interval = window.setInterval(() => setClock(Date.now()), 1000)
    return () => window.clearInterval(interval)
  }, [view])

  useEffect(() => {
    if (view === 'test' && remaining === 0) void submitTest()
  }, [remaining, view])

  useEffect(() => {
    const openProfile = () => setView('profile')
    window.addEventListener('candidate-profile', openProfile)
    return () => window.removeEventListener('candidate-profile', openProfile)
  }, [])

  async function enterTest() {
    if (!campaignId) { setError('Aucune campagne active n’est disponible.'); return }
    setBusy(true); setError('')
    try {
      const next = await api.start(campaignId)
      setState(next)
      const [loadedQuestions, saved] = await Promise.all([api.questions(campaignId), api.savedAnswers(campaignId)])
      setQuestions(loadedQuestions)
      setAnswers(Object.fromEntries(Object.entries(saved).map(([id, value]) => [id, value.answer])))
      setView('test')
    } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }

  async function selectCampaign(nextCampaignId: string) {
    if (nextCampaignId === campaignId) return
    setBusy(true); setError(''); setView('home'); setQuestions([]); setAnswers({}); setScore(null); setCurrent(0)
    setCampaignId(nextCampaignId)
    localStorage.setItem('candidate_campaign', nextCampaignId)
    try {
      const nextState = await api.state(nextCampaignId)
      setState(nextState)
      if (nextState.status === 'SUBMITTED') {
        const nextScore = await api.result(nextCampaignId)
        setScore(nextScore); setView('result')
      }
    } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }

  async function saveAnswer(value: string) {
    if (!currentQuestion || !campaignId) return
    const nextAnswers = { ...answers, [currentQuestion.id]: value }
    setAnswers(nextAnswers)
    try {
      await api.answer(campaignId, currentQuestion.id, value, false)
      setState((previous) => previous ? { ...previous, answered_count: Object.keys(nextAnswers).length } : previous)
    } catch (reason) { setError((reason as Error).message) }
  }

  async function submitTest() {
    if (busy || !campaignId) return
    setBusy(true)
    try {
      const result = await api.submit(campaignId)
      setScore(result); setView('result')
      setState((previous) => previous ? { ...previous, status: 'SUBMITTED' } : previous)
    } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }

  function logout() {
    localStorage.removeItem('candidate_token'); localStorage.removeItem('candidate_campaign'); setToken(null); setRole(null); setState(null); setOffers([]); setProfile(null); setCampaignId(''); setView('home')
  }

  if (!token) return <Auth onAuthenticated={(nextToken) => { localStorage.setItem('candidate_token', nextToken); setToken(nextToken) }} />
  if (role === 'RECRUITER' || role === 'ADMIN') return <RecruiterDashboard role={role} onLogout={logout} />
  if (view === 'profile' && profile) return <ProfileView profile={profile} onSaved={setProfile} onBack={() => setView('home')} onLogout={logout} />
  if (view === 'test' && currentQuestion) return <TestView question={currentQuestion} index={current} total={questions.length} answer={answers[currentQuestion.id] ?? ''} remaining={remaining} onAnswer={saveAnswer} onJump={setCurrent} onPrevious={() => setCurrent(Math.max(0, current - 1))} onNext={() => setCurrent(Math.min(questions.length - 1, current + 1))} onSubmit={submitTest} busy={busy} error={error} />
  if (view === 'result' && score) return <ResultView score={score} onLogout={logout} />
  return <Home state={state} offers={offers} selectedCampaignId={campaignId} offer={offers.find((offer) => offer.id === campaignId)} onSelectCampaign={selectCampaign} onStart={enterTest} onLogout={logout} busy={busy} error={error} />
}

function Auth({ onAuthenticated }: { onAuthenticated: (token: string) => void }) {
  const [registerMode, setRegisterMode] = useState(false); const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [firstName, setFirstName] = useState(''); const [lastName, setLastName] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try { const result = registerMode ? await api.register(email, password, firstName, lastName) : await api.login(email, password); onAuthenticated(result.access_token) } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }
  return <main className="auth-shell"><section className="auth-copy"><p className="eyebrow">CAMPAGNE TALENTS 2026</p><h1>Montrez ce que vous savez faire.</h1><p>Une évaluation claire, équitable et conçue pour révéler vos compétences.</p></section><form className="auth-card" onSubmit={submit}><p className="eyebrow">ESPACE CANDIDAT</p><h2>{registerMode ? 'Créer votre compte' : 'Bienvenue'}</h2>{registerMode && <div className="form-row"><label>Prénom<input value={firstName} onChange={(event) => setFirstName(event.target.value)} required /></label><label>Nom<input value={lastName} onChange={(event) => setLastName(event.target.value)} required /></label></div>}<label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label>Mot de passe<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required /></label>{error && <p className="error">{error}</p>}<button className="primary-button" disabled={busy}>{busy ? 'Connexion...' : registerMode ? 'Créer le compte' : 'Se connecter'}</button><button type="button" className="link-button" onClick={() => setRegisterMode(!registerMode)}>{registerMode ? 'J’ai déjà un compte' : 'Créer un compte candidat'}</button></form></main>
}

function Header({ onLogout }: { onLogout: () => void }) { return <header className="topbar"><div className="brand"><span className="brand-mark">Q</span><span>Quorum</span></div><div className="topbar-actions"><button className="quiet-button" onClick={() => window.dispatchEvent(new Event('candidate-profile'))}>Mon profil</button><button className="quiet-button" onClick={onLogout}>Se déconnecter</button></div></header> }

function Home({ state, offers, selectedCampaignId, offer, onSelectCampaign, onStart, onLogout, busy, error }: { state: TestState | null; offers: JobOffer[]; selectedCampaignId: string; offer?: JobOffer; onSelectCampaign: (campaignId: string) => void; onStart: () => void; onLogout: () => void; busy: boolean; error: string }) {
  const submitted = state?.status === 'SUBMITTED'
  return <><Header onLogout={onLogout} /><main className="page"><div className="page-heading"><div><p className="eyebrow">VOTRE PARCOURS</p><h1>Bonjour, candidat.</h1><p className="muted">Choisissez l’offre à évaluer, puis commencez le questionnaire associé.</p></div><span className={`status ${submitted ? 'status-done' : 'status-open'}`}>{submitted ? 'Terminé' : 'À commencer'}</span></div><section className="offers-section"><div className="section-label"><p className="eyebrow">OFFRES DISPONIBLES</p><span>{offers.length} offre{offers.length > 1 ? 's' : ''}</span></div><div className="offer-list">{offers.map((availableOffer) => <button key={availableOffer.id} className={`offer-card ${availableOffer.id === selectedCampaignId ? 'selected' : ''}`} onClick={() => onSelectCampaign(availableOffer.id)} disabled={busy}><span className="offer-index">{availableOffer.id === selectedCampaignId ? '✓' : '→'}</span><span className="offer-content"><strong>{availableOffer.job_title}</strong><small>{availableOffer.name}</small></span><span className="offer-duration">{Math.round(availableOffer.duration_seconds / 60)} min</span></button>)}</div></section><section className="test-hero"><div><p className="eyebrow">ÉVALUATION SÉLECTIONNÉE</p><h2>{offer?.job_title ?? 'Sélectionnez une offre'}</h2><p className="muted">{offer?.name ?? 'Les questions apparaîtront dès que vous aurez choisi une offre.'}</p></div><div className="test-meta"><div><strong>{state?.total_questions ?? '—'}</strong><span>questions</span></div><div><strong>{offer ? `${Math.round((state?.duration_seconds ?? offer.duration_seconds) / 60)} min` : '—'}</strong><span>durée</span></div><div><strong>100</strong><span>score max</span></div></div></section>{error && <p className="error">{error}</p>}{!offer ? <div className="notice">Aucune offre active n’est disponible pour le moment.</div> : submitted ? <div className="notice">Votre test a été soumis. Votre résultat sera affiché ici lorsqu’il sera disponible.</div> : <button className="primary-button start-button" onClick={onStart} disabled={busy}>{busy ? 'Préparation...' : state?.status === 'IN_PROGRESS' ? 'Reprendre le questionnaire' : 'Commencer le questionnaire'} <span>→</span></button>}<section className="rules"><h3>Avant de commencer</h3><div className="rule-grid"><div><span>01</span><p>Le chronomètre démarre dès que vous commencez le questionnaire.</p></div><div><span>02</span><p>Vos réponses sont sauvegardées au fil de l’eau.</p></div><div><span>03</span><p>Une fois envoyé, le questionnaire ne peut plus être modifié.</p></div></div></section></main></>
}

function TestView({ question, index, total, answer, remaining, onAnswer, onJump, onPrevious, onNext, onSubmit, busy, error }: { question: Question; index: number; total: number; answer: string; remaining: number | null; onAnswer: (value: string) => void; onJump: (index: number) => void; onPrevious: () => void; onNext: () => void; onSubmit: () => void; busy: boolean; error: string }) {
  const minutes = Math.floor((remaining ?? 0) / 60).toString().padStart(2, '0'); const seconds = ((remaining ?? 0) % 60).toString().padStart(2, '0')
  return <main className="test-shell"><header className="test-topbar"><div className="brand"><span className="brand-mark">Q</span><span>Quorum</span></div><div className="timer"><span className="timer-dot" /> {minutes}:{seconds}</div></header><div className="test-layout"><aside className="question-nav"><p className="eyebrow">PROGRESSION</p>{Array.from({ length: total }, (_, item) => <button key={item} className={`question-number ${item === index ? 'active' : ''} ${item < index ? 'answered' : ''}`} onClick={() => onJump(item)}>{(item + 1).toString().padStart(2, '0')}<span>{item < index ? '✓' : item === index ? '•' : '—'}</span></button>)}</aside><section className="question-panel"><div className="question-heading"><span>Question {index + 1} / {total}</span><span>{question.category} · {question.skill}</span></div><div className="progress"><span style={{ width: `${((index + 1) / total) * 100}%` }} /></div><article><p className="question-type">CHOIX UNIQUE · {question.points} POINTS</p><h1>{question.statement}</h1><div className="options">{question.options.map((option) => <label className={`option ${answer === option.key ? 'selected' : ''}`} key={option.key}><input type="radio" name={question.id} checked={answer === option.key} onChange={() => onAnswer(option.key)} /><span className="option-key">{option.key}</span><span>{option.label}</span></label>)}</div></article>{error && <p className="error">{error}</p>}<footer className="question-actions"><button className="quiet-button" onClick={onPrevious} disabled={index === 0}>← Précédente</button>{index === total - 1 ? <button className="primary-button" onClick={onSubmit} disabled={busy}>Soumettre le test</button> : <button className="primary-button" onClick={onNext}>Question suivante <span>→</span></button>}</footer></section></div></main>
}

function ProfileView({ profile, onSaved, onBack, onLogout }: { profile: CandidateProfile; onSaved: (profile: CandidateProfile) => void; onBack: () => void; onLogout: () => void }) {
  const [phone, setPhone] = useState(profile.phone ?? '')
  const [education, setEducation] = useState(profile.education ?? '')
  const [experience, setExperience] = useState(profile.experience ?? '')
  const [location, setLocation] = useState(profile.location ?? '')
  const [availability, setAvailability] = useState(profile.availability ?? '')
  const [linkedinUrl, setLinkedinUrl] = useState(profile.linkedin_url ?? '')
  const [summary, setSummary] = useState(profile.summary ?? '')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  async function save(event: React.FormEvent) { event.preventDefault(); setBusy(true); setError(''); setMessage(''); try { onSaved(await api.updateProfile({ phone, location, availability, linkedin_url: linkedinUrl, summary, education, experience })); setMessage('Profil enregistré.') } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) } }
  async function upload(event: React.ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; if (!file) return; setBusy(true); setError(''); setMessage(''); try { const document = await api.uploadCv(file); onSaved({ ...profile, cv_name: document.original_name }); setMessage('CV téléversé avec succès.') } catch (reason) { setError((reason as Error).message) } finally { setBusy(false); event.target.value = '' } }
  return <><Header onLogout={onLogout} /><main className="page profile-page"><button className="quiet-button back-button" onClick={onBack}>← Retour au parcours</button><div className="profile-heading"><p className="eyebrow">MON DOSSIER</p><h1>Faisons connaissance.</h1><p className="muted">Un profil complet aide l’équipe à comprendre votre parcours au-delà du questionnaire.</p></div><div className="profile-grid"><section className="panel profile-card"><div className="profile-identity"><span className="profile-avatar">{profile.first_name[0]}{profile.last_name[0]}</span><div><h2>{profile.first_name} {profile.last_name}</h2><p>{profile.email}</p></div></div><form onSubmit={save}><div className="profile-form-grid"><label>Téléphone<input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="Votre numéro" /></label><label>Ville / pays<input value={location} onChange={(event) => setLocation(event.target.value)} placeholder="Tunis, Tunisie" /></label><label>Disponibilité<input value={availability} onChange={(event) => setAvailability(event.target.value)} placeholder="Ex. disponible immédiatement" /></label><label>LinkedIn<input value={linkedinUrl} onChange={(event) => setLinkedinUrl(event.target.value)} placeholder="https://linkedin.com/in/..." /></label></div><label>En quelques mots<textarea value={summary} onChange={(event) => setSummary(event.target.value)} rows={3} placeholder="Votre profil, vos objectifs, vos points forts" /></label><label>Formation<textarea value={education} onChange={(event) => setEducation(event.target.value)} rows={3} placeholder="Diplômes, établissements, spécialités" /></label><label>Expérience<textarea value={experience} onChange={(event) => setExperience(event.target.value)} rows={4} placeholder="Missions, réalisations et expériences principales" /></label>{error && <p className="error">{error}</p>}{message && <p className="notice">{message}</p>}<button className="primary-button" disabled={busy}>{busy ? 'Enregistrement...' : 'Enregistrer mon dossier'}</button></form></section><aside className="panel cv-card"><p className="eyebrow">PIÈCE JOINTE</p><h2>Votre CV</h2><p className="muted">Un document récent aide à mieux situer votre expérience.</p><div className="cv-file"><span className="cv-icon">↗</span><span>{profile.cv_name ?? 'Aucun CV ajouté'}</span></div><label className="upload-button">{busy ? 'Traitement...' : profile.cv_name ? 'Remplacer le CV' : 'Ajouter mon CV'}<input type="file" accept=".pdf,.doc,.docx,application/pdf" onChange={upload} disabled={busy} /></label></aside></div></main></>
}

function ResultView({ score, onLogout }: { score: Score; onLogout: () => void }) { return <><Header onLogout={onLogout} /><main className="page result-page"><p className="eyebrow">RÉSULTAT DE L’ÉVALUATION</p><h1>Votre score est là.</h1><section className="result-card"><div className="score-circle"><strong>{Math.round(score.normalized_score)}</strong><span>/ 100</span></div><div><p className="eyebrow">NIVEAU</p><h2>{score.level}</h2><p className="muted">Vous avez obtenu {score.earned_points} points sur {score.maximum_points}.</p></div></section><section className="breakdown"><h3>Résultats par catégorie</h3>{Object.entries(score.breakdown).map(([label, value]) => <div className="breakdown-row" key={label}><span>{label}</span><div className="bar"><i style={{ width: `${value.score}%` }} /></div><strong>{Math.round(value.score)}%</strong></div>)}</section></main></> }

export default App
