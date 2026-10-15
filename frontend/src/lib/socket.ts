export type SocketMessageHandler = (event: any) => void
export type SocketStatusHandler = (status: "connecting" | "connected" | "reconnecting" | "closed") => void

export class ReconnectingSocket {
  private path: string
  private ws: WebSocket | null = null
  private onMessage: SocketMessageHandler
  private onStatus?: SocketStatusHandler
  private pingInterval: any = null
  private reconnectTimer: any = null
  private reconnectAttempts = 0
  private shouldClose = false

  constructor(path: string, onMessage: SocketMessageHandler, onStatus?: SocketStatusHandler) {
    this.path = path.startsWith("/") ? path : `/${path}`
    this.onMessage = onMessage
    this.onStatus = onStatus
    this.connect()
  }

  private getUrl(): string {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:"
    return `${proto}//${window.location.host}${this.path}`
  }

  public connect() {
    this.shouldClose = false
    this.cleanup()
    this.onStatus?.(this.reconnectAttempts === 0 ? "connecting" : "reconnecting")

    try {
      this.ws = new WebSocket(this.getUrl())

      this.ws.onopen = () => {
        this.reconnectAttempts = 0
        this.onStatus?.("connected")
        // Start 25s ping
        this.pingInterval = setInterval(() => {
          if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: "ping" }))
          }
        }, 25000)
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          this.onMessage(data)
        } catch (err) {
          console.warn("Failed to parse websocket message", err)
        }
      }

      this.ws.onclose = () => {
        this.cleanup()
        if (!this.shouldClose) {
          this.onStatus?.("reconnecting")
          const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 10000)
          this.reconnectAttempts++
          this.reconnectTimer = setTimeout(() => this.connect(), delay)
        } else {
          this.onStatus?.("closed")
        }
      }

      this.ws.onerror = (err) => {
        console.warn("WebSocket error on", this.path, err)
      }
    } catch (e) {
      this.cleanup()
      this.reconnectTimer = setTimeout(() => this.connect(), 2000)
    }
  }

  public send(msg: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(typeof msg === "string" ? msg : JSON.stringify(msg))
      return true
    }
    return false
  }

  private cleanup() {
    if (this.pingInterval) clearInterval(this.pingInterval)
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.pingInterval = null
    this.reconnectTimer = null
  }

  public close() {
    this.shouldClose = true
    this.cleanup()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.onStatus?.("closed")
  }
}
