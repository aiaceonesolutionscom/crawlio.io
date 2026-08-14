import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { ActivityIcon, RadioIcon } from 'lucide-react';
import { cn } from '../../utils/cn';
import { agentWsUrl, getAgentActivity, type ActivityDTO } from '../../../lib/api/agent';

export interface LiveActivityEvent {
  conversation_id: string | null;
  stage: string;
  status: string;
  detail: string | null;
  created_at: string;
}

const STAGE_LABELS: Record<string, string> = {
  email_received: 'New inbound email received',
  lead_identified: 'Identified lead',
  knowledge_loaded: 'Loaded business knowledge',
  intent_detected: 'Detected customer intent',
  building_reply: 'Preparing response',
  ai_reply_sent: 'Sending response...',
  ai_stopped: 'AI stopped before send',
  unsubscribe_detected: 'Unsubscribe requested by customer',
  meeting_booked: 'Meeting booked',
  crm_updated: 'Lead saved to CRM',
  outreach_sent: 'Outreach email sent',
};

export function ActivityPanel() {
  const { getToken } = useAuth();
  const [events, setEvents] = useState<LiveActivityEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const [replay, setReplay] = useState<ActivityDTO[]>([]);

  // Replay persisted activity once on mount so the panel isn't empty after a reload.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const token = await getToken();
        const data = await getAgentActivity(token);
        if (!cancelled) setReplay(data);
      } catch {
        /* ignore */
      }
    })();
    return () => { cancelled = true; };
  }, [getToken]);

  const connect = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;
      const socket = new WebSocket(agentWsUrl());
      socket.onopen = () => {
        setConnected(true);
        socket.send(JSON.stringify({ token }));
      };
      socket.onmessage = (msg) => {
        try {
          const data = JSON.parse(msg.data as string);
          if (data.type === 'ai_activity') {
            setEvents((prev) => [{ ...data, created_at: data.created_at }, ...prev].slice(0, 40));
          }
        } catch { /* keepalive pings and non-JSON frames are ignored */ }
      };
      socket.onclose = () => {
        setConnected(false);
        // Backoff reconnect.
        setTimeout(() => { wsRef.current = null; void connect(); }, 3000);
      };
      socket.onerror = () => socket.close();
      wsRef.current = socket;
    } catch {
      setTimeout(() => { void connect(); }, 5000);
    }
  }, [getToken]);

  useEffect(() => {
    void connect();
    return () => {
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect]);

  const merged: LiveActivityEvent[] = [
    ...events,
    ...replay
      .filter((r) => !events.some((e) => e.created_at === r.created_at && e.stage === r.stage))
      .map((r) => ({ conversation_id: r.conversation_id, stage: r.stage, status: r.status, detail: r.detail, created_at: r.created_at || '' })),
  ];

  return (
    <div className="flex h-full flex-col rounded-2xl border border-ink-800 bg-ink-900/90">
      <div className="flex items-center justify-between border-b border-ink-850 px-4 py-3">
        <p className="flex items-center gap-2 text-[12px] font-medium text-chalk">
          <ActivityIcon className="h-4 w-4 text-signal" /> AI Activity
        </p>
        <span className={cn('flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-wider', connected ? 'text-signal' : 'text-chalk-faint')}>
          <RadioIcon className={cn('h-3 w-3', connected && 'animate-pulse')} />
          {connected ? 'Live' : 'Offline'}
        </span>
      </div>
      <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-3">
        {merged.length === 0 && (
          <div className="py-10 text-center">
            <p className="text-[12px] text-chalk-dim">Agent activity will appear here in real time.</p>
          </div>
        )}
        {merged.map((e, i) => (
          <div key={`${e.created_at}-${e.stage}-${i}`} className="flex gap-2 text-[11.5px]">
            <span className={cn('mt-0.5 h-2 w-2 shrink-0 rounded-full', e.status === 'failed' ? 'bg-ember' : e.status === 'running' ? 'bg-signal animate-pulse' : 'bg-emerald')} />
            <div className="min-w-0">
              <p className="text-chalk">
                {e.status === 'failed' && '✕ '}
                {STAGE_LABELS[e.stage] || e.stage}
              </p>
              {e.detail && <p className="truncate text-chalk-faint">{e.detail}</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}