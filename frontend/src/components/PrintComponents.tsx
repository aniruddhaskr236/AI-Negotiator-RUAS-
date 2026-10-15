import { useEffect, useRef, type ReactNode } from "react"
import { Link } from "react-router"
import type { CallStatus, Shop, TranscriptTurn } from "@/mock"

type AsyncState = "ready" | "loading" | "empty" | "error" | "reconnecting"
export type EvidenceField = "first_price" | "final_price" | "warranty" | "time"

const money = (value: number | null) =>
  value === null ? "—" : `₹${value.toLocaleString("en-IN")}`

export function StampLabel({
  children,
  tone = "magenta",
}: {
  children: ReactNode
  tone?: "magenta" | "green"
}) {
  return <span className={`stamp stamp--${tone}`}>{children}</span>
}

export function CmykBar() {
  return (
    <div className="cmyk-bar" aria-label="CMYK colour bar">
      <span className="bg-cyan" />
      <span className="bg-magenta" />
      <span className="bg-yellow" />
      <span className="bg-ink" />
    </div>
  )
}

export function StatusChip({ status }: { status: CallStatus }) {
  return (
    <span className={`status-chip status-chip--${status}`}>
      {status === "talking" && (
        <span className="blink-square" aria-hidden="true" />
      )}
      {status.toUpperCase()}
    </span>
  )
}

export function HealthChip({
  state,
  label,
}: {
  state: "online" | "degraded" | "offline" | "reconnecting"
  label?: string
}) {
  return (
    <span className={`health-chip health-chip--${state}`}>
      <span className="health-dot" aria-hidden="true" />
      {label ?? state.toUpperCase()}
    </span>
  )
}

export function LoadingBar({ label = "LOADING EVIDENCE" }: { label?: string }) {
  return (
    <div className="loading-wrap" role="status">
      <div className="loading-label">{label}</div>
      <div className="loading-bar">
        <span />
      </div>
    </div>
  )
}

export function ErrorBanner({
  title = "SOMETHING JAMMED",
  message,
  onRetry,
}: {
  title?: string
  message: string
  onRetry?: () => void
}) {
  return (
    <div className="error-banner" role="alert">
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
      {onRetry && (
        <button className="btn btn--secondary" onClick={onRetry}>
          RETRY
        </button>
      )}
    </div>
  )
}

export function EmptyState({
  title = "NO PROOFS YET",
  message = "Evidence will appear here when a call connects.",
  action,
}: {
  title?: string
  message?: string
  action?: ReactNode
}) {
  return (
    <div className="empty-state">
      <span className="registration-mark" aria-hidden="true" />
      <h3>{title}</h3>
      <p>{message}</p>
      {action}
    </div>
  )
}

const languageByShop: Record<string, string> = {
  "1": "हिन्दी",
  "2": "EN",
  "3": "ಕನ್ನಡ",
}

function QrMark() {
  const cells = [
    1, 1, 1, 0, 1, 0, 1, 1, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1,
    0, 1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 1, 1, 0, 1,
  ]
  return (
    <span className="qr-mark" aria-hidden="true">
      {cells.map((filled, index) => (
        <i className={filled ? "filled" : ""} key={index} />
      ))}
    </span>
  )
}

export function CallCard({
  shop,
  status = shop.status,
  duration = "00:00",
  transcriptState = "ready",
  onRetry,
}: {
  shop: Shop
  status?: CallStatus
  duration?: string
  transcriptState?: AsyncState
  onRetry?: () => void
}) {
  const isFailed = status === "failed"

  return (
    <article
      className={`print-card dashboard-call-card crop-card${
        isFailed ? " is-failed" : ""
      }`}
    >
      <div className="card-topline">
        <span className="language-chip">{languageByShop[shop.id] ?? "EN"}</span>
        <StatusChip status={status} />
      </div>
      <h3 className="card-title">{shop.name}</h3>
      <div className="call-clock">
        <span>CALL DURATION</span>
        <strong>{duration}</strong>
      </div>
      {isFailed && (
        <div className="call-error">
          <span>{shop.error ?? "Call failed"}</span>
          {onRetry && (
            <button className="btn btn--secondary btn--small" onClick={onRetry}>
              RETRY
            </button>
          )}
        </div>
      )}
      <TranscriptPanel
        compact
        turns={transcriptState === "loading" ? [] : shop.transcript}
        state={transcriptState}
      />
      <div className="card-footer">
        <QrMark />
        <div>
          <span>SHOP LINE / 0{shop.id}</span>
          <Link className="text-link" to={`/shop/${shop.id}`}>
            OPEN SHOP LINE →
          </Link>
        </div>
      </div>
    </article>
  )
}

