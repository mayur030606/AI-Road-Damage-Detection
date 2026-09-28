import React, { useState } from 'react';
import { EventLifecycleStatus, TelemetryEvent } from '../types';

interface StatusUpdateModalProps {
  event: TelemetryEvent | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdateStatus: (eventId: string, newStatus: EventLifecycleStatus) => Promise<void>;
}

const LIFECYCLE_OPTIONS: { status: EventLifecycleStatus; label: string; desc: string }[] = [
  {
    status: 'DETECTED',
    label: 'Detected',
    desc: 'Initial AI observation logged; pending municipal review.',
  },
  {
    status: 'VERIFIED',
    label: 'Verified',
    desc: 'Confirmed by municipal operator or multi-bus corroboration.',
  },
  {
    status: 'ASSIGNED',
    label: 'Assigned',
    desc: 'Dispatched to field maintenance team or contractor.',
  },
  {
    status: 'IN_PROGRESS',
    label: 'In Progress',
    desc: 'Road repairs or signal maintenance actively underway.',
  },
  {
    status: 'RESOLVED',
    label: 'Resolved',
    desc: 'Issue fixed and verified repaired; incident closed.',
  },
];

export const StatusUpdateModal: React.FC<StatusUpdateModalProps> = ({
  event,
  isOpen,
  onClose,
  onUpdateStatus,
}) => {
  const [selectedStatus, setSelectedStatus] = useState<EventLifecycleStatus>(
    event?.lifecycleStatus || 'DETECTED'
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Sync selected status when event changes
  React.useEffect(() => {
    if (event) {
      setSelectedStatus(event.lifecycleStatus);
      setErrorMsg(null);
    }
  }, [event]);

  if (!isOpen || !event) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await onUpdateStatus(event.eventId, selectedStatus);
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to update event status');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" data-testid="status-update-modal">
      <div className="modal-content">
        <div className="modal-header">
          <h3 className="modal-title">Update Lifecycle Status</h3>
          <button className="close-btn" onClick={onClose} aria-label="Close modal">
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <p className="modal-subtitle">
              Event ID: <span className="font-mono">{event.eventId}</span> ({event.eventType})
            </p>

            {errorMsg && <div className="modal-error">{errorMsg}</div>}

            <div className="status-options">
              {LIFECYCLE_OPTIONS.map((opt) => (
                <label
                  key={opt.status}
                  className={`status-option-card ${
                    selectedStatus === opt.status ? 'selected' : ''
                  }`}
                >
                  <input
                    type="radio"
                    name="lifecycleStatus"
                    value={opt.status}
                    checked={selectedStatus === opt.status}
                    onChange={() => setSelectedStatus(opt.status)}
                    className="radio-input"
                  />
                  <div className="option-info">
                    <div className="option-header">
                      <span className="option-label">{opt.label}</span>
                      <span className={`status-tag status-${opt.status.toLowerCase()}`}>
                        {opt.status}
                      </span>
                    </div>
                    <span className="option-desc">{opt.desc}</span>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Updating...' : 'Save Status'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
