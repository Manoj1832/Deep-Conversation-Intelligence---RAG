from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Set
from uuid import uuid4, UUID
from backend.app.models.schemas import SourceMessageSchema, ConversationSessionSchema
from backend.app.config import config

class ConversationSessionizer:
    """
    Chronological conversation session segmentation based on inactivity threshold.
    Default threshold: 6.0 hours.
    Preserves strict chronological order. Does not treat sessions as confirmed topics.
    """

    def __init__(self, inactivity_threshold_hours: float = 6.0):
        self.threshold = timedelta(hours=inactivity_threshold_hours)
        self.threshold_hours = inactivity_threshold_hours

    def segment(self, messages: List[SourceMessageSchema]) -> Tuple[List[ConversationSessionSchema], List[SourceMessageSchema]]:
        """
        Takes unsorted/sorted messages, sorts them chronologically,
        assigns session_ids, and returns (sessions, updated_messages).
        """
        if not messages:
            return [], []

        # Ensure strict chronological sort: (timestamp, source_line_number)
        sorted_messages = sorted(messages, key=lambda m: (m.timestamp, m.source_line_number))

        sessions: List[ConversationSessionSchema] = []
        current_session_id = uuid4()
        session_messages: List[SourceMessageSchema] = [sorted_messages[0]]
        sorted_messages[0].session_id = current_session_id

        for i in range(1, len(sorted_messages)):
            prev_msg = sorted_messages[i - 1]
            curr_msg = sorted_messages[i]

            time_diff = curr_msg.timestamp - prev_msg.timestamp
            # Inactivity threshold boundary check
            if time_diff > self.threshold:
                # Finalize previous session
                sessions.append(self._build_session(current_session_id, session_messages))
                # Start new session
                current_session_id = uuid4()
                session_messages = [curr_msg]
            else:
                session_messages.append(curr_msg)

            curr_msg.session_id = current_session_id

        # Finalize last session
        if session_messages:
            sessions.append(self._build_session(current_session_id, session_messages))

        return sessions, sorted_messages

    def _build_session(self, session_id: UUID, msgs: List[SourceMessageSchema]) -> ConversationSessionSchema:
        partner_count = sum(1 for m in msgs if m.sender == "partner")
        user_count = sum(1 for m in msgs if m.sender == "user")
        
        # Unique archive IDs contributing to this session
        archive_ids: List[UUID] = list({m.archive_id for m in msgs})

        return ConversationSessionSchema(
            session_id=session_id,
            start_timestamp=msgs[0].timestamp,
            end_timestamp=msgs[-1].timestamp,
            inactivity_threshold_hours=self.threshold_hours,
            message_count=len(msgs),
            partner_message_count=partner_count,
            user_message_count=user_count,
            source_archive_ids=archive_ids,
            created_at=datetime.utcnow()
        )
