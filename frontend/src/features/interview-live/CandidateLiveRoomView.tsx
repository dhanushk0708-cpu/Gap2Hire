import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Mic,
  MicOff,
  Video,
  VideoOff,
  Send,
  Radio,
  Clock,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  AlertTriangle,
  RefreshCw,
  Volume2,
  Play,
  FileText,
} from 'lucide-react';
import { useInterviewWebSocket } from '../../core/websocket/useInterviewWebSocket';
import { AvatarVisualizer } from '../../shared/components/AvatarVisualizer';
import { interviewSessionsApi } from '../../core/api/endpoints';

const ALLOWED_DURATIONS = [5, 15, 30, 45, 60];

const parseDeadlineMs = (dateStr: string | null | undefined): number => {
  if (!dateStr) return 0;
  // If no timezone is specified in the string (no 'Z' and no offset like '+05:30'),
  // JavaScript's new Date() interprets it as local time instead of UTC.
  // We append 'Z' to guarantee it is parsed as UTC.
  const hasTimezone = dateStr.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(dateStr);
  const normalized = hasTimezone ? dateStr : `${dateStr}Z`;
  return new Date(normalized).getTime();
};

export const CandidateLiveRoomView: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  // Interview Lifecycle State
  const [sessionStatus, setSessionStatus] = useState<string>('LOADING');
  const [hasStarted, setHasStarted] = useState<boolean>(false);
  const [isCompleted, setIsCompleted] = useState<boolean>(false);
  const [completionReason, setCompletionReason] = useState<string>('NORMAL');
  const [selectedDuration, setSelectedDuration] = useState<number>(30);
  const [deadlineAt, setDeadlineAt] = useState<string | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState<number>(30 * 60);

  // AV Readiness Gate States
  const [cameraReady, setCameraReady] = useState<boolean>(false);
  const [micReady, setMicReady] = useState<boolean>(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [micError, setMicError] = useState<string | null>(null);
  const [micVolume, setMicVolume] = useState<number>(0);
  const [isStartingInterview, setIsStartingInterview] = useState<boolean>(false);

  // Mid-Interview Media Disruption & Recovery State
  const [mediaDisrupted, setMediaDisrupted] = useState<boolean>(false);
  const [recoverySecondsLeft, setRecoverySecondsLeft] = useState<number>(30);
  const [disruptionReason, setDisruptionReason] = useState<string>('');
  const recoveryTimerRef = useRef<any>(null);

  // Active Device Media States
  const [micActive, setMicActive] = useState(true);
  const [cameraActive, setCameraActive] = useState(true);
  const [isRecording, setIsRecording] = useState(false);
  const [textInput, setTextInput] = useState('');
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [hasStream, setHasStream] = useState(false);
  const [availableCameras, setAvailableCameras] = useState<{ deviceId: string; label: string }[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<string>('');
  const [activeCameraLabel, setActiveCameraLabel] = useState<string>('Webcam');

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const readinessVideoRef = useRef<HTMLVideoElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioAnalyserRef = useRef<AnalyserNode | null>(null);
  const micAnimFrameRef = useRef<number | null>(null);

  // Setup WebSocket connection
  const {
    isConnected,
    avatarState,
    messages,
    currentAIQuestion,
    currentCapability,
    activeAlert,
    durationDeadline,
    completionState,
    mediaWarning,
    dismissAlert,
    sendCandidateMessage,
    sendCandidateAudio,
    sendIntegrityEvent,
    sendVisionFrame,
    sendStartInterview,
    sendMediaTimeout,
  } = useInterviewWebSocket({
    sessionId: sessionId || '',
    onAIMessage: useCallback((text: string) => {
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        window.speechSynthesis.speak(utterance);
      }
    }, []),
    onCompleted: useCallback((completion) => {
      setIsCompleted(true);
      setCompletionReason(completion.reason || 'TIME_EXPIRED');
    }, []),
  });

  // Check initial session state on mount
  useEffect(() => {
    if (!sessionId) return;
    let mounted = true;

    interviewSessionsApi
      .getExecutionState(sessionId)
      .then((state) => {
        if (!mounted) return;
        setSessionStatus(state.interview_status);

        if (state.interview_status === 'COMPLETED') {
          setIsCompleted(true);
          setCompletionReason(state.completion_reason || 'NORMAL');
          setHasStarted(true);
        } else if (state.interview_status === 'IN_PROGRESS') {
          setHasStarted(true);
          if (state.deadline_at) {
            setDeadlineAt(state.deadline_at);
            const targetMs = parseDeadlineMs(state.deadline_at);
            const remaining = typeof state.remaining_seconds === 'number' && state.remaining_seconds > 0
              ? state.remaining_seconds
              : Math.max(0, Math.floor((targetMs - Date.now()) / 1000));
            setRemainingSeconds(remaining);
            if (remaining <= 0) {
              setIsCompleted(true);
              setCompletionReason('TIME_EXPIRED');
            }
          } else if (state.duration_minutes) {
            setSelectedDuration(state.duration_minutes);
            setRemainingSeconds(state.duration_minutes * 60);
          }
        } else {
          // CREATED or SCHEDULED - needs AV gate
          setHasStarted(false);
          if (state.duration_minutes && ALLOWED_DURATIONS.includes(state.duration_minutes)) {
            setSelectedDuration(state.duration_minutes);
          }
        }
      })
      .catch((err) => {
        console.error('Failed to fetch session state:', err);
      });

    return () => {
      mounted = false;
    };
  }, [sessionId]);

  // Sync deadline updates from WebSocket
  useEffect(() => {
    if (durationDeadline) {
      if (durationDeadline.deadlineAt) {
        setDeadlineAt(durationDeadline.deadlineAt);
      }
      if (typeof durationDeadline.remainingSeconds === 'number' && durationDeadline.remainingSeconds > 0) {
        setRemainingSeconds(durationDeadline.remainingSeconds);
      } else if (durationDeadline.deadlineAt) {
        const targetMs = parseDeadlineMs(durationDeadline.deadlineAt);
        const rem = Math.max(0, Math.floor((targetMs - Date.now()) / 1000));
        if (rem > 0) {
          setRemainingSeconds(rem);
        }
      }
      if (durationDeadline.durationMinutes) {
        setSelectedDuration(durationDeadline.durationMinutes);
      }
    }
  }, [durationDeadline]);

  // Sync completion updates from WebSocket
  useEffect(() => {
    if (completionState && completionState.isCompleted) {
      setIsCompleted(true);
      setCompletionReason(completionState.reason || 'TIME_EXPIRED');
    }
  }, [completionState]);

  // Synchronized countdown ticker based on authoritative deadline
  useEffect(() => {
    if (!hasStarted || isCompleted) return;

    const timer = setInterval(() => {
      if (deadlineAt) {
        const targetMs = parseDeadlineMs(deadlineAt);
        const diff = Math.max(
          0,
          Math.floor((targetMs - Date.now()) / 1000)
        );
        setRemainingSeconds(diff);
        if (diff <= 0) {
          setIsCompleted(true);
          setCompletionReason('TIME_EXPIRED');
          interviewSessionsApi
            .complete(sessionId || '', { reason: 'TIME_EXPIRED' })
            .catch(console.error);
        }
      } else {
        setRemainingSeconds((prev) => {
          if (prev <= 1) {
            setIsCompleted(true);
            setCompletionReason('TIME_EXPIRED');
            interviewSessionsApi
              .complete(sessionId || '', { reason: 'TIME_EXPIRED' })
              .catch(console.error);
            return 0;
          }
          return prev - 1;
        });
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [hasStarted, isCompleted, deadlineAt, sessionId]);

  // Audio volume analyzer for readiness testing
  const setupAudioMeter = useCallback((stream: MediaStream) => {
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioCtx) return;

      const audioCtx = new AudioCtx();
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);

      audioContextRef.current = audioCtx;
      audioAnalyserRef.current = analyser;

      const pcmData = new Uint8Array(analyser.frequencyBinCount);
      const updateVolume = () => {
        if (!audioAnalyserRef.current) return;
        audioAnalyserRef.current.getByteFrequencyData(pcmData);
        let sum = 0;
        for (let i = 0; i < pcmData.length; i++) {
          sum += pcmData[i];
        }
        const avg = sum / pcmData.length;
        // Normalize 0-100
        const normalized = Math.min(100, Math.round((avg / 128) * 100));
        setMicVolume(normalized);
        micAnimFrameRef.current = requestAnimationFrame(updateVolume);
      };

      updateVolume();
    } catch (e) {
      console.warn('AudioContext volume meter setup failed:', e);
    }
  }, []);

  // WebCam & Microphone media initialization
  const startMedia = useCallback(
    async (preferredDeviceId?: string) => {
      try {
        setCameraError(null);
        setMicError(null);

        let chosenDeviceId = preferredDeviceId;

        if (!chosenDeviceId) {
          const preDevices = await navigator.mediaDevices.enumerateDevices();
          const preVideo = preDevices.filter((d) => d.kind === 'videoinput');
          const physical = preVideo.find(
            (d) =>
              d.label.toLowerCase().includes('integrated') ||
              (!d.label.toLowerCase().includes('smart connect') &&
                !d.label.toLowerCase().includes('virtual') &&
                d.label.length > 0)
          );
          if (physical && physical.deviceId) {
            chosenDeviceId = physical.deviceId;
          }
        }

        const videoConstraints: MediaTrackConstraints = chosenDeviceId
          ? {
              deviceId: { exact: chosenDeviceId },
              width: { ideal: 640 },
              height: { ideal: 480 },
            }
          : {
              width: { ideal: 640 },
              height: { ideal: 480 },
              facingMode: 'user',
            };

        const stream = await navigator.mediaDevices.getUserMedia({
          video: videoConstraints,
          audio: true,
        });

        // Enumerate devices post-permission
        const postDevices = await navigator.mediaDevices.enumerateDevices();
        const postVideoInputs = postDevices.filter((d) => d.kind === 'videoinput');
        setAvailableCameras(
          postVideoInputs.map((d, idx) => ({
            deviceId: d.deviceId,
            label: d.label || `Camera ${idx + 1}`,
          }))
        );

        const videoTrack = stream.getVideoTracks()[0];
        const audioTrack = stream.getAudioTracks()[0];

        // Validate camera track
        if (videoTrack && videoTrack.readyState === 'live' && videoTrack.enabled) {
          setCameraReady(true);
          setCameraError(null);
        } else {
          setCameraReady(false);
          setCameraError('Camera track is inactive or unavailable.');
        }

        // Validate audio track
        if (audioTrack && audioTrack.readyState === 'live' && audioTrack.enabled) {
          setMicReady(true);
          setMicError(null);
          setupAudioMeter(stream);
        } else {
          setMicReady(false);
          setMicError('Microphone track is inactive or unavailable.');
        }

        // If virtual camera detected when physical webcam is available, switch
        if (
          !preferredDeviceId &&
          videoTrack?.label.toLowerCase().includes('smart connect')
        ) {
          const realWebcam = postVideoInputs.find(
            (d) =>
              d.label.toLowerCase().includes('integrated') ||
              (!d.label.toLowerCase().includes('smart connect') &&
                !d.label.toLowerCase().includes('virtual'))
          );
          if (realWebcam && realWebcam.deviceId) {
            stream.getTracks().forEach((t) => t.stop());
            return startMedia(realWebcam.deviceId);
          }
        }

        const currentLabel = videoTrack?.label || 'Webcam';
        setActiveCameraLabel(currentLabel);
        setSelectedCameraId(videoTrack?.getSettings().deviceId || '');

        // Stop prior tracks
        if (mediaStreamRef.current) {
          mediaStreamRef.current.getTracks().forEach((t) => t.stop());
        }

        mediaStreamRef.current = stream;
        setMediaStream(stream);
        setHasStream(true);

        // Bind to readiness video preview if present
        if (readinessVideoRef.current) {
          readinessVideoRef.current.srcObject = stream;
          readinessVideoRef.current.muted = true;
          readinessVideoRef.current.play().catch(console.warn);
        }

        // Bind to active room video preview if present
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.muted = true;
          videoRef.current.play().catch(console.warn);
        }

        sendIntegrityEvent('CAMERA_CONNECTED', { info: 'Camera initialized', device: currentLabel });
        sendIntegrityEvent('MICROPHONE_CONNECTED', { info: 'Microphone initialized' });

        // Continuous track event listeners
        videoTrack.onended = () => handleMediaDisrupted('Camera track disconnected');
        videoTrack.onmute = () => handleMediaDisrupted('Camera track muted by system');
        audioTrack.onended = () => handleMediaDisrupted('Microphone track disconnected');
        audioTrack.onmute = () => handleMediaDisrupted('Microphone track muted by system');
      } catch (err: any) {
        console.warn('Webcam/Mic access denied or unavailable:', err);
        setHasStream(false);
        setCameraReady(false);
        setMicReady(false);
        const errMsg = err?.message || 'Permission denied or device not found.';
        setCameraError(errMsg);
        setMicError(errMsg);
      }
    },
    [sendIntegrityEvent, setupAudioMeter]
  );

  // Initialize media on mount
  useEffect(() => {
    startMedia();

    return () => {
      if (micAnimFrameRef.current) {
        cancelAnimationFrame(micAnimFrameRef.current);
      }
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(console.warn);
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
      }
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
      if (recoveryTimerRef.current) {
        clearInterval(recoveryTimerRef.current);
      }
    };
  }, [startMedia]);

  // Bind media stream to active video element
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    if (mediaStream && cameraActive) {
      if (video.srcObject !== mediaStream) {
        video.srcObject = mediaStream;
      }
      video.muted = true;
      video.play().catch(console.warn);
    } else if (!cameraActive && video.srcObject) {
      video.pause();
    }
  }, [mediaStream, cameraActive]);

  // Bind media stream to readiness video element
  useEffect(() => {
    const video = readinessVideoRef.current;
    if (!video) return;

    if (mediaStream && cameraReady) {
      if (video.srcObject !== mediaStream) {
        video.srcObject = mediaStream;
      }
      video.muted = true;
      video.play().catch(console.warn);
    }
  }, [mediaStream, cameraReady]);

  // Mid-interview media disruption and 30s recovery period
  const handleMediaDisrupted = useCallback(
    (reason: string) => {
      if (!hasStarted || isCompleted) return;

      console.warn('[MEDIA DISRUPTED]:', reason);
      setMediaDisrupted(true);
      setDisruptionReason(reason);
      setRecoverySecondsLeft(30);

      sendIntegrityEvent('CAMERA_DISCONNECTED', {
        reason,
        note: '30-second bounded media recovery period initiated',
      });

      if (recoveryTimerRef.current) {
        clearInterval(recoveryTimerRef.current);
      }

      recoveryTimerRef.current = setInterval(() => {
        setRecoverySecondsLeft((prev) => {
          if (prev <= 1) {
            clearInterval(recoveryTimerRef.current);
            // Recovery period expired -> terminate interview
            console.error('[MEDIA RECOVERY EXPIRED]: Ending interview with INTERRUPTED_MEDIA_FAILURE');
            setIsCompleted(true);
            setCompletionReason('INTERRUPTED_MEDIA_FAILURE');
            sendMediaTimeout();
            interviewSessionsApi
              .complete(sessionId || '', { reason: 'INTERRUPTED_MEDIA_FAILURE' })
              .catch(console.error);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    },
    [hasStarted, isCompleted, sendIntegrityEvent, sendMediaTimeout, sessionId]
  );

  const restoreMedia = useCallback(() => {
    if (recoveryTimerRef.current) {
      clearInterval(recoveryTimerRef.current);
      recoveryTimerRef.current = null;
    }
    setMediaDisrupted(false);
    setDisruptionReason('');
    sendIntegrityEvent('CAMERA_CONNECTED', { note: 'Media restored successfully within recovery window' });
  }, [sendIntegrityEvent]);

  // Toggle Camera
  const toggleCamera = () => {
    if (mediaStreamRef.current) {
      const videoTrack = mediaStreamRef.current.getVideoTracks()[0];
      if (videoTrack) {
        const nextEnabled = !videoTrack.enabled;
        videoTrack.enabled = nextEnabled;
        setCameraActive(nextEnabled);
        if (!nextEnabled) {
          sendIntegrityEvent('CAMERA_MUTED', { note: 'Camera disabled by user' });
          handleMediaDisrupted('Camera disabled by user');
        } else {
          sendIntegrityEvent('CAMERA_CONNECTED', { note: 'Camera enabled by user' });
          restoreMedia();
          if (videoRef.current) {
            videoRef.current.play().catch(console.warn);
          }
        }
      }
    }
  };

  // Toggle Microphone
  const toggleMic = () => {
    if (mediaStreamRef.current) {
      const audioTrack = mediaStreamRef.current.getAudioTracks()[0];
      if (audioTrack) {
        const nextEnabled = !audioTrack.enabled;
        audioTrack.enabled = nextEnabled;
        setMicActive(nextEnabled);
        if (!nextEnabled) {
          sendIntegrityEvent('MICROPHONE_MUTED', { note: 'Microphone disabled by user' });
          handleMediaDisrupted('Microphone disabled by user');
        } else {
          sendIntegrityEvent('MICROPHONE_CONNECTED', { note: 'Microphone enabled by user' });
          restoreMedia();
        }
      }
    }
  };

  // Sample frame for YOLO vision detection
  useEffect(() => {
    if (!hasStarted || !isConnected || !cameraActive || !hasStream || isCompleted) return;

    const sampleIntervalMs = 500;
    const canvas = document.createElement('canvas');
    canvas.width = 640;
    canvas.height = 480;
    const ctx = canvas.getContext('2d');

    const intervalId = setInterval(() => {
      const video = videoRef.current;
      if (video && (video.readyState >= 2 || video.videoWidth > 0) && ctx) {
        ctx.drawImage(video, 0, 0, 640, 480);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
        sendVisionFrame(dataUrl);
      }
    }, sampleIntervalMs);

    return () => clearInterval(intervalId);
  }, [hasStarted, isConnected, cameraActive, hasStream, isCompleted, sendVisionFrame]);

  // Tab visibility telemetry
  useEffect(() => {
    if (!hasStarted || isCompleted) return;

    const handleVisibilityChange = () => {
      if (document.hidden) {
        sendIntegrityEvent('TAB_HIDDEN', {
          timestamp: new Date().toISOString(),
          note: 'Browser tab became inactive/hidden',
        });
      } else {
        sendIntegrityEvent('TAB_VISIBLE', {
          timestamp: new Date().toISOString(),
          note: 'Browser tab returned to foreground',
        });
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [hasStarted, isCompleted, sendIntegrityEvent]);

  // Audio recording handlers for spoken responses
  const startAudioRecording = () => {
    if (!mediaStreamRef.current || mediaDisrupted || isCompleted) return;
    try {
      const audioStream = new MediaStream(mediaStreamRef.current.getAudioTracks());
      const recorder = new MediaRecorder(audioStream);
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64Audio = (reader.result as string).split(',')[1];
          if (base64Audio) {
            sendCandidateAudio(base64Audio, 'audio/webm');
          }
        };
        reader.readAsDataURL(audioBlob);
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } catch (err) {
      console.error('Audio recorder error:', err);
    }
  };

  const stopAudioRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  // Handle Text Submission
  const handleSendText = (e: React.FormEvent) => {
    e.preventDefault();
    if (!textInput.trim() || mediaDisrupted || isCompleted) return;
    sendCandidateMessage(textInput);
    setTextInput('');
  };

  // Start Interview from AV Gate
  const handleStartInterview = async () => {
    if (!sessionId || !cameraReady || !micReady) return;
    setIsStartingInterview(true);
    try {
      const res = await interviewSessionsApi.start(sessionId, {
        duration_minutes: selectedDuration,
        media_verified: true,
      });

      sendStartInterview(selectedDuration, true);
      if (res.deadline_at) {
        setDeadlineAt(res.deadline_at);
        const targetMs = parseDeadlineMs(res.deadline_at);
        const rem = typeof res.remaining_seconds === 'number' && res.remaining_seconds > 0
          ? res.remaining_seconds
          : Math.max(0, Math.floor((targetMs - Date.now()) / 1000));
        setRemainingSeconds(rem > 0 ? rem : selectedDuration * 60);
      } else {
        setRemainingSeconds(selectedDuration * 60);
      }
      setHasStarted(true);
    } catch (err: any) {
      alert(err.message || 'Failed to start interview');
    } finally {
      setIsStartingInterview(false);
    }
  };

  const formatCountdown = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // ==========================================
  // VIEW 1: COMPLETED INTERVIEW STATE
  // ==========================================
  if (isCompleted) {
    const isTimeout = completionReason === 'TIME_EXPIRED';
    const isInterrupted = completionReason === 'INTERRUPTED_MEDIA_FAILURE';

    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: 'var(--bg-app)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '2rem',
        }}
      >
        <div
          className="card"
          style={{
            maxWidth: '600px',
            width: '100%',
            textAlign: 'center',
            padding: '2.5rem 2rem',
            backgroundColor: '#FFFFFF',
            boxShadow: 'var(--shadow-lg)',
            borderRadius: 'var(--radius-xl)',
          }}
        >
          <div
            style={{
              width: 68,
              height: 68,
              borderRadius: '50%',
              backgroundColor: isTimeout ? '#FEF3C7' : isInterrupted ? '#FEE2E2' : '#D1FAE5',
              color: isTimeout ? '#D97706' : isInterrupted ? '#DC2626' : '#059669',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 1.5rem auto',
            }}
          >
            {isTimeout ? (
              <Clock size={36} />
            ) : isInterrupted ? (
              <AlertTriangle size={36} />
            ) : (
              <CheckCircle2 size={36} />
            )}
          </div>

          <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)', marginBottom: '0.75rem' }}>
            {isTimeout
              ? 'Interview time is over'
              : isInterrupted
              ? 'Interview Interrupted (Media Failure)'
              : 'Interview Completed'}
          </h2>

          <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '1.75rem' }}>
            {isTimeout
              ? `The configured round duration (${selectedDuration} min) deadline has passed. All candidate answers, multi-round evidence, and behavior logs have been finalized and persisted.`
              : isInterrupted
              ? 'The interview room lost required camera or microphone connectivity and exceeded the 30-second recovery timeout. All evidence collected up to this point has been preserved.'
              : 'All interview rounds and competency evaluations have finished. Your comprehensive evidence report and scorecard are now ready.'}
          </p>

          <div
            style={{
              padding: '1rem',
              backgroundColor: 'var(--bg-subtle)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-base)',
              marginBottom: '2rem',
              display: 'flex',
              justifyContent: 'space-around',
              fontSize: '0.8125rem',
            }}
          >
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Completion Reason:</span>{' '}
              <strong style={{ color: 'var(--text-main)' }}>{completionReason}</strong>
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Configured Round:</span>{' '}
              <strong style={{ color: 'var(--text-main)' }}>{selectedDuration} mins</strong>
            </div>
          </div>

          <Link
            to={`/interviews/${sessionId}/report`}
            className="btn btn-primary btn-lg"
            style={{ width: '100%', display: 'inline-flex', justifyContent: 'center', gap: '0.5rem' }}
          >
            <FileText size={18} />
            View Evidence Report
          </Link>
        </div>
      </div>
    );
  }

  // ==========================================
  // VIEW 2: PRE-INTERVIEW AV READINESS GATE
  // ==========================================
  if (!hasStarted) {
    const isAllReady = cameraReady && micReady;

    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: 'var(--bg-app)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <header
          style={{
            height: '64px',
            backgroundColor: '#FFFFFF',
            borderBottom: '1px solid var(--border-base)',
            padding: '0 2rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--primary-600)',
                color: '#FFFFFF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 800,
              }}
            >
              G
            </div>
            <div>
              <h2 style={{ fontSize: '1rem', fontWeight: 700 }}>Autonomous Interview Room</h2>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Session: {sessionId?.slice(0, 8)}...
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
            <ShieldCheck size={16} color="var(--primary-600)" />
            Device & Environmental Pre-Check
          </div>
        </header>

        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '2rem',
          }}
        >
          <div
            className="card"
            style={{
              maxWidth: '720px',
              width: '100%',
              backgroundColor: '#FFFFFF',
              boxShadow: 'var(--shadow-md)',
              borderRadius: 'var(--radius-xl)',
              padding: '2rem',
            }}
          >
            <div style={{ textAlign: 'center', marginBottom: '1.75rem' }}>
              <h3 style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-main)' }}>
                Pre-Interview Media & Readiness Check
              </h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
                Both camera and microphone access are required before starting the interview.
              </p>
            </div>

            {/* Video Preview and Mic Meter */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '1.5rem',
                marginBottom: '1.75rem',
              }}
            >
              {/* Camera Preview Tile */}
              <div
                style={{
                  backgroundColor: '#0F172A',
                  borderRadius: 'var(--radius-lg)',
                  height: '220px',
                  position: 'relative',
                  overflow: 'hidden',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  border: `2px solid ${cameraReady ? '#10B981' : '#DC2626'}`,
                }}
              >
                <video
                  ref={readinessVideoRef}
                  autoPlay
                  playsInline
                  muted
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'cover',
                    transform: 'scaleX(-1)',
                    display: cameraReady ? 'block' : 'none',
                  }}
                />
                {!cameraReady && (
                  <div style={{ textAlign: 'center', color: '#94A3B8', padding: '1rem' }}>
                    <VideoOff size={32} style={{ margin: '0 auto 0.5rem auto', color: '#EF4444' }} />
                    <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#E2E8F0' }}>
                      Camera Inactive or Blocked
                    </div>
                    <div style={{ fontSize: '0.725rem', color: '#94A3B8', marginTop: '0.25rem' }}>
                      {cameraError || 'Please allow browser camera permissions'}
                    </div>
                  </div>
                )}
                {cameraReady && (
                  <div
                    style={{
                      position: 'absolute',
                      top: '0.75rem',
                      left: '0.75rem',
                      backgroundColor: 'rgba(15, 23, 42, 0.85)',
                      padding: '0.2rem 0.6rem',
                      borderRadius: '9999px',
                      fontSize: '0.675rem',
                      fontWeight: 700,
                      color: '#10B981',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                    }}
                  >
                    <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: '#10B981' }} />
                    PREVIEW LIVE
                  </div>
                )}
              </div>

              {/* Status & Diagnostics Checklist */}
              <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {/* Camera Status Card */}
                  <div
                    style={{
                      padding: '0.85rem 1rem',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: cameraReady ? '#ECFDF5' : '#FEF2F2',
                      border: `1px solid ${cameraReady ? '#A7F3D0' : '#FECACA'}`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                      {cameraReady ? <Video size={18} color="#059669" /> : <VideoOff size={18} color="#DC2626" />}
                      <div>
                        <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: cameraReady ? '#065F46' : '#991B1B' }}>
                          Camera Video Stream
                        </div>
                        <div style={{ fontSize: '0.725rem', color: cameraReady ? '#047857' : '#B91C1C' }}>
                          {cameraReady ? `Active (${activeCameraLabel})` : cameraError || 'Permission Required'}
                        </div>
                      </div>
                    </div>
                    {cameraReady ? (
                      <CheckCircle2 size={18} color="#059669" />
                    ) : (
                      <AlertCircle size={18} color="#DC2626" />
                    )}
                  </div>

                  {/* Microphone Status Card */}
                  <div
                    style={{
                      padding: '0.85rem 1rem',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: micReady ? '#ECFDF5' : '#FEF2F2',
                      border: `1px solid ${micReady ? '#A7F3D0' : '#FECACA'}`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                      {micReady ? <Mic size={18} color="#059669" /> : <MicOff size={18} color="#DC2626" />}
                      <div>
                        <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: micReady ? '#065F46' : '#991B1B' }}>
                          Microphone Audio Track
                        </div>
                        <div style={{ fontSize: '0.725rem', color: micReady ? '#047857' : '#B91C1C' }}>
                          {micReady ? 'Live & unmuted' : micError || 'Permission Required'}
                        </div>
                      </div>
                    </div>
                    {micReady ? (
                      <CheckCircle2 size={18} color="#059669" />
                    ) : (
                      <AlertCircle size={18} color="#DC2626" />
                    )}
                  </div>

                  {/* Live Volume Meter Bar */}
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '0.25rem' }}>
                      <span style={{ color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                        <Volume2 size={13} /> Mic Audio Activity Level
                      </span>
                      <span style={{ fontWeight: 600, color: micReady ? 'var(--primary-600)' : 'var(--text-muted)' }}>
                        {micReady ? `${micVolume}%` : 'Muted'}
                      </span>
                    </div>
                    <div
                      style={{
                        height: '8px',
                        backgroundColor: 'var(--bg-subtle)',
                        borderRadius: '9999px',
                        overflow: 'hidden',
                        border: '1px solid var(--border-base)',
                      }}
                    >
                      <div
                        style={{
                          height: '100%',
                          width: `${micVolume}%`,
                          backgroundColor: micVolume > 60 ? '#EF4444' : micVolume > 15 ? '#10B981' : '#3B82F6',
                          transition: 'width 0.1s ease',
                        }}
                      />
                    </div>
                  </div>
                </div>

                {/* Device Selector & Retry */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '1rem' }}>
                  {availableCameras.length > 1 && (
                    <select
                      value={selectedCameraId}
                      onChange={(e) => startMedia(e.target.value)}
                      style={{
                        fontSize: '0.75rem',
                        padding: '0.3rem 0.5rem',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--border-base)',
                        maxWidth: '200px',
                      }}
                    >
                      {availableCameras.map((cam) => (
                        <option key={cam.deviceId} value={cam.deviceId}>
                          {cam.label}
                        </option>
                      ))}
                    </select>
                  )}
                  <button
                    onClick={() => startMedia()}
                    className="btn btn-secondary btn-sm"
                    style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                  >
                    <RefreshCw size={13} />
                    Re-check Devices
                  </button>
                </div>
              </div>
            </div>

            {/* HR-Configurable Duration Selection */}
            <div
              style={{
                padding: '1rem',
                backgroundColor: 'var(--bg-subtle)',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--border-base)',
                marginBottom: '1.75rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.65rem' }}>
                <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Clock size={15} color="var(--primary-600)" />
                  Scheduled Round Duration:
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Enforced by backend deadline
                </span>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {ALLOWED_DURATIONS.map((dur) => (
                  <button
                    key={dur}
                    type="button"
                    onClick={() => setSelectedDuration(dur)}
                    className={`btn btn-sm ${selectedDuration === dur ? 'btn-primary' : 'btn-secondary'}`}
                    style={{
                      flex: 1,
                      minWidth: '70px',
                      fontWeight: selectedDuration === dur ? 700 : 500,
                    }}
                  >
                    {dur} min
                  </button>
                ))}
              </div>
            </div>

            {/* Start Button */}
            <div>
              <button
                onClick={handleStartInterview}
                disabled={!isAllReady || isStartingInterview}
                className="btn btn-primary btn-lg"
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                  opacity: isAllReady ? 1 : 0.6,
                  cursor: isAllReady ? 'pointer' : 'not-allowed',
                }}
              >
                <Play size={18} />
                {isStartingInterview
                  ? 'Initializing Session...'
                  : isAllReady
                  ? `Start ${selectedDuration}-Minute Interview`
                  : 'Grant Camera & Microphone Access to Continue'}
              </button>
              {!isAllReady && (
                <div style={{ fontSize: '0.75rem', color: '#DC2626', textAlign: 'center', marginTop: '0.65rem' }}>
                  * The Start button is locked until both camera and microphone pass hardware readiness checks.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ==========================================
  // VIEW 3: ACTIVE LIVE INTERVIEW ROOM
  // ==========================================
  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: 'var(--bg-app)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Header */}
      <header
        style={{
          height: '64px',
          backgroundColor: '#FFFFFF',
          borderBottom: '1px solid var(--border-base)',
          padding: '0 1.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--primary-600)',
              color: '#FFFFFF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 800,
            }}
          >
            G
          </div>
          <div>
            <h2 style={{ fontSize: '1rem', fontWeight: 700 }}>Autonomous Interview Room</h2>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Session: {sessionId?.slice(0, 8)}...
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
          {/* Synchronized Authoritative Countdown Timer */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
              fontSize: '0.875rem',
              fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              color: remainingSeconds < 120 ? '#DC2626' : 'var(--text-main)',
              backgroundColor: remainingSeconds < 120 ? '#FEF2F2' : 'var(--bg-subtle)',
              border: `1px solid ${remainingSeconds < 120 ? '#FCA5A5' : 'var(--border-base)'}`,
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--radius-md)',
            }}
            title="Authoritative deadline countdown"
          >
            <Clock size={16} color={remainingSeconds < 120 ? '#DC2626' : 'var(--primary-600)'} />
            <span>{formatCountdown(remainingSeconds)}</span>
            <span style={{ fontSize: '0.675rem', fontWeight: 600, color: 'var(--text-muted)' }}>
              remaining
            </span>
          </div>

          {/* Connection Status */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              fontSize: '0.75rem',
              fontWeight: 600,
              color: isConnected ? '#059669' : '#DC2626',
            }}
          >
            <Radio size={14} className={isConnected ? 'animate-pulse' : ''} />
            {isConnected ? 'Connected' : 'Connecting...'}
          </div>

          {/* View Evidence Report */}
          <Link
            to={`/interviews/${sessionId}/report`}
            className="btn btn-secondary btn-sm"
          >
            View Evidence Report
          </Link>
        </div>
      </header>

      {/* ⚠️ MID-INTERVIEW MEDIA DISRUPTION RECOVERY BANNER */}
      {mediaDisrupted && (
        <div
          style={{
            margin: '0.75rem 1.25rem 0 1.25rem',
            padding: '1rem 1.25rem',
            backgroundColor: '#FEF2F2',
            border: '2px solid #DC2626',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 4px 6px -1px rgba(220, 38, 38, 0.1)',
            zIndex: 20,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <AlertTriangle size={24} color="#DC2626" />
            <div>
              <div style={{ fontSize: '0.925rem', fontWeight: 800, color: '#991B1B' }}>
                ⚠️ Camera / Microphone Disrupted — Interview Paused
              </div>
              <div style={{ fontSize: '0.8125rem', color: '#B91C1C', marginTop: '0.15rem' }}>
                {disruptionReason || 'Required media stream is unavailable.'} Please re-enable your camera and microphone.
              </div>
              <div style={{ fontSize: '0.75rem', color: '#7F1D1D', fontWeight: 700, marginTop: '0.25rem' }}>
                Time to recovery: {recoverySecondsLeft}s remaining before session is ended. (Interview deadline continues ticking).
              </div>
            </div>
          </div>
          <button
            onClick={() => startMedia()}
            className="btn btn-danger btn-sm"
            style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}
          >
            <RefreshCw size={13} />
            Restore Media Now
          </button>
        </div>
      )}

      {/* 🔴 RED INTEGRITY OBSERVATION ALERT BANNER */}
      {activeAlert && (
        <div
          style={{
            margin: '0.75rem 1.25rem 0 1.25rem',
            padding: '1rem 1.25rem',
            backgroundColor: '#FEF2F2',
            border: '2px solid #DC2626',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 4px 6px -1px rgba(220, 38, 38, 0.1)',
            zIndex: 10,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                backgroundColor: '#DC2626',
                color: '#FFFFFF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 800,
                fontSize: '16px',
                flexShrink: 0,
              }}
            >
              🔴
            </div>
            <div>
              <div style={{ fontSize: '0.925rem', fontWeight: 800, color: '#991B1B', letterSpacing: '0.02em' }}>
                {activeAlert.title || '🔴 INTEGRITY OBSERVATION'}
              </div>
              <div style={{ fontSize: '0.875rem', fontWeight: 600, color: '#B91C1C', marginTop: '0.15rem' }}>
                {activeAlert.message}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#7F1D1D', marginTop: '0.2rem' }}>
                Observed at {new Date(activeAlert.occurredAt).toLocaleTimeString()} • Evidence frame captured • Interview continues uninterrupted
              </div>
            </div>
          </div>
          <button
            onClick={dismissAlert}
            style={{
              padding: '0.4rem 0.85rem',
              backgroundColor: '#FFFFFF',
              border: '1px solid #DC2626',
              borderRadius: 'var(--radius-sm)',
              color: '#991B1B',
              fontSize: '0.75rem',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Acknowledge
          </button>
        </div>
      )}

      {/* Main Room Grid */}
      <div
        style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: '1fr 380px',
          gap: '1.25rem',
          padding: '1.25rem',
          maxHeight: 'calc(100vh - 64px)',
          overflow: 'hidden',
        }}
      >
        {/* Left Side: Avatar & Current Question */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '1.25rem',
            overflowY: 'auto',
          }}
        >
          {/* Avatar Card */}
          <div
            className="card"
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: '260px',
              backgroundColor: '#FFFFFF',
            }}
          >
            <AvatarVisualizer state={avatarState} size="lg" />
          </div>

          {/* Current Question Display Card */}
          <div
            className="card"
            style={{
              borderLeft: '4px solid var(--primary-600)',
              backgroundColor: '#FFFFFF',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--primary-600)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Active Question • {currentCapability || 'Competency Probe'}
              </div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Multi-Round Adaptive Q&A
              </span>
            </div>
            <h3 style={{ fontSize: '1.15rem', lineHeight: 1.5, color: 'var(--text-main)' }}>
              {currentAIQuestion || 'Hello! Welcome to your interview session. Please speak or type your answers clearly.'}
            </h3>
          </div>

          {/* Interaction & Response Input */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-main)' }}>
                Your Answer
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                {!isRecording ? (
                  <button
                    onClick={startAudioRecording}
                    disabled={mediaDisrupted || isCompleted}
                    className="btn btn-secondary btn-sm"
                    style={{ color: '#059669' }}
                    title="Speak answer via microphone"
                  >
                    <Mic size={14} />
                    Start Speaking
                  </button>
                ) : (
                  <button
                    onClick={stopAudioRecording}
                    className="btn btn-danger btn-sm"
                    title="Stop speaking & submit audio"
                  >
                    <MicOff size={14} />
                    Done Speaking (Submit)
                  </button>
                )}
              </div>
            </div>

            <form onSubmit={handleSendText} style={{ display: 'flex', gap: '0.5rem' }}>
              <input
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                disabled={mediaDisrupted || isCompleted}
                placeholder={
                  mediaDisrupted
                    ? 'Progression paused: please restore camera & mic...'
                    : 'Type your response or click "Start Speaking"...'
                }
                style={{ flex: 1 }}
              />
              <button
                type="submit"
                disabled={!textInput.trim() || mediaDisrupted || isCompleted}
                className="btn btn-primary"
              >
                <Send size={15} />
                Send
              </button>
            </form>
          </div>
        </div>

        {/* Right Side: Candidate WebCam Preview & Live Transcript */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '1.25rem',
            overflow: 'hidden',
          }}
        >
          {/* Candidate Camera View */}
          <div
            className="card"
            style={{
              padding: '0.75rem',
              backgroundColor: '#0F172A',
              borderRadius: 'var(--radius-lg)',
              overflow: 'hidden',
              position: 'relative',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
            }}
          >
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              style={{
                width: '100%',
                height: '190px',
                objectFit: 'cover',
                borderRadius: 'var(--radius-md)',
                transform: 'scaleX(-1)',
                border: '2px solid #10B981',
                boxShadow: '0 0 10px rgba(16, 185, 129, 0.25)',
                display: cameraActive && hasStream ? 'block' : 'none',
              }}
            />

            {/* LIVE Badge */}
            {cameraActive && hasStream && (
              <div
                style={{
                  position: 'absolute',
                  top: '1.25rem',
                  left: '1.25rem',
                  right: '1.25rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  pointerEvents: 'none',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.35rem',
                    backgroundColor: 'rgba(15, 23, 42, 0.8)',
                    backdropFilter: 'blur(4px)',
                    color: '#10B981',
                    padding: '0.2rem 0.55rem',
                    borderRadius: '9999px',
                    fontSize: '0.675rem',
                    fontWeight: 700,
                  }}
                >
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      backgroundColor: '#10B981',
                    }}
                  />
                  LIVE
                </div>

                <div
                  style={{
                    backgroundColor: 'rgba(15, 23, 42, 0.8)',
                    backdropFilter: 'blur(4px)',
                    color: '#CBD5E1',
                    padding: '0.2rem 0.55rem',
                    borderRadius: '9999px',
                    fontSize: '0.65rem',
                    fontWeight: 600,
                    maxWidth: '180px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  title={activeCameraLabel}
                >
                  📷 {activeCameraLabel}
                </div>
              </div>
            )}

            {/* Fallback when camera disabled */}
            {!(cameraActive && hasStream) && (
              <div
                style={{
                  height: '190px',
                  width: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.75rem',
                  color: '#94A3B8',
                  fontSize: '0.875rem',
                  backgroundColor: '#1E293B',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div
                  style={{
                    width: 52,
                    height: 52,
                    borderRadius: '50%',
                    backgroundColor: 'var(--primary-600)',
                    color: '#FFFFFF',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 800,
                    fontSize: '1.25rem',
                  }}
                >
                  G
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontWeight: 600, color: '#E2E8F0', fontSize: '0.875rem' }}>
                    {cameraActive ? 'Initializing Webcam...' : 'Camera Disabled'}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#94A3B8', marginTop: '0.15rem' }}>
                    Click "Camera Off" below to resume
                  </div>
                </div>
              </div>
            )}

            {/* Media controls bar */}
            <div
              style={{
                display: 'flex',
                gap: '0.75rem',
                marginTop: '0.75rem',
                alignItems: 'center',
              }}
            >
              <button
                onClick={toggleMic}
                className="btn btn-secondary btn-sm"
                style={{ color: micActive ? '#059669' : '#DC2626' }}
              >
                {micActive ? <Mic size={14} /> : <MicOff size={14} />}
                {micActive ? 'Mic On' : 'Mic Off'}
              </button>
              <button
                onClick={toggleCamera}
                className="btn btn-secondary btn-sm"
                style={{ color: cameraActive ? '#059669' : '#DC2626' }}
              >
                {cameraActive ? <Video size={14} /> : <VideoOff size={14} />}
                {cameraActive ? 'Camera On' : 'Camera Off'}
              </button>
            </div>
          </div>

          {/* Real-time Conversation Transcript Feed */}
          <div
            className="card"
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            <h4 style={{ fontSize: '0.95rem', marginBottom: '0.75rem' }}>
              Live Transcript
            </h4>
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
                paddingRight: '0.5rem',
              }}
            >
              {messages.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.8125rem', textAlign: 'center', margin: 'auto' }}>
                  Awaiting first question from interviewer...
                </div>
              ) : (
                messages.map((m, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '0.75rem',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: m.role === 'ai' ? 'var(--primary-50)' : 'var(--bg-subtle)',
                      border: `1px solid ${m.role === 'ai' ? 'var(--primary-200)' : 'var(--border-base)'}`,
                      fontSize: '0.8125rem',
                    }}
                  >
                    <div
                      style={{
                        fontWeight: 700,
                        fontSize: '0.7rem',
                        color: m.role === 'ai' ? 'var(--primary-700)' : 'var(--text-secondary)',
                        textTransform: 'uppercase',
                        marginBottom: '0.2rem',
                      }}
                    >
                      {m.role === 'ai' ? 'AI Interviewer' : 'Candidate'}
                    </div>
                    <div style={{ color: 'var(--text-main)', lineHeight: 1.5 }}>
                      {m.content}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
