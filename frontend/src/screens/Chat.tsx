// @ts-nocheck -- generated from the approved design under its JS runtime contract; not hand-written TypeScript.
/* eslint-disable @typescript-eslint/no-unused-vars */
import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";

const { Button, Input, Textarea, Select } = UI;
const { Plus, Search, Check, X, User, Settings, FileText, Trash, ArrowLeft, AlertCircle, CheckCircle } = Icons;

const SAMPLE_CONVERSATIONS = [
  {
    id: 'conv-001',
    title: 'Q3 Information Security Review',
    created_at: '2026-10-14T09:23:00Z',
    updated_at: '2026-10-14T10:15:00Z',
    messages: [
      {
        id: 'msg-001',
        role: 'user',
        content: 'What is our current password policy for service accounts?',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-14T09:23:00Z',
        citations: []
      },
      {
        id: 'msg-002',
        role: 'assistant',
        content: 'Service accounts must use passwords of at least 20 characters with rotation every 90 days. Privileged service accounts require vault-managed credentials with automatic rotation enabled. Shared service account passwords are prohibited — each service must have its own dedicated credential pair.',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-14T09:23:06Z',
        citations: [
          { id: 'cit-001', filename: 'InfoSec_Policy_v3.2.pdf', page_section: 'Page 14, §4.3', chunk_id: 'chunk-047' },
          { id: 'cit-002', filename: 'InfoSec_Policy_v3.2.pdf', page_section: 'Page 15, §4.5', chunk_id: 'chunk-049' }
        ]
      },
      {
        id: 'msg-003',
        role: 'user',
        content: 'Who approves exceptions to the password rotation policy?',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-14T09:45:00Z',
        citations: []
      },
      {
        id: 'msg-004',
        role: 'assistant',
        content: 'Exceptions to the password rotation policy must be approved by the CISO and documented in the Security Exception Register. Each exception has a maximum validity of 6 months and must include a business justification, risk assessment, and compensating controls. The Security Committee reviews all active exceptions quarterly.',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-14T09:45:09Z',
        citations: [
          { id: 'cit-003', filename: 'InfoSec_Policy_v3.2.pdf', page_section: 'Page 18, §5.2', chunk_id: 'chunk-058' }
        ]
      },
      {
        id: 'msg-005',
        role: 'user',
        content: 'What are the GDPR fines for non-compliance with data retention schedules?',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-14T10:15:00Z',
        citations: []
      },
      {
        id: 'msg-006',
        role: 'assistant',
        content: 'I could not find specific information about GDPR fine amounts or data retention schedules in your uploaded Knowledge Base documents. Under GDPR Article 83, fines can reach up to €20 million or 4% of global annual turnover, whichever is higher. This is general knowledge from Gemini, not from your company documents. If this topic is relevant, consider uploading your data retention policy to the Knowledge Base.',
        is_fallback: true,
        is_error: false,
        created_at: '2026-10-14T10:15:14Z',
        citations: []
      }
    ]
  },
  {
    id: 'conv-002',
    title: 'Employee Onboarding Workflow',
    created_at: '2026-10-12T14:30:00Z',
    updated_at: '2026-10-12T15:02:00Z',
    messages: [
      {
        id: 'msg-007',
        role: 'user',
        content: 'What documents does a new hire need to submit on day one?',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-12T14:30:00Z',
        citations: []
      },
      {
        id: 'msg-008',
        role: 'assistant',
        content: 'New hires must submit the following on their first day: a completed I-9 form with acceptable identification documents, a signed Non-Disclosure Agreement, the direct deposit authorization form, and emergency contact information. The hiring manager is responsible for collecting these documents and forwarding them to HR within 3 business days of the start date.',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-12T14:30:07Z',
        citations: [
          { id: 'cit-004', filename: 'Onboarding_Checklist_2026.docx', page_section: '§2.1, Para 3', chunk_id: 'chunk-012' },
          { id: 'cit-005', filename: 'HR_Handbook_Rev4.pdf', page_section: 'Page 8, §1.4', chunk_id: 'chunk-021' }
        ]
      },
      {
        id: 'msg-009',
        role: 'user',
        content: 'How long does the probationary period last?',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-12T15:01:00Z',
        citations: []
      },
      {
        id: 'msg-010',
        role: 'assistant',
        content: 'The standard probationary period is 90 days from the start date. During this period, new hires undergo performance reviews at 30, 60, and 90 days. The hiring manager must submit a probationary review form to HR at least 5 business days before the 90-day mark. Extension of the probationary period requires written approval from the department head and HR Director.',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-12T15:01:08Z',
        citations: [
          { id: 'cit-006', filename: 'HR_Handbook_Rev4.pdf', page_section: 'Page 22, §3.7', chunk_id: 'chunk-034' }
        ]
      }
    ]
  },
  {
    id: 'conv-003',
    title: 'API Gateway Rate Limiting',
    created_at: '2026-10-10T11:00:00Z',
    updated_at: '2026-10-10T11:35:00Z',
    messages: [
      {
        id: 'msg-011',
        role: 'user',
        content: 'What are the default rate limits for the production API gateway?',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-10T11:00:00Z',
        citations: []
      },
      {
        id: 'msg-012',
        role: 'assistant',
        content: 'The production API gateway enforces a default rate limit of 1,000 requests per minute per API key, with a burst allowance of 200 requests in any 5-second window. Enterprise tier keys have a limit of 10,000 requests per minute. Rate limit headers (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset) are included in all API responses for client-side throttling.',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-10T11:00:09Z',
        citations: [
          { id: 'cit-007', filename: 'API_Gateway_Config.pdf', page_section: 'Page 7, §3.2', chunk_id: 'chunk-019' }
        ]
      },
      {
        id: 'msg-013',
        role: 'user',
        content: 'How do I configure custom rate limits for a specific client?',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-10T11:35:00Z',
        citations: []
      },
      {
        id: 'msg-014',
        role: 'assistant',
        content: 'The Gemini API returned an error (429: quota_exceeded) while generating an answer for this question. Your documents, chat history, and account are all preserved — no data was lost. Please try sending the question again in a few minutes. If the problem persists, contact your administrator to verify the Gemini API key and quota status.',
        is_fallback: false,
        is_error: true,
        created_at: '2026-10-10T11:35:16Z',
        citations: []
      }
    ]
  },
  {
    id: 'conv-004',
    title: 'Expense Report Guidelines',
    created_at: '2026-10-08T08:45:00Z',
    updated_at: '2026-10-08T09:10:00Z',
    messages: [
      {
        id: 'msg-015',
        role: 'user',
        content: 'What is the per diem rate for domestic travel?',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-08T08:45:00Z',
        citations: []
      },
      {
        id: 'msg-016',
        role: 'assistant',
        content: 'The standard domestic per diem rate is $89 per day for meals and incidentals. For tier-1 cities (New York, San Francisco, Los Angeles, Chicago, Boston), the rate is $134 per day. Per diem covers breakfast ($15), lunch ($25), and dinner ($49) — the remaining amount covers incidentals. Receipts are not required for per diem claims, but all other expenses over $25 require itemized receipts. Expense reports must be submitted within 30 days of trip completion.',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-08T08:45:12Z',
        citations: [
          { id: 'cit-008', filename: 'Travel_Expense_Policy.pdf', page_section: 'Page 5, §2.3', chunk_id: 'chunk-008' },
          { id: 'cit-009', filename: 'Travel_Expense_Policy.pdf', page_section: 'Page 6, §2.4', chunk_id: 'chunk-009' }
        ]
      }
    ]
  },
  {
    id: 'conv-005',
    title: 'VPN Setup for Remote Access',
    created_at: '2026-10-07T16:20:00Z',
    updated_at: '2026-10-07T16:50:00Z',
    messages: [
      {
        id: 'msg-017',
        role: 'user',
        content: 'How do I configure the company VPN on macOS?',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-07T16:20:00Z',
        citations: []
      },
      {
        id: 'msg-018',
        role: 'assistant',
        content: 'To configure the company VPN on macOS: Open System Settings, select VPN, click "Add VPN Configuration" and choose IKEv2. Enter the server address vpn.quorq.ai. Use your corporate email as the remote ID and your Active Directory password for authentication. Enable "Connect on demand" for automatic reconnection. Click Apply, then connect. If you encounter certificate errors, download the root certificate from the IT portal and add it to your Keychain.',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-07T16:20:13Z',
        citations: [
          { id: 'cit-010', filename: 'VPN_Setup_Guide.md', page_section: '§1.3, Lines 24–38', chunk_id: 'chunk-005' }
        ]
      },
      {
        id: 'msg-019',
        role: 'user',
        content: 'What ports need to be open on the firewall for the VPN to work?',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-07T16:48:00Z',
        citations: []
      },
      {
        id: 'msg-020',
        role: 'assistant',
        content: 'The following ports must be open for IKEv2 VPN: UDP 500 (IKE), UDP 4500 (NAT-T), and ESP (protocol 50) for the IPsec data channel. If you are behind a restrictive firewall, the VPN client will automatically fall back to TCP 443 encapsulation. No additional inbound ports are required on the client side. The gateway IP is 203.0.113.42 — add it to your firewall allowlist if needed.',
        is_fallback: false,
        is_error: false,
        created_at: '2026-10-07T16:48:10Z',
        citations: [
          { id: 'cit-011', filename: 'VPN_Setup_Guide.md', page_section: '§3.1, Lines 52–58', chunk_id: 'chunk-011' }
        ]
      }
    ]
  }
];

