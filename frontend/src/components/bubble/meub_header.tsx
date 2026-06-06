// frontend/src/components/bubble/meub_header.tsx
//
// The canonical My EU Bubble content-area header. One structure, one style, used
// by every sub-feature so the headers read consistently: an accent-coloured icon
// on the left, an h2 title (1.5rem, #0f172a) with a muted subtitle, and an
// optional right-hand "aside" slot for each tab's own count chip / toggles /
// action buttons (the per-tab uniqueness is preserved there + via the icon
// colour). Bespoke tabs (Comparator, Legislative Train) keep their flourish by
// passing `titleClassName` / `accent`.
import type { ReactNode } from 'react';
import Icon from '@mdi/react';
import './meub_header.css';

export function MeubHeader({ icon, accent, title, subtitle, aside, titleClassName }: {
  icon: string;
  accent?: string;            // icon colour — each tab's signature accent
  title: ReactNode;
  subtitle?: ReactNode;
  aside?: ReactNode;          // right-side count chip / controls / actions
  titleClassName?: string;    // optional flourish (e.g. gradient title)
}) {
  return (
    <header className="meub-head">
      <div className="meub-head__lead">
        <span className="meub-head__icon" style={accent ? { color: accent } : undefined}>
          <Icon path={icon} size={1.05} />
        </span>
        <div className="meub-head__text">
          <h2 className={titleClassName ? `meub-head__title ${titleClassName}` : 'meub-head__title'}>{title}</h2>
          {subtitle != null && subtitle !== '' && <p className="meub-head__subtitle">{subtitle}</p>}
        </div>
      </div>
      {aside != null && <div className="meub-head__aside">{aside}</div>}
    </header>
  );
}

export default MeubHeader;