function StateFrame({
  state,
  children,
  onRetry,
}: {
  state: AsyncState
  children: ReactNode
  onRetry?: () => void
}) {
  const retry = onRetry ?? (() => window.location.reload())

  if (state === "loading") return <LoadingBar />
  if (state === "reconnecting") return <LoadingBar label="RECONNECTING" />
  if (state === "error")
    return (
      <ErrorBanner
        message="The evidence feed could not be loaded."
        onRetry={retry}
      />
    )
  if (state === "empty") return <EmptyState />
  return children
}

export function TranscriptPanel({
  turns,
  state = "ready",
  compact = false,
  onRetry,
}: {
  turns: TranscriptTurn[]
  state?: AsyncState
  compact?: boolean
  onRetry?: () => void
}) {
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const list = listRef.current
    if (list) list.scrollTop = list.scrollHeight
  }, [turns.length])

  return (
    <section
      className={`panel transcript-panel${
        compact ? " transcript-panel--compact" : ""
      }`}
    >
      {!compact && (
        <div className="section-heading">
          <div>
            <span className="eyebrow">VERBATIM RECORD</span>
            <h2>CALL TRANSCRIPT</h2>
          </div>
          <StampLabel>PROOF</StampLabel>
        </div>
      )}
      <StateFrame
        state={turns.length === 0 && state === "ready" ? "empty" : state}
        onRetry={onRetry}
      >
        <div className="transcript-list" ref={listRef} aria-live="polite">
          {turns.map((turn, index) => (
            <div
              className={`speech speech--${turn.speaker}`}
              key={`${turn.ts}-${index}`}
            >
              <div className="speech-meta">
                <strong>{turn.speaker.toUpperCase()}</strong>
                <time>{turn.ts}</time>
              </div>
              <p lang={turn.lang}>{turn.text}</p>
              {turn.translation && (
                <p className="translation">↳ {turn.translation}</p>
              )}
            </div>
          ))}
        </div>
      </StateFrame>
    </section>
  )
}

