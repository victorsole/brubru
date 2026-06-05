/**
 * Document Editor — full-screen, Word-like WYSIWYG editor for My Documents (Phase 1).
 *
 * Markdown stays canonical: the doc's markdown is parsed into TipTap on open, and
 * serialised back to markdown on save (so Chat, the memory layer and export are
 * untouched). Text formatting only in this phase — inline images and the Mistral AI
 * co-writer arrive in Phases 2 and 3 (see docs/new_format/07_my_documents_editor_build_plan.md).
 *
 * Save / "Save as new version" delegate to the parent via onSave, reusing the existing
 * updateDocument + /version flow.
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { useEditor, EditorContent, BubbleMenu, type Editor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Image from '@tiptap/extension-image';
import Table from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';
import Placeholder from '@tiptap/extension-placeholder';
import { Markdown } from 'tiptap-markdown';
import { marked } from 'marked';
import { useAuth } from '../../hooks/use_auth';
import Icon from '@mdi/react';
import {
  mdiFormatBold,
  mdiFormatItalic,
  mdiFormatStrikethrough,
  mdiFormatHeader1,
  mdiFormatHeader2,
  mdiFormatHeader3,
  mdiFormatListBulleted,
  mdiFormatListNumbered,
  mdiFormatQuoteClose,
  mdiLinkVariant,
  mdiLinkOff,
  mdiTable,
  mdiMinus,
  mdiUndo,
  mdiRedo,
  mdiClose,
  mdiContentSave,
  mdiContentSavePlus,
  mdiImagePlusOutline,
} from '@mdi/js';
import type { UserDocument } from '../../hooks/use_bubble';
import './document_editor.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/** Upload an image to the editor asset store; returns its absolute URL or null. */
async function uploadEditorImage(file: File, token: string | null): Promise<string | null> {
  const fd = new FormData();
  fd.append('file', file);
  try {
    const res = await fetch(`${API_BASE_URL}/api/documents/assets`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    });
    if (!res.ok) return null;
    const data = await res.json();
    return (data.url as string) || null;
  } catch {
    return null;
  }
}

interface DocumentEditorProps {
  doc: UserDocument;
  onClose: () => void;
  /** Persist edits. asNewVersion=true routes through the /version flow. */
  onSave: (title: string, markdown: string, asNewVersion: boolean) => Promise<void>;
}

interface ToolbarButtonProps {
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  icon: string;
  label: string;
}

const ToolbarButton = ({ onClick, active, disabled, icon, label }: ToolbarButtonProps) => (
  <button
    type="button"
    className={`document-editor__tool ${active ? 'document-editor__tool--active' : ''}`}
    onMouseDown={(e) => e.preventDefault()}
    onClick={onClick}
    disabled={disabled}
    title={label}
    aria-label={label}
    aria-pressed={active}
  >
    <Icon path={icon} size={0.75} />
  </button>
);

const AI_ACTIONS = ['rewrite', 'shorten', 'expand', 'formalise', 'simplify', 'continue'] as const;
const AI_LANGS: Array<[string, string]> = [
  ['es', 'ES'],
  ['ca', 'CA'],
  ['fr', 'FR'],
  ['it', 'IT'],
  ['nl', 'NL'],
  ['en', 'EN'],
];

