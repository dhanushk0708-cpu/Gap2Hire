import asyncio
from datetime import datetime, timezone
import io
import logging
import os
from pathlib import Path
import time
from typing import Any
from uuid import UUID, uuid4

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.interview_integrity import InterviewIntegrityEvent
from app.models.user import User
from app.schemas.interview_integrity import IntegrityEventType
from app.services.interview_integrity import get_authorized_interview_session_for_integrity
from app.services.interview_ws_manager import connection_manager

logger = logging.getLogger(__name__)

# COCO Class mapping for YOLO
COCO_PERSON_CLASS_ID = 0
COCO_CELL_PHONE_CLASS_ID = 67


class SessionVisionTracker:
    def __init__(self):
        self.consecutive_phone_detections: int = 0
        self.consecutive_multi_person_detections: int = 0
        self.last_phone_event_time: float = 0.0
        self.last_multi_person_event_time: float = 0.0

    def reset_session(self):
        self.consecutive_phone_detections = 0
        self.consecutive_multi_person_detections = 0
        self.last_phone_event_time = 0.0
        self.last_multi_person_event_time = 0.0


class VisionService:
    _instance: "VisionService | None" = None

    def __init__(self):
        self._model = None
        self._is_available: bool = False
        self._init_attempted: bool = False
        self._trackers: dict[UUID, SessionVisionTracker] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "VisionService":
        if cls._instance is None:
            cls._instance = VisionService()
        return cls._instance

    def _ensure_model_loaded(self):
        if self._init_attempted:
            return
        self._init_attempted = True
        if not settings.vision_enabled:
            logger.info("Vision integrity service is disabled by configuration.")
            return

        try:
            from ultralytics import YOLO

            model_path = settings.vision_model_name
            logger.info(f"Loading YOLO model for vision integrity: {model_path}")
            self._model = YOLO(model_path)
            # Warm up JIT/PyTorch execution graph with small dummy image to eliminate cold-start delay
            dummy = Image.new("RGB", (64, 64), color=(0, 0, 0))
            self._model.predict(source=dummy, imgsz=416, classes=[COCO_PERSON_CLASS_ID, COCO_CELL_PHONE_CLASS_ID], verbose=False)
            self._is_available = True
            logger.info("YOLO model initialized and warmed up successfully for vision integrity.")
        except Exception as exc:
            logger.error(f"Failed to initialize YOLO model for vision integrity: {exc}", exc_info=True)
            self._is_available = False

    @property
    def is_available(self) -> bool:
        self._ensure_model_loaded()
        return self._is_available

    def get_tracker(self, session_id: UUID) -> SessionVisionTracker:
        if session_id not in self._trackers:
            self._trackers[session_id] = SessionVisionTracker()
        return self._trackers[session_id]

    def remove_tracker(self, session_id: UUID):
        self._trackers.pop(session_id, None)

    async def detect_objects(self, image_bytes: bytes) -> dict[str, Any]:
        """
        Runs YOLO object detection synchronously in an executor to avoid blocking the event loop.
        Extracts counts and confidences strictly for person (class 0) and cell phone (class 67).
        """
        self._ensure_model_loaded()
        if not self._is_available or self._model is None:
            return {
                "available": False,
                "person_count": 0,
                "phone_detected": False,
                "phone_confidence": 0.0,
                "person_confidences": [],
            }

        def _infer():
            try:
                img = Image.open(io.BytesIO(image_bytes))
                # Only look for person (0) and cell phone (67) with optimized 416 resolution for sub-50ms inference
                results = self._model.predict(
                    source=img,
                    imgsz=416,
                    conf=settings.vision_confidence_threshold,
                    classes=[COCO_PERSON_CLASS_ID, COCO_CELL_PHONE_CLASS_ID],
                    verbose=False,
                )
                if not results:
                    return 0, False, 0.0, []

                r = results[0]
                boxes = r.boxes
                if boxes is None or len(boxes) == 0:
                    return 0, False, 0.0, []

                person_confs = []
                phone_confs = []

                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    if cls_id == COCO_PERSON_CLASS_ID:
                        person_confs.append(conf)
                    elif cls_id == COCO_CELL_PHONE_CLASS_ID:
                        phone_confs.append(conf)

                person_cnt = len(person_confs)
                has_phone = len(phone_confs) > 0
                max_phone_conf = max(phone_confs) if phone_confs else 0.0

                return person_cnt, has_phone, max_phone_conf, person_confs
            except Exception as e:
                logger.error(f"Error during YOLO frame inference: {e}")
                return 0, False, 0.0, []

        loop = asyncio.get_running_loop()
        person_cnt, has_phone, max_phone_conf, person_confs = await loop.run_in_executor(None, _infer)

        return {
            "available": True,
            "person_count": person_cnt,
            "phone_detected": has_phone,
            "phone_confidence": max_phone_conf,
            "person_confidences": person_confs,
        }

    async def save_evidence_frame(self, session_id: UUID, event_id: UUID, image_bytes: bytes) -> str:
        """
        Saves a single evidence JPEG frame securely under storage/integrity/{session_id}/{event_id}.jpg.
        Returns the relative reference path.
        """
        base_dir = Path(settings.vision_storage_dir) / str(session_id)
        base_dir.mkdir(parents=True, exist_ok=True)
        file_path = base_dir / f"{event_id}.jpg"

        def _write():
            img = Image.open(io.BytesIO(image_bytes))
            # Save standard optimized JPEG
            img.convert("RGB").save(file_path, format="JPEG", quality=85)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write)

        return f"integrity/{session_id}/{event_id}.jpg"

    async def process_sampled_frame(
        self,
        session_id: UUID,
        image_bytes: bytes,
        user: User,
        db_session: AsyncSession | None = None,
    ) -> list[dict[str, Any]]:
        """
        Evaluates a sampled webcam frame from an authorized interview session.
        Applies consecutive-frame stability and cooldown thresholds.
        If a condition triggers, broadcasts observation to candidate and HR observer sockets immediately,
        saves evidence frame, and persists InterviewIntegrityEvent.
        """
        detection = await self.detect_objects(image_bytes)
        if not detection.get("available", False):
            return []

        person_count = detection["person_count"]
        phone_detected = detection["phone_detected"]
        phone_conf = detection["phone_confidence"]
        person_confs = detection["person_confidences"]
        multi_person_conf = person_confs[1] if len(person_confs) > 1 else (person_confs[0] if person_confs else 0.0)

        tracker = self.get_tracker(session_id)
        now = time.time()
        triggered_events = []

        async with self._lock:
            # 1. Update stability counters
            if phone_detected:
                tracker.consecutive_phone_detections += 1
            else:
                tracker.consecutive_phone_detections = 0

            if person_count > 1:
                tracker.consecutive_multi_person_detections += 1
            else:
                tracker.consecutive_multi_person_detections = 0

            # 2. Check PHONE_DETECTED trigger condition
            phone_triggered = (
                tracker.consecutive_phone_detections >= settings.vision_required_consecutive_detections
                and (now - tracker.last_phone_event_time) >= settings.vision_event_cooldown_seconds
            )

            # 3. Check MULTIPLE_PERSONS_DETECTED trigger condition
            multi_person_triggered = (
                tracker.consecutive_multi_person_detections >= settings.vision_required_consecutive_detections
                and (now - tracker.last_multi_person_event_time) >= settings.vision_event_cooldown_seconds
            )

            # Process Phone Trigger
            if phone_triggered:
                tracker.last_phone_event_time = now
                tracker.consecutive_phone_detections = 0

                event_id = uuid4()
                evidence_ref = f"integrity/{session_id}/{event_id}.jpg"
                evidence_url = f"/api/v1/interviews/{session_id}/integrity-evidence/{event_id}"
                occurred_iso = datetime.now(timezone.utc).isoformat()

                metadata = {
                    "object": "cell phone",
                    "confidence": round(phone_conf, 2),
                    "evidence_reference": evidence_ref,
                    "evidence_url": evidence_url,
                    "model": "YOLO",
                    "model_version": settings.vision_model_name,
                    "detection_count": 1,
                    "timestamp": occurred_iso,
                }

                # Broadcast observation event over WebSocket IMMEDIATELY to minimize UI alert latency
                payload = {
                    "type": "integrity_observation",
                    "event_type": IntegrityEventType.PHONE_DETECTED.value,
                    "alert_title": "🔴 INTEGRITY OBSERVATION",
                    "alert_message": "Mobile phone detected — Evidence frame captured",
                    "event_id": str(event_id),
                    "evidence_reference": evidence_ref,
                    "evidence_url": evidence_url,
                    "confidence": round(phone_conf, 2),
                    "occurred_at": occurred_iso,
                    "metadata": metadata,
                }
                await connection_manager.send_json(session_id, payload)
                triggered_events.append(payload)
                logger.warning(f"[VISION ALERT] Phone detected in session {session_id} (conf={phone_conf:.2f})")

                # Persist evidence frame & database record
                await self.save_evidence_frame(session_id, event_id, image_bytes)
                integrity_event = InterviewIntegrityEvent(
                    id=event_id,
                    interview_session_id=session_id,
                    event_type=IntegrityEventType.PHONE_DETECTED.value,
                    occurred_at=datetime.now(timezone.utc),
                    metadata_json=metadata,
                    created_at=datetime.now(timezone.utc),
                )
                if db_session is not None:
                    db_session.add(integrity_event)
                    await db_session.commit()
                else:
                    from app.db.session import async_session_factory
                    async with async_session_factory() as sess:
                        sess.add(integrity_event)
                        await sess.commit()

            # Process Multiple Persons Trigger
            if multi_person_triggered:
                tracker.last_multi_person_event_time = now
                tracker.consecutive_multi_person_detections = 0

                event_id = uuid4()
                evidence_ref = f"integrity/{session_id}/{event_id}.jpg"
                evidence_url = f"/api/v1/interviews/{session_id}/integrity-evidence/{event_id}"
                occurred_iso = datetime.now(timezone.utc).isoformat()

                metadata = {
                    "object": "multiple people",
                    "confidence": round(multi_person_conf, 2),
                    "evidence_reference": evidence_ref,
                    "evidence_url": evidence_url,
                    "model": "YOLO",
                    "model_version": settings.vision_model_name,
                    "detection_count": person_count,
                    "timestamp": occurred_iso,
                }

                # Broadcast observation event over WebSocket IMMEDIATELY to minimize UI alert latency
                payload = {
                    "type": "integrity_observation",
                    "event_type": IntegrityEventType.MULTIPLE_PERSONS_DETECTED.value,
                    "alert_title": "🔴 INTEGRITY OBSERVATION",
                    "alert_message": "Multiple people detected — Evidence frame captured",
                    "event_id": str(event_id),
                    "evidence_reference": evidence_ref,
                    "evidence_url": evidence_url,
                    "confidence": round(multi_person_conf, 2),
                    "occurred_at": occurred_iso,
                    "metadata": metadata,
                }
                await connection_manager.send_json(session_id, payload)
                triggered_events.append(payload)
                logger.warning(f"[VISION ALERT] Multiple persons ({person_count}) detected in session {session_id}")

                # Persist evidence frame & database record
                await self.save_evidence_frame(session_id, event_id, image_bytes)
                integrity_event = InterviewIntegrityEvent(
                    id=event_id,
                    interview_session_id=session_id,
                    event_type=IntegrityEventType.MULTIPLE_PERSONS_DETECTED.value,
                    occurred_at=datetime.now(timezone.utc),
                    metadata_json=metadata,
                    created_at=datetime.now(timezone.utc),
                )
                if db_session is not None:
                    db_session.add(integrity_event)
                    await db_session.commit()
                else:
                    from app.db.session import async_session_factory
                    async with async_session_factory() as sess:
                        sess.add(integrity_event)
                        await sess.commit()

        return triggered_events


vision_service = VisionService.get_instance()