function formatTime(iso) {
  var d = new Date(iso);
  var h = d.getHours();
  var m = d.getMinutes();
  return (h < 10 ? '0' + h : h) + ':' + (m < 10 ? '0' + m : m);
}

function formatDate(iso) {
  var d = new Date(iso);
  var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return months[d.getMonth()] + ' ' + d.getDate();
}

function formatDateFull(iso) {
  var d = new Date(iso);
  var months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  return months[d.getMonth()] + ' ' + d.getDate() + ', ' + d.getFullYear();
}

function getLastMessagePreview(conv) {
  if (conv.messages.length === 0) return 'No messages yet';
  var last = conv.messages[conv.messages.length - 1];
  if (last.is_error) return 'Gemini API error — retry needed';
  if (last.is_fallback) return 'Answered from general knowledge';
  if (last.role === 'user') return last.content;
  return last.content;
}

function generateResponse(question) {
  var q = question.toLowerCase();
  var id = 'cit-' + Date.now() + '-' + Math.random().toString(36).substr(2, 4);

  if (q.indexOf('password') >= 0 || q.indexOf('security') >= 0 || q.indexOf('credential') >= 0 || q.indexOf('encryption') >= 0 || q.indexOf('mfa') >= 0 || q.indexOf('authentication') >= 0) {
    return {
      content: 'Based on the Information Security Policy in your Knowledge Base, all accounts accessing production systems require multi-factor authentication. Service account passwords must be at least 20 characters with 90-day rotation, and privileged credentials must be vault-managed with automatic rotation. Standard user passwords require a minimum of 12 characters.',
      is_fallback: false,
      citations: [
        { id: id, filename: 'InfoSec_Policy_v3.2.pdf', page_section: 'Page 14, §4.3', chunk_id: 'chunk-047' }
      ]
    };
  }

  if (q.indexOf('onboard') >= 0 || q.indexOf('hire') >= 0 || q.indexOf('new employee') >= 0 || q.indexOf('hr') >= 0 || q.indexOf('probation') >= 0) {
    return {
      content: 'Your Knowledge Base documents indicate that new employees must complete the onboarding checklist within their first week, including the I-9 form, NDA, direct deposit setup, and security awareness training. The probationary period is 90 days with performance reviews at 30, 60, and 90 days. The hiring manager submits a review form to HR at least 5 business days before the 90-day mark.',
      is_fallback: false,
      citations: [
        { id: id, filename: 'Onboarding_Checklist_2026.docx', page_section: '§2.1, Para 3', chunk_id: 'chunk-012' },
        { id: id + '-2', filename: 'HR_Handbook_Rev4.pdf', page_section: 'Page 22, §3.7', chunk_id: 'chunk-034' }
      ]
    };
  }

  if (q.indexOf('api') >= 0 || q.indexOf('rate limit') >= 0 || q.indexOf('gateway') >= 0 || q.indexOf('throttle') >= 0 || q.indexOf('endpoint') >= 0) {
    return {
      content: 'The API Gateway Configuration document specifies a default rate limit of 1,000 requests per minute per API key, with a burst allowance of 200 requests in any 5-second window. Enterprise tier keys are capped at 10,000 requests per minute. Rate limit headers are included on all responses for client-side throttling. Custom limits can be configured per client through the gateway admin panel.',
      is_fallback: false,
      citations: [
        { id: id, filename: 'API_Gateway_Config.pdf', page_section: 'Page 7, §3.2', chunk_id: 'chunk-019' }
      ]
    };
  }

  if (q.indexOf('expense') >= 0 || q.indexOf('per diem') >= 0 || q.indexOf('reimburse') >= 0 || q.indexOf('travel') >= 0) {
    return {
      content: 'According to the Travel and Expense Policy in your Knowledge Base, the standard domestic per diem is $89 per day for meals and incidentals, with tier-1 cities at $134 per day. Receipts are required for all non-per-diem expenses over $25. Expense reports must be submitted within 30 days of trip completion through the expense management portal.',
      is_fallback: false,
      citations: [
        { id: id, filename: 'Travel_Expense_Policy.pdf', page_section: 'Page 5, §2.3', chunk_id: 'chunk-008' }
      ]
    };
  }

  if (q.indexOf('vpn') >= 0 || q.indexOf('remote') >= 0 || q.indexOf('network') >= 0 || q.indexOf('firewall') >= 0 || q.indexOf('port') >= 0) {
    return {
      content: 'The VPN Setup Guide in your Knowledge Base specifies IKEv2 with server address vpn.quorq.ai. Required ports are UDP 500, UDP 4500, and ESP protocol 50, with automatic TCP 443 fallback for restrictive firewalls. Multi-factor authentication is enforced for all VPN connections. The gateway IP is 203.0.113.42.',
      is_fallback: false,
      citations: [
        { id: id, filename: 'VPN_Setup_Guide.md', page_section: '§1.3, Lines 24–38', chunk_id: 'chunk-005' }
      ]
    };
  }

  if (q.indexOf('document') >= 0 || q.indexOf('upload') >= 0 || q.indexOf('knowledge base') >= 0) {
    return {
      content: 'Your Knowledge Base currently contains indexed documents in PDF, DOCX, TXT, and MD formats. Administrators can upload new documents through the Knowledge Base tab. Each document goes through text extraction, chunking at approximately 1,000 characters with 150-character overlap, and Gemini 768-dimensional embedding generation before becoming searchable.',
      is_fallback: false,
      citations: [
        { id: id, filename: 'System_Overview.md', page_section: '§1, Lines 1–12', chunk_id: 'chunk-001' }
      ]
    };
  }

  return {
    content: 'I could not find information about this topic in your uploaded Knowledge Base documents. Based on Gemini\'s general knowledge: ' + question.charAt(0).toUpperCase() + question.slice(1) + ' — this answer has not been verified against your company documents. If this topic is important to your work, consider uploading relevant documents to the Knowledge Base so future questions can be answered with citations.',
    is_fallback: true,
    citations: []
  };
}