/** Selection bubble menu: Mistral-first AI actions on the selected passage. */
const AiBubble = ({ editor, token }: { editor: Editor; token: string | null }) => {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [translateMode, setTranslateMode] = useState(false);

  const run = async (action: string, targetLanguage?: string) => {
    const { from, to } = editor.state.selection;
    const text = editor.state.doc.textBetween(from, to, '\n');
    if (!text.trim()) return;
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/documents/ai-assist`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ action, text, target_language: targetLanguage }),
      });
      if (!res.ok) {
        alert(t('documentEditor.aiFailed'));
        return;
      }
      const data = await res.json();
      const result = (data.result || '').trim();
      if (!result) return;
      // Render the returned markdown to HTML so formatting (bold, lists, headings)
      // comes through instead of literal "**" syntax.
      const html = marked.parse(result, { async: false }) as string;
      if (action === 'continue') {
        editor.chain().focus().insertContentAt(to, html).run();
      } else {
        editor.chain().focus().insertContentAt({ from, to }, html).run();
      }
    } catch {
      alert(t('documentEditor.aiFailed'));
    } finally {
      setBusy(false);
      setTranslateMode(false);
    }
  };

  return (
    <BubbleMenu
      editor={editor}
      tippyOptions={{ duration: 100, maxWidth: 'none', placement: 'top' }}
      shouldShow={({ editor: ed, from, to }) => from !== to && !ed.isActive('image')}
    >
      <div className="document-editor__ai-bubble">
        {busy ? (
          <span className="document-editor__ai-busy">{t('documentEditor.aiThinking')}</span>
        ) : translateMode ? (
          <>
            <span className="document-editor__ai-label">{t('documentEditor.translateTo')}</span>
            {AI_LANGS.map(([code, label]) => (
              <button
                key={code}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => run('translate', code)}
              >
                {label}
              </button>
            ))}
            <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => setTranslateMode(false)}>
              <Icon path={mdiClose} size={0.6} />
            </button>
          </>
        ) : (
          <>
            {AI_ACTIONS.map((a) => (
              <button
                key={a}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => run(a)}
              >
                {t(`documentEditor.ai_${a}`)}
              </button>
            ))}
            <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => setTranslateMode(true)}>
              {t('documentEditor.ai_translate')}
            </button>
          </>
        )}
      </div>
    </BubbleMenu>
  );
};

const Toolbar = ({ editor, onPickImage }: { editor: Editor; onPickImage: () => void }) => {
  const { t } = useTranslation();

  const setLink = () => {
    const previous = editor.getAttributes('link').href as string | undefined;
    const url = window.prompt(t('documentEditor.linkPrompt'), previous || 'https://');
    if (url === null) return;
    if (url === '') {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
  };

  return (
    <div className="document-editor__toolbar" role="toolbar" aria-label={t('documentEditor.toolbar')}>
      <ToolbarButton
        icon={mdiFormatBold}
        label={t('documentEditor.bold')}
        active={editor.isActive('bold')}
        onClick={() => editor.chain().focus().toggleBold().run()}
      />
      <ToolbarButton
        icon={mdiFormatItalic}
        label={t('documentEditor.italic')}
        active={editor.isActive('italic')}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      />
      <ToolbarButton
        icon={mdiFormatStrikethrough}
        label={t('documentEditor.strike')}
        active={editor.isActive('strike')}
        onClick={() => editor.chain().focus().toggleStrike().run()}
      />
      <span className="document-editor__tool-sep" />
      <ToolbarButton
        icon={mdiFormatHeader1}
        label={t('documentEditor.h1')}
        active={editor.isActive('heading', { level: 1 })}
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
      />
      <ToolbarButton
        icon={mdiFormatHeader2}
        label={t('documentEditor.h2')}
        active={editor.isActive('heading', { level: 2 })}
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
      />
      <ToolbarButton
        icon={mdiFormatHeader3}
        label={t('documentEditor.h3')}
        active={editor.isActive('heading', { level: 3 })}
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
      />
      <span className="document-editor__tool-sep" />
      <ToolbarButton
        icon={mdiFormatListBulleted}
        label={t('documentEditor.bulletList')}
        active={editor.isActive('bulletList')}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
      />
      <ToolbarButton
        icon={mdiFormatListNumbered}
        label={t('documentEditor.orderedList')}
        active={editor.isActive('orderedList')}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
      />
      <ToolbarButton
        icon={mdiFormatQuoteClose}
        label={t('documentEditor.blockquote')}
        active={editor.isActive('blockquote')}
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
      />
      <span className="document-editor__tool-sep" />
      <ToolbarButton
        icon={mdiLinkVariant}
        label={t('documentEditor.link')}
        active={editor.isActive('link')}
        onClick={setLink}
      />
      <ToolbarButton
        icon={mdiLinkOff}
        label={t('documentEditor.unlink')}
        disabled={!editor.isActive('link')}
        onClick={() => editor.chain().focus().unsetLink().run()}
      />
      <ToolbarButton
        icon={mdiTable}
        label={t('documentEditor.table')}
        onClick={() =>
          editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
        }
      />
      <ToolbarButton icon={mdiImagePlusOutline} label={t('documentEditor.image')} onClick={onPickImage} />
      <ToolbarButton
        icon={mdiMinus}
        label={t('documentEditor.horizontalRule')}
        onClick={() => editor.chain().focus().setHorizontalRule().run()}
      />
      <span className="document-editor__tool-sep" />
      <ToolbarButton
        icon={mdiUndo}
        label={t('documentEditor.undo')}
        disabled={!editor.can().undo()}
        onClick={() => editor.chain().focus().undo().run()}
      />
      <ToolbarButton
        icon={mdiRedo}
        label={t('documentEditor.redo')}
        disabled={!editor.can().redo()}
        onClick={() => editor.chain().focus().redo().run()}
      />
    </div>
  );
};

export const DocumentEditor = ({ doc, onClose, onSave }: DocumentEditorProps) => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [title, setTitle] = useState(doc.title);
  const [saving, setSaving] = useState<null | 'save' | 'version'>(null);
  const editorRef = useRef<Editor | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Upload an image file and insert it at the cursor (serialises to markdown ![](url)).
  const uploadAndInsert = useCallback(
    async (file: File) => {
      if (!file.type.startsWith('image/')) return;
      const url = await uploadEditorImage(file, token);
      if (url) editorRef.current?.chain().focus().setImage({ src: url }).run();
      else alert(t('documentEditor.imageFailed'));
    },
    [token, t],
  );

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit,
      Link.configure({ openOnClick: false, autolink: true }),
      Image.configure({ allowBase64: false }),
      Table.configure({ resizable: false }),
      TableRow,
      TableHeader,
      TableCell,
      Placeholder.configure({ placeholder: t('documentEditor.placeholder') }),
      Markdown.configure({ html: false, transformPastedText: true, linkify: false }),
    ],
    content: doc.content || '',
    editorProps: {
      handlePaste: (_view, event) => {
        const items = event.clipboardData?.items;
        if (!items) return false;
        for (let i = 0; i < items.length; i++) {
          if (items[i].type.startsWith('image/')) {
            const f = items[i].getAsFile();
            if (f) {
              void uploadAndInsert(f);
              return true;
            }
          }
        }
        return false;
      },
      handleDrop: (_view, event) => {
        const f = (event as DragEvent).dataTransfer?.files?.[0];
        if (f && f.type.startsWith('image/')) {
          void uploadAndInsert(f);
          event.preventDefault();
          return true;
        }
        return false;
      },
    },
  });

  useEffect(() => {
    editorRef.current = editor;
  }, [editor]);

  const handleSave = async (asNewVersion: boolean) => {
    if (!editor) return;
    setSaving(asNewVersion ? 'version' : 'save');
    try {
      const markdown = editor.storage.markdown.getMarkdown();
      await onSave(title.trim() || t('documentEditor.untitled'), markdown, asNewVersion);
      if (!asNewVersion) onClose();
    } catch (err) {
      console.error('[DocumentEditor] save failed:', err);
      alert(t('documentEditor.saveFailed'));
    } finally {
      setSaving(null);
    }
  };

  const wordCount = editor ? editor.getText().trim().split(/\s+/).filter(Boolean).length : 0;

  return createPortal(
    <div className="document-editor" role="dialog" aria-modal="true" aria-label={t('documentEditor.title')}>
      <div className="document-editor__bar">
        <button className="document-editor__close" onClick={onClose} aria-label={t('documentEditor.close')}>
          <Icon path={mdiClose} size={0.9} />
        </button>
        <input
          className="document-editor__title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={t('documentEditor.titlePlaceholder')}
          aria-label={t('documentEditor.titleLabel')}
        />
        <span className="document-editor__count">
          {wordCount} {t('documentsTab.wordsLabel')}
        </span>
        <div className="document-editor__bar-actions">
          <button
            className="document-editor__btn document-editor__btn--ghost"
            onClick={() => handleSave(true)}
            disabled={saving !== null}
            title={t('documentEditor.saveVersionHint')}
          >
            <Icon path={mdiContentSavePlus} size={0.7} />
            {t('documentEditor.saveAsVersion')}
          </button>
          <button
            className="document-editor__btn document-editor__btn--primary"
            onClick={() => handleSave(false)}
            disabled={saving !== null}
          >
            <Icon path={mdiContentSave} size={0.7} />
            {saving === 'save' ? t('documentEditor.saving') : t('documentEditor.save')}
          </button>
        </div>
      </div>

      {editor && <Toolbar editor={editor} onPickImage={() => fileInputRef.current?.click()} />}
      {editor && <AiBubble editor={editor} token={token} />}

      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/gif,image/webp"
        style={{ display: 'none' }}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void uploadAndInsert(f);
          e.target.value = '';
        }}
      />

      <div className="document-editor__canvas">
        <div className="document-editor__page">
          <EditorContent editor={editor} className="document-editor__content" />
        </div>
      </div>
    </div>,
    document.body,
  );
};