export function OfferTable({
  shops,
  state = "ready",
  statuses,
  variant = "live",
  scores,
  onEvidence,
  onRetry,
}: {
  shops: Shop[]
  state?: AsyncState
  statuses?: Record<string, CallStatus>
  variant?: "live" | "ranked"
  scores?: Record<string, number>
  onEvidence?: (shop: Shop, field: EvidenceField) => void
  onRetry?: () => void
}) {
  const completePrices = shops
    .filter((shop) => shop.final_price !== null)
    .map((shop) => shop.final_price as number)
  const bestPrice = completePrices.length ? Math.min(...completePrices) : null

  const evidenceCell = (
    value: ReactNode,
    unknown: boolean,
    warning?: string,
  ) => (
    <span className="evidence-cell">
      {unknown ? (
        <span className="skeleton-cell" aria-label="Waiting for evidence" />
      ) : (
        value
      )}
      {warning && (
        <span
          className="confidence-warning"
          tabIndex={0}
          data-tooltip={warning}
          aria-label={warning}
        >
          !
        </span>
      )}
    </span>
  )

  if (variant === "ranked") {
    const reportCell = (
      shop: Shop,
      field: EvidenceField,
      value: ReactNode,
      unknown = false,
    ) => (
      <span className="report-evidence-cell">
        {unknown ? <span className="unknown-value">—</span> : value}
        <button
          aria-label={`Open evidence for ${shop.name} ${field.replace("_", " ")}`}
          className="evidence-link"
          onClick={() => onEvidence?.(shop, field)}
          title="Open transcript evidence"
        >
          ↗
        </button>
      </span>
    )

    return (
      <section className="panel ranked-offers">
        <div className="section-heading">
          <div>
            <span className="eyebrow">WEIGHTED RESULT</span>
            <h2>RANKED QUOTES</h2>
          </div>
          <span className="table-live-label">SCORES UPDATE LIVE</span>
        </div>
        <StateFrame
          state={shops.length === 0 && state === "ready" ? "empty" : state}
          onRetry={onRetry}
        >
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>RANK</th>
                  <th>SHOP</th>
                  <th>SCORE</th>
                  <th>FIRST QUOTE</th>
                  <th>FINAL PRICE</th>
                  <th>SAVING</th>
                  <th>WARRANTY</th>
                  <th>TIME</th>
                  <th>PART TYPE</th>
                  <th>CONDITIONS</th>
                </tr>
              </thead>
              <tbody>
                {shops.map((shop, index) => (
                  <tr className={index === 0 ? "best-offer" : ""} key={shop.id}>
                    <td>
                      <span
                        className={`rank-block${
                          index === 0 ? " is-first" : ""
                        }`}
                      >
                        #{index + 1}
                      </span>
                    </td>
                    <th>{shop.name}</th>
                    <td>
                      <strong className="score-value">
                        {(scores?.[shop.id] ?? 0).toFixed(1)}
                      </strong>
                    </td>
                    <td>
                      {reportCell(
                        shop,
                        "first_price",
                        money(shop.first_price),
                        shop.first_price === null,
                      )}
                    </td>
                    <td>
                      {reportCell(
                        shop,
                        "final_price",
                        <strong>{money(shop.final_price)}</strong>,
                        shop.final_price === null,
                      )}
                    </td>
                    <td>
                      {shop.first_price !== null && shop.final_price !== null
                        ? `₹${(shop.first_price - shop.final_price).toLocaleString("en-IN")}`
                        : "—"}
                    </td>
                    <td>
                      {reportCell(
                        shop,
                        "warranty",
                        shop.warranty_months === 0
                          ? "NONE"
                          : `${shop.warranty_months} MONTH${shop.warranty_months === 1 ? "" : "S"}`,
                        shop.warranty_months === null,
                      )}
                    </td>
                    <td>
                      {reportCell(
                        shop,
                        "time",
                        shop.eta_days
                          ? `${shop.eta_days} DAY${shop.eta_days > 1 ? "S" : ""}`
                          : "",
                        shop.eta_days === null,
                      )}
                    </td>
                    <td>{shop.part_type || "—"}</td>
                    <td>{shop.conditions || "NOT CONFIRMED"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </StateFrame>
      </section>
    )
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">SIDE-BY-SIDE</span>
          <h2>QUOTE PROOF</h2>
        </div>
        <span className="table-live-label">LIVE / AUTO-UPDATING</span>
      </div>
      <StateFrame
        state={shops.length === 0 && state === "ready" ? "empty" : state}
        onRetry={onRetry}
      >
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>SHOP</th>
                <th>FIRST QUOTE</th>
                <th>FINAL PRICE</th>
                <th>SAVING</th>
                <th>WARRANTY</th>
                <th>TIME</th>
                <th>PART TYPE</th>
                <th>CONDITIONS</th>
              </tr>
            </thead>
            <tbody>
              {shops.map((shop) => {
                const saving =
                  shop.first_price !== null && shop.final_price !== null
                    ? shop.first_price - shop.final_price
                    : null
                const currentStatus = statuses?.[shop.id] ?? shop.status
                const isBest =
                  shop.final_price !== null && shop.final_price === bestPrice
                return (
                  <tr className={isBest ? "best-offer" : ""} key={shop.id}>
                    <th>
                      {shop.name}
                      <StatusChip status={currentStatus} />
                    </th>
                    <td>
                      {evidenceCell(
                        money(shop.first_price),
                        shop.first_price === null,
                      )}
                    </td>
                    <td>
                      {evidenceCell(
                        <strong>{money(shop.final_price)}</strong>,
                        shop.final_price === null,
                      )}
                    </td>
                    <td>
                      {evidenceCell(
                        saving === null
                          ? ""
                          : `₹${saving.toLocaleString("en-IN")}`,
                        saving === null,
                      )}
                    </td>
                    <td>
                      {evidenceCell(
                        shop.warranty_months === 0
                          ? "NONE"
                          : `${shop.warranty_months} MO`,
                        shop.warranty_months === null,
                      )}
                    </td>
                    <td>
                      {evidenceCell(
                        shop.eta_days
                          ? `${shop.eta_days} DAY${shop.eta_days > 1 ? "S" : ""}`
                          : "",
                        shop.eta_days === null,
                      )}
                    </td>
                    <td>
                      {evidenceCell(
                        shop.part_type,
                        !shop.part_type,
                        shop.id === "2"
                          ? "Low confidence: offered aftermarket part differs from the preferred original part"
                          : undefined,
                      )}
                    </td>
                    <td>
                      {evidenceCell(
                        shop.conditions || "NONE",
                        shop.status === "failed",
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </StateFrame>
    </section>
  )
}

export function TimelineStrip({
  events,
  state = "ready",
  onRetry,
}: {
  events: Array<Record<"time" | "text", string>>
  state?: AsyncState
  onRetry?: () => void
}) {
  return (
    <section className="panel">
      <div className="section-heading compact-heading">
        <div>
          <span className="eyebrow">NEGOTIATION LOG</span>
          <h2>WHAT MOVED</h2>
        </div>
      </div>
      <StateFrame
        state={events.length === 0 && state === "ready" ? "empty" : state}
        onRetry={onRetry}
      >
        <ol className="timeline">
          {events.map((event, index) => (
            <li key={`${event.time}-${index}`}>
              <time>{event.time}</time>
              <span className="timeline-mark" aria-hidden="true" />
              <p>{event.text}</p>
            </li>
          ))}
        </ol>
      </StateFrame>
    </section>
  )
}
