import { useCallback, useEffect, useRef, useState } from 'react';
import { getStoredToken } from '../api/client';
import type { AvatarState, IntegrityAlert, IntegrityEventType, IntegrityObservationEvent, InterviewMessage } from '../types';

export interface UseInterviewWebSocketProps {
  sessionId: string;
  onAIMessage?: (content: string, targetCapability?: string) => void;
  onAIAudio?: (base64Audio: string, contentType: string) => void;
  onIntegrityObservation?: (event: IntegrityObservationEvent) => void;
  onError?: (err: any) => void;
}

export function useInterviewWebSocket({
  sessionId,
  onAIMessage,
  onAIAudio,
  onIntegrityObservation,
  onError,
}: UseInterviewWebSocketProps) {
  const [isConnected, setIsConnected] = useState(false);
  const [avatarState, setAvatarState] = useState<AvatarState>('IDLE');
  const [messages, setMessages] = useState<InterviewMessage[]>([]);
  const [currentAIQuestion, setCurrentAIQuestion] = useState<string | null>(null);
  const [currentCapability, setCurrentCapability] = useState<string | null>(null);
  const [activeAlert, setActiveAlert] = useState<IntegrityAlert | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const isClosingExplicitly = useRef(false);

  // Send structured WS JSON payload
  const sendEvent = useCallback((event: Record<string, any>) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(event));
    }
  }, []);

  // Send candidate text message
  const sendCandidateMessage = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      const outgoing = {
        type: 'candidate_message',
        content: text.trim(),
      };
      console.log('[WS ANSWER SENT]');
      sendEvent(outgoing);
      setMessages((prev) => [
        ...prev,
        { role: 'candidate', content: text.trim(), created_at: new Date().toISOString() },
      ]);
      setAvatarState('THINKING');
    },
    [sendEvent]
  );

  // Send candidate recorded audio
  const sendCandidateAudio = useCallback(
    (base64Audio: string, contentType = 'audio/webm') => {
      console.log('[WS ANSWER SENT] (audio)');
      sendEvent({
        type: 'candidate_audio',
        audio: base64Audio,
        content_type: contentType,
      });
      setAvatarState('THINKING');
    },
    [sendEvent]
  );

  // Emit neutral observational integrity event
  const sendIntegrityEvent = useCallback(
    (
      eventType: IntegrityEventType,
      metadata: Record<string, any> = {},
      evidenceImage?: string
    ) => {
      sendEvent({
        type: 'integrity_event',
        event_type: eventType,
        occurred_at: new Date().toISOString(),
        metadata,
        ...(evidenceImage ? { evidence_image: evidenceImage } : {}),
      });
    },
    [sendEvent]
  );

  // Send sampled camera frame for object detection
  const sendVisionFrame = useCallback(
    (base64Image: string) => {
      sendEvent({
        type: 'vision_frame',
        image: base64Image,
        timestamp: new Date().toISOString(),
      });
    },
    [sendEvent]
  );

  const dismissAlert = useCallback(() => {
    setActiveAlert(null);
  }, []);

  const onAIMessageRef = useRef(onAIMessage);
  onAIMessageRef.current = onAIMessage;
  const onAIAudioRef = useRef(onAIAudio);
  onAIAudioRef.current = onAIAudio;
  const onIntegrityObservationRef = useRef(onIntegrityObservation);
  onIntegrityObservationRef.current = onIntegrityObservation;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  useEffect(() => {
    if (!sessionId) return;

    isClosingExplicitly.current = false;
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token') || getStoredToken();
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/api/v1/interviews/${sessionId}/ws?token=${token || ''}`;

    console.log('[WS CONNECTING]', `${protocol}//${host}/api/v1/interviews/${sessionId}/ws?token=REDACTED`);

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[WS CONNECTED] session_id:', sessionId);
      setIsConnected(true);
      setAvatarState('IDLE');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('[WS MESSAGE TYPE]:', data.type, data.event || '');

        if (data.type === 'avatar_state' && data.state) {
          setAvatarState(data.state);
        } else if (data.type === 'ai_message') {
          console.log('[WS AI QUESTION]:', data.content);
          setCurrentAIQuestion(data.content);
          if (data.target_capability) {
            setCurrentCapability(data.target_capability);
          }
          setMessages((prev) => [
            ...prev,
            {
              role: 'ai',
              content: data.content,
              created_at: new Date().toISOString(),
            },
          ]);
          setAvatarState('SPEAKING');
          onAIMessageRef.current?.(data.content, data.target_capability);
        } else if (data.type === 'ai_audio') {
          onAIAudioRef.current?.(data.audio, data.content_type || 'audio/mpeg');
          setAvatarState('SPEAKING');
        } else if (data.type === 'transcript') {
          setMessages((prev) => [
            ...prev,
            {
              role: 'candidate',
              content: data.content,
              created_at: new Date().toISOString(),
            },
          ]);
        } else if (data.type === 'integrity_observation') {
          console.warn('[WS INTEGRITY OBSERVATION]:', data.event_type);
          const alert: IntegrityAlert = {
            id: data.event_id || String(Date.now()),
            eventType: data.event_type,
            title: data.alert_title || '🔴 INTEGRITY OBSERVATION',
            message: data.alert_message || (data.event_type === 'PHONE_DETECTED' ? 'Mobile phone detected — Evidence frame captured' : 'Multiple people detected — Evidence frame captured'),
            occurredAt: data.occurred_at || new Date().toISOString(),
            evidenceUrl: data.evidence_url,
            evidenceReference: data.evidence_reference,
          };
          setActiveAlert(alert);
          onIntegrityObservationRef.current?.(data);
        }
      } catch (err) {
        console.error('[WS PARSE ERROR]:', err);
      }
    };

    ws.onerror = (err) => {
      console.error('[WS ERROR]:', err);
      setAvatarState('ERROR');
      onErrorRef.current?.(err);
    };

    ws.onclose = (event) => {
      console.log('[WS CLOSED] code:', event.code, 'reason:', event.reason);
      setIsConnected(false);
      if (!isClosingExplicitly.current) {
        setAvatarState('IDLE');
      }
    };

    return () => {
      isClosingExplicitly.current = true;
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close(1000, 'Component unmounted');
      }
    };
  }, [sessionId]);

  return {
    isConnected,
    avatarState,
    setAvatarState,
    messages,
    setMessages,
    currentAIQuestion,
    currentCapability,
    activeAlert,
    dismissAlert,
    sendCandidateMessage,
    sendCandidateAudio,
    sendIntegrityEvent,
    sendVisionFrame,
  };
}
