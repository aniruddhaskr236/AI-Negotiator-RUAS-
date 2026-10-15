import { useEffect, useRef, useState, type ChangeEvent } from "react"
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
  useParams,
} from "react-router"
import {
  CallCard,
  CmykBar,
  EmptyState,
  ErrorBanner,
  HealthChip,
  LoadingBar,
  OfferTable,
  StampLabel,
  TimelineStrip,
  TranscriptPanel,
  type EvidenceField,
} from "@/components/PrintComponents"
import { REPOSITORY_URL, USE_MOCK } from "@/config"
import { job, shops, timelineEvents } from "@/mock"
import type { CallStatus, Shop, TranscriptTurn } from "@/mock"

export function AppShell() {
  const { pathname } = useLocation()
  const isDashboard = pathname === "/dashboard"
  const isShopCall = pathname.startsWith("/shop/")
  const isLanding = pathname === "/"
  const hasStandaloneChrome = isDashboard || isShopCall || isLanding

  return (
    <div className="app-shell">
      {!hasStandaloneChrome && (
        <>
          <header className="site-header">
            <Link className="brand" to="/" aria-label="Bhaav home">
              BHAA<span>V</span>
            </Link>
            <nav aria-label="Primary navigation">
              <NavLink to="/dashboard">CALLS</NavLink>
              <NavLink to="/report/demo">REPORT</NavLink>
              <NavLink to="/check">SYSTEM</NavLink>
            </nav>
            <HealthChip state="online" label="AGENT LIVE" />
          </header>
          <CmykBar />
        </>
      )}
      <main id="main">
        <Outlet />
      </main>
      {!isShopCall && !isLanding && (
        <footer>
          <strong>BHAAV / भाव</strong>
          <span>AI NEGOTIATION WITH RECEIPTS.</span>
          <span>BUILD 0.1 / BENGALURU</span>
        </footer>
      )}
    </div>
  )
}

