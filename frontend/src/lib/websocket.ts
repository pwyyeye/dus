"use client";

const WS_BASE = process.env.NEXT_PUBLIC_WS_BASE_URL || "ws://localhost:8000/ws";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "change-me-to-a-strong-random-string-at-least-32-chars";
const RECONNECT_BASE = 1000;
const RECONNECT_MAX = 30000;

type MessageHandler = (data: { type: string; payload: unknown }) => void;

class WsClient {
  private ws: WebSocket | null = null;
  private handlers: Set<MessageHandler> = new Set();
  private reconnectDelay = RECONNECT_BASE;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setTimeout> | null = null;
  private _onOpen: (() => void) | null = null;
  private _onClose: (() => void) | null = null;

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    const url = `${WS_BASE}?api_key=${encodeURIComponent(API_KEY)}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectDelay = RECONNECT_BASE;
      this._onOpen?.();
      this._schedulePing();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "ping") {
          this.ws?.send("pong");
          return;
        }
        for (const handler of this.handlers) {
          handler(data);
        }
      } catch {
        // ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      this._onClose?.();
      this._clearPing();
      this._scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  disconnect() {
    this._clearReconnect();
    this._clearPing();
    this.ws?.close();
    this.ws = null;
  }

  onMessage(handler: MessageHandler) {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  onOpen(cb: () => void) {
    this._onOpen = cb;
    return () => { this._onOpen = null; };
  }

  onClose(cb: () => void) {
    this._onClose = cb;
    return () => { this._onClose = null; };
  }

  private _scheduleReconnect() {
    this._clearReconnect();
    this.reconnectTimer = setTimeout(() => {
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, RECONNECT_MAX);
      this.connect();
    }, this.reconnectDelay);
  }

  private _clearReconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private _schedulePing() {
    this._clearPing();
    this.pingTimer = setTimeout(() => {
      this.ws?.send("pong");
      this._schedulePing();
    }, 25000);
  }

  private _clearPing() {
    if (this.pingTimer) {
      clearTimeout(this.pingTimer);
      this.pingTimer = null;
    }
  }
}

export const wsClient = new WsClient();