export default function Screen() {
  var conversationsState = React.useState(SAMPLE_CONVERSATIONS);
  var conversations = conversationsState[0];
  var setConversations = conversationsState[1];

  var selectedIdState = React.useState(SAMPLE_CONVERSATIONS[0].id);
  var selectedId = selectedIdState[0];
  var setSelectedId = selectedIdState[1];

  var inputState = React.useState('');
  var input = inputState[0];
  var setInput = inputState[1];

  var isSendingState = React.useState(false);
  var isSending = isSendingState[0];
  var setIsSending = isSendingState[1];

  var searchState = React.useState('');
  var search = searchState[0];
  var setSearch = searchState[1];

  var deleteConfirmIdState = React.useState(null);
  var deleteConfirmId = deleteConfirmIdState[0];
  var setDeleteConfirmId = deleteConfirmIdState[1];

  var retryingState = React.useState(false);
  var retrying = retryingState[0];
  var setRetrying = retryingState[1];

  var messagesEndRef = React.useRef(null);
  var inputRef = React.useRef(null);

  var selectedConversation = conversations.find(function(c) { return c.id === selectedId; });
  var messages = selectedConversation ? selectedConversation.messages : [];

  var filteredConversations = conversations
    .filter(function(c) {
      if (!search.trim()) return true;
      return c.title.toLowerCase().indexOf(search.toLowerCase()) >= 0;
    })
    .sort(function(a, b) {
      return new Date(b.updated_at) - new Date(a.updated_at);
    });

  React.useEffect(function() {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages.length, isSending]);

  function handleSelectConversation(id) {
    setSelectedId(id);
    setDeleteConfirmId(null);
  }

  function handleCreateConversation() {
    var newId = 'conv-' + Date.now();
    var now = new Date().toISOString();
    var newConv = {
      id: newId,
      title: 'New Conversation',
      created_at: now,
      updated_at: now,
      messages: []
    };
    setConversations([newConv].concat(conversations));
    setSelectedId(newId);
    setDeleteConfirmId(null);
    setTimeout(function() {
      if (inputRef.current) inputRef.current.focus();
    }, 50);
  }

  function handleDeleteConversation(id) {
    var remaining = conversations.filter(function(c) { return c.id !== id; });
    setConversations(remaining);
    setDeleteConfirmId(null);
    if (selectedId === id) {
      if (remaining.length > 0) {
        setSelectedId(remaining[0].id);
      } else {
        setSelectedId(null);
      }
    }
  }

  function handleSendMessage(e) {
    if (e) e.preventDefault();
    var question = input.trim();
    if (!question || isSending) return;

    var now = new Date().toISOString();
    var userMsg = {
      id: 'msg-' + Date.now(),
      role: 'user',
      content: question,
      is_fallback: false,
      is_error: false,
      created_at: now,
      citations: []
    };

    var isFirstMessage = messages.length === 0;
    var newTitle = isFirstMessage ? question.substring(0, 50) + (question.length > 50 ? '…' : '') : selectedConversation.title;

    setConversations(conversations.map(function(c) {
      if (c.id !== selectedId) return c;
      return {
        ...c,
        title: newTitle,
        messages: c.messages.concat([userMsg]),
        updated_at: now
      };
    }));

    setInput('');
    setIsSending(true);

    setTimeout(function() {
      var response = generateResponse(question);
      var respMsg = {
        id: 'msg-' + Date.now() + '-resp',
        role: 'assistant',
        content: response.content,
        is_fallback: response.is_fallback,
        is_error: false,
        created_at: new Date().toISOString(),
        citations: response.citations
      };

      setConversations(function(prev) {
        return prev.map(function(c) {
          if (c.id !== selectedId) return c;
          return {
            ...c,
            messages: c.messages.concat([respMsg]),
            updated_at: new Date().toISOString()
          };
        });
      });
      setIsSending(false);
      setRetrying(false);
    }, 1400);
  }

  function handleRetryLastQuestion() {
    if (!selectedConversation || messages.length === 0) return;
    var lastUserMsg = null;
    for (var i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        lastUserMsg = messages[i];
        break;
      }
    }
    if (!lastUserMsg) return;

    var errorIdx = -1;
    for (var j = messages.length - 1; j >= 0; j--) {
      if (messages[j].is_error) {
        errorIdx = j;
        break;
      }
    }

    setRetrying(true);
    setIsSending(true);

    setTimeout(function() {
      var response = generateResponse(lastUserMsg.content);
      var respMsg = {
        id: 'msg-' + Date.now() + '-retry',
        role: 'assistant',
        content: response.content,
        is_fallback: response.is_fallback,
        is_error: false,
        created_at: new Date().toISOString(),
        citations: response.citations
      };

      setConversations(function(prev) {
        return prev.map(function(c) {
          if (c.id !== selectedId) return c;
          var newMsgs = c.messages.slice();
          if (errorIdx >= 0) {
            newMsgs[errorIdx] = respMsg;
          } else {
            newMsgs.push(respMsg);
          }
          return {
            ...c,
            messages: newMsgs,
            updated_at: new Date().toISOString()
          };
        });
      });
      setIsSending(false);
      setRetrying(false);
    }, 1400);
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  }

  var hasErrorInLastMessage = messages.length > 0 && messages[messages.length - 1].is_error;

  function renderMessage(msg) {
    var isUser = msg.role === 'user';
    return React.createElement('div', {
      key: msg.id,
      style: {
        display: 'flex',
        gap: '10px',
        marginBottom: '16px',
        animation: 'msgEnter 0.3s ease-out'
      }
    },
      React.createElement('div', {
        style: {
          flexShrink: 0,
          width: '28px',
          height: '28px',
          borderRadius: brand.radius,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: isUser ? brand.primaryColor : (msg.is_error ? brand.neutralColor + '20' : brand.accentColor + '15'),
          color: isUser ? '#fff' : brand.neutralColor
        }
      },
        isUser
          ? React.createElement(Icons.User, { size: 14 })
          : msg.is_error
            ? React.createElement(Icons.AlertCircle, { size: 14 })
            : React.createElement(Icons.CheckCircle, { size: 14 })
      ),
      React.createElement('div', { style: { flex: 1, minWidth: 0 } },
        React.createElement('div', {
          style: {
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            marginBottom: '4px'
          }
        },
          React.createElement('span', {
            style: {
              fontSize: '13px',
              fontWeight: 600,
              color: isUser ? brand.primaryColor : (msg.is_error ? brand.neutralColor : brand.accentColor)
            }
          }, isUser ? 'You' : 'Knowledge Assistant'),
          React.createElement('span', {
            style: {
              fontSize: '11px',
              color: brand.neutralColor,
              fontVariantNumeric: 'tabular-nums'
            }
          }, formatTime(msg.created_at))
        ),
        msg.is_error
          ? React.createElement('div', {
              style: {
                padding: '10px 12px',
                borderRadius: brand.radius,
                backgroundColor: brand.neutralColor + '0D',
                border: '1px solid ' + brand.neutralColor + '30',
                fontSize: '13px',
                lineHeight: 1.5
              }
            }, msg.content)
          : React.createElement('div', {
              style: {
                fontSize: '13px',
                lineHeight: 1.55,
                color: '#1e293b',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word'
              }
            }, msg.content),
        msg.is_fallback && !msg.is_error
          ? React.createElement('div', {
              style: {
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                marginTop: '8px',
                padding: '3px 9px',
                borderRadius: brand.radius,
                fontSize: '11px',
                fontWeight: 600,
                color: brand.neutralColor,
                backgroundColor: brand.neutralColor + '12',
                border: '1px solid ' + brand.neutralColor + '33'
              }
            },
              React.createElement(Icons.AlertCircle, { size: 11 }),
              'Not from your documents'
            )
          : null,
        msg.citations && msg.citations.length > 0
          ? React.createElement('div', {
              style: { marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }
            },
              React.createElement('span', {
                style: {
                  fontSize: '11px',
                  fontWeight: 600,
                  color: brand.neutralColor,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em'
                }
              }, 'Cited from ' + msg.citations.length + ' source' + (msg.citations.length > 1 ? 's' : '')),
              msg.citations.map(function(cit, i) {
                return React.createElement('div', {
                  key: cit.id || i,
                  style: {
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '4px 10px',
                    borderRadius: brand.radius,
                    fontSize: '12px',
                    color: brand.accentColor,
                    backgroundColor: brand.accentColor + '0D',
                    border: '1px solid ' + brand.accentColor + '25',
                    width: 'fit-content'
                  }
                },
                  React.createElement(Icons.FileText, { size: 12 }),
                  React.createElement('span', { style: { fontVariantNumeric: 'tabular-nums' } },
                    cit.filename + ' — ' + cit.page_section
                  )
                );
              })
            )
          : null
      )
    );
  }

  function renderThinkingIndicator() {
    return React.createElement('div', {
      style: { display: 'flex', gap: '10px', marginBottom: '16px' }
    },
      React.createElement('div', {
        style: {
          flexShrink: 0,
          width: '28px',
          height: '28px',
          borderRadius: brand.radius,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: brand.accentColor + '15',
          color: brand.accentColor
        }
      }, React.createElement(Icons.CheckCircle, { size: 14 })),
      React.createElement('div', null,
        React.createElement('div', {
          style: {
            fontSize: '13px',
            fontWeight: 600,
            color: brand.accentColor,
            marginBottom: '4px'
          }
        }, 'Knowledge Assistant'),
        React.createElement('div', {
          style: { display: 'flex', gap: '4px', alignItems: 'center' },
          'aria-label': 'Assistant is searching the Knowledge Base and generating an answer'
        },
          React.createElement('span', {
            className: 'ka-dot',
            style: { animationDelay: '0s' }
          }),
          React.createElement('span', {
            className: 'ka-dot',
            style: { animationDelay: '0.15s' }
          }),
          React.createElement('span', {
            className: 'ka-dot',
            style: { animationDelay: '0.3s' }
          }),
          React.createElement('span', {
            style: {
              fontSize: '12px',
              color: brand.neutralColor,
              marginLeft: '6px'
            }
          }, retrying ? 'Retrying…' : 'Searching Knowledge Base…')
        )
      )
    );
  }

  return React.createElement('div', {
    style: { fontFamily: brand.fontBody }
  },
    React.createElement('style', null,
      '@keyframes msgEnter { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }' +
      '@keyframes kaPulse { 0%, 80%, 100% { opacity: 0.25; } 40% { opacity: 1; } }' +
      '.ka-dot { width: 7px; height: 7px; border-radius: 50%; background-color: ' + brand.accentColor + '; display: inline-block; animation: kaPulse 1.2s infinite ease-in-out; }' +
      '@media (prefers-reduced-motion: reduce) { .ka-dot { animation: none; opacity: 0.6; } @keyframes msgEnter { from { opacity: 1; transform: none; } to { opacity: 1; transform: none; } } }'
    ),

    React.createElement('div', { style: { marginBottom: '12px' } },
      React.createElement('h1', {
        style: {
          fontFamily: brand.fontHeading,
          fontSize: '20px',
          fontWeight: 700,
          color: '#0f172a',
          margin: 0
        }
      }, 'Chat'),
      React.createElement('p', {
        style: {
          fontSize: '13px',
          color: brand.neutralColor,
          margin: '2px 0 0 0'
        }
      }, 'Ask questions and get answers grounded in your Knowledge Base documents with source citations.')
    ),

    React.createElement('div', {
      style: {
        display: 'flex',
        gap: '12px',
        height: 'calc(100vh - 9rem)',
        minHeight: '480px'
      }
    },

      React.createElement('div', {
        style: {
          width: '300px',
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: '#fff',
          border: '1px solid ' + brand.neutralColor + '1A',
          borderRadius: brand.radius,
          overflow: 'hidden'
        }
      },
        React.createElement('div', {
          style: {
            padding: '12px',
            borderBottom: '1px solid ' + brand.neutralColor + '1A'
          }
        },
          React.createElement('div', {
            style: {
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '10px'
            }
          },
            React.createElement('h2', {
              style: {
                fontSize: '13px',
                fontWeight: 600,
                color: '#0f172a',
                margin: 0
              }
            }, 'Conversations'),
            React.createElement(Button, {
              size: 'sm',
              onClick: handleCreateConversation,
              style: {
                fontSize: '12px',
                padding: '4px 10px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px'
              }
            }, React.createElement(Icons.Plus, { size: 13 }), 'New')
          ),
          React.createElement('div', { style: { position: 'relative' } },
            React.createElement(Icons.Search, {
              size: 14,
              style: {
                position: 'absolute',
                left: '8px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: brand.neutralColor,
                pointerEvents: 'none'
              }
            }),
            React.createElement(Input, {
              id: 'conversation-search',
              placeholder: 'Search by title…',
              value: search,
              onChange: function(e) { setSearch(e.target.value); },
              style: {
                paddingLeft: '28px',
                fontSize: '13px',
                height: '32px'
              },
              'aria-label': 'Search conversations by title'
            })
          )
        ),

        React.createElement('div', {
          style: { flex: 1, overflowY: 'auto' },
          role: 'list',
          'aria-label': 'Conversation list'
        },
          filteredConversations.length === 0
            ? React.createElement('div', {
                style: {
                  padding: '24px 16px',
                  textAlign: 'center'
                }
              },
                React.createElement('div', {
                  style: {
                    fontSize: '13px',
                    color: brand.neutralColor,
                    marginBottom: '4px'
                  }
                }, search.trim()
                  ? 'No conversations match "' + search + '"'
                  : 'No conversations yet'
                ),
                React.createElement('div', {
                  style: {
                    fontSize: '12px',
                    color: brand.neutralColor + '99'
                  }
                }, search.trim()
                  ? 'Try a different search term.'
                  : 'Click "New" to start your first conversation.'
                )
              )
            : filteredConversations.map(function(conv) {
                var isSelected = conv.id === selectedId;
                var isConfirming = deleteConfirmId === conv.id;
                var preview = getLastMessagePreview(conv);
                return React.createElement('div', {
                  key: conv.id,
                  role: 'listitem',
                  style: {
                    display: 'flex',
                    alignItems: 'stretch',
                    borderBottom: '1px solid ' + brand.neutralColor + '0F',
                    transition: 'background-color 0.15s'
                  }
                },
                  React.createElement('button', {
                    onClick: function() { handleSelectConversation(conv.id); },
                    'aria-label': 'Open conversation: ' + conv.title + ', ' + conv.messages.length + ' messages, last updated ' + formatDate(conv.updated_at),
                    'aria-current': isSelected ? 'true' : 'false',
                    style: {
                      flex: 1,
                      textAlign: 'left',
                      padding: '10px 12px',
                      backgroundColor: isSelected ? brand.primaryColor + '0D' : 'transparent',
                      borderLeft: isSelected ? '3px solid ' + brand.primaryColor : '3px solid transparent',
                      cursor: 'pointer',
                      transition: 'background-color 0.15s, border-color 0.15s',
                      minWidth: 0,
                      background: 'none',
                      borderTop: 'none',
                      borderBottom: 'none',
                      borderRight: 'none'
                    },
                    onMouseEnter: function(e) {
                      if (!isSelected) e.currentTarget.style.backgroundColor = brand.neutralColor + '08';
                    },
                    onMouseLeave: function(e) {
                      if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
                    }
                  },
                    React.createElement('div', {
                      style: {
                        fontSize: '13px',
                        fontWeight: 600,
                        color: '#0f172a',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        marginBottom: '2px'
                      }
                    }, conv.title),
                    React.createElement('div', {
                      style: {
                        fontSize: '11px',
                        color: brand.neutralColor,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        marginBottom: '2px'
                      }
                    }, preview),
                    React.createElement('div', {
                      style: {
                        fontSize: '11px',
                        color: brand.neutralColor + 'CC',
                        fontVariantNumeric: 'tabular-nums'
                      }
                    }, formatDate(conv.updated_at) + ' · ' + conv.messages.length + ' msg' + (conv.messages.length === 1 ? '' : 's'))
                  ),
                  isConfirming
                    ? React.createElement('div', {
                        style: {
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'center',
                          padding: '6px 8px',
                          gap: '4px'
                        }
                      },
                        React.createElement('button', {
                          onClick: function() { handleDeleteConversation(conv.id); },
                          'aria-label': 'Confirm delete conversation: ' + conv.title,
                          style: {
                            width: '24px',
                            height: '20px',
                            border: '1px solid ' + brand.accentColor,
                            borderRadius: '4px',
                            backgroundColor: brand.accentColor,
                            color: '#fff',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            padding: 0
                          }
                        }, React.createElement(Icons.Check, { size: 12 })),
                        React.createElement('button', {
                          onClick: function() { setDeleteConfirmId(null); },
                          'aria-label': 'Cancel delete',
                          style: {
                            width: '24px',
                            height: '20px',
                            border: '1px solid ' + brand.neutralColor + '40',
                            borderRadius: '4px',
                            backgroundColor: '#fff',
                            color: brand.neutralColor,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            padding: 0
                          }
                        }, React.createElement(Icons.X, { size: 12 }))
                      )
                    : React.createElement('button', {
                        onClick: function(e) {
                          e.stopPropagation();
                          setDeleteConfirmId(conv.id);
                        },
                        'aria-label': 'Delete conversation: ' + conv.title,
                        style: {
                          padding: '10px 8px',
                          border: 'none',
                          backgroundColor: 'transparent',
                          color: brand.neutralColor,
                          cursor: 'pointer',
                          flexShrink: 0,
                          opacity: 0.6,
                          transition: 'opacity 0.15s, color 0.15s'
                        },
                        onMouseEnter: function(e) {
                          e.currentTarget.style.opacity = '1';
                          e.currentTarget.style.color = '#dc2626';
                        },
                        onMouseLeave: function(e) {
                          e.currentTarget.style.opacity = '0.6';
                          e.currentTarget.style.color = brand.neutralColor;
                        }
                      }, React.createElement(Icons.Trash, { size: 14 }))
                );
              })
        )
      ),

      React.createElement('div', {
        style: {
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: '#fff',
          border: '1px solid ' + brand.neutralColor + '1A',
          borderRadius: brand.radius,
          overflow: 'hidden',
          minWidth: 0
        }
      },
        selectedConversation
          ? React.createElement(React.Fragment, null,

              React.createElement('div', {
                style: {
                  padding: '12px 16px',
                  borderBottom: '1px solid ' + brand.neutralColor + '1A',
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  gap: '12px'
                }
              },
                React.createElement('div', { style: { minWidth: 0 } },
                  React.createElement('h2', {
                    style: {
                      fontSize: '15px',
                      fontWeight: 600,
                      color: '#0f172a',
                      margin: 0,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }
                  }, selectedConversation.title),
                  React.createElement('div', {
                    style: {
                      fontSize: '11px',
                      color: brand.neutralColor,
                      marginTop: '2px',
                      fontVariantNumeric: 'tabular-nums'
                    }
                  }, 'Started ' + formatDateFull(selectedConversation.created_at) + ' · ' + selectedConversation.messages.length + ' message' + (selectedConversation.messages.length === 1 ? '' : 's'))
                ),
                React.createElement('button', {
                  onClick: function() {
                    setDeleteConfirmId(selectedConversation.id);
                  },
                  'aria-label': 'Delete this conversation',
                  style: {
                    padding: '4px 8px',
                    border: '1px solid ' + brand.neutralColor + '30',
                    borderRadius: brand.radius,
                    backgroundColor: 'transparent',
                    color: brand.neutralColor,
                    cursor: 'pointer',
                    fontSize: '12px',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    flexShrink: 0,
                    transition: 'color 0.15s, border-color 0.15s'
                  },
                  onMouseEnter: function(e) {
                    e.currentTarget.style.color = '#dc2626';
                    e.currentTarget.style.borderColor = '#dc2626';
                  },
                  onMouseLeave: function(e) {
                    e.currentTarget.style.color = brand.neutralColor;
                    e.currentTarget.style.borderColor = brand.neutralColor + '30';
                  }
                }, React.createElement(Icons.Trash, { size: 13 }), 'Delete')
              ),

              React.createElement('div', {
                style: {
                  flex: 1,
                  overflowY: 'auto',
                  padding: '16px'
                },
                'aria-live': 'polite',
                'aria-label': 'Chat messages'
              },
                messages.length === 0 && !isSending
                  ? React.createElement('div', {
                      style: {
                        height: '100%',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        textAlign: 'center',
                        padding: '24px'
                      }
                    },
                      React.createElement('div', {
                        style: {
                          width: '48px',
                          height: '48px',
                          borderRadius: '50%',
                          backgroundColor: brand.primaryColor + '0D',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          marginBottom: '12px'
                        }
                      }, React.createElement(Icons.Search, { size: 22, style: { color: brand.primaryColor } })),
                      React.createElement('div', {
                        style: {
                          fontSize: '15px',
                          fontWeight: 600,
                          color: '#0f172a',
                          marginBottom: '4px'
                        }
                      }, 'Ask your first question'),
                      React.createElement('div', {
                        style: {
                          fontSize: '13px',
                          color: brand.neutralColor,
                          maxWidth: '340px',
                          lineHeight: 1.5
                        }
                      }, 'Answers are grounded in your Knowledge Base documents with citations to source pages. If no relevant document is found, you will get a general-knowledge answer with a clear badge.')
                    )
                  : React.createElement(React.Fragment, null,
                      messages.map(renderMessage),
                      isSending ? renderThinkingIndicator() : null,
                      hasErrorInLastMessage && !isSending
                        ? React.createElement('div', {
                            style: {
                              display: 'flex',
                              gap: '8px',
                              marginTop: '4px',
                              marginLeft: '38px'
                            }
                          },
                            React.createElement(Button, {
                              size: 'sm',
                              onClick: handleRetryLastQuestion,
                              style: {
                                fontSize: '12px',
                                padding: '5px 12px',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px'
                              }
                            }, React.createElement(Icons.ArrowLeft, { size: 12 }), 'Retry question')
                          )
                        : null,
                      React.createElement('div', { ref: messagesEndRef })
                    )
              ),

              React.createElement('div', {
                style: {
                  padding: '12px 16px',
                  borderTop: '1px solid ' + brand.neutralColor + '1A',
                  backgroundColor: brand.backgroundColor
                }
              },
                React.createElement('form', {
                  onSubmit: handleSendMessage,
                  style: { display: 'flex', gap: '8px', alignItems: 'flex-end' }
                },
                  React.createElement('div', { style: { flex: 1 } },
                    React.createElement('label', {
                      htmlFor: 'chat-input',
                      style: {
                        position: 'absolute',
                        width: '1px',
                        height: '1px',
                        overflow: 'hidden',
                        clip: 'rect(0 0 0 0)'
                      }
                    }, 'Ask a question about your Knowledge Base documents'),
                    React.createElement(Textarea, {
                      id: 'chat-input',
                      ref: inputRef,
                      value: input,
                      onChange: function(e) { setInput(e.target.value); },
                      onKeyDown: handleKeyDown,
                      placeholder: 'Ask a question about your Knowledge Base documents…',
                      rows: 2,
                      disabled: isSending,
                      style: {
                        fontSize: '13px',
                        resize: 'none',
                        maxHeight: '120px',
                        backgroundColor: '#fff'
                      }
                    })
                  ),
                  React.createElement(Button, {
                    type: 'submit',
                    disabled: !input.trim() || isSending,
                    style: {
                      height: '40px',
                      padding: '0 16px',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '5px',
                      fontSize: '13px',
                      fontWeight: 500,
                      flexShrink: 0
                    }
                  }, isSending ? 'Sending…' : 'Send')
                ),
                React.createElement('div', {
                  style: {
                    fontSize: '11px',
                    color: brand.neutralColor + '99',
                    marginTop: '6px'
                  }
                }, 'Press Enter to send, Shift+Enter for a new line')
              )
            )
          : React.createElement('div', {
              style: {
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                textAlign: 'center',
                padding: '24px'
              }
            },
              React.createElement('div', {
                style: {
                  width: '48px',
                  height: '48px',
                  borderRadius: '50%',
                  backgroundColor: brand.neutralColor + '15',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '12px'
                }
              }, React.createElement(Icons.Plus, { size: 22, style: { color: brand.neutralColor } })),
              React.createElement('div', {
                style: {
                  fontSize: '15px',
                  fontWeight: 600,
                  color: '#0f172a',
                  marginBottom: '4px'
                }
              }, 'No conversation selected'),
              React.createElement('div', {
                style: {
                  fontSize: '13px',
                  color: brand.neutralColor,
                  maxWidth: '320px',
                  lineHeight: 1.5,
                  marginBottom: '16px'
                }
              }, 'Select a conversation from the list or create a new one to start asking questions.'),
              React.createElement(Button, {
                onClick: handleCreateConversation,
                style: {
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px',
                  fontSize: '13px'
                }
              }, React.createElement(Icons.Plus, { size: 14 }), 'New Conversation')
            )
      )
    )
  );
}
