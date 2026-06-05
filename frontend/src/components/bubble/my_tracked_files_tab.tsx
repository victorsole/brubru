/**
 * My Tracked Files Tab Component
 *
 * Personal watchlist of tracked legislative files.
 * Shows tracked files with status, recent changes, and quick actions.
 * Part of My EU Bubble - Legislative Tracking Enhancement
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiFileDocumentOutline,
  mdiAlertCircleOutline,
  mdiClockOutline,
  mdiAccountGroupOutline,
  mdiPlus,
  mdiRefresh,
  mdiTrashCanOutline,
  mdiOpenInNew,
  mdiHistory,
  mdiMagnify,
  mdiClose,
  mdiStarOutline,
  mdiLoading,
  mdiPencilOutline,
  mdiAccountTieOutline,
  mdiFilterVariant,
  mdiTextBoxCheckOutline,
  mdiFileDocumentMultipleOutline,
  mdiBookOpenPageVariantOutline,
  mdiPlaylistPlus,
  mdiInformationOutline,
  mdiChevronDown,
  mdiChevronUp,
} from '@mdi/js';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { getDeepDiveForProcedure, getDeepDiveUrl } from '../../utils/deep_dive_map';
import axios from 'axios';
import { useLegislativeTrains } from '../../hooks/use_legislative_trains';
import type { TrackedFile } from '../../hooks/use_legislative_trains';
import { useCommitteeWork, PROCEDURE_TYPE_INFO, STATUS_INFO } from '../../hooks/use_committee_work';
import type { CommitteeWorkItem } from '../../hooks/use_committee_work';
import { useTextsAdopted } from '../../hooks/use_texts_adopted';
import { TextAdoptedCard } from './text_adopted_card';
import { useCommissionDocuments } from '../../hooks/use_commission_documents';
import { getEultUrl, getRegDelUrl } from '../../utils/eu_links';
import { CommissionDocumentCard } from './commission_document_card';
import { LegislativeFileDetail } from './legislative_file_detail';
import { HotThisWeekWidget } from './hot_this_week_widget';
import { useAuth } from '../../hooks/use_auth';
import { plainLanguageTypeKey } from '../../utils/procedure_type';
import './my_tracked_files_tab.css';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Order + labels for grouping the tracked list by plain-language kind of action
// (doc-06 §7). typeKey null = the "Other files" catch-all.
const TRACKED_GROUP_ORDER: Array<{ typeKey: string | null; titleKey: string; tipKey?: string }> = [
  { typeKey: 'typeNewLaw', titleKey: 'groupNewLaw', tipKey: 'tipGroupNewLaw' },
  { typeKey: 'typeParliamentPosition', titleKey: 'groupParliamentPosition', tipKey: 'tipGroupParliamentPosition' },
  { typeKey: 'typeAgreement', titleKey: 'groupAgreement', tipKey: 'tipGroupAgreement' },
  { typeKey: 'typeScrutiny', titleKey: 'groupScrutiny', tipKey: 'tipGroupScrutiny' },
  { typeKey: 'typeBudget', titleKey: 'groupBudget', tipKey: 'tipGroupBudget' },
  { typeKey: null, titleKey: 'groupOther' },
];

// Commission Directorate-General code -> display name, for the Commission Docs
// tab (PI anchor = DG, since those documents carry no EP committee). Covers the
// DGs present in the data; unknown codes fall back to the bare code.
const DG_NAMES: Record<string, string> = {
  AGRI: 'Agriculture and Rural Development',
  MARE: 'Maritime Affairs and Fisheries',
  SANTE: 'Health and Food Safety',
  CLIMA: 'Climate Action',
  ENV: 'Environment',
  ENER: 'Energy',
  MOVE: 'Mobility and Transport',
  GROW: 'Internal Market, Industry, Entrepreneurship and SMEs',
  COMP: 'Competition',
  TRADE: 'Trade',
  ECFIN: 'Economic and Financial Affairs',
  TAXUD: 'Taxation and Customs Union',
  JUST: 'Justice and Consumers',
  HOME: 'Migration and Home Affairs',
  EMPL: 'Employment, Social Affairs and Inclusion',
  CNECT: 'Communications Networks, Content and Technology',
  REGIO: 'Regional and Urban Policy',
  RTD: 'Research and Innovation',
  EAC: 'Education, Youth, Sport and Culture',
  DEFIS: 'Defence Industry and Space',
  ECHO: 'Humanitarian Aid and Civil Protection',
  INTPA: 'International Partnerships',
  NEAR: 'Neighbourhood and Enlargement',
  ENEST: 'Enlargement and Eastern Neighbourhood',
  MENA: 'Middle East and North Africa',
  FISMA: 'Financial Stability, Financial Services and Capital Markets Union',
  ESTAT: 'Eurostat',
  EEAS: 'European External Action Service',
  FPI: 'Foreign Policy Instruments',
  SG: 'Secretariat-General',
  REFOR: 'Structural Reform Support',
};

interface SearchableFile {
  id: string;
  title: string;
  current_status: string;
  oeil_procedure_ref?: string;
}

export const MyTrackedFilesTab = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const {
    trackedFiles,
    recentChanges,
    isLoadingTrackedFiles,
    fetchTrackedFiles,
    fetchRecentChanges,
    untrackFile,
    fetchFileDetail,
    selectedFile,
    trackFile,
    isTracking,
  } = useLegislativeTrains();

  // Committee Work hook
  const {
    items: committeeWorkItems,
    committees,
    isLoadingItems: isLoadingCommitteeWork,
    fetchItems: fetchCommitteeWorkItems,
    fetchCommittees,
    fetchTrackedItems: fetchCommitteeTrackedItems,
    trackedItems: committeeTrackedItems,
    trackItem: trackCommitteeItem,
    untrackItem: untrackCommitteeItem,
  } = useCommitteeWork();

  // Texts Adopted hook
  const {
    items: textsAdoptedItems,
    isLoadingItems: isLoadingTextsAdopted,
    fetchItems: fetchTextsAdoptedItems,
    fetchTrackedItems: fetchTextsTrackedItems,
    trackedItems: textsTrackedItems,
    trackItem: trackTextItem,
    untrackItem: untrackTextItem,
  } = useTextsAdopted();

  // Commission Documents hook
  const {
    items: commissionDocItems,
    isLoadingItems: isLoadingCommissionDocs,
    fetchItems: fetchCommissionDocItems,
    fetchTrackedItems: fetchCommissionTrackedItems,
    trackedItems: commissionTrackedItems,
    trackItem: trackCommissionItem,
    untrackItem: untrackCommissionItem,
  } = useCommissionDocuments();

  const hasLoadedRef = useRef(false);
  const [activeTab, setActiveTab] = useState<'legislative' | 'committee' | 'texts_adopted' | 'commission_docs'>('legislative');
  const [amendmentCounts, setAmendmentCounts] = useState<Record<string, number>>({});
  const [showAddModal, setShowAddModal] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [listQuery, setListQuery] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [availableFiles, setAvailableFiles] = useState<SearchableFile[]>([]);
  const [isLoadingFiles, setIsLoadingFiles] = useState(false);
  const [trackingFileId, setTrackingFileId] = useState<string | null>(null);
  const [visibleCount, setVisibleCount] = useState(25);
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest' | 'alphabetical'>('newest');
  const PAGE_STEP = 25;
  const [showAdvancedRef, setShowAdvancedRef] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  // In-committee tab state. The view is linked to the user's Policy Interests:
  // committees resolved from PI (myCommittees) are pre-selected in "mine" mode;
  // "all" mode drops the committee filter so the user can browse everything.
  const [myCommittees, setMyCommittees] = useState<string[]>([]);
  const [committeeMode, setCommitteeMode] = useState<'mine' | 'all'>('all');
  const [committeeChips, setCommitteeChips] = useState<string[]>([]);
  const [committeeKind, setCommitteeKind] = useState<string>('all');
  const [showTechnical, setShowTechnical] = useState(false);
  const [addCommitteeCode, setAddCommitteeCode] = useState('');

  // Adopted-texts tab state (mirrors the In-committee PI alignment).
  const [textsMode, setTextsMode] = useState<'mine' | 'all'>('all');
  const [textsChips, setTextsChips] = useState<string[]>([]);
  const [textsKind, setTextsKind] = useState<string>('all');
  const [addTextsCommitteeCode, setAddTextsCommitteeCode] = useState('');

  // Commission-docs tab state. Anchor is the Directorate-General (dg_responsible),
  // not an EP committee, since Commission documents carry no committee.
  const [myDgs, setMyDgs] = useState<string[]>([]);
  const [docsMode, setDocsMode] = useState<'mine' | 'all'>('all');
  const [docsChips, setDocsChips] = useState<string[]>([]);
  const [docsKind, setDocsKind] = useState<string>('all');
  const [addDocsDg, setAddDocsDg] = useState('');

  // OEIL direct tracking state
  const [oeilProcedureRef, setOeilProcedureRef] = useState('');
  const [isTrackingOeil, setIsTrackingOeil] = useState(false);
  const [oeilTrackError, setOeilTrackError] = useState<string | null>(null);
  const [oeilTrackSuccess, setOeilTrackSuccess] = useState<string | null>(null);

  // Fetch amendment counts for tracked files
  const fetchAmendmentCounts = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/legislative-train/tracked/amendment-counts`);
      setAmendmentCounts(response.data.amendment_counts || {});
    } catch (error) {
      console.error('Failed to fetch amendment counts:', error);
    }
  };

  useEffect(() => {
    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;

    const loadData = async () => {
      await fetchTrackedFiles();
      await fetchRecentChanges(168); // Last 7 days
      await fetchAmendmentCounts();
      // Load committee work data. Pull the whole table (only a few hundred rows)
      // so the PI split, kind filter and search all run client-side.
      useCommitteeWork.setState({ limit: 500 });
      await fetchCommittees();
      await fetchCommitteeWorkItems();
      await fetchCommitteeTrackedItems();
      // Resolve the user's Policy Interests -> committee codes and pre-select them.
      try {
        const token = useAuth.getState().token;
        const mc = await axios.get<{ committees: string[] }>(
          `${API_BASE}/api/committee-work/my-committees`,
          token ? { headers: { Authorization: `Bearer ${token}` } } : undefined,
        );
        const codes = mc.data?.committees || [];
        setMyCommittees(codes);
        if (codes.length > 0) {
          setCommitteeChips(codes);
          setCommitteeMode('mine');
          setTextsChips(codes);
          setTextsMode('mine');
        }
      } catch {
        // Anonymous or no mappable interests: stay in "all committees" mode.
      }
      // Load texts adopted data (whole set; filter client-side like In-committee)
      useTextsAdopted.setState({ limit: 500 });
      await fetchTextsAdoptedItems();
      await fetchTextsTrackedItems();
      // Load commission documents data (whole set; filter client-side by DG)
      useCommissionDocuments.setState({ limit: 500 });
      await fetchCommissionDocItems();
      await fetchCommissionTrackedItems();
      // Resolve the user's Policy Interests -> Commission DGs and pre-select them.
      try {
        const token = useAuth.getState().token;
        const md = await axios.get<{ dgs: string[] }>(
          `${API_BASE}/api/commission-documents/my-dgs`,
          token ? { headers: { Authorization: `Bearer ${token}` } } : undefined,
        );
        const dgs = md.data?.dgs || [];
        setMyDgs(dgs);
        if (dgs.length > 0) {
          setDocsChips(dgs);
          setDocsMode('mine');
        }
      } catch {
        // Anonymous or no mappable interests: stay in "all" mode.
      }
    };

    loadData();
  }, []);

  // Deep-link: ?file=<file_id> opens that tracked file's detail modal directly.
  // Used by the EFPIA / OJ / Votes "tracked file" links so a click lands on the
  // law's own card inside My Files, not the Legislative Train list or the Chat.
  //
  // Open ONCE per file id (the ref guard stops the effect re-firing on unrelated
  // searchParams changes), and once the modal is closed, strip the `file` param
  // from the URL — otherwise the stale param lingers, the browser autocompletes
  // the long URL, and the modal reopens automatically on every visit.
  const openedFileRef = useRef<string | null>(null);

  useEffect(() => {
    const fileParam = searchParams.get('file');
    if (fileParam && openedFileRef.current !== fileParam) {
      openedFileRef.current = fileParam;
      fetchFileDetail(fileParam);
    }
  }, [searchParams]);

  useEffect(() => {
    // Modal was closed (selectedFile cleared) but the URL still carries ?file=
    // from a deep-link we already consumed -> clean it so it can't auto-reopen.
    if (!selectedFile && openedFileRef.current && searchParams.get('file')) {
      const next = new URLSearchParams(searchParams);
      next.delete('file');
      setSearchParams(next, { replace: true });
      openedFileRef.current = null;
    }
  }, [selectedFile]);

  const handleRefresh = async () => {
    if (activeTab === 'legislative') {
      await fetchTrackedFiles();
      await fetchRecentChanges(168);
    } else if (activeTab === 'committee') {
      await fetchCommitteeWorkItems();
    } else if (activeTab === 'texts_adopted') {
      await fetchTextsAdoptedItems();
    } else {
      await fetchCommissionDocItems();
    }
  };

  // Populate tracked files from the user's Policy Interests (Section 1 -> 2).
  const handleSyncFromInterests = async () => {
    setIsSyncing(true);
    try {
      const token = useAuth.getState().token;
      const res = await axios.post<{ seeded: number; committees: string[] }>(
        `${API_BASE}/api/legislative-train/sync-from-interests`,
        {},
        token ? { headers: { Authorization: `Bearer ${token}` } } : undefined,
      );
      await fetchTrackedFiles();
      await fetchRecentChanges(168);
      const n = res.data?.seeded ?? 0;
      alert(n > 0 ? t('myFilesTab.syncAdded', { count: n }) : t('myFilesTab.syncNone'));
    } catch {
      alert(t('myFilesTab.syncFailed'));
    } finally {
      setIsSyncing(false);
    }
  };

  const handleUntrack = async (file: TrackedFile) => {
    if (window.confirm('Are you sure you want to stop tracking this file?')) {
      try {
        // Use procedure ref if available, otherwise use carriage_id (UUID)
        const useCarriageId = !file.oeil_procedure_ref;
        const identifier = file.oeil_procedure_ref || file.carriage_id;
        await untrackFile(identifier, useCarriageId);
      } catch {
        alert('Failed to untrack file. Please try again.');
      }
    }
  };

  // Load available files when modal opens (or when searching server-side)
  const loadAvailableFiles = async (searchTerm?: string) => {
    setIsLoadingFiles(true);
    try {
      const params = new URLSearchParams({ limit: '500' });
      if (searchTerm && searchTerm.trim()) {
        params.set('search', searchTerm.trim());
      }
      const response = await axios.get<{ carriages: SearchableFile[]; total: number }>(
        `${API_BASE}/api/legislative-train/carriages?${params.toString()}`
      );
      setAvailableFiles(response.data.carriages || []);
    } catch (error) {
      console.error('Failed to load files:', error);
    } finally {
      setIsLoadingFiles(false);
    }
  };

  // Debounced server-side search
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    if (value.trim().length >= 3) {
      searchTimeoutRef.current = setTimeout(() => loadAvailableFiles(value), 400);
    } else if (value.trim().length === 0) {
      // Reset to full list when search is cleared
      searchTimeoutRef.current = setTimeout(() => loadAvailableFiles(), 200);
    }
  };

  // Open modal and load files
  const handleOpenAddModal = () => {
    setShowAddModal(true);
    setSearchQuery('');
    if (availableFiles.length === 0) {
      loadAvailableFiles();
    }
  };

  // Track a file from the modal - always use UUID for reliability
  const handleTrackFromModal = async (file: SearchableFile) => {
    setTrackingFileId(file.id);
    try {
      // Always use UUID (carriage ID) for tracking - more reliable than procedure ref
      await trackFile(file.id, true);
    } catch (error: unknown) {
      // Show specific error message
      const axiosError = error as { response?: { status?: number; data?: { detail?: string } } };
      if (axiosError.response?.status === 401) {
        alert('Please log in to track files.');
      } else {
        alert(axiosError.response?.data?.detail || 'Failed to track file. Please try again.');
      }
    } finally {
      setTrackingFileId(null);
    }
  };

  // Track an OEIL procedure directly (not from Legislative Train)
  const handleTrackOeilProcedure = async () => {
    if (!oeilProcedureRef.trim()) {
      setOeilTrackError('Please enter a procedure reference');
      return;
    }

    // Validate format: YYYY/NNNN(XXX)
    const procedurePattern = /^\d{4}\/\d{4}\([A-Z]{3}\)$/;
    if (!procedurePattern.test(oeilProcedureRef.trim())) {
      setOeilTrackError('Invalid format. Use: YYYY/NNNN(XXX) e.g., 2024/0176(COD)');
      return;
    }

    setIsTrackingOeil(true);
    setOeilTrackError(null);
    setOeilTrackSuccess(null);

    try {
      const response = await axios.post(
        `${API_BASE}/api/legislative-train/track/oeil?procedure_ref=${encodeURIComponent(oeilProcedureRef.trim())}`
      );

      setOeilTrackSuccess(`Now tracking: ${response.data.title || oeilProcedureRef}`);
      setOeilProcedureRef('');

      // Refresh tracked files
      await fetchTrackedFiles();
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string }; status?: number } };
      if (axiosError.response?.status === 404) {
        setOeilTrackError('Procedure not found in OEIL. Check the reference.');
      } else if (axiosError.response?.status === 401) {
        setOeilTrackError('Please log in to track procedures.');
      } else {
        setOeilTrackError(axiosError.response?.data?.detail || 'Failed to track procedure');
      }
    } finally {
      setIsTrackingOeil(false);
    }
  };

  // Compute available statuses from data
  const availableStatuses = Array.from(
    new Set(availableFiles.map(f => f.current_status))
  ).sort();

  // Parse procedure reference to extract year and number for sorting
  // Format: YYYY/NNNN(TYPE) e.g., 2018/0332(COD)
  const parseProcedureRef = (ref: string | undefined): { year: number; number: number } => {
    if (!ref) return { year: 0, number: 0 };
    const match = ref.match(/^(\d{4})\/(\d{4})\(/);
    if (match) {
      return {
        year: parseInt(match[1], 10),
        number: parseInt(match[2], 10)
      };
    }
    return { year: 0, number: 0 };
  };

  // Filter files based on status (search is now handled server-side)
  const filteredFiles = availableFiles.filter((file) => {
    // Status filter
    if (statusFilter !== 'all' && file.current_status !== statusFilter) {
      return false;
    }
    return true;
  });

  // Sort filtered files based on sortOrder
  const sortedFiles = [...filteredFiles].sort((a, b) => {
    if (sortOrder === 'alphabetical') {
      return a.title.localeCompare(b.title);
    }

    const refA = parseProcedureRef(a.oeil_procedure_ref);
    const refB = parseProcedureRef(b.oeil_procedure_ref);

    // Primary sort by year, secondary by number
    if (refA.year !== refB.year) {
      return sortOrder === 'newest' ? refB.year - refA.year : refA.year - refB.year;
    }
    // Same year, sort by proposal number
    return sortOrder === 'newest' ? refB.number - refA.number : refA.number - refB.number;
  });

  // Browse list: drop placeholder / non-procedure titles so the picker is not full of junk.
  const browseFiles = sortedFiles.filter((f) => {
    const title = (f.title || '').trim();
    if (title.length < 8) return false;
    if (/^Procedure File:\s*\d{4}\/\d+\([A-Z]+\)/i.test(title)) return false;
    return true;
  });
  const shownFiles = browseFiles.slice(0, visibleCount);

  // Reset the visible count when the query, status filter or sort order changes.
  useEffect(() => {
    setVisibleCount(PAGE_STEP);
  }, [searchQuery, statusFilter, sortOrder]);

  // Check if a file is already tracked
  const isAlreadyTracked = (file: SearchableFile) => {
    return trackedFiles.some(
      (tf) => tf.file_id === file.id || tf.oeil_procedure_ref === file.oeil_procedure_ref
    );
  };

  const getStatusColor = (status: string) => {
    const statusMap: Record<string, string> = {
      announced: '#9e9e9e',
      legislative_initiative: '#2196f3',
      tabled: '#ff9800',
      close_to_adoption: '#4caf50',
      completed: '#4caf50',
      adopted: '#4caf50',
      blocked: '#f44336',
      withdrawn: '#757575',
    };
    return statusMap[status] || '#9e9e9e';
  };

  const getChangeIcon = (changeType: string) => {
    switch (changeType) {
      case 'status_change':
        return mdiHistory;
      case 'new_document':
        return mdiFileDocumentOutline;
      case 'blocking':
        return mdiAlertCircleOutline;
      default:
        return mdiClockOutline;
    }
  };

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) {
      return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    }
    if (diffHours > 0) {
      return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    }
    return 'Just now';
  };

  // Inline search filter for the tracked lists (separate from the Add-modal search).
  const q = listQuery.trim().toLowerCase();
  const matchQ = (...vals: Array<string | null | undefined>) =>
    !q || vals.some((v) => (v || '').toLowerCase().includes(q));
  const visibleTracked = trackedFiles.filter((f) =>
    matchQ(f.title, f.oeil_procedure_ref, f.lead_committee),
  );

  // --- In-committee tab: PI split + kind/search filters + grouping ----------
  // Plain-language "kind" families used by the Kind dropdown (doc-06 Axis A).
  const COMMITTEE_KINDS = [
    'typeNewLaw', 'typeParliamentPosition', 'typeAgreement', 'typeBudget', 'typeScrutiny',
  ] as const;
  // Scraper junk titles (no real title was captured), e.g.
  //   "Delegated acts (DEA) ECON" / "Resolution on topical subjects (RSP) ENVI"
  //   "***I Ordinary legislative procedure (COD) first reading AGRI ENVI"
  //   "Procedure File: 2025/2880(RSP)"
  const isStubTitle = (title?: string) => {
    const tl = (title || '').trim();
    if (!tl) return true;
    return /\([A-Z]+\)\s+[A-Z]{3,4}\s*$/.test(tl)          // "(DEA) ENVI"
      || /^\*+/.test(tl)                                    // "***I ..."
      || /ordinary legislative procedure|first reading|second reading/i.test(tl)
      || /^procedure file:/i.test(tl);
  };
  // Technical / housekeeping = scrutiny families, no plain-language family, or a stub title.
  const isTechnicalItem = (item: CommitteeWorkItem) => {
    const key = plainLanguageTypeKey(item.procedure_ref);
    return key === null || key === 'typeScrutiny' || isStubTitle(item.title);
  };

  const committeeNameOf = (code: string) =>
    committees.find((c) => c.code === code)?.name || code;

  const committeeGroups = useMemo(() => {
    const activeCodes = new Set(committeeChips);
    const filtered = committeeWorkItems.filter((item) => {
      if (committeeMode === 'mine' && myCommittees.length > 0) {
        if (!myCommittees.includes(item.committee_code)) return false;
      }
      if (activeCodes.size > 0 && !activeCodes.has(item.committee_code)) return false;
      if (committeeKind !== 'all'
        && plainLanguageTypeKey(item.procedure_ref) !== committeeKind) return false;
      if (!showTechnical && isTechnicalItem(item)) return false;
      if (!matchQ(item.title, item.procedure_ref, item.rapporteur_name)) return false;
      return true;
    });
    // Group by committee, my-interest committees first, then by item relevance.
    const byCode = new Map<string, CommitteeWorkItem[]>();
    for (const item of filtered) {
      const list = byCode.get(item.committee_code) || [];
      list.push(item);
      byCode.set(item.committee_code, list);
    }
    return Array.from(byCode.entries())
      .map(([code, items]) => ({
        code,
        name: committeeNameOf(code),
        isMine: myCommittees.includes(code),
        // Newest first (first_seen is the reliable date), then by relevance.
        items: items.sort((a, b) =>
          (new Date(b.first_seen || 0).getTime() - new Date(a.first_seen || 0).getTime())
          || (b.relevance_score - a.relevance_score)
          || a.title.localeCompare(b.title)),
      }))
      .sort((a, b) => (Number(b.isMine) - Number(a.isMine)) || a.code.localeCompare(b.code));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [committeeWorkItems, committeeMode, committeeChips, committeeKind, showTechnical, myCommittees, q, committees]);

  const committeeVisibleCount = committeeGroups.reduce((n, g) => n + g.items.length, 0);
  const toggleChip = (code: string) =>
    setCommitteeChips((prev) => prev.includes(code)
      ? prev.filter((c) => c !== code) : [...prev, code]);

  // Which committee items the user already tracks (separate store from carriages).
  const committeeTrackedIds = useMemo(
    () => new Set((committeeTrackedItems || []).map((t) => t.work_item.id)),
    [committeeTrackedItems],
  );
  const handleCommitteeTrack = async (item: CommitteeWorkItem) => {
    try {
      await trackCommitteeItem(item.id);
    } catch {
      alert(t('myFilesTab.trackFailed'));
    }
  };
  const handleCommitteeUntrack = async (item: CommitteeWorkItem) => {
    try {
      await untrackCommitteeItem(item.id);
    } catch {
      alert(t('myFilesTab.trackFailed'));
    }
  };
  // View details: open the in-app file modal when the item is linked to a
  // carriage; otherwise fall back to the OEIL procedure page.
  const handleCommitteeViewDetail = (item: CommitteeWorkItem) => {
    if (item.legislative_carriage_id) {
      fetchFileDetail(item.legislative_carriage_id);
    } else {
      const url = item.oeil_url || (item.procedure_ref
        ? `https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${encodeURIComponent(item.procedure_ref)}`
        : null);
      if (url) window.open(url, '_blank', 'noopener,noreferrer');
    }
  };

  // --- Adopted texts: PI split + kind/search filters + grouping -------------
  const TEXT_KINDS = ['resolution', 'legislative_resolution', 'decision', 'recommendation', 'other'] as const;
  const textsGroups = useMemo(() => {
    const activeCodes = new Set(textsChips);
    const filtered = textsAdoptedItems.filter((item) => {
      const codes = item.committees || [];
      if (textsMode === 'mine' && myCommittees.length > 0
        && !codes.some((c) => myCommittees.includes(c))) return false;
      if (activeCodes.size > 0 && !codes.some((c) => activeCodes.has(c))) return false;
      if (textsKind !== 'all' && item.text_type !== textsKind) return false;
      if (!matchQ(item.title, item.ta_reference, item.procedure_ref, item.rapporteur_name)) return false;
      return true;
    });
    const byCode = new Map<string, typeof filtered>();
    for (const item of filtered) {
      const code = (item.committees && item.committees[0]) || 'OTHER';
      const list = byCode.get(code) || [];
      list.push(item);
      byCode.set(code, list);
    }
    return Array.from(byCode.entries())
      .map(([code, items]) => ({
        code,
        name: code === 'OTHER' ? t('myFilesTab.committeeOther') : committeeNameOf(code),
        isMine: myCommittees.includes(code),
        items: [...items].sort((a, b) =>
          new Date(b.adoption_date).getTime() - new Date(a.adoption_date).getTime()),
      }))
      .sort((a, b) =>
        (Number(b.isMine) - Number(a.isMine))
        || (a.code === 'OTHER' ? 1 : b.code === 'OTHER' ? -1 : a.code.localeCompare(b.code)));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [textsAdoptedItems, textsMode, textsChips, textsKind, myCommittees, q, committees]);

  const textsVisibleCount = textsGroups.reduce((n, g) => n + g.items.length, 0);
  const toggleTextsChip = (code: string) =>
    setTextsChips((prev) => prev.includes(code)
      ? prev.filter((c) => c !== code) : [...prev, code]);

  const textsTrackedIds = useMemo(
    () => new Set((textsTrackedItems || []).map((tk) => tk.text.id)),
    [textsTrackedItems],
  );
  const handleTextTrack = async (item: { id: string }) => {
    try { await trackTextItem(item.id); } catch { alert(t('myFilesTab.trackFailed')); }
  };
  const handleTextUntrack = async (item: { id: string }) => {
    try { await untrackTextItem(item.id); } catch { alert(t('myFilesTab.trackFailed')); }
  };
  const handleTextViewDetail = (item: { legislative_carriage_id?: string; procedure_ref?: string }) => {
    if (item.legislative_carriage_id) {
      fetchFileDetail(item.legislative_carriage_id);
    } else if (item.procedure_ref) {
      window.open(
        `https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${encodeURIComponent(item.procedure_ref)}`,
        '_blank', 'noopener,noreferrer',
      );
    }
  };

  // --- Commission documents: PI split by DG + kind/search + grouping --------
  const DOC_KINDS = ['COM', 'SWD', 'JOIN', 'OJ'] as const;
  const dgNameOf = (code: string) => DG_NAMES[code] || code;
  const docsGroups = useMemo(() => {
    const activeCodes = new Set(docsChips);
    const filtered = commissionDocItems.filter((item) => {
      const dg = item.dg_responsible || '';
      if (docsMode === 'mine' && myDgs.length > 0 && !myDgs.includes(dg)) return false;
      if (activeCodes.size > 0 && !activeCodes.has(dg)) return false;
      if (docsKind !== 'all' && item.doc_type !== docsKind) return false;
      if (!matchQ(item.title, item.reference, item.dg_responsible, item.procedure_ref)) return false;
      return true;
    });
    const byDg = new Map<string, typeof filtered>();
    for (const item of filtered) {
      const dg = item.dg_responsible || 'OTHER';
      const list = byDg.get(dg) || [];
      list.push(item);
      byDg.set(dg, list);
    }
    return Array.from(byDg.entries())
      .map(([code, items]) => ({
        code,
        name: code === 'OTHER' ? t('myFilesTab.committeeOther') : dgNameOf(code),
        isMine: myDgs.includes(code),
        items: [...items].sort((a, b) =>
          new Date(b.publication_date || 0).getTime() - new Date(a.publication_date || 0).getTime()),
      }))
      .sort((a, b) =>
        (Number(b.isMine) - Number(a.isMine))
        || (a.code === 'OTHER' ? 1 : b.code === 'OTHER' ? -1 : a.code.localeCompare(b.code)));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [commissionDocItems, docsMode, docsChips, docsKind, myDgs, q]);

  const docsVisibleCount = docsGroups.reduce((n, g) => n + g.items.length, 0);
  const toggleDocsChip = (code: string) =>
    setDocsChips((prev) => prev.includes(code)
      ? prev.filter((c) => c !== code) : [...prev, code]);
  // DGs available to add (present in the data, not already a chip).
  const availableDgs = useMemo(() => {
    const set = new Set<string>();
    for (const item of commissionDocItems) {
      if (item.dg_responsible) set.add(item.dg_responsible);
    }
    return Array.from(set).sort();
  }, [commissionDocItems]);

  const docsTrackedIds = useMemo(
    () => new Set((commissionTrackedItems || []).map((tk) => tk.document.id)),
    [commissionTrackedItems],
  );
  const handleDocTrack = async (item: { id: string }) => {
    try { await trackCommissionItem(item.id); } catch { alert(t('myFilesTab.trackFailed')); }
  };
  const handleDocUntrack = async (item: { id: string }) => {
    try { await untrackCommissionItem(item.id); } catch { alert(t('myFilesTab.trackFailed')); }
  };

  // Cross-link to the Amendments sub-feature (MEP Amendments) with this
  // procedure preselected. Search-only navigation keeps the MEUB pathname.
  const openMepAmendments = (ref?: string | null) => {
    if (!ref) return;
    navigate({ search: `?tab=amendments&procedure=${encodeURIComponent(ref)}` });
  };

  return (
    <div className="my-tracked-files-tab">
      {/* Header */}
      <div className="my-tracked-files-tab__header">
        <div className="my-tracked-files-tab__header-left">
          <h2>{t('myFilesTab.title')}</h2>
          <p className="my-tracked-files-tab__subtitle">
            {activeTab === 'legislative'
              ? t('myFilesTab.filesTracked', { count: trackedFiles.length })
              : activeTab === 'committee'
              ? t('myFilesTab.committeeItems', { count: committeeWorkItems.length })
              : activeTab === 'texts_adopted'
              ? t('myFilesTab.adoptedTexts', { count: textsAdoptedItems.length })
              : t('myFilesTab.commissionDocs', { count: commissionDocItems.length })
            }
          </p>
        </div>
        <div className="my-tracked-files-tab__header-actions">
          <button
            className="my-tracked-files-tab__btn my-tracked-files-tab__btn--icon"
            onClick={handleRefresh}
            disabled={isLoadingTrackedFiles || isLoadingCommitteeWork || isLoadingTextsAdopted || isLoadingCommissionDocs}
            title={t('myFilesTab.refresh')}
            aria-label={t('myFilesTab.refresh')}
          >
            <Icon path={mdiRefresh} size={0.85} />
          </button>
          {activeTab === 'legislative' && (
            <button
              className="my-tracked-files-tab__btn my-tracked-files-tab__btn--secondary"
              onClick={handleSyncFromInterests}
              disabled={isSyncing}
              title={t('myFilesTab.syncFromInterestsHint')}
            >
              <Icon path={isSyncing ? mdiLoading : mdiPlaylistPlus} size={0.8} spin={isSyncing} />
              {isSyncing ? t('myFilesTab.syncing') : t('myFilesTab.syncFromInterests')}
            </button>
          )}
          {activeTab === 'legislative' && (
            <button
              className="my-tracked-files-tab__btn my-tracked-files-tab__btn--primary"
              onClick={handleOpenAddModal}
            >
              <Icon path={mdiPlus} size={0.8} />
              {t('myFilesTab.trackFile')}
            </button>
          )}
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="my-tracked-files-tab__tabs">
        <button
          className={`my-tracked-files-tab__tab ${activeTab === 'legislative' ? 'my-tracked-files-tab__tab--active' : ''}`}
          onClick={() => setActiveTab('legislative')}
          title={t('myFilesTab.tipLegislative')}
        >
          <Icon path={mdiFileDocumentOutline} size={0.8} />
          {t('myFilesTab.legislativeTrain')}
          <Icon path={mdiInformationOutline} size={0.55} className="my-tracked-files-tab__tab-info" />
        </button>
        <button
          className={`my-tracked-files-tab__tab ${activeTab === 'committee' ? 'my-tracked-files-tab__tab--active' : ''}`}
          onClick={() => setActiveTab('committee')}
          title={t('myFilesTab.tipCommittee')}
        >
          <Icon path={mdiAccountGroupOutline} size={0.8} />
          {t('myFilesTab.committeeWork')}
          <Icon path={mdiInformationOutline} size={0.55} className="my-tracked-files-tab__tab-info" />
        </button>
        <button
          className={`my-tracked-files-tab__tab ${activeTab === 'texts_adopted' ? 'my-tracked-files-tab__tab--active' : ''}`}
          onClick={() => setActiveTab('texts_adopted')}
          title={t('myFilesTab.tipTextsAdopted')}
        >
          <Icon path={mdiTextBoxCheckOutline} size={0.8} />
          {t('myFilesTab.textsAdopted')}
          <Icon path={mdiInformationOutline} size={0.55} className="my-tracked-files-tab__tab-info" />
        </button>
        <button
          className={`my-tracked-files-tab__tab ${activeTab === 'commission_docs' ? 'my-tracked-files-tab__tab--active' : ''}`}
          onClick={() => setActiveTab('commission_docs')}
          title={t('myFilesTab.tipCommissionDocs')}
        >
          <Icon path={mdiFileDocumentMultipleOutline} size={0.8} />
          {t('myFilesTab.commissionDocs')}
          <Icon path={mdiInformationOutline} size={0.55} className="my-tracked-files-tab__tab-info" />
        </button>
      </div>

      {/* Search filter bar — filters the active tab's list */}
      <div className="my-tracked-files-tab__search">
        <Icon path={mdiMagnify} size={0.85} className="my-tracked-files-tab__search-icon" />
        <input
          type="search"
          className="my-tracked-files-tab__search-input"
          value={listQuery}
          onChange={(e) => setListQuery(e.target.value)}
          placeholder={t('myFilesTab.searchPlaceholder')}
          aria-label={t('myFilesTab.searchPlaceholder')}
        />
        {listQuery && (
          <button
            type="button"
            className="my-tracked-files-tab__search-clear"
            onClick={() => setListQuery('')}
            aria-label={t('myFilesTab.clearSearch')}
          >
            <Icon path={mdiClose} size={0.7} />
          </button>
        )}
      </div>

      {/* Legislative Files Tab Content */}
      {activeTab === 'legislative' && (
        <>
          {/* Hot This Week Widget — surfaces files with recent activity */}
          <HotThisWeekWidget
            isAuthenticated={isAuthenticated}
            onView={(file) => fetchFileDetail(file.file_id)}
            onTrack={async (file) => {
              try {
                await trackFile(file.carriage_id, true);
                await fetchTrackedFiles();
              } catch (error: unknown) {
                const ax = error as { response?: { status?: number; data?: { detail?: string } } };
                if (ax.response?.status === 401) {
                  alert(t('myFilesTab.alertLogin'));
                } else {
                  alert(ax.response?.data?.detail || t('myFilesTab.alertFailedTrack'));
                }
              }
            }}
          />

          {/* Recent Changes Section */}
          {recentChanges.length > 0 && (
            <div className="my-tracked-files-tab__changes">
              <h3 className="my-tracked-files-tab__section-title">
                <Icon path={mdiHistory} size={0.9} />
                {t('myFilesTab.recentChanges')}
              </h3>
              <div className="my-tracked-files-tab__changes-list">
                {recentChanges.slice(0, 5).map((change, idx) => (
                  <div key={idx} className="my-tracked-files-tab__change-item">
                    <div
                      className="my-tracked-files-tab__change-icon"
                      data-type={change.change_type}
                    >
                      <Icon path={getChangeIcon(change.change_type)} size={0.8} />
                    </div>
                    <div className="my-tracked-files-tab__change-content">
                      <div className="my-tracked-files-tab__change-title">
                        {change.title}
                      </div>
                      <div className="my-tracked-files-tab__change-description">
                        {change.change_type === 'status_change' && (
                          <>
                            {t('myFilesTab.statusChanged')} {change.old_value?.replace(/_/g, ' ')} →{' '}
                            <strong>{change.new_value?.replace(/_/g, ' ')}</strong>
                          </>
                        )}
                        {change.change_type === 'new_document' && change.description}
                        {change.change_type === 'blocking' && t('myFilesTab.blockedNoProgress')}
                      </div>
                    </div>
                    <div className="my-tracked-files-tab__change-time">
                      {formatTimeAgo(change.changed_at)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tracked Files List */}
          <div className="my-tracked-files-tab__files">
            <h3 className="my-tracked-files-tab__section-title">
              <Icon path={mdiFileDocumentOutline} size={0.9} />
              {t('myFilesTab.trackedFiles')}
            </h3>

            {isLoadingTrackedFiles ? (
          <div className="my-tracked-files-tab__loading">
            {t('myFilesTab.loadingTracked')}
          </div>
        ) : trackedFiles.length === 0 ? (
          <div className="my-tracked-files-tab__empty">
            <Icon path={mdiFileDocumentOutline} size={2} color="#ccc" />
            <h4>{t('myFilesTab.noTrackedFiles')}</h4>
            <p>{t('myFilesTab.syncFromInterestsHint')}</p>
            <button
              className="my-tracked-files-tab__btn my-tracked-files-tab__btn--primary"
              onClick={handleSyncFromInterests}
              disabled={isSyncing}
            >
              <Icon path={isSyncing ? mdiLoading : mdiPlaylistPlus} size={0.8} spin={isSyncing} />
              {isSyncing ? t('myFilesTab.syncing') : t('myFilesTab.syncFromInterests')}
            </button>
            <button
              className="my-tracked-files-tab__btn my-tracked-files-tab__btn--secondary"
              onClick={handleOpenAddModal}
            >
              <Icon path={mdiPlus} size={0.8} />
              {t('myFilesTab.trackYourFirstFile')}
            </button>
          </div>
        ) : visibleTracked.length === 0 ? (
          <div className="my-tracked-files-tab__empty">
            <Icon path={mdiMagnify} size={2} color="#ccc" />
            <p>{t('myFilesTab.noFilesMatchSearch')}</p>
          </div>
        ) : (
          <div className="my-tracked-files-tab__files-list">
            {TRACKED_GROUP_ORDER.map(({ typeKey, titleKey, tipKey }) => {
              const groupFiles = visibleTracked.filter(
                (file) => plainLanguageTypeKey(file.oeil_procedure_ref) === typeKey,
              );
              if (groupFiles.length === 0) return null;
              return (
                <div key={titleKey} className="my-tracked-files-tab__group">
                  <h4 className="my-tracked-files-tab__group-title">
                    {t(`myFilesTab.${titleKey}`)}
                    {tipKey && (
                      <span className="my-tracked-files-tab__group-info" title={t(`myFilesTab.${tipKey}`)}>
                        <Icon path={mdiInformationOutline} size={0.6} />
                      </span>
                    )}
                    <span className="my-tracked-files-tab__group-count">({groupFiles.length})</span>
                  </h4>
                  {groupFiles.map((file) => (
                    <TrackedFileCard
                      key={file.id}
                      file={file}
                      onViewDetail={() => fetchFileDetail(file.file_id)}
                      onUntrack={() => handleUntrack(file)}
                      onDraftAmendment={() => {
                        navigate('/amendator');
                      }}
                      onMepAmendments={() => openMepAmendments(file.oeil_procedure_ref)}
                      getStatusColor={getStatusColor}
                      amendmentCount={amendmentCounts[file.carriage_id]}
                    />
                  ))}
                </div>
              );
            })}
          </div>
        )}
          </div>
        </>
      )}

      {/* In committee Tab Content */}
      {activeTab === 'committee' && (
        <div className="my-tracked-files-tab__committee-work">
          <div className="my-tracked-files-tab__committee-controls">
            {/* Segmented toggle: My interests | All committees */}
            {myCommittees.length > 0 && (
              <div className="my-tracked-files-tab__segmented" role="tablist">
                <button
                  type="button"
                  role="tab"
                  aria-selected={committeeMode === 'mine'}
                  className={`my-tracked-files-tab__segment ${committeeMode === 'mine' ? 'my-tracked-files-tab__segment--active' : ''}`}
                  onClick={() => { setCommitteeMode('mine'); setCommitteeChips(myCommittees); }}
                >
                  {t('myFilesTab.myInterests')} ({myCommittees.length})
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={committeeMode === 'all'}
                  className={`my-tracked-files-tab__segment ${committeeMode === 'all' ? 'my-tracked-files-tab__segment--active' : ''}`}
                  onClick={() => { setCommitteeMode('all'); setCommitteeChips([]); }}
                >
                  {t('myFilesTab.allCommitteesLabel')}
                </button>
              </div>
            )}

            {/* Committee chips = the active committee filter (editable) */}
            <div className="my-tracked-files-tab__committee-chips">
              {committeeChips.map((code) => (
                <button
                  key={code}
                  type="button"
                  className="my-tracked-files-tab__chip my-tracked-files-tab__chip--active"
                  title={committeeNameOf(code)}
                  onClick={() => toggleChip(code)}
                >
                  {code}
                  <Icon path={mdiClose} size={0.55} />
                </button>
              ))}
              <select
                className="my-tracked-files-tab__chip-add"
                value={addCommitteeCode}
                onChange={(e) => { if (e.target.value) { toggleChip(e.target.value); setAddCommitteeCode(''); } }}
              >
                <option value="">{t('myFilesTab.addCommittee')}</option>
                {committees.filter((c) => !committeeChips.includes(c.code)).map((c) => (
                  <option key={c.code} value={c.code}>{c.code} - {c.name}</option>
                ))}
              </select>
            </div>

            {/* Search + Kind + technical toggle */}
            <div className="my-tracked-files-tab__committee-filters">
              <div className="my-tracked-files-tab__committee-search">
                <Icon path={mdiMagnify} size={0.8} />
                <input
                  type="text"
                  placeholder={t('myFilesTab.searchCommittee')}
                  value={listQuery}
                  onChange={(e) => setListQuery(e.target.value)}
                />
              </div>
              <div className="my-tracked-files-tab__committee-kind">
                <Icon path={mdiFilterVariant} size={0.8} />
                <select value={committeeKind} onChange={(e) => setCommitteeKind(e.target.value)}>
                  <option value="all">{t('myFilesTab.allKinds')}</option>
                  {COMMITTEE_KINDS.map((k) => (
                    <option key={k} value={k}>{t(`myFilesTab.${k}`)}</option>
                  ))}
                </select>
              </div>
              <label className="my-tracked-files-tab__committee-techtoggle">
                <input
                  type="checkbox"
                  checked={showTechnical}
                  onChange={(e) => setShowTechnical(e.target.checked)}
                />
                {t('myFilesTab.showTechnical')}
              </label>
            </div>

            <div className="my-tracked-files-tab__committee-note">
              <Icon path={mdiInformationOutline} size={0.6} />
              <span title={t('myFilesTab.committeeDataNote')}>
                {t('myFilesTab.committeeDataNoteShort')}
              </span>
            </div>
          </div>

          {/* Grouped-by-committee list */}
          {isLoadingCommitteeWork ? (
            <div className="my-tracked-files-tab__loading">
              <Icon path={mdiLoading} size={1} spin />
              {t('myFilesTab.loadingCommittee')}
            </div>
          ) : committeeVisibleCount === 0 ? (
            <div className="my-tracked-files-tab__empty">
              <Icon path={mdiAccountGroupOutline} size={2} color="#ccc" />
              <h4>{t('myFilesTab.noCommitteeWork')}</h4>
              <p>
                {committeeMode === 'mine'
                  ? t('myFilesTab.noCommitteeMine')
                  : t('myFilesTab.tryAdjusting')}
              </p>
            </div>
          ) : (
            <div className="my-tracked-files-tab__committee-groups">
              {committeeGroups.map((group) => (
                <div key={group.code} className="my-tracked-files-tab__committee-group">
                  <div className="my-tracked-files-tab__committee-group-title">
                    <span className="my-tracked-files-tab__committee-group-code">{group.code}</span>
                    <span className="my-tracked-files-tab__committee-group-name">{group.name}</span>
                    {group.isMine && (
                      <span
                        className="my-tracked-files-tab__committee-group-mine"
                        title={t('myFilesTab.matchesInterests')}
                      >
                        <Icon path={mdiStarOutline} size={0.6} />
                        {t('myFilesTab.matchesInterests')}
                      </span>
                    )}
                    <span className="my-tracked-files-tab__committee-group-count">{group.items.length}</span>
                  </div>
                  <div className="my-tracked-files-tab__committee-list">
                    {group.items.map((item) => (
                      <CommitteeWorkCard
                        key={item.id}
                        item={item}
                        isJunkTitle={isStubTitle(item.title)}
                        isTracked={committeeTrackedIds.has(item.id)}
                        onViewDetail={() => handleCommitteeViewDetail(item)}
                        onTrack={() => handleCommitteeTrack(item)}
                        onUntrack={() => handleCommitteeUntrack(item)}
                        onMepAmendments={() => openMepAmendments(item.procedure_ref)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Texts Adopted Tab Content */}
      {activeTab === 'texts_adopted' && (
        <div className="my-tracked-files-tab__committee-work">
          <div className="my-tracked-files-tab__committee-controls">
            {/* Segmented toggle: My interests | All committees */}
            {myCommittees.length > 0 && (
              <div className="my-tracked-files-tab__segmented" role="tablist">
                <button
                  type="button"
                  role="tab"
                  aria-selected={textsMode === 'mine'}
                  className={`my-tracked-files-tab__segment ${textsMode === 'mine' ? 'my-tracked-files-tab__segment--active' : ''}`}
                  onClick={() => { setTextsMode('mine'); setTextsChips(myCommittees); }}
                >
                  {t('myFilesTab.myInterests')} ({myCommittees.length})
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={textsMode === 'all'}
                  className={`my-tracked-files-tab__segment ${textsMode === 'all' ? 'my-tracked-files-tab__segment--active' : ''}`}
                  onClick={() => { setTextsMode('all'); setTextsChips([]); }}
                >
                  {t('myFilesTab.allCommitteesLabel')}
                </button>
              </div>
            )}

            {/* Committee chips = the active committee filter (editable) */}
            <div className="my-tracked-files-tab__committee-chips">
              {textsChips.map((code) => (
                <button
                  key={code}
                  type="button"
                  className="my-tracked-files-tab__chip my-tracked-files-tab__chip--active"
                  title={committeeNameOf(code)}
                  onClick={() => toggleTextsChip(code)}
                >
                  {code}
                  <Icon path={mdiClose} size={0.55} />
                </button>
              ))}
              <select
                className="my-tracked-files-tab__chip-add"
                value={addTextsCommitteeCode}
                onChange={(e) => { if (e.target.value) { toggleTextsChip(e.target.value); setAddTextsCommitteeCode(''); } }}
              >
                <option value="">{t('myFilesTab.addCommittee')}</option>
                {committees.filter((c) => !textsChips.includes(c.code)).map((c) => (
                  <option key={c.code} value={c.code}>{c.code} - {c.name}</option>
                ))}
              </select>
            </div>

            {/* Search + kind */}
            <div className="my-tracked-files-tab__committee-filters">
              <div className="my-tracked-files-tab__committee-search">
                <Icon path={mdiMagnify} size={0.8} />
                <input
                  type="text"
                  placeholder={t('myFilesTab.searchCommittee')}
                  value={listQuery}
                  onChange={(e) => setListQuery(e.target.value)}
                />
              </div>
              <div className="my-tracked-files-tab__committee-kind">
                <Icon path={mdiFilterVariant} size={0.8} />
                <select value={textsKind} onChange={(e) => setTextsKind(e.target.value)}>
                  <option value="all">{t('myFilesTab.allTypes')}</option>
                  {TEXT_KINDS.map((k) => (
                    <option key={k} value={k}>
                      {t(`myFilesTab.${k === 'legislative_resolution' ? 'legislativeResolution' : k}`)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Grouped-by-committee list */}
          {isLoadingTextsAdopted ? (
            <div className="my-tracked-files-tab__loading">
              <Icon path={mdiLoading} size={1} spin />
              {t('myFilesTab.loadingAdopted')}
            </div>
          ) : textsVisibleCount === 0 ? (
            <div className="my-tracked-files-tab__empty">
              <Icon path={mdiTextBoxCheckOutline} size={2} color="#ccc" />
              <h4>{t('myFilesTab.noAdoptedFound')}</h4>
              <p>
                {textsMode === 'mine'
                  ? t('myFilesTab.noCommitteeMine')
                  : t('myFilesTab.tryAdjusting')}
              </p>
            </div>
          ) : (
            <div className="my-tracked-files-tab__committee-groups">
              {textsGroups.map((group) => (
                <div key={group.code} className="my-tracked-files-tab__committee-group">
                  <div className="my-tracked-files-tab__committee-group-title">
                    <span className="my-tracked-files-tab__committee-group-code">{group.code}</span>
                    <span className="my-tracked-files-tab__committee-group-name">{group.name}</span>
                    {group.isMine && (
                      <span
                        className="my-tracked-files-tab__committee-group-mine"
                        title={t('myFilesTab.matchesInterests')}
                      >
                        <Icon path={mdiStarOutline} size={0.6} />
                        {t('myFilesTab.matchesInterests')}
                      </span>
                    )}
                    <span className="my-tracked-files-tab__committee-group-count">{group.items.length}</span>
                  </div>
                  <div className="my-tracked-files-tab__texts-adopted-list">
                    {group.items.map((item) => (
                      <TextAdoptedCard
                        key={item.id}
                        item={item}
                        isTracked={textsTrackedIds.has(item.id)}
                        onViewDetail={() => handleTextViewDetail(item)}
                        onTrack={() => handleTextTrack(item)}
                        onUntrack={() => handleTextUntrack(item)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Commission Documents Tab Content */}
      {activeTab === 'commission_docs' && (
        <div className="my-tracked-files-tab__committee-work">
          <div className="my-tracked-files-tab__committee-controls">
            {/* Segmented toggle: My interests | All departments */}
            {myDgs.length > 0 && (
              <div className="my-tracked-files-tab__segmented" role="tablist">
                <button
                  type="button"
                  role="tab"
                  aria-selected={docsMode === 'mine'}
                  className={`my-tracked-files-tab__segment ${docsMode === 'mine' ? 'my-tracked-files-tab__segment--active' : ''}`}
                  onClick={() => { setDocsMode('mine'); setDocsChips(myDgs); }}
                >
                  {t('myFilesTab.myInterests')} ({myDgs.length})
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={docsMode === 'all'}
                  className={`my-tracked-files-tab__segment ${docsMode === 'all' ? 'my-tracked-files-tab__segment--active' : ''}`}
                  onClick={() => { setDocsMode('all'); setDocsChips([]); }}
                >
                  {t('myFilesTab.allDepartmentsLabel')}
                </button>
              </div>
            )}

            {/* DG chips = the active department filter (editable) */}
            <div className="my-tracked-files-tab__committee-chips">
              {docsChips.map((code) => (
                <button
                  key={code}
                  type="button"
                  className="my-tracked-files-tab__chip my-tracked-files-tab__chip--active"
                  title={dgNameOf(code)}
                  onClick={() => toggleDocsChip(code)}
                >
                  {code}
                  <Icon path={mdiClose} size={0.55} />
                </button>
              ))}
              <select
                className="my-tracked-files-tab__chip-add"
                value={addDocsDg}
                onChange={(e) => { if (e.target.value) { toggleDocsChip(e.target.value); setAddDocsDg(''); } }}
              >
                <option value="">{t('myFilesTab.addDepartment')}</option>
                {availableDgs.filter((c) => !docsChips.includes(c)).map((c) => (
                  <option key={c} value={c}>{c} - {dgNameOf(c)}</option>
                ))}
              </select>
            </div>

            {/* Search + kind */}
            <div className="my-tracked-files-tab__committee-filters">
              <div className="my-tracked-files-tab__committee-search">
                <Icon path={mdiMagnify} size={0.8} />
                <input
                  type="text"
                  placeholder={t('myFilesTab.searchDocsPlaceholder')}
                  value={listQuery}
                  onChange={(e) => setListQuery(e.target.value)}
                />
              </div>
              <div className="my-tracked-files-tab__committee-kind">
                <Icon path={mdiFilterVariant} size={0.8} />
                <select value={docsKind} onChange={(e) => setDocsKind(e.target.value)}>
                  <option value="all">{t('myFilesTab.allTypes')}</option>
                  {DOC_KINDS.map((k) => (
                    <option key={k} value={k}>{t(`myFilesTab.${k.toLowerCase()}Alias`)}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Grouped-by-DG list */}
          {isLoadingCommissionDocs ? (
            <div className="my-tracked-files-tab__loading">
              <Icon path={mdiLoading} size={1} spin />
              {t('myFilesTab.loadingCommissionDocs')}
            </div>
          ) : docsVisibleCount === 0 ? (
            <div className="my-tracked-files-tab__empty">
              <Icon path={mdiFileDocumentMultipleOutline} size={2} color="#ccc" />
              <h4>{t('myFilesTab.noCommissionDocs')}</h4>
              <p>
                {docsMode === 'mine'
                  ? t('myFilesTab.noDepartmentMine')
                  : t('myFilesTab.tryAdjusting')}
              </p>
            </div>
          ) : (
            <div className="my-tracked-files-tab__committee-groups">
              {docsGroups.map((group) => (
                <div key={group.code} className="my-tracked-files-tab__committee-group">
                  <div className="my-tracked-files-tab__committee-group-title">
                    <span className="my-tracked-files-tab__committee-group-code">{group.code}</span>
                    <span className="my-tracked-files-tab__committee-group-name">{group.name}</span>
                    {group.isMine && (
                      <span
                        className="my-tracked-files-tab__committee-group-mine"
                        title={t('myFilesTab.matchesInterests')}
                      >
                        <Icon path={mdiStarOutline} size={0.6} />
                        {t('myFilesTab.matchesInterests')}
                      </span>
                    )}
                    <span className="my-tracked-files-tab__committee-group-count">{group.items.length}</span>
                  </div>
                  <div className="my-tracked-files-tab__commission-docs-list">
                    {group.items.map((item) => (
                      <CommissionDocumentCard
                        key={item.id}
                        item={item}
                        isTracked={docsTrackedIds.has(item.id)}
                        onTrack={() => handleDocTrack(item)}
                        onUntrack={() => handleDocUntrack(item)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Add File Modal - Search and Track (uses portal to escape stacking context) */}
      {showAddModal && createPortal(
        <div className="my-tracked-files-tab__modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="my-tracked-files-tab__modal my-tracked-files-tab__modal--search" onClick={(e) => e.stopPropagation()}>
            <div className="my-tracked-files-tab__modal-header">
              <h3>{t('myFilesTab.trackLegislativeFile')}</h3>
              <button
                className="my-tracked-files-tab__modal-close"
                onClick={() => setShowAddModal(false)}
              >
                <Icon path={mdiClose} size={0.9} />
              </button>
            </div>

            {/* Recommended shortcut: auto-populate from interests */}
            <div className="my-tracked-files-tab__modal-nudge">
              <Icon path={mdiPlaylistPlus} size={0.9} />
              <span>{t('myFilesTab.modalNudge')}</span>
              <button
                className="my-tracked-files-tab__modal-nudge-btn"
                onClick={() => {
                  setShowAddModal(false);
                  handleSyncFromInterests();
                }}
                disabled={isSyncing}
              >
                {t('myFilesTab.syncFromInterests')}
              </button>
            </div>

            {/* Search-first: search always visible; status/sort fold away to free result space */}
            <div className="my-tracked-files-tab__modal-search">
              <div className="my-tracked-files-tab__search-input">
                <Icon path={mdiMagnify} size={0.9} />
                <input
                  type="search"
                  placeholder={t('myFilesTab.modalSearchPlaceholder')}
                  value={searchQuery}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  autoFocus
                />
                {searchQuery && (
                  <button onClick={() => handleSearchChange('')} aria-label={t('myFilesTab.clearSearch')}>
                    <Icon path={mdiClose} size={0.7} />
                  </button>
                )}
              </div>
              <button
                type="button"
                className={`my-tracked-files-tab__filter-toggle ${showFilters ? 'my-tracked-files-tab__filter-toggle--active' : ''}`}
                onClick={() => setShowFilters((v) => !v)}
                aria-expanded={showFilters}
              >
                <Icon path={mdiFilterVariant} size={0.8} />
                {t('myFilesTab.filters')}
                <Icon path={showFilters ? mdiChevronUp : mdiChevronDown} size={0.7} />
              </button>
            </div>
            {showFilters && (
              <div className="my-tracked-files-tab__modal-filters">
                <select
                  className="my-tracked-files-tab__modal-select"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  aria-label={t('myFilesTab.statusLabel')}
                >
                  <option value="all">{t('myFilesTab.allWithCount', { count: browseFiles.length })}</option>
                  {availableStatuses.map((status) => (
                    <option key={status} value={status}>
                      {status.replace(/_/g, ' ')}
                    </option>
                  ))}
                </select>
                <select
                  className="my-tracked-files-tab__modal-select"
                  value={sortOrder}
                  onChange={(e) => setSortOrder(e.target.value as 'newest' | 'oldest' | 'alphabetical')}
                  aria-label={t('myFilesTab.sortLabel')}
                >
                  <option value="newest">{t('myFilesTab.sortNewest')}</option>
                  <option value="oldest">{t('myFilesTab.sortOldest')}</option>
                  <option value="alphabetical">{t('myFilesTab.sortAZ')}</option>
                </select>
              </div>
            )}

            {/* Files List */}
            <div className="my-tracked-files-tab__search-results">
              {isLoadingFiles ? (
                <div className="my-tracked-files-tab__search-loading">
                  <Icon path={mdiLoading} size={1} spin />
                  {t('myFilesTab.loadingLegFiles')}
                </div>
              ) : browseFiles.length === 0 ? (
                <div className="my-tracked-files-tab__search-empty">
                  {searchQuery ? t('myFilesTab.noFilesMatch') : t('myFilesTab.noFilesAvailable')}
                </div>
              ) : (
                <div className="my-tracked-files-tab__search-list">
                  {shownFiles.map((file) => {
                    const alreadyTracked = isAlreadyTracked(file);
                    const isCurrentlyTracking = trackingFileId === file.id;
                    const typeKey = plainLanguageTypeKey(file.oeil_procedure_ref);

                    return (
                      <div
                        key={file.id}
                        className={`my-tracked-files-tab__search-item ${alreadyTracked ? 'my-tracked-files-tab__search-item--tracked' : ''}`}
                      >
                        <div className="my-tracked-files-tab__search-item-content">
                          <div className="my-tracked-files-tab__search-item-title">
                            {file.title}
                          </div>
                          <div className="my-tracked-files-tab__search-item-meta">
                            {typeKey && (
                              <span className="my-tracked-files-tab__search-item-type">
                                {t(`myFilesTab.${typeKey}`)}
                              </span>
                            )}
                            <span
                              className="my-tracked-files-tab__search-item-status"
                              style={{ backgroundColor: getStatusColor(file.current_status) }}
                            >
                              {file.current_status.replace(/_/g, ' ')}
                            </span>
                            {file.oeil_procedure_ref && (
                              <span className="my-tracked-files-tab__search-item-ref">
                                {file.oeil_procedure_ref}
                              </span>
                            )}
                          </div>
                        </div>
                        <button
                          className="my-tracked-files-tab__search-item-track"
                          onClick={() => handleTrackFromModal(file)}
                          disabled={alreadyTracked || isCurrentlyTracking || isTracking}
                          title={alreadyTracked ? t('myFilesTab.alreadyTracked') : t('myFilesTab.trackThisFile')}
                        >
                          {isCurrentlyTracking ? (
                            <Icon path={mdiLoading} size={0.8} spin />
                          ) : (
                            <Icon path={mdiStarOutline} size={0.8} />
                          )}
                          {alreadyTracked ? t('myFilesTab.tracked') : t('myFilesTab.track')}
                        </button>
                      </div>
                    );
                  })}
                  {/* Load more */}
                  {browseFiles.length > visibleCount && (
                    <div className="my-tracked-files-tab__load-more">
                      <button
                        className="my-tracked-files-tab__load-more-btn"
                        onClick={() => setVisibleCount((c) => c + PAGE_STEP)}
                      >
                        {t('myFilesTab.loadMore')}
                      </button>
                      <span className="my-tracked-files-tab__load-more-info">
                        {t('myFilesTab.showingCount', { shown: shownFiles.length, total: browseFiles.length })}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Advanced: add by OEIL procedure reference (expert path) */}
            <div className="my-tracked-files-tab__advanced">
              <button
                type="button"
                className="my-tracked-files-tab__advanced-toggle"
                onClick={() => setShowAdvancedRef((v) => !v)}
                aria-expanded={showAdvancedRef}
              >
                <Icon path={showAdvancedRef ? mdiChevronUp : mdiChevronDown} size={0.8} />
                {t('myFilesTab.advancedAddByRef')}
              </button>
              {showAdvancedRef && (
                <div className="my-tracked-files-tab__oeil-track">
                  <p className="my-tracked-files-tab__oeil-track-hint">
                    {t('myFilesTab.oeilHintPrefix')}{' '}
                    <a href="https://oeil.europarl.europa.eu" target="_blank" rel="noopener noreferrer">OEIL</a>.
                  </p>
                  <div className="my-tracked-files-tab__oeil-track-input">
                    <input
                      type="text"
                      placeholder={t('myFilesTab.oeilPlaceholder')}
                      value={oeilProcedureRef}
                      onChange={(e) => {
                        setOeilProcedureRef(e.target.value.toUpperCase());
                        setOeilTrackError(null);
                        setOeilTrackSuccess(null);
                      }}
                      onKeyDown={(e) => e.key === 'Enter' && handleTrackOeilProcedure()}
                    />
                    <button
                      className="my-tracked-files-tab__oeil-track-btn"
                      onClick={handleTrackOeilProcedure}
                      disabled={isTrackingOeil || !oeilProcedureRef.trim()}
                    >
                      {isTrackingOeil ? <Icon path={mdiLoading} size={0.8} spin /> : <Icon path={mdiPlus} size={0.8} />}
                      {t('myFilesTab.trackBtn')}
                    </button>
                  </div>
                  {oeilTrackError && (
                    <div className="my-tracked-files-tab__oeil-track-error">
                      <Icon path={mdiAlertCircleOutline} size={0.7} />
                      {oeilTrackError}
                    </div>
                  )}
                  {oeilTrackSuccess && (
                    <div className="my-tracked-files-tab__oeil-track-success">
                      <Icon path={mdiStarOutline} size={0.7} />
                      {oeilTrackSuccess}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* File Detail Modal */}
      <LegislativeFileDetail />
    </div>
  );
};

// Tracked File Card Component
interface TrackedFileCardProps {
  file: TrackedFile;
  onViewDetail: () => void;
  onUntrack: () => void;
  onDraftAmendment: () => void;
  onMepAmendments?: () => void;
  getStatusColor: (status: string) => string;
  amendmentCount?: number;
}

const TrackedFileCard = ({ file, onViewDetail, onUntrack, onDraftAmendment, onMepAmendments, getStatusColor, amendmentCount }: TrackedFileCardProps) => {
  const { t } = useTranslation();
  const oeilUrl = file.oeil_procedure_ref
    ? `https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${encodeURIComponent(file.oeil_procedure_ref)}`
    : null;
  const eultUrl = file.oeil_procedure_ref ? getEultUrl(file.oeil_procedure_ref) : null;
  const regDelUrl = file.oeil_procedure_ref ? getRegDelUrl(file.oeil_procedure_ref) : null;

  return (
    <div className="tracked-file-card">
      <div className="tracked-file-card__header">
        <div
          className="tracked-file-card__status"
          style={{ backgroundColor: getStatusColor(file.current_status) }}
        >
          {file.current_status.replace(/_/g, ' ')}
        </div>
        {plainLanguageTypeKey(file.oeil_procedure_ref) && (
          <div className="tracked-file-card__plain-type">
            {t(`myFilesTab.${plainLanguageTypeKey(file.oeil_procedure_ref)}`)}
          </div>
        )}
        {file.is_blocked && (
          <div className="tracked-file-card__blocked">
            <Icon path={mdiAlertCircleOutline} size={0.7} />
            {t('myFilesTab.blocked')}
          </div>
        )}
        {amendmentCount !== undefined && amendmentCount > 0 && (
          <div className="tracked-file-card__amendment-badge">
            <Icon path={mdiPencilOutline} size={0.6} />
            {t('myFilesTab.amendments', { count: amendmentCount })}
          </div>
        )}
      </div>

      <h4 className="tracked-file-card__title" onClick={onViewDetail}>
        {file.title}
      </h4>

      <div className="tracked-file-card__meta">
        {file.oeil_procedure_ref && (
          <span className="tracked-file-card__ref">
            {file.oeil_procedure_ref}
          </span>
        )}
        {file.lead_committee && (
          <span className="tracked-file-card__committee">
            <Icon path={mdiAccountGroupOutline} size={0.6} />
            {file.lead_committee}
          </span>
        )}
        {file.days_in_current_status && (
          <span className="tracked-file-card__days">
            <Icon path={mdiClockOutline} size={0.6} />
            {t('myFilesTab.daysInStatus', { n: file.days_in_current_status })}
          </span>
        )}
      </div>

      <div className="tracked-file-card__actions">
        <button
          className="tracked-file-card__action-btn tracked-file-card__action-btn--primary"
          onClick={onViewDetail}
        >
          <Icon path={mdiFileDocumentOutline} size={0.7} />
          {t('myFilesTab.viewDetails')}
        </button>
        <button
          className="tracked-file-card__action-btn tracked-file-card__action-btn--amendator"
          onClick={onDraftAmendment}
          title={t('myFilesTab.openInAmendator')}
        >
          <Icon path={mdiPencilOutline} size={0.7} />
          {t('myFilesTab.draftAmendment')}
        </button>
        {onMepAmendments && file.oeil_procedure_ref && (
          <button
            className="tracked-file-card__action-btn"
            onClick={onMepAmendments}
          >
            <Icon path={mdiAccountGroupOutline} size={0.7} />
            {t('amendmentsTab.mepAmendments')}
          </button>
        )}
        {file.oeil_procedure_ref && getDeepDiveForProcedure(file.oeil_procedure_ref) && (
          <a
            href={getDeepDiveUrl(getDeepDiveForProcedure(file.oeil_procedure_ref)!, 'en')}
            target="_blank"
            rel="noopener noreferrer"
            className="tracked-file-card__action-btn tracked-file-card__action-btn--deep-dive"
          >
            <Icon path={mdiBookOpenPageVariantOutline} size={0.7} />
            {t('myFilesTab.deepDive')}
          </a>
        )}
        {oeilUrl && (
          <a
            href={oeilUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="tracked-file-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            {t('myFilesTab.oeil')}
          </a>
        )}
        {eultUrl && (
          <a
            href={eultUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="tracked-file-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            {t('myFilesTab.euLawTracker')}
          </a>
        )}
        {regDelUrl && (
          <a
            href={regDelUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="tracked-file-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            {t('myFilesTab.regDel')}
          </a>
        )}
        <button
          className="tracked-file-card__action-btn tracked-file-card__action-btn--danger"
          onClick={onUntrack}
        >
          <Icon path={mdiTrashCanOutline} size={0.7} />
          {t('myFilesTab.untrack')}
        </button>
      </div>

      <div className="tracked-file-card__footer">
        <span className="tracked-file-card__tracked-since">
          {t('myFilesTab.trackingSince', { date: new Date(file.tracked_since).toLocaleDateString() })}
        </span>
      </div>
    </div>
  );
};

// Committee Work Card Component
interface CommitteeWorkCardProps {
  item: CommitteeWorkItem;
  isJunkTitle?: boolean;
  isTracked?: boolean;
  onViewDetail?: () => void;
  onTrack?: () => void;
  onUntrack?: () => void;
  onMepAmendments?: () => void;
}

const CommitteeWorkCard = ({ item, isJunkTitle, isTracked, onViewDetail, onTrack, onUntrack, onMepAmendments }: CommitteeWorkCardProps) => {
  const { t } = useTranslation();
  const procedureInfo = PROCEDURE_TYPE_INFO[item.procedure_type] || { name: item.procedure_type, color: '#6b7280', score: 0 };
  const statusInfo = STATUS_INFO[item.status] || { name: item.status, color: '#9ca3af' };
  // Plain-language family ("New EU law", "Resolution", ...) for the prominent
  // badge; the raw OEIL code stays as the tooltip. null = no plain family.
  const kindKey = plainLanguageTypeKey(item.procedure_ref);
  const kindLabel = kindKey ? t(`myFilesTab.${kindKey}`) : procedureInfo.name;
  const showStatus = item.status && item.status !== 'unknown';
  // Graceful fallback when the scraper left a junk title: show the plain kind
  // and committee rather than the garbage string.
  const displayTitle = isJunkTitle
    ? t('myFilesTab.committeeFallbackTitle', { kind: kindLabel, ref: item.procedure_ref })
    : item.title;

  const oeilUrl = item.oeil_url || (item.procedure_ref
    ? `https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${encodeURIComponent(item.procedure_ref)}`
    : null
  );
  const eultUrl = item.procedure_ref ? getEultUrl(item.procedure_ref) : null;
  const regDelUrl = item.procedure_ref ? getRegDelUrl(item.procedure_ref) : null;

  return (
    <div className="committee-work-card">
      <div className="committee-work-card__header">
        <span
          className="committee-work-card__procedure-type"
          style={{ backgroundColor: procedureInfo.color }}
          title={`${procedureInfo.name} (${item.procedure_type})`}
        >
          {kindLabel}
        </span>
        {showStatus && (
          <span
            className="committee-work-card__status"
            style={{ backgroundColor: statusInfo.color }}
          >
            {statusInfo.name}
          </span>
        )}
      </div>

      <h4
        className="committee-work-card__title"
        onClick={onViewDetail}
        style={onViewDetail ? { cursor: 'pointer' } : undefined}
      >
        {displayTitle}
      </h4>

      <div className="committee-work-card__meta">
        <span className="committee-work-card__ref">
          {item.procedure_ref}
        </span>
        {item.rapporteur_name && (
          <span className="committee-work-card__rapporteur">
            <Icon path={mdiAccountTieOutline} size={0.6} />
            {item.rapporteur_name}
          </span>
        )}
        <span className="committee-work-card__relevance" title={t('myFilesTab.score', { n: item.relevance_score })}>
          {t('myFilesTab.score', { n: item.relevance_score })}
        </span>
      </div>

      <div className="committee-work-card__actions">
        {onViewDetail && (
          <button
            type="button"
            className="committee-work-card__action-btn committee-work-card__action-btn--primary"
            onClick={onViewDetail}
          >
            <Icon path={mdiFileDocumentOutline} size={0.7} />
            {t('myFilesTab.viewDetails')}
          </button>
        )}
        {onMepAmendments && (
          <button
            type="button"
            className="committee-work-card__action-btn"
            onClick={onMepAmendments}
          >
            <Icon path={mdiAccountGroupOutline} size={0.7} />
            {t('amendmentsTab.mepAmendments')}
          </button>
        )}
        {isTracked ? (
          onUntrack && (
            <button
              type="button"
              className="committee-work-card__action-btn committee-work-card__action-btn--danger"
              onClick={onUntrack}
            >
              <Icon path={mdiTrashCanOutline} size={0.7} />
              {t('myFilesTab.untrack')}
            </button>
          )
        ) : (
          onTrack && (
            <button
              type="button"
              className="committee-work-card__action-btn committee-work-card__action-btn--track"
              onClick={onTrack}
            >
              <Icon path={mdiPlaylistPlus} size={0.7} />
              {t('myFilesTab.track')}
            </button>
          )
        )}
        {oeilUrl && (
          <a
            href={oeilUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="committee-work-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            {t('myFilesTab.oeil')}
          </a>
        )}
        {eultUrl && (
          <a
            href={eultUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="committee-work-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            {t('myFilesTab.euLawTracker')}
          </a>
        )}
        {regDelUrl && (
          <a
            href={regDelUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="committee-work-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            {t('myFilesTab.regDel')}
          </a>
        )}
        {item.ep_page_url && (
          <a
            href={item.ep_page_url}
            target="_blank"
            rel="noopener noreferrer"
            className="committee-work-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            {t('myFilesTab.epPage')}
          </a>
        )}
      </div>
    </div>
  );
};
