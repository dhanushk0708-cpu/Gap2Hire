import React, { useState, useEffect, useRef } from 'react';
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
} from 'lucide-react';
import { useInterviewWebSocket } from '../../core/websocket/useInterviewWebSocket';
import { AvatarVisualizer } from '../../shared/components/AvatarVisualizer';
import { interviewSessionsApi } from '../../core/api/endpoints';

export const CandidateLiveRoomView: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  // Local device media states
  const [micActive, setMicActive] = useState(true);
  const [cameraActive, setCameraActive] = useState(true);
  const [isRecording, setIsRecording] = useState(false);
  const [textInput, setTextInput] = useState('');
  const [secondsElapsed, setSecondsElapsed] = useState(0);
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [hasStream, setHasStream] = useState(false);
  const [availableCameras, setAvailableCameras] = useState<{ deviceId: string; label: string }[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<string>('');
  const [activeCameraLabel, setActiveCameraLabel] = useState<string>('Webcam');

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // Setup WebSocket connection
  const {
    isConnected,
    avatarState,
    messages,
    currentAIQuestion,
    currentCapability,
    activeAlert,
    dismissAlert,
    sendCandidateMessage,
    sendCandidateAudio,
    sendIntegrityEvent,
    sendVisionFrame,
  } = useInterviewWebSocket({
    sessionId: sessionId || '',
    onAIMessage: React.useCallback((text: string) => {
      // If browser SpeechSynthesis is available and candidate has audio enabled
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        window.speechSynthesis.speak(utterance);
      }
    }, []),
  });

  // Dedicated effect to bind mediaStream to the video element and trigger play()
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    if (mediaStream && cameraActive) {
      if (video.srcObject !== mediaStream) {
        video.srcObject = mediaStream;
      }
      video.muted = true;
      console.log('[WEBCAM DIAGNOSTIC 2] Assigned videoRef.current.srcObject:', {
        srcObject: video.srcObject,
        readyState: video.readyState,
        videoWidth: video.videoWidth,
        videoHeight: video.videoHeight,
      });

      video
        .play()
        .then(() => {
          console.log('[WEBCAM DIAGNOSTIC 3] video.play() SUCCESS:', {
            readyState: video.readyState,
            videoWidth: video.videoWidth,
            videoHeight: video.videoHeight,
          });
        })
        .catch((err) => {
          console.error('[WEBCAM DIAGNOSTIC 3] video.play() ERROR:', err);
        });
    } else if (!cameraActive && video.srcObject) {
      video.pause();
    }
  }, [mediaStream, cameraActive]);

  // Sample a frame from webcam video every 500ms and send for YOLO vision detection
  useEffect(() => {
    if (!isConnected || !cameraActive || !hasStream) return;

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
  }, [isConnected, cameraActive, hasStream, sendVisionFrame]);

  // Session elapsed timer
  useEffect(() => {
    const timer = setInterval(() => {
      setSecondsElapsed((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // WebCam & Microphone media initialization
  const startMedia = React.useCallback(
    async (preferredDeviceId?: string) => {
      try {
        let chosenDeviceId = preferredDeviceId;

        // If not specified, inspect available cameras and prioritize physical hardware
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

        console.log('[WEBCAM DIAGNOSTIC 0] Requesting getUserMedia with constraints:', videoConstraints);

        const stream = await navigator.mediaDevices.getUserMedia({
          video: videoConstraints,
          audio: true,
        });

        // Enumerate devices post-permission to obtain labeled device lists
        const postDevices = await navigator.mediaDevices.enumerateDevices();
        const postVideoInputs = postDevices.filter((d) => d.kind === 'videoinput');
        setAvailableCameras(
          postVideoInputs.map((d, idx) => ({
            deviceId: d.deviceId,
            label: d.label || `Camera ${idx + 1}`,
          }))
        );

        const currentTrack = stream.getVideoTracks()[0];
        console.log('[WEBCAM DIAGNOSTIC 1] getUserMedia resolved:', {
          streamExists: !!stream,
          videoTracksLength: stream.getVideoTracks().length,
          trackReadyState: currentTrack?.readyState,
          trackEnabled: currentTrack?.enabled,
          trackLabel: currentTrack?.label,
          trackSettings: currentTrack?.getSettings(),
        });

        // If the automatically selected camera is "Smart Connect Camera" (a virtual camera),
        // and an "Integrated Camera" is present, automatically switch to the real physical webcam!
        if (
          !preferredDeviceId &&
          currentTrack?.label.toLowerCase().includes('smart connect')
        ) {
          const realWebcam = postVideoInputs.find(
            (d) =>
              d.label.toLowerCase().includes('integrated') ||
              (!d.label.toLowerCase().includes('smart connect') &&
                !d.label.toLowerCase().includes('virtual'))
          );
          if (realWebcam && realWebcam.deviceId) {
            console.warn(
              `[WEBCAM REDIRECT] Default was '${currentTrack.label}' (virtual). Switching to physical camera: '${realWebcam.label}'`
            );
            stream.getTracks().forEach((t) => t.stop());
            return startMedia(realWebcam.deviceId);
          }
        }

        const currentLabel = currentTrack?.label || 'Webcam';
        setActiveCameraLabel(currentLabel);
        setSelectedCameraId(currentTrack?.getSettings().deviceId || '');

        // Stop prior stream tracks if replacing
        if (mediaStreamRef.current) {
          mediaStreamRef.current.getTracks().forEach((t) => t.stop());
        }

        mediaStreamRef.current = stream;
        setMediaStream(stream);
        setHasStream(true);

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.muted = true;
          videoRef.current.play().catch(console.warn);
        }

        sendIntegrityEvent('CAMERA_CONNECTED', { info: 'Camera initialized', device: currentLabel });
        sendIntegrityEvent('MICROPHONE_CONNECTED', { info: 'Microphone initialized' });
      } catch (err) {
        console.warn('Webcam/Mic access denied or unavailable:', err);
        setHasStream(false);
      }
    },
    [sendIntegrityEvent]
  );

  useEffect(() => {
    let active = true;
    startMedia();

    return () => {
      active = false;
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
      }
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, [startMedia]);

  // Tab visibility telemetry (Neutral observational reporting)
  useEffect(() => {
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
  }, [sendIntegrityEvent]);

  // Toggle Camera
  const toggleCamera = () => {
    if (mediaStreamRef.current) {
      const videoTrack = mediaStreamRef.current.getVideoTracks()[0];
      if (videoTrack) {
        const nextEnabled = !videoTrack.enabled;
        videoTrack.enabled = nextEnabled;
        setCameraActive(nextEnabled);
        sendIntegrityEvent(nextEnabled ? 'CAMERA_CONNECTED' : 'CAMERA_DISCONNECTED');
        if (nextEnabled && videoRef.current) {
          videoRef.current.play().catch(console.warn);
        }
      }
    }
  };

  // Toggle Microphone
  const toggleMic = () => {
    if (mediaStreamRef.current) {
      const audioTrack = mediaStreamRef.current.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        setMicActive(audioTrack.enabled);
        sendIntegrityEvent(audioTrack.enabled ? 'MICROPHONE_CONNECTED' : 'MICROPHONE_DISCONNECTED');
      }
    }
  };

  // Audio recording handlers for spoken responses
  const startAudioRecording = () => {
    if (!mediaStreamRef.current) return;
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
    if (!textInput.trim()) return;
    sendCandidateMessage(textInput);
    setTextInput('');
  };

  const formatTimer = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: 'var(--bg-app)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Room Header */}
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
          {/* Elapsed Timer */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              fontSize: '0.875rem',
              fontWeight: 600,
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-main)',
              backgroundColor: 'var(--bg-subtle)',
              padding: '0.3rem 0.65rem',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <Clock size={15} color="var(--primary-600)" />
            {formatTimer(secondsElapsed)}
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

          {/* End / Exit Interview */}
          <Link
            to={`/interviews/${sessionId}/report`}
            className="btn btn-secondary btn-sm"
          >
            View Evidence Report
          </Link>
        </div>
      </header>

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
        {/* Left Side: Avatar Visualizer & Current Question */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '1.25rem',
            overflowY: 'auto',
          }}
        >
          {/* AI Avatar Card */}
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
                placeholder="Type your response or click 'Start Speaking'..."
                style={{ flex: 1 }}
              />
              <button
                type="submit"
                disabled={!textInput.trim()}
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
              onLoadedMetadata={() => {
                if (videoRef.current) {
                  videoRef.current.play().catch(console.warn);
                }
              }}
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

            {/* LIVE Badge & Active Device Name overlay */}
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
                    letterSpacing: '0.04em',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
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

            {/* Fallback Gap2Hire Logo placeholder when camera is unavailable or disabled */}
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
                    boxShadow: '0 4px 12px rgba(37, 99, 235, 0.3)',
                  }}
                >
                  G
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontWeight: 600, color: '#E2E8F0', fontSize: '0.875rem' }}>
                    {cameraActive ? 'Initializing Webcam...' : 'Camera Disabled'}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#94A3B8', marginTop: '0.15rem' }}>
                    {cameraActive ? 'Requesting device permission' : 'Click "Camera Off" below to resume'}
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

            {/* Camera Switcher if multiple video devices exist */}
            {availableCameras.length > 1 && (
              <div
                style={{
                  marginTop: '0.5rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  width: '100%',
                  justifyContent: 'center',
                }}
              >
                <label style={{ fontSize: '0.7rem', color: '#94A3B8', fontWeight: 600 }}>Source:</label>
                <select
                  value={selectedCameraId}
                  onChange={(e) => startMedia(e.target.value)}
                  style={{
                    fontSize: '0.725rem',
                    padding: '0.15rem 0.35rem',
                    backgroundColor: '#1E293B',
                    color: '#E2E8F0',
                    border: '1px solid #334155',
                    borderRadius: 'var(--radius-sm)',
                    maxWidth: '180px',
                    cursor: 'pointer',
                  }}
                >
                  {availableCameras.map((cam) => (
                    <option key={cam.deviceId} value={cam.deviceId}>
                      {cam.label}
                    </option>
                  ))}
                </select>
              </div>
            )}
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
