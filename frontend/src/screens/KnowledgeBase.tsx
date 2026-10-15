// @ts-nocheck -- generated from the approved design under its JS runtime contract; not hand-written TypeScript.
/* eslint-disable @typescript-eslint/no-unused-vars */
import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { useNavigate } from "@/lib/navigate";

const { Button, Input, Select, Table, THead, TBody, TR, TH, TD, Stat } = UI;
const { Search, Check, User, FileText, Trash, Edit, Filter, Download, Upload, AlertCircle } = Icons;

export default function Screen() {
  const navigate = useNavigate();
  const brand = {
    primaryColor: '#1d4ed8',
    accentColor: '#059669',
    neutralColor: '#64748b',
    backgroundColor: '#f8fafc',
    radius: '0.5rem',
    fontHeading: 'Inter, system-ui, sans-serif',
    fontBody: 'Inter, system-ui, sans-serif',
  };

  // Current user (admin)
  const currentUser = {
    email: 'satya.ganaraju@quorq.ai',
    role: 'Administrator',
    name: 'Satya Ganaraju',
  };
  const isAdmin = currentUser.role === 'Administrator';

  // Initial document data — realistic week's worth
  const initialDocuments = [
    { id: 'doc-001', filename: 'Q4-2025-Financial-Report.pdf', file_type: 'PDF', file_size: 4823567, status: 'Ready', failure_reason: null, uploaded_by: 'satya.ganaraju@quorq.ai', created_at: '2026-10-08T09:14:00Z' },
    { id: 'doc-002', filename: 'Employee-Handbook-2026.docx', file_type: 'DOCX', file_size: 1248000, status: 'Ready', failure_reason: null, uploaded_by: 'satya.ganaraju@quorq.ai', created_at: '2026-10-08T10:02:00Z' },
    { id: 'doc-003', filename: 'Security-Policy-v4.md', file_type: 'MD', file_size: 28450, status: 'Ready', failure_reason: null, uploaded_by: 'satya.ganaraju@quorq.ai', created_at: '2026-10-09T14:30:00Z' },
    { id: 'doc-004', filename: 'API-Gateway-Architecture.pdf', file_type: 'PDF', file_size: 8901234, status: 'Ready', failure_reason: null, uploaded_by: 'satya.ganaraju@quorq.ai', created_at: '2026-10-09T15:45:00Z' },
    { id: 'doc-005', filename: 'Vendor-Onboarding-Guide.docx', file_type: 'DOCX', file_size: 567000, status: 'Ready', failure_reason: null, uploaded_by: 'satya.ganaraju@quorq.ai', created_at: '2026-10-10T08:20:00Z' },
    { id: 'doc-006', filename: 'Incident-Response-Runbook.txt', file_type: 'TXT', file_size: 18900, status: 'Ready', failure_reason: null, uploaded_by: 'satya.ganaraju@quorq.ai', created_at: '2026-10-10T11:15:00Z' },
    { id: 'doc-007', filename: 'Scanned-Legacy-Contracts.pdf', file_type: 'PDF', file_size: 15240000, status: 'Failed', failure_reason: 'Gemini embedding API quota exceeded during chunk embedding generation (chunk 34 of 142). Re-index to retry.', uploaded_by: 'satya.ganaraju@quorq.ai', created_at: '2026-10-11T13:00:00Z' },
    { id: 'doc-008', filename: 'Data-Retention-Policy.md', file_type: 'MD', file_size: 15600, status: 'Ready', failure_reason: null, uploaded_by: 'satya.ganaraju@quorq.ai', created_at: '2026-10-12T09:30:00Z' },
    { id: 'doc-009', filename: 'Quarterly-Board-Minutes.pdf', file_type: 'PDF', file_size: 3456000, status: 'Processing', failure_reason: null, uploaded_by: 'satya.ganaraju@quorq.ai', created_at: '2026-10-15T07:45:00Z' },
    { id: 'doc-010', filename: 'Cloud-Migration-Plan.docx', file_type: 'DOCX', file_size: 2340000, status: 'Processing', failure_reason: null, uploaded_by: 'satya.ganaraju@quorq.ai', created_at: '2026-10-15T08:10:00Z' },
    { id: 'doc-011', filename: 'Onsite-Network-Diagram.pdf', file_type: 'PDF', file_size: 6780000, status: 'Ready', failure_reason: null, uploaded_by: 'satya.ganaraju@quorq.ai', created_at: '2026-10-11T16:20:00Z' },
    { id: 'doc-012', filename: 'Compliance-Audit-Checklist.txt', file_type: 'TXT', file_size: 9800, status: 'Ready', failure_reason: null, uploaded_by: 'satya.ganaraju@quorq.ai', created_at: '2026-10-12T14:00:00Z' },
    { id: 'doc-013', filename: 'HR-Benefits-Summary-2026.docx', file_type: 'DOCX', file_size: 890000, status: 'Ready', failure_reason: null, uploaded_by: 'satya.ganaraju@quorq.ai', created_at: '2026-10-13T10:30:00Z' },
  ];

  const [documents, setDocuments] = React.useState(initialDocuments);
  const [searchTerm, setSearchTerm] = React.useState('');
  const [typeFilter, setTypeFilter] = React.useState('all');
  const [statusFilter, setStatusFilter] = React.useState('all');
  const [uploadError, setUploadError] = React.useState(null);
  const [uploading, setUploading] = React.useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = React.useState(null);
  const [recentlyUploaded, setRecentlyUploaded] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [loadError, setLoadError] = React.useState(null);
  const [isDragging, setIsDragging] = React.useState(false);
  const [retryingId, setRetryingId] = React.useState(null);

  // Simulate polling: processing documents transition to Ready after a delay
  const processingTimers = React.useRef([]);

  React.useEffect(() => {
    return () => {
      processingTimers.current.forEach(t => clearTimeout(t));
    };
  }, []);

  // Simulate processing completion for initial processing docs
  React.useEffect(() => {
    documents.forEach(doc => {
      if (doc.status === 'Processing') {
        const timer = setTimeout(() => {
          setDocuments(prev => prev.map(d => {
            if (d.id === doc.id) {
              // doc-010 fails for variety, doc-009 succeeds
              if (d.id === 'doc-010') {
                return { ...d, status: 'Failed', failure_reason: 'Gemini embedding API returned 429 Too Many Requests during batch embedding. Re-index to retry.' };
              }
              return { ...d, status: 'Ready', failure_reason: null };
            }
            return d;
          }));
        }, 6000);
        processingTimers.current.push(timer);
      }
    });
  }, []); // run once on mount

  // Counts for statistics
  const stats = {
    total: documents.length,
    ready: documents.filter(d => d.status === 'Ready').length,
    processing: documents.filter(d => d.status === 'Processing').length,
    failed: documents.filter(d => d.status === 'Failed').length,
  };

  // Filtered documents
  const filteredDocuments = documents.filter(doc => {
    const matchesSearch = searchTerm === '' || doc.filename.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = typeFilter === 'all' || doc.file_type === typeFilter;
    const matchesStatus = statusFilter === 'all' || doc.status === statusFilter;
    return matchesSearch && matchesType && matchesStatus;
  });

  // Helper: format file size
  function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
  }

  // Helper: format date
  function formatDate(iso) {
    const d = new Date(iso);
    const opts = { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' };
    return d.toLocaleDateString('en-US', opts);
  }

  // Handle file upload (simulated)
  function handleFileUpload(file) {
    setUploadError(null);

    if (!file) return;

    // Validate file type
    const ext = file.name.split('.').pop().toUpperCase();
    const allowedTypes = ['PDF', 'DOCX', 'TXT', 'MD'];
    if (!allowedTypes.includes(ext)) {
      setUploadError(file.name + ' is not a supported format. Only PDF, DOCX, TXT, and MD files are accepted.');
      return;
    }

    // Validate file size (25 MB)
    if (file.size > 25 * 1024 * 1024) {
      setUploadError(file.name + ' is ' + formatSize(file.size) + ' — exceeds the 25 MB upload limit.');
      return;
    }

    setUploading(true);

    // Simulate upload + processing start
    setTimeout(() => {
      const newDoc = {
        id: 'doc-' + String(documents.length + 1).padStart(3, '0') + '-' + Date.now().toString().slice(-4),
        filename: file.name,
        file_type: ext,
        file_size: file.size,
        status: 'Processing',
        failure_reason: null,
        uploaded_by: currentUser.email,
        created_at: new Date().toISOString(),
      };
      setDocuments(prev => [newDoc, ...prev]);
      setRecentlyUploaded(prev => [...prev, newDoc.id]);
      setUploading(false);

      // Simulate processing completion
      const timer = setTimeout(() => {
        setDocuments(prev => prev.map(d => {
          if (d.id === newDoc.id) {
            return { ...d, status: 'Ready', failure_reason: null };
          }
          return d;
        }));
        processingTimers.current.push(timer);
      }, 5000);
      processingTimers.current.push(timer);
    }, 800);
  }

  function handleFileInputChange(e) {
    const file = e.target.files && e.target.files[0];
    if (file) handleFileUpload(file);
    e.target.value = '';
  }

  function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    if (isAdmin) setIsDragging(true);
  }

  function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }

  function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (!isAdmin) return;
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  }

  function handleDelete(docId) {
    setDocuments(prev => prev.filter(d => d.id !== docId));
    setConfirmDeleteId(null);
    setRecentlyUploaded(prev => prev.filter(id => id !== docId));
  }

  function handleReindex(docId) {
    setRetryingId(docId);
    setDocuments(prev => prev.map(d =>
      d.id === docId ? { ...d, status: 'Processing', failure_reason: null } : d
    ));

    // Simulate reindex processing
    const timer = setTimeout(() => {
      setDocuments(prev => prev.map(d => {
        if (d.id === docId) {
          return { ...d, status: 'Ready', failure_reason: null };
        }
        return d;
      }));
      setRetryingId(null);
      processingTimers.current.push(timer);
    }, 4000);
    processingTimers.current.push(timer);
  }

  // Status badge component
  function StatusBadge({ status }) {
    const config = {
      Ready: {
        bg: 'rgba(5, 150, 105, 0.08)',
        color: brand.accentColor,
        label: 'Ready',
        dot: brand.accentColor,
      },
      Processing: {
        bg: 'rgba(29, 78, 216, 0.08)',
        color: brand.primaryColor,
        label: 'Processing',
        dot: brand.primaryColor,
      },
      Failed: {
        bg: 'rgba(220, 38, 38, 0.08)',
        color: '#dc2626',
        label: 'Failed',
        dot: '#dc2626',
      },
    };
    const c = config[status] || config.Processing;
    return React.createElement('span', {
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '2px 10px',
        borderRadius: '9999px',
        fontSize: '12px',
        fontWeight: 500,
        backgroundColor: c.bg,
        color: c.color,
        whiteSpace: 'nowrap',
        fontVariantNumeric: 'tabular-nums',
      },
    },
      React.createElement('span', {
        style: {
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: c.dot,
          animation: status === 'Processing' ? 'kaPulse 1.5s ease-in-out infinite' : 'none',
        },
        'aria-hidden': 'true',
      }),
      c.label
    );
  }

  // Stat card
  function StatCard({ label, value, tone }) {
    const tones = {
      total: { color: '#0f172a', bg: '#ffffff', border: '#e2e8f0' },
      ready: { color: brand.accentColor, bg: 'rgba(5, 150, 105, 0.04)', border: 'rgba(5, 150, 105, 0.2)' },
      processing: { color: brand.primaryColor, bg: 'rgba(29, 78, 216, 0.04)', border: 'rgba(29, 78, 216, 0.2)' },
      failed: { color: '#dc2626', bg: 'rgba(220, 38, 38, 0.04)', border: 'rgba(220, 38, 38, 0.2)' },
    };
    const t = tones[tone] || tones.total;
    return React.createElement('div', {
      style: {
        flex: '1 1 0',
        minWidth: '140px',
        backgroundColor: t.bg,
        border: '1px solid ' + t.border,
        borderRadius: brand.radius,
        padding: '14px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
      },
    },
      React.createElement('span', {
        style: {
          fontSize: '11px',
          fontWeight: 600,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          color: brand.neutralColor,
        },
      }, label),
      React.createElement('span', {
        style: {
          fontSize: '28px',
          fontWeight: 700,
          color: t.color,
          lineHeight: 1.1,
          fontVariantNumeric: 'tabular-nums',
        },
      }, String(value).padStart(2, '0'))
    );
  }

  const fileInputRef = React.useRef(null);

  // Inline styles for keyframes
  const styleElement = React.createElement('style', null, `
    @keyframes kaPulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.3; }
    }
    @keyframes kaSlideIn {
      from { opacity: 0; transform: translateY(-4px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes kaShimmer {
      0% { background-position: -200% 0; }
      100% { background-position: 200% 0; }
    }
    @media (prefers-reduced-motion: reduce) {
      * { animation: none !important; transition: none !important; }
    }
    .ka-row-enter { animation: kaSlideIn 0.3s ease-out; }
    .ka-link:hover { text-decoration: underline; }
    .ka-action-btn:focus-visible {
      outline: 2px solid ${brand.primaryColor};
      outline-offset: 2px;
    }
    .ka-search:focus-visible, .ka-select:focus-visible {
      outline: 2px solid ${brand.primaryColor};
      outline-offset: 1px;
    }
  `);

  // Dropzone (admin only)
  const dropzone = isAdmin ? React.createElement('div', {
    onDragOver: handleDragOver,
    onDragLeave: handleDragLeave,
    onDrop: handleDrop,
    style: {
      border: '2px dashed ' + (isDragging ? brand.primaryColor : '#cbd5e1'),
      borderRadius: brand.radius,
      backgroundColor: isDragging ? 'rgba(29, 78, 216, 0.04)' : '#ffffff',
      padding: '20px 24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: '16px',
      transition: 'all 0.2s ease',
      cursor: 'pointer',
    },
    onClick: () => fileInputRef.current && fileInputRef.current.click(),
    role: 'button',
    tabIndex: 0,
    'aria-label': 'Upload a document to the Knowledge Base. Supported formats: PDF, DOCX, TXT, MD. Maximum size 25 megabytes.',
    onKeyDown: (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        fileInputRef.current && fileInputRef.current.click();
      }
    },
  },
    React.createElement('div', {
      style: { display: 'flex', alignItems: 'center', gap: '14px' },
    },
      React.createElement(Icons.Upload, {
        size: 24,
        'aria-hidden': 'true',
        style: { color: brand.primaryColor },
      }),
      React.createElement('div', null,
        React.createElement('p', {
          style: { fontSize: '14px', fontWeight: 600, color: '#0f172a', margin: 0 },
        }, uploading ? 'Uploading and starting processing…' : 'Drop a file here or click to browse'),
        React.createElement('p', {
          style: { fontSize: '12px', color: brand.neutralColor, margin: '2px 0 0 0' },
        }, 'Supported: PDF, DOCX, TXT, MD — up to 25 MB. Files are stored permanently until explicitly deleted.')
      )
    ),
    uploading && React.createElement('div', {
      style: {
        fontSize: '12px',
        color: brand.primaryColor,
        fontWeight: 500,
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
      },
    },
      React.createElement('span', {
        style: {
          width: '10px',
          height: '10px',
          border: '2px solid rgba(29, 78, 216, 0.2)',
          borderTopColor: brand.primaryColor,
          borderRadius: '50%',
          display: 'inline-block',
          animation: 'kaPulse 0.8s linear infinite',
        },
        'aria-hidden': 'true',
      }),
      'Processing upload…'
    ),
    React.createElement('input', {
      ref: fileInputRef,
      type: 'file',
      accept: '.pdf,.docx,.txt,.md',
      onChange: handleFileInputChange,
      style: { display: 'none' },
      'aria-hidden': 'true',
      tabIndex: -1,
    })
  ) : null;

  // Upload error
  const uploadErrorEl = uploadError ? React.createElement('div', {
    style: {
      marginTop: '8px',
      padding: '10px 14px',
      borderRadius: brand.radius,
      backgroundColor: 'rgba(220, 38, 38, 0.06)',
      border: '1px solid rgba(220, 38, 38, 0.2)',
      fontSize: '13px',
      color: '#dc2626',
      display: 'flex',
      alignItems: 'flex-start',
      gap: '8px',
    },
    role: 'alert',
  },
    React.createElement(Icons.AlertCircle, { size: 16, 'aria-hidden': 'true', style: { flexShrink: 0, marginTop: '1px' } }),
    React.createElement('span', null, uploadError)
  ) : null;

  // Document table
  const tableContent = (function() {
    if (loadError) {
      return React.createElement('div', {
        style: { padding: '40px 24px', textAlign: 'center' },
      },
        React.createElement(Icons.AlertCircle, { size: 32, 'aria-hidden': 'true', style: { color: '#dc2626', marginBottom: '12px' } }),
        React.createElement('p', {
          style: { fontSize: '14px', fontWeight: 600, color: '#0f172a', margin: '0 0 4px 0' },
        }, 'Could not load the Knowledge Base'),
        React.createElement('p', {
          style: { fontSize: '13px', color: brand.neutralColor, margin: '0 0 16px 0' },
        }, loadError + ' The last known document list is shown below if available.'),
        React.createElement(UI.Button, {
          variant: 'outline',
          onClick: () => { setLoadError(null); },
        }, 'Retry loading')
      );
    }

    if (filteredDocuments.length === 0 && documents.length === 0) {
      // First use / empty state
      return React.createElement('div', {
        style: { padding: '48px 24px', textAlign: 'center' },
      },
        React.createElement(Icons.FileText, { size: 36, 'aria-hidden': 'true', style: { color: '#cbd5e1', marginBottom: '12px' } }),
        React.createElement('p', {
          style: { fontSize: '15px', fontWeight: 600, color: '#0f172a', margin: '0 0 6px 0' },
        }, isAdmin ? 'No documents in the Knowledge Base yet' : 'No documents have been uploaded'),
        React.createElement('p', {
          style: { fontSize: '13px', color: brand.neutralColor, margin: '0 0 16px 0', maxWidth: '380px', marginLeft: 'auto', marginRight: 'auto' },
        }, isAdmin
          ? 'Upload your first document using the dropzone above. Files are indexed and become searchable in chat.'
          : 'An administrator needs to upload documents before they appear here. Check back shortly.'
        )
      );
    }

    if (filteredDocuments.length === 0) {
      // No results from filters
      return React.createElement('div', {
        style: { padding: '40px 24px', textAlign: 'center' },
      },
        React.createElement(Icons.Search, { size: 28, 'aria-hidden': 'true', style: { color: '#cbd5e1', marginBottom: '10px' } }),
        React.createElement('p', {
          style: { fontSize: '14px', fontWeight: 600, color: '#0f172a', margin: '0 0 4px 0' },
        }, 'No documents match your filters'),
        React.createElement('p', {
          style: { fontSize: '13px', color: brand.neutralColor, margin: '0 0 14px 0' },
        }, 'Try adjusting the search term or clearing the type and status filters.'),
        React.createElement(UI.Button, {
          variant: 'outline',
          onClick: () => { setSearchTerm(''); setTypeFilter('all'); setStatusFilter('all'); },
        }, 'Clear all filters')
      );
    }

    return React.createElement(UI.Table, null,
      React.createElement(UI.THead, null,
        React.createElement(UI.TR, null,
          React.createElement(UI.TH, { style: { textAlign: 'left', whiteSpace: 'nowrap' } }, 'Filename'),
          React.createElement(UI.TH, { style: { textAlign: 'left', whiteSpace: 'nowrap' } }, 'Type'),
          React.createElement(UI.TH, { style: { textAlign: 'right', whiteSpace: 'nowrap' } }, 'Size'),
          React.createElement(UI.TH, { style: { textAlign: 'left', whiteSpace: 'nowrap' } }, 'Uploaded'),
          React.createElement(UI.TH, { style: { textAlign: 'left', whiteSpace: 'nowrap' } }, 'Status'),
          isAdmin ? React.createElement(UI.TH, { style: { textAlign: 'right', whiteSpace: 'nowrap' } }, 'Actions') : null,
        )
      ),
      React.createElement(UI.TBody, null,
        filteredDocuments.map(doc =>
          React.createElement(UI.TR, {
            key: doc.id,
            className: recentlyUploaded.includes(doc.id) ? 'ka-row-enter' : '',
            style: { cursor: 'pointer' },
            onClick: () => navigate('chat'),
          },
            // Filename
            React.createElement(UI.TD, {
              style: { maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
            },
              React.createElement('div', {
                style: { display: 'flex', alignItems: 'center', gap: '8px' },
              },
                React.createElement(Icons.FileText, {
                  size: 14,
                  'aria-hidden': 'true',
                  style: { color: brand.neutralColor, flexShrink: 0 },
                }),
                React.createElement('span', {
                  style: { fontSize: '13px', fontWeight: 500, color: '#0f172a' },
                  title: doc.filename,
                }, doc.filename)
              )
            ),
            // Type
            React.createElement(UI.TD, {
              style: { fontSize: '12px', color: brand.neutralColor, fontWeight: 500, whiteSpace: 'nowrap' },
            }, doc.file_type),
            // Size
            React.createElement(UI.TD, {
              style: { fontSize: '12px', color: brand.neutralColor, textAlign: 'right', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' },
            }, formatSize(doc.file_size)),
            // Upload date
            React.createElement(UI.TD, {
              style: { fontSize: '12px', color: brand.neutralColor, whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' },
            }, formatDate(doc.created_at)),
            // Status
            React.createElement(UI.TD, {
              style: { whiteSpace: 'nowrap' },
            },
              React.createElement('div', {
                style: { display: 'flex', flexDirection: 'column', gap: '4px' },
              },
                React.createElement(StatusBadge, { status: doc.status }),
                doc.status === 'Failed' && doc.failure_reason ? React.createElement('span', {
                  style: {
                    fontSize: '11px',
                    color: '#991b1b',
                    maxWidth: '320px',
                    lineHeight: '1.4',
                  },
                }, doc.failure_reason) : null
              )
            ),
            // Actions (admin only)
            isAdmin ? React.createElement(UI.TD, {
              style: { textAlign: 'right', whiteSpace: 'nowrap' },
              onClick: (e) => e.stopPropagation(),
            },
              React.createElement('div', {
                style: { display: 'inline-flex', alignItems: 'center', gap: '4px' },
              },
                // Download
                React.createElement('button', {
                  className: 'ka-action-btn',
                  onClick: () => { /* simulated download */ },
                  'aria-label': 'Download ' + doc.filename,
                  title: 'Download',
                  style: {
                    border: 'none',
                    backgroundColor: 'transparent',
                    padding: '6px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    color: brand.neutralColor,
                    display: 'inline-flex',
                    alignItems: 'center',
                    transition: 'background-color 0.15s, color 0.15s',
                  },
                  onMouseEnter: (e) => { e.currentTarget.style.backgroundColor = '#f1f5f9'; e.currentTarget.style.color = brand.primaryColor; },
                  onMouseLeave: (e) => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = brand.neutralColor; },
                }, React.createElement(Icons.Download, { size: 15, 'aria-hidden': 'true' })),
                // Re-index (only for failed or ready)
                doc.status !== 'Processing' ? React.createElement('button', {
                  className: 'ka-action-btn',
                  onClick: () => handleReindex(doc.id),
                  'aria-label': 'Re-index ' + doc.filename,
                  title: 'Re-index',
                  disabled: retryingId === doc.id,
                  style: {
                    border: 'none',
                    backgroundColor: 'transparent',
                    padding: '6px',
                    borderRadius: '6px',
                    cursor: retryingId === doc.id ? 'wait' : 'pointer',
                    color: brand.neutralColor,
                    display: 'inline-flex',
                    alignItems: 'center',
                    opacity: retryingId === doc.id ? 0.5 : 1,
                    transition: 'background-color 0.15s, color 0.15s',
                  },
                  onMouseEnter: (e) => { if (retryingId !== doc.id) { e.currentTarget.style.backgroundColor = '#f1f5f9'; e.currentTarget.style.color = brand.primaryColor; } },
                  onMouseLeave: (e) => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = brand.neutralColor; },
                }, retryingId === doc.id
                  ? React.createElement('span', { style: { width: '15px', height: '15px', border: '2px solid rgba(29,78,216,0.2)', borderTopColor: brand.primaryColor, borderRadius: '50%', display: 'inline-block', animation: 'kaPulse 0.8s linear infinite' }, 'aria-hidden': 'true' })
                  : React.createElement(Icons.Edit, { size: 15, 'aria-hidden': 'true' })
                ) : null,
                // Delete
                React.createElement('button', {
                  className: 'ka-action-btn',
                  onClick: () => setConfirmDeleteId(doc.id),
                  'aria-label': 'Delete ' + doc.filename,
                  title: 'Delete',
                  style: {
                    border: 'none',
                    backgroundColor: 'transparent',
                    padding: '6px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    color: brand.neutralColor,
                    display: 'inline-flex',
                    alignItems: 'center',
                    transition: 'background-color 0.15s, color 0.15s',
                  },
                  onMouseEnter: (e) => { e.currentTarget.style.backgroundColor = 'rgba(220,38,38,0.08)'; e.currentTarget.style.color = '#dc2626'; },
                  onMouseLeave: (e) => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = brand.neutralColor; },
                }, React.createElement(Icons.Trash, { size: 15, 'aria-hidden': 'true' }))
              )
            ) : null
          )
        )
      )
    );
  })();

  // Delete confirmation dialog
  const deleteDialog = confirmDeleteId ? (function() {
    const doc = documents.find(d => d.id === confirmDeleteId);
    if (!doc) return null;
    return React.createElement('div', {
      style: {
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50,
        animation: 'kaSlideIn 0.15s ease-out',
      },
      onClick: () => setConfirmDeleteId(null),
      onKeyDown: (e) => { if (e.key === 'Escape') setConfirmDeleteId(null); },
    },
      React.createElement('div', {
        role: 'dialog',
        'aria-modal': 'true',
        'aria-labelledby': 'delete-dialog-title',
        onClick: (e) => e.stopPropagation(),
        style: {
          backgroundColor: '#ffffff',
          borderRadius: brand.radius,
          padding: '24px',
          maxWidth: '420px',
          width: '90%',
          boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
        },
      },
        React.createElement('h2', {
          id: 'delete-dialog-title',
          style: { fontSize: '16px', fontWeight: 700, color: '#0f172a', margin: '0 0 8px 0', fontFamily: brand.fontHeading },
        }, 'Delete document?'),
        React.createElement('p', {
          style: { fontSize: '14px', color: '#334155', margin: '0 0 20px 0', lineHeight: 1.5 },
        }, React.createElement('strong', null, doc.filename) + ' will be permanently removed along with all extracted chunks, embeddings, and index metadata. This cannot be undone.'),
        React.createElement('div', {
          style: { display: 'flex', justifyContent: 'flex-end', gap: '10px' },
        },
          React.createElement(UI.Button, {
            variant: 'outline',
            onClick: () => setConfirmDeleteId(null),
          }, 'Cancel'),
          React.createElement(UI.Button, {
            variant: 'destructive',
            onClick: () => handleDelete(confirmDeleteId),
            style: { backgroundColor: '#dc2626', color: '#ffffff', border: 'none', borderRadius: brand.radius, padding: '8px 16px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' },
          }, 'Delete permanently')
        )
      )
    );
  })() : null;

  return React.createElement('div', {
    style: {
      fontFamily: brand.fontBody,
      color: '#0f172a',
      backgroundColor: brand.backgroundColor,
      minHeight: '100%',
      padding: '24px 28px',
    },
  },
    styleElement,

    // Screen heading
    React.createElement('div', {
      style: { marginBottom: '20px' },
    },
      React.createElement('div', {
        style: { display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' },
      },
        React.createElement('div', null,
          React.createElement('h1', {
            style: { fontSize: '22px', fontWeight: 700, color: '#0f172a', margin: 0, fontFamily: brand.fontHeading, letterSpacing: '-0.01em' },
          }, 'Knowledge Base'),
          React.createElement('p', {
            style: { fontSize: '13px', color: brand.neutralColor, margin: '4px 0 0 0' },
          }, documents.length + ' documents indexed — answers cite these sources before falling back to Gemini general knowledge'),
        ),
        // Account link
        React.createElement('button', {
          onClick: () => navigate('account'),
          className: 'ka-link',
          style: {
            border: 'none',
            backgroundColor: 'transparent',
            fontSize: '13px',
            color: brand.neutralColor,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            textDecoration: 'none',
          },
          'aria-label': 'Go to account settings for ' + currentUser.email,
        },
          React.createElement(Icons.User, { size: 14, 'aria-hidden': 'true' }),
          currentUser.email
        )
      )
    ),

    // Statistics
    React.createElement('div', {
      style: { display: 'flex', gap: '12px', marginBottom: '20px', flexWrap: 'wrap' },
    },
      React.createElement(StatCard, { label: 'Total Documents', value: stats.total, tone: 'total' }),
      React.createElement(StatCard, { label: 'Ready', value: stats.ready, tone: 'ready' }),
      React.createElement(StatCard, { label: 'Processing', value: stats.processing, tone: 'processing' }),
      React.createElement(StatCard, { label: 'Failed', value: stats.failed, tone: 'failed' })
    ),

    // Upload dropzone (admin only)
    isAdmin && React.createElement('div', {
      style: { marginBottom: '20px' },
    },
      dropzone,
      uploadErrorEl
    ),

    // Search + filters bar
    React.createElement('div', {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        marginBottom: '12px',
        flexWrap: 'wrap',
      },
    },
      // Search
      React.createElement('div', {
        style: { position: 'relative', flex: '1 1 240px', minWidth: '200px' },
      },
        React.createElement(Icons.Search, {
          size: 15,
          'aria-hidden': 'true',
          style: { position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: brand.neutralColor, pointerEvents: 'none' },
        }),
        React.createElement(UI.Input, {
          className: 'ka-search',
          type: 'text',
          placeholder: 'Search by filename…',
          value: searchTerm,
          onChange: (e) => setSearchTerm(e.target.value),
          'aria-label': 'Search documents by filename',
          style: {
            paddingLeft: '32px',
            fontSize: '13px',
            height: '34px',
            borderRadius: brand.radius,
            border: '1px solid #cbd5e1',
            backgroundColor: '#ffffff',
            width: '100%',
          },
        })
      ),
      // Type filter
      React.createElement('div', null,
        React.createElement('label', {
          htmlFor: 'type-filter',
          style: { fontSize: '11px', fontWeight: 600, color: brand.neutralColor, display: 'block', marginBottom: '2px', letterSpacing: '0.04em', textTransform: 'uppercase' },
        }, 'Type'),
        React.createElement(UI.Select, {
          id: 'type-filter',
          className: 'ka-select',
          value: typeFilter,
          onChange: (e) => setTypeFilter(e.target.value),
          'aria-label': 'Filter documents by file type',
          style: {
            fontSize: '13px',
            height: '34px',
            borderRadius: brand.radius,
            border: '1px solid #cbd5e1',
            backgroundColor: '#ffffff',
            cursor: 'pointer',
          },
        },
          React.createElement('option', { value: 'all' }, 'All types'),
          React.createElement('option', { value: 'PDF' }, 'PDF'),
          React.createElement('option', { value: 'DOCX' }, 'DOCX'),
          React.createElement('option', { value: 'TXT' }, 'TXT'),
          React.createElement('option', { value: 'MD' }, 'MD')
        )
      ),
      // Status filter
      React.createElement('div', null,
        React.createElement('label', {
          htmlFor: 'status-filter',
          style: { fontSize: '11px', fontWeight: 600, color: brand.neutralColor, display: 'block', marginBottom: '2px', letterSpacing: '0.04em', textTransform: 'uppercase' },
        }, 'Status'),
        React.createElement(UI.Select, {
          id: 'status-filter',
          className: 'ka-select',
          value: statusFilter,
          onChange: (e) => setStatusFilter(e.target.value),
          'aria-label': 'Filter documents by processing status',
          style: {
            fontSize: '13px',
            height: '34px',
            borderRadius: brand.radius,
            border: '1px solid #cbd5e1',
            backgroundColor: '#ffffff',
            cursor: 'pointer',
          },
        },
          React.createElement('option', { value: 'all' }, 'All statuses'),
          React.createElement('option', { value: 'Ready' }, 'Ready'),
          React.createElement('option', { value: 'Processing' }, 'Processing'),
          React.createElement('option', { value: 'Failed' }, 'Failed')
        )
      ),
      // Results count
      React.createElement('span', {
        style: {
          fontSize: '12px',
          color: brand.neutralColor,
          marginLeft: 'auto',
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        },
      }, filteredDocuments.length + ' of ' + documents.length + ' documents')
    ),

    // Document table
    React.createElement('div', {
      style: {
        backgroundColor: '#ffffff',
        border: '1px solid #e2e8f0',
        borderRadius: brand.radius,
        overflow: 'hidden',
      },
    },
      React.createElement('div', {
        style: { overflowX: 'auto' },
      },
        React.createElement('div', {
          style: { minWidth: '720px' },
        },
          tableContent
        )
      )
    ),

    // Processing note
    stats.processing > 0 && React.createElement('div', {
      style: {
        marginTop: '12px',
        fontSize: '12px',
        color: brand.neutralColor,
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
      },
    },
      React.createElement('span', {
        style: {
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          backgroundColor: brand.primaryColor,
          animation: 'kaPulse 1.5s ease-in-out infinite',
        },
        'aria-hidden': 'true',
      }),
      stats.processing + ' document' + (stats.processing > 1 ? 's are' : ' is') + ' being indexed — status updates automatically every few seconds.'
    ),

    // Delete confirmation dialog
    deleteDialog
  );
}
