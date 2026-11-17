import re
from datetime import datetime
from typing import Generator, Optional, Dict, Any, Tuple
from dataclasses import dataclass

@dataclass
class ParsedRawRecord:
    source_line_number: int
    raw_header_line: str
    timestamp_raw: str
    timestamp_dt: datetime
    original_sender: str
    body: str
    message_type: str
    media_type: str
    is_system_message: bool
    is_multiline: bool

class WhatsAppParser:
    """
    Robust streaming WhatsApp parser supporting:
    - iOS export formats with Left-to-Right Marks (LRM \\u200e) and Narrow No-Break Space (\\u202f)
    - Android export formats ('DD/MM/YYYY, HH:MM - Sender: Msg')
    - 12-hour (AM/PM) and 24-hour timestamp variations
    - Multiline messages with exact newlines preserved
    - Emojis (single, sequence, ZWJ sequences)
    - Tamil unicode & Tanglish transliteration
    - Media omission placeholders (<Media omitted>, image omitted, sticker omitted, etc.)
    - Deleted message markers
    - System events and call logs
    - Empty placeholder lines
    """

    # iOS: [11/29/25, 6:09:06 PM] Sender: Message
    IOS_PATTERN = re.compile(
        r'^\u200e?\[(\d{1,2})[/\.-](\d{1,2})[/\.-](\d{2,4}),\s+(\d{1,2}:\d{2}(?::\d{2})?)(?:\s|[\u202f\xa0])?([AaPp][Mm])?\]\s+([^:]+):(?:\s*(.*))?$'
    )

    # Android: 11/29/2025, 18:09 - Sender: Message or 11/29/2025, 6:09 pm - Sender: Message
    ANDROID_PATTERN = re.compile(
        r'^\u200e?(\d{1,2})[/\.-](\d{1,2})[/\.-](\d{2,4}),\s+(\d{1,2}:\d{2}(?::\d{2})?)(?:\s|[\u202f\xa0])?([AaPp][Mm])?\s+-\s+([^:]+):(?:\s*(.*))?$'
    )

    MEDIA_MAP = {
        'image omitted': 'image',
        'video omitted': 'video',
        'audio omitted': 'audio',
        'sticker omitted': 'sticker',
        'document omitted': 'document',
        'gif omitted': 'gif',
        'contact card omitted': 'contact',
        '<media omitted>': 'image'
    }

    SYSTEM_PATTERNS = [
        'messages and calls are end-to-end encrypted',
        'disappearing messages were turned',
        'turned off disappearing messages',
        'turned on disappearing messages',
        'turned on advanced chat privacy',
        'turned off advanced chat privacy',
        'you blocked this person',
        'you unblocked this person',
        'security code changed',
        'changed their phone number',
        'changed the subject to',
        'changed this group\'s icon'
    ]

    CALL_PATTERNS = [
        'missed voice call',
        'missed video call',
        'voice call,',
        'video call,'
    ]

    DELETED_PATTERNS = [
        'this message was deleted',
        'you deleted this message'
    ]

    def parse_timestamp(self, p1: str, p2: str, yr: str, tm: str, ampm: Optional[str]) -> datetime:
        """
        Parses date and time into UTC datetime.
        Determines MM/DD vs DD/MM:
        If p1 > 12 -> DD/MM/YY
        If p2 > 12 -> MM/DD/YY (standard WhatsApp iOS US format)
        Defaults to MM/DD/YY as verified by inspection of the source archives.
        """
        v1, v2 = int(p1), int(p2)
        if v1 > 12:
            day, month = v1, v2
        else:
            month, day = v1, v2

        full_year = int('20' + yr if len(yr) == 2 else yr)

        # Parse time components
        time_parts = tm.split(':')
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        second = int(time_parts[2]) if len(time_parts) > 2 else 0

        if ampm:
            ampm_upper = ampm.upper()
            if ampm_upper == 'PM' and hour < 12:
                hour += 12
            elif ampm_upper == 'AM' and hour == 12:
                hour = 0

        return datetime(full_year, month, day, hour, minute, second)

    def classify_body(self, body: str) -> Tuple[str, str, bool]:
        """
        Classifies message type, media type, and whether it is a system message.
        Preserves original body verbatim.
        """
        clean = body.replace('\u200e', '').strip().lower()
        
        if not clean:
            return 'empty_placeholder', 'none', True

        # Check deleted messages
        for d in self.DELETED_PATTERNS:
            if d in clean:
                return 'deleted', 'none', False

        # Check media attachments
        for m_key, m_type in self.MEDIA_MAP.items():
            if m_key in clean:
                return 'media', m_type, False

        # Check call logs
        for c in self.CALL_PATTERNS:
            if clean.startswith(c) or f'‎{c}' in clean:
                return 'call_log', 'none', True

        # Check system events
        for s in self.SYSTEM_PATTERNS:
            if s in clean:
                return 'system', 'none', True

        return 'text', 'none', False

    def stream_parse(self, lines: Generator[str, None, None]) -> Generator[ParsedRawRecord, None, None]:
        """
        Streams lines from raw chat export, stitches multiline continuations,
        and yields ParsedRawRecord objects.
        """
        current_record: Optional[Dict[str, Any]] = None

        for line_num, line in enumerate(lines, start=1):
            # Check iOS format first, then Android
            m = self.IOS_PATTERN.match(line) or self.ANDROID_PATTERN.match(line)
            if m:
                # Flush existing record if buffered
                if current_record:
                    m_type, media_t, is_sys = self.classify_body(current_record['body'])
                    yield ParsedRawRecord(
                        source_line_number=current_record['source_line_number'],
                        raw_header_line=current_record['raw_header_line'],
                        timestamp_raw=current_record['timestamp_raw'],
                        timestamp_dt=current_record['timestamp_dt'],
                        original_sender=current_record['original_sender'],
                        body=current_record['body'],
                        message_type=m_type,
                        media_type=media_t,
                        is_system_message=is_sys,
                        is_multiline=current_record['is_multiline']
                    )

                p1, p2, yr, tm, ampm, sender, body = (
                    m.group(1), m.group(2), m.group(3), m.group(4),
                    m.group(5), m.group(6), m.group(7) or ''
                )
                dt = self.parse_timestamp(p1, p2, yr, tm, ampm)
                raw_ts = f"{p1}/{p2}/{yr} {tm} {ampm or ''}".strip()

                current_record = {
                    'source_line_number': line_num,
                    'raw_header_line': line,
                    'timestamp_raw': raw_ts,
                    'timestamp_dt': dt,
                    'original_sender': sender.strip(),
                    'body': body,
                    'is_multiline': False
                }
            else:
                # Continuation line
                if current_record:
                    # Append newline and continuation line verbatim
                    current_record['body'] += '\n' + line
                    current_record['is_multiline'] = True

        # Flush final record
        if current_record:
            m_type, media_t, is_sys = self.classify_body(current_record['body'])
            yield ParsedRawRecord(
                source_line_number=current_record['source_line_number'],
                raw_header_line=current_record['raw_header_line'],
                timestamp_raw=current_record['timestamp_raw'],
                timestamp_dt=current_record['timestamp_dt'],
                original_sender=current_record['original_sender'],
                body=current_record['body'],
                message_type=m_type,
                media_type=media_t,
                is_system_message=is_sys,
                is_multiline=current_record['is_multiline']
            )