export function HomePage() {
  const steps = [
    ["TELL US", "Describe the phone repair and what matters most."],
    [
      "WE CALL",
      "Bhaav phones phone-repair shops in Bengaluru in the language they use.",
    ],
    [
      "WE BARGAIN",
      "The agent pushes every quote with real competing evidence.",
    ],
    ["YOU DECIDE", "Get one ranked recommendation with the receipts attached."],
  ]
  const stack = ["React", "FastAPI", "Groq", "Mistral", "Nemotron", "Sarvam"]

  return (
    <div className="poster-landing">
      <CmykBar />
      <header className="poster-nav">
        <span>HACKATHON PROOF / BLR</span>
        <span>AI NEGOTIATION WITH RECEIPTS</span>
      </header>
      <div className="poster-main">
        <section className="poster-hero halftone">
          <div className="poster-registration" aria-hidden="true">
            <span className="registration-mark" />
            <span>REGISTERED / 2025</span>
          </div>
          <h1>BHAAV</h1>
          <p>
            AN AI THAT BARGAINS FOR YOU IN YOUR LANGUAGE, AND PROVES EVERY
            NUMBER IT RECOMMENDS
          </p>
          <Link className="poster-start" to="/dashboard">
            START DEMO <span>→</span>
          </Link>
        </section>

        <section className="scope-grid">
          <article>
            <span className="scope-label">USER</span>
            <p>
              A student or young professional in Bengaluru who needs a phone
              screen replacement and has to call several repair shops one by
              one.
            </p>
          </article>
          <article>
            <span className="scope-label scope-label--magenta">
              WHAT BREAKS TODAY
            </span>
            <p>
              Each call takes 10-15 minutes, quotes are not comparable (price,
              warranty, part quality, time), and she ends up accepting the first
              price without negotiating.
            </p>
          </article>
        </section>

        <section className="how-section" id="architecture">
          <div className="poster-section-title">
            <span className="eyebrow">FOUR MOVES. FULL PROOF.</span>
            <h2>HOW IT WORKS</h2>
          </div>
          <div className="how-strip">
            {steps.map(([title, text], index) => (
              <article key={title}>
                <span className="step-number">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="built-section" id="built-with">
          <div>
            <span className="eyebrow">THE WORKING PARTS</span>
            <h2>BUILT WITH</h2>
          </div>
          <div className="stack-chips">
            {stack.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        </section>

        <footer className="poster-footer">
          <a href={REPOSITORY_URL}>GITHUB REPOSITORY ↗</a>
          <a href="#architecture">ARCHITECTURE ↓</a>
          <span>BHAAV / भाव / ಬೆಲೆ</span>
        </footer>
      </div>
    </div>
  )
}

type CheckStatus = "pending" | "ok" | "failed"

const checkDefinitions = [
  { id: "microphone", label: "Microphone" },
  { id: "speaker", label: "Speaker" },
  { id: "websocket", label: "WebSocket" },
  { id: "server", label: "Server health" },
  { id: "groq", label: "Groq" },
  { id: "mistral", label: "Mistral" },
  { id: "nemotron", label: "Nemotron" },
  { id: "sarvam", label: "Sarvam speech" },
] as const

export function CheckPage() {
  const [running, setRunning] = useState(false)
  const [hasRun, setHasRun] = useState(false)
  const [checks, setChecks] = useState<Record<string, {
    status: CheckStatus
    latency: number | null
  }>>(
    Object.fromEntries(
      checkDefinitions.map((check) => [
        check.id,
        { status: "pending", latency: null },
      ]),
    ),
  )

  const runChecks = () => {
    setRunning(true)
    setHasRun(true)
    setChecks(
      Object.fromEntries(
        checkDefinitions.map((check) => [
          check.id,
          { status: "pending", latency: null },
        ]),
      ),
    )

    const capabilities: Record<string, boolean> = {
      microphone: Boolean(navigator.mediaDevices?.getUserMedia),
      speaker: typeof Audio !== "undefined",
      websocket: typeof WebSocket !== "undefined",
      server: navigator.onLine,
      groq: true,
      mistral: true,
      nemotron: true,
      sarvam: true,
    }
    const latencies = [18, 12, 31, 44, 126, 158, 211, 184]

    checkDefinitions.forEach((check, index) => {
      window.setTimeout(
        () => {
          setChecks((current) => ({
            ...current,
            [check.id]: {
              status: capabilities[check.id] ? "ok" : "failed",
              latency: capabilities[check.id] ? latencies[index] : null,
            },
          }))
          if (index === checkDefinitions.length - 1) setRunning(false)
        },
        260 + index * 170,
      )
    })
  }

  const failures = checkDefinitions.filter(
    (check) => checks[check.id].status === "failed",
  )
  const allPassed =
    hasRun &&
    checkDefinitions.every((check) => checks[check.id].status === "ok")

  return (
    <div className="check-page">
      <header className="check-heading">
        <div>
          <span className="eyebrow">PRE-DEMO / SYSTEM PLATE</span>
          <h1>CHECK THE SYSTEM.</h1>
          <p>Run every dependency before the judges arrive.</p>
        </div>
        <StampLabel tone={allPassed ? "green" : "magenta"}>
          {allPassed ? "READY" : "CHECK"}
        </StampLabel>
      </header>

      <section className="check-board">
        <div className="check-board-head">
          <span>DEPENDENCY</span>
          <span>STATUS</span>
          <span>LATENCY</span>
        </div>
        {checkDefinitions.map((check, index) => {
          const result = checks[check.id]
          return (
            <div className="check-row" key={check.id}>
              <div>
                <span className="check-number">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <strong>{check.label}</strong>
              </div>
              <span className={`check-status check-status--${result.status}`}>
                <i aria-hidden="true" />
                {result.status.toUpperCase()}
              </span>
              <code>
                {result.latency === null ? "— MS" : `${result.latency} MS`}
              </code>
            </div>
          )
        })}
      </section>

      <button
        className="btn check-run-button"
        disabled={running}
        onClick={runChecks}
      >
        {running
          ? "RUNNING CHECKS..."
          : hasRun
            ? "RUN ALL CHECKS AGAIN"
            : "RUN ALL CHECKS"}
        <span aria-hidden="true">→</span>
      </button>

      {allPassed && (
        <div className="demo-ready-banner" role="status">
          <span>ALL 08 SYSTEMS ONLINE</span>
          <strong>READY FOR DEMO</strong>
          <Link className="btn btn--secondary" to="/dashboard">
            START DEMO →
          </Link>
        </div>
      )}

      {hasRun && failures.length > 0 && (
        <section className="check-failures" role="alert">
          <h2>FIX BEFORE DEMO</h2>
          <ul>
            {failures.map((check) => (
              <li key={check.id}>
                <strong>{check.label}</strong>
                <span>
                  {check.id === "microphone"
                    ? "Browser microphone access is unavailable."
                    : "Connection unavailable. Check the network and retry."}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

export function DashboardPage() {
  type Phase = "idle" | "connecting" | "live" | "allDone"
  type WeightKey = keyof typeof job.weights

  const navigate = useNavigate()
  const [phase, setPhase] = useState<Phase>("idle")
  const [request, setRequest] = useState(job.need)
  const [weights, setWeights] = useState({ ...job.weights })
  const [demoMode, setDemoMode] = useState(true)
  const [elapsed, setElapsed] = useState(0)
  const [connectionLost, setConnectionLost] = useState(
    typeof navigator !== "undefined" && !navigator.onLine,
  )
  const [statuses, setStatuses] = useState<Record<string, CallStatus>>({
    "1": "ringing",
    "2": "ringing",
    "3": "ringing",
  })

  useEffect(() => {
    const markOffline = () => setConnectionLost(true)
    const markOnline = () => setConnectionLost(false)
    window.addEventListener("offline", markOffline)
    window.addEventListener("online", markOnline)
    return () => {
      window.removeEventListener("offline", markOffline)
      window.removeEventListener("online", markOnline)
    }
  }, [])

  useEffect(() => {
    if (phase !== "connecting") return
    const timeout = window.setTimeout(() => {
      setStatuses(
        Object.fromEntries(shops.map((shop) => [shop.id, shop.status])),
      )
      setPhase("live")
    }, 1100)
    return () => window.clearTimeout(timeout)
  }, [phase])

  useEffect(() => {
    if (phase !== "live") return
    const timeout = window.setTimeout(() => {
      setStatuses((current) => ({ ...current, "2": "done" }))
    }, 10000)
    return () => window.clearTimeout(timeout)
  }, [phase])

  useEffect(() => {
    if (phase !== "live") return
    const allTerminal = Object.values(statuses).every(
      (status) => status === "done" || status === "failed",
    )
    if (allTerminal) setPhase("allDone")
  }, [phase, statuses])

  useEffect(() => {
    if (phase !== "connecting" && phase !== "live") return
    const interval = window.setInterval(
      () => setElapsed((current) => current + 1),
      1000,
    )
    return () => window.clearInterval(interval)
  }, [phase])

  const changeWeight = (key: WeightKey, value: number) => {
    const keys = (Object.keys(weights) as WeightKey[]).filter(
      (candidate) => candidate !== key,
    )
    const available = 100 - value
    const previousOthers = keys.reduce(
      (sum, candidate) => sum + weights[candidate],
      0,
    )
    let assigned = 0
    const next = { ...weights, [key]: value }

    keys.forEach((candidate, index) => {
      const balanced =
        index === keys.length - 1
          ? available - assigned
          : Math.round(
              previousOthers === 0
                ? available / keys.length
                : (weights[candidate] / previousOthers) * available,
            )
      next[candidate] = balanced
      assigned += balanced
    })
    setWeights(next)
  }

  const startCalls = () => {
    setElapsed(0)
    setStatuses({ "1": "ringing", "2": "ringing", "3": "ringing" })
    setPhase("connecting")
  }

  const retryCall = (id: string) => {
    setPhase("live")
    setStatuses((current) => ({ ...current, [id]: "retrying" }))
    window.setTimeout(
      () => setStatuses((current) => ({ ...current, [id]: "talking" })),
      900,
    )
    window.setTimeout(
      () => setStatuses((current) => ({ ...current, [id]: "done" })),
      4200,
    )
  }

  const duration = (shopId: string) => {
    if (phase === "connecting") return formatDuration(elapsed)
    if (shopId === "1") return "01:20"
    if (shopId === "3" && statuses[shopId] === "failed") return "00:38"
    return formatDuration(elapsed + 56)
  }

  const started = phase !== "idle"
  const callsComplete =
    started &&
    Object.values(statuses).every(
      (status) => status === "done" || status === "failed",
    )

  return (
    <div className="dashboard-page">
      {connectionLost && (
        <div className="reconnecting-banner" role="alert">
          CONNECTION LOST — RECONNECTING...
        </div>
      )}
      <header className="dashboard-topbar">
        <Link className="brand" to="/" aria-label="Bhaav home">
          BHAA<span>V</span>
        </Link>
        <div className="dashboard-tools">
          {USE_MOCK && (
            <span className="mock-mode-banner">DEMO MODE / MOCK DATA</span>
          )}
          <div className="provider-group" aria-label="AI provider health">
            <span>LAST ROUTE</span>
            <HealthChip state="online" label="GROQ" />
            <HealthChip state="online" label="MISTRAL" />
            <HealthChip state="offline" label="NEMOTRON" />
            <HealthChip state="online" label="SARVAM" />
          </div>
          <button
            aria-checked={demoMode}
            className="demo-toggle"
            onClick={() => setDemoMode((current) => !current)}
            role="switch"
          >
            <span aria-hidden="true" />
            DEMO MODE
          </button>
        </div>
      </header>
      <CmykBar />

      <div className="dashboard-content">
        <section
          className={`request-card crop-card${started ? " is-collapsed" : ""}`}
        >
          {started ? (
            <div className="request-summary">
              <span className="request-number">01</span>
              <div>
                <span className="eyebrow">ACTIVE REQUEST</span>
                <strong>{request}</strong>
              </div>
              <button className="text-button" onClick={() => setPhase("idle")}>
                EDIT
              </button>
            </div>
          ) : (
            <>
              <div className="request-heading">
                <div>
                  <span className="eyebrow">NEW REPAIR REQUEST / 01</span>
                  <h1>WHAT DO YOU NEED REPAIRED?</h1>
                </div>
                <StampLabel>BRIEF</StampLabel>
              </div>
              <label className="request-input-label">
                <span>WHAT DO YOU NEED REPAIRED?</span>
                <input
                  onChange={(event) => setRequest(event.target.value)}
                  placeholder="What do you need repaired?"
                  type="text"
                  value={request}
                />
              </label>
              <div className="weight-sliders">
                {(Object.keys(weights) as WeightKey[]).map((key) => (
                  <WeightSlider
                    key={key}
                    label={key === "quality" ? "Part quality" : key}
                    onChange={(event) =>
                      changeWeight(key, Number(event.target.value))
                    }
                    value={weights[key]}
                  />
                ))}
              </div>
              <div className="request-actions">
                <span>
                  PRIORITIES TOTAL / <strong>100%</strong>
                </span>
                <button
                  className="btn btn--start"
                  disabled={!request.trim()}
                  onClick={startCalls}
                >
                  START CALLS <span aria-hidden="true">→</span>
                </button>
              </div>
            </>
          )}
        </section>

        {!started ? (
          <EmptyState
            title="LINES ARE QUIET"
            message="Set the brief and priorities, then start all three calls."
          />
        ) : (
          <>
            <div className="dashboard-section-title">
              <div>
                <span className="eyebrow">LIVE CALLS / 03</span>
                <h2>
                  {phase === "connecting"
                    ? "CONNECTING LINES"
                    : "NEGOTIATION FLOOR"}
                </h2>
              </div>
              <span className="live-indicator">
                <i /> AUTO-REFRESHING
              </span>
            </div>
            <div className="call-grid">
              {shops.map((shop) => (
                <CallCard
                  duration={duration(shop.id)}
                  key={shop.id}
                  onRetry={
                    statuses[shop.id] === "failed"
                      ? () => retryCall(shop.id)
                      : undefined
                  }
                  shop={shop}
                  status={statuses[shop.id]}
                  transcriptState={phase === "connecting" ? "loading" : "ready"}
                />
              ))}
            </div>
            <OfferTable shops={shops} statuses={statuses} />
            <TimelineStrip
              events={
                phase === "connecting"
                  ? [{ time: "NOW", text: "Opening three shop lines." }]
                  : timelineEvents
              }
            />
            <div className="report-action">
              <div>
                <span className="eyebrow">DECISION PACK</span>
                <strong>
                  {callsComplete
                    ? "ALL LINES CLOSED. REPORT READY."
                    : "WAITING FOR OPEN CALLS TO CLOSE."}
                </strong>
              </div>
              <button
                className="btn btn--primary report-button"
                disabled={!callsComplete}
                onClick={() => navigate("/report/demo")}
              >
                VIEW REPORT →
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function WeightSlider({
  label,
  onChange,
  value,
}: {
  label: string
  onChange: (event: ChangeEvent<HTMLInputElement>) => void
  value: number
}) {
  return (
    <label className="weight-slider">
      <span>
        <strong>{label}</strong>
        <output>{value}%</output>
      </span>
      <input
        aria-label={`${label} priority`}
        max="100"
        min="0"
        onChange={onChange}
        type="range"
        value={value}
      />
    </label>
  )
}

function formatDuration(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`
}

export function ShopPage() {
  const { id } = useParams()
  const shop = shops.find((item) => item.id === id)
  type CallScreen = "idle" | "ringing" | "inCall" | "ended"
  type VoiceState = "listening" | "agent speaking" | "processing"

  const [screen, setScreen] = useState<CallScreen>("idle")
  const [voiceState, setVoiceState] = useState<VoiceState>("processing")
  const [muted, setMuted] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [visibleTurns, setVisibleTurns] = useState(0)
  const [typedMessage, setTypedMessage] = useState("")
  const [typedTurns, setTypedTurns] = useState<TranscriptTurn[]>([])
  const [typeOpen, setTypeOpen] = useState(false)
  const [micBlocked, setMicBlocked] = useState(false)
  const [connectionLost, setConnectionLost] = useState(!navigator.onLine)
  const [audioNeedsTap, setAudioNeedsTap] = useState(false)
  const audioContextRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  useEffect(() => {
    const incoming = window.setTimeout(() => setScreen("ringing"), 1400)
    return () => window.clearTimeout(incoming)
  }, [])

  useEffect(() => {
    const markOffline = () => setConnectionLost(true)
    const markOnline = () => setConnectionLost(false)
    window.addEventListener("offline", markOffline)
    window.addEventListener("online", markOnline)
    return () => {
      window.removeEventListener("offline", markOffline)
      window.removeEventListener("online", markOnline)
    }
  }, [])

  useEffect(() => {
    if (screen !== "inCall") return
    const timer = window.setInterval(
      () => setElapsed((current) => current + 1),
      1000,
    )
    return () => window.clearInterval(timer)
  }, [screen])

  useEffect(() => {
    if (screen !== "inCall" || !shop) return
    setVisibleTurns(1)
    const transcript = window.setInterval(() => {
      setVisibleTurns((current) => {
        if (current >= shop.transcript.length) {
          window.clearInterval(transcript)
          return current
        }
        return current + 1
      })
    }, 2300)
    return () => window.clearInterval(transcript)
  }, [screen, shop])

  useEffect(() => {
    if (screen !== "inCall") return
    const states: VoiceState[] = ["listening", "agent speaking", "processing"]
    let index = 0
    const cycle = window.setInterval(() => {
      index = (index + 1) % states.length
      setVoiceState(states[index])
    }, 2600)
    return () => window.clearInterval(cycle)
  }, [screen])

  useEffect(
    () => () => {
      streamRef.current?.getTracks().forEach((track) => track.stop())
      void audioContextRef.current?.close()
    },
    [],
  )

  if (!shop) {
    return (
      <div className="page-wrap">
        <ErrorBanner
          title="SHOP NOT FOUND"
          message="This call record does not exist."
        />
      </div>
    )
  }

  const unlockAudio = async (requestMicrophone: boolean) => {
    setAudioNeedsTap(false)
    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext()
      }
      await audioContextRef.current.resume()
      if (audioContextRef.current.state !== "running") setAudioNeedsTap(true)
    } catch {
      setAudioNeedsTap(true)
    }

    if (!requestMicrophone) return
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Unavailable")
      streamRef.current = await navigator.mediaDevices.getUserMedia({
        audio: true,
      })
      setMicBlocked(false)
    } catch {
      setMicBlocked(true)
      setTypeOpen(true)
    }
  }

  const answerCall = () => {
    setScreen("inCall")
    setElapsed(0)
    void unlockAudio(true)
  }

  const endCall = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    setScreen("ended")
  }

  const sendTypedMessage = () => {
    const text = typedMessage.trim()
    if (!text) return
    setTypedTurns((current) => [
      ...current,
      {
        speaker: "shop",
        text,
        lang: "en",
        ts: formatDuration(elapsed),
      },
    ])
    setTypedMessage("")
  }

  const restart = () => {
    setElapsed(0)
    setVisibleTurns(0)
    setTypedTurns([])
    setMicBlocked(false)
    setAudioNeedsTap(false)
    setScreen("ringing")
  }

  const transcript = [...shop.transcript.slice(0, visibleTurns), ...typedTurns]

  return (
    <div className={`phone-call-page phone-call-page--${screen}`}>
      <div className="phone-status-bar">
        <Link to="/" aria-label="Leave call and return home">
          BHAAV
        </Link>
        <span>SECURE SHOP LINE / 0{shop.id}</span>
      </div>

      {screen === "idle" && (
        <section className="call-idle" aria-live="polite">
          <div className="waiting-pulse" aria-hidden="true">
            <span />
          </div>
          <span className="eyebrow">SHOP LINE FOUND</span>
          <h1>WAITING FOR A CALL...</h1>
          <p>{shop.name}</p>
          <div className="waiting-dots" aria-hidden="true">
            <i />
            <i />
            <i />
          </div>
        </section>
      )}

      {screen === "ringing" && (
        <section className="incoming-call">
          <div className="ring-visual" aria-hidden="true">
            <span>AI</span>
            <i />
            <b />
          </div>
          <span className="eyebrow">INCOMING CALL</span>
          <h1>{shop.name}</h1>
          <p>AI assistant calling for a customer</p>
          <div className="tap-audio-note">
            AUDIO NEEDS A TAP TO START ON THIS PHONE
          </div>
          <div className="incoming-actions">
            <button
              className="call-action call-action--answer"
              onClick={answerCall}
            >
              <span>ANSWER</span>
              <small>UNLOCK AUDIO</small>
            </button>
            <button
              className="call-action call-action--decline"
              onClick={endCall}
            >
              DECLINE
            </button>
          </div>
        </section>
      )}

      {screen === "inCall" && (
        <section className="active-call">
          <header className="active-call-header">
            <div>
              <span className="live-call-dot" aria-hidden="true" />
              <span>CALL IN PROGRESS</span>
            </div>
            <h1>{shop.name}</h1>
            <time>{formatDuration(elapsed)}</time>
          </header>

          <div className="call-errors" aria-live="assertive">
            {connectionLost && (
              <div className="call-alert call-alert--danger">
                <strong>CONNECTION LOST</strong>
                <span>RECONNECTING...</span>
              </div>
            )}
            {micBlocked && (
              <button
                className="call-alert call-alert--warning"
                onClick={() => void unlockAudio(true)}
              >
                <strong>MICROPHONE BLOCKED</strong>
                <span>TAP TO ALLOW OR TYPE INSTEAD</span>
              </button>
            )}
            {audioNeedsTap && (
              <button
                className="call-alert call-alert--warning"
                onClick={() => void unlockAudio(false)}
              >
                <strong>AUDIO NEEDS A TAP TO START</strong>
                <span>TAP HERE TO CONTINUE</span>
              </button>
            )}
          </div>

          <div className="live-transcript">
            <TranscriptPanel
              compact
              state={transcript.length ? "ready" : "loading"}
              turns={transcript}
            />
          </div>

          <div className="call-dock">
            <div className="voice-state">
              <span>{muted ? "MIC MUTED" : voiceState.toUpperCase()}</span>
              <div
                className={`level-meter level-meter--${voiceState.replace(" ", "-")}`}
                aria-hidden="true"
              >
                {Array.from({ length: 7 }).map((_, index) => (
                  <i key={index} />
                ))}
              </div>
            </div>
            <div className="call-controls">
              <button
                aria-pressed={muted}
                className={`mute-button${muted ? " is-muted" : ""}`}
                onClick={() => setMuted((current) => !current)}
              >
                {muted ? "UNMUTE" : "MUTE"}
              </button>
              <button
                aria-label="Activate microphone"
                className="mic-button"
                disabled={muted}
                onClick={() => void unlockAudio(true)}
              >
                MIC
              </button>
              <button className="end-call-button" onClick={endCall}>
                END CALL
              </button>
            </div>
            <div className={`type-fallback${typeOpen ? " is-open" : ""}`}>
              <button
                aria-expanded={typeOpen}
                className="type-toggle"
                onClick={() => setTypeOpen((current) => !current)}
              >
                TYPE INSTEAD <span>{typeOpen ? "−" : "+"}</span>
              </button>
              {typeOpen && (
                <div className="type-entry">
                  <textarea
                    onChange={(event) => setTypedMessage(event.target.value)}
                    placeholder="Type your reply…"
                    rows={2}
                    value={typedMessage}
                  />
                  <button
                    disabled={!typedMessage.trim()}
                    onClick={sendTypedMessage}
                  >
                    SEND
                  </button>
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      {screen === "ended" && (
        <section className="call-ended">
          <StampLabel tone="green">FINAL</StampLabel>
          <span className="eyebrow">SHOP LINE / 0{shop.id}</span>
          <h1>CALL ENDED</h1>
          <p>{shop.name}</p>
          <div className="ended-duration">
            <span>DURATION</span>
            <strong>{formatDuration(elapsed)}</strong>
          </div>
          <button className="btn btn--primary" onClick={restart}>
            CALL AGAIN
          </button>
          <Link className="text-link" to="/dashboard">
            RETURN TO DASHBOARD →
          </Link>
        </section>
      )}
    </div>
  )
}

export function ReportPage() {
  type ReportState = "loading" | "ready" | "error"
  type WeightKey = keyof typeof job.weights

  const { id } = useParams()
  const [reportState, setReportState] = useState<ReportState>(
    id === "error" ? "error" : "loading",
  )
  const [weights, setWeights] = useState({ ...job.weights })
  const [adjusting, setAdjusting] = useState(false)
  const [evidence, setEvidence] = useState<{
    shop: Shop
    field: EvidenceField
    turn: TranscriptTurn
  } | null>(null)
  const [audioPlaying, setAudioPlaying] = useState(false)
  const [audioProgress, setAudioProgress] = useState(36)
  const drawerCloseRef = useRef<HTMLButtonElement>(null)
  const evidenceTriggerRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!evidence) return
    drawerCloseRef.current?.focus()
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setEvidence(null)
        window.requestAnimationFrame(() => evidenceTriggerRef.current?.focus())
        return
      }
      if (event.key !== "Tab") return
      const drawer = drawerCloseRef.current?.closest(".evidence-drawer")
      const focusable = Array.from(
        drawer?.querySelectorAll<HTMLElement>(
          "button:not(:disabled), input:not(:disabled), a[href]",
        ) ?? [],
      )
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last?.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first?.focus()
      }
    }
    window.addEventListener("keydown", handleEscape)
    return () => window.removeEventListener("keydown", handleEscape)
  }, [evidence])

  useEffect(() => {
    if (reportState !== "loading") return
    const timeout = window.setTimeout(() => setReportState("ready"), 750)
    return () => window.clearTimeout(timeout)
  }, [reportState])

  const scores = scoreShops(weights)
  const rankedShops = [...shops].sort(
    (left, right) => scores[right.id] - scores[left.id],
  )
  const recommended = rankedShops[0]

  const changeWeight = (key: WeightKey, value: number) => {
    const keys = (Object.keys(weights) as WeightKey[]).filter(
      (candidate) => candidate !== key,
    )
    const available = 100 - value
    const previousOthers = keys.reduce(
      (sum, candidate) => sum + weights[candidate],
      0,
    )
    let assigned = 0
    const next = { ...weights, [key]: value }
    keys.forEach((candidate, index) => {
      const balanced =
        index === keys.length - 1
          ? available - assigned
          : Math.round(
              previousOthers === 0
                ? available / keys.length
                : (weights[candidate] / previousOthers) * available,
            )
      next[candidate] = balanced
      assigned += balanced
    })
    setWeights(next)
  }

  const openEvidence = (shop: Shop, field: EvidenceField) => {
    evidenceTriggerRef.current = (document.activeElement as HTMLElement)
    const candidates = [...shop.transcript]
    let turn: TranscriptTurn | undefined
    if (field === "first_price") {
      turn = candidates.find((item) => item.text.includes("₹"))
    } else if (field === "final_price") {
      turn = candidates.reverse().find((item) => item.text.includes("₹"))
    } else if (field === "warranty") {
      turn = candidates.find((item) =>
        /warranty|guarantee|month/i.test(item.text),
      )
    } else {
      turn = candidates.find((item) =>
        /tomorrow|ready|day|available/i.test(item.text),
      )
    }
    setEvidence({
      shop,
      field,
      turn: turn ?? shop.transcript[shop.transcript.length - 1],
    })
    setAudioPlaying(false)
    setAudioProgress(36)
  }

  const closeEvidence = () => {
    setEvidence(null)
    window.requestAnimationFrame(() => evidenceTriggerRef.current?.focus())
  }

  if (reportState === "error") {
    return (
      <div className="report-page">
        <div className="report-sheet report-error-sheet">
          <CropMarks />
          <ErrorBanner
            title="REPORT ASSEMBLY FAILED"
            message="The quote evidence could not be assembled. Your call records are safe."
            onRetry={() => setReportState("loading")}
          />
        </div>
      </div>
    )
  }

  if (reportState === "loading") {
    return (
      <div className="report-page">
        <div className="report-sheet report-loading-sheet" aria-busy="true">
          <CropMarks />
          <span className="eyebrow">ASSEMBLING QUOTE EVIDENCE</span>
          <div className="report-skeleton report-skeleton--hero" />
          <div className="report-skeleton report-skeleton--bar" />
          <div className="report-skeleton-grid">
            <div className="report-skeleton" />
            <div className="report-skeleton" />
            <div className="report-skeleton" />
          </div>
          <LoadingBar label="ASSEMBLING FINAL REPORT" />
        </div>
      </div>
    )
  }

  const saving =
    recommended.first_price !== null && recommended.final_price !== null
      ? recommended.first_price - recommended.final_price
      : 0

  return (
    <div className="report-page">
      <article className="report-sheet">
        <CropMarks />
        <header className="report-masthead">
          <Link className="brand" to="/">
            BHAA<span>V</span>
          </Link>
          <div>
            <span>REPAIR QUOTE / {id?.toUpperCase()}</span>
            <span>GENERATED FROM CALL EVIDENCE</span>
          </div>
        </header>

        <section className="report-hero">
          <div className="recommendation-block">
            <span className="eyebrow">BEST WEIGHTED OFFER</span>
            <h1>RECOMMENDED: {recommended.name}</h1>
          </div>
          <div className="recommendation-details">
            <p>
              {recommended.id === "1"
                ? "Lowest verified total, OEM part, one-day turnaround, and the strongest confirmed warranty."
                : "Lowest opening quote under the current weights, but its final price, GST, and part authenticity remain unconfirmed."}
            </p>
            <div className="report-price">
              <span>
                {recommended.final_price === null
                  ? "CURRENT QUOTE"
                  : "FINAL PRICE"}
              </span>
              <strong>
                ₹
                {(
                  recommended.final_price ?? recommended.first_price
                )?.toLocaleString("en-IN") ?? "—"}
              </strong>
            </div>
            <div className="saving-label">
              {recommended.final_price === null
                ? "PROVISIONAL — FINAL PRICE NOT CONFIRMED"
                : `SAVED ₹${saving.toLocaleString("en-IN")} VS FIRST QUOTE`}
            </div>
          </div>
          <StampLabel tone="green">FINAL</StampLabel>
        </section>

        <section className="priority-section">
          <div className="report-section-heading">
            <div>
              <span className="eyebrow">YOUR BUYING LOGIC</span>
              <h2>PRIORITY WEIGHTS</h2>
            </div>
            <button
              aria-expanded={adjusting}
              className="btn btn--secondary adjust-button"
              onClick={() => setAdjusting((current) => !current)}
            >
              {adjusting ? "DONE ADJUSTING" : "ADJUST WEIGHTS"}
            </button>
          </div>
          <div
            className="priority-bar"
            aria-label="Priority weight distribution"
          >
            {(Object.keys(weights) as WeightKey[]).map((key) => (
              <div
                className={`priority-segment priority-segment--${key}`}
                key={key}
                style={{ width: `${weights[key]}%` }}
              >
                <span>{key}</span>
                <strong>{weights[key]}%</strong>
              </div>
            ))}
          </div>
          {adjusting && (
            <div className="weight-sliders report-weight-sliders">
              {(Object.keys(weights) as WeightKey[]).map((key) => (
                <WeightSlider
                  key={key}
                  label={
                    key === "quality"
                      ? "Part quality"
                      : key
                  }
                  onChange={(event) =>
                    changeWeight(key, Number(event.target.value))
                  }
                  value={weights[key]}
                />
              ))}
            </div>
          )}
        </section>

        <OfferTable
          onEvidence={openEvidence}
          scores={scores}
          shops={rankedShops}
          variant="ranked"
        />

        <section className="why-others">
          <div className="report-section-heading">
            <div>
              <span className="eyebrow">TRADE-OFF CHECK</span>
              <h2>WHY NOT THE OTHERS?</h2>
            </div>
          </div>
          <div className="tradeoff-grid">
            {rankedShops.slice(1).map((shop, index) => (
              <article key={shop.id}>
                <span className="tradeoff-rank">#{index + 2}</span>
                <h3>{shop.name}</h3>
                <p>
                  {shop.status === "failed"
                    ? "No answer after two attempts, so price, warranty, part quality, and turnaround could not be verified."
                    : "An aftermarket part, shorter warranty, and slower turnaround outweigh the lower opening quote."}
                </p>
              </article>
            ))}
          </div>
        </section>

        <section className="caveats-panel">
          <span className="eyebrow">READ BEFORE ORDERING</span>
          <h2>CAVEATS</h2>
          <ul>
            <li>Shop 2 did not confirm GST</li>
            <li>Shop 3 did not answer</li>
          </ul>
        </section>

        <TimelineStrip events={timelineEvents} />

        <div className="report-footer-action">
          <div>
            <span className="eyebrow">END OF QUOTE SHEET</span>
            <strong>KEEP THE EVIDENCE. MAKE THE CALL.</strong>
          </div>
          <Link className="btn btn--primary" to="/dashboard">
            ← BACK TO DASHBOARD
          </Link>
        </div>
      </article>

      {evidence && (
        <>
          <button
            aria-label="Close evidence drawer"
            className="evidence-scrim"
            onClick={closeEvidence}
          />
          <aside
            aria-label="Quote evidence"
            aria-modal="true"
            className="evidence-drawer"
            role="dialog"
          >
            <header>
              <div>
                <span className="eyebrow">
                  SOURCE RECORD / CALL 0{evidence.shop.id}
                </span>
                <h2>EVIDENCE</h2>
              </div>
              <button
                aria-label="Close evidence drawer"
                className="drawer-close"
                onClick={closeEvidence}
                ref={drawerCloseRef}
              >
                ×
              </button>
            </header>
            <div className="evidence-meta">
              <span>{evidence.field.replace("_", " ").toUpperCase()}</span>
              <strong>{evidence.shop.name}</strong>
            </div>
            <blockquote>
              <div>
                <strong>{evidence.turn.speaker.toUpperCase()}</strong>
                <time>{evidence.turn.ts}</time>
              </div>
              <mark lang={evidence.turn.lang}>{evidence.turn.text}</mark>
              <p>ENGLISH: {evidence.turn.translation ?? evidence.turn.text}</p>
            </blockquote>
            <div className="audio-proof">
              <span className="eyebrow">CALL AUDIO / PLACEHOLDER</span>
              <button
                className="audio-play"
                onClick={() => setAudioPlaying((current) => !current)}
              >
                {audioPlaying ? "PAUSE" : "PLAY"} AUDIO
              </button>
              <label>
                <span>{formatDuration(Math.round(audioProgress))}</span>
                <input
                  aria-label="Audio position"
                  max="100"
                  min="0"
                  onChange={(event) =>
                    setAudioProgress(Number(event.target.value))
                  }
                  type="range"
                  value={audioProgress}
                />
                <span>01:40</span>
              </label>
            </div>
            <p className="evidence-note">
              Linked directly from the recorded negotiation transcript.
            </p>
          </aside>
        </>
      )}
    </div>
  )
}

function CropMarks() {
  return (
    <div className="report-crop-marks" aria-hidden="true">
      <i className="crop-mark crop-mark--tl" />
      <i className="crop-mark crop-mark--tr" />
      <i className="crop-mark crop-mark--bl" />
      <i className="crop-mark crop-mark--br" />
    </div>
  )
}

function scoreShops(weights: typeof job.weights) {
  const quoteValues = shops
    .map((shop) => shop.first_price ?? shop.final_price)
    .filter((value): value is number => value !== null)
  const lowestPrice = Math.min(...quoteValues)

  return Object.fromEntries(
    shops.map((shop) => {
      const quote = shop.first_price ?? shop.final_price
      if (shop.status === "failed" || quote === null) return [shop.id, 0]
      const price = (lowestPrice / quote) * 100
      const guarantee = (Math.min(shop.warranty_months ?? 0, 6) / 6) * 100
      const speed = shop.eta_days ? (1 / shop.eta_days) * 100 : 0
      const quality = shop.part_type === "OEM"
        ? 100
        : shop.part_type === "Aftermarket"
          ? 60
          : 0
      const total =
        (price * weights.price +
          guarantee * weights.warranty +
          speed * weights.speed +
          quality * weights.quality) /
        100
      return [shop.id, total]
    }),
  ) as Record<string, number>
}

export function NotFoundPage() {
  return (
    <div className="page-wrap">
      <EmptyState
        title="404 / WRONG NUMBER"
        message="This page fell outside the crop marks."
        action={
          <Link className="btn btn--primary" to="/">
            BACK TO BHAAV
          </Link>
        }
      />
    </div>
  )
}

function PageHeading({
  eyebrow,
  title,
  note,
  stamp,
}: {
  eyebrow: string
  title: string
  note?: string
  stamp?: string
}) {
  return (
    <header className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        {note && <p>{note}</p>}
      </div>
      {stamp && (
        <StampLabel tone={stamp === "FINAL" ? "green" : "magenta"}>
          {stamp}
        </StampLabel>
      )}
    </header>
  )
}
